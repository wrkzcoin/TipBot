from typing import Dict
from uuid import uuid4

import aiohttp
import asyncio
import json

from config import config

import sys
sys.path.append("..")


class RPCException(Exception):
    def __init__(self, message):
        super(RPCException, self).__init__(message)


async def call_aiohttp_wallet(method_name: str, coin: str, time_out: int = None, payload: Dict = None) -> Dict:
    coin_family = getattr(getattr(config,"daemon"+coin),"coin_family","TRTL")
    full_payload = {
        'params': payload or {},
        'jsonrpc': '2.0',
        'id': str(uuid4()),
        'method': f'{method_name}'
    }
    url = get_wallet_rpc_url(coin.upper())
    timeout = time_out or 8
    if method_name == "save" or method_name == "store":
        timeout = 300
    try:
        if coin_family == "XMR":
            async with aiohttp.ClientSession(headers={'Content-Type': 'application/json'}) as session:
                async with session.post(url, ssl=False, json=full_payload, timeout=timeout) as response:
                    # sometimes => "message": "Not enough unlocked money" for checking fee
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        await session.close()
                        decoded_data = json.loads(res_data)
                        if 'result' in decoded_data:
                            return decoded_data['result']
                        else:
                            return None
        elif coin_family == "TRTL" or coin_family == "CCX":
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=full_payload, timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        await session.close()
                        decoded_data = json.loads(res_data)
                        return decoded_data['result']
    except asyncio.TimeoutError:
        print('TIMEOUT: method_name: {} - coin_family: {} - time_out {}'.format(method_name, coin_family, time_out))
        print('TIMEOUT: payload: ')
        print(full_payload)


async def call_doge_ltc(method_name: str, coin: str, payload: str = None) -> Dict:
    headers = {
        'content-type': 'text/plain;',
    }
    if payload is None:
        data = '{"jsonrpc": "1.0", "id":"'+str(uuid4())+'", "method": "'+method_name+'", "params": [] }'
    else:
        data = '{"jsonrpc": "1.0", "id":"'+str(uuid4())+'", "method": "'+method_name+'", "params": ['+payload+'] }'
    url = None
    if coin.upper() == "DOGE":
        url = f'http://{config.daemonDOGE.username}:{config.daemonDOGE.password}@{config.daemonDOGE.host}:{config.daemonDOGE.rpcport}/'
    elif coin.upper() == "LTC":
        url = f'http://{config.daemonLTC.username}:{config.daemonLTC.password}@{config.daemonLTC.host}:{config.daemonLTC.rpcport}/'
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data, timeout=8) as response:
            if response.status == 200:
                res_data = await response.read()
                res_data = res_data.decode('utf-8')
                await session.close()
                decoded_data = json.loads(res_data)
                return decoded_data['result']


def get_wallet_rpc_url(coin: str = None):
    coin_family = getattr(getattr(config,"daemon"+coin),"coin_family","TRTL")
    if coin_family == "TRTL" or coin_family == "CCX" :
        return "http://"+getattr(config,"daemon"+coin,config.daemonWRKZ).wallethost + ":" + \
            str(getattr(config,"daemon"+coin,config.daemonWRKZ).walletport) \
            + '/json_rpc'
    elif coin_family == "XMR":
        return "http://"+getattr(config,"daemon"+coin,config.daemonWRKZ).wallethost + ":" + \
            str(getattr(config,"daemon"+coin,config.daemonWRKZ).walletport) \
            + '/json_rpc'
