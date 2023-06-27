from __future__ import annotations

import discord
from discord.ext import commands

from core import Bot, Cog, Context


class Meta(Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.command(name="ping")
    async def ping(self, ctx: Context) -> None:
        """Returns the bot's latency."""
        await ctx.send(f"Pong! {round(self.bot.latency * 1000)}ms")

    @commands.command(name="uptime")
    async def uptime(self, ctx: Context) -> None:
        """Returns the bot's uptime."""
        relative_discord_time = discord.utils.format_dt(self.bot.uptime, style="R")

        await ctx.send(f"Uptime: {relative_discord_time}")


async def setup(bot: Bot) -> None:
    await bot.add_cog(Meta(bot))
