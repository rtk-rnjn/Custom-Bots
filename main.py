from __future__ import annotations

import asyncio
import os

import aiohttp

from core import Bot
from utils import Config, bots

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
