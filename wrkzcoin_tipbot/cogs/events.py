import json
import sys
import time
import traceback
import datetime
from cachetools import TTLCache

import disnake
from disnake.ext import commands, tasks
from attrdict import AttrDict
import asyncio

import Bot
from Bot import SERVER_BOT, num_format_coin, EMOJI_INFORMATION, seconds_str

import store
from config import config
from Bot import truncate, logchanbot
from cogs.economy import database_economy
from cogs.wallet import WalletAPI
import redis_utils


class Events(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.ttlcache = TTLCache(maxsize=500, ttl=60.0)
        redis_utils.openRedis()
        self.saving_message = False
        self.process_saving_message.start()
        self.max_saving_message = 5
        
        self.reload_coin_paprika.start()
        self.reload_coingecko.start()
        
        self.botLogChan = None


    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)

    async def insert_discord_message(self, list_message):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO discord_messages (`serverid`, `server_name`, `channel_id`, `channel_name`, `user_id`, 
                               `message_author`, `message_id`, `message_time`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.executemany(sql, list_message)
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None


    @tasks.loop(seconds=30.0)
    async def process_saving_message(self):
        await asyncio.sleep(5.0)
        if self.saving_message == False and len(self.bot.message_list) > 0:
            # saving_message
            self.saving_message = True
            try:
                saving = await self.insert_discord_message(self.bot.message_list)
                if saving: self.bot.message_list = []
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            self.saving_message = False


    @tasks.loop(seconds=120.0)
    async def reload_coin_paprika(self):
        try:
            await self.get_coin_paprika_list()
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @tasks.loop(seconds=120.0)
    async def reload_coingecko(self):
        try:
            await self.get_coingecko_list()
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    async def get_coin_setting(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    coin_list = {}
                    coin_list_name = []
                    sql = """ SELECT * FROM `coin_settings` """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each in result:
                            coin_list[each['coin_name']] = each
                            coin_list_name.append(each['coin_name'])
                        return AttrDict(coin_list)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None


    async def get_coin_list_name(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    coin_list_name = []
                    sql = """ SELECT `coin_name` FROM `coin_settings` """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each in result:
                            coin_list_name.append(each['coin_name'])
                        return coin_list_name
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None


    # This token hints is priority
    async def get_token_hints(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
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
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None


    # coin_paprika_list
    async def get_coin_paprika_list(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_paprika_list` """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        id_list = {}
                        symbol_list = {}
                        for each_item in result:
                            id_list[each_item['id']] = each_item # key example: btc-bitcoin	
                            symbol_list[each_item['symbol'].upper()] = each_item # key example: BTC
                        self.bot.coin_paprika_id_list = id_list
                        self.bot.coin_paprika_symbol_list = symbol_list
                        return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    # get_coingecko_list
    async def get_coingecko_list(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_coingecko_list` """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        id_list = {}
                        symbol_list = {}
                        for each_item in result:
                            id_list[each_item['id']] = each_item # key example: btc-bitcoin	
                            symbol_list[each_item['symbol'].upper()] = each_item # key example: BTC
                        self.bot.coin_coingecko_id_list = id_list
                        self.bot.coin_coingecko_symbol_list = symbol_list
                        return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None


    async def get_faucet_coin_list(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT `coin_name` FROM `coin_settings` WHERE `enable_faucet`=%s """
                    await cur.execute(sql, (1))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        return [each['coin_name'] for each in result]
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
        game = disnake.Game(name="Moved to / > http://invite.discord.bot.tips")
        await self.bot.change_presence(status=disnake.Status.online, activity=game)
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
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        # Load token hints
        try:
            await self.get_token_hints()
            print("token_hints loaded...")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        # Get get_coin_paprika_list list to it
        try:
            await self.get_coin_paprika_list()
            print("get_coin_paprika_list loaded...")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        # Get get_coingecko_list list to it
        try:
            await self.get_coingecko_list()
            print("get_coingecko_list loaded...")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.Cog.listener()
    async def on_message(self, message):
        # should ignore webhook message
        if isinstance(message.channel, disnake.DMChannel) == False and message.webhook_id:
            return

        if isinstance(message.channel, disnake.DMChannel) == False and message.author.bot == False and message.author != self.bot.user:
            self.bot.message_list.append((str(message.guild.id), message.guild.name, str(message.channel.id), message.channel.name, str(message.author.id), "{}#{}".format(message.author.name, message.author.discriminator), str(message.id), int(time.time())))
            # TODO: adjust number message to save
            if self.saving_message == False and len(self.bot.message_list) >= self.max_saving_message:
                # saving_message
                self.saving_message = True
                try:
                    saving = await self.insert_discord_message(self.bot.message_list)
                    if saving: self.bot.message_list = []
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                self.saving_message = False


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
                    return
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
                    return
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
        elif inter.message.author == self.bot.user and inter.component.custom_id.startswith("economy_{}_".format(inter.author.id)):
            if inter.component.custom_id.startswith("economy_{}_eat_".format(inter.author.id)):
                # Not to duplicate
                key = inter.component.custom_id + str(int(time.time()))
                try:
                    if self.ttlcache[key] == key:
                        return
                    else:
                        self.ttlcache[key] = key
                except Exception as e:
                    pass
                # Not to duplicate
                # Eat
                name = inter.component.custom_id.replace("economy_{}_eat_".format(inter.author.id), "")
                db = database_economy()
                get_foodlist_guild = await db.economy_get_guild_foodlist(str(inter.guild.id), False)
                all_food_in_guild = {}
                if get_foodlist_guild and len(get_foodlist_guild) > 0:
                    for each_food in get_foodlist_guild:
                        all_food_in_guild[str(each_food['food_emoji'])] = each_food['food_id']
                get_food_id = await db.economy_get_food_id(all_food_in_guild[name])
                COIN_NAME = get_food_id['cost_coin_name'].upper()
                User_WalletAPI = WalletAPI(self.bot)
                net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
                type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
                get_deposit = await User_WalletAPI.sql_get_userwallet(str(inter.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
                if get_deposit is None:
                    get_deposit = await User_WalletAPI.sql_register_user(str(inter.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
                    
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']

                height = None
                try:
                    if type_coin in ["ERC-20", "TRC-20"]:
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
                    else:
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                # height can be None
                userdata_balance = await store.sql_user_balance_single(str(inter.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                total_balance = userdata_balance['adjust']

                # Negative check
                try:
                    if total_balance < 0:
                        msg_negative = 'Negative balance detected:\nUser: '+str(inter.author.id)+'\nCoin: '+COIN_NAME+'\nBalance: '+str(total_balance)
                        await logchanbot(msg_negative)
                except Exception as e:
                    await logchanbot(traceback.format_exc())
                # End negative check
                food_name = get_food_id['food_name']
                if get_food_id['cost_expense_amount'] > total_balance:
                    if inter.author.id in self.bot.GAME_INTERACTIVE_ECO:
                        self.bot.GAME_INTERACTIVE_ECO.remove(inter.author.id)
                    await inter.response.send_message(content=f"{EMOJI_RED_NO} {inter.author.mention}, Insufficient balance to eat `{food_name}`.")
                else:
                    # Else, go on and Insert work to DB
                    add_energy = get_food_id['gained_energy']
                    get_userinfo = await db.economy_get_user(str(inter.author.id), '{}#{}'.format(inter.author.name, inter.author.discriminator))
                    
                    if get_userinfo['energy_current'] + add_energy > get_userinfo['energy_total']:
                        add_energy = get_userinfo['energy_total'] - get_userinfo['energy_current']
                    total_energy = get_userinfo['energy_current'] + add_energy
                    COIN_NAME = get_food_id['cost_coin_name']
                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                    # Not to duplicate
                    key = inter.component.custom_id + str(int(time.time()))
                    try:
                        if self.ttlcache[key] == key:
                            return
                        else:
                            self.ttlcache[key] = key
                    except Exception as e:
                        pass
                    # Not to duplicate
                    insert_eating = await db.economy_insert_eating(str(inter.author.id), str(inter.guild.id), get_food_id['cost_coin_name'], 
                                                                   get_food_id['cost_expense_amount'], get_food_id['fee_ratio']*get_food_id['cost_expense_amount'], 
                                                                   coin_decimal, add_energy)

                    paid_money = '{} {}'.format(num_format_coin(get_food_id['cost_expense_amount'], get_food_id['cost_coin_name'], coin_decimal, False), COIN_NAME)
                    if insert_eating:
                        await inter.response.send_message(f'{EMOJI_INFORMATION} {inter.author.mention} You paid `{paid_money}` and ate `{food_name}`. You gained `{add_energy}` energy. You have total `{total_energy}` energy.')
                        await inter.message.delete()
                    else:
                        await inter.response.send_message(content=f"{EMOJI_RED_NO} {inter.author.mention}, Internal error.")
                if inter.author.id in self.bot.GAME_INTERACTIVE_ECO:
                    self.bot.GAME_INTERACTIVE_ECO.remove(inter.author.id)
            elif inter.component.custom_id.startswith("economy_{}_work_".format(inter.author.id)):
                # Not to duplicate
                key = inter.component.custom_id + str(int(time.time()))
                try:
                    if self.ttlcache[key] == key:
                        return
                    else:
                        self.ttlcache[key] = key
                except Exception as e:
                    pass
                # Not to duplicate
                # Work
                name = inter.component.custom_id.replace("economy_{}_work_".format(inter.author.id), "")
                db = database_economy()
                all_work_in_guild = {}
                get_worklist_guild = await db.economy_get_guild_worklist(str(inter.guild.id), False)
                if get_worklist_guild and len(get_worklist_guild) > 0:
                    get_userinfo = await db.economy_get_user(str(inter.author.id), '{}#{}'.format(inter.author.name, inter.author.discriminator))
                    for each_work in get_worklist_guild:
                        all_work_in_guild[each_work['work_emoji']] = each_work['work_id']

                    # Insert work to DB
                    get_work_id = await db.economy_get_workd_id(all_work_in_guild[name])
                    add_energy = get_work_id['exp_gained_loss']
                    
                    if get_userinfo['energy_current'] + get_work_id['energy_loss'] > get_userinfo['energy_total'] and get_work_id['energy_loss'] > 0:
                        add_energy = get_userinfo['energy_total'] - get_userinfo['energy_current']
                    COIN_NAME = get_work_id['reward_coin_name']
                    coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")

                    insert_activity = await db.economy_insert_activity(str(inter.author.id), str(inter.guild.id), all_work_in_guild[name], get_work_id['duration_in_second'], COIN_NAME, get_work_id['reward_expense_amount'], get_work_id['reward_expense_amount']*get_work_id['fee_ratio'], coin_decimal, add_energy, get_work_id['health_loss'], get_work_id['energy_loss'])
                    if insert_activity:
                        additional_text = " You can claim in: `{}`.".format(seconds_str(get_work_id['duration_in_second']))
                        task_name = "{} {}".format(get_work_id['work_name'], get_work_id['work_emoji'])
                        await inter.response.send_message(f'{EMOJI_INFORMATION} {inter.author.mention} You started a new task - {task_name}! {additional_text}')
                    else:
                        await inter.response.send_message(f"{EMOJI_INFORMATION} {inter.author.mention}, Internal error.")
                    if inter.author.id in self.bot.GAME_INTERACTIVE_ECO:
                        self.bot.GAME_INTERACTIVE_ECO.remove(inter.author.id)
                    await inter.message.delete()
            elif inter.component.custom_id.startswith("economy_{}_item_".format(inter.author.id)):
                # Not to duplicate
                key = inter.component.custom_id + str(int(time.time()))
                try:
                    if self.ttlcache[key] == key:
                        return
                    else:
                        self.ttlcache[key] = key
                except Exception as e:
                    pass
                # Backpack
                name = inter.component.custom_id.replace("economy_{}_item_".format(inter.author.id), "")
                all_item_backpack = {}
                db = database_economy()
                get_user_inventory = await db.economy_get_user_inventory(str(inter.author.id))
                nos_items = sum(each_item['numbers'] for each_item in get_user_inventory if each_item['item_name'] != "Gem")
                if get_user_inventory and nos_items == 0:
                    await inter.response.send_message(f"{EMOJI_RED_NO} {inter.author.mention} You do not have any item in your backpack.")
                    return
                if get_user_inventory and len(get_user_inventory) > 0:
                    for each_item in get_user_inventory:
                        all_item_backpack[str(each_item['item_emoji'])] = each_item['item_id']
            
                get_item_id = await db.economy_get_item_id(all_item_backpack[name])
                # Else, go on and Insert work to DB
                add_energy = 0
                add_energy_health_str = ""
                get_userinfo = await db.economy_get_user(str(inter.author.id), '{}#{}'.format(inter.author.name, inter.author.discriminator))
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
                update_userinfo = await db.economy_item_update_used(str(inter.author.id), all_item_backpack[name], add_energy, add_health)
                using_item = '{} {}'.format(get_item_id['item_name'], get_item_id['item_emoji'])
                if update_userinfo:
                    await inter.response.send_message(f'{EMOJI_INFORMATION} {inter.author.mention} You used `{using_item}`. You gained `{add_energy_health_str}`. {total_energy_health_str}')
                else:
                    await inter.response.send_message(f"{EMOJI_RED_NO} {inter.author.mention} Internal error.")
                if inter.author.id in self.bot.GAME_INTERACTIVE_ECO:
                    self.bot.GAME_INTERACTIVE_ECO.remove(inter.author.id)
                await inter.message.delete()



    @commands.Cog.listener()
    async def on_shard_ready(self, shard_id):
        print(f'Shard {shard_id} connected')


    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.bot_log()
        add_server_info = await store.sql_addinfo_by_server(str(guild.id), guild.name, config.discord.prefixCmd, "WRKZ", True)
        await self.botLogChan.send(f'Bot joins a new guild {guild.name} / {guild.id} / Users: {len(guild.members)}. Total guilds: {len(self.bot.guilds)}.')
        return


    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        await self.bot_log()
        add_server_info = await store.sql_updateinfo_by_server(str(guild.id), "status", "REMOVED")
        await self.botLogChan.send(f'Bot was removed from guild {guild.name} / {guild.id}. Total guilds: {len(self.bot.guilds)}')
        return


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
