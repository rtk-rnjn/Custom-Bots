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

import logging
from collections import Counter
from typing import Optional

import discord
from discord.ext import commands

from core import Bot, Cog, Context  # pylint: disable=import-error

log = logging.getLogger("meta")


class Meta(Cog):
    """Commands for getting information about the bot or a user or any other meta stuff."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.command(name="ping")
    async def ping(self, ctx: Context) -> None:
        """Returns the bot's latency."""
        await ctx.reply(f"Pong! {round(self.bot.latency * 1000)}ms")

    @commands.command(name="uptime")
    async def uptime(self, ctx: Context) -> None:
        """Returns the bot's uptime."""
        relative_discord_time = discord.utils.format_dt(self.bot.uptime, style="R")

        await ctx.reply(f"Uptime: {relative_discord_time}")

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
                f"{str(target.activity.type).split('.')[-1].title() if target.activity else 'N/A'} {target.activity.name if target.activity else ''}",  # pylint: disable=use-maxsplit-arg
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

    @commands.command(name="avatar", aliases=["av"])
    async def avatar(self, ctx: Context, *, member: Optional[discord.Member] = None):
        """Returns the avatar of the user"""
        target = member or ctx.author
        embed = discord.Embed(
            title=f"{target}'s Avatar",
            color=target.color,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_image(url=target.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.command(aliases=["guildavatar", "serverlogo", "servericon"])
    async def guildicon(self, ctx: Context):
        """
        Get the freaking server icon
        """
        assert ctx.guild is not None

        if not ctx.guild.icon:
            return await ctx.reply(f"{ctx.author.mention} {ctx.guild.name} has no icon yet!")

        embed = discord.Embed(timestamp=discord.utils.utcnow())
        embed.set_image(url=ctx.guild.icon.url)

        await ctx.reply(embed=embed)

    @commands.command(name="serverinfo", aliases=["guildinfo", "si", "gi"])
    async def server_info(self, ctx: Context):  # pylint: disable=too-many-locals, too-many-branches
        """Get the basic stats about the server"""
        assert ctx.guild is not None

        embed: discord.Embed = discord.Embed(
            title=f"Server Info: {ctx.guild.name}",
            colour=ctx.guild.owner.colour if ctx.guild.owner else None,
            timestamp=discord.utils.utcnow(),
        )
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        embed.set_footer(text=f"ID: {ctx.guild.id}")
        statuses = [
            len(list(filter(lambda m: str(m.status) == "online", ctx.guild.members))),
            len(list(filter(lambda m: str(m.status) == "idle", ctx.guild.members))),
            len(list(filter(lambda m: str(m.status) == "dnd", ctx.guild.members))),
            len(list(filter(lambda m: str(m.status) == "offline", ctx.guild.members))),
        ]

        fields = [
            ("Owner", ctx.guild.owner, True),
            ("Region", "Deprecated", True),
            ("Created at", f"{discord.utils.format_dt(ctx.guild.created_at)}", True),
            (
                "Total Members",
                (
                    f"Members: {len(ctx.guild.members)}\n"
                    f"Humans: {len(list(filter(lambda m: not m.bot, ctx.guild.members)))}\n"
                    f"Bots: {len(list(filter(lambda m: m.bot, ctx.guild.members)))}"
                ),
                True,
            ),
            (
                "Total channels",
                (
                    f"Categories: {len(ctx.guild.categories)}\n"
                    f"Text: {len(ctx.guild.text_channels)}\n"
                    f"Voice:{len(ctx.guild.voice_channels)}"
                ),
                True,
            ),
            (
                "General",
                (
                    f"Roles: {len(ctx.guild.roles)}\n"
                    f"Emojis: {len(ctx.guild.emojis)}\n"
                    f"Boost Level: {ctx.guild.premium_tier}"
                ),
                True,
            ),
            (
                "Statuses",
                (
                    f":green_circle: {statuses[0]}\n"
                    f":yellow_circle: {statuses[1]}\n"
                    f":red_circle: {statuses[2]}\n"
                    f":black_circle: {statuses[3]}"
                ),
                True,
            ),
        ]

        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)

        features = set(ctx.guild.features)
        all_features = {
            "PARTNERED": "Partnered",
            "VERIFIED": "Verified",
            "DISCOVERABLE": "Server Discovery",
            "COMMUNITY": "Community Server",
            "FEATURABLE": "Featured",
            "WELCOME_SCREEN_ENABLED": "Welcome Screen",
            "INVITE_SPLASH": "Invite Splash",
            "VIP_REGIONS": "VIP Voice Servers",
            "VANITY_URL": "Vanity Invite",
            "COMMERCE": "Commerce",
            "LURKABLE": "Lurkable",
            "NEWS": "News Channels",
            "ANIMATED_ICON": "Animated Icon",
            "BANNER": "Banner",
        }

        if info := [f":ballot_box_with_check: {label}" for feature, label in all_features.items() if feature in features]:
            embed.add_field(name="Features", value="\n".join(info))

        if ctx.guild.premium_tier != 0:
            boosts = f"Level {ctx.guild.premium_tier}\n{ctx.guild.premium_subscription_count} boosts"
            last_boost = max(ctx.guild.members, key=lambda m: m.premium_since or ctx.guild.created_at)
            if last_boost.premium_since is not None:
                boosts = f"{boosts}\nLast Boost: {last_boost} ({discord.utils.format_dt(last_boost.premium_since, 'R')})"
            embed.add_field(name="Boosts", value=boosts, inline=True)
        else:
            embed.add_field(name="Boosts", value="Level 0", inline=True)

        emoji_stats = Counter()
        for emoji in ctx.guild.emojis:
            if emoji.animated:
                emoji_stats["animated"] += 1
                emoji_stats["animated_disabled"] += not emoji.available
            else:
                emoji_stats["regular"] += 1
                emoji_stats["disabled"] += not emoji.available

        fmt = (
            f'Regular: {emoji_stats["regular"]}/{ctx.guild.emoji_limit}\n'
            f'Animated: {emoji_stats["animated"]}/{ctx.guild.emoji_limit}\n'
        )
        if emoji_stats["disabled"] or emoji_stats["animated_disabled"]:
            fmt = f'{fmt}Disabled: {emoji_stats["disabled"]} regular, {emoji_stats["animated_disabled"]} animated\n'

        fmt = f"{fmt}Total Emoji: {len(ctx.guild.emojis)}/{ctx.guild.emoji_limit*2}"
        embed.add_field(name="Emoji", value=fmt, inline=True)

        if ctx.guild.me.guild_permissions.ban_members:
            embed.add_field(
                name="Banned Members",
                value=f"{len([_ async for _ in ctx.guild.bans(limit=1000)])}+",
                inline=True,
            )
        if ctx.guild.me.guild_permissions.manage_guild:
            embed.add_field(name="Invites", value=f"{len(await ctx.guild.invites())}", inline=True)

        if ctx.guild.banner:
            embed.set_image(url=ctx.guild.banner.url)

        await ctx.reply(embed=embed)


async def setup(bot: Bot) -> None:
    """Load the Meta cog."""
    await bot.add_cog(Meta(bot))
