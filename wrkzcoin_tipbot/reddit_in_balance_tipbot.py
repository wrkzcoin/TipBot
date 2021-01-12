from config import config
from wallet import *
import store, daemonrpc_client, addressvalidation, walletapi
import sys, traceback
# redis
import redis, json
import uuid, time
import asyncio


from generic_xmr.address_msr import address_msr as address_msr
from generic_xmr.address_xmr import address_xmr as address_xmr
from generic_xmr.address_upx import address_upx as address_upx
from generic_xmr.address_wow import address_wow as address_wow
from generic_xmr.address_xol import address_xol as address_xol

# eth erc
from eth_account import Account
from decimal import Decimal

import math, random
# ascii table
from terminaltables import AsciiTable

# reddit
import praw

reddit = praw.Reddit(user_agent=config.reddit.user_agent,
                     client_id=config.reddit.client_id,
                     client_secret=config.reddit.client_secret,
                     username=config.reddit.username,
                     password=config.reddit.password)

# db = dataset.connect('sqlite:///reddit.db')
# get a reference to the table 'user'
#comment_table = db['comments']
#user_table = db['user']
#message_table = db['message']

ENABLE_COIN = config.reddit.Enabe_Reddit_Coin.split(",")
ENABLE_COIN_DOGE = config.telegram.Enable_Coin_Doge.split(",")
ENABLE_COIN_ERC = config.reddit.Enable_Coin_ERC.split(",")
ENABLE_COIN_NANO = config.telegram.Enable_Coin_Nano.split(",")
SERVER = 'REDDIT'
WITHDRAW_IN_PROCESS = []
redis_pool = None
redis_conn = None
redis_expired = 120

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


# Create ETH
def create_eth_wallet():
    Account.enable_unaudited_hdwallet_features()
    acct, mnemonic = Account.create_with_mnemonic()
    return {'address': acct.address, 'seed': mnemonic, 'private_key': acct.privateKey.hex()}


async def logchanbot(content: str):
    filterword = config.discord.logfilterword.split(",")
    for each in filterword:
        content = content.replace(each, config.discord.filteredwith)
    if len(content) > 1500: content = content[:1500]
    try:
        webhook = DiscordWebhook(url=config.discord.botdbghook, content=f'```{discord.utils.escape_markdown(content)}```')
        webhook.execute()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


# Notify user
async def notify_new_move_balance_user():
    time_lap = 5
    while True:
        try:
            pending_tx = await store.sql_get_move_balance_table('NO', 'NO')
            if pending_tx and len(pending_tx) > 0:
                # let's notify_new_tx_user
                for eachTx in pending_tx:
                    try:
                        if eachTx['to_server'] == SERVER:
                            user_found = await store.sql_get_userwallet(eachTx['to_userid'], eachTx['coin_name'], SERVER)
                            if user_found:
                                if eachTx['coin_name'] in ENABLE_COIN_ERC:
                                    eachTx['amount'] = float(eachTx['amount'])
                                message_text = "You got a tip deposit:\n\nCoin: {}\nAmount: {}\nFrom: {}@{} ({})".format(eachTx['coin_name'], num_format_coin(eachTx['amount'], eachTx['coin_name']), eachTx['from_userid'], eachTx['from_server'], eachTx['from_name'])
                                try:
                                    reddit.redditor(eachTx['to_userid']).message("You got a tip deposit {}".format(eachTx['coin_name']), message_text)
                                except Exception as e:
                                    print(traceback.format_exc())
                                    await logchanbot(traceback.format_exc())
                                update_receiver = await store.sql_update_move_balance_table(eachTx['id'], 'RECEIVER')
                                await asyncio.sleep(2)
                    except Exception as e:
                        print(traceback.format_exc())
                        await logchanbot(traceback.format_exc())
            await asyncio.sleep(time_lap)
        except:
            print(traceback.format_exc())
            await logchanbot(traceback.format_exc())
        await asyncio.sleep(2)


def is_maintenance_coin(coin: str):
    global redis_conn, redis_expired
    COIN_NAME = coin.upper()
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


def is_coin_txable(coin: str):
    global redis_conn, redis_expired
    COIN_NAME = coin.upper()
    if is_maintenance_coin(COIN_NAME):
        return False
    # Check if exist in redis
    try:
        openRedis()
        key = config.redis_setting.prefix_coin_setting + COIN_NAME + '_TX'
        if redis_conn and redis_conn.exists(key):
            return False
        else:
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def is_coin_depositable(coin: str):
    global redis_conn, redis_expired
    COIN_NAME = coin.upper()
    if is_maintenance_coin(COIN_NAME):
        return False
    # Check if exist in redis
    try:
        openRedis()
        key = config.redis_setting.prefix_coin_setting + COIN_NAME + '_DEPOSIT'
        if redis_conn and redis_conn.exists(key):
            return False
        else:
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def is_coin_tipable(coin: str):
    global redis_conn, redis_expired
    COIN_NAME = coin.upper()
    if is_maintenance_coin(COIN_NAME):
        return False
    # Check if exist in redis
    try:
        openRedis()
        key = config.redis_setting.prefix_coin_setting + COIN_NAME + '_TIP'
        if redis_conn and redis_conn.exists(key):
            return False
        else:
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def add_tx_action_redis(action: str, delete_temp: bool = False):
    try:
        openRedis()
        key = config.redis_setting.prefix_action_tx
        if redis_conn:
            if delete_temp:
                redis_conn.delete(key)
            else:
                redis_conn.lpush(key, action)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def get_cn_coin_from_address(CoinAddress: str):
    COIN_NAME = None
    if CoinAddress.startswith("Wrkz"):
        COIN_NAME = "WRKZ"
    elif CoinAddress.startswith("dg"):
        COIN_NAME = "DEGO"
    elif CoinAddress.startswith("cat1"):
        COIN_NAME = "CX"
    elif CoinAddress.startswith("XCR"):
        COIN_NAME = "NBXC"
    elif CoinAddress.startswith("ccx7"):
        COIN_NAME = "CCX"
    elif CoinAddress.startswith("fango"):
        COIN_NAME = "XFG"
    elif CoinAddress.startswith("btcm"):
        COIN_NAME = "BTCMZ"
    elif CoinAddress.startswith("PLe"):
        COIN_NAME = "PLE"
    elif CoinAddress.startswith("TRTL"):
        COIN_NAME = "TRTL"
    elif CoinAddress.startswith("bit") and (len(CoinAddress) == 98 or len(CoinAddress) == 109):
        COIN_NAME = "XTOR"
    elif (CoinAddress.startswith("4") or CoinAddress.startswith("8") or CoinAddress.startswith("5") or CoinAddress.startswith("9")) \
        and (len(CoinAddress) == 95 or len(CoinAddress) == 106):
        # XMR / MSR
        # 5, 9: MSR
        # 4, 8: XMR
        addr = None
        # Try MSR
        try:
            addr = address_msr(CoinAddress)
            COIN_NAME = "MSR"
            return COIN_NAME
        except Exception as e:
            # await logchanbot(traceback.format_exc())
            pass
        # Try XMR
        try:
            addr = address_xmr(CoinAddress)
            COIN_NAME = "XMR"
            return COIN_NAME
        except Exception as e:
            # await logchanbot(traceback.format_exc())
            pass
        # Try UPX	
        try:	
            addr = address_upx(CoinAddress)	
            COIN_NAME = "UPX"	
            return COIN_NAME	
        except Exception as e:	
            # traceback.print_exc(file=sys.stdout)	
            pass
    elif CoinAddress.startswith("L") and (len(CoinAddress) == 95 or len(CoinAddress) == 106):
        COIN_NAME = "LOKI"
    elif CoinAddress.startswith("cms") and (len(CoinAddress) == 98 or len(CoinAddress) == 109):
        COIN_NAME = "BLOG"
    elif (CoinAddress.startswith("WW") and len(CoinAddress) == 97) or \
    (CoinAddress.startswith("Wo") and len(CoinAddress) == 97) or \
    (CoinAddress.startswith("So") and len(CoinAddress) == 108):
        COIN_NAME = "WOW"
    elif (CoinAddress.startswith("Xw") and len(CoinAddress) == 97) or \
    (CoinAddress.startswith("iz") and len(CoinAddress) == 108):
        COIN_NAME = "XOL"
    elif ((CoinAddress.startswith("UPX") and len(CoinAddress) == 98) or (CoinAddress.startswith("UPi") and len(CoinAddress) == 109) or (CoinAddress.startswith("Um") and len(CoinAddress) == 97)):
        COIN_NAME = "UPX"
    elif (CoinAddress.startswith("5") or CoinAddress.startswith("9")) and (len(CoinAddress) == 95 or len(CoinAddress) == 106):
        COIN_NAME = "MSR"
    elif (CoinAddress.startswith("fh") and len(CoinAddress) == 97) or \
    (CoinAddress.startswith("fi") and len(CoinAddress) == 108) or \
    (CoinAddress.startswith("fs") and len(CoinAddress) == 97):
        COIN_NAME = "XWP"
    elif CoinAddress.startswith("D") and len(CoinAddress) == 34:
        COIN_NAME = "DOGE"
    elif (CoinAddress[0] in ["M", "L"]) and len(CoinAddress) == 34:
        COIN_NAME = "LTC"
    elif (CoinAddress[0] in ["P", "Q"]) and len(CoinAddress) == 34:
        COIN_NAME = "PGO"
    elif (CoinAddress[0] in ["3", "1"]) and len(CoinAddress) == 34:
        COIN_NAME = "BTC"
    elif (CoinAddress[0] in ["X"]) and len(CoinAddress) == 34:
        COIN_NAME = "DASH"
    elif CoinAddress.startswith("ban_") and len(CoinAddress) == 64:
        COIN_NAME = "BAN"
    elif CoinAddress.startswith("nano_") and len(CoinAddress) == 65:
        COIN_NAME = "NANO"
    print('get_cn_coin_from_address return {}: {}'.format(CoinAddress, COIN_NAME))
    return COIN_NAME


if __name__ == "__main__":
    loop = asyncio.get_event_loop()  
    loop.run_until_complete(notify_new_move_balance_user())  
    loop.close()  
