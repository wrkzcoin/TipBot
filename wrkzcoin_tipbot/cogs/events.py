import asyncio
import datetime
import sys
import time
import traceback

import aiomysql
import disnake
import store
from Bot import SERVER_BOT, num_format_coin, EMOJI_INFORMATION, EMOJI_RED_NO, seconds_str
from Bot import logchanbot
from aiomysql.cursors import DictCursor
from attrdict import AttrDict
from cachetools import TTLCache
from cogs.economy import database_economy
from cogs.wallet import WalletAPI
from config import config
from disnake.ext import commands, tasks
from cogs.utils import Utils


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)

        self.ttlcache = TTLCache(maxsize=500, ttl=60.0)
        self.process_saving_message.start()
        self.max_saving_message = 100
        self.is_saving_message = False

        self.reload_coin_paprika.start()
        self.reload_coingecko.start()

        self.update_discord_stats.start()

        self.botLogChan = None
        self.message_id_list = []
        # DB
        self.pool = None

    async def openConnection(self):
        try:
            if self.pool is None:
                self.pool = await aiomysql.create_pool(host=config.mysql.host, port=3306, minsize=4, maxsize=6,
                                                       user=config.mysql.user, password=config.mysql.password,
                                                       db=config.mysql.db, cursorclass=DictCursor, autocommit=True)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)

    # Update stats
    async def insert_new_stats(self, num_server: int, num_online: int, num_users: int, num_bots: int, num_tips: int,
                               date: int):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO discord_stats (`num_server`, `num_online`, `num_users`, `num_bots`, `num_tips`, `date`) VALUES (%s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (num_server, num_online, num_users, num_bots, num_tips, date))
                    await conn.commit()
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

    async def get_tipping_count(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT (SELECT COUNT(*) FROM user_balance_mv) AS nos_tipping,
                              (SELECT COUNT(*) FROM user_balance_mv_data) AS nos_user """
                    await cur.execute(sql, ())
                    result = await cur.fetchone()
                    return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    # End Update stats

    # Trivia / Math
    async def insert_mathtip_responder(self, message_id: str, guild_id: str, from_userid: str, responder_id: str,
                                       responder_name: str, result: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT IGNORE INTO discord_mathtip_responder (`message_id`, `guild_id`, `from_userid`, `responder_id`, `responder_name`, `from_and_responder_uniq`, `result`, `inserted_time`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (message_id, guild_id, from_userid, responder_id, responder_name,
                                            "{}-{}-{}".format(message_id, from_userid, responder_id), result,
                                            int(time.time())))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return False

    async def check_if_mathtip_responder_in(self, message_id: str, from_userid: str, responder_id: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    swap_in = 0.0
                    sql = """ SELECT * FROM `discord_mathtip_responder` WHERE `message_id`=%s AND `from_userid`=%s AND `responder_id`=%s LIMIT 1 """
                    await cur.execute(sql, (message_id, from_userid, responder_id))
                    result = await cur.fetchone()
                    if result and len(result) > 0: return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return False

    async def get_discord_mathtip_by_msgid(self, msg_id: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `discord_mathtip_tmp` WHERE `message_id`=%s """
                    await cur.execute(sql, (msg_id))
                    result = await cur.fetchone()
                    if result: return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def get_discord_triviatip_by_msgid(self, message_id: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    swap_in = 0.0
                    sql = """ SELECT * FROM `discord_triviatip_tmp` WHERE `message_id`=%s LIMIT 1 """
                    await cur.execute(sql, (message_id))
                    result = await cur.fetchone()
                    if result: return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def insert_trivia_responder(self, message_id: str, guild_id: str, question_id: str, from_userid: str,
                                      responder_id: str, responder_name: str, result: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT IGNORE INTO discord_triviatip_responder (`message_id`, `guild_id`, `question_id`, `from_userid`, `responder_id`, `responder_name`, `from_and_responder_uniq`, `result`, `inserted_time`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (
                    message_id, guild_id, question_id, from_userid, responder_id, responder_name,
                    "{}-{}-{}".format(message_id, from_userid, responder_id), result, int(time.time())))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return False

    async def check_if_trivia_responder_in(self, message_id: str, from_userid: str, responder_id: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    swap_in = 0.0
                    sql = """ SELECT * FROM `discord_triviatip_responder` WHERE `message_id`=%s AND `from_userid`=%s AND `responder_id`=%s LIMIT 1 """
                    await cur.execute(sql, (message_id, from_userid, responder_id))
                    result = await cur.fetchone()
                    if result and len(result) > 0: return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return False

    # End Trivia / Math

    async def get_discord_bot_message(self, message_id: str, is_deleted: str = "NO"):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `discord_bot_message_owner` WHERE `message_id`=%s AND `is_deleted`=%s LIMIT 1 """
                    await cur.execute(sql, (message_id, is_deleted))
                    result = await cur.fetchone()
                    if result: return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def delete_discord_bot_message(self, message_id: str, owner_id: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `discord_bot_message_owner` SET `is_deleted`=%s, `date_deleted`=%s WHERE `message_id`=%s AND `owner_id`=%s LIMIT 1 """
                    await cur.execute(sql, ("YES", int(time.time()), message_id, owner_id))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def insert_discord_message(self, list_message):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO discord_messages (`serverid`, `server_name`, `channel_id`, `channel_name`, `user_id`, 
                               `message_author`, `message_id`, `message_time`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE 
                              `message_time`=VALUES(`message_time`)
                              """
                    await cur.executemany(sql, list_message)
                    return cur.rowcount
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return 0

    async def delete_discord_message(self, message_id, user_id):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ DELETE FROM discord_messages WHERE `message_id`=%s AND `user_id`=%s LIMIT 1 """
                    await cur.execute(sql, (message_id, user_id))
                    await conn.commit()
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @tasks.loop(seconds=20.0)
    async def process_saving_message(self):
        time_lap = 10  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "events_process_saving_message"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 2: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        if len(self.bot.message_list) > 0:
            # saving_message
            try:
                saving = await self.insert_discord_message(list(set(self.bot.message_list)))
                if saving > 0:
                    self.bot.message_list = []
            except Exception:
                traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def reload_coin_paprika(self):
        time_lap = 60  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "events_reload_coin_paprika"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.get_coin_paprika_list()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def reload_coingecko(self):
        time_lap = 60  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "events_reload_coingecko"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.get_coingecko_list()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=3600.0)
    async def update_discord_stats(self):
        time_lap = 5.0  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "events_update_discord_stats"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            num_server = len(self.bot.guilds)
            num_online = sum(1 for m in self.bot.get_all_members() if m.status == disnake.Status.online)
            num_users = sum(1 for m in self.bot.get_all_members() if m.bot == False)
            num_bots = sum(1 for m in self.bot.get_all_members() if m.bot == True)
            get_tipping_count = await self.get_tipping_count()
            num_tips = get_tipping_count['nos_tipping']
            await self.insert_new_stats(num_server, num_online, num_users, num_bots, num_tips, int(time.time()))
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    async def get_coin_setting(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    coin_list = {}
                    coin_list_name = []
                    sql = """ SELECT * FROM `coin_settings` WHERE `enable`=1 """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each in result:
                            coin_list[each['coin_name']] = each
                            coin_list_name.append(each['coin_name'])
                        return AttrDict(coin_list)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def get_coin_list_name(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    coin_list_name = []
                    sql = """ SELECT `coin_name` FROM `coin_settings` WHERE `enable`=1 """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each in result:
                            coin_list_name.append(each['coin_name'])
                        return coin_list_name
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    # This token hints is priority
    async def get_token_hints(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_alias_price` """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        hints = {}
                        hint_names = {}
                        for each_item in result:
                            hints[each_item['ticker']] = each_item
                            hint_names[each_item['name'].upper()] = each_item
                        self.bot.token_hints = hints
                        self.bot.token_hint_names = hint_names
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def get_coin_alias_name(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_alias_name` """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        alias_names = {}
                        for each_item in result:
                            alias_names[each_item['alt_name'].upper()] = each_item['coin_name']
                        self.bot.coin_alias_names = alias_names
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    # coin_paprika_list
    async def get_coin_paprika_list(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_paprika_list` WHERE `enable`=1 """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        id_list = {}
                        symbol_list = {}
                        for each_item in result:
                            id_list[each_item['id']] = each_item  # key example: btc-bitcoin
                            symbol_list[each_item['symbol'].upper()] = each_item  # key example: BTC
                        self.bot.coin_paprika_id_list = id_list
                        self.bot.coin_paprika_symbol_list = symbol_list
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    # get_coingecko_list
    async def get_coingecko_list(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_coingecko_list` """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        id_list = {}
                        symbol_list = {}
                        for each_item in result:
                            id_list[each_item['id']] = each_item  # key example: btc-bitcoin
                            symbol_list[each_item['symbol'].upper()] = each_item  # key example: BTC
                        self.bot.coin_coingecko_id_list = id_list
                        self.bot.coin_coingecko_symbol_list = symbol_list
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def get_faucet_coin_list(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT `coin_name` FROM `coin_settings` WHERE `enable`=1 AND `enable_faucet`=%s """
                    await cur.execute(sql, (1))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        return [each['coin_name'] for each in result]
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    @commands.Cog.listener()
    async def on_shard_ready(shard_id):
        print(f'Shard {shard_id} connected')

    @commands.Cog.listener()
    async def on_connect(self):
        # Load coin setting
        try:
            coin_list = await self.get_coin_setting()
            if coin_list:
                self.bot.coin_list = coin_list
                print("coin setting loaded...")
            coin_list_name = await self.get_coin_list_name()
            if coin_list_name:
                self.bot.coin_name_list = coin_list_name
                print("coin_list_name loaded...")
            # faucet coins
            faucet_coins = await self.get_faucet_coin_list()
            if faucet_coins:
                self.bot.faucet_coins = faucet_coins
                print("faucet_coins loaded...")
        except Exception:
            traceback.print_exc(file=sys.stdout)

        # Load token hints
        try:
            await self.get_token_hints()
            print("token_hints loaded...")
            await self.get_coin_alias_name()
            print("coin_alias_name loaded...")
        except Exception:
            traceback.print_exc(file=sys.stdout)

        # Get get_coin_paprika_list list to it
        try:
            await self.get_coin_paprika_list()
            print("get_coin_paprika_list loaded...")
        except Exception:
            traceback.print_exc(file=sys.stdout)

        # Get get_coingecko_list list to it
        try:
            await self.get_coingecko_list()
            print("get_coingecko_list loaded...")
        except Exception:
            traceback.print_exc(file=sys.stdout)


    @commands.Cog.listener()
    async def on_ready(self):
        print('Logged in as')
        print(self.bot.user.name)
        print(self.bot.user.id)
        print('------')
        self.bot.start_time = datetime.datetime.now()
        game = disnake.Game(name="prefix /")
        await self.bot.change_presence(status=disnake.Status.online, activity=game)
        botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)
        await botLogChan.send(f'I am back :)')

    @commands.Cog.listener()
    async def on_message(self, message):
        # should ignore webhook message
        if message is None:
            return

        if hasattr(message, "channel") and hasattr(message.channel, "id") and message.webhook_id:
            return

        if hasattr(message, "channel") and hasattr(message.channel,
                                                   "id") and message.author.bot == False and message.author != self.bot.user:
            if message.id not in self.message_id_list:
                try:
                    self.bot.message_list.append((str(message.guild.id), message.guild.name, str(message.channel.id),
                                                  message.channel.name, str(message.author.id),
                                                  "{}#{}".format(message.author.name, message.author.discriminator),
                                                  str(message.id), int(time.time())))
                    self.message_id_list.append(message.id)
                except Exception:
                    pass
            if len(self.bot.message_list) >= self.max_saving_message:
                # saving_message
                try:
                    saving = await self.insert_discord_message(list(set(self.bot.message_list)))
                    if saving > 0:
                        self.bot.message_list = []
                except Exception:
                    traceback.print_exc(file=sys.stdout)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        # should ignore webhook message
        if message is None:
            return

        if hasattr(message, "channel") and hasattr(message.channel, "id") and message.webhook_id:
            return

        if hasattr(message, "channel") and hasattr(message.channel,
                                                   "id") and message.author.bot == False and message.author != self.bot.user:
            if message.id in self.message_id_list:
                # saving_message
                try:
                    saving = await self.insert_discord_message(list(set(self.bot.message_list)))
                    if saving > 0:
                        self.bot.message_list = []
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            # Try delete from database
            try:
                await self.delete_discord_message(str(message.id), str(message.author.id))
            except Exception:
                traceback.print_exc(file=sys.stdout)

    @commands.Cog.listener()
    async def on_button_click(self, inter):
        # If DM, can always delete
        if inter.message.author == self.bot.user and isinstance(inter.channel, disnake.DMChannel):
            try:
                await inter.message.delete()
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif inter.message.author == self.bot.user and inter.component.custom_id == "close_any_message":
            try:
                await inter.message.delete()
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif inter.message.author == self.bot.user and inter.component.custom_id == "close_message":
            get_message = await self.get_discord_bot_message(str(inter.message.id), "NO")
            if get_message and get_message['owner_id'] == str(inter.author.id):
                try:
                    await inter.message.delete()
                    await self.delete_discord_bot_message(str(inter.message.id), str(inter.author.id))
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            elif get_message and get_message['owner_id'] != str(inter.author.id):
                # Not your message.
                return
            else:
                # no record, just delete
                try:
                    await inter.message.delete()
                except Exception:
                    traceback.print_exc(file=sys.stdout)
        elif hasattr(inter,
                     "message") and inter.message.author == self.bot.user and inter.component.custom_id.startswith(
                "trivia_answers_"):
            try:
                msg = "Nothing to do!"
                get_message = None
                try:
                    msg_id = inter.message.id
                    get_message = await store.get_discord_triviatip_by_msgid(str(msg_id))
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    original_message = await inter.original_message()
                    get_message = await store.get_discord_triviatip_by_msgid(str(original_message.id))

                if get_message is None:
                    await inter.response.send_message(content="Failed for Trivia Button Click!")
                    await logchanbot(
                        f"[ERROR TRIVIA] Failed to click Trivia Tip in guild {inter.guild.name} / {inter.guild.id} by {inter.author.name}#{inter.author.discriminator}!")
                    return

                if get_message and int(get_message['from_userid']) == inter.author.id:
                    ## await inter.response.send_message(content="You are the owner of trivia id: {}".format(str(inter.message.id)), ephemeral=True)
                    return
                # Check if user in
                check_if_in = await self.check_if_trivia_responder_in(str(inter.message.id), get_message['from_userid'],
                                                                      str(inter.author.id))
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
                        except Exception:
                            pass
                        # Check if buttun is wrong or right
                        result = "WRONG"
                        if inter.component.label == get_message['button_correct_answer']:
                            result = "RIGHT"
                        insert_triviatip = await self.insert_trivia_responder(str(inter.message.id),
                                                                              get_message['guild_id'],
                                                                              get_message['question_id'],
                                                                              get_message['from_userid'],
                                                                              str(inter.author.id),
                                                                              "{}#{}".format(inter.author.name,
                                                                                             inter.author.discriminator),
                                                                              result)
                        msg = "You answered to trivia id: {}".format(str(inter.message.id))
                        await inter.response.defer()
                        await inter.response.send_message(content=msg, ephemeral=True)
                        return
            except (disnake.InteractionResponded, disnake.InteractionTimedOut, disnake.NotFound) as e:
                return await inter.followup.send(
                    msg,
                    ephemeral=True,
                )
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif hasattr(inter,
                     "message") and inter.message.author == self.bot.user and inter.component.custom_id.startswith(
                "mathtip_answers_"):
            try:
                msg = "Nothing to do!"
                try:
                    msg_id = inter.message.id
                    get_message = await store.get_discord_mathtip_by_msgid(str(msg_id))
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    original_message = await inter.original_message()
                    get_message = await store.get_discord_mathtip_by_msgid(str(original_message.id))

                if get_message is None:
                    await inter.response.send_message(content="Failed for Math Tip Button Click!")
                    await logchanbot(
                        f"[ERROR MATHTIP] Failed to click Math Tip in guild {inter.guild.name} / {inter.guild.id} by {inter.author.name}#{inter.author.discriminator}!")
                    return

                if get_message and int(get_message['from_userid']) == inter.author.id:
                    ## await inter.response.send_message(content="You are the owner of trivia id: {}".format(str(inter.message.id)), ephemeral=True)
                    return
                # Check if user in
                check_if_in = await self.check_if_mathtip_responder_in(str(inter.message.id),
                                                                       get_message['from_userid'], str(inter.author.id))
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
                        except Exception:
                            pass
                        # Check if buttun is wrong or right
                        result = "WRONG"
                        if float(inter.component.label) == float(get_message['eval_answer']):
                            result = "RIGHT"
                        insert_triviatip = await self.insert_mathtip_responder(str(inter.message.id),
                                                                               get_message['guild_id'],
                                                                               get_message['from_userid'],
                                                                               str(inter.author.id),
                                                                               "{}#{}".format(inter.author.name,
                                                                                              inter.author.discriminator),
                                                                               result)
                        msg = "You answered to trivia id: {}".format(str(inter.message.id))
                        await inter.response.defer()
                        await inter.response.send_message(content=msg, ephemeral=True)
                        return
            except (disnake.InteractionResponded, disnake.InteractionTimedOut, disnake.NotFound) as e:
                return await inter.followup.send(
                    msg,
                    ephemeral=True,
                )
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif inter.message.author == self.bot.user and inter.component.custom_id.startswith(
                "economy_{}_".format(inter.author.id)):
            if inter.component.custom_id.startswith("economy_{}_eat_".format(inter.author.id)):
                # Not to duplicate
                key = inter.component.custom_id + str(int(time.time())) + str(inter.author.id)
                try:
                    if self.ttlcache[key] == key:
                        return
                    else:
                        self.ttlcache[key] = key
                except Exception:
                    pass
                # Not to duplicate
                # Eat
                # Place holder message
                try:
                    await inter.response.send_message(f'{inter.author.mention}, checking food...')
                except Exception:
                    return
                name = inter.component.custom_id.replace("economy_{}_eat_".format(inter.author.id), "")
                db = database_economy(self.bot)
                get_foodlist_guild = await db.economy_get_guild_foodlist(str(inter.guild.id), False)
                all_food_in_guild = {}
                if get_foodlist_guild and len(get_foodlist_guild) > 0:
                    for each_food in get_foodlist_guild:
                        all_food_in_guild[str(each_food['food_emoji'])] = each_food['food_id']
                get_food_id = await db.economy_get_food_id(all_food_in_guild[name])
                coin_name = get_food_id['cost_coin_name'].upper()

                net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                get_deposit = await self.wallet_api.sql_get_userwallet(str(inter.author.id), coin_name, net_name,
                                                                       type_coin, SERVER_BOT, 0)
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(str(inter.author.id), coin_name, net_name,
                                                                          type_coin, SERVER_BOT, 0)

                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']
                else:
                    wallet_address = get_deposit['balance_wallet_address']

                height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                # height can be None
                userdata_balance = await store.sql_user_balance_single(str(inter.author.id), coin_name, wallet_address,
                                                                       type_coin, height, deposit_confirm_depth,
                                                                       SERVER_BOT)
                total_balance = userdata_balance['adjust']

                # Negative check
                try:
                    if total_balance < 0:
                        msg_negative = 'Negative balance detected:\nUser: ' + str(
                            inter.author.id) + '\nCoin: ' + coin_name + '\nBalance: ' + str(total_balance)
                        await logchanbot(msg_negative)
                except Exception:
                    await logchanbot(traceback.format_exc())
                # End negative check
                food_name = get_food_id['food_name']
                if get_food_id['cost_expense_amount'] > total_balance:
                    if inter.author.id in self.bot.GAME_INTERACTIVE_ECO:
                        self.bot.GAME_INTERACTIVE_ECO.remove(inter.author.id)
                    await inter.edit_original_message(
                        content=f"{EMOJI_RED_NO} {inter.author.mention}, insufficient balance to eat `{food_name}`.")
                else:
                    # Else, go on and Insert work to DB
                    add_energy = get_food_id['gained_energy']
                    get_userinfo = await db.economy_get_user(str(inter.author.id), '{}#{}'.format(inter.author.name,
                                                                                                  inter.author.discriminator))

                    if get_userinfo['energy_current'] + add_energy > get_userinfo['energy_total']:
                        add_energy = get_userinfo['energy_total'] - get_userinfo['energy_current']
                    total_energy = get_userinfo['energy_current'] + add_energy
                    coin_name = get_food_id['cost_coin_name']
                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                    contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                    # Not to duplicate
                    key = inter.component.custom_id + str(int(time.time())) + str(inter.author.id)
                    try:
                        if self.ttlcache[key] == key:
                            return
                        else:
                            self.ttlcache[key] = key
                    except Exception:
                        pass
                    # Not to duplicate
                    insert_eating = await db.economy_insert_eating(str(inter.author.id), str(inter.guild.id),
                                                                   get_food_id['cost_coin_name'],
                                                                   get_food_id['cost_expense_amount'],
                                                                   get_food_id['fee_ratio'] * get_food_id[
                                                                       'cost_expense_amount'],
                                                                   coin_decimal, contract, add_energy)

                    paid_money = '{} {}'.format(
                        num_format_coin(get_food_id['cost_expense_amount'], get_food_id['cost_coin_name'], coin_decimal,
                                        False), coin_name)
                    if insert_eating:
                        await inter.edit_original_message(
                            content=f'{EMOJI_INFORMATION} {inter.author.mention}, you paid `{paid_money}` and ate `{food_name}`. You gained `{add_energy}` energy. You have total `{total_energy}` energy.')
                        await inter.message.delete()
                    else:
                        await inter.edit_original_message(
                            content=f"{EMOJI_RED_NO} {inter.author.mention}, internal error.")
                if inter.author.id in self.bot.GAME_INTERACTIVE_ECO:
                    self.bot.GAME_INTERACTIVE_ECO.remove(inter.author.id)

            elif inter.component.custom_id.startswith("economy_{}_work_".format(inter.author.id)):
                # Not to duplicate
                key = inter.component.custom_id + str(int(time.time())) + str(inter.author.id)
                try:
                    if self.ttlcache[key] == key:
                        return
                    else:
                        self.ttlcache[key] = key
                except Exception:
                    pass
                # Not to duplicate
                # Work
                # Place holder message
                try:
                    await inter.response.send_message(f'{inter.author.mention}, checking your work...')
                except Exception:
                    return
                name = inter.component.custom_id.replace("economy_{}_work_".format(inter.author.id), "")
                db = database_economy(self.bot)
                all_work_in_guild = {}
                get_worklist_guild = await db.economy_get_guild_worklist(str(inter.guild.id), False)
                if get_worklist_guild and len(get_worklist_guild) > 0:
                    get_userinfo = await db.economy_get_user(str(inter.author.id), '{}#{}'.format(inter.author.name,
                                                                                                  inter.author.discriminator))
                    for each_work in get_worklist_guild:
                        all_work_in_guild[each_work['work_emoji']] = each_work['work_id']

                    # Insert work to DB
                    get_work_id = await db.economy_get_workd_id(all_work_in_guild[name])
                    add_energy = get_work_id['exp_gained_loss']

                    if get_userinfo['energy_current'] + get_work_id['energy_loss'] > get_userinfo['energy_total'] and \
                            get_work_id['energy_loss'] > 0:
                        add_energy = get_userinfo['energy_total'] - get_userinfo['energy_current']
                    coin_name = get_work_id['reward_coin_name']
                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")

                    insert_activity = await db.economy_insert_activity(str(inter.author.id), str(inter.guild.id),
                                                                       all_work_in_guild[name],
                                                                       get_work_id['duration_in_second'], coin_name,
                                                                       get_work_id['reward_expense_amount'],
                                                                       get_work_id['reward_expense_amount'] *
                                                                       get_work_id['fee_ratio'], coin_decimal,
                                                                       add_energy, get_work_id['health_loss'],
                                                                       get_work_id['energy_loss'])
                    if insert_activity:
                        additional_text = " You can claim in: `{}`.".format(
                            seconds_str(get_work_id['duration_in_second']))
                        task_name = "{} {}".format(get_work_id['work_name'], get_work_id['work_emoji'])
                        await inter.edit_original_message(
                            content=f'{EMOJI_INFORMATION} {inter.author.mention}, you started a new task - {task_name}! {additional_text}')
                    else:
                        await inter.edit_original_message(
                            content=f"{EMOJI_INFORMATION} {inter.author.mention}, internal error.")
                    if inter.author.id in self.bot.GAME_INTERACTIVE_ECO:
                        self.bot.GAME_INTERACTIVE_ECO.remove(inter.author.id)
                    await inter.message.delete()

            elif inter.component.custom_id.startswith("economy_{}_item_".format(inter.author.id)):
                # Not to duplicate
                key = inter.component.custom_id + str(int(time.time())) + str(inter.author.id)
                try:
                    if self.ttlcache[key] == key:
                        return
                    else:
                        self.ttlcache[key] = key
                except Exception:
                    pass
                # Backpack
                # Place holder message
                try:
                    await inter.response.send_message(f'{inter.author.mention}, checking your items...')
                except Exception:
                    return

                name = inter.component.custom_id.replace("economy_{}_item_".format(inter.author.id), "")
                all_item_backpack = {}
                db = database_economy(self.bot)
                get_user_inventory = await db.economy_get_user_inventory(str(inter.author.id))
                nos_items = sum(
                    each_item['numbers'] for each_item in get_user_inventory if each_item['item_name'] != "Gem")
                if get_user_inventory and nos_items == 0:
                    await inter.edit_original_message(
                        content=f"{EMOJI_RED_NO} {inter.author.mention}, you do not have any item in your backpack.")
                    return
                if get_user_inventory and len(get_user_inventory) > 0:
                    for each_item in get_user_inventory:
                        all_item_backpack[str(each_item['item_emoji'])] = each_item['item_id']

                get_item_id = await db.economy_get_item_id(all_item_backpack[name])
                # Else, go on and Insert work to DB
                add_energy = 0
                add_energy_health_str = ""
                get_userinfo = await db.economy_get_user(str(inter.author.id),
                                                         '{}#{}'.format(inter.author.name, inter.author.discriminator))
                if get_item_id['item_energy'] > 0:
                    add_energy = get_item_id['item_energy']
                    if get_userinfo['energy_current'] + add_energy > get_userinfo['energy_total']:
                        add_energy = get_userinfo['energy_total'] - get_userinfo['energy_current']
                    add_energy_health_str = "{} energy".format(add_energy)
                    total_energy = get_userinfo['energy_current'] + add_energy
                    total_energy_health_str = f"You have total `{total_energy}` energy."
                add_health = 0
                if get_item_id['item_health'] > 0:
                    add_health = get_item_id['item_health']
                    if get_userinfo['health_current'] + add_health > get_userinfo['health_total']:
                        add_health = get_userinfo['health_total'] - get_userinfo['health_current']
                    add_energy_health_str = "{} health".format(add_health)
                    total_health = get_userinfo['health_current'] + add_health
                    total_energy_health_str = f"You have total `{total_health}` health."
                # Update userinfo
                update_userinfo = await db.economy_item_update_used(str(inter.author.id), all_item_backpack[name],
                                                                    add_energy, add_health)
                using_item = '{} {}'.format(get_item_id['item_name'], get_item_id['item_emoji'])
                if update_userinfo:
                    await inter.edit_original_message(
                        content=f'{EMOJI_INFORMATION} {inter.author.mention}, you used `{using_item}`. You gained `{add_energy_health_str}`. {total_energy_health_str}')
                else:
                    await inter.edit_original_message(content=f"{EMOJI_RED_NO} {inter.author.mention}, internal error.")
                if inter.author.id in self.bot.GAME_INTERACTIVE_ECO:
                    self.bot.GAME_INTERACTIVE_ECO.remove(inter.author.id)
                await inter.message.delete()

    @commands.Cog.listener()
    async def on_shard_ready(self, shard_id):
        print(f'Shard {shard_id} connected')

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.bot_log()
        try:
            num_server = len(self.bot.guilds)
            num_online = sum(1 for m in self.bot.get_all_members() if m.status == disnake.Status.online)
            num_users = sum(1 for m in self.bot.get_all_members() if m.bot == False)
            num_bots = sum(1 for m in self.bot.get_all_members() if m.bot == True)
            get_tipping_count = await self.get_tipping_count()
            num_tips = get_tipping_count['nos_tipping']
            await self.insert_new_stats(num_server, num_online, num_users, num_bots, num_tips, int(time.time()))
            try:
                if len(self.bot.guilds) > 0 and len(self.bot.guilds) % 10 == 0:
                    botdetails = disnake.Embed(title='About Me', description='')
                    botdetails.add_field(name='Creator\'s Discord Name:', value='pluton#8888', inline=True)
                    botdetails.add_field(name='My Github:', value="[TipBot Github](https://github.com/wrkzcoin/TipBot)",
                                         inline=True)
                    botdetails.add_field(name='Invite Me:', value=config.discord.invite_link, inline=True)
                    botdetails.add_field(name='Servers:', value=len(self.bot.guilds), inline=True)
                    try:
                        botdetails.add_field(name="Online", value='{:,.0f}'.format(
                            sum(1 for m in self.bot.get_all_members() if m.status == disnake.Status.online)),
                                             inline=True)
                        botdetails.add_field(name="Users", value='{:,.0f}'.format(
                            sum(1 for m in self.bot.get_all_members() if m.bot == False)), inline=True)
                        botdetails.add_field(name="Bots", value='{:,.0f}'.format(
                            sum(1 for m in self.bot.get_all_members() if m.bot == True)), inline=True)
                        botdetails.add_field(name="Tips", value='{:,.0f}'.format(get_tipping_count['nos_tipping']),
                                             inline=True)
                        botdetails.add_field(name="Wallets", value='{:,.0f}'.format(get_tipping_count['nos_user']),
                                             inline=True)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    botdetails.set_footer(text='Made in Python',
                                          icon_url='http://findicons.com/files/icons/2804/plex/512/python.png')
                    botdetails.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar)
                    await self.botLogChan.send(embed=botdetails)
            except Exception:
                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        add_server_info = await store.sql_addinfo_by_server(str(guild.id), guild.name, config.discord.prefixCmd, "WRKZ",
                                                            True)
        await self.botLogChan.send(
            f'Bot joins a new guild {guild.name} / {guild.id} / Users: {len(guild.members)}. Total guilds: {len(self.bot.guilds)}.')

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        await self.bot_log()
        try:
            num_server = len(self.bot.guilds)
            num_online = sum(1 for m in self.bot.get_all_members() if m.status == disnake.Status.online)
            num_users = sum(1 for m in self.bot.get_all_members() if m.bot == False)
            num_bots = sum(1 for m in self.bot.get_all_members() if m.bot == True)
            get_tipping_count = await self.get_tipping_count()
            num_tips = get_tipping_count['nos_tipping']
            await self.insert_new_stats(num_server, num_online, num_users, num_bots, num_tips, int(time.time()))
            try:
                if len(self.bot.guilds) > 0 and len(self.bot.guilds) % 10 == 0:
                    botdetails = disnake.Embed(title='About Me', description='')
                    botdetails.add_field(name='Creator\'s Discord Name:', value='pluton#8888', inline=True)
                    botdetails.add_field(name='My Github:', value="[TipBot Github](https://github.com/wrkzcoin/TipBot)",
                                         inline=True)
                    botdetails.add_field(name='Invite Me:', value=config.discord.invite_link, inline=True)
                    botdetails.add_field(name='Servers:', value=len(self.bot.guilds), inline=True)
                    try:
                        botdetails.add_field(name="Online", value='{:,.0f}'.format(
                            sum(1 for m in self.bot.get_all_members() if m.status == disnake.Status.online)),
                                             inline=True)
                        botdetails.add_field(name="Users", value='{:,.0f}'.format(
                            sum(1 for m in self.bot.get_all_members() if m.bot == False)), inline=True)
                        botdetails.add_field(name="Bots", value='{:,.0f}'.format(
                            sum(1 for m in self.bot.get_all_members() if m.bot == True)), inline=True)
                        botdetails.add_field(name="Tips", value='{:,.0f}'.format(get_tipping_count['nos_tipping']),
                                             inline=True)
                        botdetails.add_field(name="Wallets", value='{:,.0f}'.format(get_tipping_count['nos_user']),
                                             inline=True)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    botdetails.set_footer(text='Made in Python',
                                          icon_url='http://findicons.com/files/icons/2804/plex/512/python.png')
                    botdetails.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar)
                    await self.botLogChan.send(embed=botdetails)
            except Exception:
                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        add_server_info = await store.sql_updateinfo_by_server(str(guild.id), "status", "REMOVED")
        await self.botLogChan.send(
            f'Bot was removed from guild {guild.name} / {guild.id}. Total guilds: {len(self.bot.guilds)}')


def setup(bot):
    bot.add_cog(Events(bot))
