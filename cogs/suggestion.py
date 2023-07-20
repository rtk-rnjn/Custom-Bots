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

import io
import logging
from typing import Optional, Union

import discord
from discord.ext import commands

from core import Bot, Cog, Context  # pylint: disable=import-error

REACTION_EMOJI = ["\N{UPWARDS BLACK ARROW}", "\N{DOWNWARDS BLACK ARROW}"]

OTHER_REACTION = {
    "INVALID": {"emoji": "\N{WARNING SIGN}", "color": 0xFFFFE0},
    "ABUSE": {"emoji": "\N{DOUBLE EXCLAMATION MARK}", "color": 0xFFA500},
    "INCOMPLETE": {"emoji": "\N{WHITE QUESTION MARK ORNAMENT}", "color": 0xFFFFFF},
    "DECLINE": {"emoji": "\N{CROSS MARK}", "color": 0xFF0000},
    "APPROVED": {"emoji": "\N{WHITE HEAVY CHECK MARK}", "color": 0x90EE90},
    "DUPLICATE": {"emoji": "\N{HEAVY EXCLAMATION MARK SYMBOL}", "color": 0xDDD6D5},
}

log = logging.getLogger("suggestion")


class Suggestions(Cog):
    """Suggestion cog for the bot."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.message: dict[int, dict] = {}

    async def __fetch_suggestion_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        if guild.id == self.bot.config.guild_id:
            log.debug("fetching suggestion channel from config")
            return self.bot.get_channel(self.bot.config.suggestion_channel)  # type: ignore

    async def get_or_fetch_message(
        self, msg_id: int, *, guild: discord.Guild, channel: discord.TextChannel | None = None,
    ) -> Optional[discord.Message]:
        """Get or fetch a message from the cache or API."""
        if guild.id != self.bot.config.guild_id:
            return

        channel_id = 0
        try:
            self.message[msg_id]
        except KeyError:
            if channel is None:
                try:
                    channel_id: int = self.bot.config.suggestion_channel
                except (KeyError, AttributeError) as e:
                    raise commands.BadArgument("No suggestion channel is setup") from e
            msg = await self.__fetch_message_from_channel(message=msg_id, channel=self.bot.get_channel(channel_id))
        else:
            msg = self.message[msg_id]["message"]

        return msg if (msg and (msg.author.id == self.bot.user.id)) else None

    async def __fetch_message_from_channel(
        self, *, message: int, channel: discord.abc.GuildChannel | discord.Thread | discord.abc.PrivateChannel | None,
    ) -> discord.Message | None:
        assert isinstance(channel, discord.TextChannel)

        async for msg in channel.history(
            limit=1,
            before=discord.Object(message + 1),
            after=discord.Object(message - 1),
        ):
            payload = {
                "message_author": msg.author,
                "message": msg,
                "message_downvote": self.__get_emoji_count_from_msg(msg, emoji="\N{DOWNWARDS BLACK ARROW}"),
                "message_upvote": self.__get_emoji_count_from_msg(msg, emoji="\N{UPWARDS BLACK ARROW}"),
            }
            self.message[message] = payload
            return msg

    def __get_emoji_count_from_msg(
        self,
        msg: discord.Message,
        *,
        emoji: Union[discord.Emoji, discord.PartialEmoji, str],
    ) -> int:
        for reaction in msg.reactions:
            if str(reaction.emoji) == str(emoji):
                return reaction.count

        return 0

    async def __suggest(
        self,
        content: Optional[str] = None,
        *,
        embed: discord.Embed,
        ctx: Context,
        file: Optional[discord.File] = None,
    ) -> discord.Message:
        channel: Optional[discord.TextChannel] = await self.__fetch_suggestion_channel(ctx.guild)
        if channel is None:
            raise commands.BadArgument(f"{ctx.author.mention} error fetching suggestion channel")

        msg: discord.Message = await channel.send(content, embed=embed, file=file or discord.utils.MISSING)

        for reaction in REACTION_EMOJI:
            await msg.add_reaction(reaction)

        log.debug("creating thread for suggestion %s", msg.id)
        thread = await msg.create_thread(name=f"Suggestion {ctx.author}")

        payload = {
            "message_author": msg.author,
            "message_downvote": 0,
            "message_upvote": 0,
            "message": msg,
            "thread": thread.id,
        }
        self.message[msg.id] = payload
        return msg

    async def __notify_on_suggestion(self, ctx: Context, *, message: discord.Message) -> None:
        jump_url: str = message.jump_url
        _id: int = message.id
        content = (
            f"{ctx.author.mention} your suggestion being posted.\n"
            f"To delete the suggestion type: `{ctx.clean_prefix or self.bot.config.prefix}suggest delete {_id}`\n"
            f"> {jump_url}"
        )
        try:
            await ctx.author.send(content)
            log.debug("notified user %s on suggestion %s", ctx.author, _id)
        except discord.Forbidden:
            pass

    async def __notify_user(
        self,
        ctx: Context,
        user: Optional[discord.Member] = None,
        *,
        message: discord.Message,
        remark: str,
    ) -> None:
        if user is None:
            return

        remark = remark or "No remark was given"

        content = (
            f"{user.mention} your suggestion of ID: {message.id} had being updated.\n"
            f"By: {ctx.author} (`{ctx.author.id}`)\n"
            f"Remark: {remark}\n"
            f"> {message.jump_url}"
        )
        try:
            await user.send(content)
            log.debug("notified user %s on suggestion %s", user, message.id)
        except discord.Forbidden:
            pass

    @commands.group(aliases=["suggestion"], invoke_without_command=True)
    @commands.cooldown(1, 60, commands.BucketType.member)
    @commands.bot_has_permissions(embed_links=True, create_public_threads=True)
    async def suggest(self, ctx: Context, *, suggestion: commands.clean_content) -> None:
        """Suggest something. Abuse of the command may result in required mod actions."""
        if not ctx.invoked_subcommand:
            embed = (
                discord.Embed(description=suggestion, timestamp=ctx.message.created_at, color=0xADD8E6)
                .set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
                .set_footer(
                    text=f"Author ID: {ctx.author.id}",
                    icon_url=getattr(ctx.guild.icon, "url", ctx.author.display_avatar.url),
                )
            )

            file: Optional[discord.File] = None

            if ctx.message.attachments and (
                ctx.message.attachments[0].url.lower().endswith(("png", "jpeg", "jpg", "gif", "webp"))
            ):
                _bytes = await ctx.message.attachments[0].read(use_cached=True)
                file = discord.File(io.BytesIO(_bytes), "image.jpg")
                embed.set_image(url="attachment://image.jpg")

            msg = await self.__suggest(ctx=ctx, embed=embed, file=file)
            await self.__notify_on_suggestion(ctx, message=msg)
            await ctx.message.delete(delay=0)

    @suggest.command(name="set")
    @commands.cooldown(1, 60, commands.BucketType.member)
    @commands.has_permissions(manage_guild=True)
    async def suggest_set_channel(self, ctx: Context, *, channel: discord.TextChannel) -> None:
        """Set the suggestion channel."""
        self.bot.config.set_suggestion_channel(channel.id)
        await ctx.reply(f"{ctx.author.mention} Done", delete_after=5)
        await self.bot.config.update_to_db()

    @suggest.command(name="delete")
    @commands.cooldown(1, 60, commands.BucketType.member)
    @commands.bot_has_permissions(read_message_history=True)
    async def suggest_delete(self, ctx: Context, *, ID: int) -> None:  # noqa: N803
        """To delete the suggestion you suggested."""
        msg: Optional[discord.Message] = await self.get_or_fetch_message(ID, guild=ctx.guild)
        if not msg:
            await ctx.reply(
                f"{ctx.author.mention} Can not find message of ID `{ID}`. Probably already deleted, or `{ID}` is invalid",
            )
            return

        if ctx.channel.permissions_for(ctx.author).manage_messages:
            await msg.delete(delay=0)
            await ctx.reply(f"{ctx.author.mention} Done", delete_after=5)
            return

        try:
            if int(msg.embeds[0].footer.text.split(":")[1]) != ctx.author.id:  # type: ignore
                await ctx.reply(f"{ctx.author.mention} You don't own that 'suggestion'")
                return
        except (IndexError, AttributeError, ValueError):
            pass

        await msg.delete(delay=0)
        await ctx.reply(f"{ctx.author.mention} Done", delete_after=5)

    @suggest.command(name="resolved")
    @commands.bot_has_guild_permissions(manage_threads=True)
    @commands.cooldown(1, 60, commands.BucketType.member)
    async def suggest_resolved(self, ctx: Context, *, thread_id: int) -> None:
        """To mark the suggestion as resolved."""
        msg: Optional[discord.Message] = await self.get_or_fetch_message(thread_id, guild=ctx.guild)
        if not msg:
            await ctx.reply(
                f"{ctx.author.mention} Can not find message of ID `{thread_id}`. Probably already deleted, or `{thread_id}` is invalid",
            )
            return

        try:
            if int(msg.embeds[0].footer.text.split(":")[1]) != ctx.author.id:  # type: ignore
                await ctx.reply(f"{ctx.author.mention} You don't own that 'suggestion'")
                return
        except (IndexError, AttributeError, ValueError):
            pass

        thread: discord.Thread = await self.bot.getch(ctx.guild.get_channel, ctx.guild.fetch_channel, thread_id)
        if not msg or not thread:
            await ctx.reply(
                f"{ctx.author.mention} Can not find message of ID `{thread_id}`. Probably already deleted, or `{thread_id}` is invalid",
            )
            return

        await thread.edit(
            archived=True,
            locked=True,
            reason=f"Suggestion resolved by {ctx.author} ({ctx.author.id})",
        )
        await ctx.reply(f"{ctx.author.mention} Done", delete_after=5)

    @suggest.command(name="note", aliases=["remark"])
    @commands.check_any(commands.has_permissions(manage_messages=True))
    async def add_note(self, ctx: Context, ID: int, *, remark: str) -> None:  # noqa: N803
        """To add a note in suggestion embed."""
        msg: Optional[discord.Message] = await self.get_or_fetch_message(ID, guild=ctx.guild)
        if not msg:
            await ctx.reply(
                f"{ctx.author.mention} Can not find message of ID `{ID}`. Probably already deleted, or `{ID}` is invalid",
            )
            return

        embed: discord.Embed = msg.embeds[0]
        embed.clear_fields()
        embed.add_field(name="Remark", value=remark[:250])
        new_msg = await msg.edit(content=msg.content, embed=embed)
        self.message[new_msg.id]["message"] = new_msg

        try:
            user_id = int(embed.footer.text.split(":")[1])  # type: ignore
        except (IndexError, AttributeError, ValueError):
            await ctx.reply(f"{ctx.author.mention} Can not find user ID of the suggestion. Probably already deleted")
            return

        user = ctx.guild.get_member(user_id)
        await self.__notify_user(ctx, user, message=msg, remark=remark)

        await ctx.reply(f"{ctx.author.mention} Done", delete_after=5)

    @suggest.command(name="clear", aliases=["cls"])
    @commands.check_any(commands.has_permissions(manage_messages=True))
    async def clear_suggestion_embed(
        self,
        ctx: Context,
        ID: int,  # noqa: N803
    ) -> None:
        """To remove all kind of notes and extra reaction from suggestion embed."""
        msg: Optional[discord.Message] = await self.get_or_fetch_message(ID, guild=ctx.guild)
        if not msg:
            await ctx.reply(
                f"{ctx.author.mention} Can not find message of ID `{ID}`. Probably already deleted, or `{ID}` is invalid",
            )
            return

        embed: discord.Embed = msg.embeds[0]
        embed.clear_fields()
        embed.color = 0xADD8E6
        new_msg = await msg.edit(embed=embed, content=None)
        self.message[new_msg.id]["message"] = new_msg

        for reaction in msg.reactions:
            if str(reaction.emoji) not in REACTION_EMOJI:
                await msg.clear_reaction(reaction.emoji)
        await ctx.reply(f"{ctx.author.mention} Done", delete_after=5)

    @suggest.command(name="flag")
    @commands.check_any(commands.has_permissions(manage_messages=True))
    async def suggest_flag(self, ctx: Context, ID: int, flag: str) -> None:  # noqa: N803
        """To flag the suggestion.

        Avalibale Flags :-
        - INVALID
        - ABUSE
        - INCOMPLETE
        - DECLINE
        - APPROVED
        - DUPLICATE
        """
        msg: Optional[discord.Message] = await self.get_or_fetch_message(ID, guild=ctx.guild)
        if not msg:
            await ctx.reply(
                f"{ctx.author.mention} Can not find message of ID `{ID}`. Probably already deleted, or `{ID}` is invalid",
            )
            return

        if msg.author.id != self.bot.user.id:
            await ctx.reply(f"{ctx.author.mention} Invalid `{ID}`")
            return

        flag = flag.upper()
        try:
            payload: dict[str, Union[int, str]] = OTHER_REACTION[flag]
        except KeyError:
            await ctx.reply(f"{ctx.author.mention} Invalid Flag")
            return

        embed: discord.Embed = msg.embeds[0]
        if payload.get("color"):
            embed.color = discord.Color.from_str(str(payload["color"]))

        try:
            user_id = int(embed.footer.text.split(":")[1])  # type: ignore
        except (IndexError, AttributeError, ValueError):
            await ctx.reply(f"{ctx.author.mention} Can not find user ID of the suggestion. Probably already deleted")
            return

        user: Optional[discord.Member] = await self.bot.get_or_fetch_member(ctx.guild, user_id)
        await self.__notify_user(ctx, user, message=msg, remark="")

        content = f"Flagged: {flag} | {payload['emoji']}"
        new_msg = await msg.edit(content=content, embed=embed)
        self.message[new_msg.id]["message"] = new_msg

        await ctx.reply(f"{ctx.author.mention} Done", delete_after=5)

    @Cog.listener(name="on_raw_message_delete")
    async def suggest_msg_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        """Remove the message from cache."""
        if payload.message_id in self.message:
            del self.message[payload.message_id]

    @Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Parse the message and create suggestion."""
        await self.bot.wait_until_ready()
        if message.author.bot or message.guild is None:
            return

        ls = self.bot.config.suggestion_channel
        if not ls:
            return

        if message.channel.id != ls:
            return

        if _ := await self.__parse_mod_action(message):
            return

        context: Context = await self.bot.get_context(message, cls=Context)
        await self.suggest(context, suggestion=message.clean_content)  # type: ignore

    @Cog.listener()
    async def on_message_edit(self, _: discord.Message, after: discord.Message) -> None:
        """Update the message in cache."""
        if after.id in self.message:
            self.message[after.id]["message"] = after

    @Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Update the message in cache."""
        if payload.message_id not in self.message:
            return

        if str(payload.emoji) not in REACTION_EMOJI:
            return

        if str(payload.emoji) == "\N{UPWARDS BLACK ARROW}":
            self.message[payload.message_id]["message_upvote"] += 1
        if str(payload.emoji) == "\N{DOWNWARDS BLACK ARROW}":
            self.message[payload.message_id]["message_downvote"] += 1

    @Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        """Update the message in cache."""
        if payload.message_id not in self.message:
            return

        if str(payload.emoji) not in REACTION_EMOJI:
            return

        if str(payload.emoji) == "\N{UPWARDS BLACK ARROW}":
            self.message[payload.message_id]["message_upvote"] -= 1
        if str(payload.emoji) == "\N{DOWNWARDS BLACK ARROW}":
            self.message[payload.message_id]["message_downvote"] -= 1

    async def __parse_mod_action(self, message: discord.Message) -> Optional[bool]:
        assert isinstance(message.author, discord.Member)

        if not self.__is_mod(message.author):
            return

        if message.content.upper() in OTHER_REACTION:
            context: Context = await self.bot.get_context(message, cls=Context)
            # cmd: commands.Command = self.bot.get_command("suggest flag")

            msg: discord.Message | discord.DeletedReferencedMessage | None = getattr(message.reference, "resolved", None)

            if not isinstance(msg, discord.Message):
                return

            if msg.author.id != self.bot.user.id:
                return

            # await context.invoke(cmd, msg.id, message.content.upper())
            await self.suggest_flag(context, msg.id, message.content.upper())
            return True

    def __is_mod(self, member: discord.Member) -> bool:
        perms: discord.Permissions = member.guild_permissions
        if any([perms.manage_guild, perms.manage_messages]):
            return True

        return bool(discord.utils.get(member.roles, name="Moderator"))


async def setup(bot: Bot) -> None:
    """Load the Suggestion cog."""
    await bot.add_cog(Suggestions(bot))
