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

import difflib
import inspect
import logging
from typing import Literal

import arrow
import discord
from colorama import Fore
from discord.ext import commands
from jishaku.paginators import PaginatorInterface

from core import Bot, Cog, Context  # pylint: disable=import-error

from .cog_utils import AuditFlag

log = logging.getLogger("owner")


class Owner(Cog):
    """Owner only commands."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: Context) -> bool:
        """Check if the user is owner of the bot."""
        if await self.bot.is_owner(ctx.author):
            return True

        await ctx.reply("You are not the owner of this bot.")
        return False

    @commands.command(aliases=["streaming", "listening", "watching"])
    async def playing(
        self,
        ctx: Context,
        status: Literal["online", "dnd", "idle"] | None = "dnd",
        *,
        media: str,
    ) -> None:
        """Update bot presence accordingly to invoke command.

        Examples
        --------
        `- [p]playing online Hello World!`
        `- [p]listening dnd Hello World!`

        The default status is dnd. Command can also be used as:
        `- [p]playing Hello World!`
        """
        p_types = {"playing": 0, "streaming": 1, "listening": 2, "watching": 3, None: 0}
        await self.bot.change_presence(
            activity=discord.Activity(name=media, type=p_types[ctx.invoked_with]),
            status=discord.Status(status),
        )
        log.info("presence changed to %s %s", ctx.invoked_with, media)
        await self.bot.log_bot_event(
            content=f"Presence changed to {ctx.invoked_with} {media}",
        )
        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @commands.command()
    async def prefix(self, ctx: Context, *, prefix: str) -> None:
        """Change bot prefix.

        Example:
        -------
        `[p]prefix !`

        Note:
        ----
        - You must be owner of the bot to use this command.
        - The prefix can be any string.
        - Prefix will be case insensitive.
        """
        self.bot.config.set_prefix(prefix)
        log.info("prefix changed to %s", prefix)
        await self.bot.log_bot_event(content=f"Prefix changed to {prefix}")
        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        await self.bot.mongo.customBots.mainConfigCollection.update_one(
            {"id": self.bot.config.id},
            {"$set": {"prefix": prefix}},
        )

    @commands.command()
    async def shutdown(self, ctx: Context) -> None:
        """Shutdown the bot."""
        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        await self.bot.log_bot_event(content="Bot shutdown")
        await self.bot.close()

    @commands.command()
    async def leave(self, ctx: Context) -> None:
        """Make the bot leave the server."""
        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        await self.bot.log_bot_event(content="Bot left the server")
        await ctx.guild.leave()

    @commands.command(aliases=["audit-log", "auditlogs", "audit-logs"])
    @commands.bot_has_guild_permissions(view_audit_log=True)
    async def auditlog(self, ctx: Context, *, flags: AuditFlag) -> None:
        """To get the audit log of the server, in nice format.

        **Flags:**
        - `--user` or `-u` to get audit logs of a specific user.
        - `--action` or `-a` to get audit logs of a specific action.
        - `--before` or `-b` to get audit logs before a specific date.
        - `--after` or `-a` to get audit logs after a specific date.
        - `--limit` or `-l` to limit the number of audit logs.
        - `--oldest-first` or `-o` to get the oldest audit logs first.
        - `--guild` or `-g` to get audit logs of a specific guild.
        """
        page = commands.Paginator(prefix="```ansi", max_size=1985)

        guild = flags.guild or ctx.guild

        kwargs = {}

        if flags.user:
            kwargs["user"] = flags.user

        kwargs["limit"] = max(flags.limit or 0, 100)
        if flags.action:
            _actions = [ele for ele in dir(discord.AuditLogAction) if not ele.startswith("_")]
            if close_match := difflib.get_close_matches(flags.action, _actions, n=1, cutoff=0.5):
                kwargs["action"] = getattr(discord.AuditLogAction, close_match[0])  # type: ignore

            else:
                msg = f"Action {flags.action} not found."
                raise commands.BadArgument(msg)

        if flags.before:
            kwargs["before"] = flags.before.dt

        if flags.after:
            kwargs["after"] = flags.after.dt

        if flags.oldest_first:
            kwargs["oldest_first"] = flags.oldest_first

        assert guild is not None

        async for entry in guild.audit_logs(**kwargs):
            humanize = arrow.get(entry.created_at, tzinfo="+00:00").humanize()
            dt = entry.created_at.strftime("%Y-%m-%d %H:%M:%S")

            action_name = entry.action.name.replace("_", " ").title()
            if isinstance(entry.target, discord.Member | discord.User):
                target = f"`{entry.target}` ({Fore.MAGENTA}{entry.target.id}{Fore.WHITE})"
            elif isinstance(entry.target, discord.Object):
                target = f"`Deleted Object` ({Fore.MAGENTA}{entry.target.id}{Fore.WHITE})"
            elif entry.target is None:
                target = f"`Unknown Target` ({Fore.MAGENTA}0{Fore.WHITE})"
            else:
                target = f"`{entry.target.__class__.__name__}` ({Fore.MAGENTA}{entry.target.id}{Fore.WHITE})"

            user = (
                f"`{entry.user}` ({Fore.MAGENTA}{entry.user.id}{Fore.WHITE})"
                if entry.user
                else f"`Unknown User` ({Fore.MAGENTA}0{Fore.WHITE})"
            )
            page.add_line(
                inspect.cleandoc(
                    f"""
                    {Fore.CYAN}{dt} ({humanize}) {Fore.WHITE}| {Fore.BLUE}{action_name} {Fore.WHITE}({Fore.MAGENTA}{entry.id}{Fore.WHITE})
                    {Fore.GREEN}Moderator: {Fore.WHITE}{user}
                    {Fore.GREEN}Target   : {Fore.WHITE}{target}
                    """,
                ),
            )
            page.add_line("\n" + f"{Fore.BLACK}-" * 40 + "\n")

        interface = PaginatorInterface(ctx.bot, page, owner=ctx.author)
        await interface.send_to(ctx)


async def setup(bot: Bot) -> None:
    """Load the Owner cog."""
    await bot.add_cog(Owner(bot))
