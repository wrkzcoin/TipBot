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
        elif hasattr(inter, "message") and inter.message.author == self.bot.user and inter.component.custom_id.startswith("trivia_answers_"):
            try:
                msg = "Nothing to do!"
                get_message = await store.get_discord_triviatip_by_msgid(str(inter.message.id))
                if get_message and int(get_message['from_userid']) == inter.author.id:
                    ## await inter.response.send_message(content="You are the owner of trivia id: {}".format(str(inter.message.id)), ephemeral=True)
                    ## return
                    pass
                # Check if user in
                check_if_in = await store.check_if_trivia_responder_in(str(inter.message.id), get_message['from_userid'], str(inter.author.id))
                if check_if_in:
                    # await inter.response.send_message(content="You already answer of trivia id: {}".format(str(inter.message.id)), ephemeral=True)
                    await inter.response.defer()
                    return
                else:
                    # If time already pass
                    if int(time.time()) > get_message['trivia_endtime']:
                        return
                    else:
                        key = "triviatip_{}_{}".format(str(inter.message.id), str(inter.author.id))
                        try:
                            if self.ttlcache[key] == key:
                                return
                            else:
                                self.ttlcache[key] = key
                        except Exception as e:
                            pass
                        # Check if buttun is wrong or right
                        result = "WRONG"
                        if inter.component.label == get_message['button_correct_answer']:
                            result = "RIGHT"
                        insert_triviatip = await store.insert_trivia_responder(str(inter.message.id), get_message['guild_id'], get_message['question_id'], get_message['from_userid'], str(inter.author.id), "{}#{}".format(inter.author.name, inter.author.discriminator), result)
                        msg = "You answered to trivia id: {}".format(str(inter.message.id))
                        await inter.response.defer()
                        await inter.response.send_message(content=msg, ephemeral=True)
                        return
            except (disnake.InteractionResponded, disnake.InteractionTimedOut, disnake.NotFound) as e:
                return await inter.followup.send(
                    msg,
                    ephemeral=True,
                )
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        elif hasattr(inter, "message") and inter.message.author == self.bot.user and inter.component.custom_id.startswith("mathtip_answers_"):
            try:
                msg = "Nothing to do!"
                get_message = await store.get_discord_mathtip_by_msgid(str(inter.message.id))
                if get_message and int(get_message['from_userid']) == inter.author.id:
                    ## await inter.response.send_message(content="You are the owner of trivia id: {}".format(str(inter.message.id)), ephemeral=True)
                    # return
                    pass
                # Check if user in
                check_if_in = await store.check_if_mathtip_responder_in(str(inter.message.id), get_message['from_userid'], str(inter.author.id))
                if check_if_in:
                    # await inter.response.send_message(content="You already answer of trivia id: {}".format(str(inter.message.id)), ephemeral=True)
                    await inter.response.defer()
                    return
                else:
                    # If time already pass
                    if int(time.time()) > get_message['math_endtime']:
                        return
                    else:
                        key = "mathtip_{}_{}".format(str(inter.message.id), str(inter.author.id))
                        try:
                            if self.ttlcache[key] == key:
                                return
                            else:
                                self.ttlcache[key] = key
                        except Exception as e:
                            pass
                        # Check if buttun is wrong or right
                        result = "WRONG"
                        if float(inter.component.label) == float(get_message['eval_answer']):
                            result = "RIGHT"
                        insert_triviatip = await store.insert_mathtip_responder(str(inter.message.id), get_message['guild_id'], get_message['from_userid'], str(inter.author.id), "{}#{}".format(inter.author.name, inter.author.discriminator), result)
                        msg = "You answered to trivia id: {}".format(str(inter.message.id))
                        await inter.response.defer()
                        await inter.response.send_message(content=msg, ephemeral=True)
                        return
            except (disnake.InteractionResponded, disnake.InteractionTimedOut, disnake.NotFound) as e:
                return await inter.followup.send(
                    msg,
                    ephemeral=True,
                )
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
