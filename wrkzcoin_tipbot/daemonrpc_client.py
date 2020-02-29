from typing import Dict
from uuid import uuid4

import rpc_client, walletapi
import json
import aiohttp
import asyncio

import sys, traceback
sys.path.append("..")
from config import config

# Coin using wallet-api
WALLET_API_COIN = config.Enable_Coin_WalletApi.split(",")

class RPCException(Exception):
    def __init__(self, message):
        super(RPCException, self).__init__(message)


async def getWalletStatus(coin: str):
    global WALLET_API_COIN
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    time_out = 16
    if COIN_NAME in WALLET_API_COIN:
        method = "/status"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(walletapi.get_wallet_api_url(COIN_NAME) + method, headers=walletapi.get_wallet_api_header(COIN_NAME), timeout=time_out) as response:
                    json_resp = await response.json()
                    if response.status == 200 or response.status == 201:
                        result = json_resp
                        return {"blockCount": result['walletBlockCount'], "knownBlockCount": result['networkBlockCount']}
                    elif json_resp and 'errorMessage' in json_resp:
                        raise RPCException(json_resp['errorMessage'])
        except asyncio.TimeoutError:
            print('TIMEOUT: {} COIN_NAME {} - timeout {}'.format(method, COIN_NAME, time_out))
            return None
        except aiohttp.ContentTypeError:
            print('aiohttp.ContentTypeError: {} COIN_NAME {}'.format(method, COIN_NAME))
            print(await response.text())
            return None
        except aiohttp.ClientConnectorError:
            print('aiohttp.ClientConnectorError: {} COIN_NAME {}'.format(method, COIN_NAME))
            return None
        except Exception:
            traceback.print_exc(file=sys.stdout)
            return None
    if coin_family == "TRTL" or coin_family == "CCX":
        return await rpc_client.call_aiohttp_wallet('getStatus', COIN_NAME)
    elif coin_family == "XMR":
        # TODO: check wallet status
        return await rpc_client.call_aiohttp_wallet('get_height', COIN_NAME, time_out=time_out)


async def getDaemonRPCStatus(coin: str):
    COIN_NAME = coin.upper()
    if COIN_NAME in ["DOGE", "LTC", "BTC", "DASH", "BCH"]:
        result = await rpc_client.call_doge('getinfo', COIN_NAME)
    return result


async def gettopblock(coin: str, time_out: int = None):
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    result = None
    timeout = time_out or 32
    if coin_family == "TRTL" or coin_family == "CCX" or coin_family == "XMR":
        result = await call_daemon('getblockcount', COIN_NAME, time_out = timeout)
        if result:
            full_payload = {
                'jsonrpc': '2.0',
                'method': 'getblockheaderbyheight',
                'params': {'height': result['count'] - 1}
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(get_daemon_rpc_url(COIN_NAME)+'/json_rpc', json=full_payload, timeout=timeout) as response:
                        if response.status == 200:
                            res_data = await response.json()
                            await session.close()
                            return res_data['result']
            except asyncio.TimeoutError:
                print('TIMEOUT: {} COIN_NAME {} - timeout {}'.format('getblockheaderbyheight', COIN_NAME, time_out))
                return None
            except Exception:
                traceback.print_exc(file=sys.stdout)
                return None
        else:
            return None


async def call_daemon(method_name: str, coin: str, time_out: int = None, payload: Dict = None) -> Dict:
    full_payload = {
        'params': payload or {},
        'jsonrpc': '2.0',
        'id': str(uuid4()),
        'method': f'{method_name}'
    }
    timeout = time_out or 16
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(get_daemon_rpc_url(coin.upper())+'/json_rpc', json=full_payload, timeout=timeout) as response:
                if response.status == 200:
                    res_data = await response.json()
                    await session.close()
                    return res_data['result']
    except asyncio.TimeoutError:
        print('TIMEOUT: {} COIN_NAME {} - timeout {}'.format(method_name, coin.upper(), time_out))
        return None
    except Exception:
        traceback.print_exc(file=sys.stdout)
        return None


def get_daemon_rpc_url(coin: str = None):
    return "http://"+getattr(config,"daemon"+coin,config.daemonWRKZ).host+":"+str(getattr(config,"daemon"+coin,config.daemonWRKZ).port)
