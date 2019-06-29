from typing import Dict
from uuid import uuid4

import rpc_client
import requests, json
import aiohttp
import asyncio

import sys
sys.path.append("..")
from config import config

class RPCException(Exception):
    def __init__(self, message):
        super(RPCException, self).__init__(message)

def getWalletStatus(coin: str):
    coin = coin.upper()
    info = {}
    return rpc_client.call_what('getStatus', coin.upper())


def getDaemonRPCStatus(coin: str):
    if (coin.upper() == "DOGE"):
        result = rpc_client.call_methodDOGE('getinfo')
    elif (coin.upper() == "LTC"):
        result = rpc_client.call_methodLTC('getinfo')
    return result


async def gettopblock(coin: str):
    result = await call_daemon('getblockcount', coin)
    full_payload = {
        'jsonrpc': '2.0',
        'method': 'getblockheaderbyheight',
        'params': {'height': result['count'] - 1}
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(get_daemon_rpc_url(coin.upper())+'/json_rpc', json=full_payload, timeout=8) as response:
            if response.status == 200:
                res_data = await response.json()
                await session.close()
                return res_data['result']


async def call_daemon(method_name: str, coin: str, payload: Dict = None) -> Dict:
    full_payload = {
        'params': payload or {},
        'jsonrpc': '2.0',
        'id': str(uuid4()),
        'method': f'{method_name}'
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(get_daemon_rpc_url(coin.upper())+'/json_rpc', json=full_payload, timeout=8) as response:
            if response.status == 200:
                res_data = await response.json()
                await session.close()
                return res_data['result']


def get_daemon_rpc_url(coin: str = None):
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        url = "http://"+config.daemonTRTL.host+":"+str(config.daemonTRTL.port)
    elif coin.upper() == "DEGO":
        url = "http://"+config.daemonDEGO.host+":"+str(config.daemonDEGO.port)
    elif coin.upper() == "LCX":
        url = "http://"+config.daemonLCX.host+":"+str(config.daemonLCX.port)
    elif coin.upper() == "CX":
        url = "http://"+config.daemonCX.host+":"+str(config.daemonCX.port)
    elif coin.upper() == "WRKZ":
        url = "http://"+config.daemonWRKZ.host+":"+str(config.daemonWRKZ.port)
    elif coin.upper() == "OSL":
        url = "http://"+config.daemonOSL.host+":"+str(config.daemonOSL.port)
    elif coin.upper() == "BTCM":
        url = "http://"+config.daemonBTCM.host+":"+str(config.daemonBTCM.port)
    elif coin.upper() == "TLRM":
        url = "http://"+config.daemonTLRM.host+":"+str(config.daemonTLRM.port)
    elif coin.upper() == "MTIP":
        url = "http://"+config.daemonMTIP.host+":"+str(config.daemonMTIP.port)
    elif coin.upper() == "XCY":
        url = "http://"+config.daemonXCY.host+":"+str(config.daemonXCY.port)
    elif coin.upper() == "PLE":
        url = "http://"+config.daemonPLE.host+":"+str(config.daemonPLE.port)
    elif coin.upper() == "ELPH":
        url = "http://"+config.daemonELPH.host+":"+str(config.daemonELPH.port)
    elif coin.upper() == "ANX":
        url = "http://"+config.daemonANX.host+":"+str(config.daemonANX.port)
    elif coin.upper() == "NBX":
        url = "http://"+config.daemonNBX.host+":"+str(config.daemonNBX.port)
    elif coin.upper() == "ARMS":
        url = "http://"+config.daemonARMS.host+":"+str(config.daemonARMS.port)
    elif coin.upper() == "IRD":
        url = "http://"+config.daemonIRD.host+":"+str(config.daemonIRD.port)
    elif coin.upper() == "HITC":
        url = "http://"+config.daemonHITC.host+":"+str(config.daemonHITC.port)
    elif coin.upper() == "NACA":
        url = "http://"+config.daemonNACA.host+":"+str(config.daemonNACA.port)
    else:
        url = "http://"+config.daemonWRKZ.host+":"+str(config.daemonWRKZ.port)
    return url