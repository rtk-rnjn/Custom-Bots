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

import logging
from typing import Literal, Optional

import discord
from discord.ext import commands

from core import Bot, Cog, Context  # pylint: disable=import-error

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
        status: Optional[Literal["online", "dnd", "idle"]] = "dnd",
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
        await ctx.bot.change_presence(
            activity=discord.Activity(name=media, type=p_types[ctx.invoked_with]),
            status=discord.Status(status),
        )
        log.info("presence changed to %s %s", ctx.invoked_with, media)
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
        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        await self.bot.mongo.customBots.mainConfigCollection.update_one(
            {"id": self.bot.config.id}, {"$set": {"prefix": prefix}},
        )


async def setup(bot: Bot) -> None:
    """Load the Owner cog."""
    await bot.add_cog(Owner(bot))
