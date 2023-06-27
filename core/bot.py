from __future__ import annotations

import logging.handlers
import os

import discord
import jishaku  # noqa: F401  # pylint: disable=unused-import
from discord.ext import commands

from utils import Config, CustomFormatter, all_cogs

os.environ["JISHAKU_HIDE"] = "True"
os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_NO_DM_TRACEBACK"] = "True"
os.environ["JISHAKU_FORCE_PAGINATOR"] = "True"

discord.utils.setup_logging(
    formatter=CustomFormatter(),
    handler=logging.handlers.RotatingFileHandler(
        filename=".log",
        encoding="utf-8",
        maxBytes=1 * 1024 * 1024,  # 1 MiB
        backupCount=1,  # Rotate through 1 files
    ),
)


class Bot(commands.Bot):
    def __init__(self, config: Config, *args, **kwargs):
        super().__init__(
            command_prefix=config.prefix,
            intents=discord.Intents.all(),
            case_insensitive=True,
            strip_after_prefix=True,
            activity=config.activity,
            status=config.status,
            owner_ids=config.owner_ids,
        )
        self.cogs_to_load = config.cogs
        self.session = None

    async def setup_hook(self) -> None:
        await self.load_extension("jishaku")
        if len(self.cogs_to_load) == 1 and self.cogs_to_load[0] == "~":
            self.cogs_to_load = all_cogs

        for cog in self.cogs_to_load:
            try:
                await self.load_extension(cog)
            except commands.ExtensionNotFound:
                print(f"Extension {cog} not found. Skipping.")
            except commands.ExtensionFailed as e:
                print(f"Extension {cog} failed to load. Skipping.")
                print(e)
            else:
                print(f"Loaded extension {cog}.")

    async def on_ready(self) -> None:
        if not hasattr(self, "uptime"):
            self.uptime = discord.utils.utcnow()

        bot_id = getattr(self.user, "id", None)

        print(f"Logged in as {self.user} ({bot_id})")
