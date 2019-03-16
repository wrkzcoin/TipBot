from typing import List, Dict
import json

import sys
sys.path.append("..")
import rpc_client
import requests
from config import config

def register() -> str:
    result = rpc_client.call_method('createAddress')
    reg_address = {}
    reg_address['address'] = result['address']
    reg_address['privateSpendKey'] = getSpendKey(result['address'])
    # print('Wallet register: '+reg_address['address']+'=>privateSpendKey: '+reg_address['privateSpendKey'])
    return reg_address

def getSpendKey(from_address: str) -> str:
    payload = {
        'address': from_address
    }
    result = rpc_client.call_method('getSpendKeys', payload=payload)
    return result['spendSecretKey']

def send_transaction(from_address: str, to_address: str, amount: int) -> str:
    payload = {
        'addresses': [from_address],
        'transfers': [{
            "amount": amount,
            "address": to_address
        }],
        'fee': config.tx_fee,
        'anonymity': config.wallet.mixin
    }
    result = rpc_client.call_method('sendTransaction', payload=payload)
    return result['transactionHash']

def send_transaction_id(from_address: str, to_address: str, amount: int, paymentid: str) -> str:
    payload = {
        'addresses': [from_address],
        'transfers': [{
            "amount": amount,
            "address": to_address
        }],
        'fee': config.tx_fee,
        'anonymity': config.wallet.mixin,
        'paymentId': paymentid
    }
    result = rpc_client.call_method('sendTransaction', payload=payload)
    return result['transactionHash']

def send_transactionall(from_address: str, to_address) -> str:
    payload = {
        'addresses': [from_address],
        'transfers': to_address,
        'fee': config.tx_fee,
        'anonymity': config.wallet.mixin
    }
    result = rpc_client.call_method('sendTransaction', payload=payload)
    return result['transactionHash']

def get_all_balances_all() -> Dict[str, Dict]:
    walletCall = rpc_client.call_method('getAddresses')
    wallets = [] ## new array
    for address in walletCall['addresses']:
        wallet = rpc_client.call_method('getBalance', {'address': address})
        wallets.append({'address':address,'unlocked':wallet['availableBalance'],'locked':wallet['lockedAmount']})
    return wallets

def get_some_balances(wallet_addresses: List[str]) -> Dict[str, Dict]:
    wallets = [] ## new array
    for address in wallet_addresses:
        wallet = rpc_client.call_method('getBalance', {'address': address})
        wallets.append({'address':address,'unlocked':wallet['availableBalance'],'locked':wallet['lockedAmount']})
    return wallets

def get_balance_address(address: str) -> Dict[str, Dict]:
    result = rpc_client.call_method('getBalance', {'address': address})
    return result

def wallet_optimize_single(subaddress: str, threshold: int) -> int:
    payload = {
        "threshold": threshold,
        "anonymity": config.wallet.mixin,
        "addresses": [
            subaddress
        ],
        "destinationAddress": subaddress
    }
    print('Optimizing wallet: '+subaddress)
    i=0
    while True:
        resp = requests.post(f'http://{config.wallet.host}:{config.wallet.port}/json_rpc', json=payload)
        try:
            resp.raise_for_status()
            json_resp = resp.json()
            if 'transactionHash' in json_resp:
                i=i+1
            if 'error' in json_resp:
                break
        except requests.exceptions.HTTPError as e:
            print("Fusion Error: " + str(e))
            break
    return i

