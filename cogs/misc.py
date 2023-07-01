"""
MIT License

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

import json
import logging
from typing import Optional

import discord
from discord.ext import commands

from core import Bot, Cog, Context

from .cog_utils import EmbedBuilder, EmbedCancel, EmbedSend

log = logging.getLogger("misc")


PERMANENT_INVITE = "https://discord.gg/Zk4H4K9Z4e"


class Misc(Cog):
    """Miscellaneous commands."""

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
        """A nice command to make custom embeds.

        Embed can also be created from JSON object.
        Example:
        `[p]embed {"title": "Hello", "description": "World!"}`
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
        assert self.bot.user

        main_guild = self.bot.get_guild(self.bot.config.guild_id)  # type: discord.Guild  # type: ignore
        owner = self.bot.get_user(self.bot.config.owner_id)  # type: discord.User  # type: ignore

        await ctx.reply(
            embed=discord.Embed(
                title="This bot is not intended to be used in multiple servers.",
                description=(
                    "You can still add the bot on your server, but it won't work.\n"
                    f"> - Bot is made to work in **[{main_guild.name}]({PERMANENT_INVITE})** (ID: `{main_guild.id}`)\n"
                    f"> - If you want to use the bot in your server, please consider asking **[{owner.mention} - `{owner}`]** (`{owner.id}`)\n"
                ),
                url=discord.utils.oauth_url(self.bot.user.id, permissions=discord.Permissions(0)),
            )
            .set_thumbnail(url=self.bot.user.display_avatar.url)
            .set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        )


async def setup(bot: Bot) -> None:
    await bot.add_cog(Misc(bot))
