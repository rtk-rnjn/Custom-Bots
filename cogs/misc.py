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
                await ctx.send(f"{ctx.author.mention} you didn't provide the proper json object. Error raised: {e}")
        else:
            await ctx.send(
                f"{ctx.author.mention} you don't have Embed Links permission in {channel.mention}"  # type: ignore
            )

    @commands.command(name="invite")
    async def invite_command(self, ctx: Context):
        """Invite the bot to your server."""
        await ctx.reply(
            embed=discord.Embed(
                title="This bot is not intended to be used in multiple servers.",
                description="You can still add the bot on your server, but it won't work.",
                url=discord.utils.oauth_url(self.bot.user.id, permissions=discord.Permissions(0)),
            )
            .set_thumbnail(url=self.bot.user.display_avatar.url)
            .set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        )


async def setup(bot: Bot) -> None:
    await bot.add_cog(Misc(bot))
