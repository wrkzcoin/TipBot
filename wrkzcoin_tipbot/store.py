import json
import os.path
import sys
import time
import traceback
from typing import Dict

import aiohttp
import aiomysql
import asyncio
import disnake
import httpx
import pymysql.cursors

from aiohttp import TCPConnector
from aiomysql.cursors import DictCursor
from discord_webhook import AsyncDiscordWebhook
# For seed to key
from eth_account import Account
from ethtoken.abi import EIP20_ABI
from httpx import AsyncClient, Timeout, Limits
from tronpy import AsyncTron
from tronpy.exceptions import AddressNotFound, UnknownError
from tronpy.keys import PrivateKey
from tronpy.providers.async_http import AsyncHTTPProvider
from web3 import Web3
from web3.middleware import geth_poa_middleware

Account.enable_unaudited_hdwallet_features()

from Bot import decrypt_string, load_config

config = load_config()

pool = None
pool_netmon = None
conn = None
sys.path.append("..")

async def openConnection():
    global pool
    try:
        if pool is None:
            pool = await aiomysql.create_pool(
                host=config['mysql']['host'], port=3306, minsize=8, maxsize=16,
                user=config['mysql']['user'], password=config['mysql']['password'],
                db=config['mysql']['db'], cursorclass=DictCursor, autocommit=True
            )
    except:
        print("ERROR: Unexpected error: Could not connect to MySql instance.")
        traceback.print_exc(file=sys.stdout)

async def openConnection_node_monitor():
    global pool_netmon
    try:
        if pool_netmon is None:
            pool = await aiomysql.create_pool(
                host=config['mysql_node_monitor']['host'], port=3306, minsize=1, maxsize=2,
                user=config['mysql_node_monitor']['user'], password=config['mysql_node_monitor']['password'],
                db=config['mysql_node_monitor']['db'], cursorclass=DictCursor, autocommit=True
            )
    except:
        print("ERROR: Unexpected error: Could not connect to MySql instance.")
        traceback.print_exc(file=sys.stdout)

async def logchanbot(content: str):
    try:
        webhook = AsyncDiscordWebhook(
            url=config['discord']['webhook_default_url'],
            content=disnake.utils.escape_markdown(content)
        )
        await webhook.execute()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

async def handle_best_node(network: str):
    global pool_netmon
    table = ""
    if network.upper() == "TRX":
        table = "chain_trx"
    try:
        await openConnection_node_monitor()
        async with pool_netmon.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT id, url, name, duration, MAX(height) as height
                          FROM `""" + table + """`
                          GROUP BY url ORDER BY height DESC LIMIT 10 """
                await cur.execute(sql, )
                nodes = await cur.fetchall()
                if nodes and len(nodes) > 1:
                    # Check which one has low fetch time
                    url = nodes[0]['url']
                    fetch_time = nodes[0]['duration']
                    for each_node in nodes:
                        if fetch_time > each_node['duration']:
                            url = each_node['url']
                    return url
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

async def sql_addinfo_by_server(
    server_id: str, servername: str, prefix: str, default_coin: str, rejoin: bool = True
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if rejoin:
                    sql = """ INSERT INTO `discord_server` 
                    (`serverid`, `servername`, `prefix`, `default_coin`, `status`)
                    VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY 
                    UPDATE 
                    `servername`=VALUES(`servername`),
                    `prefix`=VALUES(`prefix`), 
                    `default_coin`=VALUES(`default_coin`), 
                    `status`=VALUES(`status`)
                    """
                    await cur.execute(sql, (server_id, servername[:28], prefix, default_coin, "REJOINED",))
                    await conn.commit()
                else:
                    sql = """ INSERT INTO `discord_server` (`serverid`, `servername`, `prefix`, `default_coin`)
                    VALUES (%s, %s, %s, %s) ON DUPLICATE KEY  
                    UPDATE 
                    `servername`=VALUES(`servername`),
                    `prefix`=VALUES(`prefix`), 
                    `default_coin`=VALUES(`default_coin`)
                    """
                    await cur.execute(sql, (server_id, servername[:28], prefix, default_coin))
                    await conn.commit()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

async def sql_add_messages(list_messages):
    if len(list_messages) == 0:
        return 0
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT IGNORE INTO `discord_messages` (`serverid`, `server_name`, 
                `channel_id`, `channel_name`, `user_id`, `message_author`, `message_id`, 
                `message_content`, `message_time`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                await cur.executemany(sql, list_messages)
                await conn.commit()
                return cur.rowcount
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def sql_get_messages(
    server_id: str, channel_id: str, time_int: int, num_user: int = None
):
    global pool
    lapDuration = int(time.time()) - time_int
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                list_talker = []
                if num_user is None:
                    sql = """ SELECT DISTINCT `user_id` 
                    FROM discord_messages 
                    WHERE `serverid` = %s AND `channel_id` = %s AND `message_time`>%s
                    """
                    await cur.execute(sql, (server_id, channel_id, lapDuration,))
                    result = await cur.fetchall()
                    if result:
                        for item in result:
                            if int(item['user_id']) not in list_talker:
                                list_talker.append(int(item['user_id']))
                else:
                    sql = """ SELECT `user_id` FROM discord_messages 
                    WHERE `serverid` = %s AND `channel_id` = %s 
                    GROUP BY `user_id` ORDER BY max(`message_time`) DESC LIMIT %s
                    """
                    await cur.execute(sql, (server_id, channel_id, num_user,))
                    result = await cur.fetchall()
                    if result:
                        for item in result:
                            if int(item['user_id']) not in list_talker:
                                list_talker.append(int(item['user_id']))
                return list_talker
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def sql_changeinfo_by_server(
    server_id: str, what: str, value: str
):
    global pool
    config = load_config()
    if what.lower() in config['mysql']['guild_field_list']:
        try:
            # print(f"ok try to change {what} to {value}")
            await openConnection()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `discord_server` SET `""" + what.lower() + """` = %s 
                    WHERE `serverid` = %s
                    """
                    await cur.execute(sql, (value, server_id,))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    return False

# TODO: get balance based on various coin, external withdraw, other expenses, tipping out, etc
async def sql_user_balance_single(
    user_id: str, coin: str, address: str, coin_family: str, top_block: int,
    confirmed_depth: int = 0, user_server: str = 'DISCORD'
):
    global pool
    # address: TRTL/BCN/XMR = paymentId
    token_name = coin.upper()
    user_server = user_server.upper()
    if top_block is None:
        # If we can not get top block, confirm after 20mn. This is second not number of block
        nos_block = 20 * 60
    else:
        nos_block = top_block - confirmed_depth
    confirmed_inserted = 30  # 30s for nano
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # moving tip + / -
                sql = """
                        SELECT 
                        (SELECT IFNULL((SELECT (`balance`-`withdrew`+`deposited`)  
                        FROM `user_balance_mv_data` 
                        WHERE `user_id`=%s AND `token_name`=%s AND `user_server`=%s LIMIT 1), 0))

                        - (SELECT IFNULL((SELECT SUM(`real_amount`)  
                        FROM `discord_airdrop_tmp` 
                        WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))

                        - (SELECT IFNULL((SELECT SUM(`real_amount`)  
                        FROM `discord_mathtip_tmp` 
                        WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))

                        - (SELECT IFNULL((SELECT SUM(`real_amount`)  
                        FROM `discord_triviatip_tmp` 
                        WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))

                        - (SELECT IFNULL((SELECT SUM(`amount_sell`)  
                        FROM `open_order` 
                        WHERE `coin_sell`=%s AND `userid_sell`=%s AND `status`=%s), 0))

                        - (SELECT IFNULL((SELECT SUM(`amount`)  
                        FROM `guild_raffle_entries` 
                        WHERE `coin_name`=%s AND `user_id`=%s AND `user_server`=%s AND `status`=%s), 0))

                        - (SELECT IFNULL((SELECT SUM(`init_amount`)  
                        FROM `discord_partydrop_tmp` 
                        WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))

                        - (SELECT IFNULL((SELECT SUM(`joined_amount`)  
                        FROM `discord_partydrop_join` 
                        WHERE `attendant_id`=%s AND `token_name`=%s AND `status`=%s), 0))

                        - (SELECT IFNULL((SELECT SUM(`real_amount`)  
                        FROM `discord_quickdrop` 
                        WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))

                        - (SELECT IFNULL((SELECT SUM(`real_amount`)  
                        FROM `discord_talkdrop_tmp` 
                        WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))
                      """
                query_param = [user_id, token_name, user_server,
                               user_id, token_name, "ONGOING",
                               user_id, token_name, "ONGOING",
                               user_id, token_name, "ONGOING",
                               token_name, user_id, "OPEN",
                               token_name, user_id, user_server, "REGISTERED",
                               user_id, token_name, "ONGOING",
                               user_id, token_name, "ONGOING",
                               user_id, token_name, "ONGOING",
                               user_id, token_name, "ONGOING"]
                sql += """ AS mv_balance"""
                await cur.execute(sql, tuple(query_param))
                result = await cur.fetchone()
                if result:
                    mv_balance = result['mv_balance']
                else:
                    mv_balance = 0
            balance = {}
            try:
                balance['adjust'] = 0
                balance['mv_balance'] = float("%.6f" % mv_balance) if mv_balance else 0
                balance['adjust'] = float("%.6f" % balance['mv_balance'])
            except Exception:
                print("store issue user_balance coin name: {}".format(token_name))
                traceback.print_exc(file=sys.stdout)
            # Negative check
            try:
                if balance['adjust'] < 0:
                    msg_negative = 'Negative balance detected:\nServer:' + user_server + '\nUser: ' + user_id + '\nToken: ' + token_name + '\nBalance: ' + str(
                        balance['adjust'])
                    await logchanbot(msg_negative)
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return balance
    except Exception:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store user_balance " +str(traceback.format_exc()))

# owner message to delete (which bot respond)
async def add_discord_bot_message(message_id: str, guild_id: str, owner_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_bot_message_owner 
                (`message_id`, `guild_id`, `owner_id`, `stored_time`) 
                VALUES (%s, %s, %s, %s) """
                await cur.execute(sql, (message_id, guild_id, owner_id, int(time.time())))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def get_discord_mathtip_by_msgid(msg_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `discord_mathtip_tmp` 
                WHERE `message_id`=%s """
                await cur.execute(sql, msg_id)
                result = await cur.fetchone()
                if result:
                    return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return None

async def get_discord_triviatip_by_msgid(msg_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `discord_triviatip_tmp` 
                WHERE `message_id`=%s LIMIT 1
                """
                await cur.execute(sql, msg_id)
                result = await cur.fetchone()
                if result:
                    return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return None
# End owner message

# get coin_setting
async def get_coin_settings(coin_type: str = None):
    global pool
    try:
        sql_coin_type = ""
        if coin_type: sql_coin_type = """ AND `type`='""" + coin_type.upper() + """'"""
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `coin_settings` 
                WHERE `is_maintenance`=0 AND `enable`=1 """ + sql_coin_type
                await cur.execute(sql, )
                result = await cur.fetchall()
                if result:
                    return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def sql_nano_get_user_wallets(coin: str):
    global pool
    coin_name = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM nano_user 
                WHERE `coin_name`=%s """
                await cur.execute(sql, coin_name)
                result = await cur.fetchall()
                return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def sql_get_userwallet_by_paymentid(paymentid: str, coin: str, coin_family: str):
    coin_name = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                result = None
                if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    sql = """ SELECT * FROM `cn_user_paymentid` 
                    WHERE `paymentid`=%s AND `coin_name`=%s LIMIT 1
                    """
                    await cur.execute(sql, (paymentid, coin_name))
                    result = await cur.fetchone()
                elif coin_family == "CHIA":
                    sql = """ SELECT * FROM `xch_user` 
                    WHERE `balance_wallet_address`=%s AND `coin_name`=%s LIMIT 1
                    """
                    await cur.execute(sql, (paymentid, coin_name))
                    result = await cur.fetchone()
                elif coin_family == "BTC":
                    # if doge family, address is paymentid
                    sql = """ SELECT * FROM `doge_user` 
                    WHERE `balance_wallet_address`=%s AND `coin_name`=%s LIMIT 1
                    """
                    await cur.execute(sql, (paymentid, coin_name))
                    result = await cur.fetchone()
                elif coin_family == "NANO":
                    # if doge family, address is paymentid
                    sql = """ SELECT * FROM `nano_user` 
                    WHERE `balance_wallet_address`=%s AND `coin_name`=%s LIMIT 1
                    """
                    await cur.execute(sql, (paymentid, coin_name))
                    result = await cur.fetchone()
                elif coin_family == "XLM":
                    # if doge family, address is paymentid
                    sql = """ SELECT * FROM `xlm_user` 
                    WHERE `main_address`=%s AND `memo`=%s LIMIT 1
                    """
                    address_memo = paymentid.split()
                    await cur.execute(sql, (address_memo[0], address_memo[2]))
                    result = await cur.fetchone()
                elif coin_family == "COSMOS":
                    # if doge family, address is paymentid
                    sql = """ SELECT * FROM `cosmos_user` 
                    WHERE `main_address`=%s AND `memo`=%s LIMIT 1
                    """
                    address_memo = paymentid.split()
                    await cur.execute(sql, (address_memo[0], address_memo[2]))
                    result = await cur.fetchone()
                elif coin_family == "VITE":
                    # if doge family, address is paymentid
                    sql = """ SELECT * FROM `vite_user`
                    WHERE `main_address`=%s AND `memo`=%s LIMIT 1
                    """
                    address_memo = paymentid.split()
                    await cur.execute(sql, (address_memo[0], address_memo[2]))
                    result = await cur.fetchone()
                elif coin_family == "ADA":
                    # if ADA family, address is paymentid
                    sql = """ SELECT * FROM `ada_user`
                    WHERE `balance_wallet_address`=%s LIMIT 1
                    """
                    await cur.execute(sql, paymentid)
                    result = await cur.fetchone()
                elif coin_family == "SOL":
                    # if SOL family, address is paymentid
                    sql = """ SELECT * FROM `sol_user`
                    WHERE `balance_wallet_address`=%s LIMIT 1
                    """
                    await cur.execute(sql, paymentid)
                    result = await cur.fetchone()
                return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return None

# ERC, TRC scan
async def get_txscan_stored_list_erc(net_name: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if net_name == "TRX":
                    sql = """ SELECT * FROM `trc20_contract_scan` 
                    WHERE `net_name`=%s ORDER BY `blockNumber` DESC LIMIT 500
                    """
                    await cur.execute(sql, (net_name))
                    result = await cur.fetchall()
                    if result and len(result) > 0: return {
                        'txHash_unique': [item['contract_blockNumber_Tx_from_to_uniq'] for item in result]}
                else:
                    sql = """ SELECT * FROM `erc20_contract_scan`
                    WHERE `net_name`=%s ORDER BY `blockNumber` DESC LIMIT 500
                    """
                    await cur.execute(sql, (net_name))
                    result = await cur.fetchall()
                    if result and len(result) > 0: return {
                        'txHash_unique': [item['contract_blockNumber_Tx_from_to_uniq'] for item in result]}
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return {'txHash_unique': []}

async def get_latest_stored_scanning_height_erc(net_name: str, contract: str = None):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if net_name == "TRX":
                    sql = """ SELECT MAX(`blockNumber`) as TopBlock 
                    FROM `trc20_contract_scan` WHERE `net_name`=%s AND `contract`=%s
                    """
                    await cur.execute(sql, (net_name, contract))
                    result = await cur.fetchone()
                    if result and result['TopBlock']:
                        return int(result['TopBlock'])
                else:
                    sql = """ SELECT MAX(`blockNumber`) as TopBlock 
                    FROM `erc20_contract_scan` WHERE `net_name`=%s
                    """
                    await cur.execute(sql, (net_name))
                    result = await cur.fetchone()
                    if result and result['TopBlock']:
                        return int(result['TopBlock'])
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return 1

async def get_monit_contract_tx_insert_erc(list_data):
    global pool
    if len(list_data) == 0:
        return 0
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT IGNORE INTO `erc20_contract_scan` 
                (`net_name`, `contract`, `topics_dump`, `from_addr`, `to_addr`, `blockNumber`, 
                `blockTime`, `transactionHash`, `contract_blockNumber_Tx_from_to_uniq`) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.executemany(sql, list_data)
                await conn.commit()
                return cur.rowcount
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        pass
    return 0

async def get_monit_contract_tx_insert_trc(list_data):
    global pool
    if len(list_data) == 0:
        return 0
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT IGNORE INTO `trc20_contract_scan` 
                (`net_name`, `contract`, `from_addr`, `to_addr`, `blockNumber`, `blockTime`, 
                `transactionHash`, `contract_blockNumber_Tx_from_to_uniq`) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.executemany(sql, list_data)
                await conn.commit()
                return cur.rowcount
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        pass
    return 0

async def get_monit_scanning_net_name_update_height(
    net_name: str, new_height: int, coin_name: str = None
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if net_name == "TRX":
                    sql = """ UPDATE `coin_settings` 
                    SET `scanned_from_height`=%s 
                    WHERE `net_name`=%s AND 
                      (`scanned_from_height`<%s OR `scanned_from_height` IS NULL) 
                      AND `coin_name`=%s 
                    LIMIT 1 """
                    await cur.execute(sql, (new_height, net_name, new_height, coin_name))
                    await conn.commit()
                    return new_height
                else:
                    sql = """ UPDATE `coin_ethscan_setting` SET `scanned_from_height`=%s 
                    WHERE `net_name`=%s AND `scanned_from_height`<%s  
                    LIMIT 1 """
                    await cur.execute(sql, (new_height, net_name, new_height))
                    await conn.commit()
                    return new_height
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def trx_get_block_number(url: str, timeout: int = 64):
    height = 0
    url = url + "wallet/getnowblock"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={'Content-Type': 'application/json'},
                timeout=timeout
            ) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if decoded_data and 'block_header' in decoded_data:
                        height = decoded_data['block_header']['raw_data']['number']
    except asyncio.TimeoutError:
        print('TRX: get block number {}s for TOKEN {}'.format(timeout, "TRX"))
    except aiohttp.client_exceptions.ServerDisconnectedError:
        print('TRX: server disconnected url: {} for TOKEN {}'.format(url, "TRX"))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return height

async def trx_get_block_info(url: str, height: int, timeout: int = 32):
    try:
        _http_client = AsyncClient(
            limits=Limits(max_connections=10, max_keepalive_connections=5),
            timeout=Timeout(timeout=10, connect=5, read=5)
        )
        TronClient = AsyncTron(provider=AsyncHTTPProvider(url, client=_http_client))
        get_block = await TronClient.get_block(height)
        await TronClient.close()
        if get_block:
            return get_block['block_header']['raw_data']
    except httpx.RemoteProtocolError:
        print("httpx.RemoteProtocolError: url {} for TRX".format(url))
    except httpx.ReadTimeout:
        print("httpx.ReadTimeout: url {} for TRX".format(url))
    except httpx.ConnectTimeout:
        print("httpx.ConnectTimeout: url {} for TRX".format(url))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

async def erc_get_block_number(url: str, timeout: int = 64):
    data = '{"jsonrpc":"2.0", "method":"eth_blockNumber", "params":[], "id":1}'
    try:
        async with aiohttp.ClientSession(connector=TCPConnector(ssl=False)) as session:
            async with session.post(
                url, headers={'Content-Type': 'application/json'},
                json=json.loads(data),
                timeout=timeout
            ) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if decoded_data and 'result' in decoded_data:
                        return int(decoded_data['result'], 16)
    except asyncio.TimeoutError:
        print('TIMEOUT: {} get block number {}s'.format(url, timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


async def erc_get_block_info(url: str, height: int, timeout: int = 32):
    try:
        data = '{"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":["' + str(hex(height)) + '", false],"id":1}'
        try:
            async with aiohttp.ClientSession(connector=TCPConnector(ssl=False)) as session:
                async with session.post(
                    url, headers={'Content-Type': 'application/json'},
                    json=json.loads(data),
                    timeout=timeout
                ) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        await session.close()
                        decoded_data = json.loads(res_data)
                        if decoded_data and 'result' in decoded_data:
                            return decoded_data['result']
        except asyncio.TimeoutError:
            print('TIMEOUT: erc_get_block_info for {}s'.format(timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    except ValueError:
        traceback.print_exc(file=sys.stdout)
    return None

async def sql_get_all_erc_user(type_coin_user: str, called_Update: int = 0):
    # Check update only who has recently called for balance
    # If called_Update = 3600, meaning who called balance for last 1 hr
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if called_Update == 0:
                    sql = """ SELECT `user_id`, `balance_wallet_address`, `seed`, `user_server`
                    FROM `erc20_user` WHERE `type`=%s """
                    await cur.execute(sql, (type_coin_user))
                    result = await cur.fetchall()
                    if result:
                        return result
                elif called_Update > 0:
                    lap = int(time.time()) - called_Update
                    sql = """ SELECT `user_id`, `balance_wallet_address`, `seed`, `user_server`
                    FROM `erc20_user` 
                    WHERE (`called_Update`>%s OR `is_discord_guild`=1) AND `type`=%s """
                    await cur.execute(sql, (lap, type_coin_user))
                    result = await cur.fetchall()
                    if result:
                        return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def sql_get_all_tezos_user(type_coin_user: str, called_Update: int = 0):
    # Check update only who has recently called for balance
    # If called_Update = 3600, meaning who called balance for last 1 hr
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if called_Update == 0:
                    sql = """ SELECT `user_id`, `balance_wallet_address`, `type`, `seed`, 
                    `key`, `user_server` FROM `tezos_user` 
                    WHERE `type`=%s
                    """
                    await cur.execute(sql, (type_coin_user))
                    result = await cur.fetchall()
                    if result: return result
                elif called_Update > 0:
                    lap = int(time.time()) - called_Update
                    sql = """ SELECT `user_id`, `balance_wallet_address`, `type`, `seed`, `key`, `user_server`
                    FROM `tezos_user` 
                    WHERE (`called_Update`>%s OR `is_discord_guild`=1) AND `type`=%s
                    """
                    await cur.execute(sql, (lap, type_coin_user))
                    result = await cur.fetchall()
                    if result:
                        return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def sql_recent_tezos_move_deposit(called_Update: int = 300):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                lap = int(time.time()) - called_Update
                sql = """ SELECT * FROM `tezos_move_deposit` 
                          WHERE `time_insert`>%s """
                await cur.execute(sql, lap)
                result = await cur.fetchall()
                if result:
                    return [each['balance_wallet_address'] for each in result]
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def sql_get_all_zil_user(type_coin_user: str, called_Update: int = 0):
    # Check update only who has recently called for balance
    # If called_Update = 3600, meaning who called balance for last 1 hr
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if called_Update == 0:
                    sql = """ SELECT `user_id`, `balance_wallet_address`, `type`, `key`, `user_server` 
                    FROM `zil_user` WHERE `type`=%s
                    """
                    await cur.execute(sql, (type_coin_user))
                    result = await cur.fetchall()
                    if result:
                        return result
                elif called_Update > 0:
                    lap = int(time.time()) - called_Update
                    sql = """ SELECT `user_id`, `balance_wallet_address`, `type`, `key`, `user_server`
                    FROM zil_user 
                    WHERE (`called_Update`>%s OR `is_discord_guild`=1) AND `type`=%s
                    """
                    await cur.execute(sql, (lap, type_coin_user))
                    result = await cur.fetchall()
                    if result:
                        return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def sql_recent_zil_move_deposit(called_Update: int = 300):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                lap = int(time.time()) - called_Update
                sql = """ SELECT * FROM `zil_move_deposit` 
                          WHERE `time_insert`>%s """
                await cur.execute(sql, lap)
                result = await cur.fetchall()
                if result:
                    return [each['balance_wallet_address'] for each in result]
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def sql_get_all_vet_user(called_Update: int = 0):
    # Check update only who has recently called for balance
    # If called_Update = 3600, meaning who called balance for last 1 hr
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if called_Update == 0:
                    sql = """ SELECT `user_id`, `balance_wallet_address`, `key`, `user_server`
                    FROM `vet_user` """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result:
                        return result
                elif called_Update > 0:
                    lap = int(time.time()) - called_Update
                    sql = """ SELECT `user_id`, `balance_wallet_address`, `key`, `user_server`
                    FROM vet_user 
                    WHERE (`called_Update`>%s OR `is_discord_guild`=1) """
                    await cur.execute(sql, (lap,))
                    result = await cur.fetchall()
                    if result:
                        return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def sql_recent_vet_move_deposit(
    coin_name: str, called_Update: int = 300
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                lap = int(time.time()) - called_Update
                sql = """ SELECT * FROM `vet_move_deposit` 
                          WHERE `time_insert`>%s AND `token_name`=%s """
                await cur.execute(sql, (lap, coin_name))
                result = await cur.fetchall()
                if result:
                    return [each['balance_wallet_address'] for each in result]
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def sql_get_all_near_user(type_coin_user: str, called_Update: int = 0):
    # Check update only who has recently called for balance
    # If called_Update = 3600, meaning who called balance for last 1 hr
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if called_Update == 0:
                    sql = """ SELECT `user_id`, `user_id_near`, `coin_name`, `balance_wallet_address`, 
                    `type`, `seed`, `privateKey`, `last_moved_gas`, `user_server`
                    FROM `near_user` WHERE `type`=%s """
                    await cur.execute(sql, (type_coin_user))
                    result = await cur.fetchall()
                    if result:
                        return result
                elif called_Update > 0:
                    lap = int(time.time()) - called_Update
                    sql = """ SELECT `user_id`, `user_id_near`, `coin_name`, `balance_wallet_address`, 
                    `type`, `seed`, `privateKey`, `last_moved_gas`, `user_server` FROM `near_user` 
                    WHERE (`called_Update`>%s OR `is_discord_guild`=1) AND `type`=%s """
                    await cur.execute(sql, (lap, type_coin_user))
                    result = await cur.fetchall()
                    if result:
                        return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def sql_recent_near_move_deposit(called_Update: int = 300):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                lap = int(time.time()) - called_Update
                sql = """ SELECT * FROM `near_move_deposit` 
                          WHERE `time_insert`>%s """
                await cur.execute(sql, lap)
                result = await cur.fetchall()
                if result and len(result) > 0:
                    return [each['balance_wallet_address'] for each in result]
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def recent_balance_call_neo_user(called_Update: int = 0):
    # Check update only who has recently called for balance
    # If called_Update = 3600, meaning who called balance for last 1 hr
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if called_Update == 0:
                    sql = """ SELECT `user_id`, `balance_wallet_address`, `privateKey`, `user_server`
                    FROM `neo_user` """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result:
                        return result
                elif called_Update > 0:
                    lap = int(time.time()) - called_Update
                    sql = """ SELECT `user_id`, `balance_wallet_address`, `privateKey`, `user_server` 
                    FROM neo_user 
                    WHERE (`called_Update`>%s OR `is_discord_guild`=1) """
                    await cur.execute(sql, lap)
                    result = await cur.fetchall()
                    if result:
                        return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def neo_get_existing_tx():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT `txhash` FROM `neo_get_transfers` """
                await cur.execute(sql,)
                result = await cur.fetchall()
                if result:
                    return [each['txhash'] for each in result]
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

# TODO: this is for ERC-20 only, remove
async def http_wallet_getbalance(
    url: str, address: str, contract: str, time_out: int = 64
):
    if contract is None:
        data = '{"jsonrpc":"2.0","method":"eth_getBalance","params":["' + address + '", "latest"],"id":1}'
        try:
            async with aiohttp.ClientSession(connector=TCPConnector(ssl=False)) as session:
                async with session.post(
                    url,
                    headers={'Content-Type': 'application/json'},
                    json=json.loads(data),
                    timeout=time_out
                ) as response:
                    if response.status == 200:
                        data = await response.read()
                        try:
                            data = data.decode('utf-8')
                            decoded_data = json.loads(data)
                            if decoded_data and 'result' in decoded_data:
                                return int(decoded_data['result'], 16)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
        except asyncio.TimeoutError:
            print('TIMEOUT: get balance {} for {}s'.format(url, time_out))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    else:
        data = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [
                {
                    "to": contract,
                    "data": "0x70a08231000000000000000000000000" + address[2:]
                }, "latest"
            ],
            "id": 1
        }
        try:
            async with aiohttp.ClientSession(connector=TCPConnector(ssl=False)) as session:
                async with session.post(
                    url, headers={'Content-Type': 'application/json'},
                    json=data,
                    timeout=time_out
                ) as response:
                    if response.status == 200:
                        data = await response.read()
                        data = data.decode('utf-8')
                        decoded_data = json.loads(data)
                        if decoded_data and 'result' in decoded_data:
                            if decoded_data['result'] == "0x":
                                return 0
                            return int(decoded_data['result'], 16)
        except aiohttp.client_exceptions.ServerDisconnectedError:
            print("http_wallet_getbalance disconnected from url: {} for contract {}".format(url, contract))
        except asyncio.TimeoutError:
            print('TIMEOUT: get balance {} for {}s'.format(url, time_out))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    return None

async def check_approved_erc20(
    user_id: str, contract: str, address: str, user_server: str, network: str
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT * FROM `erc20_approved_spender` 
                WHERE `user_id`=%s AND `balance_wallet_address`=%s 
                AND `contract`=%s AND `user_server`=%s AND `network`=%s LIMIT 1
                """
                await cur.execute(sql, (
                    user_id, address, contract, user_server, network)
                )
                result = await cur.fetchone()
                if result:
                    return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return False

async def insert_approved_erc20(
    user_id: str, contract: str, address: str, user_server: str, network: str, approved_hash: str
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO `erc20_approved_spender` 
                          (`user_id`, `balance_wallet_address`, `contract`, `user_server`, 
                          `network`, `approved_hash`, `approved_date`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (
                    user_id, address, contract, user_server, 
                    network, approved_hash, int(time.time()))
                )
                await conn.commit()
                return cur.rowcount
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return 0

async def sql_move_deposit_for_spendable(
    token_name: str, contract: str, user_id: str, balance_wallet_address: str,
    to_main_address: str, real_amount: float, real_deposit_fee: float, 
    token_decimal: int, txn: str, user_server: str, network: str
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO erc20_move_deposit (`token_name`, `contract`, 
                `user_id`, `balance_wallet_address`, `to_main_address`, `real_amount`,
                `real_deposit_fee`, `token_decimal`, `txn`, `time_insert`, 
                `user_server`, `network`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (
                    token_name, contract, user_id, balance_wallet_address, to_main_address, real_amount,
                    real_deposit_fee, token_decimal, txn, int(time.time()), user_server.upper(),
                    network
                    )
                )
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return False

async def sql_get_pending_move_deposit_erc20(net_name: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM erc20_move_deposit 
                          WHERE `status`=%s AND `network`=%s 
                          AND `notified_confirmation`=%s """
                await cur.execute(sql, ('PENDING', net_name, 'NO'))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return None

async def sql_get_tx_info_erc20(url: str, tx: str, timeout: int = 64):
    data = '{"jsonrpc":"2.0", "method": "eth_getTransactionReceipt", "params":["' + tx + '"], "id":1}'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers={'Content-Type': 'application/json'},
                json=json.loads(data),
                timeout=timeout
            ) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if decoded_data and 'result' in decoded_data:
                        return decoded_data['result']
    except asyncio.TimeoutError:
        print('TIMEOUT: {} get block number {}s'.format(url, timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def sql_check_pending_move_deposit_erc20(
    url: str, net_name: str, deposit_confirm_depth: int,
    block_timeout: int = 64
):
    global pool
    top_block = await erc_get_block_number(url, block_timeout)
    if top_block is None:
        print(f'Can not get top block {url} - {net_name}.')
        return

    list_pending = await sql_get_pending_move_deposit_erc20(net_name)
    if list_pending and len(list_pending) > 0:
        # Have pending, let's check
        for each_tx in list_pending:
            # Check tx from RPC
            check_tx = await sql_get_tx_info_erc20(url, each_tx['txn'], block_timeout)
            if check_tx is not None:
                tx_block_number = int(check_tx['blockNumber'], 16)
                status = "CONFIRMED"
                if 'status' in check_tx and int(check_tx['status'], 16) == 0:
                    status = "FAILED"
                if top_block - deposit_confirm_depth > tx_block_number:
                    await sql_update_confirming_move_tx_erc20(
                        each_tx['txn'], tx_block_number, top_block - tx_block_number, status
                    )
            elif check_tx is None:
                # None found
                if int(time.time()) - 4 * 3600 > each_tx['time_insert']:
                    status = "FAILED"
                    tx_block_number = 0
                    await sql_update_confirming_move_tx_erc20(
                        each_tx['txn'], tx_block_number, top_block - tx_block_number, status
                    )

async def sql_update_confirming_move_tx_erc20(
    tx: str, blockNumber: int, confirmed_depth: int, status
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE erc20_move_deposit 
                SET `status`=%s, `blockNumber`=%s, `confirmed_depth`=%s 
                WHERE `txn`=%s
                """
                await cur.execute(sql, (status, blockNumber, confirmed_depth, tx))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return None

async def get_monit_scanning_contract_balance_address_erc20(
    net_name: str, called_Update: int = 1200
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                lap = int(time.time()) - called_Update
                sql = """ SELECT * FROM `erc20_contract_scan`
                WHERE `net_name`=%s AND `blockTime`>%s """
                await cur.execute(sql, (net_name, lap,))
                result = await cur.fetchall()
                if result and len(result) > 0: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def sql_update_erc_user_update_call_many_erc20(list_data):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                UPDATE `erc20_user` SET `called_Update`=%s
                WHERE `balance_wallet_address`=%s
                """
                await cur.executemany(sql, list_data)
                await conn.commit()
                return cur.rowcount
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return 0

async def sql_get_pending_notification_users_erc20(user_server: str = 'DISCORD'):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `erc20_move_deposit`
                WHERE `status`=%s 
                AND `notified_confirmation`=%s 
                AND `user_server`=%s
                """
                await cur.execute(sql, ('CONFIRMED', 'NO', user_server))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def sql_updating_pending_move_deposit_erc20(
    notified_confirmation: bool, failed_notification: bool, txn: str
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                UPDATE erc20_move_deposit 
                SET `notified_confirmation`=%s, `failed_notification`=%s, `time_notified`=%s
                WHERE `txn`=%s AND `time_notified` IS NULL
                """
                await cur.execute(sql, (
                    'YES' if notified_confirmation else 'NO',
                    'YES' if failed_notification else 'NO',
                    int(time.time()), txn
                    )
                )
                await conn.commit()
                return cur.rowcount
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return 0

async def trx_check_minimum_deposit(
    url: str, coin: str, type_coin: str, contract: str, coin_decimal: int,
    min_move_deposit: float, min_gas_tx: float, fee_limit_trx: float, gas_ticker: str,
    move_gas_amount: float, chainId: str, real_deposit_fee: float, time_lap: int = 0
):
    global pool
    token_name = coin.upper()
    list_user_addresses = await sql_get_all_trx_user(token_name, time_lap)
    msg_deposit = ""
    balance_below_min = 0
    balance_above_min = 0
    if list_user_addresses and len(list_user_addresses) > 0:
        # OK check them one by one
        for each_address in list_user_addresses:
            # Check if they failed many time during last 8h, if yes, next
            try:
                lap = int(time.time()) - 1 * 3600
                num_failed_limit = 3
                await openConnection()
                async with pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ SELECT COUNT(*) AS failed FROM `trc20_move_deposit` 
                        WHERE `balance_wallet_address`=%s 
                        AND `time_insert`>%s
                        """
                        await cur.execute(sql, (each_address['balance_wallet_address'], lap))
                        result = await cur.fetchone()
                        if result is not None and 'failed' in result and result['failed'] >= num_failed_limit:
                            msg = "trx_check_minimum_deposit: skip address `{}`.. failed threshold.".format(
                                each_address['balance_wallet_address'])
                            await logchanbot(msg)
                            continue
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

            deposited_balance = float(
                await trx_wallet_getbalance(
                    url, each_address['balance_wallet_address'], token_name, coin_decimal, type_coin, contract
                )
            )
            if deposited_balance is None or deposited_balance == 0:
                continue

            if deposited_balance < min_move_deposit:
                balance_below_min += 1
                pass
            else:
                balance_above_min += 1
                await asyncio.sleep(1.0)
                if token_name == "TRX":
                    # gas TRX is 6 coin_decimal
                    real_deposited_balance = deposited_balance - min_gas_tx
                    try:
                        _http_client = AsyncClient(
                            limits=Limits(max_connections=10, max_keepalive_connections=5),
                            timeout=Timeout(timeout=10, connect=5, read=5)
                        )
                        TronClient = AsyncTron(provider=AsyncHTTPProvider(url, client=_http_client))
                        txb = (
                            TronClient.trx.transfer(
                                each_address['balance_wallet_address'], config['trc']['MainAddress'],
                                int(real_deposited_balance * 10 ** 6)
                            )
                            # .memo("test memo")
                            # .fee_limit(100_000_000)
                            .fee_limit(int(fee_limit_trx * 10 ** 6))
                        )

                        txn = await txb.build()
                        priv_key = PrivateKey(bytes.fromhex(decrypt_string(each_address['private_key'])))
                        txn_ret = await txn.sign(priv_key).broadcast()
                        try:
                            in_block = await txn_ret.wait()
                            if 'result' in in_block and in_block['result'] == "FAILED":
                                msg = json.dumps(in_block)
                                await logchanbot(msg)
                                await asyncio.sleep(2.0)
                                continue
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                        await TronClient.close()
                        if txn_ret and in_block:
                            try:
                                await trx_move_deposit_for_spendable(
                                    token_name, contract, each_address['user_id'],
                                    each_address['balance_wallet_address'], config['trc']['MainAddress'],
                                    real_deposited_balance,
                                    real_deposit_fee, coin_decimal, txn_ret['txid'], in_block['blockNumber'],
                                    each_address['user_server']
                                )
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                        await asyncio.sleep(3)
                    except httpx.RemoteProtocolError:
                        print("httpx.RemoteProtocolError: url {} for token {}".format(url, coin))
                    except httpx.ReadTimeout:
                        print("httpx.ReadTimeout: url {} for token {}".format(url, coin))
                    except httpx.ConnectTimeout:
                        print("httpx.ConnectTimeout: url {} for token {}".format(url, coin))
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                else:
                    # Let's move to main address
                    if type_coin == "TRC-20":
                        try:
                            tron_node = await handle_best_node("TRX")
                            _http_client = AsyncClient(
                                limits=Limits(max_connections=10, max_keepalive_connections=5),
                                timeout=Timeout(timeout=10, connect=5, read=5)
                            )
                            TronClient = AsyncTron(provider=AsyncHTTPProvider(tron_node, client=_http_client))
                            cntr = await TronClient.get_contract(contract)
                            precision = await cntr.functions.decimals()
                            balance = await cntr.functions.balanceOf(
                                each_address['balance_wallet_address']) / 10 ** precision
                            print("{} - {} - {}".format(token_name, each_address['balance_wallet_address'], balance))
                            # Check balance and Transfer gas to it
                            try:
                                # Gas decimal is 6 for TRX
                                gas_balance = await trx_wallet_getbalance(
                                    url, each_address['balance_wallet_address'], "TRX", 6, type_coin, contract
                                )
                                if gas_balance < min_gas_tx:
                                    txb_gas = (
                                        TronClient.trx.transfer(
                                            config['trc']['MainAddress'],
                                            each_address['balance_wallet_address'],
                                            int(move_gas_amount * 10 ** 6)
                                        ).fee_limit(int(fee_limit_trx * 10 ** 6))
                                    )
                                    txn_gas = await txb_gas.build()
                                    priv_key_gas = PrivateKey(bytes.fromhex(config['trc']['MainAddress_key']))
                                    txn_ret_gas = await txn_gas.sign(priv_key_gas).broadcast()
                                    await asyncio.sleep(0.5)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            txb = await cntr.functions.transfer(config['trc']['MainAddress'],
                                                                int(balance * 10 ** coin_decimal))
                            txb = txb.with_owner(each_address['balance_wallet_address']).fee_limit(
                                int(fee_limit_trx * 10 ** 6))
                            txn = await txb.build()

                            priv_key = PrivateKey(bytes.fromhex(decrypt_string(each_address['private_key'])))
                            txn_ret = await txn.sign(priv_key).broadcast()
                            in_block = None
                            try:
                                in_block = await txn_ret.wait()
                                if 'result' in in_block and in_block['result'] == "FAILED":
                                    msg = json.dumps(in_block)
                                    await logchanbot(msg)
                                    await asyncio.sleep(2.0)
                                    continue
                                await asyncio.sleep(0.5)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            await TronClient.close()
                            if txn_ret and in_block:
                                try:
                                    inserted = await trx_move_deposit_for_spendable(
                                        token_name, contract, each_address['user_id'],
                                        each_address['balance_wallet_address'], config['trc']['MainAddress'], balance,
                                        real_deposit_fee, coin_decimal, txn_ret['txid'], in_block['blockNumber'],
                                        each_address['user_server']
                                    )
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                            await asyncio.sleep(0.5)
                        except httpx.RemoteProtocolError:
                            print("httpx.RemoteProtocolError: url {} for token {}".format(url, coin))
                        except httpx.ReadTimeout:
                            print("httpx.ReadTimeout: url {} for token {}".format(url, coin))
                        except httpx.ConnectTimeout:
                            print("httpx.ConnectTimeout: url {} for token {}".format(url, coin))
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                    elif type_coin == "TRC-10":
                        try:
                            tron_node = await handle_best_node("TRX")
                            _http_client = AsyncClient(
                                limits=Limits(max_connections=10, max_keepalive_connections=5),
                                timeout=Timeout(timeout=10, connect=5, read=5)
                            )
                            TronClient = AsyncTron(provider=AsyncHTTPProvider(tron_node, client=_http_client))
                            balance = await trx_wallet_getbalance(
                                url, each_address['balance_wallet_address'], token_name,
                                coin_decimal, type_coin, contract
                            )
                            # Check balance and Transfer gas to it
                            try:
                                gas_balance = await trx_wallet_getbalance(
                                    url, each_address['balance_wallet_address'],
                                    token_name, coin_decimal, type_coin, contract
                                )
                                if gas_balance < min_gas_tx:
                                    txb_gas = (
                                        TronClient.trx.transfer(
                                            config['trc']['MainAddress'],
                                            each_address['balance_wallet_address'],
                                            int(move_gas_amount * 10 ** coin_decimal)
                                        ).fee_limit(int(fee_limit_trx * 10 ** 6))
                                    )
                                    txn_gas = await txb_gas.build()
                                    priv_key_gas = PrivateKey(bytes.fromhex(config['trc']['MainAddress_key']))
                                    txn_ret_gas = await txn_gas.sign(priv_key_gas).broadcast()
                                    await asyncio.sleep(0.5)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            ### here
                            precision = 10 ** coin_decimal
                            amount = int(precision * balance)
                            txb = (
                                TronClient.trx.asset_transfer(
                                    each_address['balance_wallet_address'], config['trc']['MainAddress'], amount,
                                    token_id=int(contract)
                                )
                                .fee_limit(int(fee_limit_trx * 10 ** 6))
                            )
                            txn = await txb.build()
                            priv_key = PrivateKey(bytes.fromhex(decrypt_string(each_address['private_key'])))
                            txn_ret = await txn.sign(priv_key).broadcast()
                            in_block = None
                            try:
                                in_block = await txn_ret.wait()
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            await TronClient.close()
                            if txn_ret and in_block:
                                try:
                                    inserted = await trx_move_deposit_for_spendable(
                                        token_name, str(contract), each_address['user_id'], each_address['balance_wallet_address'],
                                        config['trc']['MainAddress'], balance, real_deposit_fee, coin_decimal, txn_ret['txid'],
                                        in_block['blockNumber'], each_address['user_server']
                                    )
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                            await asyncio.sleep(3)
                        except httpx.RemoteProtocolError:
                            print("httpx.RemoteProtocolError: url {} for token {}".format(url, coin))
                        except httpx.ReadTimeout:
                            print("httpx.ReadTimeout: url {} for token {}".format(url, coin))
                        except httpx.ConnectTimeout:
                            print("httpx.ConnectTimeout: url {} for token {}".format(url, coin))
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
        msg_deposit += "TOKEN {}: Total deposit address: {}: Below min.: {} Above min. {}".format(
            token_name, len(list_user_addresses), balance_below_min, balance_above_min
        )
    else:
        msg_deposit += "TOKEN {}: No deposit address.\n".format(token_name)
    return msg_deposit

async def sql_check_pending_move_deposit_trc20(
    url: str, net_name: str, deposit_confirm_depth: int, option: str = 'PENDING'
):
    global pool
    topBlock = await trx_get_block_number(url, timeout=64)
    if topBlock is None:
        await logchanbot('Can not get top block for {}.'.format(net_name))
        return
    list_pending = await trx_get_pending_move_deposit(option.upper())
    if len(list_pending) > 0:
        # Have pending, let's check
        for each_tx in list_pending:
            try:
                tx_block_number = each_tx['blockNumber']
                # if option.upper() == "ALL":
                #    print("Checking tx: {}... for {}".format(each_tx['txn'][0:10], net_name))
                #    print("topBlock: {}, Conf Depth: {}, Tx Block Numb: {}".format(topBlock, deposit_confirm_depth , tx_block_number))
                if topBlock - deposit_confirm_depth > tx_block_number:
                    check_tx = await trx_get_tx_info(url, each_tx['txn'])
                    if check_tx:
                        confirming_tx = await trx_update_confirming_move_tx(
                            each_tx['txn'], topBlock - tx_block_number, 'CONFIRMED'
                        )
                    else:
                        confirming_tx = await trx_update_confirming_move_tx(
                            each_tx['txn'], topBlock - tx_block_number, 'FAILED'
                        )
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot("store " +str(traceback.format_exc()))

async def trx_get_tx_info(url: str, tx: str):
    timeout = 64
    try:
        _http_client = AsyncClient(
            limits=Limits(max_connections=10, max_keepalive_connections=5),
            timeout=Timeout(timeout=10, connect=5, read=5)
        )
        TronClient = AsyncTron(provider=AsyncHTTPProvider(url, client=_http_client))
        getTx = await TronClient.get_transaction(tx)
        await TronClient.close()
        if getTx['ret'][0]['contractRet'] != "SUCCESS":
            # That failed.
            await logchanbot("TRX not succeeded with tx: {}".format(tx))
            return False
        else:
            return True
    except httpx.RemoteProtocolError:
        print("httpx.RemoteProtocolError: url {} for TRX".format(url))
    except httpx.ReadTimeout:
        print("httpx.ReadTimeout: url {} for TRX".format(url))
    except httpx.ConnectTimeout:
        print("httpx.ConnectTimeout: url {} for TRX".format(url))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

async def trx_wallet_getbalance(
    url: str, address: str, coin: str, coin_decimal: int, type_coin: str, contract: str = None
):
    token_name = coin.upper()
    balance = 0.0
    try:
        _http_client = AsyncClient(
            limits=Limits(max_connections=10, max_keepalive_connections=5),
            timeout=Timeout(timeout=10, connect=5, read=5)
        )
        TronClient = AsyncTron(provider=AsyncHTTPProvider(url, client=_http_client))
        if contract is None or token_name == "TRX":
            try:
                balance = await TronClient.get_account_balance(address)
            except AddressNotFound:
                balance = 0.0
            except httpx.ConnectTimeout:
                print(f"httpx.ConnectTimeout with {url}")
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        else:
            if type_coin == "TRC-20":
                try:
                    cntr = await TronClient.get_contract(contract)
                    SYM = await cntr.functions.symbol()
                    if token_name.upper() == SYM.upper():
                        precision = await cntr.functions.decimals()
                        balance = await cntr.functions.balanceOf(address) / 10 ** precision
                    else:
                        await logchanbot("Mis-match SYM vs TOKEN NAME: {} vs {}".format(SYM, token_name))
                except (AddressNotFound, UnknownError) as e:
                    pass
                except httpx.RemoteProtocolError:
                    print("httpx.RemoteProtocolError: url {} for token {}".format(url, coin))
                except httpx.ReadTimeout:
                    print("httpx.ReadTimeout: url {} for token {}".format(url, coin))
                except httpx.ConnectTimeout:
                    print("httpx.ConnectTimeout: url {} for token {}".format(url, coin))
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            elif type_coin == "TRC-10":
                try:
                    precision = coin_decimal
                    balance = await TronClient.get_account_asset_balance(
                        addr=address, token_id=int(contract)
                    ) / 10 ** precision
                except (AddressNotFound, UnknownError):
                    balance = 0.0
                except Exception as e:
                    pass
        await TronClient.close()
    except httpx.RemoteProtocolError:
        print("httpx.RemoteProtocolError: url {} for token {}".format(url, coin))
    except httpx.ReadTimeout:
        print("httpx.ReadTimeout: url {} for token {}".format(url, coin))
    except httpx.ConnectTimeout:
        print("httpx.ConnectTimeout: url {} for token {}".format(url, coin))
    except UnknownError as e:
        pass
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    except AddressNotFound:
        balance = 0.0
    return balance

async def trx_update_confirming_move_tx(
    tx: str, confirmed_depth: int, status: str = 'CONFIRMED'
):
    global pool
    status = status.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ UPDATE trc20_move_deposit
                SET `status`=%s, `confirmed_depth`=%s
                WHERE `txn`=%s
                """
                await cur.execute(sql, (status, confirmed_depth, tx))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return None

async def sql_get_pending_notification_users_trc20(user_server: str = 'DISCORD'):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `trc20_move_deposit` 
                WHERE `status`=%s 
                AND `notified_confirmation`=%s 
                AND `user_server`=%s """
                await cur.execute(sql, ('CONFIRMED', 'NO', user_server))
                result = await cur.fetchall()
                if result:
                    return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return None

async def trx_get_pending_move_deposit(option: str = 'PENDING'):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                if option.upper() == "PENDING":
                    sql = """ SELECT * FROM trc20_move_deposit 
                    WHERE `status`=%s AND `notified_confirmation`=%s
                    """
                    await cur.execute(sql, (option.upper(), 'NO'))
                    result = await cur.fetchall()
                    if result: return result
                elif option.upper() == "ALL":
                    sql = """ SELECT * FROM trc20_move_deposit 
                    WHERE `status`<>%s AND `status`<>%s
                    """
                    await cur.execute(sql, ('FAILED', 'CONFIRMED'))
                    result = await cur.fetchall()
                    if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def sql_updating_pending_move_deposit_trc20(
    notified_confirmation: bool, failed_notification: bool, txn: str
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE trc20_move_deposit 
                SET `notified_confirmation`=%s, `failed_notification`=%s, `time_notified`=%s
                WHERE `txn`=%s AND `time_notified` IS NULL
                """
                await cur.execute(sql, (
                    'YES' if notified_confirmation else 'NO',
                    'YES' if failed_notification else 'NO',
                    int(time.time()), txn
                    )
                )
                await conn.commit()
                return cur.rowcount
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return 0

async def sql_get_all_trx_user(coin: str, called_Update: int = 0):
    # Check update only who has recently called for balance
    # If called_Update = 3600, meaning who called balance for last 1 hr
    global pool
    token_name = coin.upper()
    extra_str = ""
    if token_name == "TRX":
        extra_str = """ WHERE (`type`='TRX' """
    else:
        extra_str = """ WHERE (`type`='TRC-20' """
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                if called_Update == 0:
                    sql = """ SELECT `user_id`, `user_id_trc20`, `balance_wallet_address`, 
                    `hex_address`, `private_key`, `user_server` FROM trc20_user 
                    """ + extra_str + """ ) OR `is_discord_guild`=1 """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result:
                        return result
                elif called_Update > 0:
                    lap = int(time.time()) - called_Update
                    sql = """ SELECT `user_id`, `user_id_trc20`, `balance_wallet_address`, 
                    `hex_address`, `private_key`, `user_server`
                    FROM trc20_user 
                    """ + extra_str + """ AND `called_Update`>%s) OR `is_discord_guild`=1 """
                    await cur.execute(sql, (lap))
                    result = await cur.fetchall()
                    if result:
                        return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def get_all_coin_token_addresses():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """   (SELECT t1.balance_wallet_address as addresses FROM erc20_user t1)
                UNION
                (SELECT t2.balance_wallet_address FROM trc20_user t2)
                UNION
                (SELECT t3.balance_wallet_address FROM cn_user_paymentid t3)
                UNION
                (SELECT t4.balance_wallet_address FROM xch_user t4)
                UNION
                (SELECT t5.balance_wallet_address FROM doge_user t5)
                UNION
                (SELECT t6.balance_wallet_address FROM nano_user t6)
                """
                await cur.execute(sql, ())
                result = await cur.fetchall()
                if result and len(result) > 0: return [each['addresses'] for each in result]
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return []

async def contract_tx_remove_after(type_coin: str, duration: int = 1200):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            lap = int(time.time()) - duration
            async with conn.cursor() as cur:
                if type_coin == "TRC-20":
                    sql = """ DELETE FROM `trc20_contract_scan` WHERE `blockTime`<%s """
                    await cur.execute(sql, (lap))
                    return True
                else:
                    sql = """ DELETE FROM `erc20_contract_scan` WHERE `blockTime`<%s """
                    await cur.execute(sql, (lap))
                    return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

## math tip
async def insert_discord_mathtip(
    token_name: str, contract: str, from_userid: str, from_username: str, message_id: str,
    eval_content: str, eval_answer: float, wrong_answer_1: float, wrong_answer_2: float,
    wrong_answer_3: float, guild_id: str, channel_id: str, real_amount: float,
    real_amount_usd: float, real_amount_usd_text: str, unit_price_usd: float,
    token_decimal: int, math_endtime: int, network: str, status: str = "ONGOING"
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_mathtip_tmp 
                (`token_name`, `contract`, `from_userid`, `from_username`, `message_id`, 
                `eval_content`, `eval_answer`, `wrong_answer_1`, `wrong_answer_2`, 
                `wrong_answer_3`, `guild_id`, `channel_id`, `real_amount`, 
                `real_amount_usd`, `real_amount_usd_text`, `unit_price_usd`, 
                `token_decimal`, `message_time`, `math_endtime`, `network`, `status`) 
                VALUES 
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (
                    token_name, contract, from_userid, from_username, message_id, eval_content, 
                    eval_answer, wrong_answer_1, wrong_answer_2, wrong_answer_3, guild_id, 
                    channel_id, real_amount, real_amount_usd, real_amount_usd_text, unit_price_usd, 
                    token_decimal, int(time.time()), math_endtime, network, status
                    )
                )
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return False

async def get_discord_mathtip_by_chanid(chan_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `discord_mathtip_tmp` 
                WHERE `channel_id`=%s AND `status`=%s ORDER BY `math_endtime` ASC LIMIT 10 """
                await cur.execute(sql, (chan_id, "ONGOING"))
                result = await cur.fetchall()
                if result:
                    return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def discord_mathtip_update(message_id: str, status: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE `discord_mathtip_tmp` SET `status`=%s 
                WHERE `message_id`=%s AND `status`<>%s LIMIT 1 """
                await cur.execute(sql, (status, message_id, status))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return None

async def get_math_responders_by_message_id(message_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `discord_mathtip_responder` 
                WHERE `message_id`=%s
                """
                await cur.execute(sql, (message_id))
                result = await cur.fetchall()
                if result and len(result) > 0:
                    wrong_ids = []
                    right_ids = []
                    wrong_names = []
                    right_names = []
                    for each in result:
                        if each['result'] == "RIGHT":
                            right_ids.append(each['responder_id'])
                            right_names.append(each['responder_name'])
                        else:
                            wrong_ids.append(each['responder_id'])
                            wrong_names.append(each['responder_name'])

                    return {'total': len(result), 'wrong_ids': wrong_ids, 'wrong_names': wrong_names,
                            'right_ids': right_ids, 'right_names': right_names}
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return {'total': 0, 'wrong_ids': [], 'wrong_names': [], 'right_ids': [], 'right_names': []}
# end of math tip

## Trivia
async def get_random_q_db(level: str):
    # level = EASY, MEDIUM, HARD
    difficulty = ""
    if level in ["EASY", "MEDIUM", "HARD"]:
        difficulty = "`difficulty`='" + level + "'"
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `trivia_db` 
                WHERE `is_enable`=%s """ + difficulty + """ ORDER BY RAND() LIMIT 1 """
                await cur.execute(sql, (1))
                result = await cur.fetchone()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def get_q_db(q_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `trivia_db` WHERE `id`=%s LIMIT 1 """
                await cur.execute(sql, (q_id))
                result = await cur.fetchone()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def get_active_discord_triviatip():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `discord_triviatip_tmp`
                WHERE `status`=%s """
                await cur.execute(sql, ("ONGOING"))
                result = await cur.fetchall()
                if result and len(result) > 0: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def get_responders_by_message_id(message_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `discord_triviatip_responder`
                WHERE `message_id`=%s """
                await cur.execute(sql, (message_id))
                result = await cur.fetchall()
                if result and len(result) > 0:
                    wrong_ids = []
                    right_ids = []
                    wrong_names = []
                    right_names = []
                    for each in result:
                        if each['result'] == "RIGHT":
                            right_ids.append(each['responder_id'])
                            right_names.append(each['responder_name'])
                        else:
                            wrong_ids.append(each['responder_id'])
                            wrong_names.append(each['responder_name'])

                    return {'total': len(result), 'wrong_ids': wrong_ids, 'wrong_names': wrong_names,
                            'right_ids': right_ids, 'right_names': right_names}
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return {'total': 0, 'wrong_ids': [], 'wrong_names': [], 'right_ids': [], 'right_names': []}

async def insert_discord_triviatip(
    token_name: str, contract: str, from_userid: str, from_owner_name: str,
    message_id: str, question_content: str, question_id: int, button_correct_answer: str,
    guild_id: str, channel_id: str, real_amount: float, real_amount_usd: float,
    real_amount_usd_text: str, unit_price_usd: float, token_decimal: int,
    trivia_endtime: int, network: str, status: str = "ONGOING"
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_triviatip_tmp 
                (`token_name`, `contract`, `from_userid`, `from_owner_name`, `message_id`, 
                `question_content`, `question_id`, `button_correct_answer`, `guild_id`, 
                `channel_id`, `real_amount`, `real_amount_usd`, `real_amount_usd_text`, 
                `unit_price_usd`, `token_decimal`, `message_time`, `trivia_endtime`, 
                `network`, `status`) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (
                    token_name, contract, from_userid, from_owner_name, message_id, 
                    question_content, question_id, button_correct_answer, guild_id, 
                    channel_id, real_amount, real_amount_usd, real_amount_usd_text,
                    unit_price_usd, token_decimal, int(time.time()), trivia_endtime,
                    network, status
                    )
                )
                await conn.commit()
                sql = """ UPDATE trivia_db 
                SET numb_asked=numb_asked+1 WHERE `id`=%s """
                await cur.execute(sql, question_id)
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return False

async def discord_triviatip_update(message_id: str, status: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE `discord_triviatip_tmp` 
                SET `status`=%s WHERE `message_id`=%s AND `status`<>%s LIMIT 1 """
                await cur.execute(sql, (status, message_id, status))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return None
## End of Trivia


async def sql_user_balance_mv_single(
    from_userid: str, to_userid: str, guild_id: str, channel_id: str,
    real_amount: float, coin: str, tiptype: str, token_decimal: int, user_server: str,
    contract: str, real_amount_usd: float, extra_message: str = None
):
    global pool
    token_name = coin.upper()
    currentTs = int(time.time())
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO user_balance_mv 
                          (`token_name`, `contract`, `from_userid`, `to_userid`, `guild_id`, `channel_id`, 
                          `real_amount`, `real_amount_usd`, `token_decimal`, `type`, `date`, `user_server`, 
                          `extra_message`) 
                          VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS DECIMAL(40,18)), CAST(%s AS DECIMAL(40,18)), %s, %s, %s, %s, %s);

                          INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, 
                          `balance`, `update_date`) 
                          VALUES (%s, %s, %s, CAST(%s AS DECIMAL(40,18)), %s) ON DUPLICATE KEY 
                          UPDATE 
                          `balance`=`balance`+VALUES(`balance`), 
                          `update_date`=VALUES(`update_date`);

                          INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, 
                          `balance`, `update_date`) 
                          VALUES (%s, %s, %s, CAST(%s AS DECIMAL(40,18)), %s) ON DUPLICATE KEY 
                          UPDATE 
                          `balance`=`balance`+VALUES(`balance`), 
                          `update_date`=VALUES(`update_date`);

                          """
                await cur.execute(sql, (
                    token_name, contract, from_userid, to_userid, guild_id, channel_id, 
                    real_amount, real_amount_usd, token_decimal, tiptype, currentTs, 
                    user_server, extra_message, from_userid, token_name, user_server,
                    -real_amount, currentTs, to_userid, token_name, user_server, 
                    real_amount, currentTs
                    )
                )
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return None

async def sql_user_balance_mv_multple_amount(user_dict_tip, tiptype: str, user_server: str):
    # user_dict_tip is array [{'from_user': xx, 'to_user': xx, 'guild_id': xx, 'channel_id': xx, 'amount': xx, 'coin': xx, 'decimal': xx, 'contract': xx or None, 'real_amount_usd': xx, 'extra_message': xxx or None}]
    global pool
    values_list = []
    currentTs = int(time.time())
    # type_list = []
    for item in user_dict_tip:
        values_list.append((
            item['coin'], item['contract'], item['from_user'], item['to_user'], 
            item['guild_id'], item['channel_id'], item['amount'], item['decimal'],
            tiptype.upper(), currentTs, user_server, item['real_amount_usd'], 
            item['extra_message'], item['from_user'], item['coin'], user_server, -item['amount'], 
            currentTs, item['to_user'], item['coin'], user_server,
            item['amount'], currentTs,
            )
        )

    if len(values_list) == 0:
        print("sql_user_balance_mv_multiple: got 0 data inserting. return...")
        return

    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO user_balance_mv (`token_name`, `contract`, `from_userid`, 
                `to_userid`, `guild_id`, `channel_id`, `real_amount`, `token_decimal`, 
                `type`, `date`, `user_server`, `real_amount_usd`, `extra_message`) 
                          VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS DECIMAL(40,18)), %s, %s, %s, %s, %s, %s);
                        
                          INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, 
                          `balance`, `update_date`) 
                          VALUES (%s, %s, %s, CAST(%s AS DECIMAL(40,18)), %s) ON DUPLICATE KEY 
                          UPDATE 
                          `balance`=`balance`+VALUES(`balance`), 
                          `update_date`=VALUES(`update_date`);

                          INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, 
                          `balance`, `update_date`) 
                          VALUES (%s, %s, %s, CAST(%s AS DECIMAL(40,18)), %s) ON DUPLICATE KEY 
                          UPDATE 
                          `balance`=`balance`+VALUES(`balance`), 
                          `update_date`=VALUES(`update_date`);
                """
                await cur.executemany(sql, values_list)
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return False

async def sql_user_balance_mv_multiple(
    user_from: str, user_tos, guild_id: str, channel_id: str, amount_each: float,
    coin: str, tiptype: str, token_decimal: int, user_server: str, contract: str,
    real_amount_usd: float, extra_message: str = None
):
    # user_tos is array "account1", "account2", ....
    global pool
    token_name = coin.upper()
    values_list = []
    currentTs = int(time.time())
    # type_list = []
    for item in user_tos:
        values_list.append((
            token_name, contract, user_from, item, guild_id, channel_id, amount_each, token_decimal,
            tiptype.upper(), currentTs, user_server, real_amount_usd, extra_message, user_from,
            token_name, user_server, -amount_each, currentTs, item, token_name, user_server,
            amount_each, currentTs,
            )
        )

    if len(values_list) == 0:
        print("sql_user_balance_mv_multiple: got 0 data inserting. return...")
        return

    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO user_balance_mv (`token_name`, `contract`, `from_userid`, 
                `to_userid`, `guild_id`, `channel_id`, `real_amount`, `token_decimal`, `type`, 
                `date`, `user_server`, `real_amount_usd`, `extra_message`) 
                          VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS DECIMAL(40,18)), %s, %s, %s, %s, %s, %s);
                        
                INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, 
                `balance`, `update_date`) 
                VALUES (%s, %s, %s, CAST(%s AS DECIMAL(40,18)), %s) ON DUPLICATE KEY 
                UPDATE 
                `balance`=`balance`+VALUES(`balance`), 
                `update_date`=VALUES(`update_date`);

                INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                VALUES (%s, %s, %s, CAST(%s AS DECIMAL(40,18)), %s) ON DUPLICATE KEY 
                UPDATE 
                `balance`=`balance`+VALUES(`balance`), 
                `update_date`=VALUES(`update_date`);
                """
                await cur.executemany(sql, values_list)
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return False

async def trx_move_deposit_for_spendable(
    token_name: str, contract: str, user_id: str, balance_wallet_address: str,
    to_main_address: str, real_amount: float, real_deposit_fee: float,
    token_decimal: int, txn: str, blockNumber: int, user_server: str = 'DISCORD'
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ INSERT INTO trc20_move_deposit (`token_name`, `contract`, `user_id`, 
                `balance_wallet_address`, `to_main_address`, `real_amount`, `real_deposit_fee`,
                `token_decimal`, `txn`, `blockNumber`, `time_insert`, 
                `user_server`) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (
                    token_name, contract, user_id, balance_wallet_address, to_main_address, real_amount,
                    real_deposit_fee, token_decimal, txn, blockNumber, int(time.time()),
                    user_server.upper()
                    )
                )
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return False

## ADA
async def ada_get_address_pools(min_remaining: int = 20):
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                used_addresses = []
                sql = """ SELECT `wallet_name`, `wallet_id`, `addresses`, `address_pool_gap` 
                          FROM `ada_wallets` WHERE `wallet_name`<>%s AND (`address_pool_gap`-`used_address`)>%s AND `addresses` IS NOT NULL 
                          ORDER BY `id` ASC LIMIT 1 """
                await cur.execute(sql, ("withdraw_ada", min_remaining))
                result = await cur.fetchone()
                if result:
                    wallet_name_address = result['addresses'].split("\n")
                    sql = """ SELECT `balance_wallet_address`, `wallet_name` FROM `ada_user` 
                              WHERE `wallet_name`=%s """
                    await cur.execute(sql, (result['wallet_name']))
                    res_used_address = await cur.fetchall()

                    if res_used_address and len(res_used_address) > 0:
                        used_addresses = [each['balance_wallet_address'] for each in res_used_address]
                    if len(used_addresses) == 0:
                        return {"wallet_name": result['wallet_name'], "addresses": wallet_name_address,
                                "address_pool_gap": result['address_pool_gap'], "remaining": len(wallet_name_address)}
                    else:
                        remaining = []
                        for each in wallet_name_address:
                            if each not in used_addresses:
                                remaining.append(each)
                        return {"wallet_name": result['wallet_name'], "addresses": remaining,
                                "address_pool_gap": result['address_pool_gap'], "remaining": len(remaining)}
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None
## END ADA

async def sql_toggle_tipnotify(user_id: str, onoff: str):
    # Bot will add user_id if it failed to DM
    global pool
    onoff = onoff.upper()
    if onoff == "OFF":
        try:
            await openConnection()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `bot_tipnotify_user` 
                    WHERE `user_id` = %s LIMIT 1 """
                    await cur.execute(sql, (user_id))
                    result = await cur.fetchone()
                    if result is None:
                        sql = """ INSERT INTO `bot_tipnotify_user` (`user_id`, `date`)
                                  VALUES (%s, %s) """
                        await cur.execute(sql, (user_id, int(time.time())))
                        await conn.commit()
        except pymysql.err.Warning as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("store " +str(traceback.format_exc()))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("store " +str(traceback.format_exc()))
    elif onoff == "ON":
        try:
            await openConnection()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ DELETE FROM `bot_tipnotify_user` 
                    WHERE `user_id` = %s """
                    await cur.execute(sql, str(user_id))
                    await conn.commit()
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("store " +str(traceback.format_exc()))

async def sql_get_tipnotify():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT `user_id`, `date` 
                FROM `bot_tipnotify_user` """
                await cur.execute(sql, )
                result = await cur.fetchall()
                ignorelist = []
                for row in result:
                    ignorelist.append(row['user_id'])
                return ignorelist
    except Exception as e:
        await logchanbot("store " +str(traceback.format_exc()))

# FreeTip
async def insert_freetip_collector(
    message_id: str, from_userid: str, collector_id: str, collector_name: str
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT IGNORE INTO discord_airdrop_collector 
                (`message_id`, `from_userid`, `collector_id`, `collector_name`, 
                `from_and_collector_uniq`, `inserted_time`)
                VALUES (%s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (
                    message_id, from_userid, collector_id, collector_name,
                    "{}-{}-{}".format(message_id, from_userid, collector_id), int(time.time())
                    )
                )
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return False

async def check_if_freetip_collector_in(
    message_id: str, from_userid: str, collector_id: str
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `discord_airdrop_collector` 
                WHERE `message_id`=%s AND `from_userid`=%s AND `collector_id`=%s LIMIT 1 """
                await cur.execute(sql, (message_id, from_userid, collector_id))
                result = await cur.fetchone()
                if result and len(result) > 0: return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return False

async def get_freetip_collector_by_id(message_id: str, from_userid: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `discord_airdrop_collector` 
                WHERE `message_id`=%s AND `from_userid`=%s """
                await cur.execute(sql, (message_id, from_userid))
                result = await cur.fetchall()
                if result and len(result) > 0: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def insert_discord_freetip(
    token_name: str, contract: str, from_userid: str, from_name: str, message_id: str,
    airdrop_content: str, guild_id: str, channel_id: str, real_amount: float,
    real_amount_usd: float, real_amount_usd_text: str, unit_price_usd: float,
    token_decimal: int, airdrop_time: int, status: str = "ONGOING", verify_int: int=0
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_airdrop_tmp (`token_name`, `contract`, 
                `from_userid`, `from_ownername`, `message_id`, `airdrop_content`, 
                `guild_id`, `channel_id`, `real_amount`, `real_amount_usd`, 
                `real_amount_usd_text`, `unit_price_usd`, `token_decimal`, 
                `message_time`, `airdrop_time`, `status`, `verify`) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (
                    token_name, contract, from_userid, from_name, message_id, 
                    airdrop_content, guild_id, channel_id, real_amount, 
                    real_amount_usd, real_amount_usd_text, unit_price_usd, 
                    token_decimal, int(time.time()),
                    airdrop_time, status, verify_int
                ))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return False

async def get_active_discord_freetip(lap: int = 60):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `discord_airdrop_tmp` 
                WHERE `status`=%s AND `airdrop_time`>%s """
                await cur.execute(sql, ("ONGOING", int(time.time()) - lap))
                result = await cur.fetchall()
                if result and len(result) > 0:
                    return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def get_inactive_discord_freetip(lap: int = 1200):
    # cleanup some mess
    # assume any active still ONGOING state for ~20mn
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `discord_airdrop_tmp` 
                WHERE `status`=%s AND `airdrop_time`<%s """
                await cur.execute(sql, ("ONGOING", int(time.time()) - lap))
                result = await cur.fetchall()
                if result and len(result) > 0: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("store " +str(traceback.format_exc()))
    return []

async def get_discord_freetip_by_msgid(message_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                swap_in = 0.0
                sql = """ SELECT * FROM `discord_airdrop_tmp` 
                WHERE `message_id`=%s LIMIT 1 """
                await cur.execute(sql, (message_id))
                result = await cur.fetchone()
                if result:
                    return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def discord_freetip_update(message_id: str, status: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE `discord_airdrop_tmp` 
                SET `status`=%s WHERE `message_id`=%s AND `status`<>%s LIMIT 1 """
                await cur.execute(sql, (status, message_id, status))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def discord_freetip_ongoing(user_id: str, status: str = "ONGOING"):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT (SELECT COUNT(*) FROM `discord_airdrop_tmp` WHERE `from_userid`=%s AND `status`=%s) as airdrop, 
                                 (SELECT COUNT(*) FROM `discord_mathtip_tmp` WHERE `from_userid`=%s AND `status`=%s) as mathtip,
                                 (SELECT COUNT(*) FROM `discord_triviatip_tmp` WHERE `from_userid`=%s AND `status`=%s) as triviatip,
                                 (SELECT COUNT(*) FROM `discord_partydrop_tmp` WHERE `from_userid`=%s AND `status`=%s) as partydrop,
                                 (SELECT COUNT(*) FROM `discord_quickdrop` WHERE `from_userid`=%s AND `status`=%s) as quickdrop,
                                 (SELECT COUNT(*) FROM `discord_talkdrop_tmp` WHERE `from_userid`=%s AND `status`=%s) as talkdrop
                      """
                await cur.execute(sql, (
                    user_id, status, user_id, status, 
                    user_id, status, user_id, status,
                    user_id, status, user_id, status
                    )
                )
                result = await cur.fetchone()
                if result:
                    return result['airdrop'] + result['mathtip'] + result['triviatip'] + \
                    result['partydrop'] + result['quickdrop'] + result['talkdrop']
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return 0

async def discord_freetip_ongoing_guild(guild_id: str, status: str = "ONGOING"):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT (SELECT COUNT(*) FROM `discord_airdrop_tmp` WHERE `guild_id`=%s AND `status`=%s) as airdrop, 
                                 (SELECT COUNT(*) FROM `discord_mathtip_tmp` WHERE `guild_id`=%s AND `status`=%s) as mathtip,
                                 (SELECT COUNT(*) FROM `discord_triviatip_tmp` WHERE `guild_id`=%s AND `status`=%s) as triviatip,
                                 (SELECT COUNT(*) FROM `discord_partydrop_tmp` WHERE `guild_id`=%s AND `status`=%s) as partydrop,
                                 (SELECT COUNT(*) FROM `discord_quickdrop` WHERE `guild_id`=%s AND `status`=%s) as quickdrop,
                                 (SELECT COUNT(*) FROM `discord_talkdrop_tmp` WHERE `guild_id`=%s AND `status`=%s) as talkdrop
                      """
                await cur.execute(sql, (
                    guild_id, status, guild_id, status, 
                    guild_id, status, guild_id, status,
                    guild_id, status, guild_id, status
                    )
                )
                result = await cur.fetchone()
                if result:
                    return result['airdrop'] + result['mathtip'] + result['triviatip'] + \
                    result['partydrop'] + result['quickdrop'] + result['talkdrop']
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return 0
# End of FreeTip

# Trade
async def sql_count_open_order_by_sellerid(user_id: str, user_server: str, status: str = None):
    global pool
    user_server = user_server.upper()
    if status is None: status = 'OPEN'
    if status: status = status.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT COUNT(*) FROM `open_order` WHERE `userid_sell` = %s 
                          AND `status`=%s AND `sell_user_server`=%s """
                await cur.execute(sql, (user_id, status, user_server))
                result = await cur.fetchone()
                return int(result['COUNT(*)']) if 'COUNT(*)' in result else 0
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return 0

# use to store data
async def sql_store_openorder(
    coin_sell: str, coin_decimal_sell: str, amount_sell: float,
    amount_sell_after_fee: float, userid_sell: str, coin_get: str, coin_decimal_buy: str,
    amount_get: float, amount_get_after_fee: float, sell_div_get: float,
    sell_user_server: str = 'DISCORD'
):
    global pool
    sell_user_server = sell_user_server.upper()
    if amount_sell == 0 or amount_sell_after_fee == 0 or amount_get == 0 \
            or amount_get_after_fee == 0 or sell_div_get == 0:
        print("Catch zero amount in {sql_store_openorder}!!!")
        return False
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO open_order (`coin_sell`, `coin_sell_decimal`, 
                `amount_sell`, `amount_sell_after_fee`, `userid_sell`, `coin_get`, `coin_get_decimal`, 
                `amount_get`, `amount_get_after_fee`, `sell_div_get`, `order_created_date`, `pair_name`, 
                `status`, `sell_user_server`) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (
                    coin_sell, coin_decimal_sell,
                    amount_sell, amount_sell_after_fee, userid_sell, coin_get, coin_decimal_buy,
                    amount_get, amount_get_after_fee, sell_div_get, float("%.3f" % time.time()),
                    coin_sell + "-" + coin_get,
                    'OPEN', sell_user_server))
                await conn.commit()
                return cur.lastrowid
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

# If in Discord, notified = True
# If API, notified = False
async def sql_match_order_by_sellerid(
    userid_get: str, ref_numb: str, buy_user_server: str, sell_user_server: str,
    userid_sell: str, notified: bool = True
):
    global pool
    buy_user_server = buy_user_server.upper()
    if buy_user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    currentTs = int(time.time())
                    ref_numb = int(ref_numb)
                    sql = """ UPDATE `open_order` SET `status`=%s, `order_completed_date`=%s, 
                              `userid_get` = %s, `buy_user_server`=%s 
                              WHERE `order_id`=%s AND `status`=%s """
                    await cur.execute(sql, (
                    'COMPLETE', float("%.3f" % time.time()), userid_get, buy_user_server, ref_numb, 'OPEN'))
                    await conn.commit()

                    sql = """ SELECT * FROM `open_order` WHERE `order_id` = %s LIMIT 1 """
                    await cur.execute(sql, (ref_numb))
                    result = await cur.fetchone()
                    if result is not None:
                        fee_user = "TRADE"
                        fee_sell = result['amount_sell'] - result['amount_sell_after_fee']
                        fee_get = result['amount_get'] - result['amount_get_after_fee']
                        # credit + / - to balance and add data to it.
                        list_tx = []
                        # from seller to buyer
                        list_tx.append((result['coin_sell'], None, result['userid_sell'], result['userid_get'], "TRADE",
                                        "TRADE", result['amount_sell_after_fee'], 0.0, result['coin_sell_decimal'],
                                        "TRADE", currentTs, sell_user_server, result['userid_sell'],
                                        result['coin_sell'], sell_user_server, -result['amount_sell_after_fee'],
                                        currentTs, result['userid_get'], result['coin_sell'], sell_user_server,
                                        result['amount_sell_after_fee'], currentTs))
                        # from buyer to seller
                        list_tx.append((result['coin_get'], None, result['userid_get'], result['userid_sell'], "TRADE",
                                        "TRADE", result['amount_get_after_fee'], 0.0, result['coin_get_decimal'],
                                        "TRADE", currentTs, sell_user_server, result['userid_get'], result['coin_get'],
                                        sell_user_server, -result['amount_get_after_fee'], currentTs,
                                        result['userid_sell'], result['coin_get'], sell_user_server,
                                        result['amount_get_after_fee'], currentTs))
                        # fee from seller
                        list_tx.append((result['coin_sell'], None, result['userid_sell'], fee_user, "TRADE", "TRADE",
                                        fee_sell, 0.0, result['coin_sell_decimal'], "TRADE", currentTs,
                                        sell_user_server, result['userid_sell'], result['coin_sell'], sell_user_server,
                                        -fee_sell, currentTs, fee_user, result['coin_sell'], sell_user_server, fee_sell,
                                        currentTs))
                        # fee from buyer
                        list_tx.append((result['coin_get'], None, result['userid_get'], fee_user, "TRADE", "TRADE",
                                        fee_get, 0.0, result['coin_get_decimal'], "TRADE", currentTs, sell_user_server,
                                        result['userid_get'], result['coin_get'], sell_user_server, -fee_get, currentTs,
                                        fee_user, result['coin_get'], sell_user_server, fee_get, currentTs))

                        sql = """ INSERT INTO user_balance_mv 
                                  (`token_name`, `contract`, `from_userid`, `to_userid`, `guild_id`, `channel_id`, `real_amount`, `real_amount_usd`, `token_decimal`, `type`, `date`, `user_server`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS DECIMAL(40,18)), CAST(%s AS DECIMAL(40,18)), %s, %s, %s, %s);

                                  INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                                  VALUES (%s, %s, %s, CAST(%s AS DECIMAL(40,18)), %s) ON DUPLICATE KEY 
                                  UPDATE 
                                  `balance`=`balance`+VALUES(`balance`), 
                                  `update_date`=VALUES(`update_date`);

                                  INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                                  VALUES (%s, %s, %s, CAST(%s AS DECIMAL(40,18)), %s) ON DUPLICATE KEY 
                                  UPDATE 
                                  `balance`=`balance`+VALUES(`balance`), 
                                  `update_date`=VALUES(`update_date`);

                                  """
                        await cur.executemany(sql, list_tx)
                        await conn.commit()
                    # Insert into open_order_notify_complete table
                    try:
                        if notified:
                            sql = """ INSERT INTO open_order_notify_complete (`order_id`, `userid_sell`, `complete_date`, `sell_user_server`) 
                                      VALUES (%s, %s, %s, %s) """
                            await cur.execute(sql, (ref_numb, userid_sell, int(time.time()), sell_user_server))
                            await conn.commit()
                        else:
                            sql = """ INSERT INTO open_order_notify_complete (`order_id`, `userid_sell`, `complete_date`, `sell_user_server`, `notified_seller`) 
                                      VALUES (%s, %s, %s, %s, %s) """
                            await cur.execute(sql, (ref_numb, userid_sell, int(time.time()), sell_user_server, "NO"))
                            await conn.commit()
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                    return True
                except ValueError:
                    return False
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

async def sql_get_open_order_by_alluser(
    coin: str, status: str, option: str, limit: int = 50
):
    global pool
    coin_name = coin.upper()
    limit_str = ""
    if limit > 0:
        limit_str = "LIMIT " + str(limit)
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if coin_name != 'ALL' and option.upper() in ["DESC", "ASC"]:
                    sql = """ SELECT * FROM `open_order` 
                    WHERE `status`=%s AND `coin_get`=%s 
                    ORDER BY sell_div_get """ + option.upper() + " " + limit_str
                    await cur.execute(sql, (status, coin_name))
                elif coin_name == 'ALL':
                    sql = """ SELECT * FROM `open_order` 
                    WHERE `status`=%s 
                    ORDER BY order_created_date DESC """ + limit_str
                    await cur.execute(sql, (status))
                else:
                    sql = """ SELECT * FROM `open_order` 
                    WHERE `status`=%s AND `coin_sell`=%s 
                    ORDER BY sell_div_get ASC """ + limit_str
                    await cur.execute(sql, (status, coin_name))
                result = await cur.fetchall()
                return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

async def sql_get_open_order_by_alluser_by_coins(
    coin1: str, coin2: str, status: str, option_order: str, limit: int = 50
):
    global pool
    option_order = option_order.upper()
    if option_order not in ["DESC", "ASC"]:
        return False
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if coin2.upper() == "ALL":
                    sql = """ SELECT * FROM open_order 
                    WHERE `status`=%s AND `coin_sell`=%s 
                    ORDER BY sell_div_get """ + option_order + """ LIMIT """ + str(limit)
                    await cur.execute(sql, (status, coin1.upper()))
                    result = await cur.fetchall()
                    return result
                else:
                    sql = """ SELECT * FROM open_order 
                    WHERE `status`=%s AND `coin_sell`=%s AND `coin_get`=%s 
                    ORDER BY sell_div_get """ + option_order + """ LIMIT """ + str(limit)
                    await cur.execute(sql, (status, coin1.upper(), coin2.upper()))
                    result = await cur.fetchall()
                    return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

async def sql_get_order_numb(order_num: str, status: str = None):
    global pool
    if status is None: status = 'OPEN'
    if status: status = status.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                result = None
                if status == "ANY":
                    sql = """ SELECT * FROM `open_order` WHERE `order_id` = %s LIMIT 1 """
                    await cur.execute(sql, (order_num))
                    result = await cur.fetchone()
                else:
                    sql = """ SELECT * FROM `open_order` WHERE `order_id` = %s 
                              AND `status`=%s LIMIT 1 """
                    await cur.execute(sql, (order_num, status))
                    result = await cur.fetchone()
                return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

async def sql_get_open_order_by_sellerid_all(userid_sell: str, status: str = 'OPEN'):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `open_order` WHERE `userid_sell`=%s 
                          AND `status`=%s ORDER BY order_created_date DESC LIMIT 20 """
                await cur.execute(sql, (userid_sell, status))
                result = await cur.fetchall()
                return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

async def sql_cancel_open_order_by_sellerid(userid_sell: str, coin: str = 'ALL'):
    global pool
    coin_name = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if len(coin) < 6:
                    if coin_name == 'ALL':
                        sql = """ UPDATE open_order SET `status`=%s, `cancel_date`=%s 
                        WHERE `userid_sell`=%s AND `status`=%s """
                        await cur.execute(sql, ('CANCEL', float("%.3f" % time.time()), userid_sell, 'OPEN'))
                        await conn.commit()
                        return True
                    else:
                        sql = """ UPDATE open_order SET `status`=%s, `cancel_date`=%s 
                        WHERE `userid_sell`=%s 
                        AND `status`=%s AND `coin_sell`=%s """
                        await cur.execute(sql, ('CANCEL', float("%.3f" % time.time()), userid_sell, 'OPEN', coin_name))
                        await conn.commit()
                        return True
                else:
                    try:
                        ref_numb = int(coin)
                        sql = """ UPDATE open_order SET `status`=%s, `cancel_date`=%s 
                        WHERE `userid_sell`=%s AND `status`=%s AND `order_id`=%s """
                        await cur.execute(sql, ('CANCEL', float("%.3f" % time.time()), userid_sell, 'OPEN', ref_numb))
                        await conn.commit()
                        return True
                    except ValueError:
                        return False
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

async def sql_get_open_order_by_sellerid(userid_sell: str, coin: str, status: str = 'OPEN'):
    global pool
    coin_name = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `open_order` WHERE `userid_sell`=%s AND `coin_sell` = %s 
                          AND `status`=%s ORDER BY order_created_date DESC LIMIT 20 """
                await cur.execute(sql, (userid_sell, coin_name, status))
                result = await cur.fetchall()
                return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False
# End of Trade

# Faucet / Game stats
async def sql_list_game_coins():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT DISTINCT `coin_name` FROM `coin_bot_reward_games` """
                await cur.execute(sql, )
                result = await cur.fetchall()
                if result and len(result) > 0:
                    return [each['coin_name'] for each in result]
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return []

async def sql_faucet_count_all():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT COUNT(*) FROM discord_faucet """
                await cur.execute(sql, )
                result = await cur.fetchone()
                return int(result['COUNT(*)']) if 'COUNT(*)' in result else 0
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def sql_game_stat(game_coins):
    global pool
    if len(game_coins) == 0: return None
    stat = {}
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM discord_game """
                await cur.execute(sql, )
                result_game = await cur.fetchall()
                if result_game and len(result_game) > 0:
                    stat['paid_play'] = len(result_game)
                    # https://stackoverflow.com/questions/21518271/how-to-sum-values-of-the-same-key-in-a-dictionary
                    stat['paid_hangman_play'] = sum(d.get('HANGMAN', 0) for d in result_game)
                    stat['paid_bagel_play'] = sum(d.get('BAGEL', 0) for d in result_game)
                    stat['paid_slot_play'] = sum(d.get('SLOT', 0) for d in result_game)
                    for each in game_coins:
                        stat[each] = sum(d.get('won_amount', 0) for d in result_game if d['coin_name'] == each)
                sql = """ SELECT * FROM discord_game_free """
                await cur.execute(sql, )
                result_game_free = await cur.fetchall()
                if result_game_free and len(result_game_free) > 0:
                    stat['free_play'] = len(result_game_free)
                    stat['free_hangman_play'] = sum(d.get('HANGMAN', 0) for d in result_game_free)
                    stat['free_bagel_play'] = sum(d.get('BAGEL', 0) for d in result_game_free)
                    stat['free_slot_play'] = sum(d.get('SLOT', 0) for d in result_game_free)
            return stat
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def sql_faucet_sum_count_claimed(coin: str):
    coin_name = coin.upper()
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT SUM(claimed_amount) as claimed, COUNT(claimed_amount) as count FROM discord_faucet
                          WHERE `coin_name`=%s """
                await cur.execute(sql, (coin_name))
                result = await cur.fetchone()
                # {'claimed_amount': xxx, 'count': xxx}
                # print(result)
                return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def sql_discord_userinfo_get(user_id: str, user_server: str = 'DISCORD'):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # select first
                sql = """ SELECT * FROM discord_userinfo 
                          WHERE `user_id` = %s AND `user_server`=%s """
                await cur.execute(sql, (user_id, user_server))
                result = await cur.fetchone()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def sql_roach_get_by_id(roach_id: str, user_server: str = 'DISCORD'):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # select first
                sql = """ SELECT `roach_id`, `main_id`, `date` FROM discord_faucetroach 
                          WHERE (`roach_id` = %s OR `main_id` = %s) AND `user_server`=%s """
                await cur.execute(sql, (roach_id, roach_id, user_server))
                result = await cur.fetchall()
                if result is None:
                    return None
                else:
                    roaches = []
                    for each in result:
                        roaches.append(each['roach_id'])
                        roaches.append(each['main_id'])
                    return set(roaches)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

async def sql_faucet_checkuser(user_id: str, user_server: str = 'DISCORD', type_a: str='TAKE'):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return

    result = None
    list_roach = None
    if user_server == 'DISCORD':
        list_roach = await sql_roach_get_by_id(user_id, user_server)
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if list_roach:
                    roach_sql = "(" + ",".join(list_roach) + ")"
                    sql = """
                    SELECT * FROM discord_faucet WHERE claimed_user IN """ + roach_sql + """ 
                    AND `user_server`=%s AND `type`=%s
                    ORDER BY claimed_at DESC LIMIT 1
                    """
                    await cur.execute(sql, (user_server, type_a))
                else:
                    sql = """
                    SELECT * FROM discord_faucet 
                    WHERE `claimed_user` = %s AND `user_server`=%s AND `type`=%s
                    ORDER BY claimed_at DESC LIMIT 1"""
                    await cur.execute(sql, (user_id, user_server, type_a))
                result = await cur.fetchone()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return result

async def sql_faucet_count_user(user_id: str, user_server: str = 'DISCORD'):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT COUNT(*) FROM discord_faucet 
                WHERE claimed_user = %s AND `user_server`=%s
                """
                await cur.execute(sql, (user_id, user_server))
                result = await cur.fetchone()
                return int(result['COUNT(*)']) if 'COUNT(*)' in result else 0
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def sql_faucet_add(
    claimed_user: str, claimed_server: str, coin_name: str, claimed_amount: float, decimal: int,
    user_server: str = 'DISCORD', type_a: str = 'TAKE'
):
    global pool
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM', 'REDDIT']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO discord_faucet 
                (`claimed_user`, `coin_name`, `claimed_amount`, 
                `decimal`, `claimed_at`, `claimed_server`, `user_server`, `type`) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (
                    claimed_user, coin_name, claimed_amount, decimal,
                    int(time.time()), claimed_server, user_server, type_a
                    )
                )
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None
# End Faucet / Game stats

# Check if approved already
async def erc20_if_approved(
    url: str, contract: str, 
    sender_address: str, operator_address: str
):
    try:
        w3 = Web3(Web3.HTTPProvider(url))
        # inject the poa compatibility middleware to the innermost layer
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        abi = [
            {
                "constant": True,
                "inputs": [
                    {"name": "_owner", "type": "address"},
                    {"name": "_spender", "type": "address"},
                ],
                "name": "allowance",
                "outputs": [{"name": "", "type": "uint256"}],
                "payable": False,
                "stateMutability": "view",
                "type": "function",
            },
        ]
        cnt = w3.eth.contract(address=w3.toChecksumAddress(contract), abi=abi)
        _spender = w3.toChecksumAddress(
            operator_address
        ) 
        spendable_amount = cnt.functions.allowance(w3.toChecksumAddress(sender_address), _spender).call()
        if spendable_amount > 0:
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return False

# TODO: remove
async def erc20_transfer_token_to_operator(
    url: str, chainId: int, contract: str, 
    sender_address: str, operator_address: str, 
    operator_seed: str, atomic_amount: int
):
    try:
        w3 = Web3(Web3.HTTPProvider(url))

        # inject the poa compatibility middleware to the innermost layer
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        # check allowance:
        unicorns = w3.eth.contract(address=w3.toChecksumAddress(contract), abi=EIP20_ABI)
        allowance = unicorns.functions.allowance(w3.toChecksumAddress(sender_address), w3.toChecksumAddress(operator_address)).call()
        if allowance and allowance < atomic_amount:
            print("Contract: {} operator: {} allowance for address: {} is less than amount {} < {}.".format(contract, operator_address, sender_address, allowance, atomic_amount))
            return None

        nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(operator_address))
        unicorn_txn = unicorns.functions.transferFrom(
            w3.toChecksumAddress(sender_address),
            w3.toChecksumAddress(operator_address),
            atomic_amount  # amount to send
        ).buildTransaction({
            'from': w3.toChecksumAddress(operator_address),
            'gasPrice': w3.eth.gasPrice,
            "chainId": chainId,
            'nonce': nonce
        })

        acct = Account.from_mnemonic(
            mnemonic=operator_seed)
        signed_txn = w3.eth.account.signTransaction(unicorn_txn, private_key=acct.key)

        sent_tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
        tx_receipt = w3.eth.waitForTransactionReceipt(sent_tx)
        return tx_receipt.transactionHash.hex() # hash Tx
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return None
## end of approve spender to operator

# Guild
async def sql_updateinfo_by_server(server_id: str, what: str, value: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT `serverid`, `servername`, `prefix`, `default_coin`, `numb_user`, `numb_bot`, `tiponly` 
                          FROM `discord_server` WHERE `serverid`=%s """
                await cur.execute(sql, (server_id,))
                result = await cur.fetchone()
                if result is None:
                    return None
                else:
                    if what in ["servername", "prefix", "default_coin", "tiponly", "status"]:
                        sql = """ UPDATE `discord_server` SET `""" + what + """`=%s WHERE `serverid`=%s """
                        await cur.execute(sql, (value, server_id,))
                        await conn.commit()
                    else:
                        return None
    except Exception as e:
        await logchanbot(str(traceback.format_exc()) + "\n\n" + f"({sql}, ({what}, {value}, {server_id},)")

# Partydrop
async def insert_partydrop_create(
    token_name: str, contract: str, from_userid: str, from_ownername: str,
    message_id: str, guild_id: str, channel_id: str, minimum_amount: float, 
    init_amount: float, real_init_amount_usd: float, real_init_amount_usd_text: str, 
    unit_price_usd: float, token_decimal: int, partydrop_time: int, 
    status: str = "ONGOING"
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO `discord_partydrop_tmp` 
                (`token_name`, `contract`, `from_userid`, `from_ownername`, `message_id`, 
                `guild_id`, `channel_id`, `minimum_amount`, `init_amount`, 
                `real_init_amount_usd`, `real_init_amount_usd_text`, `unit_price_usd`, 
                `token_decimal`, `message_time`, `partydrop_time`, `status`) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (
                    token_name, contract, from_userid, from_ownername, 
                    message_id, guild_id, channel_id, minimum_amount, 
                    init_amount, real_init_amount_usd, real_init_amount_usd_text, 
                    unit_price_usd, token_decimal, int(time.time()), 
                    partydrop_time, status
                    )
                )
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("partydrop create " +str(traceback.format_exc()))
    return False

async def get_party_id(message_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `discord_partydrop_tmp` 
                WHERE `message_id`=%s LIMIT 1
                """
                await cur.execute(sql, message_id)
                result = await cur.fetchone()
                if result:
                    return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def get_all_party(status: str="ONGOING"):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `discord_partydrop_tmp` 
                WHERE `status`=%s
                """
                await cur.execute(sql, status)
                result = await cur.fetchall()
                if result:
                    return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return []

async def get_party_attendant(message_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `discord_partydrop_join` 
                WHERE `message_id`=%s 
                """
                await cur.execute(sql, message_id)
                result = await cur.fetchall()
                if result:
                    return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return []

async def attend_party(
    message_id: str, attendant_id: str, attendant_name: str, 
    joined_amount: float, token_name: str, token_decimal: int
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO `discord_partydrop_join` (`message_id`, `attendant_id`, `attendant_name`, 
                `joined_amount`, `token_name`, `token_decimal`, `inserted_time`) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)  ON DUPLICATE KEY 
                UPDATE 
                `added`=`added`+1,
                `last_added`=VALUES(`inserted_time`),
                `last_amount`=VALUES(`joined_amount`),
                `joined_amount`=`joined_amount`+VALUES(`joined_amount`)
                """
                await cur.execute(sql, (
                    message_id, attendant_id, attendant_name, 
                    joined_amount, token_name, token_decimal, 
                    int(time.time())
                    )
                )
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

async def update_party_id(message_id: str, to_status: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE `discord_partydrop_tmp` 
                SET `status`=%s WHERE `message_id`=%s;
                UPDATE `discord_partydrop_join` 
                SET `status`=%s WHERE `message_id`=%s;
                """
                await cur.execute(sql, (to_status, message_id, 
                                        to_status, message_id))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

async def update_party_id_amount(message_id: str, added_amount: float):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE `discord_partydrop_tmp` 
                SET `init_amount`=`init_amount`+%s WHERE `message_id`=%s
                """
                await cur.execute(sql, (added_amount, message_id))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

async def update_party_failed(message_id: str, turn_off: bool=False):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if turn_off is False:
                    sql = """ UPDATE `discord_partydrop_tmp` 
                    SET `failed_check`=`failed_check`+1 
                    WHERE `message_id`=%s 
                    LIMIT 1
                    """
                    await cur.execute(sql, message_id)
                    await conn.commit()
                    return True
                else:
                    # Change status
                    sql = """ UPDATE `discord_partydrop_tmp` 
                    SET `status`=%s 
                    WHERE `message_id`=%s 
                    LIMIT 1
                    """
                    await cur.execute(sql, ("NOCOLLECT", message_id))
                    await conn.commit()
                    return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False
# End Partydrop

# quickdrop
async def insert_quickdrop_create(
    token_name: str, contract: str, from_userid: str, from_ownername: str,
    message_id: str, guild_id: str, channel_id: str, real_amount: float, 
    real_amount_usd: float, real_amount_usd_text: float, 
    unit_price_usd: float, token_decimal: int, quickdrop_time: int, 
    status: str = "ONGOING", need_verify: int=0
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO `discord_quickdrop` 
                (`token_name`, `contract`, `from_userid`, `from_ownername`, `message_id`, 
                `guild_id`, `channel_id`, `real_amount`, `real_amount_usd`, `real_amount_usd_text`, 
                `unit_price_usd`, `token_decimal`, `message_time`, `expiring_time`, `status`, `need_verify`) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (
                    token_name, contract, from_userid, from_ownername, 
                    message_id, guild_id, channel_id, real_amount, 
                    real_amount_usd, real_amount_usd_text, 
                    unit_price_usd, token_decimal, int(time.time()), 
                    quickdrop_time, status, need_verify
                    )
                )
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("quickdrop create " +str(traceback.format_exc()))
    return False

async def get_all_quickdrop(status: str="ONGOING"):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `discord_quickdrop` 
                WHERE `status`=%s
                """
                await cur.execute(sql, status)
                result = await cur.fetchall()
                if result:
                    return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return []

async def update_quickdrop_id_status(message_id: str, status: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE `discord_quickdrop` 
                SET `status`=%s 
                WHERE `message_id`=%s
                """
                await cur.execute(sql, (status, message_id))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

async def get_quickdrop_id(message_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `discord_quickdrop` 
                WHERE `message_id`=%s LIMIT 1
                """
                await cur.execute(sql, message_id)
                result = await cur.fetchone()
                if result:
                    return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def update_quickdrop_id(
    message_id: str, status: str, collected_id: str, collected_name: str, collected_date: int
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE `discord_quickdrop` 
                SET `status`=%s, `collected_by_userid`=%s, `collected_by_username`=%s, `collected_date`=%s 
                WHERE `message_id`=%s LIMIT 1
                """
                await cur.execute(sql, (status, collected_id, collected_name, collected_date, message_id))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False
# End quickdrop

# Talkdrop
async def insert_talkdrop_create(
    token_name: str, contract: str, from_userid: str, from_ownername: str,
    message_id: str, guild_id: str, channel_id: str, talked_in_channel: str, 
    talked_from_when: int, minimum_message: int, real_amount: float, real_amount_usd: float, 
    real_amount_usd_text: str, unit_price_usd: float, token_decimal: int, 
    talkdrop_time: int, status: str = "ONGOING"
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO `discord_talkdrop_tmp` 
                (`token_name`, `contract`, `from_userid`, `from_ownername`, 
                `message_id`, `guild_id`, `channel_id`, `talked_in_channel`, 
                `talked_from_when`, `minimum_message`, `real_amount`, `real_amount_usd`, 
                `real_amount_usd_text`, `unit_price_usd`, `token_decimal`, `message_time`, 
                `talkdrop_time`, `status`) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (
                    token_name, contract, from_userid, from_ownername, 
                    message_id, guild_id, channel_id, talked_in_channel, talked_from_when, 
                    minimum_message, real_amount, real_amount_usd, real_amount_usd_text, 
                    unit_price_usd, token_decimal, int(time.time()), 
                    talkdrop_time, status
                    )
                )
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot("talkdrop create " +str(traceback.format_exc()))
    return False

async def get_all_talkdrop(status: str="ONGOING"):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `discord_talkdrop_tmp` 
                WHERE `status`=%s
                """
                await cur.execute(sql, status)
                result = await cur.fetchall()
                if result:
                    return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return []

async def get_talkdrop_collectors(message_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `discord_talkdrop_collector` 
                WHERE `message_id`=%s 
                """
                await cur.execute(sql, message_id)
                result = await cur.fetchall()
                if result:
                    return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return []

async def update_talkdrop_id(message_id: str, to_status: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ UPDATE `discord_talkdrop_tmp` 
                SET `status`=%s WHERE `message_id`=%s
                """
                await cur.execute(sql, (to_status, message_id))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

async def get_talkdrop_id(message_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `discord_talkdrop_tmp` 
                WHERE `message_id`=%s LIMIT 1
                """
                await cur.execute(sql, message_id)
                result = await cur.fetchone()
                if result:
                    return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def talkdrop_check_user(
    guild_id: str, channel_id: str, user_id: str, from_when: int
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT COUNT(*) AS talks FROM `discord_messages` 
                WHERE `serverid`=%s AND `channel_id`=%s AND `user_id`=%s AND `message_time`>%s
                """
                await cur.execute(sql, (guild_id, channel_id, user_id, from_when))
                result = await cur.fetchone()
                if result:
                    return result['talks']
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return 0

async def checkin_talkdrop_collector(message_id: str, user_id: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM `discord_talkdrop_collector` 
                WHERE `message_id`=%s AND `collector_id`=%s LIMIT 1
                """
                await cur.execute(sql, (message_id, user_id))
                result = await cur.fetchone()
                if result:
                    return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

async def add_talkdrop(
    message_id: str, from_userid: str, 
    collector_id: str, collector_name: float
):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO `discord_talkdrop_collector` (`message_id`, `from_userid`, `collector_id`, 
                `collector_name`, `inserted_time`) 
                VALUES (%s, %s, %s, %s, %s)
                """
                await cur.execute(sql, (message_id, from_userid, collector_id, 
                                        collector_name, int(time.time())))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

async def update_talkdrop_failed(message_id: str, turn_off: bool=False):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if turn_off is False:
                    sql = """ UPDATE `discord_talkdrop_tmp` 
                    SET `failed_check`=`failed_check`+1 WHERE `message_id`=%s 
                    LIMIT 1
                    """
                    await cur.execute(sql, message_id)
                    await conn.commit()
                    return True
                else:
                    # Change status
                    sql = """ UPDATE `discord_talkdrop_tmp` 
                    SET `status`=%s WHERE `message_id`=%s 
                    LIMIT 1
                    """
                    await cur.execute(sql, ("NOCOLLECT", message_id))
                    await conn.commit()
                    return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False
# End Talkdrop

# Recent Activity
# Same as utils.recent_tips
async def recent_tips(
    user_id: str, user_server: str, token_name: str, coin_family: str, what: str, limit: int
):
    global pool
    coin_name = token_name.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if what.lower() == "withdraw":
                    if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        sql = """ SELECT * FROM `cn_external_tx` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "BTC":
                        sql = """ SELECT * FROM `neo_external_tx` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "NEO":
                        sql = """ SELECT * FROM `doge_external_tx` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "NEAR":
                        sql = """ SELECT * FROM `near_external_tx` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s 
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "NANO":
                        sql = """ SELECT * FROM `nano_external_tx` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "CHIA":
                        sql = """ SELECT * FROM `xch_external_tx` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "ERC-20":
                        sql = """ SELECT * FROM `erc20_external_tx` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s 
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "XTZ":
                        sql = """ SELECT * FROM `tezos_external_tx` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s 
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "ZIL":
                        sql = """ SELECT * FROM `zil_external_tx` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s 
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "VET":
                        sql = """ SELECT * FROM `vet_external_tx` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s 
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "VITE":
                        sql = """ SELECT * FROM `vite_external_tx` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "TRC-20":
                        sql = """ SELECT * FROM `trc20_external_tx` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s 
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "XRP":
                        sql = """ SELECT * FROM `xrp_external_tx` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "XLM":
                        sql = """ SELECT * FROM `xlm_external_tx` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "COSMOS":
                        sql = """ SELECT * FROM `cosmos_external_tx` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s AND `success`=0
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "ADA":
                        sql = """ SELECT * FROM `xlm_external_tx` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "SOL" or coin_family == "SPL":
                        sql = """ SELECT * FROM `sol_external_tx` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s 
                        ORDER BY `date` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                elif what.lower() == "deposit":
                    if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        sql = """
                        SELECT a.*, b.*
                        FROM cn_user_paymentid a
                            INNER JOIN cn_get_transfers b
                                ON a.paymentid = b.payment_id
                        WHERE a.user_id=%s AND a.user_server=%s and a.coin_name=%s
                        ORDER BY b.time_insert DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "BTC":
                        sql = """
                        SELECT a.*, b.*
                        FROM doge_user a
                            INNER JOIN doge_get_transfers b
                                ON a.balance_wallet_address = b.address
                        WHERE a.user_id=%s AND a.user_server=%s and a.coin_name=%s
                        ORDER BY b.time_insert DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "NEO":
                        sql = """
                        SELECT a.*, b.*
                        FROM neo_user a
                            INNER JOIN neo_get_transfers b
                                ON a.balance_wallet_address = b.address
                        WHERE a.user_id=%s AND a.user_server=%s and b.coin_name=%s
                        ORDER BY b.time_insert DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "NEAR":
                        sql = """
                        SELECT * 
                        FROM `near_move_deposit`
                        WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s AND `status`=%s
                        ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name, "CONFIRMED"))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "NANO":
                        sql = """
                        SELECT * 
                        FROM `nano_move_deposit`
                        WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                        ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "CHIA":
                        sql = """
                        SELECT a.*, b.*
                        FROM xch_user a
                            INNER JOIN xch_get_transfers b
                                ON a.balance_wallet_address = b.address
                        WHERE a.user_id=%s AND a.user_server=%s and b.coin_name=%s
                        ORDER BY b.time_insert DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "ERC-20":
                        sql = """
                        SELECT * 
                        FROM `erc20_move_deposit` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s AND `status`=%s
                        ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name, "CONFIRMED"))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "XTZ":
                        sql = """
                        SELECT * 
                        FROM `tezos_move_deposit`
                        WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s AND `status`=%s
                        ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name, "CONFIRMED"))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "ZIL":
                        sql = """
                        SELECT * 
                        FROM `zil_move_deposit` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s
                        ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "VET":
                        sql = """
                        SELECT * 
                        FROM `vet_move_deposit`
                        WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s
                        ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "VITE":
                        sql = """
                        SELECT * 
                        FROM `vite_get_transfers`
                        WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                        ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "TRC-20":
                        sql = """
                        SELECT * 
                        FROM `trc20_move_deposit`
                        WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s AND `status`=%s
                        ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name, "CONFIRMED"))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "XRP":
                        sql = """
                        SELECT * 
                        FROM `xrp_get_transfers` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                        ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "XLM":
                        sql = """
                        SELECT * 
                        FROM `xlm_get_transfers` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                        ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "COSMOS":
                        sql = """
                        SELECT * 
                        FROM `cosmos_get_transfers` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                        ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "ADA":
                        sql = """
                        SELECT * 
                        FROM `ada_get_transfers`
                        WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                        ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name))
                        result = await cur.fetchall()
                        if result:
                            return result
                    elif coin_family == "SOL" or coin_family == "SPL":
                        sql = """
                        SELECT * 
                        FROM `sol_move_deposit` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `token_name`=%s AND `status`=%s
                        ORDER BY `time_insert` DESC LIMIT """+ str(limit)
                        await cur.execute(sql, (user_id, user_server, coin_name, "CONFIRMED"))
                        result = await cur.fetchall()
                        if result:
                            return result
                elif what.lower() == "receive":
                    sql = """ SELECT * FROM `user_balance_mv` 
                    WHERE `to_userid`=%s AND `user_server`=%s AND `token_name`=%s 
                    ORDER BY `date` DESC LIMIT """+ str(limit)
                    await cur.execute(sql, (user_id, user_server, coin_name))
                    result = await cur.fetchall()
                    if result:
                        return result
                elif what.lower() == "expense":
                    sql = """ SELECT * FROM `user_balance_mv` 
                    WHERE `from_userid`=%s AND `user_server`=%s AND `token_name`=%s AND `to_userid`<>%s
                    ORDER BY `date` DESC LIMIT """+ str(limit)
                    await cur.execute(sql, (user_id, user_server, coin_name, "TRADE"))
                    result = await cur.fetchall()
                    if result:
                        return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return []
# End of recent activity
