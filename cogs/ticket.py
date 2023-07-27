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
import logging
from collections.abc import Callable

import discord
from discord.ext import commands, tasks

from core import Bot, Cog, Context  # pylint: disable=import-error
from utils import MessageID, RoleID  # pylint: disable=import-error

log = logging.getLogger("ticket")


class Tickets(Cog):  # pylint: disable=too-many-public-methods
    """Ticket related commands."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.ticket_collection = self.bot.ticket

        self._ticket_cache = {}
        self.database_updater.start()  # pylint: disable=no-member

        # {
        #     "ticket_{BOT_ID}": {
        #         "ticket_category_channel": INT,
        #         "ticket_ping_role": INT,
        #         "ticket_message": INT,
        #         "ticket_message_channel": INT,
        #         "ticket_log_channel": INT,
        #         "active_tickets": [
        #             {
        #                 "ticket_id": INT,
        #                 "ticket_owner": INT,
        #                 "ticket_channel": INT,
        #                 "ticket_name": STR,
        #                 "ticket_topic": STR,
        #                 "ticket_members": [
        #                     INT
        #                 ]
        #             }
        #         ]
        #     }
        # }

    DEFAULT_PAYLOAD = {
        "ticket_category_channel": None,
        "ticket_ping_role": None,
        "ticket_message": None,
        "ticket_message_channel": None,
        "ticket_log_channel": None,
        "active_tickets": [],
    }

    @tasks.loop(minutes=5)
    async def database_updater(self) -> None:
        """Update the ticket cache every 5 minutes."""
        log.info("Updating ticket cache... %s", self._ticket_cache)
        await self.bot.log_bot_event(content="Updating ticket cache...")
        await self._save_ticket_cache()

    async def cog_load(self) -> None:
        """Load the ticket cache when the cog is loaded."""
        await self._load_ticket_cache()

    async def cog_unload(self) -> None:
        """Save the ticket cache when the cog is unloaded."""
        log.info("Saving ticket cache... %s", self._ticket_cache)
        await self.bot.log_bot_event(content="Saving ticket cache...")
        await self._save_ticket_cache()

        if self.database_updater.is_running():  # pylint: disable=no-member
            self.database_updater.cancel()  # pylint: disable=no-member

    async def _save_ticket_cache(self) -> None:
        if self._ticket_cache:
            bot_id = self.bot.user.id  # type: ignore
            await self.ticket_collection.update_one({"_id": f"ticket_{bot_id}"}, {"$set": self._ticket_cache}, upsert=True)

    async def _load_ticket_cache(self) -> None:
        bot_id = self.bot.user.id  # type: ignore
        self._ticket_cache = await self.ticket_collection.find_one({"_id": f"ticket_{bot_id}"}) or {}

        self._ticket_cache = {**self.DEFAULT_PAYLOAD, **self._ticket_cache}

    async def create_ticket(self, guild: discord.Guild, user: discord.Member) -> None:
        """Create a ticket for the user."""
        category_channel = self._ticket_cache["ticket_category_channel"]  # type: int
        ping_role = self._ticket_cache["ticket_ping_role"]

        category = guild.get_channel(category_channel or 0)  # type: discord.CategoryChannel | None  # type: ignore
        if category is None:
            await user.send(
                f"Ticket category channel not found. Ask your Administrator to set it up.\n> Sent from `{guild.name}`",
            )
            return

        role = guild.get_role(ping_role or 0)  # type: discord.Role | None
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        if role is not None:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        ticket = await category.create_text_channel(
            name=f"ticket-{len(self._ticket_cache['active_tickets']) + 1}",
            topic="Ticket",
            overwrites=overwrites,
        )
        data = {
            "ticket_id": ticket.id,
            "ticket_owner": user.id,
            "ticket_channel": ticket.id,
            "ticket_name": ticket.name,
            "ticket_topic": ticket.topic,
            "ticket_members": [user.id],
        }
        self._ticket_cache["active_tickets"].append(data)

        await ticket.send(
            f"{user.mention} {role.mention if role else ''} your ticket has been created. Please wait for a staff member to assist you.",
        )
        await self.log_ticket_event(guild=guild, ticket=data, event="create")

    async def delete_ticket(self, guild: discord.Guild, ticket: dict) -> None:
        """Delete a ticket."""
        category_channel = self._ticket_cache["ticket_category_channel"]
        category = guild.get_channel(category_channel or 0)
        if category is None:
            return

        assert isinstance(category, discord.CategoryChannel)

        ticket_channel = guild.get_channel(ticket["ticket_channel"])
        if ticket_channel is None:
            return

        assert isinstance(ticket_channel, discord.TextChannel)

        await ticket_channel.delete(reason="Ticket closed.")

        self._ticket_cache["active_tickets"].remove(ticket)

    @commands.group(name="ticket", aliases=["tick"], invoke_without_command=True)
    @commands.bot_has_guild_permissions(manage_channels=True, manage_roles=True)
    async def ticket(self, ctx: Context) -> None:
        """Ticket related commands."""
        if not ctx.invoked_subcommand:
            await ctx.send_help(ctx.command)

    @ticket.command(name="new", aliases=["create"])
    @commands.bot_has_guild_permissions(manage_channels=True, manage_roles=True)
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def ticket_new(self, ctx: Context) -> None:
        """Create a new ticket.

        Bot must have `Manage Channels` and `Manage Roles` permissions.
        You can only have one active ticket at a time.

        Example:
        -------
        - `[p]ticket new`
        """
        active_tickets = self._ticket_cache["active_tickets"] or []  # type: list[dict]
        if ctx.author.id in [ticket["ticket_owner"] for ticket in active_tickets]:
            await ctx.reply(f"{ctx.author.mention} you already have an active ticket.")
            return

        assert isinstance(ctx.guild, discord.Guild) and isinstance(ctx.author, discord.Member)

        await self.create_ticket(ctx.guild, ctx.author)

    @ticket.command(name="close", aliases=["delete"])
    @commands.bot_has_guild_permissions(manage_channels=True, manage_roles=True)
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def ticket_close(self, ctx: Context) -> None:
        """Close a ticket.

        Bot must have `Manage Channels` and `Manage Roles` permissions.

        Example:
        -------
        - `[p]ticket close`
        """
        active_tickets = self._ticket_cache["active_tickets"]  # type: list[dict]
        ticket = next(
            (ticket for ticket in active_tickets if ticket["ticket_owner"] == ctx.author.id),
            None,
        )

        if ticket is None:
            await ctx.reply(f"{ctx.author.mention} you don't have an active ticket.")
            return

        assert isinstance(ctx.guild, discord.Guild)

        await self.delete_ticket(ctx.guild, ticket)
        await self.log_ticket_event(guild=ctx.guild, ticket=ticket, event="delete")

    @ticket.command(name="add", aliases=["invite"])
    @commands.bot_has_guild_permissions(manage_channels=True, manage_roles=True)
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def ticket_add(self, ctx: Context, *, member: discord.Member) -> None:
        """Add a member to your ticket.

        Bot must have `Manage Channels` and `Manage Roles` permissions.

        Example:
        -------
        - `[p]ticket add @member`
        """
        active_tickets = self._ticket_cache["active_tickets"]  # type: list[dict]
        ticket = next(
            (ticket for ticket in active_tickets if ticket["ticket_owner"] == ctx.author.id),
            None,
        )

        if ticket is None:
            await ctx.reply(f"{ctx.author.mention} you don't have an active ticket.")
            return

        assert isinstance(ctx.guild, discord.Guild)

        ticket_channel = ctx.guild.get_channel(ticket["ticket_channel"])
        if ticket_channel is None:
            return

        assert isinstance(ticket_channel, discord.TextChannel)

        await ticket_channel.set_permissions(
            member,
            read_messages=True,
            send_messages=True,
            reason=f"Added by {ctx.author} ({ctx.author.id})",
        )

        self._ticket_cache["active_tickets"][self._ticket_cache["active_tickets"].index(ticket)]["ticket_members"].append(
            member.id,
        )

        await ticket_channel.send(f"{member.mention} added to the ticket.")

    @ticket.command(name="remove", aliases=["kick"])
    @commands.bot_has_guild_permissions(manage_channels=True, manage_roles=True)
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def ticket_remove(self, ctx: Context, *, member: discord.Member) -> None:
        """Remove a member from your ticket.

        Bot must have `Manage Channels` and `Manage Roles` permissions.

        Example:
        -------
        - `[p]ticket remove @member`
        """
        active_tickets = self._ticket_cache["active_tickets"]  # type: list[dict]
        ticket = next(
            (ticket for ticket in active_tickets if ticket["ticket_owner"] == ctx.author.id),
            None,
        )

        if ticket is None:
            await ctx.reply(f"{ctx.author.mention} you don't have an active ticket.")
            return

        assert isinstance(ctx.guild, discord.Guild)

        ticket_channel = ctx.guild.get_channel(ticket["ticket_channel"])
        if ticket_channel is None:
            return

        assert isinstance(ticket_channel, discord.TextChannel)

        await ticket_channel.set_permissions(
            member,
            read_messages=False,
            send_messages=False,
            reason=f"Removed by {ctx.author} ({ctx.author.id})",
        )

        self._ticket_cache["active_tickets"][self._ticket_cache["active_tickets"].index(ticket)]["ticket_members"].remove(
            member.id,
        )

        await ticket_channel.send(f"{member.mention} removed from the ticket.")

    async def __wait_for_message(
        self,
        msg: str,
        *,
        ctx: Context,
        check: Callable[[discord.Message], bool],
        convertor: commands.Converter | None = None,
    ) -> str | discord.Object | None:
        try:
            await ctx.reply(embed=discord.Embed(description=msg))
            message = await self.bot.wait_for("message", timeout=60.0, check=check)  # type: discord.Message
        except asyncio.TimeoutError as e:
            err = "Ticket setup timed out."
            raise commands.BadArgument(err) from e

        if message.content.lower() == "cancel":
            err = "Ticket setup cancelled."
            raise commands.BadArgument(err)
        if message.content.lower() in {"none", "no"}:
            return None
        return message.content if convertor is None else await convertor.convert(ctx, message.content)

    @ticket.group(name="setup", aliases=["config"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def ticket_setup(self, ctx: Context) -> None:
        # sourcery skip: last-if-guard
        """Ticket setup walkthrough.

        Invoker must have `Manage Server` permissions.

        Example:
        -------
        - `[p]ticket setup`
        """
        if not ctx.invoked_subcommand:

            def check(m: discord.Message) -> bool:
                return m.author == ctx.author and m.channel == ctx.channel

            ping_role = await self.__wait_for_message(
                "Ping role for tickets? (type `none` for no ping role)",
                ctx=ctx,
                check=check,
                convertor=RoleID(),
            )
            self._ticket_cache["ticket_ping_role"] = getattr(ping_role, "id", None)
            category = await self.__wait_for_message(
                "Category for tickets? (type `none` for no category)",
                ctx=ctx,
                check=check,
                convertor=commands.CategoryChannelConverter(),
            )
            self._ticket_cache["ticket_category_channel"] = getattr(category, "id", None)
            log_channel = await self.__wait_for_message(
                "Log channel for tickets? (type `none` for no log channel)",
                ctx=ctx,
                check=check,
                convertor=commands.TextChannelConverter(),
            )
            self._ticket_cache["ticket_log_channel"] = getattr(log_channel, "id", None)
            message = await self.__wait_for_message(
                "Message in which users can react to open a ticket? (type `none` for no message)",
                ctx=ctx,
                check=check,
            )
            if message is not None:
                self._ticket_cache["ticket_message"] = message
            else:
                maybe_create_new_message: str = await self.__wait_for_message(  # type: ignore
                    "Do you want me to create a new message? (yes/no)",
                    ctx=ctx,
                    check=check,
                )
                if maybe_create_new_message.lower() in {"yes", "y"}:
                    message = await ctx.reply(embed=discord.Embed(description="React to open a ticket."))
                    self._ticket_cache["ticket_message"] = message.id
                    await message.add_reaction("\N{TICKET}")
                else:
                    self._ticket_cache["ticket_message"] = None

            await ctx.reply(embed=discord.Embed(description="Ticket setup complete."))
            await self._save_ticket_cache()

    @ticket_setup.command(name="pingrole", aliases=["ping"])
    @commands.has_permissions(manage_guild=True)
    async def ticket_setup_pingrole(self, ctx: Context, *, role: RoleID | None = None) -> None:
        """Set the ping role for tickets.

        Invoker must have `Manage Server` permissions.

        Example:
        -------
        - `[p]ticket setup pingrole @role`
        """
        if role is None:
            self._ticket_cache["ticket_ping_role"] = None
            await ctx.reply("Ticket ping role removed.")
            return

        assert isinstance(role, discord.Role)

        self._ticket_cache["ticket_ping_role"] = role.id
        await ctx.reply(f"Ticket ping role set to {role.mention}.")

    @ticket_setup.command(name="category", aliases=["cat"])
    @commands.has_permissions(manage_guild=True)
    async def ticket_setup_category(self, ctx: Context, *, category: discord.CategoryChannel | None = None) -> None:
        """Set the ticket category.

        Invoker must have `Manage Server` permissions.

        Example:
        -------
        - `[p]ticket setup category #category`
        - `[p]ticket setup category 123456789`
        """
        if category is None:
            self._ticket_cache["ticket_category_channel"] = None
            await ctx.reply("Ticket category removed.")
            return

        self._ticket_cache["ticket_category_channel"] = category.id
        await ctx.reply(f"Ticket category set to {category.mention}.")

    @ticket_setup.command(name="message", aliases=["msg"])
    @commands.has_permissions(manage_guild=True)
    async def ticket_setup_message(self, ctx: Context, *, message: MessageID | None = None) -> None:
        """Set the ticket message.

        Invoker must have `Manage Server` permissions.

        Example:
        -------
        - `[p]ticket setup message 123456789`
        - `[p]ticket setup message https://discord.com/channels/123/456/789`
        """
        if message is None:
            self._ticket_cache["ticket_message"] = None
            await ctx.reply("Ticket message removed.")
            return

        assert isinstance(message, discord.Message)

        self._ticket_cache["ticket_message"] = message.id
        await ctx.reply(f"Ticket message set to {message.jump_url}.")

    @ticket_setup.command(name="logchannel", aliases=["log"])
    @commands.has_permissions(manage_guild=True)
    async def ticket_setup_logchannel(self, ctx: Context, *, channel: discord.TextChannel | None = None) -> None:
        """Set the ticket log channel.

        Invoker must have `Manage Server` permissions.

        Example:
        -------
        - `[p]ticket setup logchannel #channel`
        """
        if channel is None:
            self._ticket_cache["ticket_log_channel"] = None
            await ctx.reply("Ticket log channel removed.")
            return

        self._ticket_cache["ticket_log_channel"] = channel.id
        await ctx.reply(f"Ticket log channel set to {channel.mention}.")

    async def log_ticket_event(self, *, guild: discord.Guild, ticket: dict, event: str) -> None:
        """Log a ticket event."""
        log_channel = guild.get_channel(self._ticket_cache["ticket_log_channel"] or 0)
        if log_channel is None:
            return

        assert isinstance(log_channel, discord.TextChannel)

        embed = (
            discord.Embed(
                title="Ticket Event",
                description=f"Ticket event for <@{ticket['ticket_owner']}>\n**Event:** {event}",
                color=discord.Color.blurple(),
            )
            .add_field(
                name="Ticket Owner",
                value=f"<@{ticket['ticket_owner']}> ({ticket['ticket_owner']})",
            )
            .add_field(
                name="Ticket Channel",
                value=f"<#{ticket['ticket_channel']}> ({ticket['ticket_channel']})",
            )
            .add_field(
                name="Ticket Members",
                value=", ".join(
                    [
                        f"<@{member}> ({member})"
                        for member in ticket["ticket_members"]
                        if guild.get_member(member) is not None
                    ],
                ),
            )
        )

        await log_channel.send(embed=embed)

    @Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Handle the ticket reaction event."""
        message_id = payload.message_id

        if message_id != self._ticket_cache["ticket_message"]:
            return

        if str(payload.emoji) != "\N{TICKET}":
            return

        guild = self.bot.get_guild(payload.guild_id or 0)  # type: discord.Guild | None
        if guild is None:
            return

        user: discord.Member | None = await self.bot.get_or_fetch_member(guild, payload.message_id)
        if user is None:
            return

        if user.bot:
            return

        for ticket in self._ticket_cache["active_tickets"]:
            if ticket["ticket_owner"] == user.id:
                return

        await self.create_ticket(guild, user)


async def setup(bot: Bot) -> None:
    """Load the Tickets cog."""
    await bot.add_cog(Tickets(bot))
