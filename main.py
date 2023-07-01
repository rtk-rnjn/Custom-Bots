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


async def run(bot: Bot, config: Config):
    async with aiohttp.ClientSession() as session:
        async with bot:
            setattr(bot, "session", session)
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


async def main():
    loop = asyncio.get_event_loop()
    tasks = []
    for config in BOT_CONFIGS:
        if not config or config.token is None:
            continue

        bot = Bot(config)

        setattr(bot, "mongo", AsyncIOMotorClient(ENV["MONGO_URI"]))
        setattr(bot, "sync_mongo", MONGO_CLIENT)
        setattr(bot, "guild_id", config.guild_id)

        bot.init_db()

        tasks.append(
            loop.create_task(
                run(bot, config),
                name=f"BOT_{config.name.replace(' ', '_').upper()}_{config.id}_TASK",
            )
        )

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
