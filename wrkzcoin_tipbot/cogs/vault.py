import sys, os
import traceback
from datetime import datetime
import time
import json
import asyncio, aiohttp
from typing import Optional
from pathlib import Path
import functools

from Bot import encrypt_string, decrypt_string, log_to_channel, SERVER_BOT, EMOJI_RED_NO, EMOJI_INFORMATION
from cogs.utils import Utils
from cogs.wallet import WalletAPI
import disnake
from disnake.app_commands import Option
from disnake.enums import OptionType
from disnake.enums import ButtonStyle
from disnake import TextInputStyle
from disnake.ext import commands, tasks
from eth_account import Account

from web3 import Web3
from web3.middleware import geth_poa_middleware

Account.enable_unaudited_hdwallet_features()

# wallet thing
from pywallet import wallet as ethwallet

import store
from cogs.utils import Utils, num_format_coin, gen_password
from cogs.wallet import WalletAPI


def create_address_eth():
    seed = ethwallet.generate_mnemonic()
    w = ethwallet.create_wallet(network="ETH", seed=seed, children=1)
    return w

async def http_wallet_getbalance(
    url: str, address: str, contract: str, time_out: int = 15
):
    if contract is None:
        data = '{"jsonrpc":"2.0","method":"eth_getBalance","params":["' + address + '", "latest"],"id":1}'
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
                async with session.post(
                    url,
                    headers={'Content-Type': 'application/json'},
                    json=json.loads(data),
                    timeout=time_out
                ) as response:
                    if response.status == 200:
                        data = await response.read()
                        try:
                            data = data.decode('utf-8')
                            decoded_data = json.loads(data)
                            if decoded_data and 'result' in decoded_data:
                                return int(decoded_data['result'], 16)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
        except asyncio.TimeoutError:
            print('TIMEOUT: get balance {} for {}s'.format(url, time_out))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    else:
        data = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [
                {
                    "to": contract,
                    "data": "0x70a08231000000000000000000000000" + address[2:]
                }, "latest"
            ],
            "id": 1
        }
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
                async with session.post(
                    url, headers={'Content-Type': 'application/json'},
                    json=data,
                    timeout=time_out
                ) as response:
                    if response.status == 200:
                        data = await response.read()
                        data = data.decode('utf-8')
                        decoded_data = json.loads(data)
                        if decoded_data and 'result' in decoded_data:
                            if decoded_data['result'] == "0x":
                                return 0
                            return int(decoded_data['result'], 16)
        except aiohttp.client_exceptions.ServerDisconnectedError:
            print("http_wallet_getbalance disconnected from url: {} for contract {}".format(url, contract))
        except asyncio.TimeoutError:
            print('TIMEOUT: get balance {} for {}s'.format(url, time_out))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    return None

async def estimate_gas_amount_send_all(
    url: str, from_address: str, to_address: str
):
    # should return gas and amount
    try:
        # get balance
        get_balance = await http_wallet_getbalance(
            url, from_address, None, 5
        )
        if get_balance is None:
            return None

        # HTTPProvider:
        w3 = Web3(Web3.HTTPProvider(url))
        # inject the poa compatibility middleware to the innermost layer
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        # get gas price
        gasPrice = w3.eth.gasPrice
        estimateGas = w3.eth.estimateGas(
            {
                'to': w3.toChecksumAddress(to_address),
                'from': w3.toChecksumAddress(from_address),
                'value': get_balance # atomic already
            }
        )
        est_gas_amount = gasPrice * estimateGas # atomic
        return {
            "gas_price": w3.eth.gasPrice,
            "estimate_gas": estimateGas,
            "gas_amount": est_gas_amount,
            "remaining": get_balance - est_gas_amount
        }
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None
    
def send_erc_token(
    url: str, chainId: str, from_address: str, seed: str,
    to_address: str, float_balance: float, float_amount: float, coin_decimal: int,
    gas: dict=None
):
    try:
        # HTTPProvider:
        w3 = Web3(Web3.HTTPProvider(url))
        # inject the poa compatibility middleware to the innermost layer
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(from_address))

        if gas is None:
            # get gas price
            gasPrice = w3.eth.gasPrice
            estimateGas = w3.eth.estimateGas(
                {
                    'to': w3.toChecksumAddress(to_address),
                    'from': w3.toChecksumAddress(from_address),
                    'value': int(float_amount * 10 ** coin_decimal)
                }
            )

            est_gas_amount = gasPrice * estimateGas # atomic
            if est_gas_amount > (float_balance - float_amount)*10**coin_decimal:
                return {
                    "success": False,
                    "msg": "You don't have sufficient gas remaining.",
                    "tx": None
                }
        else:
            gasPrice = gas['gasPrice']
            estimateGas = gas['estimateGas']
        transaction = {
            'from': w3.toChecksumAddress(from_address),
            'to': w3.toChecksumAddress(to_address),
            'value': int(float_amount*10**coin_decimal),
            'nonce': nonce,
            'gasPrice': gasPrice,
            'gas': estimateGas,
            'chainId': chainId
        }
        acct = Account.from_mnemonic(mnemonic=decrypt_string(seed))
        signed = w3.eth.account.sign_transaction(transaction, private_key=acct.key)
        # send Transaction:
        send_gas_tx = w3.eth.sendRawTransaction(signed.rawTransaction)
        tx_receipt = w3.eth.waitForTransactionReceipt(send_gas_tx)
        # return tx_receipt.transactionHash.hex() # hash Tx
        return {
            "success": True,
            "msg": "You sent transaction to network tx hash: {}".format(tx_receipt.transactionHash.hex()),
            "tx": tx_receipt.transactionHash.hex(),
            "others": str(tx_receipt)
        }
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return {
        "success": False,
        "msg": "Internal error. Please report",
        "tx": None
    }

async def bnc_get_balance(
    coin_name: str, wallet_api_url: str,
    header: str, address: str, timeout: int=30
):
    try:
        if coin_name in ["WRKZ", "DEGO"]:
            headers = {
                'X-API-KEY': header,
                'Content-Type': 'application/json'
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    wallet_api_url + "/balance/" + address,
                    headers=headers,
                    timeout=timeout
                ) as response:
                    if response.status == 200:
                        json_resp = await response.json()
                        return json_resp
                    else:
                        print(f"internal error during get address wallet {coin_name}")
        elif coin_name in ["WOW", "XMR"]:
            headers = {
                'Content-Type': 'application/json'
            }
            json_data = {
                "jsonrpc":"2.0",
                "id":"0",
                "method":"get_balance",
                "params":{
                    "account_index": 0
                }
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    wallet_api_url + "/json_rpc",
                    headers=headers,
                    json=json_data,
                    timeout=timeout
                ) as response:
                    if response.status == 200:
                        json_resp = await response.json()
                        return json_resp
                    else:
                        print(f"internal error during get balance wallet {coin_name}")
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

# for WRKZ, DEGO
async def bcn_delete_address(
    coin_name: str, address: str, wallet_api_url: str, header: str, timeout: int=60
):
    try:
        if coin_name in ["WRKZ", "DEGO"]:
            headers = {
                'X-API-KEY': header,
                'Content-Type': 'application/json'
            }
            method = "/addresses/" + address
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    wallet_api_url + method,
                    headers=headers,
                    timeout=timeout
                ) as response:
                    if response.status == 200 or response.status == 201:
                        try:
                            # call save wallet
                            async with session.put(
                                wallet_api_url + "/save",
                                headers=headers,
                                timeout=timeout
                            ) as save_resp:
                                if save_resp.status != 200:
                                    print(f"internal error during save wallet {coin_name}")
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                        return True
                    else:
                        print(f"internal error during sending transaction of wallet {coin_name}")
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def bcn_send_external(
    coin_name: str, source_address: str, ex_address: str, paymentId: str,
    atomic_amount: int, wallet_api_url: str, header: str, send_all: bool=False, timeout: int=60      
):
    try:
        if coin_name in ["WRKZ", "DEGO"]:
            headers = {
                'X-API-KEY': header,
                'Content-Type': 'application/json'
            }
            json_data = {
                "destinations": [{"address": ex_address, "amount": atomic_amount}],
                "sourceAddresses": [
                    source_address
                ],
                "paymentID": paymentId if paymentId else "",
                "changeAddress": source_address
            }
            method = "/transactions/send/advanced"
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    wallet_api_url + method,
                    headers=headers,
                    json=json_data,
                    timeout=timeout
                ) as response:
                    json_resp = await response.json()
                    if response.status == 200 or response.status == 201:
                        return json_resp
                    else:
                        print(f"internal error during sending transaction of wallet {coin_name}")
        elif coin_name in ["WOW", "XMR"]:
            try:
                if send_all is False:
                    acc_index = 0
                    payload = {
                        "destinations": [{'amount': int(atomic_amount), 'address': ex_address}],
                        "account_index": acc_index,
                        "subaddr_indices": [],
                        "priority": 1,
                        "unlock_time": 0,
                        "get_tx_key": True,
                        "get_tx_hex": False,
                        "get_tx_metadata": False
                    }
                    full_payload = {
                        'params': payload,
                        'jsonrpc': '2.0',
                        'id': 0,
                        'method': "transfer"
                    }
                else:
                    payload = {
                        "address": ex_address,
                        "priority": 1,
                        "unlock_time": 0,
                        "get_tx_key": True,
                        "get_tx_hex": False,
                        "get_tx_metadata": False
                    }
                    full_payload = {
                        'params': payload,
                        'jsonrpc': '2.0',
                        'id': 0,
                        'method': "sweep_all"
                    }
                async with aiohttp.ClientSession(headers={'Content-Type': 'application/json'}) as session:
                    async with session.post(
                        wallet_api_url + "/json_rpc",
                        json=full_payload,
                        timeout=timeout
                    ) as response:
                        # sometimes => "message": "Not enough unlocked money" for checking fee
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            decoded_data = json.loads(res_data)
                            if 'result' in decoded_data:
                                return decoded_data['result']
                            else:
                                return None
            except asyncio.TimeoutError:
                print('TIMEOUT: {} coin_name {} - timeout {}'.format("transfer", coin_name, timeout))
            except Exception:
                traceback.print_exc(file=sys.stdout)
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def find_user_by_id(user_id: str, user_server: str):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT * FROM `bot_users` WHERE `user_id`=%s AND `user_server`=%s LIMIT 1
                """
                await cur.execute(sql, (user_id, user_server))
                result = await cur.fetchone()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def bcn_open_wallet(
    wallet_api_url: str, coin_name: str, user_id: str,
    user_server: str, filename: str, password: str, timeout: int=60
):
    wallet_filename = user_server + "_" + coin_name + "_" + user_id
    if wallet_filename != filename:
        print("Mis-match wallet file and user!")
        return False
    try:
        headers = {
            'Content-Type': 'application/json'
        }
        json_data = {
            "jsonrpc":"2.0",
            "id":"0",
            "method":"open_wallet",
            "params":{
                "filename": filename,
                "password": password
            }
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                wallet_api_url + "/json_rpc",
                headers=headers,
                json=json_data,
                timeout=timeout
            ) as response:
                if response.status == 200:
                    print("bcn_open_wallet: open wallet file {}".format(filename))
                    # get key and seeds
                    return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def bcn_close_wallet(
    wallet_api_url: str, coin_name: str, user_id: str,
    user_server: str, filename: str, timeout: int=60
):
    wallet_filename = user_server + "_" + coin_name + "_" + user_id
    if wallet_filename != filename:
        print("Mis-match wallet file and user!")
        return False
    try:
        headers = {
            'Content-Type': 'application/json'
        }
        json_data_save = {
            "jsonrpc":"2.0",
            "id":"0",
            "method":"store"
        }
        json_data_close = {
            "jsonrpc":"2.0",
            "id":"0",
            "method":"close_wallet"
        }
        # save first
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    wallet_api_url + "/json_rpc",
                    headers=headers,
                    json=json_data_save,
                    timeout=timeout
                ) as response:
                    pass
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # close
        async with aiohttp.ClientSession() as session:
            async with session.post(
                wallet_api_url + "/json_rpc",
                headers=headers,
                json=json_data_close,
                timeout=timeout
            ) as response:
                if response.status == 200:
                    # get key and seeds
                    return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def bcn_get_height(
    coin_name: str, wallet_api_url: str, header: str, timeout: int=30
):
    try:
        if coin_name in ["WRKZ", "DEGO"]:
            headers = {
                'X-API-KEY': header,
                'Content-Type': 'application/json'
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    wallet_api_url + "/status",
                    headers=headers,
                    timeout=timeout
                ) as response:
                    if response.status == 200:
                        json_resp = await response.json()
                        return json_resp
                    else:
                        print(f"internal error during get height wallet {coin_name}")
        elif coin_name in ["WOW", "XMR"]:
            try:
                headers = {
                    'Content-Type': 'application/json'
                }
                json_data = {
                    "jsonrpc":"2.0",
                    "id":"0",
                    "method":"get_height",
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        wallet_api_url + "/json_rpc",
                        headers=headers,
                        json=json_data,
                        timeout=timeout
                    ) as response:
                        if response.status == 200:
                            json_resp = await response.json()
                            return json_resp
                        else:
                            print(f"internal error during get height wallet {coin_name}")
                            return None
            except Exception:
                traceback.print_exc(file=sys.stdout)
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def bcn_get_address_bool(
    coin_name: str, wallet_api_url: str, header: str,
    address: str, timeout: int=30
):
    try:
        if coin_name in ["WRKZ", "DEGO"]:
            headers = {
                'X-API-KEY': header,
                'Content-Type': 'application/json'
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    wallet_api_url + "/addresses",
                    headers=headers,
                    timeout=timeout
                ) as response:
                    if response.status == 200:
                        json_resp = await response.json()
                        return address in json_resp['addresses']
                    else:
                        print(f"internal error during get address wallet {coin_name}")
        elif coin_name in ["WOW", "XMR"]:
            headers = {
                'Content-Type': 'application/json'
            }
            try:
                json_data = {
                    "jsonrpc":"2.0",
                    "id":"0",
                    "method":"get_address",
                    "params": {
                        "account_index": 0
                    }
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        wallet_api_url + "/json_rpc",
                        headers=headers,
                        json=json_data,
                        timeout=timeout
                    ) as response:
                        json_resp = await response.json()
                        if "error" in json_resp:
                            return False
                        return address == json_resp['result']['address']
            except Exception:
                traceback.print_exc(file=sys.stdout)
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def bcn_get_new_address(
    coin_name: str, wallet_api_url: str, header: str, wallet_data: dict=None,
    user_id: str=None, user_server: str=None, slot_id: int=None, timeout: int=30
):
    try:
        if coin_name in ["WRKZ", "DEGO"]:
            headers = {
                'X-API-KEY': header,
                'Content-Type': 'application/json'
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    wallet_api_url + "/addresses/create",
                    headers=headers,
                    timeout=timeout
                ) as response:
                    if response.status == 201:
                        json_resp = await response.json()
                        # call save wallet
                        async with session.put(
                            wallet_api_url + "/save",
                            headers=headers,
                            timeout=timeout
                        ) as save_resp:
                            if save_resp.status == 200:
                                return json_resp
                            else:
                                print(f"internal error during save wallet {coin_name}")
                    else:
                        print(f"internal error during create wallet {coin_name}")
        elif coin_name in ["WOW", "XMR"]:
            # assign that slot to him
            update_slot = await vault_xmr_update_slot_used(
                user_id, user_server, 1, slot_id, wallet_data['filename']
            )
            if update_slot is True:
                try:
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    json_data = {
                        "jsonrpc":"2.0",
                        "id":"0",
                        "method":"create_wallet",
                        "params":{
                            "filename": wallet_data['filename'],
                            "password": wallet_data['password'],
                            "language": "English"
                        }
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            wallet_api_url + "/json_rpc",
                            headers=headers,
                            json=json_data,
                            timeout=timeout
                        ) as response:
                            if response.status == 200:
                                # get key and seeds
                                address = None
                                seed = None
                                json_data = {
                                    "jsonrpc":"2.0",
                                    "id":"0",
                                    "method":"get_address",
                                    "params": {
                                        "account_index": 0
                                    }
                                }
                                async with session.post(
                                    wallet_api_url + "/json_rpc",
                                    headers=headers,
                                    json=json_data,
                                    timeout=timeout
                                ) as response:
                                    json_resp = await response.json()
                                    address = json_resp['result']['address']
                                json_data = {
                                    "jsonrpc":"2.0",
                                    "id":"0",
                                    "method":"query_key",
                                    "params": {
                                        "key_type": "mnemonic"
                                    }
                                }
                                async with session.post(
                                    wallet_api_url + "/json_rpc",
                                    headers=headers,
                                    json=json_data,
                                    timeout=timeout
                                ) as response:
                                    json_resp = await response.json()
                                    seed = json_resp['result']['key']
                                return {
                                    "address": address,
                                    "seed": seed
                                }
                            else:
                                return None
                except Exception:
                    traceback.print_exc(file=sys.stdout)
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def vault_insert(
    user_id: str, user_server: str, coin_name: str, coin_type: str,
    address: str, spend_key: str, view_key: str, private_key: str,
    seed: str, dump: str, height: int=None, password: str=None
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                INSERT INTO `vaults` 
                (`coin_name`, `type`, `user_id`, `user_server`, `address`, `spend_key`,
                `view_key`, `private_key`, `seed`, `dump`, `address_ts`, `height`, `password`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);

                UPDATE `vaults_coin_setting`
                SET `used`=`used`+1
                WHERE `coin_name`=%s LIMIT 1;
                """
                await cur.execute(sql, (
                    coin_name, coin_type, user_id, user_server, address,
                    spend_key, view_key, private_key, seed, dump, int(time.time()), height, password,
                    coin_name
                ))
                await conn.commit()
                return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def vault_archive(
    user_id: str, user_server: str, coin_name: str, coin_type: str,
    address: str, spend_key: str, view_key: str, private_key: str,
    seed: str, dump: str, address_ts: int, height: int=None, confirm: int=0, backup_date: int=None,
    password: str=None
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                INSERT INTO `vaults_archive` 
                (`coin_name`, `type`, `user_id`, `user_server`, `address`, `spend_key`,
                `view_key`, `private_key`, `seed`, `dump`, `address_ts`, `height`, 
                `confirmed_backup`, `backup_date`, `deleted_date`, `password`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);

                UPDATE `vaults_coin_setting`
                SET `used`=`used`-1
                WHERE `coin_name`=%s LIMIT 1;

                DELETE FROM `vaults`
                WHERE `coin_name`=%s AND `user_id`=%s AND `user_server`=%s LIMIT 1;
                """
                await cur.execute(sql, (
                    coin_name, coin_type, user_id, user_server, address,
                    spend_key, view_key, private_key, seed, dump, address_ts, height,
                    confirm, backup_date, int(time.time()), password,
                    coin_name,
                    coin_name, user_id, user_server
                ))
                await conn.commit()
                return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def vault_withdraw(
    user_id: str, user_server: str, coin_name: str,
    address: str, extra: str, amount: float, ref: str, other: str
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                INSERT INTO `vaults_withdraw` 
                (`coin_name`, `user_id`, `user_server`, `external_address`, `extra`,
                `amount`, `date`, `ref`, `others`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                """
                await cur.execute(sql, (
                    coin_name, user_id, user_server, address, extra,
                    amount, int(time.time()), ref, other
                ))
                await conn.commit()
                return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def vault_confirm_backup(
    user_id: str, user_server: str, coin_name: str
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                UPDATE `vaults` SET
                `confirmed_backup`=1, `backup_date`=%s
                WHERE `coin_name`=%s AND `user_id`=%s AND `user_server`=%s
                LIMIT 1;
                """
                await cur.execute(sql, (
                    int(time.time()), coin_name, user_id, user_server
                ))
                await conn.commit()
                return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def vault_xmr_find_slot(coin_name: str):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT * FROM `vaults_process_spawn`
                WHERE `coin_name`=%s AND `is_dead`=0 AND `is_used`=0 AND `user_id` IS NULL
                """
                await cur.execute(sql, (coin_name))
                result = await cur.fetchall()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

async def vault_xmr_find_slot_by_user(coin_name: str, user_id: str, user_server: str):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT * FROM `vaults_process_spawn`
                WHERE `coin_name`=%s AND `is_dead`=0 AND `user_id`=%s AND `user_server`=%s
                LIMIT 1
                """
                await cur.execute(sql, (coin_name, user_id, user_server))
                result = await cur.fetchone()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def vault_xmr_update_slot_used(
    user_id: str, user_server: str, is_used: int, slot_id: int, wallet_file: str=None
):
    # toggle slot used and unused
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                occupied_from = int(time.time())
                if is_used == 0:
                    occupied_from = None
                sql = """
                UPDATE `vaults_process_spawn`
                SET `user_id`=%s, `user_server`=%s, `is_used`=%s, `occupied_from`=%s, `wallet_file`=%s
                WHERE `is_dead`=0 AND `is_used`<>%s AND `id`=%s
                """
                await cur.execute(sql, (
                    user_id, user_server, is_used, occupied_from,
                    wallet_file, is_used, slot_id
                ))
                await conn.commit()
                return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def vault_xmr_find_occupied_slot(duration: int=60):
    try:
        lap = int(time.time()) - duration
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT * FROM `vaults_process_spawn`
                WHERE `user_id` IS NOT NULL AND `occupied_from`<%s
                """
                await cur.execute(sql, lap)
                result = await cur.fetchall()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

async def get_a_user_vault_list(user_id: str, user_server: str):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT * FROM `vaults`
                WHERE `user_id`=%s AND `user_server`=%s
                """
                await cur.execute(sql, (user_id, user_server))
                result = await cur.fetchall()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

async def get_a_user_vault_coin(user_id: str, coin_name: str, user_server: str):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT * FROM `vaults`
                WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                LIMIT 1
                """
                await cur.execute(sql, (user_id, user_server, coin_name))
                result = await cur.fetchone()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def get_coin_vault_setting(coin_name: str):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT * FROM `vaults_coin_setting`
                WHERE `coin_name`=%s
                LIMIT 1
                """
                await cur.execute(sql, coin_name)
                result = await cur.fetchone()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

class ConfirmBackup(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=60.0)
        self.value: Optional[bool] = None

    @disnake.ui.button(label="Yes, already backup!", style=disnake.ButtonStyle.green)
    async def confirm(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.send_message(f"{inter.author.mention}, confirming ...")
        await inter.delete_original_message()
        self.value = True
        self.stop()

    @disnake.ui.button(label="No, will do later!", style=disnake.ButtonStyle.grey)
    async def cancel(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.send_message(f"{inter.author.mention}, you need to backup before you can withdraw.", delete_after=6.0)
        self.value = False
        self.stop()

class ConfirmArchive(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=60.0)
        self.value: Optional[bool] = None

    @disnake.ui.button(label="Yes, remove it!", style=disnake.ButtonStyle.green)
    async def confirm(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.send_message(f"{inter.author.mention}, removing ...")
        await inter.delete_original_message()
        self.value = True
        self.stop()

    @disnake.ui.button(label="No, don't do!", style=disnake.ButtonStyle.grey)
    async def cancel(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.send_message(f"{inter.author.mention}, not removing ...")
        await inter.delete_original_message()
        self.value = False
        self.stop()

class DropdownVaultCoin(disnake.ui.StringSelect):
    def __init__(self, ctx, owner_id, bot, embed, list_coins, selected_coin):
        self.ctx = ctx
        self.owner_id = owner_id
        self.bot = bot
        self.embed = embed
        self.list_coins = list_coins
        self.selected_coin = selected_coin
        self.utils = Utils(self.bot)
        self.wallet_api = WalletAPI(self.bot)

        options = [
            disnake.SelectOption(
                label=each, description="Select {}".format(each.upper()),
                emoji=getattr(getattr(self.bot.coin_list, each), "coin_emoji_discord")
            ) for each in list_coins
        ]

        super().__init__(
            placeholder="Choose menu..." if self.selected_coin is None else self.selected_coin,
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, inter: disnake.MessageInteraction):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, that is not your menu!", delete_after=3.0)
            return
        else:
            await inter.response.send_message(f"{inter.author.mention}, checking wallet ...", ephemeral=True)
            # check if user has that coin
            get_a_vault = None
            if self.values[0] is not None:
                get_a_vault = await get_a_user_vault_coin(str(self.owner_id), self.values[0], SERVER_BOT)

            # Button settings
            if get_a_vault is None:
                disable_update = False
                disable_withdraw = True
                disable_viewkey = True
                disable_archive = True
            else:
                disable_update = True
                disable_withdraw = False
                disable_viewkey = True
                disable_archive = True
                if self.values[0] in ["ETH", "MATIC", "BNB"] + ["WOW", "XMR"] + ["WRKZ", "DEGO"]:
                    disable_archive = False
                if get_a_vault['confirmed_backup'] == 0:
                    disable_withdraw = True
                    disable_viewkey = False

            self.embed.clear_fields()
            self.embed.add_field(
                name="Selected coins",
                value=self.values[0],
                inline=False
            )
            coin_setting = None
            if self.values[0] is not None:
                coin_setting = await get_coin_vault_setting(self.values[0])
            if get_a_vault is not None:
                self.embed.add_field(
                    name="Address",
                    value=get_a_vault['address'],
                    inline=False
                )
                try:
                    if coin_setting is not None:
                        if self.values[0] in ["WRKZ", "DEGO"]:
                            get_balance = await bnc_get_balance(
                                self.values[0], coin_setting['wallet_address'], coin_setting['header'], get_a_vault['address'], 30
                            )
                            if get_balance is not None:
                                self.embed.add_field(
                                    name="Balance",
                                    value="Unlocked: {}\nLocked: {}".format(
                                        num_format_coin(get_balance['unlocked']/10**coin_setting['coin_decimal']),
                                        num_format_coin(get_balance['locked']/10**coin_setting['coin_decimal'])
                                    ),
                                    inline=False
                                )
                                try:
                                    wallet_height = await bcn_get_height(self.values[0], coin_setting['wallet_address'],  coin_setting['header'], 30)
                                    if wallet_height is not None:
                                        self.embed.add_field(
                                            name="Sync",
                                            value="Wallet Height: {}\nNetwork: {}".format(
                                                wallet_height['walletBlockCount'],
                                                wallet_height['networkBlockCount']
                                            ),
                                            inline=False
                                        )
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                                if get_balance['unlocked']/10**coin_setting['coin_decimal'] <= coin_setting['min_withdraw_btn']:
                                    if coin_setting['min_withdraw_btn'] > 0:
                                        self.embed.add_field(
                                            name="Withdraw note",
                                            value="You would need minimum {} {} to have withdraw button enable.".format(
                                                num_format_coin(coin_setting['min_withdraw_btn']), self.values[0]
                                            ),
                                            inline=False
                                        )
                                    disable_withdraw = True
                            else:
                                self.embed.add_field(
                                    name="Balance",
                                    value="N/A",
                                    inline=False
                                )
                                disable_withdraw = True
                            if coin_setting['note']:
                                self.embed.add_field(
                                    name="Coin/Token note",
                                    value=coin_setting['note'],
                                    inline=False
                                )
                        elif self.values[0] in ["ETH", "MATIC", "BNB"]:
                            get_balance = await http_wallet_getbalance(
                                coin_setting['daemon_address'], get_a_vault['address'], None, 5
                            )
                            if get_balance is not None:
                                self.embed.add_field(
                                    name="Balance",
                                    value="{}".format(
                                        num_format_coin(get_balance/10**coin_setting['coin_decimal']),
                                    ),
                                    inline=False
                                )
                                if get_balance/10**coin_setting['coin_decimal'] <= coin_setting['min_withdraw_btn']:
                                    if coin_setting['min_withdraw_btn'] > 0:
                                        self.embed.add_field(
                                            name="Withdraw note",
                                            value="You would need minimum {} {} to have withdraw button enable.".format(
                                                num_format_coin(coin_setting['min_withdraw_btn']), self.values[0]
                                            ),
                                            inline=False
                                        )
                                    disable_withdraw = True
                            else:
                                self.embed.add_field(
                                    name="Balance",
                                    value="N/A",
                                    inline=False
                                )
                                disable_withdraw = True
                        elif self.values[0] in ["WOW", "XMR"]:
                            # check if user has wallet service running
                            # async def vault_xmr_find_slot_by_user(coin_name: str, user_id: str, user_server: str):
                            get_slot = await vault_xmr_find_slot_by_user(
                                self.values[0], str(inter.author.id), SERVER_BOT
                            )
                            if get_slot is None:
                                disable_update = False
                                disable_withdraw = True
                                disable_viewkey = True
                                disable_archive = False
                                view = VaultMenu(
                                    self.bot, self.ctx, inter.author.id, self.embed, self.bot.config['vault']['enable_vault'],
                                    self.values[0], disable_update, disable_withdraw, disable_viewkey, disable_archive
                                )
                                await self.ctx.edit_original_message(content=None, embed=self.embed, view=view)
                                await inter.edit_original_message(
                                    f"{inter.author.mention}, you haven't open {self.values[0]} wallet yet! Tap Open."
                                )
                                await asyncio.sleep(5.0)
                                await inter.delete_original_message()
                                return
                            else:
                                disable_update = True
                                disable_withdraw = False
                                disable_viewkey = True
                                disable_archive = False
                                if get_a_vault['confirmed_backup'] == 0:
                                    disable_withdraw = True
                                    disable_viewkey = False
                                if get_slot['user_id'] != str(inter.author.id):
                                    await inter.edit_original_message(
                                        content=f"{inter.author.mention}, mis-match wallet. Report to TipBot dev!"
                                    )
                                    return
                                wallet_api_url = get_slot['rpc_address']
                            get_balance = await bnc_get_balance(
                                self.values[0], wallet_api_url, None, None, 30
                            )
                            if get_balance is not None:
                                self.embed.add_field(
                                    name="Balance",
                                    value="Balance: {}\nUnlocked: {}".format(
                                        num_format_coin(get_balance['result']['balance']/10**coin_setting['coin_decimal']),
                                        num_format_coin(get_balance['result']['unlocked_balance']/10**coin_setting['coin_decimal'])
                                    ),
                                    inline=False
                                )
                                try:
                                    wallet_height = await bcn_get_height(self.values[0], wallet_api_url, None, 30)
                                    type_coin = "XMR"
                                    netheight = ""
                                    height = await self.wallet_api.get_block_height(type_coin, self.values[0], None)
                                    if height is not None:
                                        netheight = "\nNetwork: {}".format(height)
                                    if wallet_height is not None:
                                        self.embed.add_field(
                                            name="Sync",
                                            value="Wallet Height: {}{}".format(
                                                wallet_height['result']['height'], netheight
                                            ),
                                            inline=False
                                        )
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                                if get_balance['result']['unlocked_balance']/10**coin_setting['coin_decimal'] <= coin_setting['min_withdraw_btn']:
                                    if coin_setting['min_withdraw_btn'] > 0:
                                        self.embed.add_field(
                                            name="Withdraw note",
                                            value="You would need minimum {} {} to have withdraw button enable.".format(
                                                num_format_coin(coin_setting['min_withdraw_btn']), self.values[0]
                                            ),
                                            inline=False
                                        )
                                    disable_withdraw = True
                            else:
                                self.embed.add_field(
                                    name="Balance",
                                    value="N/A",
                                    inline=False
                                )
                                disable_withdraw = True
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            self.embed.add_field(
                name="Other note",
                value=self.bot.config['vault']['note_msg'],
                inline=False
            )
            if coin_setting and coin_setting['wallet_apps']:
                self.embed.add_field(
                    name="Wallet App",
                    value=coin_setting['wallet_apps'],
                    inline=False
                )
            view = VaultMenu(
                self.bot, self.ctx, inter.author.id, self.embed, self.bot.config['vault']['enable_vault'],
                self.values[0], disable_update, disable_withdraw, disable_viewkey, disable_archive
            )
            await self.ctx.edit_original_message(content=None, embed=self.embed, view=view)
            await inter.delete_original_message()

class VaultMenu(disnake.ui.View):
    def __init__(
        self, bot,
        ctx,
        owner_id: int,
        embed,
        list_coins,
        selected_coin: str=None,
        disable_create_update: bool=True, disable_withdraw: bool=True,
        disable_viewkey: bool=True, disable_archive: bool=True
    ):
        super().__init__(timeout=120.0)
        self.bot = bot
        self.ctx = ctx
        self.owner_id = owner_id
        self.embed = embed
        self.selected_coin = selected_coin
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)

        self.btn_vault_update.disabled = disable_create_update
        self.btn_vault_withdraw.disabled = disable_withdraw
        self.btn_vault_viewkey.disabled = disable_viewkey
        self.btn_vault_archive.disabled = disable_archive

        self.add_item(DropdownVaultCoin(
            ctx, owner_id, self.bot, self.embed, list_coins, self.selected_coin
        ))

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, disnake.ui.Button):
                child.disabled = True
        await self.ctx.edit_original_message(
            view=None
        )

    @disnake.ui.button(label="Create/Open", style=ButtonStyle.green, custom_id="vault_update")
    async def btn_vault_update(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        # In case future this is public
        if interaction.author.id != self.owner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, that's not yours!", ephemeral=True)
        else:
            await interaction.response.send_message(f"{interaction.author.mention}, creating/opening...", ephemeral=True)
            inserting = False
            address = ""
            if self.selected_coin in ["WOW", "XMR"]:
                if self.bot.config['vault']['disable_monero_coins'] == 1:
                    await interaction.edit_original_message(
                        content=f"{interaction.author.mention}, {self.selected_coin} is currently on maintenance. Try again later!")
                    return
                # check if there is any unused slot for wallet service
                # prompt for password first, minimum 8, max 32?
                # created wallet with SERVER_COIN_userid (as file name)
                # after create, user shall get seed and keys
                type_coin = "XMR"

                # Disable all view first
                disable_update = True
                disable_withdraw = True
                disable_viewkey = True
                disable_archive = True
                disable_view = VaultMenu(
                    self.bot, self.ctx, self.owner_id, self.embed, self.bot.config['vault']['enable_vault'],
                    self.selected_coin, disable_update, disable_withdraw, disable_viewkey, disable_archive
                )
                await self.ctx.edit_original_message(content=None, embed=self.embed, view=disable_view)

                get_free_slot = await vault_xmr_find_slot(self.selected_coin)
                if len(get_free_slot) == 0:
                    await interaction.edit_original_message(
                        content=f"{interaction.author.mention}, there is no free slot wallet service right now! Try again later!")
                    return
                wallet_url = get_free_slot[0]['rpc_address']
                slot_id = get_free_slot[0]['id']
                wallet_filename = SERVER_BOT + "_" + self.selected_coin + "_" + str(interaction.author.id)
                coin_setting = await get_coin_vault_setting(self.selected_coin)
                # Check if user already created one. If yes, check available slot to open
                get_a_vault = await get_a_user_vault_coin(str(self.owner_id), self.selected_coin, SERVER_BOT)
                if get_a_vault is None:
                    # get coin height
                    height = await self.wallet_api.get_block_height(type_coin, self.selected_coin, None)
                    if height is None:
                        await interaction.edit_original_message(
                            content=f"{interaction.author.mention}, internal error when creating {self.selected_coin} address! Failed to get block info.")
                        return
                    # check if file wallet exist?
                    # assign one slot to him
                    # pickup first one
                    wallet_password = gen_password(12) # generate random string
                    path = Path(self.bot.config['vault'][self.selected_coin.lower() + '_wallet_dir'] + wallet_filename)
                    if path.is_file() is True:
                        await interaction.edit_original_message(
                            content=f"{interaction.author.mention}, wallet file exists! You may ask TipBot dev to check.")
                        await log_to_channel(
                            "vault",
                            f"[VAULT ERROR] User {interaction.author.name}#{interaction.author.discriminator} / {interaction.author.mention} "\
                            f"failed to created a new {self.selected_coin} wallet. Wallet file exist!",
                            self.bot.config['discord']['vault_webhook']
                        )
                        return
                    create_wallet = await bcn_get_new_address(
                        coin_name = self.selected_coin, wallet_api_url=wallet_url,
                        header=coin_setting['header'],
                        wallet_data={"filename": wallet_filename, "password": wallet_password},
                        user_id=str(interaction.author.id), user_server=SERVER_BOT, slot_id=get_free_slot[0]['id'],
                        timeout=30
                    )
                    if create_wallet is not None and type(create_wallet) == dict:
                        inserting = await vault_insert(
                            str(self.owner_id), SERVER_BOT, self.selected_coin, type_coin,
                            create_wallet['address'], spend_key=None,
                            view_key=None, private_key=None, seed=encrypt_string(create_wallet['seed']),
                            dump=encrypt_string(json.dumps(create_wallet)),
                            height=height, password=encrypt_string(wallet_password)
                        )
                        address = create_wallet['address']
                        # Do not return, we need to go to next
                    else:
                        await interaction.edit_original_message(
                            content=f"{interaction.author.mention}, internal error when creating {self.selected_coin} address!")
                        return
                else:
                    # Check if there is file
                    path = Path(self.bot.config['vault'][self.selected_coin.lower() + '_wallet_dir'] + wallet_filename)
                    if path.is_file() is False:
                        await interaction.edit_original_message(
                            content=f"{interaction.author.mention}, internal error when opening {self.selected_coin} wallet (wallet file not exist)!")
                        await log_to_channel(
                            "vault",
                            f"[VAULT ERROR] User {interaction.author.name}#{interaction.author.discriminator} / {interaction.author.mention} "\
                            f"failed to open {self.selected_coin} wallet. Wallet file doesn't exist!",
                            self.bot.config['discord']['vault_webhook']
                        )
                        return
                    # Check if there is an open thread in DB already
                    get_slot = await vault_xmr_find_slot_by_user(
                        self.selected_coin, str(interaction.author.id), SERVER_BOT
                    )
                    if get_slot is None:
                        # Not yet open, open wallet
                        opening = await bcn_open_wallet(
                            wallet_url, self.selected_coin, str(interaction.author.id),
                            SERVER_BOT, wallet_filename, decrypt_string(get_a_vault['password']), 30
                        )
                        if opening is False:
                            await interaction.edit_original_message(
                                content=f"{interaction.author.mention}, internal error when opening {self.selected_coin} wallet!")
                            await log_to_channel(
                                "vault",
                                f"[VAULT ERROR] User {interaction.author.name}#{interaction.author.discriminator} / {interaction.author.mention} "\
                                f"failed to open {self.selected_coin} wallet..",
                                self.bot.config['discord']['vault_webhook']
                            )
                            return
                        else:
                            # update slot
                            update_slot = await vault_xmr_update_slot_used(
                                str(interaction.author.id), SERVER_BOT, 1, slot_id, wallet_filename
                            )
                            if update_slot is False:
                                await log_to_channel(
                                    "vault",
                                    f"[VAULT ERROR] User {interaction.author.name}#{interaction.author.discriminator} / {interaction.author.mention} "\
                                    f"failed to update slot {slot_id} for {self.selected_coin}..",
                                    self.bot.config['discord']['vault_webhook']
                                )
                                return
                            else:
                                await log_to_channel(
                                    "vault",
                                    f"[VAULT] User {interaction.author.name}#{interaction.author.discriminator} / {interaction.author.mention} "\
                                    f" open {self.selected_coin} wallet successfully ...",
                                    self.bot.config['discord']['vault_webhook']
                                )
                                await asyncio.sleep(1.0)
                    # update slot, update embed?
                    self.embed.clear_fields()
                    self.embed.add_field(
                        name="Selected coins",
                        value=self.selected_coin,
                        inline=False
                    )
                    self.embed.add_field(
                        name="Address",
                        value=get_a_vault['address'],
                        inline=False
                    )
                    disable_update = True
                    disable_withdraw = False
                    disable_viewkey = True
                    disable_archive = False
                    try:
                        get_balance = await bnc_get_balance(
                            self.selected_coin, wallet_url, None, None, 30
                        )
                        if get_balance is not None:
                            self.embed.add_field(
                                name="Balance",
                                value="Balance: {}\nUnlocked: {}".format(
                                    num_format_coin(get_balance['result']['balance']/10**coin_setting['coin_decimal']),
                                    num_format_coin(get_balance['result']['unlocked_balance']/10**coin_setting['coin_decimal'])
                                ),
                                inline=False
                            )
                            try:
                                wallet_height = await bcn_get_height(self.selected_coin, wallet_url, None, 30)
                                type_coin = "XMR"
                                netheight = ""
                                height = await self.wallet_api.get_block_height(type_coin, self.selected_coin, None)
                                if height is not None:
                                    netheight = "\nNetwork: {}".format(height)
                                if wallet_height is not None:
                                    self.embed.add_field(
                                        name="Sync",
                                        value="Wallet Height: {}{}".format(
                                            wallet_height['result']['height'], netheight
                                        ),
                                        inline=False
                                    )
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            if get_balance['result']['unlocked_balance']/10**coin_setting['coin_decimal'] <= coin_setting['min_withdraw_btn']:
                                if coin_setting['min_withdraw_btn'] > 0:
                                    self.embed.add_field(
                                        name="Withdraw note",
                                        value="You would need minimum {} {} to have withdraw button enable.".format(
                                            num_format_coin(coin_setting['min_withdraw_btn']), self.values[0]
                                        ),
                                        inline=False
                                    )
                                disable_withdraw = True
                        else:
                            self.embed.add_field(
                                name="Balance",
                                value="N/A",
                                inline=False
                            )
                            disable_withdraw = True
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    self.embed.add_field(
                        name="NOTE",
                        value=self.bot.config['vault']['note_msg'],
                        inline=False
                    )
                    if get_a_vault['confirmed_backup'] == 0:
                        disable_withdraw = True
                        disable_viewkey = False
                    if self.selected_coin in ["ETH", "MATIC", "BNB"] + ["WOW", "XMR"]:
                        disable_archive = False
                    view = VaultMenu(
                        self.bot, self.ctx, self.owner_id, self.embed, self.bot.config['vault']['enable_vault'],
                        self.selected_coin, disable_update, disable_withdraw, disable_viewkey, disable_archive
                    )
                    await interaction.delete_original_message()
                    await self.ctx.edit_original_message(content=None, embed=self.embed, view=view)
                    return
            elif self.selected_coin in ["ETH", "MATIC", "BNB"]:
                type_coin = "ERC-20"
                w = create_address_eth()
                inserting = await vault_insert(
                    str(self.owner_id), SERVER_BOT, self.selected_coin, type_coin,
                    w['address'], None, None, encrypt_string(w['private_key']), encrypt_string(w['seed']), encrypt_string(str(w)),
                    None
                )
                address = w['address']
            elif self.selected_coin in ["WRKZ", "DEGO"]:
                type_coin = "TRTL-API"
                coin_setting = await get_coin_vault_setting(self.selected_coin)
                # get coin height
                height = await self.wallet_api.get_block_height(type_coin, self.selected_coin, None)
                if height is None:
                    await interaction.edit_original_message(
                        content=f"{interaction.author.mention}, internal error when creating {self.selected_coin} address! Failed to get block info.")
                    return
                if coin_setting is None:
                    await interaction.edit_original_message(
                        content=f"{interaction.author.mention}, internal error when creating {self.selected_coin} address!")
                    return
                else:
                    if coin_setting['is_maintenance'] == 1:
                        await interaction.edit_original_message(
                            content=f"{interaction.author.mention}, {self.selected_coin} is currently on maintenance!", ephemeral=True)
                        return
                    elif coin_setting['used'] >= coin_setting['max_number']:
                        await interaction.edit_original_message(
                            content=f"{interaction.author.mention}, {self.selected_coin} usage is high right now. "\
                                "We will increase the capacity and you can check again later!", ephemeral=True)
                        return
                create_wallet = await bcn_get_new_address(
                    coin_name = self.selected_coin, wallet_api_url=coin_setting['wallet_address'],
                    header=coin_setting['header'], timeout=30
                )
                if create_wallet is not None:
                    inserting = await vault_insert(
                        str(self.owner_id), SERVER_BOT, self.selected_coin, type_coin,
                        create_wallet['address'], spend_key=encrypt_string(create_wallet['privateSpendKey']),
                        view_key=coin_setting['view_key'], private_key=None, seed=None, dump=encrypt_string(json.dumps(create_wallet)),
                        height=height, password=None
                    )
                    address = create_wallet['address']
                else:
                    await interaction.edit_original_message(content=f"{interaction.author.mention}, internal error when creating {self.selected_coin} address!")            
            if inserting is True:
                self.embed.clear_fields()
                self.embed.add_field(
                    name="Selected coins",
                    value=self.selected_coin,
                    inline=False
                )
                self.embed.add_field(
                    name="Address",
                    value=address,
                    inline=False
                )
                self.embed.add_field(
                    name="NOTE",
                    value=self.bot.config['vault']['note_msg'],
                    inline=False
                )
                disable_update = True
                disable_withdraw = True
                disable_viewkey = False
                disable_archive = True
                disable_archive = True
                if self.selected_coin in ["ETH", "MATIC", "BNB"] + ["WOW", "XMR"]:
                    disable_archive = False
                view = VaultMenu(
                    self.bot, self.ctx, self.owner_id, self.embed, self.bot.config['vault']['enable_vault'],
                    self.selected_coin, disable_update, disable_withdraw, disable_viewkey, disable_archive
                )
                await interaction.edit_original_message(f"{interaction.author.mention}, successfully created your {self.selected_coin} address! Please View Seed/Key and backup it now!")
                await self.ctx.edit_original_message(content=None, embed=self.embed, view=view)
                await log_to_channel(
                    "vault",
                    f"[VAULT] User {interaction.author.name}#{interaction.author.discriminator} / {interaction.author.mention} "\
                    f"successfully created a new {self.selected_coin} wallet.",
                    self.bot.config['discord']['vault_webhook']
                )
            else:
                disable_update = True
                disable_withdraw = True
                disable_viewkey = True
                disable_archive = True
                view = VaultMenu(
                    self.bot, self.ctx, self.owner_id, self.embed, self.bot.config['vault']['enable_vault'],
                    self.selected_coin, disable_update, disable_withdraw, disable_viewkey, disable_archive
                )
                await interaction.edit_original_message(f"{interaction.author.mention}, internal error when creating {self.selected_coin} address!")
                await self.ctx.edit_original_message(content=None, embed=self.embed, view=view)

    @disnake.ui.button(label="Withdraw", style=ButtonStyle.primary, custom_id="vault_withdraw")
    async def btn_vault_withdraw(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        # In case future this is public
        if interaction.author.id != self.owner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, that's not yours!", ephemeral=True)
        else:
            # Waits until the user submits the modal.
            try:
                coin_setting = await get_coin_vault_setting(self.selected_coin)
                if coin_setting['is_maintenance'] == 1:
                    await interaction.response.send_message(
                        content=f"{interaction.author.mention}, {self.selected_coin} is currently on maintenance!")
                    return
                chain_id = coin_setting['chain_id']
                get_a_vault = await get_a_user_vault_coin(str(self.owner_id), self.selected_coin, SERVER_BOT)
                if get_a_vault is None:
                    await interaction.response.send_message(
                        content=f"{interaction.author.mention}, you don't have {self.selected_coin}'s vault!")
                    return

                if self.selected_coin in ["ETH", "MATIC", "BNB"]:
                    type_coin = "ERC-20"
                    seed = get_a_vault['seed']
                    wallet_url = coin_setting['wallet_address']
                elif self.selected_coin in ["WRKZ", "DEGO"]:
                    type_coin = "TRTL-API"
                    seed = None
                    wallet_height = await bcn_get_height(self.selected_coin, coin_setting['wallet_address'],  coin_setting['header'], 30)
                    height = await self.wallet_api.get_block_height(type_coin, self.selected_coin, None)
                    if wallet_height is None or height is None:
                        await interaction.response.send_message(
                            content=f"{interaction.author.mention}, {self.selected_coin}'s wallet is having sync issue. Try again later!")
                        return
                    else:
                        # check height
                        if abs(wallet_height['walletBlockCount'] - height) > 3:
                            await interaction.response.send_message(
                                content=f"{interaction.author.mention}, {self.selected_coin}'s sync gab between wallet and network is too big. Try again later!")
                            return
                    wallet_url = coin_setting['wallet_address']

                elif self.selected_coin in ["WOW", "XMR"]:
                    if self.bot.config['vault']['disable_monero_coins'] == 1:
                        await interaction.response.send_message(
                            content=f"{interaction.author.mention}, {self.selected_coin} is currently on maintenance. Try again later!")
                        return
                    type_coin = "XMR"
                    seed = None

                    get_slot = await vault_xmr_find_slot_by_user(
                        self.selected_coin, str(interaction.author.id), SERVER_BOT
                    )
                    wallet_filename = SERVER_BOT + "_" + self.selected_coin + "_" + str(interaction.author.id)
                    if get_slot is None:
                        # user hasn't opened wallet
                        get_free_slot = await vault_xmr_find_slot(self.selected_coin)
                        if len(get_free_slot) == 0:
                            await interaction.response.send_message(
                                content=f"{interaction.author.mention}, there is no free slot wallet service right now! Try again later!")
                            return

                        wallet_url = get_free_slot[0]['rpc_address']
                        slot_id = get_free_slot[0]['id']
                        # Not yet open, open wallet
                        opening = await bcn_open_wallet(
                            wallet_url, self.selected_coin, str(interaction.author.id),
                            SERVER_BOT, wallet_filename, decrypt_string(get_a_vault['password']), 30
                        )
                        if opening is False:
                            await interaction.response.send_message(
                                content=f"{interaction.author.mention}, internal error when opening {self.selected_coin} wallet!")
                            await log_to_channel(
                                "vault",
                                f"[VAULT ERROR] User {interaction.author.name}#{interaction.author.discriminator} / {interaction.author.mention} "\
                                f"failed to open {self.selected_coin} wallet..",
                                self.bot.config['discord']['vault_webhook']
                            )
                            return
                        else:
                            # update slot
                            update_slot = await vault_xmr_update_slot_used(
                                str(interaction.author.id), SERVER_BOT, 1, slot_id, wallet_filename
                            )
                            if update_slot is False:
                                await log_to_channel(
                                    "vault",
                                    f"[VAULT ERROR] User {interaction.author.name}#{interaction.author.discriminator} / {interaction.author.mention} "\
                                    f"failed to update slot {slot_id} for {self.selected_coin}..",
                                    self.bot.config['discord']['vault_webhook']
                                )
                                return
                            else:
                                await log_to_channel(
                                    "vault",
                                    f"[VAULT] User {interaction.author.name}#{interaction.author.discriminator} / {interaction.author.mention} "\
                                    f" open {self.selected_coin} wallet successfully ...",
                                    self.bot.config['discord']['vault_webhook']
                                )
                                await asyncio.sleep(1.0)
                    else:
                        # has slot but if wallet is open?
                        wallet_url = get_slot['rpc_address']
                        check_open = await bcn_get_address_bool(self.selected_coin, wallet_url, None, get_a_vault['address'], 30)
                        if check_open is False:
                            # open
                            await bcn_open_wallet(
                                wallet_url, self.selected_coin, str(interaction.author.id),
                                SERVER_BOT, wallet_filename, decrypt_string(get_a_vault['password']), 30
                            )

                    coin_setting = await get_coin_vault_setting(self.selected_coin)
                    wallet_height = await bcn_get_height(
                        self.selected_coin, wallet_url,  coin_setting['header'], 30
                    )
                    # Check height
                    height = await self.wallet_api.get_block_height(type_coin, self.selected_coin, None)
                    if wallet_height is None or height is None:
                        await interaction.response.send_message(
                            content=f"{interaction.author.mention}, {self.selected_coin}'s wallet is having sync issue. Try again later!")
                        return
                    else:
                        # check height
                        if abs(wallet_height['result']['height'] - height) > 3:
                            await interaction.response.send_message(
                                content=f"{interaction.author.mention}, {self.selected_coin}'s sync gab between wallet and network is too big. Try again later!")
                            return
                await interaction.response.send_modal(
                    modal=Withdraw(
                        interaction, self.bot, self.selected_coin, type_coin, coin_setting['coin_decimal'], 
                        get_a_vault['address'], seed, wallet_url, chain_id, 
                        coin_setting['header']
                    )
                )
                modal_inter: disnake.ModalInteraction = await self.bot.wait_for(
                    "modal_submit",
                    check=lambda i: i.custom_id == "modal_vault_withdraw" and i.author.id == interaction.author.id,
                    timeout=90,
                )
            except asyncio.TimeoutError:
                # The user didn't submit the modal in the specified period of time.
                # This is done since Discord doesn't dispatch any event for when a modal is closed/dismissed.
                return
            except Exception:
                traceback.print_exc(file=sys.stdout)
            #await interaction.response.send_message(f"{interaction.author.mention}, TODO!", ephemeral=True)

    @disnake.ui.button(label="View Key/Seed", style=ButtonStyle.gray, custom_id="vault_viewkey")
    async def btn_vault_viewkey(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        # In case future this is public
        if interaction.author.id != self.owner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, that's not yours!", ephemeral=True)
        else:
            await interaction.response.send_message(f"{interaction.author.mention}, loading data...", ephemeral=True)
            get_a_vault = None
            if self.selected_coin is not None:
                get_a_vault = await get_a_user_vault_coin(str(self.owner_id), self.selected_coin, SERVER_BOT)
            if get_a_vault is None:
                await interaction.edit_original_message(f"{interaction.author.mention}, internal error when loading your {self.selected_coin} data!")
            else:
                coin_setting = await get_coin_vault_setting(self.selected_coin)
                data = ""
                if self.selected_coin in ["ETH", "MATIC", "BNB"]:
                    data = "Address: {}\n".format(get_a_vault['address'])
                    data += "Seed: {}\n".format(decrypt_string(get_a_vault['seed']))
                elif self.selected_coin in ["WRKZ", "DEGO"]:
                    data = "Address: {}\n".format(get_a_vault['address'])
                    data += "View key: {}\n".format(decrypt_string(get_a_vault['view_key']))
                    data += "Spend key: {}\n".format(decrypt_string(get_a_vault['spend_key']))
                elif self.selected_coin in ["WOW", "XMR"]:
                    if self.bot.config['vault']['disable_monero_coins'] == 1:
                        await interaction.edit_original_message(
                            content=f"{interaction.author.mention}, {self.selected_coin} is currently on maintenance. Try again later!")
                        return
                    data = "Address: {}\n".format(get_a_vault['address'])
                    data += "Seed: {}\n".format(decrypt_string(get_a_vault['seed']))
                if get_a_vault['height'] is not None:
                    data += "Scan height: {}".format(get_a_vault['height'])
                view = ConfirmBackup()
                msg = f"{interaction.author.mention}, your {self.selected_coin} data! "\
                    f"Keep for yourself and don't share!```{data}```Please backup before you can withdraw! "\
                    "Once you confirm backup, you can't see the keys again."
                await interaction.edit_original_message(
                    content=msg,
                    view=view
                )
                # Wait for the View to stop listening for input...
                await view.wait()
                if view.value is False:
                    await interaction.delete_original_message()
                    return
                elif view.value is None:
                    await interaction.delete_original_message()
                    return
                else:
                    # Update
                    update_backup = await vault_confirm_backup(
                        str(interaction.author.id), SERVER_BOT, self.selected_coin
                    )
                    if update_backup is True:
                        disable_update = True
                        disable_withdraw = True
                        disable_viewkey = True
                        disable_archive = True
                        view = VaultMenu(
                            self.bot, self.ctx, self.owner_id, self.embed, self.bot.config['vault']['enable_vault'],
                            self.selected_coin, disable_update, disable_withdraw, disable_viewkey, disable_archive
                        )
                        await self.ctx.edit_original_message(content=None, view=view)
                        await interaction.edit_original_message(
                            content=f"{EMOJI_INFORMATION} {interaction.author.mention}, thank you for backup! You can run `/vault view` again for update.", view=None
                        )
                        await log_to_channel(
                            "vault",
                            f"[VAULT] User {interaction.author.name}#{interaction.author.discriminator} / {interaction.author.mention} "\
                            f"successfully backup his/her {self.selected_coin} key/seed.",
                            self.bot.config['discord']['vault_webhook']
                        )
                        await asyncio.sleep(2.0)
                        await self.ctx.delete_original_message()
                    else:
                        await interaction.edit_original_message(
                            content=f"{EMOJI_INFORMATION} {interaction.author.mention}, internal error. Please report!", view=None
                        )
                        await self.ctx.delete_original_message()

    @disnake.ui.button(label="❗ Archive", style=ButtonStyle.red, custom_id="vault_archive")
    async def btn_vault_archive(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        # In case future this is public
        if interaction.author.id != self.owner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, that's not yours!", ephemeral=True)
        else:
            await interaction.response.send_message(f"{interaction.author.mention}, checking ...", ephemeral=True)
            # Get user wallet
            get_a_vault = None
            if self.selected_coin is not None:
                get_a_vault = await get_a_user_vault_coin(str(self.owner_id), self.selected_coin, SERVER_BOT)
            if get_a_vault is None:
                await interaction.edit_original_message(
                    content=f"{interaction.author.mention}, you don't have {self.selected_coin}'s vault!")
                return

            view = ConfirmArchive()
            msg = f"{interaction.author.mention}, Do you want to remove this wallet? You can create a new one later."
            await interaction.edit_original_message(
                content=msg,
                view=view
            )
            # Wait for the View to stop listening for input...
            await view.wait()
            if view.value is False:
                await interaction.delete_original_message()
                return
            elif view.value is None:
                await interaction.delete_original_message()
                return
            else:
                # Disable all view first
                disable_update = True
                disable_withdraw = True
                disable_viewkey = True
                disable_archive = True
                disable_view = VaultMenu(
                    self.bot, self.ctx, self.owner_id, self.embed, self.bot.config['vault']['enable_vault'],
                    self.selected_coin, disable_update, disable_withdraw, disable_viewkey, disable_archive
                )
                await self.ctx.edit_original_message(content=None, embed=self.embed, view=disable_view)
                deleting = False
                # Check which coin is it?
                if self.selected_coin in ["ETH", "MATIC", "BNB"]:
                    # Archiving
                    deleting = await vault_archive(
                        str(self.owner_id), SERVER_BOT, self.selected_coin, get_a_vault['type'],
                        get_a_vault['address'], get_a_vault['spend_key'], get_a_vault['view_key'],
                        get_a_vault['private_key'], get_a_vault['seed'], get_a_vault['dump'],
                        get_a_vault['address_ts'], get_a_vault['height'], get_a_vault['confirmed_backup'], 
                        get_a_vault['backup_date'], None
                    )
                elif self.selected_coin in ["WRKZ", "DEGO"]:
                    if self.bot.config['vault']['disable_wrkz_coins'] == 1:
                        await interaction.edit_original_message(
                            content=f"{interaction.author.mention}, {self.selected_coin} is currently on maintenance. Try again later!")
                        return
                    coin_setting = await get_coin_vault_setting(self.selected_coin)
                    if coin_setting is None:
                        await interaction.edit_original_message(
                            content=f"{interaction.author.mention}, couldn't get coin setting for {self.selected_coin}!")
                        return
                    delete_address = await bcn_delete_address(
                        self.selected_coin, get_a_vault['address'], coin_setting['wallet_address'], coin_setting['header'], 60
                    )
                    if delete_address is True:
                        deleting = await vault_archive(
                            str(self.owner_id), SERVER_BOT, self.selected_coin, get_a_vault['type'],
                            get_a_vault['address'], get_a_vault['spend_key'], get_a_vault['view_key'],
                            get_a_vault['private_key'], get_a_vault['seed'], get_a_vault['dump'],
                            get_a_vault['address_ts'], get_a_vault['height'], get_a_vault['confirmed_backup'], 
                            get_a_vault['backup_date'], get_a_vault['password']
                        )
                elif self.selected_coin in ["WOW", "XMR"]:
                    if self.bot.config['vault']['disable_monero_coins'] == 1:
                        await interaction.edit_original_message(
                            content=f"{interaction.author.mention}, {self.selected_coin} is currently on maintenance. Try again later!")
                        return
                    # close wallet if open, remove spawn if running
                    get_slot = await vault_xmr_find_slot_by_user(
                        self.selected_coin, str(interaction.author.id), SERVER_BOT
                    )
                    if get_slot is not None:
                        wallet_filename = SERVER_BOT + "_" + self.selected_coin + "_" + str(interaction.author.id)
                        wallet_key = wallet_filename + ".keys"
                        try:
                            wallet_api_url = get_slot['rpc_address']
                            # close wallet
                            await bcn_close_wallet(
                                wallet_api_url, self.selected_coin, str(interaction.author.id),
                                SERVER_BOT, wallet_filename, 30
                            )
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                        # update spawn
                        try:
                            await vault_xmr_update_slot_used(
                                None, None, 0, get_slot['id'], None
                            )
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                    # Move files
                    try:
                        os.rename(
                            self.bot.config['vault'][self.selected_coin.lower() + '_wallet_dir'] + wallet_filename,
                            self.bot.config['vault']['archive_wallet_dir'] + wallet_filename + "_"+ str(int(time.time()))
                        )
                        os.rename(
                            self.bot.config['vault'][self.selected_coin.lower() + '_wallet_dir'] + wallet_key,
                            self.bot.config['vault']['archive_wallet_dir'] + wallet_key + "_"+ str(int(time.time()))
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    deleting = await vault_archive(
                        str(self.owner_id), SERVER_BOT, self.selected_coin, get_a_vault['type'],
                        get_a_vault['address'], get_a_vault['spend_key'], get_a_vault['view_key'],
                        get_a_vault['private_key'], get_a_vault['seed'], get_a_vault['dump'],
                        get_a_vault['address_ts'], get_a_vault['height'], get_a_vault['confirmed_backup'], 
                        get_a_vault['backup_date'], get_a_vault['password']
                    )
                if deleting is True:
                    await interaction.delete_original_message()
                    disable_update = False
                    disable_withdraw = True
                    disable_viewkey = True
                    disable_archive = True
                    view = VaultMenu(
                        self.bot, self.ctx, self.owner_id, self.embed, self.bot.config['vault']['enable_vault'],
                        self.selected_coin, disable_update, disable_withdraw, disable_viewkey, disable_archive
                    )
                    await self.ctx.edit_original_message(content="Wallet deleted. Please execute `/vault` command again.", embed=None, view=None)
                    await log_to_channel(
                        "vault",
                        f"[VAULT] User {interaction.author.name}#{interaction.author.discriminator} / {interaction.author.mention} "\
                        f"successfully deleted his/her {self.selected_coin}.",
                        self.bot.config['discord']['vault_webhook']
                    )
                else:
                    await interaction.edit_original_message(
                        content=f"{EMOJI_INFORMATION} {interaction.author.mention}, internal error. Please report!", view=None
                    )

class Withdraw(disnake.ui.Modal):
    def __init__(
            self, ctx, bot, coin_name: str, coin_type: str,
            coin_decimal: int, source_address: str, seed: str,
            endpoint: str, chain_id: int, contract_header: str
    ) -> None:
        self.ctx = ctx
        self.bot = bot
        self.coin_name = coin_name.upper()
        self.coin_type = coin_type
        self.coin_decimal = coin_decimal
        self.source_address = source_address
        self.seed = seed
        self.endpoint = endpoint
        self.chain_id = chain_id
        self.contract_header = contract_header
        extra_option = None
        note = "We recommend you to transfer to your own wallet!"
        max_len = 16
        address_max = 256
        if self.coin_type in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
            extra_option = "Payment ID"
            max_len = 64
            note = "If you use an integrated address, don't input Payment ID."
        elif self.coin_type == "XLM":
            extra_option = "MEMO"
            max_len = 64

        components = [
            disnake.ui.TextInput(
                label="Amount",
                placeholder="100",
                custom_id="amount_id",
                style=TextInputStyle.short,
                max_length=16,
                required=True
            ),
            disnake.ui.TextInput(
                label="Address",
                placeholder="your external address",
                custom_id="address_id",
                style=TextInputStyle.paragraph,
                max_length=address_max,
                required=True
            )
        ]

        if extra_option is not None:
            components.append([
                disnake.ui.TextInput(
                    label=extra_option,
                    placeholder="none",
                    custom_id="extra_option",
                    style=TextInputStyle.short,
                    max_length=max_len,
                    required=False
                )
            ])
        super().__init__(title=f"Withdraw {self.coin_name}", custom_id="modal_vault_withdraw", components=components)

    async def callback(self, interaction: disnake.ModalInteraction) -> None:
        # Check if type of question is bool or multipe
        await interaction.response.send_message(content=f"{interaction.author.mention}, checking withdraw ...", ephemeral=True)

        amount = interaction.text_values['amount_id'].strip()
        if amount == "":
            await interaction.edit_original_message(f"{interaction.author.mention}, amount is empty!")
            return

        address = interaction.text_values['address_id'].strip()
        if address == "":
            await interaction.edit_original_message(f"{interaction.author.mention}, address can't be empty!")
            return

        try:
            # check if amount is all
            gas = None
            send_all = False
            if amount.upper() == "ALL" and self.coin_name in ["ETH", "MATIC", "BNB"]:
                get_est_amount = await estimate_gas_amount_send_all(
                    self.endpoint, self.source_address, address
                )
                if get_est_amount is None:
                    await interaction.edit_original_message(
                        content=f"{interaction.author.mention}, failed to get estimation"\
                        f" gas amount for {self.coin_name}. Try again later!"
                    )
                    return
                else:
                    amount = float(get_est_amount['remaining']/(10**self.coin_decimal))
                    atomic_amount = get_est_amount['remaining']
                    if atomic_amount <= 0:
                        await interaction.edit_original_message(
                            content=f"{interaction.author.mention}, not sufficient balance to cover gas for sending {self.coin_name}!"
                        )
                        return
                    gas = {"gasPrice": get_est_amount['gas_price'], "estimateGas": get_est_amount['estimate_gas']}
            elif amount.upper() == "ALL" and self.coin_name in ["WOW", "XMR"]:
                # sweep_all
                send_all = True
                atomic_amount = 0 # placehodler
            elif amount.upper() == "ALL":
                await interaction.edit_original_message(
                    content=f"{interaction.author.mention}, {self.coin_name} doesn't support send `ALL` yet."
                )
                return
            else:
                amount = float(amount.replace(",", ""))
                atomic_amount = amount * 10 ** self.coin_decimal
                if atomic_amount <= 0:
                    await interaction.edit_original_message(
                        content=f"{interaction.author.mention}, invalid given amount!")
                    return
        except ValueError:
            await interaction.edit_original_message(
                content=f"{interaction.author.mention}, invalid given amount!")
            return

        extra_option = None
        if 'extra_option' in interaction.text_values:
            extra_option = interaction.text_values['extra_option'].strip()
            if extra_option is None or len(extra_option) == 0:
                extra_option = None

        coin_name = self.coin_name
        try:
            if self.source_address == address.lower():
                await interaction.edit_original_message(
                    f"{interaction.author.mention}, you should not try to same as source address!"
                )
                return
            if coin_name in ["WRKZ", "DEGO"]:
                sending = await bcn_send_external(
                    coin_name, self.source_address, address, extra_option,
                    atomic_amount, self.endpoint, self.contract_header, send_all=False, timeout=60
                )
                if sending is not None:
                    await interaction.edit_original_message(
                        f"{interaction.author.mention}, successfully sending out {amount} {coin_name}, tx: {sending['transactionHash']}!"
                    )
                    try:
                        await vault_withdraw(
                            str(interaction.author.id), SERVER_BOT, coin_name, address, extra_option,
                            amount, sending['transactionHash'], json.dumps(sending)
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    await log_to_channel(
                        "vault",
                        f"[VAULT] User {interaction.author.name}#{interaction.author.discriminator} / {interaction.author.mention} "\
                        f"successfully withdrew {num_format_coin(amount)} {coin_name}.",
                        self.bot.config['discord']['vault_webhook']
                    )
                    await self.ctx.delete_original_message()
                else:
                    await interaction.edit_original_message(
                        content=f"{interaction.author.mention}, internal error during sending {coin_name}!")
                return
            elif coin_name in ["WOW", "XMR"]:
                sending = await bcn_send_external(
                    coin_name, self.source_address, address, extra_option,
                    atomic_amount, self.endpoint, self.contract_header, send_all=send_all, timeout=60
                )
                if sending is not None:
                    if send_all is False:
                        tx_hash = sending['tx_hash']
                        send_amount = amount
                    else:
                        tx_hash = ", ".join(sending['tx_hash_list'])
                        send_amount = sum(sending['amount_list'])/10**self.coin_decimal
                    await interaction.edit_original_message(
                        f"{interaction.author.mention}, successfully sending out {send_amount} {coin_name}, tx: {tx_hash}!"
                    )
                    try:
                        await vault_withdraw(
                            str(interaction.author.id), SERVER_BOT, coin_name, address, extra_option,
                            send_amount, tx_hash, json.dumps(sending)
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    await log_to_channel(
                        "vault",
                        f"[VAULT] User {interaction.author.name}#{interaction.author.discriminator} / {interaction.author.mention} "\
                        f"successfully withdrew {send_amount} {coin_name}.",
                        self.bot.config['discord']['vault_webhook']
                    )
                    await self.ctx.delete_original_message()
                else:
                    await interaction.edit_original_message(
                        content=f"{interaction.author.mention}, internal error during sending {coin_name}!")
                return
            elif coin_name in ["ETH", "MATIC", "BNB"]:
                # get actual balance
                get_balance = await http_wallet_getbalance(
                    self.endpoint, self.source_address, None, 10
                )
                if get_balance is None:
                    await interaction.edit_original_message(
                        content=f"{interaction.author.mention}, failed to retrieve your {coin_name}'s balance. Try again later!")
                    return

                transaction = functools.partial(
                    send_erc_token, self.endpoint, self.chain_id, self.source_address, 
                    self.seed, address, get_balance/(10**self.coin_decimal), amount, self.coin_decimal,
                    gas
                )
                sending = await self.bot.loop.run_in_executor(None, transaction)

                if sending['success'] is False:
                    await interaction.edit_original_message(
                        content=f"{interaction.author.mention}, failed to send your {coin_name}. {sending['msg']}")
                else:
                    await interaction.edit_original_message(
                        content=f"{interaction.author.mention}, successfully withdraw {amount} {coin_name}. {sending['tx']}")
                    try:
                        await vault_withdraw(
                            str(interaction.author.id), SERVER_BOT, coin_name, address, None,
                            amount, sending['tx'], sending['others']
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    await log_to_channel(
                        "vault",
                        f"[VAULT] User {interaction.author.name}#{interaction.author.discriminator} / {interaction.author.mention} "\
                        f"successfully withdrew {num_format_coin(amount)} {coin_name}.",
                        self.bot.config['discord']['vault_webhook']
                    )
        except Exception:
            traceback.print_exc(file=sys.stdout)

class Vault(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)

    @commands.slash_command(
        name="vault",
        dm_permission=True,
        description="Various crypto vault commands in TipBot."
    )
    async def vault(self, ctx):
        try:
            await ctx.response.send_message(f"{ctx.author.mention}, vault loading ...", ephemeral=True)
            # If command is in public
            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, this command needs to be in DM."
                await ctx.edit_original_message(msg, ephemeral=True)
                return
            is_user_locked = self.utils.is_locked_user(str(ctx.author.id), SERVER_BOT)
            if is_user_locked is True:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, your account is locked for using the Bot. Please contact bot dev by /about link."
                await ctx.edit_original_message(msg, ephemeral=True)
                return
            # checking if vault is enable
            get_user = await find_user_by_id(str(ctx.author.id), SERVER_BOT)
            if get_user is None or (get_user and get_user['vault_enable'] == 0):
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you don't have have vault access yet! If you want to enable or test this, please contact TipBot dev."
                await ctx.edit_original_message(msg, ephemeral=True)
                return
            if self.bot.config['vault']['disable'] == 1 and ctx.author.id != self.bot.config['discord']['owner_id']:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, Vault is currently on maintenance. Be back soon!"
                await ctx.edit_original_message(msg, ephemeral=True)
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
            return

    @vault.sub_command(
        name="intro",
        usage="vault intro",
        description="Introduction of /vault."
    )
    async def vault_intro(
        self,
        ctx
    ):
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/vault intro", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            embed = disnake.Embed(
                title="Your TipBot's Vault",
                description=f"{ctx.author.mention}, You can join our supported guild for #help.",
                timestamp=datetime.now(),
            )
            embed.add_field(
                name="BRIEF",
                value=self.bot.config['vault']['brief_msg'],
                inline=False
            )
            embed.add_field(
                name="NOTE",
                value=self.bot.config['vault']['note_msg'],
                inline=False
            )
            embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
            embed.set_thumbnail(url=self.bot.user.display_avatar)
            await ctx.edit_original_message(content=None, embed=embed)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @vault.sub_command(
        name="view",
        usage="vault view",
        description="View your /vault."
    )
    async def vault_view(
        self,
        ctx
    ):
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/vault view", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            embed = disnake.Embed(
                title="Your TipBot's Vault",
                description=f"{ctx.author.mention}, You can join our supported guild for #help.",
                timestamp=datetime.now(),
            )
            embed.add_field(
                name="Supported coins",
                value=", ".join(self.bot.config['vault']['enable_vault']),
                inline=False
            )
            get_user_vaults = await get_a_user_vault_list(str(ctx.author.id), SERVER_BOT)
            if len(get_user_vaults) == 0:
                embed.add_field(
                    name="Your vault",
                    value="Empty",
                    inline=False
                )
            else:
                coin_list = [i['coin_name'] for i in get_user_vaults]
                embed.add_field(
                    name="Your vault",
                    value=", ".join(coin_list),
                    inline=False
                )
            embed.add_field(
                name="NOTE",
                value=self.bot.config['vault']['note_msg'],
                inline=False
            )
            embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
            embed.set_thumbnail(url=self.bot.user.display_avatar)
            disable_update = True
            disable_withdraw = True
            disable_viewkey = True
            disable_archive = True
            selected_coin = None
            view = VaultMenu(
                self.bot, ctx, ctx.author.id, embed, self.bot.config['vault']['enable_vault'],
                selected_coin, disable_update, disable_withdraw, disable_viewkey, disable_archive
            )
            await ctx.edit_original_message(content=None, embed=embed, view=view)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @tasks.loop(seconds=60.0)
    async def check_vault_xmr_occupied(self):
        time_lap = 5  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "check_vault_xmr_occupied"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            # get all occupied wallet
            get_active_proc = await vault_xmr_find_occupied_slot(self.bot.config['vault']['max_duration_occupied'])
            if len(get_active_proc) > 0:
                for i in get_active_proc:
                    try:
                        wallet_api_url = i['rpc_address']
                        # close wallet
                        wallet_filename = i['wallet_file']
                        if i['wallet_file'] is None:
                            wallet_filename = i['user_server'] + "_" + i['coin_name'] + "_" + i['user_id']
                        await bcn_close_wallet(
                            wallet_api_url, i['coin_name'], i['user_id'],
                            i['user_server'], wallet_filename, 30
                        )
                        # update spawn
                        try:
                            await vault_xmr_update_slot_used(
                                None, None, 0, i['id'], None
                            )
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                        user_msg = f"Bot closed your opened wallet for {i['coin_name']} to save resource. "\
                            f"You can open and check it again with `/vault view`."
                        if i['user_server'] == SERVER_BOT:
                            member = self.bot.get_user(int(i['user_id']))
                            if member is not None:
                                await member.send(user_msg)
                        await log_to_channel(
                            "vault",
                            f"[VAULT] System closed wallet of {i['coin_name']} for <@{i['user_id']}>",
                            self.bot.config['discord']['vault_webhook']
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.check_vault_xmr_occupied.is_running():
            self.check_vault_xmr_occupied.start()

    async def cog_load(self):
        await self.bot.wait_until_ready()
        if not self.check_vault_xmr_occupied.is_running():
            self.check_vault_xmr_occupied.start()

    def cog_unload(self):
        self.check_vault_xmr_occupied.cancel()

def setup(bot):
    bot.add_cog(Vault(bot))
