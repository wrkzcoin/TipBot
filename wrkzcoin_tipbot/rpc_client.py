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


async def call_aiohttp_wallet(method_name: str, coin: str, payload: Dict = None) -> Dict:
    full_payload = {
        'params': payload or {},
        'jsonrpc': '2.0',
        'id': str(uuid4()),
        'method': f'{method_name}'
    }
    url = get_wallet_rpc_url(coin.upper())
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=full_payload, timeout=8) as response:
            if response.status == 200:
                res_data = await response.read()
                res_data = res_data.decode('utf-8')
                await session.close()
                decoded_data = json.loads(res_data)
                return decoded_data['result']


async def call_methodDOGE(method_name: str, payload: str = None) -> Dict:
    headers = {
        'content-type': 'text/plain;',
    }
    if payload is None:
        data = '{"jsonrpc": "1.0", "id":"'+str(uuid4())+'", "method": "'+method_name+'", "params": [] }'
    else:
        data = '{"jsonrpc": "1.0", "id":"'+str(uuid4())+'", "method": "'+method_name+'", "params": ['+payload+'] }'
    url = f'http://{config.daemonDOGE.username}:{config.daemonDOGE.password}@{config.daemonDOGE.host}:{config.daemonDOGE.rpcport}/'
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data, timeout=8) as response:
            if response.status == 200:
                res_data = await response.read()
                res_data = res_data.decode('utf-8')
                await session.close()
                decoded_data = json.loads(res_data)
                return decoded_data['result']


async def call_methodLTC(method_name: str, payload: str = None) -> Dict:
    headers = {
        'content-type': 'text/plain;',
    }
    if payload is None:
        data = '{"jsonrpc": "1.0", "id":"'+str(uuid4())+'", "method": "'+method_name+'", "params": [] }'
    else:
        data = '{"jsonrpc": "1.0", "id":"'+str(uuid4())+'", "method": "'+method_name+'", "params": ['+payload+'] }'
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
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        url = "http://"+config.daemonTRTL.wallethost+":"+str(config.daemonTRTL.walletport)
    elif coin.upper() == "DEGO":
        url = "http://"+config.daemonDEGO.wallethost+":"+str(config.daemonDEGO.walletport)
    elif coin.upper() == "LCX":
        url = "http://"+config.daemonLCX.wallethost+":"+str(config.daemonLCX.walletport)
    elif coin.upper() == "CX":
        url = "http://"+config.daemonCX.wallethost+":"+str(config.daemonCX.walletport)
    elif coin.upper() == "WRKZ":
        url = "http://"+config.daemonWRKZ.wallethost+":"+str(config.daemonWRKZ.walletport)
    elif coin.upper() == "OSL":
        url = "http://"+config.daemonOSL.wallethost+":"+str(config.daemonOSL.walletport)
    elif coin.upper() == "BTCM":
        url = "http://"+config.daemonBTCM.wallethost+":"+str(config.daemonBTCM.walletport)
    elif coin.upper() == "TLRM":
        url = "http://"+config.daemonTLRM.wallethost+":"+str(config.daemonTLRM.walletport)
    elif coin.upper() == "MTIP":
        url = "http://"+config.daemonMTIP.wallethost+":"+str(config.daemonMTIP.walletport)
    elif coin.upper() == "XCY":
        url = "http://"+config.daemonXCY.wallethost+":"+str(config.daemonXCY.walletport)
    elif coin.upper() == "PLE":
        url = "http://"+config.daemonPLE.wallethost+":"+str(config.daemonPLE.walletport)
    elif coin.upper() == "ELPH":
        url = "http://"+config.daemonELPH.wallethost+":"+str(config.daemonELPH.walletport)
    elif coin.upper() == "ANX":
        url = "http://"+config.daemonANX.wallethost+":"+str(config.daemonANX.walletport)
    elif coin.upper() == "NBX":
        url = "http://"+config.daemonNBX.wallethost+":"+str(config.daemonNBX.walletport)
    elif coin.upper() == "ARMS":
        url = "http://"+config.daemonARMS.wallethost+":"+str(config.daemonARMS.walletport)
    elif coin.upper() == "IRD":
        url = "http://"+config.daemonIRD.wallethost+":"+str(config.daemonIRD.walletport)
    elif coin.upper() == "HITC":
        url = "http://"+config.daemonHITC.wallethost+":"+str(config.daemonHITC.walletport)
    elif coin.upper() == "NACA":
        url = "http://"+config.daemonNACA.wallethost+":"+str(config.daemonNACA.walletport)
    else:
        url = "http://"+config.daemonWRKZ.wallethost+":"+str(config.daemonWRKZ.walletport)
    return url + '/json_rpc'
