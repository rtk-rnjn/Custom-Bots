from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os

import aiohttp
from discord.utils import setup_logging

from core import Bot
from utils import Config, CustomFormatter, bots

if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
else:
    try:
        import uvloop  # type: ignore
    except ImportError:
        pass
    else:
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


async def run(bot: Bot, config: Config):
    async with aiohttp.ClientSession() as session:
        async with bot:
            setattr(bot, "session", session)
            await bot.start(config.token)


setup_logging(
    formatter=CustomFormatter(),
    handler=logging.handlers.RotatingFileHandler(
        filename=".log",
        encoding="utf-8",
        maxBytes=1 * 1024 * 1024,  # 1 MiB
        backupCount=1,  # Rotate through 1 files
    ),
)


async def main():
    loop = asyncio.get_event_loop()
    tasks = []
    for bot in bots["bots"]:
        config = Config(**bot)

        if config.token is None:
            continue

        bot = Bot(config)

        tasks.append(
            loop.create_task(
                run(bot, config),
                name=f"BOT_{config.name.replace(' ', '_').upper()}_{config.id}_TASK",
            )
        )

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
