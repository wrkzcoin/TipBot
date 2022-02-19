import json
import sys
import time
import traceback
import datetime
from cachetools import TTLCache

import disnake
from disnake.ext import commands
from attrdict import AttrDict

import Bot
import store
from config import config
from Bot import truncate, logchanbot

class Events(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.ttlcache = TTLCache(maxsize=500, ttl=60.0)


    async def get_coin_setting(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    coin_list = {}
                    sql = """ SELECT * FROM `coin_settings` """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each in result:
                            coin_list[each['coin_name']] = each
                        return AttrDict(coin_list)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None


    @commands.Cog.listener()
    async def on_ready(self):
        print('Logged in as')
        print(self.bot.user.name)
        print(self.bot.user.id)
        print('------')
        self.bot.start_time = datetime.datetime.now()
        game = disnake.Game(name=".")
        await self.bot.change_presence(status=disnake.Status.online, activity=game)
        # Load coin setting
        try:
            coin_list = await self.get_coin_setting()
            if coin_list:
                self.bot.coin_list = coin_list
                print("coin setting loaded...")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.Cog.listener()
    async def on_button_click(self, inter):
        # If DM, can always delete
        if inter.message.author == self.bot.user and isinstance(inter.channel, disnake.DMChannel):
            try:
                await inter.message.delete()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        elif inter.message.author == self.bot.user and inter.component.custom_id == "close_any_message":
            try:
                await inter.message.delete()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        elif inter.message.author == self.bot.user and inter.component.custom_id == "close_message":
            get_message = await store.get_discord_bot_message(str(inter.message.id), "NO")
            if get_message and get_message['owner_id'] == str(inter.author.id):
                try:
                    await inter.message.delete()
                    await store.delete_discord_bot_message(str(inter.message.id), str(inter.author.id))
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            elif get_message and get_message['owner_id'] != str(inter.author.id):
                # Not your message.
                return
            else:
                # no record, just delete
                try:
                    await inter.message.delete()
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)


    @commands.Cog.listener()
    async def on_shard_ready(self, shard_id):
        print(f'Shard {shard_id} connected')


    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        pass

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        pass

    @commands.Cog.listener()
    async def on_message(self, message):
        # should ignore webhook message
        if isinstance(message.channel, disnake.DMChannel) == False and message.webhook_id:
            return

        if isinstance(message.channel, disnake.DMChannel) == False and message.author.bot == False and message.author != self.bot.user:
            await Bot.add_msg_redis(json.dumps([str(message.guild.id), message.guild.name, str(message.channel.id), message.channel.name,
                                                str(message.author.id), message.author.name, str(message.id), int(time.time())]), False)


    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        # If bot react, ignore.
        if user.id == self.bot.user.id:
            return


    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.guild_id is None:
            return  # Reaction is on a private message
        """Handle a reaction add."""
        try:
            emoji_partial = str(payload.emoji)
            message_id = payload.message_id
            channel_id = payload.channel_id
            user_id = payload.user_id
            guild = self.bot.get_guild(payload.guild_id)
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return
            if isinstance(channel, disnake.DMChannel):
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await Bot.logchanbot(traceback.format_exc())
            return
        message = None
        author = None
        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                author = message.author
            except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                # No message found
                return
            member = self.bot.get_user(user_id)


def setup(bot):
    bot.add_cog(Events(bot))
