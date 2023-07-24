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

import asyncio
import json
import logging
from collections import Counter
from typing import Optional

import discord
from discord.ext import commands

from core import Bot, Cog, Context  # pylint: disable=import-error

from .cog_utils import AnnouncementView, EmbedBuilder, EmbedCancel, EmbedSend

log = logging.getLogger("misc")


class Misc(Cog):
    """Miscellaneous commands."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.__cached_messages: dict[int, discord.Message | list[discord.Message]] = {}

    @commands.command(name="embed")
    async def embed_command(
        self,
        ctx: Context,
        channel: Optional[discord.TextChannel] = None,
        *,
        data: Optional[str] = None,
    ) -> None:
        """A nice command to make custom embeds.

        Embed can also be created from JSON object.

        Example:
        -------
        `[p]embed {"title": "Hello", "description": "World!"}`
        """
        channel = channel or ctx.channel  # type: ignore
        if channel.permissions_for(ctx.author).embed_links:  # type: ignore
            if not data:
                view = EmbedBuilder(ctx, items=[EmbedSend(channel), EmbedCancel()])  # type: ignore
                await view.rendor()
                return
            try:
                await channel.send(embed=discord.Embed.from_dict(json.loads(str(data))))  # type: ignore
            except Exception as e:  # pylint: disable=broad-except
                await ctx.reply(f"{ctx.author.mention} you didn't provide the proper json object. Error raised: {e}")
        else:
            await ctx.reply(
                f"{ctx.author.mention} you don't have Embed Links permission in {channel.mention}",  # type: ignore
            )

    @commands.command(name="invite")
    async def invite_command(self, ctx: Context) -> None:
        """Invite the bot to your server."""
        assert self.bot.user

        main_guild = self.bot.get_guild(self.bot.config.guild_id)  # type: discord.Guild  # type: ignore
        owner = self.bot.get_user(self.bot.config.owner_id)  # type: discord.User  # type: ignore

        await ctx.reply(
            embed=discord.Embed(
                title="This bot is not intended to be used in multiple servers.",
                description=(
                    "You can still add the bot on your server, but it won't work.\n"
                    f"> - Bot is made to work in **[{main_guild.name}]({self.bot.config.permanent_invite})** (ID: `{main_guild.id}`)\n"
                    f"> - If you want to use the bot in your server, please consider asking **[{owner.mention} - `{owner}`]** (`{owner.id}`)\n"
                ),
                url=discord.utils.oauth_url(self.bot.user.id, permissions=discord.Permissions(0)),
            )
            .set_thumbnail(url=self.bot.user.display_avatar.url)
            .set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url),
        )

    @commands.command()
    async def cleanup(self, ctx: Context, search: int = 100) -> None:
        """Cleans up the bot's messages from the channel.

        If a search number is specified, it searches that many messages to delete.

        If the bot has Manage Messages permissions then it will try to delete
        messages that look like they invoked the bot as well.

        After the cleanup is completed, the bot will send you a message with
        which people got their messages deleted and their count. This is useful
        to see which users are spammers.

        Members with Manage Messages can search up to 1000 messages.
        Members without can search up to 25 messages.
        """
        strategy = self._basic_cleanup_strategy
        assert isinstance(ctx.author, discord.Member) and isinstance(ctx.me, discord.Member)
        is_mod = ctx.channel.permissions_for(ctx.author).manage_messages
        if ctx.channel.permissions_for(ctx.me).manage_messages:
            if is_mod:
                strategy = self._complex_cleanup_strategy
            else:
                strategy = self._regular_user_cleanup_strategy

        search = min(max(2, search), 1000) if is_mod else min(max(2, search), 25)
        spammers = await strategy(ctx, search)
        deleted = sum(spammers.values())
        messages = [f'{deleted} message{" was" if deleted == 1 else "s were"} removed.']
        if deleted:
            messages.append("")
            spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
            messages.extend(f"- **{author}**: {count}" for author, count in spammers)

        await ctx.reply("\n".join(messages), delete_after=10)

    async def _basic_cleanup_strategy(self, ctx: Context, search: int) -> dict[str, int]:
        count = 0
        async for msg in ctx.history(limit=search, before=ctx.message):
            if msg.author == ctx.me and not msg.mentions and not msg.role_mentions:
                await msg.delete()
                count += 1
        return {"Bot": count}

    async def _complex_cleanup_strategy(self, ctx: Context, search: int) -> dict[str, int]:
        assert ctx.guild is not None and isinstance(ctx.channel, discord.TextChannel)
        prefixes = tuple(self.bot.config.prefix)  # thanks startswith

        def check(m: discord.Message) -> bool:
            return m.author == ctx.me or m.content.startswith(prefixes)

        deleted = await ctx.channel.purge(limit=search, check=check, before=ctx.message)
        return Counter(m.author.display_name for m in deleted)

    async def _regular_user_cleanup_strategy(self, ctx: Context, search: int) -> dict[str, int]:
        assert ctx.guild is not None and isinstance(ctx.channel, discord.TextChannel)

        prefixes = tuple(self.bot.config.prefix)

        def check(m: discord.Message) -> bool:
            return (m.author == ctx.me or m.content.startswith(prefixes)) and not m.mentions and not m.role_mentions

        deleted = await ctx.channel.purge(limit=search, check=check, before=ctx.message)
        return Counter(m.author.display_name for m in deleted)

    @Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        """Cache deleted messages."""
        if message.author.bot:
            return

        self.__cached_messages[message.channel.id] = message
        log.debug("message deleted and cached in %s", message.channel.id)

    @Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """Cache edited messages."""
        if before.author.bot:
            return

        self.__cached_messages[before.channel.id] = [before, after]
        log.debug("message edited and cached in %s", before.channel.id)

    @commands.command()
    async def snipe(self, ctx: Context, *, channel: Optional[discord.TextChannel] = None) -> None:  # type: ignore
        """Snipe a deleted message.

        Shows the last deleted message in the channel.
        If a channel is specified, it will show the last deleted message in that channel.

        **Example:**
        - `[p]snipe` - Shows the last deleted message in the channel.
        - `[p]snipe #general` - Shows the last deleted message in #general.
        """
        channel = channel or ctx.channel  # type: discord.abc.GuildChannel  # type: ignore

        perms = channel.permissions_for(ctx.author)
        if not perms.read_messages and not perms.read_message_history:
            await ctx.reply(f"{ctx.author.mention} you don't have permission to read messages in {channel.mention}")
            return

        if channel.id not in self.__cached_messages:
            await ctx.reply(f"{ctx.author.mention} there are no deleted messages in {channel.mention}")
            return

        message = self.__cached_messages.pop(channel.id)
        log.debug("message sniped in %s", channel.id)

        if isinstance(message, list):
            before, after = message
            if before.content == after.content:
                await ctx.reply(f"{ctx.author.mention} there are no deleted messages in {channel.mention}")
                return

            embed = (
                discord.Embed(
                    title="Message edited",
                    description=(f"**Before:**\n{before.content}\n\n**After:**\n{after.content}"),
                    timestamp=before.created_at,
                )
                .set_author(name=before.author, icon_url=before.author.display_avatar.url)
                .set_footer(text=f"Author ID: {before.author.id}")
            )

            await ctx.reply(embed=embed)
            return

        embed = (
            discord.Embed(
                title="Message deleted",
                description=message.content,
                timestamp=message.created_at,
            )
            .set_author(name=message.author, icon_url=message.author.display_avatar.url)
            .set_footer(text=f"Author ID: {message.author.id}")
        )
        await ctx.reply(embed=embed)

    @commands.group(name="announce", aliases=["announcements", "announcement"], invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    async def announce_group(
        self, ctx: Context, channel: Optional[discord.TextChannel] = None, *, msg: Optional[str] = None
    ) -> None:
        """Send an announcement to the announcements channel."""
        if ctx.invoked_subcommand is None:
            if not msg:
                try:
                    message: discord.Message = await self.bot.wait_for(
                        "message",
                        check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                        timeout=120,
                    )
                except asyncio.TimeoutError:
                    await ctx.reply(f"{ctx.author.mention} you took too long to respond.")
                    return
                msg = message.content

            view = AnnouncementView(
                ctx=ctx,
                content=msg,
                current_channel=channel.id if channel else ctx.channel.id,
                in_embed=False,
            )
            view.message = await ctx.send(embed=discord.Embed(description=msg), view=view)

    @announce_group.command(name="embed")
    @commands.has_permissions(manage_messages=True)
    async def announce_embed_command(self, ctx: Context, channel: Optional[discord.TextChannel] = None, *, msg: str) -> None:
        """Send an announcement to the announcements channel."""
        view = AnnouncementView(
            ctx=ctx,
            content=msg,
            current_channel=channel.id if channel else ctx.channel.id,
            in_embed=True,
        )
        view.message = await ctx.send(embed=discord.Embed(description=msg), view=view)

    @announce_group.command(name="quick", aliases=["q"])
    @commands.has_permissions(manage_messages=True)
    async def announce_quick_command(self, ctx: Context, *, msg: str) -> None:
        """Send an announcement to the announcements channel."""
        await ctx.message.delete(delay=0)
        pinnged = ("@everyone" in msg) or ("@here" in msg)
        if not pinnged:
            msg = f"@everyone\n{msg}\n\nRegards,\n{ctx.author.mention} ({ctx.author})"

        await ctx.send(msg)


async def setup(bot: Bot) -> None:
    """Load the Misc cog."""
    await bot.add_cog(Misc(bot))
