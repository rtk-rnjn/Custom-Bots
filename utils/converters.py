"""MIT License.

Copyright (c) 2023 Ritik Ranjan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial, wraps
from typing import TYPE_CHECKING, Any
from collections.abc import Callable

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from core import Context

__all__ = (
    "can_execute_action",
    "convert_bool",
    "MemberID",
    "MessageID",
    "RoleID",
    "BannedMember",
    "ActionReason",
    "ToAsync",
)


def can_execute_action(  # pylint: disable=too-many-return-statements
    ctx: Context,
    mod: discord.Member,
    target: discord.Member | discord.Role | discord.User | None,
) -> bool | None:
    """Checks if the moderator can execute the action on the target."""
    assert ctx.guild

    if ctx.author == ctx.guild.owner:
        return True

    if mod == ctx.guild.owner:
        return False

    if mod == target:
        return False

    if isinstance(target, discord.Role):
        return mod.top_role.position > target.position

    if isinstance(target, discord.Member):
        if mod.top_role == target.top_role:
            return False

        return mod.top_role >= target.top_role

    return None


def convert_bool(entiry: str) -> bool | None:
    """Converts a string to a boolean value."""
    yes = {
        "yes",
        "y",
        "true",
        "t",
        "1",
        "enable",
        "on",
        "active",
        "activated",
        "ok",
        "accept",
        "agree",
    }
    if entiry.lower() in yes:
        return True

    no = {
        "no",
        "n",
        "false",
        "f",
        "0",
        "disable",
        "off",
        "deactive",
        "deactivated",
        "cancel",
        "deny",
        "disagree",
    }

    return False if entiry.lower() in no else None


class MemberID(commands.Converter):  # pylint: disable=too-few-public-methods
    """A converter that handles user mentions and user IDs."""

    async def convert(self, ctx: Context, argument: str) -> discord.Member | None:
        """Convert a user mention or ID to a member object."""
        assert ctx.guild is not None and isinstance(ctx.author, discord.Member)
        try:
            m: discord.Member | None = await commands.MemberConverter().convert(ctx, argument)  # type: ignore
        except commands.BadArgument:
            try:
                member_id = int(argument, base=10)
            except ValueError:
                raise commands.BadArgument(f"{argument} is not a valid member or member ID.") from None

            m: discord.Member | discord.User | None = await ctx.bot.get_or_fetch_member(ctx.guild, member_id)
            if m is None:
                # hackban case
                return type(  # type: ignore
                    "_Hackban",
                    (),
                    {"id": member_id, "__str__": lambda s: f"Member ID {s.id}"},
                )()

        if not can_execute_action(ctx, ctx.author, m):
            raise commands.BadArgument(
                f"{ctx.author.mention} can not {ctx.command.qualified_name} the {m}, as the their's role is above you",  # type: ignore
            )
        return m  # type: ignore


class MessageID(commands.Converter):  # pylint: disable=too-few-public-methods
    """A converter that handles message mentions and message IDs."""

    async def convert(self, ctx: Context, argument: str) -> discord.Message | None:
        """Convert the argument to a message object."""
        assert ctx.guild is not None
        try:
            message: discord.Message | None = await commands.MessageConverter().convert(ctx, argument)  # type: ignore
        except commands.BadArgument:
            pass
        else:
            return message
        try:
            message_id = int(argument, base=10)
        except ValueError:
            raise commands.BadArgument(f"{argument} is not a valid message or message ID.") from None

        message: discord.Message | None = discord.utils.get(ctx.bot.cached_messages, id=message_id)  # type: ignore
        if message is None:
            try:
                message: discord.Message | None = await ctx.bot.get_or_fetch_message(ctx.channel, message_id)  # type: ignore
            except discord.NotFound:
                raise commands.BadArgument(f"{argument} is not a valid message or message ID.") from None
        return message


class RoleID(commands.Converter):  # pylint: disable=too-few-public-methods
    """A converter that handles role mentions and role IDs."""

    async def convert(self, ctx: Context, argument: str) -> discord.Role | None:
        """Convert the argument to a role object."""
        assert ctx.guild is not None and isinstance(ctx.author, discord.Member)
        try:
            role: discord.Role | None = await commands.RoleConverter().convert(ctx, argument)
        except commands.BadArgument:
            try:
                role_id = int(argument, base=10)
            except ValueError:
                raise commands.BadArgument(f"{argument} is not a valid role or role ID.") from None

            role: discord.Role | None = discord.utils.get(ctx.guild.roles, id=role_id)
            if role is None:
                raise commands.BadArgument(f"{argument} is not a valid role or role ID.") from None

        if not can_execute_action(ctx, ctx.author, role):
            raise commands.BadArgument(
                f"{ctx.author.mention} can not {ctx.command.qualified_name} the {role}, as the their's role is above you",  # type: ignore
            )
        return role


class BannedMember(commands.Converter):  # pylint: disable=too-few-public-methods
    """A coverter that is used for fetching Banned Member of Guild."""

    async def convert(self, ctx: Context, argument: str) -> discord.User | None:
        """Convert the argument to a banned member."""
        assert ctx.guild is not None

        if argument.isdigit():
            member_id = int(argument, base=10)
            try:
                ban_entry = await ctx.guild.fetch_ban(discord.Object(id=member_id))
                return ban_entry.user
            except discord.NotFound:
                raise commands.BadArgument("User Not Found! Probably this member has not been banned before.") from None

        async for entry in ctx.guild.bans():
            if argument in (entry.user.name, str(entry.user)):
                return entry.user
            if str(entry.user) == argument:
                return entry.user

        raise commands.BadArgument("User Not Found! Probably this member has not been banned before.") from None


class ActionReason(commands.Converter):  # pylint: disable=too-few-public-methods
    """Action reason converter."""

    async def convert(self, ctx: Context, argument: str | None = None) -> str:
        """Convert the argument to a action string."""
        ret = f"{ctx.author} ({ctx.author.id}) -> {argument or 'no reason provided'}"

        length = 0 if argument is None else len(argument)
        if len(ret) > 512:
            reason_max = 512 - len(ret) + length
            raise commands.BadArgument(f"Reason is too long ({length}/{reason_max})")
        return ret


class ToAsync:  # pylint: disable=too-few-public-methods
    """Converts a blocking function to an async function."""

    def __init__(self, *, executor: ThreadPoolExecutor | None = None) -> None:
        self.executor = executor or ThreadPoolExecutor()

    def __call__(self, blocking: Callable[..., Any]) -> Callable[..., Any]:  # noqa: D102
        @wraps(blocking)
        async def wrapper(*args, **kwargs) -> Any:
            return await asyncio.get_event_loop().run_in_executor(self.executor, partial(blocking, *args, **kwargs))

        return wrapper
