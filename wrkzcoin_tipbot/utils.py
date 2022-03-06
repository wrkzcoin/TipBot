import asyncio
import datetime
import difflib
import re
from enum import Enum
import sys, traceback

import disnake
import numpy as np
from disnake.embeds import _EmptyEmbed
from disnake.ext.commands import BadArgument, Converter

from disnake import ActionRow, Button, ButtonStyle
from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice
from typing import List
from Bot import RowButton_row_close_any_message


# Defines a simple paginator of buttons for the embed.
class MenuPage(disnake.ui.View):
    message: disnake.Message

    def __init__(self, inter, embeds: List[disnake.Embed], timeout: float=60):
        super().__init__(timeout=timeout)
        self.inter = inter

        # Sets the embed list variable.
        self.embeds = embeds

        # Current embed number.
        self.embed_count = 0

        # Disables previous page button by default.
        self.prev_page.disabled = True
        
        self.first_page.disabled = True

        # Sets the footer of the embeds with their respective page numbers.
        for i, embed in enumerate(self.embeds):
            embed.set_footer(text=f"Page {i + 1} of {len(self.embeds)}")


    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, disnake.ui.Button):
                child.disabled = True

        if type(self.inter) == disnake.ApplicationCommandInteraction:
            await self.inter.edit_original_message(view=RowButton_row_close_any_message())
        else:
            if self.message:
                await self.message.edit(view=RowButton_row_close_any_message())


    @disnake.ui.button(label="⏪", style=disnake.ButtonStyle.red)
    async def first_page(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if interaction.author != self.inter.author:
            return

        # Decrements the embed count.
        self.embed_count = 0

        # Gets the embed object.
        embed = self.embeds[self.embed_count]
        
        self.last_page.disabled = False

        # Enables the next page button and disables the previous page button if we're on the first embed.
        self.next_page.disabled = False
        if self.embed_count == 0:
            self.prev_page.disabled = True
            self.first_page.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)


    @disnake.ui.button(label="◀️", style=disnake.ButtonStyle.red)
    async def prev_page(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if interaction.author != self.inter.author:
            return

        # Decrements the embed count.
        self.embed_count -= 1

        # Gets the embed object.
        embed = self.embeds[self.embed_count]
        
        self.last_page.disabled = False

        # Enables the next page button and disables the previous page button if we're on the first embed.
        self.next_page.disabled = False
        if self.embed_count == 0:
            self.prev_page.disabled = True
            self.first_page.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

    # @disnake.ui.button(label="⏹️", style=disnake.ButtonStyle.red)
    @disnake.ui.button(label="⏹️", style=disnake.ButtonStyle.red)
    async def remove(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if interaction.author != self.inter.author:
            return
        #await interaction.response.edit_message(view=None)
        await interaction.message.delete()


    # @disnake.ui.button(label="", emoji="▶️", style=disnake.ButtonStyle.green)
    @disnake.ui.button(label="▶️", style=disnake.ButtonStyle.green)
    async def next_page(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if interaction.author != self.inter.author:
            return
        # Increments the embed count.
        self.embed_count += 1

        # Gets the embed object.
        embed = self.embeds[self.embed_count]

        # Enables the previous page button and disables the next page button if we're on the last embed.
        self.prev_page.disabled = False
        
        self.first_page.disabled = False

        if self.embed_count == len(self.embeds) - 1:
            self.next_page.disabled = True
            self.last_page.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)


    @disnake.ui.button(label="⏩", style=disnake.ButtonStyle.green)
    async def last_page(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if interaction.author != self.inter.author:
            return
        # Increments the embed count.
        self.embed_count = len(self.embeds) - 1

        # Gets the embed object.
        embed = self.embeds[self.embed_count]
        
        self.first_page.disabled = False

        # Enables the previous page button and disables the next page button if we're on the last embed.
        self.prev_page.disabled = False
        if self.embed_count == len(self.embeds) - 1:
            self.next_page.disabled = True
            self.last_page.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

