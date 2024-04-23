import sys
import traceback
from datetime import datetime
from decimal import Decimal
import time
import math
import uuid
import asyncio
import aiohttp
import aiomysql
from aiomysql.cursors import DictCursor
import json
from typing import Dict, Optional
import disnake
from disnake.app_commands import Option
from disnake.enums import OptionType
from disnake.ext import commands, tasks
from cogs.utils import Utils, num_format_coin
from cogs.wallet import WalletAPI
from Bot import SERVER_BOT, log_to_channel, decrypt_string, truncate
import store
import cn_addressvalidation
from cogs.utils import print_color

class AutoSwap(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.pool = None
        self.bot.other_data['autoswap_pairs'] = None
        self.bot.other_data['autoswap_tokens'] = None
        self.bot.other_data['autoswap_tokens_from'] = None
        self.bot.other_data['autoswap_tokens_to'] = None

    async def openConnection(self):
        try:
            if self.pool is None:
                self.pool = await aiomysql.create_pool(
                    host=self.bot.config['mysql']['host'], port=3306, minsize=4, maxsize=8,
                    user=self.bot.config['mysql']['user'], password=self.bot.config['mysql']['password'],
                    db=self.bot.config['mysql']['db'], cursorclass=DictCursor, autocommit=True
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def check_withdraw_coin_address(self, coin_family: str, address: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                await conn.ping(reconnect=True)
                async with conn.cursor() as cur:
                    result = None
                    if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        sql = """ SELECT * FROM `cn_user_paymentid` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "CHIA":
                        sql = """ SELECT * FROM `xch_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "BTC":
                        # if doge family, address is paymentid
                        sql = """ SELECT * FROM `doge_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "NANO":
                        # if doge family, address is paymentid
                        sql = """ SELECT * FROM `nano_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "ADA":
                        # if ADA family, address is paymentid
                        sql = """ SELECT * FROM `ada_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family in ["SOL", "SPL"]:
                        # if SOL family, address is paymentid
                        sql = """ SELECT * FROM `sol_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "ERC-20":
                        sql = """ SELECT * FROM `erc20_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "TRC-20":
                        sql = """ SELECT * FROM `trc20_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "XTZ":
                        sql = """ SELECT * FROM `tezos_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "ZIL":
                        sql = """ SELECT * FROM `zil_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "NEAR":
                        sql = """ SELECT * FROM `near_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return result

    async def cex_sell_swapper(
        self, amount: str, sell_token: str, for_token: str, timeout: int=10
    ):
        try:
            headers = {
                'Authorization': self.bot.config['autoswap']['autoswapper_key'],
                'Content-Type': 'application/json',
            }
            data = '{"method": "sell", "params": [{"amount": "'+amount+'", "sell_token": "'+sell_token+'", "for_token": "'+for_token+'"}], "id": 99}'
            json_data = json.loads(data)
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.bot.config['autoswap']['cexapi_sell_backend'],
                    headers=headers,
                    json=json_data,
                    timeout=timeout
                ) as response:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if decoded_data['success'] is True:
                        return decoded_data
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def cex_get_lp_info(
        self, pair: str, timeout: int=10
    ):
        try:
            headers = {
                'Content-Type': 'application/json'
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(self.bot.config['autoswap']['cexapi_pub_summary'] + pair, headers=headers, timeout=timeout) as response:
                    json_resp = await response.json()
                    if response.status == 200 or response.status == 201:
                        return json_resp['result']
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def gettopblock(self, coin: str, time_out: int = None):
        coin_name = coin.upper()
        coin_family = getattr(getattr(self.bot.coin_list, coin_name), "type")
        get_daemon_rpc_url = getattr(getattr(self.bot.coin_list, coin_name), "daemon_address")
        result = None
        timeout = time_out or 32

        if coin_name in ["LTHN"] or coin_family in ["BCN", "TRTL-API", "TRTL-SERVICE"]:
            method_name = "getblockcount"
            full_payload = {
                'params': {},
                'jsonrpc': '2.0',
                'id': str(uuid.uuid4()),
                'method': f'{method_name}'
            }
            try:

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        get_daemon_rpc_url + '/json_rpc',
                        json=full_payload,
                        timeout=timeout
                    ) as response:
                        if response.status == 200:
                            res_data = await response.json()
                            result = None
                            if res_data and 'result' in res_data:
                                result = res_data['result']
                            else:
                                result = res_data
                            if result:
                                full_payload = {
                                    'jsonrpc': '2.0',
                                    'method': 'getblockheaderbyheight',
                                    'params': {'height': result['count'] - 1}
                                }
                                try:
                                    async with aiohttp.ClientSession() as session:
                                        async with session.post(
                                            get_daemon_rpc_url + '/json_rpc',
                                            json=full_payload,
                                            timeout=timeout
                                        ) as response:
                                            if response.status == 200:
                                                res_data = await response.json()
                                                if 'result' in res_data:
                                                    return res_data['result']
                                                else:
                                                    print("Couldn't get result for coin: {}".format(coin_name))
                                            else:
                                                print("Coin {} got response status: {}".format(coin_name, response.status))
                                except asyncio.TimeoutError:
                                    traceback.print_exc(file=sys.stdout)
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            return None
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return None
        elif coin_family == "XMR":
            method_name = "get_block_count"
            full_payload = {
                'params': {},
                'jsonrpc': '2.0',
                'id': str(uuid.uuid4()),
                'method': f'{method_name}'
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        get_daemon_rpc_url + '/json_rpc',
                        json=full_payload,
                        timeout=timeout
                    ) as response:
                        if response.status == 200:
                            try:
                                res_data = await response.json()
                            except Exception:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                res_data = json.loads(res_data)
                            result = None
                            if res_data and 'result' in res_data:
                                result = res_data['result']
                            else:
                                result = res_data
                            if result:
                                full_payload = {
                                    'jsonrpc': '2.0',
                                    'method': 'get_block_header_by_height',
                                    'params': {'height': result['count'] - 1}
                                }
                                try:
                                    async with aiohttp.ClientSession() as session:
                                        async with session.post(
                                            get_daemon_rpc_url + '/json_rpc',
                                            json=full_payload,
                                            timeout=timeout
                                        ) as response:
                                            if response.status == 200:
                                                res_data = await response.json()
                                                if res_data and 'result' in res_data:
                                                    return res_data['result']
                                                else:
                                                    return res_data
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            return None
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return None

    async def trtl_api_get_transfers(
        self, url: str, key: str, height_start: int = None,
        height_end: int = None
    ):
        time_out = 30
        method = "/transactions"
        headers = {
            'X-API-KEY': key,
            'Content-Type': 'application/json'
        }
        if (height_start is None) or (height_end is None):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url + method, headers=headers, timeout=time_out) as response:
                        json_resp = await response.json()
                        if response.status == 200 or response.status == 201:
                            return json_resp['transactions']
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif height_start and height_end:
            method += '/' + str(height_start) + '/' + str(height_end)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url + method, headers=headers, timeout=time_out) as response:
                        json_resp = await response.json()
                        if response.status == 200 or response.status == 201:
                            return json_resp['transactions']
            except Exception:
                traceback.print_exc(file=sys.stdout)

    async def trtl_service_getTransactions(
        self, url: str, coin: str, firstBlockIndex: int = 2000000,
        blockCount: int = 200000
    ):
        coin_name = coin.upper()
        time_out = 60
        payload = {
            'firstBlockIndex': firstBlockIndex if firstBlockIndex > 0 else 1,
            'blockCount': blockCount,
        }
        result = await self.call_aiohttp_wallet_xmr_bcn(
            'getTransactions', coin_name, time_out=time_out, payload=payload
        )
        if result and 'items' in result:
            return result['items']
        return []

    async def create_address(
        self, user_id: str, user_server: str, from_coin: str
    ):
        try:
            coin_name = from_coin.upper()
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            if type_coin.upper() in ["TRTL-API", "TRTL-SERVICE", "BCN"]:
                # passed test WRKZ, DEGO
                main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                get_prefix_char = getattr(getattr(self.bot.coin_list, coin_name), "get_prefix_char")
                get_prefix = getattr(getattr(self.bot.coin_list, coin_name), "get_prefix")
                get_addrlen = getattr(getattr(self.bot.coin_list, coin_name), "get_addrlen")
                balance_address = {}
                balance_address['payment_id'] = cn_addressvalidation.paymentid()
                balance_address['integrated_address'] = cn_addressvalidation.cn_make_integrated(
                    main_address, get_prefix_char, get_prefix, get_addrlen,
                    balance_address['payment_id']
                )['integrated_address']
                return {
                    "user_id": user_id,
                    "user_server": user_server,
                    "from_coin": coin_name,
                    "from_address": balance_address['integrated_address'],
                    "from_address_extra": balance_address['payment_id'],
                    "from_privateKey": None,
                    "created_ts": int(time.time())
                }
            elif type_coin.upper() == "XMR":
                main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                paymentid = cn_addressvalidation.paymentid(8)
                payload = {
                    "standard_address": main_address,
                    "payment_id": paymentid
                }
                address_ia = await self.call_aiohttp_wallet_xmr_bcn('make_integrated_address', coin_name, payload=payload)
                return {
                    "user_id": user_id,
                    "user_server": user_server,
                    "from_coin": coin_name,
                    "from_address": address_ia['integrated_address'],
                    "from_address_extra": paymentid,
                    "from_privateKey": None,
                    "created_ts": int(time.time())
                }
            elif type_coin.upper() == "NANO":
                walletkey = decrypt_string(getattr(getattr(self.bot.coin_list, coin_name), "walletkey"))
                balance_address = await self.call_nano(
                    coin_name, payload='{ "action": "account_create", "wallet": "' + walletkey + '" }'
                )
                return {
                    "user_id": user_id,
                    "user_server": user_server,
                    "from_coin": coin_name,
                    "from_address": balance_address['account'],
                    "from_address_extra": None,
                    "from_privateKey": None,
                    "created_ts": int(time.time())
                }
            elif type_coin.upper() == "BTC":
                naming = self.bot.config['kv_db']['prefix'] + "_" + user_server + "_" + str(user_id) + '_SWAP'
                payload = f'"{naming}"'
                if coin_name in ["BTCZ", "VTC", "ZEC", "FLUX"]:
                    payload = ''
                elif coin_name in ["HNS"]:
                    payload = '"default"'
                address_call = await self.call_doge('getnewaddress', coin_name, payload=payload)
                reg_address = {}
                reg_address['address'] = address_call
                payload = f'"{address_call}"'
                key_call = await self.call_doge('dumpprivkey', coin_name, payload=payload)
                reg_address['privateKey'] = key_call
                if reg_address['address'] and reg_address['privateKey']:
                    balance_address = reg_address
                    return {
                        "user_id": user_id,
                        "user_server": user_server,
                        "from_coin": coin_name,
                        "from_address": balance_address['address'],
                        "from_address_extra": None,
                        "from_privateKey": reg_address['privateKey'],
                        "created_ts": int(time.time())
                    }
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def history_deposit(
        self, user_id: str, user_server: str, coin_name: str = None
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                await conn.ping(reconnect=True)
                async with conn.cursor() as cur:
                    coin_sql = ""
                    row_data = [user_id, user_server, "YES"]
                    if coin_name:
                        coin_sql = " AND `coin_name`=%s"
                        row_data.append(coin_name)
                    sql = """
                    SELECT * FROM `autoswap_deposits` 
                    WHERE `user_id`=%s AND `user_server`=%s AND `can_credit`=%s
                    """ + coin_sql + """
                    ORDER BY `time_insert` DESC LIMIT 20;
                    """
                    await cur.execute(sql, tuple(row_data))
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def history_withraw(
        self, user_id: str, user_server: str, coin_name: str = None
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                await conn.ping(reconnect=True)
                async with conn.cursor() as cur:
                    coin_sql = ""
                    row_data = [user_id, user_server, 1]
                    if coin_name:
                        coin_sql = " AND `to_coin`=%s"
                        row_data.append(coin_name)
                    sql = """
                    SELECT * FROM `autoswap_withdraw` 
                    WHERE `user_id`=%s AND `user_server`=%s AND `success`=%s
                    """ + coin_sql + """
                    ORDER BY `withdraw_ts` DESC LIMIT 20;
                    """
                    await cur.execute(sql, tuple(row_data))
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def pair_list(
        self
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                await conn.ping(reconnect=True)
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `autoswap_list_pairs` 
                    WHERE `enable`=%s
                    ORDER BY `from_coin` ASC, `to_coin` ASC
                    """
                    await cur.execute(sql, (
                        1
                    ))
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []   

    async def user_mylist(
        self, user_id: str, user_server: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                await conn.ping(reconnect=True)
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `autoswap_list_users` 
                    WHERE `user_id`=%s AND `user_server`=%s 
                    ORDER BY `from_coin` ASC, `to_coin` ASC
                    """
                    await cur.execute(sql, (
                        user_id, user_server
                    ))
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []    

    async def user_add_pair(
        self, user_id: str, user_server: str, from_coin: str, from_address: str, 
        from_address_extra: str, from_privateKey: str, to_coin: str, to_address: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                await conn.ping(reconnect=True)
                async with conn.cursor() as cur:
                    sql = """
                    INSERT INTO `autoswap_list_users` 
                    (`user_id`, `user_server`, `from_coin`, `from_address`, `from_address_extra`, `from_privateKey`, `to_coin`, `to_address`, `created_ts`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    await cur.execute(sql, (
                        user_id, user_server, from_coin, from_address, 
                        from_address_extra, from_privateKey, to_coin, to_address, int(time.time())
                    ))
                    await conn.commit()
                    return cur.lastrowid
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return 0

    async def user_del_pair(
        self, user_id: str, user_server: str, from_coin: str, to_coin: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                await conn.ping(reconnect=True)
                async with conn.cursor() as cur:
                    sql = """
                    DELETE FROM `autoswap_list_users` 
                    WHERE `user_id`=%s AND `user_server`=%s AND `from_coin`=%s AND `to_coin`=%s
                    LIMIT 1;
                    """
                    await cur.execute(sql, (
                        user_id, user_server, from_coin, to_coin
                    ))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def get_userwallet_by_extra(self, paymentid: str, coin: str, coin_family: str):
        coin_name = coin.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                await conn.ping(reconnect=True)
                async with conn.cursor() as cur:
                    result = None
                    if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        sql = """
                        SELECT * FROM `autoswap_list_users` 
                        WHERE `from_address_extra`=%s AND `from_coin`=%s LIMIT 1;
                        """
                        await cur.execute(sql, (paymentid, coin_name))
                        result = await cur.fetchone()
                    elif coin_family in ["BTC", "NANO"]:
                        # if doge family, address is paymentid
                        sql = """
                        SELECT * FROM `autoswap_list_users` 
                        WHERE `from_address`=%s AND `from_coin`=%s LIMIT 1;
                        """
                        await cur.execute(sql, (paymentid, coin_name))
                        result = await cur.fetchone()
                    return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None

    # Wallet things
    async def call_doge(self, method_name: str, coin: str, payload: str = None) -> Dict:
        timeout = 150
        coin_name = coin.upper()
        headers = {
            'content-type': 'text/plain;',
        }
        if coin_name in ["HNS"]:
            if payload is None:
                data = '{"method": "' + method_name + '" }'
            else:
                data = '{"method": "' + method_name + '", "params": [' + payload + '] }'
        else:
            if payload is None:
                data = '{"jsonrpc": "1.0", "id":"' + str(
                    uuid.uuid4()) + '", "method": "' + method_name + '", "params": [] }'
            else:
                data = '{"jsonrpc": "1.0", "id":"' + str(
                    uuid.uuid4()) + '", "method": "' + method_name + '", "params": [' + payload + '] }'

        url = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
        if method_name == "getblockchaininfo" or method_name == "getinfo":  # daemon
            url = getattr(getattr(self.bot.coin_list, coin_name), "daemon_address")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data, timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        decoded_data = json.loads(res_data)
                        return decoded_data['result']
                    else:
                        print(f'Call {coin_name} returns {str(response.status)} with method {method_name}')
                        print(data)
        except (aiohttp.client_exceptions.ServerDisconnectedError, aiohttp.client_exceptions.ClientOSError):
            print("call_doge: got disconnected for coin: {}".format(coin_name))
        except asyncio.TimeoutError:
            print('TIMEOUT: method_name: {} - COIN: {} - timeout {}'.format(method_name, coin.upper(), timeout))
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def send_external_doge(
        self, user_from: str, amount: float, to_address: str, coin: str
    ):
        coin_name = coin.upper()
        try:
            comment = user_from
            comment_to = to_address
            payload = f'"{to_address}", {amount}, "{comment}", "{comment_to}", false'
            if getattr(getattr(self.bot.coin_list, coin_name), "coin_has_pos") == 1:
                payload = f'"{to_address}", {amount}, "{comment}", "{comment_to}"'
            txHash = await self.call_doge('sendtoaddress', coin_name, payload=payload)
            if txHash:
                return txHash
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def call_nano(self, coin: str, payload: str) -> Dict:
        timeout = 100
        coin_name = coin.upper()
        url = getattr(getattr(self.bot.coin_list, coin_name), "rpchost")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload, timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        decoded_data = json.loads(res_data)
                        return decoded_data
        except asyncio.TimeoutError:
            print('TIMEOUT: COIN: {} - timeout {}'.format(coin.upper(), timeout))
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def nano_sendtoaddress(
        self, source: str, to_address: str, atomic_amount: int, coin: str
    ) -> str:
        coin_name = coin.upper()
        walletkey = decrypt_string(getattr(getattr(self.bot.coin_list, coin_name), "walletkey"))
        payload = '{ "action": "send", "wallet": "' + walletkey + '", "source": "' + source + '", "destination": "' + to_address + '", "amount": "' + str(atomic_amount) + '" }'
        sending = await self.call_nano(coin_name, payload=payload)
        if sending and 'block' in sending:
            return sending
        return None

    async def send_external_xmr(
        self, type_coin: str, from_address: str, amount: float, to_address: str,
        coin: str, coin_decimal: int, tx_fee: float, is_fee_per_byte: int,
        get_mixin: int, wallet_api_url: str, wallet_api_header: str
    ):
        coin_name = coin.upper()
        time_out = 150
        if coin_name == "DEGO":
            time_out = 300
        try:
            if type_coin == "XMR":
                acc_index = 0
                payload = {
                    "destinations": [{'amount': int(amount * 10 ** coin_decimal), 'address': to_address}],
                    "account_index": acc_index,
                    "subaddr_indices": [],
                    "priority": 1,
                    "unlock_time": 0,
                    "get_tx_key": True,
                    "get_tx_hex": False,
                    "get_tx_metadata": False
                }
                if coin_name == "UPX":
                    payload = {
                        "destinations": [{'amount': int(amount * 10 ** coin_decimal), 'address': to_address}],
                        "account_index": acc_index,
                        "subaddr_indices": [],
                        "ring_size": 11,
                        "get_tx_key": True,
                        "get_tx_hex": False,
                        "get_tx_metadata": False
                    }
                result = await self.call_aiohttp_wallet_xmr_bcn(
                    'transfer', coin_name, time_out=time_out, payload=payload
                )
                if result and 'tx_hash' in result and 'tx_key' in result:
                    return {"hash": result['tx_hash'], "key": result['tx_key']}
            elif type_coin == "TRTL-SERVICE" or type_coin == "BCN":
                if is_fee_per_byte != 1:
                    payload = {
                        'addresses': [from_address],
                        'transfers': [{
                            "amount": int(amount * 10 ** coin_decimal),
                            "address": to_address
                        }],
                        'fee': int(tx_fee * 10 ** coin_decimal),
                        'anonymity': get_mixin
                    }
                else:
                    payload = {
                        'addresses': [from_address],
                        'transfers': [{
                            "amount": int(amount * 10 ** coin_decimal),
                            "address": to_address
                        }],
                        'anonymity': get_mixin
                    }
                result = await self.call_aiohttp_wallet_xmr_bcn(
                    'sendTransaction', coin_name, time_out=time_out, payload=payload
                )
                if result and 'transactionHash' in result:
                    return {"hash": result['transactionHash'], "key": None}
            elif type_coin == "TRTL-API":
                if is_fee_per_byte != 1:
                    json_data = {
                        "destinations": [{"address": to_address, "amount": int(amount * 10 ** coin_decimal)}],
                        "mixin": get_mixin,
                        "fee": int(tx_fee * 10 ** coin_decimal),
                        "sourceAddresses": [
                            from_address
                        ],
                        "paymentID": "",
                        "changeAddress": from_address
                    }
                else:
                    json_data = {
                        "destinations": [{"address": to_address, "amount": int(amount * 10 ** coin_decimal)}],
                        "mixin": get_mixin,
                        "sourceAddresses": [
                            from_address
                        ],
                        "paymentID": "",
                        "changeAddress": from_address
                    }
                method = "/transactions/send/advanced"
                try:
                    headers = {
                        'X-API-KEY': wallet_api_header,
                        'Content-Type': 'application/json'
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            wallet_api_url + method,
                            headers=headers,
                            json=json_data,
                            timeout=time_out
                        ) as response:
                            json_resp = await response.json()
                            if response.status == 200 or response.status == 201:
                                return {"hash": json_resp['transactionHash'], "key": None}
                except Exception:
                    traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def call_aiohttp_wallet_xmr_bcn(
        self, method_name: str, coin: str, time_out: int = None,
        payload: Dict = None
    ) -> Dict:
        coin_name = coin.upper()
        coin_family = getattr(getattr(self.bot.coin_list, coin_name), "type")
        full_payload = {
            'params': payload or {},
            'jsonrpc': '2.0',
            'id': str(uuid.uuid4()),
            'method': f'{method_name}'
        }
        url = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
        timeout = time_out or 60
        if method_name == "save" or method_name == "store":
            timeout = 300
        elif method_name == "sendTransaction":
            timeout = 180
        elif method_name == "createAddress" or method_name == "getSpendKeys":
            timeout = 60
        try:
            if coin_family == "XMR":
                try:
                    async with aiohttp.ClientSession(headers={'Content-Type': 'application/json'}) as session:
                        async with session.post(url, json=full_payload, timeout=timeout) as response:
                            # sometimes => "message": "Not enough unlocked money" for checking fee
                            if method_name == "transfer":
                                print('{} - transfer'.format(coin_name))
                                # print(full_payload)
                            if response.status == 200:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                if method_name == "transfer":
                                    print(res_data)

                                decoded_data = json.loads(res_data)
                                if 'result' in decoded_data:
                                    return decoded_data['result']
                                else:
                                    return None
                except asyncio.TimeoutError:
                    print('TIMEOUT: {} coin_name {} - timeout {}'.format(method_name, coin_name, timeout))
                    return None
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    return None
            elif coin_family in ["TRTL-SERVICE", "BCN"]:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, json=full_payload, timeout=timeout) as response:
                            if response.status == 200 or response.status == 201:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')

                                decoded_data = json.loads(res_data)
                                if 'result' in decoded_data:
                                    return decoded_data['result']
                            return None
                except asyncio.TimeoutError:
                    print('TIMEOUT: {} coin_name {} - timeout {}'.format(method_name, coin_name, timeout))
                    return None
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    return None
        except asyncio.TimeoutError:
            print('TIMEOUT: method_name: {} - coin_family: {} - timeout {}'.format(method_name, coin_family, timeout))
        except Exception:
            traceback.print_exc(file=sys.stdout)

    # To use with update_balance_trtl_api()
    async def update_balance_tasks_trtl_api(self, coin_name: str, debug: bool):
        if debug is True:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} Check balance {coin_name}", color="yellow")
        gettopblock = await self.gettopblock(coin_name, time_out=60)
        if gettopblock is None:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} Got None for top block {coin_name}", color="yellow")
            return
        height = int(gettopblock['block_header']['height'])
        try:
            await self.utils.async_set_cache_kv(
                "block",
                f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}",
                height
            )
        except Exception:
            traceback.print_exc(file=sys.stdout)

        url = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
        key = getattr(getattr(self.bot.coin_list, coin_name), "header")
        get_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        get_min_deposit_amount = int(
            getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit") * 10 ** coin_decimal)

        get_transfers = await self.trtl_api_get_transfers(url, key, height - 2000, height)
        list_balance_user = {}
        if get_transfers and len(get_transfers) >= 1:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                await conn.ping(reconnect=True)
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `autoswap_deposits` WHERE `coin_name`=%s """
                    await cur.execute(sql, (coin_name,))
                    result = await cur.fetchall()
                    d = [i['txid'] for i in result]
                    # print('=================='+coin_name+'===========')
                    # print(d)
                    # print('=================='+coin_name+'===========')
                    for tx in get_transfers:
                        # Could be one block has two or more tx with different payment ID
                        # add to balance only confirmation depth meet
                        if len(tx['transfers']) > 0 and height >= int(tx['blockHeight']) + get_confirm_depth and \
                            tx['transfers'][0]['amount'] >= get_min_deposit_amount and 'paymentID' in tx:
                            if 'paymentID' in tx and tx['paymentID'] in list_balance_user:
                                if tx['transfers'][0]['amount'] > 0:
                                    list_balance_user[tx['paymentID']] += tx['transfers'][0]['amount']
                            elif 'paymentID' in tx and tx['paymentID'] not in list_balance_user:
                                if tx['transfers'][0]['amount'] > 0:
                                    list_balance_user[tx['paymentID']] = tx['transfers'][0]['amount']
                            try:
                                if tx['hash'] not in d:
                                    if 'paymentID' in tx and len(tx['paymentID']) > 0:
                                        try:
                                            user_paymentId = await self.get_userwallet_by_extra(
                                                tx['paymentID'], coin_name,
                                                getattr(getattr(self.bot.coin_list, coin_name), "type")
                                            )
                                            u_server = None
                                            user_id = None
                                            if user_paymentId:
                                                u_server = user_paymentId['user_server']
                                                user_id = user_paymentId['user_id']
                                            if user_id is None:
                                                continue
                                            sql = """
                                            INSERT IGNORE INTO `autoswap_deposits` 
                                            (`coin_name`, `user_id`, `user_server`, `txid`, `blockhash`, `address`, `extra`, `height`, `amount`, `confirmations`, `time_insert`) 
                                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                            """
                                            await cur.execute(sql, (
                                                coin_name, user_id, u_server, tx['hash'], None, None, tx['paymentID'], tx['blockHeight'],
                                                float(int(tx['transfers'][0]['amount']) / 10 ** coin_decimal), height - tx['blockHeight'], int(time.time())
                                            ))
                                            await conn.commit()
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
        if debug is True:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} End check balance {coin_name}", color="green")
        return True

    # To use with update_balance_xmr()
    async def update_balance_tasks_xmr(self, coin_name: str, debug: bool):
        if debug is True:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} Check balance {coin_name}", color="yellow")
        gettopblock = await self.gettopblock(coin_name, time_out=60)
        if gettopblock is None:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} Got None for top block {coin_name}", color="yellow")
            return
        height = int(gettopblock['block_header']['height'])
        try:
            await self.utils.async_set_cache_kv(
                "block",
                f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}",
                height
            )
        except Exception:
            traceback.print_exc(file=sys.stdout)

        get_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        get_min_deposit_amount = int(
            getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit") * 10 ** coin_decimal)

        payload = {
            "in": True,
            "out": True,
            "pending": False,
            "failed": False,
            "pool": False,
            "filter_by_height": True,
            "min_height": height - 2000,
            "max_height": height
        }

        get_transfers = await self.call_aiohttp_wallet_xmr_bcn(
            'get_transfers', coin_name, payload=payload
        )
        if get_transfers and len(get_transfers) >= 1 and 'in' in get_transfers:
            try:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    await conn.ping(reconnect=True)
                    async with conn.cursor() as cur:
                        sql = """ SELECT * FROM `autoswap_deposits` WHERE `coin_name`=%s """
                        await cur.execute(sql, (coin_name,))
                        result = await cur.fetchall()
                        d = [i['txid'] for i in result]
                        # print('=================='+coin_name+'===========')
                        # print(d)
                        # print('=================='+coin_name+'===========')
                        list_balance_user = {}
                        for tx in get_transfers['in']:
                            # add to balance only confirmation depth meet
                            if height >= int(tx['height']) + get_confirm_depth and tx['amount'] >= get_min_deposit_amount and 'payment_id' in tx:
                                if 'payment_id' in tx and tx['payment_id'] in list_balance_user:
                                    list_balance_user[tx['payment_id']] += tx['amount']
                                elif 'payment_id' in tx and tx['payment_id'] not in list_balance_user:
                                    list_balance_user[tx['payment_id']] = tx['amount']
                                try:
                                    if tx['txid'] not in d:
                                        user_paymentId = await self.get_userwallet_by_extra(
                                            tx['payment_id'], coin_name,
                                            getattr(getattr(self.bot.coin_list, coin_name), "type"))
                                        u_server = None
                                        user_id = None
                                        if user_paymentId:
                                            u_server = user_paymentId['user_server']
                                            user_id = user_paymentId['user_id']
                                        if user_id is None:
                                            continue
                                        sql = """
                                        INSERT IGNORE INTO `autoswap_deposits` 
                                        (`coin_name`, `user_id`, `user_server`, `txid`, `blockhash`, `address`, `extra`, `height`, `amount`, `confirmations`, `time_insert`) 
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                        """
                                        await cur.execute(sql, (
                                            coin_name, user_id, u_server, tx['txid'], None, None, tx['payment_id'], tx['height'],
                                            float(tx['amount'] / 10 ** coin_decimal), height - tx['height'], int(time.time())
                                        ))
                                        await conn.commit()
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
            except Exception:
                traceback.print_exc(file=sys.stdout)
        if debug is True:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} End check balance {coin_name}", color="green")
        return True

    # to use with update_balance_btc()
    async def update_balance_tasks_btc(self, coin_name: str, debug: bool):
        if debug is True:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} Check balance {coin_name}", color="yellow")
        gettopblock = None
        if getattr(getattr(self.bot.coin_list, coin_name), "use_getinfo_btc") == 1:
            gettopblock = await self.call_doge('getinfo', coin_name)
        else:
            gettopblock = await self.call_doge('getblockchaininfo', coin_name)
        if gettopblock is None:
            return False
        height = int(gettopblock['blocks'])
        try:
            await self.utils.async_set_cache_kv(
                "block",
                f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}",
                height
            )
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(1.0)
            return False

        get_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        get_min_deposit_amount = int(
            getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit") * 10 ** coin_decimal)

        payload = '"*", 100, 0'
        if coin_name in ["HNS"]:
            payload = '"default"'
        get_transfers = await self.call_doge('listtransactions', coin_name, payload=payload)
        if get_transfers and len(get_transfers) >= 1:
            try:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    await conn.ping(reconnect=True)
                    async with conn.cursor() as cur:
                        sql = """
                        SELECT * FROM `autoswap_deposits` 
                        WHERE `coin_name`=%s
                        """
                        await cur.execute(sql, (coin_name))
                        result = await cur.fetchall()
                        d = ["{}_{}".format(i['txid'], i['address']) for i in result]
                        # print('=================='+coin_name+'===========')
                        # print(d)
                        # print('=================='+coin_name+'===========')
                        list_balance_user = {}
                        for tx in get_transfers:
                            # add to balance only confirmation depth meet
                            if get_confirm_depth <= int(tx['confirmations']) and tx['amount'] >= get_min_deposit_amount:
                                if 'address' in tx and tx['address'] in list_balance_user and tx['amount'] > 0:
                                    list_balance_user[tx['address']] += tx['amount']
                                elif 'address' in tx and tx['address'] not in list_balance_user and tx['amount'] > 0:
                                    list_balance_user[tx['address']] = tx['amount']
                                try:
                                    if tx.get('address') is None and tx.get('category') and tx['category'] == "send":
                                        continue
                                    if "{}_{}".format(tx['txid'], tx['address']) not in d:
                                        user_paymentId = await self.get_userwallet_by_extra(
                                            tx['address'], coin_name,
                                            getattr(getattr(self.bot.coin_list, coin_name), "type")
                                        )
                                        u_server = None
                                        user_id = None
                                        if user_paymentId:
                                            u_server = user_paymentId['user_server']
                                            user_id = user_paymentId['user_id']
                                        if user_id is None:
                                            # Skipped for None
                                            continue
                                        if tx['category'] == 'receive':
                                            sql = """
                                            INSERT IGNORE INTO `autoswap_deposits` 
                                            (`coin_name`, `user_id`, `user_server`, `txid`, `blockhash`, `address`, `amount`, `confirmations`, `time_insert`) 
                                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                            """
                                            await cur.execute(sql, (
                                                coin_name, user_id, u_server, tx['txid'], tx['blockhash'], tx['address'],
                                                float(tx['amount']), tx['confirmations'], int(time.time())
                                            ))
                                            await conn.commit()
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
            except Exception:
                traceback.print_exc(file=sys.stdout)
        if debug is True:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} End check balance {coin_name}", color="green")
    # End of wallet thing

    @commands.slash_command(
        name="autoswap",
        description="Autoswap commands/sub-commands."
    )
    async def autoswap(self, ctx):
        if self.bot.config['autoswap']['is_private'] == 1 and ctx.author.id not in self.bot.config['autoswap']['testers']:
            await ctx.response.send_message(content=f"{ctx.author.mention}, this command is not public yet. Please try again later!", ephemeral=True)
            return

    @autoswap.sub_command_group(
        name="history",
        usage="autoswap history",
        description="List history of /autoswap",
    )
    async def autoswap_history(
        self,
        ctx
    ):
        pass

    @autoswap_history.sub_command(
        name="deposit",
        usage="autoswap history deposit",
        options=[
            Option("token", "coin/token", OptionType.string, required=False)
        ],
        description = "List history of an autoswap pair for deposit."
    )
    async def autoswap_history_deposit(
        self,
        ctx,
        token: str = None
    ):
        await ctx.response.defer(ephemeral=True)
        try:
            mylist = await self.user_mylist(str(ctx.author.id), SERVER_BOT)
            if len(mylist) == 0:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, you didn't create any autoswap pair yet.")
            else:
                if token and token.upper() not in self.bot.other_data['autoswap_tokens']:
                    await ctx.edit_original_message(content=f"{ctx.author.mention}, **{token}** is not available!")
                    return
                else:
                    get_list = await self.history_deposit(
                        str(ctx.author.id), SERVER_BOT, token.upper() if token is not None else None
                    )
                    if len(get_list) == 0:
                        await ctx.edit_original_message(content=f"{ctx.author.mention}, there is no history of deposit.")
                    else:
                        list_msg = []
                        for c, each in enumerate(get_list, start=1):
                            list_msg.append("{}) tx: {}..{} - {} {} <t:{}:f>.".format(
                                c, each['txid'][0:6], each['txid'][-7:], each['amount'], each['coin_name'], each['time_insert']
                            ))
                        await ctx.edit_original_message(content="{}, list autoswap deposit(s):\n{}".format(
                            ctx.author.mention, "\n".join(list_msg)
                        ))
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await ctx.edit_original_message(content=f"{ctx.author.mention}, internal error!")

    @autoswap_history.sub_command(
        name="withdraw",
        usage="autoswap history withdraw",
        options=[
            Option("token", "coin/token", OptionType.string, required=False)
        ],
        description = "List history of an autoswap pair for withdraw."
    )
    async def autoswap_history_withdraw(
        self,
        ctx,
        token: str = None
    ):
        await ctx.response.defer(ephemeral=True)
        try:
            mylist = await self.user_mylist(str(ctx.author.id), SERVER_BOT)
            if len(mylist) == 0:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, you didn't create any autoswap pair yet.")
            else:
                if token and token.upper() not in self.bot.other_data['autoswap_tokens']:
                    await ctx.edit_original_message(content=f"{ctx.author.mention}, **{token}** is not available!")
                    return
                else:
                    get_list = await self.history_withraw(
                        str(ctx.author.id), SERVER_BOT, token.upper() if token is not None else None
                    )
                    if len(get_list) == 0:
                        await ctx.edit_original_message(content=f"{ctx.author.mention}, there is no history of withdraw.")
                    else:
                        list_msg = []
                        for c, each in enumerate(get_list, start=1):
                            list_msg.append("{}) tx: {}..{} - {} {} <t:{}:f>.".format(
                                c, each['txid'][0:6], each['txid'][-7:], each['amount'], each['to_coin'], each['withdraw_ts']
                            ))
                        await ctx.edit_original_message(content="{}, list autoswap withdraw(s):\n{}".format(
                            ctx.author.mention, "\n".join(list_msg)
                        ))
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await ctx.edit_original_message(content=f"{ctx.author.mention}, internal error!")

    @autoswap.sub_command(
        name="list-pairs",
        usage="autoswap list-pairs",
        description="List available pairs.",
    )
    async def list_pairs(
        self,
        ctx,
    ):
        await ctx.response.defer(ephemeral=True)
        try:
            if self.bot.other_data['autoswap_pairs'] is None:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, that information is currently unavailable. Check again later!")
            else:
                list_pairs = list(sorted(self.bot.other_data['autoswap_pairs'].keys()))
                await ctx.edit_original_message(content="{}, list possible autoswap to create (total: **{}**):\n```{}```".format(ctx.author.mention, len(list_pairs), ", ".join(list_pairs)))
            return
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await ctx.edit_original_message(content=f"{ctx.author.mention}, internal error!")

    @autoswap.sub_command(
        name="detail",
        usage="autoswap detail",
        options=[
            Option("from_to", "From coin/token to coin/token", OptionType.string, required=True)
        ],
        description="Show a detail of your autoswap pair.",
    )
    async def autoswap_detail(
        self,
        ctx,
        from_to: str
    ):
        await ctx.response.defer(ephemeral=True)
        try:
            mylist = await self.user_mylist(str(ctx.author.id), SERVER_BOT)
            if len(mylist) == 0:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, you didn't create any autoswap pair yet.")
            else:
                from_to = from_to.upper()
                if from_to not in self.bot.other_data['autoswap_pairs'].keys():
                    await ctx.edit_original_message(content=f"{ctx.author.mention}, **{from_to}** is not available!")
                    return

                # Check if a that from to in his list
                split_from = from_to.split("-")
                mylist = await self.user_mylist(str(ctx.author.id), SERVER_BOT)
                detailed = None
                for c, each in enumerate(mylist, start=1):
                    if each['from_coin'] == split_from[0] and each['to_coin'] == split_from[1]:
                        detailed = each
                        break
                if detailed:
                    remaining_withdraw = 0
                    total_credit = 0
                    swapped_credit = 0
                    withdrew = 0
                    total_for_withdraw = 0
                    if detailed['total_for_withdraw'] - detailed['withdrew'] > 0:
                        round_to_coin = 6 # hard-code set to 6
                        remaining_withdraw = detailed['total_for_withdraw'] - detailed['withdrew']
                        remaining_withdraw = math.floor(remaining_withdraw *10**round_to_coin)/10**round_to_coin
                    if detailed['total_credit'] > 0:
                        round_to_coin = 6 # hard-code set to 6
                        total_credit = math.floor(detailed['total_credit'] *10**round_to_coin)/10**round_to_coin
                    if detailed['swapped_credit'] > 0:
                        round_to_coin = 6 # hard-code set to 6
                        swapped_credit = math.floor(detailed['swapped_credit'] *10**round_to_coin)/10**round_to_coin
                    if detailed['withdrew'] > 0:
                        round_to_coin = 6 # hard-code set to 6
                        withdrew = math.floor(detailed['withdrew'] *10**round_to_coin)/10**round_to_coin
                    if detailed['total_for_withdraw'] > 0:
                        round_to_coin = 6 # hard-code set to 6
                        total_for_withdraw = math.floor(detailed['total_for_withdraw'] *10**round_to_coin)/10**round_to_coin
                    await ctx.edit_original_message(content="{}, your **{}** autoswap:\n```From: {}\nDeposit address: {}\nDeposited: {} {}\nSwapped: {} {}\n\nTo: {}\nOutgoing address: {}\nTotal swapped: {} {}\nWithdrew: {} {}\nRemaining to withdraw: {} {}```".format(
                        ctx.author.mention, from_to, detailed['from_coin'], detailed['from_address'], total_credit, 
                        detailed['from_coin'], swapped_credit, detailed['from_coin'],
                        detailed['to_coin'], detailed['to_address'], total_for_withdraw, detailed['to_coin'], 
                        withdrew, detailed['to_coin'], remaining_withdraw, detailed['to_coin']
                    ))
                else:
                    await ctx.edit_original_message(content=f"{ctx.author.mention}, you didn't create autoswap **{from_to}** yet!")
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await ctx.edit_original_message(content=f"{ctx.author.mention}, internal error!")

    @autoswap.sub_command(
        name="mylist",
        usage="autoswap mylist",
        description="List of your setup autoswap.",
    )
    async def mylist(
        self,
        ctx,
    ):
        await ctx.response.defer(ephemeral=True)
        try:
            mylist = await self.user_mylist(str(ctx.author.id), SERVER_BOT)
            if len(mylist) == 0:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, you didn't create any autoswap pair yet.")
            else:
                list_swap = []
                for c, each in enumerate(mylist, start=1):
                    list_swap.append("{}) from {} to {} / {}..{}".format(c, each['from_coin'], each['to_coin'], each['to_address'][0:6], each['to_address'][-7:]))
                await ctx.edit_original_message(content="{} list autoswap:\n```{}```".format(ctx.author.mention, "\n".join(list_swap)))
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await ctx.edit_original_message(content=f"{ctx.author.mention}, internal error!")

    @autoswap.sub_command(
        name="add",
        usage="autoswap add <from> <to> <out address>",
        options=[
            Option("from_coin", "Depositng coin/token", OptionType.string, required=True),
            Option("to_coin", "To withdraw coin/token", OptionType.string, required=True),
            Option("out_address", "Address to auto withdraw", OptionType.string, required=True)
        ],
        description="Setup an autoswap incoming/outgoing coin/token.")
    async def autoswap_user_add(
        self,
        ctx,
        from_coin: str,
        to_coin: str,
        out_address: str
    ):
        await ctx.response.defer(ephemeral=True)
        try:
            from_coin = from_coin.upper()
            to_coin = to_coin.upper()
            if from_coin == to_coin:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, both coin/token can't be the same.")
                return
            elif from_coin not in self.bot.other_data['autoswap_tokens']:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, **{from_coin}** is not available for /autoswap!")
                return
            elif to_coin not in self.bot.other_data['autoswap_tokens']:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, **{to_coin}** is not available for /autoswap!")
                return
            elif "{}-{}".format(from_coin, to_coin) not in self.bot.other_data['autoswap_pairs'].keys():
                await ctx.edit_original_message(content=f"{ctx.author.mention}, **{from_coin} to {to_coin}** is not available with /autoswap!")
            else:
                type_coin = getattr(getattr(self.bot.coin_list, to_coin), "type")
                # check address for certain coins
                try:
                    if self.bot.config['api_helper']['address_validator_enable'] == 1:
                        if type_coin.upper() in ["TRTL-API", "TRTL-SERVICE", "BCN"]:
                            get_prefix_char = getattr(getattr(self.bot.coin_list, to_coin), "get_prefix_char")
                            get_prefix = getattr(getattr(self.bot.coin_list, to_coin), "get_prefix")
                            get_addrlen = getattr(getattr(self.bot.coin_list, to_coin), "get_addrlen")
                            get_intaddrlen = getattr(getattr(self.bot.coin_list, to_coin), "get_intaddrlen")
                            validate_address = cn_addressvalidation.cn_validate_address(
                                out_address, get_prefix, get_addrlen, get_prefix_char
                            )
                            if validate_address is False:
                                validate_address = cn_addressvalidation.cn_validate_integrated(
                                    out_address, get_prefix_char, get_prefix, get_intaddrlen
                                )
                                if validate_address is False:
                                    await ctx.edit_original_message(
                                        content=f"{ctx.author.mention}, given address `{out_address}` is invalid for coin/token **{to_coin.upper()}**."\
                                        " If you think this is an error, please join our Discord for support."
                                    )
                                    await log_to_channel(
                                        "autoswap",
                                        f"🔴 [INVALID ADDRESS] User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                        f"create an autoswap with an invalid address {out_address} for coin {to_coin.upper()}.",
                                        self.bot.config['discord']['autoswap_webhook']
                                    )
                                    return
                        else:
                            check_type = None
                            if type_coin == "ERC-20":
                                check_type = "eth"
                            elif type_coin == "TRC-20" or type_coin == "TRC-10":
                                check_type = "trx"
                            elif type_coin == "SOL" and type_coin == "SPL":
                                check_type = "sol"
                            elif type_coin == "XLM":
                                check_type = "xlm"
                            elif type_coin == "XRP":
                                check_type = "xrp"
                            elif type_coin == "ADA":
                                check_type = "ada"
                            elif type_coin == "VET":
                                check_type = "vet"
                            elif type_coin == "XTZ":
                                check_type = "xtz"
                            elif to_coin.lower() in self.bot.config['api_helper']['address_validator_list']:
                                check_type = to_coin.lower()
                            if check_type is not None:
                                check_address = await self.utils.validate_address_coin(
                                    self.bot.config['api_helper']['address_validator'], out_address, check_type, timeout=20
                                )
                                if check_address is False:
                                    await ctx.edit_original_message(
                                        content=f"{ctx.author.mention}, given address `{out_address}` is invalid for coin/token **{to_coin.upper()}**."\
                                        " If you think this is an error, please join our Discord for support."
                                    )
                                    await log_to_channel(
                                        "autoswap",
                                        f"🔴 [INVALID ADDRESS] User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                        f"create an autoswap with an invalid address {out_address} for coin {to_coin.upper()}.",
                                        self.bot.config['discord']['autoswap_webhook']
                                    )
                                    return
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                try:
                    check_exist = await self.check_withdraw_coin_address(type_coin, out_address)
                    if check_exist is not None:
                        await ctx.edit_original_message(
                            content=f"{ctx.author.mention}, given address `{out_address}` for depositing address and must not be used for this."\
                            " If you think this is an error, please join our Discord for support."
                        )
                        await log_to_channel(
                            "autoswap",
                            f"🔴 [ERROR] User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                            f"create an autoswap with a deposit address {out_address} for coin {to_coin.upper()}.",
                            self.bot.config['discord']['autoswap_webhook']
                        )
                        return
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                # check if user already have it
                mylist = await self.user_mylist(str(ctx.author.id), SERVER_BOT)
                if len(mylist) > 0:
                    selected_pair = None
                    for each in mylist:
                        if each['from_coin'] == from_coin.upper() and each['to_coin'] == to_coin.upper():
                            selected_pair = each
                            break
                    if selected_pair is not None:
                        from_to_msg = "```Outgoing {}:\n{}\n\nDeposit {}:\n{}```".format(
                            selected_pair['to_coin'],
                            selected_pair['to_address'],
                            selected_pair['from_coin'],
                            selected_pair['from_address'],
                        )
                        await ctx.edit_original_message(
                            content=f"{ctx.author.mention}, you already created an autoswap from {from_coin.upper()} to {to_coin.upper()}! {from_to_msg}Use `/autoswap detail` for more information."
                        )
                        return
                # create a deposit address
                create_wallet = await self.create_address(
                    str(ctx.author.id), SERVER_BOT, from_coin
                )
                if create_wallet is None:
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, internal error duing creating an autoswap deposit address."
                    )
                    return
                adding = await self.user_add_pair(
                    str(ctx.author.id), SERVER_BOT, from_coin, create_wallet['from_address'],
                    from_address_extra=create_wallet['from_address_extra'], from_privateKey=create_wallet['from_privateKey'], to_coin=to_coin,
                    to_address=out_address
                )
                if adding > 0:
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, set autoswap from: **{from_coin} to {to_coin}** address: "\
                        f"```OUTGOING {to_coin}:\n{out_address}```\nYour **{from_coin}** deposit is: ```DEPOSIT {from_coin}:\n{create_wallet['from_address']}```"
                    )
                    await log_to_channel(
                        "autoswap",
                        f"[NEW AUTOSWAP] User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                        f"created an autoswap from {create_wallet['from_address']} / {from_coin.upper()} to address {out_address} for coin {to_coin.upper()}.",
                        self.bot.config['discord']['autoswap_webhook']
                    )
                else:
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, internal error when adding new autoswap!"
                    )
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await ctx.edit_original_message(content=f"{ctx.author.mention}, internal error!")

    @autoswap.sub_command(
        name="delete",
        usage="autoswap delete <from-to>",
        options=[
            Option("from_to", "From coin/token to coin/token", OptionType.string, required=True)
        ],
        description="Setup an autoswap incoming/outgoing coin/token.")
    async def autoswap_user_delete(
        self,
        ctx,
        from_to: str
    ):
        await ctx.response.defer(ephemeral=True)
        try:
            from_to = from_to.upper()
            if from_to not in self.bot.other_data['autoswap_pairs'].keys():
                await ctx.edit_original_message(content=f"{ctx.author.mention}, **{from_to}** is not available!")
            else:
                mylist = await self.user_mylist(str(ctx.author.id), SERVER_BOT)
                if len(mylist) == 0:
                    await ctx.edit_original_message(content=f"{ctx.author.mention}, you didn't create any autoswap pair yet.")
                else:
                    # check if user already have it
                    list_pairs = ["{}-{}".format(i['from_coin'], i['to_coin']) for i in mylist]
                    if from_to not in list_pairs:
                        await ctx.edit_original_message(
                            content=f"{ctx.author.mention}, you don't have such autoswap **{from_to}**!"
                        )
                        return
                    else:
                        await ctx.edit_original_message(content=f"{ctx.author.mention}, TODO.")
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await ctx.edit_original_message(content=f"{ctx.author.mention}, internal error!")

    @autoswap_detail.autocomplete("from_to")
    @autoswap_user_delete.autocomplete("from_to")
    async def autoswap_user_delete_from_to_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        if self.bot.other_data['autoswap_pairs'] is None:
            return ["N/A"]
        return [name for name in self.bot.other_data['autoswap_pairs'].keys() if string in name.lower()][:10]

    @autoswap_user_add.autocomplete("from_coin")
    async def autoswap_token_from_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        if self.bot.other_data['autoswap_tokens_from'] is None:
            return ["N/A"]
        return [name for name in self.bot.other_data['autoswap_tokens_from'] if string in name.lower()][:10]
   
    @autoswap_user_add.autocomplete("to_coin")
    async def autoswap_token_to_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        if self.bot.other_data['autoswap_tokens_to'] is None:
            return ["N/A"]
        return [name for name in self.bot.other_data['autoswap_tokens_to'] if string in name.lower()][:10]

    @autoswap_history_deposit.autocomplete("token")
    @autoswap_history_withdraw.autocomplete("token")
    async def autoswap_tokens_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        if self.bot.other_data['autoswap_tokens'] is None:
            return ["N/A"]
        return [name for name in self.bot.other_data['autoswap_tokens'] if string in name.lower()][:10]

    @tasks.loop(seconds=60.0)
    async def update_balance_trtl_api(self):
        time_lap = 5  # seconds                    
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "autoswap_update_balance_trtl_api"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            list_trtl_api = await store.get_coin_settings("TRTL-API")
            if len(list_trtl_api) > 0:
                list_coins = [each['coin_name'].upper() for each in list_trtl_api]
                tasks = []
                for coin_name in list_coins:
                    if coin_name not in self.bot.other_data['autoswap_tokens']:
                        continue
                    if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 1 or getattr(
                            getattr(self.bot.coin_list, coin_name), "enable_deposit") == 0:
                        continue
                    tasks.append(self.update_balance_tasks_trtl_api(coin_name, False))

                completed = 0
                for task in asyncio.as_completed(tasks):
                    fetch_updates = await task
                    if fetch_updates is True:
                        completed += 1
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def update_balance_xmr(self):
        time_lap = 5  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "autoswap_update_balance_xmr"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        if self.bot.other_data['autoswap_tokens'] is None:
            return
        try:
            list_xmr_api = await store.get_coin_settings("XMR")
            if len(list_xmr_api) > 0:
                list_coins = [each['coin_name'].upper() for each in list_xmr_api]
                tasks = []
                for coin_name in list_coins:
                    if coin_name not in self.bot.other_data['autoswap_tokens']:
                        continue
                    if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 1 or getattr(
                            getattr(self.bot.coin_list, coin_name), "enable_deposit") == 0:
                        continue
                    tasks.append(self.update_balance_tasks_xmr(coin_name, False))
                completed = 0
                for task in asyncio.as_completed(tasks):
                    fetch_updates = await task
                    if fetch_updates is True:
                        completed += 1
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def update_balance_btc(self):
        time_lap = 5  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "autoswap_update_balance_btc"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        if self.bot.other_data['autoswap_tokens'] is None:
            return
        try:
            list_btc_api = await store.get_coin_settings("BTC")
            if len(list_btc_api) > 0:
                list_coins = [each['coin_name'].upper() for each in list_btc_api]
                tasks = []
                for coin_name in list_coins:
                    if coin_name not in self.bot.other_data['autoswap_tokens']:
                        continue
                    if not hasattr(self.bot.coin_list, coin_name):
                        continue
                    if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 1 or getattr(
                            getattr(self.bot.coin_list, coin_name), "enable_deposit") == 0:
                        continue
                    tasks.append(self.update_balance_tasks_btc(coin_name, False))
                completed = 0
                for task in asyncio.as_completed(tasks):
                    fetch_updates = await task
                    if fetch_updates is True:
                        completed += 1
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=15.0)
    async def notify_autoswap_deposits(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "autoswap_notify_deposit"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                await conn.ping(reconnect=True)
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `autoswap_deposits` 
                    WHERE `notified_confirmation`=%s AND `failed_notification`=%s AND `user_server`=%s
                    """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            if eachTx['user_id']:
                                # Discord
                                if not eachTx['user_id'].isdigit():
                                    continue
                                member = self.bot.get_user(int(eachTx['user_id']))
                                get_confirm_depth = getattr(getattr(self.bot.coin_list, eachTx['coin_name']), "deposit_confirm_depth")
                                if get_confirm_depth <= eachTx['confirmations'] and member is not None:
                                    msg = "You got a new autoswap deposit for {}: ```Tx: {}\nAmount: {}```".format(
                                            eachTx['coin_name'], eachTx['txid'],
                                            num_format_coin(eachTx['amount'])
                                        )
                                    try:
                                        await log_to_channel(
                                            "autoswap",
                                            "[DEPOSIT] {} {} from <@{}> / {}. ref: {}".format(
                                                num_format_coin(eachTx['amount']),
                                                eachTx['coin_name'], eachTx['user_id'], eachTx['user_id'], eachTx['txid']
                                            ),
                                            self.bot.config['discord']['autoswap_webhook']
                                        )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    try:
                                        await member.send(msg)
                                        sql = """
                                        UPDATE `autoswap_deposits` 
                                        SET `notified_confirmation`=%s, `time_notified`=%s, `can_credit`=%s 
                                        WHERE `txid`=%s AND `user_id`=%s LIMIT 1
                                        """
                                        await cur.execute(sql, ("YES", int(time.time()), "YES", eachTx['txid'], eachTx['user_id']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """
                                        UPDATE `autoswap_deposits` 
                                        SET `notified_confirmation`=%s, `failed_notification`=%s, `can_credit`=%s 
                                        WHERE `txid`=%s AND `user_id`=%s LIMIT 1
                                        """
                                        await cur.execute(sql, ("NO", "YES", "YES", eachTx['txid'], eachTx['user_id']))
                                        await conn.commit()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=30.0)
    async def autoswap_checking_min(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "autoswap_checking_min"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                await conn.ping(reconnect=True)
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `autoswap_list_users` 
                    WHERE `remaining_credit`> 0
                    """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each in result:
                            try:
                                cexswap_enable = getattr(getattr(self.bot.coin_list, each['from_coin']), "cexswap_enable")
                                cexswap_min = getattr(getattr(self.bot.coin_list, each['from_coin']), "cexswap_min")
                                if cexswap_enable != 1:
                                    continue
                                if each['remaining_credit'] and float(cexswap_min) >= each['remaining_credit']:
                                    continue
                                elif each['remaining_credit'] and each['remaining_credit'] > 0:
                                    get_lp_info = await self.cex_get_lp_info(
                                        "{}-{}".format(each['from_coin'], each['to_coin']), timeout=10
                                    )
                                    if get_lp_info and get_lp_info.get('total_liquidity'):
                                        to_trade = each['remaining_credit']
                                        min_trade = get_lp_info['minimum'][each['from_coin']]
                                        max_trade = get_lp_info['maxium'][each['from_coin']]
                                        if each['remaining_credit'] < min_trade:
                                            continue
                                        else:
                                            # can swap
                                            if each['remaining_credit'] > max_trade:
                                                to_trade = max_trade
                                            # Credit to AUTOSWAP
                                            creditor = "SYSTEM"
                                            credit_to = self.bot.config['autoswap']['autoswap']
                                            coin_name = each['from_coin']
                                            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                                            crediting = await store.sql_user_balance_mv_single(
                                                creditor, credit_to, "CREDIT+", "CREDIT+", to_trade,
                                                coin_name, "AUTOSWAP", coin_decimal, SERVER_BOT,
                                                contract, 0.0, None
                                            )
                                            if crediting is True:
                                                print("Crediting {} for {} {} to swap for {}.".format(credit_to, to_trade, coin_name, each['to_coin']))
                                                swapping = await self.cex_sell_swapper(
                                                    str(to_trade), each['from_coin'], each['to_coin'], 15
                                                )
                                                if swapping and swapping.get('success') and swapping['success'] is True:
                                                    sql = """
                                                    INSERT INTO `autoswap_swap_logs` 
                                                    (`ref_log`, `for_user_id`, `user_server`, `from_coin`, `sell_amount`, `to_coin`, `got_amount`, `sold_dump`, `date`)
                                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                                    """
                                                    await cur.execute(sql, (
                                                        swapping['ref'], each['user_id'], each['user_server'],
                                                        each['from_coin'], to_trade, each['to_coin'], float(swapping['get'].replace(",", "")),
                                                        json.dumps(swapping), swapping['time']
                                                    ))
                                                    await conn.commit()
                                                    if cur.lastrowid > 0:
                                                        await log_to_channel(
                                                            "autoswap",
                                                            f"[AUTOSWAPPER] for {each['user_id']} "\
                                                            f"selling {str(to_trade)} {each['from_coin']} for {swapping['get']} {each['to_coin']} ref: {swapping['ref']}.",
                                                            self.bot.config['discord']['autoswap_webhook']
                                                        )
                                                    else:
                                                        await log_to_channel(
                                                            "autoswap",
                                                            f"[AUTOSWAPPER] failed to insert to DB {each['user_id']} "\
                                                            f"selling {str(to_trade)} {each['from_coin']} for {each['to_coin']} ref: {swapping['ref']}.",
                                                            self.bot.config['discord']['autoswap_webhook']
                                                        )
                                                else:
                                                    print("Failed to swap {} {} to swap for {}.".format(to_trade, coin_name, each['to_coin']))
                                                    print(swapping)
                                    else:
                                        await log_to_channel(
                                            "autoswap",
                                            f"[AUTOSWAPPER] error getting LP information for pair {each['from_coin']}-{each['to_coin']} with "\
                                            f"error message {get_lp_info['error']}.",
                                            self.bot.config['discord']['autoswap_webhook']
                                        )
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=30.0)
    async def autoswap_checking_withdraw(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "autoswap_checking_withdraw"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                await conn.ping(reconnect=True)
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `autoswap_list_users` 
                    WHERE `remaining_withdraw`> 0
                    """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each in result:
                            coin_name = each['to_coin']
                            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                            enable_withdraw = getattr(getattr(self.bot.coin_list, coin_name), "enable_withdraw")
                            is_maintenance = getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance")
                            real_min_tx = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tx")
                            real_max_tx = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tx")
                            NetFee = getattr(getattr(self.bot.coin_list, coin_name), "real_withdraw_fee")
                            main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                            tx_fee = getattr(getattr(self.bot.coin_list, coin_name), "tx_fee")
                            is_fee_per_byte = getattr(getattr(self.bot.coin_list, coin_name), "is_fee_per_byte")
                            mixin = getattr(getattr(self.bot.coin_list, coin_name), "mixin")
                            wallet_address = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
                            header = getattr(getattr(self.bot.coin_list, coin_name), "header")
                            round_withdraw_places = getattr(getattr(self.bot.coin_list, coin_name), "round_withdraw_places")
                            if tx_fee is None:
                                tx_fee = NetFee
                            if enable_withdraw == 0 or is_maintenance == 1:
                                continue
                            if each['remaining_withdraw'] and float(real_min_tx) >= each['remaining_withdraw']:
                                continue
                            elif each['remaining_withdraw'] and each['remaining_withdraw'] > 0:
                                to_withdraw_before_fee = each['remaining_withdraw']
                                if to_withdraw_before_fee > real_max_tx:
                                    to_withdraw_before_fee = real_max_tx
                                to_withdraw = to_withdraw_before_fee - NetFee
                                # truncate
                                if round_withdraw_places is not None:
                                    to_withdraw = math.floor(to_withdraw *10**round_withdraw_places)/10**round_withdraw_places

                                tx_hash = None
                                tx_key = None
                                withdraw_ts = int(time.time())
                                if type_coin == "NANO":
                                    sending = await self.nano_sendtoaddress(
                                        main_address, each['to_address'], int(Decimal(to_withdraw) * 10 ** coin_decimal), coin_name
                                    )
                                    tx_hash = sending['block']
                                elif type_coin == "BTC":
                                    sending = await self.send_external_doge(
                                        self.bot.config['autoswap']['autoswap'], to_withdraw, each['to_address'], coin_name
                                    )
                                    tx_hash = sending
                                if type_coin == "XMR" or type_coin == "TRTL-API" or type_coin == "TRTL-SERVICE" or type_coin == "BCN":
                                    sending = await self.send_external_xmr(
                                        type_coin, main_address, to_withdraw, each['to_address'], coin_name, coin_decimal,
                                        tx_fee, is_fee_per_byte, mixin, wallet_address, header
                                    )
                                    tx_hash = sending['hash']
                                    tx_key = sending['key']
                                if tx_hash is None:
                                    sql = """
                                    INSERT INTO `autoswap_withdraw_failed_logs` 
                                    (`user_id`, `user_server`, `coin_name`, `address`, `amount`, `time`)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                    """
                                    await cur.execute(sql, (
                                        each['user_id'], each['user_server'],
                                        coin_name, each['to_address'], to_withdraw, int(time.time())
                                    ))
                                    await conn.commit()
                                    await log_to_channel(
                                        "autoswap",
                                        f"🔴 [FAILED WITHDRAW] failed to auto withdraw for user {each['user_id']} / {each['user_server']} "\
                                        f"with {str(to_withdraw)} {coin_name}.",
                                        self.bot.config['discord']['autoswap_webhook']
                                    )
                                else:
                                    sql = """
                                    INSERT INTO `autoswap_withdraw` 
                                    (`user_id`, `user_server`, `from_coin`, `to_coin`, `to_address`, `withdraw_ts`, `txid`, `tx_key`, `amount`, `fee_and_tax`)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    """
                                    await cur.execute(sql, (
                                        each['user_id'], each['user_server'], each['from_coin'], each['to_coin'],
                                        each['to_address'], withdraw_ts, tx_hash, tx_key, to_withdraw, NetFee
                                    ))
                                    await conn.commit()
                                    await log_to_channel(
                                        "autoswap",
                                        f"[WITHDRAW] auto withdraw for user {each['user_id']} / {each['user_server']} "\
                                        f"with {str(to_withdraw)} {coin_name} to address {each['to_address']} and hash {tx_hash}.",
                                        self.bot.config['discord']['autoswap_webhook']
                                    )
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=15.0)
    async def notify_autoswap_withdraw(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_autoswap_withdraw"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                await conn.ping(reconnect=True)
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `autoswap_withdraw` 
                    WHERE `notified_confirmation`=%s AND `failed_notification`=%s AND `user_server`=%s
                    """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            try:
                                if eachTx['user_id']:
                                    # Discord
                                    if not eachTx['user_id'].isdigit():
                                        continue
                                    member = self.bot.get_user(int(eachTx['user_id']))
                                    if member is not None:
                                        msg = "Autoswap withdrew <t:{}:f> for {} from swapping {}: ```Tx: {}\nAmount: {} {}\nTo address: {}```".format(
                                                eachTx['withdraw_ts'], eachTx['to_coin'], eachTx['from_coin'], eachTx['txid'],
                                                num_format_coin(eachTx['amount']), eachTx['to_coin'], eachTx['to_address']
                                            )
                                        try:
                                            await member.send(msg)
                                            sql = """
                                            UPDATE `autoswap_withdraw` 
                                            SET `notified_confirmation`=%s, `time_notified`=%s
                                            WHERE `txid`=%s AND `user_id`=%s LIMIT 1
                                            """
                                            await cur.execute(sql, ("YES", int(time.time()), eachTx['txid'], eachTx['user_id']))
                                            await conn.commit()
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                            sql = """
                                            UPDATE `autoswap_withdraw` 
                                            SET `notified_confirmation`=%s, `failed_notification`=%s
                                            WHERE `txid`=%s AND `user_id`=%s LIMIT 1
                                            """
                                            await cur.execute(sql, ("NO", "YES", eachTx['txid'], eachTx['user_id']))
                                            await conn.commit()
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.update_balance_btc.is_running():
            self.update_balance_btc.start()
        if not self.update_balance_xmr.is_running():
            self.update_balance_xmr.start()
        if not self.update_balance_trtl_api.is_running():
            self.update_balance_trtl_api.start()
        if not self.notify_autoswap_deposits.is_running():
            self.notify_autoswap_deposits.start()
        if not self.autoswap_checking_min.is_running():
            self.autoswap_checking_min.start()
        if not self.autoswap_checking_withdraw.is_running():
            self.autoswap_checking_withdraw.start()
        if not self.notify_autoswap_withdraw.is_running():
            self.notify_autoswap_withdraw.start()
        if self.bot.other_data['autoswap_pairs'] is None:
            get_pairs = await self.pair_list()
            token_list = []
            token_list_from = []
            token_list_to = []
            if len(get_pairs) > 0:
                self.bot.other_data['autoswap_pairs'] = {}
                for i in get_pairs:
                    self.bot.other_data['autoswap_pairs']["{}-{}".format(i['from_coin'], i['to_coin'])] = i
                print("autoswap reloaded {} pair(s)...".format(len(get_pairs)))            
                token_list.append(i['from_coin'])
                token_list.append(i['to_coin'])
                token_list_from.append(i['from_coin'])
                token_list_to.append(i['to_coin'])
            self.bot.other_data['autoswap_tokens'] = list(set(token_list))
            self.bot.other_data['autoswap_tokens_from'] = list(set(token_list_from))
            self.bot.other_data['autoswap_tokens_to'] = list(set(token_list_to))

    async def cog_load(self):
        if not self.update_balance_btc.is_running():
            self.update_balance_btc.start()
        if not self.update_balance_xmr.is_running():
            self.update_balance_xmr.start()
        if not self.update_balance_trtl_api.is_running():
            self.update_balance_trtl_api.start()
        if not self.notify_autoswap_deposits.is_running():
            self.notify_autoswap_deposits.start()
        if not self.autoswap_checking_min.is_running():
            self.autoswap_checking_min.start()
        if not self.autoswap_checking_withdraw.is_running():
            self.autoswap_checking_withdraw.start()
        if not self.notify_autoswap_withdraw.is_running():
            self.notify_autoswap_withdraw.start()
        get_pairs = await self.pair_list()
        if len(get_pairs) > 0:
            self.bot.other_data['autoswap_pairs'] = {}
            token_list = []
            token_list_from = []
            token_list_to = []
            for i in get_pairs:
                self.bot.other_data['autoswap_pairs']["{}-{}".format(i['from_coin'], i['to_coin'])] = i
                token_list.append(i['from_coin'])
                token_list.append(i['to_coin'])
                token_list_from.append(i['from_coin'])
                token_list_to.append(i['to_coin'])
            self.bot.other_data['autoswap_tokens'] = list(set(token_list))
            self.bot.other_data['autoswap_tokens_from'] = list(set(token_list_from))
            self.bot.other_data['autoswap_tokens_to'] = list(set(token_list_to))
            print("autoswap reloaded {} pair(s)...".format(len(get_pairs)))

    def cog_unload(self):
        self.bot.other_data['autoswap_pairs'] = None
        self.bot.other_data['autoswap_tokens'] = None
        self.bot.other_data['autoswap_tokens_from'] = None
        self.bot.other_data['autoswap_tokens_to'] = None
        self.update_balance_btc.cancel()
        self.update_balance_xmr.cancel()
        self.update_balance_trtl_api.cancel()
        self.notify_autoswap_deposits.cancel()
        self.autoswap_checking_min.cancel()
        self.autoswap_checking_withdraw.cancel()
        self.notify_autoswap_withdraw.cancel()

def setup(bot):
    bot.add_cog(AutoSwap(bot))
