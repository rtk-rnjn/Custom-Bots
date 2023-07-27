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
IMPLIED, INCLUDING BUT NOT LIMITED typing. THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

import re
from contextlib import suppress

import discord
from discord.ext import commands
from PIL import ImageColor

from core import Context  # pylint: disable=import-error


class EmbedSend(discord.ui.Button):
    """A button that sends the embed to the specified channel."""

    view: EmbedBuilder

    def __init__(self, channel: discord.TextChannel) -> None:
        self.channel = channel
        super().__init__(label=f"Send to #{channel.name}", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the interaction."""
        try:
            m: discord.Message | None = await self.channel.send(embed=self.view.embed)

        except Exception as e:  # pylint: disable=broad-except
            await interaction.response.send_message(f"An error occured: {e}", ephemeral=True)

        else:
            await interaction.response.send_message(
                f"\N{WHITE HEAVY CHECK MARK} | Embed was sent to {self.channel.mention} ([Jump URL](<{m.jump_url}>))",
                ephemeral=True,
            )
            await self.view.on_timeout()


class EmbedCancel(discord.ui.Button["EmbedBuilder"]):
    """A button that cancels the embed sending."""

    def __init__(self) -> None:
        super().__init__(label="Cancel", style=discord.ButtonStyle.red)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the interaction."""
        assert self.view is not None

        await interaction.response.send_message("\N{CROSS MARK} | Embed sending cancelled.", ephemeral=True)
        await self.view.on_timeout()


class BotColor:  # pylint: disable=too-few-public-methods
    """A color converter that converts a string to a discord.Color object."""

    @classmethod
    async def convert(cls, ctx: Context, arg: str) -> discord.Colour | discord.Message:
        """Convert the string to a discord.Color object."""
        match, check = None, False
        with suppress(AttributeError):
            match = re.match(r"\(?(\d+),?\s*(\d+),?\s*(\d+)\)?", arg)
            if match:
                check = all(0 <= int(x) <= 255 for x in match.groups())
        if match and check:
            return discord.Color.from_rgb(*[int(i) for i in match.groups()])
        _converter = commands.ColorConverter()
        result = None
        try:
            result = await _converter.convert(ctx, arg)
        except commands.BadColorArgument:
            with suppress(ValueError):
                color = ImageColor.getrgb(arg)
                result = discord.Color.from_rgb(*color)
        return result or await ctx.reply(f"`{arg}` isn't a valid color.")


class Content(discord.ui.Modal, title="Edit Message Content"):
    """A modal that takes input from the user."""

    _content: discord.ui.TextInput = discord.ui.TextInput(
        label="Content",
        placeholder="This text will be displayed over the embed",
        required=False,
        max_length=2000,
        style=discord.TextStyle.long,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:  # pylint: disable=arguments-differ
        """Handle the interaction."""
        await interaction.response.defer()


class BotView(discord.ui.View):
    """A base view for all views."""

    message: discord.Message
    custom_id = None

    def __init__(self, ctx: Context, *, timeout: float | None = 30) -> None:
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.bot = ctx.bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:  # pylint: disable=arguments-differ
        """Check if the interaction is valid."""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Sorry, you can't use this interaction as it is not started by you.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Disable all buttons and selects."""
        if hasattr(self, "message"):
            for b in self.children:
                if isinstance(b, discord.ui.Button) and b.style != discord.ButtonStyle.link:
                    b.style, b.disabled = discord.ButtonStyle.grey, True
                elif isinstance(b, discord.ui.Select):
                    b.disabled = True
            with suppress(discord.HTTPException):
                await self.message.edit(view=self)
                return

    async def on_error(  # pylint: disable=arguments-differ
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item,
    ) -> None:
        """Handle the error."""
        self.ctx.bot.dispatch("command_error", self.ctx, error)


class BotInput(discord.ui.Modal):
    """A modal that takes input from the user."""

    def __init__(self, title: str) -> None:
        super().__init__(title=title)

    async def on_submit(self, interaction: discord.Interaction) -> None:  # pylint: disable=arguments-differ
        """Handle the interaction."""
        with suppress(discord.NotFound):
            await interaction.response.defer()


class EmbedOptions(discord.ui.Select):
    """A select menu that allows you to edit the embed."""

    view: EmbedBuilder

    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        super().__init__(
            placeholder="Select an option to design the message.",
            options=[
                discord.SelectOption(
                    label="Edit Message (Title, Description, Footer)",
                    value="main",
                    description="Edit your embed title, description, and footer.",
                ),
                discord.SelectOption(
                    label="Edit Thumbnail Image",
                    description="Small Image on the right side of embed",
                    value="thumb",
                ),
                discord.SelectOption(
                    label="Edit Main Image",
                    description="Edit your embed Image",
                    value="image",
                ),
                discord.SelectOption(
                    label="Edit Footer Icon",
                    description="Small icon near footer message",
                    value="footer_icon",
                ),
                discord.SelectOption(
                    label="Edit Embed Color",
                    description="Change the color of the embed",
                    value="color",
                ),
            ],
        )

    async def callback(  # pylint: disable=too-many-branches, too-many-statements
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Handle the interaction."""
        assert self.view is not None

        if (selected := self.values[0]) == "content":
            modal = Content()
            await interaction.response.send_modal(modal)
            await modal.wait()
            self.view.content = modal._content.value or ""  # pylint: disable=protected-access

            await self.view.refresh_view()

        elif selected == "main":
            modal = BotInput("Set Embed Message")
            modal.add_item(
                discord.ui.TextInput(
                    label="Title",
                    placeholder="Enter text for title of embed here...",
                    max_length=256,
                    required=False,
                    style=discord.TextStyle.short,
                    default=self.view.embed.title,
                ),
            )
            modal.add_item(
                discord.ui.TextInput(
                    label="Description",
                    placeholder="Enter text for description of embed here...",
                    max_length=4000,
                    required=False,
                    style=discord.TextStyle.long,
                    default=self.view.embed.description,
                ),
            )
            modal.add_item(
                discord.ui.TextInput(
                    label="Footer Text",
                    placeholder="Enter text for footer of embed here...",
                    style=discord.TextStyle.long,
                    max_length=2048,
                    required=False,
                    default=self.view.embed.footer.text,
                ),
            )
            await interaction.response.send_modal(modal)
            await modal.wait()

            t, d, f = (
                str(modal.children[0]),
                str(modal.children[1]),
                str(modal.children[2]),
            )

            self.view.embed.title = t or None
            self.view.embed.description = d or None
            self.view.embed.set_footer(text=f or None, icon_url=self.view.embed.footer.icon_url)

            await self.view.refresh_view()

        elif selected == "thumb":
            modal = BotInput("Edit Thumbnail Image")
            modal.add_item(
                discord.ui.TextInput(
                    label="Enter Image URL (Optional)",
                    placeholder="Leave empty to remove Image.",
                    required=False,
                    default=getattr(self.view.embed.thumbnail, "url", None),
                ),
            )
            await interaction.response.send_modal(modal)
            await modal.wait()
            url = str(modal.children[0]) or None

            if not url or not url.startswith("https"):
                self.view.embed.set_thumbnail(url=None)

            else:
                self.view.embed.set_thumbnail(url=url)
            await self.view.refresh_view()

        elif selected == "image":
            modal = BotInput("Edit Main Image")
            modal.add_item(
                discord.ui.TextInput(
                    label="Enter Image URL (Optional)",
                    placeholder="Leave empty to remove Image.",
                    required=False,
                    default=getattr(self.view.embed.image, "url", None),
                ),
            )
            await interaction.response.send_modal(modal)
            await modal.wait()
            url = str(modal.children[0]) or None

            if not url or not url.startswith("https"):
                self.view.embed.set_image(url=None)

            else:
                self.view.embed.set_image(url=url)

            await self.view.refresh_view()

        elif selected == "footer_icon":
            modal = BotInput("Edit Footer Icon")
            modal.add_item(
                discord.ui.TextInput(
                    label="Enter Image URL (Optional)",
                    placeholder="Leave empty to remove Icon.",
                    required=False,
                    default=getattr(self.view.embed.footer, "icon_url", None),
                ),
            )
            await interaction.response.send_modal(modal)
            await modal.wait()
            url = str(modal.children[0]) or None

            if not url or not url.startswith("https"):
                self.view.embed.set_footer(icon_url=None, text=self.view.embed.footer.text)

            else:
                self.view.embed.set_footer(icon_url=url, text=self.view.embed.footer.text)

            await self.view.refresh_view()

        elif selected == "color":
            modal = BotInput("Set Embed Color")
            modal.add_item(
                discord.ui.TextInput(
                    label="Enter a valid Color",
                    placeholder="Examples: red, yellow, #00ffb3, etc.",
                    required=False,
                    max_length=7,
                ),
            )
            await interaction.response.send_modal(modal)
            await modal.wait()

            color = 0x36393E

            with suppress(ValueError):
                if c := str(modal.children[0]):
                    color = int(str(await BotColor.convert(self.ctx, c)).replace("#", ""), 16)

            self.view.embed.color = color

            await self.view.refresh_view()


class EmbedBuilder(BotView):
    """A view that builds an embed."""

    def __init__(self, ctx: Context, **kwargs: list[discord.ui.Item]) -> None:
        super().__init__(ctx, timeout=100)

        self.ctx = ctx
        self.add_item(EmbedOptions(self.ctx))

        for i in kwargs.get("items", []):
            self.add_item(i)

    @property
    def formatted(self) -> dict:
        """Return the embed as a dict."""
        return dict(self.embed.to_dict())

    async def refresh_view(self, to_del: discord.Message | None = None) -> None:
        """Refresh the embed builder."""
        if to_del is not None:
            await to_del.delete(delay=0)

        with suppress(discord.HTTPException):
            self.message = await self.message.edit(content=self.content, embed=self.embed, view=self)

    async def rendor(self, *, content: str | None = None, embed: discord.Embed = discord.utils.MISSING, **kw: ...) -> None:
        """Rendor the embed builder."""
        self.message: discord.Message = await self.ctx.reply(
            content or "\u200b",
            embed=embed or self.help_embed,
            view=self,
        )

        self.content = self.message.content  # pylint: disable=attribute-defined-outside-init
        self.embed = self.message.embeds[0]  # pylint: disable=attribute-defined-outside-init

    @property
    def help_embed(self) -> discord.Embed:
        """Return the help embed."""
        return (
            discord.Embed(title="Title", description="Description")
            .set_thumbnail(
                url="https://cdn.discordapp.com/attachments/853174868551532564/860464565338898472/embed_thumbnail.png",
            )
            .set_image(url="https://cdn.discordapp.com/attachments/853174868551532564/860462053063393280/embed_image.png")
            .set_footer(
                text="Footer Message",
                icon_url="https://media.discordapp.net/attachments/853174868551532564/860464989164535828/embed_footer.png",
            )
        )


class ChannelSelect(discord.ui.Select["AnnouncementView"]):
    """A select menu that allows you to select a channel."""

    _keywords = (
        "announcement",
        "announcements",
        "announce",
        "notify",
        "notification",
        "notifications",
        "news",
        "updates",
        "update",
        "important",
        "important-stuff",
        "read-me",
        "readme",
        "read-me-first",
        "readme-first",
        "info",
        "information",
        "rules",
        "rule",
    )

    def __init__(self, *, ctx: Context) -> None:
        options = []
        for channel in ctx.guild.text_channels:
            _to_append = False
            bot_perms = channel.permissions_for(ctx.guild.me)
            my_perms = channel.permissions_for(ctx.author)

            if not (my_perms.read_messages and my_perms.send_messages and my_perms.embed_links):
                continue

            if not (bot_perms.read_messages and bot_perms.send_messages and bot_perms.embed_links):
                continue

            if any(name in channel.name.lower() for name in self._keywords):
                _to_append = True

            elif channel.is_news():
                _to_append = True

            elif channel.is_nsfw():
                _to_append = False

            else:
                _to_append = True

            if _to_append:
                options.append(
                    discord.SelectOption(
                        label=f"#{channel.name}",
                        value=str(channel.id),
                        description=f"Total Members: {len(channel.members)}",
                    ),
                )

        super().__init__(
            placeholder="Select a channel to send the announcement to.",
            min_values=1,
            max_values=1,
            options=options[:25],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the interaction."""
        assert self.view is not None

        await interaction.response.send_message(
            f"\N{WHITE HEAVY CHECK MARK} | You selected <#{self.values[0]}>.",
            ephemeral=True,
        )
        self.view.current_channel = int(self.values[0])


class AnnouncementView(discord.ui.View):  # pylint: disable=too-many-instance-attributes
    """A view for the announcement command."""

    message: discord.Message

    def __init__(
        self,
        ctx: Context,
        *,
        timeout: float | None = 180,
        current_channel: int,
        content: str,
        in_embed: bool = False,
    ) -> None:
        super().__init__(timeout=timeout)

        self.ctx = ctx
        self.channel_select = self.add_item(ChannelSelect(ctx=ctx))
        self.current_channel = current_channel
        self.content = content
        self.in_embed = in_embed

        self._config_ping_everyone = False
        self._config_delete_after: float = -1
        self._config_reply_reference: int = -1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:  # pylint: disable=arguments-differ
        """Check if the interaction is valid."""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Sorry, you can't use this interaction as it is not started by you.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Disable all buttons and selects."""
        if hasattr(self, "message"):
            for b in self.children:
                if isinstance(b, (discord.ui.Button)) and b.style != discord.ButtonStyle.link:
                    b.style, b.disabled = discord.ButtonStyle.grey, True
                elif isinstance(b, discord.ui.Select):
                    b.disabled = True
            with suppress(discord.HTTPException):
                await self.message.edit(view=self)
                return

    async def on_error(  # pylint: disable=arguments-differ
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item,
    ) -> None:
        """Handle the error."""
        await interaction.response.send_message(f"An error occured: {error}", ephemeral=True)
        interaction.client.dispatch("error", error, ctx=self.ctx, interaction=interaction, item=item)

    @discord.ui.button(label="Send Announcement", style=discord.ButtonStyle.green, row=1)
    async def send_announcement(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        """Send the announcement."""
        await interaction.response.defer()
        channel = self.ctx.guild.get_channel(self.current_channel)
        if channel is None:
            return await interaction.followup.send(
                "The channel you selected was deleted or I can't access it anymore.",
                ephemeral=True,
            )

        if self.in_embed:
            embed = discord.Embed(
                title="Announcement",
                description=self.content,
                color=discord.Color.blurple(),
            )
            embed.set_footer(text=f"Announcement by {self.ctx.author}", icon_url=self.ctx.author.display_avatar.url)
            content = discord.utils.MISSING
        else:
            embed = discord.utils.MISSING
            content = self.content

        if not isinstance(channel, discord.CategoryChannel | discord.ForumChannel):
            delete_after = self._config_delete_after if self._config_delete_after > 0 else None
            reply_reference = (
                channel.get_partial_message(self._config_reply_reference)
                if self._config_reply_reference > discord.utils.DISCORD_EPOCH
                else None
            )
            allowed_mentions = (
                discord.AllowedMentions(everyone=self._config_ping_everyone)
                if self._config_ping_everyone
                else discord.AllowedMentions(users=True, roles=True)
            )

            bot_perms = channel.permissions_for(self.ctx.guild.me)
            if not (bot_perms.read_messages and bot_perms.send_messages and bot_perms.embed_links):
                return await interaction.followup.send(
                    "I don't have enough permissions to send messages in that channel.",
                    ephemeral=True,
                )

            my_perms = channel.permissions_for(self.ctx.author)
            if not (my_perms.read_messages and my_perms.send_messages and my_perms.embed_links):
                return await interaction.followup.send(
                    "You don't have enough permissions to send messages in that channel.",
                    ephemeral=True,
                )

            try:
                await channel.send(
                    content,
                    embed=embed,
                    delete_after=delete_after,  # type: ignore
                    reference=reply_reference,  # type: ignore
                    allowed_mentions=allowed_mentions,
                )
            except discord.HTTPException as e:
                await channel.send(content, embed=embed)
                await interaction.followup.send(
                    (
                        f"Message Sent but, an error occured while sending the announcement: {e}\n"
                        "Please report this to the developer."
                    ),
                    ephemeral=True,
                )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, row=1)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        """Cancel the announcement."""
        await interaction.response.defer()
        await interaction.followup.send("Cancelled the announcement.", ephemeral=True)
        await self.message.delete(delay=0)

    @discord.ui.button(label="Ping @everyone: No", style=discord.ButtonStyle.blurple, row=3)
    async def ping_everyone(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Ping @everyone in the announcement."""
        await interaction.response.defer()
        self._config_ping_everyone = not self._config_ping_everyone
        button.label = f"Ping @everyone: {self._config_ping_everyone}"
        button.style = discord.ButtonStyle.green if self._config_ping_everyone else discord.ButtonStyle.blurple
        await self.message.edit(view=self)

        await interaction.followup.send(
            ("Will" if self._config_ping_everyone else "Won't") + " ping @everyone.",
            ephemeral=True,
        )

    @discord.ui.button(label="Delete After: Infinity", style=discord.ButtonStyle.blurple, row=3)
    async def delete_after(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Delete the announcement after a specified time."""
        await interaction.response.defer()
        await interaction.followup.send("Please enter the time in seconds to delete the announcement after.", ephemeral=True)
        try:
            msg = await self.ctx.bot.wait_for(
                "message",
                check=lambda m: (m.author == self.ctx.author and m.channel == self.ctx.channel) and m.content.isdigit(),
                timeout=30,
            )
        except TimeoutError:
            return await interaction.followup.send("You took too long to respond.")

        self._config_delete_after = float(msg.content)
        button.label = f"Delete After: {self._config_delete_after}"
        button.style = discord.ButtonStyle.green
        await self.message.edit(view=self)
        await msg.delete(delay=0)

        await interaction.followup.send(
            f"Message will be deleted after {self._config_delete_after} seconds.",
            ephemeral=True,
        )

    @discord.ui.button(label="Reply Reference: Not Set", style=discord.ButtonStyle.blurple, row=3)
    async def reply_reference(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Reply to a message in the announcement."""
        await interaction.response.defer()
        await interaction.followup.send("Please enter the message ID to reply to.", ephemeral=True)
        try:
            msg = await self.ctx.bot.wait_for(
                "message",
                check=lambda m: (m.author == self.ctx.author and m.channel == self.ctx.channel) and m.content.isdigit(),
                timeout=30,
            )
        except TimeoutError:
            return await interaction.followup.send("You took too long to respond.")

        self._config_reply_reference = int(msg.content)
        button.label = f"Reply Reference: {self._config_reply_reference}"
        button.style = discord.ButtonStyle.green
        await self.message.edit(view=self)
        await msg.delete(delay=0)

        await interaction.followup.send(
            f"Message will be replied to {self._config_reply_reference}.",
            ephemeral=True,
        )
