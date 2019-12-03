from typing import List, Dict
import json
from uuid import uuid4
import rpc_client
import aiohttp
import asyncio
import time

from config import config

import sys
sys.path.append("..")

class RPCException(Exception):
    def __init__(self, message):
        super(RPCException, self).__init__(message)



async def walletapi_registerOTHER(coin: str) -> str:
    time_out = 32
    COIN_NAME = coin.upper()
    reg_address = None
    method = "/addresses/create"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(get_wallet_api_url(COIN_NAME) + method, headers=get_wallet_api_header(COIN_NAME), timeout=time_out) as response:
                json_resp = await response.json()
                if response.status == 200 or response.status == 201:
                    reg_address = await response.json()
                    print('Wallet register: '+reg_address['address']+'=>privateSpendKey: '+reg_address['privateSpendKey'])
                elif 'errorMessage' in json_resp:
                    raise RPCException(json_resp['errorMessage'])
    except asyncio.TimeoutError:
        print('TIMEOUT: {} COIN_NAME {} - timeout {}'.format(method, COIN_NAME, time_out))
    return reg_address


async def walletapi_get_all_addresses(coin: str) -> Dict[str, Dict]:
    time_out = 32
    COIN_NAME = coin.upper()
    result = None
    method = "/addresses"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(get_wallet_api_url(COIN_NAME) + method, headers=get_wallet_api_header(COIN_NAME), timeout=time_out) as response:
                json_resp = await response.json()
                if response.status == 200 or response.status == 201:
                    result = await response.json()
                    return result['addresses']
                elif 'errorMessage' in json_resp:
                    raise RPCException(json_resp['errorMessage'])
    except asyncio.TimeoutError:
        print('TIMEOUT: {} COIN_NAME {} - timeout {}'.format(method, COIN_NAME, time_out))


async def walletapi_send_transaction(from_address: str, to_address: str, amount: int, coin: str) -> str:
    time_out = 300
    COIN_NAME = coin.upper()
    json_data = {
        "destinations": [{"address": to_address, "amount": amount}],
        "mixin": get_mixin(coin),
        "fee": get_tx_fee(coin),
        "sourceAddresses": [
            from_address
        ],
        "paymentID": "",
        "changeAddress": from_address
    }
    method = "/transactions/send/advanced"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(get_wallet_api_url(COIN_NAME) + method, headers=get_wallet_api_header(COIN_NAME), json=json_data, timeout=time_out) as response:
                json_resp = await response.json()
                if response.status == 200 or response.status == 201:
                    return json_resp['transactionHash']
                elif 'errorMessage' in json_resp:
                    raise RPCException(json_resp['errorMessage'])
    except asyncio.TimeoutError:
        print('TIMEOUT: {} COIN_NAME {} - timeout {}'.format(method, COIN_NAME, time_out))



async def walletapi_send_transaction_id(from_address: str, to_address: str, amount: int, paymentid: str, coin: str) -> str:
    time_out = 300
    COIN_NAME = coin.upper()
    json_data = {
        'sourceAddresses': [from_address],
        'destinations': [{
            "amount": amount,
            "address": to_address
        }],
        'fee': get_tx_fee(coin),
        'mixin': get_mixin(coin),
        'paymentID': paymentid
    }
    method = "/transactions/send/advanced"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(get_wallet_api_url(COIN_NAME) + method, headers=get_wallet_api_header(COIN_NAME), json=json_data, timeout=time_out) as response:
                json_resp = await response.json()
                if response.status == 200 or response.status == 201:
                    return json_resp['transactionHash']
                elif 'errorMessage' in json_resp:
                    raise RPCException(json_resp['errorMessage'])
    except asyncio.TimeoutError:
        print('TIMEOUT: {} COIN_NAME {} - timeout {}'.format(method, COIN_NAME, time_out))


async def walletapi_send_transactionall(from_address: str, to_address, coin: str) -> str:
    time_out = 300
    COIN_NAME = coin.upper()
    result = None
    json_data = {
        "destinations": to_address,
        "mixin": get_mixin(coin),
        "fee": get_tx_fee(coin),
        "sourceAddresses": [
            from_address
        ],
        "paymentID": "",
        "changeAddress": from_address
    }
    method = "/transactions/send/advanced"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(get_wallet_api_url(COIN_NAME) + method, headers=get_wallet_api_header(COIN_NAME), json=json_data, timeout=time_out) as response:
                json_resp = await response.json()
                if response.status == 200 or response.status == 201:
                    return json_resp['transactionHash']
                elif 'errorMessage' in json_resp:
                    raise RPCException(json_resp['errorMessage'])
    except asyncio.TimeoutError:
        print('TIMEOUT: {} COIN_NAME {} - timeout {}'.format(method, COIN_NAME, time_out))


async def walletapi_get_all_balances_all(coin: str) -> Dict[str, Dict]:
    time_out = 32
    COIN_NAME = coin.upper()
    wallets = None
    method = "/balances"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(get_wallet_api_url(COIN_NAME) + method, headers=get_wallet_api_header(COIN_NAME), timeout=time_out) as response:
                json_resp = await response.json()
                if response.status == 200 or response.status == 201:
                    wallets = await response.json()
                    return wallets
                elif 'errorMessage' in json_resp:
                    raise RPCException(json_resp['errorMessage'])
    except asyncio.TimeoutError:
        print('TIMEOUT: {} COIN_NAME {} - timeout {}'.format(method, COIN_NAME, time_out))


async def walletapi_get_some_balances(wallet_addresses: List[str], coin: str) -> Dict[str, Dict]:
    time_out = 32
    COIN_NAME = coin.upper()
    wallets = []  # new array
    for address in wallet_addresses:
        method = "/balance/" + address
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(get_wallet_api_url(COIN_NAME) + method, headers=get_wallet_api_header(COIN_NAME), timeout=time_out) as response:
                    json_resp = await response.json()
                    if response.status == 200 or response.status == 201:
                        wallet = await response.json()
                        wallet['address'] = address
                        wallets.append(wallet)
                    elif 'errorMessage' in json_resp:
                        raise RPCException(json_resp['errorMessage'])
        except asyncio.TimeoutError:
            print('TIMEOUT: {} COIN_NAME {} - timeout {}'.format(method, COIN_NAME, time_out))
    return wallets


async def walletapi_get_sum_balances(coin: str) -> Dict[str, Dict]:
    time_out = 32
    COIN_NAME = coin.upper()
    wallet = None
    method = "/balance"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(get_wallet_api_url(COIN_NAME) + method, headers=get_wallet_api_header(COIN_NAME), timeout=time_out) as response:
                json_resp = await response.json()
                if response.status == 200 or response.status == 201:
                    wallet = await response.json()
                    return wallet
                elif 'errorMessage' in json_resp:
                    raise RPCException(json_resp['errorMessage'])
    except asyncio.TimeoutError:
        print('TIMEOUT: {} COIN_NAME {} - timeout {}'.format(method, COIN_NAME, time_out))
    return None


async def walletapi_get_balance_address(address: str, coin: str) -> Dict[str, Dict]:
    time_out = 32
    COIN_NAME = coin.upper()
    wallet = None
    method = "/balance/" + address
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(get_wallet_api_url(COIN_NAME) + method, headers=get_wallet_api_header(COIN_NAME), timeout=time_out) as response:
                json_resp = await response.json()
                if response.status == 200 or response.status == 201:
                    wallet = await response.json()
                    return wallet
                elif 'errorMessage' in json_resp:
                    raise RPCException(json_resp['errorMessage'])
    except asyncio.TimeoutError:
        print('TIMEOUT: {} COIN_NAME {} - timeout {}'.format(method, COIN_NAME, time_out))
    return None


async def walletapi_wallet_optimize_single(subaddress: str, coin: str) -> int:
    time_out = 32
    COIN_NAME = coin.upper()

    json_data = {
        "mixin": get_mixin(COIN_NAME),
        "sourceAddresses": [
            subaddress
        ],
        "destination": subaddress
    }
    print('Optimizing wallet: '+subaddress)
    i = 0
    method = "/transactions/send/fusion/advanced"
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(get_wallet_api_url(COIN_NAME) + method, headers=get_wallet_api_header(COIN_NAME), json=json_data, timeout=time_out) as response:
                    if response.status == 200 or response.status == 201:
                        res_data = await response.json()
                        if 'transactionHash' in res_data:
                            i = i + 1
                        else:
                            break
                    else:
                        print('response.text: ')
                        print(await response.text())
                        print('fusion {} response.status return: {}'.format(COIN_NAME, response.status))
                        break
        except asyncio.TimeoutError:
            print('TIMEOUT: {} COIN_NAME {} - timeout {}'.format(method, COIN_NAME, time_out))
            return i
    return i


async def save_walletapi(coin: str):
    time_out = 1200
    COIN_NAME = coin.upper()
    start = time.time()
    method = "/save"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(get_wallet_api_url(COIN_NAME) + method, headers=get_wallet_api_header(COIN_NAME), timeout=time_out) as response:
                if response.status == 200 or response.status == 201:
                    end = time.time()
                    return float(end - start)
                else:
                    return False
    except asyncio.TimeoutError:
        print('TIMEOUT: {} COIN_NAME {} - timeout {}'.format(method, COIN_NAME, time_out))
        return False


def walletapi_get_wallet_api_url(coin: str):
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family == "TRTL":
        return "http://"+getattr(config,"daemon"+COIN_NAME,config.daemonWRKZ).wallethost + ":" + \
            str(getattr(config,"daemon"+COIN_NAME,config.daemonWRKZ).walletport) \
            + '/json_rpc'
    elif coin_family == "XMR":
        return "http://"+getattr(config,"daemon"+COIN_NAME,config.daemonWRKZ).wallethost + ":" + \
            str(getattr(config,"daemon"+COIN_NAME,config.daemonWRKZ).walletport) \
            + '/json_rpc'


def get_mixin(coin: str = None):
    return getattr(config,"daemon"+coin,config.daemonWRKZ).mixin


def get_tx_fee(coin: str):
    return getattr(config,"daemon"+coin,config.daemonWRKZ).tx_fee


def get_wallet_api_url(coin: str):
    COIN_NAME = coin.upper()
    url = "http://"+getattr(config, "daemon"+COIN_NAME, config.daemonWRKZ).walletapi_host +":"+getattr(config, "daemon"+COIN_NAME, config.daemonWRKZ).walletapi_port
    return url

 
def get_wallet_api_header(coin: str):
    COIN_NAME = coin.upper()
    headers = {
        'X-API-KEY': f'{getattr(config, "daemon"+COIN_NAME, config.daemonWRKZ).walletapi_header}',
        'Content-Type': 'application/json'
    }
    return headers


def get_wallet_api_open_str(coin: str):
    COIN_NAME = coin.upper()
    wallet_str = '{"daemonHost":"'+str(getattr(config, "daemon"+COIN_NAME, config.daemonWRKZ).host)+\
        '", "daemonPort":'+str(getattr(config, "daemon"+COIN_NAME, config.daemonWRKZ).port)+\
        ', "filename":"'+str(getattr(config, "daemon"+COIN_NAME, config.daemonWRKZ).walletapi_file)+\
        '", "password":"'+str(getattr(config, "daemon"+COIN_NAME, config.daemonWRKZ).walletapi_password)+'"}'
    return wallet_str
