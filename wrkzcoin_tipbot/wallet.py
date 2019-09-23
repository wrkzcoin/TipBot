from typing import List, Dict
import json
from uuid import uuid4
import rpc_client
import aiohttp
import asyncio
import time
import addressvalidation

from config import config

import sys
sys.path.append("..")


async def registerOTHER(coin: str) -> str:
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    reg_address = {}
    if coin_family == "XMR":
        payload = {
            'label' : 'tipbot'
        }
        result = await rpc_client.call_aiohttp_wallet('create_account', COIN_NAME, payload=payload)
        print(result)
        if result is None:
            print("Error when creating address ");
            return None
        else:
            # {"account_index": 1, "address": "bit..."}
            reg_address = result
            return reg_address
    else:
        result = await rpc_client.call_aiohttp_wallet('createAddress', COIN_NAME)
        reg_address['address'] = result['address']
        reg_address['privateSpendKey'] = await getSpendKey(result['address'], COIN_NAME)
        
        # Avoid any crash and nothing to restore or import
        print('Wallet register: '+reg_address['address']+'=>privateSpendKey: '+reg_address['privateSpendKey'])
        # End print log ID,spendkey to log file
        return reg_address


async def get_all_addresses(coin: str) -> Dict[str, Dict]:
    COIN_NAME = coin.upper()
    result = await rpc_client.call_aiohttp_wallet('getAddresses', COIN_NAME)
    return result['addresses']


async def getSpendKey(from_address: str, coin: str) -> str:
    coin = coin.upper()
    payload = {
        'address': from_address
    }
    result = await rpc_client.call_aiohttp_wallet('getSpendKeys', coin, payload=payload)
    return result['spendSecretKey']


async def send_transaction(from_address: str, to_address: str, amount: int, coin: str, acc_index: int = None) -> str:
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    result = None
    time_out = 32
    if coin_family == "TRTL" or coin_family == "CCX":
        payload = {
            'addresses': [from_address],
            'transfers': [{
                "amount": amount,
                "address": to_address
            }],
            'fee': get_tx_fee(COIN_NAME),
            'anonymity': get_mixin(COIN_NAME)
        }
        result = await rpc_client.call_aiohttp_wallet('sendTransaction', COIN_NAME, time_out=time_out, payload=payload)
        if result:
            if 'transactionHash' in result:
                return result['transactionHash']
    elif coin_family == "XMR":
        payload = {
            "destinations": [{'amount': amount, 'address': to_address}],
            "account_index": acc_index,
            "subaddr_indices": [],
            "priority": 1,
            "unlock_time": 0,
            "get_tx_key": True,
            "get_tx_hex": False,
            "get_tx_metadata": False
        }
        result = await rpc_client.call_aiohttp_wallet('transfer', COIN_NAME, time_out=time_out, payload=payload)
        if result:
            if ('tx_hash' in result) and ('tx_key' in result):
                return result
    return result


async def send_transaction_id(from_address: str, to_address: str, amount: int, paymentid: str, coin: str) -> str:
    time_out = 32
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
    result = await rpc_client.call_aiohttp_wallet('sendTransaction', coin, time_out=time_out, payload=payload)
    if result:
        if 'transactionHash' in result:
            return result['transactionHash']
    return result


async def send_transactionall(from_address: str, to_address, coin: str, acc_index: int = None) -> str:
    time_out = 32
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    result = None
    if coin_family == "TRTL" or coin_family == "CCX":
        payload = {
            'addresses': [from_address],
            'transfers': to_address,
            'fee': get_tx_fee(coin),
            'anonymity': get_mixin(coin),
        }
        result = await rpc_client.call_aiohttp_wallet('sendTransaction', coin, time_out=time_out, payload=payload)
        if result:
            if 'transactionHash' in result:
                return result['transactionHash']
    elif coin_family == "XMR":
        payload = {
            "destinations": to_address,
            "account_index": acc_index,
            "subaddr_indices": [],
            "priority": 1,
            "unlock_time": 0,
            "get_tx_key": True,
            "get_tx_hex": False,
            "get_tx_metadata": False
        }
        result = await rpc_client.call_aiohttp_wallet('transfer', COIN_NAME, time_out=time_out, payload=payload)
        if result:
            if ('tx_hash' in result) and ('tx_key' in result):
                return result
    return result


async def get_all_balances_all(coin: str) -> Dict[str, Dict]:
    coin = coin.upper()
    walletCall = await rpc_client.call_aiohttp_wallet('getAddresses', coin)
    wallets = [] ## new array
    for address in walletCall['addresses']:
        wallet = await rpc_client.call_aiohttp_wallet('getBalance', coin, payload={'address': address})
        wallets.append({'address':address,'unlocked':wallet['availableBalance'],'locked':wallet['lockedAmount']})
    return wallets


async def get_some_balances(wallet_addresses: List[str], coin: str) -> Dict[str, Dict]:
    coin = coin.upper()
    wallets = []  # new array
    for address in wallet_addresses:
        wallet = await rpc_client.call_aiohttp_wallet('getBalance', coin, payload={'address': address})
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


async def get_balance_address(address: str, coin: str, acc_index: int = None) -> Dict[str, Dict]:
    coin = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+coin),"coin_family","TRTL")
    if coin_family == "XMR":
        if acc_index is None:
            acc_index = 0
        result = await rpc_client.call_aiohttp_wallet('getbalance', coin, payload={'account_index': acc_index, 'address_indices': [acc_index]})
        wallet = None
        if result:
            wallet = {'address':address,'locked':(result['balance'] - result['unlocked_balance']),'unlocked':result['unlocked_balance']}
        return wallet
    elif coin_family == "TRTL":
        result = await rpc_client.call_aiohttp_wallet('getBalance', coin, payload={'address': address})
        wallet = None
        if result:
            wallet = {'address':address,'unlocked':result['availableBalance'],'locked':result['lockedAmount']}
        return wallet


async def wallet_optimize_single(subaddress: str, threshold: int, coin: str=None) -> int:
    time_out = 32
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
        url = get_wallet_api_url(coin)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=full_payload, timeout=time_out) as response:
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
        except asyncio.TimeoutError:
            print('TIMEOUT: method_name: {} - coin_family: {} - timeout {}'.format('sendFusionTransaction', coin, time_out))
            return i
    return i


async def rpc_cn_wallet_save(coin: str):
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    start = time.time()
    if coin_family == "TRTL" or coin_family == "CCX":
        result = await rpc_client.call_aiohttp_wallet('save', coin)
    elif coin_family == "XMR":
        result = await rpc_client.call_aiohttp_wallet('store', coin)
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


def get_decimal(coin: str = None):
    return getattr(config,"daemon"+coin,config.daemonWRKZ).decimal


def get_addrlen(coin: str = None):
    return getattr(config,"daemon"+coin,config.daemonWRKZ).AddrLen


def get_intaddrlen(coin: str = None):
    return getattr(config,"daemon"+coin,config.daemonWRKZ).IntAddrLen


def get_prefix(coin: str = None):
    return getattr(config,"daemon"+coin,config.daemonWRKZ).prefix


def get_prefix_char(coin: str = None):
    return getattr(config,"daemon"+coin,config.daemonWRKZ).prefixChar


def get_donate_address(coin: str = None):
    return getattr(config,"daemon"+coin,config.daemonWRKZ).DonateAddress

def get_donate_account_name(coin: str):
    return getattr(config,"daemon"+coin).DonateAccount


def get_voucher_address(coin: str = None):
    return getattr(config,"daemon"+coin,config.daemonWRKZ).voucher_address


def get_diff_target(coin: str = None):
    return getattr(config,"daemon"+coin,config.daemonWRKZ).DiffTarget


def get_tx_fee(coin: str):
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family == "TRTL" or coin_family == "CCX" or coin_family == "DOGE" or coin_family == "LTC" :
        return getattr(config,"daemon"+coin,config.daemonWRKZ).tx_fee        
    elif coin_family == "XMR":
        return getattr(config,"daemon"+coin,config.daemonXMR).tx_fee


async def get_tx_fee_xmr(coin: str, amount: int = None, to_address: str = None):
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","XMR")      
    if coin_family == "XMR":
        payload = {
            "destinations": [{'amount': amount, 'address': to_address}],
            "account_index": 0,
            "subaddr_indices": [],
            "get_tx_key": True,
            "do_not_relay": True,
            "get_tx_hex": True,
            "get_tx_metadata": False
        }
        result = await rpc_client.call_aiohttp_wallet('transfer', COIN_NAME, time_out=8, payload=payload)
        if result:
            if ('tx_hash' in result) and ('tx_key' in result) and ('fee' in result):
                return result['fee']


def get_coin_fullname(coin: str = None):
    qr_address_pref = {"TRTL":"turtlecoin","DEGO":"derogold","CX":"catalyst","WRKZ":"wrkzcoin","OSL":"oscillate",\
    "BTCMZ":"bitcoinmono","MTIP":"monkeytips","XCY":"cypruscoin","PLE":"plenteum","ELPH":"elphyrecoin","ANX":"aluisyocoin","NBX":"nibbleclassic",\
    "ARMS":"2acoin","HITC":"hitc","NACA":"nashcash","XTOR":"bittoro","BLOG":"blogcoin","LOKI":"loki","XMR":"monero","XEQ":"Equilibria","ARQ":"arqma"}
    return getattr(qr_address_pref,coin,"wrkzcoin")


def get_reserved_fee(coin: str = None):
    return getattr(config,"daemon"+coin,config.daemonWRKZ).voucher_reserved_fee


def get_min_tx_amount(coin: str = None):
    return getattr(config,"daemon"+coin,config.daemonWRKZ).min_tx_amount


def get_max_tx_amount(coin: str = None):
    return getattr(config,"daemon"+coin,config.daemonWRKZ).max_tx_amount


def get_interval_opt(coin: str = None):
    return getattr(config,"daemon"+coin,config.daemonWRKZ).IntervalOptimize


def get_min_opt(coin: str = None):
    return getattr(config,"daemon"+coin,config.daemonWRKZ).MinToOptimize


def get_coinlogo_path(coin: str = None):
    return config.qrsettings.coin_logo_path + getattr(config,"daemon"+coin,config.daemonWRKZ).voucher_logo


def num_format_coin(amount, coin: str = None):
    COIN_NAME = None
    if coin is None:
        COIN_NAME = "WRKZ"
    else:
        COIN_NAME = coin.upper()
    
    if COIN_NAME == "DOGE":
        coin_decimal = 1
    elif COIN_NAME == "LTC":
        coin_decimal = 1
    else:
        coin_decimal = get_decimal(COIN_NAME)
    amount_str = 'Invalid.'
    if COIN_NAME == 	"DOGE":
        return '{:,.6f}'.format(amount)
    if coin_decimal > 100000000:
        amount_str = '{:,.10f}'.format(amount / coin_decimal)
    elif coin_decimal > 1000000:
        amount_str = '{:,.8f}'.format(amount / coin_decimal)
    elif coin_decimal > 10000:
        amount_str = '{:,.6f}'.format(amount / coin_decimal)
    elif coin_decimal > 100:
        amount_str = '{:,.4f}'.format(amount / coin_decimal)
    else:
        amount_str = '{:,.2f}'.format(amount / coin_decimal)
    return amount_str


# XMR
async def validate_address_xmr(address: str, coin: str):
    coin_family = getattr(getattr(config,"daemon"+coin),"coin_family","XMR")
    if coin_family == "XMR":
        payload = {
            "address" : address,
            "any_net_type": True,
            "allow_openalias": True
        }
        address_xmr = await rpc_client.call_aiohttp_wallet('validate_address', coin, payload=payload)
        if address_xmr:
            return address_xmr
        else:
            return None


async def make_integrated_address_xmr(address: str, coin: str, paymentid: str = None):
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","XMR")
    if paymentid:
        try:
            value = int(paymentid, 16)
        except ValueError:
            return False
    else:
        paymentid = addressvalidation.paymentid(8)
    if coin_family == "XMR":
        payload = {
            "standard_address" : address,
            "payment_id": {} or paymentid
        }
        address_ia = await rpc_client.call_aiohttp_wallet('make_integrated_address', COIN_NAME, payload=payload)
        if address_ia:
            return address_ia
        else:
            return None


async def get_transfers_xmr(coin: str, height_start: int = None, height_end: int = None):
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","XMR")
    if coin_family == "XMR":
        payload = None
        if height_start and height_end:
            payload = {
                "in" : True,
                "out": True,
                "pending": False,
                "failed": False,
                "pool": False,
                "filter_by_height": True,
                "min_height": height_start,
                "max_height": height_end
            }
        else:
            payload = {
                "in" : True,
                "out": True,
                "pending": False,
                "failed": False,
                "pool": False,
                "filter_by_height": False
            }
        result = await rpc_client.call_aiohttp_wallet('get_transfers', COIN_NAME, payload=payload)
        return result


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
    if len(valid_call) >= 1:
        for item in valid_call:
            account_list.append({"address": item['address'], "account": item['account'], "amount": item['amount']})
    return account_list


async def DOGE_LTC_dumpprivkey(address: str, coin: str) -> str:
    payload = f'"{address}"'
    key_call = await rpc_client.call_doge_ltc('dumpprivkey', coin.upper(), payload=payload)
    return key_call
