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

import re
import typing as T
from contextlib import suppress

import discord
from discord.ext import commands
from PIL import ImageColor

from core import Context


class EmbedSend(discord.ui.Button):
    view: EmbedBuilder

    def __init__(self, channel: discord.TextChannel):
        self.channel = channel
        super().__init__(label="Send to #{0}".format(channel.name), style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction) -> T.Any:
        try:
            m: T.Optional[discord.Message] = await self.channel.send(embed=self.view.embed)

        except Exception as e:
            await interaction.response.send_message(f"An error occured: {e}", ephemeral=True)

        else:
            await interaction.response.send_message(
                f"\N{WHITE HEAVY CHECK MARK} | Embed was sent to {self.channel.mention} ([Jump URL](<{m.jump_url}>))",
                ephemeral=True,
            )
            await self.view.on_timeout()


class EmbedCancel(discord.ui.Button["EmbedBuilder"]):
    def __init__(self):
        super().__init__(label="Cancel", style=discord.ButtonStyle.red)

    async def callback(self, interaction: discord.Interaction) -> T.Any:
        assert self.view is not None

        await interaction.response.send_message("\N{CROSS MARK} | Embed sending cancelled.", ephemeral=True)
        await self.view.on_timeout()


class BotColor:
    @classmethod
    async def convert(cls, ctx: Context, arg: str):
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
    _content: discord.ui.TextInput = discord.ui.TextInput(
        label="Content",
        placeholder="This text will be displayed over the embed",
        required=False,
        max_length=2000,
        style=discord.TextStyle.long,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()


class BotView(discord.ui.View):
    message: discord.Message
    custom_id = None

    def __init__(self, ctx: Context, *, timeout: T.Optional[float] = 30):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.bot = ctx.bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Sorry, you can't use this interaction as it is not started by you.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        if hasattr(self, "message"):
            for b in self.children:
                if isinstance(b, discord.ui.Button) and b.style != discord.ButtonStyle.link:
                    b.style, b.disabled = discord.ButtonStyle.grey, True
                elif isinstance(b, discord.ui.Select):
                    b.disabled = True
            with suppress(discord.HTTPException):
                await self.message.edit(view=self)
                return

    async def on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
        self.ctx.bot.dispatch("command_error", self.ctx, error)


class BotInput(discord.ui.Modal):
    def __init__(self, title: str):
        super().__init__(title=title)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        with suppress(discord.NotFound):
            await interaction.response.defer()


class EmbedOptions(discord.ui.Select):
    view: EmbedBuilder

    def __init__(self, ctx: Context):
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

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None

        if (selected := self.values[0]) == "content":
            modal = Content()
            await interaction.response.send_modal(modal)
            await modal.wait()
            self.view.content = modal._content.value or ""

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
                )
            )
            modal.add_item(
                discord.ui.TextInput(
                    label="Description",
                    placeholder="Enter text for description of embed here...",
                    max_length=4000,
                    required=False,
                    style=discord.TextStyle.long,
                    default=self.view.embed.description,
                )
            )
            modal.add_item(
                discord.ui.TextInput(
                    label="Footer Text",
                    placeholder="Enter text for footer of embed here...",
                    style=discord.TextStyle.long,
                    max_length=2048,
                    required=False,
                    default=self.view.embed.footer.text,
                )
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
                )
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
                )
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
                )
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
                )
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
    def __init__(self, ctx: Context, **kwargs: T.Any):
        super().__init__(ctx, timeout=100)

        self.ctx = ctx
        self.add_item(EmbedOptions(self.ctx))

        for _ in kwargs.get("items", []):  # to add extra buttons and handle this view externally
            self.add_item(_)

    @property
    def formatted(self):
        return self.embed.to_dict()

    async def refresh_view(self, to_del: T.Optional[discord.Message] = None):
        if to_del is not None:
            await to_del.delete(delay=0)

        with suppress(discord.HTTPException):
            self.message = await self.message.edit(content=self.content, embed=self.embed, view=self)

    async def rendor(self, **kwargs: T.Any):
        self.message: discord.Message = await self.ctx.reply(
            kwargs.get("content", "\u200b"),
            embed=kwargs.get("embed", self.help_embed),
            view=self,
        )

        self.content = self.message.content
        self.embed = self.message.embeds[0]

    @property
    def help_embed(self):
        return (
            discord.Embed(title="Title", description="Description")
            .set_thumbnail(
                url="https://cdn.discordapp.com/attachments/853174868551532564/860464565338898472/embed_thumbnail.png"
            )
            .set_image(url="https://cdn.discordapp.com/attachments/853174868551532564/860462053063393280/embed_image.png")
            .set_footer(
                text="Footer Message",
                icon_url="https://media.discordapp.net/attachments/853174868551532564/860464989164535828/embed_footer.png",
            )
        )
