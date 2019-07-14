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


async def registerOTHER(coin: str) -> str:
    coin = coin.upper()
    result = await rpc_client.call_aiohttp_wallet('createAddress', coin)

    reg_address = {}
    reg_address['address'] = result['address']
    reg_address['privateSpendKey'] = await getSpendKey(result['address'], coin)

    # Avoid any crash and nothing to restore or import
    print('Wallet register: '+reg_address['address']+'=>privateSpendKey: '+reg_address['privateSpendKey'])
    # End print log ID,spendkey to log file
    return reg_address


async def getSpendKey(from_address: str, coin: str) -> str:
    coin = coin.upper()
    payload = {
        'address': from_address
    }
    result = await rpc_client.call_aiohttp_wallet('getSpendKeys', coin, payload=payload)
    return result['spendSecretKey']


async def send_transaction_donate(from_address: str, to_address: str, amount: int, coin: str) -> str:
    coin = coin.upper()
    payload = {
        'addresses': [from_address],
        'transfers': [{
            "amount": amount,
            "address": to_address
        }],
        'fee': get_tx_fee(coin),
        'anonymity': get_mixin(coin)
    }
    result = None
    result = await rpc_client.call_aiohttp_wallet('sendTransaction', coin, payload=payload)
    if result:
        if 'transactionHash' in result:
            return result['transactionHash']
    return result


async def send_transaction(from_address: str, to_address: str, amount: int, coin: str) -> str:
    coin = coin.upper()
    payload = {
        'addresses': [from_address],
        'transfers': [{
            "amount": amount,
            "address": to_address
        }],
        'fee': get_tx_fee(coin),
        'anonymity': get_mixin(coin)
    }
    result = None
    result = await rpc_client.call_aiohttp_wallet('sendTransaction', coin, payload=payload)
    if result:
        if 'transactionHash' in result:
            return result['transactionHash']
    return result


async def send_transaction_id(from_address: str, to_address: str, amount: int, paymentid: str, coin: str) -> str:
    coin = coin.upper()
    payload = {
        'addresses': [from_address],
        'transfers': [{
            "amount": amount,
            "address": to_address
        }],
        'fee': get_tx_fee(coin),
        'anonymity': get_mixin(coin),
        'paymentId': paymentid
    }
    result = None
    result = await rpc_client.call_aiohttp_wallet('sendTransaction', coin, payload=payload)
    if result:
        if 'transactionHash' in result:
            return result['transactionHash']
    return result


async def send_transactionall(from_address: str, to_address, coin: str) -> str:
    coin = coin.upper()
    payload = {
        'addresses': [from_address],
        'transfers': to_address,
        'fee': get_tx_fee(coin),
        'anonymity': get_mixin(coin),
    }
    result = None
    result = await rpc_client.call_aiohttp_wallet('sendTransaction', coin, payload=payload)
    if result:
        if 'transactionHash' in result:
            return result['transactionHash']
    return result


async def get_all_balances_all(coin: str) -> Dict[str, Dict]:
    coin = coin.upper()
    walletCall = await rpc_client.call_aiohttp_wallet('getAddresses', coin)
    wallets = [] ## new array
    for address in walletCall['addresses']:
        wallet = await rpc_client.call_aiohttp_wallet('getBalance', coin, {'address': address})
        wallets.append({'address':address,'unlocked':wallet['availableBalance'],'locked':wallet['lockedAmount']})
    return wallets


async def get_some_balances(wallet_addresses: List[str], coin: str) -> Dict[str, Dict]:
    coin = coin.upper()
    wallets = []  # new array
    for address in wallet_addresses:
        wallet = await rpc_client.call_aiohttp_wallet('getBalance', coin, {'address': address})
        wallets.append({'address':address,'unlocked':wallet['availableBalance'],'locked':wallet['lockedAmount']})
    return wallets


async def get_sum_balances(coin: str) -> Dict[str, Dict]:
    coin = coin.upper()
    wallet = None
    wallet = await rpc_client.call_aiohttp_wallet('getBalance', coin)
    if wallet:
        wallet = {'unlocked':wallet['availableBalance'],'locked':wallet['lockedAmount']}
        return wallet
    return None


async def get_balance_address(address: str, coin: str) -> Dict[str, Dict]:
    coin = coin.upper()
    result = await rpc_client.call_aiohttp_wallet('getBalance', coin, {'address': address})
    wallet = None
    if result:
        wallet = {'address':address,'unlocked':result['availableBalance'],'locked':result['lockedAmount']}
    return wallet


async def wallet_optimize_single(subaddress: str, threshold: int, coin: str=None) -> int:
    if coin is None:
        coin = "WRKZ"
    else:
        coin = coin.upper()

    params = {
        "threshold": int(threshold),
        "anonymity": get_mixin(coin),
        "addresses": [
            subaddress
        ],
        "destinationAddress": subaddress
    }
    full_payload = {
        'params': params or {},
        'jsonrpc': '2.0',
        'id': str(uuid4()),
        'method': 'sendFusionTransaction'
    }

    i = 0
    while True:
        #print('get_wallet_api_url(coin): '+ get_wallet_api_url(coin))
        url = get_wallet_api_url(coin) + '/json_rpc'
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=full_payload, timeout=8) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if 'result' in decoded_data:
                        if 'transactionHash' in decoded_data['result']:
                            i=i+1
                        else:
                            break
                    else:
                        break
                else:
                    break
    return i


async def rpc_cn_wallet_save(coin: str):
    coin = coin.upper()
    start = time.time()
    result = await rpc_client.call_aiohttp_wallet('save', coin)
    end = time.time()
    return float(end - start)


async def wallet_estimate_fusion(subaddress: str, threshold: int, coin: str=None) -> int:
    if coin is None:
        coin = "WRKZ"
    else:
        coin = coin.upper()

    payload = {
        "threshold": threshold,
        "addresses": [
            subaddress
        ]
    }
    result = await rpc_client.call_aiohttp_wallet('estimateFusion', coin, payload=payload)
    return result


def get_wallet_api_url(coin: str = None):
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME == "TRTL":
        url = "http://"+config.daemonTRTL.wallethost+":"+config.daemonTRTL.walletport
    elif COIN_NAME == "DEGO":
        url = "http://"+config.daemonDEGO.wallethost+":"+config.daemonDEGO.walletport
    elif COIN_NAME == "LCX":
        url = "http://"+config.daemonLCX.wallethost+":"+config.daemonLCX.walletport
    elif COIN_NAME == "CX":
        url = "http://"+config.daemonCX.wallethost+":"+config.daemonCX.walletport
    elif COIN_NAME == "WRKZ":
        url = "http://"+config.daemonWRKZ.wallethost+":"+config.daemonWRKZ.walletport
    elif COIN_NAME == "OSL":
        url = "http://"+config.daemonOSL.wallethost+":"+config.daemonOSL.walletport
    elif COIN_NAME == "BTCM":
        url = "http://"+config.daemonBTCM.wallethost+":"+config.daemonBTCM.walletport
    elif COIN_NAME == "MTIP":
        url = "http://"+config.daemonMTIP.wallethost+":"+config.daemonMTIP.walletport
    elif COIN_NAME == "XCY":
        url = "http://"+config.daemonXCY.wallethost+":"+config.daemonXCY.walletport
    elif COIN_NAME == "PLE":
        url = "http://"+config.daemonPLE.wallethost+":"+config.daemonPLE.walletport
    elif COIN_NAME == "ELPH":
        url = "http://"+config.daemonELPH.wallethost+":"+config.daemonELPH.walletport
    elif COIN_NAME == "ANX":
        url = "http://"+config.daemonANX.wallethost+":"+config.daemonANX.walletport
    elif COIN_NAME == "NBX":
        url = "http://"+config.daemonNBX.wallethost+":"+config.daemonNBX.walletport
    elif COIN_NAME == "ARMS":
        url = "http://"+config.daemonARMS.wallethost+":"+config.daemonARMS.walletport
    elif COIN_NAME == "IRD":
        url = "http://"+config.daemonIRD.wallethost+":"+config.daemonIRD.walletport
    elif COIN_NAME == "HITC":
        url = "http://"+config.daemonHITC.wallethost+":"+config.daemonHITC.walletport
    elif COIN_NAME == "NACA":
        url = "http://"+config.daemonNACA.wallethost+":"+config.daemonNACA.walletport
    else:
        url = "http://"+config.daemonWRKZ.wallethost+":"+config.daemonWRKZ.walletport
    return url

def get_mixin(coin: str = None):
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME == "TRTL":
        mixin = config.daemonTRTL.mixin
    elif COIN_NAME == "DEGO":
        mixin = config.daemonDEGO.mixin
    elif COIN_NAME == "LCX":
        mixin = config.daemonLCX.mixin
    elif COIN_NAME == "CX":
        mixin = config.daemonCX.mixin
    elif COIN_NAME == "WRKZ":
        mixin = config.daemonWRKZ.mixin
    elif COIN_NAME == "OSL":
        mixin = config.daemonOSL.mixin
    elif COIN_NAME == "BTCM":
        mixin = config.daemonBTCM.mixin
    elif COIN_NAME == "MTIP":
        mixin = config.daemonMTIP.mixin
    elif COIN_NAME == "XCY":
        mixin = config.daemonXCY.mixin
    elif COIN_NAME == "PLE":
        mixin = config.daemonPLE.mixin
    elif COIN_NAME == "ELPH":
        mixin = config.daemonELPH.mixin
    elif COIN_NAME == "ANX":
        mixin = config.daemonANX.mixin
    elif COIN_NAME == "NBX":
        mixin = config.daemonNBX.mixin
    elif COIN_NAME == "ARMS":
        mixin = config.daemonARMS.mixin
    elif COIN_NAME == "IRD":
        mixin = config.daemonIRD.mixin
    elif COIN_NAME == "HITC":
        mixin = config.daemonHITC.mixin
    elif COIN_NAME == "NACA":
        mixin = config.daemonNACA.mixin
    else:
        mixin = config.daemonWRKZ.mixin
    return mixin


def get_decimal(coin: str = None):
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME == "TRTL":
        decimal = config.daemonTRTL.decimal
    elif COIN_NAME == "DEGO":
        decimal = config.daemonDEGO.decimal
    elif COIN_NAME == "LCX":
        decimal = config.daemonLCX.decimal
    elif COIN_NAME == "CX":
        decimal = config.daemonCX.decimal
    elif COIN_NAME == "WRKZ":
        decimal = config.daemonWRKZ.decimal
    elif COIN_NAME == "OSL":
        decimal = config.daemonOSL.decimal
    elif COIN_NAME == "BTCM":
        decimal = config.daemonBTCM.decimal
    elif COIN_NAME == "MTIP":
        decimal = config.daemonMTIP.decimal
    elif COIN_NAME == "XCY":
        decimal = config.daemonXCY.decimal
    elif COIN_NAME == "PLE":
        decimal = config.daemonPLE.decimal
    elif COIN_NAME == "ELPH":
        decimal = config.daemonELPH.decimal
    elif COIN_NAME == "ANX":
        decimal = config.daemonANX.decimal
    elif COIN_NAME == "NBX":
        decimal = config.daemonNBX.decimal
    elif COIN_NAME == "ARMS":
        decimal = config.daemonARMS.decimal
    elif COIN_NAME == "IRD":
        decimal = config.daemonIRD.decimal
    elif COIN_NAME == "HITC":
        decimal = config.daemonHITC.decimal
    elif COIN_NAME == "NACA":
        decimal = config.daemonNACA.decimal
    else:
        decimal = config.daemonWRKZ.decimal
    return decimal


def get_addrlen(coin: str = None):
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME == "TRTL":
        len = config.daemonTRTL.AddrLen
    elif COIN_NAME == "DEGO":
        len = config.daemonDEGO.AddrLen
    elif COIN_NAME == "LCX":
        len = config.daemonLCX.AddrLen
    elif COIN_NAME == "CX":
        len = config.daemonCX.AddrLen
    elif COIN_NAME == "WRKZ":
        len = config.daemonWRKZ.AddrLen
    elif COIN_NAME == "OSL":
        len = config.daemonOSL.AddrLen
    elif COIN_NAME == "BTCM":
        len = config.daemonBTCM.AddrLen
    elif COIN_NAME == "MTIP":
        len = config.daemonMTIP.AddrLen
    elif COIN_NAME == "XCY":
        len = config.daemonXCY.AddrLen
    elif COIN_NAME == "PLE":
        len = config.daemonPLE.AddrLen
    elif COIN_NAME == "ELPH":
        len = config.daemonELPH.AddrLen
    elif COIN_NAME == "ANX":
        len = config.daemonANX.AddrLen
    elif COIN_NAME == "NBX":
        len = config.daemonNBX.AddrLen
    elif COIN_NAME == "ARMS":
        len = config.daemonARMS.AddrLen
    elif COIN_NAME == "IRD":
        len = config.daemonIRD.AddrLen
    elif COIN_NAME == "HITC":
        len = config.daemonHITC.AddrLen
    elif COIN_NAME == "NACA":
        len = config.daemonNACA.AddrLen
    else:
        len = config.daemonWRKZ.AddrLen
    return len


def get_intaddrlen(coin: str = None):
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME == "TRTL":
        len = config.daemonTRTL.IntAddrLen
    elif COIN_NAME == "DEGO":
        len = config.daemonDEGO.IntAddrLen
    elif COIN_NAME == "LCX":
        len = config.daemonLCX.IntAddrLen
    elif COIN_NAME == "CX":
        len = config.daemonCX.IntAddrLen
    elif COIN_NAME == "WRKZ":
        len = config.daemonWRKZ.IntAddrLen
    elif COIN_NAME == "OSL":
        len = config.daemonOSL.IntAddrLen
    elif COIN_NAME == "BTCM":
        len = config.daemonBTCM.IntAddrLen
    elif COIN_NAME == "MTIP":
        len = config.daemonMTIP.IntAddrLen
    elif COIN_NAME == "XCY":
        len = config.daemonXCY.IntAddrLen
    elif COIN_NAME == "PLE":
        len = config.daemonPLE.IntAddrLen
    elif COIN_NAME == "ELPH":
        len = config.daemonELPH.IntAddrLen
    elif COIN_NAME == "ANX":
        len = config.daemonANX.IntAddrLen
    elif COIN_NAME == "NBX":
        len = config.daemonNBX.IntAddrLen
    elif COIN_NAME == "ARMS":
        len = config.daemonARMS.IntAddrLen
    elif COIN_NAME == "IRD":
        len = config.daemonIRD.IntAddrLen
    elif COIN_NAME == "HITC":
        len = config.daemonHITC.IntAddrLen
    elif COIN_NAME == "NACA":
        len = config.daemonNACA.IntAddrLen
    else:
        len = config.daemonWRKZ.IntAddrLen
    return len


def get_prefix(coin: str = None):
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME == "TRTL":
        prefix = config.daemonTRTL.prefix
    elif COIN_NAME == "DEGO":
        prefix = config.daemonDEGO.prefix
    elif COIN_NAME == "LCX":
        prefix = config.daemonLCX.prefix
    elif COIN_NAME == "CX":
        prefix = config.daemonCX.prefix
    elif COIN_NAME == "WRKZ":
        prefix = config.daemonWRKZ.prefix
    elif COIN_NAME == "OSL":
        prefix = config.daemonOSL.prefix
    elif COIN_NAME == "BTCM":
        prefix = config.daemonBTCM.prefix
    elif COIN_NAME == "MTIP":
        prefix = config.daemonMTIP.prefix
    elif COIN_NAME == "XCY":
        prefix = config.daemonXCY.prefix
    elif COIN_NAME == "PLE":
        prefix = config.daemonPLE.prefix
    elif COIN_NAME == "ELPH":
        prefix = config.daemonELPH.prefix
    elif COIN_NAME == "ANX":
        prefix = config.daemonANX.prefix
    elif COIN_NAME == "NBX":
        prefix = config.daemonNBX.prefix
    elif COIN_NAME == "ARMS":
        prefix = config.daemonARMS.prefix
    elif COIN_NAME == "IRD":
        prefix = config.daemonIRD.prefix
    elif COIN_NAME == "HITC":
        prefix = config.daemonHITC.prefix
    elif COIN_NAME == "NACA":
        prefix = config.daemonNACA.prefix
    else:
        prefix = config.daemonWRKZ.prefix
    return prefix


def get_prefix_char(coin: str = None):
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME == "TRTL":
        prefix_char = config.daemonTRTL.prefixChar
    elif COIN_NAME == "DEGO":
        prefix_char = config.daemonDEGO.prefixChar
    elif COIN_NAME == "LCX":
        prefix_char = config.daemonLCX.prefixChar
    elif COIN_NAME == "CX":
        prefix_char = config.daemonCX.prefixChar
    elif COIN_NAME == "WRKZ":
        prefix_char = config.daemonWRKZ.prefixChar
    elif COIN_NAME == "OSL":
        prefix_char = config.daemonOSL.prefixChar
    elif COIN_NAME == "BTCM":
        prefix_char = config.daemonBTCM.prefixChar
    elif COIN_NAME == "MTIP":
        prefix_char = config.daemonMTIP.prefixChar
    elif COIN_NAME == "XCY":
        prefix_char = config.daemonXCY.prefixChar
    elif COIN_NAME == "PLE":
        prefix_char = config.daemonPLE.prefixChar
    elif COIN_NAME == "ELPH":
        prefix_char = config.daemonELPH.prefixChar
    elif COIN_NAME == "ANX":
        prefix_char = config.daemonANX.prefixChar
    elif COIN_NAME == "NBX":
        prefix_char = config.daemonNBX.prefixChar
    elif COIN_NAME == "ARMS":
        prefix_char = config.daemonARMS.prefixChar
    elif COIN_NAME == "IRD":
        prefix_char = config.daemonIRD.prefixChar
    elif COIN_NAME == "HITC":
        prefix_char = config.daemonHITC.prefixChar
    elif COIN_NAME == "NACA":
        prefix_char = config.daemonNACA.prefixChar
    else:
        prefix_char = config.daemonWRKZ.prefixChar
    return prefix_char


def get_donate_address(coin: str = None):
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME == "TRTL":
        donate_address = config.daemonTRTL.DonateAddress
    elif COIN_NAME == "DEGO":
        donate_address = config.daemonDEGO.DonateAddress
    elif COIN_NAME == "LCX":
        donate_address = config.daemonLCX.DonateAddress
    elif COIN_NAME == "CX":
        donate_address = config.daemonCX.DonateAddress
    elif COIN_NAME == "WRKZ":
        donate_address = config.daemonWRKZ.DonateAddress
    elif COIN_NAME == "OSL":
        donate_address = config.daemonOSL.DonateAddress
    elif COIN_NAME == "BTCM":
        donate_address = config.daemonBTCM.DonateAddress
    elif COIN_NAME == "MTIP":
        donate_address = config.daemonMTIP.DonateAddress
    elif COIN_NAME == "XCY":
        donate_address = config.daemonXCY.DonateAddress
    elif COIN_NAME == "PLE":
        donate_address = config.daemonPLE.DonateAddress
    elif COIN_NAME == "ELPH":
        donate_address = config.daemonELPH.DonateAddress
    elif COIN_NAME == "ANX":
        donate_address = config.daemonANX.DonateAddress
    elif COIN_NAME == "NBX":
        donate_address = config.daemonNBX.DonateAddress
    elif COIN_NAME == "ARMS":
        donate_address = config.daemonARMS.DonateAddress
    elif COIN_NAME == "IRD":
        donate_address = config.daemonIRD.DonateAddress
    elif COIN_NAME == "HITC":
        donate_address = config.daemonHITC.DonateAddress
    elif COIN_NAME == "NACA":
        donate_address = config.daemonNACA.DonateAddress
    else:
        donate_address = config.daemonWRKZ.DonateAddress
    return donate_address


def get_voucher_address(coin: str = None):
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME == "TRTL":
        voucher_address = config.daemonTRTL.voucher_address
    elif COIN_NAME == "DEGO":
        voucher_address = config.daemonDEGO.voucher_address
    elif COIN_NAME == "LCX":
        voucher_address = config.daemonLCX.voucher_address
    elif COIN_NAME == "CX":
        voucher_address = config.daemonCX.voucher_address
    elif COIN_NAME == "WRKZ":
        voucher_address = config.daemonWRKZ.voucher_address
    elif COIN_NAME == "OSL":
        voucher_address = config.daemonOSL.voucher_address
    elif COIN_NAME == "BTCM":
        voucher_address = config.daemonBTCM.voucher_address
    elif COIN_NAME == "MTIP":
        voucher_address = config.daemonMTIP.voucher_address
    elif COIN_NAME == "XCY":
        voucher_address = config.daemonXCY.voucher_address
    elif COIN_NAME == "PLE":
        voucher_address = config.daemonPLE.voucher_address
    elif COIN_NAME == "ELPH":
        voucher_address = config.daemonELPH.voucher_address
    elif COIN_NAME == "ANX":
        voucher_address = config.daemonANX.voucher_address
    elif COIN_NAME == "NBX":
        voucher_address = config.daemonNBX.voucher_address
    elif COIN_NAME == "ARMS":
        voucher_address = config.daemonARMS.voucher_address
    elif COIN_NAME == "IRD":
        voucher_address = config.daemonIRD.voucher_address
    elif COIN_NAME == "HITC":
        voucher_address = config.daemonHITC.voucher_address
    elif COIN_NAME == "NACA":
        voucher_address = config.daemonNACA.voucher_address
    else:
        voucher_address = config.daemonWRKZ.voucher_address
    return voucher_address


def get_diff_target(coin: str = None):
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME == "TRTL":
        diff_target = config.daemonTRTL.DiffTarget
    elif COIN_NAME == "DEGO":
        diff_target = config.daemonDEGO.DiffTarget
    elif COIN_NAME == "LCX":
        diff_target = config.daemonLCX.DiffTarget
    elif COIN_NAME == "CX":
        diff_target = config.daemonCX.DiffTarget
    elif COIN_NAME == "WRKZ":
        diff_target = config.daemonWRKZ.DiffTarget
    elif COIN_NAME == "OSL":
        diff_target = config.daemonOSL.DiffTarget
    elif COIN_NAME == "BTCM":
        diff_target = config.daemonBTCM.DiffTarget
    elif COIN_NAME == "MTIP":
        diff_target = config.daemonMTIP.DiffTarget
    elif COIN_NAME == "XCY":
        diff_target = config.daemonXCY.DiffTarget
    elif COIN_NAME == "PLE":
        diff_target = config.daemonPLE.DiffTarget
    elif COIN_NAME == "ELPH":
        diff_target = config.daemonELPH.DiffTarget
    elif COIN_NAME == "ANX":
        diff_target = config.daemonANX.DiffTarget
    elif COIN_NAME == "NBX":
        diff_target = config.daemonNBX.DiffTarget
    elif COIN_NAME == "ARMS":
        diff_target = config.daemonARMS.DiffTarget
    elif COIN_NAME == "IRD":
        diff_target = config.daemonIRD.DiffTarget
    elif COIN_NAME == "HITC":
        diff_target = config.daemonHITC.DiffTarget
    elif COIN_NAME == "NACA":
        diff_target = config.daemonNACA.DiffTarget
    else:
        diff_target = config.daemonWRKZ.DiffTarget
    return diff_target


def get_tx_fee(coin: str = None):
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME == "TRTL":
        tx_fee = config.daemonTRTL.tx_fee
    elif COIN_NAME == "DEGO":
        tx_fee = config.daemonDEGO.tx_fee
    elif COIN_NAME == "LCX":
        tx_fee = config.daemonLCX.tx_fee
    elif COIN_NAME == "CX":
        tx_fee = config.daemonCX.tx_fee
    elif COIN_NAME == "WRKZ":
        tx_fee = config.daemonWRKZ.tx_fee
    elif COIN_NAME == "OSL":
        tx_fee = config.daemonOSL.tx_fee
    elif COIN_NAME == "BTCM":
        tx_fee = config.daemonBTCM.tx_fee
    elif COIN_NAME == "MTIP":
        tx_fee = config.daemonMTIP.tx_fee
    elif COIN_NAME == "XCY":
        tx_fee = config.daemonXCY.tx_fee
    elif COIN_NAME == "PLE":
        tx_fee = config.daemonPLE.tx_fee
    elif COIN_NAME == "ELPH":
        tx_fee = config.daemonELPH.tx_fee
    elif COIN_NAME == "ANX":
        tx_fee = config.daemonANX.tx_fee
    elif COIN_NAME == "NBX":
        tx_fee = config.daemonNBX.tx_fee
    elif COIN_NAME == "ARMS":
        tx_fee = config.daemonARMS.tx_fee
    elif COIN_NAME == "IRD":
        tx_fee = config.daemonIRD.tx_fee
    elif COIN_NAME == "HITC":
        tx_fee = config.daemonHITC.tx_fee
    elif COIN_NAME == "NACA":
        tx_fee = config.daemonNACA.tx_fee
    else:
        tx_fee = config.daemonWRKZ.tx_fee
    return tx_fee


def get_coin_fullname(coin: str = None):
    qr_address_pref = None
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME == "TRTL":
        qr_address_pref = "turtlecoin"
    elif COIN_NAME == "DEGO":
        qr_address_pref = "derogold"
    elif COIN_NAME == "LCX":
        qr_address_pref = "lightchain"
    elif COIN_NAME == "CX":
        qr_address_pref = "catalyst"
    elif COIN_NAME == "WRKZ":
        qr_address_pref = "wrkzcoin"
    elif COIN_NAME == "OSL":
        qr_address_pref = "oscillate"
    elif COIN_NAME == "BTCM":
        qr_address_pref = "bitcoinmono"
    elif COIN_NAME == "MTIP":
        qr_address_pref = "monkeytips"
    elif COIN_NAME == "XCY":
        qr_address_pref = "cypruscoin"
    elif COIN_NAME == "PLE":
        qr_address_pref = "plenteum"
    elif COIN_NAME == "ELPH":
        qr_address_pref = "elphyrecoin"
    elif COIN_NAME == "ANX":
        qr_address_pref = "aluisyocoin"
    elif COIN_NAME == "NBX":
        qr_address_pref = "nibbleclassic"
    elif COIN_NAME == "ARMS":
        qr_address_pref = "2acoin"
    elif COIN_NAME == "IRD":
        qr_address_pref = "iridium"
    elif COIN_NAME == "HITC":
        qr_address_pref = "hitc"
    elif COIN_NAME == "NACA":
        qr_address_pref = "nashcash"
    return qr_address_pref


def get_reserved_fee(coin: str = None):
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME == "TRTL":
        reserved_fee = config.daemonTRTL.voucher_reserved_fee
    elif COIN_NAME == "DEGO":
        reserved_fee = config.daemonDEGO.voucher_reserved_fee
    elif COIN_NAME == "LCX":
        reserved_fee = config.daemonLCX.voucher_reserved_fee
    elif COIN_NAME == "CX":
        reserved_fee = config.daemonCX.voucher_reserved_fee
    elif COIN_NAME == "WRKZ":
        reserved_fee = config.daemonWRKZ.voucher_reserved_fee
    elif COIN_NAME == "OSL":
        reserved_fee = config.daemonOSL.voucher_reserved_fee
    elif COIN_NAME == "BTCM":
        reserved_fee = config.daemonBTCM.voucher_reserved_fee
    elif COIN_NAME == "MTIP":
        reserved_fee = config.daemonMTIP.voucher_reserved_fee
    elif COIN_NAME == "XCY":
        reserved_fee = config.daemonXCY.voucher_reserved_fee
    elif COIN_NAME == "PLE":
        reserved_fee = config.daemonPLE.voucher_reserved_fee
    elif COIN_NAME == "ELPH":
        reserved_fee = config.daemonELPH.voucher_reserved_fee
    elif COIN_NAME == "ANX":
        reserved_fee = config.daemonANX.voucher_reserved_fee
    elif COIN_NAME == "NBX":
        reserved_fee = config.daemonNBX.voucher_reserved_fee
    elif COIN_NAME == "ARMS":
        reserved_fee = config.daemonARMS.voucher_reserved_fee
    elif COIN_NAME == "IRD":
        reserved_fee = config.daemonIRD.voucher_reserved_fee
    elif COIN_NAME == "HITC":
        reserved_fee = config.daemonHITC.voucher_reserved_fee
    elif COIN_NAME == "NACA":
        reserved_fee = config.daemonNACA.voucher_reserved_fee
    else:
        reserved_fee = config.daemonWRKZ.voucher_reserved_fee
    return reserved_fee


def get_min_tx_amount(coin: str = None):
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME == "TRTL":
        min_tx_amount = config.daemonTRTL.min_tx_amount
    elif COIN_NAME == "DEGO":
        min_tx_amount = config.daemonDEGO.min_tx_amount
    elif COIN_NAME == "LCX":
        min_tx_amount = config.daemonLCX.min_tx_amount
    elif COIN_NAME == "CX":
        min_tx_amount = config.daemonCX.min_tx_amount
    elif COIN_NAME == "WRKZ":
        min_tx_amount = config.daemonWRKZ.min_tx_amount
    elif COIN_NAME == "OSL":
        min_tx_amount = config.daemonOSL.min_tx_amount
    elif COIN_NAME == "BTCM":
        min_tx_amount = config.daemonBTCM.min_tx_amount
    elif COIN_NAME == "MTIP":
        min_tx_amount = config.daemonMTIP.min_tx_amount
    elif COIN_NAME == "XCY":
        min_tx_amount = config.daemonXCY.min_tx_amount
    elif COIN_NAME == "ELPH":
        min_tx_amount = config.daemonELPH.min_tx_amount
    elif COIN_NAME == "ANX":
        min_tx_amount = config.daemonANX.min_tx_amount
    elif COIN_NAME == "NBX":
        min_tx_amount = config.daemonNBX.min_tx_amount
    elif COIN_NAME == "ARMS":
        min_tx_amount = config.daemonARMS.min_tx_amount
    elif COIN_NAME == "IRD":
        min_tx_amount = config.daemonIRD.min_tx_amount
    elif COIN_NAME == "HITC":
        min_tx_amount = config.daemonHITC.min_tx_amount
    elif COIN_NAME == "NACA":
        min_tx_amount = config.daemonNACA.min_tx_amount
    else:
        min_tx_amount = config.daemonWRKZ.min_tx_amount
    return min_tx_amount


def get_max_tx_amount(coin: str = None):
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()
        
    if COIN_NAME == "TRTL":
        max_tx_amount = config.daemonTRTL.max_tx_amount
    elif COIN_NAME == "DEGO":
        max_tx_amount = config.daemonDEGO.max_tx_amount
    elif COIN_NAME == "LCX":
        max_tx_amount = config.daemonLCX.max_tx_amount
    elif COIN_NAME == "CX":
        max_tx_amount = config.daemonCX.max_tx_amount
    elif COIN_NAME == "WRKZ":
        max_tx_amount = config.daemonWRKZ.max_tx_amount
    elif COIN_NAME == "OSL":
        max_tx_amount = config.daemonOSL.max_tx_amount
    elif COIN_NAME == "BTCM":
        max_tx_amount = config.daemonBTCM.max_tx_amount
    elif COIN_NAME == "MTIP":
        max_tx_amount = config.daemonMTIP.max_tx_amount
    elif COIN_NAME == "XCY":
        max_tx_amount = config.daemonXCY.max_tx_amount
    elif COIN_NAME == "PLE":
        max_tx_amount = config.daemonPLE.max_tx_amount
    elif COIN_NAME == "ELPH":
        max_tx_amount = config.daemonELPH.max_tx_amount
    elif COIN_NAME == "ANX":
        max_tx_amount = config.daemonANX.max_tx_amount
    elif COIN_NAME == "NBX":
        max_tx_amount = config.daemonNBX.max_tx_amount
    elif COIN_NAME == "ARMS":
        max_tx_amount = config.daemonARMS.max_tx_amount
    elif COIN_NAME == "IRD":
        max_tx_amount = config.daemonIRD.max_tx_amount
    elif COIN_NAME == "HITC":
        max_tx_amount = config.daemonHITC.max_tx_amount
    elif COIN_NAME == "NACA":
        max_tx_amount = config.daemonNACA.max_tx_amount
    else:
        max_tx_amount = config.daemonWRKZ.max_tx_amount
    return max_tx_amount


def get_interval_opt(coin: str = None):
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME == "TRTL":
        interval = config.daemonTRTL.IntervalOptimize
    elif COIN_NAME == "DEGO":
        interval = config.daemonDEGO.IntervalOptimize
    elif COIN_NAME == "LCX":
        interval = config.daemonLCX.IntervalOptimize
    elif COIN_NAME == "CX":
        interval = config.daemonCX.IntervalOptimize
    elif COIN_NAME == "WRKZ":
        interval = config.daemonWRKZ.IntervalOptimize
    elif COIN_NAME == "OSL":
        interval = config.daemonOSL.IntervalOptimize
    elif COIN_NAME == "BTCM":
        interval = config.daemonBTCM.IntervalOptimize
    elif COIN_NAME == "MTIP":
        interval = config.daemonMTIP.IntervalOptimize
    elif COIN_NAME == "XCY":
        interval = config.daemonXCY.IntervalOptimize
    elif COIN_NAME == "PLE":
        interval = config.daemonPLE.IntervalOptimize
    elif COIN_NAME == "ELPH":
        interval = config.daemonELPH.IntervalOptimize
    elif COIN_NAME == "ANX":
        interval = config.daemonANX.IntervalOptimize
    elif COIN_NAME == "NBX":
        interval = config.daemonNBX.IntervalOptimize
    elif COIN_NAME == "ARMS":
        interval = config.daemonARMS.IntervalOptimize
    elif COIN_NAME == "IRD":
        interval = config.daemonIRD.IntervalOptimize
    elif COIN_NAME == "HITC":
        interval = config.daemonHITC.IntervalOptimize
    elif COIN_NAME == "NACA":
        interval = config.daemonNACA.IntervalOptimize
    else:
        interval = config.daemonWRKZ.IntervalOptimize
    return interval


def get_min_opt(coin: str = None):
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME == "TRTL":
        mini_opt = config.daemonTRTL.MinToOptimize
    elif COIN_NAME == "DEGO":
        mini_opt = config.daemonDEGO.MinToOptimize
    elif COIN_NAME == "LCX":
        mini_opt = config.daemonLCX.MinToOptimize
    elif COIN_NAME == "CX":
        mini_opt = config.daemonCX.MinToOptimize
    elif COIN_NAME == "WRKZ":
        mini_opt = config.daemonWRKZ.MinToOptimize
    elif COIN_NAME == "OSL":
        mini_opt = config.daemonOSL.MinToOptimize
    elif COIN_NAME == "BTCM":
        mini_opt = config.daemonBTCM.MinToOptimize
    elif COIN_NAME == "MTIP":
        mini_opt = config.daemonMTIP.MinToOptimize
    elif COIN_NAME == "XCY":
        mini_opt = config.daemonXCY.MinToOptimize
    elif COIN_NAME == "PLE":
        mini_opt = config.daemonPLE.MinToOptimize
    elif COIN_NAME == "ELPH":
        mini_opt = config.daemonELPH.MinToOptimize
    elif COIN_NAME == "ANX":
        mini_opt = config.daemonANX.MinToOptimize
    elif COIN_NAME == "NBX":
        mini_opt = config.daemonNBX.MinToOptimize
    elif COIN_NAME == "ARMS":
        mini_opt = config.daemonARMS.MinToOptimize
    elif COIN_NAME == "IRD":
        mini_opt = config.daemonIRD.MinToOptimize
    elif COIN_NAME == "HITC":
        mini_opt = config.daemonHITC.MinToOptimize
    elif COIN_NAME == "NACA":
        mini_opt = config.daemonNACA.MinToOptimize
    else:
        mini_opt = config.daemonWRKZ.MinToOptimize
    return mini_opt


def get_coinlogo_path(coin: str = None):
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME == "TRTL":
        coinlogo_path = config.daemonTRTL.voucher_logo
    elif COIN_NAME == "DEGO":
        coinlogo_path = config.daemonDEGO.voucher_logo
    elif COIN_NAME == "LCX":
        coinlogo_path = config.daemonLCX.voucher_logo
    elif COIN_NAME == "CX":
        coinlogo_path = config.daemonCX.voucher_logo
    elif COIN_NAME == "WRKZ":
        coinlogo_path = config.daemonWRKZ.voucher_logo
    elif COIN_NAME == "OSL":
        coinlogo_path = config.daemonOSL.voucher_logo
    elif COIN_NAME == "BTCM":
        coinlogo_path = config.daemonBTCM.voucher_logo
    elif COIN_NAME == "MTIP":
        coinlogo_path = config.daemonMTIP.voucher_logo
    elif COIN_NAME == "XCY":
        coinlogo_path = config.daemonXCY.voucher_logo
    elif COIN_NAME == "PLE":
        coinlogo_path = config.daemonPLE.voucher_logo
    elif COIN_NAME == "ELPH":
        coinlogo_path = config.daemonELPH.voucher_logo
    elif COIN_NAME == "ANX":
        coinlogo_path = config.daemonANX.voucher_logo
    elif COIN_NAME == "NBX":
        coinlogo_path = config.daemonNBX.voucher_logo
    elif COIN_NAME == "ARMS":
        coinlogo_path = config.daemonARMS.voucher_logo
    elif COIN_NAME == "IRD":
        coinlogo_path = config.daemonIRD.voucher_logo
    elif COIN_NAME == "HITC":
        coinlogo_path = config.daemonHITC.voucher_logo
    elif COIN_NAME == "NACA":
        coinlogo_path = config.daemonNACA.voucher_logo
    else:
        coinlogo_path = config.daemonWRKZ.voucher_logo
    return config.qrsettings.coin_logo_path + coinlogo_path


def num_format_coin(amount, coin: str = None):
    if coin is None:
        coin = "WRKZ"
    else:
        coin = coin.upper()
    if coin == "DOGE":
        coin_decimal = 1
    elif coin == "LTC":
        coin_decimal = 1
    else:
        coin_decimal = get_decimal(coin)
    amount_str = 'Invalid.'
    if coin == 	"DOGE":
        return '{:,.6f}'.format(amount)
    if coin_decimal > 1000000:
        amount_str = '{:,.8f}'.format(amount / coin_decimal)
    elif coin_decimal > 10000:
        amount_str = '{:,.6f}'.format(amount / coin_decimal)
    elif coin_decimal > 100:
        amount_str = '{:,.4f}'.format(amount / coin_decimal)
    else:
        amount_str = '{:,.2f}'.format(amount / coin_decimal)
    return amount_str


async def DOGE_LTC_register(account: str, coin: str) -> str:
    payload = f'"{account}"'
    address_call = await rpc_client.call_doge_ltc('getnewaddress', coin.upper(), payload=payload)
    reg_address = {}
    reg_address['address'] = address_call
    payload = f'"{address_call}"'
    key_call = await rpc_client.call_doge_ltc('dumpprivkey', coin.upper(), payload=payload)
    reg_address['privateKey'] = key_call
    return reg_address


async def DOGE_LTC_validaddress(address: str, coin: str) -> str:
    payload = f'"{address}"'
    valid_call = await rpc_client.call_doge_ltc('validateaddress', coin.upper(), payload=payload)
    return valid_call


async def DOGE_LTC_getbalance_acc(account: str, coin: str, confirmation: int=None) -> str:
    if confirmation is None:
        conf = 1
    else:
        conf = confirmation
    payload = f'"{account}", {conf}'
    valid_call = await rpc_client.call_doge_ltc('getbalance', coin.upper(), payload=payload)
    return valid_call


async def DOGE_LTC_getaccountaddress(account: str, coin: str) -> str:
    payload = f'"{account}"'
    valid_call = await rpc_client.call_doge_ltc('getaccountaddress', coin.upper(), payload=payload)
    return valid_call


async def DOGE_LTC_sendtoaddress(to_address: str, amount: float, comment: str, coin: str, comment_to: str=None) -> str:
    if comment_to is None:
        comment_to = "wrkz"
    payload = f'"{to_address}", {amount}, "{comment}", "{comment_to}", true'
    valid_call = await rpc_client.call_doge_ltc('sendtoaddress', coin.upper(), payload=payload)
    return valid_call


async def DOGE_LTC_listreceivedbyaddress(coin: str):
    payload = '0, true'
    valid_call = await rpc_client.call_doge_ltc('listreceivedbyaddress', coin.upper(), payload=payload)
    account_list = []
    if len(valid_call) >=1:
        for item in valid_call:
            account_list.append({"address": item['address'], "account": item['account'], "amount": item['amount']})
    return account_list


async def DOGE_LTC_dumpprivkey(address: str, coin: str) -> str:
    payload = f'"{address}"'
    key_call = await rpc_client.call_doge_ltc('dumpprivkey', coin.upper(), payload=payload)
    return key_call
