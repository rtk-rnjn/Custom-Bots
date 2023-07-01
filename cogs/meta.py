from __future__ import annotations

import logging
from typing import Optional

import discord
from discord.ext import commands

from core import Bot, Cog, Context

log = logging.getLogger("meta")


class Meta(Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.command(name="ping")
    async def ping(self, ctx: Context) -> None:
        """Returns the bot's latency."""
        await ctx.send(f"Pong! {round(self.bot.latency * 1000)}ms")

    @commands.command(name="uptime")
    async def uptime(self, ctx: Context) -> None:
        """Returns the bot's uptime."""
        relative_discord_time = discord.utils.format_dt(self.bot.uptime, style="R")

        await ctx.send(f"Uptime: {relative_discord_time}")

    @commands.command(name="userinfo", aliases=["memberinfo", "ui", "mi"])
    @commands.bot_has_permissions(embed_links=True)
    async def user_info(self, ctx: Context, *, member: Optional[discord.Member] = None):
        """Get the basic stats about the member in the server"""
        target = member or ctx.author  # type: discord.Member  # type: ignore
        roles = list(target.roles)
        embed = discord.Embed(
            title="User information",
            colour=target.colour,
            timestamp=discord.utils.utcnow(),
        )

        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text=f"ID: {target.id}")
        fields = [
            ("Name", str(target), True),
            ("Created at", f"{discord.utils.format_dt(target.created_at)}", True),
            ("Status", f"{str(target.status).title()}", True),
            (
                "Activity",
                f"{str(target.activity.type).split('.')[-1].title() if target.activity else 'N/A'} {target.activity.name if target.activity else ''}",
                True,
            ),
            ("Joined at", f"{discord.utils.format_dt(target.joined_at) if target.joined_at else 'N/A'}", True),
            ("Boosted", bool(target.premium_since), True),
            ("Bot?", target.bot, True),
            ("Nickname", target.display_name, True),
            (f"Top Role [{len(roles)}]", target.top_role.mention, True),
        ]
        perms = []
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
        if target.guild_permissions.administrator:
            perms.append("Administrator")
        if (
            target.guild_permissions.kick_members
            and target.guild_permissions.ban_members
            and target.guild_permissions.manage_messages
        ):
            perms.append("Server Moderator")
        if target.guild_permissions.manage_guild:
            perms.append("Server Manager")
        if target.guild_permissions.manage_roles:
            perms.append("Role Manager")
        if target.guild_permissions.moderate_members:
            perms.append("Can Timeout Members")
        embed.description = f"Key perms: {', '.join(perms or ['NA'])}"
        if target.banner:
            embed.set_image(url=target.banner.url)
        await ctx.reply(ctx.author.mention, embed=embed)

    @commands.command()
    async def roleinfo(self, ctx: Context, *, role: discord.Role):
        """To get the info regarding the server role"""
        embed = discord.Embed(
            title=f"Role Information: {role.name}",
            description=f"ID: `{role.id}`",
            color=role.color,
            timestamp=discord.utils.utcnow(),
        )
        data = [
            ("Created At", f"{discord.utils.format_dt(role.created_at)}", True),
            ("Is Hoisted?", role.hoist, True),
            ("Position", role.position, True),
            ("Managed", role.managed, True),
            ("Mentionalble?", role.mentionable, True),
            ("Members", len(role.members), True),
            ("Mention", role.mention, True),
            ("Is Boost role?", role.is_premium_subscriber(), True),
            ("Is Bot role?", role.is_bot_managed(), True),
        ]
        for name, value, inline in data:
            embed.add_field(name=name, value=value, inline=inline)
        perms = []
        if role.permissions.administrator:
            perms.append("Administrator")
        if role.permissions.kick_members and role.permissions.ban_members:
            perms.append("Server Head Moderator")
        if (
            role.permissions.manage_guild
            and role.permissions.manage_channels
            and role.permissions.manage_webhooks
            and role.permissions.manage_roles
            and role.permissions.manage_emojis
        ):
            perms.append("Server Manager")
        if role.permissions.manage_nicknames and role.permissions.moderate_members and role.permissions.manage_messages:
            perms.append("Server Moderator")

        embed.description = f"Key perms: {', '.join(perms or ['NA'])}"
        embed.set_footer(text=f"ID: {role.id}")
        if role.unicode_emoji:
            embed.set_thumbnail(
                url=f"https://raw.githubusercontent.com/iamcal/emoji-data/master/img-twitter-72/{ord(list(role.unicode_emoji)[0]):x}.png"
            )
        if role.icon:
            embed.set_thumbnail(url=role.icon.url)
        await ctx.reply(embed=embed)


async def setup(bot: Bot) -> None:
    await bot.add_cog(Meta(bot))
