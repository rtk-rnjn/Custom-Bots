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
IMPLIED, INCLUDING BUT NOT LIMITED typing. THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os

import aiohttp
from discord.utils import setup_logging
from motor.motor_asyncio import AsyncIOMotorClient

from core import Bot
from utils import BOT_CONFIGS, ENV, MONGO_CLIENT, Config, CustomFormatter

if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
else:
    try:
        import uvloop  # type: ignore
    except ImportError:
        pass
    else:
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


async def run(bot: Bot, config: Config) -> None:
    """Run the bot."""
    async with aiohttp.ClientSession() as session:
        async with bot:
            bot.session = session
            await bot.start(config.token)


setup_logging(
    formatter=CustomFormatter(),
    handler=logging.handlers.RotatingFileHandler(
        filename=".discord.log",
        encoding="utf-8",
        maxBytes=1 * 1024 * 1024,  # 1 MiB
        backupCount=1,  # Rotate through 1 files
    ),
)


async def main() -> None:
    """Main entry point."""
    loop = asyncio.get_event_loop()
    tasks = []
    for config in BOT_CONFIGS:
        if not config or config.token is None:
            continue

        bot = Bot(config)

        bot.mongo = AsyncIOMotorClient(ENV["MONGO_URI"])
        bot.sync_mongo = MONGO_CLIENT
        bot.guild_id = config.guild_id

        bot.init_db()

        tasks.append(
            loop.create_task(
                run(bot, config),
                name=f"BOT_{config.name.replace(' ', '_').upper()}_{config.id}_TASK",
            ),
        )

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
