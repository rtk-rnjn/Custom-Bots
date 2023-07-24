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

import discord
from pymongo import UpdateOne

from core import Bot, Cog  # pylint: disable=import-error

log = logging.getLogger("events.on_msg")


class OnMessage(Cog):
    """Cog for logging messages sent by the bot."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Log messages sent by the bot."""
        assert message.guild and self.bot.user

        if message.author.bot:
            return

        if message.guild.id != self.bot.config.guild_id:
            return

        data = UpdateOne(
            {"_id": self.bot.user.id},
            {
                "$inc": {
                    "message_sent": 1,
                },
                "$addToSet": {
                    "message_log": {
                        "message_id": message.id,
                        "message_channel_id": message.channel.id,
                        "message_channel_name": str(message.channel),
                        "message_guild_id": message.guild.id,
                        "message_author_id": message.author.id,
                        "message_author_name": str(message.author),
                        "message_author_avatar": message.author.display_avatar.url,
                        "message_author_bot": message.author.bot,
                        "message_content": message.content,
                        "message_created_at": message.created_at,
                        "message_edited_at": message.edited_at,
                    },
                },
            },
            upsert=True,
        )

        self.bot.add_to_db_writer(collection="messageCollection", entity=data)

    @Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """Log edited messages sent by the bot."""
        assert before.guild and self.bot.user

        if before.author.bot or before.content == after.content:
            return

        data = UpdateOne(
            {"_id": self.bot.user.id, "message_log.message_id": before.id},
            {
                "$set": {
                    "message_log.$.message_content": after.content,
                    "message_log.$.message_edited_at": after.edited_at,
                },
                "$inc": {
                    "message_edited": 1,
                },
            },
        )

        self.bot.add_to_db_writer(collection="messageCollection", entity=data)

    @Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        """Log deleted messages sent by the bot."""
        assert message.guild and self.bot.user

        if message.author.bot:
            return

        data = UpdateOne(
            {"_id": self.bot.user.id, "message_log.message_id": message.id},
            {
                "$pull": {"message_log": {"message_id": message.id}},
                "$inc": {
                    "message_deleted": 1,
                },
            },
        )

        self.bot.add_to_db_writer(collection="messageCollection", entity=data)
