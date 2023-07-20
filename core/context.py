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

from typing import TYPE_CHECKING

import discord
from discord.ext import commands


class Context(commands.Context[commands.Bot]):
    """A custom context class for the bot."""

    if TYPE_CHECKING:
        from .bot import Bot  # pylint: disable=import-outside-toplevel

    bot: Bot
    author: discord.Member
    guild: discord.Guild
    channel: discord.abc.GuildChannel
    command: commands.Command

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.config = self.bot.main_db.mainConfigCollection

    async def send(self, *args, **kwargs) -> discord.Message:
        """Send a message to the channel. If fails, then send in DMs."""
        # check if the bot has permission to send messages

        permission = self.channel.permissions_for(self.me)  # type: ignore

        if not (
            permission.send_messages
            and permission.read_messages
            and permission.read_message_history
            and permission.embed_links
        ):
            try:
                return await self.author.send(
                    f"Hey! I don't have permission to send messages in {self.channel.mention}.\n"
                    "> Please grant me the required permissions and try again.",
                )
            except discord.Forbidden:
                pass

        return await super().send(*args, **kwargs)

    async def reply(self, *args, **kwargs) -> discord.Message:
        """Reply to the message. If fails, then send normally."""
        try:
            return await self.send(*args, **kwargs, reference=kwargs.pop("reference", self.message), mention_author=False)
        except discord.HTTPException:
            return await self.send(*args, **kwargs, mention_author=True)
