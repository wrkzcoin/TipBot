#!/usr/bin/python3.8
from typing import List, Dict
import asyncio, aiohttp
from aiohttp import web
import time, json
import store
import sys, traceback
# eth erc
from eth_account import Account
from decimal import Decimal

from config import config
from wallet import *
# redis
import redis

redis_pool = None
redis_conn = None
redis_expired = 120

ENABLE_TRADE_COIN = config.trade.enable_coin.split(",")

ENABLE_COIN = config.Enable_Coin.split(",")
ENABLE_COIN_DOGE = config.Enable_Coin_Doge.split(",")
ENABLE_XMR = config.Enable_Coin_XMR.split(",")
ENABLE_XCH = config.Enable_Coin_XCH.split(",")
ENABLE_COIN_NANO = config.Enable_Coin_Nano.split(",")
ENABLE_COIN_ERC = config.Enable_Coin_ERC.split(",")
ENABLE_COIN_TRC = config.Enable_Coin_TRC.split(",")
MAINTENANCE_COIN = config.Maintenance_Coin.split(",")
MIN_TRADE_RATIO = float(config.trade.Min_Ratio)
TRADE_PERCENT = config.trade.Trade_Margin
SERVER_BOT = "TRADE_API"

CF = True


def init():
    global redis_pool
    print("PID %d: initializing redis pool..." % os.getpid())
    redis_pool = redis.ConnectionPool(host='localhost', port=6379, decode_responses=True, db=8)


def openRedis():
    global redis_pool, redis_conn
    if redis_conn is None:
        try:
            redis_conn = redis.Redis(connection_pool=redis_pool)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


async def logchanbot(content: str):
    filterword = config.discord.logfilterword.split(",")
    for each in filterword:
        content = content.replace(each, config.discord.filteredwith)
    if len(content) > 1500: content = content[:1500]
    try:
        webhook = DiscordWebhook(url=config.discord.botdbghook, content=content)
        webhook.execute()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def tradeapi_webhook(content: str):
    if len(content) > 1999: content = content[:1999]
    try:
        webhook = DiscordWebhook(url=config.discord.tradehook, content=content)
        webhook.execute()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


## Section of Trade
## TO DO: merge functions to a place
def get_min_sell(coin: str, token_info = None):
    COIN_NAME = coin.upper()
    if COIN_NAME in ENABLE_COIN_ERC+ENABLE_COIN_TRC:
        return token_info['min_buysell']
    else:
        return getattr(config,"daemon"+coin,config.daemonWRKZ).min_buysell

def get_max_sell(coin: str, token_info = None):
    COIN_NAME = coin.upper()
    if COIN_NAME in ENABLE_COIN_ERC+ENABLE_COIN_TRC:
        return token_info['max_buysell']
    else:
        return getattr(config,"daemon"+coin,config.daemonWRKZ).max_buysell
## END OF Section of Trade

# Create ETH
def create_eth_wallet():
    Account.enable_unaudited_hdwallet_features()
    acct, mnemonic = Account.create_with_mnemonic()
    return {'address': acct.address, 'seed': mnemonic, 'private_key': acct.privateKey.hex()}


def is_tradeable_coin(coin: str):
    global redis_conn, redis_expired
    COIN_NAME = coin.upper()

    # Check if exist in redis
    try:
        openRedis()
        key = config.redis_setting.prefix_coin_setting + COIN_NAME + '_TRADEABLE'
        if redis_conn and redis_conn.exists(key):
            return True
        else:
            return False
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def is_maintenance_coin(coin: str):
    global redis_conn, redis_expired, MAINTENANCE_COIN
    COIN_NAME = coin.upper()
    if COIN_NAME in MAINTENANCE_COIN:
        return True
    # Check if exist in redis
    try:
        openRedis()
        key = config.redis_setting.prefix_coin_setting + COIN_NAME + '_MAINT'
        if redis_conn and redis_conn.exists(key):
            return True
        else:
            return False
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def handle_get_all(request):
    global CF, ENABLE_TRADE_COIN, ENABLE_COIN, ENABLE_COIN_DOGE, ENABLE_XMR, ENABLE_XCH, ENABLE_COIN_NANO, ENABLE_COIN_ERC, ENABLE_COIN_TRC
    check_auth = None
    userid = ""
    client_ip = request.headers.get('X-Real-IP', None)
    if CF:
        # if cloudflare
        client_ip = request.headers.get('X-Forwarded-For', None)
    if 'authorization-user' in request.headers and 'authorization-key' in request.headers:
        userid = request.headers['authorization-user']
        key = request.headers['authorization-key']
        check_auth = await store.check_header(userid, key)
    if check_auth is None:
        try:
            print('Denied client ip: {} / {} / requested {}'.format(client_ip, request.headers.get('cf-ipcountry', None), request.rel_url))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return await respond_unauthorized_request()

    if CF:
        try:
            print('Client ip: {} / {} / Browser: {} requested {}'.format(client_ip, request.headers.get('cf-ipcountry', None), request.headers.get('User-Agent', None), request.rel_url))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    uri = str(request.rel_url).lower()
    if uri.startswith("/get_balance/"):
        # there is coin after
        COIN_NAME = uri.replace("/get_balance/", "").upper().replace("/", "")
        if COIN_NAME not in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC+ENABLE_COIN_TRC+ENABLE_XCH:
            return await respond_bad_request()
        else:
            wallet = await store.sql_get_userwallet(userid, COIN_NAME)
            if wallet is None:
                if COIN_NAME in ENABLE_COIN_ERC:
                    w = create_eth_wallet()
                    userregister = await store.sql_register_user(userid, COIN_NAME, 'DISCORD', 0, w)
                elif COIN_NAME in ENABLE_COIN_TRC:
                    result = await store.create_address_trx()
                    userregister = await store.sql_register_user(userid, COIN_NAME, 'DISCORD', 0, result)
                else:
                    userregister = await store.sql_register_user(userid, COIN_NAME, 'DISCORD', 0)
                wallet = await store.sql_get_userwallet(userid, COIN_NAME)
            userdata_balance = await store.sql_user_balance(userid, COIN_NAME)
            xfer_in = 0
            if COIN_NAME not in ENABLE_COIN_ERC+ENABLE_COIN_TRC:
                xfer_in = await store.sql_user_balance_get_xfer_in(userid, COIN_NAME)
            if COIN_NAME in ENABLE_COIN_DOGE+ENABLE_COIN_ERC+ENABLE_COIN_TRC:
                actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
            elif COIN_NAME in ENABLE_COIN_NANO:
                actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                actual_balance = round(actual_balance / get_decimal(COIN_NAME), 6) * get_decimal(COIN_NAME)
            else:
                actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
            balance_actual = num_format_coin(actual_balance, COIN_NAME)
            result = {"success": True, COIN_NAME: {"balance": balance_actual, "maintenance": True if is_maintenance_coin(COIN_NAME) else False}}
            # add to api call
            try:
                call = await store.api_trade_store(userid, uri)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            return web.Response(text=json.dumps(result).replace("\\", ""), status=200)
    elif uri.startswith("/deposit/"):
        # there is coin after
        COIN_NAME = uri.replace("/deposit/", "").upper().replace("/", "")
        if COIN_NAME not in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC+ENABLE_COIN_TRC+ENABLE_XCH:
            return await respond_bad_request()
        else:
            if COIN_NAME in ENABLE_COIN_ERC:
                coin_family = "ERC-20"
            elif COIN_NAME in ENABLE_COIN_TRC:
                coin_family = "TRC-20"
            else:
                try:
                    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
                except Exception as e:
                    return await respond_internal_error()
            if is_maintenance_coin(COIN_NAME):
                result = {"success": False, COIN_NAME: {"maintenance": True if is_maintenance_coin(COIN_NAME) else False}}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=500)

            if coin_family in ["TRTL", "BCN"]:
                wallet = await store.sql_get_userwallet(userid, COIN_NAME)
                if wallet is None:
                    userregister = await store.sql_register_user(userid, COIN_NAME, 'DISCORD', 0)
                    wallet = await store.sql_get_userwallet(userid, COIN_NAME)
            elif coin_family == "XMR":
                wallet = await store.sql_get_userwallet(userid, COIN_NAME)
                if wallet is None:
                    userregister = await store.sql_register_user(userid, COIN_NAME, 'DISCORD', 0)
                    wallet = await store.sql_get_userwallet(userid, COIN_NAME)
            elif coin_family == "XCH":
                wallet = await store.sql_get_userwallet(userid, COIN_NAME)
                if wallet is None:
                    userregister = await store.sql_register_user(userid, COIN_NAME, 'DISCORD', 0)
                    wallet = await store.sql_get_userwallet(userid, COIN_NAME)
            elif coin_family == "DOGE":
                wallet = await store.sql_get_userwallet(userid, COIN_NAME)
                if wallet is None:
                    wallet = await store.sql_register_user(userid, COIN_NAME, 'DISCORD', 0)
                    wallet = await store.sql_get_userwallet(userid, COIN_NAME)
            elif coin_family == "NANO":
                wallet = await store.sql_get_userwallet(userid, COIN_NAME)
                if wallet is None:
                    wallet = await store.sql_register_user(userid, COIN_NAME, 'DISCORD', 0)
                    wallet = await store.sql_get_userwallet(userid, COIN_NAME)
            elif coin_family == "ERC-20":
                wallet = await store.sql_get_userwallet(userid, COIN_NAME)
                if wallet is None:
                    w = await create_address_eth()
                    wallet = await store.sql_register_user(userid, COIN_NAME, 'DISCORD', 0, w)
                    wallet = await store.sql_get_userwallet(userid, COIN_NAME)
            elif coin_family == "TRC-20":
                wallet = await store.sql_get_userwallet(userid, COIN_NAME)
                if wallet is None:
                    result = await store.create_address_trx()
                    wallet = await store.sql_register_user(userid, COIN_NAME, 'DISCORD', 0, result)
                    wallet = await store.sql_get_userwallet(userid, COIN_NAME)
            else:
                return await respond_bad_request_404()

            if wallet is None:
                return await respond_internal_error()
            else:
                # add to api call
                try:
                    call = await store.api_trade_store(userid, uri)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                result = {"success": True, COIN_NAME: {"deposit_address": wallet['balance_wallet_address'], "maintenance": True if is_maintenance_coin(COIN_NAME) else False}}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=200)
    elif uri.startswith("/get_balance"):
        # TODO: rate limit check for all coin balance check
        # Disable temporary
        return await respond_bad_request_404()
        
        balance_list = {}
        maintenance_list = []
        for COIN_NAME in [coinItem.upper() for coinItem in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC+ENABLE_COIN_TRC+ENABLE_XCH]:
            # TODO: add maintenance check
            if is_maintenance_coin(COIN_NAME):
                maintenance_list.append(COIN_NAME)
            wallet = await store.sql_get_userwallet(userid, COIN_NAME)
            if wallet is None:
                if COIN_NAME in ENABLE_COIN_ERC:
                    w = create_eth_wallet()
                    userregister = await store.sql_register_user(userid, COIN_NAME, 'DISCORD', 0, w)
                elif COIN_NAME in ENABLE_COIN_TRC:
                    result = await store.create_address_trx()
                    userregister = await store.sql_register_user(userid, COIN_NAME, 'DISCORD', 0, result)
                else:
                    userregister = await store.sql_register_user(userid, COIN_NAME, 'DISCORD', 0)
                wallet = await store.sql_get_userwallet(userid, COIN_NAME)
            userdata_balance = await store.sql_user_balance(userid, COIN_NAME)
            xfer_in = 0
            if COIN_NAME not in ENABLE_COIN_ERC+ENABLE_COIN_TRC:
                xfer_in = await store.sql_user_balance_get_xfer_in(userid, COIN_NAME)
            if COIN_NAME in ENABLE_COIN_DOGE+ENABLE_COIN_ERC+ENABLE_COIN_TRC:
                actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
            elif COIN_NAME in ENABLE_COIN_NANO:
                actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                actual_balance = round(actual_balance / get_decimal(COIN_NAME), 6) * get_decimal(COIN_NAME)
            else:
                actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
            # TODO: add negative check
            balance_actual = num_format_coin(actual_balance, COIN_NAME)
            if actual_balance > 0:
                balance_list[COIN_NAME] = balance_actual
        # add to api call
        try:
            call = await store.api_trade_store(userid, uri)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        result = {"success": True, "balances": balance_list, "maitenance": maintenance_list}
        return web.Response(text=json.dumps(result).replace("\\", ""), status=200)
    else:
        return await respond_bad_request_404()


async def handle_post_all(request):
    global CF, ENABLE_TRADE_COIN, ENABLE_COIN, ENABLE_COIN_DOGE, ENABLE_XMR, ENABLE_XCH, ENABLE_COIN_NANO, ENABLE_COIN_ERC, ENABLE_COIN_TRC, MIN_TRADE_RATIO
    check_auth = None
    userid = ""
    client_ip = request.headers.get('X-Real-IP', None)
    if CF:
        # if cloudflare
        client_ip = request.headers.get('X-Forwarded-For', None)
    if 'authorization-user' in request.headers and 'authorization-key' in request.headers:
        userid = request.headers['authorization-user']
        key = request.headers['authorization-key']
        check_auth = await store.check_header(userid, key)
    if check_auth is None:
        try:
            print('Denied client ip: {} / {} / requested {}'.format(client_ip, request.headers.get('cf-ipcountry', None), request.rel_url))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return await respond_unauthorized_request()

    if CF:
        try:
            print('Client ip: {} / {} / Browser: {} requested {}'.format(client_ip, request.headers.get('cf-ipcountry', None), request.headers.get('User-Agent', None), request.rel_url))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    uri = str(request.rel_url).lower()
    data = await request.json()
    # add to api call
    try:
        call = await store.api_trade_store(userid, uri, json.dumps(data))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

    if uri.startswith("/sell"):
        try:
            await logchanbot("{}: user: {} called /sell:```{}```".format(SERVER_BOT, userid, json.dumps(data) if data else ""))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        def check_float(potential_float):
            try:
                float(potential_float)
                return True
            except ValueError:
                return False

        if 'coin_sell' in data and 'coin_get' in data and 'amount_sell' in data and 'amount_get' in data:
            if len(data['coin_sell']) == 0 or len(data['coin_get']) == 0 or len(data['amount_sell']) == 0 or len(data['amount_get']) == 0:
                result = {"success": False, "result": {"error": "Input data must not be empty."}}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=500)
            if data['coin_sell'].isalnum() == False or data['coin_get'].isalnum() == False:
                result = {"success": False, "result": {"error": "Invalid coin name for sell or buy."}}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=500)
            if check_float(data['amount_sell'].replace(",", "")) == False and check_float(data['amount_get'].replace(",", "")) == False:
                result = {"success": False, "result": {"error": "Invalid amount for sell or buy."}}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=500)

            sell_ticker = data['coin_sell'].upper()
            buy_ticker = data['coin_get'].upper()
            if sell_ticker not in ENABLE_TRADE_COIN:
                result = {"success": False, "result": {"error": "{} is not in tradable coin.".format(sell_ticker)}}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=500)
            if buy_ticker not in ENABLE_TRADE_COIN:
                result = {"success": False, "result": {"error": "{} is not in tradable coin.".format(buy_ticker)}}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=500)
            sell_amount = data['amount_sell'].replace(",", "")
            buy_amount = data['amount_get'].replace(",", "")
            try:
                sell_amount = Decimal(sell_amount)
                buy_amount = Decimal(buy_amount)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                result = {"success": False, "result": {"error": "Invalid trade amount(s)."}}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=500)
            # If they are tradable
            if not is_tradeable_coin(sell_ticker):
                result = {"success": False, "result": {"error": "{} is not tradable.".format(sell_ticker)}}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=500)
            if not is_tradeable_coin(buy_ticker):
                result = {"success": False, "result": {"error": "{} is not tradable.".format(buy_ticker)}}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=500)
            # If same ticker
            if buy_ticker == sell_ticker:
                result = {"success": False, "result": {"error": "Same ticker(s)."}}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=500)
            
            # get opened order:
            user_count_order = await store.sql_count_open_order_by_sellerid(userid, 'DISCORD')
            if user_count_order >= config.trade.Max_Open_Order:
                result = {"success": False, "result": {"error": "Reached max opened orders."}}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=500)

            # Check sell_ticker
            if sell_ticker in ENABLE_COIN_ERC:
                coin_family_sell = "ERC-20"
                sell_token_info = await store.get_token_info(sell_ticker)
            elif sell_ticker in ENABLE_COIN_TRC:
                coin_family_sell = "TRC-20"
                sell_token_info = await store.get_token_info(sell_ticker)
            else:
                coin_family_sell = getattr(getattr(config,"daemon"+sell_ticker),"coin_family","TRTL")
                sell_token_info = None
            real_amount_sell = int(sell_amount * get_decimal(sell_ticker)) if coin_family_sell in ["BCN", "XMR", "TRTL", "NANO", "XCH"] else float(sell_amount)
            if real_amount_sell == 0:
                result = {"success": False, "result": {"error": "Selling 0."}}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=500)
            # Check min/max
            if real_amount_sell < get_min_sell(sell_ticker, sell_token_info):
                result = {"success": False, "result": {"error": "Below minimum trade {} {}.".format(num_format_coin(get_min_sell(sell_ticker, sell_token_info), sell_ticker), sell_ticker)}}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=500)
            if real_amount_sell > get_max_sell(sell_ticker, sell_token_info):
                result = {"success": False, "result": {"error": "Above maximum trade {} {}.".format(num_format_coin(get_max_sell(sell_ticker, sell_token_info), sell_ticker), sell_ticker)}}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=500)
            # Check buy_ticker
            if buy_ticker in ENABLE_COIN_ERC:
                coin_family_buy = "ERC-20"
                buy_token_info = await store.get_token_info(buy_ticker)
            elif buy_ticker in ENABLE_COIN_TRC:
                coin_family_buy = "TRC-20"
                buy_token_info = await store.get_token_info(buy_ticker)
            else:
                coin_family_buy = getattr(getattr(config,"daemon"+buy_ticker),"coin_family","TRTL")
                buy_token_info = None

            real_amount_buy = int(buy_amount * get_decimal(buy_ticker)) if coin_family_buy in ["BCN", "XMR", "TRTL", "NANO", "XCH"] else float(buy_amount)

            if real_amount_buy == 0:
                result = {"success": False, "result": {"error": "Buying 0."}}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=500)
            if real_amount_buy < get_min_sell(buy_ticker, buy_token_info):
                result = {"success": False, "result": {"error": "Below minimum trade {} {}.".format(num_format_coin(get_min_sell(buy_ticker, buy_token_info), buy_ticker), sell_ticker)}}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=500)
            if real_amount_buy > get_max_sell(buy_ticker, buy_token_info):
                result = {"success": False, "result": {"error": "Above maximum trade {} {}.".format(num_format_coin(get_max_sell(buy_ticker, buy_token_info), buy_ticker), sell_ticker)}}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=500)

            if not is_maintenance_coin(sell_ticker):
                balance_actual = 0
                wallet = await store.sql_get_userwallet(userid, sell_ticker, 'DISCORD')
                if wallet is None:
                    userregister = await store.sql_register_user(userid, sell_ticker, 'DISCORD', 0)
                userdata_balance = await store.sql_user_balance(userid, sell_ticker)
                xfer_in = 0
                if sell_ticker not in ENABLE_COIN_ERC+ENABLE_COIN_TRC:
                    xfer_in = await store.sql_user_balance_get_xfer_in(userid, sell_ticker)
                if sell_ticker in ENABLE_COIN_DOGE+ENABLE_COIN_ERC+ENABLE_COIN_TRC:
                    actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
                elif sell_ticker in ENABLE_COIN_NANO:
                    actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                    actual_balance = round(actual_balance / get_decimal(sell_ticker), 6) * get_decimal(sell_ticker)
                else:
                    actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])

                # Negative check
                try:
                    if actual_balance < 0:
                        msg_negative = 'Negative balance detected:\nUser: '+userid+'\nCoin: '+sell_ticker+'\nAtomic Balance: '+str(actual_balance)
                        await logchanbot(msg_negative)
                except Exception as e:
                    await logchanbot(traceback.format_exc())

                if actual_balance < real_amount_sell:
                    result = {"success": False, "result": {"error": "Not sufficient balance. Having {} {}.".format(num_format_coin(actual_balance, sell_ticker), sell_ticker)}}
                    return web.Response(text=json.dumps(result).replace("\\", ""), status=500)
                if (sell_amount / buy_amount) < MIN_TRADE_RATIO or (buy_amount / sell_amount) < MIN_TRADE_RATIO:
                    result = {"success": False, "result": {"error": "Too low rate."}}
                    return web.Response(text=json.dumps(result).replace("\\", ""), status=500)
                # call other function
                return await sell_process(userid, real_amount_sell, sell_ticker, real_amount_buy, buy_ticker, data)
        else:
            result = {"success": False, "result": {"error": "Invalid data call."}}
            return web.Response(text=json.dumps(result).replace("\\", ""), status=500)
    elif uri.startswith("/buy"):
        try:
            await logchanbot("{}: user: {} called /buy:```{}```".format(SERVER_BOT, userid, json.dumps(data) if data else ""))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if 'ref_number' in data:
            # Have ref_number
            # Check if exist and check balance and if own order
            ref_number = data['ref_number']
            get_order_num = await store.sql_get_order_numb(ref_number)
            if get_order_num:
                # check if own order
                if get_order_num['sell_user_server'] == "DISCORD" and int(userid) == int(get_order_num['userid_sell']):
                    result = {"success": False, "result": {"error": "You can not buy your own order."}}
                    return web.Response(text=json.dumps(result).replace("\\", ""), status=400)
                else:
                    # check if sufficient balance
                    wallet = await store.sql_get_userwallet(userid, get_order_num['coin_get'], 'DISCORD')
                    if wallet is None:
                        if get_order_num['coin_get'] in ENABLE_COIN_ERC:
                            w = create_eth_wallet()
                            userregister = await store.sql_register_user(userid, get_order_num['coin_get'], 'DISCORD', 0, w)
                        elif get_order_num['coin_get'] in ENABLE_COIN_TRC:
                            result = await store.create_address_trx()
                            userregister = await store.sql_register_user(userid, get_order_num['coin_get'], 'DISCORD', 0, result)
                        else:
                            userregister = await store.sql_register_user(userid, get_order_num['coin_get'], 'DISCORD', 0)
                        wallet = await store.sql_get_userwallet(userid, get_order_num['coin_get'], 'DISCORD')
                    if wallet:
                        userdata_balance = await store.sql_user_balance(userid, get_order_num['coin_get'], 'DISCORD')
                        xfer_in = 0
                        if get_order_num['coin_get'] not in ENABLE_COIN_ERC+ENABLE_COIN_TRC:
                            xfer_in = await store.sql_user_balance_get_xfer_in(userid, get_order_num['coin_get'])
                        if get_order_num['coin_get'] in ENABLE_COIN_DOGE+ENABLE_COIN_ERC+ENABLE_COIN_TRC:
                            actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
                        elif get_order_num['coin_get'] in ENABLE_COIN_NANO:
                            actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                            actual_balance = round(actual_balance / get_decimal(get_order_num['coin_get']), 6) * get_decimal(get_order_num['coin_get'])
                        else:
                            actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                        # Negative check
                        try:
                            if actual_balance < 0:
                                msg_negative = 'Negative balance detected:\nUser: '+userid+'\nCoin: '+get_order_num['coin_get']+'\nAtomic Balance: '+str(actual_balance)
                                await logchanbot(msg_negative)
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                    if actual_balance < get_order_num['amount_get_after_fee']:
                        result = {"success": False, "result": {"error": "Not sufficient balance. Having {} {}.".format(num_format_coin(actual_balance, get_order_num['coin_get']), get_order_num['coin_get'])}}
                        return web.Response(text=json.dumps(result).replace("\\", ""), status=500)
                    else:
                        # let's make order update
                        match_order = await store.sql_match_order_by_sellerid(userid, ref_number, 'DISCORD', get_order_num['sell_user_server'], get_order_num['userid_sell'], False)
                        if match_order:
                            # trade webhook
                            success_msg = '{} Order completed! Get: {} {} From selling: {} {}'.format(ref_number, num_format_coin(get_order_num['amount_sell_after_fee'], 
                                            get_order_num['coin_sell']), get_order_num['coin_sell'], num_format_coin(get_order_num['amount_get'], 
                                            get_order_num['coin_get']), get_order_num['coin_get'])
                            try:
                                webhook_msg = "**#{}** Order completed! {} {} Sold!".format(ref_number, num_format_coin(get_order_num['amount_get'], 
                                            get_order_num['coin_get']), get_order_num['coin_get'])
                                await tradeapi_webhook(webhook_msg)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            result = {"success": True, "result": {"ref_number": str(ref_number), "message": success_msg}}
                            return web.Response(text=json.dumps(result).replace("\\", ""), status=200)
                        else:
                            return await respond_internal_error()
            else:
                result = {"success": False, "message": "Order does not exist or already completed."}
                return web.Response(text=json.dumps(result).replace("\\", ""), status=400)
        else:
            return await respond_bad_request()
    elif uri.startswith("/cancel"):
        try:
            await logchanbot("{}: user: {} called /cancel:```{}```".format(SERVER_BOT, userid, json.dumps(data) if data else ""))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        get_open_order = await store.sql_get_open_order_by_sellerid_all(userid, 'OPEN')
        if len(get_open_order) == 0:
            result = {"success": False, "message": "You do not have any open order."}
            return web.Response(text=json.dumps(result).replace("\\", ""), status=400)

        if 'ref_number' in data:
            # Check if exist and check balance and if own order
            ref_number = data['ref_number']
            if ref_number.isnumeric():
                cancelled = False
                for open_order_list in get_open_order:
                    if ref_number == str(open_order_list['order_id']):
                        cancel_order = await store.sql_cancel_open_order_by_sellerid(userid, ref_number) 
                        if cancel_order: cancelled = True
                if cancelled == False:
                    result = {"success": False, "message": f"You do not have sell #{ref_number}."}
                    return web.Response(text=json.dumps(result).replace("\\", ""), status=400)
                else:
                    result = {"success": True, "message": f"You cancelled #{ref_number}."}
                    return web.Response(text=json.dumps(result).replace("\\", ""), status=400)
            else:
                return await respond_bad_request_404()
        else:
            return await respond_bad_request_404()
    else:
        return await respond_bad_request_404()


async def sell_process(userid, real_amount_sell: float, sell_ticker: str, real_amount_buy: float, buy_ticker: str, data):
    global TRADE_PERCENT
    sell_ticker = sell_ticker.upper()
    buy_ticker = buy_ticker.upper()
    if sell_ticker in ["NANO", "BAN"]:
        real_amount_sell = round(real_amount_sell, 20)
    else:
        real_amount_sell = round(real_amount_sell, 8)
    if buy_ticker in ["NANO", "BAN"]:
        real_amount_buy = round(real_amount_buy, 20)
    else:
        real_amount_buy = round(real_amount_buy, 8)
    sell_div_get = round(real_amount_sell / real_amount_buy, 32)
    fee_sell = round(TRADE_PERCENT * real_amount_sell, 8)
    fee_buy = round(TRADE_PERCENT * real_amount_buy, 8)
    if fee_sell == 0: fee_sell = 0.00000100
    if fee_buy == 0: fee_buy = 0.00000100
    # No need to check if order same rate exists
    order_add = await store.sql_store_openorder(userid, "API: {}".format(json.dumps(data)), sell_ticker, 
                            real_amount_sell, real_amount_sell-fee_sell, userid, 
                            buy_ticker, real_amount_buy, real_amount_buy-fee_buy, sell_div_get, 'DISCORD')
    if order_add:
        get_message = "New open order created: **#{}** Selling: {} {} For: {} {} Fee: {} {}".format(order_add, 
                                                                        num_format_coin(real_amount_sell, sell_ticker), sell_ticker,
                                                                        num_format_coin(real_amount_buy, buy_ticker), buy_ticker,
                                                                        num_format_coin(fee_sell, sell_ticker), sell_ticker)
        # trade webhook
        try:
            await tradeapi_webhook(get_message)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        result = {"success": True, "result": {"message": get_message}}
        return web.Response(text=json.dumps(result).replace("\\", ""), status=200)
    else:
        result = {"success": False, "result": {"error": "Internal error during sell_process."}}
        return web.Response(text=json.dumps(result).replace("\\", ""), status=500)
        # response
        # add message to trade channel as well.
        # TODO: use webhook


# some bg1
async def bg_1(app):
    while True:
        # DO nothing
        pass

async def respond_unauthorized_request():
    text = "Unauthorized"
    return web.Response(text=text, status=401)


async def respond_bad_request():
    text = "Bad Request"
    return web.Response(text=text, status=400)


async def respond_bad_request_404():
    text = "Bad Request"
    return web.Response(text=text, status=404)


async def respond_internal_error():
    text = 'Internal Server Error'
    return web.Response(text=text, status=500)


#async def start_background_tasks(app):
#    app['market_live'] = asyncio.create_task(bg_1(app))


async def cleanup_background_tasks(app):
    app['market_live'].cancel()
    await app['market_live']


app = web.Application()
#app.on_startup.append(start_background_tasks)
#app.on_cleanup.append(cleanup_background_tasks)

app.router.add_route('GET', '/{tail:.*}', handle_get_all)
app.router.add_route('POST', '/{tail:.*}', handle_post_all)

web.run_app(app, host='127.0.0.1', port=2023)
