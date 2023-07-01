from __future__ import annotations

import argparse
import datetime
import logging
import re
import shlex
from typing import Any, Callable, Optional, Union

import discord
from discord.ext import commands
from typing_extensions import Annotated

from core import Bot, Cog, Context
from utils import ActionReason, BannedMember, MemberID, RoleID, ShortTime

log = logging.getLogger("mod")


class Arguments(argparse.ArgumentParser):
    def error(self, message: str):
        raise RuntimeError(message)


HELP_MESSAGE_KICK_BAN = """
- Make sure Bot role is above the target role in the role hierarchy.
- Make sure Bot has the permission to kick/ban members.
- Make sure Bot can access the target channel/member.
"""


class Mod(Cog):
    """Moderation commands."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: Context) -> bool:
        if not ctx.guild:
            raise commands.BadArgument("This command can only be used in a server.")
        return ctx.guild is not None

    async def kick_method(self, *, user: discord.Member | discord.User, guild: discord.Guild, reason: str) -> bool:
        if member := guild.get_member(user.id):
            try:
                log.debug("kicking %s from guild %s", member, guild.name)
                await member.kick(reason=reason)
            except discord.Forbidden:
                return False
            else:
                return True

        raise commands.BadArgument(f"User `{user}` is not a member of guild `{guild.name}`")

    async def ban_method(self, *, user: discord.Member | discord.User, guild: discord.Guild, reason: str) -> bool:
        try:
            log.debug("banning %s from guild %s", user, guild.name)
            await guild.ban(user, reason=reason)
        except discord.Forbidden:
            return False
        else:
            return True

    async def unban_method(self, *, user: discord.User, guild: discord.Guild, reason: str) -> bool:
        try:
            log.debug("unbanning %s from guild %s", user, guild.name)
            await guild.unban(user, reason=reason)
        except discord.Forbidden:
            return False
        else:
            return True

    async def lock_channel_method(self, *, channel: discord.TextChannel | discord.VoiceChannel, reason: str) -> bool:
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
        else:
            return True

    async def unlock_channel_method(self, *, channel: discord.TextChannel | discord.VoiceChannel, reason: str) -> bool:
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
        else:
            return True

    async def purge_method(
        self,
        ctx: Context,
        limit: int,
        predicate: Callable[[discord.Message], Any],
        *,
        before: int | None = None,
        after: int | None = None,
    ) -> bool:
        if limit > 1000:
            raise commands.BadArgument("Can only purge up to 1000 messages at a time.")

        passed_before = ctx.message if before is None else discord.Object(before)
        passed_after = discord.Object(after) if after is not None else None

        try:
            if isinstance(
                ctx.channel,
                (
                    discord.TextChannel,
                    discord.Thread,
                    discord.ForumChannel,
                    discord.VoiceChannel,
                ),
            ):
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
                return True
            else:
                raise commands.BadArgument("This command can only be used in text channels.")
        except discord.Forbidden:
            return False

    async def timeout_method(
        self,
        *,
        user: discord.Member | discord.User,
        guild: discord.Guild,
        duration: datetime.datetime,
        reason: Optional[str] = None,
    ) -> bool:
        member = guild.get_member(user.id)
        if member is None:
            raise commands.BadArgument(f"User `{user}` is not a member of guild `{guild.name}`")

        if member.timed_out_until is not None and member.timed_out_until > discord.utils.utcnow():
            raise commands.BadArgument(
                f"User `{member}` is already timed out. Their timeout will remove **{discord.utils.format_dt(member.timed_out_until, 'R')}**"
            )

        try:
            log.debug("timing out %s in guild %s till %s", member, guild.name, duration)
            await member.timeout(duration, reason=reason)
        except discord.Forbidden:
            return False
        else:
            return True

    async def unmute_method(
        self,
        *,
        user: discord.Member | discord.User,
        guild: discord.Guild,
        reason: Optional[str] = None,
    ) -> bool:
        member = guild.get_member(user.id)
        if member is None:
            raise commands.BadArgument(f"User `{user}` is not a member of guild `{guild.name}`")

        if member.timed_out_until is None:
            return False

        try:
            log.debug("unmuting %s in guild %s", member, guild.name)
            await member.edit(timed_out_until=None, reason=reason)
        except discord.Forbidden:
            return False
        else:
            return True

    async def add_role_method(
        self,
        *,
        user: discord.Member | discord.User,
        guild: discord.Guild,
        role: discord.Role,
        reason: Optional[str] = None,
    ) -> bool:
        member = guild.get_member(user.id)
        if member is None:
            raise commands.BadArgument(f"User `{user}` is not a member of guild `{guild.name}`")

        try:
            log.debug("adding role %s to %s in guild %s", role.name, member, guild.name)
            await member.add_roles(role, reason=reason)
        except discord.Forbidden:
            return False
        else:
            return True

    async def remove_role_method(
        self,
        *,
        user: discord.Member | discord.User,
        guild: discord.Guild,
        role: discord.Role,
        reason: Optional[str] = None,
    ) -> bool:
        member = guild.get_member(user.id)
        if member is None:
            raise commands.BadArgument(f"User `{user}` is not a member of guild `{guild.name}`")

        try:
            log.debug("removing role %s from %s in guild %s", role.name, member, guild.name)
            await member.remove_roles(role, reason=reason)
        except discord.Forbidden:
            return False
        else:
            return True

    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick_command(
        self,
        ctx: Context,
        user: MemberID,
        *,
        reason: Annotated[Optional[str], ActionReason] = None,
    ) -> None:
        """Kick a user from the server.

        Both the bot and the user invoking the command must have the `Kick Members` permission.
        The bot will not kick users under the following conditions:
        - The user is the owner of the server
        - The invoker is user themselves
        - The invoker top role position is equal to or lower than the user top role position
        - The bot top role position is equal to or lower than the user top role position

        Example:
        `[p]kick @user spamming` - kicks the user for "spamming"
        `[p]kick 1234567890 idk` - kicks the user with the ID 1234567890 for "idk"

        Providing reason is Optional. Can be left blank. Exmaple:
        `[p]kick @user` - kicks the user for no reason
        `[p]kick 1234567890` - kicks the user with the ID 1234567890 for no reason
        """
        if await self.kick_method(user=user, guild=ctx.guild, reason=reason):  # type: ignore
            await ctx.send(f"Kicked **{user}** for reason: **{reason}**")
        else:
            await ctx.send(f"Failed kicking **{user}**.\n{HELP_MESSAGE_KICK_BAN}")

    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban_command(
        self,
        ctx: Context,
        user: MemberID,
        *,
        reason: Annotated[Optional[str], ActionReason] = None,
    ) -> None:
        """Ban a user from the server.

        Both the bot and the user invoking the command must have the `Ban Members` permission.
        The bot will not ban users under the following conditions:
        - The user is the owner of the server
        - The invoker is user themselves
        - The invoker top role position is equal to or lower than the user top role position
        - The bot top role position is equal to or lower than the user top role position

        Example:
        `[p]ban @user spamming` - bans the user for "spamming"
        `[p]ban 1234567890 idk` - bans the user with the ID 1234567890 for "idk"

        Providing reason is Optional. Can be left blank. Exmaple:
        `[p]ban @user` - bans the user for no reason
        `[p]ban 1234567890` - bans the user with the ID 1234567890 for no reason
        """
        if await self.ban_method(user=user, guild=ctx.guild, reason=reason):  # type: ignore
            await ctx.send(f"Banned **{user}** for reason: **{reason}**")
        else:
            await ctx.send(f"Failed banning **{user}**.\n{HELP_MESSAGE_KICK_BAN}")

    @commands.command(name="unban")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban_command(
        self,
        ctx: Context,
        user: BannedMember,
        *,
        reason: Annotated[Optional[str], ActionReason] = None,
    ) -> None:
        """Unban a user from the server.

        Both the bot and the user invoking the command must have the `Ban Members` permission.

        Example:
        `[p]unban @user appeal accepted` - unbans the user for "appeal accepted"
        `[p]unban 1234567890 idk` - unbans the user with the ID 1234567890 for "idk"

        Providing reason is Optional. Can be left blank. Exmaple:
        `[p]unban @user` - unbans the user for no reason
        `[p]unban 1234567890` - unbans the user with the ID 1234567890 for no reason
        """
        if await self.unban_method(user=user, guild=ctx.guild, reason=reason):  # type: ignore
            await ctx.send(f"Unbanned **{user}** for reason: **{reason}**")
        else:
            await ctx.send(f"Failed unbanning **{user}**.\n{HELP_MESSAGE_KICK_BAN}")

    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lock_command(
        self,
        ctx: Context,
        channel: Optional[Union[discord.TextChannel, discord.VoiceChannel]] = None,
        *,
        reason: Annotated[Optional[str], ActionReason] = None,
    ) -> None:
        """Lock the text channel or voice channel the command is invoked in or the channel specified.

        Both the bot and the user invoking the command must have the `Manage Channels` permission.

        What bot does:-

        - Text Channel:
            - Denies `Send Messages` permission for @everyone role
        - Voice Channel:
            - Denies `Speak` permission for @everyone role

        Example:
        `[p]lock #general spamming` - locks the #general channel for "spamming"
        `[p]lock 1234567890 idk` - locks the channel with the ID 1234567890 for "idk"

        Providing reason is Optional. Can be left blank. Exmaple:
        `[p]lock #general` - locks the #general channel for no reason
        `[p]lock 1234567890` - locks the channel with the ID 1234567890 for no reason
        """
        channel = channel or ctx.channel  # type: ignore
        if await self.lock_channel_method(channel=channel, reason=reason):  # type: ignore
            await ctx.send(f"Locked **{channel}**.")
        else:
            await ctx.send(f"Failed locking **{channel}**.")

    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlock_command(
        self,
        ctx: Context,
        channel: Optional[Union[discord.TextChannel, discord.VoiceChannel]] = None,
        *,
        reason: Annotated[Optional[str], ActionReason] = None,
    ) -> None:
        """Unlock the text channel or voice channel the command is invoked in or the channel specified.

        Both the bot and the user invoking the command must have the `Manage Channels` permission.

        What bot does:-

        - Text Channel:
            - Allows `Send Messages` permission for @everyone role
        - Voice Channel:
            - Allows `Speak` permission for @everyone role

        Example:
        `[p]unlock #general spamming` - unlocks the #general channel for "spamming"
        `[p]unlock 1234567890 idk` - unlocks the channel with the ID 1234567890 for "idk"

        Providing reason is Optional. Can be left blank. Exmaple:
        `[p]unlock #general` - unlocks the #general channel for no reason
        `[p]unlock 1234567890` - unlocks the channel with the ID 1234567890 for no reason
        """
        channel = channel or ctx.channel  # type: ignore
        if await self.unlock_channel_method(channel=channel, reason=reason):  # type: ignore
            await ctx.send(f"Unlocked **{channel}**.")
        else:
            await ctx.send(f"Failed unlocking **{channel}**.")

    @commands.group(name="purge", invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True, read_message_history=True)
    async def purge_command(self, ctx: Context, limit: Optional[int] = 100) -> None:
        """Purge messages from a channel.

        Both the bot and the user invoking the command must have the `Manage Messages` permission.
        And the bot must have the `Read Message History` permission.

        Example:
        `[p]purge 50` - purges last 50 messages
        `[p]purge 100` - purges last 100 messages

        Providing limit is Optional. Can be left blank. Exmaple:
        `[p]purge` - purges last 100 messages
        """
        if ctx.invoked_subcommand is None:

            def check(message: discord.Message) -> bool:
                return True

            if await self.purge_method(ctx, limit or 100, check):
                await ctx.send(f"Purged **{limit or 100}** messages.")
            else:
                await ctx.send("Failed purging messages. Try smaller amount.")

    @purge_command.command()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def embeds(self, ctx: Context, search: int = 100):
        """Removes messages that have embeds in them."""
        await self.purge_method(ctx, search, lambda e: len(e.embeds))

    @purge_command.command(name="regex")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def _regex(self, ctx: Context, pattern: Optional[str] = None, search: int = 100):
        """Removed messages that matches the regex pattern."""
        pattern = pattern or r".*"

        def check(m: discord.Message) -> bool:
            return bool(re.match(rf"{pattern}", m.content))

        await self.purge_method(ctx, search, check)

    @purge_command.command()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def files(self, ctx: Context, search: int = 100):
        """Removes messages that have attachments in them."""
        await self.purge_method(ctx, search, lambda e: len(e.attachments))

    @purge_command.command()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def images(self, ctx: Context, search: int = 100):
        """Removes messages that have embeds or attachments."""
        await self.purge_method(ctx, search, lambda e: len(e.embeds) or len(e.attachments))

    @purge_command.command()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def user(self, ctx: Context, member: discord.Member, search: int = 100):
        """Removes all messages by the member."""
        await self.purge_method(ctx, search, lambda e: e.author == member)

    @purge_command.command()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def contains(self, ctx: Context, *, substr: str):
        """Removes all messages containing a substring.
        The substring must be at least 3 characters long.
        """
        if len(substr) < 3:
            await ctx.send("The substring length must be at least 3 characters.")
        else:
            await self.purge_method(ctx, 100, lambda e: substr in e.content)

    @purge_command.command(name="bot", aliases=["bots"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def _bot(self, ctx: Context, prefix: Optional[str] = None, search: int = 100):
        """Removes a bot user's messages and messages with their optional prefix."""

        def predicate(m: discord.Message):
            return (m.webhook_id is None and m.author.bot) or (prefix and m.content.startswith(prefix))

        await self.purge_method(ctx, search, predicate)

    @purge_command.command(name="emoji", aliases=["emojis"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def _emoji(self, ctx: Context, search: int = 100):
        """Removes all messages containing custom emoji."""
        custom_emoji = re.compile(r"<a?:[a-zA-Z0-9\_]+:([0-9]+)>")

        def predicate(m: discord.Message):
            return custom_emoji.search(m.content)

        await self.purge_method(ctx, search, predicate)

    @purge_command.command(name="reactions")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def _reactions(self, ctx: Context, search: int = 100):
        """Removes all reactions from messages that have them."""

        if search > 2000:
            return await ctx.send(f"Too many messages to search for ({search}/2000)")

        total_reactions = 0
        async for message in ctx.history(limit=search, before=ctx.message):
            if len(message.reactions):
                total_reactions += sum(r.count for r in message.reactions)
                await message.clear_reactions()

        await ctx.send(f"Successfully removed {total_reactions} reactions.")

    @purge_command.command(name="all")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def _all(self, ctx: Context, search: int = 100):
        """Removes all messages. This is equivalent to `[p]purge` command."""
        await self.purge_method(ctx, search, lambda e: True)

    @purge_command.command(name="custom")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, manage_messages=True)
    async def custom(self, ctx: Context, *, arguments: str):
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

        Examples:
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
        except Exception as e:
            await ctx.send(str(e))
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
                except Exception as e:
                    await ctx.send(str(e))
                    return

            predicates.append(lambda m: m.author in users)

        if args.contains:
            predicates.append(lambda m: any(sub in m.content for sub in args.contains))

        if args.starts:
            predicates.append(lambda m: any(m.content.startswith(s) for s in args.starts))

        if args.ends:
            predicates.append(lambda m: any(m.content.endswith(s) for s in args.ends))

        op = any if args._or else all

        def predicate(m: discord.Message):
            r = op(p(m) for p in predicates)
            return not r if args._not else r

        if args.after and args.search is None:
            args.search = 2000

        if args.search is None:
            args.search = 100

        args.search = max(0, min(2000, args.search))  # clamp from 0-2000
        await self.purge_method(ctx, args.search, predicate, before=args.before, after=args.after)

    @commands.command(name="timeout", aliases=["mute"])
    @commands.has_permissions(manage_messages=True, moderate_members=True)
    @commands.bot_has_guild_permissions(moderate_members=True)
    async def timeout(
        self,
        ctx: Context,
        user: MemberID,
        duration: ShortTime,
        *,
        reason: Annotated[Optional[str], ActionReason] = None,
    ):
        """Timeout a user for a specified duration.

        Bot must have `Time Out Members` permission.
        Also invoker must have `Time Out Members` and `Manage Messages` permissions.

        The duration can be specified as a number followed by a unit.
        Valid units are `s`, `m`, `h`, `d`, `w`

        For example, `1h` would be 1 hour, `5m` would be 5 minutes, `2d` would be 2 days.

        Examples:
        - `[p]timeout @user 1h`
            - This will time out @user for 1 hour.
        """

        if await self.timeout_method(user=user, duration=duration.dt, reason=reason, guild=ctx.guild):  # type: ignore
            await ctx.send(
                f"Successfully timed out {user}. Timeout will remove **{discord.utils.format_dt(duration.dt, 'R')}**."
            )

    @commands.command(name="untimeout", aliases=["unmute"])
    @commands.has_permissions(manage_messages=True, moderate_members=True)
    @commands.bot_has_guild_permissions(moderate_members=True)
    async def untimeout(
        self,
        ctx: Context,
        user: MemberID,
        *,
        reason: Annotated[Optional[str], ActionReason] = None,
    ):
        """Untimeout a user.

        Bot must have `Time Out Members` permission.
        Also invoker must have `Time Out Members` and `Manage Messages` permissions.

        Examples:
        - `[p]untimeout @user`
            - This will remove the timeout from @user.
        """

        if await self.unmute_method(user=user, reason=reason, guild=ctx.guild):  # type: ignore
            await ctx.send(f"Successfully removed timeout from {user}.")

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
        user: MemberID,
        role: RoleID,
        *,
        reason: Annotated[Optional[str], ActionReason],
    ) -> None:
        """Add a role to a user.

        Bot must have `Manage Roles` permission.
        Also invoker must have `Manage Roles` permission.

        Examples:
        - `[p]add role @user @role reason`
            - This will add @role to @user with the reason `reason`.

        Notes:
        - The reason is optional.
        """

        if await self.add_role_method(user=user, role=role, guild=ctx.guild, reason=reason):  # type: ignore
            await ctx.send(f"Successfully added {role} to {user}.")

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
        user: MemberID,
        role: RoleID,
        *,
        reason: Annotated[Optional[str], ActionReason],
    ) -> None:
        """Remove a role from a user.

        Bot must have `Manage Roles` permission.
        Also invoker must have `Manage Roles` permission.

        Examples:
        - `[p]remove role @user @role reason`
            - This will remove @role from @user with the reason `reason`.

        Notes:
        - The reason is optional.
        """

        if await self.remove_role_method(user=user, role=role, guild=ctx.guild, reason=reason):  # type: ignore
            await ctx.send(f"Successfully removed {role} from {user}.")


async def setup(bot: Bot) -> None:
    await bot.add_cog(Mod(bot))
