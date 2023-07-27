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

import argparse
import datetime
import logging
import re
import shlex
from collections.abc import Callable
from typing import Annotated

import discord
from discord.ext import commands

from core import Bot, Cog, Context  # pylint: disable=import-error
from utils import ActionReason, BannedMember, MemberID, RoleID, ShortTime  # pylint: disable=import-error

log = logging.getLogger("mod")


class Arguments(argparse.ArgumentParser):
    """Custom ArgumentParser to override the error method."""

    def error(self, message: str) -> None:
        """Raise RuntimeError instead of ArgumentParser error."""
        raise RuntimeError(message)


HELP_MESSAGE_KICK_BAN = """
- Make sure Bot role is above the target role in the role hierarchy.
- Make sure Bot has the permission to kick/ban members.
- Make sure Bot can access the target channel/member.
"""


class Mod(Cog):  # pylint: disable=too-many-public-methods
    """Moderation commands."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def mod_log(
        self,
        *,
        ctx: Context,
        message: str | None = None,
        target: discord.Member | discord.User | discord.abc.GuildChannel,
    ) -> None:
        """Factory method to send a mod log message."""
        embed = (
            discord.Embed(
                description=f"Reason: {message or 'not provided'}",
            )
            .set_footer(text=f"Moderator: {ctx.author} ({ctx.author.id})", icon_url=ctx.author.display_avatar.url)
            .set_author(
                name=f"{target} ({target.id}) - {ctx.command}(ed)",
                icon_url=target.display_avatar.url
                if isinstance(target, discord.Member)
                else self.bot.user.display_avatar.url,
            )
        )

        mod_channel_id = self.bot.config.modlog_channel
        if mod_channel_id is None:
            return

        mod_channel = self.bot.get_channel(mod_channel_id)  # type: discord.TextChannel  # type: ignore
        if mod_channel is None:
            return

        await mod_channel.send(embed=embed)

    async def cog_check(self, ctx: Context) -> bool:
        """Check if the command can be executed in the invoked context."""
        if not ctx.guild:
            msg = "This command can only be used in a server."
            raise commands.BadArgument(msg)
        return ctx.guild is not None

    async def kick_method(self, *, user: discord.Member | discord.User, guild: discord.Guild, reason: str | None) -> bool:
        """Kick a user from the server."""
        if member := guild.get_member(user.id):
            try:
                log.debug("kicking %s from guild %s", member, guild.name)
                await member.kick(reason=reason)
            except discord.Forbidden:
                return False

            return True

        msg = f"User `{user}` is not a member of guild `{guild.name}`"
        raise commands.BadArgument(msg)

    async def ban_method(self, *, user: discord.Member | discord.User, guild: discord.Guild, reason: str | None) -> bool:
        """Ban a user from the server."""
        try:
            log.debug("banning %s from guild %s", user, guild.name)
            await guild.ban(user, reason=reason)
        except discord.Forbidden:
            return False

        return True

    async def unban_method(self, *, user: discord.Member | discord.User, guild: discord.Guild, reason: str | None) -> bool:
        """Unban a user from the server."""
        try:
            log.debug("unbanning %s from guild %s", user, guild.name)
            await guild.unban(user, reason=reason)
        except discord.Forbidden:
            return False

        return True

    async def lock_channel_method(self, *, channel: discord.TextChannel | discord.VoiceChannel, reason: str | None) -> bool:
        """Lock a text channel or voice channel."""
        try:
            if isinstance(channel, discord.TextChannel):
                overwrites = channel.overwrites_for(channel.guild.default_role)
                overwrites.send_messages = False
                log.debug("locking %s in guild %s", channel, channel.guild.name)
                await channel.set_permissions(channel.guild.default_role, overwrite=overwrites, reason=reason)
            if isinstance(channel, discord.VoiceChannel):
                overwrites = channel.overwrites_for(channel.guild.default_role)
                overwrites.speak = False
                log.debug("locking %s in guild %s", channel, channel.guild.name)
                await channel.set_permissions(channel.guild.default_role, overwrite=overwrites, reason=reason)
        except discord.Forbidden:
            return False

        return True

    async def unlock_channel_method(
        self,
        *,
        channel: discord.TextChannel | discord.VoiceChannel,
        reason: str | None,
    ) -> bool:
        """Unlock a text channel or voice channel."""
        try:
            if isinstance(channel, discord.TextChannel):
                overwrites = channel.overwrites_for(channel.guild.default_role)
                overwrites.send_messages = None
                log.debug("unlocking %s in guild %s", channel, channel.guild.name)
                await channel.set_permissions(channel.guild.default_role, overwrite=overwrites, reason=reason)
            if isinstance(channel, discord.VoiceChannel):
                overwrites = channel.overwrites_for(channel.guild.default_role)
                overwrites.speak = None
                log.debug("unlocking %s in guild %s", channel, channel.guild.name)
                await channel.set_permissions(channel.guild.default_role, overwrite=overwrites, reason=reason)
        except discord.Forbidden:
            return False

        return True

    async def purge_method(
        self,
        ctx: Context,
        limit: int,
        predicate: Callable[[discord.Message], bool],
        *,
        before: int | None = None,
        after: int | None = None,
    ) -> bool:
        """Purge messages from a channel."""
        await ctx.message.delete(delay=0.5)

        if limit > 1000:
            msg = "Can only purge up to 1000 messages at a time."
            raise commands.BadArgument(msg)

        passed_before = ctx.message if before is None else discord.Object(before)
        passed_after = discord.Object(after) if after is not None else None

        try:
            if not isinstance(
                ctx.channel,
                discord.TextChannel | discord.Thread | discord.VoiceChannel,
            ):
                msg = "This command can only be used in text channels."
                raise commands.BadArgument(msg)
            log.debug(
                "purging %s messages in channel %s in guild %s",
                limit,
                ctx.channel.name,
                ctx.guild.name,  # type: ignore
            )
            await ctx.channel.purge(
                limit=limit,
                before=passed_before,
                after=passed_after,
                check=predicate,
            )
            await self.mod_log(ctx=ctx, message=f"Purged {limit or 100} messages.", target=ctx.channel)  # type: ignore

            return True

        except discord.Forbidden:
            return False

    async def timeout_method(
        self,
        *,
        user: discord.Member | discord.User,
        guild: discord.Guild,
        duration: datetime.datetime,
        reason: str | None = None,
    ) -> bool:
        """Timeout a user from the server."""
        member = guild.get_member(user.id)
        if member is None:
            msg = f"User `{user}` is not a member of guild `{guild.name}`"
            raise commands.BadArgument(msg)

        if member.timed_out_until is not None and member.timed_out_until > discord.utils.utcnow():
            msg = f"User `{member}` is already timed out. Their timeout will remove **{discord.utils.format_dt(member.timed_out_until, 'R')}**"
            raise commands.BadArgument(
                msg,
            )

        if duration > discord.utils.utcnow() + datetime.timedelta(days=28):
            msg = "Timeout duration cannot be more than 28 days."
            raise commands.BadArgument(msg)

        try:
            log.debug("timing out %s in guild %s till %s", member, guild.name, duration)
            await member.timeout(duration, reason=reason)
        except discord.Forbidden:
            return False

        return True

    async def unmute_method(
        self,
        *,
        user: discord.Member | discord.User,
        guild: discord.Guild,
        reason: str | None = None,
    ) -> bool:
        """Unmute a user from the server."""
        member = guild.get_member(user.id)
        if member is None:
            msg = f"User `{user}` is not a member of guild `{guild.name}`"
            raise commands.BadArgument(msg)

        if member.timed_out_until is None:
            return False

        try:
            log.debug("unmuting %s in guild %s", member, guild.name)
            await member.edit(timed_out_until=None, reason=reason)
        except discord.Forbidden:
            return False

        return True

    async def add_role_method(
        self,
        *,
        user: discord.Member | discord.User,
        guild: discord.Guild,
        role: discord.Role,
        reason: str | None = None,
    ) -> bool:
        """Add a role to a member."""
        member = guild.get_member(user.id)
        if member is None:
            msg = f"User `{user}` is not a member of guild `{guild.name}`"
            raise commands.BadArgument(msg)

        try:
            log.debug("adding role %s to %s in guild %s", role.name, member, guild.name)
            await member.add_roles(role, reason=reason)
        except discord.Forbidden:
            return False

        return True

    async def remove_role_method(
        self,
        *,
        user: discord.Member | discord.User,
        guild: discord.Guild,
        role: discord.Role,
        reason: str | None = None,
    ) -> bool:
        """Remove a role from a member."""
        member = guild.get_member(user.id)
        if member is None:
            msg = f"User `{user}` is not a member of guild `{guild.name}`"
            raise commands.BadArgument(msg)

        try:
            log.debug("removing role %s from %s in guild %s", role.name, member, guild.name)
            await member.remove_roles(role, reason=reason)
        except discord.Forbidden:
            return False

        return True

    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick_command(
        self,
        ctx: Context,
        user: Annotated[discord.Member, MemberID],
        *,
        reason: Annotated[str | None, ActionReason] = None,
    ) -> None:
        """Kick a user from the server.

        Both the bot and the user invoking the command must have the `Kick Members` permission.
        The bot will not kick users under the following conditions:
        - The user is the owner of the server
        - The invoker is user themselves
        - The invoker top role position is equal to or lower than the user top role position
        - The bot top role position is equal to or lower than the user top role position

        Example:
        -------
        `[p]kick @user spamming` - kicks the user for "spamming"
        `[p]kick 1234567890 idk` - kicks the user with the ID 1234567890 for "idk"

        Providing reason is Optional. Can be left blank. Exmaple:
        `[p]kick @user` - kicks the user for no reason
        `[p]kick 1234567890` - kicks the user with the ID 1234567890 for no reason
        """
        if await self.kick_method(user=user, guild=ctx.guild, reason=reason):
            await ctx.reply(f"Kicked **{user}** for reason: **{reason}**")
            await self.mod_log(ctx=ctx, target=user, message=reason)
        else:
            await ctx.reply(f"Failed kicking **{user}**.\n{HELP_MESSAGE_KICK_BAN}")

    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban_command(
        self,
        ctx: Context,
        user: Annotated[discord.Member, MemberID],
        *,
        reason: Annotated[str | None, ActionReason] = None,
    ) -> None:
        """Ban a user from the server.

        Both the bot and the user invoking the command must have the `Ban Members` permission.
        The bot will not ban users under the following conditions:
        - The user is the owner of the server
        - The invoker is user themselves
        - The invoker top role position is equal to or lower than the user top role position
        - The bot top role position is equal to or lower than the user top role position

        Example:
        -------
        `[p]ban @user spamming` - bans the user for "spamming"
        `[p]ban 1234567890 idk` - bans the user with the ID 1234567890 for "idk"

        Providing reason is Optional. Can be left blank. Exmaple:
        `[p]ban @user` - bans the user for no reason
        `[p]ban 1234567890` - bans the user with the ID 1234567890 for no reason
        """
        if await self.ban_method(user=user, guild=ctx.guild, reason=reason):
            await ctx.reply(f"Banned **{user}** for reason: **{reason}**")
            await self.mod_log(ctx=ctx, target=user, message=reason)
        else:
            await ctx.reply(f"Failed banning **{user}**.\n{HELP_MESSAGE_KICK_BAN}")

    @commands.command(name="unban")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban_command(
        self,
        ctx: Context,
        user: Annotated[discord.Member | discord.User, BannedMember],
        *,
        reason: Annotated[str | None, ActionReason] = None,
    ) -> None:
        """Unban a user from the server.

        Both the bot and the user invoking the command must have the `Ban Members` permission.

        Example:
        -------
        `[p]unban @user appeal accepted` - unbans the user for "appeal accepted"
        `[p]unban 1234567890 idk` - unbans the user with the ID 1234567890 for "idk"

        Providing reason is Optional. Can be left blank. Exmaple:
        `[p]unban @user` - unbans the user for no reason
        `[p]unban 1234567890` - unbans the user with the ID 1234567890 for no reason
        """
        if await self.unban_method(user=user, guild=ctx.guild, reason=reason):
            await ctx.reply(f"Unbanned **{user}** for reason: **{reason}**")
            await self.mod_log(ctx=ctx, target=user, message=reason)
        else:
            await ctx.reply(f"Failed unbanning **{user}**.\n{HELP_MESSAGE_KICK_BAN}")

    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lock_command(
        self,
        ctx: Context,
        channel: discord.TextChannel | discord.VoiceChannel | None = None,
        *,
        reason: Annotated[str | None, ActionReason] = None,
    ) -> None:
        """Lock the text channel or voice channel the command is invoked in or the channel specified.

        Both the bot and the user invoking the command must have the `Manage Channels` permission.

        What bot does:-

        - Text Channel:
            - Denies `Send Messages` permission for @everyone role
        - Voice Channel:
            - Denies `Speak` permission for @everyone role

        Example:
        -------
        `[p]lock #general spamming` - locks the #general channel for "spamming"
        `[p]lock 1234567890 idk` - locks the channel with the ID 1234567890 for "idk"

        Providing reason is Optional. Can be left blank. Exmaple:
        `[p]lock #general` - locks the #general channel for no reason
        `[p]lock 1234567890` - locks the channel with the ID 1234567890 for no reason
        """
        ch = channel or ctx.channel  # type: discord.TextChannel | discord.VoiceChannel  # type: ignore
        if await self.lock_channel_method(channel=ch, reason=reason):
            await ctx.reply(f"Locked **{ch}**.")
            await self.mod_log(ctx=ctx, target=ch, message=reason)
        else:
            await ctx.reply(f"Failed locking **{ch}**.")

    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlock_command(
        self,
        ctx: Context,
        channel: discord.TextChannel | discord.VoiceChannel | None = None,
        *,
        reason: Annotated[str | None, ActionReason] = None,
    ) -> None:
        """Unlock the text channel or voice channel the command is invoked in or the channel specified.

        Both the bot and the user invoking the command must have the `Manage Channels` permission.

        What bot does:-

        - Text Channel:
            - Allows `Send Messages` permission for @everyone role
        - Voice Channel:
            - Allows `Speak` permission for @everyone role

        Example:
        -------
        `[p]unlock #general spamming` - unlocks the #general channel for "spamming"
        `[p]unlock 1234567890 idk` - unlocks the channel with the ID 1234567890 for "idk"

        Providing reason is Optional. Can be left blank. Exmaple:
        `[p]unlock #general` - unlocks the #general channel for no reason
        `[p]unlock 1234567890` - unlocks the channel with the ID 1234567890 for no reason
        """
        ch = channel or ctx.channel  # type: discord.TextChannel | discord.VoiceChannel  # type: ignore
        if await self.unlock_channel_method(channel=ch, reason=reason):
            await ctx.reply(f"Unlocked **{ch}**.")
            await self.mod_log(ctx=ctx, target=ch, message=reason)
        else:
            await ctx.reply(f"Failed unlocking **{ch}**.")

    @commands.group(name="purge", invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True, read_message_history=True)
    async def purge_command(self, ctx: Context, limit: int | None = 100) -> None:
        """Purge messages from a channel.

        Both the bot and the user invoking the command must have the `Manage Messages` permission.
        And the bot must have the `Read Message History` permission.

        Example:
        -------
        `[p]purge 50` - purges last 50 messages
        `[p]purge 100` - purges last 100 messages

        Providing limit is Optional. Can be left blank. Exmaple:
        `[p]purge` - purges last 100 messages
        """
        if ctx.invoked_subcommand is None:

            def check(_: discord.Message) -> bool:
                return True

            if await self.purge_method(ctx, limit or 100, check):
                await ctx.reply(f"Purged **{limit or 100}** messages.")
            else:
                await ctx.reply("Failed purging messages. Try smaller amount.")

    @purge_command.command()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def embeds(self, ctx: Context, search: int = 100) -> None:
        """Removes messages that have embeds in them."""
        await self.purge_method(ctx, search, lambda e: bool(len(e.embeds)))

    @purge_command.command(name="regex")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def _regex(self, ctx: Context, pattern: str | None = None, search: int = 100) -> None:
        """Removed messages that matches the regex pattern."""
        pattern = pattern or r".*"

        def check(m: discord.Message) -> bool:
            return bool(re.match(rf"{pattern}", m.content))

        await self.purge_method(ctx, search, check)

    @purge_command.command()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def files(self, ctx: Context, search: int = 100) -> None:
        """Removes messages that have attachments in them."""
        await self.purge_method(ctx, search, lambda e: bool(len(e.attachments)))

    @purge_command.command()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def images(self, ctx: Context, search: int = 100) -> None:
        """Removes messages that have embeds or attachments."""
        await self.purge_method(ctx, search, lambda e: bool(len(e.embeds) or len(e.attachments)))

    @purge_command.command()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def user(self, ctx: Context, member: discord.Member, search: int = 100) -> None:
        """Removes all messages by the member."""
        await self.purge_method(ctx, search, lambda e: e.author == member)

    @purge_command.command()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def contains(self, ctx: Context, *, substr: str) -> None:
        """Removes all messages containing a substring.

        The substring must be at least 3 characters long.
        """
        if len(substr) < 3:
            await ctx.reply("The substring length must be at least 3 characters.")
        else:
            await self.purge_method(ctx, 100, lambda e: substr in e.content)

    @purge_command.command(name="bot", aliases=["bots"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def _bot(self, ctx: Context, prefix: str | None = None, search: int = 100) -> None:
        """Removes a bot user's messages and messages with their optional prefix."""

        def predicate(m: discord.Message) -> bool:
            return bool((m.webhook_id is None and m.author.bot) or (prefix and m.content.startswith(prefix)))

        await self.purge_method(ctx, search, predicate)

    @purge_command.command(name="emoji", aliases=["emojis"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def _emoji(self, ctx: Context, search: int = 100) -> None:
        """Removes all messages containing custom emoji."""
        custom_emoji = re.compile(r"<a?:[a-zA-Z0-9\_]+:([0-9]+)>")

        def predicate(m: discord.Message) -> bool:
            return bool(custom_emoji.search(m.content))

        await self.purge_method(ctx, search, predicate)

    @purge_command.command(name="reactions")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def _reactions(self, ctx: Context, search: int = 100) -> None:
        """Removes all reactions from messages that have them."""
        if search > 2000:
            await ctx.reply(f"Too many messages to search for ({search}/2000)")
            return

        total_reactions = 0
        async for message in ctx.history(limit=search, before=ctx.message):
            if len(message.reactions):
                total_reactions += sum(r.count for r in message.reactions)
                await message.clear_reactions()

        await ctx.reply(f"Successfully removed {total_reactions} reactions.")

    @purge_command.command(name="all")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def _all(self, ctx: Context, search: int = 100) -> None:
        """Removes all messages. This is equivalent to `[p]purge` command."""
        await self.purge_method(ctx, search, lambda e: True)

    @purge_command.command(name="custom")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def custom(  # noqa: C901  # pylint: disable=too-many-statements, too-many-branches
        self,
        ctx: Context,
        *,
        arguments: str,
    ) -> None:
        """A more advanced purge command.

        This command uses a powerful "command line" syntax.

        Most options support multiple values to indicate 'any' match.
        If the value has spaces it must be quoted.
        The messages are only deleted if all options are met unless the `--or` flag is passed, in which case only if any is met.

        The following options are valid.
        `--user`: A mention or name of the user to remove.
        `--contains`: A substring to search for in the message.
        `--starts`: A substring to search if the message starts with.
        `--ends`: A substring to search if the message ends with.
        `--search`: How many messages to search. Default 100. Max 2000.
        `--after`: Messages must come after this message ID.
        `--before`: Messages must come before this message ID.

        Flag options (no arguments):
        `--bot`: Check if it's a bot user.
        `--embeds`: Check if the message has embeds.
        `--files`: Check if the message has attachments.
        `--emoji`: Check if the message has custom emoji.
        `--reactions`: Check if the message has reactions
        `--or`: Use logical OR for all options.
        `--not`: Use logical NOT for all options.

        Examples
        --------
        - `[p]purge custom --user @user --contains "hello world" --embeds`
            - This will remove all messages by @user that contain "hello world" and have embeds.

        - `[p]purge custom --contains cum --not --user @user`
            - This will remove all messages that contain "cum" but are not by @user.
        """
        parser = Arguments(add_help=False, allow_abbrev=False)
        parser.add_argument("--user", nargs="+")
        parser.add_argument("--contains", nargs="+")
        parser.add_argument("--starts", nargs="+")
        parser.add_argument("--ends", nargs="+")
        parser.add_argument("--or", action="store_true", dest="_or")
        parser.add_argument("--not", action="store_true", dest="_not")
        parser.add_argument("--emoji", action="store_true")
        parser.add_argument("--bot", action="store_const", const=lambda m: m.author.bot)
        parser.add_argument("--embeds", action="store_const", const=lambda m: len(m.embeds))
        parser.add_argument("--files", action="store_const", const=lambda m: len(m.attachments))
        parser.add_argument("--reactions", action="store_const", const=lambda m: len(m.reactions))
        parser.add_argument("--search", type=int)
        parser.add_argument("--after", type=int)
        parser.add_argument("--before", type=int)

        try:
            args = parser.parse_args(shlex.split(arguments))
        except Exception as e:  # pylint: disable=broad-except
            await ctx.reply(str(e))
            return

        predicates = []
        if args.bot:
            predicates.append(args.bot)

        if args.embeds:
            predicates.append(args.embeds)

        if args.files:
            predicates.append(args.files)

        if args.reactions:
            predicates.append(args.reactions)

        if args.emoji:
            custom_emoji = re.compile(r"<:(\w+):(\d+)>")
            predicates.append(lambda m: custom_emoji.search(m.content))

        if args.user:
            users = []
            converter = commands.MemberConverter()
            for u in args.user:
                try:
                    user = await converter.convert(ctx, u)
                    users.append(user)
                except (commands.CommandError, commands.BadArgument) as e:
                    await ctx.reply(str(e))
                    return

            predicates.append(lambda m: m.author in users)

        if args.contains:
            predicates.append(lambda m: any(sub in m.content for sub in args.contains))

        if args.starts:
            predicates.append(lambda m: any(m.content.startswith(s) for s in args.starts))

        if args.ends:
            predicates.append(lambda m: any(m.content.endswith(s) for s in args.ends))

        op = any if args._or else all  # pylint: disable=protected-access

        def predicate(m: discord.Message) -> bool:
            r = op(p(m) for p in predicates)
            return not r if args._not else r  # pylint: disable=protected-access

        if args.after and args.search is None:
            args.search = 2000

        if args.search is None:
            args.search = 100

        args.search = max(0, min(2000, args.search))  # clamp from 0-2000
        await self.purge_method(ctx, args.search, predicate, before=args.before, after=args.after)

    @commands.command(name="timeout", aliases=["mute", "stfu"])
    @commands.has_permissions(manage_messages=True, moderate_members=True)
    @commands.bot_has_guild_permissions(moderate_members=True)
    async def timeout(
        self,
        ctx: Context,
        user: Annotated[discord.Member, MemberID],
        duration: ShortTime,
        *,
        reason: Annotated[str | None, ActionReason] = None,
    ) -> None:
        """Timeout a user for a specified duration.

        Bot must have `Time Out Members` permission.
        Also invoker must have `Time Out Members` and `Manage Messages` permissions.

        The duration can be specified as a number followed by a unit.
        Valid units are `s`, `m`, `h`, `d`, `w`

        For example, `1h` would be 1 hour, `5m` would be 5 minutes, `2d` would be 2 days.

        Note: The duration cannot be more than 28 days.

        Examples
        --------
        - `[p]timeout @user 1h`
            - This will time out @user for 1 hour.
        """
        if duration.dt > discord.utils.utcnow() + datetime.timedelta(days=28):
            msg = "Timeout duration cannot be more than 28 days. Consider banning instead."
            raise commands.BadArgument(msg)

        if await self.timeout_method(user=user, duration=duration.dt, reason=reason, guild=ctx.guild):
            await ctx.reply(
                f"Successfully timed out {user}. Timeout will remove **{discord.utils.format_dt(duration.dt, 'R')}**.",
            )
            await self.mod_log(ctx=ctx, target=user, message=reason)

    @commands.command(name="untimeout", aliases=["unmute"])
    @commands.has_permissions(manage_messages=True, moderate_members=True)
    @commands.bot_has_guild_permissions(moderate_members=True)
    async def untimeout(
        self,
        ctx: Context,
        user: Annotated[discord.Member, MemberID],
        *,
        reason: Annotated[str | None, ActionReason] = None,
    ) -> None:
        """Untimeout a user.

        Bot must have `Time Out Members` permission.
        Also invoker must have `Time Out Members` and `Manage Messages` permissions.

        Examples
        --------
        - `[p]untimeout @user`
            - This will remove the timeout from @user.
        """
        if await self.unmute_method(user=user, reason=reason, guild=ctx.guild):
            await ctx.reply(f"Successfully removed timeout from {user}.")
            await self.mod_log(ctx=ctx, target=user, message=reason)

    @commands.group(name="add")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def add(self, ctx: Context) -> None:
        """Add a role to a user.

        Bot must have `Manage Roles` permission.
        Also invoker must have `Manage Roles` permission.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @add.command(name="role")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def add_role(
        self,
        ctx: Context,
        user: Annotated[discord.Member, MemberID],
        role: Annotated[discord.Role, RoleID],
        *,
        reason: Annotated[str | None, ActionReason] = None,
    ) -> None:
        """Add a role to a user.

        Bot must have `Manage Roles` permission.
        Also invoker must have `Manage Roles` permission.

        Examples
        --------
        - `[p]add role @user @role reason`
            - This will add @role to @user with the reason `reason`.

        Notes
        -----
        - The reason is optional.
        """
        if await self.add_role_method(user=user, role=role, guild=ctx.guild, reason=reason):  # type: ignore
            await ctx.reply(f"Successfully added {role} to {user}.")
            await self.mod_log(ctx=ctx, target=user, message=reason)

    @commands.group(name="remove")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def remove(self, ctx: Context) -> None:
        """Remove a role from a user.

        Bot must have `Manage Roles` permission.
        Also invoker must have `Manage Roles` permission.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @remove.command(name="role")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def remove_role(
        self,
        ctx: Context,
        user: Annotated[discord.Member, MemberID],
        role: Annotated[discord.Role, RoleID],
        *,
        reason: Annotated[str | None, ActionReason] = None,
    ) -> None:
        """Remove a role from a user.

        Bot must have `Manage Roles` permission.
        Also invoker must have `Manage Roles` permission.

        Examples
        --------
        - `[p]remove role @user @role reason`
            - This will remove @role from @user with the reason `reason`.

        Notes
        -----
        - The reason is optional.
        """
        if await self.remove_role_method(user=user, role=role, guild=ctx.guild, reason=reason):
            await ctx.reply(f"Successfully removed {role} from {user}.")
            await self.mod_log(ctx=ctx, target=user, message=reason)


async def setup(bot: Bot) -> None:
    """Load the Mod cog."""
    await bot.add_cog(Mod(bot))
