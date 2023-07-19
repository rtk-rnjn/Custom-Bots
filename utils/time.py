"""
MIT License

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

import datetime
import re
from typing import TYPE_CHECKING, Any, Optional

from dateutil.relativedelta import relativedelta
from discord.ext import commands

if TYPE_CHECKING:
    from typing_extensions import Self

    from core import Context


class ShortTime:
    """A converter that converts a short time string into a datetime.datetime object."""

    compiled = re.compile(
        """
           (?:(?P<years>[0-9])(?:years?|y))?
           (?:(?P<months>[0-9]{1,2})(?:months?|mon?))?
           (?:(?P<weeks>[0-9]{1,4})(?:weeks?|w))?
           (?:(?P<days>[0-9]{1,5})(?:days?|d))?
           (?:(?P<hours>[0-9]{1,5})(?:hours?|hr?))?
           (?:(?P<minutes>[0-9]{1,5})(?:minutes?|m(?:in)?))?
           (?:(?P<seconds>[0-9]{1,5})(?:seconds?|s(?:ec)?))?
        """,
        re.VERBOSE,
    )

    discord_fmt = re.compile(r"<t:(?P<ts>[0-9]+)(?:\:?[RFfDdTt])?>")

    dt: datetime.datetime

    def __init__(
        self,
        argument: str,
        *,
        now: Optional[datetime.datetime] = None,
        tzinfo: datetime.tzinfo = datetime.timezone.utc,
    ):
        match = self.compiled.fullmatch(argument)
        if match is None or not match.group(0):
            match = self.discord_fmt.fullmatch(argument)
            if match is not None:
                self.dt = datetime.datetime.fromtimestamp(int(match.group("ts")), tz=datetime.timezone.utc)
                if tzinfo is not datetime.timezone.utc:
                    self.dt = self.dt.astimezone(tzinfo)
                return
            else:
                raise commands.BadArgument("invalid time provided")

        data = {k: int(v) for k, v in match.groupdict(default=0).items()}
        now = now or datetime.datetime.now(datetime.timezone.utc)
        self.dt = now + relativedelta(**data)
        if tzinfo is not datetime.timezone.utc:
            self.dt = self.dt.astimezone(tzinfo)

    @classmethod
    async def convert(cls, ctx: Context, argument: str) -> Self:
        """Converts the argument into a datetime.datetime object."""
        tzinfo = datetime.timezone.utc
        return cls(argument, now=ctx.message.created_at, tzinfo=tzinfo)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} dt={self.dt}>"

    def __str__(self) -> str:
        return self.dt.isoformat()
