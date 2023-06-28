from __future__ import annotations

import json
import logging
from typing import Optional

import discord
from discord.ext import commands

from core import Bot, Cog, Context

from .cog_utils import EmbedBuilder, EmbedCancel, EmbedSend

log = logging.getLogger("misc")


class Misc(Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.command(name="embed")
    async def embed_command(
        self,
        ctx: Context,
        channel: Optional[discord.TextChannel] = None,
        *,
        data: Optional[str] = None,
    ):
        """A nice command to make custom embeds, from `JSON`. Provided it is in the format that Discord expects it to be in.
        You can find the documentation on `https://discord.com/developers/docs/resources/channel#embed-object`.
        """
        channel = channel or ctx.channel  # type: ignore
        if channel.permissions_for(ctx.author).embed_links:  # type: ignore
            if not data:
                view = EmbedBuilder(ctx, items=[EmbedSend(channel), EmbedCancel()])  # type: ignore
                await view.rendor()
                return
            try:
                await channel.send(embed=discord.Embed.from_dict(json.loads(str(data))))  # type: ignore
            except Exception as e:
                await ctx.send(
                    f"{ctx.author.mention} you didn't provide the proper json object. Error raised: {e}"
                )
        else:
            await ctx.send(
                f"{ctx.author.mention} you don't have Embed Links permission in {channel.mention}"  # type: ignore
            )


async def setup(bot: Bot) -> None:
    log.info("Loading Misc cog...")
    await bot.add_cog(Misc(bot))
