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

from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from discord.ext.commands.errors import CommandError

if TYPE_CHECKING:
    from core import Cog, Context


class Help(commands.HelpCommand):
    def __init__(
        self,
    ):
        super().__init__(
            command_attrs={
                "hidden": True,
                "help": "Shows help about the bot, a command, or a category",
                "cooldown": commands.CooldownMapping.from_cooldown(1, 3.0, commands.BucketType.member),
            }
        )

    async def on_help_command_error(self, ctx: Context, error: CommandError):
        await ctx.send(f"Well this is awkward...```py\n{error}```")

    async def send_bot_help(self, mapping):
        ctx = self.context
        prefix = ctx.clean_prefix
        embed = discord.Embed(
            title="Help",
            description=f"Use `{prefix}help <command>` for more info on a command.\nUse `{prefix}help <category>` for more info on a category.",
        )
        for cog, cmds in mapping.items():
            filtered = await self.filter_commands(cmds, sort=True)
            if not filtered:
                continue
            cog_name = getattr(cog, "qualified_name", "No Category")
            embed.add_field(
                name=cog_name,
                value=f"`{prefix}help {cog_name.lower()}`",
            )
        await ctx.send(embed=embed)

    async def send_cog_help(self, cog: Cog):
        ctx = self.context
        prefix = ctx.clean_prefix
        embed = discord.Embed(title=cog.qualified_name, description=cog.description)
        for command in cog.get_commands():
            if not command.hidden:
                embed.add_field(
                    name=f"`{prefix}{command.qualified_name}`",
                    value=command.short_doc or "No description",
                    inline=False,
                )
        await ctx.send(embed=embed)

    async def send_command_help(self, command: commands.Command):
        ctx = self.context
        prefix = ctx.clean_prefix
        embed = discord.Embed(title=f"`{prefix}{command.qualified_name}`", description=command.help or "No description")
        await ctx.send(embed=embed)

    async def send_group_help(self, group: commands.Group):
        ctx = self.context
        prefix = ctx.clean_prefix
        embed = discord.Embed(title=f"`{prefix}{group.qualified_name}`", description=group.help or "No description")
        for command in group.commands:
            if not command.hidden:
                embed.add_field(
                    name=f"`{prefix}{command.qualified_name}`",
                    value=command.short_doc or "No description",
                    inline=False,
                )
        await ctx.send(embed=embed)

    async def send_error_message(self, error):
        ctx = self.context
        await ctx.send(f"Well this is awkward...```py\n{error}```")
