from typing import List, Dict
import json
from uuid import uuid4
import rpc_client
import aiohttp
import asyncio
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
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        url = "http://"+config.daemonTRTL.wallethost+":"+config.daemonTRTL.walletport
    elif coin.upper() == "DEGO":
        url = "http://"+config.daemonDEGO.wallethost+":"+config.daemonDEGO.walletport
    elif coin.upper() == "LCX":
        url = "http://"+config.daemonLCX.wallethost+":"+config.daemonLCX.walletport
    elif coin.upper() == "CX":
        url = "http://"+config.daemonCX.wallethost+":"+config.daemonCX.walletport
    elif coin.upper() == "WRKZ":
        url = "http://"+config.daemonWRKZ.wallethost+":"+config.daemonWRKZ.walletport
    elif coin.upper() == "OSL":
        url = "http://"+config.daemonOSL.wallethost+":"+config.daemonOSL.walletport
    elif coin.upper() == "BTCM":
        url = "http://"+config.daemonBTCM.wallethost+":"+config.daemonBTCM.walletport
    elif coin.upper() == "MTIP":
        url = "http://"+config.daemonMTIP.wallethost+":"+config.daemonMTIP.walletport
    elif coin.upper() == "XCY":
        url = "http://"+config.daemonXCY.wallethost+":"+config.daemonXCY.walletport
    elif coin.upper() == "PLE":
        url = "http://"+config.daemonPLE.wallethost+":"+config.daemonPLE.walletport
    elif coin.upper() == "ELPH":
        url = "http://"+config.daemonELPH.wallethost+":"+config.daemonELPH.walletport
    elif coin.upper() == "ANX":
        url = "http://"+config.daemonANX.wallethost+":"+config.daemonANX.walletport
    elif coin.upper() == "NBX":
        url = "http://"+config.daemonNBX.wallethost+":"+config.daemonNBX.walletport
    elif coin.upper() == "ARMS":
        url = "http://"+config.daemonARMS.wallethost+":"+config.daemonARMS.walletport
    elif coin.upper() == "IRD":
        url = "http://"+config.daemonIRD.wallethost+":"+config.daemonIRD.walletport
    elif coin.upper() == "HITC":
        url = "http://"+config.daemonHITC.wallethost+":"+config.daemonHITC.walletport
    elif coin.upper() == "NACA":
        url = "http://"+config.daemonNACA.wallethost+":"+config.daemonNACA.walletport
    else:
        url = "http://"+config.daemonWRKZ.wallethost+":"+config.daemonWRKZ.walletport
    return url

def get_mixin(coin: str = None):
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        mixin = config.daemonTRTL.mixin
    elif coin.upper() == "DEGO":
        mixin = config.daemonDEGO.mixin
    elif coin.upper() == "LCX":
        mixin = config.daemonLCX.mixin
    elif coin.upper() == "CX":
        mixin = config.daemonCX.mixin
    elif coin.upper() == "WRKZ":
        mixin = config.daemonWRKZ.mixin
    elif coin.upper() == "OSL":
        mixin = config.daemonOSL.mixin
    elif coin.upper() == "BTCM":
        mixin = config.daemonBTCM.mixin
    elif coin.upper() == "MTIP":
        mixin = config.daemonMTIP.mixin
    elif coin.upper() == "XCY":
        mixin = config.daemonXCY.mixin
    elif coin.upper() == "PLE":
        mixin = config.daemonPLE.mixin
    elif coin.upper() == "ELPH":
        mixin = config.daemonELPH.mixin
    elif coin.upper() == "ANX":
        mixin = config.daemonANX.mixin
    elif coin.upper() == "NBX":
        mixin = config.daemonNBX.mixin
    elif coin.upper() == "ARMS":
        mixin = config.daemonARMS.mixin
    elif coin.upper() == "IRD":
        mixin = config.daemonIRD.mixin
    elif coin.upper() == "HITC":
        mixin = config.daemonHITC.mixin
    elif coin.upper() == "NACA":
        mixin = config.daemonNACA.mixin
    else:
        mixin = config.daemonWRKZ.mixin
    return mixin


def get_decimal(coin: str = None):
    if coin is None:
        coin = "WRKZ"
    else:
        coin = coin.upper().strip()
    if coin.upper() == "TRTL":
        decimal = config.daemonTRTL.decimal
    elif coin.upper() == "DEGO":
        decimal = config.daemonDEGO.decimal
    elif coin.upper() == "LCX":
        decimal = config.daemonLCX.decimal
    elif coin.upper() == "CX":
        decimal = config.daemonCX.decimal
    elif coin.upper() == "WRKZ":
        decimal = config.daemonWRKZ.decimal
    elif coin.upper() == "OSL":
        decimal = config.daemonOSL.decimal
    elif coin.upper() == "BTCM":
        decimal = config.daemonBTCM.decimal
    elif coin.upper() == "MTIP":
        decimal = config.daemonMTIP.decimal
    elif coin.upper() == "XCY":
        decimal = config.daemonXCY.decimal
    elif coin.upper() == "PLE":
        decimal = config.daemonPLE.decimal
    elif coin.upper() == "ELPH":
        decimal = config.daemonELPH.decimal
    elif coin.upper() == "ANX":
        decimal = config.daemonANX.decimal
    elif coin.upper() == "NBX":
        decimal = config.daemonNBX.decimal
    elif coin.upper() == "ARMS":
        decimal = config.daemonARMS.decimal
    elif coin.upper() == "IRD":
        decimal = config.daemonIRD.decimal
    elif coin.upper() == "HITC":
        decimal = config.daemonHITC.decimal
    elif coin.upper() == "NACA":
        decimal = config.daemonNACA.decimal
    else:
        decimal = config.daemonWRKZ.decimal
    return decimal


def get_addrlen(coin: str = None):
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        len = config.daemonTRTL.AddrLen
    elif coin.upper() == "DEGO":
        len = config.daemonDEGO.AddrLen
    elif coin.upper() == "LCX":
        len = config.daemonLCX.AddrLen
    elif coin.upper() == "CX":
        len = config.daemonCX.AddrLen
    elif coin.upper() == "WRKZ":
        len = config.daemonWRKZ.AddrLen
    elif coin.upper() == "OSL":
        len = config.daemonOSL.AddrLen
    elif coin.upper() == "BTCM":
        len = config.daemonBTCM.AddrLen
    elif coin.upper() == "MTIP":
        len = config.daemonMTIP.AddrLen
    elif coin.upper() == "XCY":
        len = config.daemonXCY.AddrLen
    elif coin.upper() == "PLE":
        len = config.daemonPLE.AddrLen
    elif coin.upper() == "ELPH":
        len = config.daemonELPH.AddrLen
    elif coin.upper() == "ANX":
        len = config.daemonANX.AddrLen
    elif coin.upper() == "NBX":
        len = config.daemonNBX.AddrLen
    elif coin.upper() == "ARMS":
        len = config.daemonARMS.AddrLen
    elif coin.upper() == "IRD":
        len = config.daemonIRD.AddrLen
    elif coin.upper() == "HITC":
        len = config.daemonHITC.AddrLen
    elif coin.upper() == "NACA":
        len = config.daemonNACA.AddrLen
    else:
        len = config.daemonWRKZ.AddrLen
    return len


def get_intaddrlen(coin: str = None):
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        len = config.daemonTRTL.IntAddrLen
    elif coin.upper() == "DEGO":
        len = config.daemonDEGO.IntAddrLen
    elif coin.upper() == "LCX":
        len = config.daemonLCX.IntAddrLen
    elif coin.upper() == "CX":
        len = config.daemonCX.IntAddrLen
    elif coin.upper() == "WRKZ":
        len = config.daemonWRKZ.IntAddrLen
    elif coin.upper() == "OSL":
        len = config.daemonOSL.IntAddrLen
    elif coin.upper() == "BTCM":
        len = config.daemonBTCM.IntAddrLen
    elif coin.upper() == "MTIP":
        len = config.daemonMTIP.IntAddrLen
    elif coin.upper() == "XCY":
        len = config.daemonXCY.IntAddrLen
    elif coin.upper() == "PLE":
        len = config.daemonPLE.IntAddrLen
    elif coin.upper() == "ELPH":
        len = config.daemonELPH.IntAddrLen
    elif coin.upper() == "ANX":
        len = config.daemonANX.IntAddrLen
    elif coin.upper() == "NBX":
        len = config.daemonNBX.IntAddrLen
    elif coin.upper() == "ARMS":
        len = config.daemonARMS.IntAddrLen
    elif coin.upper() == "IRD":
        len = config.daemonIRD.IntAddrLen
    elif coin.upper() == "HITC":
        len = config.daemonHITC.IntAddrLen
    elif coin.upper() == "NACA":
        len = config.daemonNACA.IntAddrLen
    else:
        len = config.daemonWRKZ.IntAddrLen
    return len


def get_prefix(coin: str = None):
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        prefix = config.daemonTRTL.prefix
    elif coin.upper() == "DEGO":
        prefix = config.daemonDEGO.prefix
    elif coin.upper() == "LCX":
        prefix = config.daemonLCX.prefix
    elif coin.upper() == "CX":
        prefix = config.daemonCX.prefix
    elif coin.upper() == "WRKZ":
        prefix = config.daemonWRKZ.prefix
    elif coin.upper() == "OSL":
        prefix = config.daemonOSL.prefix
    elif coin.upper() == "BTCM":
        prefix = config.daemonBTCM.prefix
    elif coin.upper() == "MTIP":
        prefix = config.daemonMTIP.prefix
    elif coin.upper() == "XCY":
        prefix = config.daemonXCY.prefix
    elif coin.upper() == "PLE":
        prefix = config.daemonPLE.prefix
    elif coin.upper() == "ELPH":
        prefix = config.daemonELPH.prefix
    elif coin.upper() == "ANX":
        prefix = config.daemonANX.prefix
    elif coin.upper() == "NBX":
        prefix = config.daemonNBX.prefix
    elif coin.upper() == "ARMS":
        prefix = config.daemonARMS.prefix
    elif coin.upper() == "IRD":
        prefix = config.daemonIRD.prefix
    elif coin.upper() == "HITC":
        prefix = config.daemonHITC.prefix
    elif coin.upper() == "NACA":
        prefix = config.daemonNACA.prefix
    else:
        prefix = config.daemonWRKZ.prefix
    return prefix


def get_prefix_char(coin: str = None):
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        prefix_char = config.daemonTRTL.prefixChar
    elif coin.upper() == "DEGO":
        prefix_char = config.daemonDEGO.prefixChar
    elif coin.upper() == "LCX":
        prefix_char = config.daemonLCX.prefixChar
    elif coin.upper() == "CX":
        prefix_char = config.daemonCX.prefixChar
    elif coin.upper() == "WRKZ":
        prefix_char = config.daemonWRKZ.prefixChar
    elif coin.upper() == "OSL":
        prefix_char = config.daemonOSL.prefixChar
    elif coin.upper() == "BTCM":
        prefix_char = config.daemonBTCM.prefixChar
    elif coin.upper() == "MTIP":
        prefix_char = config.daemonMTIP.prefixChar
    elif coin.upper() == "XCY":
        prefix_char = config.daemonXCY.prefixChar
    elif coin.upper() == "PLE":
        prefix_char = config.daemonPLE.prefixChar
    elif coin.upper() == "ELPH":
        prefix_char = config.daemonELPH.prefixChar
    elif coin.upper() == "ANX":
        prefix_char = config.daemonANX.prefixChar
    elif coin.upper() == "NBX":
        prefix_char = config.daemonNBX.prefixChar
    elif coin.upper() == "ARMS":
        prefix_char = config.daemonARMS.prefixChar
    elif coin.upper() == "IRD":
        prefix_char = config.daemonIRD.prefixChar
    elif coin.upper() == "HITC":
        prefix_char = config.daemonHITC.prefixChar
    elif coin.upper() == "NACA":
        prefix_char = config.daemonNACA.prefixChar
    else:
        prefix_char = config.daemonWRKZ.prefixChar
    return prefix_char


def get_donate_address(coin: str = None):
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        donate_address = config.daemonTRTL.DonateAddress
    elif coin.upper() == "DEGO":
        donate_address = config.daemonDEGO.DonateAddress
    elif coin.upper() == "LCX":
        donate_address = config.daemonLCX.DonateAddress
    elif coin.upper() == "CX":
        donate_address = config.daemonCX.DonateAddress
    elif coin.upper() == "WRKZ":
        donate_address = config.daemonWRKZ.DonateAddress
    elif coin.upper() == "OSL":
        donate_address = config.daemonOSL.DonateAddress
    elif coin.upper() == "BTCM":
        donate_address = config.daemonBTCM.DonateAddress
    elif coin.upper() == "MTIP":
        donate_address = config.daemonMTIP.DonateAddress
    elif coin.upper() == "XCY":
        donate_address = config.daemonXCY.DonateAddress
    elif coin.upper() == "PLE":
        donate_address = config.daemonPLE.DonateAddress
    elif coin.upper() == "ELPH":
        donate_address = config.daemonELPH.DonateAddress
    elif coin.upper() == "ANX":
        donate_address = config.daemonANX.DonateAddress
    elif coin.upper() == "NBX":
        donate_address = config.daemonNBX.DonateAddress
    elif coin.upper() == "ARMS":
        donate_address = config.daemonARMS.DonateAddress
    elif coin.upper() == "IRD":
        donate_address = config.daemonIRD.DonateAddress
    elif coin.upper() == "HITC":
        donate_address = config.daemonHITC.DonateAddress
    elif coin.upper() == "NACA":
        donate_address = config.daemonNACA.DonateAddress
    else:
        donate_address = config.daemonWRKZ.DonateAddress
    return donate_address


def get_voucher_address(coin: str = None):
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        voucher_address = config.daemonTRTL.voucher_address
    elif coin.upper() == "DEGO":
        voucher_address = config.daemonDEGO.voucher_address
    elif coin.upper() == "LCX":
        voucher_address = config.daemonLCX.voucher_address
    elif coin.upper() == "CX":
        voucher_address = config.daemonCX.voucher_address
    elif coin.upper() == "WRKZ":
        voucher_address = config.daemonWRKZ.voucher_address
    elif coin.upper() == "OSL":
        voucher_address = config.daemonOSL.voucher_address
    elif coin.upper() == "BTCM":
        voucher_address = config.daemonBTCM.voucher_address
    elif coin.upper() == "MTIP":
        voucher_address = config.daemonMTIP.voucher_address
    elif coin.upper() == "XCY":
        voucher_address = config.daemonXCY.voucher_address
    elif coin.upper() == "PLE":
        voucher_address = config.daemonPLE.voucher_address
    elif coin.upper() == "ELPH":
        voucher_address = config.daemonELPH.voucher_address
    elif coin.upper() == "ANX":
        voucher_address = config.daemonANX.voucher_address
    elif coin.upper() == "NBX":
        voucher_address = config.daemonNBX.voucher_address
    elif coin.upper() == "ARMS":
        voucher_address = config.daemonARMS.voucher_address
    elif coin.upper() == "IRD":
        voucher_address = config.daemonIRD.voucher_address
    elif coin.upper() == "HITC":
        voucher_address = config.daemonHITC.voucher_address
    elif coin.upper() == "NACA":
        voucher_address = config.daemonNACA.voucher_address
    else:
        voucher_address = config.daemonWRKZ.voucher_address
    return voucher_address


def get_diff_target(coin: str = None):
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        diff_target = config.daemonTRTL.DiffTarget
    elif coin.upper() == "DEGO":
        diff_target = config.daemonDEGO.DiffTarget
    elif coin.upper() == "LCX":
        diff_target = config.daemonLCX.DiffTarget
    elif coin.upper() == "CX":
        diff_target = config.daemonCX.DiffTarget
    elif coin.upper() == "WRKZ":
        diff_target = config.daemonWRKZ.DiffTarget
    elif coin.upper() == "OSL":
        diff_target = config.daemonOSL.DiffTarget
    elif coin.upper() == "BTCM":
        diff_target = config.daemonBTCM.DiffTarget
    elif coin.upper() == "MTIP":
        diff_target = config.daemonMTIP.DiffTarget
    elif coin.upper() == "XCY":
        diff_target = config.daemonXCY.DiffTarget
    elif coin.upper() == "PLE":
        diff_target = config.daemonPLE.DiffTarget
    elif coin.upper() == "ELPH":
        diff_target = config.daemonELPH.DiffTarget
    elif coin.upper() == "ANX":
        diff_target = config.daemonANX.DiffTarget
    elif coin.upper() == "NBX":
        diff_target = config.daemonNBX.DiffTarget
    elif coin.upper() == "ARMS":
        diff_target = config.daemonARMS.DiffTarget
    elif coin.upper() == "IRD":
        diff_target = config.daemonIRD.DiffTarget
    elif coin.upper() == "HITC":
        diff_target = config.daemonHITC.DiffTarget
    elif coin.upper() == "NACA":
        diff_target = config.daemonNACA.DiffTarget
    else:
        diff_target = config.daemonWRKZ.DiffTarget
    return diff_target


def get_tx_fee(coin: str = None):
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        tx_fee = config.daemonTRTL.tx_fee
    elif coin.upper() == "DEGO":
        tx_fee = config.daemonDEGO.tx_fee
    elif coin.upper() == "LCX":
        tx_fee = config.daemonLCX.tx_fee
    elif coin.upper() == "CX":
        tx_fee = config.daemonCX.tx_fee
    elif coin.upper() == "WRKZ":
        tx_fee = config.daemonWRKZ.tx_fee
    elif coin.upper() == "OSL":
        tx_fee = config.daemonOSL.tx_fee
    elif coin.upper() == "BTCM":
        tx_fee = config.daemonBTCM.tx_fee
    elif coin.upper() == "MTIP":
        tx_fee = config.daemonMTIP.tx_fee
    elif coin.upper() == "XCY":
        tx_fee = config.daemonXCY.tx_fee
    elif coin.upper() == "PLE":
        tx_fee = config.daemonPLE.tx_fee
    elif coin.upper() == "ELPH":
        tx_fee = config.daemonELPH.tx_fee
    elif coin.upper() == "ANX":
        tx_fee = config.daemonANX.tx_fee
    elif coin.upper() == "NBX":
        tx_fee = config.daemonNBX.tx_fee
    elif coin.upper() == "ARMS":
        tx_fee = config.daemonARMS.tx_fee
    elif coin.upper() == "IRD":
        tx_fee = config.daemonIRD.tx_fee
    elif coin.upper() == "HITC":
        tx_fee = config.daemonHITC.tx_fee
    elif coin.upper() == "NACA":
        tx_fee = config.daemonNACA.tx_fee
    else:
        tx_fee = config.daemonWRKZ.tx_fee
    return tx_fee


def get_coin_fullname(coin: str = None):
    qr_address_pref = None
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        qr_address_pref = "turtlecoin"
    elif coin.upper() == "DEGO":
        qr_address_pref = "derogold"
    elif coin.upper() == "LCX":
        qr_address_pref = "lightchain"
    elif coin.upper() == "CX":
        qr_address_pref = "catalyst"
    elif coin.upper() == "WRKZ":
        qr_address_pref = "wrkzcoin"
    elif coin.upper() == "OSL":
        qr_address_pref = "oscillate"
    elif coin.upper() == "BTCM":
        qr_address_pref = "bitcoinmono"
    elif coin.upper() == "MTIP":
        qr_address_pref = "monkeytips"
    elif coin.upper() == "XCY":
        qr_address_pref = "cypruscoin"
    elif coin.upper() == "PLE":
        qr_address_pref = "plenteum"
    elif coin.upper() == "ELPH":
        qr_address_pref = "elphyrecoin"
    elif coin.upper() == "ANX":
        qr_address_pref = "aluisyocoin"
    elif coin.upper() == "NBX":
        qr_address_pref = "nibbleclassic"
    elif coin.upper() == "ARMS":
        qr_address_pref = "2acoin"
    elif coin.upper() == "IRD":
        qr_address_pref = "iridium"
    elif coin.upper() == "HITC":
        qr_address_pref = "hitc"
    elif coin.upper() == "NACA":
        qr_address_pref = "nashcash"
    return qr_address_pref


def get_reserved_fee(coin: str = None):
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        reserved_fee = config.daemonTRTL.voucher_reserved_fee
    elif coin.upper() == "DEGO":
        reserved_fee = config.daemonDEGO.voucher_reserved_fee
    elif coin.upper() == "LCX":
        reserved_fee = config.daemonLCX.voucher_reserved_fee
    elif coin.upper() == "CX":
        reserved_fee = config.daemonCX.voucher_reserved_fee
    elif coin.upper() == "WRKZ":
        reserved_fee = config.daemonWRKZ.voucher_reserved_fee
    elif coin.upper() == "OSL":
        reserved_fee = config.daemonOSL.voucher_reserved_fee
    elif coin.upper() == "BTCM":
        reserved_fee = config.daemonBTCM.voucher_reserved_fee
    elif coin.upper() == "MTIP":
        reserved_fee = config.daemonMTIP.voucher_reserved_fee
    elif coin.upper() == "XCY":
        reserved_fee = config.daemonXCY.voucher_reserved_fee
    elif coin.upper() == "PLE":
        reserved_fee = config.daemonPLE.voucher_reserved_fee
    elif coin.upper() == "ELPH":
        reserved_fee = config.daemonELPH.voucher_reserved_fee
    elif coin.upper() == "ANX":
        reserved_fee = config.daemonANX.voucher_reserved_fee
    elif coin.upper() == "NBX":
        reserved_fee = config.daemonNBX.voucher_reserved_fee
    elif coin.upper() == "ARMS":
        reserved_fee = config.daemonARMS.voucher_reserved_fee
    elif coin.upper() == "IRD":
        reserved_fee = config.daemonIRD.voucher_reserved_fee
    elif coin.upper() == "HITC":
        reserved_fee = config.daemonHITC.voucher_reserved_fee
    elif coin.upper() == "NACA":
        reserved_fee = config.daemonNACA.voucher_reserved_fee
    else:
        reserved_fee = config.daemonWRKZ.voucher_reserved_fee
    return reserved_fee


def get_min_tx_amount(coin: str = None):
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        min_tx_amount = config.daemonTRTL.min_tx_amount
    elif coin.upper() == "DEGO":
        min_tx_amount = config.daemonDEGO.min_tx_amount
    elif coin.upper() == "LCX":
        min_tx_amount = config.daemonLCX.min_tx_amount
    elif coin.upper() == "CX":
        min_tx_amount = config.daemonCX.min_tx_amount
    elif coin.upper() == "WRKZ":
        min_tx_amount = config.daemonWRKZ.min_tx_amount
    elif coin.upper() == "OSL":
        min_tx_amount = config.daemonOSL.min_tx_amount
    elif coin.upper() == "BTCM":
        min_tx_amount = config.daemonBTCM.min_tx_amount
    elif coin.upper() == "MTIP":
        min_tx_amount = config.daemonMTIP.min_tx_amount
    elif coin.upper() == "XCY":
        min_tx_amount = config.daemonXCY.min_tx_amount
    elif coin.upper() == "ELPH":
        min_tx_amount = config.daemonELPH.min_tx_amount
    elif coin.upper() == "ANX":
        min_tx_amount = config.daemonANX.min_tx_amount
    elif coin.upper() == "NBX":
        min_tx_amount = config.daemonNBX.min_tx_amount
    elif coin.upper() == "ARMS":
        min_tx_amount = config.daemonARMS.min_tx_amount
    elif coin.upper() == "IRD":
        min_tx_amount = config.daemonIRD.min_tx_amount
    elif coin.upper() == "HITC":
        min_tx_amount = config.daemonHITC.min_tx_amount
    elif coin.upper() == "NACA":
        min_tx_amount = config.daemonNACA.min_tx_amount
    else:
        min_tx_amount = config.daemonWRKZ.min_tx_amount
    return min_tx_amount


def get_max_tx_amount(coin: str = None):
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        max_tx_amount = config.daemonTRTL.max_tx_amount
    elif coin.upper() == "DEGO":
        max_tx_amount = config.daemonDEGO.max_tx_amount
    elif coin.upper() == "LCX":
        max_tx_amount = config.daemonLCX.max_tx_amount
    elif coin.upper() == "CX":
        max_tx_amount = config.daemonCX.max_tx_amount
    elif coin.upper() == "WRKZ":
        max_tx_amount = config.daemonWRKZ.max_tx_amount
    elif coin.upper() == "OSL":
        max_tx_amount = config.daemonOSL.max_tx_amount
    elif coin.upper() == "BTCM":
        max_tx_amount = config.daemonBTCM.max_tx_amount
    elif coin.upper() == "MTIP":
        max_tx_amount = config.daemonMTIP.max_tx_amount
    elif coin.upper() == "XCY":
        max_tx_amount = config.daemonXCY.max_tx_amount
    elif coin.upper() == "PLE":
        max_tx_amount = config.daemonPLE.max_tx_amount
    elif coin.upper() == "ELPH":
        max_tx_amount = config.daemonELPH.max_tx_amount
    elif coin.upper() == "ANX":
        max_tx_amount = config.daemonANX.max_tx_amount
    elif coin.upper() == "NBX":
        max_tx_amount = config.daemonNBX.max_tx_amount
    elif coin.upper() == "ARMS":
        max_tx_amount = config.daemonARMS.max_tx_amount
    elif coin.upper() == "IRD":
        max_tx_amount = config.daemonIRD.max_tx_amount
    elif coin.upper() == "HITC":
        max_tx_amount = config.daemonHITC.max_tx_amount
    elif coin.upper() == "NACA":
        max_tx_amount = config.daemonNACA.max_tx_amount
    else:
        max_tx_amount = config.daemonWRKZ.max_tx_amount
    return max_tx_amount


def get_interval_opt(coin: str = None):
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        interval = config.daemonTRTL.IntervalOptimize
    elif coin.upper() == "DEGO":
        interval = config.daemonDEGO.IntervalOptimize
    elif coin.upper() == "LCX":
        interval = config.daemonLCX.IntervalOptimize
    elif coin.upper() == "CX":
        interval = config.daemonCX.IntervalOptimize
    elif coin.upper() == "WRKZ":
        interval = config.daemonWRKZ.IntervalOptimize
    elif coin.upper() == "OSL":
        interval = config.daemonOSL.IntervalOptimize
    elif coin.upper() == "BTCM":
        interval = config.daemonBTCM.IntervalOptimize
    elif coin.upper() == "MTIP":
        interval = config.daemonMTIP.IntervalOptimize
    elif coin.upper() == "XCY":
        interval = config.daemonXCY.IntervalOptimize
    elif coin.upper() == "PLE":
        interval = config.daemonPLE.IntervalOptimize
    elif coin.upper() == "ELPH":
        interval = config.daemonELPH.IntervalOptimize
    elif coin.upper() == "ANX":
        interval = config.daemonANX.IntervalOptimize
    elif coin.upper() == "NBX":
        interval = config.daemonNBX.IntervalOptimize
    elif coin.upper() == "ARMS":
        interval = config.daemonARMS.IntervalOptimize
    elif coin.upper() == "IRD":
        interval = config.daemonIRD.IntervalOptimize
    elif coin.upper() == "HITC":
        interval = config.daemonHITC.IntervalOptimize
    elif coin.upper() == "NACA":
        interval = config.daemonNACA.IntervalOptimize
    else:
        interval = config.daemonWRKZ.IntervalOptimize
    return interval


def get_min_opt(coin: str = None):
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        mini_opt = config.daemonTRTL.MinToOptimize
    elif coin.upper() == "DEGO":
        mini_opt = config.daemonDEGO.MinToOptimize
    elif coin.upper() == "LCX":
        mini_opt = config.daemonLCX.MinToOptimize
    elif coin.upper() == "CX":
        mini_opt = config.daemonCX.MinToOptimize
    elif coin.upper() == "WRKZ":
        mini_opt = config.daemonWRKZ.MinToOptimize
    elif coin.upper() == "OSL":
        mini_opt = config.daemonOSL.MinToOptimize
    elif coin.upper() == "BTCM":
        mini_opt = config.daemonBTCM.MinToOptimize
    elif coin.upper() == "MTIP":
        mini_opt = config.daemonMTIP.MinToOptimize
    elif coin.upper() == "XCY":
        mini_opt = config.daemonXCY.MinToOptimize
    elif coin.upper() == "PLE":
        mini_opt = config.daemonPLE.MinToOptimize
    elif coin.upper() == "ELPH":
        mini_opt = config.daemonELPH.MinToOptimize
    elif coin.upper() == "ANX":
        mini_opt = config.daemonANX.MinToOptimize
    elif coin.upper() == "NBX":
        mini_opt = config.daemonNBX.MinToOptimize
    elif coin.upper() == "ARMS":
        mini_opt = config.daemonARMS.MinToOptimize
    elif coin.upper() == "IRD":
        mini_opt = config.daemonIRD.MinToOptimize
    elif coin.upper() == "HITC":
        mini_opt = config.daemonHITC.MinToOptimize
    elif coin.upper() == "NACA":
        mini_opt = config.daemonNACA.MinToOptimize
    else:
        mini_opt = config.daemonWRKZ.MinToOptimize
    return mini_opt


def get_coinlogo_path(coin: str = None):
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        coinlogo_path = config.daemonTRTL.voucher_logo
    elif coin.upper() == "DEGO":
        coinlogo_path = config.daemonDEGO.voucher_logo
    elif coin.upper() == "LCX":
        coinlogo_path = config.daemonLCX.voucher_logo
    elif coin.upper() == "CX":
        coinlogo_path = config.daemonCX.voucher_logo
    elif coin.upper() == "WRKZ":
        coinlogo_path = config.daemonWRKZ.voucher_logo
    elif coin.upper() == "OSL":
        coinlogo_path = config.daemonOSL.voucher_logo
    elif coin.upper() == "BTCM":
        coinlogo_path = config.daemonBTCM.voucher_logo
    elif coin.upper() == "MTIP":
        coinlogo_path = config.daemonMTIP.voucher_logo
    elif coin.upper() == "XCY":
        coinlogo_path = config.daemonXCY.voucher_logo
    elif coin.upper() == "PLE":
        coinlogo_path = config.daemonPLE.voucher_logo
    elif coin.upper() == "ELPH":
        coinlogo_path = config.daemonELPH.voucher_logo
    elif coin.upper() == "ANX":
        coinlogo_path = config.daemonANX.voucher_logo
    elif coin.upper() == "NBX":
        coinlogo_path = config.daemonNBX.voucher_logo
    elif coin.upper() == "ARMS":
        coinlogo_path = config.daemonARMS.voucher_logo
    elif coin.upper() == "IRD":
        coinlogo_path = config.daemonIRD.voucher_logo
    elif coin.upper() == "HITC":
        coinlogo_path = config.daemonHITC.voucher_logo
    elif coin.upper() == "NACA":
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


async def DOGE_register(account: str, coin: str) -> str:
    payload = f'"{account}"'
    address_call = await rpc_client.call_doge_ltc('getnewaddress', coin.upper(), payload=payload)
    reg_address = {}
    reg_address['address'] = address_call
    payload = f'"{address_call}"'
    key_call = await rpc_client.call_doge_ltc('dumpprivkey', coin.upper(), payload=payload)
    reg_address['privateKey'] = key_call
    return reg_address


async def DOGE_validaddress(address: str, coin: str) -> str:
    payload = f'"{address}"'
    valid_call = await rpc_client.call_doge_ltc('validateaddress', coin.upper(), payload=payload)
    return valid_call


async def DOGE_getbalance_acc(account: str, coin: str, confirmation: int=None) -> str:
    if confirmation is None:
        conf = 1
    else:
        conf = confirmation
    payload = f'"{account}", {conf}'
    valid_call = await rpc_client.call_doge_ltc('getbalance', coin.upper(), payload=payload)
    return valid_call


async def DOGE_getaccountaddress(account: str, coin: str) -> str:
    payload = f'"{account}"'
    valid_call = await rpc_client.call_doge_ltc('getaccountaddress', coin.upper(), payload=payload)
    return valid_call


async def DOGE_sendtoaddress(to_address: str, amount: float, comment: str, coin: str, comment_to: str=None) -> str:
    if comment_to is None:
        comment_to = "wrkz"
    payload = f'"{to_address}", {amount}, "{comment}", "{comment_to}", true'
    valid_call = await rpc_client.call_doge_ltc('sendtoaddress', coin.upper(), payload=payload)
    return valid_call


async def DOGE_listreceivedbyaddress(coin: str):
    payload = '0, true'
    valid_call = await rpc_client.call_doge_ltc('listreceivedbyaddress', coin.upper(), payload=payload)
    account_list = []
    if len(valid_call) >=1:
        for item in valid_call:
            account_list.append({"address": item['address'], "account": item['account'], "amount": item['amount']})
    return account_list


async def DOGE_dumpprivkey(address: str, coin: str) -> str:
    payload = f'"{address}"'
    key_call = await rpc_client.call_doge_ltc('dumpprivkey', coin.upper(), payload=payload)
    return key_call
