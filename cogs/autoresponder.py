from __future__ import annotations

import re
from typing import Union

import discord
from discord.ext import commands, tasks

from core import Bot, Cog, Context


class Autoresponder(Cog):
    """Automatically respond to messages."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self._message_cache: dict[str, str] = {}
        self._reaction_cache: dict[str, str] = {}
        self.save_loop.start()

        self.__need_save = False

        self.cooldown = commands.CooldownMapping.from_cooldown(1, 5, commands.BucketType.channel)

    async def cog_load(self) -> None:
        query = {
            "id": self.bot.config.id,
            "ar_msg": {"$exists": True},
        }
        data = await self.bot.main_config.find_one(query)
        if data is None:
            return

        self._message_cache = data["ar_msg"]

    async def cog_unload(self) -> None:
        await self.save()
        if self.save_loop.is_running():
            self.save_loop.cancel()

    async def save(self) -> None:
        query = {"id": self.bot.config.id}
        update = {"$set": {"ar_msg": self._message_cache}}
        await self.bot.main_config.update_one(query, update, upsert=True)

    @commands.group(name="autoresponder", aliases=["ar"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def autoresponder(self, ctx: Context) -> None:
        """The base command for the autoresponder."""
        if not ctx.invoked_subcommand:
            await ctx.send_help(ctx.command)

    @autoresponder.command(name="add", aliases=["create"])
    async def autoresponder_add(self, ctx: Context, trigger: str, *, response: commands.clean_content) -> None:
        """Add a new autoresponder

        The trigger can be a regex pattern or a normal string.

        Examples:
        - `[p]ar add hello Hello World!`
        """
        if trigger in self._message_cache:
            await ctx.reply(
                f"There is already an autoresponder for `{trigger}`.", allowed_mentions=discord.AllowedMentions.none()
            )
            return

        self._message_cache[trigger] = str(response)
        await ctx.reply(f"Added a new autoresponder for `{trigger}`.", allowed_mentions=discord.AllowedMentions.none())

        self.__need_save = True

    @autoresponder.command(name="remove", aliases=["delete"])
    async def autoresponder_remove(self, ctx: Context, trigger: str) -> None:
        """Remove an autoresponder

        Examples:
        - `[p]ar remove hello`
        """
        try:
            del self._message_cache[trigger]
        except KeyError:
            await ctx.reply(
                f"Couldn't find an autoresponder for `{trigger}`.", allowed_mentions=discord.AllowedMentions.none()
            )
            return

        await ctx.reply(f"Removed the autoresponder for `{trigger}`.", allowed_mentions=discord.AllowedMentions.none())

        self.__need_save = True

    @autoresponder.command(name="list")
    async def autoresponder_list(self, ctx: Context) -> None:
        """List all autoresponders."""
        if not self._message_cache:
            await ctx.reply("There are no autoresponders.", allowed_mentions=discord.AllowedMentions.none())
            return

        embed = discord.Embed(title="Autoresponders")
        embed.description = "`" + "`, `".join(self._message_cache.keys()) + "`"

        await ctx.reply(embed=embed)

    @autoresponder.command(name="clear")
    async def autoresponder_clear(self, ctx: Context) -> None:
        """Clear all autoresponders."""
        self._message_cache.clear()
        await ctx.reply("Cleared all autoresponders.", allowed_mentions=discord.AllowedMentions.none())

        self.__need_save = True

    @autoresponder.command(name="show")
    async def autoresponder_show(self, ctx: Context, trigger: str) -> None:
        """Show the response for an autoresponder."""
        try:
            response = self._message_cache[trigger]
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
        if message.author.bot or not message.guild or not message.content:
            return
        
        bucket = self.cooldown.get_bucket(message)
        retry_after = bucket.update_rate_limit() if bucket else 0
        if retry_after:
            return

        for trigger, response in self._message_cache.items():
            try:
                if re.search(trigger, message.content, re.IGNORECASE):
                    await message.channel.send(response)
            except re.error:
                pass

            if message.content.lower() == trigger.lower():
                await message.channel.send(response)

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
    async def autoresponder_reaction_add(self, ctx: Context, trigger: str, *, reaction: Union[str, discord.Emoji]) -> None:
        """Add a new autoresponder reaction

        The trigger can be a regex pattern or a normal string.

        Examples:
        - `[p]ar reaction add hello :wave:`
        """
        if trigger in self._reaction_cache:
            await ctx.reply(
                f"There is already an autoresponder reaction for `{trigger}`.",
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        self._reaction_cache[trigger] = str(reaction)
        await ctx.reply(
            f"Added a new autoresponder reaction for `{trigger}`.", allowed_mentions=discord.AllowedMentions.none()
        )

        self.__need_save = True

    @autoresponder_reaction.command(name="remove", aliases=["delete"])
    async def autoresponder_reaction_remove(self, ctx: Context, trigger: str) -> None:
        """Remove an autoresponder reaction

        Examples:
        - `[p]ar reaction remove hello`
        """
        try:
            del self._reaction_cache[trigger]
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
    async def autoresponder_reaction_list(self, ctx: Context) -> None:
        """List all autoresponder reactions."""
        if not self._reaction_cache:
            await ctx.reply("There are no autoresponder reactions.", allowed_mentions=discord.AllowedMentions.none())
            return

        embed = discord.Embed(title="Autoresponder Reactions")
        embed.description = "`" + "`, `".join(self._reaction_cache.keys()) + "`"

        await ctx.reply(embed=embed)

    @autoresponder_reaction.command(name="clear")
    async def autoresponder_reaction_clear(self, ctx: Context) -> None:
        """Clear all autoresponder reactions."""
        self._reaction_cache.clear()
        await ctx.reply("Cleared all autoresponder reactions.", allowed_mentions=discord.AllowedMentions.none())

        self.__need_save = True

    @autoresponder_reaction.command(name="show")
    async def autoresponder_reaction_show(self, ctx: Context, trigger: str) -> None:
        """Show the response for an autoresponder reaction."""
        try:
            response = self._reaction_cache[trigger]
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
        if message.author.bot or not message.guild:
            return
        
        bucket = self.cooldown.get_bucket(message)
        retry_after = bucket.update_rate_limit() if bucket else 0
        if retry_after:
            return

        for trigger, response in self._reaction_cache.items():
            try:
                if re.search(trigger, message.content, re.IGNORECASE):
                    await self.add_reaction(message, response)
            except re.error:
                pass

            if message.content.lower() == trigger.lower():
                await self.add_reaction(message, response)
