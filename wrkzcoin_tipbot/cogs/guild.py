import asyncio

import sys
import time
import traceback
from datetime import datetime
import random

import uuid
from decimal import Decimal
import aiomysql
from aiomysql.cursors import DictCursor
import timeago
import disnake
from disnake.ext import tasks, commands

from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice
from discord_webhook import DiscordWebhook

import store
from Bot import get_token_list, num_format_coin, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_ARROW_RIGHTHOOK, SERVER_BOT, RowButton_close_message, RowButton_row_close_any_message, human_format, text_to_num, truncate, NOTIFICATION_OFF_CMD, DEFAULT_TICKER, seconds_str

from config import config
from cogs.wallet import WalletAPI
import redis_utils
from utils import MenuPage


class Guild(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        redis_utils.openRedis()
        self.botLogChan = None
        self.enable_logchan = True

        # Tasks
        self.monitor_guild_reward_amount.start()
        
        # Raffle
        self.raffle_min_useronline = 10
        self.raffle_1st_winner = 0.5
        self.raffle_2nd_winner = 0.3
        self.raffle_3rd_winner = 0.19
        self.raffle_pot_fee = 0.01 # Total 100%
        
        self.check_raffle_status.start()

        # DB
        self.pool = None


    async def openConnection(self):
        try:
            if self.pool is None:
                self.pool = await aiomysql.create_pool(host=config.mysql.host, port=3306, minsize=8, maxsize=16, 
                                                       user=config.mysql.user, password=config.mysql.password,
                                                       db=config.mysql.db, cursorclass=DictCursor, autocommit=True)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)


    async def get_faucet_claim_user_guild(self, userId: str, guild_id: str, user_server: str="DISCORD"):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `user_balance_mv` 
                              WHERE `from_userid`=%s AND `to_userid`= %s AND `type`=%s AND `user_server`=%s 
                              ORDER BY `date` DESC LIMIT 1 """
                    await cur.execute(sql, ( guild_id, userId, "GUILDFAUCET", user_server))
                    result = await cur.fetchone()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None


    async def user_balance(self, userID: str, coin: str, address: str, coin_family: str, top_block: int, confirmed_depth: int=0, user_server: str = 'DISCORD'):
        # address: TRTL/BCN/XMR = paymentId
        TOKEN_NAME = coin.upper()
        user_server = user_server.upper()
        if top_block is None:
            # If we can not get top block, confirm after 20mn. This is second not number of block
            nos_block = 20*60
        else:
            nos_block = top_block - confirmed_depth
        confirmed_inserted = 30 # 30s for nano
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # balance['adjust'] = float("%.4f" % ( balance['mv_balance']+balance['incoming_tx']-balance['airdropping']-balance['mathtip']-balance['triviatip']-balance['tx_expense']-balance['open_order'] ))
                    # moving tip + / -
                    start = time.time()
                    sql = """ SELECT `balance` AS mv_balance FROM `user_balance_mv_data` WHERE `user_id`=%s AND `token_name` = %s AND `user_server` = %s LIMIT 1 """
                    await cur.execute(sql, (userID, TOKEN_NAME, user_server))
                    result = await cur.fetchone()
                    if result:
                        mv_balance = result['mv_balance']
                    else:
                        mv_balance = 0
                    # pending airdrop
                    sql = """ SELECT SUM(real_amount) AS airdropping FROM `discord_airdrop_tmp` WHERE `from_userid`=%s 
                              AND `token_name` = %s AND `status`=%s """
                    await cur.execute(sql, (userID, TOKEN_NAME, "ONGOING"))
                    result = await cur.fetchone()
                    if result:
                        airdropping = result['airdropping']
                    else:
                        airdropping = 0

                    # pending mathtip
                    sql = """ SELECT SUM(real_amount) AS mathtip FROM `discord_mathtip_tmp` WHERE `from_userid`=%s 
                              AND `token_name` = %s AND `status`=%s """
                    await cur.execute(sql, (userID, TOKEN_NAME, "ONGOING"))
                    result = await cur.fetchone()
                    if result:
                        mathtip = result['mathtip']
                    else:
                        mathtip = 0

                    # pending triviatip
                    sql = """ SELECT SUM(real_amount) AS triviatip FROM `discord_triviatip_tmp` WHERE `from_userid`=%s 
                              AND `token_name` = %s AND `status`=%s """
                    await cur.execute(sql, (userID, TOKEN_NAME, "ONGOING"))
                    result = await cur.fetchone()
                    if result:
                        triviatip = result['triviatip']
                    else:
                        triviatip = 0

                    # Expense (negative)
                    sql = """ SELECT SUM(amount_sell) AS open_order FROM open_order WHERE `coin_sell`=%s AND `userid_sell`=%s 
                              AND `status`=%s
                          """
                    await cur.execute(sql, (TOKEN_NAME, userID, 'OPEN'))
                    result = await cur.fetchone()
                    if result:
                        open_order = result['open_order']
                    else:
                        open_order = 0

                    # guild_raffle_entries fee entry
                    sql = """ SELECT SUM(amount) AS raffle_fee FROM guild_raffle_entries WHERE `coin_name`=%s AND `user_id`=%s  
                              AND `user_server`=%s AND `status`=%s
                          """
                    await cur.execute(sql, (TOKEN_NAME, userID, user_server, 'REGISTERED'))
                    result = await cur.fetchone()
                    raffle_fee = 0.0
                    if result and ('raffle_fee' in result) and result['raffle_fee']:
                        raffle_fee = result['raffle_fee']

                    # Each coin
                    if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        sql = """ SELECT SUM(amount+withdraw_fee) AS tx_expense FROM `cn_external_tx` WHERE `user_id`=%s AND `coin_name` = %s AND `user_server` = %s AND `crediting`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, user_server, "YES" ))
                        result = await cur.fetchone()
                        if result:
                            tx_expense = result['tx_expense']
                        else:
                            tx_expense = 0

                        if top_block is None:
                            sql = """ SELECT SUM(amount) AS incoming_tx FROM `cn_get_transfers` WHERE `payment_id`=%s AND `coin_name` = %s 
                                      AND `amount`>0 AND `time_insert`< %s """
                            await cur.execute(sql, ( address, TOKEN_NAME, int(time.time())-nos_block )) # seconds
                        else:
                            sql = """ SELECT SUM(amount) AS incoming_tx FROM `cn_get_transfers` WHERE `payment_id`=%s AND `coin_name` = %s 
                                      AND `amount`>0 AND `height`< %s """
                            await cur.execute(sql, ( address, TOKEN_NAME, nos_block ))
                        result = await cur.fetchone()
                        if result and result['incoming_tx']:
                            incoming_tx = result['incoming_tx']
                        else:
                            incoming_tx = 0
                    elif coin_family == "BTC":
                        sql = """ SELECT SUM(amount+withdraw_fee) AS tx_expense FROM `doge_external_tx` WHERE `user_id`=%s AND `coin_name`=%s AND `user_server`=%s AND `crediting`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, user_server, "YES" ))
                        result = await cur.fetchone()
                        if result:
                            tx_expense = result['tx_expense']
                        else:
                            tx_expense = 0

                        sql = """ SELECT SUM(amount) AS incoming_tx FROM `doge_get_transfers` WHERE `address`=%s AND `coin_name` = %s AND (`category` = %s or `category` = %s) 
                                  AND `confirmations`>=%s AND `amount`>0 """
                        await cur.execute(sql, (address, TOKEN_NAME, 'receive', 'generate', confirmed_depth))
                        result = await cur.fetchone()
                        if result and result['incoming_tx']:
                            incoming_tx = result['incoming_tx']
                        else:
                            incoming_tx = 0
                    elif coin_family == "NANO":
                        sql = """ SELECT SUM(amount) AS tx_expense FROM `nano_external_tx` WHERE `user_id`=%s AND `coin_name` = %s AND `user_server`=%s AND `crediting`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, user_server, "YES" ))
                        result = await cur.fetchone()
                        if result:
                            tx_expense = result['tx_expense']
                        else:
                            tx_expense = 0

                        sql = """ SELECT SUM(amount) AS incoming_tx FROM `nano_move_deposit` WHERE `user_id`=%s AND `coin_name` = %s 
                                  AND `amount`>0 AND `time_insert`< %s AND `user_server`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, int(time.time())-confirmed_inserted, user_server ))
                        result = await cur.fetchone()
                        if result and result['incoming_tx']:
                            incoming_tx = result['incoming_tx']
                        else:
                            incoming_tx = 0
                    elif coin_family == "CHIA":
                        sql = """ SELECT SUM(amount+withdraw_fee) AS tx_expense FROM `xch_external_tx` WHERE `user_id`=%s AND `coin_name` = %s AND `user_server` = %s AND `crediting`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, user_server, "YES" ))
                        result = await cur.fetchone()
                        if result:
                            tx_expense = result['tx_expense']
                        else:
                            tx_expense = 0

                        if top_block is None:
                            sql = """ SELECT SUM(amount) AS incoming_tx FROM `xch_get_transfers` WHERE `address`=%s AND `coin_name` = %s 
                                      AND `amount`>0 AND `time_insert`< %s """
                            await cur.execute(sql, (address, TOKEN_NAME, nos_block)) # seconds
                        else:
                            sql = """ SELECT SUM(amount) AS incoming_tx FROM `xch_get_transfers` WHERE `address`=%s AND `coin_name` = %s 
                                      AND `amount`>0 AND `height`<%s """
                            await cur.execute(sql, (address, TOKEN_NAME, nos_block))
                        result = await cur.fetchone()
                        if result and result['incoming_tx']:
                            incoming_tx = result['incoming_tx']
                        else:
                            incoming_tx = 0
                    elif coin_family == "ERC-20":
                        # When sending tx out, (negative)
                        sql = """ SELECT SUM(real_amount+real_external_fee) AS tx_expense FROM `erc20_external_tx` 
                                  WHERE `user_id`=%s AND `token_name` = %s AND `crediting`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, "YES" ))
                        result = await cur.fetchone()
                        if result:
                            tx_expense = result['tx_expense']
                        else:
                            tx_expense = 0

                        # in case deposit fee -real_deposit_fee
                        sql = """ SELECT SUM(real_amount-real_deposit_fee) AS incoming_tx FROM `erc20_move_deposit` WHERE `user_id`=%s 
                                  AND `token_name` = %s AND `confirmed_depth`> %s AND `status`=%s """
                        await cur.execute(sql, (userID, TOKEN_NAME, confirmed_depth, "CONFIRMED"))
                        result = await cur.fetchone()
                        if result:
                            incoming_tx = result['incoming_tx']
                        else:
                            incoming_tx = 0
                    elif coin_family == "TRC-20":
                        # When sending tx out, (negative)
                        sql = """ SELECT SUM(real_amount+real_external_fee) AS tx_expense FROM `trc20_external_tx` 
                                  WHERE `user_id`=%s AND `token_name` = %s AND `crediting`=%s AND `sucess`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, "YES", 1 ))
                        result = await cur.fetchone()
                        if result:
                            tx_expense = result['tx_expense']
                        else:
                            tx_expense = 0

                        # in case deposit fee -real_deposit_fee
                        sql = """ SELECT SUM(real_amount-real_deposit_fee) AS incoming_tx FROM `trc20_move_deposit` WHERE `user_id`=%s 
                                  AND `token_name` = %s AND `confirmed_depth`> %s AND `status`=%s """
                        await cur.execute(sql, (userID, TOKEN_NAME, confirmed_depth, "CONFIRMED"))
                        result = await cur.fetchone()
                        if result:
                            incoming_tx = result['incoming_tx']
                        else:
                            incoming_tx = 0

                balance = {}
                balance['adjust'] = 0

                balance['mv_balance'] = float("%.6f" % mv_balance) if mv_balance else 0

                balance['airdropping'] = float("%.6f" % airdropping) if airdropping else 0
                balance['mathtip'] = float("%.6f" % mathtip) if mathtip else 0
                balance['triviatip'] = float("%.6f" % triviatip) if triviatip else 0

                balance['tx_expense'] = float("%.6f" % tx_expense) if tx_expense else 0
                balance['incoming_tx'] = float("%.6f" % incoming_tx) if incoming_tx else 0
                
                balance['open_order'] = float("%.6f" % open_order) if open_order else 0
                balance['raffle_fee'] = float("%.6f" % raffle_fee) if raffle_fee else 0

                balance['adjust'] = float("%.6f" % ( balance['mv_balance']+balance['incoming_tx']-balance['airdropping']-balance['mathtip']-balance['triviatip']-balance['tx_expense']-balance['open_order']-balance['raffle_fee'] ))
                # Negative check
                try:
                    if balance['adjust'] < 0:
                        msg_negative = 'Negative balance detected:\nServer:'+user_server+'\nUser: '+userID+'\nToken: '+TOKEN_NAME+'\nBalance: '+str(balance['adjust'])
                        await logchanbot(msg_negative)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                return balance
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())


    @tasks.loop(seconds=10.0)
    async def check_raffle_status(self):
        time_lap = 10 # seconds
        to_close_fromopen = 300 # second
        while not self.bot.is_closed():
            await asyncio.sleep(time_lap)
            # Try DM user if they are winner, and if they are loser
            get_all_active_raffle = await self.raffle_get_all(SERVER_BOT)
            if get_all_active_raffle and len(get_all_active_raffle) > 0:
                for each_raffle in get_all_active_raffle:
                    # loop each raffle
                    try:
                        if each_raffle['status'] == "OPENED":
                            if each_raffle['ending_ts'] - to_close_fromopen < int(time.time()):
                                # less than 3 participants, cancel
                                list_raffle_id = await self.raffle_get_from_by_id(each_raffle['id'], SERVER_BOT, None)
                                if (list_raffle_id and list_raffle_id['entries'] and len(list_raffle_id['entries']) < 3) or \
                                (list_raffle_id and list_raffle_id['entries'] is None):
                                    # Cancel game
                                    cancelled_status = await self.raffle_cancel_id(each_raffle['id'])
                                    msg_raffle = "Cancelled raffle #{} in guild {}: **Shortage of users**. User entry fee refund!".format(each_raffle['id'], each_raffle['guild_name'])
                                    serverinfo = await store.sql_info_by_server(each_raffle['guild_id'])
                                    if serverinfo['raffle_channel']:
                                        raffle_chan = self.bot.get_channel(int(serverinfo['raffle_channel']))
                                        if raffle_chan:
                                            await raffle_chan.send(msg_raffle)
                                    await logchanbot(msg_raffle)                                
                                else:
                                    # change status from Open to ongoing
                                    update_status = await self.raffle_update_id(each_raffle['id'], 'ONGOING', None, None, None, None, None, None, None, None, None, None)
                                    if update_status:
                                        msg_raffle = "Changed raffle #{} status to **ONGOING** in guild {}/{}! ".format(each_raffle['id'], each_raffle['guild_name'], each_raffle['guild_id'])
                                        msg_raffle += "Raffle will start in **{}**".format(seconds_str(to_close_fromopen))
                                        serverinfo = await store.sql_info_by_server(each_raffle['guild_id'])                                        
                                        if serverinfo['raffle_channel']:
                                            raffle_chan = self.bot.get_channel(int(serverinfo['raffle_channel']))
                                            if raffle_chan:
                                                await raffle_chan.send(msg_raffle)
                                                try:
                                                    # Ping users
                                                    list_ping = []
                                                    for each_user in list_raffle_id['entries']:
                                                        list_ping.append("<@{}>".format(each_user['user_id']))
                                                    await raffle_chan.send(", ".join(list_ping))
                                                except Exception as e:
                                                    traceback.print_exc(file=sys.stdout)
                                                    await logchanbot(traceback.format_exc()) 
                                        await logchanbot(msg_raffle)
                                    else:
                                        await logchanbot(f"Internal error to {msg_raffle}")
                        elif each_raffle['status'] == "ONGOING":
                            COIN_NAME = each_raffle['coin_name']
                            serverinfo = await store.sql_info_by_server(each_raffle['guild_id'])
                            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                            contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
                            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
                            unit_price_usd = 0.0
                            if usd_equivalent_enable == 1:
                                native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                                COIN_NAME_FOR_PRICE = COIN_NAME
                                if native_token_name:
                                    COIN_NAME_FOR_PRICE = native_token_name
                                if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                                    id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                                    per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                                    if per_unit > 0: unit_price_usd = per_unit
                                else:
                                    per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
                                    if per_unit > 0: unit_price_usd = per_unit
                            if each_raffle['ending_ts'] < int(time.time()):
                                # Let's random and update
                                list_raffle_id = await self.raffle_get_from_by_id(each_raffle['id'], SERVER_BOT, None)
                                # This is redundant with above!
                                if list_raffle_id and list_raffle_id['entries'] and len(list_raffle_id['entries']) < 3:
                                    # Cancel game
                                    cancelled_status = await self.raffle_cancel_id(each_raffle['id'])
                                    msg_raffle = "Cancelled raffle #{} in guild {}: shortage of users. User entry fee refund!".format(each_raffle['id'], each_raffle['guild_id'])
                                    if serverinfo['raffle_channel']:
                                        raffle_chan = self.bot.get_channel(int(serverinfo['raffle_channel']))
                                        if raffle_chan:
                                            await raffle_chan.send(msg_raffle)
                                    await logchanbot(msg_raffle)
                                if list_raffle_id and list_raffle_id['entries'] and len(list_raffle_id['entries']) >= 3:
                                    entries_id = []
                                    user_entries_id = {}
                                    user_entries_name = {}
                                    list_winners = []
                                    won_amounts = []
                                    total_reward = 0.0
                                    list_losers = []
                                    for each_entry in list_raffle_id['entries']:
                                        entries_id.append(each_entry['entry_id'])
                                        user_entries_id[each_entry['entry_id']] = each_entry['user_id']
                                        user_entries_name[each_entry['entry_id']] = each_entry['user_name']
                                        total_reward += float(each_entry['amount'])
                                        list_losers.append(each_entry['user_id'])
                                    winner_1 = random.choice(entries_id)
                                    winner_1_user = user_entries_id[winner_1]
                                    winner_1_name = user_entries_name[winner_1]
                                    entries_id.remove(winner_1)
                                    list_winners.append(winner_1_user)
                                    won_amounts.append(float(total_reward) * self.raffle_1st_winner)
                                    list_losers.remove(user_entries_id[winner_1])

                                    winner_2 = random.choice(entries_id)
                                    winner_2_user = user_entries_id[winner_2]
                                    winner_2_name = user_entries_name[winner_2]
                                    entries_id.remove(winner_2)
                                    list_winners.append(winner_2_user)
                                    won_amounts.append(float(total_reward) * self.raffle_2nd_winner)
                                    list_losers.remove(user_entries_id[winner_2])

                                    winner_3 = random.choice(entries_id)
                                    winner_3_user = user_entries_id[winner_3]
                                    winner_3_name = user_entries_name[winner_3]
                                    entries_id.remove(winner_3)
                                    list_winners.append(winner_3_user)
                                    won_amounts.append(float(total_reward) * self.raffle_3rd_winner)
                                    list_losers.remove(user_entries_id[winner_3])
                                    won_amounts.append(float(total_reward) * self.raffle_pot_fee)
                                    # channel_id = RAFFLE
                                    update_status = await self.raffle_update_id(each_raffle['id'], 'COMPLETED', COIN_NAME, list_winners, won_amounts, list_losers, float(each_raffle['amount']), coin_decimal, unit_price_usd, contract, each_raffle['guild_id'], "RAFFLE")
                                    embed = disnake.Embed(title = "RAFFLE #{} / {}".format(each_raffle['id'], each_raffle['guild_name']), timestamp=datetime.fromtimestamp(int(time.time())))
                                    embed.add_field(name="ENTRY FEE", value="{} {}".format(num_format_coin(each_raffle['amount'], COIN_NAME, coin_decimal, False), COIN_NAME), inline=True)
                                    embed.add_field(name="1st WINNER: {}".format(winner_1_name), value="{} {}".format(num_format_coin(won_amounts[0], COIN_NAME, coin_decimal, False), COIN_NAME), inline=False)
                                    embed.add_field(name="2nd WINNER: {}".format(winner_2_name), value="{} {}".format(num_format_coin(won_amounts[1], COIN_NAME, coin_decimal, False), COIN_NAME), inline=False)
                                    embed.add_field(name="3rd WINNER: {}".format(winner_3_name), value="{} {}".format(num_format_coin(won_amounts[2], COIN_NAME, coin_decimal, False), COIN_NAME), inline=False)
                                    embed.set_footer(text="Raffle for {} by {}".format(each_raffle['guild_name'], each_raffle['created_username']))
                                    
                                    msg_raffle = "**Completed raffle #{} in guild {}! Winner entries: #1: {}, #2: {}, #3: {}**\n".format(each_raffle['id'], each_raffle['guild_name'], winner_1_name, winner_2_name, winner_3_name)
                                    msg_raffle += "```Three winners get reward of #1: {}{}, #2: {}{}, #3: {}{}```".format(num_format_coin(won_amounts[0], COIN_NAME, coin_decimal, False), COIN_NAME, num_format_coin(won_amounts[1], COIN_NAME, coin_decimal, False), COIN_NAME, num_format_coin(won_amounts[2], COIN_NAME, coin_decimal, False), COIN_NAME)
                                    if serverinfo['raffle_channel']:
                                        raffle_chan = self.bot.get_channel(int(serverinfo['raffle_channel']))
                                        if raffle_chan:
                                            await raffle_chan.send(embed=embed)
                                    await logchanbot(msg_raffle)
                                    for each_entry in list_winners:
                                        try:
                                            # Find user
                                            user_found = self.bot.get_user(int(each_entry))
                                            if user_found:
                                                try:
                                                    await user_found.send(embed=embed)
                                                except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                                    traceback.print_exc(file=sys.stdout)
                                                    await logchanbot(f"[Discord]/Raffle can not message to {user_found.name}#{user_found.discriminator} about winning raffle.")
                                            else:
                                                await logchanbot('[Discord]/Raffle Can not find entry id: {}'.format(each_entry))
                                        except Exception as e:
                                            traceback.print_exc(file=sys.stdout)
                                            await logchanbot(traceback.format_exc())
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
            await asyncio.sleep(time_lap)
            break

    async def raffle_update_id(self, raffle_id: int, status: str, coin: str=None, list_winner=None, list_amounts=None, list_entries=None, amount_each: float=None, coin_decimal: int=None, unit_price_usd: float=None, contract: str=None, guild_id: str=None, channel_id: str=None):
        # list_winner = 3
        # list_amounts = 4
        user_server = SERVER_BOT
        currentTs = int(time.time())
        try:
            await self.openConnection()	
            async with self.pool.acquire() as conn:	
                async with conn.cursor() as cur:
                    if list_winner is None and list_amounts is None:
                        sql = """ UPDATE guild_raffle SET `status`=%s WHERE `id`=%s """	
                        await cur.execute(sql, (status.upper(), raffle_id))
                        await conn.commit()
                        return True
                    else:
                        values_list = []
                        if status.upper() == "COMPLETED" and list_winner and list_amounts:
                            sql = """ UPDATE guild_raffle SET `status`=%s, `winner_userid_1st`=%s,
                                      `winner_1st_amount`=%s, `winner_userid_2nd`=%s,
                                      `winner_2nd_amount`=%s, `winner_userid_3rd`=%s,
                                      `winner_3rd_amount`=%s, `raffle_fund_pot`=%s WHERE `id`=%s """
                            await cur.execute(sql, (status.upper(), list_winner[0], list_amounts[0], 
                                                    list_winner[1], list_amounts[1], list_winner[2],
                                                    list_amounts[2], list_amounts[3], raffle_id))

                            # Update # guild_raffle_entries
                            update_status = [('WINNER', list_amounts[0], raffle_id, list_winner[0]), ('WINNER', list_amounts[1], raffle_id, list_winner[1]), ('WINNER', list_amounts[2], raffle_id, list_winner[2])]
                            for each_loser in list_entries:
                                update_status.append(( 'LOST', amount_each, raffle_id, each_loser ))
                            sql = """ UPDATE guild_raffle_entries SET `status`=%s, `won_amount`=%s WHERE `raffle_id`=%s 
                                      AND `user_id`=%s """
                            await cur.executemany(sql, update_status)
                            await conn.commit()

                            # Move from players to guild, then from guild to winner
                            for item in list_entries+[list_winner[0], list_winner[1], list_winner[2]]:
                                values_list.append(( coin.upper(), contract, item, guild_id, guild_id, channel_id, amount_each, coin_decimal, "RAFFLE", currentTs, user_server, float(amount_each)*float(unit_price_usd), item, coin.upper(), user_server, -amount_each, currentTs, guild_id, coin.upper(), user_server, amount_each, currentTs, ))
                            # reward to winners
                            # 1st
                            values_list.append(( coin.upper(), contract, guild_id, list_winner[0], guild_id, channel_id, list_amounts[0], coin_decimal, "RAFFLE", currentTs, user_server, unit_price_usd*list_amounts[0], guild_id, coin.upper(), user_server, -list_amounts[0], currentTs, list_winner[0], coin.upper(), user_server, list_amounts[0], currentTs ))
                            values_list.append(( coin.upper(), contract, guild_id, list_winner[1], guild_id, channel_id, list_amounts[1], coin_decimal, "RAFFLE", currentTs, user_server, unit_price_usd*list_amounts[1], guild_id, coin.upper(), user_server, -list_amounts[1], currentTs, list_winner[1], coin.upper(), user_server, list_amounts[1], currentTs ))
                            values_list.append(( coin.upper(), contract, guild_id, list_winner[2], guild_id, channel_id, list_amounts[2], coin_decimal, "RAFFLE", currentTs, user_server, unit_price_usd*list_amounts[2], guild_id, coin.upper(), user_server, -list_amounts[2], currentTs, list_winner[2], coin.upper(), user_server, list_amounts[2], currentTs ))
                            # raffle pot fee 0.01
                            values_list.append(( coin.upper(), contract, guild_id, "RAFFLE", guild_id, channel_id, list_amounts[3], coin_decimal, "RAFFLE", currentTs, user_server, unit_price_usd*list_amounts[3], guild_id, coin.upper(), user_server, -list_amounts[3], currentTs, "RAFFLE", coin.upper(), user_server, list_amounts[3], currentTs ))
                            sql = """ INSERT INTO user_balance_mv (`token_name`, `contract`, `from_userid`, `to_userid`, `guild_id`, `channel_id`, `real_amount`, `token_decimal`, `type`, `date`, `user_server`, `real_amount_usd`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s, %s, %s, %s, %s);
                                    
                                      INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                                      VALUES (%s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s) ON DUPLICATE KEY 
                                      UPDATE 
                                      `balance`=`balance`+VALUES(`balance`), 
                                      `update_date`=VALUES(`update_date`);

                                      INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                                      VALUES (%s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s) ON DUPLICATE KEY 
                                      UPDATE 
                                      `balance`=`balance`+VALUES(`balance`), 
                                      `update_date`=VALUES(`update_date`);
                            """
                            await cur.executemany(sql, values_list)
                            await conn.commit()
                            return True	
        except Exception as e:	
            await logchanbot(traceback.format_exc())	
        return False

    async def raffle_cancel_id(self, raffle_id: int):
        try:	
            await self.openConnection()	
            async with self.pool.acquire() as conn:	
                async with conn.cursor() as cur:
                    sql = """ UPDATE guild_raffle SET `status`=%s WHERE `id`=%s AND `status` IN ('ONGOING', 'OPENED') LIMIT 1 """	
                    await cur.execute(sql, ('CANCELLED', raffle_id))
                    await conn.commit()	
                    sql = """ UPDATE guild_raffle_entries SET `status`=%s WHERE `raffle_id`=%s """	
                    await cur.execute(sql, ('CANCELLED', raffle_id))
                    await conn.commit()	
                    return True	
        except Exception as e:	
            await logchanbot(traceback.format_exc())	
        return False

    async def raffle_get_all(self, user_server: str='DISCORD'):
        global pool
        user_server = user_server.upper()
        try:
            await self.openConnection()	
            async with self.pool.acquire() as conn:	
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM guild_raffle 
                              WHERE `user_server`=%s AND `status` IN ('OPENED', 'ONGOING') """
                    await cur.execute(sql, (user_server))
                    result = await cur.fetchall()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())	
        return None

    async def raffle_get_from_by_id(self, idx: str, user_server: str='DISCORD', user_check: str=None):
        user_server = user_server.upper()
        try:	
            await self.openConnection()	
            async with self.pool.acquire() as conn:	
                async with conn.cursor() as cur:	
                    sql = """ SELECT * FROM guild_raffle 
                              WHERE `id`=%s AND `user_server`=%s LIMIT 1 """
                    await cur.execute(sql, (idx, user_server))
                    result = await cur.fetchone()
                    if result:
                        sql = """ SELECT * FROM guild_raffle_entries 
                                  WHERE `raffle_id`=%s AND `user_server`=%s ORDER BY `entry_id` DESC """
                        await cur.execute(sql, (idx, user_server))
                        result_list = await cur.fetchall()
                        if result_list and len(result_list) > 0:
                            result['entries'] = result_list
                            if user_check:
                                sql = """ SELECT * FROM guild_raffle_entries 
                                          WHERE `raffle_id`=%s AND `user_server`=%s AND `user_id`=%s LIMIT 1 """
                                await cur.execute(sql, (idx, user_server, user_check))
                                result_check = await cur.fetchone()
                                if result_check:
                                    result['user_joined'] = True
                                else:
                                    result['user_joined'] = False
                        else:
                            result['entries'] = None
                            result['user_joined'] = False
                    return result
        except Exception as e:	
            await logchanbot(traceback.format_exc())	
        return None

    async def raffle_get_from_guild(self, guild: str, last_play: bool=False, user_server: str='DISCORD'):
        user_server = user_server.upper()
        try:
            await self.openConnection()	
            async with self.pool.acquire() as conn:	
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM guild_raffle 
                              WHERE `guild_id`=%s AND `user_server`=%s ORDER BY `id` DESC LIMIT 1 """
                    if last_play: sql += "OFFSET 1"
                    await cur.execute(sql, (guild, user_server))
                    result = await cur.fetchone()
                    if result: return result
        except Exception as e:	
            await logchanbot(traceback.format_exc())	
        return None

    async def raffle_insert_new_entry(self, raffle_id: int, guild_id: str, amount: float, decimal: int, coin: str, user_id: str, user_name: str, user_server: str='DISCORD'):
        COIN_NAME = coin.upper()
        user_server = user_server.upper()  
        try:	
            await self.openConnection()	
            async with self.pool.acquire() as conn:	
                async with conn.cursor() as cur:	
                    sql = """ INSERT INTO guild_raffle_entries (`raffle_id`, `guild_id`, `amount`, `decimal`, 
                              `coin_name`, `user_id`, `user_name`, `entry_ts`, `user_server`) 	
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """	
                    await cur.execute(sql, (raffle_id, guild_id, amount, decimal, COIN_NAME, user_id,
                                            user_name, int(time.time()), user_server,))
                    await conn.commit()	
                    return True	
        except Exception as e:	
            await logchanbot(traceback.format_exc())	
        return False

    async def raffle_insert_new(self, guild_id: str, guild_name: str, amount: float, decimal: int, coin: str, created_userid: str, created_username: str, created_ts: int, ending_ts: str, user_server: str='DISCORD'):
        COIN_NAME = coin.upper()
        user_server = user_server.upper()  
        try:	
            await self.openConnection()	
            async with self.pool.acquire() as conn:	
                async with conn.cursor() as cur:	
                    sql = """ INSERT INTO guild_raffle (`guild_id`, `guild_name`, `amount`, `decimal`, 
                              `coin_name`, `created_userid`, `created_username`, `created_ts`, `ending_ts`, `user_server`) 	
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """	
                    await cur.execute(sql, (guild_id, guild_name, amount, decimal, COIN_NAME, created_userid,
                                            created_username, created_ts, ending_ts, user_server,))
                    await conn.commit()	
                    return True	
        except Exception as e:	
            await logchanbot(traceback.format_exc())	
        return False

    async def raffle_get_from_guild(self, guild: str, last_play: bool=False, user_server: str='DISCORD'):
        user_server = user_server.upper()
        try:
            await self.openConnection()	
            async with self.pool.acquire() as conn:	
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM guild_raffle 
                              WHERE `guild_id`=%s AND `user_server`=%s ORDER BY `id` DESC LIMIT 1 """
                    if last_play: sql += "OFFSET 1"
                    await cur.execute(sql, (guild, user_server))
                    result = await cur.fetchone()
                    if result: return result
        except Exception as e:	
            await logchanbot(traceback.format_exc())	
        return None

    # Check if guild has at least 10x amount of reward or disable
    @tasks.loop(seconds=30.0)
    async def monitor_guild_reward_amount(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(3.0)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `discord_server` WHERE `vote_reward_amount`>0 """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each_guild in result:
                            # Check guild's balance
                            COIN_NAME = each_guild['vote_reward_coin']
                            net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
                            type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
                            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                            contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
                            token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
                            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
                            
                            Guild_WalletAPI = WalletAPI(self.bot)
                            get_deposit = await Guild_WalletAPI.sql_get_userwallet(each_guild['serverid'], COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
                            if get_deposit is None:
                                get_deposit = await Guild_WalletAPI.sql_register_user(each_guild['serverid'], COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 1)

                            wallet_address = get_deposit['balance_wallet_address']
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

                            userdata_balance = await self.user_balance(each_guild['serverid'], COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                            actual_balance = float(userdata_balance['adjust'])
                            if actual_balance < 10*float(each_guild['vote_reward_amount']):
                                amount = 10*float(each_guild['vote_reward_amount'])
                                # Disable it
                                # Process, only guild owner can process
                                update_reward = await self.update_reward(each_guild['serverid'], actual_balance, COIN_NAME, True, None)
                                if update_reward > 0:
                                    try:
                                        guild_found = self.bot.get_guild(int(each_guild['serverid']))
                                        user_found = self.bot.get_user(guild_found.owner.id)
                                        if user_found is not None:
                                            await user_found.send(f"Currently, your guild's balance of {COIN_NAME} is lower than 10x reward: {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}. Vote reward is disable.")
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                    await self.vote_logchan(f'[{SERVER_BOT}] Disable vote reward for {guild_found.name} / {guild_found.id}. Guild\'s balance below 10x: {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}.')
        except Exception as e:
            traceback.print_exc(file=sys.stdout)



    async def vote_logchan(self, content: str):
        try:
            webhook = DiscordWebhook(url=config.topgg.topgg_votehook, content=content)
            webhook.execute()
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    async def guild_find_by_key(self, guild_id: str, secret: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
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
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE discord_server SET `"""+secret+"""`=%s WHERE `serverid`=%s LIMIT 1 """
                    await cur.execute(sql, (key, guild_id))
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None

    async def update_reward(self, guild_id: str, amount: float, coin_name: str, disable: bool=False, channel: str=None):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if disable == True:
                        sql = """ UPDATE discord_server SET `vote_reward_amount`=%s, `vote_reward_coin`=%s, `vote_reward_channel`=%s WHERE `serverid`=%s LIMIT 1 """
                        await cur.execute(sql, ( None, None, guild_id, None ))
                        await conn.commit()
                        return cur.rowcount
                    else:
                        sql = """ UPDATE discord_server SET `vote_reward_amount`=%s, `vote_reward_coin`=%s, `vote_reward_channel`=%s WHERE `serverid`=%s LIMIT 1 """
                        await cur.execute(sql, ( amount, coin_name.upper(), channel, guild_id  ))
                        await conn.commit()
                        return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return 0

    async def update_faucet(self, guild_id: str, amount: float, coin_name: str, duration: int=43200, disable: bool=False, channel: str=None):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if disable == True:
                        sql = """ UPDATE discord_server SET `faucet_amount`=%s, `faucet_coin`=%s, `faucet_channel`=%s, `faucet_duration`=%s WHERE `serverid`=%s LIMIT 1 """
                        await cur.execute(sql, ( None, None, None, None, guild_id ))
                        await conn.commit()
                        return cur.rowcount
                    else:
                        sql = """ UPDATE discord_server SET `faucet_amount`=%s, `faucet_coin`=%s, `faucet_channel`=%s, `faucet_duration`=%s WHERE `serverid`=%s LIMIT 1 """
                        await cur.execute(sql, ( amount, coin_name.upper(), channel, duration, guild_id  ))
                        await conn.commit()
                        return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return 0

    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.slash_command(description="Various guild's commands.")
    async def guild(self, ctx):
        pass


    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @guild.sub_command(
        usage="guild createraffle <amount> <coin> <duration>", 
        options=[
            Option('amount', 'amount', OptionType.number, required=True),
            Option('coin', 'coin', OptionType.string, required=True),
            Option('duration', 'duration', OptionType.string, required=True)
        ],
        description="Create a raffle."
    )
    async def createraffle(
        self, 
        ctx, 
        amount: float, 
        coin: str, 
        duration: str
    ):
        await self.bot_log()
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))

        if serverinfo['raffle_channel']:
            raffle_chan = self.bot.get_channel(int(serverinfo['raffle_channel']))
            if not raffle_chan:
                await ctx.response.send_message(f"{EMOJI_RED_NO} {ctx.author.mention} Can not find raffle channel or invalid.")
                return
        else:
            await ctx.response.send_message(f"{EMOJI_RED_NO} {ctx.author.mention} There is no raffle channel yet.")
            return

        try:
            amount = Decimal(amount)
        except ValueError:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid amount {amount}!"
            ctx.response.send_message(msg)
            return

        COIN_NAME = coin.upper()
        enable_raffle = getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_raffle")

        net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
        contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
        token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
        MinTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_tip")
        MaxTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_max_tip")
        usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")

        if not hasattr(self.bot.coin_list, COIN_NAME):
            await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
            return

        if enable_raffle != 1:
            await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** not available for raffle.')
            return

        duration_accepted = ["1H", "2H", "3H", "4H", "5H", "6H", "12H", "1D", "2D", "3D", "4D", "5D", "6D", "7D"]
        duration_accepted_list = ", ".join(duration_accepted)
        duration = duration.upper()
        if duration not in duration_accepted:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention} **INVALID DATE**! Please use {duration_accepted_list}"
            await ctx.response.send_message(msg)
            return

        try:
            num_online = len([member for member in ctx.guild.members if member.bot == False and member.status != disnake.Status.offline])
            if num_online < self.raffle_min_useronline:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, your guild needs to have at least: {str(self.raffle_min_useronline)} users online!"
                await ctx.response.send_message(msg)
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        if amount < MinTip or amount > MaxTip:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} amount has to be between `{num_format_coin(MinTip, COIN_NAME, coin_decimal, False)} {token_display}` and `{num_format_coin(MaxTip, COIN_NAME, coin_decimal, False)} {token_display}`.'
            await ctx.response.send_message(msg)
            return

        get_raffle = await self.raffle_get_from_guild(str(ctx.guild.id), False, SERVER_BOT)
        if get_raffle and get_raffle['status'] not in ["COMPLETED", "CANCELLED"]:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, there is still **ONGOING** or **OPENED** raffle!"
            await ctx.response.send_message(msg)
            return
        else:
            # Let's insert
            duration_in_s = 0
            try:
                if "D" in duration and "H" in duration:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, **INVALID DATE**! Please use {duration_accepted_list}."
                    await ctx.response.send_message(msg)
                    return
                elif "D" in duration:
                    duration_in_s = int(duration.replace("D", ""))*3600*24 # convert to second
                elif "H" in duration:
                    duration_in_s = int(duration.replace("H", ""))*3600 # convert to second
            except ValueError:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention} invalid duration!"
                await ctx.response.send_message(msg)
                return

            if duration_in_s <= 0:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention} invalid duration!"
                await ctx.response.send_message(msg)
                return
            try:
                start_ts = int(time.time())
                message_raffle = "{}#{} created a raffle for **{} {}** in guild `{}`. Raffle in **{}**.".format(ctx.author.name, ctx.author.discriminator, num_format_coin(amount, COIN_NAME, coin_decimal, False), COIN_NAME, ctx.guild.name, duration)
                try:
                    await ctx.response.send_message(message_raffle)
                    insert_raffle = await self.raffle_insert_new(str(ctx.guild.id), ctx.guild.name, amount, coin_decimal, COIN_NAME, str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator), start_ts, start_ts+duration_in_s, SERVER_BOT)
                    await logchanbot(message_raffle)
                    return
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(f"Failed to message raffle creation in guild {ctx.guild.name} / {ctx.guild.id} ")
            except Exception as e:
                traceback.print_exc(file=sys.stdout)


    @guild.sub_command(
        usage="guild raffle [info|join|check]", 
        options=[
            Option('subc', 'subc', OptionType.string, required=False, choices=[
                OptionChoice("Get Information", "INFO"),
                OptionChoice("Join opened raffle", "JOIN"),
                OptionChoice("Check raffle's status", "CHECK")
            ]
            )
        ],
        description="Raffle commands."
    )
    async def raffle(
        self, 
        ctx, 
        subc: str=None
    ):
        await self.bot_log()
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))

        if serverinfo['raffle_channel']:
            raffle_chan = self.bot.get_channel(int(serverinfo['raffle_channel']))
            if not raffle_chan:
                await ctx.response.send_message(f"{EMOJI_RED_NO} {ctx.author.mention} Can not find raffle channel or invalid.")
                return
        else:
            await ctx.response.send_message(f"{EMOJI_RED_NO} {ctx.author.mention} There is no raffle channel yet.")
            return

        if subc is None:
            subc = "INFO"
        subc = subc.upper()

        get_raffle = await self.raffle_get_from_guild(str(ctx.guild.id), False, SERVER_BOT)
        list_raffle_id = None
        if get_raffle:
            list_raffle_id = await self.raffle_get_from_by_id(get_raffle['id'], SERVER_BOT, str(ctx.author.id))
        subc_list = ["INFO", "LAST", "JOIN", "CHECK"]
        if subc not in subc_list:
            await ctx.response.send_message(f"{EMOJI_RED_NO} {ctx.author.mention} **INVALID SUB COMMAND**!")
            return
        else:
            if get_raffle is None:
                await ctx.response.send_message(f"{EMOJI_RED_NO} {ctx.author.mention}, there is no information of current raffle yet!")
                return
        try:
            if ctx.author.bot == True:
                await ctx.response.send_message(f"{EMOJI_RED_NO} {ctx.author.mention}, Bot is not allowed!")
                return
        except Exception as e:
            pass

        COIN_NAME = get_raffle['coin_name']
        coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
        if subc == "INFO":
            try:
                ending_ts = datetime.utcfromtimestamp(int(get_raffle['ending_ts']))
                embed = disnake.Embed(title = "RAFFLE #{} / {}".format(get_raffle['id'], ctx.guild.name), timestamp=ending_ts)
                embed.add_field(name="ENTRY FEE", value="{} {}".format(num_format_coin(get_raffle['amount'], COIN_NAME, coin_decimal, False), COIN_NAME), inline=True)
                create_ts = datetime.utcfromtimestamp(int(get_raffle['created_ts'])).strftime("%Y-%m-%d %H:%M:%S")
                create_ts_ago = str(timeago.format(create_ts, datetime.fromtimestamp(int(time.time()))))
                embed.add_field(name="CREATED", value=create_ts_ago, inline=True)
                if list_raffle_id and list_raffle_id['entries']:
                    embed.add_field(name="PARTICIPANTS", value=len(list_raffle_id['entries']), inline=True)
                    if 0 < len(list_raffle_id['entries']) < 20:
                        list_ping = []
                        for each_user in list_raffle_id['entries']:
                            list_ping.append(each_user['user_name'])
                        embed.add_field(name="PARTICIPANT LIST", value=", ".join(list_ping), inline=False)
                    embed.add_field(name="RAFFLE JAR", value=num_format_coin(len(list_raffle_id['entries'])*float(get_raffle['amount']), COIN_NAME, coin_decimal, False)+" "+COIN_NAME, inline=True)
                else:
                    embed.add_field(name="PARTICIPANTS", value="0", inline=True)
                embed.add_field(name="STATUS", value=get_raffle['status'], inline=True)
                if get_raffle['status'] in ["OPENED", "ONGOING"]:
                    if int(get_raffle['ending_ts'])-int(time.time()) < 0:
                        embed.add_field(name="WHEN", value="(ON QUEUE UPDATING)", inline=False)
                    else:
                        def seconds_str_days(time: float):
                            day = time // (24 * 3600)
                            time = time % (24 * 3600)
                            hour = time // 3600
                            time %= 3600
                            minutes = time // 60
                            time %= 60
                            seconds = time
                            return "{:02d} day(s) {:02d}:{:02d}:{:02d}".format(day, hour, minutes, seconds)
                        embed.add_field(name="WHEN", value=seconds_str_days(int(get_raffle['ending_ts'])-int(time.time())), inline=False)
                embed.set_footer(text="Raffle for {} by {}".format(ctx.guild.name, get_raffle['created_username']))
                await ctx.response.send_message(embed=embed)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        elif subc == "JOIN":
            if get_raffle is None:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, there is no information of current raffle yet for this guild {ctx.guild.name}!"
                await ctx.response.send_message(msg)
                return
            else:
                # Check if already in:
                # If not in, add to DB
                # If current is not opened
                try:
                    if get_raffle['status'] != "OPENED":
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, there is no **OPENED** game raffle on this guild {ctx.guild.name}!"
                        await ctx.response.send_message(msg)
                        return
                    else:
                        raffle_id = get_raffle['id']
                        if list_raffle_id and list_raffle_id['user_joined']:
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you already join this raffle #**{str(raffle_id)}** in guild {ctx.guild.name}!"
                            await ctx.response.send_message(msg)
                            return
                        else:
                            COIN_NAME = get_raffle['coin_name']
                            net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
                            type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")

                            User_WalletAPI = WalletAPI(self.bot)
                            user_entry = await User_WalletAPI.sql_get_userwallet(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
                            if user_entry is None:
                                user_entry = await User_WalletAPI.sql_register_user(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)

                            wallet_address = user_entry['balance_wallet_address']
                            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                wallet_address = user_entry['paymentid']

                            height = None
                            try:
                                if type_coin in ["ERC-20", "TRC-20"]:
                                    height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
                                else:
                                    height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)

                            userdata_balance = await self.user_balance(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                            actual_balance = float(userdata_balance['adjust'])

                            if actual_balance < get_raffle['amount']:
                                fee_str = num_format_coin(get_raffle['amount'], COIN_NAME, get_raffle['decimal'], False) + " " + COIN_NAME
                                having_str = num_format_coin(actual_balance, COIN_NAME, get_raffle['decimal'], False) + " " + COIN_NAME
                                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to join raffle entry. Fee: {fee_str}, having: {having_str}."
                                await ctx.response.send_message(msg)
                                return
                            # Let's add
                            try:
                                ## add QUEUE:
                                if ctx.author.id not in self.bot.GAME_RAFFLE_QUEUE:
                                    self.bot.GAME_RAFFLE_QUEUE.append(ctx.author.id)
                                else:
                                    msg = f"{ctx.author.mention} You already on queue of joinining."
                                    await ctx.response.send_message(msg)
                                    return
                                insert_entry = await self.raffle_insert_new_entry(get_raffle['id'], str(ctx.guild.id), get_raffle['amount'], get_raffle['decimal'], get_raffle['coin_name'], str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator), SERVER_BOT)
                                note_entry = num_format_coin(get_raffle['amount'], get_raffle['coin_name'], get_raffle['decimal'], False) + " " + get_raffle['coin_name'] + " is deducted from your balance."
                                msg = f'{ctx.author.mention}, successfully registered your Entry for raffle #**{raffle_id}** in {ctx.guild.name}! {note_entry}'
                                await ctx.response.send_message(msg)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            ## remove QUEUE: reply
                            if ctx.author.id in self.bot.GAME_RAFFLE_QUEUE:
                                self.bot.GAME_RAFFLE_QUEUE.remove(ctx.author.id)
                            return
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
        elif subc == "CHECK":
            if get_raffle is None:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, there is no information of current raffle yet!'
                await ctx.response.send_message(msg)
                return
            else:
                # If current is not opened
                try:
                    raffle_id = get_raffle['id']
                    if get_raffle['status'] == "OPENED":
                        msg = f'{ctx.author.mention}, current raffle #{raffle_id} for guild {ctx.guild.name} is **OPENED**!'
                        await ctx.response.send_message(msg)
                        return
                    elif get_raffle['status'] == "ONGOING":
                        msg = f'{ctx.author.mention}, current raffle #{raffle_id} for guild {ctx.guild.name} is **ONGOING**!'
                        await ctx.response.send_message(msg)
                        return
                    elif get_raffle['status'] == "COMPLETED":
                        msg = f'{ctx.author.mention}, current raffle #{raffle_id} for guild {ctx.guild.name} is **COMPLETED**!'
                        await ctx.response.send_message(msg)
                        return
                    elif get_raffle['status'] == "CANCELLED":
                        msg = f'{ctx.author.mention}, current raffle #{raffle_id} for guild {ctx.guild.name} is **CANCELLED**!'
                        await ctx.response.send_message(msg)
                        return
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
        elif subc == "LAST":
            if get_raffle is None:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, there is no information of current raffle yet!'
                await ctx.response.send_message(msg)
                return


    @guild.sub_command(
        usage="guild balance", 
        description="Show guild's balance"
    )
    async def balance(
        self,
        ctx
    ):
        has_none_balance = True
        total_all_balance_usd = 0.0
        mytokens = await store.get_coin_settings(coin_type=None)
        if type(ctx) != disnake.ApplicationCommandInteraction:
            tmp_msg = await ctx.reply("Loading...")
        coin_balance_list = {}
        coin_balance = {}
        coin_balance_usd = {}
        coin_balance_equivalent_usd = {}
        for each_token in mytokens:
            COIN_NAME = each_token['coin_name']
            type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
            net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")

            Guild_WalletAPI = WalletAPI(self.bot)
            get_deposit = await Guild_WalletAPI.sql_get_userwallet(str(ctx.guild.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
            if get_deposit is None:
                get_deposit = await Guild_WalletAPI.sql_register_user(str(ctx.guild.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 1)
            wallet_address = get_deposit['balance_wallet_address']
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
            userdata_balance = await self.user_balance(str(ctx.guild.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
            total_balance = userdata_balance['adjust']
            if total_balance > 0:
                has_none_balance = False
                coin_balance_list[COIN_NAME] = "{} {}".format(num_format_coin(total_balance, COIN_NAME, coin_decimal, False), token_display)
                coin_balance[COIN_NAME] = total_balance
                usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
                coin_balance_usd[COIN_NAME] = 0.0
                coin_balance_equivalent_usd[COIN_NAME] = ""
                if usd_equivalent_enable == 1:
                    native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                    COIN_NAME_FOR_PRICE = COIN_NAME
                    if native_token_name:
                        COIN_NAME_FOR_PRICE = native_token_name
                    per_unit = None
                    if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                        id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                        per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                    else:
                        per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
                    if per_unit and per_unit > 0:
                        coin_balance_usd[COIN_NAME] = float(Decimal(total_balance) * Decimal(per_unit))
                        total_all_balance_usd += coin_balance_usd[COIN_NAME]
                        if coin_balance_usd[COIN_NAME] >= 0.01:
                            coin_balance_equivalent_usd[COIN_NAME] = " ~ {:,.2f}$".format(coin_balance_usd[COIN_NAME])
                        elif coin_balance_usd[COIN_NAME] >= 0.0001:
                            coin_balance_equivalent_usd[COIN_NAME] = " ~ {:,.4f}$".format(coin_balance_usd[COIN_NAME])
                            

        if has_none_balance == True:
            msg = f'{ctx.author.mention}, this guild does not have any balance.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        else:
            ## add page
            all_pages = []
            num_coins = 0
            per_page = 8
            
            if total_all_balance_usd >= 0.01:
                total_all_balance_usd = "Having ~ {:,.2f}$".format(total_all_balance_usd)
            elif total_all_balance_usd >= 0.0001:
                total_all_balance_usd = "Having ~ {:,.4f}$".format(total_all_balance_usd)
            else:
                total_all_balance_usd = "Thank you for using TipBot!"
                
            for k, v in coin_balance_list.items():
                if num_coins == 0 or num_coins % per_page == 0:
                    page = disnake.Embed(title=f'[ GUILD **{ctx.guild.name.upper()}** BALANCE LIST ]',
                                         description=f"`{total_all_balance_usd}`",
                                         color=disnake.Color.red(),
                                         timestamp=datetime.fromtimestamp(int(time.time())), )
                    page.set_thumbnail(url=ctx.author.display_avatar)
                    page.set_footer(text="Use the reactions to flip pages.")
                page.add_field(name="{}{}".format(k, coin_balance_equivalent_usd[k]), value="```{}```".format(v), inline=True)
                num_coins += 1
                if num_coins > 0 and num_coins % per_page == 0:
                    all_pages.append(page)
                    if num_coins < len(coin_balance_list):
                        page = disnake.Embed(title=f'[ GUILD **{ctx.guild.name.upper()}** BALANCE LIST ]',
                                             description=f"`{total_all_balance_usd}`",
                                             color=disnake.Color.red(),
                                             timestamp=datetime.fromtimestamp(int(time.time())), )
                        page.set_thumbnail(url=ctx.author.display_avatar)
                        page.set_footer(text="Use the reactions to flip pages.")
                    else:
                        all_pages.append(page)
                        break
                elif num_coins == len(coin_balance_list):
                    all_pages.append(page)
                    break

            if len(all_pages) == 1:
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(embed=all_pages[0], view=RowButton_close_message())
                else:
                    await tmp_msg.delete()
                    await ctx.reply(content=None, embed=all_pages[0], view=RowButton_close_message())
            else:
                view = MenuPage(ctx, all_pages, timeout=30)
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    view.message = await ctx.response.send_message(embed=all_pages[0], view=view)
                else:
                    await tmp_msg.delete()
                    view.message = await ctx.reply(content=None, embed=all_pages[0], view=view)


    @commands.has_permissions(administrator=True)
    @guild.sub_command(
        usage="guild votereward <amount> <coin/token> [channel]", 
        options=[
            Option('amount', 'amount', OptionType.string, required=True), 
            Option('coin', 'coin', OptionType.string, required=True),
            Option('channel', 'channel', OptionType.channel, required=True)
        ],
        description="Set a reward when a user vote to your guild (topgg, ...)."
    )
    async def votereward(
        self,
        ctx,
        amount: str, 
        coin: str,
        channel: disnake.TextChannel
    ):
        COIN_NAME = coin.upper()
        if not hasattr(self.bot.coin_list, COIN_NAME):
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
            else:
                await ctx.reply(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
            return

        net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
        contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
        token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
        MinTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_tip")
        MaxTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_max_tip")
        usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
        
        Guild_WalletAPI = WalletAPI(self.bot)
        get_deposit = await Guild_WalletAPI.sql_get_userwallet(str(ctx.guild.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
        if get_deposit is None:
            get_deposit = await Guild_WalletAPI.sql_register_user(str(ctx.guild.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 1)

        wallet_address = get_deposit['balance_wallet_address']
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

        userdata_balance = await self.user_balance(str(ctx.guild.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
        actual_balance = float(userdata_balance['adjust'])

        amount = amount.replace(",", "")
        amount = text_to_num(amount)
        if amount is None:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        # We assume max reward by MaxTip / 10
        elif amount < MinTip or amount > MaxTip / 10:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Reward cannot be smaller than {num_format_coin(MinTip, COIN_NAME, coin_decimal, False)} {token_display} or bigger than {num_format_coin(MaxTip / 10, COIN_NAME, coin_decimal, False)} {token_display}.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg, ephemeral=True)
            else:
                await ctx.reply(msg)
            return
        # We assume at least guild need to have 100x of reward or depends on guild's population
        elif amount*100 > actual_balance:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} you need to have at least 100x reward balance. 100x rewards = {num_format_coin(amount*100, COIN_NAME, coin_decimal, False)} {token_display}.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg, ephemeral=True)
            else:
                await ctx.reply(msg)
            return
        elif amount*len(ctx.guild.members) > actual_balance:
            population = len(ctx.guild.members)
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} you need to have at least {str(population)}x reward balance. {str(population)}x rewards = {num_format_coin(amount*population, COIN_NAME, coin_decimal, False)} {token_display}.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg, ephemeral=True)
            else:
                await ctx.reply(msg)
            return
        else:
            # Check channel
            get_channel = self.bot.get_channel(int(channel.id))
            channel_str = str(channel.id)
            # Test message
            msg = f"New vote reward set to {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display} by {ctx.author.name}#{ctx.author.discriminator} and message here."
            try:
                await get_channel.send(msg)
            except Exception as e:
                msg = f'{ctx.author.mention}, failed to message channel {channel.mention}. Set reward denied!'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg, ephemeral=True)
                else:
                    await ctx.reply(msg)
                traceback.print_exc(file=sys.stdout)
                return
            
            # Process, only guild owner can process
            try:
                serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
                if serverinfo is None:
                    # Let's add some info if server return None
                    add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            except Exception as e:
                msg = f'{ctx.author.mention}, internal error. Please report.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg, ephemeral=True)
                else:
                    await ctx.reply(msg)
                traceback.print_exc(file=sys.stdout)
            update_reward = await self.update_reward(str(ctx.guild.id), float(amount), COIN_NAME, False, channel_str)
            if update_reward > 0:
                msg = f'{ctx.author.mention} Successfully set reward for voting in guild {ctx.guild.name} to {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg, ephemeral=True)
                else:
                    await ctx.reply(msg)
                try:
                    await self.vote_logchan(f'[{SERVER_BOT}] A user {ctx.author.name}#{ctx.author.discriminator} set a vote reward in guild {ctx.guild.name} / {ctx.guild.id} to {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}.')
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            else:
                msg = f'{ctx.author.mention} internal error or nothing updated.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg, ephemeral=True)
                else:
                    await ctx.reply(msg)
            return


    @guild.sub_command(
        usage="guild deposit <amount> <coin/token>", 
        options=[
            Option('amount', 'amount', OptionType.string, required=True), 
            Option('coin', 'coin', OptionType.string, required=True) 
        ],
        description="Deposit from your balance to the said guild"
    )
    async def deposit(
        self,
        ctx,
        amount: str, 
        coin: str
    ):
        COIN_NAME = coin.upper()
        if not hasattr(self.bot.coin_list, COIN_NAME):
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
            else:
                await ctx.reply(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
            return
        # Do the job
        try:
            net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
            token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
            MinTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_tip")
            MaxTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_max_tip")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")

            Guild_WalletAPI = WalletAPI(self.bot)
            get_deposit = await Guild_WalletAPI.sql_get_userwallet(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
            if get_deposit is None:
                get_deposit = await Guild_WalletAPI.sql_register_user(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)

            wallet_address = get_deposit['balance_wallet_address']
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

            # check if amount is all
            all_amount = False
            if not amount.isdigit() and amount.upper() == "ALL":
                all_amount = True
                userdata_balance = await self.user_balance(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                amount = float(userdata_balance['adjust'])
            # If $ is in amount, let's convert to coin/token
            elif "$" in amount[-1] or "$" in amount[0]: # last is $
                # Check if conversion is allowed for this coin.
                amount = amount.replace(",", "").replace("$", "")
                if usd_equivalent_enable == 0:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{COIN_NAME}`."
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
                else:
                    native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                    COIN_NAME_FOR_PRICE = COIN_NAME
                    if native_token_name:
                        COIN_NAME_FOR_PRICE = native_token_name
                    per_unit = None
                    if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                        id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                        per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                    else:
                        per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
                    if per_unit and per_unit > 0:
                        amount = float(Decimal(amount) / Decimal(per_unit))
                    else:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. Try with different method.'
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg)
                        else:
                            await ctx.reply(msg)
                        return
            else:
                amount = amount.replace(",", "")
                amount = text_to_num(amount)
                if amount is None:
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount.')
                    else:
                        await ctx.reply(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount.')
                    return
            # end of check if amount is all
            userdata_balance = await self.user_balance(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
            actual_balance = Decimal(userdata_balance['adjust'])
            amount = Decimal(amount)
            if amount <= 0:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please topup more {COIN_NAME}'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
                
            if amount > actual_balance:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to deposit {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg, ephemeral=True)
                else:
                    await ctx.reply(msg)
                return

            elif amount < MinTip or amount > MaxTip:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention} Transaction cannot be smaller than {num_format_coin(MinTip, COIN_NAME, coin_decimal, False)} {token_display} or bigger than {num_format_coin(MaxTip, COIN_NAME, coin_decimal, False)} {token_display}.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg, ephemeral=True)
                else:
                    await ctx.reply(msg)
                return

            equivalent_usd = ""
            amount_in_usd = 0.0
            per_unit = None
            if usd_equivalent_enable == 1:
                native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                COIN_NAME_FOR_PRICE = COIN_NAME
                if native_token_name:
                    COIN_NAME_FOR_PRICE = native_token_name
                if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                    id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                    per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                else:
                    per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
                if per_unit and per_unit > 0:
                    amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                    if amount_in_usd > 0.0001:
                        equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)

            # OK, move fund
            if ctx.author.id in self.bot.TX_IN_PROCESS:
                await ctx.response.send_message(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
                return
            else:
                self.bot.TX_IN_PROCESS.append(ctx.author.id)
                try:
                    tip = await store.sql_user_balance_mv_single(str(ctx.author.id), str(ctx.guild.id), str(ctx.guild.id), str(ctx.channel.id), amount, COIN_NAME, 'GUILDDEPOSIT', coin_decimal, SERVER_BOT, contract, amount_in_usd)
                    if tip:
                        try:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention} **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}**{equivalent_usd} was transferred to {ctx.guild.name}.'
                            if type(ctx) == disnake.ApplicationCommandInteraction:
                                await ctx.response.send_message(msg)
                            else:
                                await ctx.reply(msg)
                        except (disnake.Forbidden, disnake.errors.Forbidden, disnake.errors.HTTPException) as e:
                            pass
                        guild_found = self.bot.get_guild(ctx.guild.id)
                        if guild_found: user_found = self.bot.get_user(guild_found.owner.id)
                        if user_found:
                            notifyList = await store.sql_get_tipnotify()
                            if str(guild_found.owner.id) not in notifyList:
                                try:
                                    await user_found.send(f'Your guild **{ctx.guild.name}** got a deposit of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}**{equivalent_usd} from {ctx.author.name}#{ctx.author.discriminator} in `#{ctx.channel.name}`\n{NOTIFICATION_OFF_CMD}')
                                except (disnake.Forbidden, disnake.errors.Forbidden, disnake.errors.HTTPException) as e:
                                    pass
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                if ctx.author.id in self.bot.TX_IN_PROCESS:
                    self.bot.TX_IN_PROCESS.remove(ctx.author.id)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.has_permissions(administrator=True)
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


    @commands.has_permissions(administrator=True)
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


    # Guild deposit
    async def async_mdeposit(self, ctx, token: str=None, plain: str=None):
        COIN_NAME = None
        if token is None:
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(f'{ctx.author.mention}, token name is missing.')
            else:
                await ctx.reply(f'{ctx.author.mention}, token name is missing.')
            return
        else:
            COIN_NAME = token.upper()
            # print(self.bot.coin_list)
            if not hasattr(self.bot.coin_list, COIN_NAME):
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
                else:
                    await ctx.reply(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
                return
            else:
                if getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_deposit") == 0:
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** deposit disable.')
                    else:
                        await ctx.reply(f'{ctx.author.mention}, **{COIN_NAME}** deposit disable.')
                    return
                    
        # Do the job
        try:
            Guild_WalletAPI = WalletAPI(self.bot)
            net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
            get_deposit = await Guild_WalletAPI.sql_get_userwallet(str(ctx.guild.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
            if get_deposit is None:
                get_deposit = await Guild_WalletAPI.sql_register_user(str(ctx.guild.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 1)
                
            wallet_address = get_deposit['balance_wallet_address']
            description = ""
            fee_txt = ""
            guild_note = " This is guild's deposit address and NOT YOURS."
            token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_note") and len(getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_note")) > 0:
                description = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_note")
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "real_deposit_fee") and getattr(getattr(self.bot.coin_list, COIN_NAME), "real_deposit_fee") > 0:
                fee_txt = " **{} {}** will be deducted from your deposit when it reaches minimum. ".format(getattr(getattr(self.bot.coin_list, COIN_NAME), "real_deposit_fee"), token_display)
            embed = disnake.Embed(title=f'Deposit for guild {ctx.guild.name}', description=description + fee_txt + guild_note, timestamp=datetime.fromtimestamp(int(time.time())))
            embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
            try:
                gen_qr_address = await Guild_WalletAPI.generate_qr_address(wallet_address)
                embed.set_thumbnail(url=config.storage.deposit_url + wallet_address + ".png")
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            plain_msg = 'Guild {} deposit address: ```{}```'.format(ctx.guild.name, wallet_address)
            embed.add_field(name="Guild {}".format(ctx.guild.name), value="`{}`".format(wallet_address), inline=False)
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link") and len(getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link")) > 0:
                embed.add_field(name="Other links", value="[{}]({})".format("Explorer", getattr(getattr(self.bot.coin_list, COIN_NAME), "explorer_link")), inline=False)
            embed.set_footer(text="Use: deposit plain (for plain text)")
            try:
                # Try DM first
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    if plain and plain.lower() == 'plain' or plain.lower() == 'text':
                        await ctx.response.send_message(plain_msg, view=RowButton_row_close_any_message())
                    else:
                        await ctx.response.send_message(embed=embed, view=RowButton_row_close_any_message())
                else:
                    if plain and plain.lower() == 'plain' or plain.lower() == 'text':
                        msg = await ctx.reply(plain_msg, view=RowButton_row_close_any_message())
                    else:
                        msg = await ctx.reply(embed=embed, view=RowButton_row_close_any_message())
            except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.guild_only()
    @commands.slash_command(
        usage="mdeposit <coin_name>", 
        options=[
            Option('token', 'token', OptionType.string, required=True),
            Option('plain', 'plain', OptionType.string, required=False)
        ],
        description="Get a deposit address for a guild."
    )
    async def mdeposit(
        self, 
        ctx,
        token: str,
        plain: str = 'embed'
    ):
        await self.async_mdeposit(ctx, token, plain)


    @commands.has_permissions(administrator=True)
    @guild.sub_command(
        usage="guild faucetclaim <amount> <coin/token> <channel>", 
        options=[
            Option('amount', 'amount', OptionType.string, required=True), 
            Option('coin', 'coin', OptionType.string, required=True),
            Option('duration', 'duration', OptionType.string, required=True),
            Option('channel', 'channel', OptionType.channel, required=True)
        ],
        description="Allow your guild's user to claim reward."
    )
    async def faucetclaim(
        self,
        ctx,
        amount: str, 
        coin: str,
        duration: str,
        channel: disnake.TextChannel
    ):
        COIN_NAME = coin.upper()
        if not hasattr(self.bot.coin_list, COIN_NAME):
            await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
            return

        duration_s = 12*3600
        duration = duration.upper()
        if duration not in ["4H", "8H", "12H", "24H"]:
            await ctx.response.send_message(f'{ctx.author.mention}, accepted duration 4H, 8H, 12H, 24H.')
            return
        elif duration == "4H":
            duration_s = 4*3600
        elif duration == "8H":
            duration_s = 8*3600
        elif duration == "12H":
            duration_s = 12*3600
        elif duration == "24H":
            duration_s = 24*3600

        net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
        contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
        token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
        MinTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_tip")
        MaxTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_max_tip")
        usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
        
        Guild_WalletAPI = WalletAPI(self.bot)
        get_deposit = await Guild_WalletAPI.sql_get_userwallet(str(ctx.guild.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
        if get_deposit is None:
            get_deposit = await Guild_WalletAPI.sql_register_user(str(ctx.guild.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 1)

        wallet_address = get_deposit['balance_wallet_address']
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

        userdata_balance = await self.user_balance(str(ctx.guild.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
        actual_balance = float(userdata_balance['adjust'])

        amount = amount.replace(",", "")
        amount = text_to_num(amount)
        if amount is None:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
            await ctx.response.send_message(msg)
            return
        # We assume max reward by MaxTip / 10
        elif amount < MinTip or amount > MaxTip / 10:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, faucet cannot be smaller than {num_format_coin(MinTip, COIN_NAME, coin_decimal, False)} {token_display} or bigger than {num_format_coin(MaxTip / 10, COIN_NAME, coin_decimal, False)} {token_display}.'
            await ctx.response.send_message(msg, ephemeral=True)
            return
        # We assume at least guild need to have 100x of reward or depends on guild's population
        elif amount*200 > actual_balance:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you need to have at least 100x reward balance. 100x rewards = {num_format_coin(amount*200, COIN_NAME, coin_decimal, False)} {token_display}.'
            await ctx.response.send_message(msg, ephemeral=True)
            return
        elif amount*len(ctx.guild.members) > actual_balance:
            population = len(ctx.guild.members)
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you need to have at least {str(population)}x reward balance. {str(population)}x rewards = {num_format_coin(amount*population, COIN_NAME, coin_decimal, False)} {token_display}.'
            await ctx.response.send_message(msg, ephemeral=True)
            return
        else:
            # Check channel
            get_channel = self.bot.get_channel(int(channel.id))
            channel_str = str(channel.id)
            # Test message
            msg = f"New guild /faucet set to {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display} by {ctx.author.name}#{ctx.author.discriminator} and message here."
            try:
                await get_channel.send(msg)
            except Exception as e:
                msg = f'{ctx.author.mention}, failed to message channel {channel.mention}. Set faucet denied!'
                await ctx.response.send_message(msg, ephemeral=True)
                traceback.print_exc(file=sys.stdout)
                return
            
            # Process, only guild owner can process
            try:
                serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
                if serverinfo is None:
                    # Let's add some info if server return None
                    add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                msg = f'{ctx.author.mention}, internal error. Please report.'
                await ctx.response.send_message(msg, ephemeral=True)

            update_faucet = await self.update_faucet(str(ctx.guild.id), float(amount), COIN_NAME, duration_s, False, channel_str)
            if update_faucet > 0:
                msg = f'{ctx.author.mention} Successfully faucet in guild {ctx.guild.name} to {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display} for every {duration}.'
                await ctx.response.send_message(msg)
                try:
                    await logchanbot(f'[{SERVER_BOT}] A user {ctx.author.name}#{ctx.author.discriminator} set /faucet in guild {ctx.guild.name} / {ctx.guild.id} to {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display} for every {duration}.')
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            else:
                msg = f'{ctx.author.mention} internal error or nothing updated.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg, ephemeral=True)
                else:
                    await ctx.reply(msg)
            return


    async def async_guild_info(self, ctx):
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))

        embed = disnake.Embed(title = "Guild {} / {}".format(ctx.guild.name, ctx.guild.id), timestamp=datetime.now())
        try:
            owner_id = ctx.guild.owner.id
            total_number = ctx.guild.member_count
            total_roles = len(ctx.guild.roles)
            nos_text_channel = len(ctx.guild.text_channels)
            nos_categories = len(ctx.guild.categories)
            num_online = len([member for member in ctx.guild.members if member.bot == False and member.status != disnake.Status.offline])
            num_bot = len([member for member in ctx.guild.members if member.bot == True])
            m_statistics = "Owner: <@{}>\n```Total Members: {}\nOnline: {}\nBots: {}\nRoles: {}\nCategories: {}\nText Channels: {}```".format(owner_id, total_number, num_online, num_bot, total_roles, nos_categories, nos_text_channel)
            embed.add_field(name="Statistics", value=m_statistics, inline=False)
            embed.set_thumbnail(url=str(ctx.guild.icon))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if serverinfo['tiponly'] is not None:
            embed.add_field(name="Allowed Coins (Tip)", value="{}".format(serverinfo['tiponly']), inline=True)
        if serverinfo['enable_faucet'] == "YES" and serverinfo['faucet_channel']:
            embed.add_field(name="Faucet Channel", value="<#{}>".format(serverinfo['faucet_channel']), inline=True)
        if serverinfo['botchan']:
            embed.add_field(name="Bot Channel", value="<#{}>".format(serverinfo['botchan']), inline=True)
        if serverinfo['economy_channel'] and serverinfo['enable_economy'] == "YES":
            embed.add_field(name="Economy Channel", value="<#{}>".format(serverinfo['economy_channel']), inline=True)
        embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}")
        await ctx.response.send_message(embed=embed)

    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @guild.sub_command(
        usage="guild info", 
        description="Get information about a guild."
    )
    async def info(
        self,
        ctx
    ):
        await self.async_guild_info(ctx)

    @commands.guild_only()
    @commands.user_command(name="GuildInfo")  # optional
    async def guild_info(self, ctx: disnake.ApplicationCommandInteraction):
        await self.async_guild_info(ctx)


    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @commands.slash_command(usage="/faucet",
                            description="Claim guild's faucet.")
    async def faucet(
        self, 
        ctx
    ):
        await self.bot_log()
        # bot check in the first place
        if ctx.author.bot == True:
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} (Bot) using **/faucet** {ctx.guild.name} / {ctx.guild.id}')
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, Bot is not allowed using this."
            await ctx.response.send_message(msg)
            return

        if ctx.author.id in self.bot.TX_IN_PROCESS:
            msg = f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
            await ctx.response.send_message(msg)
            return

        # check if bot channel is set:
        try: 
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if serverinfo and serverinfo['faucet_channel'] and ctx.channel.id != int(serverinfo['faucet_channel']):
                try:
                    channel = self.bot.get_channel(int(serverinfo['faucet_channel']))
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, {channel.mention} is the faucet channel!!!'
                    await ctx.response.send_message(msg)
                    return
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            if serverinfo and serverinfo['enable_faucet'] == "NO":
                if self.enable_logchan:
                    await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} tried **/faucet** in {ctx.guild.name} / {ctx.guild.id} which is disable.')
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, **/faucet** in this guild is disable."
                await ctx.response.send_message(msg)
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            return
        # end of channel check

        if serverinfo['faucet_coin'] and serverinfo['faucet_amount'] > 0 and serverinfo['faucet_duration'] is not None:
            COIN_NAME = serverinfo['faucet_coin']
            amount = serverinfo['faucet_amount']
            duration = serverinfo['faucet_duration']

            if not hasattr(self.bot.coin_list, COIN_NAME):
                msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
                await ctx.response.send_message(msg)
                return

            get_last_claim = await self.get_faucet_claim_user_guild( str(ctx.author.id), str(ctx.guild.id), SERVER_BOT )
            if get_last_claim is not None and int(time.time()) - get_last_claim['date'] < duration:
                last_duration = seconds_str( int(time.time()) - get_last_claim['date'] )
                waiting_time = seconds_str( duration - int(time.time()) + get_last_claim['date'] )
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you just claimed in this guild `{ctx.guild.name}` last {last_duration} ago. Waiting time {waiting_time}."
                await ctx.response.send_message(msg)
                return
            else:
                # OK claim
                net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
                type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
                coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
                token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")

                MinTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_tip")
                MaxTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_max_tip")
                usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")

                Guild_WalletAPI = WalletAPI(self.bot)
                get_deposit = await Guild_WalletAPI.sql_get_userwallet(str(ctx.guild.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
                if get_deposit is None:
                    get_deposit = await Guild_WalletAPI.sql_register_user(str(ctx.guild.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 1)

                wallet_address = get_deposit['balance_wallet_address']
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

                userdata_balance = await store.sql_user_balance_single(str(ctx.guild.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                actual_balance = float(userdata_balance['adjust'])
                # Check if tx in progress
                if ctx.guild.id in self.bot.TX_IN_PROCESS:
                    msg = f'{EMOJI_ERROR} {ctx.author.mention}, another tx in progress with this guild.'
                    await ctx.response.send_message(msg)
                    return

                if amount <= 0:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please topup guild more {COIN_NAME}'
                    await ctx.response.send_message(msg)
                    return

                if amount > actual_balance:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, guild has insufficient balance for {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}.'
                    await ctx.response.send_message(msg, ephemeral=True)
                    return
                elif amount < MinTip or amount > MaxTip:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, transaction cannot be smaller than {num_format_coin(MinTip, COIN_NAME, coin_decimal, False)} {token_display} or bigger than {num_format_coin(MaxTip, COIN_NAME, coin_decimal, False)} {token_display}.'
                    await ctx.response.send_message(msg, ephemeral=True)
                    return

                equivalent_usd = ""
                amount_in_usd = 0.0
                if usd_equivalent_enable == 1:
                    native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                    COIN_NAME_FOR_PRICE = COIN_NAME
                    if native_token_name:
                        COIN_NAME_FOR_PRICE = native_token_name
                    if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                        id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                        per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                    else:
                        per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
                    if per_unit and per_unit > 0:
                        amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                        if amount_in_usd > 0.0001:
                            equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)
                if ctx.guild.id not in self.bot.TX_IN_PROCESS:
                    self.bot.TX_IN_PROCESS.append(ctx.guild.id)
                    try:
                        tip = await store.sql_user_balance_mv_single(str(ctx.guild.id), str(ctx.author.id), str(ctx.guild.id), str(ctx.channel.id), amount, COIN_NAME, 'GUILDFAUCET', coin_decimal, SERVER_BOT, contract, amount_in_usd)
                        if tip:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention} got a faucet of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}**{equivalent_usd} from `{ctx.guild.name}`. Other reward command `/take` and `/claim`. Invite me to your guild? Click on my name and "Add to Server".'
                            await ctx.response.send_message(msg)
                            await logchanbot(f'[Discord] User {ctx.author.name}#{ctx.author.discriminator} claimed guild /faucet {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME} in guild {ctx.guild.name}/{ctx.guild.id}.')
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                    if ctx.guild.id in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.remove(ctx.guild.id)
        else:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, this guild `{ctx.guild.name}` has no guild\'s faucet or internal error.'
            await ctx.response.send_message(msg)
            await logchanbot(f'[Discord] [ERROR] User {ctx.author.name}#{ctx.author.discriminator} claimed guild /faucet in guild {ctx.guild.name}/{ctx.guild.id}.')
            return
    # Guild deposit

    # Setting command
    @commands.guild_only()
    @commands.slash_command(description="Guild setting commands.")
    async def setting(self, ctx):
        pass


    @commands.has_permissions(manage_channels=True)
    @setting.sub_command(
        usage="setting tiponly <coin1, coin2, ....>", 
        options=[
            Option('coin_list', 'coin_list', OptionType.string, required=True)
        ],
        description="Allow only these coins for tipping"
    )
    async def tiponly(self, ctx, coin_list: str):
        await self.bot_log()
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))

        coin_list = coin_list.upper()
        if coin_list in ["ALLCOIN", "*", "ALL", "TIPALL", "ANY"]:
            changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'tiponly', "ALLCOIN")
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} changed tiponly in {ctx.guild.name} / {ctx.guild.id} to `ALLCOIN`')
            msg = f'{ctx.author.mention}, all coins will be allowed in here.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                msg = await ctx.reply(msg)
            return
        elif " " in coin_list or "," in coin_list:
            # multiple coins
            if " " in coin_list:
                coins = coin_list.split()
            elif "," in coin_list:
                coins = coin_list.split(",")
            contained = []
            if len(coins) > 0:
                for each_coin in coins:
                    if not hasattr(self.bot.coin_list, each_coin.upper()):
                        continue
                    else:
                        contained.append(each_coin.upper())
            if contained and len(contained) >= 2:
                tiponly_value = ','.join(contained)
                if self.enable_logchan:
                    await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} changed tiponly in {ctx.guild.name} / {ctx.guild.id} to `{tiponly_value}`')
                msg = f'{ctx.author.mention} TIPONLY for guild {ctx.guild.name} set to: **{tiponly_value}**.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    msg = await ctx.reply(msg)
                changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'tiponly', tiponly_value.upper())
            else:
                msg = f'{ctx.author.mention} No known coin in **{coin_list}**. TIPONLY is remained unchanged in guild `{ctx.guild.name}`.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    msg = await ctx.reply(msg)
        else:
            # Single coin
            if coin_list not in self.bot.coin_name_list:
                msg = f'{ctx.author.mention} {coin_list} is not in any known coin we set.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    msg = await ctx.reply(msg)
            else:
                # coin_list is single coin set_coin
                changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'tiponly', coin_list)
                if self.enable_logchan:
                    await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} changed tiponly in {ctx.guild.name} / {ctx.guild.id} to `{coin_list}`')
                msg = f'{ctx.author.mention} {coin_list} will be the only tip here in guild `{ctx.guild.name}`.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)


    @commands.has_permissions(manage_channels=True)
    @setting.sub_command(
        usage="setting trade", 
        description="Toggle trade enable ON/OFF in your guild"
    )
    async def trade(
        self, 
        ctx,
    ):
        await self.bot_log()
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
                                                                
        if serverinfo and serverinfo['enable_trade'] == "YES":
            changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_trade', 'NO')
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} DISABLE trade in their guild {ctx.guild.name} / {ctx.guild.id}')
            msg = f"{ctx.author.mention} DISABLE TRADE feature in this guild {ctx.guild.name}."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
        elif serverinfo and serverinfo['enable_trade'] == "NO":
            changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_trade', 'YES')
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} ENABLE trade in their guild {ctx.guild.name} / {ctx.guild.id}')
            msg = f"{ctx.author.mention} ENABLE TRADE feature in this guild {ctx.guild.name}."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
        else:
            msg = f"{ctx.author.mention} Internal error when calling serverinfo function."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)

    @commands.has_permissions(manage_channels=True)
    @setting.sub_command(
        usage="setting nsfw", 
        description="Toggle nsfw ON/OFF in your guild"
    )
    async def nsfw(
        self, 
        ctx,
    ):
        await self.bot_log()
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))

        if serverinfo and serverinfo['enable_nsfw'] == "YES":
            changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_nsfw', 'NO')
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} DISABLE NSFW in their guild {ctx.guild.name} / {ctx.guild.id}')
            msg = f"{ctx.author.mention} DISABLE NSFW command in this guild {ctx.guild.name}."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
        elif serverinfo and serverinfo['enable_nsfw'] == "NO":
            changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_nsfw', 'YES')
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} ENABLE NSFW in their guild {ctx.guild.name} / {ctx.guild.id}')
            msg = f"{ctx.author.mention} ENABLE NSFW command in this guild {ctx.guild.name}."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
        else:
            msg = f"{ctx.author.mention} Internal error when calling serverinfo function."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)

    @commands.has_permissions(manage_channels=True)
    @setting.sub_command(
        usage="setting game", 
        description="Toggle game ON/OFF in your guild"
    )
    async def game(
        self, 
        ctx,
    ):
        await self.bot_log()
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo['enable_game'] == "YES":
            changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_game', 'NO')
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} DISABLE game in their guild {ctx.guild.name} / {ctx.guild.id}')
            msg = f"{ctx.author.mention} DISABLE GAME feature in this guild {ctx.guild.name}."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
        elif serverinfo and serverinfo['enable_game'] == "NO":
            changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_game', 'YES')
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} ENABLE game in their guild {ctx.guild.name} / {ctx.guild.id}')
            msg = f"{ctx.author.mention} ENABLE GAME feature in this guild {ctx.guild.name}."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
        else:
            msg = f"{ctx.author.mention} Internal error when calling serverinfo function."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)


    @commands.has_permissions(manage_channels=True)
    @setting.sub_command(
        usage="setting botchan", 
        description="Set bot channel to the commanded channel"
    )
    async def botchan(
        self, 
        ctx,
    ):
        await self.bot_log()
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo['botchan']:
            try: 
                if ctx.channel.id == int(serverinfo['botchan']):
                    msg = f"{EMOJI_RED_NO} {ctx.channel.mention} is already the bot channel here!"
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
                else:
                    # change channel info
                    changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'botchan', str(ctx.channel.id))
                    msg = f'Bot channel of guild {ctx.guild.name} has set to {ctx.channel.mention}.'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    if self.enable_logchan:
                        await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} change bot channel {ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}.')
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
        else:
            # change channel info
            changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'botchan', str(ctx.channel.id))
            msg = f'Bot channel of guild {ctx.guild.name} has set to {ctx.channel.mention}.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} changed bot channel {ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}.')


    @commands.has_permissions(manage_channels=True)
    @setting.sub_command(
        usage="setting economychan", 
        description="Set economy game channel to the commanded channel"
    )
    async def economychan(
        self, 
        ctx,
    ):
        await self.bot_log()
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo['economy_channel']:
            try: 
                if ctx.channel.id == int(serverinfo['economy_channel']):
                    msg = f"{EMOJI_RED_NO} {ctx.channel.mention} is already the economy game channel here!"
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
                else:
                    # change channel info
                    changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'economy_channel', str(ctx.channel.id))
                    msg = f'Economy game channel of guild {ctx.guild.name} has set to {ctx.channel.mention}.'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    if self.enable_logchan:
                        await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} change economy game channel {ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}.')
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
        else:
            # change channel info
            changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'economy_channel', str(ctx.channel.id))
            msg = f'Economy game channel of guild {ctx.guild.name} has set to {ctx.channel.mention}.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} changed economy game channel {ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}.')


    @commands.has_permissions(manage_channels=True)
    @setting.sub_command(
        usage="setting setfaucet", 
        description="Toggle faucet enable ON/OFF in your guild"
    )
    async def setfaucet(
        self, 
        ctx,
    ):
        await self.bot_log()
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))

        if serverinfo and serverinfo['enable_faucet'] == "YES":
            changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_faucet', 'NO')
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} DISABLE faucet (take) command in their guild {ctx.guild.name} / {ctx.guild.id}')
            msg = f"{ctx.author.mention} DISABLE faucet (take/claim) command in this guild {ctx.guild.name}."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
        elif serverinfo and serverinfo['enable_faucet'] == "NO":
            changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_faucet', 'YES')
            if self.enable_logchan:
                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} ENABLE faucet (take) command in their guild {ctx.guild.name} / {ctx.guild.id}')
            msg = f"{ctx.author.mention} ENABLE faucet (take/claim) command in this guild {ctx.guild.name}."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
        else:
            msg = f"{ctx.author.mention} Internal error when calling serverinfo function."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)


    async def async_set_gamechan(self, ctx, game):
        game_list = config.game.game_list.split(",")
        if game is None:
            msg = f"{EMOJI_RED_NO} {ctx.channel.mention} please mention a game name to set game channel for it. Game list: {config.game.game_list}."
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        else:
            game = game.lower()
            if game not in game_list:
                msg = f"{EMOJI_RED_NO} {ctx.channel.mention} please mention a game name within this list: {config.game.game_list}."
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
            else:
                serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
                index_game = "game_" + game + "_channel"
                if serverinfo is None:
                    # Let's add some info if server return None
                    add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id), ctx.guild.name, "/", DEFAULT_TICKER)
                    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
                if serverinfo[index_game]:
                    try: 
                        if ctx.channel.id == int(serverinfo[index_game]):
                            msg = f"{EMOJI_RED_NO} {ctx.channel.mention} is already for game **{game}** channel here!"
                            if type(ctx) == disnake.ApplicationCommandInteraction:
                                await ctx.response.send_message(msg)
                            else:
                                await ctx.reply(msg)
                            return
                        else:
                            # change channel info
                            changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), index_game, str(ctx.channel.id))
                            msg = f'{ctx.channel.mention} Game **{game}** channel has set to {ctx.channel.mention}.'
                            if type(ctx) == disnake.ApplicationCommandInteraction:
                                await ctx.response.send_message(msg)
                            else:
                                await ctx.reply(msg)
                            if self.enable_logchan:
                                await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} changed game **{game}** in channel {ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}.')
                            return
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
                else:
                    # change channel info
                    changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), index_game, str(ctx.channel.id))
                    msg = f'{ctx.channel.mention} Game **{game}** channel has set to {ctx.channel.mention}.'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    if self.enable_logchan:
                        await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} set game **{game}** channel in {ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}.')
                    return

    @commands.has_permissions(manage_channels=True)
    @guild.sub_command(
        usage="guild gamechan <game>", 
        options=[
            Option('game', 'game', OptionType.string, required=True, choices=[
                OptionChoice("2048", "2048"),
                OptionChoice("BLACKJACK", "BLACKJACK"),
                OptionChoice("DICE", "DICE"),
                OptionChoice("MAZE", "MAZE"),
                OptionChoice("SLOT", "SLOT"),
                OptionChoice("SNAIL", "SNAIL"),
                OptionChoice("SOKOBAN", "SOKOBAN")
            ]
            )
        ],
        description="Set guild's specific game channel."
    )
    @commands.has_permissions(manage_channels=True)
    async def gamechan(
        self, 
        ctx,
        game: str
    ):
        await self.bot_log()
        await self.async_set_gamechan(ctx, game)


    @commands.has_permissions(manage_channels=True)
    @setting.sub_command(
        usage="setting gamechan <game>", 
        options=[
            Option('game', 'game', OptionType.string, required=True, choices=[
                OptionChoice("2048", "2048"),
                OptionChoice("BLACKJACK", "BLACKJACK"),
                OptionChoice("DICE", "DICE"),
                OptionChoice("MAZE", "MAZE"),
                OptionChoice("SLOT", "SLOT"),
                OptionChoice("SNAIL", "SNAIL"),
                OptionChoice("SOKOBAN", "SOKOBAN")
            ]
            )
        ],
        description="Set guild's specific game channel."
    )
    
    @commands.has_permissions(manage_channels=True)
    async def gamechan(
        self, 
        ctx,
        game: str
    ):
        await self.bot_log()
        await self.async_set_gamechan(ctx, game)

    # End of setting

def setup(bot):
    bot.add_cog(Guild(bot))