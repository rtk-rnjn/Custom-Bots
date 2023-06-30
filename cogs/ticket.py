from __future__ import annotations

from typing import Optional

import discord
from discord.ext import commands

from core import Bot, Cog, Context
from utils import MessageID, RoleID


class Ticket(Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.ticket_collection = self.bot.ticket

        self._ticket_cache = {}

        """
        {
            "ticket_{BOT_ID}": {
                "ticket_category_channel": INT,
                "ticket_ping_role": INT,
                "ticket_message": INT,
                "ticket_message_channel": INT,
                "ticket_log_channel": INT,
                "active_tickets": [
                    {
                        "ticket_id": INT,
                        "ticket_owner": INT,
                        "ticket_channel": INT,
                        "ticket_name": STR,
                        "ticket_topic": STR,
                        "ticket_members": [
                            INT
                        ]
                ]
            }
        }
        """

    DEFAULT_PAYLOAD = {
        "ticket_category_channel": None,
        "ticket_ping_role": None,
        "ticket_message": None,
        "ticket_message_channel": None,
        "ticket_log_channel": None,
        "active_tickets": [],
    }

    async def cog_load(self):
        BOT_ID = self.bot.user.id  # type: ignore
        self._ticket_cache = (
            await self.ticket_collection.find_one({"_id": f"ticket_{BOT_ID}"}) or {}
        )

        self._ticket_cache = {**self.DEFAULT_PAYLOAD, **self._ticket_cache}

    async def cog_unload(self):
        BOT_ID = self.bot.user.id  # type: ignore
        await self.ticket_collection.update_one(
            {"_id": f"ticket_{BOT_ID}"}, {"$set": self._ticket_cache}
        )

    async def create_ticket(self, guild: discord.Guild, user: discord.Member) -> None:
        category_channel = self._ticket_cache["ticket_category_channel"]
        ping_role = self._ticket_cache["ticket_ping_role"]

        category = guild.get_channel(category_channel)
        if category is None:
            return

        assert isinstance(category, discord.CategoryChannel)

        role = guild.get_role(ping_role)
        ticket = await category.create_text_channel(
            name=f"ticket-{len(self._ticket_cache['active_tickets']) + 1}",
            topic="Ticket",
            overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(
                    read_messages=True, send_messages=True
                ),
                user: discord.PermissionOverwrite(
                    read_messages=True, send_messages=True
                ),
                role: discord.PermissionOverwrite(
                    read_messages=True, send_messages=True
                ),
            },
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
            f"{user.mention} {role.mention if role else ''} your ticket has been created. Please wait for a staff member to assist you."
        )
        await self.log_ticket_event(guild=guild, ticket=data, event="create")

    async def delete_ticket(self, guild: discord.Guild, ticket: dict) -> None:
        category_channel = self._ticket_cache["ticket_category_channel"]
        category = guild.get_channel(category_channel)
        if category is None:
            return

        assert isinstance(category, discord.CategoryChannel)

        ticket_channel = guild.get_channel(ticket["ticket_channel"])
        if ticket_channel is None:
            return

        assert isinstance(ticket_channel, discord.TextChannel)

        await ticket_channel.delete(reason="Ticket closed.")

        self._ticket_cache["active_tickets"].remove(ticket)

    @commands.group(name="ticket", aliases=["tickets"], invoke_without_command=True)
    async def ticket(self, ctx: Context) -> None:
        """Ticket related commands"""
        if not ctx.invoked_subcommand:
            await ctx.send_help(ctx.command)

    @ticket.command(name="new", aliases=["create"])
    async def ticket_new(self, ctx: Context) -> None:
        """Create a new ticket"""
        active_tickets = self._ticket_cache["active_tickets"]
        if ctx.author.id in [ticket["ticket_owner"] for ticket in active_tickets]:
            await ctx.reply(f"{ctx.author.mention} you already have an active ticket.")
            return

        assert isinstance(ctx.guild, discord.Guild) and isinstance(
            ctx.author, discord.Member
        )

        await self.create_ticket(ctx.guild, ctx.author)

    @ticket.command(name="close", aliases=["delete"])
    async def ticket_close(self, ctx: Context) -> None:
        """Close a ticket"""
        active_tickets = self._ticket_cache["active_tickets"]
        ticket = next(
            (
                ticket
                for ticket in active_tickets
                if ticket["ticket_owner"] == ctx.author.id
            ),
            None,
        )

        if ticket is None:
            await ctx.reply(f"{ctx.author.mention} you don't have an active ticket.")
            return

        assert isinstance(ctx.guild, discord.Guild)

        await self.delete_ticket(ctx.guild, ticket)
        await self.log_ticket_event(guild=ctx.guild, ticket=ticket, event="delete")

    @ticket.command(name="add", aliases=["invite"])
    async def ticket_add(self, ctx: Context, *, member: discord.Member) -> None:
        """Add a member to your ticket"""
        active_tickets = self._ticket_cache["active_tickets"]
        ticket = next(
            (
                ticket
                for ticket in active_tickets
                if ticket["ticket_owner"] == ctx.author.id
            ),
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

        self._ticket_cache["active_tickets"][
            self._ticket_cache["active_tickets"].index(ticket)
        ]["ticket_members"].append(member.id)

        await ticket_channel.send(f"{member.mention} added to the ticket.")

    @ticket.command(name="remove", aliases=["kick"])
    async def ticket_remove(self, ctx: Context, *, member: discord.Member) -> None:
        """Remove a member from your ticket"""
        active_tickets = self._ticket_cache["active_tickets"]
        ticket = next(
            (
                ticket
                for ticket in active_tickets
                if ticket["ticket_owner"] == ctx.author.id
            ),
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

        self._ticket_cache["active_tickets"][
            self._ticket_cache["active_tickets"].index(ticket)
        ]["ticket_members"].remove(member.id)

        await ticket_channel.send(f"{member.mention} removed from the ticket.")

    @ticket.group(name="setup", aliases=["config"], invoke_without_command=True)
    async def ticket_setup(self, ctx: Context) -> None:
        pass

    @ticket_setup.command(name="pingrole", aliases=["ping"])
    async def ticket_setup_pingrole(
        self, ctx: Context, *, role: Optional[RoleID] = None
    ) -> None:
        """Set the ping role for tickets"""
        if role is None:
            self._ticket_cache["ticket_ping_role"] = None
            await ctx.reply("Ticket ping role removed.")
            return

        self._ticket_cache["ticket_ping_role"] = role
        await ctx.reply(f"Ticket ping role set to {role.mention}.")  # type: ignore

    @ticket_setup.command(name="category", aliases=["cat"])
    async def ticket_setup_category(
        self, ctx: Context, *, category: Optional[discord.CategoryChannel] = None
    ) -> None:
        """Set the ticket category"""
        if category is None:
            self._ticket_cache["ticket_category_channel"] = None
            await ctx.reply("Ticket category removed.")
            return

        self._ticket_cache["ticket_category_channel"] = category.id
        await ctx.reply(f"Ticket category set to {category.mention}.")

    @ticket_setup.command(name="message", aliases=["msg"])
    async def ticket_setup_message(
        self, ctx: Context, *, message: Optional[MessageID] = None
    ) -> None:
        pass

    @ticket_setup.command(name="logchannel", aliases=["log"])
    async def ticket_setup_logchannel(
        self, ctx: Context, *, channel: Optional[discord.TextChannel] = None
    ) -> None:
        """Set the ticket log channel"""
        if channel is None:
            self._ticket_cache["ticket_log_channel"] = None
            await ctx.reply("Ticket log channel removed.")
            return

        self._ticket_cache["ticket_log_channel"] = channel.id
        await ctx.reply(f"Ticket log channel set to {channel.mention}.")

    async def log_ticket_event(self, *, guild: discord.Guild, ticket: dict, event: str):
        """Log a ticket event"""
        log_channel = guild.get_channel(self._ticket_cache["ticket_log_channel"])
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
                    ]
                ),
            )
        )

        await log_channel.send(embed=embed)


async def setup(bot: Bot) -> None:
    await bot.add_cog(Ticket(bot))
