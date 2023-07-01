from __future__ import annotations

from core import Bot

from .on_cmd import OnCommand
from .on_msg import OnMessage


async def setup(bot: Bot) -> None:
    await bot.add_cog(OnCommand(bot))
    await bot.add_cog(OnMessage(bot))
