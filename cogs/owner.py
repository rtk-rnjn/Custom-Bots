from __future__ import annotations

import logging
from typing import Literal, Optional

import discord
from discord.ext import commands

from core import Bot, Cog, Context

log = logging.getLogger("owner")


class Owner(Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: Context) -> bool:
        return await self.bot.is_owner(ctx.author)

    @commands.command(aliases=["streaming", "listening", "watching"], hidden=True)
    async def playing(
        self,
        ctx: Context,
        status: Optional[Literal["online", "dnd", "offline", "idle"]] = "dnd",
        *,
        media: str,
    ):
        """Update bot presence accordingly to invoke command

        This is equivalent to:
        ```py
        p_types = {'playing': 0, 'streaming': 1, 'listening': 2, 'watching': 3}
        await ctx.bot.change_presence(discord.Activity(name=media, type=p_types[ctx.invoked_with]))
        ```
        """
        p_types = {"playing": 0, "streaming": 1, "listening": 2, "watching": 3, None: 0}
        await ctx.bot.change_presence(
            activity=discord.Activity(name=media, type=p_types[ctx.invoked_with]),
            status=discord.Status(status),
        )
        log.info("presence changed to %s %s", ctx.invoked_with, media)
        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
