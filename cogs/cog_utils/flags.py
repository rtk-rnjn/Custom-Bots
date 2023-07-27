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

from typing import Annotated

import discord
from discord.ext import commands

from utils import ShortTime, convert_bool


class AuditFlag(commands.FlagConverter, case_insensitive=True, prefix="--", delimiter=" "):
    """Flags for audit command."""

    guild: discord.Guild | None = commands.flag(
        name="guild",
        aliases=["g"],
        default=None,
        description="Filter by guild",
        override=True,
    )

    limit: int | None = commands.flag(
        name="limit",
        aliases=["l", "size"],
        default=100,
        description="Limit the number of actions to fetch",
        override=True,
    )

    action: str | None = commands.flag(
        name="action",
        aliases=["act"],
        default=None,
        description="Filter by action",
        override=True,
    )

    before: ShortTime | None = commands.flag(
        name="before",
        aliases=["b", "bf"],
        default=None,
        description="Filter actions before this time",
        override=True,
    )

    after: ShortTime | None = commands.flag(
        name="after",
        aliases=["a", "af"],
        default=None,
        description="Filter actions after this time",
        override=True,
    )

    oldest_first: Annotated[bool | None, convert_bool] = commands.flag(
        name="oldest_first",
        aliases=["of", "oldest-first"],
        default=None,
        description="Sort by oldest first",
        override=True,
    )

    user: discord.User | discord.Member | None = commands.flag(
        name="user",
        aliases=["member", "u", "m"],
        default=None,
        description="Filter by user",
        override=True,
    )
