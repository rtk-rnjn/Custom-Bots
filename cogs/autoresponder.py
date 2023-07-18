from __future__ import annotations

import logging
import random
import re
from typing import Union

import discord
from discord.ext import commands, tasks

from core import Bot, Cog, Context

RANDOM_GREETINGS = [
    "hi",
    "hello",
    "hey",
    "howdy",
    "hola",
    "greetings",
    "sup",
    "yo",
    "wassup",
    "what's up",
    "what's good",
    "what's happening",
    "what's new",
    "what's popping",
]

log = logging.getLogger("autoresponder")


class Autoresponder(Cog):
    """Automatically respond to messages."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self._ar_message_cache: dict[str, str] = {}
        self._ar_reaction_cache: dict[str, str] = {}
        self.save_loop.start()

        self.__need_save = False

        self.cooldown = commands.CooldownMapping.from_cooldown(1, 5, commands.BucketType.user)

    def formatter(self, response: str, message: discord.Message) -> str:
        # sourcery skip: inline-immediately-returned-variable
        """Format the message content with the message object."""
        assert isinstance(message.guild, discord.Guild) and isinstance(message.channel, discord.abc.GuildChannel)

        response = (
            response.replace("{author}", str(message.author))
            .replace("{author_mention}", message.author.mention)
            .replace("{author_name}", message.author.name)
            .replace("{author_display_name}", message.author.display_name)
            .replace("{author_id}", str(message.author.id))
            # channel
            .replace("{channel}", str(message.channel))
            .replace("{channel_mention}", message.channel.mention)
            .replace("{channel_name}", message.channel.name)
            .replace("{channel_id}", str(message.channel.id))
            # guild
            .replace("{guild}", str(message.guild))
            .replace("{guild_name}", message.guild.name)
            .replace("{guild_id}", str(message.guild.id))
            # message
            .replace("{message}", message.content)
            .replace("{message_id}", str(message.id))
            # bot
            .replace("{bot}", str(self.bot.user))
            .replace("{bot_mention}", self.bot.user.mention)
            .replace("{bot_name}", self.bot.user.name)
            .replace("{bot_id}", str(self.bot.user.id))
            # functions
            .replace("{!random_greeting}", random.choice(RANDOM_GREETINGS))
            .replace("{!random_int}", str(random.randint(0, 100)))
        )

        return response

    async def cog_load(self) -> None:
        query = {
            "id": self.bot.config.id,
            "ar_msg": {"$exists": True},
        }
        log.info("fetching autoresponder messages...")
        data = await self.bot.main_config.find_one(query, {"ar_msg": 1})
        log.info("fetched autoresponder messages with data %s", data)
        if data is None:
            return

        self._ar_message_cache = data["ar_msg"]

    async def cog_unload(self) -> None:
        await self.save()
        if self.save_loop.is_running():
            self.save_loop.cancel()

    async def save(self) -> None:
        query = {"id": self.bot.config.id}
        update = {"$set": {"ar_msg": self._ar_message_cache}}
        log.info("saving autoresponder messages... %s", update)
        await self.bot.main_config.update_one(query, update, upsert=True)
        log.info("saved autoresponder messages")

    @commands.group(name="autoresponder", aliases=["ar"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def autoresponder(self, ctx: Context) -> None:
        """The base command for the autoresponder."""
        if not ctx.invoked_subcommand:
            await ctx.send_help(ctx.command)

    @autoresponder.command(name="add", aliases=["create"])
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_add(self, ctx: Context, trigger: str, *, response: commands.clean_content) -> None:
        """Add a new autoresponder

        The trigger can be a regex pattern or a normal string.

        Examples:
        - `[p]ar add hello Hello World!`
        - `[p]ar add ^hello$ Hello World!`

        - `[p]ar add hi {author_mention} {!random_greeting} welcome to {guild_name}!`

        Bot variables:
        - `{author}        ` - The author's full name.
        - `{author_mention}` - The author's mention.
        - `{author_name}   ` - The author's name.
        - `{author_display_name}` - The author's display name.
        - `{author_id}     ` - The author's ID.
        - `{channel}       ` - The channel's full name.
        - `{channel_mention}` - The channel's mention.
        - `{channel_name}  ` - The channel's name.
        - `{channel_id}    ` - The channel's ID.
        - `{guild}         ` - The guild's full name.
        - `{guild_name}    ` - The guild's name.
        - `{guild_id}      ` - The guild's ID.
        - `{message}       ` - The message's content.
        - `{message_id}    ` - The message's ID.
        - `{bot}           ` - The bot's full name.
        - `{bot_mention}   ` - The bot's mention.
        - `{bot_name}      ` - The bot's name.
        - `{bot_id}        ` - The bot's ID.
        - `{!random_greeting}` - A random greeting.
        - `{!random_int}   ` - A random integer between 0 and 100.
        """
        if trigger in self._ar_message_cache:
            await ctx.reply(
                f"There is already an autoresponder for `{trigger}`.", allowed_mentions=discord.AllowedMentions.none()
            )
            return

        self._ar_message_cache[trigger] = str(response)
        log.debug("added autoresponder for %s", trigger)
        await ctx.reply(f"Added a new autoresponder for `{trigger}`.", allowed_mentions=discord.AllowedMentions.none())

        self.__need_save = True

    @autoresponder.command(name="remove", aliases=["delete"])
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_remove(self, ctx: Context, trigger: str) -> None:
        """Remove an autoresponder

        Examples:
        - `[p]ar remove hello`
        """
        try:
            del self._ar_message_cache[trigger]
            log.debug("Removed autoresponder for %s", trigger)
        except KeyError:
            await ctx.reply(
                f"Couldn't find an autoresponder for `{trigger}`.", allowed_mentions=discord.AllowedMentions.none()
            )
            return

        await ctx.reply(f"Removed the autoresponder for `{trigger}`.", allowed_mentions=discord.AllowedMentions.none())

        self.__need_save = True

    @autoresponder.command(name="list")
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_list(self, ctx: Context) -> None:
        """List all autoresponders."""
        if not self._ar_message_cache:
            await ctx.reply("There are no autoresponders.", allowed_mentions=discord.AllowedMentions.none())
            return

        embed = discord.Embed(title="Autoresponders")
        embed.description = "`" + "`, `".join(self._ar_message_cache.keys()) + "`"

        await ctx.reply(embed=embed)

    @autoresponder.command(name="clear")
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_clear(self, ctx: Context) -> None:
        """Clear all autoresponders."""
        self._ar_message_cache.clear()
        log.debug("cleared all autoresponders")
        await ctx.reply("Cleared all autoresponders.", allowed_mentions=discord.AllowedMentions.none())

        self.__need_save = True

    @autoresponder.command(name="show")
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_show(self, ctx: Context, trigger: str) -> None:
        """Show the response for an autoresponder."""
        try:
            response = self._ar_message_cache[trigger]
        except KeyError:
            await ctx.reply(
                f"Couldn't find an autoresponder for `{trigger}`.", allowed_mentions=discord.AllowedMentions.none()
            )
            return

        embed = discord.Embed(title=f"Autoresponder - {trigger}")
        embed.description = response

        await ctx.reply(embed=embed)

    @Cog.listener("on_message")
    async def on_ar_message(self, message: discord.Message) -> None:
        if not self._ar_message_cache:
            return

        if message.author.bot or not message.guild or not message.content:
            return

        bucket = self.cooldown.get_bucket(message)
        retry_after = bucket.update_rate_limit() if bucket else 0
        if retry_after:
            return

        for trigger, response in self._ar_message_cache.items():
            trigger = re.escape(trigger.strip())
            try:
                if re.fullmatch(rf"{trigger}", message.content, re.IGNORECASE):
                    await message.channel.send(self.formatter(response, message))
                    return
            except re.error:
                pass
            else:
                if message.content.lower() == trigger.lower():
                    await message.channel.send(self.formatter(response, message))
                    return

    @tasks.loop(minutes=5)
    async def save_loop(self) -> None:
        if self.__need_save:
            await self.save()
            self.__need_save = False

    @autoresponder.group(name="reaction", aliases=["react"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_reaction(self, ctx: Context) -> None:
        """The base command for the autoresponder reaction."""
        if not ctx.invoked_subcommand:
            await ctx.send_help(ctx.command)

    @autoresponder_reaction.command(name="add", aliases=["create"])
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_reaction_add(self, ctx: Context, trigger: str, *, reaction: Union[str, discord.Emoji]) -> None:
        """Add a new autoresponder reaction

        The trigger can be a regex pattern or a normal string.

        Examples:
        - `[p]ar reaction add hello :wave:`
        """
        if trigger in self._ar_reaction_cache:
            await ctx.reply(
                f"There is already an autoresponder reaction for `{trigger}`.",
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        self._ar_reaction_cache[trigger] = str(reaction)
        log.debug("added a new autoresponder reaction for %s", trigger)
        await ctx.reply(
            f"Added a new autoresponder reaction for `{trigger}`.", allowed_mentions=discord.AllowedMentions.none()
        )

        self.__need_save = True

    @autoresponder_reaction.command(name="remove", aliases=["delete"])
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_reaction_remove(self, ctx: Context, trigger: str) -> None:
        """Remove an autoresponder reaction

        Examples:
        - `[p]ar reaction remove hello`
        """
        try:
            del self._ar_reaction_cache[trigger]
            log.debug("removed an autoresponder reaction for %s", trigger)
        except KeyError:
            await ctx.reply(
                f"Couldn't find an autoresponder reaction for `{trigger}`.", allowed_mentions=discord.AllowedMentions.none()
            )
            return

        await ctx.reply(
            f"Removed the autoresponder reaction for `{trigger}`.", allowed_mentions=discord.AllowedMentions.none()
        )

        self.__need_save = True

    @autoresponder_reaction.command(name="list")
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_reaction_list(self, ctx: Context) -> None:
        """List all autoresponder reactions."""
        if not self._ar_reaction_cache:
            await ctx.reply("There are no autoresponder reactions.", allowed_mentions=discord.AllowedMentions.none())
            return

        embed = discord.Embed(title="Autoresponder Reactions")
        embed.description = "`" + "`, `".join(self._ar_reaction_cache.keys()) + "`"

        await ctx.reply(embed=embed)

    @autoresponder_reaction.command(name="clear")
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_reaction_clear(self, ctx: Context) -> None:
        """Clear all autoresponder reactions."""
        self._ar_reaction_cache.clear()
        log.debug("cleared all autoresponder reactions")
        await ctx.reply("Cleared all autoresponder reactions.", allowed_mentions=discord.AllowedMentions.none())

        self.__need_save = True

    @autoresponder_reaction.command(name="show")
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_reaction_show(self, ctx: Context, trigger: str) -> None:
        """Show the response for an autoresponder reaction."""
        try:
            response = self._ar_reaction_cache[trigger]
        except KeyError:
            await ctx.reply(
                f"Couldn't find an autoresponder reaction for `{trigger}`.", allowed_mentions=discord.AllowedMentions.none()
            )
            return

        embed = discord.Embed(title=f"Autoresponder Reaction - {trigger}")
        embed.description = response

        await ctx.reply(embed=embed)

    async def add_reaction(self, message: discord.Message, reaction: str) -> None:
        try:
            await message.add_reaction(discord.PartialEmoji.from_str(reaction))
        except discord.HTTPException:
            pass

    @Cog.listener("on_message")
    async def on_ar_reaction(self, message: discord.Message) -> None:
        if not self._ar_reaction_cache:
            return

        if message.author.bot or not message.guild:
            return

        bucket = self.cooldown.get_bucket(message)
        retry_after = bucket.update_rate_limit() if bucket else 0
        if retry_after:
            return

        for trigger, response in self._ar_reaction_cache.items():
            try:
                if re.fullmatch(rf"{trigger}", message.content, re.IGNORECASE):
                    await self.add_reaction(message, response)
                    return
            except re.error:
                pass
            else:
                if message.content.lower() == trigger.lower():
                    await self.add_reaction(message, response)
                    return


async def setup(bot: Bot) -> None:
    await bot.add_cog(Autoresponder(bot))
