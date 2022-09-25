import base64
import functools
import json
import os
import os.path
import random
import sys
import time
import traceback
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict

import aiohttp
import aiomysql
import asyncio
import disnake
import numpy as np
import qrcode
from aiomysql.cursors import DictCursor
from cachetools import TTLCache
from disnake.app_commands import Option
from disnake.enums import OptionType
from disnake.ext import commands, tasks
from eth_account import Account
from eth_utils import is_hex_address  # Check hex only
from ethtoken.abi import EIP20_ABI
from httpx import AsyncClient, Timeout, Limits
from pywallet import wallet as ethwallet
from solana.keypair import Keypair
from solana.publickey import PublicKey
# For Solana
from solana.rpc.async_api import AsyncClient as Sol_AsyncClient
from solana.system_program import TransferParams, transfer
from solana.transaction import Transaction
# Stellar
from stellar_sdk import (
    AiohttpClient,
    Asset,
    Keypair as Stella_Keypair,
    Network,
    ServerAsync,
    TransactionBuilder,
    parse_transaction_envelope_from_xdr
)
from terminaltables import AsciiTable
from tronpy import AsyncTron
from tronpy.keys import PrivateKey
from tronpy.providers.async_http import AsyncHTTPProvider
from web3 import Web3
from web3.middleware import geth_poa_middleware

from mnemonic import Mnemonic
from pytezos.crypto.key import Key as XtzKey
from pytezos import pytezos

from bip_utils import Bip39SeedGenerator, Bip44Coins, Bip44
import near_api

import xrpl
from xrpl.asyncio.account import get_latest_transaction, get_account_transactions, get_account_payment_transactions
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.asyncio.ledger import get_fee
from xrpl.models.transactions import Payment
from xrpl.asyncio.transaction import safe_sign_transaction, send_reliable_submission
from xrpl.asyncio.ledger import get_latest_validated_ledger_sequence
from xrpl.asyncio.account import get_next_valid_seq_number

from pyzil.crypto import zilkey
from pyzil.zilliqa import chain as zil_chain
from pyzil.zilliqa.units import Zil, Qa
from pyzil.account import Account as Zil_Account
from pyzil.contract import Contract as zil_contract

from thor_requests.connect import Connect as thor_connect
from thor_requests.wallet import Wallet as thor_wallet
from thor_requests.contract import Contract as thor_contract

import cn_addressvalidation
import redis_utils
import store
from Bot import num_format_coin, logchanbot, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_ARROW_RIGHTHOOK, SERVER_BOT, \
    RowButtonRowCloseAnyMessage, text_to_num, truncate, seconds_str, encrypt_string, decrypt_string, \
    EMOJI_HOURGLASS_NOT_DONE, alert_if_userlock, MSG_LOCKED_ACCOUNT, EMOJI_MONEYFACE, EMOJI_INFORMATION
from config import config
from cogs.utils import MenuPage
from cogs.utils import Utils

Account.enable_unaudited_hdwallet_features()


async def near_get_status(url: str, timeout: int=16):
    try:
        data = {"jsonrpc": "2.0", "id": "1", "method": "status", "params": []}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers={'Content-Type': 'application/json'}, timeout=timeout) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if decoded_data is not None:
                        return decoded_data
    except asyncio.TimeoutError:
        print('TIMEOUT: near_get_status {} for {}s'.format(url, timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def near_check_balance(url: str, account_id: str, timeout: int=32):
    try:
        data = {
            "method": "query",
            "params": {"request_type": "view_account", "finality": "final", "account_id": account_id},
            "id":1,
            "jsonrpc":"2.0"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers={'Content-Type': 'application/json'}, timeout=timeout) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if decoded_data is not None and 'result' in decoded_data:
                        return decoded_data['result']
    except asyncio.TimeoutError:
        print('TIMEOUT: near_check_balance {} for {}s'.format(url, timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def near_check_balance_token(url: str, contract_id: str, account_id: str, timeout: int=32):
    try:
        decode_account = '{"account_id":"'+account_id+'"}'
        data = '{"method":"query","params":{"request_type": "call_function", "account_id": "'+contract_id+'","method_name": "ft_balance_of", "args_base64": "'+str(base64.b64encode(bytes(decode_account, encoding='utf-8')).decode()).replace("\n", "")+'", "finality": "final"},"id":1,"jsonrpc":"2.0"}'
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=json.loads(data), headers={'Content-Type': 'application/json'}, timeout=timeout) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if decoded_data is not None and 'result' in decoded_data:
                        ascii_result = decoded_data['result']['result']
                        if len(ascii_result) > 0:
                            result = "".join([chr(c) for c in ascii_result])
                            return int(result.replace('"', '')) # atomic
    except asyncio.TimeoutError:
        print('TIMEOUT: near_check_balance_token {} for {}s'.format(url, timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

def tezos_check_balance(url: str, key: str):
    try:
        user_address = pytezos.using(shell=url, key=key)
        return user_address.balance() # Decimal / real
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return 0.0

async def tezos_check_token_balances(url: str, address: str, timeout: int=16):
    headers = {
        'Content-Type': 'application/json'
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url + "tokens/balances?account=" + address, headers=headers, timeout=timeout) as response:
                json_resp = await response.json()
                if response.status == 200 or response.status == 201:
                    return json_resp
                else:
                    print("tezos_check_token_balances: return {}".format(response.status))
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

def tezos_check_token_balance(url: str, token_contract: str, address, coin_decimal: int, token_id: int = 0):
    try:
        token = pytezos.using(shell=url).contract(token_contract)
        addresses = []
        for each_address in address:
            addresses.append({'owner': each_address, 'token_id': token_id})
        token_balance = token.balance_of(requests=addresses, callback=None).view()
        if token_balance:
            result_balance = {}
            for each in token_balance:
                result_balance[each['request']['owner']] = int(each['balance'])
            return result_balance # dict of address => balance in float
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return {}

async def tezos_check_reveal(url: str, address: str, timeout: int=32):
    headers = {
        'Content-Type': 'application/json'
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url + "accounts/" + address, headers=headers, timeout=timeout) as response:
                json_resp = await response.json()
                if response.status == 200 or response.status == 201:
                    if json_resp['type'] == "user" and 'revealed' in json_resp and json_resp['revealed'] is True:
                        return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

def tezos_reveal_address(url: str, key: str):
    try:
        user_address = pytezos.using(shell=url, key=key)
        tx = user_address.reveal().autofill().sign().inject()
        return tx
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def tezos_get_head(url: str, timeout: int=32):
    headers = {
        'Content-Type': 'application/json'
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url + "head/", headers=headers, timeout=timeout) as response:
                json_resp = await response.json()
                if response.status == 200 or response.status == 201:
                    if 'synced' in json_resp and json_resp['synced'] is True:
                        return json_resp
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def tezos_get_tx(url: str, tx_hash: str, timeout: int=8):
    headers = {
        'Content-Type': 'application/json'
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url + "operations/transactions/" + tx_hash, headers=headers, timeout=timeout) as response:
                json_resp = await response.json()
                if response.status == 200 or response.status == 201:
                    if len(json_resp) == 1 and "status" in json_resp[0] and "level" in json_resp[0]:
                        return json_resp[0]
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def xrp_get_status(url: str, timeout: int=16):
    try:
        data = {"method":"ledger","params":[{"ledger_index":"validated","full": False,"accounts": False,"transactions": False,"expand": False,"owner_funds": False}]}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers={'Content-Type': 'application/json'}, timeout=timeout) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if decoded_data is not None:
                        return decoded_data
    except asyncio.TimeoutError:
        print('TIMEOUT: xrp_get_status {} for {}s'.format(url, timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def xrp_get_latest_transactions(url: str, address: str):
    async_client = AsyncJsonRpcClient(url)
    try:
        list_tx = await get_account_payment_transactions(address, async_client)
        return list_tx
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return []

async def xrp_get_account_info(url: str, address: str, timeout=32):
    try:
        data = {"method": "account_info", "params": [{"account": address}]}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers={'Content-Type': 'application/json'}, timeout=timeout) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if decoded_data is not None:
                        return decoded_data['result']['account_data']['Balance']
    except asyncio.TimeoutError:
        print('TIMEOUT: xrp_get_account_info {} for {}s'.format(url, timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def xrp_get_account_lines(url: str, address: str, timeout=32):
    try:
        data = {"method": "account_lines", "params": [{"account": address}]}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers={'Content-Type': 'application/json'}, timeout=timeout) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if decoded_data is not None:
                        return decoded_data['result']['lines']
    except asyncio.TimeoutError:
        print('TIMEOUT: xrp_get_account_info {} for {}s'.format(url, timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def zil_get_status(url: str, timeout=32):
    try:
        data = {"id": "1", "jsonrpc": "2.0", "method": "GetBlockchainInfo", "params": [""]}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers={'Content-Type': 'application/json'}, timeout=timeout) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if decoded_data is not None:
                        return decoded_data
    except asyncio.TimeoutError:
        print('TIMEOUT: zil_get_status {} for {}s'.format(url, timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

def zil_check_balance(key: str):
    # No node needed
    try:
        zil_chain.set_active_chain(zil_chain.MainNet)
        account = Zil_Account(private_key=key)
        balance = account.get_balance() # real already
        return balance
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return 0.0

async def zil_check_token_balance(url: str, contract: str, address_0x: str, timeout: int=32):
    try:
        data = {"id": "1", "jsonrpc": "2.0", "method": "GetSmartContractSubState", "params": [contract,"balances", [address_0x]]}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers={'Content-Type': 'application/json'}, timeout=timeout) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if (decoded_data is not None) and ('result' in decoded_data) \
                        and (decoded_data['result'] is not None) and ('balances' in decoded_data['result']) \
                        and (decoded_data['result']['balances'] is not None) \
                        and (address_0x in decoded_data['result']['balances']):
                        return decoded_data['result']['balances'][address_0x] # atomic
    except asyncio.TimeoutError:
        print('TIMEOUT: zil_check_token_balance {} for {}s'.format(url, timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return 0

async def zil_get_tx(url: str, tx_hash: str, timeout: int=16):
    headers = {
        'Content-Type': 'application/json'
    }
    data = {"id": "1", "jsonrpc": "2.0", "method": "GetTransaction", "params": [tx_hash]}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers, timeout=timeout) as response:
                json_resp = await response.json()
                if json_resp['result']['receipt']['success'] == True:
                    return json_resp
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

def vet_get_balance(url: str, address: str):
    try:
        connector = thor_connect(url)
        # Account
        balance = connector.get_account(address)
        if 'balance' in balance and 'energy' in balance:
            return {'VET': int(balance['balance'], 16), 'VTHO': int(balance['energy'], 16)} # return atomic
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

def vet_get_token_balance(url: str, contract_addr: str, address: str):
    try:
        _contract = thor_contract.fromFile("./VTHO.json")
        connector = thor_connect(url)
        # Emulate the "balanceOf()" function
        res = connector.call(
            caller=address, # fill in your caller address or all zero address
            contract=_contract,
            func_name="balanceOf",
            func_params=[address],
            to=contract_addr,
        )
        if res is not None and 'data' in res:
            return int(res['data'], 16) # atomic
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

def vet_move_token(url: str, token_name: str, contract: str, to_address: str, from_key: str, gas_payer_key: str, atomic_amount: int):
    try:
        connector = thor_connect(url)
        _sender = thor_wallet.fromPrivateKey(bytes.fromhex(from_key))
        _gas_payer = thor_wallet.fromPrivateKey(bytes.fromhex(gas_payer_key))
        transaction = None
        if token_name == "VET":
            transaction = connector.transfer_vet(
                _sender,
                to=to_address,
                value=atomic_amount,
                gas_payer=_gas_payer
            )
        elif token_name == "VTHO":
            transaction = connector.transfer_vtho(
                _sender, 
                to=to_address,
                vtho_in_wei=atomic_amount,
                gas_payer=_gas_payer
            )
        else:
            transaction = connector.transfer_token(
                _sender, 
                to=to_address,
                token_contract_addr=contract, # smart contract
                amount_in_wei=atomic_amount,
                gas_payer=_gas_payer
            )
        if transaction is not None and 'id' in transaction:
            return transaction['id'] # transaction ID or hash
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def vet_get_status(url: str, timeout=32):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url + "blocks/best", headers={'Content-Type': 'application/json'}, timeout=timeout) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if decoded_data is not None:
                        return decoded_data
    except asyncio.TimeoutError:
        print('TIMEOUT: vet_get_status {} for {}s'.format(url, timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def vet_get_tx(url: str, tx_hash: str, timeout: int=16):
    headers = {
        'Content-Type': 'application/json'
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url + "transactions/" + tx_hash + "/receipt", headers=headers, timeout=timeout) as response:
                json_resp = await response.json()
                if json_resp and 'reverted' in json_resp:
                    return json_resp
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def vite_get_height(url: str):
    try:
        data = {"jsonrpc": "2.0", "id": 1, "method": "ledger_getSnapshotChainHeight", "params": []}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, timeout=32) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    decoded_data = json.loads(res_data)
                    json_resp = decoded_data
                    return int(json_resp['result'])
                    # > {'jsonrpc': '2.0', 'id': 1, 'result': '22959761'}
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def vite_ledger_getAccountBlocksByAddress(url: str, address: str, last: int=50):
    try:
        data = {"jsonrpc": "2.0", "id": 1, "method": "ledger_getAccountBlocksByAddress", "params": [address, 0, last]}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, timeout=32) as response:
                res_data = await response.read()
                res_data = res_data.decode('utf-8')
                json_resp = json.loads(res_data)
                return json_resp['result']
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

async def vite_ledger_getAccountBlockByHash(url: str, tx_hash: str):
    try:
        data = {"jsonrpc": "2.0", "id": 1, "method": "ledger_getAccountBlockByHash", "params": [tx_hash]}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, timeout=32) as response:
                res_data = await response.read()
                res_data = res_data.decode('utf-8')
                json_resp = json.loads(res_data)
                return json_resp['result']
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def vite_send_tx(url: str, from_address: str, to_address: str, amount: str, data, tokenId: str, priv):
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tx_sendTxWithPrivateKey",
            "params": [{
                "selfAddr": from_address,
                "toAddr": to_address,
                "tokenTypeId": tokenId,
                "privateKey": priv,
                "amount": amount,
                "data": data,
                "blockType": 2
            }]
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=32) as response:
                res_data = await response.read()
                res_data = res_data.decode('utf-8')
                json_resp = json.loads(res_data)
                return json_resp['result']
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None


class RPCException(Exception):
    def __init__(self, message):
        super(RPCException, self).__init__(message)


class Faucet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # DB
        self.pool = None

    async def openConnection(self):
        try:
            if self.pool is None:
                self.pool = await aiomysql.create_pool(host=config.mysql.host, port=3306, minsize=2, maxsize=4,
                                                       user=config.mysql.user, password=config.mysql.password,
                                                       db=config.mysql.db, cursorclass=DictCursor, autocommit=True)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def get_faucet_coin_list(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT `reward_for`, `coin_name`, `reward_amount`
                              FROM `coin_bot_reward_setting` 
                              WHERE `enable`=1 
                              ORDER BY `coin_name` """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        return result
        except Exception:
            await logchanbot("wallet get_faucet_coin_list " + str(traceback.format_exc()))
        return []

    async def update_faucet_user(self, user_id: str, coin_name: str, user_server: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `coin_user_reward_setting` (`user_id`, `coin_name`, `user_server`)
                              VALUES (%s, %s, %s) ON DUPLICATE KEY 
                              UPDATE 
                              `coin_name`=VALUES(`coin_name`)
                              """
                    await cur.execute(sql, (user_id, coin_name.upper(), user_server.upper(),))
                    await conn.commit()
                    return True
        except Exception:
            await logchanbot("wallet update_faucet_user " + str(traceback.format_exc()))
        return False

    async def get_user_faucet_coin(self, user_id: str, user_server: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """SELECT * FROM `coin_user_reward_setting` 
                             WHERE `user_id`=%s AND `user_server`=%s LIMIT 1 
                          """
                    await cur.execute(sql, (user_id, user_server.upper()))
                    result = await cur.fetchone()
                    if result: return result
        except Exception:
            await logchanbot("wallet get_user_faucet_coin " + str(traceback.format_exc()))
        return None

    async def insert_reward(self, user_id: str, reward_for: str, reward_amount: float, coin_name: str, reward_time: int,
                            user_server: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `coin_user_reward_list` (`user_id`, `reward_for`, `reward_amount`, `coin_name`, `reward_time`, `user_server`)
                              VALUES (%s, %s, %s, %s, %s, %s)
                              """
                    await cur.execute(sql, (
                    user_id, reward_for, reward_amount, coin_name.upper(), reward_time, user_server.upper(),))
                    await conn.commit()
                    return True
        except Exception:
            await logchanbot("wallet insert_reward " + str(traceback.format_exc()))
        return False


class WalletAPI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        redis_utils.openRedis()
        # DB
        self.pool = None

    async def get_coin_balance(self, coin: str):
        balance = 0.0
        coin_name = coin.upper()
        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        display_name = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
        contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
        if type_coin == "ERC-20":
            main_balance = await store.http_wallet_getbalance(self.bot.erc_node_list[net_name], config.eth.MainAddress, contract, 16)
            balance = float(main_balance / 10 ** coin_decimal)
        elif type_coin in ["TRC-20", "TRC-10"]:
            main_balance = await store.trx_wallet_getbalance(config.trc.MainAddress, coin_name, coin_decimal, type_coin,
                                                             contract)
            if main_balance:
                # already divided decimal
                balance = main_balance
        elif type_coin == "TRTL-API":
            key = getattr(getattr(self.bot.coin_list, coin_name), "header")
            method = "/balance"
            headers = {
                'X-API-KEY': key,
                'Content-Type': 'application/json'
            }
            url = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url + method, headers=headers, timeout=32) as response:
                        json_resp = await response.json()
                        if response.status == 200 or response.status == 201:
                            balance = float(Decimal(json_resp['unlocked']) / Decimal(10 ** coin_decimal))
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif type_coin == "TRTL-SERVICE":
            url = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
            json_data = {"jsonrpc": "2.0", "id": 1, "password": "passw0rd", "method": "getBalance", "params": {}}
            headers = {
                'Content-Type': 'application/json'
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=json_data, headers=headers, timeout=32) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            decoded_data = json.loads(res_data)
                            json_resp = decoded_data
                            balance = float(
                                Decimal(json_resp['result']['availableBalance']) / Decimal(10 ** coin_decimal))
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif type_coin == "XMR":
            url = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
            json_data = {"jsonrpc": "2.0", "id": "0", "method": "get_balance",
                         "params": {"account_index": 0, "address_indices": []}}
            headers = {
                'Content-Type': 'application/json'
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=json_data, headers=headers, timeout=32) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            decoded_data = json.loads(res_data)
                            json_resp = decoded_data
                            balance = float(Decimal(json_resp['result']['balance']) / Decimal(10 ** coin_decimal))
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif type_coin == "BTC":
            url = getattr(getattr(self.bot.coin_list, coin_name), "daemon_address")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, data='{"jsonrpc": "1.0", "id":"' + str(
                            uuid.uuid4()) + '", "method": "getbalance", "params": [] }', timeout=32) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            decoded_data = json.loads(res_data)
                            json_resp = decoded_data
                            balance = float(Decimal(json_resp['result']))
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif type_coin == "CHIA":
            headers = {
                'Content-Type': 'application/json'
            }
            json_data = {
                "wallet_id": 1
            }
            try:
                url = getattr(getattr(self.bot.coin_list, coin_name), "rpchost") + '/' + "get_wallet_balance"
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=json_data, headers=headers, timeout=32) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            decoded_data = json.loads(res_data)['wallet_balance']
                            balance = float(Decimal(decoded_data['spendable_balance']) / Decimal(10 ** coin_decimal))
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif type_coin == "NANO":
            url = getattr(getattr(self.bot.coin_list, coin_name), "rpchost")
            main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
            headers = {
                'Content-Type': 'application/json'
            }
            json_data = {
                "action": "account_balance",
                "account": main_address
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=json_data, timeout=32) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            decoded_data = json.loads(res_data)
                            json_resp = decoded_data
                            balance = float(Decimal(json_resp['balance']) / Decimal(10 ** coin_decimal))
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif type_coin == "SOL":
            async def fetch_wallet_balance(url: str, address: str):
                # url: is endpoint
                try:
                    client = Sol_AsyncClient(url)
                    balance = await client.get_balance(PublicKey(address))
                    if 'result' in balance:
                        await client.close()
                        return balance['result']
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                return None

            try:
                get_balance = await fetch_wallet_balance(self.bot.erc_node_list['SOL'], config.sol.MainAddress)
                if 'context' in get_balance and 'value' in get_balance:
                    balance = float(get_balance['value'] / 10 ** coin_decimal)
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif type_coin == "XLM":
            balance = 0.0
            url = getattr(getattr(self.bot.coin_list, coin_name), "http_address")
            issuer = getattr(getattr(self.bot.coin_list, coin_name), "contract")
            asset_code = getattr(getattr(self.bot.coin_list, coin_name), "header")
            main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
            try:
                async with ServerAsync(
                        horizon_url=url, client=AiohttpClient()
                ) as server:
                    account = await server.accounts().account_id(main_address).call()
                    if 'balances' in account and len(account['balances']) > 0:
                        for each_balance in account['balances']:
                            if coin_name == "XLM" and each_balance['asset_type'] == "native":
                                balance = float(each_balance['balance'])
                                break
                            elif 'asset_code' in each_balance and 'asset_issuer' in each_balance and \
                                each_balance['asset_code'] == asset_code and issuer == each_balance['asset_issuer']:
                                balance = float(each_balance['balance'])
                                break
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif type_coin == "XTZ":
            balance = 0.0
            rpchost = getattr(getattr(self.bot.coin_list, "XTZ"), "rpchost")
            main_address = getattr(getattr(self.bot.coin_list, "XTZ"), "MainAddress")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            key = decrypt_string(getattr(getattr(self.bot.coin_list, "XTZ"), "walletkey"))
            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
            if coin_name == "XTZ":
                check_balance = functools.partial(tezos_check_balance, self.bot.erc_node_list['XTZ'], key)
                balance = await self.bot.loop.run_in_executor(None, check_balance)
                if balance:
                    balance = float(balance)
            else:
                token_id = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
                get_token_balances = functools.partial(tezos_check_token_balance, self.bot.erc_node_list['XTZ'], contract, [main_address], coin_decimal, int(token_id))
                bot_run_get_token_balances = await self.bot.loop.run_in_executor(None, get_token_balances)
                if bot_run_get_token_balances is not None:
                    balance = bot_run_get_token_balances[main_address] / 10 ** coin_decimal
        elif type_coin == "HNT":
            try:
                main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                wallet_host = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
                headers = {
                    'Content-Type': 'application/json'
                }
                json_data = {
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "account_get",
                    "params": {
                        "address": main_address
                    }
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(wallet_host, headers=headers, json=json_data, timeout=32) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            decoded_data = json.loads(res_data)
                            json_resp = decoded_data
                            if 'result' in json_resp:
                                balance = json_resp['result']['balance'] / 10 ** coin_decimal
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif type_coin == "NEAR":
            main_address = getattr(getattr(self.bot.coin_list, "NEAR"), "MainAddress")
            token_contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            if coin_name == "NEAR":
                get_balance = await near_check_balance(self.bot.erc_node_list['NEAR'], main_address, 32)
                balance = int(get_balance['amount']) / 10 ** coin_decimal
            else:
                get_balance = await near_check_balance_token(self.bot.erc_node_list['NEAR'], token_contract, main_address, 32)
                balance = get_balance / 10 ** coin_decimal
        elif type_coin == "XRP":
            main_address = getattr(getattr(self.bot.coin_list, "XRP"), "MainAddress")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            if coin_name == "XRP":
                balance = await xrp_get_account_info(self.bot.erc_node_list['XRP'], main_address)
                balance = int(balance) / 10 ** coin_decimal
            else:
                balance = await xrp_get_account_lines(self.bot.erc_node_list['XRP'], main_address)
                if len(balance) > 0:
                    for each in balance:
                        if each['currency'] + "XRP" == coin_name:
                            balance = float(each['balance']) / 10 ** coin_decimal
                            break
        elif type_coin == "VET":
            main_address = getattr(getattr(self.bot.coin_list, "XRP"), "MainAddress")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
            if coin_name == "VET":
                check_balance = functools.partial(vet_get_balance, self.bot.erc_node_list['VET'], main_address)
                balance = await self.bot.loop.run_in_executor(None, check_balance)
                return balance['VET'] / 10 ** coin_decimal
            elif coin_name == "VTHO":
                check_balance = functools.partial(vet_get_balance, self.bot.erc_node_list['VET'], main_address)
                balance = await self.bot.loop.run_in_executor(None, check_balance)
                return balance['VTHO'] / 10 ** coin_decimal
            else:
                get_token_balance = functools.partial(vet_get_token_balance, self.bot.erc_node_list['VET'], contract, main_address)
                balance = await self.bot.loop.run_in_executor(None, get_token_balance)
                return balance / 10 ** coin_decimal
        return balance

    async def user_balance(self, user_id: str, coin: str, address: str, coin_family: str, top_block: int,
                           confirmed_depth: int = 0, user_server: str = 'DISCORD'):
        # address: TRTL/BCN/XMR = paymentId
        token_name = coin.upper()
        user_server = user_server.upper()

        key = user_id + "_" + coin + "_" + user_server
        try:
            if key in self.bot.user_balance_cache:
                return self.bot.user_balance_cache[key]
        except Exception:
            pass
        if top_block is None:
            # If we can not get top block, confirm after 20mn. This is second not number of block
            nos_block = 20 * 60
        else:
            nos_block = top_block - confirmed_depth
        confirmed_inserted = 30  # 30s for nano
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # moving tip + / -
                    sql = """
                            SELECT 
                            (SELECT IFNULL((SELECT `balance`  
                            FROM `user_balance_mv_data` 
                            WHERE `user_id`=%s AND `token_name`=%s AND `user_server`=%s LIMIT 1), 0))

                            - (SELECT IFNULL((SELECT SUM(`real_amount`)  
                            FROM `discord_airdrop_tmp` 
                            WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`real_amount`)  
                            FROM `discord_mathtip_tmp` 
                            WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`real_amount`)  
                            FROM `discord_triviatip_tmp` 
                            WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`amount_sell`)  
                            FROM `open_order` 
                            WHERE `coin_sell`=%s AND `userid_sell`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`amount`)  
                            FROM `guild_raffle_entries` 
                            WHERE `coin_name`=%s AND `user_id`=%s AND `user_server`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`init_amount`)  
                            FROM `discord_partydrop_tmp` 
                            WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`joined_amount`)  
                            FROM `discord_partydrop_join` 
                            WHERE `attendant_id`=%s AND `token_name`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`real_amount`)  
                            FROM `discord_quickdrop` 
                            WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))

                            - (SELECT IFNULL((SELECT SUM(`real_amount`)  
                            FROM `discord_talkdrop_tmp` 
                            WHERE `from_userid`=%s AND `token_name`=%s AND `status`=%s), 0))
                          """
                    query_param = [user_id, token_name, user_server,
                                   user_id, token_name, "ONGOING",
                                   user_id, token_name, "ONGOING",
                                   user_id, token_name, "ONGOING",
                                   token_name, user_id, "OPEN",
                                   token_name, user_id, user_server, "REGISTERED",
                                   user_id, token_name, "ONGOING",
                                   user_id, token_name, "ONGOING",
                                   user_id, token_name, "ONGOING",
                                   user_id, token_name, "ONGOING"]
                    if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        sql += """
                            - (SELECT IFNULL((SELECT SUM(amount+withdraw_fee)  
                            FROM `cn_external_tx` 
                            WHERE `user_id`=%s AND `coin_name`=%s AND `user_server`=%s AND `crediting`=%s), 0))
                            """
                        query_param += [user_id, token_name, user_server, "YES"]
                        if top_block is None:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount) FROM `cn_get_transfers` WHERE `payment_id`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `time_insert`< %s AND `user_server`=%s), 0))
                            """
                            query_param += [address, token_name, int(time.time()) - nos_block, user_server]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount) FROM `cn_get_transfers` 
                            WHERE `payment_id`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `height`< %s AND `user_server`=%s), 0))
                            """
                            query_param += [address, token_name, nos_block, user_server]
                    elif coin_family == "BTC":
                        sql += """
                            - (SELECT IFNULL((SELECT SUM(amount+withdraw_fee)  
                            FROM `doge_external_tx` 
                            WHERE `user_id`=%s AND `coin_name`=%s AND `user_server`=%s AND `crediting`=%s), 0))
                            """
                        query_param += [user_id, token_name, user_server, "YES"]
                        if token_name not in ["PGO"]:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(`amount`) 
                            FROM `doge_get_transfers` 
                            WHERE `address`=%s AND `coin_name`=%s 
                            AND (`category` = %s or `category` = %s) 
                            AND `confirmations`>=%s AND `amount`>0), 0))
                            """
                            query_param += [address, token_name, 'receive', 'generate', confirmed_depth]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                            FROM `doge_get_transfers` 
                            WHERE `address`=%s AND `coin_name`=%s AND `category` = %s 
                            AND `confirmations`>=%s AND `amount`>0), 0))
                            """
                            query_param += [address, token_name, 'receive', confirmed_depth]
                    elif coin_family == "NEO":
                        sql += """
                            - (SELECT IFNULL((SELECT SUM(real_amount+real_external_fee)  
                            FROM `neo_external_tx` 
                            WHERE `user_id`=%s AND `coin_name`=%s 
                            AND `user_server`=%s AND `crediting`=%s), 0))
                               """
                        query_param += [user_id, token_name, user_server, "YES"]
                        if top_block is None:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(`amount`)  
                            FROM `neo_get_transfers` 
                            WHERE `address`=%s 
                            AND `coin_name`=%s AND `category` = %s 
                            AND `time_insert`<=%s AND `amount`>0), 0))
                                   """
                            query_param += [address, token_name, 'received', int(time.time()) - nos_block]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(`amount`)  
                            FROM `neo_get_transfers` 
                            WHERE `address`=%s 
                            AND `coin_name`=%s AND `category` = %s 
                            AND `confirmations`<=%s AND `amount`>0), 0))
                                   """
                            query_param += [address, token_name, 'received', nos_block]
                    elif coin_family == "NEAR":
                        sql += """
                            - (SELECT IFNULL((SELECT SUM(real_amount+real_external_fee)  
                            FROM `near_external_tx` 
                            WHERE `user_id`=%s AND `token_name`=%s 
                            AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        if top_block is None:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount-real_deposit_fee) 
                            FROM `near_move_deposit` 
                            WHERE `balance_wallet_address`=%s 
                            AND `user_id`=%s AND `token_name`=%s 
                            AND `time_insert`<=%s AND `amount`>0), 0))
                            """
                            query_param += [address, user_id, token_name, int(time.time()) - nos_block]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount-real_deposit_fee)  
                            FROM `near_move_deposit` 
                            WHERE `balance_wallet_address`=%s 
                            AND `user_id`=%s AND `token_name`=%s 
                            AND `confirmations`<=%s AND `amount`>0), 0))
                            """
                            query_param += [address, user_id, token_name, nos_block]
                    elif coin_family == "NANO":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(`amount`)  
                        FROM `nano_external_tx` 
                        WHERE `user_id`=%s AND `coin_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]

                        sql += """
                        + (SELECT IFNULL((SELECT SUM(amount)  
                        FROM `nano_move_deposit` WHERE `user_id`=%s 
                        AND `coin_name`=%s 
                        AND `amount`>0 AND `time_insert`< %s AND `user_server`=%s), 0))
                        """
                        query_param += [user_id, token_name, int(time.time()) - confirmed_inserted, user_server]
                    elif coin_family == "CHIA":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(amount+withdraw_fee)  
                        FROM `xch_external_tx` 
                        WHERE `user_id`=%s AND `coin_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]

                        if top_block is None:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(`amount`)  
                            FROM `xch_get_transfers` 
                            WHERE `address`=%s AND `coin_name`=%s AND `amount`>0 
                            AND `time_insert`< %s), 0))
                            """
                            query_param += [address, token_name, nos_block]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(`amount`)  
                            FROM `xch_get_transfers` 
                            WHERE `address`=%s AND `coin_name`=%s AND `amount`>0 AND `height`<%s), 0))
                            """
                            query_param += [address, token_name, nos_block]
                    elif coin_family == "ERC-20":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(real_amount+real_external_fee)  
                        FROM `erc20_external_tx` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        
                        sql += """
                        + (SELECT IFNULL((SELECT SUM(real_amount-real_deposit_fee)  
                        FROM `erc20_move_deposit` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `confirmed_depth`> %s AND `user_server`=%s AND `status`=%s), 0))
                        """
                        query_param += [user_id, token_name, confirmed_depth, user_server, "CONFIRMED"]
                    elif coin_family == "XTZ":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(real_amount+real_external_fee)  
                        FROM `tezos_external_tx` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        
                        sql += """
                        + (SELECT IFNULL((SELECT SUM(real_amount-real_deposit_fee)  
                        FROM `tezos_move_deposit` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `confirmed_depth`> %s AND `user_server`=%s 
                        AND `status`=%s), 0))
                        """
                        query_param += [user_id, token_name, 0, user_server, "CONFIRMED"]
                    elif coin_family == "ZIL":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(real_amount+real_external_fee)  
                        FROM `zil_external_tx` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        
                        sql += """
                        + (SELECT IFNULL((SELECT SUM(real_amount-real_deposit_fee)  
                        FROM `zil_move_deposit` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `confirmed_depth`> %s AND `user_server`=%s AND `status`=%s), 0))
                        """
                        query_param += [user_id, token_name, 0, user_server, "CONFIRMED"]
                    elif coin_family == "VET":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(real_amount+real_external_fee)  
                        FROM `vet_external_tx` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        
                        sql += """
                        + (SELECT IFNULL((SELECT SUM(real_amount-real_deposit_fee)  
                        FROM `vet_move_deposit` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `confirmed_depth`> %s AND `user_server`=%s AND `status`=%s), 0))
                        """
                        query_param += [user_id, token_name, 0, user_server, "CONFIRMED"]
                    elif coin_family == "VITE":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(amount+withdraw_fee)  
                        FROM `vite_external_tx` 
                        WHERE `user_id`=%s AND `coin_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        
                        address_memo = address.split()
                        if top_block is None:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                                      FROM `vite_get_transfers` 
                                      WHERE `address`=%s AND `memo`=%s 
                                      AND `coin_name`=%s AND `amount`>0 
                                      AND `time_insert`< %s AND `user_server`=%s), 0))
                            """
                            query_param += [address_memo[0], address_memo[2], token_name, nos_block, user_server]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                            FROM `vite_get_transfers` 
                            WHERE `address`=%s AND `memo`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `height`<%s AND `user_server`=%s), 0))
                            """
                            query_param += [address_memo[0], address_memo[2], token_name, nos_block, user_server]
                    elif coin_family == "TRC-20":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(real_amount+real_external_fee)  
                        FROM `trc20_external_tx` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s AND `sucess`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES", 1]
                        
                        sql += """
                        + (SELECT IFNULL((SELECT SUM(real_amount-real_deposit_fee)  
                        FROM `trc20_move_deposit` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `confirmed_depth`> %s AND `user_server`=%s AND `status`=%s), 0))
                        """
                        query_param += [user_id, token_name, confirmed_depth, user_server, "CONFIRMED"]
                    elif coin_family == "HNT":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(amount+withdraw_fee)  
                        FROM `hnt_external_tx` 
                        WHERE `user_id`=%s AND `coin_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        
                        address_memo = address.split()
                        if top_block is None:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                            FROM `hnt_get_transfers` 
                            WHERE `address`=%s AND `memo`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `time_insert`< %s AND `user_server`=%s), 0))
                            """
                            query_param += [address_memo[0], address_memo[2], token_name, nos_block, user_server]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                            FROM `hnt_get_transfers` 
                            WHERE `address`=%s AND `memo`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `height`<%s AND `user_server`=%s), 0))
                            """
                            query_param += [address_memo[0], address_memo[2], token_name, nos_block, user_server]

                    elif coin_family == "XRP":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(amount+tx_fee)  
                        FROM `xrp_external_tx` 
                        WHERE `user_id`=%s AND `coin_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        
                        if top_block is None:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                            FROM `xrp_get_transfers` 
                            WHERE `destination_tag`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `time_insert`< %s AND `user_server`=%s), 0))
                            """
                            query_param += [address, token_name, nos_block, user_server]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                            FROM `xrp_get_transfers` 
                            WHERE `destination_tag`=%s AND `coin_name`=%s AND `amount`>0 AND `height`<%s AND `user_server`=%s), 0))
                            """
                            query_param += [address, token_name, nos_block, user_server]
                    elif coin_family == "XLM":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(amount+withdraw_fee)  
                        FROM `xlm_external_tx` 
                        WHERE `user_id`=%s AND `coin_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        
                        address_memo = address.split()
                        if top_block is None:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                                      FROM `xlm_get_transfers` 
                                      WHERE `address`=%s AND `memo`=%s 
                                      AND `coin_name`=%s AND `amount`>0 
                                      AND `time_insert`< %s AND `user_server`=%s), 0))
                            """
                            query_param += [address_memo[0], address_memo[2], token_name, nos_block, user_server]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                            FROM `xlm_get_transfers` 
                            WHERE `address`=%s AND `memo`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `height`<%s AND `user_server`=%s), 0))
                            """
                            query_param += [address_memo[0], address_memo[2], token_name, nos_block, user_server]
                    elif coin_family == "ADA":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(real_amount+real_external_fee)  
                        FROM `ada_external_tx` 
                        WHERE `user_id`=%s AND `coin_name`=%s AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        if top_block is None:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount) 
                            FROM `ada_get_transfers` WHERE `output_address`=%s AND `direction`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `time_insert`< %s AND `user_server`=%s), 0))
                            """
                            query_param += [address, "incoming", token_name, nos_block, user_server]

                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount) 
                            FROM `ada_get_transfers` 
                            WHERE `output_address`=%s AND `direction`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `inserted_at_height`<%s AND `user_server`=%s), 0))
                            """
                            query_param += [address, "incoming", token_name, nos_block, user_server]
                    elif coin_family == "SOL" or coin_family == "SPL":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(real_amount+real_external_fee)  
                        FROM `sol_external_tx` 
                        WHERE `user_id`=%s AND `coin_name`=%s AND `user_server`=%s AND `crediting`=%s), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        
                        sql += """
                        + (SELECT IFNULL((SELECT SUM(real_amount-real_deposit_fee)  
                        FROM `sol_move_deposit` 
                        WHERE `user_id`=%s AND `token_name`=%s 
                        AND `confirmed_depth`> %s AND `user_server`=%s AND `status`=%s), 0))
                        """
                        query_param += [user_id, token_name, confirmed_depth, user_server, "CONFIRMED"]
                    sql += """ AS mv_balance"""
                    await cur.execute(sql, tuple(query_param))
                    result = await cur.fetchone()
                    if result:
                        mv_balance = result['mv_balance']
                    else:
                        mv_balance = 0
                balance = {}
                try:
                    balance['adjust'] = 0
                    balance['mv_balance'] = float("%.6f" % mv_balance) if mv_balance else 0
                    balance['adjust'] = float("%.6f" % balance['mv_balance'])
                except Exception:
                    print("issue user_balance coin name: {}".format(token_name))
                    traceback.print_exc(file=sys.stdout)
                # Negative check
                try:
                    if balance['adjust'] < 0:
                        msg_negative = 'Negative balance detected:\nServer:' + user_server + '\nUser: ' + user_id + '\nToken: ' + token_name + '\nBalance: ' + str(
                            balance['adjust'])
                        await logchanbot(msg_negative)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                try:
                    self.bot.user_balance_cache[key] = balance
                except Exception:
                    pass
                return balance
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet user_balance " +str(traceback.format_exc()))


    def get_block_height(self, type_coin: str, coin: str, net_name: str = None):
        redis_utils.openRedis()
        height = None
        coin_name = coin.upper()
        try:
            if type_coin in ["ERC-20", "TRC-20"]:
                height = int(redis_utils.redis_conn.get(
                    f'{config.redis.prefix + config.redis.daemon_height}{net_name}').decode())
            elif type_coin in ["XLM", "NEO", "VITE"]:
                height = int(redis_utils.redis_conn.get(
                    f'{config.redis.prefix + config.redis.daemon_height}{type_coin}').decode())
            else:
                height = int(redis_utils.redis_conn.get(
                    f'{config.redis.prefix + config.redis.daemon_height}{coin_name}').decode())
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return height

    async def openConnection(self):
        try:
            if self.pool is None:
                self.pool = await aiomysql.create_pool(host=config.mysql.host, port=3306, minsize=2, maxsize=4,
                                                       user=config.mysql.user, password=config.mysql.password,
                                                       db=config.mysql.db, cursorclass=DictCursor, autocommit=True)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def generate_qr_address(
            self,
            address: str
    ):
        # return path to image
        # address = wallet['balance_wallet_address']
        # return address if success, else None
        address_path = address.replace('{', '_').replace('}', '_').replace(':', '_').replace('"', "_").replace(',',
                                                                                                               "_").replace(
            ' ', "_")
        if not os.path.exists(config.storage.path_deposit_qr_create + address_path + ".png"):
            try:
                # do some QR code
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=2,
                )
                qr.add_data(address)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                img = img.resize((256, 256))
                img.save(config.storage.path_deposit_qr_create + address_path + ".png")
                return address
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot("wallet generate_qr_address " + str(traceback.format_exc()))
        else:
            return address
        return None

    # ERC-20, TRC-20, native is one
    # Gas Token like BNB, xDAI, MATIC, TRX will be a different address
    async def sql_register_user(self, user_id, coin: str, netname: str, type_coin: str, user_server: str,
                                chat_id: int = 0, is_discord_guild: int = 0):
        async def get_max_id_xrp():
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    try:
                        sql = """ SELECT `id`, `destination_tag` FROM `xrp_user` ORDER BY `id` DESC LIMIT 1 """
                        await cur.execute(sql,)
                        result = await cur.fetchone()
                        if result:
                            return result['destination_tag']
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    return None

        try:
            coin_name = coin.upper()
            user_server = user_server.upper()
            balance_address = None
            main_address = None

            if type_coin.upper() == "ZIL" and coin_name != netname.upper():
                user_id_erc20 = str(user_id) + "_" + type_coin.upper() + "_TOKEN"
                type_coin_user = "ZIL-TOKEN"
            elif type_coin.upper() == "ZIL" and coin_name == netname.upper():
                user_id_erc20 = str(user_id) + "_" + coin_name.upper()
                type_coin_user = coin_name
            elif type_coin.upper() == "XRP" and coin_name != netname.upper():
                user_id_erc20 = str(user_id) + "_" + type_coin.upper() + "_TOKEN"
                type_coin_user = "XRP-TOKEN"
            elif type_coin.upper() == "XRP" and coin_name == netname.upper():
                user_id_erc20 = str(user_id) + "_" + coin_name.upper()
                type_coin_user = coin_name
            elif type_coin.upper() == "NEAR" and coin_name != netname.upper():
                user_id_erc20 = str(user_id) + "_" + type_coin.upper() + "_TOKEN"
                type_coin_user = "NEAR-TOKEN"
            elif type_coin.upper() == "NEAR" and coin_name == netname.upper():
                user_id_erc20 = str(user_id) + "_" + coin_name.upper()
                type_coin_user = coin_name
            elif type_coin.upper() == "XTZ" and coin_name != netname.upper():
                user_id_erc20 = str(user_id) + "_" + type_coin.upper() + "_FA"
                type_coin_user = "XTZ-FA"
            elif type_coin.upper() == "XTZ" and coin_name == netname.upper():
                user_id_erc20 = str(user_id) + "_" + coin_name.upper()
                type_coin_user = coin_name
            elif type_coin.upper() == "ERC-20" and coin_name != netname.upper():
                user_id_erc20 = str(user_id) + "_" + type_coin.upper()
                type_coin_user = "ERC-20"
            elif type_coin.upper() == "ERC-20" and coin_name == netname.upper():
                user_id_erc20 = str(user_id) + "_" + coin_name
                type_coin_user = coin_name
            if type_coin.upper() in ["TRC-20", "TRC-10"] and coin_name != netname.upper():
                type_coin = "TRC-20"
                type_coin_user = "TRC-20"
                user_id_erc20 = str(user_id) + "_" + type_coin.upper()
            elif type_coin.upper() in ["TRC-20", "TRC-10"] and coin_name == netname.upper():
                user_id_erc20 = str(user_id) + "_" + coin_name
                type_coin_user = "TRX"

            if type_coin.upper() == "ZIL":
                account = Zil_Account.generate()
                balance_address = {'address': account.bech32_address, 'key': account.zil_key._bytes_private.hex()}
            elif type_coin.upper() == "XRP":
                get_id = await get_max_id_xrp()
                id_num = 100000000
                if get_id is not None:
                    id_num = get_id + 1
                seed = decrypt_string(getattr(getattr(self.bot.coin_list, "XRP"), "walletkey"))
                wallet = xrpl.wallet.Wallet(seed, 0)
                xaddress = xrpl.core.addresscodec.classic_address_to_xaddress(wallet.classic_address, id_num, is_test_network=False)
                balance_address = {'balance_wallet_address': xaddress, 'address': wallet.classic_address, 'destination_tag': id_num}
            elif type_coin.upper() == "ERC-20":
                # passed test XDAI, MATIC
                w = await self.create_address_eth()
                balance_address = w['address']
            elif type_coin.upper() == "XTZ":
                mnemo = Mnemonic("english")
                words = str(mnemo.generate(strength=128))
                key = XtzKey.from_mnemonic(mnemonic=words, passphrase="", email="")
                balance_address = {'address': key.public_key_hash(), 'seed': words, 'key': key.secret_key()}
            elif type_coin.upper() == "NEAR":
                mnemo = Mnemonic("english")
                words = str(mnemo.generate(strength=128))
                seed = [words]

                seed_bytes = Bip39SeedGenerator(words).Generate("")
                bip44_mst_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.NEAR_PROTOCOL)
                key_byte = bip44_mst_ctx.PrivateKey().Raw().ToHex()
                address = bip44_mst_ctx.PublicKey().ToAddress()

                sender_key_pair = near_api.signer.KeyPair(bytes.fromhex(key_byte))
                sender_signer = near_api.signer.Signer(address, sender_key_pair)
                new_addr = sender_signer.public_key.hex()
                if new_addr == address:
                    balance_address = {'address': address, 'seed': words, 'key': key_byte}
                else:
                    return None
            elif type_coin.upper() in ["TRC-20", "TRC-10"]:
                # passed test TRX, USDT
                w = await self.create_address_trx()
                balance_address = w
            elif type_coin.upper() in ["TRTL-API", "TRTL-SERVICE", "BCN"]:
                # passed test WRKZ, DEGO
                main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                get_prefix_char = getattr(getattr(self.bot.coin_list, coin_name), "get_prefix_char")
                get_prefix = getattr(getattr(self.bot.coin_list, coin_name), "get_prefix")
                get_addrlen = getattr(getattr(self.bot.coin_list, coin_name), "get_addrlen")
                balance_address = {}
                balance_address['payment_id'] = cn_addressvalidation.paymentid()
                balance_address['integrated_address'] = \
                cn_addressvalidation.cn_make_integrated(main_address, get_prefix_char, get_prefix, get_addrlen,
                                                        balance_address['payment_id'])['integrated_address']
            elif type_coin.upper() == "XMR":
                # passed test WOW
                main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                balance_address = await self.make_integrated_address_xmr(main_address, coin_name)
            elif type_coin.upper() == "NANO":
                walletkey = decrypt_string(getattr(getattr(self.bot.coin_list, coin_name), "walletkey"))
                balance_address = await self.call_nano(coin_name,
                                                       payload='{ "action": "account_create", "wallet": "' + walletkey + '" }')
            elif type_coin.upper() == "BTC":
                naming = config.redis.prefix + "_" + user_server + "_" + str(user_id)
                payload = f'"{naming}"'
                if coin_name in ["BTCZ", "VTC", "ZEC"]:
                    payload = ''
                elif coin_name in ["HNS"]:
                    payload = '"default"'
                address_call = await self.call_doge('getnewaddress', coin_name, payload=payload)
                reg_address = {}
                reg_address['address'] = address_call
                payload = f'"{address_call}"'
                key_call = await self.call_doge('dumpprivkey', coin_name, payload=payload)
                reg_address['privateKey'] = key_call
                if reg_address['address'] and reg_address['privateKey']:
                    balance_address = reg_address
            elif type_coin.upper() == "NEO":
                address_call = await self.call_neo('getnewaddress', payload=[])
                reg_address = {}
                reg_address['address'] = address_call['result']
                key_call = await self.call_neo('dumpprivkey', payload=[reg_address['address']])
                reg_address['privateKey'] = key_call['result']
                if reg_address['address'] and reg_address['privateKey']:
                    balance_address = reg_address
            elif type_coin.upper() == "CHIA":
                # passed test XFX
                payload = {'wallet_id': 1, 'new_address': True}
                try:
                    address_call = await self.call_xch('get_next_address', coin_name, payload=payload)
                    if 'success' in address_call and address_call['address']:
                        balance_address = address_call
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            elif type_coin.upper() == "HNT":
                # generate random memo
                from string import ascii_uppercase
                main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                memo = ''.join(random.choice(ascii_uppercase) for i in range(8))
                balance_address = {}
                balance_address['balance_wallet_address'] = "{} MEMO: {}".format(main_address, memo)
                balance_address['address'] = main_address
                balance_address['memo'] = memo
            elif type_coin.upper() == "XLM":
                # generate random memo
                from string import ascii_uppercase
                main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                memo = ''.join(random.choice(ascii_uppercase) for i in range(8))
                balance_address = {}
                balance_address['balance_wallet_address'] = "{} MEMO: {}".format(main_address, memo)
                balance_address['address'] = main_address
                balance_address['memo'] = memo
            elif type_coin.upper() == "ADA":
                # get address pool
                address_pools = await store.ada_get_address_pools(50)
                balance_address = {}
                if address_pools:
                    wallet_name = address_pools['wallet_name']
                    addresses = address_pools['addresses']
                    random.shuffle(addresses)
                    balance_address['balance_wallet_address'] = addresses[0]
                    balance_address['address'] = addresses[0]
                    balance_address['wallet_name'] = wallet_name
            elif type_coin.upper() == "SOL":
                balance_address = {}
                kp = Keypair.generate()
                public_key = str(kp.public_key)
                balance_address['balance_wallet_address'] = public_key
                balance_address['secret_key_hex'] = kp.secret_key.hex()
            elif type_coin.upper() == "VET":
                wallet = thor_wallet.newWallet()
                balance_address = {'balance_wallet_address': wallet.address, 'key': wallet.priv.hex(), 'json_dump': str(vars(wallet))}
            elif type_coin.upper() == "VITE":
                # generate random memo
                from string import ascii_uppercase
                main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                memo = ''.join(random.choice(ascii_uppercase) for i in range(10))
                balance_address = {}
                balance_address['balance_wallet_address'] = "{} MEMO: {}".format(main_address, memo)
                balance_address['address'] = main_address
                balance_address['memo'] = memo
                
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    try:
                        if netname and type_coin == "ERC-20":
                            sql = """ INSERT INTO `erc20_user` (`user_id`, `user_id_erc20`, `type`, `balance_wallet_address`, `address_ts`, 
                                      `seed`, `create_dump`, `private_key`, `public_key`, `xprivate_key`, `xpublic_key`, 
                                      `called_Update`, `user_server`, `chat_id`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (
                            str(user_id), user_id_erc20, type_coin_user, w['address'], int(time.time()),
                            encrypt_string(w['seed']), encrypt_string(str(w)), encrypt_string(str(w['private_key'])),
                            w['public_key'],
                            encrypt_string(str(w['xprivate_key'])), w['xpublic_key'], int(time.time()), user_server,
                            chat_id, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': w['address']}
                        elif type_coin == "ZIL":
                            sql = """ INSERT INTO `zil_user` (`user_id`, `user_id_asset`, `type`, `balance_wallet_address`, `address_ts`, 
                                      `key`, `called_Update`, `user_server`, `chat_id`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (
                            str(user_id), user_id_erc20, type_coin_user, balance_address['address'], int(time.time()),
                            encrypt_string(balance_address['key']), int(time.time()), user_server,
                            chat_id, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                        elif type_coin == "XTZ":
                            sql = """ INSERT INTO `tezos_user` (`user_id`, `user_id_fa20`, `type`, `balance_wallet_address`, `address_ts`, 
                                      `seed`, `key`, `called_Update`, `user_server`, `chat_id`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (
                            str(user_id), user_id_erc20, type_coin_user, balance_address['address'], int(time.time()),
                            encrypt_string(balance_address['seed']), encrypt_string(balance_address['key']), int(time.time()), user_server,
                            chat_id, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                        elif type_coin == "XRP":
                            sql = """ INSERT INTO `xrp_user` (`user_id`, `user_id_asset`, `type`, `main_address`, `destination_tag`, `balance_wallet_address`, `address_ts`, `user_server`, `chat_id`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (
                            str(user_id), user_id_erc20, type_coin_user, balance_address['address'], balance_address['destination_tag'], balance_address['balance_wallet_address'], int(time.time()), user_server, chat_id, is_discord_guild))
                            await conn.commit()
                            return balance_address
                        elif type_coin == "NEAR":
                            sql = """ INSERT INTO `near_user` (`user_id`, `user_id_near`, `coin_name`, `type`, `balance_wallet_address`, `address_ts`, 
                                      `privateKey`, `seed`, `called_Update`, `user_server`, `chat_id`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (
                            str(user_id), user_id_erc20, coin_name, type_coin_user, balance_address['address'], int(time.time()), 
                            encrypt_string(balance_address['key']), encrypt_string(balance_address['seed']), int(time.time()), user_server,
                            chat_id, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                        elif netname and netname in ["TRX"]:
                            sql = """ INSERT INTO `trc20_user` (`user_id`, `user_id_trc20`, `type`, `balance_wallet_address`, `hex_address`, `address_ts`, 
                                      `private_key`, `public_key`, `called_Update`, `user_server`, `chat_id`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (
                            str(user_id), user_id_erc20, type_coin_user, w['base58check_address'], w['hex_address'],
                            int(time.time()),
                            encrypt_string(str(w['private_key'])), w['public_key'], int(time.time()), user_server,
                            chat_id, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': w['base58check_address']}
                        elif type_coin.upper() in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                            sql = """ INSERT INTO cn_user_paymentid (`coin_name`, `user_id`, `user_id_coin`, `main_address`, `paymentid`, 
                                      `balance_wallet_address`, `paymentid_ts`, `user_server`, `chat_id`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (
                            coin_name, str(user_id), "{}_{}".format(user_id, coin_name), main_address,
                            balance_address['payment_id'],
                            balance_address['integrated_address'], int(time.time()), user_server, chat_id,
                            is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['integrated_address'],
                                    'paymentid': balance_address['payment_id']}
                        elif type_coin.upper() == "NANO":
                            sql = """ INSERT INTO `nano_user` (`coin_name`, `user_id`, `user_id_coin`, `balance_wallet_address`, `address_ts`, `user_server`, `chat_id`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (
                            coin_name, str(user_id), "{}_{}".format(user_id, coin_name), balance_address['account'],
                            int(time.time()), user_server, chat_id, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['account']}
                        elif type_coin.upper() == "BTC":
                            sql = """ INSERT INTO `doge_user` (`coin_name`, `user_id`, `user_id_coin`, `balance_wallet_address`, `address_ts`, `privateKey`, `user_server`, `chat_id`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (
                            coin_name, str(user_id), "{}_{}".format(user_id, coin_name), balance_address['address'],
                            int(time.time()),
                            encrypt_string(balance_address['privateKey']), user_server, chat_id, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                        elif type_coin.upper() == "NEO":
                            sql = """ INSERT INTO `neo_user` (`user_id`, `balance_wallet_address`, `address_ts`, `privateKey`, `user_server`, `chat_id`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (str(user_id), balance_address['address'], 
                                                    int(time.time()), encrypt_string(balance_address['privateKey']), 
                                                    user_server, chat_id, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                        elif type_coin.upper() == "CHIA":
                            sql = """ INSERT INTO `xch_user` (`coin_name`, `user_id`, `user_id_coin`, `balance_wallet_address`, `address_ts`, `user_server`, `chat_id`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (
                            coin_name, str(user_id), "{}_{}".format(user_id, coin_name), balance_address['address'],
                            int(time.time()), user_server, chat_id, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                        elif type_coin.upper() == "HNT":
                            sql = """ INSERT INTO `hnt_user` (`coin_name`, `user_id`, `main_address`, `balance_wallet_address`, `memo`, `address_ts`, `user_server`, `chat_id`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (
                            coin_name, str(user_id), main_address, balance_address['balance_wallet_address'], memo,
                            int(time.time()), user_server, chat_id, is_discord_guild))
                            await conn.commit()
                            return balance_address
                        elif type_coin.upper() == "XLM":
                            sql = """ INSERT INTO `xlm_user` (`coin_name`, `user_id`, `main_address`, `balance_wallet_address`, `memo`, `address_ts`, `user_server`, `chat_id`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (
                            coin_name, str(user_id), main_address, balance_address['balance_wallet_address'], memo,
                            int(time.time()), user_server, chat_id, is_discord_guild))
                            await conn.commit()
                            return balance_address
                        elif type_coin.upper() == "ADA":
                            sql = """ INSERT INTO `ada_user` (`user_id`, `wallet_name`, `balance_wallet_address`, `address_ts`, `user_server`, `chat_id`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s);
                                      UPDATE `ada_wallets` SET `used_address`=`used_address`+1 WHERE `wallet_name`=%s LIMIT 1; """
                            await cur.execute(sql, (
                            str(user_id), balance_address['wallet_name'], balance_address['address'], int(time.time()),
                            user_server, chat_id, is_discord_guild, balance_address['wallet_name']))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                        elif type_coin.upper() == "SOL":
                            sql = """ INSERT INTO `sol_user` (`user_id`, `balance_wallet_address`, `address_ts`, `secret_key_hex`, `called_Update`, `user_server`, `chat_id`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (
                            str(user_id), balance_address['balance_wallet_address'], int(time.time()),
                            encrypt_string(balance_address['secret_key_hex']), int(time.time()), user_server, chat_id,
                            is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['balance_wallet_address']}
                        elif type_coin.upper() == "VET":
                            sql = """ INSERT INTO `vet_user` (`user_id`, `balance_wallet_address`, `address_ts`, `key`, `json_dump`, `called_Update`, `user_server`, `chat_id`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (str(user_id), balance_address['balance_wallet_address'], int(time.time()), encrypt_string(balance_address['key']), encrypt_string(balance_address['json_dump']), int(time.time()), user_server, chat_id, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['balance_wallet_address']}
                        elif type_coin.upper() == "VITE":
                            sql = """ INSERT INTO `vite_user` (`coin_name`, `user_id`, `main_address`, `balance_wallet_address`, `memo`, `address_ts`, `user_server`, `chat_id`, `is_discord_guild`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (
                            coin_name, str(user_id), main_address, balance_address['balance_wallet_address'], memo,
                            int(time.time()), user_server, chat_id, is_discord_guild))
                            await conn.commit()
                            return balance_address
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def sql_get_userwallet(self, user_id, coin: str, netname: str, type_coin: str, user_server: str = 'DISCORD',
                                 chat_id: int = 0):
        # netname null or None, xDai, MATIC, TRX, BSC
        user_server = user_server.upper()
        coin_name = coin.upper()
        if type_coin.upper() == "ZIL" and coin_name != netname.upper():
            user_id_erc20 = str(user_id) + "_" + type_coin.upper() + "_TOKEN"
            type_coin_user = "ZIL-TOKEN"
        elif type_coin.upper() == "ZIL" and coin_name == netname.upper():
            user_id_erc20 = str(user_id) + "_" + coin_name.upper()
            type_coin_user = coin_name
        elif type_coin.upper() == "XRP" and coin_name != netname.upper():
            user_id_erc20 = str(user_id) + "_" + type_coin.upper() + "_TOKEN"
            type_coin_user = "XRP-TOKEN"
        elif type_coin.upper() == "XRP" and coin_name == netname.upper():
            user_id_erc20 = str(user_id) + "_" + coin_name.upper()
            type_coin_user = coin_name
        elif type_coin.upper() == "NEAR" and coin_name != netname.upper():
            user_id_erc20 = str(user_id) + "_" + type_coin.upper() + "_TOKEN"
            type_coin_user = "NEAR-TOKEN"
        elif type_coin.upper() == "NEAR" and coin_name == netname.upper():
            user_id_erc20 = str(user_id) + "_" + coin_name.upper()
            type_coin_user = coin_name
        if type_coin.upper() == "XTZ" and coin_name != netname.upper():
            user_id_erc20 = str(user_id) + "_" + type_coin.upper() + "_FA"
            type_coin_user = "XTZ-FA"
        elif type_coin.upper() == "XTZ" and coin_name == netname.upper():
            user_id_erc20 = str(user_id) + "_" + coin_name.upper()
            type_coin_user = coin_name
        elif type_coin.upper() == "ERC-20" and coin_name != netname.upper():
            user_id_erc20 = str(user_id) + "_" + type_coin.upper()
        elif type_coin.upper() == "ERC-20" and coin_name == netname.upper():
            user_id_erc20 = str(user_id) + "_" + coin_name
        if type_coin.upper() in ["TRC-20", "TRC-10"] and coin_name != netname.upper():
            type_coin = "TRC-20"
            user_id_erc20 = str(user_id) + "_" + type_coin.upper()
        elif type_coin.upper() in ["TRC-20", "TRC-10"] and coin_name == netname.upper():
            user_id_erc20 = str(user_id) + "_" + coin_name
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if netname and type_coin == "ERC-20":
                        sql = """ SELECT * FROM `erc20_user` WHERE `user_id`=%s 
                                  AND `user_id_erc20`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), user_id_erc20, user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif netname and netname in ["TRX"]:
                        sql = """ SELECT * FROM `trc20_user` WHERE `user_id`=%s 
                                  AND `user_id_trc20`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), user_id_erc20, user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() == "ZIL":
                        sql = """ SELECT * FROM `zil_user` WHERE `user_id`=%s 
                                  AND `user_id_asset`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), user_id_erc20, user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() == "XTZ":
                        sql = """ SELECT * FROM `tezos_user` WHERE `user_id`=%s 
                                  AND `user_id_fa20`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), user_id_erc20, user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() == "XRP":
                        sql = """ SELECT * FROM `xrp_user` WHERE `user_id`=%s 
                                  AND `user_id_asset`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), user_id_erc20, user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() == "NEAR":
                        sql = """ SELECT * FROM `near_user` WHERE `user_id`=%s 
                                  AND `user_id_near`=%s AND `coin_name`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), user_id_erc20, coin_name, user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        sql = """ SELECT * FROM `cn_user_paymentid` WHERE `user_id`=%s 
                                  AND `coin_name`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), coin_name, user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() == "NANO":
                        sql = """ SELECT * FROM `nano_user` WHERE `user_id`=%s 
                                  AND `coin_name`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), coin_name, user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() == "BTC":
                        sql = """ SELECT * FROM `doge_user` WHERE `user_id`=%s 
                                  AND `coin_name`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), coin_name, user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() == "NEO":
                        sql = """ SELECT * FROM `neo_user` WHERE `user_id`=%s 
                                  AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() == "CHIA":
                        sql = """ SELECT * FROM `xch_user` WHERE `user_id`=%s 
                                  AND `coin_name`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), coin_name, user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() == "HNT":
                        sql = """ SELECT * FROM `hnt_user` WHERE `user_id`=%s 
                                  AND `coin_name`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), coin_name, user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() == "XLM":
                        sql = """ SELECT * FROM `xlm_user` WHERE `user_id`=%s 
                                  AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() == "VITE":
                        sql = """ SELECT * FROM `vite_user` WHERE `user_id`=%s 
                                  AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() == "ADA":
                        sql = """ SELECT * FROM `ada_user` WHERE `user_id`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() == "SOL":
                        sql = """ SELECT * FROM `sol_user` WHERE `user_id`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), user_server))
                        result = await cur.fetchone()
                        if result: return result
                    elif type_coin.upper() == "VET":
                        sql = """ SELECT * FROM `vet_user` WHERE `user_id`=%s AND `user_server`=%s LIMIT 1 """
                        await cur.execute(sql, (str(user_id), user_server))
                        result = await cur.fetchone()
                        if result: return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def call_nano(self, coin: str, payload: str) -> Dict:
        timeout = 100
        coin_name = coin.upper()
        url = getattr(getattr(self.bot.coin_list, coin_name), "rpchost")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload, timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        decoded_data = json.loads(res_data)
                        return decoded_data
        except asyncio.TimeoutError:
            print('TIMEOUT: COIN: {} - timeout {}'.format(coin.upper(), timeout))
            await logchanbot('TIMEOUT: call_nano COIN: {} - timeout {}'.format(coin.upper(), timeout))
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def nano_get_wallet_balance_elements(self, coin: str) -> str:
        coin_name = coin.upper()
        walletkey = decrypt_string(getattr(getattr(self.bot.coin_list, coin_name), "walletkey"))
        get_wallet_balance = await self.call_nano(coin_name,
                                                  payload='{ "action": "wallet_balances", "wallet": "' + walletkey + '" }')
        if get_wallet_balance and 'balances' in get_wallet_balance:
            return get_wallet_balance['balances']
        return None

    async def nano_sendtoaddress(self, source: str, to_address: str, atomic_amount: int, coin: str) -> str:
        coin_name = coin.upper()
        walletkey = decrypt_string(getattr(getattr(self.bot.coin_list, coin_name), "walletkey"))
        payload = '{ "action": "send", "wallet": "' + walletkey + '", "source": "' + source + '", "destination": "' + to_address + '", "amount": "' + str(
            atomic_amount) + '" }'
        sending = await self.call_nano(coin_name, payload=payload)
        if sending and 'block' in sending:
            return sending
        return None

    async def nano_validate_address(self, coin: str, account: str) -> str:
        coin_name = coin.upper()
        valid_address = await self.call_nano(coin_name,
                                             payload='{ "action": "validate_account_number", "account": "' + account + '" }')
        if valid_address and valid_address['valid'] == "1":
            return True
        return None

    async def send_external_nano(self, main_address: str, user_from: str, amount: float, to_address: str, coin: str,
                                 coin_decimal):
        coin_name = coin.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    tx_hash = await self.nano_sendtoaddress(main_address, to_address,
                                                            int(Decimal(amount) * 10 ** coin_decimal), coin_name)
                    if tx_hash:
                        updateTime = int(time.time())
                        async with conn.cursor() as cur:
                            sql = """ INSERT INTO nano_external_tx (`coin_name`, `user_id`, `amount`, `decimal`, `to_address`, `date`, `tx_hash`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (
                            coin_name, user_from, amount, coin_decimal, to_address, int(time.time()),
                            tx_hash['block'],))
                            await conn.commit()
                            return tx_hash
        except Exception:
            await logchanbot("wallet send_external_nano " + str(traceback.format_exc()))
        return None

    async def call_xch(self, method_name: str, coin: str, payload: Dict = None) -> Dict:
        timeout = 100
        coin_name = coin.upper()

        headers = {
            'Content-Type': 'application/json',
        }
        if payload is None:
            data = '{}'
        else:
            data = payload
        url = getattr(getattr(self.bot.coin_list, coin_name), "rpchost") + '/' + method_name.lower()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers, timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        decoded_data = json.loads(res_data)
                        return decoded_data
                    else:
                        print(f'Call {coin_name} returns {str(response.status)} with method {method_name}')
        except asyncio.TimeoutError:
            print('TIMEOUT: method_name: {} - COIN: {} - timeout {}'.format(method_name, coin_name, timeout))
            await logchanbot(
                'call_doge: method_name: {} - COIN: {} - timeout {}'.format(method_name, coin_name, timeout))
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet call_xch " + str(traceback.format_exc()))

    async def send_external_xch(self, user_from: str, amount: float, to_address: str, coin: str, coin_decimal: int,
                                tx_fee: float, withdraw_fee: float, user_server: str = 'DISCORD'):
        coin_name = coin.upper()
        try:
            payload = {
                "wallet_id": 1,
                "amount": int(amount * 10 ** coin_decimal),
                "address": to_address,
                "fee": int(tx_fee * 10 ** coin_decimal)
            }
            result = await self.call_xch('send_transaction', coin_name, payload=payload)
            if result:
                result['tx_hash'] = result['transaction']
                result['transaction_id'] = result['transaction_id']
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        async with conn.cursor() as cur:
                            sql = """ INSERT INTO xch_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `date`, `tx_hash`, `user_server`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (
                            coin_name, user_from, amount, float(result['tx_hash']['fee_amount'] / 10 ** coin_decimal),
                            withdraw_fee, coin_decimal, to_address, int(time.time()), result['tx_hash']['name'],
                            user_server,))
                            await conn.commit()
                            return result['tx_hash']['name']
        except Exception:
            await logchanbot("wallet send_external_xch " + str(traceback.format_exc()))
        return None

    async def call_neo(self, method_name: str, payload) -> Dict:
        timeout = 64
        coin_name = "NEO"
        try:
            headers = {
                'Content-Type': 'application/json'
            }
            data = {"jsonrpc": "1.0", "id": 1, "method": method_name, "params": payload}
            url = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, timeout=timeout) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        print(f'call_neo returns {str(response.status)} with method {method_name}')
        except asyncio.TimeoutError:
            print('call_neo TIMEOUT: method_name: {} - timeout {}'.format(method_name, timeout))
            await logchanbot(
                'call_neo: method_name: {} - timeout {}'.format(method_name, timeout))
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet call_neo " + str(traceback.format_exc()))

    async def send_external_neo(self, user_from: str, coin_decimal: int, contract: str, amount: float, \
    to_address: str, coin_name: str, tx_fee: float, user_server: str):
        user_server = user_server.upper()
        coin_name = coin_name.upper()
        try:
            atomic_amount = int(amount*10**coin_decimal)
            payload = [[{"asset": contract, "value": atomic_amount, "address": to_address}]]
            result = await self.call_neo('sendmany', payload=payload)
            if result is not None:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ INSERT INTO neo_external_tx 
                                  (`coin_name`, `user_id`, `coin_decimal`, `contract`, `real_amount`, 
                                  `real_external_fee`, `to_address`, `date`, `tx_hash`, `tx_json`, `user_server`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (coin_name, user_from, coin_decimal, contract, 
                                                amount, tx_fee, to_address, int(time.time()), 
                                                result['result']['hash'], json.dumps(result['result']), user_server))
                        await conn.commit()
                        return result['result']['hash']
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet send_external_neo " + str(traceback.format_exc()))
        return False

    async def call_doge(self, method_name: str, coin: str, payload: str = None) -> Dict:
        timeout = 64
        coin_name = coin.upper()
        headers = {
            'content-type': 'text/plain;',
        }
        if coin_name in ["HNS"]:
            if payload is None:
                data = '{"method": "' + method_name + '" }'
            else:
                data = '{"method": "' + method_name + '", "params": [' + payload + '] }'
        else:
            if payload is None:
                data = '{"jsonrpc": "1.0", "id":"' + str(
                    uuid.uuid4()) + '", "method": "' + method_name + '", "params": [] }'
            else:
                data = '{"jsonrpc": "1.0", "id":"' + str(
                    uuid.uuid4()) + '", "method": "' + method_name + '", "params": [' + payload + '] }'

        url = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
        # print(url, method_name)
        if method_name == "getblockchaininfo" or method_name == "getinfo":  # daemon
            url = getattr(getattr(self.bot.coin_list, coin_name), "daemon_address")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data, timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        decoded_data = json.loads(res_data)
                        return decoded_data['result']
                    else:
                        print(f'Call {coin_name} returns {str(response.status)} with method {method_name}')
                        print(data)
                        print(url)
        except asyncio.TimeoutError:
            print('TIMEOUT: method_name: {} - COIN: {} - timeout {}'.format(method_name, coin.upper(), timeout))
            await logchanbot(
                'call_doge: method_name: {} - COIN: {} - timeout {}'.format(method_name, coin.upper(), timeout))
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def send_external_doge(self, user_from: str, amount: float, to_address: str, coin: str, tx_fee: float,
                                 withdraw_fee: float, user_server: str):
        user_server = user_server.upper()
        coin_name = coin.upper()
        try:
            comment = user_from
            comment_to = to_address
            payload = f'"{to_address}", {amount}, "{comment}", "{comment_to}", false'
            if getattr(getattr(self.bot.coin_list, coin_name), "coin_has_pos") == 1:
                payload = f'"{to_address}", {amount}, "{comment}", "{comment_to}"'
            txHash = await self.call_doge('sendtoaddress', coin_name, payload=payload)
            if txHash is not None:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ INSERT INTO doge_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `to_address`, `date`, `tx_hash`, `user_server`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (
                        coin_name, user_from, amount, tx_fee, withdraw_fee, to_address, int(time.time()), txHash,
                        user_server))
                        await conn.commit()
                        return txHash
        except Exception:
            await logchanbot("wallet send_external_doge " + str(traceback.format_exc()))
        return False

    async def make_integrated_address_xmr(self, address: str, coin: str, paymentid: str = None):
        coin_name = coin.upper()
        if paymentid:
            try:
                value = int(paymentid, 16)
            except ValueError:
                return False
        else:
            paymentid = cn_addressvalidation.paymentid(8)

        if coin_name == "LTHN":
            payload = {
                "payment_id": {} or paymentid
            }
            address_ia = await self.call_aiohttp_wallet_xmr_bcn('make_integrated_address', coin_name, payload=payload)
            if address_ia: return address_ia
            return None
        else:
            payload = {
                "standard_address": address,
                "payment_id": {} or paymentid
            }
            address_ia = await self.call_aiohttp_wallet_xmr_bcn('make_integrated_address', coin_name, payload=payload)
            if address_ia: return address_ia
            return None

    async def create_address_eth(self):
        def create_eth_wallet():
            seed = ethwallet.generate_mnemonic()
            w = ethwallet.create_wallet(network="ETH", seed=seed, children=1)
            return w

        wallet_eth = functools.partial(create_eth_wallet)
        create_wallet = await self.bot.loop.run_in_executor(None, wallet_eth)
        return create_wallet

    async def create_address_trx(self):
        try:
            _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                       timeout=Timeout(timeout=10, connect=5, read=5))
            TronClient = AsyncTron(provider=AsyncHTTPProvider(self.bot.erc_node_list['TRX'], client=_http_client))
            create_wallet = TronClient.generate_address()
            await TronClient.close()
            return create_wallet
        except Exception:
            traceback.print_exc(file=sys.stdout)

    def check_address_erc20(self, address: str):
        if is_hex_address(address):
            return address
        return False

    async def call_aiohttp_wallet_xmr_bcn(self, method_name: str, coin: str, time_out: int = None,
                                          payload: Dict = None) -> Dict:
        coin_name = coin.upper()
        coin_family = getattr(getattr(self.bot.coin_list, coin_name), "type")
        full_payload = {
            'params': payload or {},
            'jsonrpc': '2.0',
            'id': str(uuid.uuid4()),
            'method': f'{method_name}'
        }
        url = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
        timeout = time_out or 60
        if method_name == "save" or method_name == "store":
            timeout = 300
        elif method_name == "sendTransaction":
            timeout = 180
        elif method_name == "createAddress" or method_name == "getSpendKeys":
            timeout = 60
        try:
            if coin_name == "LTHN":
                # Copied from XMR below
                try:
                    async with aiohttp.ClientSession(headers={'Content-Type': 'application/json'}) as session:
                        async with session.post(url, json=full_payload, timeout=timeout) as response:
                            # sometimes => "message": "Not enough unlocked money" for checking fee
                            if method_name == "split_integrated_address":
                                # we return all data including error
                                if response.status == 200:
                                    res_data = await response.read()
                                    res_data = res_data.decode('utf-8')
                                    decoded_data = json.loads(res_data)
                                    return decoded_data
                            elif method_name == "transfer":
                                print('{} - transfer'.format(coin_name))

                            if response.status == 200:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                if method_name == "transfer":
                                    print(res_data)

                                decoded_data = json.loads(res_data)
                                if 'result' in decoded_data:
                                    return decoded_data['result']
                                else:
                                    return None
                except asyncio.TimeoutError:
                    await logchanbot(
                        'call_aiohttp_wallet: method_name: {} coin_name {} - timeout {}\nfull_payload:\n{}'.format(
                            method_name, coin_name, timeout, json.dumps(payload)))
                    print('TIMEOUT: {} coin_name {} - timeout {}'.format(method_name, coin_name, timeout))
                    return None
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot("wallet call_aiohttp_wallet_xmr_bcn " + str(traceback.format_exc()))
                    return None
            elif coin_family == "XMR":
                try:
                    async with aiohttp.ClientSession(headers={'Content-Type': 'application/json'}) as session:
                        async with session.post(url, json=full_payload, timeout=timeout) as response:
                            # sometimes => "message": "Not enough unlocked money" for checking fee
                            if method_name == "transfer":
                                print('{} - transfer'.format(coin_name))
                                # print(full_payload)
                            if response.status == 200:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                if method_name == "transfer":
                                    print(res_data)

                                decoded_data = json.loads(res_data)
                                if 'result' in decoded_data:
                                    return decoded_data['result']
                                else:
                                    return None
                except asyncio.TimeoutError:
                    await logchanbot(
                        'call_aiohttp_wallet: method_name: {} coin_name {} - timeout {}\nfull_payload:\n{}'.format(
                            method_name, coin_name, timeout, json.dumps(payload)))
                    print('TIMEOUT: {} coin_name {} - timeout {}'.format(method_name, coin_name, timeout))
                    return None
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot("wallet call_aiohttp_wallet_xmr_bcn " + str(traceback.format_exc()))
                    return None
            elif coin_family in ["TRTL-SERVICE", "BCN"]:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, json=full_payload, timeout=timeout) as response:
                            if response.status == 200 or response.status == 201:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')

                                decoded_data = json.loads(res_data)
                                if 'result' in decoded_data:
                                    return decoded_data['result']
                                else:
                                    await logchanbot(str(res_data))
                                    return None
                            else:
                                await logchanbot(str(response))
                                return None
                except asyncio.TimeoutError:
                    await logchanbot(
                        'call_aiohttp_wallet: {} coin_name {} - timeout {}\nfull_payload:\n{}'.format(method_name,
                                                                                                      coin_name,
                                                                                                      timeout,
                                                                                                      json.dumps(
                                                                                                          payload)))
                    print('TIMEOUT: {} coin_name {} - timeout {}'.format(method_name, coin_name, timeout))
                    return None
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot("wallet call_aiohttp_wallet_xmr_bcn " + str(traceback.format_exc()))
                    return None
        except asyncio.TimeoutError:
            await logchanbot(
                'call_aiohttp_wallet: method_name: {} - coin_family: {} - timeout {}'.format(method_name, coin_family,
                                                                                             timeout))
            print('TIMEOUT: method_name: {} - coin_family: {} - timeout {}'.format(method_name, coin_family, timeout))
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet call_aiohttp_wallet_xmr_bcn " + str(traceback.format_exc()))

    async def send_external_xmr(self, type_coin: str, from_address: str, user_from: str, amount: float, to_address: str,
                                coin: str, coin_decimal: int, tx_fee: float, withdraw_fee: float, is_fee_per_byte: int,
                                get_mixin: int, user_server: str, wallet_api_url: str = None,
                                wallet_api_header: str = None, paymentId: str = None):
        coin_name = coin.upper()
        user_server = user_server.upper()
        time_out = 32
        if coin_name == "DEGO":
            time_out = 120
        try:
            if type_coin == "XMR":
                acc_index = 0
                payload = {
                    "destinations": [{'amount': int(amount * 10 ** coin_decimal), 'address': to_address}],
                    "account_index": acc_index,
                    "subaddr_indices": [],
                    "priority": 1,
                    "unlock_time": 0,
                    "get_tx_key": True,
                    "get_tx_hex": False,
                    "get_tx_metadata": False
                }
                if coin_name == "UPX":
                    payload = {
                        "destinations": [{'amount': int(amount * 10 ** coin_decimal), 'address': to_address}],
                        "account_index": acc_index,
                        "subaddr_indices": [],
                        "ring_size": 11,
                        "get_tx_key": True,
                        "get_tx_hex": False,
                        "get_tx_metadata": False
                    }
                result = await self.call_aiohttp_wallet_xmr_bcn('transfer', coin_name, time_out=time_out,
                                                                payload=payload)
                if result and 'tx_hash' in result and 'tx_key' in result:
                    await self.openConnection()
                    async with self.pool.acquire() as conn:
                        async with conn.cursor() as cur:
                            sql = """ INSERT INTO cn_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `date`, `tx_hash`, `tx_key`, `user_server`) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (
                            coin_name, user_from, amount, tx_fee, withdraw_fee, coin_decimal, to_address,
                            int(time.time()), result['tx_hash'], result['tx_key'], user_server,))
                            await conn.commit()
                            return result['tx_hash']
            elif (type_coin == "TRTL-SERVICE" or type_coin == "BCN") and paymentId is None:
                if is_fee_per_byte != 1:
                    payload = {
                        'addresses': [from_address],
                        'transfers': [{
                            "amount": int(amount * 10 ** coin_decimal),
                            "address": to_address
                        }],
                        'fee': int(tx_fee * 10 ** coin_decimal),
                        'anonymity': get_mixin
                    }
                else:
                    payload = {
                        'addresses': [from_address],
                        'transfers': [{
                            "amount": int(amount * 10 ** coin_decimal),
                            "address": to_address
                        }],
                        'anonymity': get_mixin
                    }
                result = await self.call_aiohttp_wallet_xmr_bcn('sendTransaction', coin_name, time_out=time_out,
                                                                payload=payload)
                if result and 'transactionHash' in result:
                    if is_fee_per_byte != 1:
                        tx_hash = {"transactionHash": result['transactionHash'], "fee": tx_fee}
                    else:
                        tx_hash = {"transactionHash": result['transactionHash'], "fee": result['fee']}
                        tx_fee = float(tx_hash['fee'] / 10 ** coin_decimal)
                    try:
                        await self.openConnection()
                        async with self.pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                sql = """ INSERT INTO cn_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `date`, `tx_hash`, `user_server`) 
                                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                await cur.execute(sql, (
                                coin_name, user_from, amount, tx_fee, withdraw_fee, coin_decimal, to_address,
                                int(time.time()), tx_hash['transactionHash'], user_server))
                                await conn.commit()
                                return tx_hash['transactionHash']
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot("wallet send_external_xmr " + str(traceback.format_exc()))
            elif type_coin == "TRTL-API" and paymentId is None:
                if is_fee_per_byte != 1:
                    json_data = {
                        "destinations": [{"address": to_address, "amount": int(amount * 10 ** coin_decimal)}],
                        "mixin": get_mixin,
                        "fee": int(tx_fee * 10 ** coin_decimal),
                        "sourceAddresses": [
                            from_address
                        ],
                        "paymentID": "",
                        "changeAddress": from_address
                    }
                else:
                    json_data = {
                        "destinations": [{"address": to_address, "amount": int(amount * 10 ** coin_decimal)}],
                        "mixin": get_mixin,
                        "sourceAddresses": [
                            from_address
                        ],
                        "paymentID": "",
                        "changeAddress": from_address
                    }
                method = "/transactions/send/advanced"
                try:
                    headers = {
                        'X-API-KEY': wallet_api_header,
                        'Content-Type': 'application/json'
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(wallet_api_url + method, headers=headers, json=json_data,
                                                timeout=time_out) as response:
                            json_resp = await response.json()
                            if response.status == 200 or response.status == 201:
                                if is_fee_per_byte != 1:
                                    tx_hash = {"transactionHash": json_resp['transactionHash'], "fee": tx_fee}
                                else:
                                    tx_hash = {"transactionHash": json_resp['transactionHash'], "fee": json_resp['fee']}
                                    tx_fee = float(tx_hash['fee'] / 10 ** coin_decimal)
                                try:
                                    await self.openConnection()
                                    async with self.pool.acquire() as conn:
                                        async with conn.cursor() as cur:
                                            sql = """ INSERT INTO cn_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `date`, `tx_hash`, `user_server`) 
                                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                            await cur.execute(sql, (
                                            coin_name, user_from, amount, tx_fee, withdraw_fee, coin_decimal,
                                            to_address, int(time.time()), tx_hash['transactionHash'], user_server))
                                            await conn.commit()
                                            return tx_hash['transactionHash']
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                                    await logchanbot("wallet send_external_xmr " + str(traceback.format_exc()))
                            elif 'errorMessage' in json_resp:
                                raise RPCException(json_resp['errorMessage'])
                            else:
                                await logchanbot('walletapi_send_transaction: {} response: {}'.format(method, response))
                except asyncio.TimeoutError:
                    await logchanbot(
                        'walletapi_send_transaction: TIMEOUT: {} coin_name {} - timeout {}'.format(method, coin_name,
                                                                                                   time_out))
            elif (type_coin == "TRTL-SERVICE" or type_coin == "BCN") and paymentId is not None:
                if coin_name == "DEGO":
                    time_out = 300
                if is_fee_per_byte != 1:
                    payload = {
                        'addresses': [from_address],
                        'transfers': [{
                            "amount": int(amount * 10 ** coin_decimal),
                            "address": to_address
                        }],
                        'fee': int(tx_fee * 10 ** coin_decimal),
                        'anonymity': get_mixin,
                        'paymentId': paymentId,
                        'changeAddress': from_address
                    }
                else:
                    payload = {
                        'addresses': [from_address],
                        'transfers': [{
                            "amount": int(amount * 10 ** coin_decimal),
                            "address": to_address
                        }],
                        'anonymity': get_mixin,
                        'paymentId': paymentId,
                        'changeAddress': from_address
                    }
                result = None
                result = await self.call_aiohttp_wallet_xmr_bcn('sendTransaction', coin_name, time_out=time_out,
                                                                payload=payload)
                if result and 'transactionHash' in result:
                    if is_fee_per_byte != 1:
                        tx_hash = {"transactionHash": result['transactionHash'], "fee": tx_fee}
                    else:
                        tx_hash = {"transactionHash": result['transactionHash'], "fee": result['fee']}
                        tx_fee = float(tx_hash['fee'] / 10 ** coin_decimal)
                    try:
                        await self.openConnection()
                        async with self.pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                sql = """ INSERT INTO cn_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `paymentid`, `date`, `tx_hash`, `user_server`) 
                                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                await cur.execute(sql, (
                                coin_name, user_from, amount, tx_fee, withdraw_fee, coin_decimal, to_address, paymentId,
                                int(time.time()), tx_hash['transactionHash'], user_server))
                                await conn.commit()
                                return tx_hash['transactionHash']
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot("wallet send_external_xmr " + str(traceback.format_exc()))
            elif type_coin == "TRTL-API" and paymentId is not None:
                if is_fee_per_byte != 1:
                    json_data = {
                        'sourceAddresses': [from_address],
                        'destinations': [{
                            "amount": int(amount * 10 ** coin_decimal),
                            "address": to_address
                        }],
                        'fee': int(tx_fee * 10 ** coin_decimal),
                        'mixin': get_mixin,
                        'paymentID': paymentId,
                        'changeAddress': from_address
                    }
                else:
                    json_data = {
                        'sourceAddresses': [from_address],
                        'destinations': [{
                            "amount": int(amount * 10 ** coin_decimal),
                            "address": to_address
                        }],
                        'mixin': get_mixin,
                        'paymentID': paymentId,
                        'changeAddress': from_address
                    }
                method = "/transactions/send/advanced"
                try:
                    headers = {
                        'X-API-KEY': wallet_api_header,
                        'Content-Type': 'application/json'
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(wallet_api_url + method, headers=headers, json=json_data,
                                                timeout=time_out) as response:
                            json_resp = await response.json()
                            if response.status == 200 or response.status == 201:
                                if is_fee_per_byte != 1:
                                    tx_hash = {"transactionHash": json_resp['transactionHash'], "fee": tx_fee}
                                else:
                                    tx_hash = {"transactionHash": json_resp['transactionHash'], "fee": json_resp['fee']}
                                    tx_fee = float(tx_hash['fee'] / 10 ** coin_decimal)
                                try:
                                    await self.openConnection()
                                    async with self.pool.acquire() as conn:
                                        async with conn.cursor() as cur:
                                            sql = """ INSERT INTO cn_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `paymentid`, `date`, `tx_hash`, `user_server`) 
                                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                            await cur.execute(sql, (
                                            coin_name, user_from, amount, tx_fee, withdraw_fee, coin_decimal,
                                            to_address, paymentId, int(time.time()), tx_hash['transactionHash'],
                                            user_server))
                                            await conn.commit()
                                            return tx_hash['transactionHash']
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                                    await logchanbot("wallet send_external_xmr " + str(traceback.format_exc()))
                            elif 'errorMessage' in json_resp:
                                raise RPCException(json_resp['errorMessage'])
                except asyncio.TimeoutError:
                    await logchanbot(
                        'walletapi_send_transaction_id: TIMEOUT: {} coin_name {} - timeout {}'.format(method, coin_name,
                                                                                                      time_out))
        except Exception:
            await logchanbot("wallet send_external_xmr " + str(traceback.format_exc()))
        return None

    async def send_external_hnt(self, user_id: str, wallet_host: str, password: str, from_address: str, payee: str,
                                amount: float, coin_decimal: int, user_server: str, coin: str, withdraw_fee: float,
                                time_out=32):
        coin_name = coin.upper()
        if from_address == payee: return None
        try:
            headers = {
                'Content-Type': 'application/json'
            }
            json_send = {
                "jsonrpc": "2.0",
                "id": "1",
                "method": "wallet_pay",
                "params": {
                    "address": from_address,
                    "payee": payee,
                    "bones": int(amount * 10 ** coin_decimal)
                    # "nonce": 422
                }
            }
            json_unlock = {
                "jsonrpc": "2.0",
                "id": "1",
                "method": "wallet_unlock",
                "params": {
                    "address": from_address,
                    "password": password
                }
            }
            json_check_lock = {
                "jsonrpc": "2.0",
                "id": "1",
                "method": "wallet_is_locked",
                "params": {
                    "address": from_address
                }
            }

            async def call_hnt_wallet(url, headers, json_data, time_out):
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=json_data, timeout=time_out) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            decoded_data = json.loads(res_data)
                            json_resp = decoded_data
                            return json_resp

            # 1] Check if lock
            # 3] Unlock
            try:
                unlock = None
                check_locked = await call_hnt_wallet(wallet_host, headers=headers, json_data=json_check_lock,
                                                     time_out=time_out)
                print(check_locked)
                if 'result' in check_locked and check_locked['result'] is True:
                    await logchanbot(f'[UNLOCKED] {coin_name}...')
                    unlock = await call_hnt_wallet(wallet_host, headers=headers, json_data=json_unlock,
                                                   time_out=time_out)
                    print(unlock)
                if unlock is None or (unlock is not None and 'result' in unlock and unlock['result'] == True):
                    sendTx = await call_hnt_wallet(wallet_host, headers=headers, json_data=json_send, time_out=time_out)
                    fee = 0.0
                    if 'result' in sendTx:
                        if 'implicit_burn' in sendTx['result'] and 'fee' in sendTx['result']['implicit_burn']:
                            fee = sendTx['result']['implicit_burn']['fee'] / 10 ** coin_decimal
                        elif 'fee' in sendTx['result']:
                            fee = sendTx['result']['fee'] / 10 ** coin_decimal
                        try:
                            await self.openConnection()
                            async with self.pool.acquire() as conn:
                                async with conn.cursor() as cur:
                                    sql = """ INSERT INTO hnt_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `date`, `tx_hash`, `user_server`) 
                                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                    await cur.execute(sql, (
                                    coin_name, user_id, amount, fee, withdraw_fee, coin_decimal, payee,
                                    int(time.time()), sendTx['result']['hash'], user_server))
                                    await conn.commit()
                                    return sendTx['result']['hash']
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot("wallet send_external_hnt " + str(traceback.format_exc()))
                        # return tx_hash
                else:
                    await logchanbot('[FAILED] send_external_hnt: Failed to unlock wallet...')
                    return None
            except Exception:
                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet send_external_hnt " + str(traceback.format_exc()))
        return None

    async def check_xlm_asset(self, url: str, asset_name: str, issuer: str, to_address: str, user_id: str,
                              user_server: str):
        found = False
        try:
            async with ServerAsync(
                    horizon_url=url, client=AiohttpClient()
            ) as server:
                account = await server.accounts().account_id(to_address).call()
                if 'balances' in account and len(account['balances']) > 0:
                    for each_balance in account['balances']:
                        if 'asset_code' in each_balance and 'asset_issuer' in each_balance and \
                            each_balance['asset_code'] == asset_name and issuer == each_balance['asset_issuer']:
                            found = True
                            break
        except Exception:
            await logchanbot(
                f"[{user_server}] [XLM]: Failed /withdraw by {user_id}. Account not found for address: {to_address} / asset_name: {asset_name}.")
        return found

    async def send_external_xlm(self, url: str, withdraw_keypair: str, user_id: str, amount: float, to_address: str,
                                coin_decimal: int, user_server: str, coin: str, withdraw_fee: float,
                                asset_ticker: str = None, asset_issuer: str = None, time_out=32):
        coin_name = coin.upper()
        asset_sending = Asset.native()
        if coin_name != "XLM":
            asset_sending = Asset(asset_ticker, asset_issuer)
        tipbot_keypair = Stella_Keypair.from_secret(withdraw_keypair)
        async with ServerAsync(
                horizon_url=url, client=AiohttpClient()
        ) as server:
            tipbot_account = await server.load_account(tipbot_keypair.public_key)
            base_fee = 50000
            transaction = (
                TransactionBuilder(
                    source_account=tipbot_account,
                    network_passphrase=Network.PUBLIC_NETWORK_PASSPHRASE,
                    base_fee=base_fee,
                )
                # .add_text_memo("Hello, Stellar!")
                .append_payment_op(to_address, asset_sending, str(truncate(amount, 6)))
                .set_timeout(30)
                .build()
            )
            transaction.sign(tipbot_keypair)
            response = await server.submit_transaction(transaction)
            # print(response)
            fee = float(response['fee_charged']) / 10000000
            try:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ INSERT INTO xlm_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `date`, `tx_hash`, `user_server`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (
                        coin_name, user_id, amount, fee, withdraw_fee, coin_decimal, to_address, int(time.time()),
                        response['hash'], user_server))
                        await conn.commit()
                        return response['hash']
            except Exception:
                await logchanbot("wallet send_external_xlm " + str(traceback.format_exc()))
                traceback.print_exc(file=sys.stdout)
        return None

    async def send_external_ada(self, user_id: str, amount: float, coin_decimal: int, user_server: str, coin: str,
                                withdraw_fee: float, to_address: str, time_out=32):
        coin_name = coin.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                              FROM `ada_wallets` 
                              WHERE `is_for_withdraw`=%s ORDER BY RAND() LIMIT 1 """
                    await cur.execute(sql, (1))
                    result = await cur.fetchone()
                    if result:
                        ## got wallet setting
                        # check if wallet sync
                        async def fetch_wallet_status(url, timeout):
                            try:
                                headers = {
                                    'Content-Type': 'application/json'
                                }
                                async with aiohttp.ClientSession() as session:
                                    async with session.get(url, headers=headers, timeout=timeout) as response:
                                        res_data = await response.read()
                                        res_data = res_data.decode('utf-8')
                                        decoded_data = json.loads(res_data)
                                        return decoded_data
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            return None

                        fetch_wallet = await fetch_wallet_status(
                            result['wallet_rpc'] + "v2/wallets/" + result['wallet_id'], 32)
                        if fetch_wallet and fetch_wallet['state']['status'] == "ready":
                            # wallet is ready, "syncing" if it is syncing
                            async def send_tx(url: str, to_address: str, amount_atomic: int, timeout: int = 90):
                                try:
                                    headers = {
                                        'Content-Type': 'application/json'
                                    }
                                    data_json = {"passphrase": decrypt_string(result['passphrase']), "payments": [
                                        {"address": to_address,
                                         "amount": {"quantity": amount_atomic, "unit": "lovelace"}}],
                                                 "withdrawal": "self"}
                                    async with aiohttp.ClientSession() as session:
                                        async with session.post(url, headers=headers, json=data_json,
                                                                timeout=timeout) as response:
                                            if response.status == 202:
                                                res_data = await response.read()
                                                res_data = res_data.decode('utf-8')
                                                decoded_data = json.loads(res_data)
                                                return decoded_data
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                                return None

                            sending_tx = await send_tx(
                                result['wallet_rpc'] + "v2/wallets/" + result['wallet_id'] + "/transactions",
                                to_address, int(amount * 10 ** coin_decimal), 90)
                            if "code" in sending_tx and "message" in sending_tx:
                                return sending_tx
                            elif "status" in sending_tx and sending_tx['status'] == "pending":
                                # success
                                # withdraw_fee became: network_fee + withdraw_fee, it is fee_limit
                                network_fee = sending_tx['fee']['quantity'] / 10 ** coin_decimal
                                await self.openConnection()
                                async with self.pool.acquire() as conn:
                                    async with conn.cursor() as cur:
                                        sql = """ INSERT INTO `ada_external_tx` (`coin_name`, `asset_name`, `policy_id`, `user_id`, `real_amount`, `real_external_fee`, `network_fee`, `token_decimal`, `to_address`, `input_json`, `output_json`, `hash_id`, `date`, `user_server`) 
                                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                        await cur.execute(sql, (
                                        coin_name, None, None, user_id, amount, network_fee + withdraw_fee, network_fee,
                                        coin_decimal, to_address, json.dumps(sending_tx['inputs']),
                                        json.dumps(sending_tx['outputs']), sending_tx['id'], int(time.time()),
                                        user_server))
                                        await conn.commit()
                                        return sending_tx
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet send_external_ada " + str(traceback.format_exc()))
        return None

    async def send_external_ada_asset(self, user_id: str, amount: float, coin_decimal: int, user_server: str, coin: str,
                                      withdraw_fee: float, to_address: str, asset_name: str, policy_id: str,
                                      time_out=32):
        coin_name = coin.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                              FROM `ada_wallets` 
                              WHERE `is_for_withdraw`=%s ORDER BY RAND() LIMIT 1 """
                    await cur.execute(sql, (1))
                    result = await cur.fetchone()
                    if result:
                        ## got wallet setting
                        # check if wallet sync
                        async def fetch_wallet_status(url, timeout):
                            try:
                                headers = {
                                    'Content-Type': 'application/json'
                                }
                                async with aiohttp.ClientSession() as session:
                                    async with session.get(url, headers=headers, timeout=timeout) as response:
                                        res_data = await response.read()
                                        res_data = res_data.decode('utf-8')
                                        decoded_data = json.loads(res_data)
                                        return decoded_data
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            return None

                        fetch_wallet = await fetch_wallet_status(
                            result['wallet_rpc'] + "v2/wallets/" + result['wallet_id'], 32)
                        if fetch_wallet and fetch_wallet['state']['status'] == "ready":
                            # wallet is ready, "syncing" if it is syncing
                            async def estimate_fee_with_asset(url: str, to_address: str, asset_name: str,
                                                              policy_id: str, amount_atomic: int, timeout: int = 90):
                                try:
                                    headers = {
                                        'Content-Type': 'application/json'
                                    }
                                    data_json = {"payments": [
                                        {"address": to_address, "amount": {"quantity": 0, "unit": "lovelace"},
                                         "assets": [{"policy_id": policy_id, "asset_name": asset_name,
                                                     "quantity": amount_atomic}]}], "withdrawal": "self"}
                                    async with aiohttp.ClientSession() as session:
                                        async with session.post(url, headers=headers, json=data_json,
                                                                timeout=timeout) as response:
                                            if response.status == 202:
                                                res_data = await response.read()
                                                res_data = res_data.decode('utf-8')
                                                decoded_data = json.loads(res_data)
                                                return decoded_data
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                                return None

                            async def send_tx(url: str, to_address: str, ada_atomic_amount: int, amount_atomic: int,
                                              asset_name: str, policy_id: str, timeout: int = 90):
                                try:
                                    headers = {
                                        'Content-Type': 'application/json'
                                    }
                                    data_json = {"passphrase": decrypt_string(result['passphrase']), "payments": [
                                        {"address": to_address,
                                         "amount": {"quantity": ada_atomic_amount, "unit": "lovelace"}, "assets": [
                                            {"policy_id": policy_id, "asset_name": asset_name,
                                             "quantity": amount_atomic}]}], "withdrawal": "self"}
                                    async with aiohttp.ClientSession() as session:
                                        async with session.post(url, headers=headers, json=data_json,
                                                                timeout=timeout) as response:
                                            if response.status == 202:
                                                res_data = await response.read()
                                                res_data = res_data.decode('utf-8')
                                                decoded_data = json.loads(res_data)
                                                return decoded_data
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                                return None

                            estimate_tx = await estimate_fee_with_asset(
                                result['wallet_rpc'] + "v2/wallets/" + result['wallet_id'] + "/payment-fees",
                                to_address, asset_name, policy_id, int(amount * 10 ** coin_decimal), 10)
                            ada_fee_atomic = None
                            if estimate_tx and "minimum_coins" in estimate_tx:
                                ada_fee_atomic = estimate_tx['minimum_coins'][0]['quantity']
                                sending_tx = await send_tx(
                                    result['wallet_rpc'] + "v2/wallets/" + result['wallet_id'] + "/transactions",
                                    to_address, ada_fee_atomic, int(amount * 10 ** coin_decimal), asset_name, policy_id,
                                    90)
                                if "code" in sending_tx and "message" in sending_tx:
                                    return sending_tx
                                elif "status" in sending_tx and sending_tx['status'] == "pending":
                                    # success
                                    rows = []
                                    if len(sending_tx['outputs']) > 0:
                                        network_fee = sending_tx['fee']['quantity'] / 10 ** 6  # Fee in ADA
                                        for each_output in sending_tx['outputs']:
                                            if each_output['address'].upper() == to_address:
                                                # rows.append( () )
                                                pass
                                    data_rows = []
                                    try:
                                        data_rows.append((coin_name, asset_name, policy_id, user_id, amount,
                                                          withdraw_fee, network_fee, coin_decimal, to_address,
                                                          json.dumps(sending_tx['inputs']),
                                                          json.dumps(sending_tx['outputs']), sending_tx['id'],
                                                          int(time.time()), user_server))
                                        if getattr(getattr(self.bot.coin_list, coin_name),
                                                   "withdraw_use_gas_ticker") == 1:
                                            GAS_COIN = getattr(getattr(self.bot.coin_list, coin_name), "gas_ticker")
                                            fee_limit = getattr(getattr(self.bot.coin_list, coin_name), "fee_limit")
                                            fee_limit = fee_limit / 20  # => 2 / 20 = 0.1 ADA # Take care if you adjust fee_limit in DB
                                            # new ADA charge = ADA goes to withdraw wallet + 0.1 ADA
                                            data_rows.append((GAS_COIN, None, None, user_id,
                                                              network_fee + fee_limit + ada_fee_atomic / 10 ** 6, 0,
                                                              network_fee,
                                                              getattr(getattr(self.bot.coin_list, GAS_COIN), "decimal"),
                                                              to_address, json.dumps(sending_tx['inputs']),
                                                              json.dumps(sending_tx['outputs']), sending_tx['id'],
                                                              int(time.time()), user_server))
                                        await self.openConnection()
                                        async with self.pool.acquire() as conn:
                                            async with conn.cursor() as cur:
                                                sql = """ INSERT INTO `ada_external_tx` (`coin_name`, `asset_name`, `policy_id`, `user_id`, `real_amount`, `real_external_fee`, `network_fee`, `token_decimal`, `to_address`, `input_json`, `output_json`, `hash_id`, `date`, `user_server`) 
                                                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                await cur.executemany(sql, data_rows)
                                                await conn.commit()
                                                sending_tx[
                                                    'all_ada_fee'] = network_fee + fee_limit + ada_fee_atomic / 10 ** 6
                                                sending_tx['ada_received'] = ada_fee_atomic / 10 ** 6
                                                sending_tx['network_fee'] = network_fee
                                                return sending_tx
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        await logchanbot(
                                            f'[BUG] send_external_ada_asset: user_id: `{user_id}` failed to insert to DB for withdraw {json.dumps(data_rows)}.')
                            else:
                                print(
                                    f"send_external_ada_asset: cannot get estimated fee for sending asset `{asset_name}`")
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet send_external_ada_asset " + str(traceback.format_exc()))
        return None

    async def send_external_sol(self, url: str, user_from: str, amount: float, to_address: str, coin: str,
                                coin_decimal: int, tx_fee: float, withdraw_fee: float, user_server: str = 'DISCORD'):
        async def move_wallet_balance(url: str, receiver: str, atomic_amount: int):
            # url: is endpoint transfer
            try:
                sender = Keypair.from_secret_key(bytes.fromhex(config.sol.MainAddress_key_hex))
                client = Sol_AsyncClient(url)
                txn = Transaction().add(transfer(TransferParams(
                    from_pubkey=sender.public_key, to_pubkey=receiver, lamports=atomic_amount)))
                sending_tx = await client.send_transaction(txn, sender)
                if 'result' in sending_tx:
                    await client.close()
                    return sending_tx['result']  # This is Tx Hash
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return None

        try:
            send_tx = await move_wallet_balance(url, to_address, int(amount * 10 ** coin_decimal))
            if send_tx:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ INSERT INTO `sol_external_tx` (`coin_name`, `contract`, `user_id`, `real_amount`, `real_external_fee`, `network_fee`, `txn`, `token_decimal`, `to_address`, `date`, `user_server`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (
                        coin.upper(), None, user_from, amount, withdraw_fee, tx_fee, send_tx, coin_decimal, to_address,
                        int(time.time()), user_server))
                        await conn.commit()
                        return send_tx
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def tezos_insert_reveal(self, address: str, tx_hash: str, checked_date: int):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT IGNORE INTO `tezos_address_reveal_check` (`address`, `tx_hash`, `checked_date`) 
                              VALUES (%s, %s, %s) """
                    await cur.execute(sql, (address, tx_hash, checked_date))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def tezos_checked_reveal_db(self, address: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                              FROM `tezos_address_reveal_check` 
                              WHERE `address`=%s LIMIT 1 """
                    await cur.execute(sql, address)
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def tezos_get_user_by_address(self, address: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                              FROM `tezos_user` 
                              WHERE `balance_wallet_address`=%s LIMIT 1 """
                    await cur.execute(sql, address)
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    def tezos_move_balance(self, url: str, key: str, to_address: str, atomic_amount: int):
        try:
            user_address = pytezos.using(shell=url, key=key)
            tx = user_address.transaction(source=user_address.key.public_key_hash(), destination=to_address, amount=atomic_amount).send()
            return tx
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    def tezos_move_token_balance(self, url: str, key: str, to_address: str, contract: str, atomic_amount: int, token_id: int=0):
        try:
            token = pytezos.using(shell=url, key=key).contract(contract)
            acc = pytezos.using(shell=url, key=key)
            tx_token = token.transfer([dict(from_ = acc.key.public_key_hash(), txs = [ dict(to_ = to_address, amount = atomic_amount, token_id = int(token_id))])]).send()
            return tx_token
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    def tezos_move_token_balance_fa12(self, url: str, key: str, to_address: str, contract: str, atomic_amount: int, token_id: int=0):
        try:
            token = pytezos.using(shell=url, key=key).contract(contract)
            acc = pytezos.using(shell=url, key=key)
            tx_token = token.transfer(**{'from': acc.key.public_key_hash(), 'to': to_address, 'value': atomic_amount}).inject()
            return tx_token
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def send_external_xtz(self, url: str, key: str, user_from: str, amount: float, to_address: str, coin: str,
                                coin_decimal: int, withdraw_fee: float, network: str, user_server: str = 'DISCORD'):
        try:
            transaction = functools.partial(self.tezos_move_balance, url, key, to_address, int(amount*10**coin_decimal))
            send_tx = await self.bot.loop.run_in_executor(None, transaction)
            if send_tx:
                contents = None
                try:
                    contents = json.dumps(send_tx.contents)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ INSERT INTO `tezos_external_tx` (`token_name`, `contract`, `user_id`, `real_amount`, `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, `contents`, `user_server`, `network`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (
                        coin.upper(), None, user_from, amount, withdraw_fee, coin_decimal, to_address,
                        int(time.time()), send_tx.hash(), contents, user_server, network))
                        await conn.commit()
                        return send_tx.hash()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def send_external_xtz_asset(self, url: str, key: str, user_from: str, amount: float, to_address: str, coin: str,
                                      coin_decimal: int, withdraw_fee: float, network: str, contract: str, token_id: int, 
                                      token_type: str, user_server: str = 'DISCORD'):
        try:
            if token_type == "FA2":
                transaction = functools.partial(self.tezos_move_token_balance, url, key, to_address, contract, int(amount*10**coin_decimal), token_id)
            elif token_type == "FA1.2":
                transaction = functools.partial(self.tezos_move_token_balance_fa12, url, key, to_address, contract, int(amount*10**coin_decimal), token_id)
            send_tx = await self.bot.loop.run_in_executor(None, transaction)
            if send_tx:
                contents = None
                tx_hash = None
                try:
                    if token_type == "FA2":
                        contents = json.dumps(send_tx.contents)
                        tx_hash = send_tx.hash()
                    elif token_type == "FA1.2":
                        contents = json.dumps(send_tx['contents'])
                        tx_hash = send_tx['hash']
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ INSERT INTO `tezos_external_tx` (`token_name`, `contract`, `user_id`, `real_amount`, `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, `contents`, `user_server`, `network`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (
                        coin.upper(), contract, user_from, amount, withdraw_fee, coin_decimal, to_address,
                        int(time.time()), tx_hash, contents, user_server, network))
                        await conn.commit()
                        return tx_hash
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def tezos_insert_mv_balance(self, token_name: str, contract: str, user_id: str, balance_wallet_address: str, to_main_address: str, real_amount: float, real_deposit_fee: float, token_decimal: int, txn: str, content: str, time_insert: int, user_server: str, network: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT IGNORE INTO `tezos_move_deposit` (`token_name`, `contract`, `user_id`, `balance_wallet_address`, 
                              `to_main_address`, `real_amount`, `real_deposit_fee`, `token_decimal`, `txn`, `content`, `time_insert`, 
                              `user_server`, `network`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (token_name, contract, user_id, balance_wallet_address, to_main_address, real_amount, real_deposit_fee, token_decimal, txn, content, time_insert, user_server, network))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def tezos_get_mv_deposit_list(self, status: str="PENDING"):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                              FROM `tezos_move_deposit` 
                              WHERE `status`=%s """
                    await cur.execute(sql, status)
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def tezos_update_mv_gas(self, address: str, ts: int):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `tezos_user` 
                              SET `last_moved_gas`=%s 
                              WHERE `balance_wallet_address`=%s LIMIT 1 """
                    await cur.execute(sql, (ts, address))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def tezos_update_mv_deposit_pending(self, txn: str, blockNumber: int, confirmed_depth: int):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `tezos_move_deposit` 
                              SET `blockNumber`=%s, `status`=%s, `confirmed_depth`=%s 
                              WHERE `status`=%s AND `txn`=%s LIMIT 1 """
                    await cur.execute(sql, (blockNumber, "CONFIRMED", confirmed_depth, "PENDING", txn))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    def near_move_balance(self, url: str, key: str, by_address: str, to_address: str, atomic_amount: int):
        try:
            near_provider = near_api.providers.JsonProvider(url)
            sender_key_pair = near_api.signer.KeyPair(bytes.fromhex(key))
            sender_signer = near_api.signer.Signer(by_address, sender_key_pair)
            sender_account = near_api.account.Account(near_provider, sender_signer, by_address)
            out = sender_account.send_money(to_address, atomic_amount)
            return out
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    def near_move_balance_token(self, url: str, contract_id: str, key: str, by_address: str, to_address: str, atomic_amount: int):
        try:
            near_provider = near_api.providers.JsonProvider(url)
            sender_key_pair = near_api.signer.KeyPair(bytes.fromhex(key))
            sender_signer = near_api.signer.Signer(by_address, sender_key_pair)
            sender_account = near_api.account.Account(near_provider, sender_signer, by_address)
            args = {"receiver_id": to_address, "amount": str(atomic_amount)}
            out = sender_account.function_call(contract_id=contract_id, method_name="ft_transfer", args=args, amount=1)
            return out
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def near_get_user_by_address(self, address: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                              FROM `near_user` 
                              WHERE `balance_wallet_address`=%s LIMIT 1 """
                    await cur.execute(sql, address)
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def near_insert_mv_balance(self, token_name: str, contract: str, user_id: str, balance_wallet_address: str, to_main_address: str, real_amount: float, real_deposit_fee: float, token_decimal: int, txn: str, content: str, time_insert: int, user_server: str, network: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT IGNORE INTO `near_move_deposit` (`token_name`, `contract`, `user_id`, `balance_wallet_address`, 
                              `to_main_address`, `amount`, `real_deposit_fee`, `token_decimal`, `txn`, `content`, `time_insert`, 
                              `user_server`, `network`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (token_name, contract, user_id, balance_wallet_address, to_main_address, real_amount, real_deposit_fee, token_decimal, txn, content, time_insert, user_server, network))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def send_external_near(self, url: str, contract_id: str, key: str, user_from: str, by_address: str, amount: float, to_address: str, coin: str, coin_decimal: int, withdraw_fee: float, user_server: str = 'DISCORD'):
        try:
            if contract_id is None:
                transaction = functools.partial(self.near_move_balance, url, key, by_address, to_address, int(amount*10**coin_decimal))
            else:
                transaction = functools.partial(self.near_move_balance_token, url, contract_id, key, by_address, to_address, int(amount*10**coin_decimal))
            send_tx = await self.bot.loop.run_in_executor(None, transaction)
            if send_tx:
                tx_json = None
                try:
                    tx_json = json.dumps(send_tx)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ INSERT INTO `near_external_tx` (`token_name`, `contract`, `user_id`, `real_amount`, `real_external_fee`, `token_decimal`, `to_address`, `date`, `tx_hash`, `tx_json`, `user_server`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (
                        coin.upper(), None, user_from, amount, withdraw_fee, coin_decimal, to_address,
                        int(time.time()), send_tx['transaction_outcome']['id'], tx_json, user_server))
                        await conn.commit()
                        return send_tx['transaction_outcome']['id']
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def near_get_mv_deposit_list(self, status: str="PENDING"):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                              FROM `near_move_deposit` 
                              WHERE `status`=%s """
                    await cur.execute(sql, status)
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def near_update_mv_deposit_pending(self, txn: str, blockNumber: int, confirmed_depth: int):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `near_move_deposit` 
                              SET `blockNumber`=%s, `status`=%s, `confirmations`=%s 
                              WHERE `status`=%s AND `txn`=%s LIMIT 1 """
                    await cur.execute(sql, (blockNumber, "CONFIRMED", confirmed_depth, "PENDING", txn))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def near_update_mv_gas(self, address: str, ts: int):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `near_user` 
                              SET `last_moved_gas`=%s 
                              WHERE `balance_wallet_address`=%s LIMIT 1 """
                    await cur.execute(sql, (ts, address))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def xrp_insert_deposit(self, coin_name: str, issuer: str, user_id: str, txid: str, height: int, timestamp: int, amount: float, decimal: int, address: str, destination_tag: int, time_insert: int):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT IGNORE INTO `xrp_get_transfers` (`coin_name`, `issuer`, `user_id`, `txid`, 
                              `height`, `timestamp`, `amount`, `decimal`, `address`, `destination_tag`, `time_insert`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (coin_name, issuer, user_id, txid, height, timestamp, amount, decimal, address, destination_tag, time_insert))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def xrp_get_user_by_tag(self, tag: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                              FROM `xrp_user` 
                              WHERE `destination_tag`=%s LIMIT 1 """
                    await cur.execute(sql, tag)
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def xrp_get_list_xrp_get_transfers(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT `txid` 
                              FROM `xrp_get_transfers` """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result:
                        return [each['txid'] for each in result]
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def send_external_xrp(self, url: str, seed: str, user_from: str, to_address: str, amount: float, withdraw_fee: float, coin: str, issuer: str, currency_code: str, coin_decimal: int, user_server: str):
        try:
            async_client = AsyncJsonRpcClient(url)
            main_walllet = xrpl.wallet.Wallet(seed, 0)

            current_validated_ledger = await get_latest_validated_ledger_sequence(async_client)
            main_walllet.sequence = await get_next_valid_seq_number(main_walllet.classic_address, async_client)

            fee = await get_fee(async_client)
            # prepare the transaction
            # see https://xrpl.org/basic-data-types.html#specifying-currency-amounts
            if coin.upper() == "XRP":
                my_tx_payment = Payment(
                    account=main_walllet.classic_address,
                    amount=str(int(amount*10**6)), # XRP: 6 decimal
                    destination=to_address,
                    last_ledger_sequence=current_validated_ledger + 20,
                    sequence=main_walllet.sequence,
                    fee=fee
                )
            else:
                my_tx_payment = Payment(
                    account=main_walllet.classic_address,
                    destination=to_address,
                    amount=xrpl.models.amounts.issued_currency_amount.IssuedCurrencyAmount(
                        currency=currency_code,
                        issuer=issuer,
                        value=str(truncate(float(amount), 2)) # Try with 2
                    ),
                    flags=xrpl.models.PaymentFlagInterface(
                        tf_partial_payment=True,
                    ),
                    send_max=xrpl.models.amounts.issued_currency_amount.IssuedCurrencyAmount(
                        currency=currency_code,
                        issuer=issuer,
                        value=str(truncate(float(amount), 2)) # Try with 2
                    ),
                    last_ledger_sequence=current_validated_ledger + 20,
                    sequence=main_walllet.sequence,
                    fee=fee,
                )
            # sign the transaction
            my_tx_payment_signed = await safe_sign_transaction(my_tx_payment, main_walllet, async_client)

            # submit the transaction
            send_tx = await send_reliable_submission(my_tx_payment_signed, async_client)
            if send_tx:
                if send_tx.result['meta']['TransactionResult'] != "tesSUCCESS":
                    return None
                contents = None
                native_fee = float(int(send_tx.result['Fee'])/10**6) # XPR: Decimal 6
                try:
                    contents = json.dumps(send_tx.result)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ INSERT INTO `xrp_external_tx` (`coin_name`, `issuer`, `user_id`, `amount`, `tx_fee`, `native_fee`, `decimal`, `to_address`, `date`, `txid`, `contents`, `user_server`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (
                        coin.upper(), issuer, user_from, amount, withdraw_fee, native_fee, coin_decimal, to_address,
                        int(time.time()), send_tx.result['hash'], contents, user_server))
                        await conn.commit()
                        return send_tx.result['hash']
        except Exception:
            traceback.print_exc(file=sys.stdout)

    def zil_transfer_native(self, to_address: str, from_key: str, amount: float, timeout: int=300):
        try:
            zil_chain.set_active_chain(zil_chain.MainNet)
            account = Zil_Account(private_key=from_key)
            balance = account.get_balance()
            min_gas = Qa(zil_chain.active_chain.api.GetMinimumGasPrice())
            txn_info = account.transfer(to_addr=to_address, zils=amount, gas_price=min_gas, gas_limit=50) # real amount in zils
            txn_id = txn_info["TranID"]
            txn_details = account.wait_txn_confirm(txn_id, timeout=timeout)
            if txn_details and txn_details["receipt"]["success"]:
                return txn_details
            else:
                print("Txn failed: {}".format(txn_id))
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    def zil_transfer_token(self, contract_addr: str, to_address: str, from_key: str, atomic_amount: int):
        try:
            zil_chain.set_active_chain(zil_chain.MainNet)
            account = Zil_Account(private_key=from_key)
            contract = zil_contract.load_from_address(contract_addr)
            contract.account = account
            to_account = Zil_Account(address=to_address)
            resp = contract.call(method="Transfer", params=[zil_contract.value_dict("to", "ByStr20", to_account.address0x), zil_contract.value_dict("amount", "Uint128", str(atomic_amount))])
            return resp
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def zil_insert_mv_balance(self, token_name: str, contract: str, user_id: str, balance_wallet_address: str, to_main_address: str, real_amount: float, real_deposit_fee: float, token_decimal: int, txn: str, content: str, time_insert: int, user_server: str, network: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT IGNORE INTO `zil_move_deposit` (`token_name`, `contract`, `user_id`, `balance_wallet_address`, 
                              `to_main_address`, `real_amount`, `real_deposit_fee`, `token_decimal`, `txn`, `content`, `time_insert`, 
                              `user_server`, `network`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (token_name, contract, user_id, balance_wallet_address, to_main_address, real_amount, real_deposit_fee, token_decimal, txn, content, time_insert, user_server, network))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def zil_get_user_by_address(self, address: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                              FROM `zil_user` 
                              WHERE `balance_wallet_address`=%s LIMIT 1 """
                    await cur.execute(sql, address)
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def zil_update_mv_gas(self, address: str, ts: int):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `zil_user` 
                              SET `last_moved_gas`=%s 
                              WHERE `balance_wallet_address`=%s LIMIT 1 """
                    await cur.execute(sql, (ts, address))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def zil_get_mv_deposit_list(self, status: str="PENDING"):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                              FROM `zil_move_deposit` 
                              WHERE `status`=%s """
                    await cur.execute(sql, status)
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def zil_update_mv_deposit_pending(self, txn: str, blockNumber: int, confirmed_depth: int):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `zil_move_deposit` 
                              SET `blockNumber`=%s, `status`=%s, `confirmed_depth`=%s 
                              WHERE `status`=%s AND `txn`=%s LIMIT 1 """
                    await cur.execute(sql, (blockNumber, "CONFIRMED", confirmed_depth, "PENDING", txn))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def send_external_zil(self, key: str, user_from: str, amount: float, to_address: str, coin: str,
                                coin_decimal: int, withdraw_fee: float, network: str, user_server: str = 'DISCORD'):
        try:
            transaction = functools.partial(self.zil_transfer_native, to_address, key, amount, 600)
            send_tx = await self.bot.loop.run_in_executor(None, transaction)
            if send_tx:
                contents = None
                try:
                    contents = json.dumps(send_tx)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ INSERT INTO `zil_external_tx` (`token_name`, `contract`, `user_id`, `real_amount`, `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, `contents`, `user_server`, `network`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (
                        coin.upper(), None, user_from, amount, withdraw_fee, coin_decimal, to_address,
                        int(time.time()), send_tx['ID'], contents, user_server, network))
                        await conn.commit()
                        return send_tx['ID']
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def send_external_zil_asset(self, contract: str, key: str, user_from: str, atomic_amount: int, to_address: str, coin: str,
                                      coin_decimal: int, withdraw_fee: float, network: str, user_server: str = 'DISCORD'):
        try:
            transaction = functools.partial(self.zil_transfer_token, contract, to_address, key, atomic_amount)
            send_tx = await self.bot.loop.run_in_executor(None, transaction)
            if send_tx:
                contents = None
                try:
                    contents = json.dumps(send_tx)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ INSERT INTO `zil_external_tx` (`token_name`, `contract`, `user_id`, `real_amount`, `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, `contents`, `user_server`, `network`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (
                        coin.upper(), contract, user_from, float(atomic_amount / 10 ** coin_decimal), withdraw_fee, coin_decimal, to_address,
                        int(time.time()), send_tx['ID'], contents, user_server, network))
                        await conn.commit()
                        return send_tx['ID']
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def vet_insert_mv_balance(self, token_name: str, contract: str, user_id: str, balance_wallet_address: str, to_main_address: str, real_amount: float, real_deposit_fee: float, token_decimal: int, txn: str, content: str, time_insert: int, user_server: str, network: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT IGNORE INTO `vet_move_deposit` (`token_name`, `contract`, `user_id`, `balance_wallet_address`, 
                              `to_main_address`, `real_amount`, `real_deposit_fee`, `token_decimal`, `txn`, `content`, `time_insert`, 
                              `user_server`, `network`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (token_name, contract, user_id, balance_wallet_address, to_main_address, real_amount, real_deposit_fee, token_decimal, txn, content, time_insert, user_server, network))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def vet_get_mv_deposit_list(self, status: str="PENDING"):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                              FROM `vet_move_deposit` 
                              WHERE `status`=%s """
                    await cur.execute(sql, status)
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def vet_update_mv_deposit_pending(self, txn: str, blockNumber: int, content: str, confirmed_depth: int):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `vet_move_deposit` 
                              SET `blockNumber`=%s, `status`=%s, `confirmed_depth`=%s, `content`=%s 
                              WHERE `status`=%s AND `txn`=%s LIMIT 1 """
                    await cur.execute(sql, (blockNumber, "CONFIRMED", confirmed_depth, content, "PENDING", txn))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def insert_external_vet(self, user_from: str, amount: float, to_address: str, coin: str, contract: str, 
                                  coin_decimal: int, withdraw_fee: float, tx_hash: str, network: str, user_server: str = 'DISCORD'):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `vet_external_tx` (`token_name`, `contract`, `user_id`, `real_amount`, `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, `contents`, `user_server`, `network`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (
                    coin.upper(), contract, user_from, amount, withdraw_fee, coin_decimal, to_address,
                    int(time.time()), tx_hash, None, user_server, network))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def insert_external_vite(self, user_from: str, amount: float, to_address: str, coin: str, contract: str, 
                                   coin_decimal: int, withdraw_fee: float, tx_hash: str, contents: str, user_server: str = 'DISCORD'):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `vite_external_tx` (`coin_name`, `contract`, `user_id`, `amount`, `withdraw_fee`, `decimal`, `to_address`, `date`, `tx_hash`, `contents`, `user_server`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (
                    coin.upper(), contract, user_from, amount, withdraw_fee, coin_decimal, to_address,
                    int(time.time()), tx_hash, contents, user_server))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

class Wallet(commands.Cog):
    def __init__(self, bot):
        self.enable_logchan = True
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)

        self.botLogChan = None

        redis_utils.openRedis()

        # Swap
        self.swap_pair = {"WRKZ-BWRKZ": 1, "BWRKZ-WRKZ": 1, "WRKZ-XWRKZ": 1, "XWRKZ-WRKZ": 1, "DEGO-WDEGO": 0.001,
                          "WDEGO-DEGO": 1000, "PGO-WPGO": 1, "WPGO-PGO": 1, "CDS-PCDS": 1, "PCDS-CDS": 1}
        # Donate
        self.donate_to = 386761001808166912  # pluton#8888

        # DB
        self.pool = None
        self.ttlcache = TTLCache(maxsize=1024, ttl=60.0)
        self.mv_xtz_cache = TTLCache(maxsize=1024, ttl=30.0)

    async def openConnection(self):
        try:
            if self.pool is None:
                self.pool = await aiomysql.create_pool(host=config.mysql.host, port=3306, minsize=3, maxsize=6,
                                                       user=config.mysql.user, password=config.mysql.password,
                                                       db=config.mysql.db, cursorclass=DictCursor, autocommit=True)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def swaptoken_list(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_swap_tokens` WHERE `enable`=%s """
                    await cur.execute(sql, (1))
                    result = await cur.fetchall()
                    if result: return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def swaptoken_check(self, from_token: str, to_token: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_swap_tokens` WHERE `enable`=%s AND `from_token`=%s AND `to_token`=%s LIMIT 1 """
                    await cur.execute(sql, (1, from_token, to_token))
                    result = await cur.fetchone()
                    if result: return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def swaptoken_purchase(self, list_tx):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO user_balance_mv (`token_name`, `contract`, `from_userid`, `to_userid`, `guild_id`, `channel_id`, `real_amount`, `token_decimal`, `type`, `date`, `user_server`, `real_amount_usd`, `extra_message`) 
                          VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s, %s, %s, %s, %s, %s);
                        
                          INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                          VALUES (%s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s) ON DUPLICATE KEY 
                          UPDATE 
                          `balance`=`balance`+VALUES(`balance`), 
                          `update_date`=VALUES(`update_date`);

                          INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                          VALUES (%s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s) ON DUPLICATE KEY 
                          UPDATE 
                          `balance`=`balance`+VALUES(`balance`), 
                          `update_date`=VALUES(`update_date`);
                              """
                    await cur.executemany(sql, list_tx)
                    await conn.commit()
                    return cur.rowcount
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return 0

    async def collect_claim_list(self, user_id: str, claim_type: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `user_balance_mv` WHERE `from_userid`=%s AND `type`=%s """
                    await cur.execute(sql, (user_id, claim_type))
                    result = await cur.fetchall()
                    if result: return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def check_withdraw_coin_address(self, coin_family: str, address: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    result = None
                    if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        sql = """ SELECT * FROM `cn_user_paymentid` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "CHIA":
                        sql = """ SELECT * FROM `xch_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "BTC":
                        # if doge family, address is paymentid
                        sql = """ SELECT * FROM `doge_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "NANO":
                        # if doge family, address is paymentid
                        sql = """ SELECT * FROM `nano_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "HNT":
                        # if doge family, address is paymentid
                        sql = """ SELECT * FROM `hnt_user` WHERE `main_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "ADA":
                        # if ADA family, address is paymentid
                        sql = """ SELECT * FROM `ada_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "SOL":
                        # if SOL family, address is paymentid
                        sql = """ SELECT * FROM `sol_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "ERC-20":
                        sql = """ SELECT * FROM `erc20_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "TRC-20":
                        sql = """ SELECT * FROM `trc20_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "XTZ":
                        sql = """ SELECT * FROM `tezos_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "ZIL":
                        sql = """ SELECT * FROM `zil_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    elif coin_family == "NEAR":
                        sql = """ SELECT * FROM `near_user` WHERE `balance_wallet_address`=%s LIMIT 1 """
                        await cur.execute(sql, (address))
                        result = await cur.fetchone()
                    return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return result

    async def swap_coin(self, user_id: str, from_coin: str, from_amount: float, from_contract: str, from_decimal: int,
                        to_coin: str, to_amount: float, to_contract: str, to_decimal: int, user_server: str):
        # 1] move to_amount to_coin from "SWAP" to user_id
        # 2] move from_amount from_coin from user_id to "SWAP"
        currentTs = int(time.time())
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO user_balance_mv 
                              (`token_name`, `contract`, `from_userid`, `to_userid`, `guild_id`, `channel_id`, `real_amount`, `real_amount_usd`, `token_decimal`, `type`, `date`, `user_server`) 
                              VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS DECIMAL(32,8)), CAST(%s AS DECIMAL(32,8)), %s, %s, %s, %s);

                              INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                              VALUES (%s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s) ON DUPLICATE KEY 
                              UPDATE 
                              `balance`=`balance`+VALUES(`balance`), 
                              `update_date`=VALUES(`update_date`);

                              INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                              VALUES (%s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s) ON DUPLICATE KEY 
                              UPDATE 
                              `balance`=`balance`+VALUES(`balance`), 
                              `update_date`=VALUES(`update_date`);


                              INSERT INTO user_balance_mv 
                              (`token_name`, `contract`, `from_userid`, `to_userid`, `guild_id`, `channel_id`, `real_amount`, `real_amount_usd`, `token_decimal`, `type`, `date`, `user_server`) 
                              VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS DECIMAL(32,8)), CAST(%s AS DECIMAL(32,8)), %s, %s, %s, %s);

                              INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                              VALUES (%s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s) ON DUPLICATE KEY 
                              UPDATE 
                              `balance`=`balance`+VALUES(`balance`), 
                              `update_date`=VALUES(`update_date`);

                              INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                              VALUES (%s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s) ON DUPLICATE KEY 
                              UPDATE 
                              `balance`=`balance`+VALUES(`balance`), 
                              `update_date`=VALUES(`update_date`);
                              """
                    await cur.execute(sql, (
                    to_coin.upper(), to_contract, "SWAP", user_id, "SWAP", "SWAP", to_amount, 0.0, to_decimal, "SWAP",
                    currentTs, user_server, "SWAP", to_coin.upper(), user_server, -to_amount, currentTs, user_id,
                    to_coin.upper(), user_server, to_amount, currentTs, from_coin.upper(), from_contract, user_id,
                    "SWAP", "SWAP", "SWAP", from_amount, 0.0, from_decimal, "SWAP", currentTs, user_server, user_id,
                    from_coin.upper(), user_server, -from_amount, currentTs, "SWAP", from_coin.upper(), user_server,
                    from_amount, currentTs))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet swap_coin " + str(traceback.format_exc()))
        return None

    def check_address_erc20(self, address: str):
        if is_hex_address(address):
            return address
        return False

    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)

    @tasks.loop(seconds=60.0)
    async def monitoring_tweet_mentioned_command(self):
        time_lap = 15  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "monitoring_tweet_mentioned_command"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        async def invalidate_mentioned(twitter_id: int):
            try:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ UPDATE `twitter_mentions_timeline` SET `response_date`=%s WHERE `twitter_id`=%s LIMIT 1 """
                        await cur.execute(sql, (int(time.time()), twitter_id))
                        await conn.commit()
            except Exception:
                traceback.print_exc(file=sys.stdout)

        async def response_tip(twitter_id: int, tipped_text: str):
            try:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ UPDATE `twitter_mentions_timeline` SET `has_tip`=1, `tipped_text`=%s, `response_date`=%s WHERE `twitter_id`=%s LIMIT 1 """
                        await cur.execute(sql, (tipped_text, int(time.time()), twitter_id))
                        await conn.commit()
            except Exception:
                traceback.print_exc(file=sys.stdout)

        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `twitter_mentions_timeline` 
                              WHERE `response_date` IS NULL 
                              ORDER BY `created_at` ASC """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each_resp in result:
                            if each_resp['user_mentions_list'] is None:
                                await invalidate_mentioned(each_resp['twitter_id'])
                                continue
                            if len(json.loads(each_resp['user_mentions_list'])) <= 1:
                                # no one to tip to
                                await invalidate_mentioned(each_resp['twitter_id'])
                                continue
                            elif len(json.loads(each_resp['user_mentions_list'])) > 1:
                                text = each_resp['text'].replace("@BotTipsTweet", "").strip().upper()
                                arg = text.split()
                                if len(arg) < 4 or not text.startswith("TIP "):
                                    await invalidate_mentioned(each_resp['twitter_id'])
                                    continue
                                elif text.startswith("TIP ") and len(arg) >= 4:
                                    amount = arg[1]
                                    coin_name = arg[2].replace("#", "")
                                    if not hasattr(self.bot.coin_list, coin_name):
                                        await invalidate_mentioned(each_resp['twitter_id'])
                                        continue
                                    else:
                                        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                                        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                                        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name),
                                                                        "deposit_confirm_depth")
                                        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                        contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                                        token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")

                                        min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
                                        max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
                                        usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name),
                                                                        "usd_equivalent_enable")
                                        if "$" in amount[-1] or "$" in amount[0]:  # last is $
                                            # Check if conversion is allowed for this coin.
                                            amount = amount.replace(",", "").replace("$", "")
                                            if usd_equivalent_enable == 0:
                                                await invalidate_mentioned(each_resp['twitter_id'])
                                                continue
                                            else:
                                                native_token_name = getattr(getattr(self.bot.coin_list, coin_name),
                                                                            "native_token_name")
                                                coin_name_for_price = coin_name
                                                if native_token_name:
                                                    coin_name_for_price = native_token_name
                                                per_unit = None
                                                if coin_name_for_price in self.bot.token_hints:
                                                    id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                                                    per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                                                else:
                                                    per_unit = self.bot.coin_paprika_symbol_list[coin_name_for_price][
                                                        'price_usd']
                                                if per_unit and per_unit > 0:
                                                    amount = float(Decimal(amount) / Decimal(per_unit))
                                                else:
                                                    await invalidate_mentioned(each_resp['twitter_id'])
                                                    continue
                                        else:
                                            amount = amount.replace(",", "")
                                            amount = text_to_num(amount)
                                            if amount is None:
                                                await invalidate_mentioned(each_resp['twitter_id'])
                                                continue

                                        get_deposit = await self.sql_get_userwallet(str(each_resp['twitter_user_id']),
                                                                                    coin_name, net_name, type_coin,
                                                                                    "TWITTER", 0)
                                        if get_deposit is None:
                                            get_deposit = await self.sql_register_user(
                                                str(each_resp['twitter_user_id']), coin_name, net_name, type_coin,
                                                "TWITTER", 0, 0)

                                        wallet_address = get_deposit['balance_wallet_address']
                                        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                            wallet_address = get_deposit['paymentid']
                                        elif type_coin in ["XRP"]:
                                            wallet_address = get_deposit['destination_tag']
                                        height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                                        userdata_balance = await store.sql_user_balance_single(
                                            str(each_resp['twitter_user_id']), coin_name, wallet_address, type_coin,
                                            height, deposit_confirm_depth, "TWITTER")
                                        actual_balance = float(userdata_balance['adjust'])
                                        if amount > max_tip or amount < min_tip or amount > actual_balance:
                                            await invalidate_mentioned(each_resp['twitter_id'])
                                            continue
                                        else:
                                            list_receivers = json.loads(each_resp['user_mentions_list'])
                                            list_users = []
                                            for each_u in list_receivers:
                                                try:
                                                    key_coin = each_u['id_str'] + "_" + coin_name + "_" + "TWITTER"
                                                    if key_coin in self.bot.user_balance_cache:
                                                        del self.bot.user_balance_cache[key_coin]
                                                except Exception:
                                                    pass
                                                if each_u['id_str'] not in ["1343104498722467845", str(
                                                        each_resp['twitter_user_id'])]:  # BotTipsTweet, twitter user
                                                    list_users.append(each_u['id_str'])
                                            if len(list_users) == 0:
                                                await invalidate_mentioned(each_resp['twitter_id'])
                                                continue
                                            else:
                                                for each in list_users:
                                                    try:
                                                        to_user = await self.sql_get_userwallet(each, coin_name,
                                                                                                net_name, type_coin,
                                                                                                "TWITTER", 0)
                                                        if to_user is None:
                                                            to_user = await self.sql_register_user(each, coin_name,
                                                                                                   net_name, type_coin,
                                                                                                   "TWITTER", 0, 0)
                                                    except Exception:
                                                        traceback.print_exc(file=sys.stdout)
                                                total_amount = len(list_users) * amount
                                                if total_amount > actual_balance:
                                                    await invalidate_mentioned(each_resp['twitter_id'])
                                                    continue
                                                else:
                                                    equivalent_usd = ""
                                                    amount_in_usd = 0.0
                                                    per_unit = None
                                                    if usd_equivalent_enable == 1:
                                                        native_token_name = getattr(
                                                            getattr(self.bot.coin_list, coin_name), "native_token_name")
                                                        coin_name_for_price = coin_name
                                                        if native_token_name:
                                                            coin_name_for_price = native_token_name
                                                        if coin_name_for_price in self.bot.token_hints:
                                                            id = self.bot.token_hints[coin_name_for_price][
                                                                'ticker_name']
                                                            per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                                                        else:
                                                            per_unit = \
                                                            self.bot.coin_paprika_symbol_list[coin_name_for_price][
                                                                'price_usd']
                                                        if per_unit and per_unit > 0:
                                                            amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                                                            if amount_in_usd > 0.0001:
                                                                equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)
                                                    try:
                                                        tw_tip = await store.sql_user_balance_mv_multiple(
                                                            str(each_resp['twitter_user_id']), list_users, "TWITTER",
                                                            "TWITTER", amount, coin_name, "TWITTERTIP", coin_decimal,
                                                            "TWITTER", contract, float(amount_in_usd),
                                                            each_resp['text'])
                                                        await response_tip(each_resp['twitter_id'], each_resp['text'])
                                                    except Exception:
                                                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def monitoring_tweet_command(self):
        time_lap = 15  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "monitoring_tweet_command"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        async def update_bot_response(original_text: str, response: str, dm_id: int):
            try:
                response_text = f"\"{original_text}\"" + "\n\n" + response
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ UPDATE `twitter_fetch_bot_messages` 
                                  SET `draft_response_text`=%s WHERE `draft_response_text` IS NULL AND `id`=%s LIMIT 1
                              """
                        await cur.execute(sql, (response_text, dm_id))
                        await conn.commit()
            except Exception:
                traceback.print_exc(file=sys.stdout)

        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `twitter_fetch_bot_messages` 
                              WHERE `is_ignored`=0 AND `draft_response_text` IS NULL 
                              ORDER BY `created_timestamp` ASC """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each_msg in result:
                            # Ignore long DM
                            if each_msg['text'] and len(each_msg['text']) > 500:
                                sql = """ UPDATE `twitter_fetch_bot_messages` 
                                          SET `is_ignored`=%s, `ignored_date`=%s WHERE `id`=%s LIMIT 1
                                      """
                                await cur.execute(sql, (1, int(time.time()), each_msg['id']))
                                await conn.commit()
                                continue
                            if each_msg['text'].lower().startswith(("deposit all", "depositall")):
                                try:
                                    mytokens = await store.get_coin_settings(coin_type=None)
                                    all_names = [each['coin_name'] for each in mytokens if each['enable_twitter'] == 1]
                                    address_of_coins = {}
                                    addresses_text = []
                                    address_lines = []
                                    for coin_name in all_names:
                                        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                                        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                                        if getattr(getattr(self.bot.coin_list, coin_name), "enable_deposit") == 1:
                                            get_deposit = await self.sql_get_userwallet(each_msg['sender_id'],
                                                                                        coin_name, net_name, type_coin,
                                                                                        "TWITTER", 0)
                                            if get_deposit is None:
                                                get_deposit = await self.sql_register_user(each_msg['sender_id'],
                                                                                           coin_name, net_name,
                                                                                           type_coin, "TWITTER", 0, 0)
                                            wallet_address = get_deposit['balance_wallet_address']
                                            address_of_coins[coin_name] = wallet_address
                                    for key, value in address_of_coins.items():
                                        keys = [k for k, v in address_of_coins.items() if v == value]
                                        if keys not in addresses_text:
                                            addresses_text.append(keys)
                                            address_lines.append("{}: {}".format(", ".join(keys), value))
                                    address_lines_str = "\n\n".join(address_lines)
                                    response = "Your deposited address:\n" + address_lines_str + "\n\nPlease refer to https://coininfo.bot.tips for each coin's information."
                                    await update_bot_response(each_msg['text'], response, each_msg['id'])
                                    continue
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            elif each_msg['text'].lower().startswith("deposit "):
                                coin_name = each_msg['text'].upper().replace("DEPOSIT ", "").strip()
                                if len(coin_name) > 0 and not hasattr(self.bot.coin_list, coin_name) or getattr(
                                        getattr(self.bot.coin_list, coin_name), "enable_twitter") != 1:
                                    response = f"{coin_name} does not exist with us. Check https://coininfo.bot.tips"
                                    await update_bot_response(each_msg['text'], response, each_msg['id'])
                                    continue
                                elif len(coin_name) > 0 and hasattr(self.bot.coin_list, coin_name):
                                    net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                                    type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                                    if getattr(getattr(self.bot.coin_list, coin_name),
                                               "enable_deposit") == 1 and getattr(
                                            getattr(self.bot.coin_list, coin_name), "enable_twitter") == 1:
                                        get_deposit = await self.sql_get_userwallet(each_msg['sender_id'], coin_name,
                                                                                    net_name, type_coin, "TWITTER", 0)
                                        if get_deposit is None:
                                            get_deposit = await self.sql_register_user(each_msg['sender_id'], coin_name,
                                                                                       net_name, type_coin, "TWITTER",
                                                                                       0, 0)
                                        wallet_address = get_deposit['balance_wallet_address']
                                        if coin_name == "HNT":  # put memo and base64
                                            address_memo = wallet_address.split()
                                            address = address_memo[0]
                                            memo_ascii = address_memo[2]
                                            response = f"Your {coin_name} deposited address: {address}, memo: {memo_ascii}"
                                            await update_bot_response(each_msg['text'], response, each_msg['id'])
                                        else:
                                            response = f"Your {coin_name} deposited address: {wallet_address}"
                                            await update_bot_response(each_msg['text'], response, each_msg['id'])
                                    else:
                                        response = f"{coin_name} is not available for deposit or not available for twitter yet."
                                        await update_bot_response(each_msg['text'], response, each_msg['id'])
                                else:
                                    response = f"{coin_name} invalid coin name. Check https://coininfo.bot.tips"
                                    await update_bot_response(each_msg['text'], response, each_msg['id'])
                                continue
                            elif each_msg['text'].lower().startswith("balance"):
                                try:
                                    zero_tokens = []
                                    non_zero_tokens = {}
                                    mytokens = await store.get_coin_settings(coin_type=None)
                                    all_names = [each['coin_name'] for each in mytokens if each['enable_twitter'] == 1]
                                    for coin_name in all_names:
                                        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                                        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                                        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name),
                                                                        "deposit_confirm_depth")
                                        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                        token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                                        if getattr(getattr(self.bot.coin_list, coin_name), "enable_deposit") == 1:
                                            get_deposit = await self.sql_get_userwallet(each_msg['sender_id'],
                                                                                        coin_name, net_name, type_coin,
                                                                                        "TWITTER", 0)
                                            if get_deposit is None:
                                                get_deposit = await self.sql_register_user(each_msg['sender_id'],
                                                                                           coin_name, net_name,
                                                                                           type_coin, "TWITTER", 0, 0)
                                            wallet_address = get_deposit['balance_wallet_address']
                                            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                                wallet_address = get_deposit['paymentid']
                                            elif type_coin in ["XRP"]:
                                                wallet_address = get_deposit['destination_tag']
                                            height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                                        userdata_balance = await self.wallet_api.user_balance(each_msg['sender_id'], coin_name,
                                                                                              wallet_address, type_coin, height,
                                                                                              deposit_confirm_depth, "TWITTER")
                                        total_balance = userdata_balance['adjust']
                                        if total_balance == 0:
                                            zero_tokens.append(coin_name)
                                        elif total_balance > 0:
                                            non_zero_tokens[coin_name] = num_format_coin(total_balance, coin_name,
                                                                                         coin_decimal,
                                                                                         False) + " " + token_display
                                    if len(zero_tokens) == len(all_names):
                                        response = "You do not have any balance. Please DEPOSIT"
                                        await update_bot_response(each_msg['text'], response, each_msg['id'])
                                        continue
                                    elif len(zero_tokens) < len(all_names):
                                        response = "Your coin/tokens's balance:\n"
                                        for k, v in non_zero_tokens.items():
                                            response += "{}: {}\n".format(k, v)
                                        response += "\nZero balance coin/tokens: {}".format(", ".join(zero_tokens))
                                        await update_bot_response(each_msg['text'], response, each_msg['id'])
                                        continue
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            elif each_msg['text'].lower().startswith("withdraw "):
                                arg = each_msg['text'].split()
                                if len(arg) != 4:
                                    response = "Invalid command. Try: withdraw 10 doge D6QP5XhXvqosso2dk8yRrFrwvH9UUEGP9z"
                                    await update_bot_response(each_msg['text'], response, each_msg['id'])
                                    continue
                                else:
                                    amount = arg[1]
                                    coin_name = arg[2].upper().replace("#", "")
                                    address = arg[3]
                                    if not hasattr(self.bot.coin_list, coin_name) or getattr(
                                            getattr(self.bot.coin_list, coin_name), "enable_twitter") != 1:
                                        response = f"{coin_name} not exist with us! Check https://coininfo.bot.tips/"
                                        await update_bot_response(each_msg['text'], response, each_msg['id'])
                                        continue
                                    else:
                                        user_server = "TWITTER"
                                        try:
                                            tw_user = each_msg['sender_id']
                                            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                                            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                                            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name),
                                                                            "deposit_confirm_depth")
                                            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                            min_tx = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tx")
                                            max_tx = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tx")
                                            NetFee = getattr(getattr(self.bot.coin_list, coin_name),
                                                             "real_withdraw_fee")
                                            tx_fee = getattr(getattr(self.bot.coin_list, coin_name), "tx_fee")
                                            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name),
                                                                            "usd_equivalent_enable")

                                            try:
                                                check_exist = await self.check_withdraw_coin_address(type_coin, address)
                                                if check_exist is not None:
                                                    response = f"You can not send to this address: {address}."
                                                    await update_bot_response(each_msg['text'], response,
                                                                              each_msg['id'])
                                                    continue
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)

                                            if tx_fee is None:
                                                tx_fee = NetFee
                                            token_display = getattr(getattr(self.bot.coin_list, coin_name),
                                                                    "display_name")
                                            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                                            fee_limit = getattr(getattr(self.bot.coin_list, coin_name), "fee_limit")
                                            get_deposit = await self.sql_get_userwallet(each_msg['sender_id'],
                                                                                        coin_name, net_name, type_coin,
                                                                                        user_server, 0)
                                            if get_deposit is None:
                                                get_deposit = await self.sql_register_user(each_msg['sender_id'],
                                                                                           coin_name, net_name,
                                                                                           type_coin, user_server, 0, 0)

                                            wallet_address = get_deposit['balance_wallet_address']
                                            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                                wallet_address = get_deposit['paymentid']
                                            elif type_coin in ["XRP"]:
                                                wallet_address = get_deposit['destination_tag']

                                            height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                                            if height is None:
                                                # can not pull height, continue
                                                await logchanbot(
                                                    f"[{user_server}] - Execute withdraw for `{tw_user}` but can not pull height of {coin_name}.")
                                                continue

                                            # check if amount is all
                                            all_amount = False
                                            if not amount.isdigit() and amount.upper() == "ALL":
                                                all_amount = True
                                                userdata_balance = await self.wallet_api.user_balance(each_msg['sender_id'],
                                                                                                      coin_name, wallet_address,
                                                                                                      type_coin, height,
                                                                                                      deposit_confirm_depth,
                                                                                                      user_server)
                                                amount = float(userdata_balance['adjust']) - NetFee
                                            # If $ is in amount, let's convert to coin/token
                                            elif "$" in amount[-1] or "$" in amount[0]:  # last is $
                                                # Check if conversion is allowed for this coin.
                                                amount = amount.replace(",", "").replace("$", "")
                                                if usd_equivalent_enable == 0:
                                                    response = f"Dollar conversion is not enabled for this {coin_name}."
                                                    await update_bot_response(each_msg['text'], response,
                                                                              each_msg['id'])
                                                    continue
                                                else:
                                                    native_token_name = getattr(getattr(self.bot.coin_list, coin_name),
                                                                                "native_token_name")
                                                    coin_name_for_price = coin_name
                                                    if native_token_name:
                                                        coin_name_for_price = native_token_name
                                                    per_unit = None
                                                    if coin_name_for_price in self.bot.token_hints:
                                                        id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                                                        per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                                                    else:
                                                        per_unit = \
                                                        self.bot.coin_paprika_symbol_list[coin_name_for_price][
                                                            'price_usd']
                                                    if per_unit and per_unit > 0:
                                                        amount = float(Decimal(amount) / Decimal(per_unit))
                                                    else:
                                                        response = f"I cannot fetch equivalent price. Try with different method for this {coin_name}."
                                                        await update_bot_response(each_msg['text'], response,
                                                                                  each_msg['id'])
                                                        continue
                                            else:
                                                amount = amount.replace(",", "")
                                                amount = text_to_num(amount)
                                                if amount is None:
                                                    response = f"Invalid given amount. for this {coin_name}."
                                                    await update_bot_response(each_msg['text'], response,
                                                                              each_msg['id'])
                                                    continue

                                            if getattr(getattr(self.bot.coin_list, coin_name),
                                                       "integer_amount_only") == 1:
                                                amount = int(amount)

                                            # end of check if amount is all
                                            amount = float(amount)
                                            userdata_balance = await self.wallet_api.user_balance(each_msg['sender_id'], coin_name,
                                                                                                  wallet_address, type_coin,
                                                                                                  height, deposit_confirm_depth,
                                                                                                  user_server)
                                            actual_balance = float(userdata_balance['adjust'])

                                            # If balance 0, no need to check anything
                                            if actual_balance <= 0:
                                                response = f"Please check your **{token_display}** balance."
                                                await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                continue
                                            if amount > actual_balance:
                                                response = f"Insufficient balance to send out {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}."
                                                await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                continue

                                            if amount + NetFee > actual_balance:
                                                response = f'Insufficient balance to send out {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}. You need to leave at least network fee: {num_format_coin(NetFee, coin_name, coin_decimal, False)} {token_display}.'
                                                await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                continue

                                            elif amount < min_tx or amount > max_tx:
                                                response = f'Transaction cannot be smaller than {num_format_coin(min_tx, coin_name, coin_decimal, False)} {token_display} or bigger than {num_format_coin(max_tx, coin_name, coin_decimal, False)} {token_display}.'
                                                await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                continue
                                            equivalent_usd = ""
                                            total_in_usd = 0.0
                                            per_unit = None
                                            if usd_equivalent_enable == 1:
                                                native_token_name = getattr(getattr(self.bot.coin_list, coin_name),
                                                                            "native_token_name")
                                                coin_name_for_price = coin_name
                                                if native_token_name:
                                                    coin_name_for_price = native_token_name
                                                if coin_name_for_price in self.bot.token_hints:
                                                    id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                                                    per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                                                else:
                                                    per_unit = self.bot.coin_paprika_symbol_list[coin_name_for_price][
                                                        'price_usd']
                                                if per_unit and per_unit > 0:
                                                    total_in_usd = float(Decimal(amount) * Decimal(per_unit))
                                                    if total_in_usd >= 0.0001:
                                                        equivalent_usd = " ~ {:,.4f} USD".format(total_in_usd)

                                            if type_coin in ["ERC-20"]:
                                                # Check address
                                                valid_address = self.check_address_erc20(address)
                                                valid = False
                                                if valid_address and valid_address.upper() == address.upper():
                                                    valid = True
                                                else:
                                                    response = f"Invalid address:\n {address} "
                                                    await update_bot_response(each_msg['text'], response,
                                                                              each_msg['id'])
                                                    continue

                                                send_tx = None
                                                try:
                                                    url = self.bot.erc_node_list[net_name]
                                                    chain_id = getattr(getattr(self.bot.coin_list, coin_name),
                                                                       "chain_id")
                                                    send_tx = await self.send_external_erc20(url, net_name,
                                                                                            each_msg['sender_id'],
                                                                                            address, amount, coin_name,
                                                                                            coin_decimal, NetFee,
                                                                                            user_server, chain_id,
                                                                                            contract)
                                                except Exception:
                                                    traceback.print_exc(file=sys.stdout)
                                                    await logchanbot("wallet monitoring_tweet_command " + str(traceback.format_exc()))

                                                if send_tx:
                                                    fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                                        num_format_coin(NetFee, coin_name, coin_decimal, False),
                                                        coin_name)
                                                    try:
                                                        response = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                                                        await update_bot_response(each_msg['text'], response,
                                                                                  each_msg['id'])
                                                        continue
                                                    except Exception:
                                                        traceback.print_exc(file=sys.stdout)
                                                    try:
                                                        await logchanbot(
                                                            f'[{user_server}] A user {tw_user} sucessfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}')
                                                    except Exception:
                                                        traceback.print_exc(file=sys.stdout)
                                            elif type_coin in ["TRC-20", "TRC-10"]:
                                                # TODO: validate address
                                                send_tx = None
                                                try:
                                                    send_tx = await self.send_external_trc20(each_msg['sender_id'],
                                                                                            address, amount, coin_name,
                                                                                            coin_decimal, NetFee,
                                                                                            user_server, fee_limit,
                                                                                            type_coin, contract)
                                                except Exception:
                                                    traceback.print_exc(file=sys.stdout)
                                                    await logchanbot("wallet monitoring_tweet_command " + str(traceback.format_exc()))

                                                if send_tx:
                                                    fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                                        num_format_coin(NetFee, coin_name, coin_decimal, False),
                                                        coin_name)
                                                    response = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                                                    await update_bot_response(each_msg['text'], response,
                                                                              each_msg['id'])
                                                    await logchanbot(
                                                        f'[{user_server}] A user {tw_user} sucessfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}')
                                                    continue
                                            elif type_coin == "NANO":
                                                valid_address = await self.wallet_api.nano_validate_address(coin_name,
                                                                                                            address)
                                                if not valid_address is True:
                                                    response = f"Address: {address} is invalid."
                                                    await update_bot_response(each_msg['text'], response,
                                                                              each_msg['id'])
                                                    continue
                                                else:
                                                    try:
                                                        main_address = getattr(getattr(self.bot.coin_list, coin_name),
                                                                               "MainAddress")
                                                        send_tx = await self.wallet_api.send_external_nano(main_address,
                                                                                                          each_msg[
                                                                                                              'sender_id'],
                                                                                                          amount,
                                                                                                          address,
                                                                                                          coin_name,
                                                                                                          coin_decimal)
                                                        if send_tx:
                                                            fee_txt = "\nWithdrew fee/node: `0.00 {}`.".format(
                                                                coin_name)
                                                            SendTx_hash = send_tx['block']
                                                            response = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{SendTx_hash}`{fee_txt}'
                                                            await update_bot_response(each_msg['text'], response,
                                                                                      each_msg['id'])
                                                            await logchanbot(
                                                                f'A user {tw_user} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                                            continue
                                                        else:
                                                            await logchanbot(
                                                                f'[{user_server}] A user {tw_user} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                                    except Exception:
                                                        traceback.print_exc(file=sys.stdout)
                                                        await logchanbot("wallet monitoring_tweet_command " + str(traceback.format_exc()))
                                            elif type_coin == "CHIA":
                                                send_tx = await self.wallet_api.send_external_xch(each_msg['sender_id'],
                                                                                                 amount, address,
                                                                                                 coin_name,
                                                                                                 coin_decimal, tx_fee,
                                                                                                 NetFee, user_server)
                                                if send_tx:
                                                    fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                                        num_format_coin(NetFee, coin_name, coin_decimal, False),
                                                        coin_name)
                                                    response = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                                                    await update_bot_response(each_msg['text'], response,
                                                                              each_msg['id'])
                                                    await logchanbot(
                                                        f'[{user_server}] A user {tw_user} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                                    continue
                                                else:
                                                    await logchanbot(
                                                        f'[{user_server}] A user {tw_user} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                            elif type_coin == "HNT":
                                                wallet_host = getattr(getattr(self.bot.coin_list, coin_name),
                                                                      "wallet_address")
                                                main_address = getattr(getattr(self.bot.coin_list, coin_name),
                                                                       "MainAddress")
                                                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name),
                                                                       "decimal")
                                                password = decrypt_string(
                                                    getattr(getattr(self.bot.coin_list, coin_name), "walletkey"))
                                                send_tx = await self.wallet_api.send_external_hnt(each_msg['sender_id'],
                                                                                                 wallet_host, password,
                                                                                                 main_address, address,
                                                                                                 amount, coin_decimal,
                                                                                                 user_server, coin_name,
                                                                                                 NetFee, 32)
                                                if send_tx:
                                                    fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                                        num_format_coin(NetFee, coin_name, coin_decimal, False),
                                                        coin_name)
                                                    response = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                                                    await update_bot_response(each_msg['text'], response,
                                                                              each_msg['id'])
                                                    await logchanbot(
                                                        f'[{user_server}] A user {tw_user} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                                    continue
                                                else:
                                                    await logchanbot(
                                                        f'[{user_server}] [FAILED] A user {tw_user} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')

                                            elif type_coin == "ADA":
                                                if not address.startswith("addr1"):
                                                    response = f'Invalid address. It should start with `addr1`.'
                                                    await update_bot_response(each_msg['text'], response,
                                                                              each_msg['id'])
                                                    continue

                                                if coin_name == "ADA":
                                                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name),
                                                                           "decimal")
                                                    fee_limit = getattr(getattr(self.bot.coin_list, coin_name),
                                                                        "fee_limit")
                                                    # Use fee limit as NetFee
                                                    send_tx = await self.wallet_api.send_external_ada(
                                                        each_msg['sender_id'], amount, coin_decimal, user_server,
                                                        coin_name, fee_limit, address, 60)
                                                    if "status" in send_tx and send_tx['status'] == "pending":
                                                        tx_hash = send_tx['id']
                                                        fee = send_tx['fee']['quantity'] / 10 ** coin_decimal + fee_limit
                                                        fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                                            num_format_coin(fee, coin_name, coin_decimal, False),
                                                            coin_name)
                                                        response = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{tx_hash}`{fee_txt}'
                                                        await update_bot_response(each_msg['text'], response,
                                                                                  each_msg['id'])
                                                        await logchanbot(
                                                            f'[{user_server}] A user {tw_user} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                                        continue
                                                    elif "code" in send_tx and "message" in send_tx:
                                                        code = send_tx['code']
                                                        message = send_tx['message']
                                                        response = f'Internal error, please try again later!'
                                                        await update_bot_response(each_msg['text'], response,
                                                                                  each_msg['id'])
                                                        await logchanbot(
                                                            f'[{user_server}] [FAILED] A user {tw_user} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.```code: {code}\nmessage: {message}```')
                                                        continue
                                                    else:
                                                        response = f'Internal error, please try again later!'
                                                        await update_bot_response(each_msg['text'], response,
                                                                                  each_msg['id'])
                                                        await logchanbot(
                                                            f'[{user_server}] [FAILED] A user {tw_user} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                                        continue
                                                else:
                                                    ## 
                                                    # Check user's ADA balance.
                                                    GAS_COIN = None
                                                    fee_limit = None
                                                    try:
                                                        if getattr(getattr(self.bot.coin_list, coin_name),
                                                                   "withdraw_use_gas_ticker") == 1:
                                                            # add main token balance to check if enough to withdraw
                                                            GAS_COIN = getattr(getattr(self.bot.coin_list, coin_name),
                                                                               "gas_ticker")
                                                            fee_limit = getattr(getattr(self.bot.coin_list, coin_name),
                                                                                "fee_limit")
                                                            if GAS_COIN:
                                                                userdata_balance = await self.wallet_api.user_balance(
                                                                    each_msg['sender_id'], GAS_COIN, wallet_address,
                                                                    type_coin, height, getattr(getattr(self.bot.coin_list, GAS_COIN), "deposit_confirm_depth"), user_server)
                                                                actual_balance = userdata_balance['adjust']
                                                                if actual_balance < fee_limit:  # use fee_limit to limit ADA
                                                                    response = f'You do not have sufficient {GAS_COIN} to withdraw {coin_name}. You need to have at least a reserved `{fee_limit} {GAS_COIN}`.'
                                                                    await update_bot_response(each_msg['text'],
                                                                                              response, each_msg['id'])
                                                                    await logchanbot(
                                                                        f'[{user_server}] A user {tw_user} want to withdraw asset {coin_name} but having only {actual_balance} {GAS_COIN}.')
                                                                    continue
                                                            else:
                                                                response = 'Invalid main token, please report!'
                                                                await logchanbot(
                                                                    f'[{user_server}] [BUG] {tw_user} invalid main token for {coin_name}.')
                                                                await update_bot_response(each_msg['text'], response,
                                                                                          each_msg['id'])
                                                                continue
                                                    except Exception:
                                                        traceback.print_exc(file=sys.stdout)
                                                        response = 'I cannot check balance, please try again later!'
                                                        await logchanbot(
                                                            f'[{user_server}] A user {tw_user} failed to check balance gas coin for asset transfer...')
                                                        await update_bot_response(each_msg['text'], response,
                                                                                  each_msg['id'])
                                                        continue

                                                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name),
                                                                           "decimal")
                                                    asset_name = getattr(getattr(self.bot.coin_list, coin_name),
                                                                         "header")
                                                    policy_id = getattr(getattr(self.bot.coin_list, coin_name),
                                                                        "contract")
                                                    send_tx = await self.wallet_api.send_external_ada_asset(
                                                        each_msg['sender_id'], amount, coin_decimal, user_server,
                                                        coin_name, NetFee, address, asset_name, policy_id, 60)
                                                    if "status" in send_tx and send_tx['status'] == "pending":
                                                        tx_hash = send_tx['id']
                                                        gas_coin_msg = ""
                                                        if GAS_COIN is not None:
                                                            gas_coin_msg = " and fee `{} {}` you shall receive additional `{} {}`.".format(
                                                                num_format_coin(send_tx['network_fee'] + fee_limit / 20,
                                                                                GAS_COIN, 6, False), GAS_COIN,
                                                                num_format_coin(send_tx['ada_received'], GAS_COIN, 6,
                                                                                False), GAS_COIN)
                                                        fee_txt = "\nWithdrew fee/node: `{} {}`{}.".format(
                                                            num_format_coin(NetFee, coin_name, coin_decimal, False),
                                                            coin_name, gas_coin_msg)
                                                        response = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{tx_hash}`{fee_txt}'
                                                        await update_bot_response(each_msg['text'], response,
                                                                                  each_msg['id'])
                                                        await logchanbot(
                                                            f'[{user_server}] A user {tw_user} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                                        continue
                                                    elif "code" in send_tx and "message" in send_tx:
                                                        code = send_tx['code']
                                                        message = send_tx['message']
                                                        response = f'Internal error, please try again later!'
                                                        await logchanbot(
                                                            f'[{user_server}] [FAILED] A user {tw_user} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.```code: {code}\nmessage: {message}```')
                                                    else:
                                                        response = f'Internal error, please try again later!'
                                                        await update_bot_response(each_msg['text'], response,
                                                                                  each_msg['id'])
                                                        await logchanbot(
                                                            f'[{user_server}] [FAILED] A user {tw_user} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                                        continue
                                                    continue
                                            elif type_coin == "SOL" or type_coin == "SPL":
                                                tx_fee = getattr(getattr(self.bot.coin_list, coin_name), "tx_fee")
                                                send_tx = await self.wallet_api.send_external_sol(
                                                    self.bot.erc_node_list['SOL'], each_msg['sender_id'], amount,
                                                    address, coin_name, coin_decimal, tx_fee, NetFee, user_server)
                                                if send_tx:
                                                    fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                                        num_format_coin(NetFee, coin_name, coin_decimal, False),
                                                        coin_name)
                                                    response = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                                                    await update_bot_response(each_msg['text'], response,
                                                                              each_msg['id'])
                                                    await logchanbot(
                                                        f'[{user_server}] A user {tw_user} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                                    continue
                                                else:
                                                    await logchanbot(
                                                        f'[{user_server}] [FAILED] A user {tw_user} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                            elif type_coin == "BTC":
                                                send_tx = await self.wallet_api.send_external_doge(each_msg['sender_id'],
                                                                                                  amount, address,
                                                                                                  coin_name, 0, NetFee,
                                                                                                  user_server)  # tx_fee=0
                                                if send_tx:
                                                    fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                                        num_format_coin(NetFee, coin_name, coin_decimal, False),
                                                        coin_name)
                                                    response = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                                                    await update_bot_response(each_msg['text'], response,
                                                                              each_msg['id'])
                                                    await logchanbot(
                                                        f'[{user_server}] A user {tw_user} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                                    continue
                                                else:
                                                    await logchanbot(
                                                        f'[{user_server}] [FAILED] A user {tw_user} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                            elif type_coin == "XMR" or type_coin == "TRTL-API" or type_coin == "TRTL-SERVICE" or type_coin == "BCN":
                                                main_address = getattr(getattr(self.bot.coin_list, coin_name),
                                                                       "MainAddress")
                                                mixin = getattr(getattr(self.bot.coin_list, coin_name), "mixin")
                                                wallet_address = getattr(getattr(self.bot.coin_list, coin_name),
                                                                         "wallet_address")
                                                header = getattr(getattr(self.bot.coin_list, coin_name), "header")
                                                is_fee_per_byte = getattr(getattr(self.bot.coin_list, coin_name),
                                                                          "is_fee_per_byte")
                                                send_tx = await self.wallet_api.send_external_xmr(type_coin,
                                                                                                 main_address,
                                                                                                 each_msg['sender_id'],
                                                                                                 amount, address,
                                                                                                 coin_name,
                                                                                                 coin_decimal, tx_fee,
                                                                                                 NetFee,
                                                                                                 is_fee_per_byte, mixin,
                                                                                                 user_server,
                                                                                                 wallet_address, header,
                                                                                                 None)  # paymentId: None (end)
                                                if send_tx:
                                                    fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                                        num_format_coin(NetFee, coin_name, coin_decimal, False),
                                                        coin_name)
                                                    response = f'You withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                                                    await update_bot_response(each_msg['text'], response,
                                                                              each_msg['id'])
                                                    await logchanbot(
                                                        f'[{user_server}] A user {tw_user} successfully executed withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                                    continue
                                                else:
                                                    await logchanbot(
                                                        f'[{user_server}] A user {tw_user} failed to execute to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')  # ctx
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                            elif each_msg['text'].lower().startswith("help"):
                                response = "[In progress] - Please refer to http://chat.wrkz.work"
                                await update_bot_response(each_msg['text'], response, each_msg['id'])
                                continue
                            else:
                                sql = """ UPDATE `twitter_fetch_bot_messages` 
                                          SET `is_ignored`=%s, `ignored_date`=%s WHERE `id`=%s LIMIT 1
                                      """
                                await cur.execute(sql, (1, int(time.time()), each_msg['id']))
                                await conn.commit()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def monitoring_rt_rewards(self):
        time_lap = 10  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "monitoring_rt_rewards"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # get verified user twitter
                    twitter_discord_user = {}
                    sql = """ SELECT * FROM `twitter_linkme` 
                              WHERE `is_verified`=1 
                              """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each_t_user in result:
                            twitter_discord_user[each_t_user['id_str']] = each_t_user[
                                'discord_user_id']  # twitter[id]= discord
                    # get unpaid reward
                    sql = """ SELECT * FROM `twitter_rt_reward_logs` 
                              WHERE `rewarded_user` IS NULL AND `is_credited`=%s 
                              AND `notified_confirmation`=%s AND `failed_notification`=%s AND `unverified_reward`=%s """
                    await cur.execute(sql, ("NO", "NO", "NO", "NO"))
                    reward_tos = await cur.fetchall()
                    if reward_tos and len(reward_tos) > 0:
                        # there is pending reward
                        for each_reward in reward_tos:
                            if each_reward['expired_date'] and each_reward['expired_date'] < int(time.time()):
                                # Expired.
                                sql = """ UPDATE `twitter_rt_reward_logs` SET `unverified_reward`=%s
                                          WHERE `id`=%s LIMIT 1
                                          """
                                await cur.execute(sql, ("YES", each_reward['id']))
                                await conn.commit()
                                continue
                            each_discord_user = None
                            # Check if those twitter has verified if not could not find update it
                            if each_reward['twitter_id'] in twitter_discord_user:
                                for k, v in twitter_discord_user.items():
                                    if k == each_reward['twitter_id']:
                                        each_discord_user = twitter_discord_user[k]
                                        break
                                if each_discord_user is None:
                                    await logchanbot("[TWITTER]: can not find twitter ID {} to Discord ID".format(
                                        each_reward['twitter_id']))
                                    continue
                                # We got him verified.
                                guild_id = each_reward['guild_id']
                                guild = self.bot.get_guild(int(each_reward['guild_id']))
                                if guild:
                                    # We found guild
                                    serverinfo = await store.sql_info_by_server(each_reward['guild_id'])
                                    # Check if new link is updated. If yes, we ignore it
                                    if serverinfo['rt_link'] and each_reward['tweet_link'] != serverinfo['rt_link']:
                                        # Update
                                        sql = """ UPDATE `twitter_rt_reward_logs` SET `unverified_reward`=%s
                                                  WHERE `id`=%s LIMIT 1
                                                  """
                                        await cur.execute(sql, ("YES", each_reward['id']))
                                        await conn.commit()
                                        continue
                                    elif serverinfo['rt_reward_amount'] and serverinfo['rt_reward_coin'] and serverinfo[
                                        'rt_reward_channel'] and serverinfo['rt_link']:
                                        twitter_link = serverinfo['rt_link']
                                        coin_name = serverinfo['rt_reward_coin']
                                        # Check balance of guild
                                        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                                        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                                        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name),
                                                                        "deposit_confirm_depth")
                                        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                        contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                                        usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name),
                                                                        "usd_equivalent_enable")
                                        user_from = await self.wallet_api.sql_get_userwallet(each_reward['guild_id'],
                                                                                             coin_name, net_name,
                                                                                             type_coin, SERVER_BOT, 0)
                                        if user_from is None:
                                            user_from = await self.wallet_api.sql_register_user(each_reward['guild_id'],
                                                                                                coin_name, net_name,
                                                                                                type_coin, SERVER_BOT,
                                                                                                0)
                                        wallet_address = user_from['balance_wallet_address']
                                        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                            wallet_address = user_from['paymentid']
                                        height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)

                                        # height can be None
                                        userdata_balance = await store.sql_user_balance_single(each_reward['guild_id'],
                                                                                               coin_name,
                                                                                               wallet_address,
                                                                                               type_coin, height,
                                                                                               deposit_confirm_depth,
                                                                                               SERVER_BOT)
                                        total_balance = userdata_balance['adjust']
                                        amount = serverinfo['rt_reward_amount']
                                        if total_balance < amount:
                                            # Alert guild owner
                                            try:
                                                sql = """ UPDATE `twitter_rt_reward_logs` SET `rewarded_user`=%s, `is_credited`=%s, `notified_confirmation`=%s, `time_notified`=%s, `shortage_balance`=%s 
                                                          WHERE `id`=%s LIMIT 1
                                                          """
                                                await cur.execute(sql, (
                                                each_discord_user, "NO", "YES", int(time.time()), each_reward['id'],
                                                "YES"))
                                                await conn.commit()
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                            guild_owner = self.bot.get_user(guild.owner.id)
                                            await guild_owner.send(
                                                f'Your guild run out of guild\'s balance for {coin_name}. Deposit more!')
                                            return
                                        else:
                                            # Tip
                                            member = None
                                            try:
                                                member = self.bot.get_user(int(each_discord_user))
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                            try:
                                                amount_in_usd = 0.0
                                                if usd_equivalent_enable == 1:
                                                    native_token_name = getattr(getattr(self.bot.coin_list, coin_name),
                                                                                "native_token_name")
                                                    coin_name_for_price = coin_name
                                                    if native_token_name:
                                                        coin_name_for_price = native_token_name
                                                    if coin_name_for_price in self.bot.token_hints:
                                                        id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                                                        per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                                                    else:
                                                        per_unit = \
                                                        self.bot.coin_paprika_symbol_list[coin_name_for_price][
                                                            'price_usd']
                                                    if per_unit and per_unit > 0:
                                                        amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                                                try:
                                                    sql = """ UPDATE `twitter_rt_reward_logs` SET `rewarded_user`=%s, `is_credited`=%s, `notified_confirmation`=%s, `time_notified`=%s 
                                                              WHERE `id`=%s LIMIT 1
                                                              """
                                                    await cur.execute(sql, (
                                                    each_discord_user, "YES", "YES", int(time.time()),
                                                    each_reward['id']))
                                                    await conn.commit()
                                                    if cur.rowcount == 0:
                                                        # Skip to next..
                                                        continue
                                                except Exception:
                                                    traceback.print_exc(file=sys.stdout)
                                                    continue

                                                try:
                                                    key_coin = each_reward['guild_id'] + "_" + coin_name + "_" + "TWITTER"
                                                    if key_coin in self.bot.user_balance_cache:
                                                        del self.bot.user_balance_cache[key_coin]

                                                    key_coin = each_discord_user + "_" + coin_name + "_" + "TWITTER"
                                                    if key_coin in self.bot.user_balance_cache:
                                                        del self.bot.user_balance_cache[key_coin]
                                                except Exception:
                                                    pass

                                                tip = await store.sql_user_balance_mv_single(each_reward['guild_id'],
                                                                                             each_discord_user,
                                                                                             "TWITTER", "TWITTER",
                                                                                             amount, coin_name,
                                                                                             "RETWEET", coin_decimal,
                                                                                             SERVER_BOT, contract,
                                                                                             amount_in_usd, None)
                                                if member is not None:
                                                    msg = f"Thank you for RT <{twitter_link}>. You just got a reward of {num_format_coin(amount, coin_name, coin_decimal, False)} {coin_name}."
                                                    try:
                                                        await member.send(msg)
                                                        guild_owner = self.bot.get_user(guild.owner.id)
                                                        try:
                                                            await guild_owner.send(
                                                                f'User `{each_discord_user}` RT your twitter at <{twitter_link}>. He/she just got a reward of {num_format_coin(amount, coin_name, coin_decimal, False)} {coin_name}.')
                                                        except Exception:
                                                            pass
                                                        # Log channel if there is
                                                        try:
                                                            if serverinfo and serverinfo['rt_reward_channel']:
                                                                channel = self.bot.get_channel(
                                                                    int(serverinfo['rt_reward_channel']))
                                                                embed = disnake.Embed(title="NEW RETWEET REWARD!",
                                                                                      timestamp=datetime.now())
                                                                embed.add_field(name="User",
                                                                                value="<@{}>".format(each_discord_user),
                                                                                inline=True)
                                                                embed.add_field(name="Reward", value="{} {}".format(
                                                                    num_format_coin(amount, coin_name, coin_decimal,
                                                                                    False), coin_name), inline=True)
                                                                embed.add_field(name="RT Link",
                                                                                value=f"<{twitter_link}>", inline=False)
                                                                embed.set_author(name=self.bot.user.name,
                                                                                 icon_url=self.bot.user.display_avatar)
                                                                await channel.send(embed=embed)
                                                        except Exception:
                                                            traceback.print_exc(file=sys.stdout)
                                                            await logchanbot(
                                                                f'[TWITTER] Failed to send message to retweet reward to channel in guild: `{guild_id}` / {guild.name}.')
                                                    except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                                        await logchanbot(
                                                            f'[TWITTER] Failed to thank message to <@{each_discord_user}>.')
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                            else:
                                # this is not verified. Update it
                                sql = """ UPDATE `twitter_rt_reward_logs` SET `unverified_reward`=%s
                                          WHERE `id`=%s LIMIT 1
                                          """
                                await cur.execute(sql, ("YES", each_reward['id']))
                                await conn.commit()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    # Notify user
    @tasks.loop(seconds=60.0)
    async def notify_new_confirmed_spendable_erc20(self):
        time_lap = 5  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_new_confirmed_spendable_erc20"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            notify_list = await store.sql_get_pending_notification_users_erc20(SERVER_BOT)
            if len(notify_list) > 0:
                for each_notify in notify_list:
                    try:
                        key = "notify_new_tx_erc20_{}_{}_{}".format(each_notify['token_name'], each_notify['user_id'],
                                                                    each_notify['txn'])
                        if self.ttlcache[key] == key:
                            continue
                        else:
                            self.ttlcache[key] = key
                    except Exception:
                        pass
                    is_notify_failed = False
                    member = self.bot.get_user(int(each_notify['user_id']))
                    if member:
                        update_status = await store.sql_updating_pending_move_deposit_erc20(True, is_notify_failed,
                                                                                            each_notify['txn'])
                        if update_status > 0:
                            msg = "You got a new deposit confirmed: ```" + "Amount: {} {}".format(
                                num_format_coin(each_notify['real_amount'], each_notify['token_name'],
                                                each_notify['token_decimal'], False), each_notify['token_name']) + "```"
                            try:
                                await member.send(msg)
                            except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                is_notify_failed = True
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def notify_new_confirmed_spendable_trc20(self):
        time_lap = 5  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_new_confirmed_spendable_trc20"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            notify_list = await store.sql_get_pending_notification_users_trc20(SERVER_BOT)
            if notify_list and len(notify_list) > 0:
                for each_notify in notify_list:
                    try:
                        key = "notify_new_tx_trc20_{}_{}_{}".format(each_notify['token_name'], each_notify['user_id'],
                                                                    each_notify['txn'])
                        if self.ttlcache[key] == key:
                            continue
                        else:
                            self.ttlcache[key] = key
                    except Exception:
                        pass
                    is_notify_failed = False
                    member = self.bot.get_user(int(each_notify['user_id']))
                    if member:
                        update_status = await store.sql_updating_pending_move_deposit_trc20(True, is_notify_failed,
                                                                                            each_notify['txn'])
                        if update_status > 0:
                            msg = "You got a new deposit confirmed: ```" + "Amount: {} {}".format(
                                num_format_coin(each_notify['real_amount'], each_notify['token_name'],
                                                each_notify['token_decimal'], False), each_notify['token_name']) + "```"
                            try:
                                await member.send(msg)
                            except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                                is_notify_failed = True
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    # Notify user
    @tasks.loop(seconds=60.0)
    async def notify_new_tx_user(self):
        time_lap = 5  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_new_tx_user"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            pending_tx = await store.sql_get_new_tx_table('NO', 'NO')
            if len(pending_tx) > 0:
                # let's notify_new_tx_user
                for eachTx in pending_tx:
                    try:
                        coin_name = eachTx['coin_name']
                        if not hasattr(self.bot.coin_list, coin_name):
                            continue
                        coin_family = getattr(getattr(self.bot.coin_list, coin_name), "type")
                        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                        if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR", "BTC", "CHIA", "NANO"]:
                            user_tx = await store.sql_get_userwallet_by_paymentid(eachTx['payment_id'],
                                                                                  eachTx['coin_name'], coin_family)
                            if user_tx and 'user_server' in user_tx and user_tx['user_server'] == SERVER_BOT and user_tx['user_id'].isdigit():
                                try:
                                    key = "notify_new_tx_{}_{}_{}".format(eachTx['coin_name'], user_tx['user_id'],
                                                                          eachTx['txid'])
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                is_notify_failed = False
                                user_found = self.bot.get_user(int(user_tx['user_id']))
                                if user_found:
                                    update_notify_tx = await store.sql_update_notify_tx_table(eachTx['payment_id'],
                                                                                              user_tx['user_id'],
                                                                                              user_found.name, 'YES',
                                                                                              'NO' if is_notify_failed == False else 'YES',
                                                                                              eachTx['txid'])
                                    if update_notify_tx > 0:
                                        try:
                                            msg = None
                                            if coin_family == "NANO":
                                                msg = "You got a new deposit: ```" + "Coin: {}\nAmount: {}".format(
                                                    eachTx['coin_name'],
                                                    num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal,
                                                                    False)) + "```"
                                            elif coin_family != "BTC":
                                                msg = "You got a new deposit confirmed: ```" + "Coin: {}\nTx: {}\nAmount: {}\nHeight: {:,.0f}".format(
                                                    eachTx['coin_name'], eachTx['txid'],
                                                    num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal,
                                                                    False), eachTx['height']) + "```"
                                            else:
                                                msg = "You got a new deposit confirmed: ```" + "Coin: {}\nTx: {}\nAmount: {}\nBlock Hash: {}".format(
                                                    eachTx['coin_name'], eachTx['txid'],
                                                    num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal,
                                                                    False), eachTx['blockhash']) + "```"
                                            await user_found.send(msg)
                                        except (
                                        disnake.Forbidden, disnake.errors.Forbidden, disnake.errors.HTTPException) as e:
                                            is_notify_failed = True
                                            pass
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                else:
                                    # try to find if it is guild
                                    guild_found = self.bot.get_guild(int(user_tx['user_id']))
                                    if guild_found: user_found = self.bot.get_user(guild_found.owner.id)
                                    if guild_found and user_found:
                                        update_notify_tx = await store.sql_update_notify_tx_table(eachTx['payment_id'],
                                                                                                  user_tx['user_id'],
                                                                                                  guild_found.name,
                                                                                                  'YES',
                                                                                                  'NO' if is_notify_failed == False else 'YES',
                                                                                                  eachTx['txid'])
                                        if update_notify_tx > 0:
                                            is_notify_failed = False
                                            try:
                                                msg = None
                                                if coin_family == "NANO":
                                                    msg = "Your guild `{}` got a new deposit: ```" + "Coin: {}\nAmount: {}".format(
                                                        guild_found.name, eachTx['coin_name'],
                                                        num_format_coin(eachTx['amount'], eachTx['coin_name'],
                                                                        coin_decimal, False)) + "```"
                                                elif coin_family != "BTC":
                                                    msg = "Your guild `{}` got a new deposit confirmed: ```" + "Coin: {}\nTx: {}\nAmount: {}\nHeight: {:,.0f}".format(
                                                        guild_found.name, eachTx['coin_name'], eachTx['txid'],
                                                        num_format_coin(eachTx['amount'], eachTx['coin_name'],
                                                                        coin_decimal, False), eachTx['height']) + "```"
                                                else:
                                                    msg = "Your guild `{}` got a new deposit confirmed: ```" + "Coin: {}\nTx: {}\nAmount: {}\nBlock Hash: {}".format(
                                                        guild_found.name, eachTx['coin_name'], eachTx['txid'],
                                                        num_format_coin(eachTx['amount'], eachTx['coin_name'],
                                                                        coin_decimal, False),
                                                        eachTx['blockhash']) + "```"
                                                await user_found.send(msg)
                                            except (disnake.Forbidden, disnake.errors.Forbidden,
                                                    disnake.errors.HTTPException) as e:
                                                is_notify_failed = True
                                                pass
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                                await logchanbot("wallet notify_new_tx_user " + str(traceback.format_exc()))
                                    else:
                                        # print('Can not find user id {} to notification tx: {}'.format(user_tx['user_id'], eachTx['txid']))
                                        pass
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def notify_new_tx_user_noconfirmation(self):
        time_lap = 5  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_new_tx_user_noconfirmation"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            if config.notify_new_tx.enable_new_no_confirm == 1:
                key_tx_new = config.redis.prefix_new_tx + 'NOCONFIRM'
                key_tx_no_confirmed_sent = config.redis.prefix_new_tx + 'NOCONFIRM:SENT'
                try:
                    if redis_utils.redis_conn.llen(key_tx_new) > 0:
                        list_new_tx = redis_utils.redis_conn.lrange(key_tx_new, 0, -1)
                        list_new_tx_sent = redis_utils.redis_conn.lrange(key_tx_no_confirmed_sent, 0,
                                                                         -1)  # byte list with b'xxx'
                        # Unique the list
                        list_new_tx = np.unique(list_new_tx).tolist()
                        list_new_tx_sent = np.unique(list_new_tx_sent).tolist()
                        for tx in list_new_tx:
                            try:
                                if tx not in list_new_tx_sent:
                                    tx = tx.decode()  # decode byte from b'xxx to xxx
                                    key_tx_json = config.redis.prefix_new_tx + tx
                                    eachTx = None
                                    try:
                                        if redis_utils.redis_conn.exists(key_tx_json): eachTx = json.loads(
                                            redis_utils.redis_conn.get(key_tx_json).decode())
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    if eachTx is None: continue
                                    coin_name = eachTx['coin_name']
                                    coin_family = getattr(getattr(self.bot.coin_list, coin_name), "type")
                                    redis_utils.redis_conn.lpush(key_tx_no_confirmed_sent, tx)
                                    if eachTx and coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR", "BTC",
                                                                  "CHIA"]:
                                        get_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name),
                                                                    "deposit_confirm_depth")
                                        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                        user_tx = await store.sql_get_userwallet_by_paymentid(eachTx['payment_id'],
                                                                                              eachTx['coin_name'],
                                                                                              coin_family)
                                        if user_tx and user_tx['user_server'] == SERVER_BOT and user_tx[
                                            'user_id'].isdigit():
                                            try:
                                                key = "notify_new_tx_noconfirm_{}_{}_{}".format(eachTx['coin_name'],
                                                                                                user_tx['user_id'],
                                                                                                eachTx['txid'])
                                                if self.ttlcache[key] == key:
                                                    continue
                                                else:
                                                    self.ttlcache[key] = key
                                            except Exception:
                                                pass
                                            user_found = self.bot.get_user(int(user_tx['user_id']))
                                            if user_found:

                                                try:
                                                    msg = None
                                                    confirmation_number_txt = "{} needs {} confirmations.".format(
                                                        eachTx['coin_name'], get_confirm_depth)
                                                    if coin_family != "BTC":
                                                        msg = "You got a new **pending** deposit: ```" + "Coin: {}\nTx: {}\nAmount: {}\nHeight: {:,.0f}\n{}".format(
                                                            eachTx['coin_name'], eachTx['txid'],
                                                            num_format_coin(eachTx['amount'], eachTx['coin_name'],
                                                                            coin_decimal, False), eachTx['height'],
                                                            confirmation_number_txt) + "```"
                                                    else:
                                                        msg = "You got a new **pending** deposit: ```" + "Coin: {}\nTx: {}\nAmount: {}\nBlock Hash: {}\n{}".format(
                                                            eachTx['coin_name'], eachTx['txid'],
                                                            num_format_coin(eachTx['amount'], eachTx['coin_name'],
                                                                            coin_decimal, False), eachTx['blockhash'],
                                                            confirmation_number_txt) + "```"
                                                    await user_found.send(msg)
                                                except (disnake.Forbidden, disnake.errors.Forbidden,
                                                        disnake.errors.HTTPException) as e:
                                                    pass
                                            else:
                                                # try to find if it is guild
                                                guild_found = self.bot.get_guild(int(user_tx['user_id']))
                                                if guild_found: user_found = self.bot.get_user(guild_found.owner.id)
                                                if guild_found and user_found:
                                                    try:
                                                        msg = None
                                                        confirmation_number_txt = "{} needs {} confirmations.".format(
                                                            eachTx['coin_name'], get_confirm_depth)
                                                        if eachTx['coin_name'] != "BTC":
                                                            msg = "Your guild got a new **pending** deposit: ```" + "Coin: {}\nTx: {}\nAmount: {}\nHeight: {:,.0f}\n{}".format(
                                                                eachTx['coin_name'], eachTx['txid'],
                                                                num_format_coin(eachTx['amount'], eachTx['coin_name'],
                                                                                coin_decimal, False), eachTx['height'],
                                                                confirmation_number_txt) + "```"
                                                        else:
                                                            msg = "Your guild got a new **pending** deposit: ```" + "Coin: {}\nTx: {}\nAmount: {}\nBlock Hash: {}\n{}".format(
                                                                eachTx['coin_name'], eachTx['txid'],
                                                                num_format_coin(eachTx['amount'], eachTx['coin_name'],
                                                                                coin_decimal, False),
                                                                eachTx['blockhash'], confirmation_number_txt) + "```"
                                                        await user_found.send(msg)
                                                    except (disnake.Forbidden, disnake.errors.Forbidden,
                                                            disnake.errors.HTTPException) as e:
                                                        pass
                                                    except Exception:
                                                        traceback.print_exc(file=sys.stdout)
                                                else:
                                                    # print('Can not find user id {} to notification **pending** tx: {}'.format(user_tx['user_id'], eachTx['txid']))
                                                    pass
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def notify_new_confirmed_hnt(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_new_confirmed_hnt"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `hnt_get_transfers` WHERE `notified_confirmation`=%s AND `failed_notification`=%s AND `user_server`=%s """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            if eachTx['user_id']:
                                if not eachTx['user_id'].isdigit():
                                    continue
                                try:
                                    key = "notify_new_tx_{}_{}_{}".format(eachTx['coin_name'], eachTx['user_id'],
                                                                          eachTx['txid'])
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['coin_name']), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + "Coin: {}\nTx: {}\nAmount: {}".format(
                                        eachTx['coin_name'], eachTx['txid'],
                                        num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal,
                                                        False)) + "```"
                                    try:
                                        await member.send(msg)
                                        sql = """ UPDATE `hnt_get_transfers` SET `notified_confirmation`=%s, `time_notified`=%s WHERE `txid`=%s LIMIT 1 """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['txid']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `hnt_get_transfers` SET `notified_confirmation`=%s, `failed_notification`=%s WHERE `txid`=%s LIMIT 1 """
                                        await cur.execute(sql, ("NO", "YES", eachTx['txid']))
                                        await conn.commit()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=120.0)
    async def update_balance_hnt(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_balance_hnt"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        timeout = 30
        coin_name = "HNT"
        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 0 and getattr(
                getattr(self.bot.coin_list, coin_name), "enable_deposit") == 1:
            try:
                # get height
                try:
                    headers = {
                        'Content-Type': 'application/json',
                    }
                    json_data = {
                        "jsonrpc": "2.0",
                        "id": "1",
                        "method": "block_height"
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(getattr(getattr(self.bot.coin_list, coin_name), "wallet_address"),
                                                headers=headers, json=json_data, timeout=timeout) as response:
                            if response.status == 200:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                decoded_data = json.loads(res_data)
                                if 'result' in decoded_data:
                                    height = int(decoded_data['result'])
                                    try:
                                        redis_utils.redis_conn.set(
                                            f'{config.redis.prefix + config.redis.daemon_height}{coin_name}',
                                            str(height))
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                except Exception:
                    traceback.print_exc(file=sys.stdout)

                async def fetch_api(url, timeout):
                    try:
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'
                        }
                        async with aiohttp.ClientSession() as session:
                            async with session.get(url, headers=headers, timeout=timeout) as response:
                                if response.status == 200:
                                    res_data = await response.read()
                                    res_data = res_data.decode('utf-8')
                                    decoded_data = json.loads(res_data)
                                    return decoded_data
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    return None

                async def get_tx_incoming():
                    try:
                        await self.openConnection()
                        async with self.pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                sql = """ SELECT * FROM `hnt_get_transfers` """
                                await cur.execute(sql, )
                                result = await cur.fetchall()
                                if result: return result
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    return []

                # Get list of tx from API:
                main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                url = getattr(getattr(self.bot.coin_list, coin_name), "rpchost") + "accounts/" + main_address + "/roles"
                fetch_data = await fetch_api(url, timeout)
                incoming = []  ##payments
                if fetch_data is not None and 'data' in fetch_data:
                    # Check if len data is 0
                    if len(fetch_data['data']) == 0 and 'cursor' in fetch_data:
                        url2 = getattr(getattr(self.bot.coin_list, coin_name),
                                       "rpchost") + "accounts/" + main_address + "/roles/?cursor=" + fetch_data[
                                   'cursor']
                        # get with cursor
                        fetch_data_2 = await fetch_api(url2, timeout)
                        if fetch_data_2 is not None and 'data' in fetch_data_2:
                            if len(fetch_data_2['data']) > 0:
                                for each_item in fetch_data_2['data']:
                                    incoming.append(each_item)
                    elif len(fetch_data['data']) > 0 and 'cursor' in fetch_data:
                        for each_item in fetch_data['data']:
                            incoming.append(each_item)
                        url2 = getattr(getattr(self.bot.coin_list, coin_name),
                                       "rpchost") + "accounts/" + main_address + "/roles/?cursor=" + fetch_data[
                                   'cursor']
                        # get with cursor
                        fetch_data_2 = await fetch_api(url2, timeout)
                        if fetch_data_2 is not None and 'data' in fetch_data_2:
                            if len(fetch_data_2['data']) > 0:
                                for each_item in fetch_data_2['data']:
                                    incoming.append(each_item)
                    elif len(fetch_data['data']) > 0:
                        for each_item in fetch_data['data']:
                            incoming.append(each_item)
                if len(incoming) > 0:
                    get_incoming_tx = await get_tx_incoming()
                    list_existing_tx = []
                    if len(get_incoming_tx) > 0:
                        list_existing_tx = [each['txid'] for each in get_incoming_tx]
                    for each_tx in incoming:
                        try:
                            tx_hash = each_tx['hash']
                            if tx_hash in list_existing_tx:
                                # Go to next
                                continue
                            amount = 0.0
                            url_tx = getattr(getattr(self.bot.coin_list, coin_name), "rpchost") + "transactions/" + tx_hash
                            fetch_tx = await fetch_api(url_tx, timeout)
                            if fetch_tx and 'data' in fetch_tx:
                                height = fetch_tx['data']['height']
                                blockTime = fetch_tx['data']['time']
                                fee = fetch_tx['data']['fee'] / 10 ** coin_decimal if 'fee' in fetch_tx['data'] else None
                                if fee is None:
                                    continue
                                payer = fetch_tx['data']['payer']
                                if 'payer' in fetch_tx['data'] and fetch_tx['data'] == main_address:
                                    continue
                                if 'payments' in fetch_tx['data'] and len(fetch_tx['data']['payments']) > 0:
                                    for each_payment in fetch_tx['data']['payments']:
                                        if each_payment['payee'] == main_address:
                                            amount = each_payment['amount'] / 10 ** coin_decimal
                                            memo = base64.b64decode(each_payment['memo']).decode()
                                            try:
                                                coin_family = "HNT"
                                                user_memo = None
                                                user_id = None
                                                if len(memo) == 8:
                                                    user_memo = await store.sql_get_userwallet_by_paymentid(
                                                        "{} MEMO: {}".format(main_address, memo), coin_name, coin_family)
                                                    if user_memo is not None and user_memo['user_id']:
                                                        user_id = user_memo['user_id']
                                                await self.openConnection()
                                                async with self.pool.acquire() as conn:
                                                    async with conn.cursor() as cur:
                                                        sql = """ INSERT INTO `hnt_get_transfers` (`coin_name`, `user_id`, `txid`, `height`, `timestamp`, 
                                                                  `amount`, `fee`, `decimal`, `address`, `memo`, 
                                                                  `payer`, `time_insert`, `user_server`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                        await cur.execute(sql, (
                                                        coin_name, user_id, tx_hash, height, blockTime, amount, fee,
                                                        coin_decimal, each_payment['payee'], memo, payer, int(time.time()),
                                                        user_memo['user_server'] if user_memo else None))
                                                        await conn.commit()
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                                await logchanbot("wallet update_balance_hnt " + str(traceback.format_exc()))
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
            except asyncio.TimeoutError:
                print('TIMEOUT: COIN: {} - timeout {}'.format(coin_name, timeout))
            except Exception:
                traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def notify_new_confirmed_vite(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_new_confirmed_vite"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `vite_get_transfers` 
                    WHERE `notified_confirmation`=%s AND `failed_notification`=%s AND `user_server`=%s
                    """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            if eachTx['user_id']:
                                if not eachTx['user_id'].isdigit():
                                    continue
                                try:
                                    key = "notify_new_tx_{}_{}_{}".format(eachTx['coin_name'], eachTx['user_id'],
                                                                          eachTx['txid'])
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['coin_name']), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + "Coin: {}\nTx: {}\nAmount: {}".format(
                                        eachTx['coin_name'], eachTx['txid'],
                                        num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal,
                                                        False)) + "```"
                                    try:
                                        await member.send(msg)
                                        sql = """ UPDATE `vite_get_transfers` SET `notified_confirmation`=%s, `time_notified`=%s WHERE `txid`=%s LIMIT 1 """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['txid']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `vite_get_transfers` SET `notified_confirmation`=%s, `failed_notification`=%s WHERE `txid`=%s LIMIT 1 """
                                        await cur.execute(sql, ("NO", "YES", eachTx['txid']))
                                        await conn.commit()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=120.0)
    async def update_balance_vite(self):
        async def get_tx_incoming_vite():
            try:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """ SELECT * FROM `vite_get_transfers` """
                        await cur.execute(sql,)
                        result = await cur.fetchall()
                        if result: return result
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return []

        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_balance_vite"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        timeout = 30
        # Get status
        try:
            coin_name = "VITE"
            url = getattr(getattr(self.bot.coin_list, coin_name), "rpchost")
            main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
            height = await vite_get_height(url)
            coin_family = getattr(getattr(self.bot.coin_list, coin_name), "type")
            if height and height > 0:
                try:
                    redis_utils.redis_conn.set(
                        f'{config.redis.prefix + config.redis.daemon_height}{coin_name}',
                        str(height))
                    # if there are other asset, set them all here
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                vite_contract_list = await self.get_all_contracts("VITE", False)
                vite_contracts = [each['contract'] for each in vite_contract_list]
                # get txes
                list_txes = await vite_ledger_getAccountBlocksByAddress(url, main_address, 50)
                if list_txes and len(list_txes) > 0:
                    get_incoming_tx = await get_tx_incoming_vite()
                    list_existing_tx = []
                    if len(get_incoming_tx) > 0:
                        list_existing_tx = [each['txid'] for each in get_incoming_tx]
                    for each_tx in list_txes:
                        try:
                            get_tx = await vite_ledger_getAccountBlockByHash(url, each_tx['fromBlockHash'])
                            if get_tx is None:
                                continue
                            user_memo = None
                            user_id = None
                            if get_tx['toAddress'] == main_address and get_tx['data'] and len(get_tx['data']) > 0 and int(get_tx['confirmations']) > 0 and get_tx['tokenInfo']['tokenId'] in vite_contracts and int(get_tx['amount']) > 0:
                                contract = get_tx['tokenId']
                                tx_hash = get_tx['hash']
                                if tx_hash in list_existing_tx:
                                    # Skip
                                    continue
                                height = get_tx['firstSnapshotHeight']
                                for each_coin in self.bot.coin_name_list:
                                    if contract == getattr(getattr(self.bot.coin_list, each_coin), "contract"):
                                        coin_name = getattr(getattr(self.bot.coin_list, each_coin), "coin_name")
                                        break
                                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                amount = int(get_tx['amount']) / 10**coin_decimal
                                fee = int(get_tx['fee']) / 10**coin_decimal
                                memo = base64.b64decode(get_tx['data']).decode()
                                user_memo = await store.sql_get_userwallet_by_paymentid(
                                    "{} MEMO: {}".format(main_address, memo.strip()),
                                    coin_name, coin_family)
                                if user_memo is not None and user_memo['user_id'] is not None:
                                    user_id = user_memo['user_id']
                                    if amount > 0:
                                        await self.openConnection()
                                        async with self.pool.acquire() as conn:
                                            async with conn.cursor() as cur:
                                                sql = """ INSERT INTO `vite_get_transfers` (`coin_name`, `user_id`, `txid`, `contents`,`height`, `amount`, `fee`, `decimal`, `address`, `memo`, `time_insert`, `user_server`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                await cur.execute(sql, (
                                                coin_name, user_id, tx_hash, json.dumps(get_tx), height, amount, fee,
                                                coin_decimal, main_address, memo, int(time.time()),
                                                user_memo['user_server'] if user_memo else None))
                                                await conn.commit()
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def notify_new_confirmed_xlm(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_new_confirmed_xlm"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `xlm_get_transfers` WHERE `notified_confirmation`=%s AND `failed_notification`=%s AND `user_server`=%s """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            if eachTx['user_id']:
                                if not eachTx['user_id'].isdigit():
                                    continue
                                try:
                                    key = "notify_new_tx_{}_{}_{}".format(eachTx['coin_name'], eachTx['user_id'],
                                                                          eachTx['txid'])
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['coin_name']), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + "Coin: {}\nTx: {}\nAmount: {}".format(
                                        eachTx['coin_name'], eachTx['txid'],
                                        num_format_coin(eachTx['amount'], eachTx['coin_name'], coin_decimal,
                                                        False)) + "```"
                                    try:
                                        await member.send(msg)
                                        sql = """ UPDATE `xlm_get_transfers` SET `notified_confirmation`=%s, `time_notified`=%s WHERE `txid`=%s LIMIT 1 """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['txid']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `xlm_get_transfers` SET `notified_confirmation`=%s, `failed_notification`=%s WHERE `txid`=%s LIMIT 1 """
                                        await cur.execute(sql, ("NO", "YES", eachTx['txid']))
                                        await conn.commit()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=120.0)
    async def update_balance_xlm(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_balance_xlm"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        timeout = 30
        # Get status
        coin_name = "XLM"
        coin_family = coin_name
        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 0 and getattr(
                getattr(self.bot.coin_list, coin_name), "enable_deposit") == 1:
            try:
                async def get_xlm_transactions(endpoint: str, account_addr: str):
                    async with ServerAsync(
                            horizon_url=endpoint, client=AiohttpClient()
                    ) as server:
                        # get a list of transactions submitted by a particular account
                        transactions = await server.transactions().for_account(account_id=account_addr).order(
                            desc=True).limit(50).call()
                        if len(transactions["_embedded"]["records"]) > 0:
                            return transactions["_embedded"]["records"]
                        return []

                async def get_tx_incoming():
                    try:
                        await self.openConnection()
                        async with self.pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                sql = """ SELECT * FROM `xlm_get_transfers` """
                                await cur.execute(sql, )
                                result = await cur.fetchall()
                                if result: return result
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    return []

                headers = {
                    'Content-Type': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'
                }
                # get status
                url = getattr(getattr(self.bot.coin_list, coin_name), "http_address")
                main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers=headers, timeout=timeout) as response:
                            if response.status == 200:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                decoded_data = json.loads(res_data)
                                if 'history_latest_ledger' in decoded_data:
                                    height = decoded_data['history_latest_ledger']
                                    try:
                                        redis_utils.redis_conn.set(
                                            f'{config.redis.prefix + config.redis.daemon_height}{coin_name}',
                                            str(height))
                                        # if there are other asset, set them all here
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    get_transactions = await get_xlm_transactions(url, main_address)
                                    if len(get_transactions) > 0:
                                        get_incoming_tx = await get_tx_incoming()
                                        list_existing_tx = []
                                        if len(get_incoming_tx) > 0:
                                            list_existing_tx = [each['txid'] for each in get_incoming_tx]
                                        for each_tx in get_transactions:
                                            try:
                                                amount = 0
                                                tx_hash = each_tx['hash']
                                                if tx_hash in list_existing_tx:
                                                    # Skip
                                                    continue
                                                if 'successful' in each_tx and each_tx['successful'] != True:
                                                    # Skip
                                                    continue
                                                transaction_envelope = parse_transaction_envelope_from_xdr(
                                                    each_tx['envelope_xdr'], Network.PUBLIC_NETWORK_PASSPHRASE
                                                )
                                                for Payment in transaction_envelope.transaction.operations:
                                                    try:
                                                        destination = Payment.destination.account_id
                                                        asset_type = Payment.asset.type
                                                        asset_code = Payment.asset.code
                                                        asset_issuer = None
                                                        if asset_type == "native":
                                                            coin_name = "XLM"
                                                        else:
                                                            if hasattr(Payment.asset, "code") and hasattr(Payment.asset, "issuer"):
                                                                asset_issuer = Payment.asset.issuer
                                                                for each_coin in self.bot.coin_name_list:
                                                                    if asset_code == getattr(getattr(self.bot.coin_list, each_coin), "header") \
                                                                        and asset_issuer == getattr(getattr(self.bot.coin_list, each_coin), "contract"):
                                                                        coin_name = getattr(getattr(self.bot.coin_list, each_coin), "coin_name")
                                                                        break
                                                        if not hasattr(self.bot.coin_list, coin_name):
                                                            continue
                                                        amount = float(Payment.amount)
                                                        if destination != main_address: continue
                                                        # if asset_type not in ["native", "credit_alphanum4", "credit_alphanum12"]:
                                                        #   continue  # TODO: If other asset, check this
                                                        # Check all atrribute
                                                        all_xlm_coins = []
                                                        if self.bot.coin_name_list and len(self.bot.coin_name_list) > 0:
                                                            for each_coin in self.bot.coin_name_list:
                                                                ticker = getattr(getattr(self.bot.coin_list, each_coin), "header")
                                                                if getattr(getattr(self.bot.coin_list, each_coin), "enable") == 1:
                                                                    all_xlm_coins.append(ticker)
                                                        if asset_code not in all_xlm_coins: continue
                                                    except:
                                                        continue
                                                fee = float(transaction_envelope.transaction.fee) / 10000000  # atomic
                                                height = each_tx['ledger']
                                                user_memo = None
                                                user_id = None
                                                if 'memo' in each_tx and 'memo_type' in each_tx and each_tx[
                                                    'memo_type'] == "text" and len(each_tx['memo'].strip()) == 8:
                                                    user_memo = await store.sql_get_userwallet_by_paymentid(
                                                        "{} MEMO: {}".format(main_address, each_tx['memo'].strip()),
                                                        coin_name, coin_family)
                                                    if user_memo is not None and user_memo['user_id'] is not None:
                                                        user_id = user_memo['user_id']
                                                if amount > 0:
                                                    await self.openConnection()
                                                    async with self.pool.acquire() as conn:
                                                        async with conn.cursor() as cur:
                                                            sql = """ INSERT INTO `xlm_get_transfers` (`coin_name`, `user_id`, `txid`, `height`, `amount`, `fee`, `decimal`, `address`, `memo`, `time_insert`, `user_server`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                            await cur.execute(sql, (
                                                            coin_name, user_id, tx_hash, height, amount, fee,
                                                            coin_decimal, main_address,
                                                            each_tx['memo'].strip() if 'memo' in each_tx else None,
                                                            int(time.time()),
                                                            user_memo['user_server'] if user_memo else None))
                                                            await conn.commit()
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                            else:
                                await logchanbot(
                                    f'[XLM] failed to update balance with: {url} got {str(response.status)}')
                                await asyncio.sleep(30.0)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            except Exception:
                traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def notify_new_confirmed_ada(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_new_confirmed_ada"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `ada_get_transfers` WHERE `notified_confirmation`=%s AND `failed_notification`=%s AND `user_server`=%s """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            if eachTx['user_id']:
                                if not eachTx['user_id'].isdigit():
                                    continue
                                coin_name = eachTx['coin_name']
                                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                if eachTx['user_id'].isdigit() and eachTx['user_server'] == SERVER_BOT:
                                    member = self.bot.get_user(int(eachTx['user_id']))
                                    if member is not None:
                                        msg = "You got a new deposit (it could take a few minutes to credit): ```" + "Coin: {}\nTx: {}\nAmount: {}".format(
                                            coin_name, eachTx['hash_id'],
                                            num_format_coin(eachTx['amount'], coin_name, coin_decimal, False)) + "```"
                                        try:
                                            await member.send(msg)
                                            sql = """ UPDATE `ada_get_transfers` SET `notified_confirmation`=%s, `time_notified`=%s WHERE `hash_id`=%s AND `coin_name`=%s LIMIT 1 """
                                            await cur.execute(sql,
                                                              ("YES", int(time.time()), eachTx['hash_id'], coin_name))
                                            await conn.commit()
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                            sql = """ UPDATE `ada_get_transfers` SET `notified_confirmation`=%s, `failed_notification`=%s WHERE `hash_id`=%s AND `coin_name`=%s LIMIT 1 """
                                            await cur.execute(sql, ("NO", "YES", eachTx['hash_id'], coin_name))
                                            await conn.commit()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=30.0)
    async def update_sol_wallets_sync(self):
        time_lap = 30  # seconds
        coin_name = "SOL"
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_sol_wallets_sync"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        async def fetch_getEpochInfo(url: str, timeout: 12):
            data = '{"jsonrpc":"2.0", "method":"getEpochInfo", "id":1}'
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers={'Content-Type': 'application/json'}, json=json.loads(data),
                                            timeout=timeout) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            await session.close()
                            decoded_data = json.loads(res_data)
                            if decoded_data and 'result' in decoded_data:
                                return decoded_data['result']
            except asyncio.TimeoutError:
                print('TIMEOUT: getEpochInfo {} for {}s'.format(url, timeout))
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return None

        async def fetch_wallet_balance(url: str, address: str):
            # url: is endpoint
            try:
                client = Sol_AsyncClient(url)
                balance = await client.get_balance(PublicKey(address))
                if 'result' in balance:
                    await client.close()
                    return balance['result']
            except Exception:
                pass
            return None

        async def move_wallet_balance(url: str, sender_hex_key: str, atomic_amount: int):
            # url: is endpoint transfer
            try:
                sender = Keypair.from_secret_key(bytes.fromhex(sender_hex_key))
                receiver_addr = config.sol.MainAddress
                client = Sol_AsyncClient(url)
                txn = Transaction().add(transfer(TransferParams(
                    from_pubkey=sender.public_key, to_pubkey=receiver_addr, lamports=atomic_amount)))
                sending_tx = await client.send_transaction(txn, sender)
                if 'result' in sending_tx:
                    await client.close()
                    return sending_tx['result']  # This is Tx Hash
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return None

        await asyncio.sleep(time_lap)
        # update Height
        try:
            getEpochInfo = await fetch_getEpochInfo(self.bot.erc_node_list['SOL'], 32)
            if getEpochInfo:
                height = getEpochInfo['absoluteSlot']
                try:
                    redis_utils.redis_conn.set(f'{config.redis.prefix + config.redis.daemon_height}{coin_name}',
                                               str(height))
                except Exception:
                    traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            # If this happen. Sleep and next
            await asyncio.sleep(time_lap)
            # continue

        try:
            lap = int(time.time()) - 3600 * 2
            last_move = int(time.time()) - 90  # if there is last move, it has to be at least XXs
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `sol_user` WHERE (`called_Update`>%s OR `is_discord_guild`=1) AND `last_move_deposit`<%s """
                    await cur.execute(sql, (lap, last_move))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each_addr in result:
                            try:
                                # get deposit balance if it's less than minimum
                                get_balance = await fetch_wallet_balance(self.bot.erc_node_list['SOL'],
                                                                         each_addr['balance_wallet_address'])
                                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                real_min_deposit = getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit")
                                tx_fee = getattr(getattr(self.bot.coin_list, coin_name), "tx_fee")
                                contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                                real_deposit_fee = getattr(getattr(self.bot.coin_list, coin_name), "real_deposit_fee")
                                if get_balance and 'context' in get_balance and 'value' in get_balance:
                                    actual_balance = float(get_balance['value'] / 10 ** coin_decimal)
                                    if actual_balance >= real_min_deposit:
                                        # Let's move
                                        remaining = int((actual_balance - tx_fee) * 10 ** coin_decimal)
                                        moving = await move_wallet_balance(self.bot.erc_node_list['SOL'],
                                                                           decrypt_string(each_addr['secret_key_hex']),
                                                                           remaining)
                                        if moving:
                                            await self.openConnection()
                                            async with self.pool.acquire() as conn:
                                                async with conn.cursor() as cur:
                                                    sql = """ INSERT INTO `sol_move_deposit` (`token_name`, `contract`, `user_id`, `balance_wallet_address`, `to_main_address`, `real_amount`, `real_deposit_fee`, `token_decimal`, `txn`, `time_insert`, `user_server`) 
                                                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                                                              UPDATE `sol_user` SET `last_move_deposit`=%s WHERE `balance_wallet_address`=%s LIMIT 1; """
                                                    await cur.execute(sql, (coin_name, contract, each_addr['user_id'],
                                                                            each_addr['balance_wallet_address'],
                                                                            config.sol.MainAddress,
                                                                            actual_balance - tx_fee, real_deposit_fee,
                                                                            coin_decimal, moving, int(time.time()),
                                                                            each_addr['user_server'], int(time.time()),
                                                                            each_addr['balance_wallet_address']))
                                                    await conn.commit()
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=30.0)
    async def unlocked_move_pending_sol(self):
        time_lap = 30  # seconds
        coin_name = "SOL"
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "unlocked_move_pending_sol"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        async def fetch_getConfirmedTransaction(url: str, txn: str, timeout: 12):
            json_data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getConfirmedTransaction",
                "params": [
                    txn,
                    "json"
                ]
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers={'Content-Type': 'application/json'}, json=json_data,
                                            timeout=timeout) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            await session.close()
                            decoded_data = json.loads(res_data)
                            if decoded_data and 'result' in decoded_data:
                                return decoded_data['result']
            except asyncio.TimeoutError:
                print('TIMEOUT: getConfirmedTransaction {} for {}s'.format(url, timeout))
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return None

        time_insert = int(time.time()) - 90
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `sol_move_deposit` WHERE `status`=%s AND `time_insert`<%s """
                    await cur.execute(sql, ("PENDING", time_insert))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each_mv in result:
                            fetch_tx = await fetch_getConfirmedTransaction(self.bot.erc_node_list['SOL'],
                                                                           each_mv['txn'], 16)
                            if fetch_tx:
                                get_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name),
                                                            "deposit_confirm_depth")
                                net_height = int(redis_utils.redis_conn.get(
                                    f'{config.redis.prefix + config.redis.daemon_height}{coin_name}').decode())
                                height = fetch_tx['slot']
                                confirmed_depth = net_height - height
                                status = "FAILED"
                                if fetch_tx['meta']['err'] is None and confirmed_depth > get_confirm_depth:
                                    status = "CONFIRMED"
                                elif fetch_tx['meta']['err'] is not None and confirmed_depth > get_confirm_depth:
                                    status = "FAILED"
                                else:
                                    continue
                                await self.openConnection()
                                async with self.pool.acquire() as conn:
                                    async with conn.cursor() as cur:
                                        sql = """ UPDATE `sol_move_deposit` SET `blockNumber`=%s, `confirmed_depth`=%s, `status`=%s 
                                                  WHERE `txn`=%s LIMIT 1 """
                                        await cur.execute(sql, (height, confirmed_depth, status, each_mv['txn']))
                                        await conn.commit()
                                        ## Notify
                                        if not each_mv['user_id'].isdigit():
                                            continue
                                        coin_name = each_mv['token_name']
                                        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                        if each_mv['user_id'].isdigit() and each_mv['user_server'] == SERVER_BOT:
                                            member = self.bot.get_user(int(each_mv['user_id']))
                                            if member is not None:
                                                msg = "You got a new deposit (it could take a few minutes to credit): ```" + "Coin: {}\nMoved Tx: {}\nAmount: {}".format(
                                                    coin_name, each_mv['txn'],
                                                    num_format_coin(each_mv['real_amount'], coin_name, coin_decimal,
                                                                    False)) + "```"
                                                try:
                                                    await member.send(msg)
                                                    sql = """ UPDATE `sol_move_deposit` SET `notified_confirmation`=%s, `time_notified`=%s WHERE `txn`=%s AND `token_name`=%s LIMIT 1 """
                                                    await cur.execute(sql, (
                                                    "YES", int(time.time()), each_mv['txn'], coin_name))
                                                    await conn.commit()
                                                except Exception:
                                                    traceback.print_exc(file=sys.stdout)
                                                    sql = """ UPDATE `sol_move_deposit` SET `notified_confirmation`=%s, `failed_notification`=%s WHERE `txn`=%s AND `token_name`=%s LIMIT 1 """
                                                    await cur.execute(sql, ("NO", "YES", each_mv['txn'], coin_name))
                                                    await conn.commit()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def update_ada_wallets_sync(self):
        time_lap = 30  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_ada_wallets_sync"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        async def fetch_wallet_status(url, timeout):
            try:
                headers = {
                    'Content-Type': 'application/json'
                }
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=timeout) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            decoded_data = json.loads(res_data)
                            return decoded_data
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return None

        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `ada_wallets` """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each_wallet in result:
                            fetch_wallet = await fetch_wallet_status(
                                each_wallet['wallet_rpc'] + "v2/wallets/" + each_wallet['wallet_id'], 60)
                            if fetch_wallet:
                                try:
                                    # update height
                                    try:
                                        if each_wallet['wallet_name'] == "withdraw_ada":
                                            height = int(fetch_wallet['tip']['height']['quantity'])
                                            for each_coin in self.bot.coin_name_list:
                                                if getattr(getattr(self.bot.coin_list, each_coin), "type") == "ADA":
                                                    redis_utils.redis_conn.set(
                                                        f'{config.redis.prefix + config.redis.daemon_height}{each_coin.upper()}',
                                                        str(height))
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    await self.openConnection()
                                    async with self.pool.acquire() as conn:
                                        async with conn.cursor() as cur:
                                            sql = """ UPDATE `ada_wallets` SET `status`=%s, `updated`=%s WHERE `wallet_id`=%s LIMIT 1 """
                                            await cur.execute(sql, (
                                            json.dumps(fetch_wallet), int(time.time()), each_wallet['wallet_id']))
                                            await conn.commit()
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            # fetch address if Null
                            if each_wallet['addresses'] is None:
                                fetch_addresses = await fetch_wallet_status(
                                    each_wallet['wallet_rpc'] + "v2/wallets/" + each_wallet['wallet_id'] + "/addresses",
                                    60)
                                if fetch_addresses and len(fetch_addresses) > 0:
                                    addresses = "\n".join([each['id'] for each in fetch_addresses])
                                    try:
                                        await self.openConnection()
                                        async with self.pool.acquire() as conn:
                                            async with conn.cursor() as cur:
                                                sql = """ UPDATE `ada_wallets` SET `addresses`=%s WHERE `wallet_id`=%s LIMIT 1 """
                                                await cur.execute(sql, (addresses, each_wallet['wallet_id']))
                                                await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                            # if synced
                            if each_wallet['syncing'] is None and each_wallet['used_address'] > 0:
                                all_addresses = each_wallet['addresses'].split("\n")
                                # fetch txes last 48h
                                time_end = str(datetime.utcnow().isoformat()).split(".")[0] + "Z"
                                time_start = str((datetime.utcnow() - timedelta(hours=24.0)).isoformat()).split(".")[
                                                 0] + "Z"
                                fetch_transactions = await fetch_wallet_status(
                                    each_wallet['wallet_rpc'] + "v2/wallets/" + each_wallet[
                                        'wallet_id'] + "/transactions?start={}&end={}".format(time_start, time_end), 60)
                                # get transaction already in DB:
                                existing_hash_ids = []
                                try:
                                    await self.openConnection()
                                    async with self.pool.acquire() as conn:
                                        async with conn.cursor() as cur:
                                            sql = """ SELECT DISTINCT `hash_id` FROM `ada_get_transfers` """
                                            await cur.execute(sql, )
                                            result = await cur.fetchall()
                                            if result and len(result) > 0:
                                                existing_hash_ids = [each['hash_id'] for each in result]
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                                if fetch_transactions and len(fetch_transactions) > 0:
                                    data_rows = []
                                    for each_tx in fetch_transactions:
                                        if len(existing_hash_ids) > 0 and each_tx[
                                            'id'] in existing_hash_ids: continue  # skip
                                        try:
                                            if each_tx['status'] == "in_ledger" and each_tx[
                                                'direction'] == "incoming" and len(each_tx['outputs']) > 0:
                                                for each_output in each_tx['outputs']:
                                                    if each_output[
                                                        'address'] not in all_addresses: continue  # skip this output because no address in...
                                                    coin_name = "ADA"
                                                    coin_family = getattr(getattr(self.bot.coin_list, coin_name),
                                                                          "type")
                                                    user_tx = await store.sql_get_userwallet_by_paymentid(
                                                        each_output['address'], coin_name, coin_family)
                                                    # ADA
                                                    data_rows.append((user_tx['user_id'], coin_name, each_tx['id'],
                                                                      each_tx['inserted_at']['height']['quantity'],
                                                                      each_tx['direction'],
                                                                      json.dumps(each_tx['inputs']),
                                                                      json.dumps(each_tx['outputs']),
                                                                      each_output['address'], None, None,
                                                                      each_output['amount']['quantity'] / 10 ** 6, 6,
                                                                      int(time.time()), user_tx['user_server']))
                                                    if each_output['assets'] and len(each_output['assets']) > 0:
                                                        # Asset
                                                        for each_asset in each_output['assets']:
                                                            asset_name = each_asset['asset_name']
                                                            coin_name = None
                                                            for each_coin in self.bot.coin_name_list:
                                                                if asset_name and getattr(
                                                                        getattr(self.bot.coin_list, each_coin),
                                                                        "type") == "ADA" and getattr(
                                                                        getattr(self.bot.coin_list, each_coin),
                                                                        "header") == asset_name:
                                                                    coin_name = each_coin
                                                                    policyID = getattr(
                                                                        getattr(self.bot.coin_list, coin_name),
                                                                        "contract")
                                                                    coin_decimal = getattr(
                                                                        getattr(self.bot.coin_list, coin_name),
                                                                        "decimal")
                                                                    data_rows.append((user_tx['user_id'], coin_name,
                                                                                      each_tx['id'],
                                                                                      each_tx['inserted_at']['height'][
                                                                                          'quantity'],
                                                                                      each_tx['direction'],
                                                                                      json.dumps(each_tx['inputs']),
                                                                                      json.dumps(each_tx['outputs']),
                                                                                      each_output['address'],
                                                                                      asset_name, policyID, each_asset[
                                                                                          'quantity'] / 10 ** coin_decimal,
                                                                                      coin_decimal, int(time.time()),
                                                                                      user_tx['user_server']))
                                                                    break
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                    if len(data_rows) > 0:
                                        try:
                                            await self.openConnection()
                                            async with self.pool.acquire() as conn:
                                                async with conn.cursor() as cur:
                                                    sql = """ INSERT INTO `ada_get_transfers` (`user_id`, `coin_name`, `hash_id`, `inserted_at_height`, `direction`, `input_json`, `output_json`, `output_address`, `asset_name`, `policy_id`, `amount`, `coin_decimal`, `time_insert`, `user_server`) 
                                                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                    await cur.executemany(sql, data_rows)
                                                    await conn.commit()
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def update_balance_trtl_api(self):
        time_lap = 5  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_balance_trtl_api"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            # async def trtl_api_get_transfers(self, url: str, key: str, coin: str, height_start: int = None, height_end: int = None):
            list_trtl_api = await store.get_coin_settings("TRTL-API")
            if len(list_trtl_api) > 0:
                list_coins = [each['coin_name'].upper() for each in list_trtl_api]
                for coin_name in list_coins:
                    # print(f"Check balance {coin_name}")
                    if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 1 or getattr(
                            getattr(self.bot.coin_list, coin_name), "enable_deposit") == 0:
                        await asyncio.sleep(10.0)
                        continue
                    gettopblock = await self.gettopblock(coin_name, time_out=32)
                    height = int(gettopblock['block_header']['height'])
                    try:
                        redis_utils.redis_conn.set(f'{config.redis.prefix + config.redis.daemon_height}{coin_name}',
                                                   str(height))
                    except Exception:
                        traceback.print_exc(file=sys.stdout)

                    url = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
                    key = getattr(getattr(self.bot.coin_list, coin_name), "header")
                    get_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                    get_min_deposit_amount = int(
                        getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit") * 10 ** coin_decimal)

                    get_transfers = await self.trtl_api_get_transfers(url, key, coin_name, height - 2000, height)
                    list_balance_user = {}
                    if get_transfers and len(get_transfers) >= 1:
                        await self.openConnection()
                        async with self.pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                sql = """ SELECT * FROM `cn_get_transfers` WHERE `coin_name`=%s """
                                await cur.execute(sql, (coin_name,))
                                result = await cur.fetchall()
                                d = [i['txid'] for i in result]
                                # print('=================='+coin_name+'===========')
                                # print(d)
                                # print('=================='+coin_name+'===========')
                                for tx in get_transfers:
                                    # Could be one block has two or more tx with different payment ID
                                    # add to balance only confirmation depth meet
                                    if len(tx['transfers']) > 0 and height >= int(
                                            tx['blockHeight']) + get_confirm_depth and tx['transfers'][0][
                                        'amount'] >= get_min_deposit_amount and 'paymentID' in tx:
                                        if 'paymentID' in tx and tx['paymentID'] in list_balance_user:
                                            if tx['transfers'][0]['amount'] > 0:
                                                list_balance_user[tx['paymentID']] += tx['transfers'][0]['amount']
                                        elif 'paymentID' in tx and tx['paymentID'] not in list_balance_user:
                                            if tx['transfers'][0]['amount'] > 0:
                                                list_balance_user[tx['paymentID']] = tx['transfers'][0]['amount']
                                        try:
                                            if tx['hash'] not in d:
                                                addresses = tx['transfers']
                                                address = ''
                                                for each_add in addresses:
                                                    if len(each_add['address']) > 0:
                                                        address = each_add['address']
                                                        break
                                                if 'paymentID' in tx and len(tx['paymentID']) > 0:
                                                    try:
                                                        user_paymentId = await store.sql_get_userwallet_by_paymentid(
                                                            tx['paymentID'], coin_name,
                                                            getattr(getattr(self.bot.coin_list, coin_name), "type"))
                                                        u_server = None
                                                        if user_paymentId: u_server = user_paymentId['user_server']
                                                        sql = """ INSERT IGNORE INTO `cn_get_transfers` (`coin_name`, `txid`, `payment_id`, `height`, `timestamp`, `amount`, `fee`, `decimal`, `address`, `time_insert`, `user_server`) 
                                                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                        await cur.execute(sql, (
                                                        coin_name, tx['hash'], tx['paymentID'], tx['blockHeight'],
                                                        tx['timestamp'],
                                                        float(int(tx['transfers'][0]['amount']) / 10 ** coin_decimal),
                                                        float(int(tx['fee']) / 10 ** coin_decimal), coin_decimal,
                                                        address, int(time.time()), u_server))
                                                        await conn.commit()
                                                        # add to notification list also
                                                        sql = """ INSERT IGNORE INTO `discord_notify_new_tx` (`coin_name`, `txid`, `payment_id`, `height`, `amount`, `fee`, `decimal`, `user_server`) 
                                                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                                                        await cur.execute(sql, (
                                                        coin_name, tx['hash'], tx['paymentID'], tx['blockHeight'],
                                                        float(int(tx['transfers'][0]['amount']) / 10 ** coin_decimal),
                                                        float(int(tx['fee']) / 10 ** coin_decimal), coin_decimal,
                                                        u_server))
                                                        await conn.commit()
                                                    except Exception:
                                                        traceback.print_exc(file=sys.stdout)
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                    elif len(tx['transfers']) > 0 and height < int(
                                            tx['blockHeight']) + get_confirm_depth and tx['transfers'][0][
                                        'amount'] >= get_min_deposit_amount and 'paymentID' in tx:
                                        # add notify to redis and alert deposit. Can be clean later?
                                        if config.notify_new_tx.enable_new_no_confirm == 1:
                                            key_tx_new = config.redis.prefix_new_tx + 'NOCONFIRM'
                                            key_tx_json = config.redis.prefix_new_tx + tx['hash']
                                            try:
                                                if redis_utils.redis_conn.llen(key_tx_new) > 0:
                                                    list_new_tx = redis_utils.redis_conn.lrange(key_tx_new, 0, -1)
                                                    if list_new_tx and len(list_new_tx) > 0 and tx[
                                                        'hash'].encode() not in list_new_tx:
                                                        redis_utils.redis_conn.lpush(key_tx_new, tx['hash'])
                                                        redis_utils.redis_conn.set(key_tx_json, json.dumps(
                                                            {'coin_name': coin_name, 'txid': tx['hash'],
                                                             'payment_id': tx['paymentID'], 'height': tx['blockHeight'],
                                                             'amount': float(int(
                                                                 tx['transfers'][0]['amount']) / 10 ** coin_decimal),
                                                             'fee': float(int(tx['fee']) / 10 ** coin_decimal),
                                                             'decimal': coin_decimal}), ex=86400)
                                                elif redis_utils.redis_conn.llen(key_tx_new) == 0:
                                                    redis_utils.redis_conn.lpush(key_tx_new, tx['hash'])
                                                    redis_utils.redis_conn.set(key_tx_json, json.dumps(
                                                        {'coin_name': coin_name, 'txid': tx['hash'],
                                                         'payment_id': tx['paymentID'], 'height': tx['blockHeight'],
                                                         'amount': float(
                                                             int(tx['transfers'][0]['amount']) / 10 ** coin_decimal),
                                                         'fee': float(int(tx['fee']) / 10 ** coin_decimal),
                                                         'decimal': coin_decimal}), ex=86400)
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                # TODO: update balance cache
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def update_balance_trtl_service(self):
        time_lap = 5  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_balance_trtl_service"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            list_trtl_service = await store.get_coin_settings("TRTL-SERVICE")
            list_bcn_service = await store.get_coin_settings("BCN")
            if len(list_trtl_service + list_bcn_service) > 0:
                list_coins = [each['coin_name'].upper() for each in list_trtl_service + list_bcn_service]
                for coin_name in list_coins:
                    # print(f"Check balance {coin_name}")
                    if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 1 or getattr(
                            getattr(self.bot.coin_list, coin_name), "enable_deposit") == 0:
                        await asyncio.sleep(10.0)
                        continue
                    gettopblock = await self.gettopblock(coin_name, time_out=32)
                    height = int(gettopblock['block_header']['height'])
                    try:
                        redis_utils.redis_conn.set(f'{config.redis.prefix + config.redis.daemon_height}{coin_name}',
                                                   str(height))
                    except Exception:
                        traceback.print_exc(file=sys.stdout)

                    url = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
                    get_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                    get_min_deposit_amount = int(
                        getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit") * 10 ** coin_decimal)

                    get_transfers = await self.trtl_service_getTransactions(url, coin_name, height - 2000, height)
                    list_balance_user = {}
                    if get_transfers and len(get_transfers) >= 1:
                        await self.openConnection()
                        async with self.pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                sql = """ SELECT * FROM `cn_get_transfers` WHERE `coin_name`=%s """
                                await cur.execute(sql, (coin_name,))
                                result = await cur.fetchall()
                                d = [i['txid'] for i in result]
                                # print('=================='+coin_name+'===========')
                                # print(d)
                                # print('=================='+coin_name+'===========')
                                for txes in get_transfers:
                                    tx_in_block = txes['transactions']
                                    for tx in tx_in_block:
                                        # Could be one block has two or more tx with different payment ID
                                        # add to balance only confirmation depth meet
                                        if height >= int(tx['blockIndex']) + get_confirm_depth and tx[
                                            'amount'] >= get_min_deposit_amount and 'paymentId' in tx:
                                            if 'paymentId' in tx and tx['paymentId'] in list_balance_user:
                                                if tx['amount'] > 0: list_balance_user[tx['paymentId']] += tx['amount']
                                            elif 'paymentId' in tx and tx['paymentId'] not in list_balance_user:
                                                if tx['amount'] > 0: list_balance_user[tx['paymentId']] = tx['amount']
                                            try:
                                                if tx['transactionHash'] not in d:
                                                    addresses = tx['transfers']
                                                    address = ''
                                                    for each_add in addresses:
                                                        if len(each_add['address']) > 0:
                                                            address = each_add['address']
                                                            break
                                                    if 'paymentId' in tx and len(tx['paymentId']) > 0:
                                                        try:
                                                            user_paymentId = await store.sql_get_userwallet_by_paymentid(
                                                                tx['paymentId'], coin_name,
                                                                getattr(getattr(self.bot.coin_list, coin_name), "type"))
                                                            u_server = None
                                                            if user_paymentId: u_server = user_paymentId['user_server']
                                                            sql = """ INSERT IGNORE INTO `cn_get_transfers` (`coin_name`, `txid`, `payment_id`, `height`, `timestamp`, `amount`, `fee`, `decimal`, `address`, `time_insert`, `user_server`) 
                                                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                            await cur.execute(sql, (
                                                            coin_name, tx['transactionHash'], tx['paymentId'],
                                                            tx['blockIndex'], tx['timestamp'],
                                                            float(tx['amount'] / 10 ** coin_decimal),
                                                            float(tx['fee'] / 10 ** coin_decimal), coin_decimal,
                                                            address, int(time.time()), u_server))
                                                            await conn.commit()
                                                            # add to notification list also
                                                            sql = """ INSERT IGNORE INTO `discord_notify_new_tx` (`coin_name`, `txid`, `payment_id`, `height`, `amount`, `fee`, `decimal`, `user_server`) 
                                                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                                                            await cur.execute(sql, (
                                                            coin_name, tx['transactionHash'], tx['paymentId'],
                                                            tx['blockIndex'], float(tx['amount'] / 10 ** coin_decimal),
                                                            float(tx['fee'] / 10 ** coin_decimal), coin_decimal,
                                                            u_server))
                                                            await conn.commit()
                                                        except Exception:
                                                            traceback.print_exc(file=sys.stdout)
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                        elif height < int(tx['blockIndex']) + get_confirm_depth and tx[
                                            'amount'] >= get_min_deposit_amount and 'paymentId' in tx:
                                            # add notify to redis and alert deposit. Can be clean later?
                                            if config.notify_new_tx.enable_new_no_confirm == 1:
                                                key_tx_new = config.redis.prefix_new_tx + 'NOCONFIRM'
                                                key_tx_json = config.redis.prefix_new_tx + tx['transactionHash']
                                                try:
                                                    if redis_utils.redis_conn.llen(key_tx_new) > 0:
                                                        list_new_tx = redis_utils.redis_conn.lrange(key_tx_new, 0, -1)
                                                        if list_new_tx and len(list_new_tx) > 0 and tx[
                                                            'transactionHash'].encode() not in list_new_tx:
                                                            redis_utils.redis_conn.lpush(key_tx_new,
                                                                                         tx['transactionHash'])
                                                            redis_utils.redis_conn.set(key_tx_json, json.dumps(
                                                                {'coin_name': coin_name, 'txid': tx['transactionHash'],
                                                                 'payment_id': tx['paymentId'],
                                                                 'height': tx['blockIndex'],
                                                                 'amount': float(tx['amount'] / 10 ** coin_decimal),
                                                                 'fee': tx['fee'], 'decimal': coin_decimal}), ex=86400)
                                                    elif redis_utils.redis_conn.llen(key_tx_new) == 0:
                                                        redis_utils.redis_conn.lpush(key_tx_new, tx['transactionHash'])
                                                        redis_utils.redis_conn.set(key_tx_json, json.dumps(
                                                            {'coin_name': coin_name, 'txid': tx['transactionHash'],
                                                             'payment_id': tx['paymentId'], 'height': tx['blockIndex'],
                                                             'amount': float(tx['amount'] / 10 ** coin_decimal),
                                                             'fee': tx['fee'], 'decimal': coin_decimal}), ex=86400)
                                                except Exception:
                                                    traceback.print_exc(file=sys.stdout)
                    # TODO: update user balance
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def update_balance_xmr(self):
        time_lap = 5  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_balance_xmr"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            list_xmr_api = await store.get_coin_settings("XMR")
            if len(list_xmr_api) > 0:
                list_coins = [each['coin_name'].upper() for each in list_xmr_api]
                for coin_name in list_coins:
                    # print(f"Check balance {coin_name}")
                    if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 1 or getattr(
                            getattr(self.bot.coin_list, coin_name), "enable_deposit") == 0:
                        await asyncio.sleep(10.0)
                        continue
                    gettopblock = await self.gettopblock(coin_name, time_out=32)
                    height = int(gettopblock['block_header']['height'])
                    try:
                        redis_utils.redis_conn.set(f'{config.redis.prefix + config.redis.daemon_height}{coin_name}',
                                                   str(height))
                    except Exception:
                        traceback.print_exc(file=sys.stdout)

                    url = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
                    get_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                    get_min_deposit_amount = int(
                        getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit") * 10 ** coin_decimal)

                    payload = {
                        "in": True,
                        "out": True,
                        "pending": False,
                        "failed": False,
                        "pool": False,
                        "filter_by_height": True,
                        "min_height": height - 2000,
                        "max_height": height
                    }

                    get_transfers = await self.wallet_api.call_aiohttp_wallet_xmr_bcn('get_transfers', coin_name,
                                                                                      payload=payload)
                    if get_transfers and len(get_transfers) >= 1 and 'in' in get_transfers:
                        try:
                            await self.openConnection()
                            async with self.pool.acquire() as conn:
                                async with conn.cursor() as cur:
                                    sql = """ SELECT * FROM `cn_get_transfers` WHERE `coin_name`=%s """
                                    await cur.execute(sql, (coin_name,))
                                    result = await cur.fetchall()
                                    d = [i['txid'] for i in result]
                                    # print('=================='+coin_name+'===========')
                                    # print(d)
                                    # print('=================='+coin_name+'===========')
                                    list_balance_user = {}
                                    for tx in get_transfers['in']:
                                        # add to balance only confirmation depth meet
                                        if height >= int(tx['height']) + get_confirm_depth and tx[
                                            'amount'] >= get_min_deposit_amount and 'payment_id' in tx:
                                            if 'payment_id' in tx and tx['payment_id'] in list_balance_user:
                                                list_balance_user[tx['payment_id']] += tx['amount']
                                            elif 'payment_id' in tx and tx['payment_id'] not in list_balance_user:
                                                list_balance_user[tx['payment_id']] = tx['amount']
                                            try:
                                                if tx['txid'] not in d:
                                                    tx_address = tx['address'] if coin_name != "LTHN" else getattr(
                                                        getattr(self.bot.coin_list, coin_name), "MainAddress")
                                                    user_paymentId = await store.sql_get_userwallet_by_paymentid(
                                                        tx['payment_id'], coin_name,
                                                        getattr(getattr(self.bot.coin_list, coin_name), "type"))
                                                    u_server = None
                                                    if user_paymentId: u_server = user_paymentId['user_server']
                                                    sql = """ INSERT IGNORE INTO `cn_get_transfers` (`coin_name`, `in_out`, `txid`, `payment_id`, `height`, `timestamp`, `amount`, `fee`, `decimal`, `address`, `time_insert`, `user_server`) 
                                                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                    await cur.execute(sql, (
                                                    coin_name, tx['type'].upper(), tx['txid'], tx['payment_id'],
                                                    tx['height'], tx['timestamp'],
                                                    float(tx['amount'] / 10 ** coin_decimal),
                                                    float(tx['fee'] / 10 ** coin_decimal), coin_decimal, tx_address,
                                                    int(time.time()), u_server))
                                                    await conn.commit()
                                                    # add to notification list also
                                                    sql = """ INSERT IGNORE INTO `discord_notify_new_tx` (`coin_name`, `txid`, `payment_id`, `height`, `amount`, `fee`, `decimal`, `user_server`) 
                                                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                                                    await cur.execute(sql, (
                                                    coin_name, tx['txid'], tx['payment_id'], tx['height'],
                                                    float(tx['amount'] / 10 ** coin_decimal),
                                                    float(tx['fee'] / 10 ** coin_decimal), coin_decimal, u_server))
                                                    await conn.commit()
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                        elif height < int(tx['height']) + get_confirm_depth and tx[
                                            'amount'] >= get_min_deposit_amount and 'payment_id' in tx:
                                            # add notify to redis and alert deposit. Can be clean later?
                                            if config.notify_new_tx.enable_new_no_confirm == 1:
                                                key_tx_new = config.redis.prefix_new_tx + 'NOCONFIRM'
                                                key_tx_json = config.redis.prefix_new_tx + tx['txid']
                                                try:
                                                    if redis_utils.redis_conn.llen(key_tx_new) > 0:
                                                        list_new_tx = redis_utils.redis_conn.lrange(key_tx_new, 0, -1)
                                                        if list_new_tx and len(list_new_tx) > 0 and tx[
                                                            'txid'].encode() not in list_new_tx:
                                                            redis_utils.redis_conn.lpush(key_tx_new, tx['txid'])
                                                            redis_utils.redis_conn.set(key_tx_json, json.dumps(
                                                                {'coin_name': coin_name, 'txid': tx['txid'],
                                                                 'payment_id': tx['payment_id'], 'height': tx['height'],
                                                                 'amount': float(tx['amount'] / 10 ** coin_decimal),
                                                                 'fee': float(tx['fee'] / 10 ** coin_decimal),
                                                                 'decimal': coin_decimal}), ex=86400)
                                                    elif redis_utils.redis_conn.llen(key_tx_new) == 0:
                                                        redis_utils.redis_conn.lpush(key_tx_new, tx['txid'])
                                                        redis_utils.redis_conn.set(key_tx_json, json.dumps(
                                                            {'coin_name': coin_name, 'txid': tx['txid'],
                                                             'payment_id': tx['payment_id'], 'height': tx['height'],
                                                             'amount': float(tx['amount'] / 10 ** coin_decimal),
                                                             'fee': float(tx['fee'] / 10 ** coin_decimal),
                                                             'decimal': coin_decimal}), ex=86400)
                                                except Exception:
                                                    traceback.print_exc(file=sys.stdout)
                                    # TODO: update user balance
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def update_balance_btc(self):
        time_lap = 5  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_balance_btc"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            # async def trtl_api_get_transfers(self, url: str, key: str, coin: str, height_start: int = None, height_end: int = None):
            list_btc_api = await store.get_coin_settings("BTC")
            if len(list_btc_api) > 0:
                list_coins = [each['coin_name'].upper() for each in list_btc_api]
                for coin_name in list_coins:
                    # print(f"Check balance {coin_name}")
                    if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 1 or getattr(
                            getattr(self.bot.coin_list, coin_name), "enable_deposit") == 0:
                        await asyncio.sleep(10.0)
                        continue
                    if getattr(getattr(self.bot.coin_list, coin_name), "use_getinfo_btc") == 1:
                        gettopblock = await self.wallet_api.call_doge('getinfo', coin_name)
                    else:
                        gettopblock = await self.wallet_api.call_doge('getblockchaininfo', coin_name)
                    height = int(gettopblock['blocks'])
                    try:
                        redis_utils.redis_conn.set(f'{config.redis.prefix + config.redis.daemon_height}{coin_name}',
                                                   str(height))
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                        await asyncio.sleep(1.0)
                        continue

                    get_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                    get_min_deposit_amount = int(
                        getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit") * 10 ** coin_decimal)

                    payload = '"*", 100, 0'
                    if coin_name in ["HNS"]:
                        payload = '"default"'
                    get_transfers = await self.wallet_api.call_doge('listtransactions', coin_name, payload=payload)
                    if get_transfers and len(get_transfers) >= 1:
                        try:
                            await self.openConnection()
                            async with self.pool.acquire() as conn:
                                async with conn.cursor() as cur:
                                    sql = """ SELECT * FROM `doge_get_transfers` WHERE `coin_name`=%s AND `category` IN (%s, %s) """
                                    await cur.execute(sql, (coin_name, 'receive', 'send'))
                                    result = await cur.fetchall()
                                    d = [i['txid'] for i in result]
                                    # print('=================='+coin_name+'===========')
                                    # print(d)
                                    # print('=================='+coin_name+'===========')
                                    list_balance_user = {}
                                    for tx in get_transfers:
                                        # add to balance only confirmation depth meet
                                        if get_confirm_depth <= int(tx['confirmations']) and tx[
                                            'amount'] >= get_min_deposit_amount:
                                            if 'address' in tx and tx['address'] in list_balance_user and tx[
                                                'amount'] > 0:
                                                list_balance_user[tx['address']] += tx['amount']
                                            elif 'address' in tx and tx['address'] not in list_balance_user and tx[
                                                'amount'] > 0:
                                                list_balance_user[tx['address']] = tx['amount']
                                            try:
                                                if tx['txid'] not in d:
                                                    user_paymentId = await store.sql_get_userwallet_by_paymentid(
                                                        tx['address'], coin_name,
                                                        getattr(getattr(self.bot.coin_list, coin_name), "type"))
                                                    u_server = None
                                                    if user_paymentId: u_server = user_paymentId['user_server']
                                                    if getattr(getattr(self.bot.coin_list, coin_name), "coin_has_pos") == 1:
                                                        # generate from mining
                                                        if tx['category'] == 'receive' and 'generated' not in tx:
                                                            sql = """ INSERT IGNORE INTO `doge_get_transfers` (`coin_name`, `txid`, `blockhash`, `address`, `blocktime`, `amount`, `fee`, `confirmations`, `category`, `time_insert`, `user_server`) 
                                                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                            await cur.execute(sql, (
                                                            coin_name, tx['txid'], tx['blockhash'], tx['address'],
                                                            tx['blocktime'], float(tx['amount']),
                                                            float(tx['fee']) if 'fee' in tx else None,
                                                            tx['confirmations'], tx['category'], int(time.time()),
                                                            u_server))
                                                            await conn.commit()
                                                            # Notify Tx
                                                        if (tx['amount'] > 0) and tx[
                                                            'category'] == 'receive' and 'generated' not in tx:
                                                            sql = """ INSERT IGNORE INTO `discord_notify_new_tx` (`coin_name`, `txid`, `payment_id`, `blockhash`, `amount`, `fee`, `decimal`, `user_server`) 
                                                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                                                            await cur.execute(sql, (
                                                            coin_name, tx['txid'], tx['address'], tx['blockhash'],
                                                            float(tx['amount']),
                                                            float(tx['fee']) if 'fee' in tx else None, coin_decimal,
                                                            u_server))
                                                            await conn.commit()
                                                    else:
                                                        # generate from mining
                                                        if tx['category'] == "receive" or tx['category'] == "generate":
                                                            sql = """ INSERT IGNORE INTO `doge_get_transfers` (`coin_name`, `txid`, `blockhash`, `address`, `blocktime`, `amount`, `fee`, `confirmations`, `category`, `time_insert`, `user_server`) 
                                                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                            await cur.execute(sql, (
                                                            coin_name, tx['txid'], tx['blockhash'], tx['address'],
                                                            tx['blocktime'], float(tx['amount']),
                                                            float(tx['fee']) if 'fee' in tx else None,
                                                            tx['confirmations'], tx['category'], int(time.time()),
                                                            u_server))
                                                            await conn.commit()
                                                        # add to notification list also, doge payment_id = address
                                                        if (tx['amount'] > 0) and tx['category'] == 'receive':
                                                            sql = """ INSERT IGNORE INTO `discord_notify_new_tx` (`coin_name`, `txid`, `payment_id`, `blockhash`, `amount`, `fee`, `decimal`, `user_server`) 
                                                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                                                            await cur.execute(sql, (
                                                            coin_name, tx['txid'], tx['address'], tx['blockhash'],
                                                            float(tx['amount']),
                                                            float(tx['fee']) if 'fee' in tx else None, coin_decimal,
                                                            u_server))
                                                            await conn.commit()
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                        if get_confirm_depth > int(tx['confirmations']) > 0 \
                                            and tx['amount'] >= get_min_deposit_amount:
                                            if getattr(getattr(self.bot.coin_list, coin_name), "coin_has_pos") == 1 \
                                                and tx['category'] == 'receive' and 'generated' in tx and tx['amount'] > 0:
                                                continue
                                            # add notify to redis and alert deposit. Can be clean later?
                                            if config.notify_new_tx.enable_new_no_confirm == 1:
                                                key_tx_new = config.redis.prefix_new_tx + 'NOCONFIRM'
                                                key_tx_json = config.redis.prefix_new_tx + tx['txid']
                                                try:
                                                    if redis_utils.redis_conn.llen(key_tx_new) > 0:
                                                        list_new_tx = redis_utils.redis_conn.lrange(key_tx_new, 0, -1)
                                                        if list_new_tx and len(list_new_tx) > 0 and tx[
                                                            'txid'].encode() not in list_new_tx:
                                                            redis_utils.redis_conn.lpush(key_tx_new, tx['txid'])
                                                            redis_utils.redis_conn.set(key_tx_json, json.dumps(
                                                                {'coin_name': coin_name, 'txid': tx['txid'],
                                                                 'payment_id': tx['address'],
                                                                 'blockhash': tx['blockhash'], 'amount': tx['amount'],
                                                                 'decimal': coin_decimal}), ex=86400)
                                                    elif redis_utils.redis_conn.llen(key_tx_new) == 0:
                                                        redis_utils.redis_conn.lpush(key_tx_new, tx['txid'])
                                                        redis_utils.redis_conn.set(key_tx_json, json.dumps(
                                                            {'coin_name': coin_name, 'txid': tx['txid'],
                                                             'payment_id': tx['address'], 'blockhash': tx['blockhash'],
                                                             'amount': tx['amount'], 'decimal': coin_decimal}),
                                                                                   ex=86400)
                                                except Exception:
                                                    traceback.print_exc(file=sys.stdout)
                                    # TODO: update balance cache
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                    await asyncio.sleep(3.0)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def update_balance_neo(self):
        time_lap = 10  # seconds
        # await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_balance_neo"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        coin_name = "NEO"
        try:
            gettopblock = await self.wallet_api.call_neo('getblockcount', payload=[]) 
            try:
                height = int(gettopblock['result'])
                redis_utils.redis_conn.set(f'{config.redis.prefix + config.redis.daemon_height}{coin_name}',
                                           str(height))
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot("wallet update_balance_neo " + str(traceback.format_exc()))
                await asyncio.sleep(1.0)
                return
            list_user_addresses = await store.recent_balance_call_neo_user(7200) # last 2hrs
            list_received_in_db = await store.neo_get_existing_tx()
            all_neo_asset_hash = []
            coin_name_by_assethash = {}
            for each_coin in self.bot.coin_name_list:
                if getattr(getattr(self.bot.coin_list, each_coin), "type") == "NEO" and \
                    getattr(getattr(self.bot.coin_list, each_coin), "enable_deposit") != 0:
                    assethash = getattr(getattr(self.bot.coin_list, each_coin), "contract")
                    all_neo_asset_hash.append(assethash)
                    coin_name_by_assethash[assethash] = getattr(getattr(self.bot.coin_list, each_coin), "coin_name")
            if len(list_user_addresses) > 0:
                data_rows = []
                if getattr(getattr(self.bot.coin_list, coin_name), "enable_deposit") != 0:
                    for each_address in list_user_addresses:
                        try:
                            get_transfers = await self.wallet_api.call_neo('getnep17transfers', payload=[each_address['balance_wallet_address'], 0])
                            if 'result' in get_transfers and get_transfers['result'] and 'received' in get_transfers['result'] and get_transfers['result']['received'] and len(get_transfers['result']['received']) > 0:
                                for each_received in get_transfers['result']['received']:
                                    if each_received['txhash'] not in list_received_in_db and \
                                        each_received['assethash'] in all_neo_asset_hash:
                                        coin_name = coin_name_by_assethash[each_received['assethash']]
                                        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                        real_min_deposit = getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit")
                                        number_conf = height - each_received['blockindex']
                                        get_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                                        if number_conf <= get_confirm_depth:
                                            continue
                                        if real_min_deposit and int(each_received['amount'])/10**coin_decimal < real_min_deposit:
                                            await logchanbot("{} tx hash: {} less than minimum deposit.".format(coin_name, each_received['txhash']))
                                            continue
                                        data_rows.append((each_address['user_id'], coin_name, coin_decimal, each_received['assethash'], 
                                                          each_received['txhash'], each_address['balance_wallet_address'],
                                                          each_received['timestamp'], each_received['blockindex'], 
                                                          int(each_received['amount'])/10**coin_decimal, number_conf, 
                                                          'received', int(time.time())))
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                if len(data_rows) > 0:
                    try:
                        await self.openConnection()
                        async with self.pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                sql = """ INSERT INTO `neo_get_transfers` 
                                          (`user_id`, `coin_name`, `coin_decimal`, `assethash`, `txhash`, `address`, 
                                          `blocktime`, `blockindex`, `amount`, `confirmations`, 
                                          `category`, `time_insert`) 
                                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                await cur.executemany(sql, data_rows)
                                await conn.commit()
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def notify_new_confirmed_neo(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_new_confirmed_neo"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `neo_get_transfers` WHERE `notified_confirmation`=%s AND `failed_notification`=%s AND `user_server`=%s """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            if eachTx['user_id']:
                                if not eachTx['user_id'].isdigit():
                                    continue
                                coin_name = eachTx['coin_name']
                                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                if eachTx['user_id'].isdigit() and eachTx['user_server'] == SERVER_BOT:
                                    member = self.bot.get_user(int(eachTx['user_id']))
                                    if member is not None:
                                        msg = "You got a new deposit (it could take a few minutes to credit): ```" + "Coin: {}\nTx: {}\nAmount: {}".format(
                                            coin_name, eachTx['txhash'],
                                            num_format_coin(eachTx['amount'], coin_name, coin_decimal, False)) + "```"
                                        try:
                                            await member.send(msg)
                                            sql = """ UPDATE `neo_get_transfers` SET `notified_confirmation`=%s, `time_notified`=%s WHERE `txhash`=%s AND `coin_name`=%s LIMIT 1 """
                                            await cur.execute(sql,
                                                              ("YES", int(time.time()), eachTx['txhash'], coin_name))
                                            await conn.commit()
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                            sql = """ UPDATE `neo_get_transfers` SET `notified_confirmation`=%s, `failed_notification`=%s WHERE `txhash`=%s AND `coin_name`=%s LIMIT 1 """
                                            await cur.execute(sql, ("NO", "YES", eachTx['txhash'], coin_name))
                                            await conn.commit()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def update_balance_chia(self):
        time_lap = 5  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_balance_chia"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            list_chia_api = await store.get_coin_settings("CHIA")
            if len(list_chia_api) > 0:
                list_coins = [each['coin_name'].upper() for each in list_chia_api]
                for coin_name in list_coins:
                    # print(f"Check balance {coin_name}")
                    if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 1 or getattr(
                            getattr(self.bot.coin_list, coin_name), "enable_deposit") == 0:
                        await asyncio.sleep(10.0)
                        continue
                    gettopblock = await self.gettopblock(coin_name, time_out=32)
                    height = int(gettopblock['height'])
                    try:
                        redis_utils.redis_conn.set(f'{config.redis.prefix + config.redis.daemon_height}{coin_name}',
                                                   str(height))
                    except Exception:
                        traceback.print_exc(file=sys.stdout)

                    get_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                    get_min_deposit_amount = int(
                        getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit") * 10 ** coin_decimal)

                    payload = {'wallet_id': 1}
                    list_tx = await self.wallet_api.call_xch('get_transactions', coin_name, payload=payload)
                    if 'success' in list_tx and list_tx['transactions'] and len(list_tx['transactions']) > 0:
                        get_transfers = list_tx['transactions']
                        if get_transfers and len(get_transfers) >= 1:
                            try:
                                await self.openConnection()
                                async with self.pool.acquire() as conn:
                                    async with conn.cursor() as cur:
                                        sql = """ SELECT * FROM `xch_get_transfers` WHERE `coin_name`=%s  """
                                        await cur.execute(sql, (coin_name))
                                        result = await cur.fetchall()
                                        d = [i['txid'] for i in result]
                                        dheight = ["{}{}".format(i['height'], i['address']) for i in result]
                                        # print('=================='+coin_name+'===========')
                                        # print(d)
                                        # print('=================='+coin_name+'===========')
                                        list_balance_user = {}
                                        for tx in get_transfers:
                                            if "{}{}".format(tx['confirmed_at_height'], tx['to_address']) in dheight:
                                                # skip
                                                continue
                                            # add to balance only confirmation depth meet
                                            if height >= get_confirm_depth + int(tx['confirmed_at_height']) and tx[
                                                'amount'] >= get_min_deposit_amount:
                                                if 'to_address' in tx and tx['to_address'] in list_balance_user and tx[
                                                    'amount'] > 0:
                                                    list_balance_user[tx['to_address']] += tx['amount']
                                                elif 'to_address' in tx and tx[
                                                    'to_address'] not in list_balance_user and tx['amount'] > 0:
                                                    list_balance_user[tx['to_address']] = tx['amount']
                                                try:
                                                    if tx['name'] not in d:
                                                        # receive
                                                        if len(tx['sent_to']) == 0:
                                                            user_paymentId = await store.sql_get_userwallet_by_paymentid(
                                                                tx['to_address'], coin_name,
                                                                getattr(getattr(self.bot.coin_list, coin_name), "type"))
                                                            u_server = None
                                                            if user_paymentId: u_server = user_paymentId['user_server']

                                                            sql = """ INSERT IGNORE INTO `xch_get_transfers` (`coin_name`, `txid`, `height`, `timestamp`, `address`, `amount`, `fee`, `decimal`, `time_insert`, `user_server`) 
                                                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                            await cur.execute(sql, (
                                                            coin_name, tx['name'], tx['confirmed_at_height'],
                                                            tx['created_at_time'],
                                                            tx['to_address'], float(tx['amount'] / 10 ** coin_decimal),
                                                            float(tx['fee_amount'] / 10 ** coin_decimal), coin_decimal,
                                                            int(time.time()), u_server))
                                                            await conn.commit()
                                                        # add to notification list also, doge payment_id = address
                                                        if (tx['amount'] > 0) and len(tx['sent_to']) == 0:
                                                            user_paymentId = await store.sql_get_userwallet_by_paymentid(
                                                                tx['to_address'], coin_name,
                                                                getattr(getattr(self.bot.coin_list, coin_name), "type"))
                                                            u_server = None
                                                            if user_paymentId: u_server = user_paymentId['user_server']
                                                            sql = """ INSERT IGNORE INTO `discord_notify_new_tx` (`coin_name`, `txid`, `payment_id`, `blockhash`, `height`, `amount`, `fee`, `decimal`, `user_server`) 
                                                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                            await cur.execute(sql, (
                                                            coin_name, tx['name'], tx['to_address'], tx['name'],
                                                            int(tx['confirmed_at_height']),
                                                            float(tx['amount'] / 10 ** coin_decimal),
                                                            float(tx['fee_amount'] / 10 ** coin_decimal), coin_decimal,
                                                            u_server))
                                                            await conn.commit()
                                                except Exception:
                                                    traceback.print_exc(file=sys.stdout)
                                            if height < get_confirm_depth + int(tx['confirmed_at_height']) and tx[
                                                'amount'] >= get_min_deposit_amount:
                                                # add notify to redis and alert deposit. Can be clean later?
                                                if config.notify_new_tx.enable_new_no_confirm == 1:
                                                    key_tx_new = config.redis.prefix_new_tx + 'NOCONFIRM'
                                                    key_tx_json = config.redis.prefix_new_tx + tx['name']
                                                    try:
                                                        if redis_utils.redis_conn.llen(key_tx_new) > 0:
                                                            list_new_tx = redis_utils.redis_conn.lrange(key_tx_new, 0,
                                                                                                        -1)
                                                            if list_new_tx and len(list_new_tx) > 0 and tx[
                                                                'name'].encode() not in list_new_tx:
                                                                redis_utils.redis_conn.lpush(key_tx_new, tx['name'])
                                                                redis_utils.redis_conn.set(key_tx_json, json.dumps(
                                                                    {'coin_name': coin_name, 'txid': tx['name'],
                                                                     'payment_id': tx['to_address'],
                                                                     'height': tx['confirmed_at_height'],
                                                                     'amount': float(tx['amount'] / 10 ** coin_decimal),
                                                                     'decimal': coin_decimal}), ex=86400)
                                                        elif redis_utils.redis_conn.llen(key_tx_new) == 0:
                                                            redis_utils.redis_conn.lpush(key_tx_new, tx['name'])
                                                            redis_utils.redis_conn.set(key_tx_json, json.dumps(
                                                                {'coin_name': coin_name, 'txid': tx['name'],
                                                                 'payment_id': tx['to_address'],
                                                                 'height': tx['confirmed_at_height'],
                                                                 'amount': float(tx['amount'] / 10 ** coin_decimal),
                                                                 'decimal': coin_decimal}), ex=86400)
                                                    except Exception:
                                                        traceback.print_exc(file=sys.stdout)
                                        # TODO: update balance users
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def update_balance_nano(self):
        time_lap = 5  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_balance_nano"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            updated = 0
            list_nano = await store.get_coin_settings("NANO")
            if len(list_nano) > 0:
                list_coins = [each['coin_name'].upper() for each in list_nano]
                for coin_name in list_coins:
                    # print(f"Check balance {coin_name}")
                    if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 1 or getattr(
                            getattr(self.bot.coin_list, coin_name), "enable_deposit") == 0:
                        await asyncio.sleep(10.0)
                        continue
                    start = time.time()
                    timeout = 16
                    try:
                        gettopblock = await self.wallet_api.call_nano(coin_name, payload='{ "action": "block_count" }')
                        if gettopblock and 'count' in gettopblock:
                            height = int(gettopblock['count'])
                            # store in redis
                            try:
                                redis_utils.redis_conn.set(
                                    f'{config.redis.prefix + config.redis.daemon_height}{coin_name}', str(height))
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    get_balance = await self.wallet_api.nano_get_wallet_balance_elements(coin_name)
                    all_user_info = await store.sql_nano_get_user_wallets(coin_name)
                    all_deposit_address = {}
                    all_deposit_address_keys = []
                    if len(all_user_info) > 0:
                        all_deposit_address_keys = [each['balance_wallet_address'] for each in all_user_info]
                        for each in all_user_info:
                            all_deposit_address[each['balance_wallet_address']] = each
                    if get_balance and len(get_balance) > 0:
                        for address, balance in get_balance.items():
                            try:
                                # if bigger than minimum deposit, and no pending and the address is in user database addresses
                                real_min_deposit = getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit")
                                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                if float(int(balance['balance']) / 10 ** coin_decimal) >= real_min_deposit and float(
                                        int(balance[
                                                'pending']) / 10 ** coin_decimal) == 0 and address in all_deposit_address_keys:
                                    # let's move balance to main_address
                                    try:
                                        main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                                        move_to_deposit = await self.wallet_api.nano_sendtoaddress(address,
                                                                                                   main_address, int(
                                                balance['balance']), coin_name)  # atomic
                                        # add to DB
                                        if move_to_deposit:
                                            try:
                                                await self.openConnection()
                                                async with self.pool.acquire() as conn:
                                                    async with conn.cursor() as cur:
                                                        sql = """ INSERT INTO nano_move_deposit (`coin_name`, `user_id`, `balance_wallet_address`, `to_main_address`, `amount`, `decimal`, `block`, `time_insert`, `user_server`) 
                                                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                                        await cur.execute(sql, (
                                                        coin_name, all_deposit_address[address]['user_id'], address,
                                                        main_address,
                                                        float(int(balance['balance']) / 10 ** coin_decimal),
                                                        coin_decimal, move_to_deposit['block'], int(time.time()),
                                                        all_deposit_address[address]['user_server']))
                                                        await conn.commit()
                                                        updated += 1
                                                        # add to notification list also
                                                        # txid = new block ID
                                                        # payment_id = deposit address
                                                        sql = """ INSERT IGNORE INTO discord_notify_new_tx (`coin_name`, `txid`, `payment_id`, `amount`, `decimal`) 
                                                                  VALUES (%s, %s, %s, %s, %s) """
                                                        await cur.execute(sql, (
                                                        coin_name, move_to_deposit['block'], address,
                                                        float(int(balance['balance']) / 10 ** coin_decimal),
                                                        coin_decimal,))
                                                        await conn.commit()
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                    end = time.time()
                    # print('Done update balance: '+ coin_name+ ' updated *'+str(updated)+'* duration (s): '+str(end - start))
                    await asyncio.sleep(4.0)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=10.0)
    async def update_balance_erc20(self):
        time_lap = 2  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_balance_erc20"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            erc_contracts = await self.get_all_contracts("ERC-20", False)
            if len(erc_contracts) > 0:
                for each_c in erc_contracts:
                    try:
                        await store.sql_check_minimum_deposit_erc20(self.bot.erc_node_list[each_c['net_name']],
                                                                    each_c['net_name'], each_c['coin_name'],
                                                                    each_c['contract'], each_c['decimal'],
                                                                    each_c['min_move_deposit'], each_c['min_gas_tx'],
                                                                    each_c['gas_ticker'], each_c['move_gas_amount'],
                                                                    each_c['chain_id'], each_c['real_deposit_fee'],
                                                                    each_c['erc20_approve_spend'], 7200)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
            main_tokens = await self.get_all_contracts("ERC-20", True)
            if len(main_tokens) > 0:
                for each_c in main_tokens:
                    try:
                        await store.sql_check_minimum_deposit_erc20(self.bot.erc_node_list[each_c['net_name']],
                                                                    each_c['net_name'], each_c['coin_name'], None,
                                                                    each_c['decimal'], each_c['min_move_deposit'],
                                                                    each_c['min_gas_tx'], each_c['gas_ticker'],
                                                                    each_c['move_gas_amount'], each_c['chain_id'],
                                                                    each_c['real_deposit_fee'], 0, 7200)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def update_balance_xrp(self):
        time_lap = 5  # seconds

        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_balance_xrp"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)

        try:
            # update height
            try:
                get_height = await xrp_get_status(self.bot.erc_node_list['XRP'], 16)
                if get_height:
                    height = get_height['result']['ledger_index']
                else:
                    return
                for each_coin in self.bot.coin_name_list:
                    if getattr(getattr(self.bot.coin_list, each_coin), "type") == "XRP":
                        redis_utils.redis_conn.set(
                            f'{config.redis.prefix + config.redis.daemon_height}{each_coin.upper()}',
                            str(height))
            except Exception:
                traceback.print_exc(file=sys.stdout)
            # get transactions
            main_address = getattr(getattr(self.bot.coin_list, "XRP"), "MainAddress")
            list_tx = await xrp_get_latest_transactions(self.bot.erc_node_list['XRP'], main_address)
            get_existing_tx = await self.wallet_api.xrp_get_list_xrp_get_transfers()
            if len(list_tx) > 0:
                for each_tx in list_tx:
                    try:
                        if 'DestinationTag' in each_tx['tx'] and main_address == each_tx['tx']['Destination'] \
                            and each_tx['tx']['TransactionType'] == "Payment" \
                            and each_tx['meta']['TransactionResult'] == "tesSUCCESS":
                            to_address = each_tx['tx']['Destination'] # main_address
                            destination_tag = each_tx['tx']['DestinationTag'] # int
                            before_2000s = (datetime(2000, 1, 1, 0, 0) - datetime(1970, 1, 1)).total_seconds()
                            timestamp = before_2000s + each_tx['tx']['date']
                            get_user = await self.wallet_api.xrp_get_user_by_tag(destination_tag)
                            if get_user is None:
                                continue
                            if each_tx['tx']['hash'] in get_existing_tx:
                                continue
                            if type(each_tx['tx']['Amount']) is dict:
                                # Token
                                issuer = each_tx['tx']['Amount']['issuer']
                                currency = each_tx['tx']['Amount']['currency']
                                value = float(each_tx['tx']['Amount']['value'])
                                # Check attribute
                                coin_name = currency + "XRP"
                                coin_issuer = getattr(getattr(self.bot.coin_list, coin_name), "header")
                                if issuer != coin_issuer:
                                    continue
                                await self.wallet_api.xrp_insert_deposit(coin_name, issuer, get_user['user_id'], each_tx['tx']['hash'], each_tx['tx']['inLedger'], timestamp, value, 0, main_address, destination_tag, int(time.time()))
                            elif type(each_tx['tx']['Amount']) is str:
                                # XRP
                                value = float(int(each_tx['tx']['Amount'])/10**6) # XRP: 6 decimal
                                await self.wallet_api.xrp_insert_deposit("XRP", None, get_user['user_id'], each_tx['tx']['hash'], each_tx['tx']['inLedger'], timestamp, value, 6, main_address, destination_tag, int(time.time()))
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def notify_new_confirmed_xrp(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_new_confirmed_xrp"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `xrp_get_transfers` WHERE `notified_confirmation`=%s AND `failed_notification`=%s AND `user_server`=%s """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            coin_name = eachTx['coin_name']
                            if eachTx['user_id']:
                                if not eachTx['user_id'].isdigit():
                                    continue
                                try:
                                    key = "notify_new_tx_{}_{}_{}".format(coin_name, eachTx['user_id'],
                                                                          eachTx['txid'])
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + "Coin: {}\nTx: {}\nAmount: {}".format(
                                        coin_name, eachTx['txid'],
                                        num_format_coin(eachTx['amount'], coin_name, coin_decimal,
                                                        False)) + "```"
                                    try:
                                        await member.send(msg)
                                        sql = """ UPDATE `xrp_get_transfers` SET `notified_confirmation`=%s, `time_notified`=%s WHERE `txid`=%s LIMIT 1 """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['txid']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `xrp_get_transfers` SET `notified_confirmation`=%s, `failed_notification`=%s WHERE `txid`=%s LIMIT 1 """
                                        await cur.execute(sql, ("NO", "YES", eachTx['txid']))
                                        await conn.commit()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def update_balance_near(self):
        time_lap = 5  # seconds

        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_balance_near"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)

        try:
            # Check main
            near_contracts = await self.get_all_contracts("NEAR", False)
            coin_name = "NEAR"
            get_head = await near_get_status(self.bot.erc_node_list['NEAR'], 12)
            try:
                if get_head:
                    height = get_head['result']['sync_info']['latest_block_height']
                    redis_utils.redis_conn.set(f'{config.redis.prefix + config.redis.daemon_height}{coin_name}',
                                               str(height))
                    if len(near_contracts) > 0:
                        for each_coin in near_contracts:
                            name = each_coin['coin_name']
                            try:
                                redis_utils.redis_conn.set(f'{config.redis.prefix + config.redis.daemon_height}{name}',
                                                           str(height))
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
            except Exception:
                traceback.print_exc(file=sys.stdout)

            real_min_deposit = getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit")
            real_deposit_fee = getattr(getattr(self.bot.coin_list, coin_name), "real_deposit_fee")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            list_user_addresses = await store.sql_get_all_near_user(coin_name, 7200) # last 2hrs
            list_recent_mv = await store.sql_recent_near_move_deposit(1200) # 20mn
            main_address = getattr(getattr(self.bot.coin_list, "NEAR"), "MainAddress")
            if len(list_user_addresses) > 0:
                if getattr(getattr(self.bot.coin_list, coin_name), "enable_deposit") != 0:
                    for each_address in list_user_addresses:
                        if each_address['balance_wallet_address'] in list_recent_mv:
                            await asyncio.sleep(5.0)
                            continue
                        # check balance, skip if below minimum
                        get_balance = await near_check_balance(self.bot.erc_node_list['NEAR'], each_address['balance_wallet_address'], 32)
                        if get_balance and (int(get_balance['amount']) - int(get_balance['locked']))/10**coin_decimal > real_min_deposit:
                            balance = (int(get_balance['amount']) - int(get_balance['locked']))/10**coin_decimal
                            atomic_amount = int(get_balance['amount']) - int(get_balance['locked']) - int(real_deposit_fee*10**coin_decimal)
                            # move balance
                            transaction = functools.partial(self.wallet_api.near_move_balance, self.bot.erc_node_list['NEAR'], 
                                                            decrypt_string(each_address['privateKey']), each_address['balance_wallet_address'], main_address, atomic_amount)
                            tx = await self.bot.loop.run_in_executor(None, transaction)
                            if tx:
                                content = None
                                try:
                                    content = json.dumps(tx)
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                                # 
                                added = await self.wallet_api.near_insert_mv_balance(coin_name, None, each_address['user_id'], each_address['balance_wallet_address'], main_address, float(balance), real_deposit_fee, coin_decimal, tx['transaction_outcome']['id'], content, int(time.time()), SERVER_BOT, "NEAR")
                                await asyncio.sleep(5.0)
            # Check token
            list_user_addresses = await store.sql_get_all_near_user("NEAR-TOKEN", 7200) # last 2hrs
            for each_contract in near_contracts:
                try:
                    if len(list_user_addresses) > 0:
                        token_contract = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "contract")
                        coin_decimal = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "decimal")
                        real_min_deposit = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "real_min_deposit")
                        real_deposit_fee = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "real_deposit_fee")

                        min_gas_tx = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "min_gas_tx")
                        move_gas_amount = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "move_gas_amount")
                        for each_addr in list_user_addresses:
                            get_token_balance = await near_check_balance_token(self.bot.erc_node_list['NEAR'], token_contract, each_addr['balance_wallet_address'], 32)
                            if get_token_balance and isinstance(get_token_balance, int) and (get_token_balance/10**coin_decimal) > real_min_deposit:
                                # Check if has enough gas
                                get_gas_balance = await near_check_balance(self.bot.erc_node_list['NEAR'], each_addr['balance_wallet_address'], 32)
                                # fix coin_decimal 24 for gas
                                if get_gas_balance and (int(get_gas_balance['amount']) - int(get_gas_balance['locked']))/10**24 >= min_gas_tx:
                                    # Move token
                                    transaction = functools.partial(self.wallet_api.near_move_balance_token, self.bot.erc_node_list['NEAR'], 
                                                                    token_contract, decrypt_string(each_addr['privateKey']), each_addr['balance_wallet_address'], main_address, get_token_balance)
                                    tx = await self.bot.loop.run_in_executor(None, transaction)
                                    if tx:
                                        content = None
                                        try:
                                            content = json.dumps(tx)
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                        await self.wallet_api.near_insert_mv_balance(each_contract['coin_name'], token_contract, each_addr['user_id'], each_addr['balance_wallet_address'], main_address, float(get_token_balance/10**coin_decimal), real_deposit_fee, coin_decimal, tx['transaction_outcome']['id'], content, int(time.time()), SERVER_BOT, "NEAR")
                                        await asyncio.sleep(5.0)
                                else:
                                    # Less than 1hr, do not move
                                    if each_addr['last_moved_gas'] and int(time.time()) - each_addr['last_moved_gas'] < 3600:
                                        continue
                                    # Move gas
                                    key = decrypt_string(getattr(getattr(self.bot.coin_list, "NEAR"), "walletkey"))
                                    gas_atomic_amount = int(move_gas_amount*10**24) # fix coin_decimal 24 for gas
                                    transaction = functools.partial(self.wallet_api.near_move_balance, self.bot.erc_node_list['NEAR'], 
                                                                    key, main_address, each_addr['balance_wallet_address'], gas_atomic_amount)
                                    tx = await self.bot.loop.run_in_executor(None, transaction)
                                    if tx:
                                        await self.wallet_api.near_update_mv_gas(each_addr['balance_wallet_address'], int(time.time()))
                                        await asyncio.sleep(5.0)
                                        continue
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def check_confirming_near(self):
        time_lap = 5  # seconds

        async def near_get_tx(url: str, tx_hash: str, timeout: int=32):
            headers = {
                'Content-Type': 'application/json'
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url + "txn?hash=" + tx_hash, headers=headers, timeout=timeout) as response:
                        json_resp = await response.json()
                        if response.status == 200 or response.status == 201:
                            if json_resp['txn'] is None:
                                return None
                            elif json_resp['txn']['status'] == "Succeeded":
                                return json_resp['txn']
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return None

        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "check_confirming_near"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        coin_name = "NEAR"
        rpchost = getattr(getattr(self.bot.coin_list, coin_name), "rpchost")
        get_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
        try:
            pending_list = await self.wallet_api.near_get_mv_deposit_list("PENDING")
            if len(pending_list) > 0:
                for each_tx in pending_list:
                    try:
                        check_tx = await near_get_tx(rpchost, each_tx['txn'], 32)
                        if check_tx is not None:
                            height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                            if height and height - check_tx['height'] > get_confirm_depth:
                                number_conf = height - check_tx['height']
                                await self.wallet_api.near_update_mv_deposit_pending(each_tx['txn'], check_tx['height'], number_conf)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def notify_new_confirmed_near(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_new_confirmed_near"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `near_move_deposit` 
                              WHERE `notified_confirmation`=%s 
                              AND `failed_notification`=%s AND `user_server`=%s AND `blockNumber` IS NOT NULL """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            if eachTx['user_id']:
                                if not eachTx['user_id'].isdigit():
                                    continue
                                try:
                                    key = "notify_new_tx_{}_{}_{}".format(eachTx['token_name'], eachTx['user_id'],
                                                                          eachTx['txn'])
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['token_name']), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + "Coin: {}\nAmount: {}".format(eachTx['token_name'], num_format_coin(eachTx['amount'], eachTx['token_name'], coin_decimal, False)) + "```"
                                    try:
                                        await member.send(msg)
                                        sql = """ UPDATE `near_move_deposit` SET `notified_confirmation`=%s, `time_notified`=%s WHERE `txn`=%s LIMIT 1 """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['txn']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `near_move_deposit` SET `notified_confirmation`=%s, `failed_notification`=%s WHERE `txn`=%s LIMIT 1 """
                                        await cur.execute(sql, ("NO", "YES", eachTx['txn']))
                                        await conn.commit()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def notify_new_confirmed_vet(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_new_confirmed_vet"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `vet_move_deposit` 
                              WHERE `notified_confirmation`=%s 
                              AND `failed_notification`=%s AND `user_server`=%s AND `blockNumber` IS NOT NULL """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            if eachTx['user_id']:
                                if not eachTx['user_id'].isdigit():
                                    continue
                                try:
                                    key = "notify_new_tx_{}_{}_{}".format(eachTx['token_name'], eachTx['user_id'],
                                                                          eachTx['txn'])
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['token_name']), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + "Coin: {}\nAmount: {}".format(eachTx['token_name'], num_format_coin(eachTx['real_amount'], eachTx['token_name'], coin_decimal, False)) + "```"
                                    try:
                                        await member.send(msg)
                                        sql = """ UPDATE `vet_move_deposit` SET `notified_confirmation`=%s, `time_notified`=%s WHERE `txn`=%s LIMIT 1 """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['txn']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `vet_move_deposit` SET `notified_confirmation`=%s, `failed_notification`=%s WHERE `txn`=%s LIMIT 1 """
                                        await cur.execute(sql, ("NO", "YES", eachTx['txn']))
                                        await conn.commit()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def check_confirming_vet(self):
        time_lap = 5  # seconds

        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "check_confirming_vet"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        coin_name = "VET"
        get_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
        try:
            pending_list = await self.wallet_api.vet_get_mv_deposit_list("PENDING")
            if len(pending_list) > 0:
                for each_tx in pending_list:
                    try:
                        # vet_get_tx(url: str, tx_hash: str, timeout: int=16)
                        check_tx = await vet_get_tx(self.bot.erc_node_list['VET'], each_tx['txn'], 12)
                        if check_tx is not None:
                            height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                            if height and height - int(check_tx['meta']['blockNumber']) > get_confirm_depth:
                                number_conf = height - int(check_tx['meta']['blockNumber'])
                                await self.wallet_api.vet_update_mv_deposit_pending(each_tx['txn'], int(check_tx['meta']['blockNumber']), json.dumps(check_tx), number_conf)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def update_balance_vet(self):
        time_lap = 5  # seconds

        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_balance_vet"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            vet_contracts = await self.get_all_contracts("VET", False)
            # Check native
            coin_name = "VET"
            get_status = await vet_get_status(self.bot.erc_node_list['VET'], 16)
            if get_status:
                height = int(get_status['number'])
                redis_utils.redis_conn.set(f'{config.redis.prefix + config.redis.daemon_height}{coin_name}',
                                           str(height))
                if len(vet_contracts) > 0:
                    for each_coin in vet_contracts:
                        name = each_coin['coin_name']
                        try:
                            redis_utils.redis_conn.set(f'{config.redis.prefix + config.redis.daemon_height}{name}',
                                                       str(height))
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
            ## Check VET and VTHO
            list_user_addresses = await store.sql_get_all_vet_user(7200) # last 2hrs

            coin_name = "VET"
            get_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            real_min_deposit = getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit")
            real_deposit_fee = getattr(getattr(self.bot.coin_list, coin_name), "real_deposit_fee")

            main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
            main_address_key = decrypt_string(getattr(getattr(self.bot.coin_list, coin_name), "walletkey"))

            list_recent_mv_vet = await store.sql_recent_vet_move_deposit("VET", 300) # 5mn
            list_recent_mv_vtho = await store.sql_recent_vet_move_deposit("VTHO", 300) # 5mn
            for each_address in list_user_addresses:
                if each_address['balance_wallet_address'] in list_recent_mv_vet or \
                    each_address['balance_wallet_address'] in list_recent_mv_vtho:
                    await asyncio.sleep(5.0)
                    continue
                # Check VET and VTHO balance
                check_balance = functools.partial(vet_get_balance, self.bot.erc_node_list['VET'], each_address['balance_wallet_address'])
                balance = await self.bot.loop.run_in_executor(None, check_balance)
                # VET
                if balance and balance['VET']/10**coin_decimal >= real_min_deposit:
                    transaction = functools.partial(vet_move_token, self.bot.erc_node_list['VET'], coin_name, None, main_address, decrypt_string(each_address['key']), main_address_key, balance[coin_name])
                    tx = await self.bot.loop.run_in_executor(None, transaction)
                    if tx:
                        added = await self.wallet_api.vet_insert_mv_balance(coin_name, None, each_address['user_id'], each_address['balance_wallet_address'], main_address, float(balance[coin_name]/10**coin_decimal), real_deposit_fee, coin_decimal, tx, None, int(time.time()), SERVER_BOT, "VET")
                        await asyncio.sleep(5.0)
                # VTHO
                coin_name = "VTHO"
                get_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                real_min_deposit = getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit")
                real_deposit_fee = getattr(getattr(self.bot.coin_list, coin_name), "real_deposit_fee")
                contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                if balance and balance['VTHO']/10**coin_decimal >= real_min_deposit:
                    transaction = functools.partial(vet_move_token, self.bot.erc_node_list['VET'], coin_name, None, main_address, decrypt_string(each_address['key']), main_address_key, balance[coin_name])
                    tx = await self.bot.loop.run_in_executor(None, transaction)
                    if tx:
                        added = await self.wallet_api.vet_insert_mv_balance(coin_name, contract, each_address['user_id'], each_address['balance_wallet_address'], main_address, float(balance[coin_name]/10**coin_decimal), real_deposit_fee, coin_decimal, tx, None, int(time.time()), SERVER_BOT, "VET")
                        await asyncio.sleep(5.0)
            # Tokens
            vet_contracts = await self.get_all_contracts("VET", False)
            if len(vet_contracts) > 0 and len(list_user_addresses) > 0:
                for each_contract in vet_contracts:
                    if each_contract['coin_name'] in ["VET", "VTHO"]:
                        continue
                    token_contract = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "contract")
                    coin_decimal = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "decimal")
                    real_min_deposit = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "real_min_deposit")
                    real_deposit_fee = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "real_deposit_fee")
                    if token_contract is None:
                        continue
                    try:
                        for each_address in list_user_addresses:
                            try:
                                get_token_balance = functools.partial(vet_get_token_balance, self.bot.erc_node_list['VET'], token_contract, each_address['balance_wallet_address'])
                                balance = await self.bot.loop.run_in_executor(None, get_token_balance)
                                if balance and balance / 10 ** coin_decimal >= real_min_deposit:
                                    # move token
                                    transaction = functools.partial(vet_move_token, self.bot.erc_node_list['VET'], each_contract['coin_name'], token_contract, main_address, decrypt_string(each_address['key']), main_address_key, balance)
                                    tx = await self.bot.loop.run_in_executor(None, transaction)
                                    if tx:
                                        added = await self.wallet_api.vet_insert_mv_balance(each_contract['coin_name'], token_contract, each_address['user_id'], each_address['balance_wallet_address'], main_address, float(balance / 10**coin_decimal), real_deposit_fee, coin_decimal, tx, None, int(time.time()), SERVER_BOT, "VET")
                                        await asyncio.sleep(5.0)
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def notify_new_confirmed_zil(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_new_confirmed_zil"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `zil_move_deposit` 
                              WHERE `notified_confirmation`=%s 
                              AND `failed_notification`=%s AND `user_server`=%s AND `blockNumber` IS NOT NULL """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            if eachTx['user_id']:
                                if not eachTx['user_id'].isdigit():
                                    continue
                                try:
                                    key = "notify_new_tx_{}_{}_{}".format(eachTx['token_name'], eachTx['user_id'],
                                                                          eachTx['txn'])
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['token_name']), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + "Coin: {}\nAmount: {}".format(eachTx['token_name'], num_format_coin(eachTx['real_amount'], eachTx['token_name'], coin_decimal, False)) + "```"
                                    try:
                                        await member.send(msg)
                                        sql = """ UPDATE `zil_move_deposit` SET `notified_confirmation`=%s, `time_notified`=%s WHERE `txn`=%s LIMIT 1 """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['txn']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `zil_move_deposit` SET `notified_confirmation`=%s, `failed_notification`=%s WHERE `txn`=%s LIMIT 1 """
                                        await cur.execute(sql, ("NO", "YES", eachTx['txn']))
                                        await conn.commit()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def check_confirming_zil(self):
        time_lap = 5  # seconds

        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "check_confirming_zil"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        coin_name = "ZIL"
        get_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
        try:
            pending_list = await self.wallet_api.zil_get_mv_deposit_list("PENDING")
            if len(pending_list) > 0:
                for each_tx in pending_list:
                    try:
                        check_tx = await zil_get_tx(self.bot.erc_node_list['ZIL'], each_tx['txn'], 12)
                        if check_tx is not None:
                            height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                            if height and height - int(check_tx['result']['receipt']['epoch_num']) > get_confirm_depth:
                                number_conf = height - int(check_tx['result']['receipt']['epoch_num'])
                                await self.wallet_api.zil_update_mv_deposit_pending(each_tx['txn'], int(check_tx['result']['receipt']['epoch_num']), number_conf)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def update_balance_zil(self):
        time_lap = 5  # seconds

        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_balance_zil"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            zil_contracts = await self.get_all_contracts("ZIL", False)
            # Check native
            coin_name = "ZIL"
            get_status = await zil_get_status(self.bot.erc_node_list['ZIL'], 16)
            if get_status:
                height = int(get_status['result']['NumTxBlocks'])
                redis_utils.redis_conn.set(f'{config.redis.prefix + config.redis.daemon_height}{coin_name}',
                                           str(height))
                if len(zil_contracts) > 0:
                    for each_coin in zil_contracts:
                        name = each_coin['coin_name']
                        try:
                            redis_utils.redis_conn.set(f'{config.redis.prefix + config.redis.daemon_height}{name}',
                                                       str(height))
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
            real_min_deposit = getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit")
            real_deposit_fee = getattr(getattr(self.bot.coin_list, coin_name), "real_deposit_fee")
            list_user_addresses = await store.sql_get_all_zil_user(coin_name, 7200) # last 2hrs
            list_recent_mv = await store.sql_recent_zil_move_deposit(1200) # 20mn
            main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            if len(list_user_addresses) > 0:
                if getattr(getattr(self.bot.coin_list, coin_name), "enable_deposit") != 0:
                    for each_address in list_user_addresses:
                        if each_address['balance_wallet_address'] in list_recent_mv:
                            await asyncio.sleep(5.0)
                            continue
                        # check balance, skip if below minimum
                        check_balance = functools.partial(zil_check_balance, decrypt_string(each_address['key']))
                        balance = await self.bot.loop.run_in_executor(None, check_balance)
                        if balance >= real_min_deposit:
                            amount = float(balance) - real_deposit_fee
                            transaction = functools.partial(self.wallet_api.zil_transfer_native, main_address, decrypt_string(each_address['key']),  amount, 600)
                            tx = await self.bot.loop.run_in_executor(None, transaction)
                            if tx:
                                contents = None
                                try:
                                    contents = json.dumps(tx)
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                                added = await self.wallet_api.zil_insert_mv_balance(coin_name, None, each_address['user_id'], each_address['balance_wallet_address'], main_address, float(balance), real_deposit_fee, coin_decimal, tx['ID'], contents, int(time.time()), SERVER_BOT, "ZIL")
                                await asyncio.sleep(5.0)
            # Check token
            list_user_addresses = await store.sql_get_all_zil_user("ZIL-TOKEN", 7200) # last 2hrs
            if len(zil_contracts) > 0 and len(list_user_addresses) > 0:
                main_address = getattr(getattr(self.bot.coin_list, "ZIL"), "MainAddress")
                for each_contract in zil_contracts:
                    try:
                        token_addresses = []
                        for each_user in list_user_addresses:
                            if each_user['type'] == "ZIL":
                                continue
                            else:
                                token_addresses.append(each_user['balance_wallet_address'])
                        if len(token_addresses) > 0:
                            token_contract = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "contract")
                            coin_decimal = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "decimal")
                            real_min_deposit = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "real_min_deposit")
                            real_deposit_fee = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "real_deposit_fee")
                            min_gas_tx = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "min_gas_tx")
                            move_gas_amount = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "move_gas_amount")
                            for each_addr in token_addresses:
                                account = Zil_Account(address=each_addr)
                                get_token_balance = await zil_check_token_balance(self.bot.erc_node_list['ZIL'], token_contract, account.address0x, 32) # atomic
                                get_zil_user = await self.wallet_api.zil_get_user_by_address(each_addr)
                                if get_zil_user is None:
                                    continue
                                if get_token_balance and int(get_token_balance) / 10 ** coin_decimal >= real_min_deposit:
                                    # Check gas
                                    check_gas = functools.partial(zil_check_balance, decrypt_string(get_zil_user['key']))
                                    gas_balance = await self.bot.loop.run_in_executor(None, check_gas)
                                    if gas_balance >= min_gas_tx:
                                        # Move token
                                        amount = int(get_token_balance) # atomic
                                        ## def zil_transfer_token(self, contract_addr: str, to_address: str, from_key: str, atomic_amount: int):
                                        transaction = functools.partial(self.wallet_api.zil_transfer_token, token_contract, main_address, decrypt_string(get_zil_user['key']), amount)
                                        tx = await self.bot.loop.run_in_executor(None, transaction)
                                        if tx:
                                            contents = None
                                            try:
                                                contents = json.dumps(tx)
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                            added = await self.wallet_api.zil_insert_mv_balance(each_contract['coin_name'], token_contract, get_zil_user['user_id'], get_zil_user['balance_wallet_address'], main_address, float(int(amount) / 10 ** coin_decimal), real_deposit_fee, coin_decimal, tx['ID'], contents, int(time.time()), SERVER_BOT, "ZIL")
                                            await asyncio.sleep(5.0)
                                    else:
                                        if get_zil_user and get_zil_user['last_moved_gas'] and int(time.time()) - get_zil_user['last_moved_gas'] < 3600:
                                            continue
                                        # Move gas
                                        key = decrypt_string(getattr(getattr(self.bot.coin_list, "ZIL"), "walletkey"))
                                        transaction = functools.partial(self.wallet_api.zil_transfer_native, each_addr, key, move_gas_amount, 600)
                                        tx = await self.bot.loop.run_in_executor(None, transaction)
                                        if tx:
                                            await self.wallet_api.zil_update_mv_gas(each_addr, int(time.time()))
                                            await asyncio.sleep(1.0)
                                            continue
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def update_balance_tezos(self):
        time_lap = 5  # seconds

        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_balance_tezos"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            xtz_contracts = await self.get_all_contracts("XTZ", False)
            # Check native
            coin_name = "XTZ"
            rpchost = getattr(getattr(self.bot.coin_list, coin_name), "rpchost")
            get_head = await tezos_get_head(rpchost, 8)
            try:
                if get_head:
                    height = get_head['level']
                    redis_utils.redis_conn.set(f'{config.redis.prefix + config.redis.daemon_height}{coin_name}',
                                               str(height))
                    if len(xtz_contracts) > 0:
                        for each_coin in xtz_contracts:
                            name = each_coin['coin_name']
                            try:
                                redis_utils.redis_conn.set(f'{config.redis.prefix + config.redis.daemon_height}{name}',
                                                           str(height))
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
            except Exception:
                traceback.print_exc(file=sys.stdout)
            real_min_deposit = getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit")
            list_user_addresses = await store.sql_get_all_tezos_user(coin_name, 7200) # last 2hrs
            list_recent_mv = await store.sql_recent_tezos_move_deposit(1200) # 20mn
            if len(list_user_addresses) > 0:
                if getattr(getattr(self.bot.coin_list, coin_name), "enable_deposit") != 0:
                    for each_address in list_user_addresses:
                        if each_address['balance_wallet_address'] in list_recent_mv:
                            await asyncio.sleep(5.0)
                            continue
                        # check balance, skip if below minimum
                        check_balance = functools.partial(tezos_check_balance, self.bot.erc_node_list['XTZ'], decrypt_string(each_address['key']))
                        balance = await self.bot.loop.run_in_executor(None, check_balance)
                        if balance > real_min_deposit:
                            # Check if reveal
                            revealed_db = await self.wallet_api.tezos_checked_reveal_db(each_address['balance_wallet_address'])
                            if revealed_db and int(time.time()) - revealed_db['checked_date'] < 30:
                                continue
                            else:
                                check_revealed = await tezos_check_reveal(rpchost, each_address['balance_wallet_address'], 32)
                                if check_revealed is True:
                                    # Add to DB if not exist
                                    if revealed_db is None:
                                        await self.wallet_api.tezos_insert_reveal(each_address['balance_wallet_address'], None, int(time.time()))
                                    # Move balance:
                                    main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                                    real_deposit_fee = getattr(getattr(self.bot.coin_list, coin_name), "real_deposit_fee")
                                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                    atomic_amount = int((float(balance) - real_deposit_fee)*10**coin_decimal)
                                    try:
                                        key = "{}_{}".format(coin_name, each_address['balance_wallet_address'])
                                        if self.mv_xtz_cache[key] == key:
                                            continue
                                        else:
                                            self.mv_xtz_cache[key] = key
                                    except Exception:
                                        pass
                                    transaction = functools.partial(self.wallet_api.tezos_move_balance, self.bot.erc_node_list['XTZ'], decrypt_string(each_address['key']), main_address, atomic_amount)
                                    tx = await self.bot.loop.run_in_executor(None, transaction)
                                    if tx:
                                        contents = None
                                        try:
                                            contents = json.dumps(tx.contents)
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                        added = await self.wallet_api.tezos_insert_mv_balance(coin_name, None, each_address['user_id'], each_address['balance_wallet_address'], main_address, float(balance), real_deposit_fee, coin_decimal, tx.hash(), contents, int(time.time()), SERVER_BOT, "XTZ")
                                        await asyncio.sleep(5.0)
                                else:
                                    # Push to revealed & stored in DB
                                    do_reveal = functools.partial(tezos_reveal_address, self.bot.erc_node_list['XTZ'], decrypt_string(each_address['key']))
                                    tx_reveal = await self.bot.loop.run_in_executor(None, do_reveal)
                                    if tx_reveal:
                                        # Add to DB
                                        await self.wallet_api.tezos_insert_reveal(each_address['balance_wallet_address'], tx_reveal['hash'], int(time.time()))
                                        await asyncio.sleep(1.0)
                                        continue
            # Check token
            list_user_addresses = await store.sql_get_all_tezos_user("XTZ-FA", 7200) # last 2hrs
            if len(xtz_contracts) > 0 and len(list_user_addresses) > 0:
                main_address = getattr(getattr(self.bot.coin_list, "XTZ"), "MainAddress")
                for each_contract in xtz_contracts:
                    try:
                        token_addresses = []
                        for each_user in list_user_addresses:
                            if each_user['type'] == "XTZ":
                                continue
                            else:
                                token_addresses.append(each_user['balance_wallet_address'])
                        if len(token_addresses) > 0:
                            token_contract = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "contract")
                            coin_decimal = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "decimal")
                            token_id = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "wallet_address")
                            real_min_deposit = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "real_min_deposit")
                            real_deposit_fee = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "real_deposit_fee")
                            token_type = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "header")
                            bot_run_get_token_balances = {}
                            if token_type == "FA2":
                                get_token_balances = functools.partial(tezos_check_token_balance, self.bot.erc_node_list['XTZ'], token_contract, token_addresses, coin_decimal, int(token_id))
                                bot_run_get_token_balances = await self.bot.loop.run_in_executor(None, get_token_balances)
                            elif token_type == "FA1.2" and len(token_addresses) > 0:
                                for each_addr in token_addresses:
                                    # async def tezos_check_token_balances(url: str, address: str, timeout: int=16):
                                    get_token_balance = await tezos_check_token_balances(rpchost, each_addr, 12)
                                    bot_run_get_token_balances[each_addr] = 0
                                    if get_token_balance is not None and len(get_token_balance) > 0:
                                        for each_token in get_token_balance:
                                            try:
                                                if token_contract == each_token['token']['contract']['address'] \
                                                    and int(token_id) == int(each_token['token']['tokenId']):
                                                    bot_run_get_token_balances[each_addr] = int(each_token['balance'])
                                                    break
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                            else:
                                continue
                            if len(bot_run_get_token_balances) > 0:
                                # Check if balance above minimum and is reveal
                                can_move_token = False
                                min_gas_tx = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "min_gas_tx")
                                move_gas_amount = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "move_gas_amount")
                                contract = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "contract")
                                token_id = getattr(getattr(self.bot.coin_list, each_contract['coin_name']), "wallet_address")
                                for k, v in bot_run_get_token_balances.items():
                                    get_tezos_user = await self.wallet_api.tezos_get_user_by_address(k)
                                    if get_tezos_user is None:
                                        continue
                                    if v >= real_min_deposit*10**coin_decimal: # bigger than minimum
                                        revealed_db = await self.wallet_api.tezos_checked_reveal_db(k)
                                        if revealed_db and int(time.time()) - revealed_db['checked_date'] < 30:
                                            continue
                                        else:
                                            check_revealed = await tezos_check_reveal(rpchost, k, 32)
                                            if check_revealed is True:
                                                # Add to DB if not exist
                                                await self.wallet_api.tezos_insert_reveal(k, None, int(time.time()))
                                                can_move_token = True
                                            else:
                                                # Push to revealed & stored in DB
                                                # 1] Check if balance has enough gas. If not, move gas
                                                # 2] Push to reveal
                                                check_gas = functools.partial(tezos_check_balance, self.bot.erc_node_list['XTZ'], decrypt_string(get_tezos_user['key']))
                                                gas_balance = await self.bot.loop.run_in_executor(None, check_gas)
                                                if gas_balance >= min_gas_tx:
                                                    do_reveal = functools.partial(tezos_reveal_address, self.bot.erc_node_list['XTZ'], decrypt_string(get_tezos_user['key']))
                                                    tx_reveal = await self.bot.loop.run_in_executor(None, do_reveal)
                                                    if tx_reveal:
                                                        # Add to DB
                                                        await self.wallet_api.tezos_insert_reveal(k, tx_reveal['hash'], int(time.time()))
                                                        await asyncio.sleep(1.0)
                                                        continue
                                                else:
                                                    # skip recent gas, 1hr
                                                    if get_tezos_user['last_moved_gas'] and int(time.time()) - get_tezos_user['last_moved_gas'] < 3600:
                                                        continue
                                                    # Move gas
                                                    key = decrypt_string(getattr(getattr(self.bot.coin_list, "XTZ"), "walletkey"))
                                                    transaction = functools.partial(self.wallet_api.tezos_move_balance, self.bot.erc_node_list['XTZ'], key, k, int(move_gas_amount*10**6)) # Move XTZ, decimal 6
                                                    send_tx = await self.bot.loop.run_in_executor(None, transaction)
                                                    if send_tx:
                                                        await self.wallet_api.tezos_update_mv_gas(k, int(time.time()))
                                                        await asyncio.sleep(1.0)
                                                        continue
                                        # re-check gas
                                        if can_move_token is True:
                                            check_gas = functools.partial(tezos_check_balance, self.bot.erc_node_list['XTZ'], decrypt_string(get_tezos_user['key']))
                                            gas_balance = await self.bot.loop.run_in_executor(None, check_gas)
                                            if gas_balance >= min_gas_tx:
                                                # Move token
                                                try:
                                                    ttlkey = "{}_{}".format(each_contract['coin_name'], each_address['balance_wallet_address'])
                                                    if self.mv_xtz_cache[ttlkey] == ttlkey:
                                                        continue
                                                    else:
                                                        self.mv_xtz_cache[ttlkey] = ttlkey
                                                except Exception:
                                                    pass
                                                if token_type == "FA2":
                                                    transaction = functools.partial(self.wallet_api.tezos_move_token_balance, self.bot.erc_node_list['XTZ'], decrypt_string(get_tezos_user['key']), main_address, contract, v, token_id)
                                                elif token_type == "FA1.2":
                                                    transaction = functools.partial(self.wallet_api.tezos_move_token_balance_fa12, self.bot.erc_node_list['XTZ'], decrypt_string(get_tezos_user['key']), main_address, contract, v, token_id)
                                                else:
                                                    continue
                                                tx = await self.bot.loop.run_in_executor(None, transaction)
                                                tx_hash = None
                                                if tx:
                                                    contents = None
                                                    try:
                                                        if token_type == "FA2":
                                                            contents = json.dumps(tx.contents)
                                                            tx_hash = tx.hash()
                                                        elif token_type == "FA1.2":
                                                            contents = json.dumps(tx['contents'])
                                                            tx_hash = tx['hash']
                                                    except Exception:
                                                        traceback.print_exc(file=sys.stdout)
                                                    await self.wallet_api.tezos_insert_mv_balance(each_contract['coin_name'], contract, get_tezos_user['user_id'], k, main_address, float(v/10**coin_decimal), real_deposit_fee, coin_decimal, tx_hash, contents, int(time.time()), SERVER_BOT, "XTZ")
                                                    await asyncio.sleep(5.0)
                                            else:
                                                if get_tezos_user['last_moved_gas'] and int(time.time()) - get_tezos_user['last_moved_gas'] < 3600:
                                                    continue
                                                # Move gas
                                                key = decrypt_string(getattr(getattr(self.bot.coin_list, "XTZ"), "walletkey"))
                                                transaction = functools.partial(self.wallet_api.tezos_move_balance, self.bot.erc_node_list['XTZ'], key, k, int(move_gas_amount*10**6)) # Move XTZ, decimal 6
                                                send_tx = await self.bot.loop.run_in_executor(None, transaction)
                                                if send_tx:
                                                    await self.wallet_api.tezos_update_mv_gas(k, int(time.time()))
                                                    await asyncio.sleep(1.0)
                                                    continue
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def notify_new_confirmed_tezos(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_new_confirmed_tezos"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `tezos_move_deposit` 
                              WHERE `notified_confirmation`=%s 
                              AND `failed_notification`=%s AND `user_server`=%s AND `blockNumber` IS NOT NULL """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            if eachTx['user_id']:
                                if not eachTx['user_id'].isdigit():
                                    continue
                                try:
                                    key = "notify_new_tx_{}_{}_{}".format(eachTx['token_name'], eachTx['user_id'],
                                                                          eachTx['txn'])
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['token_name']), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + "Coin: {}\nAmount: {}".format(eachTx['token_name'], num_format_coin(eachTx['real_amount'], eachTx['token_name'], coin_decimal, False)) + "```"
                                    try:
                                        await member.send(msg)
                                        sql = """ UPDATE `tezos_move_deposit` SET `notified_confirmation`=%s, `time_notified`=%s WHERE `txn`=%s LIMIT 1 """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['txn']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `tezos_move_deposit` SET `notified_confirmation`=%s, `failed_notification`=%s WHERE `txn`=%s LIMIT 1 """
                                        await cur.execute(sql, ("NO", "YES", eachTx['txn']))
                                        await conn.commit()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def check_confirming_tezos(self):
        time_lap = 5  # seconds

        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "check_confirming_tezos"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        coin_name = "XTZ"
        rpchost = getattr(getattr(self.bot.coin_list, coin_name), "rpchost")
        get_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
        try:
            pending_list = await self.wallet_api.tezos_get_mv_deposit_list("PENDING")
            if len(pending_list) > 0:
                for each_tx in pending_list:
                    try:
                        check_tx = await tezos_get_tx(rpchost, each_tx['txn'], 32)
                        if check_tx is not None:
                            height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                            if height and height - check_tx['level'] > get_confirm_depth:
                                number_conf = height - check_tx['level']
                                await self.wallet_api.tezos_update_mv_deposit_pending(each_tx['txn'], check_tx['level'], number_conf)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def update_balance_trc20(self):
        time_lap = 5  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_balance_trc20"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            erc_contracts = await self.get_all_contracts("TRC-20", False)
            if len(erc_contracts) > 0:
                for each_c in erc_contracts:
                    try:
                        type_name = each_c['type']
                        await store.trx_check_minimum_deposit(each_c['coin_name'], type_name, each_c['contract'],
                                                              each_c['decimal'], each_c['min_move_deposit'],
                                                              each_c['min_gas_tx'], each_c['fee_limit'],
                                                              each_c['gas_ticker'], each_c['move_gas_amount'],
                                                              each_c['chain_id'], each_c['real_deposit_fee'], 7200)
                        pass
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
            main_tokens = await self.get_all_contracts("TRC-20", True)
            if len(main_tokens) > 0:
                for each_c in main_tokens:
                    try:
                        type_name = each_c['type']
                        await store.trx_check_minimum_deposit(each_c['coin_name'], type_name, None, each_c['decimal'],
                                                              each_c['min_move_deposit'], each_c['min_gas_tx'],
                                                              each_c['fee_limit'], each_c['gas_ticker'],
                                                              each_c['move_gas_amount'], each_c['chain_id'],
                                                              each_c['real_deposit_fee'], 7200)
                        pass
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def unlocked_move_pending_erc20(self):
        time_lap = 5  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "unlocked_move_pending_erc20"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            erc_contracts = await self.get_all_contracts("ERC-20", False)
            depth = max([each['deposit_confirm_depth'] for each in erc_contracts])
            net_names = await self.get_all_net_names()
            net_names = list(net_names.keys())
            if len(net_names) > 0:
                for each_name in net_names:
                    try:
                        await store.sql_check_pending_move_deposit_erc20(self.bot.erc_node_list[each_name], each_name,
                                                                         depth, 32)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def unlocked_move_pending_trc20(self):
        time_lap = 5  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "unlocked_move_pending_trc20"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            trc_contracts = await self.get_all_contracts("TRC-20", False)
            depth = max([each['deposit_confirm_depth'] for each in trc_contracts])
            net_names = await self.get_all_net_names_tron()
            net_names = list(net_names.keys())

            if len(net_names) > 0:
                for each_name in net_names:
                    try:
                        await store.sql_check_pending_move_deposit_trc20(each_name, depth, "PENDING")
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    @tasks.loop(seconds=60.0)
    async def update_balance_address_history_erc20(self):
        time_lap = 5  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_balance_address_history_erc20"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            erc_contracts = await self.get_all_contracts("ERC-20", False)
            depth = max([each['deposit_confirm_depth'] for each in erc_contracts])
            net_names = await self.get_all_net_names()
            net_names = list(net_names.keys())
            if len(net_names) > 0:
                for each_name in net_names:
                    try:
                        get_recent_tx = await store.get_monit_scanning_contract_balance_address_erc20(each_name, 7200)
                        if get_recent_tx and len(get_recent_tx) > 0:
                            tx_update_call = []
                            for each_tx in get_recent_tx:
                                to_addr = "0x" + each_tx['to_addr'][26:]
                                tx_update_call.append((each_tx['blockTime'], to_addr))
                            if len(tx_update_call) > 0:
                                update_call = await store.sql_update_erc_user_update_call_many_erc20(tx_update_call)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)


    async def send_external_erc20(self, url: str, network: str, user_id: str, to_address: str, amount: float, coin: str,
                                  coin_decimal: int, real_withdraw_fee: float, user_server: str, chain_id: str = None,
                                  contract: str = None):
        token_name = coin.upper()
        user_server = user_server.upper()

        try:
            # HTTPProvider:
            w3 = Web3(Web3.HTTPProvider(url))
            signed_txn = None
            sent_tx = None
            if contract is None:
                # Main Token
                if network == "MATIC":
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(config.eth.MainAddress), 'pending')
                else:
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(config.eth.MainAddress))
                # get gas price
                gasPrice = w3.eth.gasPrice

                estimateGas = w3.eth.estimateGas(
                    {'to': w3.toChecksumAddress(to_address), 'from': w3.toChecksumAddress(config.eth.MainAddress),
                     'value': int(amount * 10 ** coin_decimal)})

                atomic_amount = int(amount * 10 ** 18)
                transaction = {
                    'from': w3.toChecksumAddress(config.eth.MainAddress),
                    'to': w3.toChecksumAddress(to_address),
                    'value': atomic_amount,
                    'nonce': nonce,
                    'gasPrice': gasPrice,
                    'gas': estimateGas,
                    'chainId': chain_id
                }
                try:
                    signed_txn = w3.eth.account.sign_transaction(transaction, private_key=config.eth.MainAddress_key)
                    # send Transaction for gas:
                    sent_tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            else:
                # Token ERC-20
                # inject the poa compatibility middleware to the innermost layer
                w3.middleware_onion.inject(geth_poa_middleware, layer=0)

                unicorns = w3.eth.contract(address=w3.toChecksumAddress(contract), abi=EIP20_ABI)
                if network == "MATIC":
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(config.eth.MainAddress), 'pending')
                else:
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(config.eth.MainAddress))

                unicorn_txn = unicorns.functions.transfer(
                    w3.toChecksumAddress(to_address),
                    int(amount * 10 ** coin_decimal)  # amount to send
                ).buildTransaction({
                    'from': w3.toChecksumAddress(config.eth.MainAddress),
                    'gasPrice': w3.eth.gasPrice,
                    'nonce': nonce,
                    'chainId': chain_id
                })

                acct = Account.from_mnemonic(
                    mnemonic=config.eth.MainAddress_seed)
                signed_txn = w3.eth.account.signTransaction(unicorn_txn, private_key=acct.key)
                sent_tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
            if signed_txn and sent_tx:
                # Add to SQL
                try:
                    await self.openConnection()
                    async with self.pool.acquire() as conn:
                        async with conn.cursor() as cur:
                            sql = """ INSERT INTO `erc20_external_tx` (`token_name`, `contract`, `user_id`, `real_amount`, 
                                      `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, 
                                      `user_server`, `network`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql,
                                              (token_name, contract, user_id, amount, real_withdraw_fee, coin_decimal,
                                               to_address, int(time.time()), sent_tx.hex(), user_server, network))
                            await conn.commit()
                            return sent_tx.hex()
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot("wallet send_external_erc20 " + str(traceback.format_exc()))
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet send_external_erc20 " + str(traceback.format_exc()))

    async def send_external_trc20(self, user_id: str, to_address: str, amount: float, coin: str, coin_decimal: int,
                                  real_withdraw_fee: float, user_server: str, fee_limit: float, trc_type: str,
                                  contract: str = None):
        token_name = coin.upper()
        user_server = user_server.upper()

        try:
            _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                       timeout=Timeout(timeout=10, connect=5, read=5))
            TronClient = AsyncTron(provider=AsyncHTTPProvider(self.bot.erc_node_list['TRX'], client=_http_client))
            if token_name == "TRX":
                txb = (
                    TronClient.trx.transfer(config.trc.MainAddress, to_address, int(amount * 10 ** 6))
                    # .memo("test memo")
                    .fee_limit(int(fee_limit * 10 ** 6))
                )
                txn = await txb.build()
                priv_key = PrivateKey(bytes.fromhex(config.trc.MainAddress_key))
                txn_ret = await txn.sign(priv_key).broadcast()
                try:
                    in_block = await txn_ret.wait()
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                await TronClient.close()
                if txn_ret and in_block:
                    # Add to SQL
                    try:
                        await self.openConnection()
                        async with self.pool.acquire() as conn:
                            await conn.ping(reconnect=True)
                            async with conn.cursor() as cur:
                                sql = """ INSERT INTO trc20_external_tx (`token_name`, `contract`, `user_id`, `real_amount`, 
                                          `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, `user_server`) 
                                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                await cur.execute(sql, (
                                token_name, contract, user_id, amount, real_withdraw_fee, coin_decimal,
                                to_address, int(time.time()), txn_ret['txid'], user_server))
                                await conn.commit()
                                return txn_ret['txid']
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot("wallet send_external_trc20 " + str(traceback.format_exc()))
            else:
                if trc_type == "TRC-20":
                    try:
                        cntr = await TronClient.get_contract(contract)
                        precision = await cntr.functions.decimals()
                        ## TODO: alert if balance below threshold
                        ## balance = await cntr.functions.balanceOf(config.trc.MainAddress) / 10**precision
                        txb = await cntr.functions.transfer(to_address, int(amount * 10 ** coin_decimal))
                        txb = txb.with_owner(config.trc.MainAddress).fee_limit(int(fee_limit * 10 ** 6))
                        txn = await txb.build()
                        priv_key = PrivateKey(bytes.fromhex(config.trc.MainAddress_key))
                        txn_ret = await txn.sign(priv_key).broadcast()
                        in_block = None
                        try:
                            in_block = await txn_ret.wait()
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                        await TronClient.close()
                        if txn_ret and in_block:
                            # Add to SQL
                            try:
                                await self.openConnection()
                                async with self.pool.acquire() as conn:
                                    await conn.ping(reconnect=True)
                                    async with conn.cursor() as cur:
                                        sql = """ INSERT INTO trc20_external_tx (`token_name`, `contract`, `user_id`, `real_amount`, 
                                                  `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, `user_server`) 
                                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                        await cur.execute(sql, (
                                        token_name, contract, user_id, amount, real_withdraw_fee, coin_decimal,
                                        to_address, int(time.time()), txn_ret['txid'], user_server))
                                        await conn.commit()
                                        return txn_ret['txid']
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                                await logchanbot("wallet send_external_trc20 " + str(traceback.format_exc()))
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                elif trc_type == "TRC-10":
                    try:
                        precision = 10 ** coin_decimal
                        txb = (
                            TronClient.trx.asset_transfer(
                                config.trc.MainAddress, to_address, int(precision * amount), token_id=int(contract)
                            )
                            .fee_limit(int(fee_limit * 10 ** 6))
                        )
                        txn = await txb.build()
                        priv_key = PrivateKey(bytes.fromhex(config.trc.MainAddress_key))
                        txn_ret = await txn.sign(priv_key).broadcast()

                        in_block = None
                        try:
                            in_block = await txn_ret.wait()
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                        await TronClient.close()
                        if txn_ret and in_block:
                            # Add to SQL
                            try:
                                await self.openConnection()
                                async with self.pool.acquire() as conn:
                                    await conn.ping(reconnect=True)
                                    async with conn.cursor() as cur:
                                        sql = """ INSERT INTO trc20_external_tx (`token_name`, `contract`, `user_id`, `real_amount`, 
                                                  `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, `user_server`) 
                                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                        await cur.execute(sql, (
                                        token_name, str(contract), user_id, amount, real_withdraw_fee, coin_decimal,
                                        to_address, int(time.time()), txn_ret['txid'], user_server))
                                        await conn.commit()
                                        return txn_ret['txid']
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                                await logchanbot("wallet send_external_trc20 " + str(traceback.format_exc()))
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def trtl_api_get_transfers(self, url: str, key: str, coin: str, height_start: int = None,
                                     height_end: int = None):
        time_out = 30
        method = "/transactions"
        headers = {
            'X-API-KEY': key,
            'Content-Type': 'application/json'
        }
        if (height_start is None) or (height_end is None):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url + method, headers=headers, timeout=time_out) as response:
                        json_resp = await response.json()
                        if response.status == 200 or response.status == 201:
                            return json_resp['transactions']
                        elif 'errorMessage' in json_resp:
                            raise RPCException(json_resp['errorMessage'])
            except asyncio.TimeoutError:
                await logchanbot(
                    'trtl_api_get_transfers: TIMEOUT: {} - coin {} timeout {}'.format(method, coin, time_out))
            except Exception:
                await logchanbot('trtl_api_get_transfers: ' + str(traceback.format_exc()))
        elif height_start and height_end:
            method += '/' + str(height_start) + '/' + str(height_end)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url + method, headers=headers, timeout=time_out) as response:
                        json_resp = await response.json()
                        if response.status == 200 or response.status == 201:
                            return json_resp['transactions']
                        elif 'errorMessage' in json_resp:
                            raise RPCException(json_resp['errorMessage'])
            except asyncio.TimeoutError:
                await logchanbot(
                    'trtl_api_get_transfers: TIMEOUT: {} - coin {} timeout {}'.format(method, coin, time_out))
            except Exception:
                await logchanbot('trtl_api_get_transfers: ' + str(traceback.format_exc()))

    async def trtl_service_getTransactions(self, url: str, coin: str, firstBlockIndex: int = 2000000,
                                           blockCount: int = 200000):
        coin_name = coin.upper()
        time_out = 64
        payload = {
            'firstBlockIndex': firstBlockIndex if firstBlockIndex > 0 else 1,
            'blockCount': blockCount,
        }
        result = await self.wallet_api.call_aiohttp_wallet_xmr_bcn('getTransactions', coin_name, time_out=time_out,
                                                                   payload=payload)
        if result and 'items' in result:
            return result['items']
        return []

    # Mostly for BCN/XMR
    async def call_daemon(self, get_daemon_rpc_url: str, method_name: str, coin: str, time_out: int = None,
                          payload: Dict = None) -> Dict:
        full_payload = {
            'params': payload or {},
            'jsonrpc': '2.0',
            'id': str(uuid.uuid4()),
            'method': f'{method_name}'
        }
        timeout = time_out or 16
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(get_daemon_rpc_url + '/json_rpc', json=full_payload,
                                        timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.json()
                        if res_data and 'result' in res_data:
                            return res_data['result']
                        else:
                            return res_data
        except asyncio.TimeoutError:
            await logchanbot(
                'call_daemon: method: {} coin_name {} - timeout {}'.format(method_name, coin.upper(), time_out))
            return None
        except Exception:
            traceback.print_exc(file=sys.stdout)
            return None

    async def gettopblock(self, coin: str, time_out: int = None):
        coin_name = coin.upper()
        coin_family = getattr(getattr(self.bot.coin_list, coin_name), "type")
        get_daemon_rpc_url = getattr(getattr(self.bot.coin_list, coin_name), "daemon_address")
        result = None
        timeout = time_out or 32

        if coin_name in ["LTHN"] or coin_family in ["BCN", "TRTL-API", "TRTL-SERVICE"]:
            method_name = "getblockcount"
            full_payload = {
                'params': {},
                'jsonrpc': '2.0',
                'id': str(uuid.uuid4()),
                'method': f'{method_name}'
            }
            try:

                async with aiohttp.ClientSession() as session:
                    async with session.post(get_daemon_rpc_url + '/json_rpc', json=full_payload,
                                            timeout=timeout) as response:
                        if response.status == 200:
                            res_data = await response.json()
                            result = None
                            if res_data and 'result' in res_data:
                                result = res_data['result']
                            else:
                                result = res_data
                            if result:
                                full_payload = {
                                    'jsonrpc': '2.0',
                                    'method': 'getblockheaderbyheight',
                                    'params': {'height': result['count'] - 1}
                                }
                                try:
                                    async with aiohttp.ClientSession() as session:
                                        async with session.post(get_daemon_rpc_url + '/json_rpc', json=full_payload,
                                                                timeout=timeout) as response:
                                            if response.status == 200:
                                                res_data = await response.json()
                                                return res_data['result']
                                except asyncio.TimeoutError:
                                    traceback.print_exc(file=sys.stdout)
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            return None
            except asyncio.TimeoutError:
                await logchanbot(
                    'gettopblock: method: {} coin_name {} - timeout {}'.format(method_name, coin.upper(), time_out))
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return None
        elif coin_family == "XMR":
            method_name = "get_block_count"
            full_payload = {
                'params': {},
                'jsonrpc': '2.0',
                'id': str(uuid.uuid4()),
                'method': f'{method_name}'
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(get_daemon_rpc_url + '/json_rpc', json=full_payload,
                                            timeout=timeout) as response:
                        if response.status == 200:
                            try:
                                res_data = await response.json()
                            except Exception:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                res_data = json.loads(res_data)
                            result = None
                            if res_data and 'result' in res_data:
                                result = res_data['result']
                            else:
                                result = res_data
                            if result:
                                full_payload = {
                                    'jsonrpc': '2.0',
                                    'method': 'get_block_header_by_height',
                                    'params': {'height': result['count'] - 1}
                                }
                                try:
                                    async with aiohttp.ClientSession() as session:
                                        async with session.post(get_daemon_rpc_url + '/json_rpc', json=full_payload,
                                                                timeout=timeout) as response:
                                            if response.status == 200:
                                                res_data = await response.json()
                                                if res_data and 'result' in res_data:
                                                    return res_data['result']
                                                else:
                                                    return res_data
                                except asyncio.TimeoutError:
                                    await logchanbot(
                                        'gettopblock: method: {} coin_name {} - timeout {}'.format('get_block_count',
                                                                                                   coin_name, time_out))
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            return None
            except asyncio.TimeoutError:
                await logchanbot(
                    'gettopblock: method: {} coin_name {} - timeout {}'.format(method_name, coin.upper(), time_out))
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return None
        elif coin_family == "CHIA":
            url = getattr(getattr(self.bot.coin_list, coin_name), "daemon_address") + '/get_blockchain_state'
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, timeout=timeout, json={}) as response:
                        if response.status == 200:
                            res_data = await response.json()
                            return res_data['blockchain_state']['peak']
            except asyncio.TimeoutError:
                await logchanbot(
                    'gettopblock: method: {} coin_name {} - timeout {}'.format("get_blockchain_state", coin.upper(),
                                                                               time_out))
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return None

    async def get_all_contracts(self, type_token: str, main_token: bool = False):
        # type_token: ERC-20, TRC-20
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if main_token is False:
                        sql = """ SELECT * FROM `coin_settings` WHERE `type`=%s AND `enable`=%s AND `contract` IS NOT NULL AND `net_name` IS NOT NULL """
                        await cur.execute(sql, (type_token, 1))
                        result = await cur.fetchall()
                        if result and len(result) > 0: return result
                    else:
                        sql = """ SELECT * FROM `coin_settings` WHERE `type`=%s AND `enable`=%s AND `contract` IS NULL AND `net_name` IS NOT NULL """
                        await cur.execute(sql, (type_token, 1))
                        result = await cur.fetchall()
                        if result and len(result) > 0: return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet get_all_contracts " + str(traceback.format_exc()))
        return []

    async def generate_qr_address(
            self,
            address: str
    ):
        return await self.wallet_api.generate_qr_address(address)

    async def sql_get_userwallet(self, user_id, coin: str, netname: str, type_coin: str, user_server: str = 'DISCORD',
                                 chat_id: int = 0):
        return await self.wallet_api.sql_get_userwallet(user_id, coin, netname, type_coin, user_server, chat_id)

    async def sql_register_user(self, user_id, coin: str, netname: str, type_coin: str, user_server: str,
                                chat_id: int = 0, is_discord_guild: int = 0):
        return await self.wallet_api.sql_register_user(user_id, coin, netname, type_coin, user_server, chat_id,
                                                       is_discord_guild)

    async def get_all_net_names(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_ethscan_setting` WHERE `enable`=%s """
                    await cur.execute(sql, (1,))
                    result = await cur.fetchall()
                    net_names = {}
                    if result and len(result) > 0:
                        for each in result:
                            net_names[each['net_name']] = each
                        return net_names
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet get_all_net_names " + str(traceback.format_exc()))
        return {}

    async def get_all_net_names_tron(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_tronscan_setting` WHERE `enable`=%s """
                    await cur.execute(sql, (1,))
                    result = await cur.fetchall()
                    net_names = {}
                    if result and len(result) > 0:
                        for each in result:
                            net_names[each['net_name']] = each
                        return net_names
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet get_all_net_names_tron " + str(traceback.format_exc()))
        return {}

    async def async_deposit(self, ctx, token: str = None, plain: str = None):
        coin_name = None
        if token is None:
            await ctx.response.send_message(f'{ctx.author.mention}, token name is missing.')
            return
        else:
            coin_name = token.upper()
            if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
                coin_name = self.bot.coin_alias_names[coin_name]
            if not hasattr(self.bot.coin_list, coin_name):
                await ctx.response.send_message(f'{ctx.author.mention}, **{coin_name}** does not exist with us.')
                return
            else:
                if getattr(getattr(self.bot.coin_list, coin_name), "enable_deposit") == 0:
                    await ctx.response.send_message(f'{ctx.author.mention}, **{coin_name}** deposit disable.')
                    return

        # Do the job
        try:
            await ctx.response.send_message(f'{ctx.author.mention}, checking your {coin_name} address...',
                                            ephemeral=True)

            try:
                self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                             str(ctx.author.id), SERVER_BOT, "/deposit", int(time.time())))
                await self.utils.add_command_calls()
            except Exception:
                traceback.print_exc(file=sys.stdout)

            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            get_deposit = await self.sql_get_userwallet(str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT,
                                                        0)
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            if get_deposit is None:
                get_deposit = await self.sql_register_user(str(ctx.author.id), coin_name, net_name, type_coin,
                                                           SERVER_BOT, 0, 0)

            wallet_address = get_deposit['balance_wallet_address']
            description = ""
            fee_txt = ""
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
            if getattr(getattr(self.bot.coin_list, coin_name), "deposit_note") and len(
                    getattr(getattr(self.bot.coin_list, coin_name), "deposit_note")) > 0:
                description = getattr(getattr(self.bot.coin_list, coin_name), "deposit_note")
            if getattr(getattr(self.bot.coin_list, coin_name), "real_deposit_fee") and getattr(
                    getattr(self.bot.coin_list, coin_name), "real_deposit_fee") > 0:
                real_min_deposit = getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit")
                real_deposit_fee = getattr(getattr(self.bot.coin_list, coin_name), "real_deposit_fee")
                real_deposit_fee_text = ""
                if real_deposit_fee > 0:
                    real_deposit_fee_text = " {} {}".format(
                        num_format_coin(real_deposit_fee, coin_name, coin_decimal, False), token_display)
                fee_txt = " You must deposit at least {} {} to cover fees needed to credit your account. The fee{} will be deducted from your deposit amount.".format(
                    num_format_coin(real_min_deposit, coin_name, coin_decimal, False), token_display,
                    real_deposit_fee_text)
            embed = disnake.Embed(title=f'Deposit for {ctx.author.name}#{ctx.author.discriminator}',
                                  description=description + fee_txt, timestamp=datetime.fromtimestamp(int(time.time())))
            embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
            qr_address = wallet_address
            if coin_name == "HNT":
                address_memo = wallet_address.split()
                qr_address = '{"type":"payment","address":"' + address_memo[0] + '","memo":"' + address_memo[2] + '"}'
            elif type_coin in ["XLM", "VITE"]:
                address_memo = wallet_address.split()
                qr_address = address_memo[0]
            try:
                gen_qr_address = await self.generate_qr_address(qr_address)
                address_path = qr_address.replace('{', '_').replace('}', '_').replace(':', '_').replace('"',
                                                                                                        "_").replace(
                    ',', "_").replace(' ', "_")
            except Exception:
                traceback.print_exc(file=sys.stdout)

            plain_msg = '{}#{} Your deposit address for **{}**: ```{}```'.format(ctx.author.name,
                                                                                 ctx.author.discriminator, coin_name,
                                                                                 wallet_address)
            if coin_name in ["HNT", "XLM", "VITE"]:
                plain_msg = '{}#{} Your deposit address for **{}**: ```{}```'.format(ctx.author.name,
                                                                                     ctx.author.discriminator,
                                                                                     coin_name, wallet_address)
                plain_msg += "MEMO must be included OR you will lose: `{}`".format(address_memo[2])

            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"] and getattr(
                    getattr(self.bot.coin_list, coin_name),
                    "split_main_paymentid") == 1:  # split main and integrated address
                embed.add_field(name="Main Address", value="`{}`".format(get_deposit['main_address']), inline=False)
                embed.add_field(name="PaymentID (Must include)", value="`{}`".format(get_deposit['paymentid']),
                                inline=False)
            else:
                wallet_address_new = wallet_address
                if " MEMO:" in wallet_address_new:
                    wallet_address_new = wallet_address_new.replace(" MEMO:", "\nMEMO:")
                embed.add_field(name="Your Deposit Address", value="`{}`".format(wallet_address_new), inline=False)
                embed.set_thumbnail(url=config.storage.deposit_url + address_path + ".png")

            if getattr(getattr(self.bot.coin_list, coin_name), "related_coins"):
                embed.add_field(name="Related Coins", value="```{}```".format(
                    getattr(getattr(self.bot.coin_list, coin_name), "related_coins")), inline=False)

            if getattr(getattr(self.bot.coin_list, coin_name), "explorer_link") and len(
                    getattr(getattr(self.bot.coin_list, coin_name), "explorer_link")) > 0:
                embed.add_field(name="Other links", value="[{}]({})".format("Explorer", getattr(
                    getattr(self.bot.coin_list, coin_name), "explorer_link")), inline=False)

            if coin_name == "HNT":  # put memo and base64
                try:
                    address_memo = wallet_address.split()
                    embed.add_field(name="MEMO", value="```Ascii: {}\nBase64: {}```".format(address_memo[2],
                                                                                            base64.b64encode(
                                                                                                address_memo[2].encode(
                                                                                                    'ascii')).decode(
                                                                                                'ascii')), inline=False)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            elif type_coin in ["XLM", "VITE"]:
                try:
                    address_memo = wallet_address.split()
                    embed.add_field(name="MEMO", value="```{}```".format(address_memo[2]), inline=False)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            embed.set_footer(text="Use: deposit plain (for plain text)")
            try:
                if plain and plain.lower() == 'plain' or plain.lower() == 'text':
                    await ctx.edit_original_message(content=plain_msg)
                else:
                    await ctx.edit_original_message(embed=embed)
            except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.slash_command(
        usage='deposit <token> [plain/embed]',
        options=[
            Option('token', 'token', OptionType.string, required=True),
            Option('plain', 'plain', OptionType.string, required=False)
        ],
        description="Get your wallet deposit address."
    )
    async def deposit(
        self,
        ctx,
        token: str,
        plain: str = 'embed'
    ):
        await self.async_deposit(ctx, token, plain)

    # End of deposit

    # Balance
    async def async_balance(self, ctx, token: str = None):
        coin_name = None
        if token is None:
            await ctx.response.send_message(f'{ctx.author.mention}, token name is missing.')
            return
        else:
            coin_name = token.upper()
            if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
                coin_name = self.bot.coin_alias_names[coin_name]
            if not hasattr(self.bot.coin_list, coin_name):
                await ctx.response.send_message(f'{ctx.author.mention}, **{coin_name}** does not exist with us.')
                return
            else:
                if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 1:
                    await ctx.response.send_message(
                        f'{ctx.author.mention}, **{coin_name}** is currently under maintenance.')
                    return
        # Do the job
        try:
            await ctx.response.send_message(f'{ctx.author.mention}, checking your {coin_name} balance...',
                                            ephemeral=True)

            try:
                self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                             str(ctx.author.id), SERVER_BOT, "/balance", int(time.time())))
                await self.utils.add_command_calls()
            except Exception:
                traceback.print_exc(file=sys.stdout)

            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name), "usd_equivalent_enable")

            get_deposit = await self.sql_get_userwallet(str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT,
                                                        0)
            if get_deposit is None:
                get_deposit = await self.sql_register_user(str(ctx.author.id), coin_name, net_name, type_coin,
                                                           SERVER_BOT, 0, 0)

            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']
            elif type_coin in ["XRP"]:
                wallet_address = get_deposit['destination_tag']

            height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
            description = ""
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
            embed = disnake.Embed(title=f'Balance for {ctx.author.name}#{ctx.author.discriminator}',
                                  timestamp=datetime.fromtimestamp(int(time.time())))
            embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
            try:
                # height can be None
                userdata_balance = await self.wallet_api.user_balance(str(ctx.author.id), coin_name, 
                                                                      wallet_address, type_coin,
                                                                      height, deposit_confirm_depth, SERVER_BOT)
                total_balance = userdata_balance['adjust']
                equivalent_usd = ""
                if usd_equivalent_enable == 1:
                    native_token_name = getattr(getattr(self.bot.coin_list, coin_name), "native_token_name")
                    coin_name_for_price = coin_name
                    if native_token_name:
                        coin_name_for_price = native_token_name
                    per_unit = None
                    if coin_name_for_price in self.bot.token_hints:
                        id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                        per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                    else:
                        per_unit = self.bot.coin_paprika_symbol_list[coin_name_for_price]['price_usd']
                    if per_unit and per_unit > 0:
                        total_in_usd = float(Decimal(total_balance) * Decimal(per_unit))
                        if total_in_usd >= 0.01:
                            equivalent_usd = " ~ {:,.2f}$".format(total_in_usd)
                        elif total_in_usd >= 0.0001:
                            equivalent_usd = " ~ {:,.4f}$".format(total_in_usd)
                embed.add_field(name="Token/Coin {}{}".format(token_display, equivalent_usd),
                                value="```Available: {} {}```".format(
                                    num_format_coin(total_balance, coin_name, coin_decimal, False), token_display),
                                inline=False)
            except Exception:
                traceback.print_exc(file=sys.stdout)

            await ctx.edit_original_message(embed=embed)
            # Add update for future call
            try:
                await self.utils.update_user_balance_call(str(ctx.author.id), type_coin)
            except Exception:
                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    # Balances
    async def async_balances(self, ctx, tokens: str = None):
        await ctx.response.send_message(f"{ctx.author.mention} balance loading...", ephemeral=True)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/balances", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        coin_name = None
        mytokens = []
        zero_tokens = []
        unknown_tokens = []
        has_none_balance = True
        start_time = int(time.time())
        if tokens is None:
            # do all coins/token which is not under maintenance
            mytokens = await store.get_coin_settings(coin_type=None)
        else:
            # get list of coin/token from tokens
            get_tokens = await store.get_coin_settings(coin_type=None)
            token_list = None
            tokens = tokens.replace(",", " ").replace(";", " ").replace("/", " ")
            if " " in tokens:
                token_list = tokens.upper().split()
            else:
                # one token
                token_list = [tokens.upper().strip()]
            if token_list and len(token_list) > 0:
                token_list = list(set(token_list))
                for each_token in token_list:
                    try:
                        if getattr(self.bot.coin_list, each_token):
                            mytokens.append(getattr(self.bot.coin_list, each_token))
                    except Exception:
                        unknown_tokens.append(each_token)

        if len(mytokens) == 0:
            msg = f'{ctx.author.mention}, no token or not exist.'
            await ctx.edit_original_message(content=msg)
            return
        else:
            total_all_balance_usd = 0.0
            all_pages = []
            all_names = [each['coin_name'] for each in mytokens]
            total_coins = len(mytokens)
            page = disnake.Embed(title='[ YOUR BALANCE LIST ]',
                                 description="Thank you for using TipBot!",
                                 color=disnake.Color.blue(),
                                 timestamp=datetime.fromtimestamp(int(time.time())), )
            page.add_field(name="Coin/Tokens: [{}]".format(len(all_names)),
                           value="```" + ", ".join(all_names) + "```", inline=False)
            if len(unknown_tokens) > 0:
                unknown_tokens = list(set(unknown_tokens))
                page.add_field(name="Unknown Tokens: {}".format(len(unknown_tokens)),
                               value="```" + ", ".join(unknown_tokens) + "```", inline=False)
            page.set_thumbnail(url=ctx.author.display_avatar)
            page.set_footer(text="Use the reactions to flip pages.")
            all_pages.append(page)
            num_coins = 0
            per_page = 20
            # check mutual guild for is_on_mobile
            try:
                if isinstance(ctx.channel, disnake.DMChannel):
                    one_guild = [each for each in ctx.author.mutual_guilds][0]
                else:
                    one_guild = ctx.guild
                member = one_guild.get_member(ctx.author.id)
                if member.is_on_mobile() is True:
                    per_page = 10
            except Exception:
                pass

            bstart = time.time()
            for each_token in mytokens:
                try:
                    coin_name = each_token['coin_name']
                    type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                    net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                    deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                    token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                    usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name), "usd_equivalent_enable")
                    get_deposit = await self.sql_get_userwallet(str(ctx.author.id), coin_name, net_name, type_coin,
                                                                SERVER_BOT, 0)
                    if get_deposit is None:
                        get_deposit = await self.sql_register_user(str(ctx.author.id), coin_name, net_name, type_coin,
                                                                   SERVER_BOT, 0, 0)
                    wallet_address = get_deposit['balance_wallet_address']
                    if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        wallet_address = get_deposit['paymentid']
                    elif type_coin in ["XRP"]:
                        wallet_address = get_deposit['destination_tag']

                    height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                    try:
                        # Add update for future call
                        await self.utils.update_user_balance_call(str(ctx.author.id), type_coin)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    if num_coins == 0 or num_coins % per_page == 0:
                        page = disnake.Embed(title='[ YOUR BALANCE LIST ]',
                                             description="Thank you for using TipBot!",
                                             color=disnake.Color.blue(),
                                             timestamp=datetime.fromtimestamp(int(time.time())), )
                        page.set_thumbnail(url=ctx.author.display_avatar)
                        page.set_footer(text="Use the reactions to flip pages.")
                    # height can be None
                    userdata_balance = await self.wallet_api.user_balance(str(ctx.author.id), coin_name, 
                                                                          wallet_address, type_coin,
                                                                          height, deposit_confirm_depth, SERVER_BOT)
                    total_balance = userdata_balance['adjust']
                    if total_balance == 0:
                        zero_tokens.append(coin_name)
                        continue
                    elif total_balance > 0:
                        has_none_balance = False
                    equivalent_usd = ""
                    if usd_equivalent_enable == 1:
                        native_token_name = getattr(getattr(self.bot.coin_list, coin_name), "native_token_name")
                        coin_name_for_price = coin_name
                        if native_token_name:
                            coin_name_for_price = native_token_name
                        per_unit = None
                        if coin_name_for_price in self.bot.token_hints:
                            id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                            per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                        else:
                            per_unit = self.bot.coin_paprika_symbol_list[coin_name_for_price]['price_usd']
                        if per_unit and per_unit > 0:
                            total_in_usd = float(Decimal(total_balance) * Decimal(per_unit))
                            total_all_balance_usd += total_in_usd
                            if total_in_usd >= 0.01:
                                equivalent_usd = " ~ {:,.2f}$".format(total_in_usd)
                            elif total_in_usd >= 0.0001:
                                equivalent_usd = " ~ {:,.4f}$".format(total_in_usd)

                    page.add_field(name="{}{}".format(token_display, equivalent_usd), value="{}".format(
                        num_format_coin(total_balance, coin_name, coin_decimal, False)), inline=True)
                    num_coins += 1
                    if num_coins > 0 and num_coins % per_page == 0:
                        all_pages.append(page)
                        if num_coins < total_coins:
                            page = disnake.Embed(title='[ YOUR BALANCE LIST ]',
                                                 description="Thank you for using TipBot!",
                                                 color=disnake.Color.blue(),
                                                 timestamp=datetime.fromtimestamp(int(time.time())), )
                            page.set_thumbnail(url=ctx.author.display_avatar)
                            page.set_footer(text="Use the reactions to flip pages.")
                        else:
                            all_pages.append(page)
                            break
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            # Check if there is remaining
            if (total_coins - len(zero_tokens)) % per_page > 0:
                all_pages.append(page)
            # Replace first page
            if total_all_balance_usd > 0.01:
                total_all_balance_usd = "Having ~ {:,.2f}$".format(total_all_balance_usd)
            elif total_all_balance_usd > 0.0001:
                total_all_balance_usd = "Having ~ {:,.4f}$".format(total_all_balance_usd)
            else:
                total_all_balance_usd = "Thank you for using TipBot!"
            page = disnake.Embed(title='[ YOUR BALANCE LIST ]',
                                 description=f"`{total_all_balance_usd}`",
                                 color=disnake.Color.blue(),
                                 timestamp=datetime.fromtimestamp(int(time.time())), )
            # Remove zero from all_names
            if has_none_balance is True:
                msg = f'{ctx.author.mention}, you do not have any balance or the inquired tokens are empty.'
                await ctx.edit_original_message(content=msg)
                return
            else:
                all_names = [each for each in all_names if each not in zero_tokens]
                page.add_field(name="Coin/Tokens: [{}]".format(len(all_names)),
                               value="```" + ", ".join(all_names) + "```", inline=False)
                if len(unknown_tokens) > 0:
                    unknown_tokens = list(set(unknown_tokens))
                    page.add_field(name="Unknown Tokens: {}".format(len(unknown_tokens)),
                                   value="```" + ", ".join(unknown_tokens) + "```", inline=False)
                if len(zero_tokens) > 0:
                    zero_tokens = list(set(zero_tokens))
                    page.add_field(name="Zero Balances: [{}]".format(len(zero_tokens)),
                                   value="```" + ", ".join(zero_tokens) + "```", inline=False)
                page.set_thumbnail(url=ctx.author.display_avatar)
                page.set_footer(text="Use the reactions to flip pages.")
                all_pages[0] = page
                try:
                    view = MenuPage(ctx, all_pages, timeout=30, disable_remove=True)
                    view.message = await ctx.edit_original_message(content=None, embed=all_pages[0], view=view)
                    if int(time.time()) - start_time > 5:
                        await logchanbot(f"[LAG] /balances lagging very long with {ctx.author.name}#{ctx.author.discriminator}. Time taken {str(int(time.time()) - start_time)}s.")
                except Exception:
                    msg = f'{ctx.author.mention}, internal error when checking /balances. Try again later. If problem still persists, contact TipBot dev.'
                    await ctx.edit_original_message(content=msg)
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(f"[ERROR] /balances with {ctx.author.name}#{ctx.author.discriminator}")


    @commands.slash_command(
        usage='balance <token>',
        options=[
            Option('token', 'token', OptionType.string, required=True)
        ],
        description="Get your token's balance."
    )
    async def balance(
        self,
        ctx,
        token: str
    ):
        if token.upper() == "ALL":
            await self.async_balances(ctx, None)
        else:
            await self.async_balance(ctx, token)

    @commands.slash_command(
        usage='balances',
        options=[
            Option('tokens', 'tokens', OptionType.string, required=False)
        ],
        description="Get all your token's balance."
    )
    async def balances(
        self,
        ctx,
        tokens: str = None
    ):
        if tokens and hasattr(self.bot.coin_list, tokens.upper()):
            await self.async_balance(ctx, tokens)
        else:
            await self.async_balances(ctx, tokens)

    # End of Balance

    # Withdraw
    async def async_withdraw(self, ctx, amount: str, token: str, address: str):
        withdraw_tx_ephemeral = False
        coin_name = token.upper()
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
            await ctx.response.send_message(msg)
            return
        else:
            if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 1:
                msg = f'{ctx.author.mention}, **{coin_name}** is currently under maintenance.'
                await ctx.response.send_message(msg)
                return
            if getattr(getattr(self.bot.coin_list, coin_name), "enable_withdraw") != 1:
                msg = f'{ctx.author.mention}, **{coin_name}** withdraw is currently disable.'
                await ctx.response.send_message(msg)
                return

        await ctx.response.send_message(f"{EMOJI_HOURGLASS_NOT_DONE}, checking withdraw for {ctx.author.mention}..", ephemeral=True)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/withdraw", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        # remove space from address
        address = address.replace(" ", "")
        try:
            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            min_tx = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tx")
            max_tx = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tx")
            NetFee = getattr(getattr(self.bot.coin_list, coin_name), "real_withdraw_fee")
            tx_fee = getattr(getattr(self.bot.coin_list, coin_name), "tx_fee")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name), "usd_equivalent_enable")
            try:
                check_exist = await self.check_withdraw_coin_address(type_coin, address)
                if check_exist is not None:
                    msg = f'{EMOJI_ERROR} {ctx.author.mention}, you cannot send to this address `{address}`.'
                    await ctx.edit_original_message(content=msg)
                    return
            except Exception:
                traceback.print_exc(file=sys.stdout)

            if tx_fee is None:
                tx_fee = NetFee
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
            fee_limit = getattr(getattr(self.bot.coin_list, coin_name), "fee_limit")
            get_deposit = await self.sql_get_userwallet(str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT,
                                                        0)
            if get_deposit is None:
                get_deposit = await self.sql_register_user(str(ctx.author.id), coin_name, net_name, type_coin,
                                                           SERVER_BOT, 0, 0)

            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']
            elif type_coin in ["XRP"]:
                wallet_address = get_deposit['destination_tag']

            # Check if tx in progress
            if ctx.author.id in self.bot.TX_IN_PROCESS:
                msg = f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
                await ctx.edit_original_message(content=msg)
                return

            height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
            if height is None:
                msg = f'{ctx.author.mention}, **{coin_name}** cannot pull information from network. Try again later.'
                await ctx.edit_original_message(content=msg)
                return
            else:
                # check if amount is all
                all_amount = False
                if not amount.isdigit() and amount.upper() == "ALL":
                    all_amount = True
                    userdata_balance = await self.wallet_api.user_balance(str(ctx.author.id), coin_name, 
                                                                          wallet_address, type_coin,
                                                                          height, deposit_confirm_depth, SERVER_BOT)
                    amount = float(userdata_balance['adjust']) - NetFee
                # If $ is in amount, let's convert to coin/token
                elif "$" in amount[-1] or "$" in amount[0]:  # last is $
                    # Check if conversion is allowed for this coin.
                    amount = amount.replace(",", "").replace("$", "")
                    if usd_equivalent_enable == 0:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{coin_name}`."
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        native_token_name = getattr(getattr(self.bot.coin_list, coin_name), "native_token_name")
                        coin_name_for_price = coin_name
                        if native_token_name:
                            coin_name_for_price = native_token_name
                        per_unit = None
                        if coin_name_for_price in self.bot.token_hints:
                            id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                            per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                        else:
                            per_unit = self.bot.coin_paprika_symbol_list[coin_name_for_price]['price_usd']
                        if per_unit and per_unit > 0:
                            amount = float(Decimal(amount) / Decimal(per_unit))
                        else:
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. Try with different method.'
                            await ctx.edit_original_message(content=msg)
                            return
                else:
                    amount = amount.replace(",", "")
                    amount = text_to_num(amount)
                    if amount is None:
                        await ctx.edit_original_message(
                            content=f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.')
                        return

                if getattr(getattr(self.bot.coin_list, coin_name), "integer_amount_only") == 1:
                    amount = int(amount)

                # end of check if amount is all
                amount = float(amount)
                userdata_balance = await self.wallet_api.user_balance(str(ctx.author.id), coin_name, 
                                                                      wallet_address, type_coin,
                                                                      height, deposit_confirm_depth, SERVER_BOT)
                actual_balance = float(userdata_balance['adjust'])

                # If balance 0, no need to check anything
                if actual_balance <= 0:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please check your **{token_display}** balance.'
                    await ctx.edit_original_message(content=msg)
                    return
                if amount > actual_balance:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to send out {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}.'
                    await ctx.edit_original_message(content=msg)
                    return

                if amount + NetFee > actual_balance:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to send out {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}. You need to leave at least network fee: {num_format_coin(NetFee, coin_name, coin_decimal, False)} {token_display}.'
                    await ctx.edit_original_message(content=msg)
                    return
                elif amount < min_tx or amount > max_tx:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, transaction cannot be smaller than {num_format_coin(min_tx, coin_name, coin_decimal, False)} {token_display} or bigger than {num_format_coin(max_tx, coin_name, coin_decimal, False)} {token_display}.'
                    await ctx.edit_original_message(content=msg)
                    return

                equivalent_usd = ""
                total_in_usd = 0.0
                per_unit = None
                if usd_equivalent_enable == 1:
                    native_token_name = getattr(getattr(self.bot.coin_list, coin_name), "native_token_name")
                    coin_name_for_price = coin_name
                    if native_token_name:
                        coin_name_for_price = native_token_name
                    if coin_name_for_price in self.bot.token_hints:
                        id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                        per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                    else:
                        per_unit = self.bot.coin_paprika_symbol_list[coin_name_for_price]['price_usd']
                    if per_unit and per_unit > 0:
                        total_in_usd = float(Decimal(amount) * Decimal(per_unit))
                        if total_in_usd >= 0.0001:
                            equivalent_usd = " ~ {:,.4f} USD".format(total_in_usd)

                if type_coin in ["ERC-20"]:
                    # Check address
                    valid_address = self.check_address_erc20(address)
                    valid = False
                    if valid_address and valid_address.upper() == address.upper():
                        valid = True
                    else:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid address:\n`{address}`'
                        await ctx.edit_original_message(content=msg)
                        return

                    send_tx = None
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        try:
                            url = self.bot.erc_node_list[net_name]
                            chain_id = getattr(getattr(self.bot.coin_list, coin_name), "chain_id")
                            send_tx = await self.send_external_erc20(url, net_name, str(ctx.author.id), address, amount,
                                                                    coin_name, coin_decimal, NetFee, SERVER_BOT,
                                                                    chain_id, contract)
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot("wallet /withdraw " + str(traceback.format_exc()))
                        self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                        return

                    if send_tx:
                        fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                            num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                        try:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                            return
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                        try:
                            await logchanbot(
                                f'[{SERVER_BOT}] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} sucessfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}')
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                    else:
                        msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.'
                        await ctx.edit_original_message(content=msg)
                        await logchanbot(
                            f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                elif type_coin in ["TRC-20", "TRC-10"]:
                    # TODO: validate address
                    send_tx = None
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        try:
                            send_tx = await self.send_external_trc20(str(ctx.author.id), address, amount, coin_name,
                                                                    coin_decimal, NetFee, SERVER_BOT, fee_limit,
                                                                    type_coin, contract)
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot("wallet /withdraw " + str(traceback.format_exc()))
                        self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.ctx.edit_original_message(content=msg)
                        return

                    if send_tx:
                        fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                            num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                        try:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                            return
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                        try:
                            await logchanbot(
                                f'[{SERVER_BOT}] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} sucessfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}')
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                    else:
                        msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.'
                        await ctx.edit_original_message(content=msg)
                        await logchanbot(
                            f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                elif type_coin == "NANO":
                    valid_address = await self.wallet_api.nano_validate_address(coin_name, address)
                    if not valid_address is True:
                        msg = f"{EMOJI_RED_NO} Address: `{address}` is invalid."
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        if ctx.author.id not in self.bot.TX_IN_PROCESS:
                            self.bot.TX_IN_PROCESS.append(ctx.author.id)
                            try:
                                main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                                send_tx = await self.wallet_api.send_external_nano(main_address, str(ctx.author.id),
                                                                                  amount, address, coin_name,
                                                                                  coin_decimal)
                                if send_tx:
                                    fee_txt = "\nWithdrew fee/node: `0.00 {}`.".format(coin_name)
                                    SendTx_hash = send_tx['block']
                                    msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{SendTx_hash}`{fee_txt}'
                                    await ctx.edit_original_message(content=msg)
                                    await logchanbot(
                                        f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                else:
                                    msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.'
                                    await ctx.edit_original_message(content=msg)
                                    await logchanbot(
                                        f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                                await logchanbot("wallet /withdraw " + str(traceback.format_exc()))
                            self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                        else:
                            # reject and tell to wait
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                            await ctx.edit_original_message(content=msg)
                            return
                elif type_coin == "CHIA":
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        send_tx = await self.wallet_api.send_external_xch(str(ctx.author.id), amount, address, coin_name,
                                                                         coin_decimal, tx_fee, NetFee, SERVER_BOT)
                        if send_tx:
                            fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                            await logchanbot(
                                f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                        else:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                        return
                elif type_coin == "HNT":
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        wallet_host = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
                        main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                        password = decrypt_string(getattr(getattr(self.bot.coin_list, coin_name), "walletkey"))
                        send_tx = await self.wallet_api.send_external_hnt(str(ctx.author.id), wallet_host, password,
                                                                         main_address, address, amount, coin_decimal,
                                                                         SERVER_BOT, coin_name, NetFee, 32)
                        if send_tx:
                            fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                            await logchanbot(
                                f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                        else:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                        return
                elif type_coin == "VITE":
                    url = getattr(getattr(self.bot.coin_list, coin_name), "rpchost")
                    main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                    contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                    key = decrypt_string(getattr(getattr(self.bot.coin_list, coin_name), "walletkey"))
                    priv = base64.b64decode(key).hex()
                    atomic_amount = str(int(amount*10**coin_decimal))
                    if address == main_address:
                        # can not send
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you cannot send to this address `{address}`.'
                        await ctx.edit_original_message(content=msg)
                        return
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        send_tx = await vite_send_tx(url, main_address, address, atomic_amount, "", contract, priv)
                        if send_tx:
                            tx_hash = send_tx['hash']
                            await self.wallet_api.insert_external_vite(str(ctx.author.id), amount, address, coin_name, contract, coin_decimal, NetFee, send_tx['hash'], json.dumps(send_tx), SERVER_BOT)
                            fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                            await logchanbot(
                                f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{tx_hash}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                        else:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                        return
                elif type_coin == "XLM":
                    url = getattr(getattr(self.bot.coin_list, coin_name), "http_address")
                    main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                    if address == main_address:
                        # can not send
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you cannot send to this address `{address}`.'
                        await ctx.edit_original_message(content=msg)
                        return
                    if coin_name != "XLM":  # in case of asset
                        issuer = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                        asset_code = getattr(getattr(self.bot.coin_list, coin_name), "header")
                        check_asset = await self.wallet_api.check_xlm_asset(url, asset_code, issuer, address,
                                                                            str(ctx.author.id), SERVER_BOT)
                        if check_asset is False:
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you cannot send to this address `{address}`. The destination account may not trust the asset you are attempting to send!'
                            await ctx.edit_original_message(content=msg)
                            return
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        wallet_host = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
                        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                        withdraw_keypair = decrypt_string(getattr(getattr(self.bot.coin_list, coin_name), "walletkey"))
                        asset_ticker = getattr(getattr(self.bot.coin_list, coin_name), "header")
                        asset_issuer = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                        send_tx = await self.wallet_api.send_external_xlm(url, withdraw_keypair, str(ctx.author.id),
                                                                         amount, address, coin_decimal, SERVER_BOT,
                                                                         coin_name, NetFee, asset_ticker, asset_issuer,
                                                                         32)
                        if send_tx:
                            fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                            await logchanbot(
                                f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                        else:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                        return
                elif type_coin == "ADA":
                    if not address.startswith("addr1"):
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid address. It should start with `addr1`.'
                        await ctx.edit_original_message(content=msg)
                        return
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        if coin_name == "ADA":
                            self.bot.TX_IN_PROCESS.append(ctx.author.id)
                            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                            fee_limit = getattr(getattr(self.bot.coin_list, coin_name), "fee_limit")
                            # Use fee limit as NetFee
                            send_tx = await self.wallet_api.send_external_ada(str(ctx.author.id), amount, coin_decimal,
                                                                             SERVER_BOT, coin_name, fee_limit, address,
                                                                             60)
                            if "status" in send_tx and send_tx['status'] == "pending":
                                tx_hash = send_tx['id']
                                fee = send_tx['fee']['quantity'] / 10 ** coin_decimal + fee_limit
                                fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                    num_format_coin(fee, coin_name, coin_decimal, False), coin_name)
                                await logchanbot(
                                    f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{tx_hash}`{fee_txt}'
                                await ctx.edit_original_message(content=msg)
                            elif "code" in send_tx and "message" in send_tx:
                                code = send_tx['code']
                                message = send_tx['message']
                                await logchanbot(
                                    f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.```code: {code}\nmessage: {message}```')
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, internal error, please try again later!'
                                await ctx.edit_original_message(content=msg)
                            else:
                                await logchanbot(
                                    f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, internal error, please try again later!'
                                await ctx.edit_original_message(content=msg)
                            self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                            return
                        else:
                            ## 
                            # Check user's ADA balance.
                            GAS_COIN = None
                            fee_limit = None
                            try:
                                if getattr(getattr(self.bot.coin_list, coin_name), "withdraw_use_gas_ticker") == 1:
                                    # add main token balance to check if enough to withdraw
                                    GAS_COIN = getattr(getattr(self.bot.coin_list, coin_name), "gas_ticker")
                                    fee_limit = getattr(getattr(self.bot.coin_list, coin_name), "fee_limit")
                                    if GAS_COIN:
                                        userdata_balance = await self.wallet_api.user_balance(str(ctx.author.id), GAS_COIN,
                                                                                              wallet_address, type_coin, height,
                                                                                              getattr(getattr(self.bot.coin_list, GAS_COIN), "deposit_confirm_depth"),
                                                                                              SERVER_BOT)
                                        actual_balance = userdata_balance['adjust']
                                        if actual_balance < fee_limit:  # use fee_limit to limit ADA
                                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you do not have sufficient {GAS_COIN} to withdraw {coin_name}. You need to have at least a reserved `{fee_limit} {GAS_COIN}`.'
                                            await ctx.edit_original_message(content=msg)
                                            await logchanbot(
                                                f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} want to withdraw asset {coin_name} but having only {actual_balance} {GAS_COIN}.')
                                            return
                                    else:
                                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid main token, please report!'
                                        await ctx.edit_original_message(content=msg)
                                        await logchanbot(
                                            f'[BUG] {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} invalid main token for {coin_name}.')
                                        return
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, cannot check balance, please try again later!'
                                await ctx.edit_original_message(content=msg)
                                await logchanbot(
                                    f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to check balance gas coin for asset transfer...')
                                return

                            self.bot.TX_IN_PROCESS.append(ctx.author.id)
                            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                            asset_name = getattr(getattr(self.bot.coin_list, coin_name), "header")
                            policy_id = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                            send_tx = await self.wallet_api.send_external_ada_asset(str(ctx.author.id), amount,
                                                                                   coin_decimal, SERVER_BOT, coin_name,
                                                                                   NetFee, address, asset_name,
                                                                                   policy_id, 60)
                            if "status" in send_tx and send_tx['status'] == "pending":
                                tx_hash = send_tx['id']
                                gas_coin_msg = ""
                                if GAS_COIN is not None:
                                    gas_coin_msg = " and fee `{} {}` you shall receive additional `{} {}`.".format(
                                        num_format_coin(send_tx['network_fee'] + fee_limit / 20, GAS_COIN, 6, False),
                                        GAS_COIN, num_format_coin(send_tx['ada_received'], GAS_COIN, 6, False), GAS_COIN)
                                fee_txt = "\nWithdrew fee/node: `{} {}`{}.".format(
                                    num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name, gas_coin_msg)
                                await logchanbot(
                                    f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{tx_hash}`{fee_txt}'
                                await ctx.edit_original_message(content=msg)
                            elif "code" in send_tx and "message" in send_tx:
                                code = send_tx['code']
                                message = send_tx['message']
                                await logchanbot(
                                    f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.```code: {code}\nmessage: {message}```')
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, internal error, please try again later!'
                                await ctx.edit_original_message(content=msg)
                            else:
                                await logchanbot(
                                    f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, internal error, please try again later!'
                                await ctx.edit_original_message(content=msg)
                            self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                            return
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                        return
                elif type_coin == "XTZ":
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        url = self.bot.erc_node_list['XTZ']
                        key = decrypt_string(getattr(getattr(self.bot.coin_list, "XTZ"), "walletkey"))
                        main_address = getattr(getattr(self.bot.coin_list, "XTZ"), "MainAddress")
                        if address == main_address:
                            # can not send
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you cannot send to this address `{address}`.'
                            await ctx.edit_original_message(content=msg)
                            return
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        send_tx = None
                        if coin_name == "XTZ":
                            send_tx = await self.wallet_api.send_external_xtz(url, key, str(ctx.author.id), amount, address, coin_name, coin_decimal, NetFee, type_coin, SERVER_BOT)
                        else:
                            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                            token_id = int(getattr(getattr(self.bot.coin_list, coin_name), "wallet_address"))
                            token_type = getattr(getattr(self.bot.coin_list, coin_name), "header")
                            send_tx = await self.wallet_api.send_external_xtz_asset(url, key, str(ctx.author.id), amount, address, coin_name, coin_decimal, NetFee, type_coin, contract, token_id, token_type, SERVER_BOT)
                        if send_tx:
                            fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        else:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                    self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                elif type_coin == "ZIL":
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        key = decrypt_string(getattr(getattr(self.bot.coin_list, "ZIL"), "walletkey"))
                        main_address = getattr(getattr(self.bot.coin_list, "ZIL"), "MainAddress")
                        if address == main_address:
                            # can not send
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you cannot send to this address `{address}`.'
                            await ctx.edit_original_message(content=msg)
                            return
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        send_tx = None
                        if coin_name == "ZIL":
                            send_tx = await self.wallet_api.send_external_zil(key, str(ctx.author.id), amount, address, coin_name, coin_decimal, NetFee, type_coin, SERVER_BOT)
                        else:
                            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                            send_tx = await self.wallet_api.send_external_zil_asset(contract, key, str(ctx.author.id), int(amount * 10 ** coin_decimal), address, coin_name, coin_decimal, NetFee, type_coin, SERVER_BOT)
                        if send_tx:
                            fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        else:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                    self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                elif type_coin == "VET":
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        key = decrypt_string(getattr(getattr(self.bot.coin_list, "VET"), "walletkey"))
                        main_address = getattr(getattr(self.bot.coin_list, "VET"), "MainAddress")
                        contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                        if address == main_address:
                            # can not send
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you cannot send to this address `{address}`.'
                            await ctx.edit_original_message(content=msg)
                            return
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        transaction = functools.partial(vet_move_token, self.bot.erc_node_list['VET'], coin_name, contract, address, key, key, int(amount*10**coin_decimal))
                        send_tx = await self.bot.loop.run_in_executor(None, transaction)
                        if send_tx:
                            await self.wallet_api.insert_external_vet(str(ctx.author.id), amount, address, coin_name, contract, coin_decimal, NetFee, send_tx, type_coin, SERVER_BOT)
                            fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        else:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                    self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                elif type_coin == "XRP":
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        url = self.bot.erc_node_list['XRP']
                        key = decrypt_string(getattr(getattr(self.bot.coin_list, "XRP"), "walletkey"))
                        main_address = getattr(getattr(self.bot.coin_list, "XRP"), "MainAddress")
                        if address == main_address:
                            # can not send
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you cannot send to this address `{address}`.'
                            await ctx.edit_original_message(content=msg)
                            return
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        issuer = getattr(getattr(self.bot.coin_list, coin_name), "header")
                        currency_code = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                        send_tx = await self.wallet_api.send_external_xrp(url, key, str(ctx.author.id), address, amount, NetFee, coin_name, issuer, currency_code, coin_decimal, SERVER_BOT)
                        if send_tx:
                            fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        else:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                    self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                elif type_coin == "NEAR":
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        url = self.bot.erc_node_list['NEAR']
                        key = decrypt_string(getattr(getattr(self.bot.coin_list, "NEAR"), "walletkey"))
                        main_address = getattr(getattr(self.bot.coin_list, "NEAR"), "MainAddress")
                        token_contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                        if address == main_address:
                            # can not send
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you cannot send to this address `{address}`.'
                            await ctx.edit_original_message(content=msg)
                            return
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        send_tx = await self.wallet_api.send_external_near(url, token_contract, key, str(ctx.author.id), main_address, amount, address, coin_name, coin_decimal, NetFee, SERVER_BOT)
                        if send_tx:
                            fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        else:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                    self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                elif type_coin == "SOL" or type_coin == "SPL":
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        tx_fee = getattr(getattr(self.bot.coin_list, coin_name), "tx_fee")
                        send_tx = await self.wallet_api.send_external_sol(self.bot.erc_node_list['SOL'],
                                                                         str(ctx.author.id), amount, address, coin_name,
                                                                         coin_decimal, tx_fee, NetFee, SERVER_BOT)
                        if send_tx:
                            fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        else:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                        return
                elif type_coin == "BTC":
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        send_tx = await self.wallet_api.send_external_doge(str(ctx.author.id), amount, address,
                                                                          coin_name, 0, NetFee, SERVER_BOT)  # tx_fee=0
                        if send_tx:
                            fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        else:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                        return
                elif type_coin == "NEO":
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                        send_tx = await self.wallet_api.send_external_neo(str(ctx.author.id), coin_decimal, contract, amount, address,
                                                                          coin_name, NetFee, SERVER_BOT)
                        if send_tx:
                            fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        else:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'[FAILED] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                        return
                elif type_coin == "XMR" or type_coin == "TRTL-API" or type_coin == "TRTL-SERVICE" or type_coin == "BCN":
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                        mixin = getattr(getattr(self.bot.coin_list, coin_name), "mixin")
                        wallet_address = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
                        header = getattr(getattr(self.bot.coin_list, coin_name), "header")
                        is_fee_per_byte = getattr(getattr(self.bot.coin_list, coin_name), "is_fee_per_byte")
                        send_tx = await self.wallet_api.send_external_xmr(type_coin, main_address, str(ctx.author.id),
                                                                         amount, address, coin_name, coin_decimal,
                                                                         tx_fee, NetFee, is_fee_per_byte, mixin,
                                                                         SERVER_BOT, wallet_address, header,
                                                                         None)  # paymentId: None (end)
                        if send_tx:
                            fee_txt = "\nWithdrew fee/node: `{} {}`.".format(
                                num_format_coin(NetFee, coin_name, coin_decimal, False), coin_name)
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.\nTransaction hash: `{send_tx}`{fee_txt}'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully executed withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        else:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd} to `{address}`.'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} failed to execute to withdraw {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
                        self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.edit_original_message(content=msg)
                        return
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.slash_command(
        usage='withdraw',
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('token', 'token', OptionType.string, required=True),
            Option('address', 'address', OptionType.string, required=True)
        ],
        description="withdraw to your external address."
    )
    async def withdraw(
        self,
        ctx,
        amount: str,
        token: str,
        address: str
    ):
        await self.async_withdraw(ctx, amount, token, address)

    @commands.slash_command(
        usage='transfer',
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('token', 'token', OptionType.string, required=True),
            Option('address', 'address', OptionType.string, required=True)
        ],
        description="withdraw to your external address."
    )
    async def transfer(
        self,
        ctx,
        amount: str,
        token: str,
        address: str
    ):
        await self.async_withdraw(ctx, amount, token, address)

    @commands.slash_command(
        usage='send',
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('token', 'token', OptionType.string, required=True),
            Option('address', 'address', OptionType.string, required=True)
        ],
        description="withdraw to your external address."
    )
    async def send(
        self,
        ctx,
        amount: str,
        token: str,
        address: str
    ):
        await self.async_withdraw(ctx, amount, token, address)

    # End of Withdraw

    # Faucet
    async def async_claim(self, ctx: str, token: str = None):

        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Bot's checking claim..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/claim", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        faucet = Faucet(self.bot)
        get_user_coin = await faucet.get_user_faucet_coin(str(ctx.author.id), SERVER_BOT)
        list_coins = await faucet.get_faucet_coin_list()
        list_coin_names = list(set([each['coin_name'] for each in list_coins]))
        title_text = " [You haven't set any preferred reward!]"
        if get_user_coin is None:
            title_text = " [You haven't set any preferred reward!]"
        elif get_user_coin and get_user_coin['coin_name']:
            title_text = " [Preferred {}]".format(get_user_coin['coin_name'])
        list_coin_sets = {}
        for each in list_coins:
            if each['reward_for'] not in list_coin_sets:
                list_coin_sets[each['reward_for']] = []
                list_coin_sets[each['reward_for']].append({each['coin_name']: each['reward_amount']})
            else:
                list_coin_sets[each['reward_for']].append({each['coin_name']: each['reward_amount']})
        list_coins_str = ", ".join(list_coin_names)
        if token is None:
            embed = disnake.Embed(title=f'Faucet Claim{title_text}',
                                  description=f"```1] Set your reward coin claim with any of this {list_coins_str} with command /claim token_name\n\n2] Vote for TipBot in below links.\n\n```",
                                  timestamp=datetime.fromtimestamp(int(time.time())))

            reward_list_default = []
            link_list = []
            for key in ["topgg", "discordbotlist", "botsfordiscord"]:
                reward_list = []
                for each in list_coin_sets[key]:
                    for k, v in each.items():
                        reward_list.append("{}{}".format(v, k))
                reward_list_default = reward_list
                link_list.append("Vote at: [{}]({})".format(key, getattr(config.bot_vote_link, key)))
            embed.add_field(name="Vote List", value="\n".join(link_list), inline=False)
            embed.add_field(name="Vote rewards".format(key), value="```{}```".format(", ".join(reward_list_default)),
                            inline=False)
            embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
            try:

                if get_user_coin is not None:
                    embed.set_footer(
                        text="Requested by: {}#{} | preferred: {}".format(ctx.author.name, ctx.author.discriminator,
                                                                          get_user_coin['coin_name']))
            except Exception:
                traceback.print_exc(file=sys.stdout)
            await ctx.edit_original_message(content=None, embed=embed, view=RowButtonRowCloseAnyMessage())
            return
        elif token.upper() in ["LISTS", "LIST"]:
            get_claim_lists = await self.collect_claim_list(str(self.bot.user.id), "BOTVOTE")
            if len(get_claim_lists) > 0:
                coin_list = {}
                vote_with_coin = {}
                nos_vote = 0
                for each in get_claim_lists:
                    nos_vote += 1
                    if each['token_name'] not in coin_list:
                        coin_list[each['token_name']] = each['real_amount']
                        vote_with_coin[each['token_name']] = 1
                    else:
                        coin_list[each['token_name']] += each['real_amount']
                        vote_with_coin[each['token_name']] += 1
                coin_list_values = []
                for k, v in coin_list.items():
                    coin_list_values.append("{:,.4f} {} - {:,.0f} time(s)".format(v, k, vote_with_coin[k]))

                embed = disnake.Embed(title=f'Vote claim stats', timestamp=datetime.now())
                embed.add_field(name="Total Vote", value="```{}```".format("\n".join(coin_list_values)), inline=False)
                embed.set_footer(
                    text="Requested by: {}#{} | Total votes: {:,.0f}".format(ctx.author.name, ctx.author.discriminator,
                                                                             nos_vote))
                await ctx.edit_original_message(content=None, embed=embed, view=RowButtonRowCloseAnyMessage())
            return
        else:
            coin_name = token.upper()
            if coin_name not in list_coin_names:
                msg = f'{ctx.author.mention}, `{coin_name}` is invalid or does not exist in faucet list!'
                await ctx.edit_original_message(content=msg)
                return
            else:
                # Update user setting faucet
                update = await faucet.update_faucet_user(str(ctx.author.id), coin_name, SERVER_BOT)
                if update:
                    msg = f'{ctx.author.mention}, you updated your preferred claimed reward to `{coin_name}`. This preference applies only for TipBot\'s voting reward.'
                    await ctx.edit_original_message(content=msg)
                else:
                    msg = f'{ctx.author.mention}, internal error!'
                    await ctx.edit_original_message(content=msg)

    @commands.slash_command(
        usage='claim',
        options=[
            Option('token', 'token', OptionType.string, required=False)
        ],
        description="Faucet claim."
    )
    async def claim(
        self,
        ctx,
        token: str = None
    ):
        await self.async_claim(ctx, token)

    async def bot_faucet(
        self,
        ctx,
        faucet_coins
    ):
        game_coins = await store.sql_list_game_coins()
        get_game_stat = await store.sql_game_stat(game_coins)
        table_data = [
            ['TICKER', 'Available', 'Claimed / Game']
        ]
        for coin_name in [coinItem.upper() for coinItem in faucet_coins]:
            sum_sub = 0
            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name), "usd_equivalent_enable")

            get_deposit = await self.sql_get_userwallet(str(self.bot.user.id), coin_name, net_name, type_coin,
                                                        SERVER_BOT, 0)
            if get_deposit is None:
                get_deposit = await self.sql_register_user(str(self.bot.user.id), coin_name, net_name, type_coin,
                                                           SERVER_BOT, 0, 0)

            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']
            elif type_coin in ["XRP"]:
                wallet_address = get_deposit['destination_tag']

            height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
            try:
                userdata_balance = await self.wallet_api.user_balance(str(self.bot.user.id), coin_name, 
                                                                      wallet_address, type_coin,
                                                                      height, deposit_confirm_depth, SERVER_BOT)
                actual_balance = float(userdata_balance['adjust'])
                sum_sub = float(get_game_stat[coin_name])

                balance_actual = num_format_coin(actual_balance, coin_name, coin_decimal, False)
                get_claimed_count = await store.sql_faucet_sum_count_claimed(coin_name)
                sub_claim = num_format_coin(float(get_claimed_count['claimed']) + sum_sub, coin_name, coin_decimal,
                                            False) if get_claimed_count['count'] > 0 else f"0.00{coin_name}"
                if actual_balance != 0:
                    table_data.append([coin_name, balance_actual, sub_claim])
                else:
                    table_data.append([coin_name, '0', sub_claim])
            except Exception:
                traceback.print_exc(file=sys.stdout)
        table = AsciiTable(table_data)
        table.padding_left = 0
        table.padding_right = 0
        return table.table

    async def take_action(
        self,
        ctx,
        info: str = None
    ):
        await self.bot_log()

        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing /take ...'
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/take", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        faucet_simu = False
        # bot check in the first place
        if ctx.author.bot is True:
            if self.enable_logchan:
                await self.botLogChan.send(
                    f'{ctx.author.name} / {ctx.author.id} (Bot) using **take** {ctx.guild.name} / {ctx.guild.id}')
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, Bot is not allowed using this."
            await ctx.edit_original_message(content=msg)
            return

        if ctx.author.id in self.bot.TX_IN_PROCESS:
            msg = f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
            await ctx.edit_original_message(content=msg)
            return

        if not hasattr(ctx.guild, "id"):
            msg = f'{ctx.author.mention}, you can invite me to your guild with `/invite`\'s link and execute `/take`. `/take` is not available in Direct Message.'
            await ctx.edit_original_message(content=msg)
            return

        coin_name = random.choice(self.bot.faucet_coins)
        if info and info.upper() != "INFO":
            coin_name = info.upper()
            if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
                coin_name = self.bot.coin_alias_names[coin_name]
            if not hasattr(self.bot.coin_list, coin_name):
                msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
                await ctx.edit_original_message(content=msg)
                return
            elif coin_name not in self.bot.faucet_coins:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, {coin_name} not available for `/take`."
                await ctx.edit_original_message(content=msg)
                return

        total_claimed = '{:,.0f}'.format(await store.sql_faucet_count_all())
        if info and info.upper() == "INFO":
            remaining = await self.bot_faucet(ctx, self.bot.faucet_coins) or ''
            msg = f'{ctx.author.mention} /take balance:\n```{remaining}```Total user claims: **{total_claimed}** times. Tip me if you want to feed these faucets. Use /claim to vote TipBot and get reward.'
            await ctx.edit_original_message(content=msg)
            return

        claim_interval = config.faucet.interval
        half_claim_interval = int(config.faucet.interval / 2)

        serverinfo = None
        extra_take_text = ""
        try:
            # check if bot channel is set:
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if serverinfo and serverinfo['botchan'] and ctx.channel.id != int(serverinfo['botchan']):
                try:
                    botChan = self.bot.get_channel(int(serverinfo['botchan']))
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, {botChan.mention} is the bot channel!!!'
                    await ctx.edit_original_message(content=msg)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                # add penalty:
                try:
                    faucet_penalty = await store.sql_faucet_penalty_checkuser(str(ctx.author.id), True, SERVER_BOT)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                return
            if serverinfo and serverinfo['enable_faucet'] == "NO":
                if self.enable_logchan:
                    await self.botLogChan.send(
                        f'{ctx.author.name} / {ctx.author.id} tried **take** in {ctx.guild.name} / {ctx.guild.id} which is disable.')
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, **/take** in this guild is disable."
                await ctx.edit_original_message(content=msg)
                return
            elif serverinfo and serverinfo['enable_faucet'] == "YES" and serverinfo['faucet_channel'] is not None and \
                    serverinfo['faucet_coin'] is not None:
                extra_take_text = " Additional reward:\n\n⚆ You can also do /faucet in <#{}> which funded by the guild.".format(
                    serverinfo['faucet_channel'])
                if serverinfo['vote_reward_amount'] and serverinfo['vote_reward_channel']:
                    vote_reward_coin = serverinfo['vote_reward_coin']
                    vote_coin_decimal = getattr(getattr(self.bot.coin_list, vote_reward_coin), "decimal")
                    vote_reward_amount = num_format_coin(serverinfo['vote_reward_amount'], vote_reward_coin,
                                                         vote_coin_decimal, False)

                    extra_take_text += "\n⚆ Vote {} at top.gg <https://top.gg/servers/{}/vote> for {} {} each time.".format(
                        ctx.guild.name, ctx.guild.id, vote_reward_amount, serverinfo['vote_reward_coin'])
                if serverinfo['rt_reward_amount'] and serverinfo['rt_reward_coin'] and serverinfo[
                    'rt_end_timestamp'] and serverinfo['rt_end_timestamp'] - 600 > int(time.time()) and serverinfo[
                    'rt_link']:
                    # Some RT with reward still going
                    tweet_link = serverinfo['rt_link']
                    rt_reward_coin = serverinfo['rt_reward_coin']
                    rt_coin_decimal = getattr(getattr(self.bot.coin_list, rt_reward_coin), "decimal")
                    time_left = serverinfo['rt_end_timestamp'] - int(time.time()) - 600  # reserved.
                    rt_amount = num_format_coin(serverinfo['rt_reward_amount'], rt_reward_coin, rt_coin_decimal, False)

                    def seconds_str_days(time: float):
                        day = time // (24 * 3600)
                        time = time % (24 * 3600)
                        hour = time // 3600
                        time %= 3600
                        minutes = time // 60
                        time %= 60
                        seconds = time
                        return "{:02d} day(s) {:02d}:{:02d}:{:02d}".format(day, hour, minutes, seconds)

                    if time_left > 0:
                        extra_take_text += f"\n⚆ RT <{tweet_link}> and get {rt_amount} {rt_reward_coin} (Be sure you verified your twitter with TipBot <https://www.youtube.com/watch?v=q79_1M0_Hsw>). Time left `{seconds_str_days(time_left)}`."
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # end of bot channel check

        # check user claim:
        try:
            if info is None:
                check_claimed = await store.sql_faucet_checkuser(str(ctx.author.id), SERVER_BOT)
                if check_claimed is not None:
                    if int(time.time()) - check_claimed['claimed_at'] <= claim_interval * 3600:
                        time_waiting = seconds_str(
                            claim_interval * 3600 - int(time.time()) + check_claimed['claimed_at'])
                        user_claims = await store.sql_faucet_count_user(str(ctx.author.id))
                        number_user_claimed = '{:,.0f}'.format(user_claims)
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you just claimed within last {claim_interval}h. Waiting time {time_waiting} for next **take**. Total user claims: **{total_claimed}** times. You have claimed: **{number_user_claimed}** time(s). Tip me if you want to feed these faucets. Use /claim to vote TipBot and get reward.{extra_take_text}'
                        await ctx.edit_original_message(content=msg)
                        return
        except Exception:
            traceback.print_exc(file=sys.stdout)

        # check if account locked
        account_lock = await alert_if_userlock(ctx, 'take')
        if account_lock:
            msg = f"{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}"
            await ctx.edit_original_message(content=msg)
            return
        # end of check if account locked

        # check if user create account less than 3 days
        try:
            account_created = ctx.author.created_at
            if (datetime.utcnow().astimezone() - account_created).total_seconds() <= config.faucet.account_age_to_claim:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using /take. Alternatively, vote for TipBot to get reward `/claim`.{extra_take_text}"
                await ctx.edit_original_message(content=msg)
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            # check penalty:
            try:
                faucet_penalty = await store.sql_faucet_penalty_checkuser(str(ctx.author.id), False, SERVER_BOT)
                if faucet_penalty and not info:
                    if half_claim_interval * 3600 - int(time.time()) + int(faucet_penalty['penalty_at']) > 0:
                        time_waiting = seconds_str(
                            half_claim_interval * 3600 - int(time.time()) + int(faucet_penalty['penalty_at']))
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention} You claimed in a wrong channel within last {str(half_claim_interval)}h. Waiting time {time_waiting} for next **take** and be sure to be the right channel set by the guild. Use /claim to vote TipBot and get reward.{extra_take_text}'
                        await ctx.edit_original_message(content=msg)
                        return
            except Exception:
                traceback.print_exc(file=sys.stdout)
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
            return

        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name), "usd_equivalent_enable")
        contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")

        get_deposit = await self.sql_get_userwallet(str(self.bot.user.id), coin_name, net_name, type_coin, SERVER_BOT,
                                                    0)
        if get_deposit is None:
            get_deposit = await self.sql_register_user(str(self.bot.user.id), coin_name, net_name, type_coin,
                                                       SERVER_BOT, 0, 0)

        wallet_address = get_deposit['balance_wallet_address']
        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
            wallet_address = get_deposit['paymentid']
        elif type_coin in ["XRP"]:
            wallet_address = get_deposit['destination_tag']

        height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
        userdata_balance = await self.wallet_api.user_balance(str(self.bot.user.id), coin_name, 
                                                              wallet_address, type_coin, height,
                                                              deposit_confirm_depth, SERVER_BOT)
        actual_balance = float(userdata_balance['adjust'])

        amount = random.uniform(getattr(getattr(self.bot.coin_list, coin_name), "faucet_min"),
                                getattr(getattr(self.bot.coin_list, coin_name), "faucet_max"))
        trunc_num = 4
        if coin_decimal >= 8:
            trunc_num = 8
        elif coin_decimal >= 4:
            trunc_num = 4
        elif coin_decimal >= 2:
            trunc_num = 2
        else:
            trunc_num = 6
        amount = truncate(float(amount), trunc_num)
        if amount == 0:
            amount_msg_zero = 'Get 0 random amount requested faucet by: {}#{} for coin {}'.format(ctx.author.name,
                                                                                                  ctx.author.discriminator,
                                                                                                  coin_name)
            await logchanbot(amount_msg_zero)
            return

        if amount > actual_balance and not info:
            msg = f'{ctx.author.mention} Please try again later. Bot runs out of **{coin_name}**'
            await ctx.edit_original_message(content=msg)
            return

        tip = None
        if ctx.author.id not in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.append(ctx.author.id)
        else:
            msg = f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
            await ctx.edit_original_message(content=msg)
            return
        try:
            if not info:
                amount_in_usd = 0.0
                if usd_equivalent_enable == 1:
                    native_token_name = getattr(getattr(self.bot.coin_list, coin_name), "native_token_name")
                    coin_name_for_price = coin_name
                    if native_token_name:
                        coin_name_for_price = native_token_name
                    if coin_name_for_price in self.bot.token_hints:
                        id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                        per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                    else:
                        per_unit = self.bot.coin_paprika_symbol_list[coin_name_for_price]['price_usd']
                    if per_unit and per_unit > 0:
                        amount_in_usd = float(Decimal(per_unit) * Decimal(amount))

                try:
                    key_coin = str(self.bot.user.id) + "_" + coin_name + "_" + SERVER_BOT
                    if key_coin in self.bot.user_balance_cache:
                        del self.bot.user_balance_cache[key_coin]

                    key_coin = str(ctx.author.id) + "_" + coin_name + "_" + SERVER_BOT
                    if key_coin in self.bot.user_balance_cache:
                        del self.bot.user_balance_cache[key_coin]
                except Exception:
                    pass

                tip = await store.sql_user_balance_mv_single(str(self.bot.user.id), str(ctx.author.id),
                                                             str(ctx.guild.id), str(ctx.channel.id), amount, coin_name,
                                                             "FAUCET", coin_decimal, SERVER_BOT, contract,
                                                             amount_in_usd, None)
                try:
                    faucet_add = await store.sql_faucet_add(str(ctx.author.id), str(ctx.guild.id), coin_name, amount,
                                                            coin_decimal, SERVER_BOT)
                    msg = f'{EMOJI_MONEYFACE} {ctx.author.mention}, you got a random `/take` {num_format_coin(amount, coin_name, coin_decimal, False)} {coin_name}. Use /claim to vote TipBot and get reward.{extra_take_text}'
                    await ctx.edit_original_message(content=msg)
                    await logchanbot(
                        f'[Discord] User {ctx.author.name}#{ctx.author.discriminator} claimed faucet {num_format_coin(amount, coin_name, coin_decimal, False)} {coin_name} in guild {ctx.guild.name}/{ctx.guild.id}')
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot("wallet /take_action " + str(traceback.format_exc()))
            else:
                try:
                    msg = f"Simulated faucet {num_format_coin(amount, coin_name, coin_decimal, False)} {coin_name}. This is a test only. Use without **ticker** to do real faucet claim. Use /claim to vote TipBot and get reward."
                    await ctx.edit_original_message(content=msg)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot("wallet /take_action " + str(traceback.format_exc()))
                self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet /take_action " + str(traceback.format_exc()))
        self.bot.TX_IN_PROCESS.remove(ctx.author.id)

    @commands.slash_command(usage="take <info>",
                            options=[
                                Option('info', 'info', OptionType.string, required=False)
                            ],
                            description="Claim a random coin faucet.")
    async def take(
        self,
        ctx,
        info: str = None
    ):
        await self.take_action(ctx, info)

    # End of Faucet

    # Donate
    @commands.slash_command(
        usage='donate',
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('token', 'token', OptionType.string, required=True)
        ],
        description="Donate to TipBot's dev team"
    )
    async def donate(
        self,
        ctx,
        amount: str,
        token: str

    ):
        coin_name = token.upper()
        # Token name check
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
            await ctx.response.send_message(msg)
            return
        else:
            if getattr(getattr(self.bot.coin_list, coin_name), "enable_tip") != 1:
                msg = f'{ctx.author.mention}, **{coin_name}** tipping is disable.'
                await ctx.response.send_message(msg)
                return
        # End token name check
        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
        token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")

        min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
        max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
        usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name), "usd_equivalent_enable")

        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing donation check...'
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/donate", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        get_deposit = await self.wallet_api.sql_get_userwallet(str(ctx.author.id), coin_name, net_name, type_coin,
                                                               SERVER_BOT, 0)
        if get_deposit is None:
            get_deposit = await self.wallet_api.sql_register_user(str(ctx.author.id), coin_name, net_name, type_coin,
                                                                  SERVER_BOT, 0, 0)

        wallet_address = get_deposit['balance_wallet_address']
        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
            wallet_address = get_deposit['paymentid']
        elif type_coin in ["XRP"]:
            wallet_address = get_deposit['destination_tag']
                    
        # Check if tx in progress
        if ctx.author.id in self.bot.TX_IN_PROCESS:
            msg = f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
            await ctx.edit_original_message(content=msg)
            return

        height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
        # check if amount is all
        all_amount = False
        if not amount.isdigit() and amount.upper() == "ALL":
            all_amount = True
            userdata_balance = await self.wallet_api.user_balance(str(ctx.author.id), coin_name, wallet_address, type_coin, height,
                                                                  deposit_confirm_depth, SERVER_BOT)
            amount = float(userdata_balance['adjust'])
        # If $ is in amount, let's convert to coin/token
        elif "$" in amount[-1] or "$" in amount[0]:  # last is $
            # Check if conversion is allowed for this coin.
            amount = amount.replace(",", "").replace("$", "")
            if usd_equivalent_enable == 0:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{coin_name}`."
                await ctx.edit_original_message(content=msg)
                return
            else:
                native_token_name = getattr(getattr(self.bot.coin_list, coin_name), "native_token_name")
                coin_name_for_price = coin_name
                if native_token_name:
                    coin_name_for_price = native_token_name
                per_unit = None
                if coin_name_for_price in self.bot.token_hints:
                    id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                    per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                else:
                    per_unit = self.bot.coin_paprika_symbol_list[coin_name_for_price]['price_usd']
                if per_unit and per_unit > 0:
                    amount = float(Decimal(amount) / Decimal(per_unit))
                else:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. Try with different method.'
                    await ctx.edit_original_message(content=msg)
                    return
        else:
            amount = amount.replace(",", "")
            amount = text_to_num(amount)
            if amount is None:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount.'
                await ctx.edit_original_message(content=msg)
                return
        # end of check if amount is all
        userdata_balance = await self.wallet_api.user_balance(str(ctx.author.id), coin_name, wallet_address, type_coin, height,
                                                              deposit_confirm_depth, SERVER_BOT)
        actual_balance = float(userdata_balance['adjust'])
        donate_factor = 100
        if amount <= 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}.'
            await ctx.edit_original_message(content=msg)
            return
        elif amount > max_tip * donate_factor or amount < min_tip / donate_factor:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, transactions (donate) cannot be bigger than **{num_format_coin(max_tip * donate_factor, coin_name, coin_decimal, False)} {token_display}** or smaller than **{num_format_coin(min_tip / donate_factor, coin_name, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return
        elif amount > actual_balance:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to donate **{num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}**.'
            await ctx.edit_original_message(content=msg)
            return

        # check queue
        if ctx.author.id in self.bot.TX_IN_PROCESS:
            msg = f'{EMOJI_ERROR} {ctx.author.mention} {EMOJI_HOURGLASS_NOT_DONE} You have another tx in progress.'
            await ctx.edit_original_message(content=msg)
            return

        equivalent_usd = ""
        amount_in_usd = 0.0
        if usd_equivalent_enable == 1:
            native_token_name = getattr(getattr(self.bot.coin_list, coin_name), "native_token_name")
            coin_name_for_price = coin_name
            if native_token_name:
                coin_name_for_price = native_token_name
            if coin_name_for_price in self.bot.token_hints:
                id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
            else:
                per_unit = self.bot.coin_paprika_symbol_list[coin_name_for_price]['price_usd']
            if per_unit and per_unit > 0:
                amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                if amount_in_usd > 0.0001:
                    equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)
        if ctx.author.id not in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.append(ctx.author.id)
            try:
                try:
                    key_coin = str(ctx.author.id) + "_" + coin_name + "_" + SERVER_BOT
                    if key_coin in self.bot.user_balance_cache:
                        del self.bot.user_balance_cache[key_coin]

                    key_coin = str(self.donate_to) + "_" + coin_name + "_" + SERVER_BOT
                    if key_coin in self.bot.user_balance_cache:
                        del self.bot.user_balance_cache[key_coin]
                except Exception:
                    pass

                donate = await store.sql_user_balance_mv_single(str(ctx.author.id), str(self.donate_to), "DONATE",
                                                                "DONATE", amount, coin_name, "DONATE", coin_decimal,
                                                                SERVER_BOT, contract, amount_in_usd, None)
                if donate:
                    msg = f'{ctx.author.mention}, thank you for donate {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.'
                    await ctx.edit_original_message(content=msg)
                    await logchanbot(
                        f'[DONATE] A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} donated {num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}{equivalent_usd}.')
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot("wallet /donate " + str(traceback.format_exc()))
            self.bot.TX_IN_PROCESS.remove(ctx.author.id)
        else:
            msg = f'{EMOJI_ERROR} {ctx.author.mention} {EMOJI_HOURGLASS_NOT_DONE}, you have another tx in progress.'
            await ctx.edit_original_message(content=msg)

    # End of Donate

    # Swap Tokens
    @commands.slash_command(description="Swap supporting tokens")
    async def swaptokens(self, ctx):
        pass

    @swaptokens.sub_command(
        usage="swaptokens disclaimer",
        description="Show /swaptokens's disclaimer."
    )
    async def disclaimer(
        self,
        ctx
    ):
        msg = f"""{EMOJI_INFORMATION} Disclaimer: No warranty or guarantee is provided, expressed, or implied \
when using this bot and any funds lost, mis-used or stolen in using this bot. TipBot and its dev does not affiliate with the swapped tokens."""
        await ctx.response.send_message(msg)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/swaptokens disclaimer", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @swaptokens.sub_command(
        usage="swaptokens lists",
        description="Show /swaptokens's supported list."
    )
    async def lists(
        self,
        ctx
    ):
        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, checking /swaptokens lists...'
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/swaptokens lists", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        get_swap_list = await self.swaptoken_list()
        if len(get_swap_list) > 0:
            embed = disnake.Embed(title="/swaptokens lists", timestamp=datetime.now())
            for each in get_swap_list:
                # embed.add_field(name="{}->{} | Ratio: {:,.2f} : {:,.2f}".format(each['from_token'], each['to_token'], each['amount_from'], each['amount_to']), value="```Max. allowed 24h: {} {}\nMax. allowed 24h/user: {} {}\nFee: {:,.0f}{}```".format(each['max_swap_per_24h_from_token_total'], each['from_token'], each['max_swap_per_24h_from_token_user'], each['from_token'], each['fee_percent_from'], "%"), inline=False)
                embed.add_field(name="{}->{} | Ratio: {:,.2f} : {:,.2f}".format(each['from_token'], each['to_token'],
                                                                                each['amount_from'], each['amount_to']),
                                value="```Fee: {:,.0f}{}```".format(each['fee_percent_from'], "%"), inline=False)
            embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
            await ctx.edit_original_message(content=None, embed=embed)
        else:
            msg = f'{EMOJI_ERROR} {ctx.author.mention}, there is no supported token yet. Check again later!'
            await ctx.edit_original_message(content=msg)

    @swaptokens.sub_command(
        usage="swaptokens purchase",
        options=[
            Option('from_amount', 'from_amount', OptionType.string, required=True),
            Option('from_token', 'from_token', OptionType.string, required=True),
            Option('to_token', 'to_token', OptionType.string, required=True)
        ],
        description="Swap tokens / purchase"
    )
    async def purchase(
        self,
        ctx,
        from_amount: str,
        from_token: str,
        to_token: str
    ):
        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, checking /swaptokens purchase...'
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/swaptokens purchase", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        FROM_COIN = from_token.upper()
        TO_COIN = to_token.upper()
        # Check if available
        check_list = await self.swaptoken_check(FROM_COIN, TO_COIN)
        if check_list is None:
            msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, {FROM_COIN} to {TO_COIN} is not available. Please check with `/swaptokens lists`.'
            await ctx.edit_original_message(content=msg)
            return
        else:
            try:
                creditor = check_list['account_creditor']
                amount = from_amount.replace(",", "")
                amount = text_to_num(amount)
                if amount is None:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given from amount.'
                    await ctx.edit_original_message(content=msg)
                else:
                    if amount <= 0:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given from amount.'
                        await ctx.edit_original_message(content=msg)
                        return

                # Check balance user first
                net_name = getattr(getattr(self.bot.coin_list, FROM_COIN), "net_name")
                type_coin = getattr(getattr(self.bot.coin_list, FROM_COIN), "type")
                get_deposit = await self.wallet_api.sql_get_userwallet(str(ctx.author.id), FROM_COIN, net_name,
                                                                       type_coin, SERVER_BOT, 0)
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, FROM_COIN), "deposit_confirm_depth")
                min_tip = getattr(getattr(self.bot.coin_list, FROM_COIN), "real_min_tip")
                max_tip = getattr(getattr(self.bot.coin_list, FROM_COIN), "real_max_tip")
                coin_decimal = getattr(getattr(self.bot.coin_list, FROM_COIN), "decimal")
                token_display = getattr(getattr(self.bot.coin_list, FROM_COIN), "display_name")
                amount = float(amount)
                if amount < min_tip or amount > max_tip:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, amount must be between {min_tip} {FROM_COIN} and {max_tip} {FROM_COIN}.'
                    await ctx.edit_original_message(content=msg)
                    return
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(str(ctx.author.id), FROM_COIN, net_name,
                                                                          type_coin, SERVER_BOT, 0,
                                                                          1 if check_list['is_guild'] == 1 else 0)
                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']
                elif type_coin in ["XRP"]:
                    wallet_address = get_deposit['destination_tag']
                height = self.wallet_api.get_block_height(type_coin, FROM_COIN, net_name)
                userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), FROM_COIN, wallet_address,
                                                                       type_coin, height, deposit_confirm_depth,
                                                                       SERVER_BOT)
                actual_balance = float(userdata_balance['adjust'])
                if actual_balance < amount:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to /swaptokens **{num_format_coin(amount, FROM_COIN, coin_decimal, False)} {token_display}**. Having {num_format_coin(actual_balance, FROM_COIN, coin_decimal, False)} {token_display}.'
                    await ctx.edit_original_message(content=msg)
                    return

                # Check TO_COIN balance creditor
                amount_swapped = amount * check_list['amount_to'] / check_list['amount_from']
                net_name = getattr(getattr(self.bot.coin_list, TO_COIN), "net_name")
                type_coin = getattr(getattr(self.bot.coin_list, TO_COIN), "type")
                get_deposit = await self.wallet_api.sql_get_userwallet(creditor, TO_COIN, net_name, type_coin,
                                                                       SERVER_BOT, 0)
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, TO_COIN), "deposit_confirm_depth")
                coin_decimal = getattr(getattr(self.bot.coin_list, TO_COIN), "decimal")
                token_display = getattr(getattr(self.bot.coin_list, TO_COIN), "display_name")
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(creditor, TO_COIN, net_name, type_coin,
                                                                          SERVER_BOT, 0,
                                                                          1 if check_list['is_guild'] == 1 else 0)
                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']
                elif type_coin in ["XRP"]:
                    wallet_address = get_deposit['destination_tag']
                height = self.wallet_api.get_block_height(type_coin, TO_COIN, net_name)
                creditor_balance = await store.sql_user_balance_single(creditor, TO_COIN, wallet_address, type_coin,
                                                                       height, deposit_confirm_depth, SERVER_BOT)
                actual_balance = float(creditor_balance['adjust'])
                if actual_balance < amount_swapped:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, creditor has insufficient balance to /swaptokens **{num_format_coin(amount_swapped, FROM_COIN, coin_decimal, False)} {token_display}**. Remaining only {num_format_coin(actual_balance, TO_COIN, coin_decimal, False)} {token_display}.'
                    await ctx.edit_original_message(content=msg)
                    try:
                        msg_log = f"[SWAPTOKENS] - A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.id}  /swaptokens failed! Shortage of creditor's balance. Remaining only {num_format_coin(actual_balance, TO_COIN, coin_decimal, False)} {token_display}."
                        await logchanbot(msg_log)
                        if check_list['channel_log'] and check_list['channel_log'].isdigit():
                            self.logchan_swap = self.bot.get_channel(int(check_list['channel_log']))
                            await self.logchan_swap.send(content=msg_log)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    return
                else:
                    # Do swap
                    data_rows = []
                    currentTs = int(time.time())
                    fee_taker = str(config.discord.ownerID)  # "460755304863498250" # str(config.discord.ownerID)
                    # FROM_COIN
                    contract_from = getattr(getattr(self.bot.coin_list, FROM_COIN), "contract")
                    token_decimal_from = getattr(getattr(self.bot.coin_list, FROM_COIN), "decimal")
                    guild_id = str(ctx.guild.id) if hasattr(ctx.guild, "id") else "DM"
                    channel_id = str(ctx.channel.id) if hasattr(ctx.guild, "id") else "DM"
                    tiptype = "SWAPTOKENS"
                    user_server = SERVER_BOT
                    real_amount_usd = 0.0  # Leave it 0
                    extra_message = None
                    amount_after_fee = amount * (1 - check_list['fee_percent_from'] / 100)
                    fee_from = amount * check_list['fee_percent_from'] / 100

                    # Deduct amount from
                    data_rows.append((FROM_COIN, contract_from, str(ctx.author.id), creditor, guild_id, channel_id,
                                      amount_after_fee, token_decimal_from, tiptype, currentTs, user_server,
                                      real_amount_usd, extra_message, str(ctx.author.id), FROM_COIN, user_server,
                                      -amount_after_fee, currentTs, creditor, FROM_COIN, user_server, amount_after_fee,
                                      currentTs,))
                    # Fee to fee_taker
                    if fee_from > 0:
                        data_rows.append((FROM_COIN, contract_from, str(ctx.author.id), fee_taker, guild_id, channel_id,
                                          fee_from, token_decimal_from, tiptype, currentTs, user_server,
                                          real_amount_usd, extra_message, str(ctx.author.id), FROM_COIN, user_server,
                                          -fee_from, currentTs, fee_taker, FROM_COIN, user_server, fee_from,
                                          currentTs,))

                    # Deduct from creditor
                    contract_to = getattr(getattr(self.bot.coin_list, TO_COIN), "contract")
                    token_decimal_to = getattr(getattr(self.bot.coin_list, TO_COIN), "decimal")
                    amount_after_fee = amount_swapped * (1 - check_list['fee_percent_to'] / 100)
                    fee_to = amount_swapped * check_list['fee_percent_to'] / 100
                    data_rows.append((TO_COIN, contract_to, creditor, str(ctx.author.id), guild_id, channel_id,
                                      amount_after_fee, token_decimal_to, tiptype, currentTs, user_server,
                                      real_amount_usd, extra_message, creditor, TO_COIN, user_server, -amount_after_fee,
                                      currentTs, str(ctx.author.id), TO_COIN, user_server, amount_after_fee,
                                      currentTs,))
                    # Fee to fee_taker
                    if fee_to > 0:
                        data_rows.append((TO_COIN, contract_to, creditor, fee_taker, guild_id, channel_id, fee_to,
                                          token_decimal_to, tiptype, currentTs, user_server, real_amount_usd,
                                          extra_message, creditor, TO_COIN, user_server, -fee_to, currentTs, fee_taker,
                                          TO_COIN, user_server, fee_to, currentTs,))

                    swap = await self.swaptoken_purchase(data_rows)
                    if swap > 0:
                        # If there is a log channel for this.
                        try:
                            msg_log = f"[SWAPTOKENS] - A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.id}  /swaptokens successfully from {num_format_coin(amount, FROM_COIN, token_decimal_from, False)} {FROM_COIN} to {num_format_coin(amount_swapped, TO_COIN, token_decimal_to, False)} {TO_COIN} [Fee: {num_format_coin(fee_to, TO_COIN, token_decimal_to, False)} {TO_COIN}].\nCREDITOR ID: {creditor} NEW BALANCE: {num_format_coin(float(creditor_balance['adjust']) - amount_swapped, TO_COIN, token_decimal_to, False)} {TO_COIN}."
                            await logchanbot(msg_log)
                            if check_list['channel_log'] and check_list['channel_log'].isdigit():
                                self.logchan_swap = self.bot.get_channel(int(check_list['channel_log']))
                                await self.logchan_swap.send(content=msg_log)
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, successfully /swaptokens from **{num_format_coin(amount, FROM_COIN, token_decimal_from, False)} {FROM_COIN}** to **{num_format_coin(amount_swapped, TO_COIN, token_decimal_to, False)}** _{TO_COIN} [Fee: {num_format_coin(fee_to, TO_COIN, token_decimal_to, False)} {TO_COIN}]_. Thanks!'
                        await ctx.edit_original_message(content=msg)
                    else:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, internal error, please report.'
                        await ctx.edit_original_message(content=msg)
            except Exception:
                traceback.print_exc(file=sys.stdout)
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, internal error, please report.'
                await ctx.edit_original_message(content=msg)

    # End of Swap Tokens

    # Swap
    @commands.slash_command(
        usage='swap',
        options=[
            Option('from_amount', 'from_amount', OptionType.string, required=True),
            Option('from_token', 'from_token', OptionType.string, required=True),
            Option('to_token', 'to_token', OptionType.string, required=True)
        ],
        description="Swap between supported token/coin (wrap/unwrap)."
    )
    async def swap(
        self,
        ctx,
        from_amount: str,
        from_token: str,
        to_token: str

    ):
        FROM_COIN = from_token.upper()
        TO_COIN = to_token.upper()
        PAIR_NAME = FROM_COIN + "-" + TO_COIN

        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, checking /swap ...'
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/swap", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        if PAIR_NAME not in self.swap_pair:
            msg = f'{EMOJI_RED_NO}, {ctx.author.mention} `{PAIR_NAME}` is not available.'
            await ctx.edit_original_message(content=msg)
            return
        else:
            amount = from_amount.replace(",", "")
            amount = text_to_num(amount)
            if amount is None:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
                await ctx.edit_original_message(content=msg)
            else:
                if amount <= 0:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
                    await ctx.edit_original_message(content=msg)
                    return

                amount = float(amount)
                to_amount = amount * self.swap_pair[PAIR_NAME]
                net_name = getattr(getattr(self.bot.coin_list, FROM_COIN), "net_name")
                type_coin = getattr(getattr(self.bot.coin_list, FROM_COIN), "type")
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, FROM_COIN), "deposit_confirm_depth")
                coin_decimal = getattr(getattr(self.bot.coin_list, FROM_COIN), "decimal")
                min_tip = getattr(getattr(self.bot.coin_list, FROM_COIN), "real_min_tip")
                max_tip = getattr(getattr(self.bot.coin_list, FROM_COIN), "real_max_tip")
                token_display = getattr(getattr(self.bot.coin_list, FROM_COIN), "display_name")
                contract = getattr(getattr(self.bot.coin_list, FROM_COIN), "contract")
                to_contract = getattr(getattr(self.bot.coin_list, TO_COIN), "contract")
                to_coin_decimal = getattr(getattr(self.bot.coin_list, TO_COIN), "decimal")
                get_deposit = await self.wallet_api.sql_get_userwallet(str(ctx.author.id), FROM_COIN, net_name,
                                                                       type_coin, SERVER_BOT, 0)
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(str(ctx.author.id), FROM_COIN, net_name,
                                                                          type_coin, SERVER_BOT, 0, 0)

                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']
                elif type_coin in ["XRP"]:
                    wallet_address = get_deposit['destination_tag']

                # Check if tx in progress
                if ctx.author.id in self.bot.TX_IN_PROCESS:
                    msg = f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
                    await ctx.edit_original_message(content=msg)
                    return

                height = self.wallet_api.get_block_height(type_coin, FROM_COIN, net_name)
                userdata_balance = await self.wallet_api.user_balance(str(ctx.author.id), FROM_COIN, wallet_address, type_coin,
                                                                      height, deposit_confirm_depth, SERVER_BOT)
                actual_balance = float(userdata_balance['adjust'])

                if amount > max_tip or amount < min_tip:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, swap cannot be bigger than **{num_format_coin(max_tip, FROM_COIN, coin_decimal, False)} {token_display}** or smaller than **{num_format_coin(min_tip, FROM_COIN, coin_decimal, False)} {token_display}**.'
                    await ctx.edit_original_message(content=msg)
                    return
                elif amount > actual_balance:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to swap **{num_format_coin(amount, FROM_COIN, coin_decimal, False)} {token_display}**.'
                    await ctx.edit_original_message(content=msg)
                    return

                try:
                    # test get main balance of TO_COIN
                    balance = await self.wallet_api.get_coin_balance(TO_COIN)
                    if balance / 5 < to_amount:  # We allow 20% to swap
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention} insufficient liquidity to swap **{num_format_coin(amount, FROM_COIN, coin_decimal, False)} {token_display}** to {TO_COIN}. Try lower the amount of `{FROM_COIN}`.'
                        await ctx.edit_original_message(content=msg)
                        await logchanbot(
                            f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} wanted to swap from `{num_format_coin(amount, FROM_COIN, coin_decimal, False)} {FROM_COIN} to {num_format_coin(to_amount, TO_COIN, to_coin_decimal, False)} {TO_COIN}` but shortage of liquidity. Having only `{num_format_coin(balance, TO_COIN, to_coin_decimal, False)} {TO_COIN}`.')
                        return
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot("wallet /swap " + str(traceback.format_exc()))

                if ctx.author.id not in self.bot.TX_IN_PROCESS:
                    self.bot.TX_IN_PROCESS.append(ctx.author.id)
                    try:
                        swap = await self.swap_coin(str(ctx.author.id), FROM_COIN, amount, contract, coin_decimal,
                                                    TO_COIN, to_amount, to_contract, to_coin_decimal, SERVER_BOT)
                        if swap:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, swapped from `{num_format_coin(amount, FROM_COIN, coin_decimal, False)} {FROM_COIN} to {num_format_coin(to_amount, TO_COIN, to_coin_decimal, False)} {TO_COIN}`.'
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f'A user {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} swapped from `{num_format_coin(amount, FROM_COIN, coin_decimal, False)} {FROM_COIN} to {num_format_coin(to_amount, TO_COIN, to_coin_decimal, False)} {TO_COIN}`.')
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot("wallet /swap " + str(traceback.format_exc()))
                    self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                else:
                    msg = f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
                    await ctx.edit_original_message(content=msg)
                    return
    # End of Swap

    @commands.slash_command(
        description="Recent tip or withdraw"
    )
    async def recent(self, ctx):
        pass


    @recent.sub_command(
        name="withdraw",
        usage="recent withdraw <token/coin>", 
        description="Get list recent withdraws"
    )
    async def recent_withdraw(
        self, 
        ctx,
        token: str
    ):
        coin_name = token.upper()
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]

        if not hasattr(self.bot.coin_list, coin_name):
            msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
            await ctx.response.send_message(msg)
            return

        await ctx.response.send_message(f"{EMOJI_HOURGLASS_NOT_DONE}, checking recent withdraw..", ephemeral=True)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/recent withdraw", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        coin_family = getattr(getattr(self.bot.coin_list, coin_name), "type")
        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        try:
            get_recent = await store.recent_tips(str(ctx.author.id), SERVER_BOT, coin_name, coin_family, "withdraw", 10)
            if len(get_recent) == 0:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, you do not have recent withdraw of {coin_name}.")
            else:
                explorer_tx_prefix = getattr(getattr(self.bot.coin_list, coin_name), "explorer_tx_prefix")
                list_tx = []
                for each in get_recent:
                    if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        tx = each['tx_hash']
                        amount = each['amount']
                    elif coin_family == "BTC":
                        tx = each['tx_hash']
                        amount = each['amount']
                    elif coin_family == "NEO":
                        tx = each['tx_hash']
                        amount = each['real_amount']
                    elif coin_family == "NEAR":
                        tx = each['tx_hash']
                        amount = each['real_amount']
                    elif coin_family == "NANO":
                        tx = each['tx_hash']
                        amount = each['amount']
                    elif coin_family == "CHIA":
                        tx = each['tx_hash']
                        amount = each['amount']
                    elif coin_family == "ERC-20":
                        tx = each['txn']
                        amount = each['real_amount']
                    elif coin_family == "XTZ":
                        tx = each['txn']
                        amount = each['real_amount']
                    elif coin_family == "ZIL":
                        tx = each['txn']
                        amount = each['real_amount']
                    elif coin_family == "VET":
                        tx = each['txn']
                        amount = each['real_amount']
                    elif coin_family == "VITE":
                        tx = each['tx_hash']
                        amount = each['amount']
                    elif coin_family == "TRC-20":
                        tx = each['txn']
                        amount = each['real_amount']
                    elif coin_family == "HNT":
                        tx = each['tx_hash']
                        amount = each['amount']
                    elif coin_family == "XRP":
                        tx = each['txid']
                        amount = each['amount']
                    elif coin_family == "XLM":
                        tx = each['tx_hash']
                        amount = each['amount']
                    elif coin_family == "ADA":
                        tx = each['hash_id']
                        amount = each['real_amount']
                    elif coin_family == "SOL" or coin_family == "SPL":
                        tx = each['txn']
                        amount = each['real_amount']
                    if explorer_tx_prefix:
                        tx = "[{}](<{}>)".format(tx[0:12]+"...", explorer_tx_prefix.replace("{tx_hash_here}", tx))
                    list_tx.append("{} {} {}\n{}\n".format(num_format_coin(amount, coin_name, coin_decimal, False), coin_name, disnake.utils.format_dt(each['date'], style='R'), tx))
                list_tx_str = "\n".join(list_tx)
                await ctx.edit_original_message(content=f"{ctx.author.mention}, last withdraw of {coin_name}:\n{list_tx_str}")
        except Exception:
            traceback.print_exc(file=sys.stdout)


    @recent.sub_command(
        name="deposit",
        usage="recent deposit <token/coin>", 
        description="Get list recent withdraws"
    )
    async def recent_deposit(
        self, 
        ctx,
        token: str
    ):
        coin_name = token.upper()
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]

        if not hasattr(self.bot.coin_list, coin_name):
            msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
            await ctx.response.send_message(msg)
            return

        await ctx.response.send_message(f"{EMOJI_HOURGLASS_NOT_DONE}, checking recent deposit..", ephemeral=True)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/recent deposit", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        coin_family = getattr(getattr(self.bot.coin_list, coin_name), "type")
        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        try:
            get_recent = await store.recent_tips(str(ctx.author.id), SERVER_BOT, coin_name, coin_family, "deposit", 10)
            if len(get_recent) == 0:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, you do not have recent deposit of {coin_name}.")
            else:
                explorer_tx_prefix = getattr(getattr(self.bot.coin_list, coin_name), "explorer_tx_prefix")
                list_tx = []
                for each in get_recent:
                    time_insert = each['time_insert']
                    if coin_family in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        amount = each['amount']
                        tx = each['txid']
                    elif coin_family == "BTC":
                        tx = each['txid']
                        amount = each['amount']
                    elif coin_family == "NEO":
                        tx = each['txhash']
                        amount = each['amount']
                    elif coin_family == "NEAR":
                        tx = each['txn']
                        amount = each['amount'] - each['real_deposit_fee']
                    elif coin_family == "NANO":
                        tx = each['block']
                        amount = each['amount']
                    elif coin_family == "CHIA":
                        tx = each['txid']
                        amount = each['amount']
                    elif coin_family == "ERC-20":
                        tx = each['txn']
                        amount = each['real_amount'] - each['real_deposit_fee']
                    elif coin_family == "XTZ":
                        tx = each['txn']
                        amount = each['real_amount'] - each['real_deposit_fee']
                    elif coin_family == "ZIL":
                        tx = each['txn']
                        amount = each['real_amount'] - each['real_deposit_fee']
                    elif coin_family == "VET":
                        tx = each['txn']
                        amount = each['real_amount'] - each['real_deposit_fee']
                    elif coin_family == "VITE":
                        tx = each['txid']
                        amount = each['amount']
                    elif coin_family == "TRC-20":
                        tx = each['txn']
                        amount = each['real_amount'] - each['real_deposit_fee']
                    elif coin_family == "HNT":
                        tx = each['txid']
                        amount = each['amount']
                    elif coin_family == "XRP":
                        tx = each['txid']
                        amount = each['amount']
                    elif coin_family == "XLM":
                        tx = each['txid']
                        amount = each['amount']
                    elif coin_family == "ADA":
                        tx = each['hash_id']
                        amount = each['amount']
                    elif coin_family == "SOL" or coin_family == "SPL":
                        tx = each['txn']
                        amount = each['real_amount'] - each['real_deposit_fee']

                    if explorer_tx_prefix:
                        tx = "[{}](<{}>)".format(tx[0:12]+"...", explorer_tx_prefix.replace("{tx_hash_here}", tx))
                    list_tx.append("{} {} {}\n{}\n".format(num_format_coin(amount, coin_name, coin_decimal, False), coin_name, disnake.utils.format_dt(time_insert, style='R'), tx))
                list_tx_str = "\n".join(list_tx)
                await ctx.edit_original_message(content=f"{ctx.author.mention}, last deposit of {coin_name}:\n{list_tx_str}")
        except Exception:
            traceback.print_exc(file=sys.stdout)


    @recent.sub_command(
        name="receive",
        usage="recent receive <token/coin>", 
        description="Get list recent withdraws"
    )
    async def recent_receive(
        self, 
        ctx,
        token: str
    ):
        coin_name = token.upper()
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]

        if not hasattr(self.bot.coin_list, coin_name):
            msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
            await ctx.response.send_message(msg)
            return

        await ctx.response.send_message(f"{EMOJI_HOURGLASS_NOT_DONE}, checking recent receive..", ephemeral=True)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/recent receive", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        coin_family = getattr(getattr(self.bot.coin_list, coin_name), "type")
        try:
            get_recent = await store.recent_tips(str(ctx.author.id), SERVER_BOT, coin_name, coin_family, "receive", 20)
            if len(get_recent) == 0:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, you do not received any {coin_name}.")
            else:
                list_tx = []
                for each in get_recent:
                    list_tx.append("From `{}` {}, amount {} {} - {}".format(each['from_userid'], disnake.utils.format_dt(each['date'], style='R'), num_format_coin(each['real_amount'], each['token_name'], each['token_decimal'], False), each['token_name'], each['type']))
                list_tx_str = "\n\n".join(list_tx)
                await ctx.edit_original_message(content=f"{ctx.author.mention}, last receive of {coin_name}:\n{list_tx_str}")
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @recent.sub_command(
        name="expense",
        usage="recent expense <token/coin>", 
        description="Get list recent withdraws"
    )
    async def recent_expense(
        self, 
        ctx,
        token: str
    ):
        coin_name = token.upper()
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]

        if not hasattr(self.bot.coin_list, coin_name):
            msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
            await ctx.response.send_message(msg)
            return

        await ctx.response.send_message(f"{EMOJI_HOURGLASS_NOT_DONE}, checking recent expense..", ephemeral=True)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/recent expense", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        coin_family = getattr(getattr(self.bot.coin_list, coin_name), "type")
        try:
            get_recent = await store.recent_tips(str(ctx.author.id), SERVER_BOT, coin_name, coin_family, "expense", 20)
            if len(get_recent) == 0:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, you do not received any {coin_name}.")
            else:
                list_tx = []
                for each in get_recent:
                    list_tx.append("To `{}` {}, amount {} {} - {}".format(each['to_userid'], disnake.utils.format_dt(each['date'], style='R'), num_format_coin(each['real_amount'], each['token_name'], each['token_decimal'], False), each['token_name'], each['type']))
                list_tx_str = "\n\n".join(list_tx)
                await ctx.edit_original_message(content=f"{ctx.author.mention}, last expense of {coin_name}:\n{list_tx_str}")
        except Exception:
            traceback.print_exc(file=sys.stdout)


    async def cog_load(self):
        await self.bot.wait_until_ready()

        self.notify_new_tx_user_noconfirmation.start()
        self.notify_new_tx_user.start()

        # nano, banano
        self.update_balance_nano.start()
        # TRTL-API
        self.update_balance_trtl_api.start()
        # TRTL-SERVICE
        self.update_balance_trtl_service.start()
        # XMR
        self.update_balance_xmr.start()
        # BTC
        self.update_balance_btc.start()

        # NEO
        self.update_balance_neo.start()
        self.notify_new_confirmed_neo.start()

        # CHIA
        self.update_balance_chia.start()
        # ERC-20
        self.update_balance_erc20.start()
        self.unlocked_move_pending_erc20.start()
        self.update_balance_address_history_erc20.start()
        self.notify_new_confirmed_spendable_erc20.start()

        # TRC-20
        self.update_balance_trc20.start()
        self.unlocked_move_pending_trc20.start()
        self.notify_new_confirmed_spendable_trc20.start()

        # HNT
        self.update_balance_hnt.start()
        self.notify_new_confirmed_hnt.start()

        # XLM
        self.update_balance_xlm.start()
        self.notify_new_confirmed_xlm.start()

        # VITE
        self.update_balance_vite.start()
        self.notify_new_confirmed_vite.start()

        # XTZ
        self.update_balance_tezos.start()
        self.check_confirming_tezos.start()
        self.notify_new_confirmed_tezos.start()

        # ZIL
        self.update_balance_zil.start()
        self.check_confirming_zil.start()
        self.notify_new_confirmed_zil.start()

        # VET
        self.update_balance_vet.start()
        self.check_confirming_vet.start()
        self.notify_new_confirmed_vet.start()

        # NEAR
        self.update_balance_near.start()
        self.check_confirming_near.start()
        self.notify_new_confirmed_near.start()

        # XRP
        self.update_balance_xrp.start()
        self.notify_new_confirmed_xrp.start()

        # update ada wallet sync status
        self.update_ada_wallets_sync.start()
        self.notify_new_confirmed_ada.start()

        # update sol wallet sync status
        self.update_sol_wallets_sync.start()
        self.unlocked_move_pending_sol.start()

        # monitoring reward for RT
        self.monitoring_rt_rewards.start()

        # Monitoring Tweet command
        self.monitoring_tweet_command.start()
        self.monitoring_tweet_mentioned_command.start()


    def cog_unload(self):
        # Ensure the task is stopped when the cog is unloaded.
        # nano, banano
        self.update_balance_nano.stop()
        # TRTL-API
        self.update_balance_trtl_api.stop()
        # TRTL-SERVICE
        self.update_balance_trtl_service.stop()
        # XMR
        self.update_balance_xmr.stop()
        # BTC
        self.update_balance_btc.stop()

        # NEO
        self.update_balance_neo.stop()
        self.notify_new_confirmed_neo.stop()

        # CHIA
        self.update_balance_chia.stop()
        # ERC-20
        self.update_balance_erc20.stop()
        self.unlocked_move_pending_erc20.stop()
        self.update_balance_address_history_erc20.stop()
        self.notify_new_confirmed_spendable_erc20.stop()

        # TRC-20
        self.update_balance_trc20.stop()
        self.unlocked_move_pending_trc20.stop()
        self.notify_new_confirmed_spendable_trc20.stop()

        # HNT
        self.update_balance_hnt.stop()
        self.notify_new_confirmed_hnt.stop()

        # XLM
        self.update_balance_xlm.stop()
        self.notify_new_confirmed_xlm.stop()

        # VITE
        self.update_balance_vite.stop()
        self.notify_new_confirmed_vite.stop()

        # XTZ
        self.update_balance_tezos.stop()
        self.check_confirming_tezos.stop()
        self.notify_new_confirmed_tezos.stop()

        # ZIL
        self.update_balance_zil.stop()
        self.check_confirming_zil.stop()
        self.notify_new_confirmed_zil.stop()

        # VET
        self.update_balance_vet.stop()
        self.check_confirming_vet.stop()
        self.notify_new_confirmed_vet.stop()

        # NEAR
        self.update_balance_near.stop()
        self.check_confirming_near.stop()
        self.notify_new_confirmed_near.stop()

        # XRP
        self.update_balance_xrp.stop()
        self.notify_new_confirmed_xrp.stop()

        # update ada wallet sync status
        self.update_ada_wallets_sync.stop()
        self.notify_new_confirmed_ada.stop()

        # update sol wallet sync status
        self.update_sol_wallets_sync.stop()
        self.unlocked_move_pending_sol.stop()

        # monitoring reward for RT
        self.monitoring_rt_rewards.stop()

        # Monitoring Tweet command
        self.monitoring_tweet_command.stop()
        self.monitoring_tweet_mentioned_command.stop()


def setup(bot):
    bot.add_cog(Wallet(bot))
    bot.add_cog(WalletAPI(bot))
