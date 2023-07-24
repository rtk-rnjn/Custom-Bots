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

from typing import Optional

import discord
from discord.ext import commands

from core import Bot, Cog, Context  # pylint: disable=import-error


class Config(Cog):  # pylint: disable=too-few-public-methods
    """A cog for the bot's configuration."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.group(name="set", invoke_without_command=True)
    async def _set(self, ctx: Context) -> None:
        """To set the bot's configuration."""
        if not ctx.invoked_subcommand:
            await ctx.send_help(ctx.command)

    @_set.command(name="prefix")
    @commands.is_owner()
    async def _prefix(self, ctx: Context, *, prefix: str) -> None:
        """To set the bot's prefix."""
        self.bot.config.set_prefix(prefix)
        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        await self.bot.mongo.customBots.mainConfigCollection.update_one(
            {"id": self.bot.config.id},
            {"$set": {"prefix": prefix}},
        )

    @_set.command(name="suggestion", aliases=["suggest"])
    @commands.has_permissions(manage_guild=True)
    async def _suggestion(self, ctx: Context, channel: Optional[discord.TextChannel] = None) -> None:
        """To set the bot's suggestion channel."""
        ch = channel or ctx.channel

        self.bot.config.set_suggestion_channel(ch.id)
        await self.bot.config.update_to_db()

        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @_set.command(name="modlog")
    @commands.has_permissions(manage_guild=True)
    async def _modlog(self, ctx: Context, channel: Optional[discord.TextChannel] = None) -> None:
        """To set the bot's modlog channel."""
        ch = channel or ctx.channel

        self.bot.config.set_modlog_channel(ch.id)
        await self.bot.config.update_to_db()

        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @commands.group(name="unset", invoke_without_command=True)
    async def _unset(self, ctx: Context) -> None:
        """To unset the bot's configuration."""
        if not ctx.invoked_subcommand:
            await ctx.send_help(ctx.command)

    @_unset.command(name="suggestion", aliases=["suggest"])
    @commands.has_permissions(manage_guild=True)
    async def _unsuggestion(self, ctx: Context) -> None:
        """To unset the bot's suggestion channel."""
        self.bot.config.set_suggestion_channel(None)
        await self.bot.config.update_to_db()

        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @_unset.command(name="modlog")
    @commands.has_permissions(manage_guild=True)
    async def _unmodlog(self, ctx: Context) -> None:
        """To unset the bot's modlog channel."""
        self.bot.config.set_modlog_channel(None)
        await self.bot.config.update_to_db()

        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")


async def setup(bot: Bot) -> None:
    """To load the cog."""
    await bot.add_cog(Config(bot))
