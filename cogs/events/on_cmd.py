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

from pymongo import UpdateOne

from core import Bot, Cog, Context  # pylint: disable=import-error

log = logging.getLogger("events.on_cmd")


class OnCommand(Cog):
    """Cog for logging commands invoked by the bot."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @Cog.listener()
    async def on_command(self, ctx: Context) -> None:
        """Log commands invoked by the bot."""
        log.debug("%s invoked by %s (%s) in %s (%s)", ctx.command, ctx.author, ctx.author.id, ctx.guild, ctx.guild.id)

        data = UpdateOne(
            {"id": self.bot.user.id},
            {
                "$inc": {
                    f"command.{ctx.command.qualified_name}": 1,
                },
            },
            upsert=True,
        )
        self.bot.add_to_db_writer(collection="commandCollection", entity=data)

    @Cog.listener()
    async def on_command_completion(self, ctx: Context) -> None:
        """Log commands invoked by the bot."""
        data = UpdateOne(
            {"id": self.bot.user.id},
            {
                "$addToSet": {
                    "command_log": {
                        "name": ctx.command.qualified_name,
                        "author": ctx.author.id,
                        "guild": ctx.guild.id,
                        "channel": ctx.channel.id,
                        "message": ctx.message.id,
                        "message_content": ctx.message.content,
                    },
                },
            },
            upsert=True,
        )

        self.bot.add_to_db_writer(collection="commandCollection", entity=data)
