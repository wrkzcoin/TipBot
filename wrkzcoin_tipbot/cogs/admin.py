import sys
import traceback
from datetime import datetime

import disnake
from disnake.ext import commands
import time
from attrdict import AttrDict
from io import BytesIO
import random

import aiohttp, asyncio
from mnemonic import Mnemonic

import aiomysql
from aiomysql.cursors import DictCursor

# For eval
import contextlib
import io
from decimal import Decimal

from web3 import Web3
from web3.middleware import geth_poa_middleware
from ethtoken.abi import EIP20_ABI

from tronpy import AsyncTron
from tronpy.async_contract import AsyncContract, ShieldedTRC20, AsyncContractMethod
from tronpy.providers.async_http import AsyncHTTPProvider
from tronpy.exceptions import AddressNotFound
from tronpy.keys import PrivateKey

import json

from httpx import AsyncClient, Timeout, Limits
from eth_account import Account
from pywallet import wallet as ethwallet

import functools
import store
from Bot import num_format_coin, SERVER_BOT, logchanbot, encrypt_string, decrypt_string, RowButton_row_close_any_message, EMOJI_INFORMATION
from config import config
import redis_utils
from utils import MenuPage
from cogs.wallet import WalletAPI

Account.enable_unaudited_hdwallet_features()

class Admin(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
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
                    elif coin_family == "HNT":
                        sql = """ SELECT SUM(amount+withdraw_fee) AS tx_expense FROM `hnt_external_tx` WHERE `user_id`=%s AND `coin_name` = %s AND `user_server` = %s AND `crediting`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, user_server, "YES" ))
                        result = await cur.fetchone()
                        if result:
                            tx_expense = result['tx_expense']
                        else:
                            tx_expense = 0

                        # split address, memo
                        address_memo = address.split()
                        if top_block is None:
                            sql = """ SELECT SUM(amount) AS incoming_tx FROM `hnt_get_transfers` WHERE `address`=%s AND `memo`=%s AND `coin_name` = %s 
                                      AND `amount`>0 AND `time_insert`< %s """
                            await cur.execute(sql, (address_memo[0], address_memo[2], TOKEN_NAME, nos_block)) # TODO: split to address, memo
                        else:
                            sql = """ SELECT SUM(amount) AS incoming_tx FROM `hnt_get_transfers` WHERE `address`=%s AND `memo`=%s AND `coin_name` = %s 
                                      AND `amount`>0 AND `height`<%s """
                            await cur.execute(sql, (address_memo[0], address_memo[2], TOKEN_NAME, nos_block)) # TODO: split to address, memo
                        result = await cur.fetchone()
                        if result and result['incoming_tx']:
                            incoming_tx = result['incoming_tx']
                        else:
                            incoming_tx = 0
                    elif coin_family == "ADA":
                        sql = """ SELECT SUM(real_amount+real_external_fee) AS tx_expense 
                                  FROM `ada_external_tx` 
                                  WHERE `user_id`=%s AND `coin_name` = %s AND `user_server` = %s AND `crediting`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, user_server, "YES" ))
                        result = await cur.fetchone()
                        if result:
                            tx_expense = result['tx_expense']
                        else:
                            tx_expense = 0

                        if top_block is None:
                            sql = """ SELECT SUM(amount) AS incoming_tx 
                                      FROM `ada_get_transfers` WHERE `output_address`=%s AND `direction`=%s AND `coin_name`=%s 
                                      AND `amount`>0 AND `time_insert`< %s """
                            await cur.execute(sql, ( address, "incoming", TOKEN_NAME, nos_block ))
                        else:
                            sql = """ SELECT SUM(amount) AS incoming_tx 
                                      FROM `ada_get_transfers` 
                                      WHERE `output_address`=%s AND `direction`=%s AND `coin_name`=%s 
                                      AND `amount`>0 AND `inserted_at_height`<%s """
                            await cur.execute(sql, ( address, "incoming", TOKEN_NAME, nos_block ))
                        result = await cur.fetchone()
                        if result and result['incoming_tx']:
                            incoming_tx = result['incoming_tx']
                        else:
                            incoming_tx = 0
                    elif coin_family == "SOL" or coin_family == "SPL":
                        # When sending tx out, (negative)
                        sql = """ SELECT SUM(real_amount+real_external_fee) AS tx_expense FROM `sol_external_tx` 
                                  WHERE `user_id`=%s AND `coin_name` = %s AND `crediting`=%s """
                        await cur.execute(sql, ( userID, TOKEN_NAME, "YES" ))
                        result = await cur.fetchone()
                        if result:
                            tx_expense = result['tx_expense']
                        else:
                            tx_expense = 0

                        # in case deposit fee -real_deposit_fee
                        sql = """ SELECT SUM(real_amount-real_deposit_fee) AS incoming_tx FROM `sol_move_deposit` WHERE `user_id`=%s 
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

    async def cog_check(self, ctx):
        return commands.is_owner()

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

    async def sql_get_all_userid_by_coin(self, coin: str):
        COIN_NAME = coin.upper()
        type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                await conn.ping(reconnect=True)
                async with conn.cursor() as cur:
                    if type_coin.upper() == "CHIA":
                        sql = """ SELECT * FROM `xch_user` 
                                  WHERE `coin_name`=%s """
                        await cur.execute(sql, (COIN_NAME))
                        result = await cur.fetchall()
                        if result: return result
                    elif type_coin.upper() in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        sql = """ SELECT * FROM `cn_user_paymentid` 
                                  WHERE `coin_name`=%s """
                        await cur.execute(sql, (COIN_NAME))
                        result = await cur.fetchall()
                        if result: return result
                    elif type_coin.upper() == "BTC":
                        sql = """ SELECT * FROM `doge_user` 
                                  WHERE `coin_name`=%s """
                        await cur.execute(sql, (COIN_NAME))
                        result = await cur.fetchall()
                        if result: return result
                    elif type_coin.upper() == "NANO":
                        sql = """ SELECT * FROM `nano_user` 
                                  WHERE `coin_name`=%s """
                        await cur.execute(sql, (COIN_NAME))
                        result = await cur.fetchall()
                        if result: return result
                    elif type_coin.upper() == "ERC-20":
                        sql = """ SELECT * FROM `erc20_user` 
                                  WHERE `token_name`=%s """
                        await cur.execute(sql, (COIN_NAME))
                        result = await cur.fetchall()
                        if result: return result
                    elif type_coin.upper() == "TRC-20":
                        sql = """ SELECT * FROM `trc20_user` 
                                  WHERE `token_name`=%s """
                        await cur.execute(sql, (COIN_NAME))
                        result = await cur.fetchall()
                        if result: return result
                    elif type_coin.upper() == "HNT":
                        sql = """ SELECT * FROM `hnt_user` 
                                  WHERE `coin_name`=%s """
                        await cur.execute(sql, (COIN_NAME))
                        result = await cur.fetchall()
                        if result: return result
                    elif type_coin.upper() == "ADA":
                        sql = """ SELECT * FROM `ada_user` """
                        await cur.execute(sql,)
                        result = await cur.fetchall()
                        if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return []


    async def enable_disable_coin(self, coin: str, what: str, toggle: int):
        COIN_NAME = coin.upper()
        what = what.lower()
        if what not in ["withdraw", "deposit", "tip"]:
            return 0
        if what == "withdraw":
            what = "enable_withdraw"
        elif what == "deposit":
            what = "enable_deposit"
        elif what == "tip":
            what = "enable_tip"
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE coin_settings SET `"""+what+"""`=%s WHERE `coin_name`=%s AND `"""+what+"""`<>%s LIMIT 1 """               
                    await cur.execute(sql, ( toggle, COIN_NAME, toggle ))
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return 0


    async def create_address_eth(self):
        def create_eth_wallet():
            seed = ethwallet.generate_mnemonic()
            w = ethwallet.create_wallet(network="ETH", seed=seed, children=1)
            return w

        wallet_eth = functools.partial(create_eth_wallet)
        create_wallet = await self.bot.loop.run_in_executor(None, wallet_eth)
        return create_wallet


    async def create_address_trx(self):
        try:
            _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                       timeout=Timeout(timeout=10, connect=5, read=5))
            TronClient = AsyncTron(provider=AsyncHTTPProvider(config.Tron_Node.fullnode, client=_http_client))
            create_wallet = TronClient.generate_address()
            await TronClient.close()
            return create_wallet
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.is_owner()
    @commands.dm_only()
    @commands.group(
        usage="admin <subcommand>", 
        hidden = True, 
        description="Various admin commands."
    )
    async def admin(self, ctx):
        if ctx.invoked_subcommand is None: await ctx.reply(f'{ctx.author.mention}, invalid admin command')
        return

    @commands.is_owner()
    @admin.command(hidden=True, usage='admin status <text>', description='set bot\'s status.')
    async def status(self, ctx, *, msg: str):
        await self.bot.wait_until_ready()
        game = disnake.Game(name=msg)
        await self.bot.change_presence(status=disnake.Status.online, activity=game)
        msg = f'{ctx.author.mention}, changed status to: {msg}'
        await ctx.reply(msg)
        return

    @commands.is_owner()
    @admin.command(hidden=True, usage='admin ada <action> [param]', description='ADA\'s action')
    async def ada(self, ctx, action: str, param: str=None):
        action = action.upper()
        if action == "CREATE":
            async def call_ada_wallet(url: str, wallet_name: str, seeds: str, number: int, timeout=60):
                try:
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    data_json = { "mnemonic_sentence": seeds, "passphrase": config.ada.default_passphrase, "name": wallet_name, "address_pool_gap": number }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, headers=headers, json=data_json, timeout=timeout) as response:
                            if response.status == 200 or response.status == 201:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                decoded_data = json.loads(res_data)
                                return decoded_data
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                return None
            
            if param is None:
                msg = f'{ctx.author.mention}, this action requires <param> (number)!'
                await ctx.reply(msg)
                return
            else:
                try:
                    wallet_name=param.split(".")[0]
                    number=int(param.split(".")[1])
                    # Check if wallet_name exist
                    try:
                        await store.openConnection()
                        async with store.pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                sql = """ SELECT * FROM `ada_wallets` WHERE `wallet_name`=%s LIMIT 1 """               
                                await cur.execute(sql, ( wallet_name ))
                                result = await cur.fetchone()
                                if result:
                                    msg = f'{ctx.author.mention}, wallet `{wallet_name}` already exist!'
                                    await ctx.reply(msg)
                                    return
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        return

                    # param "wallet_name.number"
                    mnemo = Mnemonic("english")
                    words = str(mnemo.generate(strength=256))
                    seeds = words.split()
                    create = await call_ada_wallet(config.ada.default_wallet_url + "v2/wallets", wallet_name, seeds, number, 300)
                    if create:
                        try:
                            await store.openConnection()
                            async with store.pool.acquire() as conn:
                                async with conn.cursor() as cur:
                                    wallet_d = create['id']
                                    sql = """ INSERT INTO `ada_wallets` (`wallet_rpc`, `passphrase`, `wallet_name`, `wallet_id`, `seed`) VALUES (%s, %s, %s, %s, %s) """               
                                    await cur.execute(sql, ( config.ada.default_wallet_url, encrypt_string(config.ada.default_passphrase), wallet_name, wallet_d, encrypt_string(words) ))
                                    await conn.commit()
                                    msg = f'{ctx.author.mention}, wallet `{wallet_name}` created with number `{number}` and wallet ID: `{wallet_d}`.'
                                    await ctx.reply(msg)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    msg = f'{ctx.author.mention}, invalid <param> (wallet_name.number)!'
                    await ctx.reply(msg)
                    return
        elif action == "MOVE" or action == "MV": # no param, move from all deposit balance to withdraw
            async def fetch_wallet_status(url, timeout):
                try:
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers=headers, timeout=timeout) as response:
                            if response.status == 200:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                decoded_data = json.loads(res_data)
                                return decoded_data
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                return None

            async def estimate_fee_with_asset(url: str, to_address: str, assets, amount_atomic: int, timeout: int=90):
                # assets: list of asset
                try:
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    data_json = {"payments": [{"address": to_address, "amount": {"quantity": 0, "unit": "lovelace"}, "assets": assets}], "withdrawal": "self"}
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, headers=headers, json=data_json, timeout=timeout) as response:
                            if response.status == 202:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                decoded_data = json.loads(res_data)
                                return decoded_data
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                return None

            async def send_tx(url: str, to_address: str, ada_atomic_amount: int, assets, passphrase: str, timeout: int=90):
                try:
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    data_json = {"passphrase": decrypt_string(passphrase), "payments": [{"address": to_address, "amount": {"quantity": ada_atomic_amount, "unit": "lovelace"}, "assets": assets}], "withdrawal": "self"}
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, headers=headers, json=data_json, timeout=timeout) as response:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            decoded_data = json.loads(res_data)
                            return decoded_data
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                return None
            try:
                await store.openConnection()
                async with store.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ SELECT * FROM `ada_wallets` """               
                        await cur.execute(sql,)
                        result = await cur.fetchall()
                        if result and len(result) > 0:
                            withdraw_address = None
                            has_deposit = False
                            for each_w in result:
                                if each_w['wallet_name'] == "withdraw_ada" and each_w['is_for_withdraw'] == 1:
                                    addresses = each_w['addresses'].split("\n")
                                    random.shuffle(addresses)
                                    withdraw_address = addresses[0]
                            for each_w in result:
                                if each_w['is_for_withdraw'] != 1 and each_w['used_address'] > 0 and withdraw_address is not None:
                                    # fetch wallet_id only those being used.
                                    try:
                                        fetch_wallet = await fetch_wallet_status(each_w['wallet_rpc'] + "v2/wallets/" + each_w['wallet_id'], 60)
                                        if fetch_wallet and fetch_wallet['state']['status'] == "ready":
                                            # we will move only those synced
                                            # minimum ADA: 20
                                            min_balance = 20*10**6
                                            reserved_balance = 1*10**6
                                            amount = fetch_wallet['balance']['available']['quantity']
                                            if amount < min_balance:
                                                continue
                                            else:
                                                assets = []
                                                if 'available' in fetch_wallet['assets'] and len(fetch_wallet['assets']['available']) > 0:
                                                    for each_asset in fetch_wallet['assets']['available']:
                                                        # Check if they are in TipBot
                                                        for each_coin in self.bot.coin_name_list:
                                                            if getattr(getattr(self.bot.coin_list, each_coin), "type") == "ADA" and getattr(getattr(self.bot.coin_list, each_coin), "header") == each_asset['asset_name']:
                                                                # We have it
                                                                policy_id = getattr(getattr(self.bot.coin_list, each_coin), "contract")
                                                                assets.append({"policy_id": policy_id, "asset_name": each_asset['asset_name'], "quantity": each_asset['quantity']})
                                                # async def estimate_fee_with_asset(url: str, to_address: str, assets, amount_atomic: int, timeout: int=90):
                                                estimate_tx = await estimate_fee_with_asset(each_w['wallet_rpc']+ "v2/wallets/" + each_w['wallet_id'] + "/payment-fees", withdraw_address, assets, amount, 10)
                                                if estimate_tx and "minimum_coins" in estimate_tx and "estimated_min" in estimate_tx:
                                                    sending_tx = await send_tx(each_w['wallet_rpc'] + "v2/wallets/" + each_w['wallet_id'] + "/transactions", withdraw_address, amount-estimate_tx['estimated_min']['quantity']-reserved_balance, assets, each_w['passphrase'], 30)
                                                    if "code" in sending_tx and "message" in sending_tx:
                                                        # send error
                                                        wallet_id = each_w['wallet_id']
                                                        msg = f'{ctx.author.mention}, error with `{wallet_id}`\n````{str(sending_tx)}``'
                                                        await ctx.reply(msg)
                                                        print(msg)
                                                    elif "status" in sending_tx and sending_tx['status'] == "pending":
                                                        has_deposit = True
                                                        # success
                                                        wallet_id = each_w['wallet_id']
                                                        tx_hash = sending_tx['id']
                                                        msg = f'{ctx.author.mention}, successfully transfer `{wallet_id}` to `{withdraw_address}` via `{tx_hash}`.'
                                                        await ctx.reply(msg)
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                            if has_deposit == False:
                                msg = f'{ctx.author.mention}, there is no any wallet with balance sufficient to transfer.!'
                                await ctx.reply(msg)
                                return
                        else:
                            msg = f'{ctx.author.mention}, doesnot have any wallet in DB!'
                            await ctx.reply(msg)
                            return
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        elif action == "DELETE" or action == "DEL": # param is name only
            if param is None:
                msg = f'{ctx.author.mention}, required param `wallet_name`!'
                await ctx.reply(msg)
                return
            async def call_ada_delete_wallet(url_wallet_id: str, timeout=60):
                try:
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.delete(url_wallet_id, headers=headers, timeout=timeout) as response:
                            if response.status == 204:
                                return True
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                return None
            wallet_name=param.strip()
            wallet_id=None
            # Check if wallet_name exist
            try:
                await store.openConnection()
                async with store.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ SELECT * FROM `ada_wallets` WHERE `wallet_name`=%s LIMIT 1 """               
                        await cur.execute(sql, ( wallet_name ))
                        result = await cur.fetchone()
                        if result:
                            wallet_id = result['wallet_id']
                            delete = await call_ada_delete_wallet(config.ada.default_wallet_url + "v2/wallets/" + wallet_id, 300)
                            if delete == True:
                                try:
                                    await store.openConnection()
                                    async with store.pool.acquire() as conn:
                                        async with conn.cursor() as cur:
                                            sql = """ INSERT INTO `ada_wallets_archive` 
                                                      SELECT * FROM `ada_wallets` 
                                                      WHERE `wallet_id`=%s;
                                                      DELETE FROM `ada_wallets` WHERE `wallet_id`=%s LIMIT 1 """               
                                            await cur.execute(sql, ( wallet_id, wallet_id ))
                                            await conn.commit()
                                            msg = f'{ctx.author.mention}, sucessfully delete wallet `{wallet_name}` | `{wallet_id}`.'
                                            await ctx.reply(msg)
                                            return
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                            else:
                                msg = f'{ctx.author.mention}, failed to delete `{wallet_name}` | `{wallet_id}` from wallet server!'
                                await ctx.reply(msg)
                                return
                        else:
                            msg = f'{ctx.author.mention}, wallet `{wallet_name}` not exist in database!'
                            await ctx.reply(msg)
                            return
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                return
        elif action == "LIST": # no params
            # List all in DB
            try:
                await store.openConnection()
                async with store.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ SELECT * FROM `ada_wallets` """               
                        await cur.execute(sql,)
                        result = await cur.fetchall()
                        if result and len(result) > 0:
                            list_wallets = []
                            for each_w in result:
                                list_wallets.append("Name: {}, ID: {}".format(each_w['wallet_name'], each_w['wallet_id']))
                            list_wallets_j = "\n".join(list_wallets)
                            data_file = disnake.File(BytesIO(list_wallets_j.encode()), filename=f"list_ada_wallets_{str(int(time.time()))}.csv")
                            await ctx.author.send(file=data_file)
                            return
                        else:
                            msg = f'{ctx.author.mention}, nothing in DB!'
                            await ctx.reply(msg)
                            return
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                return
        else:
            msg = f'{ctx.author.mention}, action not exist!'
            await ctx.reply(msg)


    @commands.is_owner()
    @admin.command(hidden=True, usage='admin guildlist', description='Dump guild list, name, number of users.')
    async def guildlist(self, ctx):
        try:
            list_g = []
            for g in self.bot.guilds:
                list_g.append("{}, {}, {}".format(str(g.id), len(g.members), g.name))
            list_g_str = "ID, Numbers, Name\n" + "\n".join(list_g)
            data_file = disnake.File(BytesIO(list_g_str.encode()), filename=f"list_bot_guilds_{str(int(time.time()))}.csv")
            await ctx.author.send(file=data_file)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    @commands.is_owner()
    @admin.command(hidden=True, usage='admin clearbutton <channel id> <msg id>', description='Clear all buttons of a message ID.')
    async def clearbutton(self, ctx, channel_id: str, msg_id: str):
        try:
            _channel: disnake.TextChannel = await self.bot.fetch_channel(int(channel_id))
            _msg: disnake.Message = await _channel.fetch_message(int(msg_id))
            if _msg is not None:
                if _msg.author != self.bot.user:
                    msg = f'{ctx.author.mention}, that message `{msg_id}` was not belong to me.'
                    await ctx.reply(msg)
                else:
                    await _msg.edit(view=None)
                    msg = f'{ctx.author.mention}, removed all view from `{msg_id}`.'
                    await ctx.reply(msg)
            else:
                msg = f'{ctx.author.mention}, I can not find message `{msg_id}`.'
                await ctx.reply(msg)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.is_owner()
    @admin.command(hidden=True, usage='admin leave <guild id>', description='Bot to leave a server by ID.')
    async def leave(self, ctx, guild_id: str):
        try:
            guild = self.bot.get_guild(int(guild_id))
            if guild is not None:
                await logchanbot(f"[LEAVING] {ctx.author.name}#{ctx.author.discriminator} / {str(ctx.author.id)} commanding to leave guild `{guild.name} / {guild_id}`.")
                msg = f'{ctx.author.mention}, OK leaving guild `{guild.name} / {guild_id}`.'
                await ctx.reply(msg)
                await guild.leave()
            else:
                msg = f'{ctx.author.mention}, I can not find guild id `{guild_id}`.'
                await ctx.reply(msg)
            return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    @commands.is_owner()
    @admin.command(hidden=True, usage='auditcoin <coin name>', description='Audit coin\'s balance')
    async def auditcoin(self, ctx, coin: str):
        COIN_NAME = coin.upper()
        if not hasattr(self.bot.coin_list, COIN_NAME):
            msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
            await ctx.reply(msg)
            return
        else:
            try:
                type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
                coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
                height = None
                try:
                    if type_coin in ["ERC-20", "TRC-20"]:
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
                    else:
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                        
                all_user_id = await self.sql_get_all_userid_by_coin(COIN_NAME)
                time_start = int(time.time())
                list_users = [m.id for m in self.bot.get_all_members()]
                list_guilds = [g.id for g in self.bot.guilds]
                if len(all_user_id) > 0:
                    msg = f'{ctx.author.mention}, {EMOJI_INFORMATION} **{COIN_NAME}** there are total {str(len(all_user_id))} user records. Wait a big while...'
                    await ctx.reply(msg)
                    sum_balance = 0.0
                    sum_user = 0
                    sum_unfound_balance = 0.0
                    sum_unfound_user = 0
                    User_WalletAPI = WalletAPI(self.bot)
                    for each_user_id in all_user_id:
                        get_deposit = await User_WalletAPI.sql_get_userwallet(each_user_id['user_id'], COIN_NAME, net_name, type_coin, each_user_id['user_server'], each_user_id['chat_id'] if each_user_id['chat_id'] else 0)
                        if get_deposit is None:
                            continue
                        wallet_address = get_deposit['balance_wallet_address']
                        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                            wallet_address = get_deposit['paymentid']
                        userdata_balance = await self.user_balance(each_user_id['user_id'], COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, each_user_id['user_server'])
                        total_balance = userdata_balance['adjust']
                        sum_balance += total_balance
                        sum_user += 1
                        try:
                            if each_user_id['user_id'].isdigit() and each_user_id['user_server'] == SERVER_BOT and each_user_id['is_discord_guild'] == 0:
                                if int(each_user_id['user_server']) not in list_users:
                                    sum_unfound_user += 1
                                    sum_unfound_balance += total_balance
                            elif each_user_id['user_id'].isdigit() and each_user_id['user_server'] == SERVER_BOT and each_user_id['is_discord_guild'] == 1:
                                if int(each_user_id['user_server']) not in list_guilds:
                                    sum_unfound_user += 1
                                    sum_unfound_balance += total_balance
                        except Exception as e:
                            pass

                    duration = int(time.time()) - time_start
                    msg_checkcoin = f"{ctx.author.mention}, COIN **{COIN_NAME}**\n"
                    msg_checkcoin += "```"
                    wallet_stat_str = ""
                    if type_coin == "ADA":
                        try:
                            await store.openConnection()
                            async with store.pool.acquire() as conn:
                                async with conn.cursor() as cur:
                                    sql = """ SELECT * FROM `ada_wallets` """               
                                    await cur.execute(sql,)
                                    result = await cur.fetchall()
                                    if result and len(result) > 0:
                                        wallet_stat = []
                                        for each_w in result:
                                            wallet_stat.append("name: {}, syncing: {}, height: {}, addr. used {:,.2f}{}".format(each_w['wallet_name'], each_w['syncing'], each_w['height'], each_w['used_address']/each_w['address_pool_gap']*100, "%"))
                                        wallet_stat_str = "\n".join(wallet_stat)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                    msg_checkcoin +=  wallet_stat_str + "\n"     
                    msg_checkcoin += "Total record id in DB: " + str(sum_user) + "\n"
                    msg_checkcoin += "Total balance: " + num_format_coin(sum_balance, COIN_NAME, coin_decimal, False) + " " + COIN_NAME + "\n"
                    msg_checkcoin += "Total user/guild not found (discord): " + str(sum_unfound_user) + "\n"
                    msg_checkcoin += "Total balance not found (discord): " + num_format_coin(sum_unfound_balance, COIN_NAME, coin_decimal, False) + " " + COIN_NAME + "\n"
                    msg_checkcoin += "Time token: {}s".format(duration)
                    msg_checkcoin += "```"
                    if len(msg_checkcoin) > 1000:
                        data_file = disnake.File(BytesIO(msg_checkcoin.encode()), filename=f"auditcoin_{COIN_NAME}_{str(int(time.time()))}.txt")
                        await ctx.reply(file=data_file)
                    else:
                        await ctx.reply(msg_checkcoin)
                else:
                    msg = f'{ctx.author.mention}, {COIN_NAME}: there is no users for this.'
                    await ctx.reply(msg)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        

    @commands.is_owner()
    @admin.command(hidden=True, usage='printbal <user> <coin>', description='print user\'s balance.')
    async def printbal(self, ctx, member_id: str, coin: str, user_server: str="DISCORD"):
        COIN_NAME = coin.upper()
        if member_id.upper() == "SWAP":
            member_id = member_id.upper()
            user_server = "SYSTEM"
        else:
            user_server = user_server.upper()
        try:
            if not hasattr(self.bot.coin_list, COIN_NAME):
                await ctx.reply(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
                return
            type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
            net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
            User_WalletAPI = WalletAPI(self.bot)
            get_deposit = await User_WalletAPI.sql_get_userwallet(member_id, COIN_NAME, net_name, type_coin, user_server, 0)
            if get_deposit is None:
                get_deposit = await User_WalletAPI.sql_register_user(member_id, COIN_NAME, net_name, type_coin, user_server, 0, 0)
            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']

            height = None
            try:
                if type_coin in ["ERC-20", "TRC-20"]:
                    # Add update for future call
                    try:
                        if type_coin == "ERC-20":
                            update_call = await store.sql_update_erc20_user_update_call(member_id)
                        elif type_coin == "TRC-10" or type_coin == "TRC-20":
                            update_call = await store.sql_update_trc20_user_update_call(member_id)
                        elif type_coin == "SOL" or type_coin == "SPL":
                            update_call = await store.sql_update_sol_user_update_call(member_id)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                    height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
                else:
                    height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
                userdata_balance = await self.user_balance(member_id, COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, user_server)
                total_balance = userdata_balance['adjust']
                balance_str = "UserId: {}\n{}{} Details:\n{}".format(member_id, total_balance, COIN_NAME, json.dumps(userdata_balance))
                await ctx.reply(balance_str)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.is_owner()
    @admin.command(hidden=True, usage='baluser <user>', description='Check user balances')
    async def baluser(self, ctx, member_id: str, user_server: str="DISCORD"):
        if member_id.upper() == "SWAP":
            member_id = member_id.upper()
            user_server = "SYSTEM"
        else:
            user_server = user_server.upper()
        try:
            zero_tokens = []
            has_none_balance = True
            mytokens = await store.get_coin_settings(coin_type=None)
            total_all_balance_usd = 0.0
            all_pages = []
            all_names = [each['coin_name'] for each in mytokens]
            total_coins = len(mytokens)
            page = disnake.Embed(title=f'[ BALANCE LIST {member_id} ]',
                                  color=disnake.Color.blue(),
                                  timestamp=datetime.now(), )
            page.add_field(name="Coin/Tokens: [{}]".format(len(all_names)), 
                           value="```"+", ".join(all_names)+"```", inline=False)
            page.set_thumbnail(url=ctx.author.display_avatar)
            page.set_footer(text="Use the reactions to flip pages.")
            all_pages.append(page)
            num_coins = 0
            per_page = 8
            tmp_msg = await ctx.reply(f"{ctx.author.mention} balance loading...")
            for each_token in mytokens:
                COIN_NAME = each_token['coin_name']
                type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
                coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
                usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
                User_WalletAPI = WalletAPI(self.bot)
                get_deposit = await User_WalletAPI.sql_get_userwallet(member_id, COIN_NAME, net_name, type_coin, user_server, 0)
                if get_deposit is None:
                    get_deposit = await User_WalletAPI.sql_register_user(member_id, COIN_NAME, net_name, type_coin, user_server, 0, 0)
                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']

                height = None
                try:
                    if type_coin in ["ERC-20", "TRC-20"]:
                        # Add update for future call
                        try:
                            if type_coin == "ERC-20":
                                update_call = await store.sql_update_erc20_user_update_call(member_id)
                            elif type_coin == "TRC-10" or type_coin == "TRC-20":
                                update_call = await store.sql_update_trc20_user_update_call(member_id)
                            elif type_coin == "SOL" or type_coin == "SPL":
                                update_call = await store.sql_update_sol_user_update_call(member_id)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
                    else:
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)

                if num_coins == 0 or num_coins % per_page == 0:
                    page = disnake.Embed(title=f'[ BALANCE LIST {member_id} ]',
                                         description="Thank you for using TipBot!",
                                         color=disnake.Color.blue(),
                                         timestamp=datetime.now(), )
                    page.set_thumbnail(url=ctx.author.display_avatar)
                    page.set_footer(text="Use the reactions to flip pages.")
                # height can be None
                userdata_balance = await self.user_balance(member_id, COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, user_server)
                total_balance = userdata_balance['adjust']
                if total_balance == 0:
                    zero_tokens.append(COIN_NAME)
                    continue
                elif total_balance > 0:
                    has_none_balance = False
                equivalent_usd = ""
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
                        total_in_usd = float(Decimal(total_balance) * Decimal(per_unit))
                        total_all_balance_usd += total_in_usd
                        if total_in_usd >= 0.01:
                            equivalent_usd = " ~ {:,.2f}$".format(total_in_usd)
                        elif total_in_usd >= 0.0001:
                            equivalent_usd = " ~ {:,.4f}$".format(total_in_usd)
                         
                page.add_field(name="{}{}".format(token_display, equivalent_usd) , value="```{}```".format(num_format_coin(total_balance, COIN_NAME, coin_decimal, False)), inline=True)
                num_coins += 1
                if num_coins > 0 and num_coins % per_page == 0:
                    all_pages.append(page)
                    if num_coins < total_coins - len(zero_tokens):
                        page = disnake.Embed(title=f'[ BALANCE LIST {member_id} ]',
                                             description="Thank you for using TipBot!",
                                             color=disnake.Color.blue(),
                                             timestamp=datetime.now(), )
                        page.set_thumbnail(url=ctx.author.display_avatar)
                        page.set_footer(text="Use the reactions to flip pages.")
                    else:
                        all_pages.append(page)
                        break
                elif num_coins == total_coins:
                    all_pages.append(page)
                    break
            # remaining
            if (total_coins - len(zero_tokens)) % per_page > 0:
                all_pages.append(page)
            # Replace first page
            if total_all_balance_usd > 0.01:
                total_all_balance_usd = "Having ~ {:,.2f}$".format(total_all_balance_usd)
            elif total_all_balance_usd > 0.0001:
                total_all_balance_usd = "Having ~ {:,.4f}$".format(total_all_balance_usd)
            else:
                total_all_balance_usd = "Thank you for using TipBot!"
            page = disnake.Embed(title=f'[ BALANCE LIST {member_id} ]',
                                  description=f"`{total_all_balance_usd}`",
                                  color=disnake.Color.blue(),
                                  timestamp=datetime.now(), )
            # Remove zero from all_names
            if has_none_balance == True:
                msg = f'{member_id} does not have any balance.'
                await ctx.reply(msg)
                return
            else:
                all_names = [each for each in all_names if each not in zero_tokens]
                page.add_field(name="Coin/Tokens: [{}]".format(len(all_names)), 
                               value="```"+", ".join(all_names)+"```", inline=False)
                if len(zero_tokens) > 0:
                    zero_tokens = list(set(zero_tokens))
                    page.add_field(name="Zero Balances: [{}]".format(len(zero_tokens)), 
                                   value="```"+", ".join(zero_tokens)+"```", inline=False)
                page.set_thumbnail(url=ctx.author.display_avatar)
                page.set_footer(text="Use the reactions to flip pages.")
                all_pages[0] = page

                view = MenuPage(ctx, all_pages, timeout=30)
                await tmp_msg.delete()
                view.message = await ctx.reply(content=None, embed=all_pages[0], view=view)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.is_owner()
    @admin.command(hidden=True, usage='pending', description='Check pending things')
    async def pending(self, ctx):
        ts = datetime.utcnow()
        embed = disnake.Embed(title='Pending Actions', timestamp=ts)
        embed.add_field(name="Pending Tx", value=str(len(self.bot.TX_IN_PROCESS)), inline=True)
        if len(self.bot.TX_IN_PROCESS) > 0:
            string_ints = [str(num) for num in self.bot.TX_IN_PROCESS]
            list_pending = '{' + ', '.join(string_ints) + '}'
            embed.add_field(name="List Pending By", value=list_pending, inline=True)

        embed.add_field(name="GAME_INTERACTIVE", value=str(len(self.bot.GAME_INTERACTIVE_PRGORESS)), inline=True)
        embed.add_field(name="GAME_INTERACTIVE_ECO", value=str(len(self.bot.GAME_INTERACTIVE_ECO)), inline=True)
        embed.add_field(name="GAME_SLOT", value=str(len(self.bot.GAME_SLOT_IN_PRGORESS)), inline=True)
        embed.add_field(name="GAME_DICE", value=str(len(self.bot.GAME_DICE_IN_PRGORESS)), inline=True)
        embed.add_field(name="GAME_MAZE", value=str(len(self.bot.GAME_MAZE_IN_PROCESS)), inline=True)
        embed.set_footer(text=f"Pending requested by {ctx.author.name}#{ctx.author.discriminator}")
        try:
            await ctx.reply(embed=embed)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return


    @commands.is_owner()
    @admin.command(hidden=True, usage='withdraw <coin>', description='Enable/Disable withdraw for a coin')
    async def withdraw(self, ctx, coin: str):
        COIN_NAME = coin.upper()
        command = "withdraw"
        if not hasattr(self.bot.coin_list, COIN_NAME):
            msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
            await ctx.reply(msg)
            return
        else:
            enable_withdraw = getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_withdraw")
            new_value = 1
            new_text = "enable"
            if enable_withdraw == 1:
                new_value = 0
                new_text = "disable"
            toggle = await self.enable_disable_coin(COIN_NAME, command, new_value)
            if toggle > 0:
                msg = f"{ctx.author.mention}, **{COIN_NAME}** `{command}` is `{new_text}` now."
                await ctx.reply(msg)
            else:
                msg = f"{ctx.author.mention}, **{COIN_NAME}** `{command}` is `{new_text}` failed to update."
                await ctx.reply(msg)
            coin_list = await self.get_coin_setting()
            if coin_list:
                self.bot.coin_list = coin_list
            coin_list_name = await self.get_coin_list_name()
            if coin_list_name:
                self.bot.coin_name_list = coin_list_name

    @commands.is_owner()
    @admin.command(hidden=True, usage='tip  <coin>', description='Enable/Disable tip for a coin')
    async def tip(self, ctx, coin: str):
        COIN_NAME = coin.upper()
        command = "tip"
        if not hasattr(self.bot.coin_list, COIN_NAME):
            msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
            await ctx.reply(msg)
            return
        else:
            enable_tip = getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_tip")
            new_value = 1
            new_text = "enable"
            if enable_tip == 1:
                new_value = 0
                new_text = "disable"
            toggle = await self.enable_disable_coin(COIN_NAME, command, new_value)
            if toggle > 0:
                msg = f"{ctx.author.mention}, **{COIN_NAME}** `{command}` is `{new_text}` now."
                await ctx.reply(msg)
            else:
                msg = f"{ctx.author.mention}, **{COIN_NAME}** `{command}` is `{new_text}` failed to update."
                await ctx.reply(msg)
            coin_list = await self.get_coin_setting()
            if coin_list:
                self.bot.coin_list = coin_list
            coin_list_name = await self.get_coin_list_name()
            if coin_list_name:
                self.bot.coin_name_list = coin_list_name

    @commands.is_owner()
    @admin.command(hidden=True, usage='deposit  <coin>', description='Enable/Disable deposit for a coin')
    async def deposit(self, ctx, coin: str):
        COIN_NAME = coin.upper()
        command = "deposit"
        if not hasattr(self.bot.coin_list, COIN_NAME):
            msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
            await ctx.reply(msg)
            return
        else:
            enable_deposit = getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_deposit")
            new_value = 1
            new_text = "enable"
            if enable_deposit == 1:
                new_value = 0
                new_text = "disable"
            toggle = await self.enable_disable_coin(COIN_NAME, command, new_value)
            if toggle > 0:
                msg = f"{ctx.author.mention}, **{COIN_NAME}** `{command}` is `{new_text}` now."
                await ctx.reply(msg)
            else:
                msg = f"{ctx.author.mention}, **{COIN_NAME}** `{command}` is `{new_text}` failed to update."
                await ctx.reply(msg)
            coin_list = await self.get_coin_setting()
            if coin_list:
                self.bot.coin_list = coin_list
            coin_list_name = await self.get_coin_list_name()
            if coin_list_name:
                self.bot.coin_name_list = coin_list_name

    @commands.is_owner()
    @commands.command(hidden=True, usage='cleartx', description='Clear TX_IN_PROCESS')
    async def cleartx(self, ctx):
        if len(self.bot.TX_IN_PROCESS) == 0:
            await ctx.reply(f'{ctx.author.mention} TX_IN_PROCESS, nothing in tx pending to clear.')
        else:
            try:
                string_ints = [str(num) for num in self.bot.TX_IN_PROCESS]
                list_pending = '{' + ', '.join(string_ints) + '}'
                await ctx.reply(f'Clearing {str(len(self.bot.TX_IN_PROCESS))} {list_pending} in pending...')
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            self.bot.TX_IN_PROCESS = []
        # GAME_INTERACTIVE_ECO
        if len(self.bot.GAME_INTERACTIVE_ECO) == 0:
            await ctx.reply(f'{ctx.author.mention}, GAME_INTERACTIVE_ECO nothing in tx pending to clear.')
        else:
            try:
                string_ints = [str(num) for num in self.bot.GAME_INTERACTIVE_ECO]
                list_pending = '{' + ', '.join(string_ints) + '}'
                await ctx.reply(f'Clearing {str(len(self.bot.GAME_INTERACTIVE_ECO))} {list_pending} in pending...')
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            self.bot.GAME_INTERACTIVE_ECO = []
        # GAME_INTERACTIVE_PRGORESS
        if len(self.bot.GAME_INTERACTIVE_PRGORESS) == 0:
            await ctx.reply(f'{ctx.author.mention}, GAME_INTERACTIVE_PRGORESS nothing in tx pending to clear.')
        else:
            try:
                string_ints = [str(num) for num in self.bot.GAME_INTERACTIVE_PRGORESS]
                list_pending = '{' + ', '.join(string_ints) + '}'
                await ctx.reply(f'Clearing {str(len(self.bot.GAME_INTERACTIVE_PRGORESS))} {list_pending} in pending...')
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            self.bot.GAME_INTERACTIVE_PRGORESS = []
        return


    @commands.is_owner()
    @admin.command(
        usage="eval <expression>", 
        description="Do some eval."
    )
    async def eval(
        self, 
        ctx, 
        *, 
        code
    ):
        if config.discord.enable_eval != 1:
            return

        str_obj = io.StringIO() #Retrieves a stream of data
        try:
            with contextlib.redirect_stdout(str_obj):
                exec(code)
        except Exception as e:
            return await ctx.reply(f"```{e.__class__.__name__}: {e}```")
        await ctx.reply(f'```{str_obj.getvalue()}```')


    @commands.is_owner()
    @admin.command(hidden=True, usage='create', description='Create an address')
    async def create(self, ctx, token: str):
        if token.upper() not in ["ERC-20", "TRC-20"]:
            await ctx.reply(f'{ctx.author.mention}, only with ERC-20 and TRC-20.')
            return
        elif token.upper() == "ERC-20":
            w = await self.create_address_eth()
            await ctx.reply(f'{ctx.author.mention}, ```{str(w)}```', view=RowButton_row_close_any_message())
            return
        elif token.upper() == "TRC-20":
            w = await self.create_address_trx()
            await ctx.reply(f'{ctx.author.mention}, ```{str(w)}```', view=RowButton_row_close_any_message())
            return


    @commands.is_owner()
    @admin.command(
        usage="encrypt <expression>", 
        description="Encrypt text."
    )
    async def encrypt(
        self, 
        ctx, 
        *, 
        text
    ):
        encrypt = encrypt_string(text)
        if encrypt: return await ctx.reply(f"```{encrypt}```", view=RowButton_row_close_any_message())


    @commands.is_owner()
    @admin.command(
        usage="decrypt <expression>", 
        description="Decrypt text."
    )
    async def decrypt(
        self, 
        ctx, 
        *, 
        text
    ):
        decrypt = decrypt_string(text)
        if decrypt: return await ctx.reply(f"```{decrypt}```", view=RowButton_row_close_any_message())


def setup(bot):
    bot.add_cog(Admin(bot))
