from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial, wraps
from typing import Any, Callable, Optional, Union

import discord
from discord.ext import commands

from core import Context

__all__ = (
    "can_execute_action",
    "MemberID",
    "BannedMember",
    "ActionReason",
    "ToAsync",
)


def can_execute_action(
    ctx: Context, user: discord.Member, target: discord.Member
) -> bool:
    return (
        user.id in ctx.bot.owner_ids  # type: ignore # owner_ids can not be None
        or user == ctx.guild.owner  # type: ignore # guild can not be None and owner can not be None
        or user.top_role > target.top_role
    )


class MemberID(commands.Converter):
    """A converter that handles user mentions and user IDs."""

    async def convert(self, ctx: Context, argument: str) -> Optional[discord.Member]:
        """Convert a user mention or ID to a member object."""
        assert ctx.guild is not None and isinstance(ctx.author, discord.Member)
        try:
            m: Optional[discord.Member] = await commands.MemberConverter().convert(  # type: ignore
                ctx, argument
            )
        except commands.BadArgument:
            try:
                member_id = int(argument, base=10)
            except ValueError:
                raise commands.BadArgument(
                    f"{argument} is not a valid member or member ID."
                ) from None
            else:
                m: Optional[
                    Union[discord.Member, discord.User]
                ] = await ctx.bot.get_or_fetch_member(ctx.guild, member_id)
                if m is None:
                    # hackban case
                    return type(  # type: ignore
                        "_Hackban",
                        (),
                        {"id": member_id, "__str__": lambda s: f"Member ID {s.id}"},
                    )()

        if not can_execute_action(ctx, ctx.author, m):  # type: ignore
            raise commands.BadArgument(
                f"{ctx.author.mention} can not {ctx.command.qualified_name} the {m}, as the their's role is above you"  # type: ignore
            )
        return m  # type: ignore


class BannedMember(commands.Converter):
    """A coverter that is used for fetching Banned Member of Guild"""

    async def convert(self, ctx: Context, argument: str) -> Optional[discord.User]:
        assert ctx.guild is not None

        if argument.isdigit():
            member_id = int(argument, base=10)
            try:
                ban_entry = await ctx.guild.fetch_ban(discord.Object(id=member_id))
                return ban_entry.user
            except discord.NotFound:
                raise commands.BadArgument(
                    "User Not Found! Probably this member has not been banned before."
                ) from None

        async for entry in ctx.guild.bans():
            if argument in (entry.user.name, str(entry.user)):
                return entry.user
            if str(entry.user) == argument:
                return entry.user

        raise commands.BadArgument(
            "User Not Found! Probably this member has not been banned before."
        ) from None


class ActionReason(commands.Converter):
    """Action reason converter"""

    async def convert(self, ctx: Context, argument: Optional[str] = None) -> str:
        """Convert the argument to a action string"""
        ret = f"{ctx.author} ({ctx.author.id}) -> {argument or 'no reason provided'}"

        LEN = 0 if argument is None else len(argument)
        if len(ret) > 512:
            reason_max = 512 - len(ret) + LEN
            raise commands.BadArgument(f"Reason is too long ({LEN}/{reason_max})")
        return ret


class ToAsync:
    """Converts a blocking function to an async function"""

    def __init__(self, *, executor: Optional[ThreadPoolExecutor] = None) -> None:
        self.executor = executor or ThreadPoolExecutor()

    def __call__(self, blocking) -> Callable[..., Any]:
        @wraps(blocking)
        async def wrapper(*args, **kwargs) -> Any:
            return await asyncio.get_event_loop().run_in_executor(
                self.executor, partial(blocking, *args, **kwargs)
            )

        return wrapper
