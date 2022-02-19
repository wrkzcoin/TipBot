import asyncio
import re
import sys
import time
import traceback
from datetime import datetime
import random
import qrcode
import uuid

import disnake
from disnake.ext import tasks, commands

from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

import store
from Bot import *

from config import config


class Guild(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    async def guild_find_by_key(self, guild_id: str, secret: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT `"""+secret+"""` FROM `discord_server` WHERE `serverid`=%s """
                    await cur.execute(sql, ( guild_id ))
                    result = await cur.fetchone()
                    if result: return result[secret]
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None


    async def guild_insert_key(self, guild_id: str, key: str, secret: str, update: bool=False):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE discord_server SET `"""+secret+"""`=%s WHERE `serverid`=%s LIMIT 1 """
                    await cur.execute(sql, (key, guild_id))
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None


    @commands.guild_only()
    @commands.slash_command(description="Various guild's commands.")
    async def guild(self, ctx):
        pass


    @guild.sub_command(
        usage="guild topgg [resetkey]", 
        options=[
            Option('resetkey', 'resetkey', OptionType.string, required=False, choices=[
                OptionChoice("YES", "YES"),
                OptionChoice("NO", "NO")
            ])
        ],
        description="Get token key to set for topgg vote in bot channel."
    )
    async def topgg(
        self,
        ctx,
        resetkey: str=None
    ):
        secret = "topgg_vote_secret"
        if resetkey is None: resetkey = "NO"
        get_guild_by_key = await self.guild_find_by_key(str(ctx.guild.id), secret)
        if get_guild_by_key is None:
            # Generate
            random_string = str(uuid.uuid4())
            insert_key = await self.guild_insert_key(str(ctx.guild.id), random_string, secret, False)
            if insert_key:
                try:
                    await ctx.response.send_message(f'Your guild {ctx.guild.name}\'s topgg key: `{random_string}`\nWebook URL: `{config.topgg.guild_vote_url}`', ephemeral=True)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            else:
                try:
                    await ctx.response.send_message(f'Internal error! Please report!', ephemeral=True)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
        elif get_guild_by_key and resetkey == "NO":
            # Just display
            try:
                await ctx.response.send_message(f'Your guild {ctx.guild.name}\'s topgg key: `{get_guild_by_key}`\nWebook URL: `{config.topgg.guild_vote_url}`', ephemeral=True)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        elif get_guild_by_key and resetkey == "YES":
            # Update a new key and say to it. Do not forget to update
            random_string = str(uuid.uuid4())
            insert_key = await self.guild_insert_key(str(ctx.guild.id), random_string, secret, True)
            if insert_key:
                try:
                    await ctx.response.send_message(f'Your guild {ctx.guild.name}\'s topgg updated key: `{random_string}`\nWebook URL: `{config.topgg.guild_vote_url}`', ephemeral=True)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            else:
                try:
                    await ctx.response.send_message(f'Internal error! Please report!', ephemeral=True)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)


    @guild.sub_command(
        usage="guild discordlist [resetkey]", 
        options=[
            Option('resetkey', 'resetkey', OptionType.string, required=False, choices=[
                OptionChoice("YES", "YES"),
                OptionChoice("NO", "NO")
            ])
        ],
        description="Get token key to set for discordlist vote in bot channel."
    )
    async def discordlist(
        self,
        ctx,
        resetkey: str=None
    ):
        secret = "discordlist_vote_secret"
        if resetkey is None: resetkey = "NO"
        get_guild_by_key = await self.guild_find_by_key(str(ctx.guild.id), secret)
        if get_guild_by_key is None:
            # Generate
            random_string = str(uuid.uuid4())
            insert_key = await self.guild_insert_key(str(ctx.guild.id), random_string, secret, False)
            if insert_key:
                try:
                    await ctx.response.send_message(f'Your guild {ctx.guild.name}\'s discordlist key: `{random_string}`\nWebook URL: `{config.discordlist.guild_vote_url}`', ephemeral=True)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            else:
                try:
                    await ctx.response.send_message(f'Internal error! Please report!', ephemeral=True)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
        elif get_guild_by_key and resetkey == "NO":
            # Just display
            try:
                await ctx.response.send_message(f'Your guild {ctx.guild.name}\'s discordlist key: `{get_guild_by_key}`\nWebook URL: `{config.discordlist.guild_vote_url}`', ephemeral=True)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        elif get_guild_by_key and resetkey == "YES":
            # Update a new key and say to it. Do not forget to update
            random_string = str(uuid.uuid4())
            insert_key = await self.guild_insert_key(str(ctx.guild.id), random_string, secret, True)
            if insert_key:
                try:
                    await ctx.response.send_message(f'Your guild {ctx.guild.name}\'s discordlist updated key: `{random_string}`\nWebook URL: `{config.discordlist.guild_vote_url}`', ephemeral=True)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            else:
                try:
                    await ctx.response.send_message(f'Internal error! Please report!', ephemeral=True)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)


def setup(bot):
    bot.add_cog(Guild(bot))