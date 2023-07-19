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

import asyncio
import logging
import random
from typing import Any

import discord
from discord.ext import commands

from core import Bot, Cog, Context  # pylint: disable=import-error
from utils import ShortTime  # pylint: disable=import-error

log = logging.getLogger("giveaway")


class Giveaway(Cog):
    """Giveaway commands"""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @staticmethod
    def __is_int(st: str, error: str) -> int | None:
        if st.lower() in {"skip", "none", "no"}:
            return None
        try:
            main = int(st)
        except ValueError as e:
            raise commands.BadArgument(error) from e

        return main

    @staticmethod
    async def __wait_for_message(ctx: Context) -> str:
        def check(m: discord.Message) -> bool:
            return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id

        try:
            msg: discord.Message = await ctx.bot.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError as e:
            raise commands.BadArgument("You took too long to respond") from e

        return msg.content

    async def make_giveaway(self, ctx: Context) -> dict[str, Any]:  # pylint: disable=too-many-locals
        """Make a giveaway"""
        quest = [
            "In what channel you want to host giveaway? (Channel ID, Channel Name, Channel Mention)",
            "Duration for the giveaway",
            "Prize for the giveaway",
            "Number of winners?",
            "Required Role? (Role ID, Role Name, Role Mention) | `skip`, `none`, `no` for no role requirement",
            (
                "Required Server? (ID Only, bot must be in that server) `skip`, `none`, `no` for no role requirement\n"
                "Bot must be in that server to check the user presence"
            ),
        ]

        payload = {}
        CHANNEL = None

        for index, question in enumerate(quest, start=1):
            await ctx.reply(embed=discord.Embed(description=question))
            if index == 1:
                channel = await commands.TextChannelConverter().convert(
                    ctx, argument=(await self.__wait_for_message(ctx))
                )  # pylint: disable=superfluous-parens
                CHANNEL = channel
                payload["giveaway_channel"] = channel.id

            elif index == 2:
                duration = ShortTime(await self.__wait_for_message(ctx))
                payload["endtime"] = duration.dt.timestamp()

            elif index == 3:
                prize = await self.__wait_for_message(ctx)
                payload["prize"] = prize

            elif index == 4:
                winners = self.__is_int(await self.__wait_for_message(ctx), "Winner must be a whole number")
                payload["winners"] = winners

            elif index == 5:
                arg = await self.__wait_for_message(ctx)
                if arg.lower() not in ("skip", "no", "none"):
                    role = await commands.RoleConverter().convert(ctx, argument=arg)
                    payload["required_role"] = role.id
                else:
                    payload["required_role"] = None

            elif index == 6:
                server = self.__is_int(
                    await self.__wait_for_message(ctx),
                    "Server ID must be a whole number",
                )
                payload["required_guild"] = server

        embed = discord.Embed(
            title="\N{PARTY POPPER} Giveaway \N{PARTY POPPER}",
            timestamp=ctx.message.created_at,
            url=ctx.message.jump_url,
        )
        embed.description = (
            f"**React \N{PARTY POPPER} to win**\n\n"
            f"> Prize: **{payload['prize']}**\n"
            f"> Hosted by: {ctx.author.mention} (`{ctx.author.id}`)\n"
            f"> Ends: **<t:{int(payload['endtime'])}:R>**\n"
        )
        embed.set_footer(text=f"ID: {ctx.message.id}", icon_url=ctx.author.display_avatar.url)
        CHANNEL = CHANNEL or ctx.channel
        msg = await CHANNEL.send(embed=embed)  # type: ignore
        await msg.add_reaction("\N{PARTY POPPER}")
        ctx.bot.message_cache[msg.id] = msg
        main_post = await self._create_giveaway_post(message=msg, **payload)  # type: ignore  # flake8: noqa  # pylint: disable=missing-kwoa

        await ctx.bot.giveaways.insert_one({**main_post["extra"]["main"], "reactors": [], "status": "ONGOING"})
        await ctx.reply(embed=discord.Embed(description="Giveaway has been created!"))

        log.debug("giveaway created with payload %s", payload)
        return main_post

    async def end_giveaway(self, bot: Bot, **kw: Any) -> list[int]:
        """End a giveaway"""
        log.info("ending giveaway with payload %s", kw)
        channel: discord.TextChannel = await bot.getch(bot.get_channel, bot.fetch_channel, kw.get("giveaway_channel"))

        msg: discord.Message = await bot.get_or_fetch_message(channel, kw["message_id"])  # type: ignore
        await bot.delete_timer(_id=kw["message_id"])
        embed = msg.embeds[0]
        embed.color = 0xFF000
        await msg.edit(embed=embed)

        reactors = kw["reactors"]
        if not reactors:
            log.info("no reactors found, fetching reactors from message")
            for reaction in msg.reactions:
                if str(reaction.emoji) == "\N{PARTY POPPER}":
                    reactors: list[int] = [user.id async for user in reaction.users()]
                    break

        self.__item__remove(reactors, bot.user.id)

        if not reactors:
            return []

        win_count = kw.get("winners", 1)

        real_winners: list[int] = []

        while True:
            if win_count > len(reactors):
                # more winner than the reactions
                return real_winners

            winners = random.choices(reactors, k=win_count)
            kw["winners"] = winners
            real_winners = await Giveaway.__check_requirements(bot, **kw)

            _ = [self.__item__remove(reactors, i) for i in real_winners]  # flake8: noqa

            await self.__update_giveaway_reactors(
                bot=bot, reactors=reactors, message_id=kw.get("message_id")  # type: ignore
            )

            if not real_winners and not reactors:
                # requirement do not statisfied and we are out of reactors
                return real_winners

            if real_winners:
                return real_winners

            log.debug("no winners found, rerolling")
            win_count = win_count - len(real_winners)
            await asyncio.sleep(0)

    @staticmethod
    async def __update_giveaway_reactors(*, bot: Bot, reactors: list[int], message_id: int) -> None:
        collection = bot.giveaways
        await collection.update_one({"message_id": message_id}, {"$set": {"reactors": reactors}})

    @staticmethod
    async def __check_requirements(bot: Bot, **kw: Any) -> list[int]:
        # vars
        real_winners: list[int] = kw.get("winners", [])

        current_guild: discord.Guild = bot.get_guild(kw.get("guild_id"))  # type: ignore
        required_guild: discord.Guild = bot.get_guild(kw.get("required_guild"))  # type: ignore
        required_role: int = kw.get("required_role", 0)

        for member in kw.get("winners", []):
            member = await bot.get_or_fetch_member(current_guild, member)
            if required_guild:
                is_member_none = await bot.get_or_fetch_member(required_guild, member.id)  # type: ignore
                if is_member_none is None:
                    log.debug("member %s is not in required guild %s", member, required_guild)
                    Giveaway.__item__remove(real_winners, member)

            if required_role and not member._roles.has(required_role):  # type: ignore  # pylint: disable=protected-access
                log.debug("member %s do not have required role %s", member, required_role)
                Giveaway.__item__remove(real_winners, member)

        return real_winners

    @staticmethod
    def __item__remove(ls: list[Any], item: Any) -> list[Any]:
        try:
            ls.remove(item)
        except (ValueError, KeyError):
            return ls
        return ls

    @staticmethod
    async def _create_giveaway_post(
        *,
        message: discord.Message,
        giveaway_channel: int,
        prize: str,
        winners: int,
        endtime: float,
        required_role: int | None = None,
        required_guild: int | None = None,
    ) -> dict[str, Any]:
        post_extra = {
            "message_id": message.id,
            "author_id": message.author.id,
            "channel_id": message.channel.id,
            "giveaway_channel": giveaway_channel,
            "guild_id": message.guild.id,  # type: ignore
            "created_at": message.created_at.timestamp(),
            "prize": prize,
            "winners": winners,
            "required_role": required_role,
            "required_guild": required_guild,
        }

        return {
            "message": message,
            "created_at": message.created_at.timestamp(),
            "expires_at": endtime,
            "extra": {"name": "GIVEAWAY_END", "main": post_extra},
        }

    async def make_giveaway_drop(self, ctx: Context, *, duration: ShortTime, winners: int, prize: str):
        """Make a giveaway"""
        payload = {
            "giveaway_channel": ctx.channel.id,
            "endtime": duration.dt.timestamp(),
            "winners": winners,
            "prize": prize,
            "required_role": None,
            "required_guild": None,
        }

        embed = discord.Embed(
            title="\N{PARTY POPPER} Giveaway \N{PARTY POPPER}",
            timestamp=ctx.message.created_at,
            url=ctx.message.jump_url,
        )
        embed.description = (
            f"**React \N{PARTY POPPER} to win**\n\n"
            f"> Prize: **{payload['prize']}**\n"
            f"> Hosted by: {ctx.author.mention} (`{ctx.author.id}`)\n"
            f"> Ends: **<t:{int(payload['endtime'])}:R>**\n"
        )

        embed.set_footer(text=f"ID: {ctx.message.id}", icon_url=ctx.author.display_avatar.url)
        msg: discord.Message = await ctx.reply(embed=embed)
        await msg.add_reaction("\N{PARTY POPPER}")
        main_post = await self._create_giveaway_post(message=msg, **payload)  # flake8: noqa

        await ctx.bot.giveaways.insert_one({**main_post["extra"]["main"], "reactors": [], "status": "ONGOING"})
        return main_post

    @commands.command(name="gstart", aliases=["giveaway"])
    @commands.has_permissions(manage_guild=True)
    async def gstart_command(self, ctx: Context) -> None:
        """Start a giveaway

        The invoker must have `Manage Server` permissions to use this command.

        This command will walk you through the steps to start a giveaway."""

        post = await self.make_giveaway(ctx)
        await self.bot.create_timer(_event_name="giveaway", **post)

    @commands.command(name="gend", aliases=["giveawayend"])
    @commands.has_permissions(manage_guild=True)
    async def gend_command(self, ctx: Context, *, message: int) -> None:
        """End a giveaway

        The invoker must have `Manage Server` permissions to use this command.
        This command will end a giveaway and select a winner.

        Example:
        `[p]gend 1234567890`
        """
        if data := await self.bot.giveaways.find_one_and_update(
            {"message_id": message, "status": "ONGOING"}, {"$set": {"status": "END"}}
        ):
            member_ids = await self.end_giveaway(self.bot, **data)
            if not member_ids:
                await ctx.reply(f"{ctx.author.mention} no winners! :(")
                return

            joiner = ">, <@".join([str(i) for i in member_ids])

            await ctx.reply(
                f"Congrats <@{joiner}> you won **{data.get('prize')}**\n"
                f"> https://discord.com/channels/{data.get('guild_id')}/{data.get('giveaway_channel')}/{data.get('message_id')}"
            )
        else:
            await ctx.reply("No giveaway found")

    @commands.command(name="glist", aliases=["giveawaylist"])
    @commands.has_permissions(manage_guild=True)
    async def glist_command(self, ctx: Context) -> None:
        """Show the latest ongoing giveaways.

        The invoker must have `Manage Server` permissions to use this command.
        """
        if data := await self.bot.giveaways.find_one(
            {"status": "ONGOING", "guild_id": ctx.guild.id, "bot_id": self.bot.user.id}  # type: ignore
        ):
            await ctx.reply(f"Giveaway is ongoing at <#{data.get('giveaway_channel')}>")
        else:
            await ctx.reply("No giveaway found")

    @commands.command(name="gdelete", aliases=["giveawaydelete"])
    @commands.has_permissions(manage_guild=True)
    async def gdelete_command(self, ctx: Context, *, message: int) -> None:
        """Delete a giveaway

        The invoker must have `Manage Server` permissions to use this command.
        This command will delete a giveaway.

        Example:
        `[p]gdelete 1234567890`
        """
        if await self.bot.giveaways.find_one_and_delete({"message_id": message, "status": "ONGOING"}):
            await ctx.reply("Giveaway deleted")
            await self.bot.delete_timer(_id=message)
        else:
            await ctx.reply("No giveaway found")

    @commands.command(name="gdrop", aliases=["giveawaydrop"])
    @commands.has_permissions(manage_guild=True)
    async def gdrop_command(
        self,
        ctx: Context,
        duration: ShortTime,
        winners: int = 1,
        *,
        prize: str = "None",
    ) -> None:
        """Drop a giveaway

        The invoker must have `Manage Server` permissions to use this command.
        This command will drop a giveaway. A quick way to start a giveaway.

        The duration can be specified as a number followed by a unit.
        Valid units are `s`, `m`, `h`, `d`, `w`

        Example:
        `[p]gdrop 1h 1 Nitro`
        """
        post = await self.make_giveaway_drop(ctx, duration=duration, winners=winners, prize=prize)
        await self.bot.create_timer(_event_name="giveaway", **post)

    async def add_reactor(self, bot: Bot, payload: discord.RawReactionActionEvent):
        """Add a reactor to the giveaway"""
        if str(payload.emoji) != "\N{PARTY POPPER}":
            return

        await bot.giveaways.update_one(
            {"message_id": payload.message_id, "status": "ONGOING"},
            {"$addToSet": {"reactors": payload.user_id}},
        )

    async def remove_reactor(self, bot: Bot, payload: discord.RawReactionActionEvent):
        """Remove a reactor from the giveaway"""
        if str(payload.emoji) != "\N{PARTY POPPER}":
            return

        await bot.giveaways.update_one(
            {"message_id": payload.message_id, "status": "ONGOING"},
            {"$pull": {"reactors": payload.user_id}},
        )

    @Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Add a reactor to the giveaway"""
        await self.add_reactor(self.bot, payload)

    @Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        """Remove a reactor from the giveaway"""
        await self.remove_reactor(self.bot, payload)


async def setup(bot: Bot) -> None:
    """Load the Giveaway cog."""
    await bot.add_cog(Giveaway(bot))
