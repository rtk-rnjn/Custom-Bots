from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands


class Context(commands.Context[commands.Bot]):
    if TYPE_CHECKING:
        from .bot import Bot

    bot: Bot
