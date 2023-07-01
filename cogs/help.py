from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from discord.ext.commands.errors import CommandError

if TYPE_CHECKING:
    from core import Bot, Cog, Context


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
        bot = ctx.bot
        prefix = ctx.clean_prefix
        embed = discord.Embed(
            title="Help",
            description=f"Use `{prefix}help <command>` for more info on a command.\nUse `{prefix}help <category>` for more info on a category.",
        )
        for cog, commands in mapping.items():
            filtered = await self.filter_commands(commands, sort=True)
            if filtered:
                cog_name = getattr(cog, "qualified_name", "No Category")
                embed.add_field(
                    name=cog_name,
                    value=f"`{prefix}help {cog_name.lower()}`",
                )
        await ctx.send(embed=embed)

    async def send_cog_help(self, cog: Cog):
        ctx = self.context
        bot = ctx.bot
        prefix = ctx.clean_prefix
        embed = discord.Embed(title=cog.qualified_name, description=cog.description)
        for command in cog.get_commands():
            if not command.hidden:
                embed.add_field(
                    name=f"`{prefix}{command.name}`",
                    value=command.help or "No description",
                    inline=False,
                )
        await ctx.send(embed=embed)

    async def send_command_help(self, command: commands.Command):
        ctx = self.context
        bot = ctx.bot
        prefix = ctx.clean_prefix
        embed = discord.Embed(title=f"`{prefix}{command.name}`", description=command.help or "No description")
        await ctx.send(embed=embed)

    async def send_group_help(self, group: commands.Group):
        ctx = self.context
        bot = ctx.bot
        prefix = ctx.clean_prefix
        embed = discord.Embed(title=f"`{prefix}{group.name}`", description=group.help or "No description")
        for command in group.commands:
            if not command.hidden:
                embed.add_field(
                    name=f"`{prefix}{command.name}`",
                    value=command.short_doc or "No description",
                    inline=False,
                )
        await ctx.send(embed=embed)

    async def send_error_message(self, error):
        ctx = self.context
        bot = ctx.bot
        prefix = ctx.prefix
        await ctx.send(f"Well this is awkward...```py\n{error}```")
