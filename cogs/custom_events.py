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

import contextlib
import logging
from typing import TYPE_CHECKING, Any

import discord

from core import Bot, Cog  # pylint: disable=import-error

if TYPE_CHECKING:
    from cogs.giveaway import Giveaway


log = logging.getLogger("custom_events")


class EventCustom(Cog):
    """A custom event class for the bot."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.ON_TESTING = False

    @Cog.listener("on_timer_complete")
    async def normal_parser(
        self,
        *,
        embed: dict[str, Any] | None = None,  # type: ignore
        content: str | None = None,
        dm_notify: bool = False,
        is_todo: bool = False,
        messageChannel: int | None = None,  # noqa: N803
        messageAuthor: int | None = None,  # noqa: N803
        messageURL: str | None = None,  # noqa: N803
        **_: Any,  # noqa: ANN401
    ) -> None:
        """A custom parser on timer complete event."""
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
    async def extra_parser_giveaway(self, **kw: Any) -> None:  # noqa: ANN401
        """A custom parser on giveaway timer complete event."""
        log.info("parsing giveaway...")
        await self.bot.log_bot_event(content=f"Parsing giveaway: {kw}")
        extra = kw.get("extra")
        if not extra:
            return

        name = extra.get("name")
        if name == "GIVEAWAY_END" and (main := extra.get("main")):
            await self._parse_giveaway(**main)

    async def _parse_giveaway(
        self,
        *,
        message_id: int,
        giveaway_channel: int,
        guild_id: int,
        **kw: str,
    ) -> None:
        """Helper function to parse giveaway."""
        data: dict[str, Any] = await self.bot.giveaways.find_one(
            {
                "message_id": message_id,
                "guild_id": guild_id,
                "status": "ONGOING",
            },
        )
        cog: Giveaway = self.bot.get_cog("Giveaway")  # type: ignore
        member_ids: list[int] = await cog.end_giveaway(self.bot, **data)
        channel: discord.TextChannel | None = await self.bot.getch(
            self.bot.get_channel,
            self.bot.fetch_channel,
            giveaway_channel,
        )
        if not channel:
            return
        await self.bot.giveaways.find_one_and_update(
            {"message_id": message_id, "status": "ONGOING"},
            {"$set": {"status": "END"}},
        )
        msg_link = discord.PartialMessage(channel=channel, id=message_id).jump_url
        if not member_ids:
            await channel.send(f"No winners!\n> {msg_link}")
            return

        joiner = ">, <@".join([str(i) for i in member_ids])

        _reference = channel.get_partial_message(message_id)
        await channel.send(f"Congrats <@{joiner}> you won {kw.get('prize')}\n" f"> {msg_link}", reference=_reference)


async def setup(bot: Bot) -> None:
    """Load the EventCustom cog."""
    await bot.add_cog(EventCustom(bot))
