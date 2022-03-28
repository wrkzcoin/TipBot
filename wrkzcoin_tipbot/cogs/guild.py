import asyncio
import re
import sys
import time
import traceback
from datetime import datetime
import random
import qrcode
import uuid
from decimal import Decimal
import aiomysql
from aiomysql.cursors import DictCursor

import disnake
from disnake.ext import tasks, commands

from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice
from discord_webhook import DiscordWebhook

import store
from Bot import get_token_list, num_format_coin, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_ARROW_RIGHTHOOK, SERVER_BOT, RowButton_close_message, RowButton_row_close_any_message, human_format, text_to_num, truncate, NOTIFICATION_OFF_CMD, DEFAULT_TICKER

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

                balance['mv_balance'] = float("%.4f" % mv_balance) if mv_balance else 0

                balance['airdropping'] = float("%.4f" % airdropping) if airdropping else 0
                balance['mathtip'] = float("%.4f" % mathtip) if mathtip else 0
                balance['triviatip'] = float("%.4f" % triviatip) if triviatip else 0

                balance['tx_expense'] = float("%.4f" % tx_expense) if tx_expense else 0
                balance['incoming_tx'] = float("%.4f" % incoming_tx) if incoming_tx else 0
                
                balance['open_order'] = float("%.4f" % open_order) if open_order else 0

                balance['adjust'] = float("%.4f" % ( balance['mv_balance']+balance['incoming_tx']-balance['airdropping']-balance['mathtip']-balance['triviatip']-balance['tx_expense']-balance['open_order'] ))
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

    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)

    # Check if guild has at least 10x amount of reward or disable
    @tasks.loop(seconds=30.0)
    async def monitor_guild_reward_amount(self):
        await self.bot.wait_until_ready()
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
                                update_reward = await self.update_reward(each_guild['serverid'], actual_balance, COIN_NAME, True)
                                if update_reward is not None:
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

    async def update_reward(self, guild_id: str, amount: float, coin_name: str, disable: bool=False):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if disable == True:
                        sql = """ UPDATE discord_server SET `vote_reward_amount`=%s, `vote_reward_coin`=%s WHERE `serverid`=%s LIMIT 1 """
                        await cur.execute(sql, ( None, None, guild_id ))
                        await conn.commit()
                        return cur.rowcount
                    else:
                        sql = """ UPDATE discord_server SET `vote_reward_amount`=%s, `vote_reward_coin`=%s WHERE `serverid`=%s LIMIT 1 """
                        await cur.execute(sql, ( amount, coin_name.upper(), guild_id ))
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
                                         timestamp=datetime.utcnow(), )
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
                                             timestamp=datetime.utcnow(), )
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
        usage="guild votereward <amount> <coin/token>", 
        options=[
            Option('amount', 'amount', OptionType.string, required=True), 
            Option('coin', 'coin', OptionType.string, required=True) 
        ],
        description="Set a reward when a user vote to your guild (topgg, ...)."
    )
    async def votereward(
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
            # Process, only guild owner can process
            update_reward = await self.update_reward(str(ctx.guild.id), float(amount), COIN_NAME)
            if update_reward is not None:
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
                msg = f'{EMOJI_RED_NO} {ctx.author.mention} internal error.'
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
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
                else:
                    await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
                    msg = await ctx.reply(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
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
            embed = disnake.Embed(title=f'Deposit for guild {ctx.guild.name}', description=description + fee_txt + guild_note, timestamp=datetime.utcnow())
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
        usage="setting faucet", 
        description="Toggle faucet enable ON/OFF in your guild"
    )
    async def faucet(
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