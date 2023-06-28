from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands


class Context(commands.Context[commands.Bot]):
    if TYPE_CHECKING:
        from .bot import Bot

    bot: Bot

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.config = self.bot.main_db.configs
