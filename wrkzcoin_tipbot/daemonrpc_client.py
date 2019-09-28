from typing import Dict
from uuid import uuid4

import rpc_client
import json
import aiohttp
import asyncio

import sys
sys.path.append("..")
from config import config

class RPCException(Exception):
    def __init__(self, message):
        super(RPCException, self).__init__(message)


async def getWalletStatus(coin: str):
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    timeout = 16
    if coin_family == "TRTL" or coin_family == "CCX":
        return await rpc_client.call_aiohttp_wallet('getStatus', COIN_NAME)
    elif coin_family == "XMR":
        # TODO: check wallet status
        return await rpc_client.call_aiohttp_wallet('get_height', COIN_NAME, time_out=timeout)


async def getDaemonRPCStatus(coin: str):
    COIN_NAME = coin.upper()
    if (COIN_NAME == "DOGE") or (COIN_NAME == "LTC"):
        result = await rpc_client.call_doge_ltc('getinfo', COIN_NAME)
    return result


async def gettopblock(coin: str, time_out: int = None):
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    result = None
    timeout = time_out or 32
    if coin_family == "TRTL" or coin_family == "CCX" or coin_family == "XMR":
        result = await call_daemon('getblockcount', COIN_NAME, time_out = timeout)
        full_payload = {
            'jsonrpc': '2.0',
            'method': 'getblockheaderbyheight',
            'params': {'height': result['count'] - 1}
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(get_daemon_rpc_url(COIN_NAME)+'/json_rpc', json=full_payload, timeout=timeout) as response:
                if response.status == 200:
                    res_data = await response.json()
                    await session.close()
                    return res_data['result']


async def call_daemon(method_name: str, coin: str, time_out: int = None, payload: Dict = None) -> Dict:
    full_payload = {
        'params': payload or {},
        'jsonrpc': '2.0',
        'id': str(uuid4()),
        'method': f'{method_name}'
    }
    timeout = time_out or 8
    async with aiohttp.ClientSession() as session:
        async with session.post(get_daemon_rpc_url(coin.upper())+'/json_rpc', json=full_payload, timeout=timeout) as response:
            if response.status == 200:
                res_data = await response.json()
                await session.close()
                return res_data['result']


def get_daemon_rpc_url(coin: str = None):
    return "http://"+getattr(config,"daemon"+coin,config.daemonWRKZ).host+":"+str(getattr(config,"daemon"+coin,config.daemonWRKZ).port)
