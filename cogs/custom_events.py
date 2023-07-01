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

import contextlib
from typing import TYPE_CHECKING, Any

import discord

from core import Bot, Cog

if TYPE_CHECKING:
    from cogs.giveaway import Giveaway

import logging

log = logging.getLogger("custom_events")


class EventCustom(Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.ON_TESTING = False

    @Cog.listener("on_timer_complete")
    async def normal_parser(
        self,
        *,
        embed: dict[str, Any] = None,  # type: ignore
        content: str | None = None,
        dm_notify: bool = False,
        is_todo: bool = False,
        messageChannel: int | None = None,
        messageAuthor: int | None = None,
        messageURL: str | None = None,
        **kwargs: Any,
    ):
        if not content:
            return
        if embed is None:
            embed = {}
        embed: discord.utils.MISSING | discord.Embed = discord.Embed.from_dict(embed) if embed else discord.utils.MISSING

        if (dm_notify or is_todo) and (user := self.bot.get_user(messageAuthor or 0)):
            with contextlib.suppress(discord.Forbidden):
                await user.send(
                    content=f"{user.mention} this is reminder for: **{content}**\n>>> {messageURL}",
                    embed=embed,
                )
            return

        if channel := self.bot.get_channel(messageChannel or 0):
            assert isinstance(channel, discord.abc.Messageable)
            with contextlib.suppress(discord.Forbidden):
                await channel.send(
                    content=f"<@{messageAuthor}> this is reminder for: **{content}**\n>>> {messageURL}",
                    embed=embed,
                )
            return

    @Cog.listener("on_giveaway_timer_complete")
    async def extra_parser_giveaway(self, **kw: Any) -> None:
        log.info("parsing giveaway...")
        extra = kw.get("extra")
        if not extra:
            return

        name = extra.get("name")
        if name == "GIVEAWAY_END" and (main := extra.get("main")):
            await self._parse_giveaway(**main)

    async def _parse_giveaway(self, **kw: Any) -> None:
        data: dict[str, Any] = await self.bot.giveaways.find_one(
            {
                "message_id": kw.get("message_id"),
                "guild_id": kw.get("guild_id"),
                "status": "ONGOING",
            }
        )
        cog: Giveaway = self.bot.get_cog("Giveaway")  # type: ignore
        member_ids: list[int] = await cog.end_giveaway(self.bot, **data)
        channel: discord.TextChannel = await self.bot.getch(
            self.bot.get_channel, self.bot.fetch_channel, kw.get("giveaway_channel")
        )
        await self.bot.giveaways.find_one_and_update(
            {"message_id": kw.get("message_id"), "status": "ONGOING"},
            {"$set": {"status": "END"}},
        )
        if not channel:
            return
        msg_link = f"https://discord.com/channels/{kw.get('guild_id')}/{kw.get('giveaway_channel')}/{kw.get('message_id')}"
        if not member_ids:
            await channel.send(f"No winners!\n> {msg_link}")
            return

        joiner = ">, <@".join([str(i) for i in member_ids])

        await channel.send(f"Congrats <@{joiner}> you won {kw.get('prize')}\n" f"> {msg_link}")


async def setup(bot: Bot) -> None:
    await bot.add_cog(EventCustom(bot))
