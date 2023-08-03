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
from typing import Dict, Optional
import re

import aiohttp
import aiomysql
import asyncio
import disnake
import numpy as np
import qrcode
from aiomysql.cursors import DictCursor
from cachetools import TTLCache

from disnake import TextInputStyle
from disnake.app_commands import Option, OptionChoice
from disnake.enums import OptionType
from disnake.enums import ButtonStyle
from disnake.ext import commands, tasks
from eth_account import Account
from eth_utils import is_hex_address  # Check hex only
from ethtoken.abi import EIP20_ABI
from httpx import AsyncClient, Timeout, Limits
import httpx
from pywallet import wallet as ethwallet

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

from cosmospy import Transaction as Cosmos_Transaction

import cn_addressvalidation

import store
from Bot import logchanbot, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_ARROW_RIGHTHOOK, SERVER_BOT, \
    RowButtonRowCloseAnyMessage, text_to_num, truncate, seconds_str, encrypt_string, decrypt_string, \
    EMOJI_HOURGLASS_NOT_DONE, alert_if_userlock, MSG_LOCKED_ACCOUNT, EMOJI_MONEYFACE, EMOJI_INFORMATION, \
    seconds_str_days, log_to_channel

from cogs.utils import MenuPage
from cogs.utils import Utils, num_format_coin, chunks
from cogs.utils import print_color

Account.enable_unaudited_hdwallet_features()

# TODO: update
async def address_pre_validation_check(
    address: str, coin_name: str, type_coin: str
):
    if type_coin == "ERC-20":
        return is_hex_address(address)
    elif type_coin == "TRC-20":
        try:
            url = "https://api.trongrid.io/wallet/validateaddress"
            data = {"address": address}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, json=data,
                    headers={'Content-Type': 'application/json'},
                    timeout=8
                ) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        await session.close()
                        decoded_data = json.loads(res_data)
                        if decoded_data is not None:
                            return decoded_data['result']
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    elif type_coin == "XLM":
        pass
    elif type_coin == "COSMOS":
        pass
    elif type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
        pass
    elif type_coin == "BTC":
        pass
    elif type_coin == "NANO":
        pass
    elif type_coin == "CHIA":
        pass
    elif type_coin == "HNT":
        pass
    elif type_coin == "ADA":
        pass
    elif type_coin in ["SOL", "SPL"]:
        pass
    elif type_coin == "XTZ":
        pass
    elif type_coin == "NEO":
        pass
    elif type_coin == "NEAR":
        pass
    elif type_coin == "XRP":
        pass
    elif type_coin == "ZIL":
        pass
    elif type_coin == "VET":
        pass
    elif type_coin == "VITE":
        pass
    return False

# moved from store.py
# approve spender to operator
async def erc20_approve_spender(
    url: str, chainId: int, contract: str, 
    sender_address: str, sender_seed: str, 
    operator_address: str
):
    try:
        w3 = Web3(Web3.HTTPProvider(url))

        # inject the poa compatibility middleware to the innermost layer
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        unicorns = w3.eth.contract(address=w3.toChecksumAddress(contract), abi=EIP20_ABI)
        nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(sender_address))
        acct = Account.from_mnemonic(
            mnemonic=sender_seed)

        max_amount = w3.toWei(2**64-1,'ether')
        tx = unicorns.functions.approve(w3.toChecksumAddress(operator_address), max_amount).buildTransaction({
            "chainId": chainId,
            "nonce": nonce,
            "from": w3.toChecksumAddress(sender_address)
        })

        signed_tx = w3.eth.account.signTransaction(tx, acct.key)
        tx_hash = w3.eth.sendRawTransaction(signed_tx.rawTransaction)
        tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)
        return tx_hash.hex()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        print("url: {}, sender: {}, operator: {}".format(url, sender_address, operator_address))
        await logchanbot(traceback.format_exc())
    return None

async def sql_check_minimum_deposit_erc20(
    url: str, net_name: str, coin: str, contract: str, coin_decimal: int,
    min_move_deposit: float, min_gas_tx: float, gas_ticker: str,
    move_gas_amount: float, chainId: str, real_deposit_fee: float,
    config, erc20_approve_spend: int = 0, time_lap: int = 0,
    dev_tax_percent: float=0.0
):
    global pool
    async def send_gas(url: str, chainId: str, to_address: str, move_gas_amount: float, min_gas_tx: float):
        # HTTPProvider:
        w3 = Web3(Web3.HTTPProvider(url))

        # inject the poa compatibility middleware to the innermost layer
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        # TODO: Let's move gas from main to have sufficient to move
        nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(config['eth']['MainAddress']))

        # get gas price
        gasPrice = w3.eth.gasPrice

        estimateGas = w3.eth.estimateGas(
            {'to': w3.toChecksumAddress(to_address),
             'from': w3.toChecksumAddress(config['eth']['MainAddress']),
             'value': int(move_gas_amount * 10 ** 18)})

        est_gas_amount = float(gasPrice * estimateGas / 10 ** 18)
        if est_gas_amount > min_gas_tx:
            await logchanbot(
                "[ERROR GAS {}]: Est. {} > minimum gas {}".format(
                    url, est_gas_amount, min_gas_tx)
            )
            return False
        else:
            amount_gas_move = int(move_gas_amount * 10 ** 18)
            if amount_gas_move < move_gas_amount * 10 ** 18: amount_gas_move = int(
                move_gas_amount * 10 ** 18)
            transaction = {
                'from': w3.toChecksumAddress(config['eth']['MainAddress']),
                'to': w3.toChecksumAddress(to_address),
                'value': amount_gas_move,
                'nonce': nonce,
                'gasPrice': gasPrice,
                'gas': estimateGas,
                'chainId': int(chainId, 16)
            }
            acct = Account.from_mnemonic(
                mnemonic=config['eth']['MainAddress_seed'])
            signed = w3.eth.account.sign_transaction(transaction, private_key=acct.key)
            # send Transaction for gas:
            send_gas_tx = w3.eth.sendRawTransaction(signed.rawTransaction)
            tx_receipt = w3.eth.waitForTransactionReceipt(send_gas_tx)
            return tx_receipt.transactionHash.hex() # hash Tx

    token_name = coin.upper()
    if net_name == token_name:
        list_user_addresses = await store.sql_get_all_erc_user(net_name, time_lap)
    else:
        list_user_addresses = await store.sql_get_all_erc_user("ERC-20", time_lap)
    if contract is None:
        # Main Token
        # we do not need gas, we move straight
        balance_below_min = 0
        balance_above_min = 0
        msg_deposit = ""
        if len(list_user_addresses) > 0:
            # OK check them one by one, gas token is **18
            for each_address in list_user_addresses:
                deposited_balance = await store.http_wallet_getbalance(
                    url, each_address['balance_wallet_address'], None, 64
                )
                if deposited_balance is None:
                    continue
                real_deposited_balance = float("%.8f" % (int(deposited_balance) / 10 ** 18))
                if real_deposited_balance < min_move_deposit:
                    balance_below_min += 1
                    # skip balance move below this
                    if real_deposited_balance > 0:
                        # print("Skipped {}, {}. Having {}, minimum {}".format(token_name, each_address['balance_wallet_address'], real_deposited_balance, min_move_deposit))
                        pass
                # config['eth']['MainAddress'] => each_address['balance_wallet_address']
                else:
                    balance_above_min += 1
                    try:
                        w3 = Web3(Web3.HTTPProvider(url))

                        # inject the poa compatibility middleware to the innermost layer
                        # w3.middleware_onion.inject(geth_poa_middleware, layer=0)

                        if net_name == "MATIC":
                            nonce = w3.eth.getTransactionCount(
                                w3.toChecksumAddress(each_address['balance_wallet_address']), 'pending')
                        else:
                            nonce = w3.eth.getTransactionCount(
                                w3.toChecksumAddress(each_address['balance_wallet_address']))

                        # get gas price
                        gasPrice = w3.eth.gasPrice
                        estimateGas = w3.eth.estimateGas(
                            {
                                'to': w3.toChecksumAddress(config['eth']['MainAddress']),
                                'from': w3.toChecksumAddress(each_address['balance_wallet_address']),
                                'value': deposited_balance
                            })
                        est_gas_amount = float(gasPrice * estimateGas / 10 ** 18)
                        if min_gas_tx is None: min_gas_tx = est_gas_amount
                        if est_gas_amount > min_gas_tx:
                            await logchanbot(
                                "[ERROR GAS {}]: Est. {} > minimum gas {}".format(
                                    token_name, est_gas_amount, min_gas_tx
                                )
                            )
                            await asyncio.sleep(5.0)
                            continue

                        print("TX {} deposited_balance: {}, gasPrice*estimateGas: {}*{}={}, ".format(
                            token_name, deposited_balance / 10 ** 18, gasPrice,
                            estimateGas, gasPrice * estimateGas / 10 ** 18)
                        )
                        est_tx_fee = gasPrice * estimateGas
                        # hard-coded gas. Optimistic always failed without this over-estimation
                        if est_tx_fee < int(0.000075 * 10**18):
                            est_tx_fee = int(0.000075 * 10**18)
                        moving_balance = deposited_balance - est_tx_fee
                        print("{}: {} moving {} with gas*gasPrice: {}, total: {}".format(
                            net_name, each_address['balance_wallet_address'],
                            moving_balance/10**18, gasPrice*estimateGas/10**18,
                            moving_balance/10**18 + gasPrice*estimateGas/10**18
                        ))
                        transaction = {
                            'from': w3.toChecksumAddress(each_address['balance_wallet_address']),
                            'to': w3.toChecksumAddress(config['eth']['MainAddress']),
                            'value': moving_balance,
                            'nonce': nonce,
                            'gasPrice': gasPrice,
                            'gas': estimateGas,
                            'chainId': chainId
                        }
                        acct = Account.from_mnemonic(mnemonic=decrypt_string(each_address['seed']))
                        signed_txn = w3.eth.account.sign_transaction(transaction, private_key=acct.key)

                        # send Transaction for gas:
                        sent_tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
                        if signed_txn is not None and sent_tx is not None:
                            # Add to SQL
                            try:
                                await store.sql_move_deposit_for_spendable(
                                    token_name, None, each_address['user_id'], each_address['balance_wallet_address'],
                                    config['eth']['MainAddress'], real_deposited_balance,
                                    real_deposit_fee + dev_tax_percent*real_deposited_balance, coin_decimal,
                                    sent_tx.hex(), each_address['user_server'],
                                    net_name
                                )
                                await asyncio.sleep(10.0)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                                # await logchanbot("store " +str(traceback.format_exc()))
                        if sent_tx.hex() is not None:
                            await logchanbot("[DEPOSIT] from user {}@{} amount {} {} to main balance. Tx: {}".format(
                                each_address['user_id'], each_address['user_server'], real_deposited_balance, token_name, sent_tx.hex()
                                )
                            )
                    except Exception as e:
                        print("ERROR TOKEN: {} - from {} to {}".format(
                            token_name, each_address['balance_wallet_address'], config['eth']['MainAddress'])
                        )
                        traceback.print_exc(file=sys.stdout)
                        # await logchanbot("store " +str(traceback.format_exc()))
            msg_deposit += "TOKEN {}: Total deposit address: {}: Below min.: {} Above min. {}".format(
                token_name, len(list_user_addresses), balance_below_min, balance_above_min
            )
        else:
            msg_deposit += "TOKEN {}: No deposit address.".format(token_name)
    else:
        # ERC-20
        # get withdraw gas balance    
        gas_main_balance = await store.http_wallet_getbalance(url, config['eth']['MainAddress'], None, 64)

        # main balance has gas?
        main_balance_gas_sufficient = True
        if gas_main_balance and gas_main_balance / 10 ** 18 >= min_gas_tx:
            pass
        else:
            main_balance_gas_sufficient = False
            pass

        if list_user_addresses and len(list_user_addresses) > 0:
            # OK check them one by one
            # print("{} addresses for updating balance".format(len(list_user_addresses)))
            if main_balance_gas_sufficient is False:
                await logchanbot("Main address not having enough gas! net_name {}, main address: {}".format(
                    net_name, config['eth']['MainAddress']
                    )
                )
                return

            for each_address in list_user_addresses:
                deposited_balance = await store.http_wallet_getbalance(
                    url, each_address['balance_wallet_address'], contract, 64
                )
                if deposited_balance is None:
                    continue
                real_deposited_balance = deposited_balance / 10 ** coin_decimal
                if real_deposited_balance >= min_move_deposit:
                    print("{}/{} - {} having {}.".format(token_name, net_name, each_address['balance_wallet_address'], real_deposited_balance))
                    # Check if there is gas remaining to spend there
                    gas_of_address = await store.http_wallet_getbalance(
                        url, each_address['balance_wallet_address'], None, 64
                    )
                    if erc20_approve_spend == 1:
                        # Check if in approved DB
                        check_approved = await store.check_approved_erc20(
                            each_address['user_id'], contract, each_address['balance_wallet_address'], 
                            each_address['user_server'], net_name
                        )
                        if check_approved is False:
                            # Check if it's previously approved but not in DB
                            check_if_approved = await store.erc20_if_approved(
                                url, contract, each_address['balance_wallet_address'],
                                config['eth']['MainAddress']
                            )
                            if check_if_approved is True:
                                # Insert to DB with transaction as AUTO
                                added = await store.insert_approved_erc20(
                                    each_address['user_id'], contract, 
                                    each_address['balance_wallet_address'], 
                                    each_address['user_server'], net_name, 
                                    "APPROVED"
                                )
                                await asyncio.sleep(5.0)
                                continue
                            else:
                                # Not in DB, Check gas and set approve
                                if gas_of_address / 10 ** 18 >= min_gas_tx:
                                    transaction = await erc20_approve_spender(
                                        url, int(chainId, 16), contract, 
                                        each_address['balance_wallet_address'],
                                        decrypt_string(each_address['seed']),
                                        config['eth']['MainAddress']
                                    )
                                    if transaction:
                                        added = await store.insert_approved_erc20(
                                            each_address['user_id'], contract, 
                                            each_address['balance_wallet_address'], 
                                            each_address['user_server'], net_name, 
                                            transaction
                                        )
                                        await asyncio.sleep(5.0)
                                        continue
                                elif gas_of_address / 10 ** 18 < min_gas_tx and main_balance_gas_sufficient:
                                    send_gas_tx = await send_gas(
                                        url, chainId, each_address['balance_wallet_address'], move_gas_amount, 
                                        min_gas_tx
                                    )
                                    if send_gas_tx:
                                        await logchanbot("[{}] Sent gas {} to to {}".format(
                                            net_name, move_gas_amount/10**18, 
                                            each_address['balance_wallet_address']
                                            )
                                        )
                                    await asyncio.sleep(5.0)
                                    continue
                        else:
                            # Transfer
                            if main_balance_gas_sufficient:
                                transaction = await store.erc20_transfer_token_to_operator(
                                    url, int(chainId, 16), contract, 
                                    each_address['balance_wallet_address'],
                                    config['eth']['MainAddress'], config['eth']['MainAddress_seed'], 
                                    deposited_balance
                                )
                                if transaction is not None:
                                    # Add to SQL
                                    try:
                                        await store.sql_move_deposit_for_spendable(
                                            token_name, contract, each_address['user_id'],
                                            each_address['balance_wallet_address'], config['eth']['MainAddress'],
                                            real_deposited_balance, real_deposit_fee + dev_tax_percent*real_deposited_balance, coin_decimal,
                                            transaction, each_address['user_server'], net_name
                                        )
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                        await logchanbot("store " +str(traceback.format_exc()))
                                    print("[DEPOSIT] from user {}@{} amount {} {} to main balance. Tx: {}".format(
                                        each_address['user_id'], each_address['user_server'], real_deposited_balance, token_name, transaction
                                        )
                                    )
                                    await logchanbot("[DEPOSIT] from user {}@{} amount {} {} to main balance. Tx: {}".format(
                                        each_address['user_id'], each_address['user_server'], real_deposited_balance, token_name, transaction
                                        )
                                    )
                                    await asyncio.sleep(5.0)
                    else:
                        if gas_of_address / 10 ** 18 >= min_gas_tx:
                            print('Address {} still has gas {}{} or Zero gas is needed.'.format(
                                each_address['balance_wallet_address'], gas_ticker, gas_of_address / 10 ** 18))
                            # TODO: Let's move balance from there to withdraw address and save Tx
                            # HTTPProvider:
                            w3 = Web3(Web3.HTTPProvider(url))

                            # inject the poa compatibility middleware to the innermost layer
                            w3.middleware_onion.inject(geth_poa_middleware, layer=0)

                            unicorns = w3.eth.contract(address=w3.toChecksumAddress(contract), abi=EIP20_ABI)
                            nonce = w3.eth.getTransactionCount(
                                w3.toChecksumAddress(each_address['balance_wallet_address'])
                            )

                            unicorn_txn = unicorns.functions.transfer(
                                w3.toChecksumAddress(config['eth']['MainAddress']),
                                deposited_balance  # amount to send
                            ).buildTransaction({
                                'from': w3.toChecksumAddress(each_address['balance_wallet_address']),
                                'gasPrice': w3.eth.gasPrice,
                                'nonce': nonce
                            })

                            acct = Account.from_mnemonic(
                                mnemonic=decrypt_string(each_address['seed']))
                            signed_txn = w3.eth.account.signTransaction(unicorn_txn, private_key=acct.key)
                            sent_tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
                            if signed_txn is not None and sent_tx is not None:
                                # Add to SQL
                                try:
                                    await store.sql_move_deposit_for_spendable(
                                        token_name, contract, each_address['user_id'],
                                        each_address['balance_wallet_address'], config['eth']['MainAddress'],
                                        real_deposited_balance, real_deposit_fee + dev_tax_percent*real_deposited_balance, coin_decimal,
                                        sent_tx.hex(), each_address['user_server'], net_name
                                    )
                                    await asyncio.sleep(10.0)
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                                    await logchanbot("store " +str(traceback.format_exc()))
                            if sent_tx.hex() is not None:
                                await logchanbot("[DEPOSIT] from user {}@{} amount {} {} to main balance. Tx: {}".format(
                                    each_address['user_id'], each_address['user_server'], real_deposited_balance, token_name, sent_tx.hex()
                                    )
                                )
                        elif gas_of_address / 10 ** 18 < min_gas_tx and main_balance_gas_sufficient:
                            send_gas_tx = await send_gas(
                                url, chainId, each_address['balance_wallet_address'], move_gas_amount, min_gas_tx
                            )
                            if send_gas_tx:
                                await logchanbot(
                                    "[{}] Sent gas {} to to {}".format(
                                        net_name, move_gas_amount/10**18, each_address['balance_wallet_address']
                                    )
                                )
                            await asyncio.sleep(5.0)
                        elif gas_of_address / 10 ** 18 < min_gas_tx and main_balance_gas_sufficient == False:
                            print('Main address has no sufficient balance to supply gas {}'.format(each_address['balance_wallet_address']))


async def cosmos_get_height(url: str, timeout: int=16):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={'Content-Type': 'application/json'},
                timeout=timeout
            ) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if decoded_data is not None:
                        return int(decoded_data['result']['block']['header']['height'])
    except asyncio.TimeoutError:
        print('TIMEOUT: cosmos_get_height {} for {}s'.format(url, timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def cosmos_get_seq(url: str, address: str, timeout: int=16):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url + address,
                headers={'Content-Type': 'application/json'},
                timeout=timeout
            ) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if decoded_data is not None:
                        return decoded_data
    except asyncio.TimeoutError:
        print('TIMEOUT: get_cosmos_seq {} for {}s'.format(url, timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

async def near_get_status(url: str, timeout: int=16):
    try:
        data = {
            "jsonrpc": "2.0",
            "id": "1",
            "method":
            "status", "params": []
        }
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

async def near_check_balance(url: str, account_id: str, timeout: int=60):
    try:
        data = {
            "method": "query",
            "params": {
                "request_type": "view_account",
                "finality": "final",
                "account_id": account_id
            },
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

async def near_check_balance_token(url: str, contract_id: str, account_id: str, timeout: int=60):
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
    except asyncio.exceptions.TimeoutError:
        print("Tezos check balances timeout for url: {} / addr: {}. Time: {}".format(url, address, timeout))
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

async def tezos_check_reveal(url: str, address: str, timeout: int=60):
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

async def tezos_get_head(url: str, timeout: int=60):
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
        data = {
            "method": "ledger",
            "params":[
                {
                    "ledger_index":
                    "validated",
                    "full": False,
                    "accounts": False,
                    "transactions": False,
                    "expand": False,
                    "owner_funds": False
                }
            ]
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=timeout
            ) as response:
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
    except httpx.ReadTimeout:
        print("httpx.ReadTimeout: url {} for XRP".format(url))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return []

async def xrp_get_account_info(url: str, address: str, timeout=60):
    try:
        data = {
            "method": "account_info",
            "params": [{"account": address}]
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=timeout
            ) as response:
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

async def xrp_get_account_lines(url: str, address: str, timeout=60):
    try:
        data = {
            "method": "account_lines",
            "params": [{"account": address}]
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=timeout
            ) as response:
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

async def zil_get_status(url: str, timeout=60):
    try:
        data = {
            "id": "1",
            "jsonrpc": "2.0",
            "method": "GetBlockchainInfo",
            "params": [""]
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=timeout
            ) as response:
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

async def zil_check_token_balance(url: str, contract: str, address_0x: str, timeout: int=60):
    try:
        data = {
            "id": "1",
            "jsonrpc": "2.0",
            "method": "GetSmartContractSubState",
            "params": [contract,"balances", [address_0x]]
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=timeout
            ) as response:
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

async def zil_get_tx(
    url: str, tx_hash: str, timeout: int=16
):
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        "id": "1",
        "jsonrpc": "2.0",
        "method": "GetTransaction",
        "params": [tx_hash]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=data,
                headers=headers,
                timeout=timeout
            ) as response:
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

def vet_move_token(
    url: str, token_name: str, contract: str, to_address: str,
    from_key: str, gas_payer_key: str, atomic_amount: int
):
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

async def vet_get_status(url: str, timeout=60):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url + "blocks/best",
                headers={'Content-Type': 'application/json'},
                timeout=timeout
            ) as response:
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
            async with session.get(
                url + "transactions/" + tx_hash + "/receipt",
                headers=headers,
                timeout=timeout
            ) as response:
                json_resp = await response.json()
                if json_resp and 'reverted' in json_resp:
                    return json_resp
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def vite_get_height(url: str):
    try:
        data = {
            "jsonrpc": "2.0",
            "id": 1, "method":
            "ledger_getSnapshotChainHeight", "params": []
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, timeout=60) as response:
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
        data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "ledger_getAccountBlocksByAddress",
            "params": [address, 0, last]
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, timeout=60) as response:
                res_data = await response.read()
                res_data = res_data.decode('utf-8')
                json_resp = json.loads(res_data)
                return json_resp['result']
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

async def vite_ledger_getAccountBlockByHash(url: str, tx_hash: str):
    try:
        data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "ledger_getAccountBlockByHash",
            "params": [tx_hash]
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, timeout=60) as response:
                res_data = await response.read()
                res_data = res_data.decode('utf-8')
                json_resp = json.loads(res_data)
                return json_resp['result']
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def vite_send_tx(
    url: str, from_address: str, to_address: str,
    amount: str, data, tokenId: str, priv
):
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
            async with session.post(url, json=payload, timeout=60) as response:
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

    async def get_faucet_coin_list(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
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
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `coin_user_reward_setting`
                    (`user_id`, `coin_name`, `user_server`)
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
            await store.openConnection()
            async with store.pool.acquire() as conn:
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

    async def insert_reward(
        self, user_id: str, reward_for: str, reward_amount: float,
        coin_name: str, reward_time: int, user_server: str
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `coin_user_reward_list`
                    (`user_id`, `reward_for`, `reward_amount`, `coin_name`, `reward_time`, `user_server`)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    await cur.execute(sql, (
                        user_id, reward_for, reward_amount, coin_name.upper(),
                        reward_time, user_server.upper()
                    ))
                    await conn.commit()
                    return True
        except Exception:
            await logchanbot("wallet insert_reward " + str(traceback.format_exc()))
        return False

class ConfirmName(disnake.ui.View):
    def __init__(self, bot, owner_id: int):
        super().__init__(timeout=15.0)
        self.value: Optional[bool] = None
        self.bot = bot
        self.owner_id = owner_id

    @disnake.ui.button(label="Yes, please!", emoji="✅", style=disnake.ButtonStyle.green)
    async def confirm(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, this is not your menu!", delete_after=5.0)
        else:
            self.value = True
            self.stop()
            await inter.response.defer()

    @disnake.ui.button(label="No", emoji="❌", style=disnake.ButtonStyle.grey)
    async def cancel(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, this is not your menu!", delete_after=5.0)
        else:
            self.value = False
            self.stop()
            await inter.response.defer()

class DepositMenu(disnake.ui.View):
    def __init__(
        self, bot,
        ctx,
        owner_id: int,
        embed,
        coin_name,
        plain_addr: str,
        pointer_message: str,
        is_fav: bool=False
    ):
        super().__init__(timeout=120.0)
        self.bot = bot
        self.ctx = ctx
        self.utils = Utils(self.bot)
        self.wallet = Wallet(self.bot)
        self.owner_id = owner_id
        self.embed = embed
        self.coin_name = coin_name
        self.plain_addr =  plain_addr
        self.pointer_message = pointer_message
        if is_fav is True:
            self.btn_balance_single_add_fav.disabled = True
            self.btn_balance_single_remove_fav.disabled = False
        else:
            self.btn_balance_single_add_fav.disabled = False
            self.btn_balance_single_remove_fav.disabled = True

    async def on_timeout(self):
        await self.ctx.edit_original_message(
            view=None
        )

    @disnake.ui.button(label="Plain", emoji="📋", style=ButtonStyle.grey, custom_id="deposit_plain_address")
    async def btn_balance_single_plain(
        self, button: disnake.ui.Button,
        inter: disnake.MessageInteraction
    ):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, that is not your menu!", delete_after=3.0)
            return
        else:
            await self.ctx.edit_original_message(content=self.plain_addr, embed=None, view=None)
            await self.ctx.followup.send(self.pointer_message, ephemeral=True)

    @disnake.ui.button(label="Add", emoji="💚", style=ButtonStyle.grey, custom_id="deposit_add_fav")
    async def btn_balance_single_add_fav(
        self, button: disnake.ui.Button,
        inter: disnake.MessageInteraction
    ):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, that is not your menu!", delete_after=3.0)
            return
        else:
            await inter.response.send_message(f"{inter.author.mention}, adding to favorite ...", ephemeral=True)
            # check if he has so many fav already.
            counting = await self.utils.check_if_fav_coin(str(inter.author.id), SERVER_BOT, None)
            if len(counting) >= 15:
                await inter.edit_original_message(
                    content=f"{inter.author.mention}, you reached maximum of favorited coins already! ({str(len(counting))})"
                )
                return
            adding = await self.utils.fav_coin_add(str(inter.author.id), SERVER_BOT, self.coin_name)
            if adding is True:
                await inter.delete_original_message()
                view = DepositMenu(
                    self.bot, self.ctx, self.owner_id, self.embed, self.coin_name,
                    self.plain_addr, self.pointer_message, is_fav=True
                )
                await self.ctx.edit_original_message(view=view)

    @disnake.ui.button(label="Remove", emoji="💙", style=ButtonStyle.grey, custom_id="deposit_remove_fav")
    async def btn_balance_single_remove_fav(
        self, button: disnake.ui.Button,
        inter: disnake.MessageInteraction
    ):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, that is not your menu!", delete_after=3.0)
            return
        else:
            await inter.response.send_message(f"{inter.author.mention}, removing from favorite ...", ephemeral=True)
            removing = await self.utils.fav_coin_remove(str(inter.author.id), SERVER_BOT, self.coin_name)
            if removing is True:
                await inter.delete_original_message()
                view = DepositMenu(
                    self.bot, self.ctx, self.owner_id, self.embed, self.coin_name,
                    self.plain_addr, self.pointer_message, is_fav=False
                )
                await self.ctx.edit_original_message(view=view)

    @disnake.ui.button(label="Balance", emoji="💰", style=ButtonStyle.grey, custom_id="deposit_balance")
    async def btn_balance_single_balance(
        self, button: disnake.ui.Button,
        inter: disnake.MessageInteraction
    ):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, that is not your menu!", delete_after=3.0)
            return
        else:
            await inter.response.send_message(f"{inter.author.mention}, checking balance ...", ephemeral=True)
            # check if he has so many fav already.
            await self.wallet.async_balance(self.ctx, self.coin_name)
            await inter.delete_original_message()


class SingleBalanceMenu(disnake.ui.View):
    def __init__(
        self, bot,
        ctx,
        owner_id: int,
        embed,
        coin_name,
        is_fav: bool=False
    ):
        super().__init__(timeout=120.0)
        self.bot = bot
        self.ctx = ctx
        self.utils = Utils(self.bot)
        self.wallet = Wallet(self.bot)
        self.owner_id = owner_id
        self.embed = embed
        self.coin_name = coin_name
        if is_fav is True:
            self.btn_balance_single_add_fav.disabled = True
            self.btn_balance_single_remove_fav.disabled = False
        else:
            self.btn_balance_single_add_fav.disabled = False
            self.btn_balance_single_remove_fav.disabled = True

    async def on_timeout(self):
        await self.ctx.edit_original_message(
            view=None
        )

    @disnake.ui.button(label="Add", emoji="💚", style=ButtonStyle.grey, custom_id="balance_single_add_fav")
    async def btn_balance_single_add_fav(
        self, button: disnake.ui.Button,
        inter: disnake.MessageInteraction
    ):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, that is not your menu!", delete_after=3.0)
            return
        else:
            await inter.response.send_message(f"{inter.author.mention}, adding to favorite ...", ephemeral=True)
            # check if he has so many fav already.
            counting = await self.utils.check_if_fav_coin(str(inter.author.id), SERVER_BOT, None)
            if len(counting) >= 15:
                await inter.edit_original_message(
                    content=f"{inter.author.mention}, you reached maximum of favorited coins already! ({str(len(counting))})"
                )
                return
            adding = await self.utils.fav_coin_add(str(inter.author.id), SERVER_BOT, self.coin_name)
            if adding is True:
                await inter.delete_original_message()
                view = SingleBalanceMenu(self.bot, self.ctx, self.owner_id, self.embed, self.coin_name, is_fav=True)
                await self.ctx.edit_original_message(view=view)

    @disnake.ui.button(label="Remove", emoji="💙", style=ButtonStyle.grey, custom_id="balance_single_remove_fav")
    async def btn_balance_single_remove_fav(
        self, button: disnake.ui.Button,
        inter: disnake.MessageInteraction
    ):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, that is not your menu!", delete_after=3.0)
            return
        else:
            await inter.response.send_message(f"{inter.author.mention}, removing from favorite ...", ephemeral=True)
            removing = await self.utils.fav_coin_remove(str(inter.author.id), SERVER_BOT, self.coin_name)
            if removing is True:
                await inter.delete_original_message()
                view = SingleBalanceMenu(self.bot, self.ctx, self.owner_id, self.embed, self.coin_name, is_fav=False)
                await self.ctx.edit_original_message(view=view)

    @disnake.ui.button(label="Deposit", emoji="↪️", style=ButtonStyle.grey, custom_id="balance_single_deposit")
    async def btn_balance_deposit_coin(
        self, button: disnake.ui.Button,
        inter: disnake.MessageInteraction
    ):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, that is not your menu!", delete_after=3.0)
            return
        else:
            # delete and show other menu
            await inter.response.send_message(f"{inter.author.mention}, loading ...", ephemeral=True)
            await self.wallet.async_deposit(self.ctx, self.coin_name)
            await inter.delete_original_message()

    @disnake.ui.button(label="All coins/tokens", emoji="💰", style=ButtonStyle.grey, custom_id="balance_single_all")
    async def btn_balance_all_coins(
        self, button: disnake.ui.Button,
        inter: disnake.MessageInteraction
    ):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, that is not your menu!", delete_after=3.0)
            return
        else:
            # delete and show other menu
            await inter.response.send_message(f"{inter.author.mention}, loading all your balance ...", ephemeral=True)
            await self.wallet.async_balances(self.ctx)
            await inter.delete_original_message()

    @disnake.ui.button(label="Support", emoji="🏢", style=ButtonStyle.link, url="https://discord.com/invite/GpHzURM")
    async def btn_balance_support(
        self, button: disnake.ui.Button,
        inter: disnake.MessageInteraction
    ):
        pass

class DropdownBalance(disnake.ui.StringSelect):
    def __init__(
            self, ctx, owner_id, bot, embed, all_userdata_balance, list_chunks, list_index,
            bl_list_by_value_chunks, list_index_value,
            sorted_by, home_embed, selected_index
        ):
        self.ctx = ctx
        self.owner_id = owner_id
        self.bot = bot
        self.utils = Utils(self.bot)
        self.embed = embed
        self.all_userdata_balance = all_userdata_balance
        self.list_chunks = list_chunks
        self.list_index = list_index
        self.bl_list_by_value_chunks = bl_list_by_value_chunks
        self.list_index_value = list_index_value
        self.sorted_by = sorted_by # ALPHA, VALUE
        self.home_embed = home_embed
        self.selected_index = selected_index
        if sorted_by == "ALPHA":
            self.index_by = list_index
            self.bulk_list = list_chunks
            select_text = "Select"
        elif sorted_by == "VALUE":
            self.index_by = list_index_value
            self.bulk_list = bl_list_by_value_chunks
            select_text = "Between"

        options = [
            disnake.SelectOption(
                label=self.index_by[c],
                description="{} {}".format(select_text, self.index_by[c]),
                value=c,
            ) for c, each in enumerate(self.bulk_list)
        ]

        super().__init__(
            placeholder="Choose menu..." if self.selected_index is None else self.index_by[self.selected_index],
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, inter: disnake.MessageInteraction):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, that is not your menu!", delete_after=3.0)
            return
        else:
            if self.values[0] is None:
                await inter.response.send_message(f"{inter.author.mention}, out of range! Try again!", ephemeral=True)
                return
            else:
                self.embed.clear_fields()
                embed = self.embed.copy()
                total_section_usd = 0.0
                for c, i in enumerate(self.bulk_list[int(self.values[0])]):
                    coin_name = list(i.keys())[0]
                    token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                    if self.sorted_by == "ALPHA":
                        v = list(i.values())[0]
                    elif self.sorted_by == "VALUE":
                        v = self.all_userdata_balance[coin_name]
                    equivalent_usd = ""
                    per_unit = None
                    price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                    if price_with:
                        per_unit = await self.utils.get_coin_price(coin_name, price_with)
                        if per_unit and per_unit['price'] and per_unit['price'] > 0:
                            per_unit = per_unit['price']
                            amount_in_usd = float(Decimal(v) * Decimal(per_unit))
                            total_section_usd += amount_in_usd
                            if amount_in_usd >= 0.01:
                                equivalent_usd = " ~ {:,.2f}$".format(amount_in_usd)
                            elif amount_in_usd >= 0.0001:
                                equivalent_usd = " ~ {:,.4f}$".format(amount_in_usd)

                    coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                    if hasattr(self.ctx, "guild") and hasattr(self.ctx.guild, "id"):
                        coin_emoji = None
                    embed.add_field(
                        name="{}{}{}".format(coin_emoji + " " if coin_emoji else "", token_display, equivalent_usd),
                        value="{}".format(num_format_coin(v)),
                        inline=True
                        )
                if total_section_usd > 0:
                    embed.set_footer(text="Estimated {}".format(" ~ {:,.4f}$".format(total_section_usd)))
                else:
                    embed.set_footer(text="Estimated N/A")
                view = BalancesMenu(
                    self.bot, self.ctx, self.owner_id, embed, self.all_userdata_balance, self.list_chunks, self.list_index,
                    self.bl_list_by_value_chunks, self.list_index_value,
                    sorted_by=self.sorted_by, home_embed=self.home_embed, selected_index=int(self.values[0])
                )
                await self.ctx.edit_original_message(content=None, embed=embed, view=view)
                await inter.response.defer()

class BalancesMenu(disnake.ui.View):
    def __init__(
        self, bot,
        ctx,
        owner_id: int,
        embed,
        all_userdata_balance,
        list_chunks,
        list_index,
        bl_list_by_value_chunks,
        list_index_value,
        sorted_by,
        home_embed,
        selected_index: int=None,
    ):
        super().__init__(timeout=120.0)
        self.bot = bot
        self.ctx = ctx
        self.embed = embed
        self.all_userdata_balance = all_userdata_balance
        self.owner_id = owner_id
        self.list_chunks = list_chunks
        self.list_index = list_index
        self.bl_list_by_value_chunks = bl_list_by_value_chunks
        self.list_index_value = list_index_value
        self.sorted_by = sorted_by
        self.home_embed = home_embed
        if len(bl_list_by_value_chunks) <= 1:
            # disable sort by VALUE
            self.btn_balance_sort_usd.disabled = True
        if len(list_chunks) <= 1:
            self.list_chunks.disabled = True

        self.add_item(DropdownBalance(
            ctx, owner_id, bot, embed, all_userdata_balance, list_chunks, list_index,
            bl_list_by_value_chunks, list_index_value,
            sorted_by, home_embed, selected_index
        ))

    async def on_timeout(self):
        await self.ctx.edit_original_message(
            view=None
        )

    @disnake.ui.button(label="Home", emoji="🏠", style=ButtonStyle.grey, custom_id="balance_home")
    async def btn_balance_home(
        self, button: disnake.ui.Button,
        inter: disnake.MessageInteraction
    ):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, that is not your menu!", delete_after=3.0)
            return
        view = BalancesMenu(
            self.bot, self.ctx, self.owner_id, self.embed, self.all_userdata_balance,
            self.list_chunks, self.list_index,
            self.bl_list_by_value_chunks, self.list_index_value,
            sorted_by="ALPHA", home_embed=self.home_embed, selected_index=None
        )
        await self.ctx.edit_original_message(content=None, embed=self.home_embed, view=view)
        await inter.response.defer()

    @disnake.ui.button(label="Sort", emoji="💲", style=ButtonStyle.grey, custom_id="balance_sort_usd")
    async def btn_balance_sort_usd(
        self, button: disnake.ui.Button,
        inter: disnake.MessageInteraction
    ):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, that is not your menu!", delete_after=3.0)
            return
        view = BalancesMenu(
            self.bot, self.ctx, self.owner_id, self.embed, self.all_userdata_balance,
            self.list_chunks, self.list_index,
            self.bl_list_by_value_chunks, self.list_index_value,
            sorted_by="VALUE", home_embed=self.home_embed, selected_index=None
        )
        await self.ctx.edit_original_message(content=None, embed=self.home_embed, view=view)
        await inter.response.defer()

    @disnake.ui.button(label="Sort", emoji="🇦", style=ButtonStyle.grey, custom_id="balance_sort_alpha")
    async def btn_balance_sort_alpha(
        self, button: disnake.ui.Button,
        inter: disnake.MessageInteraction
    ):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, that is not your menu!", delete_after=3.0)
            return
        view = BalancesMenu(
            self.bot, self.ctx, self.owner_id, self.embed, self.all_userdata_balance, 
            self.list_chunks, self.list_index,
            self.bl_list_by_value_chunks, self.list_index_value,
            sorted_by="ALPHA", home_embed=self.home_embed, selected_index=None
        )
        await self.ctx.edit_original_message(content=None, embed=self.home_embed, view=view)
        await inter.response.defer()

    @disnake.ui.button(label="Support", emoji="🏢", style=ButtonStyle.link, url="https://discord.com/invite/GpHzURM")
    async def btn_balance_support(
        self, button: disnake.ui.Button,
        inter: disnake.MessageInteraction
    ):
        pass

class WalletAPI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.utils = Utils(self.bot)
        # DB
        self.pool = None

    async def openConnection(self):
        try:
            if self.pool is None:
                self.pool = await aiomysql.create_pool(
                    host=self.bot.config['mysql']['host'], port=3306, minsize=4, maxsize=8,
                    user=self.bot.config['mysql']['user'], password=self.bot.config['mysql']['password'],
                    db=self.bot.config['mysql']['db'], cursorclass=DictCursor, autocommit=True
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def cexswap_get_all_poolshares(self, user_id: str=None, ticker: str=None):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    data_rows = []
                    sql = """ SELECT * 
                    FROM `cexswap_pools_share` 
                    """
                    if user_id is not None:
                        sql += """
                        WHERE `user_id`=%s
                        """
                        data_rows += [user_id]
                    if ticker is not None:
                        if user_id is not None:
                            sql += """
                                AND (`ticker_1_name`=%s OR `ticker_2_name`=%s)
                            """
                        else:
                            sql += """
                                WHERE `ticker_1_name`=%s OR `ticker_2_name`=%s
                            """
                        data_rows += [ticker]*2
                    await cur.execute(sql, tuple(data_rows))
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def get_coin_balance(self, coin: str):
        balance = 0.0
        coin_name = coin.upper()
        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        display_name = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
        contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
        if type_coin == "ERC-20":
            main_balance = await store.http_wallet_getbalance(
                self.bot.erc_node_list[net_name], self.bot.config['eth']['MainAddress'], contract, 16
            )
            balance = float(main_balance / 10 ** coin_decimal)
        elif type_coin in ["TRC-20", "TRC-10"]:
            main_balance = await store.trx_wallet_getbalance(
                self.bot.erc_node_list["TRX"], self.bot.config['trc']['MainAddress'], 
                coin_name, coin_decimal, type_coin, contract
            )
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
                    async with session.get(url + method, headers=headers, timeout=60) as response:
                        json_resp = await response.json()
                        if response.status == 200 or response.status == 201:
                            balance = float(Decimal(json_resp['unlocked']) / Decimal(10 ** coin_decimal))
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif type_coin == "BCN":
            url = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
            json_data = {
                "jsonrpc": "2.0",
                "id": "0",
                "method": "getBalance"
            }
            headers = {
                'Content-Type': 'application/json'
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=json_data, headers=headers, timeout=60) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            decoded_data = json.loads(res_data)
                            json_resp = decoded_data
                            balance = float(Decimal(json_resp['result']['availableBalance']) / Decimal(10 ** coin_decimal))
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
                    async with session.post(url, json=json_data, headers=headers, timeout=60) as response:
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
            json_data = {
                "jsonrpc": "2.0",
                "id": "0",
                "method": "get_balance",
                "params": {"account_index": 0, "address_indices": []}
            }
            headers = {
                'Content-Type': 'application/json'
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=json_data, headers=headers, timeout=60) as response:
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
                            uuid.uuid4()) + '", "method": "getbalance", "params": [] }', timeout=60) as response:
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
                    async with session.post(url, json=json_data, headers=headers, timeout=60) as response:
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
                    async with session.post(url, headers=headers, json=json_data, timeout=60) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            decoded_data = json.loads(res_data)
                            json_resp = decoded_data
                            balance = float(Decimal(json_resp['balance']) / Decimal(10 ** coin_decimal))
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif type_coin == "SOL":
            try:
                proxy = "http://{}:{}".format(self.bot.config['api_helper']['connect_ip'], self.bot.config['api_helper']['port_solana'])
                get_balance = await self.utils.solana_get_balance(
                    proxy + "/get_balance_solana", self.bot.erc_node_list['SOL'], self.bot.config['sol']['MainAddress'], 60
                )
                if get_balance and get_balance.get('result'):
                    balance = float(get_balance['result']['balance'] / 10 ** coin_decimal)
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
                get_token_balances = functools.partial(
                    tezos_check_token_balance, self.bot.erc_node_list['XTZ'],
                    contract, [main_address], coin_decimal, int(token_id)
                )
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
                    async with session.post(wallet_host, headers=headers, json=json_data, timeout=60) as response:
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
                get_balance = await near_check_balance_token(
                    self.bot.erc_node_list['NEAR'], token_contract, main_address, 32
                )
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
                get_token_balance = functools.partial(
                    vet_get_token_balance, self.bot.erc_node_list['VET'], contract, main_address
                )
                balance = await self.bot.loop.run_in_executor(None, get_token_balance)
                return balance / 10 ** coin_decimal
        return balance

    async def all_user_balance(
        self, user_id: str, user_server: str, coinlist
    ):
        user_server = user_server.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    user_balance_coin = {}
                    sql = """
                    SELECT (`balance`-`withdrew`+`deposited`) AS balance, `token_name` 
                    FROM `user_balance_mv_data` 
                    WHERE `user_id`=%s AND `user_server`=%s
                    """
                    await cur.execute(sql, (user_id, user_server))
                    result_balance = await cur.fetchall()
                    if result_balance:
                        for i in result_balance:
                            if i['token_name'] not in user_balance_coin:
                                user_balance_coin[i['token_name']] = Decimal(i['balance'])

                        sql = """
                        SELECT SUM(`real_amount`) AS airdrop , `token_name`
                        FROM `discord_airdrop_tmp` 
                        WHERE `from_userid`=%s AND `status`=%s
                        GROUP BY `token_name`
                        """
                        await cur.execute(sql, (user_id, "ONGOING"))
                        result_airdrop = await cur.fetchall()
                        if result_airdrop:
                            for i in result_airdrop:
                                if i['token_name'] not in user_balance_coin:
                                    user_balance_coin[i['token_name']] = 0
                                user_balance_coin[i['token_name']] -= Decimal(i['airdrop'])

                        sql = """
                        SELECT SUM(`real_amount`) AS math, `token_name`
                        FROM `discord_mathtip_tmp` 
                        WHERE `from_userid`=%s AND `status`=%s
                        GROUP BY `token_name`
                        """
                        await cur.execute(sql, (user_id, "ONGOING"))
                        result_math = await cur.fetchall()
                        if result_math:
                            for i in result_math:
                                if i['token_name'] not in user_balance_coin:
                                    user_balance_coin[i['token_name']] = 0
                                user_balance_coin[i['token_name']] -= Decimal(i['math'])

                        sql = """
                        SELECT SUM(`real_amount`) AS trivia, `token_name`
                        FROM `discord_triviatip_tmp` 
                        WHERE `from_userid`=%s AND `status`=%s
                        GROUP BY `token_name`
                        """
                        await cur.execute(sql, (user_id, "ONGOING"))
                        result_trivia = await cur.fetchall()
                        if result_trivia:
                            for i in result_trivia:
                                if i['token_name'] not in user_balance_coin:
                                    user_balance_coin[i['token_name']] = 0
                                user_balance_coin[i['token_name']] -= Decimal(i['trivia'])

                        sql = """
                        SELECT SUM(`amount_sell`) AS trade, `coin_sell`
                        FROM `open_order` 
                        WHERE `userid_sell`=%s AND `status`=%s
                        GROUP BY `coin_sell`
                        """
                        await cur.execute(sql, (user_id, "OPEN"))
                        result_trade = await cur.fetchall()
                        if result_trade:
                            for i in result_trade:
                                if i['coin_sell'] not in user_balance_coin:
                                    user_balance_coin[i['coin_sell']] = 0
                                user_balance_coin[i['coin_sell']] -= Decimal(i['trade'])

                        sql = """
                        SELECT SUM(`amount`) AS raffle, `coin_name`
                        FROM `guild_raffle_entries` 
                        WHERE `user_id`=%s AND `user_server`=%s AND `status`=%s
                        GROUP BY `coin_name`
                        """
                        await cur.execute(sql, (user_id, user_server, "REGISTERED"))
                        result_raffle = await cur.fetchall()
                        if result_raffle:
                            for i in result_raffle:
                                if i['coin_name'] not in user_balance_coin:
                                    user_balance_coin[i['coin_name']] = 0
                                user_balance_coin[i['coin_name']] -= Decimal(i['raffle'])

                        sql = """
                        SELECT SUM(`init_amount`) AS party_init, `token_name`
                        FROM `discord_partydrop_tmp` 
                        WHERE `from_userid`=%s  AND `status`=%s
                        GROUP BY `token_name`
                        """
                        await cur.execute(sql, (user_id, "ONGOING"))
                        result_party_init = await cur.fetchall()
                        if result_party_init:
                            for i in result_party_init:
                                if i['token_name'] not in user_balance_coin:
                                    user_balance_coin[i['token_name']] = 0
                                user_balance_coin[i['token_name']] -= Decimal(i['party_init'])

                        sql = """
                        SELECT SUM(`joined_amount`) AS party_join, `token_name`
                        FROM `discord_partydrop_join` 
                        WHERE `attendant_id`=%s AND `status`=%s
                        GROUP BY `token_name`
                        """
                        await cur.execute(sql, (user_id, "ONGOING"))
                        result_party_join = await cur.fetchall()
                        if result_party_join:
                            for i in result_party_join:
                                if i['token_name'] not in user_balance_coin:
                                    user_balance_coin[i['token_name']] = 0
                                user_balance_coin[i['token_name']] -= Decimal(i['party_join'])

                        sql = """
                        SELECT SUM(`real_amount`) AS quick, `token_name`
                        FROM `discord_quickdrop` 
                        WHERE `from_userid`=%s AND `status`=%s
                        GROUP BY `token_name`
                        """
                        await cur.execute(sql, (user_id, "ONGOING"))
                        result_quick = await cur.fetchall()
                        if result_quick:
                            for i in result_quick:
                                if i['token_name'] not in user_balance_coin:
                                    user_balance_coin[i['token_name']] = 0
                                user_balance_coin[i['token_name']] -= Decimal(i['quick'])

                        sql = """
                        SELECT SUM(`real_amount`) AS talk, `token_name`
                        FROM `discord_talkdrop_tmp` 
                        WHERE `from_userid`=%s AND `status`=%s
                        GROUP BY `token_name`
                        """
                        await cur.execute(sql, (user_id, "ONGOING"))
                        result_talk = await cur.fetchall()
                        if result_talk:
                            for i in result_talk:
                                if i['token_name'] not in user_balance_coin:
                                    user_balance_coin[i['token_name']] = 0
                                user_balance_coin[i['token_name']] -= Decimal(i['talk'])
                    for i in coinlist:
                        if i not in user_balance_coin.keys():
                            user_balance_coin[i] = Decimal(0)
                    return user_balance_coin
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet user_balance " +str(traceback.format_exc()))

    async def user_balance(
        self, user_id: str, coin: str, address: str, coin_family: str, top_block: int,
        confirmed_depth: int = 0, user_server: str = 'DISCORD'
    ):
        # address: TRTL/BCN/XMR = paymentId
        token_name = coin.upper()
        user_server = user_server.upper()
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
                            query_param += [address, token_name, top_block, user_server]
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
                            WHERE `user_id`=%s AND `coin_name`=%s 
                            AND (`category` = %s or `category` = %s) 
                            AND `confirmations`>=%s AND `amount`>0), 0))
                            """
                            query_param += [user_id, token_name, 'receive', 'generate', confirmed_depth]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                            FROM `doge_get_transfers` 
                            WHERE `user_id`=%s AND `coin_name`=%s AND `category` = %s 
                            AND `confirmations`>=%s AND `amount`>0), 0))
                            """
                            query_param += [user_id, token_name, 'receive', confirmed_depth]
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
                            WHERE `user_id`=%s 
                            AND `coin_name`=%s AND `category` = %s 
                            AND `time_insert`<=%s AND `amount`>0), 0))
                                   """
                            query_param += [user_id, token_name, 'received', int(time.time()) - nos_block]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(`amount`)  
                            FROM `neo_get_transfers` 
                            WHERE `user_id`=%s 
                            AND `coin_name`=%s AND `category` = %s 
                            AND `confirmations`<=%s AND `amount`>0), 0))
                                   """
                            query_param += [user_id, token_name, 'received', nos_block]
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
                            query_param += [address, token_name, int(time.time()) - nos_block]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(`amount`)  
                            FROM `xch_get_transfers` 
                            WHERE `address`=%s AND `coin_name`=%s AND `amount`>0 AND `height`<%s), 0))
                            """
                            query_param += [address, token_name, top_block]
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
                            query_param += [address_memo[0], address_memo[2], token_name, int(time.time()) - nos_block, user_server]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                            FROM `vite_get_transfers` 
                            WHERE `address`=%s AND `memo`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `height`<%s AND `user_server`=%s), 0))
                            """
                            query_param += [address_memo[0], address_memo[2], token_name, top_block, user_server]
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
                            query_param += [address_memo[0], address_memo[2], token_name, int(time.time()) - nos_block, user_server]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                            FROM `hnt_get_transfers` 
                            WHERE `address`=%s AND `memo`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `height`<%s AND `user_server`=%s), 0))
                            """
                            query_param += [address_memo[0], address_memo[2], token_name, top_block, user_server]

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
                            query_param += [address, token_name, int(time.time()) - nos_block, user_server]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                            FROM `xrp_get_transfers` 
                            WHERE `destination_tag`=%s AND `coin_name`=%s AND `amount`>0 AND `height`<%s AND `user_server`=%s), 0))
                            """
                            query_param += [address, token_name, top_block, user_server]
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
                            query_param += [address_memo[0], address_memo[2], token_name, int(time.time()) - nos_block, user_server]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                            FROM `xlm_get_transfers` 
                            WHERE `address`=%s AND `memo`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `height`<%s AND `user_server`=%s), 0))
                            """
                            query_param += [address_memo[0], address_memo[2], token_name, top_block, user_server]
                    elif coin_family == "COSMOS":
                        sql += """
                        - (SELECT IFNULL((SELECT SUM(amount+withdraw_fee)  
                        FROM `cosmos_external_tx` 
                        WHERE `user_id`=%s AND `coin_name`=%s 
                        AND `user_server`=%s AND `crediting`=%s AND `success`=1), 0))
                        """
                        query_param += [user_id, token_name, user_server, "YES"]
                        
                        address_memo = address.split()
                        if top_block is None:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                                      FROM `cosmos_get_transfers` 
                                      WHERE `address`=%s AND `memo`=%s 
                                      AND `coin_name`=%s AND `amount`>0 
                                      AND `time_insert`< %s AND `user_server`=%s), 0))
                            """
                            query_param += [address_memo[0], address_memo[2], token_name, int(time.time()) - nos_block, user_server]
                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount)  
                            FROM `cosmos_get_transfers` 
                            WHERE `address`=%s AND `memo`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `height`<%s AND `user_server`=%s), 0))
                            """
                            query_param += [address_memo[0], address_memo[2], token_name, top_block, user_server]
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
                            query_param += [address, "incoming", token_name, int(time.time()) - nos_block, user_server]

                        else:
                            sql += """
                            + (SELECT IFNULL((SELECT SUM(amount) 
                            FROM `ada_get_transfers` 
                            WHERE `output_address`=%s AND `direction`=%s AND `coin_name`=%s 
                            AND `amount`>0 AND `inserted_at_height`<%s AND `user_server`=%s), 0))
                            """
                            query_param += [address, "incoming", token_name, top_block, user_server]
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
                    balance['mv_balance'] = float("%.12f" % mv_balance) if mv_balance else 0
                    balance['adjust'] = float("%.12f" % balance['mv_balance'])
                except Exception:
                    print("issue user_balance coin name: {}".format(token_name))
                    traceback.print_exc(file=sys.stdout)
                # Negative check
                try:
                    if balance['adjust'] < 0:
                        msg_negative = "Negative balance detected:\nServer:" + user_server + "\nUser: " + user_id + \
                            "\nToken: " + token_name + "\nBalance: " + str(balance['adjust'])
                        await logchanbot(msg_negative)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                return balance
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet user_balance " +str(traceback.format_exc()))

    async def get_block_height(self, type_coin: str, coin: str, net_name: str = None):
        height = None
        coin_name = coin.upper()
        try:
            if type_coin in ["ERC-20", "TRC-20"]:
                height = await self.utils.async_get_cache_kv(
                    "block",
                    f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{net_name}"
                )
            elif type_coin in ["XLM", "NEO", "VITE"]:
                height = await self.utils.async_get_cache_kv(
                    "block",
                    f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{type_coin}"
                )
            else:
                height = await self.utils.async_get_cache_kv(
                    "block",
                    f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}"
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return height

    async def generate_qr_address(
            self,
            address: str
    ):
        # return path to image
        # address = wallet['balance_wallet_address']
        # return address if success, else None
        address_path = address.replace('{', '_').replace(
            '}', '_').replace(':', '_').replace('"', "_").replace(',', "_").replace(' ', "_")
        if not os.path.exists(self.bot.config['storage']['path_deposit_qr_create'] + address_path + ".png"):
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
                img.save(self.bot.config['storage']['path_deposit_qr_create'] + address_path + ".png")
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
                        sql = """ SELECT `id`, `destination_tag` 
                        FROM `xrp_user` ORDER BY `id` DESC LIMIT 1
                        """
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
                cn_addressvalidation.cn_make_integrated(
                    main_address, get_prefix_char, get_prefix, get_addrlen,
                    balance_address['payment_id'])['integrated_address']
            elif type_coin.upper() == "XMR":
                # passed test WOW
                main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                balance_address = await self.make_integrated_address_xmr(main_address, coin_name)
            elif type_coin.upper() == "NANO":
                walletkey = decrypt_string(getattr(getattr(self.bot.coin_list, coin_name), "walletkey"))
                balance_address = await self.call_nano(
                    coin_name, payload='{ "action": "account_create", "wallet": "' + walletkey + '" }'
                )
            elif type_coin.upper() == "BTC":
                naming = self.bot.config['kv_db']['prefix'] + "_" + user_server + "_" + str(user_id)
                payload = f'"{naming}"'
                if coin_name in ["BTCZ", "VTC", "ZEC", "FLUX"]:
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
            elif type_coin.upper() == "COSMOS":
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
                proxy = "http://{}:{}".format(self.bot.config['api_helper']['connect_ip'], self.bot.config['api_helper']['port_solana'])
                create_addr = await self.utils.solana_create_address(
                    proxy + "/create_address", timeout=32
                )
                balance_address['balance_wallet_address'] = create_addr['address']
                balance_address['secret_key_hex'] = create_addr['secret_key_hex']
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
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """
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
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """
                            await cur.execute(sql, (
                            str(user_id), user_id_erc20, type_coin_user, balance_address['address'], int(time.time()),
                            encrypt_string(balance_address['key']), int(time.time()), user_server,
                            chat_id, is_discord_guild))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                        elif type_coin == "XTZ":
                            sql = """ INSERT INTO `tezos_user` (`user_id`, `user_id_fa20`, `type`, `balance_wallet_address`, `address_ts`, 
                                `seed`, `key`, `called_Update`, `user_server`, `chat_id`, `is_discord_guild`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """
                            await cur.execute(sql, (
                                str(user_id), user_id_erc20, type_coin_user, balance_address['address'], int(time.time()),
                                encrypt_string(balance_address['seed']), encrypt_string(balance_address['key']),
                                int(time.time()), user_server, chat_id, is_discord_guild
                            ))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                        elif type_coin == "XRP":
                            sql = """ INSERT INTO `xrp_user` (`user_id`, `user_id_asset`, `type`, 
                                `main_address`, `destination_tag`, `balance_wallet_address`, `address_ts`,
                                `user_server`, `chat_id`, `is_discord_guild`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """
                            await cur.execute(sql, (
                                str(user_id), user_id_erc20, type_coin_user, balance_address['address'],
                                balance_address['destination_tag'], balance_address['balance_wallet_address'],
                                int(time.time()), user_server, chat_id, is_discord_guild
                            ))
                            await conn.commit()
                            return balance_address
                        elif type_coin == "NEAR":
                            sql = """ INSERT INTO `near_user` (`user_id`, `user_id_near`, `coin_name`, 
                                `type`, `balance_wallet_address`, `address_ts`, 
                                `privateKey`, `seed`, `called_Update`, `user_server`, `chat_id`, `is_discord_guild`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """
                            await cur.execute(sql, (
                                str(user_id), user_id_erc20, coin_name, type_coin_user, balance_address['address'], int(time.time()), 
                                encrypt_string(balance_address['key']), encrypt_string(balance_address['seed']), int(time.time()),
                                user_server, chat_id, is_discord_guild
                            ))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                        elif netname and netname in ["TRX"]:
                            sql = """ INSERT INTO `trc20_user` (`user_id`, `user_id_trc20`, `type`, `balance_wallet_address`,
                                `hex_address`, `address_ts`, `private_key`, `public_key`, `called_Update`, `user_server`, 
                                `chat_id`, `is_discord_guild`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """
                            await cur.execute(sql, (
                                str(user_id), user_id_erc20, type_coin_user, w['base58check_address'], w['hex_address'],
                                int(time.time()), encrypt_string(str(w['private_key'])), w['public_key'], int(time.time()),
                                user_server, chat_id, is_discord_guild
                            ))
                            await conn.commit()
                            return {'balance_wallet_address': w['base58check_address']}
                        elif type_coin.upper() in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                            sql = """ INSERT INTO cn_user_paymentid (`coin_name`, `user_id`, `user_id_coin`, `main_address`, `paymentid`, 
                                `balance_wallet_address`, `paymentid_ts`, `user_server`, `chat_id`, `is_discord_guild`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """
                            await cur.execute(sql, (
                                coin_name, str(user_id), "{}_{}".format(user_id, coin_name), main_address,
                                balance_address['payment_id'],
                                balance_address['integrated_address'], int(time.time()), user_server, chat_id,
                                is_discord_guild
                            ))
                            await conn.commit()
                            return {
                                'balance_wallet_address': balance_address['integrated_address'],
                                'paymentid': balance_address['payment_id']
                            }
                        elif type_coin.upper() == "NANO":
                            sql = """ INSERT INTO `nano_user` (`coin_name`, `user_id`, `user_id_coin`,
                                `balance_wallet_address`, `address_ts`, `user_server`, `chat_id`, `is_discord_guild`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                """
                            await cur.execute(sql, (
                                coin_name, str(user_id), "{}_{}".format(user_id, coin_name), balance_address['account'],
                                int(time.time()), user_server, chat_id, is_discord_guild
                            ))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['account']}
                        elif type_coin.upper() == "BTC":
                            sql = """ INSERT INTO `doge_user` (`coin_name`, `user_id`, `user_id_coin`, `balance_wallet_address`,
                                `address_ts`, `privateKey`, `user_server`, `chat_id`, `is_discord_guild`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """
                            await cur.execute(sql, (
                                coin_name, str(user_id), "{}_{}".format(user_id, coin_name), balance_address['address'],
                                int(time.time()),
                                encrypt_string(balance_address['privateKey']), user_server, chat_id, is_discord_guild
                            ))
                            await conn.commit()
                            return {
                                'balance_wallet_address': balance_address['address']
                            }
                        elif type_coin.upper() == "NEO":
                            sql = """ INSERT INTO `neo_user` (`user_id`, `balance_wallet_address`, 
                                `address_ts`, `privateKey`, `user_server`, `chat_id`, `is_discord_guild`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """
                            await cur.execute(sql, (
                                str(user_id), balance_address['address'], 
                                int(time.time()), encrypt_string(balance_address['privateKey']), 
                                user_server, chat_id, is_discord_guild
                            ))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                        elif type_coin.upper() == "CHIA":
                            sql = """ INSERT INTO `xch_user` (`coin_name`, `user_id`, 
                                `user_id_coin`, `balance_wallet_address`, `address_ts`, `user_server`, `chat_id`, `is_discord_guild`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                """
                            await cur.execute(sql, (
                                coin_name, str(user_id), "{}_{}".format(user_id, coin_name), balance_address['address'],
                                int(time.time()), user_server, chat_id, is_discord_guild
                            ))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['address']}
                        elif type_coin.upper() == "HNT":
                            sql = """ INSERT INTO `hnt_user` (`coin_name`, `user_id`, `main_address`, 
                                `balance_wallet_address`, `memo`, `address_ts`, `user_server`, `chat_id`, `is_discord_guild`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """
                            await cur.execute(sql, (
                                coin_name, str(user_id), main_address, balance_address['balance_wallet_address'], memo,
                                int(time.time()), user_server, chat_id, is_discord_guild
                            ))
                            await conn.commit()
                            return balance_address
                        elif type_coin.upper() == "XLM":
                            sql = """ INSERT INTO `xlm_user` (`coin_name`, `user_id`, `main_address`, 
                                `balance_wallet_address`, `memo`, `address_ts`, `user_server`, `chat_id`, `is_discord_guild`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """
                            await cur.execute(sql, (
                                coin_name, str(user_id), main_address, balance_address['balance_wallet_address'], memo,
                                int(time.time()), user_server, chat_id, is_discord_guild
                            ))
                            await conn.commit()
                            return balance_address
                        elif type_coin.upper() == "COSMOS":
                            sql = """ INSERT INTO `cosmos_user` (`coin_name`, `user_id`, `main_address`, 
                                `balance_wallet_address`, `memo`, `address_ts`, `user_server`, `chat_id`, `is_discord_guild`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """
                            await cur.execute(sql, (
                                coin_name, str(user_id), main_address, balance_address['balance_wallet_address'], memo,
                                int(time.time()), user_server, chat_id, is_discord_guild
                            ))
                            await conn.commit()
                            return balance_address
                        elif type_coin.upper() == "ADA":
                            sql = """ INSERT INTO `ada_user` (`user_id`, `wallet_name`, `balance_wallet_address`, 
                                `address_ts`, `user_server`, `chat_id`, `is_discord_guild`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s);
                                UPDATE `ada_wallets` SET `used_address`=`used_address`+1 WHERE `wallet_name`=%s LIMIT 1; """
                            await cur.execute(sql, (
                                str(user_id), balance_address['wallet_name'], balance_address['address'], int(time.time()),
                                user_server, chat_id, is_discord_guild, balance_address['wallet_name']
                            ))
                            await conn.commit()
                            return {
                                'balance_wallet_address': balance_address['address']
                            }
                        elif type_coin.upper() == "SOL":
                            sql = """ INSERT INTO `sol_user` (`user_id`, `balance_wallet_address`, 
                                `address_ts`, `secret_key_hex`, `called_Update`, `user_server`, `chat_id`, `is_discord_guild`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                """
                            await cur.execute(sql, (
                                str(user_id), balance_address['balance_wallet_address'], int(time.time()),
                                encrypt_string(balance_address['secret_key_hex']), int(time.time()), user_server, chat_id,
                                is_discord_guild
                            ))
                            await conn.commit()
                            return {'balance_wallet_address': balance_address['balance_wallet_address']}
                        elif type_coin.upper() == "VET":
                            sql = """ INSERT INTO `vet_user` (`user_id`, `balance_wallet_address`, 
                                `address_ts`, `key`, `json_dump`, `called_Update`, `user_server`, `chat_id`, `is_discord_guild`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """
                            await cur.execute(sql, (
                                str(user_id), balance_address['balance_wallet_address'], int(time.time()),
                                encrypt_string(balance_address['key']), encrypt_string(balance_address['json_dump']),
                                int(time.time()), user_server, chat_id, is_discord_guild
                            ))
                            await conn.commit()
                            return {
                                'balance_wallet_address': balance_address['balance_wallet_address']
                            }
                        elif type_coin.upper() == "VITE":
                            sql = """ INSERT INTO `vite_user` (`coin_name`, `user_id`, `main_address`, 
                                `balance_wallet_address`, `memo`, `address_ts`, `user_server`, `chat_id`, `is_discord_guild`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """
                            await cur.execute(sql, (
                                coin_name, str(user_id), main_address, balance_address['balance_wallet_address'], memo,
                                int(time.time()), user_server, chat_id, is_discord_guild
                            ))
                            await conn.commit()
                            return balance_address
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def sql_get_userwallet(
        self, user_id, coin: str, netname: str, type_coin: str,
        user_server: str = 'DISCORD', chat_id: int = 0
    ):
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
                            AND `user_id_erc20`=%s AND `user_server`=%s LIMIT 1
                            """
                        await cur.execute(sql, (str(user_id), user_id_erc20, user_server))
                        result = await cur.fetchone()
                        if result:
                            return result
                    elif netname and netname in ["TRX"]:
                        sql = """ SELECT * FROM `trc20_user` WHERE `user_id`=%s 
                            AND `user_id_trc20`=%s AND `user_server`=%s LIMIT 1
                            """
                        await cur.execute(sql, (str(user_id), user_id_erc20, user_server))
                        result = await cur.fetchone()
                        if result:
                            return result
                    elif type_coin.upper() == "ZIL":
                        sql = """ SELECT * FROM `zil_user` WHERE `user_id`=%s 
                            AND `user_id_asset`=%s AND `user_server`=%s LIMIT 1
                            """
                        await cur.execute(sql, (str(user_id), user_id_erc20, user_server))
                        result = await cur.fetchone()
                        if result:
                            return result
                    elif type_coin.upper() == "XTZ":
                        sql = """ SELECT * FROM `tezos_user` WHERE `user_id`=%s 
                            AND `user_id_fa20`=%s AND `user_server`=%s LIMIT 1
                            """
                        await cur.execute(sql, (str(user_id), user_id_erc20, user_server))
                        result = await cur.fetchone()
                        if result:
                            return result
                    elif type_coin.upper() == "XRP":
                        sql = """ SELECT * FROM `xrp_user` WHERE `user_id`=%s 
                            AND `user_id_asset`=%s AND `user_server`=%s LIMIT 1
                            """
                        await cur.execute(sql, (str(user_id), user_id_erc20, user_server))
                        result = await cur.fetchone()
                        if result:
                            return result
                    elif type_coin.upper() == "NEAR":
                        sql = """ SELECT * FROM `near_user` WHERE `user_id`=%s 
                            AND `user_id_near`=%s AND `coin_name`=%s AND `user_server`=%s LIMIT 1
                            """
                        await cur.execute(sql, (str(user_id), user_id_erc20, coin_name, user_server))
                        result = await cur.fetchone()
                        if result:
                            return result
                    elif type_coin.upper() in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        sql = """ SELECT * FROM `cn_user_paymentid` WHERE `user_id`=%s 
                            AND `coin_name`=%s AND `user_server`=%s LIMIT 1
                            """
                        await cur.execute(sql, (str(user_id), coin_name, user_server))
                        result = await cur.fetchone()
                        if result:
                            return result
                    elif type_coin.upper() == "NANO":
                        sql = """ SELECT * FROM `nano_user` WHERE `user_id`=%s 
                            AND `coin_name`=%s AND `user_server`=%s LIMIT 1
                            """
                        await cur.execute(sql, (str(user_id), coin_name, user_server))
                        result = await cur.fetchone()
                        if result:
                            return result
                    elif type_coin.upper() == "BTC":
                        sql = """ SELECT * FROM `doge_user` WHERE `user_id`=%s 
                            AND `coin_name`=%s AND `user_server`=%s LIMIT 1
                            """
                        await cur.execute(sql, (str(user_id), coin_name, user_server))
                        result = await cur.fetchone()
                        if result:
                            return result
                    elif type_coin.upper() == "NEO":
                        sql = """ SELECT * FROM `neo_user` WHERE `user_id`=%s 
                            AND `user_server`=%s LIMIT 1
                            """
                        await cur.execute(sql, (str(user_id), user_server))
                        result = await cur.fetchone()
                        if result:
                            return result
                    elif type_coin.upper() == "CHIA":
                        sql = """ SELECT * FROM `xch_user` WHERE `user_id`=%s 
                            AND `coin_name`=%s AND `user_server`=%s LIMIT 1
                            """
                        await cur.execute(sql, (str(user_id), coin_name, user_server))
                        result = await cur.fetchone()
                        if result:
                            return result
                    elif type_coin.upper() == "HNT":
                        sql = """ SELECT * FROM `hnt_user` WHERE `user_id`=%s 
                            AND `coin_name`=%s AND `user_server`=%s LIMIT 1
                            """
                        await cur.execute(sql, (str(user_id), coin_name, user_server))
                        result = await cur.fetchone()
                        if result:
                            return result
                    elif type_coin.upper() == "XLM":
                        sql = """ SELECT * FROM `xlm_user` WHERE `user_id`=%s 
                            AND `user_server`=%s LIMIT 1
                            """
                        await cur.execute(sql, (str(user_id), user_server))
                        result = await cur.fetchone()
                        if result:
                            return result
                    elif type_coin.upper() == "COSMOS":
                        sql = """ SELECT * FROM `cosmos_user` WHERE `user_id`=%s 
                            AND `user_server`=%s AND `coin_name`=%s LIMIT 1
                            """
                        await cur.execute(sql, (str(user_id), user_server, coin_name))
                        result = await cur.fetchone()
                        if result:
                            return result
                    elif type_coin.upper() == "VITE":
                        sql = """ SELECT * FROM `vite_user` WHERE `user_id`=%s 
                            AND `user_server`=%s LIMIT 1
                            """
                        await cur.execute(sql, (str(user_id), user_server))
                        result = await cur.fetchone()
                        if result:
                            return result
                    elif type_coin.upper() == "ADA":
                        sql = """ SELECT * FROM `ada_user` 
                            WHERE `user_id`=%s AND `user_server`=%s LIMIT 1
                            """
                        await cur.execute(sql, (str(user_id), user_server))
                        result = await cur.fetchone()
                        if result:
                            return result
                    elif type_coin.upper() == "SOL":
                        sql = """ SELECT * FROM `sol_user` 
                            WHERE `user_id`=%s AND `user_server`=%s LIMIT 1
                            """
                        await cur.execute(sql, (str(user_id), user_server))
                        result = await cur.fetchone()
                        if result:
                            return result
                    elif type_coin.upper() == "VET":
                        sql = """ SELECT * FROM `vet_user` 
                            WHERE `user_id`=%s AND `user_server`=%s LIMIT 1
                            """
                        await cur.execute(sql, (str(user_id), user_server))
                        result = await cur.fetchone()
                        if result:
                            return result
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
        get_wallet_balance = await self.call_nano(
            coin_name, payload='{ "action": "wallet_balances", "wallet": "' + walletkey + '" }'
        )
        if get_wallet_balance and 'balances' in get_wallet_balance:
            return get_wallet_balance['balances']
        return None

    async def nano_sendtoaddress(
        self, source: str, to_address: str, atomic_amount: int, coin: str
    ) -> str:
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
        valid_address = await self.call_nano(
            coin_name,
            payload='{ "action": "validate_account_number", "account": "' + account + '" }'
        )
        if valid_address and valid_address['valid'] == "1":
            return True
        return None

    async def send_external_nano(
        self, main_address: str, user_from: str, amount: float,
        to_address: str, coin: str, coin_decimal
    ):
        coin_name = coin.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    tx_hash = await self.nano_sendtoaddress(
                        main_address, to_address, int(Decimal(amount) * 10 ** coin_decimal), coin_name
                    )
                    if tx_hash:
                        updateTime = int(time.time())
                        async with conn.cursor() as cur:
                            sql = """
                            INSERT INTO nano_external_tx 
                            (`coin_name`, `user_id`, `amount`, `decimal`, `to_address`, `date`, `tx_hash`) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """
                            await cur.execute(sql, (
                                coin_name, user_from, amount, coin_decimal,
                                to_address, int(time.time()), tx_hash['block'],))
                            await conn.commit()
                            return tx_hash
        except Exception:
            await logchanbot("wallet send_external_nano " + str(traceback.format_exc()))
        return None

    async def send_external_erc20_nostore(
        self, url: str, network: str, from_address: str, from_key: str,
        to_address: str, amount: float,
        coin_decimal: int, chain_id: str = None, contract: str = None
    ):
        try:
            # HTTPProvider:
            w3 = Web3(Web3.HTTPProvider(url))
            signed_txn = None
            sent_tx = None
            if contract is None:
                # Main Token
                if network == "MATIC":
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(from_address), 'pending')
                else:
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(from_address))
                # get gas price
                gasPrice = w3.eth.gasPrice

                estimateGas = w3.eth.estimateGas(
                    {'to': w3.toChecksumAddress(to_address), 'from': w3.toChecksumAddress(from_address),
                     'value': int(amount * 10 ** coin_decimal)})

                atomic_amount = int(amount * 10 ** 18)
                transaction = {
                    'from': w3.toChecksumAddress(from_address),
                    'to': w3.toChecksumAddress(to_address),
                    'value': atomic_amount,
                    'nonce': nonce,
                    'gasPrice': gasPrice,
                    'gas': estimateGas,
                    'chainId': chain_id
                }
                try:
                    signed_txn = w3.eth.account.sign_transaction(transaction, private_key=from_key)
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
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(from_address), 'pending')
                else:
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(from_address))

                unicorn_txn = unicorns.functions.transfer(
                    w3.toChecksumAddress(to_address),
                    int(amount * 10 ** coin_decimal)  # amount to send
                ).buildTransaction({
                    'from': w3.toChecksumAddress(from_address),
                    'gasPrice': w3.eth.gasPrice,
                    'nonce': nonce,
                    'chainId': chain_id
                })

                signed_txn = w3.eth.account.signTransaction(unicorn_txn, private_key=from_key)
                sent_tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
            if signed_txn and sent_tx:
                return sent_tx.hex()
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet send_external_erc20 " + str(traceback.format_exc()))
        return None

    async def call_xch(
        self, method_name: str, coin: str, payload: Dict = None
    ) -> Dict:
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

    async def send_external_xch(
        self, user_from: str, amount: float, to_address: str, coin: str, coin_decimal: int,
        tx_fee: float, withdraw_fee: float, user_server: str = 'DISCORD'
    ):
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
                            sql = """
                            INSERT INTO xch_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`,
                            `withdraw_fee`, `decimal`, `to_address`, `date`, `tx_hash`, `user_server`) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            await cur.execute(sql, (
                                coin_name, user_from, amount, float(result['tx_hash']['fee_amount'] / 10 ** coin_decimal),
                                withdraw_fee, coin_decimal, to_address, int(time.time()), result['tx_hash']['name'],
                                user_server
                                ))
                            await conn.commit()
                            return result['tx_hash']['name']
        except Exception:
            await logchanbot("wallet send_external_xch " + str(traceback.format_exc()))
        return None

    async def call_neo(self, method_name: str, payload) -> Dict:
        timeout = 64
        coin_name = "NEO"
        if not hasattr(self.bot.coin_list, coin_name):
            return None
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
                        sql = """
                        INSERT INTO neo_external_tx 
                        (`coin_name`, `user_id`, `coin_decimal`, `contract`, `real_amount`, 
                        `real_external_fee`, `to_address`, `date`, `tx_hash`, `tx_json`, `user_server`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        await cur.execute(sql, (
                            coin_name, user_from, coin_decimal, contract, 
                            amount, tx_fee, to_address, int(time.time()), 
                            result['result']['hash'], json.dumps(result['result']), user_server
                        ))
                        await conn.commit()
                        return result['result']['hash']
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet send_external_neo " + str(traceback.format_exc()))
        return False

    async def call_doge(self, method_name: str, coin: str, payload: str = None) -> Dict:
        timeout = 150
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
        except (aiohttp.client_exceptions.ServerDisconnectedError, aiohttp.client_exceptions.ClientOSError):
            print("call_doge: got disconnected for coin: {}".format(coin_name))
        except asyncio.TimeoutError:
            print('TIMEOUT: method_name: {} - COIN: {} - timeout {}'.format(method_name, coin.upper(), timeout))
            await logchanbot(
                'call_doge: method_name: {} - COIN: {} - timeout {}'.format(method_name, coin.upper(), timeout))
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def send_external_doge_nostore(
        self, user_from: str, amount: float, to_address: str, coin: str
    ):
        coin_name = coin.upper()
        try:
            comment = user_from
            comment_to = to_address
            payload = f'"{to_address}", {amount}, "{comment}", "{comment_to}", false'
            if getattr(getattr(self.bot.coin_list, coin_name), "coin_has_pos") == 1:
                payload = f'"{to_address}", {amount}, "{comment}", "{comment_to}"'
            txHash = await self.call_doge('sendtoaddress', coin_name, payload=payload)
            if txHash is not None:
                return txHash
        except Exception:
            await logchanbot("wallet send_external_doge " + str(traceback.format_exc()))
        return None

    async def send_external_doge(
        self, user_from: str, amount: float, to_address: str, coin: str, tx_fee: float,
        withdraw_fee: float, user_server: str
    ):
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
                        sql = """
                        INSERT INTO doge_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`, 
                        `withdraw_fee`, `to_address`, `date`, `tx_hash`, `user_server`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        await cur.execute(sql, (
                            coin_name, user_from, amount, tx_fee, withdraw_fee,
                            to_address, int(time.time()), txHash, user_server
                        ))
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
            _http_client = AsyncClient(
                limits=Limits(max_connections=100, max_keepalive_connections=20),
                timeout=Timeout(timeout=10, connect=5, read=5)
            )
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

    async def call_aiohttp_wallet_xmr_bcn(
        self, method_name: str, coin: str, time_out: int = None,
        payload: Dict = None
    ) -> Dict:
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
                            method_name, coin_name, timeout, json.dumps(payload)
                        )
                    )
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
                        'call_aiohttp_wallet: {} coin_name {} - timeout {}\nfull_payload:\n{}'.format(
                            method_name, coin_name, timeout, json.dumps(payload)
                        )
                    )
                    print('TIMEOUT: {} coin_name {} - timeout {}'.format(method_name, coin_name, timeout))
                    return None
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot("wallet call_aiohttp_wallet_xmr_bcn " + str(traceback.format_exc()))
                    return None
        except asyncio.TimeoutError:
            await logchanbot(
                'call_aiohttp_wallet: method_name: {} - coin_family: {} - timeout {}'.format(
                    method_name, coin_family, timeout
                )
            )
            print('TIMEOUT: method_name: {} - coin_family: {} - timeout {}'.format(method_name, coin_family, timeout))
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet call_aiohttp_wallet_xmr_bcn " + str(traceback.format_exc()))

    async def send_external_xmr_nostore(
        self, amount: float, to_address: str,
        coin_name: str, coin_decimal: int, timeout: int=120
    ):
        try:
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
            result = await self.call_aiohttp_wallet_xmr_bcn(
                'transfer', coin_name, time_out=timeout, payload=payload
            )
            if result and 'tx_hash' in result and 'tx_key' in result:
                return result
        except Exception:
            await logchanbot("wallet send_external_xmr " + str(traceback.format_exc()))
        return None

    async def send_external_xmr(
        self, type_coin: str, from_address: str, user_from: str, amount: float, to_address: str,
        coin: str, coin_decimal: int, tx_fee: float, withdraw_fee: float, is_fee_per_byte: int,
        get_mixin: int, user_server: str, wallet_api_url: str = None,
        wallet_api_header: str = None, paymentId: str = None
    ):
        coin_name = coin.upper()
        user_server = user_server.upper()
        time_out = 150
        if coin_name == "DEGO":
            time_out = 300
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
                result = await self.call_aiohttp_wallet_xmr_bcn(
                    'transfer', coin_name, time_out=time_out, payload=payload
                )
                if result and 'tx_hash' in result and 'tx_key' in result:
                    await self.openConnection()
                    async with self.pool.acquire() as conn:
                        async with conn.cursor() as cur:
                            sql = """
                            INSERT INTO cn_external_tx (`coin_name`, `user_id`, `amount`, `tx_fee`,
                            `withdraw_fee`, `decimal`, `to_address`, `date`, `tx_hash`, `tx_key`, `user_server`) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            await cur.execute(sql, (
                                coin_name, user_from, amount, tx_fee, withdraw_fee, coin_decimal, to_address,
                                int(time.time()), result['tx_hash'], result['tx_key'], user_server
                            ))
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
                result = await self.call_aiohttp_wallet_xmr_bcn(
                    'sendTransaction', coin_name, time_out=time_out, payload=payload
                )
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
                                sql = """
                                INSERT INTO cn_external_tx (`coin_name`, `user_id`, `amount`, 
                                `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `date`, `tx_hash`, `user_server`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """
                                await cur.execute(sql, (
                                    coin_name, user_from, amount, tx_fee, withdraw_fee, coin_decimal, to_address,
                                    int(time.time()), tx_hash['transactionHash'], user_server
                                ))
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
                        async with session.post(
                            wallet_api_url + method,
                            headers=headers,
                            json=json_data,
                            timeout=time_out
                        ) as response:
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
                                            sql = """
                                            INSERT INTO cn_external_tx 
                                            (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, 
                                            `to_address`, `date`, `tx_hash`, `user_server`) 
                                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                            """
                                            await cur.execute(sql, (
                                                coin_name, user_from, amount, tx_fee, withdraw_fee, coin_decimal,
                                                to_address, int(time.time()), tx_hash['transactionHash'], user_server
                                            ))
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
                        'walletapi_send_transaction: TIMEOUT: {} coin_name {} - timeout {}'.format(
                            method, coin_name, time_out
                        )
                    )
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
                result = await self.call_aiohttp_wallet_xmr_bcn(
                    'sendTransaction', coin_name, time_out=time_out, payload=payload
                )
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
                                sql = """
                                INSERT INTO cn_external_tx (`coin_name`, `user_id`, `amount`, 
                                `tx_fee`, `withdraw_fee`, `decimal`, `to_address`, `paymentid`, `date`, `tx_hash`, `user_server`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """
                                await cur.execute(sql, (
                                    coin_name, user_from, amount, tx_fee, withdraw_fee, coin_decimal,
                                    to_address, paymentId, int(time.time()), tx_hash['transactionHash'], user_server
                                ))
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
                        async with session.post(
                            wallet_api_url + method,
                            headers=headers,
                            json=json_data,
                            timeout=time_out
                        ) as response:
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
                                            sql = """
                                            INSERT INTO `cn_external_tx` 
                                            (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, `decimal`, 
                                            `to_address`, `paymentid`, `date`, `tx_hash`, `user_server`) 
                                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                            """
                                            await cur.execute(sql, (
                                                coin_name, user_from, amount, tx_fee, withdraw_fee, coin_decimal,
                                                to_address, paymentId, int(time.time()), tx_hash['transactionHash'],
                                                user_server
                                            ))
                                            await conn.commit()
                                            return tx_hash['transactionHash']
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                                    await logchanbot("wallet send_external_xmr " + str(traceback.format_exc()))
                            elif 'errorMessage' in json_resp:
                                raise RPCException(json_resp['errorMessage'])
                except asyncio.TimeoutError:
                    await logchanbot(
                        'walletapi_send_transaction_id: TIMEOUT: {} coin_name {} - timeout {}'.format(
                            method, coin_name, time_out
                        )
                    )
        except Exception:
            await logchanbot("wallet send_external_xmr " + str(traceback.format_exc()))
        return None

    async def send_external_hnt(
        self, user_id: str, wallet_host: str, password: str, from_address: str, payee: str,
        amount: float, coin_decimal: int, user_server: str, coin: str, withdraw_fee: float,
        time_out=60
    ):
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
                check_locked = await call_hnt_wallet(
                    wallet_host, headers=headers, json_data=json_check_lock, time_out=time_out
                )
                print(check_locked)
                if 'result' in check_locked and check_locked['result'] is True:
                    await logchanbot(f'[UNLOCKED] {coin_name}...')
                    unlock = await call_hnt_wallet(
                        wallet_host, headers=headers, json_data=json_unlock, time_out=time_out
                    )
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
                                    sql = """
                                    INSERT INTO hnt_external_tx 
                                    (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, 
                                    `decimal`, `to_address`, `date`, `tx_hash`, `user_server`) 
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    """
                                    await cur.execute(sql, (
                                        coin_name, user_id, amount, fee, withdraw_fee, coin_decimal, payee,
                                        int(time.time()), sendTx['result']['hash'], user_server
                                    ))
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

    async def check_xlm_asset(
        self, url: str, asset_name: str, issuer: str,
        to_address: str, user_id: str, user_server: str
    ):
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
                f"[{user_server}] [XLM]: Failed /withdraw by {user_id}. "\
                f"Account not found for address: {to_address} / asset_name: {asset_name}."
            )
        return found

    async def send_external_xlm_nostore(
        self, url: str, withdraw_keypair: str, user_id: str, amount: float, to_address: str,
        coin_decimal: int, user_server: str, coin: str, withdraw_fee: float,
        asset_ticker: str = None, asset_issuer: str = None, time_out=60, memo=None
    ):
        coin_name = coin.upper()
        asset_sending = Asset.native()
        if coin_name != "XLM":
            asset_sending = Asset(asset_ticker, asset_issuer)
        tipbot_keypair = Stella_Keypair.from_secret(withdraw_keypair)
        async with ServerAsync(
                horizon_url=url, client=AiohttpClient()
        ) as server:
            try:
                tipbot_account = await server.load_account(tipbot_keypair.public_key)
                base_fee = 50000
                if memo is not None:
                    transaction = (
                        TransactionBuilder(
                            source_account=tipbot_account,
                            network_passphrase=Network.PUBLIC_NETWORK_PASSPHRASE,
                            base_fee=base_fee,
                        )
                        .add_text_memo(memo)
                        .append_payment_op(to_address, asset_sending, str(truncate(amount, 6)))
                        .set_timeout(30)
                        .build()
                    )
                else:
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
                return response['hash']
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return None

    async def send_external_xlm(
        self, url: str, withdraw_keypair: str, user_id: str, amount: float, to_address: str,
        coin_decimal: int, user_server: str, coin: str, withdraw_fee: float,
        asset_ticker: str = None, asset_issuer: str = None, time_out=60, memo=None
    ):
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
            if memo is not None:
                transaction = (
                    TransactionBuilder(
                        source_account=tipbot_account,
                        network_passphrase=Network.PUBLIC_NETWORK_PASSPHRASE,
                        base_fee=base_fee,
                    )
                    .add_text_memo(memo)
                    .append_payment_op(to_address, asset_sending, str(truncate(amount, 6)))
                    .set_timeout(30)
                    .build()
                )
            else:
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
                        sql = """
                        INSERT INTO xlm_external_tx 
                        (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, 
                        `decimal`, `to_address`, `date`, `tx_hash`, `user_server`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        await cur.execute(sql, (
                            coin_name, user_id, amount, fee, withdraw_fee, coin_decimal,
                            to_address, int(time.time()), response['hash'], user_server
                        ))
                        await conn.commit()
                        return response['hash']
            except Exception:
                await logchanbot("wallet send_external_xlm " + str(traceback.format_exc()))
                traceback.print_exc(file=sys.stdout)
        return None

    async def cosmos_get_coin_by_denom(
        self, denom: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `coin_settings`
                    WHERE `contract`=%s AND `enable`=1 LIMIT 1
                    """
                    await cur.execute(sql, denom)
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def cosmos_send_tx(
        self, rpc_url: str, chain_id: str, coin_name: str, account_num: int, sequence: int, priv_key: str,
        amount: float, coin_decimal: int, user_id: str, to_address: str, user_server: str,
        withdraw_fee: float, fee: int=1000, gas: int=120000, memo: str ="", timeout: int=20, hrp: str="cosmos",
        denom: str="uatom",
    ):
        fee_denom: str = denom
        if hrp == "osmo":
            fee_denom = "uosmo"
        try:
            tx = Cosmos_Transaction(
                privkey=bytes.fromhex(priv_key),
                hrp=hrp,
                fee_denom=fee_denom,
                account_num=account_num,
                sequence=sequence,
                fee=fee,
                gas=gas,
                memo=memo,
                chain_id=chain_id,
            )
            tx.add_transfer(
                recipient=to_address, amount=int(amount * 10**coin_decimal), denom=denom
            )
            data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "broadcast_tx_sync", # Available methods: broadcast_tx_sync, broadcast_tx_async, broadcast_tx_commit
                "params": {
                    "tx": tx.get_tx_bytes()
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    rpc_url, json=data,
                    headers={'Content-Type': 'application/json'},
                    timeout=timeout
                ) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        await session.close()
                        decoded_data = json.loads(res_data)
                        if decoded_data is not None:
                            success = 1
                            if decoded_data['result']['code'] != 0:
                                success = 0
                            try:
                                await self.openConnection()
                                async with self.pool.acquire() as conn:
                                    async with conn.cursor() as cur:
                                        sql = """
                                        INSERT INTO `cosmos_external_tx` 
                                        (`coin_name`, `user_id`, `amount`, `tx_fee`, `withdraw_fee`, 
                                        `decimal`, `to_address`, `date`, `tx_hash`, `tx_dump`, `user_server`, `success`) 
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                        """
                                        await cur.execute(sql, (
                                            coin_name, user_id, amount, 0, withdraw_fee, coin_decimal,
                                            to_address, int(time.time()), decoded_data['result']['hash'],
                                            json.dumps(decoded_data), user_server, success
                                        ))
                                        await conn.commit()
                                        return decoded_data
                            except Exception:
                                await logchanbot("wallet cosmos_send_tx " + str(traceback.format_exc()))
                                traceback.print_exc(file=sys.stdout)
                            return decoded_data
        except asyncio.TimeoutError:
            print('TIMEOUT: cosmos_send_tx {} for {}s'.format(rpc_url, timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None

    async def send_external_ada(
        self, user_id: str, amount: float, coin_decimal: int,
        user_server: str, coin: str, withdraw_fee: float,
        to_address: str, time_out=60
    ):
        coin_name = coin.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * 
                    FROM `ada_wallets` 
                    WHERE `is_for_withdraw`=%s ORDER BY RAND() LIMIT 1
                    """
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
                                    data_json = {
                                        "passphrase": decrypt_string(result['passphrase']),
                                        "payments": [
                                            {
                                                "address": to_address,
                                                "amount": {
                                                    "quantity": amount_atomic,
                                                    "unit": "lovelace"
                                                }
                                            }
                                        ],
                                        "withdrawal": "self"
                                    }
                                    async with aiohttp.ClientSession() as session:
                                        async with session.post(
                                            url, headers=headers,
                                            json=data_json,
                                            timeout=timeout
                                        ) as response:
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
                                        sql = """
                                        INSERT INTO `ada_external_tx` 
                                        (`coin_name`, `asset_name`, `policy_id`, `user_id`, 
                                        `real_amount`, `real_external_fee`, `network_fee`, 
                                        `token_decimal`, `to_address`, `input_json`, `output_json`, 
                                        `hash_id`, `date`, `user_server`) 
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                        """
                                        await cur.execute(sql, (
                                            coin_name, None, None, user_id, amount, network_fee + withdraw_fee, network_fee,
                                            coin_decimal, to_address, json.dumps(sending_tx['inputs']),
                                            json.dumps(sending_tx['outputs']), sending_tx['id'], int(time.time()),
                                            user_server
                                        ))
                                        await conn.commit()
                                        return sending_tx
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet send_external_ada " + str(traceback.format_exc()))
        return None

    async def send_external_ada_asset(
        self, user_id: str, amount: float, coin_decimal: int, user_server: str, coin: str,
        withdraw_fee: float, to_address: str, asset_name: str, policy_id: str,
        time_out=60
    ):
        coin_name = coin.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                        FROM `ada_wallets` 
                        WHERE `is_for_withdraw`=%s ORDER BY RAND() LIMIT 1
                        """
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
                            async def estimate_fee_with_asset(
                                url: str, to_address: str, asset_name: str,
                                policy_id: str, amount_atomic: int, timeout: int = 90
                            ):
                                try:
                                    headers = {
                                        'Content-Type': 'application/json'
                                    }
                                    data_json = {"payments": [
                                        {"address": to_address, "amount": {"quantity": 0, "unit": "lovelace"},
                                         "assets": [{"policy_id": policy_id, "asset_name": asset_name,
                                                     "quantity": amount_atomic}]}], "withdrawal": "self"}
                                    async with aiohttp.ClientSession() as session:
                                        async with session.post(
                                            url,
                                            headers=headers,
                                            json=data_json,
                                            timeout=timeout
                                        ) as response:
                                            if response.status == 202:
                                                res_data = await response.read()
                                                res_data = res_data.decode('utf-8')
                                                decoded_data = json.loads(res_data)
                                                return decoded_data
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                                return None

                            async def send_tx(
                                url: str, to_address: str, ada_atomic_amount: int, amount_atomic: int,
                                asset_name: str, policy_id: str, timeout: int = 90
                            ):
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
                                        async with session.post(
                                            url, headers=headers, json=data_json,
                                            timeout=timeout
                                        ) as response:
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
                                        data_rows.append((
                                            coin_name, asset_name, policy_id, user_id, amount,
                                            withdraw_fee, network_fee, coin_decimal, to_address,
                                            json.dumps(sending_tx['inputs']),
                                            json.dumps(sending_tx['outputs']), sending_tx['id'],
                                            int(time.time()), user_server
                                        ))
                                        if getattr(getattr(self.bot.coin_list, coin_name),"withdraw_use_gas_ticker") == 1:
                                            GAS_COIN = getattr(getattr(self.bot.coin_list, coin_name), "gas_ticker")
                                            fee_limit = getattr(getattr(self.bot.coin_list, coin_name), "fee_limit")
                                            fee_limit = fee_limit / 20  # => 2 / 20 = 0.1 ADA # Take care if you adjust fee_limit in DB
                                            # new ADA charge = ADA goes to withdraw wallet + 0.1 ADA
                                            data_rows.append((
                                                GAS_COIN, None, None, user_id,
                                                network_fee + fee_limit + ada_fee_atomic / 10 ** 6, 0,
                                                network_fee,
                                                getattr(getattr(self.bot.coin_list, GAS_COIN), "decimal"),
                                                to_address, json.dumps(sending_tx['inputs']),
                                                json.dumps(sending_tx['outputs']), sending_tx['id'],
                                                int(time.time()), user_server
                                            ))
                                        await self.openConnection()
                                        async with self.pool.acquire() as conn:
                                            async with conn.cursor() as cur:
                                                sql = """
                                                INSERT INTO `ada_external_tx` 
                                                (`coin_name`, `asset_name`, `policy_id`, `user_id`, `real_amount`,
                                                `real_external_fee`, `network_fee`, `token_decimal`, `to_address`,
                                                `input_json`, `output_json`, `hash_id`, `date`, `user_server`) 
                                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                                """
                                                await cur.executemany(sql, data_rows)
                                                await conn.commit()
                                                sending_tx['all_ada_fee'] = network_fee + fee_limit + ada_fee_atomic / 10 ** 6
                                                sending_tx['ada_received'] = ada_fee_atomic / 10 ** 6
                                                sending_tx['network_fee'] = network_fee
                                                return sending_tx
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        await logchanbot(
                                            f"[BUG] send_external_ada_asset: user_id: __{user_id}__ "\
                                            f"failed to insert to DB for withdraw {json.dumps(data_rows)}."
                                        )
                            else:
                                print(
                                    f"send_external_ada_asset: cannot get estimated fee for sending asset __{asset_name}__" \
                                    f"for amount __{str(amount)} {coin_name}__"
                                )
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet send_external_ada_asset " + str(traceback.format_exc()))
        return None

    async def send_external_sol(
        self, proxy: str, url: str, user_from: str, amount: float, to_address: str, coin: str,
        coin_decimal: int, tx_fee: float, withdraw_fee: float, user_server: str = 'DISCORD'
    ):
        try:
            send_tx = await self.utils.solana_send_tx(
                proxy, url, self.bot.config['sol']['MainAddress_key_hex'], to_address, int(amount * 10 ** coin_decimal), timeout=60
            )
            if send_tx.get("hash"):
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """
                        INSERT INTO `sol_external_tx` (`coin_name`, `contract`, `user_id`, 
                        `real_amount`, `real_external_fee`, `network_fee`, `txn`, `token_decimal`,
                        `to_address`, `date`, `user_server`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        await cur.execute(sql, (
                            coin.upper(), None, user_from, amount, withdraw_fee, tx_fee, send_tx['hash'], 
                            coin_decimal, to_address, int(time.time()), user_server
                        ))
                        await conn.commit()
                        return send_tx['hash']
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def tezos_insert_reveal(self, address: str, tx_hash: str, checked_date: int):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT IGNORE INTO `tezos_address_reveal_check`
                    (`address`, `tx_hash`, `checked_date`) 
                    VALUES (%s, %s, %s)
                    """
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
                    sql = """
                    SELECT * 
                    FROM `tezos_address_reveal_check` 
                    WHERE `address`=%s LIMIT 1
                    """
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
                    sql = """
                    SELECT * 
                    FROM `tezos_user` 
                    WHERE `balance_wallet_address`=%s LIMIT 1
                    """
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

    def tezos_move_token_balance(
        self, url: str, key: str, to_address: str,
        contract: str, atomic_amount: int, token_id: int=0
    ):
        try:
            token = pytezos.using(shell=url, key=key).contract(contract)
            acc = pytezos.using(shell=url, key=key)
            tx_token = token.transfer(
                [dict(from_ = acc.key.public_key_hash(), txs = [ dict(to_ = to_address, amount = atomic_amount, token_id = int(token_id))])]
            ).send()
            return tx_token
            # adjust gas can be call with: contract.call(...).as_transaction().autofill(fee=123, gas_limit=123, storage_limit=123).sign().inject()
        except Exception:
            print("[XTZ 2.0] failed to move url: {}, contract {} moving {} to {}".format(url, contract, acc.key.public_key_hash(), to_address))
            traceback.print_exc(file=sys.stdout)
        return None

    def tezos_move_token_balance_fa12(
        self, url: str, key: str, to_address: str, contract: str,
        atomic_amount: int, token_id: int=0
    ):
        try:
            token = pytezos.using(shell=url, key=key).contract(contract)
            acc = pytezos.using(shell=url, key=key)
            tx_token = token.transfer(**{'from': acc.key.public_key_hash(), 'to': to_address, 'value': atomic_amount}).inject()
            return tx_token
        except Exception:
            print("[XTZ 1.2] failed to move url: {}, contract {} moving {} to {}".format(
                url, contract, acc.key.public_key_hash(), to_address)
            )
            traceback.print_exc(file=sys.stdout)
        return None

    async def send_external_xtz_nostore(
        self, url: str, key: str, amount: float, to_address: str, coin_decimal: int
    ):
        try:
            transaction = functools.partial(self.tezos_move_balance, url, key, to_address, int(amount*10**coin_decimal))
            send_tx = await self.bot.loop.run_in_executor(None, transaction)
            if send_tx:
                try:
                    return {"hash": send_tx.hash(), "contents": json.dumps(send_tx.contents)}
                except Exception:
                    traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def send_external_xtz(
        self, url: str, key: str, user_from: str, amount: float, to_address: str, coin: str,
        coin_decimal: int, withdraw_fee: float, network: str, user_server: str = 'DISCORD'
    ):
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
                        sql = """
                        INSERT INTO `tezos_external_tx` (`token_name`, `contract`,
                        `user_id`, `real_amount`, `real_external_fee`, `token_decimal`,
                        `to_address`, `date`, `txn`, `contents`, `user_server`, `network`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        await cur.execute(sql, (
                            coin.upper(), None, user_from, amount, withdraw_fee, coin_decimal, to_address,
                            int(time.time()), send_tx.hash(), contents, user_server, network
                        ))
                        await conn.commit()
                        return send_tx.hash()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def send_external_xtz_asset(
        self, url: str, key: str, user_from: str, amount: float, to_address: str, coin: str,
        coin_decimal: int, withdraw_fee: float, network: str, contract: str, token_id: int, 
        token_type: str, user_server: str = 'DISCORD'
    ):
        try:
            if token_type == "FA2":
                transaction = functools.partial(
                    self.tezos_move_token_balance, url, key, to_address,
                    contract, int(amount*10**coin_decimal), token_id
                )
            elif token_type == "FA1.2":
                transaction = functools.partial(
                    self.tezos_move_token_balance_fa12, url, key, to_address,
                    contract, int(amount*10**coin_decimal), token_id
                )
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
                        sql = """
                        INSERT INTO `tezos_external_tx` 
                        (`token_name`, `contract`, `user_id`, `real_amount`, `real_external_fee`,
                        `token_decimal`, `to_address`, `date`, `txn`, `contents`, `user_server`, `network`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        await cur.execute(sql, (
                            coin.upper(), contract, user_from, amount, withdraw_fee,
                            coin_decimal, to_address, int(time.time()), tx_hash,
                            contents, user_server, network
                        ))
                        await conn.commit()
                        return tx_hash
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def tezos_insert_mv_balance(
        self, token_name: str, contract: str, user_id: str, balance_wallet_address: str,
        to_main_address: str, real_amount: float, real_deposit_fee: float, token_decimal: int,
        txn: str, content: str, time_insert: int, user_server: str, network: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT IGNORE INTO `tezos_move_deposit` 
                    (`token_name`, `contract`, `user_id`, `balance_wallet_address`, 
                    `to_main_address`, `real_amount`, `real_deposit_fee`, `token_decimal`, `txn`,
                    `content`, `time_insert`, `user_server`, `network`) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (
                        token_name, contract, user_id, balance_wallet_address, to_main_address,
                        real_amount, real_deposit_fee, token_decimal, txn, content, time_insert,
                        user_server, network
                    ))
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
                    sql = """
                    SELECT * 
                    FROM `tezos_move_deposit` 
                    WHERE `status`=%s
                    """
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
                    sql = """
                    UPDATE `tezos_user` 
                    SET `last_moved_gas`=%s 
                    WHERE `balance_wallet_address`=%s LIMIT 1
                    """
                    await cur.execute(sql, (ts, address))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def tezos_update_mv_deposit_pending(
        self, txn: str, blockNumber: int, confirmed_depth: int
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    UPDATE `tezos_move_deposit` 
                    SET `blockNumber`=%s, `status`=%s, `confirmed_depth`=%s 
                    WHERE `status`=%s AND `txn`=%s LIMIT 1
                    """
                    await cur.execute(sql, (blockNumber, "CONFIRMED", confirmed_depth, "PENDING", txn))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    def near_move_balance(
        self, url: str, key: str, by_address: str, to_address: str, atomic_amount: int
    ):
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

    def near_move_balance_token(
        self, url: str, contract_id: str, key: str,
        by_address: str, to_address: str, atomic_amount: int
    ):
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
                    sql = """
                    SELECT * 
                    FROM `near_user` 
                    WHERE `balance_wallet_address`=%s LIMIT 1
                    """
                    await cur.execute(sql, address)
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def near_insert_mv_balance(
        self, token_name: str, contract: str, user_id: str,
        balance_wallet_address: str, to_main_address: str,
        real_amount: float, real_deposit_fee: float,
        token_decimal: int, txn: str, content: str,
        time_insert: int, user_server: str, network: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT IGNORE INTO `near_move_deposit` (`token_name`, `contract`, 
                    `user_id`, `balance_wallet_address`, `to_main_address`, `amount`, 
                    `real_deposit_fee`, `token_decimal`, `txn`, `content`, `time_insert`, 
                    `user_server`, `network`) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    await cur.execute(sql, (
                        token_name, contract, user_id, balance_wallet_address,
                        to_main_address, real_amount, real_deposit_fee, token_decimal,
                        txn, content, time_insert, user_server, network
                    ))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def send_external_near(
        self, url: str, contract_id: str, key: str, user_from: str,
        by_address: str, amount: float, to_address: str, coin: str,
        coin_decimal: int, withdraw_fee: float, user_server: str = 'DISCORD'
    ):
        try:
            if contract_id is None:
                transaction = functools.partial(
                    self.near_move_balance, url, key, by_address, to_address, int(amount*10**coin_decimal)
                )
            else:
                transaction = functools.partial(
                    self.near_move_balance_token, url, contract_id, key,
                    by_address, to_address, int(amount*10**coin_decimal
                ))
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
                        sql = """
                        INSERT INTO `near_external_tx` (`token_name`, `contract`, 
                        `user_id`, `real_amount`, `real_external_fee`, `token_decimal`, 
                        `to_address`, `date`, `tx_hash`, `tx_json`, `user_server`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        await cur.execute(sql, (
                            coin.upper(), None, user_from, amount, withdraw_fee, coin_decimal, to_address,
                            int(time.time()), send_tx['transaction_outcome']['id'], tx_json, user_server
                        ))
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
                    sql = """
                    SELECT * 
                    FROM `near_move_deposit` 
                    WHERE `status`=%s
                    """
                    await cur.execute(sql, status)
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def near_update_mv_deposit_pending(
        self, txn: str, blockNumber: int, confirmed_depth: int
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    UPDATE `near_move_deposit` 
                    SET `blockNumber`=%s, `status`=%s, `confirmations`=%s 
                    WHERE `status`=%s AND `txn`=%s LIMIT 1
                    """
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
                    sql = """
                    UPDATE `near_user` 
                    SET `last_moved_gas`=%s 
                    WHERE `balance_wallet_address`=%s LIMIT 1
                    """
                    await cur.execute(sql, (ts, address))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def xrp_insert_deposit(
        self, coin_name: str, issuer: str, user_id: str, txid: str, height: int,
        timestamp: int, amount: float, decimal: int, address: str,
        destination_tag: int, time_insert: int
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT IGNORE INTO `xrp_get_transfers` (`coin_name`, `issuer`, `user_id`, `txid`, 
                    `height`, `timestamp`, `amount`, `decimal`, `address`, `destination_tag`, `time_insert`) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    await cur.execute(sql, (
                        coin_name, issuer, user_id, txid, height, timestamp,
                        amount, decimal, address, destination_tag, time_insert
                    ))
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
                    sql = """
                    SELECT * 
                    FROM `xrp_user` 
                    WHERE `destination_tag`=%s LIMIT 1
                    """
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
                    sql = """
                    SELECT `txid` 
                    FROM `xrp_get_transfers`
                    """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result:
                        return [each['txid'] for each in result]
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def send_external_xrp(
        self, url: str, seed: str, user_from: str, to_address: str, amount: float,
        withdraw_fee: float, coin: str, issuer: str, currency_code: str,
        coin_decimal: int, user_server: str
    ):
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
                        sql = """
                        INSERT INTO `xrp_external_tx` (`coin_name`, `issuer`, 
                        `user_id`, `amount`, `tx_fee`, `native_fee`, `decimal`, 
                        `to_address`, `date`, `txid`, `contents`, `user_server`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        await cur.execute(sql, (
                            coin.upper(), issuer, user_from, amount, withdraw_fee,
                            native_fee, coin_decimal, to_address,
                            int(time.time()), send_tx.result['hash'],
                            contents, user_server
                        ))
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

    def zil_transfer_token(
        self, contract_addr: str, to_address: str, from_key: str, atomic_amount: int
    ):
        try:
            zil_chain.set_active_chain(zil_chain.MainNet)
            account = Zil_Account(private_key=from_key)
            contract = zil_contract.load_from_address(contract_addr)
            contract.account = account
            to_account = Zil_Account(address=to_address)
            resp = contract.call(
                method="Transfer",
                params=[
                    zil_contract.value_dict("to", "ByStr20", to_account.address0x),
                    zil_contract.value_dict("amount", "Uint128", str(atomic_amount))
                ]
            )
            return resp
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def zil_insert_mv_balance(
        self, token_name: str, contract: str, user_id: str, balance_wallet_address: str,
        to_main_address: str, real_amount: float, real_deposit_fee: float, token_decimal: int,
        txn: str, content: str, time_insert: int, user_server: str, network: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT IGNORE INTO `zil_move_deposit` (`token_name`, `contract`, `user_id`, `balance_wallet_address`, 
                    `to_main_address`, `real_amount`, `real_deposit_fee`, `token_decimal`, `txn`, `content`, `time_insert`, 
                    `user_server`, `network`) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    await cur.execute(sql, (
                        token_name, contract, user_id, balance_wallet_address,
                        to_main_address, real_amount, real_deposit_fee, token_decimal,
                        txn, content, time_insert, user_server, network
                    ))
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
                    sql = """
                    SELECT * 
                    FROM `zil_user` 
                    WHERE `balance_wallet_address`=%s LIMIT 1
                    """
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
                    sql = """
                    UPDATE `zil_user` 
                    SET `last_moved_gas`=%s 
                    WHERE `balance_wallet_address`=%s LIMIT 1
                    """
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
                    sql = """
                    SELECT * 
                    FROM `zil_move_deposit` 
                    WHERE `status`=%s
                    """
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
                    sql = """
                    UPDATE `zil_move_deposit` 
                    SET `blockNumber`=%s, `status`=%s, `confirmed_depth`=%s 
                    WHERE `status`=%s AND `txn`=%s LIMIT 1
                    """
                    await cur.execute(sql, (blockNumber, "CONFIRMED", confirmed_depth, "PENDING", txn))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def send_external_zil(
        self, key: str, user_from: str, amount: float, to_address: str, coin: str,
        coin_decimal: int, withdraw_fee: float, network: str, user_server: str = 'DISCORD'
    ):
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
                        sql = """
                        INSERT INTO `zil_external_tx` (`token_name`, `contract`, 
                        `user_id`, `real_amount`, `real_external_fee`, `token_decimal`, 
                        `to_address`, `date`, `txn`, `contents`, `user_server`, `network`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        await cur.execute(sql, (
                            coin.upper(), None, user_from, amount, withdraw_fee, coin_decimal, to_address,
                            int(time.time()), send_tx['ID'], contents, user_server, network
                        ))
                        await conn.commit()
                        return send_tx['ID']
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def send_external_zil_asset(
        self, contract: str, key: str, user_from: str, atomic_amount: int,
        to_address: str, coin: str, coin_decimal: int, withdraw_fee: float,
        network: str, user_server: str = 'DISCORD'
    ):
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
                        sql = """
                        INSERT INTO `zil_external_tx` (`token_name`, `contract`, 
                        `user_id`, `real_amount`, `real_external_fee`, `token_decimal`, 
                        `to_address`, `date`, `txn`, `contents`, `user_server`, `network`) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        await cur.execute(sql, (
                            coin.upper(), contract, user_from, float(atomic_amount / 10 ** coin_decimal),
                            withdraw_fee, coin_decimal, to_address, int(time.time()), send_tx['ID'],
                            contents, user_server, network
                        ))
                        await conn.commit()
                        return send_tx['ID']
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def vet_insert_mv_balance(
        self, token_name: str, contract: str, user_id: str, balance_wallet_address: str,
        to_main_address: str, real_amount: float, real_deposit_fee: float,
        token_decimal: int, txn: str, content: str, time_insert: int,
        user_server: str, network: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT IGNORE INTO `vet_move_deposit` (`token_name`, `contract`, `user_id`, `balance_wallet_address`, 
                    `to_main_address`, `real_amount`, `real_deposit_fee`, `token_decimal`, `txn`, `content`, `time_insert`, 
                    `user_server`, `network`) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    await cur.execute(sql, (
                        token_name, contract, user_id, balance_wallet_address,
                        to_main_address, real_amount, real_deposit_fee,
                        token_decimal, txn, content, time_insert, user_server, network
                    ))
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
                    sql = """
                    SELECT * 
                    FROM `vet_move_deposit` 
                    WHERE `status`=%s
                    """
                    await cur.execute(sql, status)
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def vet_update_mv_deposit_pending(
        self, txn: str, blockNumber: int, content: str, confirmed_depth: int
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    UPDATE `vet_move_deposit` 
                    SET `blockNumber`=%s, `status`=%s, `confirmed_depth`=%s, `content`=%s 
                    WHERE `status`=%s AND `txn`=%s LIMIT 1
                    """
                    await cur.execute(sql, (blockNumber, "CONFIRMED", confirmed_depth, content, "PENDING", txn))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def insert_external_vet(
        self, user_from: str, amount: float, to_address: str, coin: str, contract: str, 
        coin_decimal: int, withdraw_fee: float, tx_hash: str, network: str, user_server: str = 'DISCORD'
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT INTO `vet_external_tx` (`token_name`, `contract`, `user_id`, 
                    `real_amount`, `real_external_fee`, `token_decimal`, `to_address`, `date`, 
                    `txn`, `contents`, `user_server`, `network`) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    await cur.execute(sql, (
                        coin.upper(), contract, user_from, amount, withdraw_fee, coin_decimal, to_address,
                        int(time.time()), tx_hash, None, user_server, network
                    ))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def insert_external_vite(
        self, user_from: str, amount: float, to_address: str, coin: str, contract: str, 
        coin_decimal: int, withdraw_fee: float, tx_hash: str, contents: str, user_server: str = 'DISCORD'
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT INTO `vite_external_tx` (`coin_name`, `contract`, `user_id`, 
                    `amount`, `withdraw_fee`, `decimal`, `to_address`, `date`, `tx_hash`, 
                    `contents`, `user_server`) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    await cur.execute(sql, (
                        coin.upper(), contract, user_from, amount, withdraw_fee, coin_decimal, to_address,
                        int(time.time()), tx_hash, contents, user_server
                    ))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

class TransferExtra(disnake.ui.Modal):
    def __init__(self, ctx, bot, coin_name: str, coin_type: str) -> None:
        self.ctx = ctx
        self.bot = bot
        self.coin_name = coin_name.upper()
        self.coin_type = coin_type
        self.wallet_api = WalletAPI(self.bot)
        self.wallet = Wallet(self.bot)
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
        super().__init__(title=f"Transfer {self.coin_name} with extra option", custom_id="modal_transfer_extra", components=components)

    async def callback(self, interaction: disnake.ModalInteraction) -> None:
        # Check if type of question is bool or multipe
        await interaction.response.send_message(content=f"{interaction.author.mention}, checking transfer extra...", ephemeral=True)

        amount = interaction.text_values['amount_id'].strip()
        if amount == "":
            await interaction.edit_original_message(f"{interaction.author.mention}, amount is empty!")
            return

        address = interaction.text_values['address_id'].strip()
        if address == "":
            await interaction.edit_original_message(f"{interaction.author.mention}, address can't be empty!")
            return

        if 'extra_option' not in interaction.text_values:
            await interaction.edit_original_message(f"{interaction.author.mention}, without extra, please use `/withdraw` command!")
            return

        extra_option = interaction.text_values['extra_option'].strip()
        if extra_option is None or len(extra_option) == 0:
            await interaction.edit_original_message(f"{interaction.author.mention}, without extra, please use `/withdraw` command!")
            return

        coin_name = self.coin_name
        try:
            await self.wallet.async_withdraw(interaction, amount, coin_name, address, extra_option)
        except Exception:
            traceback.print_exc(file=sys.stdout)

class Wallet(commands.Cog):
    def __init__(self, bot):
        self.enable_logchan = True
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)

        self.botLogChan = None

        # Swap
        self.swap_pair = self.bot.config['wrap_list']

        # Donate
        self.donate_to = 386761001808166912  # pluton#8888

        # DB
        self.pool = None
        self.ttlcache = TTLCache(maxsize=1024, ttl=60.0)
        self.mv_xtz_cache = TTLCache(maxsize=1024, ttl=30.0)

        # cache withdraw of a coin to avoid fast withdraw
        self.withdraw_tx = TTLCache(maxsize=2048, ttl=300.0) # key = user_id + coin => time


    async def openConnection(self):
        try:
            if self.pool is None:
                self.pool = await aiomysql.create_pool(
                    host=self.bot.config['mysql']['host'], port=3306, minsize=2, maxsize=4,
                    user=self.bot.config['mysql']['user'], password=self.bot.config['mysql']['password'],
                    db=self.bot.config['mysql']['db'], cursorclass=DictCursor, autocommit=True
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def swaptoken_list(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `coin_swap_tokens` WHERE `enable`=%s
                    """
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
                    sql = """
                    SELECT * FROM `coin_swap_tokens` 
                    WHERE `enable`=%s AND `from_token`=%s AND `to_token`=%s LIMIT 1
                    """
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
                    sql = """
                    INSERT INTO user_balance_mv (`token_name`, `contract`, `from_userid`, 
                    `to_userid`, `guild_id`, `channel_id`, `real_amount`, `token_decimal`, `type`, 
                    `date`, `user_server`, `real_amount_usd`, `extra_message`) 
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
                    sql = """
                    SELECT * FROM `user_balance_mv` WHERE `from_userid`=%s AND `type`=%s
                    """
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
                    sql = """ INSERT INTO `user_balance_mv` 
                              (`token_name`, `contract`, `from_userid`, `to_userid`, `guild_id`, `channel_id`, `real_amount`, `real_amount_usd`, `token_decimal`, `type`, `date`, `user_server`) 
                              VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS DECIMAL(32,8)), CAST(%s AS DECIMAL(32,8)), %s, %s, %s, %s);

                              INSERT INTO `user_balance_mv_data` (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                              VALUES (%s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s) ON DUPLICATE KEY 
                              UPDATE 
                              `balance`=`balance`+VALUES(`balance`), 
                              `update_date`=VALUES(`update_date`);

                              INSERT INTO `user_balance_mv_data` (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                              VALUES (%s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s) ON DUPLICATE KEY 
                              UPDATE 
                              `balance`=`balance`+VALUES(`balance`), 
                              `update_date`=VALUES(`update_date`);


                              INSERT INTO `user_balance_mv` 
                              (`token_name`, `contract`, `from_userid`, `to_userid`, `guild_id`, `channel_id`, `real_amount`, `real_amount_usd`, `token_decimal`, `type`, `date`, `user_server`) 
                              VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS DECIMAL(32,8)), CAST(%s AS DECIMAL(32,8)), %s, %s, %s, %s);

                              INSERT INTO `user_balance_mv_data` (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                              VALUES (%s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s) ON DUPLICATE KEY 
                              UPDATE 
                              `balance`=`balance`+VALUES(`balance`), 
                              `update_date`=VALUES(`update_date`);

                              INSERT INTO `user_balance_mv_data` (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
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
                        from_amount, currentTs
                    ))
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
                        sql = """
                        UPDATE `twitter_mentions_timeline`
                        SET `response_date`=%s WHERE `twitter_id`=%s LIMIT 1
                        """
                        await cur.execute(sql, (int(time.time()), twitter_id))
                        await conn.commit()
            except Exception:
                traceback.print_exc(file=sys.stdout)

        async def response_tip(twitter_id: int, tipped_text: str):
            try:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """
                        UPDATE `twitter_mentions_timeline` 
                        SET `has_tip`=1, `tipped_text`=%s, `response_date`=%s
                        WHERE `twitter_id`=%s LIMIT 1
                        """
                        await cur.execute(sql, (tipped_text, int(time.time()), twitter_id))
                        await conn.commit()
            except Exception:
                traceback.print_exc(file=sys.stdout)

        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `twitter_mentions_timeline` 
                    WHERE `response_date` IS NULL 
                    ORDER BY `created_at` ASC
                    """
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
                                        price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                                        if "$" in amount[-1] or "$" in amount[0]:  # last is $
                                            # Check if conversion is allowed for this coin.
                                            amount = amount.replace(",", "").replace("$", "")
                                            if price_with is None:
                                                await invalidate_mentioned(each_resp['twitter_id'])
                                                continue
                                            else:
                                                per_unit = await self.utils.get_coin_price(coin_name, price_with)
                                                if per_unit and per_unit['price'] and per_unit['price'] > 0:
                                                    per_unit = per_unit['price']
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

                                        get_deposit = await self.sql_get_userwallet(
                                            str(each_resp['twitter_user_id']),
                                            coin_name, net_name, type_coin,
                                            "TWITTER", 0
                                        )
                                        if get_deposit is None:
                                            get_deposit = await self.sql_register_user(
                                                str(each_resp['twitter_user_id']), coin_name,
                                                net_name, type_coin, "TWITTER", 0, 0
                                            )

                                        wallet_address = get_deposit['balance_wallet_address']
                                        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                            wallet_address = get_deposit['paymentid']
                                        elif type_coin in ["XRP"]:
                                            wallet_address = get_deposit['destination_tag']
                                        height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
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
                                                if each_u['id_str'] not in ["1343104498722467845", str(
                                                        each_resp['twitter_user_id'])]:  # BotTipsTweet, twitter user
                                                    list_users.append(each_u['id_str'])
                                            if len(list_users) == 0:
                                                await invalidate_mentioned(each_resp['twitter_id'])
                                                continue
                                            else:
                                                for each in list_users:
                                                    try:
                                                        to_user = await self.sql_get_userwallet(
                                                            each, coin_name, net_name, type_coin, "TWITTER", 0
                                                        )
                                                        if to_user is None:
                                                            to_user = await self.sql_register_user(
                                                                each, coin_name, net_name, type_coin, "TWITTER", 0, 0
                                                            )
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
                                                    if price_with:
                                                        per_unit = await self.utils.get_coin_price(coin_name, price_with)
                                                        if per_unit and per_unit['price'] and per_unit['price'] > 0:
                                                            per_unit = per_unit['price']
                                                            amount_in_usd = float(Decimal(amount) * Decimal(per_unit))
                                                            if amount_in_usd >= 0.01:
                                                                equivalent_usd = " ~ {:,.2f}$".format(amount_in_usd)
                                                            elif amount_in_usd >= 0.0001:
                                                                equivalent_usd = " ~ {:,.4f}$".format(amount_in_usd)
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
                        sql = """
                        UPDATE `twitter_fetch_bot_messages` 
                        SET `draft_response_text`=%s 
                        WHERE `draft_response_text` IS NULL AND `id`=%s LIMIT 1
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
                    sql = """
                    SELECT * FROM `twitter_fetch_bot_messages` 
                    WHERE `is_ignored`=0 AND `draft_response_text` IS NULL 
                    ORDER BY `created_timestamp` ASC
                    """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each_msg in result:
                            # Ignore long DM
                            if each_msg['text'] and len(each_msg['text']) > 500:
                                sql = """
                                UPDATE `twitter_fetch_bot_messages` 
                                SET `is_ignored`=%s, `ignored_date`=%s 
                                WHERE `id`=%s LIMIT 1
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
                                            get_deposit = await self.sql_get_userwallet(
                                                each_msg['sender_id'], coin_name, net_name, type_coin,
                                                "TWITTER", 0
                                            )
                                            if get_deposit is None:
                                                get_deposit = await self.sql_register_user(
                                                    each_msg['sender_id'], coin_name, net_name,
                                                    type_coin, "TWITTER", 0, 0
                                                )
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
                                        get_deposit = await self.sql_get_userwallet(
                                            each_msg['sender_id'], coin_name,
                                            net_name, type_coin, "TWITTER", 0
                                        )
                                        if get_deposit is None:
                                            get_deposit = await self.sql_register_user(
                                                each_msg['sender_id'], coin_name,
                                                net_name, type_coin, "TWITTER",
                                                0, 0
                                            )
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
                                            get_deposit = await self.sql_get_userwallet(
                                                each_msg['sender_id'],
                                                coin_name, net_name, type_coin,
                                                "TWITTER", 0
                                            )
                                            if get_deposit is None:
                                                get_deposit = await self.sql_register_user(
                                                    each_msg['sender_id'],
                                                    coin_name, net_name,
                                                    type_coin, "TWITTER", 0, 0
                                                )
                                            wallet_address = get_deposit['balance_wallet_address']
                                            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                                wallet_address = get_deposit['paymentid']
                                            elif type_coin in ["XRP"]:
                                                wallet_address = get_deposit['destination_tag']
                                            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                                        userdata_balance = await self.wallet_api.user_balance(
                                            each_msg['sender_id'], coin_name,
                                            wallet_address, type_coin, height,
                                            deposit_confirm_depth, "TWITTER"
                                        )
                                        total_balance = userdata_balance['adjust']
                                        if total_balance == 0:
                                            zero_tokens.append(coin_name)
                                        elif total_balance > 0:
                                            non_zero_tokens[coin_name] = num_format_coin(total_balance) + " " + token_display
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
                                            price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                                            try:
                                                check_exist = await self.check_withdraw_coin_address(type_coin, address)
                                                if check_exist is not None:
                                                    response = f"You can not send to this address: {address}."
                                                    await update_bot_response(
                                                        each_msg['text'], response, each_msg['id']
                                                    )
                                                    continue
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)

                                            if tx_fee is None:
                                                tx_fee = NetFee
                                            token_display = getattr(getattr(self.bot.coin_list, coin_name),
                                                                    "display_name")
                                            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                                            fee_limit = getattr(getattr(self.bot.coin_list, coin_name), "fee_limit")
                                            get_deposit = await self.sql_get_userwallet(
                                                each_msg['sender_id'],
                                                coin_name, net_name, type_coin,
                                                user_server, 0
                                            )
                                            if get_deposit is None:
                                                get_deposit = await self.sql_register_user(
                                                    each_msg['sender_id'],
                                                    coin_name, net_name,
                                                    type_coin, user_server, 0, 0
                                                )

                                            wallet_address = get_deposit['balance_wallet_address']
                                            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                                wallet_address = get_deposit['paymentid']
                                            elif type_coin in ["XRP"]:
                                                wallet_address = get_deposit['destination_tag']

                                            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                                            if height is None:
                                                # can not pull height, continue
                                                await logchanbot(
                                                    f"[{user_server}] - Execute withdraw for __{tw_user}__ "\
                                                    f"but can not pull height of {coin_name}."
                                                )
                                                continue

                                            # check if amount is all
                                            all_amount = False
                                            if not amount.isdigit() and amount.upper() == "ALL":
                                                all_amount = True
                                                userdata_balance = await self.wallet_api.user_balance(
                                                    each_msg['sender_id'], coin_name, wallet_address,
                                                    type_coin, height, deposit_confirm_depth, user_server
                                                )
                                                amount = float(userdata_balance['adjust']) - NetFee
                                            # If $ is in amount, let's convert to coin/token
                                            elif "$" in amount[-1] or "$" in amount[0]:  # last is $
                                                # Check if conversion is allowed for this coin.
                                                amount = amount.replace(",", "").replace("$", "")
                                                if price_with is None:
                                                    response = f"Dollar conversion is not enabled for this {coin_name}."
                                                    await update_bot_response(
                                                        each_msg['text'], response, each_msg['id']
                                                    )
                                                    continue
                                                else:
                                                    per_unit = await self.utils.get_coin_price(coin_name, price_with)
                                                    if per_unit and per_unit['price'] and per_unit['price'] > 0:
                                                        per_unit = per_unit['price']
                                                        amount = float(Decimal(amount) / Decimal(per_unit))
                                                    else:
                                                        response = f"I cannot fetch equivalent price. "\
                                                            f"Try with different method for this {coin_name}."
                                                        await update_bot_response(
                                                            each_msg['text'], response, each_msg['id']
                                                        )
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
                                            userdata_balance = await self.wallet_api.user_balance(
                                                each_msg['sender_id'], coin_name, wallet_address, type_coin,
                                                height, deposit_confirm_depth, user_server
                                            )
                                            actual_balance = float(userdata_balance['adjust'])

                                            # If balance 0, no need to check anything
                                            if actual_balance <= 0:
                                                response = f"Please check your **{token_display}** balance."
                                                await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                continue
                                            if amount > actual_balance:
                                                response = f"Insufficient balance to send out "\
                                                    f"{num_format_coin(amount)} {token_display}."
                                                await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                continue

                                            if amount + NetFee > actual_balance:
                                                response = f"Insufficient balance to send out "\
                                                    f"{num_format_coin(amount)} "\
                                                    f"{token_display}. You need to leave at least network fee: "\
                                                    f"{num_format_coin(NetFee)} {token_display}."
                                                await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                continue

                                            elif amount < min_tx or amount > max_tx:
                                                response = f"Transaction cannot be smaller than "\
                                                    f"{num_format_coin(min_tx)} "\
                                                    f"{token_display} or bigger than "\
                                                    f"{num_format_coin(max_tx)} {token_display}."
                                                await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                continue
                                            equivalent_usd = ""
                                            amount_in_usd = 0.0
                                            if price_with:
                                                per_unit = await self.utils.get_coin_price(coin_name, price_with)
                                                if per_unit and per_unit['price'] and per_unit['price'] > 0:
                                                    per_unit = per_unit['price']
                                                    amount_in_usd = float(Decimal(amount) * Decimal(per_unit))
                                                    if amount_in_usd >= 0.01:
                                                        equivalent_usd = " ~ {:,.2f}$".format(amount_in_usd)
                                                    elif amount_in_usd >= 0.0001:
                                                        equivalent_usd = " ~ {:,.4f}$".format(amount_in_usd)

                                            if type_coin in ["ERC-20"]:
                                                # Check address
                                                valid_address = self.check_address_erc20(address)
                                                valid = False
                                                if valid_address and valid_address.upper() == address.upper():
                                                    valid = True
                                                else:
                                                    response = f"Invalid address:\n {address} "
                                                    await update_bot_response(
                                                        each_msg['text'], response, each_msg['id']
                                                    )
                                                    continue

                                                send_tx = None
                                                try:
                                                    url = self.bot.erc_node_list[net_name]
                                                    chain_id = getattr(getattr(self.bot.coin_list, coin_name),
                                                                       "chain_id")
                                                    send_tx = await self.send_external_erc20(
                                                        url, net_name, each_msg['sender_id'],
                                                        address, amount, coin_name, coin_decimal, NetFee,
                                                        user_server, chain_id, contract
                                                    )
                                                except Exception:
                                                    traceback.print_exc(file=sys.stdout)
                                                    await log_to_channel(
                                                        "withdraw", 
                                                        "wallet monitoring_tweet_command " + str(traceback.format_exc())
                                                    )

                                                if send_tx:
                                                    fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                                        num_format_coin(NetFee),
                                                        coin_name)
                                                    try:
                                                        response = f'You withdrew {num_format_coin(amount)} {token_display}{equivalent_usd} to _{address}_.\nTransaction hash: _{send_tx}_{fee_txt}'
                                                        await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                        continue
                                                    except Exception:
                                                        traceback.print_exc(file=sys.stdout)
                                                    try:
                                                        await log_to_channel(
                                                            "withdraw", 
                                                            f"[{user_server}] User {tw_user} sucessfully withdrew "\
                                                            f"{num_format_coin(amount)} "\
                                                            f"{token_display}{equivalent_usd}"
                                                        )
                                                    except Exception:
                                                        traceback.print_exc(file=sys.stdout)
                                            elif type_coin in ["TRC-20", "TRC-10"]:
                                                # TODO: validate address
                                                send_tx = None
                                                try:
                                                    send_tx = await self.send_external_trc20(
                                                        each_msg['sender_id'], address, amount, coin_name,
                                                        coin_decimal, NetFee, user_server, fee_limit, type_coin, contract
                                                    )
                                                except Exception:
                                                    traceback.print_exc(file=sys.stdout)
                                                    await log_to_channel(
                                                        "withdraw",
                                                        "wallet monitoring_tweet_command " + str(traceback.format_exc())
                                                    )

                                                if send_tx:
                                                    fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                                        num_format_coin(NetFee),
                                                        coin_name)
                                                    response = f'You withdrew {num_format_coin(amount)} {token_display}{equivalent_usd} to _{address}_.\nTransaction hash: _{send_tx}_{fee_txt}'
                                                    await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                    await log_to_channel(
                                                        "withdraw",
                                                        f"[{user_server}] User {tw_user} sucessfully withdrew "\
                                                        f"{num_format_coin(amount)} "\
                                                        f"{token_display}{equivalent_usd}"
                                                    )
                                                    continue
                                            elif type_coin == "NANO":
                                                valid_address = await self.wallet_api.nano_validate_address(coin_name, address)
                                                if not valid_address is True:
                                                    response = f"Address: {address} is invalid."
                                                    await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                    continue
                                                else:
                                                    try:
                                                        main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                                                        send_tx = await self.wallet_api.send_external_nano(
                                                            main_address, each_msg['sender_id'], amount,
                                                            address, coin_name, coin_decimal
                                                        )
                                                        if send_tx:
                                                            fee_txt = "\nWithdrew fee/node: `0.00 {}`.".format(
                                                                coin_name)
                                                            SendTx_hash = send_tx['block']
                                                            response = f'You withdrew {num_format_coin(amount)} "\
                                                                f"{token_display}{equivalent_usd} to _{address}_.\nTransaction hash: _{SendTx_hash}_{fee_txt}'
                                                            await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                            await log_to_channel(
                                                                "withdraw",
                                                                f"User {tw_user} successfully withdrew "\
                                                                f"{num_format_coin(amount)} "\
                                                                f"{token_display}{equivalent_usd}"
                                                            )
                                                            continue
                                                        else:
                                                            await log_to_channel(
                                                                "withdraw",
                                                                f"[{user_server}] 🔴 User {tw_user} failed to withdraw "\
                                                                f"{num_format_coin(amount)} "\
                                                                f"{token_display}{equivalent_usd} to address {address}."
                                                            )
                                                    except Exception:
                                                        traceback.print_exc(file=sys.stdout)
                                                        await log_to_channel(
                                                            "withdraw",
                                                            "wallet monitoring_tweet_command " + str(traceback.format_exc())
                                                        )
                                            elif type_coin == "CHIA":
                                                send_tx = await self.wallet_api.send_external_xch(
                                                    each_msg['sender_id'], amount, address,
                                                    coin_name, coin_decimal, tx_fee, NetFee, user_server
                                                )
                                                if send_tx:
                                                    fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                                        num_format_coin(NetFee),
                                                        coin_name)
                                                    response = f'You withdrew {num_format_coin(amount)} {token_display}{equivalent_usd} to _{address}_.\nTransaction hash: _{send_tx}_{fee_txt}'
                                                    await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                    await log_to_channel(
                                                        "withdraw",
                                                        f"[{user_server}] User {tw_user} successfully withdrew "\
                                                        f"{num_format_coin(amount)} "\
                                                        f"{token_display}{equivalent_usd}."
                                                    )
                                                    continue
                                                else:
                                                    await log_to_channel(
                                                        "withdraw",
                                                        f"[{user_server}] 🔴 User {tw_user} failed to withdraw "\
                                                        f"{num_format_coin(amount)} "\
                                                        f"{token_display}{equivalent_usd} to address {address}."
                                                    )
                                            elif type_coin == "HNT":
                                                wallet_host = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
                                                main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                                                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                                password = decrypt_string(
                                                    getattr(getattr(self.bot.coin_list, coin_name), "walletkey"))
                                                send_tx = await self.wallet_api.send_external_hnt(
                                                    each_msg['sender_id'], wallet_host, password,
                                                    main_address, address, amount, coin_decimal,
                                                    user_server, coin_name, NetFee, 32
                                                )
                                                if send_tx:
                                                    fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                                        num_format_coin(NetFee),
                                                        coin_name)
                                                    response = f"You withdrew {num_format_coin(amount)} "\
                                                        f"{token_display}{equivalent_usd} to _{address}_.\nTransaction hash: _{send_tx}_{fee_txt}"
                                                    await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                    await log_to_channel(
                                                        "withdraw",
                                                        f"[{user_server}] User {tw_user} successfully withdrew "\
                                                        f"{num_format_coin(amount)} "\
                                                        f"{token_display}{equivalent_usd}."
                                                    )
                                                    continue
                                                else:
                                                    await log_to_channel(
                                                        "withdraw",
                                                        f"[{user_server}] 🔴 User {tw_user} failed to withdraw "\
                                                        f"{num_format_coin(amount)} "\
                                                        f"{token_display}{equivalent_usd} to address {address}."
                                                    )

                                            elif type_coin == "ADA":
                                                if not address.startswith("addr1"):
                                                    response = f'Invalid address. It should start with `addr1`.'
                                                    await update_bot_response(each_msg['text'], response, each_msg['id'])
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
                                                        fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                                            num_format_coin(fee),
                                                            coin_name)
                                                        response = f"You withdrew {num_format_coin(amount)} "\
                                                            f"{token_display}{equivalent_usd} to _{address}_.\nTransaction hash: "\
                                                            f"_{tx_hash}_{fee_txt}"
                                                        await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                        await log_to_channel(
                                                            "withdraw",
                                                            f"[{user_server}] User {tw_user} successfully withdrew "\
                                                            f"{num_format_coin(amount)} "\
                                                            f"{token_display}{equivalent_usd}."
                                                        )
                                                        continue
                                                    elif "code" in send_tx and "message" in send_tx:
                                                        code = send_tx['code']
                                                        message = send_tx['message']
                                                        response = f'Internal error, please try again later!'
                                                        await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                        await log_to_channel(
                                                            "withdraw",
                                                            f"[{user_server}] 🔴 User {tw_user} failed to withdraw "\
                                                            f"{num_format_coin(amount)} "\
                                                            f"{token_display}{equivalent_usd} to address {address}.```code: {code}\nmessage: {message}```"
                                                        )
                                                        continue
                                                    else:
                                                        response = f'Internal error, please try again later!'
                                                        await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                        await log_to_channel(
                                                            "withdraw",
                                                            f"[{user_server}] 🔴 User {tw_user} failed to withdraw "\
                                                            f"{num_format_coin(amount)} "\
                                                            f"{token_display}{equivalent_usd} to address {address}."
                                                        )
                                                        continue
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
                                                                userdata_balance = await self.wallet_api.user_balance(
                                                                    each_msg['sender_id'], GAS_COIN, wallet_address,
                                                                    type_coin, height,
                                                                    getattr(getattr(self.bot.coin_list, GAS_COIN), "deposit_confirm_depth"),
                                                                    user_server
                                                                )
                                                                actual_balance = userdata_balance['adjust']
                                                                if actual_balance < fee_limit:  # use fee_limit to limit ADA
                                                                    response = f"You do not have sufficient {GAS_COIN} to withdraw {coin_name}. "\
                                                                        f"You need to have at least a reserved `{fee_limit} {GAS_COIN}`."
                                                                    await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                                    await log_to_channel(
                                                                        "withdraw",
                                                                        f"[{user_server}] User {tw_user} want to withdraw asset "\
                                                                        f"{coin_name} but having only {actual_balance} {GAS_COIN}."
                                                                    )
                                                                    continue
                                                            else:
                                                                response = 'Invalid main token, please report!'
                                                                await log_to_channel(
                                                                    "withdraw",
                                                                    f"[{user_server}] [BUG] {tw_user} invalid main token for {coin_name}."
                                                                )
                                                                await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                                continue
                                                    except Exception:
                                                        traceback.print_exc(file=sys.stdout)
                                                        response = 'I cannot check balance, please try again later!'
                                                        await log_to_channel(
                                                            "withdraw",
                                                            f"[{user_server}] User {tw_user} failed to check balance gas coin for "\
                                                            f"asset transfer..."
                                                        )
                                                        await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                        continue

                                                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                                    asset_name = getattr(getattr(self.bot.coin_list, coin_name), "header")
                                                    policy_id = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                                                    send_tx = await self.wallet_api.send_external_ada_asset(
                                                        each_msg['sender_id'], amount, coin_decimal, user_server,
                                                        coin_name, NetFee, address, asset_name, policy_id, 120)
                                                    if "status" in send_tx and send_tx['status'] == "pending":
                                                        tx_hash = send_tx['id']
                                                        gas_coin_msg = ""
                                                        if GAS_COIN is not None:
                                                            gas_coin_msg = " and fee __{} {}__ you shall receive additional __{} {}__.".format(
                                                                num_format_coin(send_tx['network_fee'] + fee_limit / 20), GAS_COIN,
                                                                num_format_coin(send_tx['ada_received']), GAS_COIN)
                                                        fee_txt = "\nWithdrew fee/node: __{} {}__{}.".format(
                                                            num_format_coin(NetFee),
                                                            coin_name, gas_coin_msg)
                                                        response = f"You withdrew {num_format_coin(amount)} "\
                                                            f"{token_display}{equivalent_usd} to _{address}_.\nTransaction hash: "\
                                                            f"_{tx_hash}_{fee_txt}"
                                                        await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                        await log_to_channel(
                                                            "withdraw",
                                                            f"[{user_server}] User {tw_user} successfully withdrew "\
                                                            f"{num_format_coin(amount)} "\
                                                            f"{token_display}{equivalent_usd}."
                                                        )
                                                        continue
                                                    elif "code" in send_tx and "message" in send_tx:
                                                        code = send_tx['code']
                                                        message = send_tx['message']
                                                        response = f'Internal error, please try again later!'
                                                        await log_to_channel(
                                                            "withdraw",
                                                            f"[{user_server}] 🔴 User {tw_user} failed to withdraw "\
                                                            f"{num_format_coin(amount)} "\
                                                            f"{token_display}{equivalent_usd} to address {address}.```code: {code}\nmessage: {message}```"
                                                        )
                                                    else:
                                                        response = f'Internal error, please try again later!'
                                                        await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                        await log_to_channel(
                                                            "withdraw",
                                                            f"[{user_server}] 🔴 User {tw_user} failed to withdraw "\
                                                            f"{num_format_coin(amount)} "\
                                                            f"{token_display}{equivalent_usd} to address {address}."
                                                        )
                                                        continue
                                                    continue
                                            elif type_coin == "SOL" or type_coin == "SPL":
                                                tx_fee = getattr(getattr(self.bot.coin_list, coin_name), "tx_fee")
                                                send_tx = await self.wallet_api.send_external_sol(
                                                    "http://{}:{}/send_transaction".format(self.bot.config['api_helper']['connect_ip'], self.bot.config['api_helper']['port_solana']),
                                                    self.bot.erc_node_list['SOL'], each_msg['sender_id'], amount,
                                                    address, coin_name, coin_decimal, tx_fee, NetFee, user_server)
                                                if send_tx:
                                                    fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                                        num_format_coin(NetFee),
                                                        coin_name)
                                                    response = f'You withdrew {num_format_coin(amount)} {token_display}{equivalent_usd} to _{address}_.\nTransaction hash: _{send_tx}_{fee_txt}'
                                                    await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                    await log_to_channel(
                                                        "withdraw",
                                                        f"[{user_server}] User {tw_user} successfully withdrew "\
                                                        f"{num_format_coin(amount)} "\
                                                        f"{token_display}{equivalent_usd}."
                                                    )
                                                    continue
                                                else:
                                                    await log_to_channel(
                                                        "withdraw",
                                                        f"[{user_server}] 🔴 User {tw_user} failed to withdraw "\
                                                        f"{num_format_coin(amount)} "\
                                                        f"{token_display}{equivalent_usd} to address {address}."
                                                    )
                                            elif type_coin == "BTC":
                                                send_tx = await self.wallet_api.send_external_doge(
                                                    each_msg['sender_id'], amount, address,
                                                    coin_name, 0, NetFee, user_server)  # tx_fee=0
                                                if send_tx:
                                                    fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                                        num_format_coin(NetFee),
                                                        coin_name)
                                                    response = f'You withdrew {num_format_coin(amount)} {token_display}{equivalent_usd} to _{address}_.\nTransaction hash: _{send_tx}_{fee_txt}'
                                                    await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                    await log_to_channel(
                                                        "withdraw",
                                                        f"[{user_server}] User {tw_user} successfully withdrew "\
                                                        f"{num_format_coin(amount)} "\
                                                        f"{token_display}{equivalent_usd}."
                                                    )
                                                    continue
                                                else:
                                                    await log_to_channel(
                                                        "withdraw",
                                                        f"[{user_server}] [FAILED] User {tw_user} failed to "\
                                                        f"withdraw {num_format_coin(amount)} "\
                                                        f"{token_display}{equivalent_usd}."
                                                    )
                                            elif type_coin == "XMR" or type_coin == "TRTL-API" or type_coin == "TRTL-SERVICE" or type_coin == "BCN":
                                                main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                                                mixin = getattr(getattr(self.bot.coin_list, coin_name), "mixin")
                                                wallet_address = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
                                                header = getattr(getattr(self.bot.coin_list, coin_name), "header")
                                                is_fee_per_byte = getattr(getattr(self.bot.coin_list, coin_name), "is_fee_per_byte")
                                                send_tx = await self.wallet_api.send_external_xmr(
                                                    type_coin, main_address, each_msg['sender_id'],
                                                    amount, address, coin_name, coin_decimal, tx_fee,
                                                    NetFee, is_fee_per_byte, mixin, user_server,
                                                    wallet_address, header, None
                                                )  # paymentId: None (end)
                                                if send_tx:
                                                    fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                                        num_format_coin(NetFee),
                                                        coin_name)
                                                    response = f'You withdrew {num_format_coin(amount)} {token_display}{equivalent_usd} to _{address}_.\nTransaction hash: _{send_tx}_{fee_txt}'
                                                    await update_bot_response(each_msg['text'], response, each_msg['id'])
                                                    await log_to_channel(
                                                        "withdraw",
                                                        f"[{user_server}] User {tw_user} successfully executed withdraw "\
                                                        f"{num_format_coin(amount)} {token_display}{equivalent_usd}."
                                                    )
                                                    continue
                                                else:
                                                    await log_to_channel(
                                                        "withdraw",
                                                        f"[{user_server}] User {tw_user} failed to execute to withdraw "\
                                                        f"{num_format_coin(amount)} {token_display}{equivalent_usd} to address {address}."
                                                    )  # ctx
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                            elif each_msg['text'].lower().startswith("help"):
                                response = "[In progress] - Please refer to http://chat.wrkz.work"
                                await update_bot_response(each_msg['text'], response, each_msg['id'])
                                continue
                            else:
                                sql = """
                                UPDATE `twitter_fetch_bot_messages` 
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
                    sql = """
                    SELECT * FROM `twitter_linkme` 
                    WHERE `is_verified`=1 
                    """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each_t_user in result:
                            twitter_discord_user[each_t_user['id_str']] = each_t_user[
                                'discord_user_id']  # twitter[id]= discord
                    # get unpaid reward
                    sql = """
                    SELECT * FROM `twitter_rt_reward_logs` 
                    WHERE `rewarded_user` IS NULL AND `is_credited`=%s 
                    AND `notified_confirmation`=%s AND `failed_notification`=%s AND `unverified_reward`=%s
                    """
                    await cur.execute(sql, ("NO", "NO", "NO", "NO"))
                    reward_tos = await cur.fetchall()
                    if reward_tos and len(reward_tos) > 0:
                        # there is pending reward
                        for each_reward in reward_tos:
                            if each_reward['expired_date'] and each_reward['expired_date'] < int(time.time()):
                                # Expired.
                                sql = """
                                UPDATE `twitter_rt_reward_logs` 
                                SET `unverified_reward`=%s
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
                                    serverinfo = self.bot.other_data['guild_list'].get(each_reward['guild_id'])
                                    # Check if new link is updated. If yes, we ignore it
                                    if serverinfo['rt_link'] and each_reward['tweet_link'] != serverinfo['rt_link']:
                                        # Update
                                        sql = """
                                        UPDATE `twitter_rt_reward_logs` 
                                        SET `unverified_reward`=%s
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
                                        price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                                        user_from = await self.wallet_api.sql_get_userwallet(
                                            each_reward['guild_id'], coin_name, net_name, type_coin, SERVER_BOT, 0
                                        )
                                        if user_from is None:
                                            user_from = await self.wallet_api.sql_register_user(
                                                each_reward['guild_id'], coin_name, net_name, type_coin, SERVER_BOT, 0
                                            )
                                        wallet_address = user_from['balance_wallet_address']
                                        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                            wallet_address = user_from['paymentid']
                                        height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)

                                        # height can be None
                                        userdata_balance = await store.sql_user_balance_single(
                                            each_reward['guild_id'], coin_name, wallet_address,
                                            type_coin, height, deposit_confirm_depth, SERVER_BOT
                                        )
                                        total_balance = userdata_balance['adjust']
                                        amount = serverinfo['rt_reward_amount']
                                        if total_balance < amount:
                                            # Alert guild owner
                                            try:
                                                sql = """
                                                UPDATE `twitter_rt_reward_logs` 
                                                SET `rewarded_user`=%s, `is_credited`=%s, 
                                                    `notified_confirmation`=%s, `time_notified`=%s, `shortage_balance`=%s 
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
                                                per_unit = None
                                                if price_with:
                                                    per_unit = await self.utils.get_coin_price(coin_name, price_with)
                                                    if per_unit and per_unit['price'] and per_unit['price'] > 0:
                                                        per_unit = per_unit['price']
                                                if per_unit and per_unit > 0:
                                                    amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                                                try:
                                                    sql = """
                                                    UPDATE `twitter_rt_reward_logs` 
                                                    SET `rewarded_user`=%s, `is_credited`=%s, 
                                                        `notified_confirmation`=%s, `time_notified`=%s 
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

                                                tip = await store.sql_user_balance_mv_single(
                                                    each_reward['guild_id'], each_discord_user,
                                                    "TWITTER", "TWITTER", amount, coin_name,
                                                    "RETWEET", coin_decimal, SERVER_BOT, contract,
                                                    amount_in_usd, None
                                                )
                                                if member is not None:
                                                    msg = f"Thank you for RT <{twitter_link}>. You just got a reward of "\
                                                        f"{num_format_coin(amount)} {coin_name}."
                                                    try:
                                                        await member.send(msg)
                                                        guild_owner = self.bot.get_user(guild.owner.id)
                                                        try:
                                                            await guild_owner.send(
                                                                f"User __{each_discord_user}__ RT your twitter at <{twitter_link}>. "\
                                                                f"He/she just got a reward of "\
                                                                f"{num_format_coin(amount)} {coin_name}."
                                                            )
                                                        except Exception:
                                                            pass
                                                        # Log channel if there is
                                                        try:
                                                            if serverinfo and serverinfo['rt_reward_channel']:
                                                                channel = self.bot.get_channel(
                                                                    int(serverinfo['rt_reward_channel']))
                                                                embed = disnake.Embed(title="NEW RETWEET REWARD!",
                                                                                      timestamp=datetime.now())
                                                                embed.add_field(
                                                                    name="User",
                                                                    value="<@{}>".format(each_discord_user),
                                                                    inline=True
                                                                )
                                                                embed.add_field(
                                                                    name="Reward",
                                                                    value="{} {}".format(
                                                                        num_format_coin(amount),
                                                                        coin_name
                                                                    ),
                                                                    inline=True)
                                                                embed.add_field(name="RT Link",
                                                                                value=f"<{twitter_link}>", inline=False)
                                                                embed.set_author(
                                                                    name=self.bot.user.name,
                                                                    icon_url=self.bot.user.display_avatar
                                                                )
                                                                await channel.send(embed=embed)
                                                        except Exception:
                                                            traceback.print_exc(file=sys.stdout)
                                                            await logchanbot(
                                                                f'[TWITTER] Failed to send message to retweet reward to channel in guild: __{guild_id}__ / {guild.name}.')
                                                    except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                                        await logchanbot(
                                                            f'[TWITTER] Failed to thank message to <@{each_discord_user}>.')
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                            else:
                                # this is not verified. Update it
                                sql = """
                                UPDATE `twitter_rt_reward_logs` 
                                SET `unverified_reward`=%s
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
                for eachTx in notify_list:
                    try:
                        key = "notify_new_tx_erc20_{}_{}_{}".format(
                            eachTx['token_name'], eachTx['user_id'], eachTx['txn']
                        )
                        if self.ttlcache[key] == key:
                            continue
                        else:
                            self.ttlcache[key] = key
                    except Exception:
                        pass
                    is_notify_failed = False
                    member = self.bot.get_user(int(eachTx['user_id']))
                    if member:
                        update_status = await store.sql_updating_pending_move_deposit_erc20(
                            True, is_notify_failed, eachTx['txn']
                        )
                        if update_status > 0:
                            msg = "You got a new deposit confirmed: ```" + "Amount: {} {}".format(
                                num_format_coin(
                                    eachTx['real_amount']
                                ),
                                eachTx['token_name']
                            ) + "```"
                            try:
                                await log_to_channel(
                                    "deposit",
                                    "[DEPOSIT] {} {} from <@{}> / {}. ref: {}".format(
                                        num_format_coin(eachTx['real_amount']),
                                        eachTx['token_name'], eachTx['user_id'], eachTx['user_id'], eachTx['txn']
                                    ),
                                    self.bot.config['discord']['deposit_webhook']
                                )
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
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
                for eachTx in notify_list:
                    try:
                        key = "notify_new_tx_trc20_{}_{}_{}".format(
                            eachTx['token_name'], eachTx['user_id'], eachTx['txn']
                        )
                        if self.ttlcache[key] == key:
                            continue
                        else:
                            self.ttlcache[key] = key
                    except Exception:
                        pass
                    is_notify_failed = False
                    member = self.bot.get_user(int(eachTx['user_id']))
                    if member:
                        update_status = await store.sql_updating_pending_move_deposit_trc20(
                            True, is_notify_failed, eachTx['txn']
                        )
                        if update_status > 0:
                            msg = "You got a new deposit confirmed: ```" + "Amount: {} {}".format(
                                num_format_coin(
                                    eachTx['real_amount']
                                ),
                                eachTx['token_name']
                            ) + "```"
                            try:
                                await log_to_channel(
                                    "deposit",
                                    "[DEPOSIT] {} {} from <@{}> / {}. ref: {}".format(
                                        num_format_coin(eachTx['real_amount']),
                                        eachTx['token_name'], eachTx['user_id'], eachTx['user_id'], eachTx['txn']
                                    ),
                                    self.bot.config['discord']['deposit_webhook']
                                )
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
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
                    sql = """
                    SELECT * FROM `hnt_get_transfers` 
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
                                    key = "notify_new_tx_{}_{}_{}".format(
                                        eachTx['coin_name'], eachTx['user_id'], eachTx['txid']
                                    )
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['coin_name']), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + \
                                        "Coin: {}\nTx: {}\nAmount: {}".format(
                                            eachTx['coin_name'], eachTx['txid'],
                                            num_format_coin(eachTx['amount'])
                                        ) + "```"
                                    try:
                                        await member.send(msg)
                                        sql = """
                                        UPDATE `hnt_get_transfers` 
                                        SET `notified_confirmation`=%s, `time_notified`=%s 
                                        WHERE `txid`=%s LIMIT 1
                                        """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['txid']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """
                                        UPDATE `hnt_get_transfers` 
                                        SET `notified_confirmation`=%s, `failed_notification`=%s 
                                        WHERE `txid`=%s LIMIT 1
                                        """
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
                        async with session.post(
                            getattr(getattr(self.bot.coin_list, coin_name), "wallet_address"),
                            headers=headers,
                            json=json_data,
                            timeout=timeout
                        ) as response:
                            if response.status == 200:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                decoded_data = json.loads(res_data)
                                if 'result' in decoded_data:
                                    height = int(decoded_data['result'])
                                    try:
                                        await self.utils.async_set_cache_kv(
                                            "block",
                                            f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}",
                                            height
                                        )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                except Exception:
                    traceback.print_exc(file=sys.stdout)

                async def fetch_api(ua: str, url, timeout):
                    try:
                        headers = {
                            'User-Agent': ua
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
                                sql = """
                                SELECT * FROM `hnt_get_transfers`
                                """
                                await cur.execute(sql, )
                                result = await cur.fetchall()
                                if result: return result
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    return []

                # Get list of tx from API:
                main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                url = getattr(getattr(self.bot.coin_list, coin_name), "rpchost") + "accounts/" + main_address + "/roles"
                fetch_data = await fetch_api(self.bot.config['discord']['default_browser_agent'], url, timeout)
                incoming = []  ##payments
                if fetch_data is not None and 'data' in fetch_data:
                    # Check if len data is 0
                    if len(fetch_data['data']) == 0 and 'cursor' in fetch_data:
                        url2 = getattr(getattr(self.bot.coin_list, coin_name),
                                       "rpchost") + "accounts/" + main_address + "/roles/?cursor=" + fetch_data[
                                   'cursor']
                        # get with cursor
                        fetch_data_2 = await fetch_api(self.bot.config['discord']['default_browser_agent'], url2, timeout)
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
                        fetch_data_2 = await fetch_api(self.bot.config['discord']['default_browser_agent'], url2, timeout)
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
                            fetch_tx = await fetch_api(self.bot.config['discord']['default_browser_agent'], url_tx, timeout)
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
                                                        "{} MEMO: {}".format(main_address, memo), coin_name, coin_family
                                                    )
                                                    if user_memo is not None and user_memo['user_id']:
                                                        user_id = user_memo['user_id']
                                                await self.openConnection()
                                                async with self.pool.acquire() as conn:
                                                    async with conn.cursor() as cur:
                                                        sql = """
                                                        INSERT INTO `hnt_get_transfers` 
                                                        (`coin_name`, `user_id`, `txid`, `height`, `timestamp`, 
                                                        `amount`, `fee`, `decimal`, `address`, `memo`, 
                                                        `payer`, `time_insert`, `user_server`) 
                                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                                        """
                                                        await cur.execute(sql, (
                                                            coin_name, user_id, tx_hash, height, blockTime, amount, fee,
                                                            coin_decimal, each_payment['payee'], memo, payer, int(time.time()),
                                                            user_memo['user_server'] if user_memo else None
                                                        ))
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
                    sql = """
                    SELECT * FROM `vite_get_transfers` 
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
                                    key = "notify_new_tx_{}_{}_{}".format(
                                        eachTx['coin_name'], eachTx['user_id'], eachTx['txid']
                                    )
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['coin_name']), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + \
                                        "Coin: {}\nTx: {}\nAmount: {}".format(
                                            eachTx['coin_name'], eachTx['txid'],
                                            num_format_coin(eachTx['amount'])
                                        ) + "```"
                                    try:
                                        await log_to_channel(
                                            "deposit",
                                            "[DEPOSIT] {} {} from <@{}> / {}. ref: {}".format(
                                                num_format_coin(eachTx['amount']),
                                                eachTx['coin_name'], eachTx['user_id'], eachTx['user_id'], eachTx['txid']
                                            ),
                                            self.bot.config['discord']['deposit_webhook']
                                        )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    try:
                                        await member.send(msg)
                                        sql = """
                                        UPDATE `vite_get_transfers` 
                                        SET `notified_confirmation`=%s, `time_notified`=%s 
                                        WHERE `txid`=%s LIMIT 1
                                        """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['txid']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """
                                        UPDATE `vite_get_transfers` 
                                        SET `notified_confirmation`=%s, `failed_notification`=%s 
                                        WHERE `txid`=%s LIMIT 1
                                        """
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
                        sql = """
                        SELECT * FROM `vite_get_transfers`
                        """
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
            if not hasattr(self.bot.coin_list, coin_name):
                return
            url = getattr(getattr(self.bot.coin_list, coin_name), "rpchost")
            main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
            height = await vite_get_height(url)
            coin_family = getattr(getattr(self.bot.coin_list, coin_name), "type")
            if height and height > 0:
                try:
                    await self.utils.async_set_cache_kv(
                        "block",
                        f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}",
                        height
                    )
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
                            memo = None

                            if get_tx['toAddress'] == main_address and \
                                int(get_tx['confirmations']) > 0 and get_tx['tokenInfo']['tokenId'] in vite_contracts \
                                    and int(get_tx['amount']) > 0:
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
                                try:
                                    if get_tx['data'] and len(get_tx['data']) > 0:
                                        memo = base64.b64decode(get_tx['data']).decode()
                                        user_memo = await store.sql_get_userwallet_by_paymentid(
                                            "{} MEMO: {}".format(main_address, memo.strip()),
                                            coin_name, coin_family
                                        )
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
 
                                if user_memo is not None and user_memo['user_id'] is not None:
                                    user_id = user_memo['user_id']

                                if amount > 0:
                                    await self.openConnection()
                                    async with self.pool.acquire() as conn:
                                        async with conn.cursor() as cur:
                                            sql = """
                                            INSERT INTO `vite_get_transfers`
                                            (`coin_name`, `user_id`, `txid`, `contents`,`height`, `amount`, `fee`, `decimal`, `address`, 
                                            `memo`, `time_insert`, `user_server`) 
                                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                            """
                                            await cur.execute(sql, (
                                                coin_name, user_id, tx_hash, json.dumps(get_tx), height, amount, fee,
                                                coin_decimal, main_address, memo, int(time.time()),
                                                user_memo['user_server'] if user_memo else None
                                            ))
                                            await conn.commit()
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def notify_new_confirmed_cosmos(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_new_confirmed_cosmos"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `cosmos_get_transfers` 
                    WHERE `notified_confirmation`=%s AND `failed_notification`=%s AND `user_server`=%s
                    """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            try:
                                if eachTx['user_id']:
                                    if not eachTx['user_id'].isdigit():
                                        continue
                                    try:
                                        key = "notify_new_tx_{}_{}_{}".format(
                                            eachTx['coin_name'], eachTx['user_id'], eachTx['txid']
                                        )
                                        if self.ttlcache[key] == key:
                                            continue
                                        else:
                                            self.ttlcache[key] = key
                                    except Exception:
                                        pass
                                    member = self.bot.get_user(int(eachTx['user_id']))
                                    if member is not None:
                                        coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['coin_name']), "decimal")
                                        msg = "You got a new deposit (it could take a few minutes to credit): ```" + \
                                            "Coin: {}\nTx: {}\nAmount: {}".format(
                                                eachTx['coin_name'], eachTx['txid'],
                                                num_format_coin(eachTx['amount'])
                                            ) + "```"
                                        try:
                                            await log_to_channel(
                                                "deposit",
                                                "[DEPOSIT] {} {} from <@{}> / {}. ref: {}".format(
                                                    num_format_coin(eachTx['amount']),
                                                    eachTx['coin_name'], eachTx['user_id'], eachTx['user_id'], eachTx['txid']
                                                ),
                                                self.bot.config['discord']['deposit_webhook']
                                            )
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                        try:
                                            await member.send(msg)
                                            sql = """
                                            UPDATE `cosmos_get_transfers` 
                                            SET `notified_confirmation`=%s, `time_notified`=%s
                                            WHERE `txid`=%s LIMIT 1
                                            """
                                            await cur.execute(sql, ("YES", int(time.time()), eachTx['txid']))
                                            await conn.commit()
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                            sql = """
                                            UPDATE `cosmos_get_transfers` 
                                            SET `notified_confirmation`=%s, `failed_notification`=%s
                                            WHERE `txid`=%s LIMIT 1
                                            """
                                            await cur.execute(sql, ("NO", "YES", eachTx['txid']))
                                            await conn.commit()
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def update_balance_cosmos(self):
        time_lap = 5  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "update_balance_cosmos"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)

        async def get_cosmos_transactions(ua: str, endpoint: str, account_addr: str):
            try:
                headers = {
                    'Content-Type': 'application/json',
                    'User-Agent': ua
                }
                url = endpoint + "?pagination.limit=50&events=coin_received.receiver={}&order_by=ORDER_BY_DESC".format("%27" + account_addr + "%27")
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url,
                        headers=headers, timeout=60
                    ) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            res_data = res_data.decode('utf-8')
                            decoded_data = json.loads(res_data)
                            if len(decoded_data) > 0:
                                return decoded_data
                        else:
                            print(url)
                            print("update_balance_cosmos return status: {}".format(response.status))
            except asyncio.exceptions.TimeoutError:
                print("update_balance_cosmos timeout for {}".format(url))
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return []

        async def get_tx_incoming():
            try:
                await self.openConnection()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        sql = """
                        SELECT * FROM `cosmos_get_transfers`
                        """
                        await cur.execute(sql,)
                        result = await cur.fetchall()
                        if result:
                            return result
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return []

        async def update_balance_cosmos_all(bot, coin_name: str, forced_coin: str=None):
            coin_family = "COSMOS"
            timeout = 30
            rpchost = getattr(getattr(bot.coin_list, coin_name), "rpchost")
            if not rpchost.endswith("/"):
                rpchost += "/"
            net_height = await cosmos_get_height(rpchost + "block", timeout)
            if net_height is None:
                print("cosmos cosmos_get_height: {} = None".format(coin_name))
                return
            else:
                try:
                    await self.utils.async_set_cache_kv(
                        "block",
                        f"{bot.config['kv_db']['prefix'] + bot.config['kv_db']['daemon_height']}{coin_name}",
                        net_height
                    )
                    # if there are other asset, set them all here
                except Exception:
                    traceback.print_exc(file=sys.stdout)

                try:
                    url = getattr(getattr(bot.coin_list, coin_name), "http_address")
                    main_address = getattr(getattr(bot.coin_list, coin_name), "MainAddress")
                    get_transactions = await get_cosmos_transactions(
                        self.bot.config['discord']['default_browser_agent'], url, main_address
                    )
                    if len(get_transactions) > 0:
                        get_incoming_tx = await get_tx_incoming()
                        list_existing_tx = []
                        if len(get_incoming_tx) > 0:
                            list_existing_tx = [each['txid'] for each in get_incoming_tx]
                        for each_tx in get_transactions['tx_responses']:
                            if each_tx['code'] != 0:
                                # skip
                                continue
                            try:
                                amount = 0.0
                                tx_hash = each_tx['txhash']
                                height = int(each_tx['height'])
                                if tx_hash in list_existing_tx:
                                    # Skip
                                    continue

                                user_id = None
                                user_memo = each_tx['tx']['body']['memo']
                                get_user_memo = None
                                if len(each_tx['tx']['body']['messages']) > 0:
                                    for each_from_to in each_tx['tx']['body']['messages']:
                                        from_addr = each_from_to['from_address']
                                        to_addr = each_from_to['to_address']
                                        if len(each_from_to['amount']) > 0:
                                            for each_amount in each_from_to['amount']:
                                                if forced_coin is None:
                                                    get_denom = await self.wallet_api.cosmos_get_coin_by_denom(each_amount['denom'])
                                                    if get_denom is None:
                                                        continue
                                                    coin_name = get_denom['coin_name']
                                                else:
                                                    coin_name = forced_coin.upper()
                                                try:
                                                    await self.utils.async_set_cache_kv(
                                                        "block",
                                                        f"{bot.config['kv_db']['prefix'] + bot.config['kv_db']['daemon_height']}{coin_name}",
                                                        net_height
                                                    )
                                                    # if there are other asset, set them all here
                                                except Exception:
                                                    traceback.print_exc(file=sys.stdout)
                                                coin_decimal = getattr(getattr(bot.coin_list, coin_name), "decimal")
                                                amount = int(each_amount['amount']) / 10**coin_decimal
                                                if main_address == to_addr:
                                                    if user_memo and len(user_memo) > 0:
                                                        get_user_memo = await store.sql_get_userwallet_by_paymentid(
                                                            "{} MEMO: {}".format(main_address, user_memo),
                                                            coin_name, coin_family
                                                        )
                                                        if get_user_memo is not None and get_user_memo['user_id'] is not None:
                                                            user_id = get_user_memo['user_id']

                                                    if amount > 0:
                                                        await self.openConnection()
                                                        async with self.pool.acquire() as conn:
                                                            async with conn.cursor() as cur:
                                                                sql = """
                                                                INSERT INTO `cosmos_get_transfers` 
                                                                (`coin_name`, `user_id`, `txid`, `height`, `amount`, 
                                                                `decimal`, `address`, `memo`, `time_insert`, `user_server`) 
                                                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                                                """
                                                                await cur.execute(sql, (
                                                                    coin_name, user_id, tx_hash, height, amount,
                                                                    coin_decimal, main_address,
                                                                    user_memo if user_memo else None,
                                                                    int(time.time()),
                                                                    get_user_memo['user_server'] if get_user_memo else None
                                                                ))
                                                                await conn.commit()
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                except Exception:
                    traceback.print_exc(file=sys.stdout)

        tasks = []
        for coin_name in self.bot.config['cosmos']['list_coins']:
            if not hasattr(self.bot.coin_list, coin_name):
                continue
            if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 1 or \
                getattr(getattr(self.bot.coin_list, coin_name), "enable_deposit") == 0:
                continue
            forced_coin = None
            if coin_name in ["LUNC", "LUNA"]:
                forced_coin = coin_name
            tasks.append(update_balance_cosmos_all(self.bot, coin_name, forced_coin=forced_coin))

        completed = 0
        if len(tasks) > 0:
            for task in asyncio.as_completed(tasks):
                fetch_updates = await task
                if fetch_updates is True:
                    completed += 1
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
                    sql = """
                    SELECT * FROM `xlm_get_transfers` 
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
                                    key = "notify_new_tx_{}_{}_{}".format(
                                        eachTx['coin_name'], eachTx['user_id'], eachTx['txid']
                                    )
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['coin_name']), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + \
                                        "Coin: {}\nTx: {}\nAmount: {}".format(
                                            eachTx['coin_name'], eachTx['txid'],
                                            num_format_coin(eachTx['amount'])
                                        ) + "```"
                                    try:
                                        await log_to_channel(
                                            "deposit",
                                            "[DEPOSIT] {} {} from <@{}> / {}. ref: {}".format(
                                                num_format_coin(eachTx['amount']),
                                                eachTx['coin_name'], eachTx['user_id'], eachTx['user_id'], eachTx['txid']
                                            ),
                                            self.bot.config['discord']['deposit_webhook']
                                        )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    try:
                                        await member.send(msg)
                                        sql = """ UPDATE `xlm_get_transfers` 
                                            SET `notified_confirmation`=%s, `time_notified`=%s
                                            WHERE `txid`=%s LIMIT 1
                                            """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['txid']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `xlm_get_transfers` 
                                            SET `notified_confirmation`=%s, `failed_notification`=%s
                                            WHERE `txid`=%s LIMIT 1
                                            """
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
                                sql = """
                                SELECT * FROM `xlm_get_transfers`
                                """
                                await cur.execute(sql,)
                                result = await cur.fetchall()
                                if result: return result
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    return []

                headers = {
                    'Content-Type': 'application/json',
                    'User-Agent': self.bot.config['discord']['default_browser_agent']
                }
                # get status
                url = getattr(getattr(self.bot.coin_list, coin_name), "http_address")
                main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            url,
                            headers=headers,
                            timeout=timeout
                        ) as response:
                            if response.status == 200:
                                res_data = await response.read()
                                res_data = res_data.decode('utf-8')
                                decoded_data = json.loads(res_data)
                                if 'history_latest_ledger' in decoded_data:
                                    height = decoded_data['history_latest_ledger']
                                    try:
                                        await self.utils.async_set_cache_kv(
                                            "block",
                                            f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}",
                                            height
                                        )
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
                                                tx_envolop = functools.partial(
                                                    parse_transaction_envelope_from_xdr,
                                                    each_tx['envelope_xdr'],
                                                    Network.PUBLIC_NETWORK_PASSPHRASE
                                                )
                                                transaction_envelope = await self.bot.loop.run_in_executor(None, tx_envolop)
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
                                                        coin_name, coin_family
                                                    )
                                                    if user_memo is not None and user_memo['user_id'] is not None:
                                                        user_id = user_memo['user_id']
                                                if amount > 0:
                                                    await self.openConnection()
                                                    async with self.pool.acquire() as conn:
                                                        async with conn.cursor() as cur:
                                                            sql = """ INSERT INTO `xlm_get_transfers` 
                                                                (`coin_name`, `user_id`, `txid`, `height`, `amount`, `fee`, 
                                                                `decimal`, `address`, `memo`, `time_insert`, `user_server`) 
                                                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                                                """
                                                            await cur.execute(sql, (
                                                                coin_name, user_id, tx_hash, height, amount, fee,
                                                                coin_decimal, main_address,
                                                                each_tx['memo'].strip() if 'memo' in each_tx else None,
                                                                int(time.time()),
                                                                user_memo['user_server'] if user_memo else None
                                                            ))
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
                    sql = """ SELECT * FROM `ada_get_transfers` 
                        WHERE `notified_confirmation`=%s AND `failed_notification`=%s AND `user_server`=%s
                        """
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
                                        msg = "You got a new deposit (it could take a few minutes to credit): ```" + \
                                            "Coin: {}\nTx: {}\nAmount: {}".format(
                                                coin_name, eachTx['hash_id'],
                                                num_format_coin(eachTx['amount'])
                                            ) + "```"
                                        try:
                                            await log_to_channel(
                                                "deposit",
                                                "[DEPOSIT] {} {} from <@{}> / {}. ref: {}".format(
                                                    num_format_coin(eachTx['amount']),
                                                    eachTx['coin_name'], eachTx['user_id'], eachTx['user_id'], eachTx['hash_id']
                                                ),
                                                self.bot.config['discord']['deposit_webhook']
                                            )
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                        try:
                                            await member.send(msg)
                                            sql = """ UPDATE `ada_get_transfers` 
                                                SET `notified_confirmation`=%s, `time_notified`=%s 
                                                WHERE `hash_id`=%s AND `coin_name`=%s LIMIT 1
                                                """
                                            await cur.execute(sql, (
                                                "YES", int(time.time()), eachTx['hash_id'], coin_name
                                            ))
                                            await conn.commit()
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                            sql = """ UPDATE `ada_get_transfers` 
                                                SET `notified_confirmation`=%s, `failed_notification`=%s 
                                                WHERE `hash_id`=%s AND `coin_name`=%s LIMIT 1
                                                """
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
                    async with session.post(
                        url,
                        headers={'Content-Type': 'application/json'},
                        json=json.loads(data),
                        timeout=timeout
                    ) as response:
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

        await asyncio.sleep(time_lap)
        # update Height
        height = None
        try:
            getEpochInfo = await fetch_getEpochInfo(self.bot.erc_node_list['SOL'], 60)
            if getEpochInfo:
                height = getEpochInfo['absoluteSlot']
                try:
                    await self.utils.async_set_cache_kv(
                        "block",
                        f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}",
                        height
                    )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            # If this happen. Sleep and next
            await asyncio.sleep(time_lap)
            # continue

        try:
            lap = int(time.time()) - 3600 * 2
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `sol_user` 
                    WHERE `called_Update`>%s OR `is_discord_guild`=1
                    ORDER BY `called_Update` DESC
                    """
                    await cur.execute(sql, lap)
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        start = time.time()
                        print(f"{datetime.now():%Y-%m-%d %H:%M:%S}: SOL, there are {str(len(result))} to check balance...")
                        numb_update = 0
                        for each_addr in result:
                            if each_addr['last_move_deposit'] > int(time.time()) - 90:
                                continue
                            try:
                                proxy = "http://{}:{}".format(self.bot.config['api_helper']['connect_ip'], self.bot.config['api_helper']['port_solana'])
                                # get deposit balance if it's less than minimum
                                get_balance = await self.utils.solana_get_balance(
                                    proxy + "/get_balance_solana", self.bot.erc_node_list['SOL'], each_addr['balance_wallet_address'], 60
                                )
                                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                real_min_deposit = getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit")
                                tx_fee = getattr(getattr(self.bot.coin_list, coin_name), "tx_fee")
                                contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                                real_deposit_fee = getattr(getattr(self.bot.coin_list, coin_name), "real_deposit_fee")
                                if get_balance and get_balance.get('result'):
                                    actual_balance = float(get_balance['result']['balance'] / 10 ** coin_decimal)
                                    if actual_balance >= real_min_deposit:
                                        # Let's move
                                        remaining = int((actual_balance - tx_fee) * 10 ** coin_decimal)
                                        moving = await self.utils.solana_send_tx(
                                            proxy + "/send_transaction",
                                            self.bot.erc_node_list['SOL'],
                                            decrypt_string(each_addr['secret_key_hex']),
                                            self.bot.config['sol']['MainAddress'],
                                            remaining, timeout=60
                                        )
                                        if moving.get('hash'):
                                            numb_update += 1
                                            await self.openConnection()
                                            async with self.pool.acquire() as conn:
                                                async with conn.cursor() as cur:
                                                    sql = """
                                                    INSERT INTO `sol_move_deposit` 
                                                    (`token_name`, `contract`, `user_id`, `balance_wallet_address`, 
                                                    `to_main_address`, `real_amount`, `real_deposit_fee`, 
                                                    `token_decimal`, `txn`, `time_insert`, `user_server`) 
                                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                                                    UPDATE `sol_user` SET `last_move_deposit`=%s 
                                                    WHERE `balance_wallet_address`=%s LIMIT 1; """
                                                    await cur.execute(sql, (
                                                        coin_name, contract, each_addr['user_id'], each_addr['balance_wallet_address'],
                                                        self.bot.config['sol']['MainAddress'], actual_balance - tx_fee, real_deposit_fee,
                                                        coin_decimal, moving['hash'], int(time.time()), each_addr['user_server'], int(time.time()),
                                                        each_addr['balance_wallet_address']
                                                    ))
                                                    await conn.commit()
                                            # reset cache
                                            await self.utils.solana_reset_balance_cache(
                                                proxy + "/reset_cache/" + each_addr['balance_wallet_address'], 30
                                            )
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                        print(f"{datetime.now():%Y-%m-%d %H:%M:%S}: SOL, Finished check {str(len(result))} address(es) and updated {str(numb_update)} address(es). {str(time.time() - start)}s")
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
                    async with session.post(
                        url,
                        headers={'Content-Type': 'application/json'},
                        json=json_data,
                        timeout=timeout
                    ) as response:
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
                    sql = """ SELECT * FROM `sol_move_deposit` 
                        WHERE `status`=%s AND `time_insert`<%s
                        """
                    await cur.execute(sql, ("PENDING", time_insert))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each_mv in result:
                            fetch_tx = await fetch_getConfirmedTransaction(
                                self.bot.erc_node_list['SOL'], each_mv['txn'], 16
                            )
                            if fetch_tx:
                                get_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name),
                                                            "deposit_confirm_depth")
                                net_height = await self.utils.async_get_cache_kv(
                                    "block",
                                    f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}"
                                )
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
                                        sql = """ UPDATE `sol_move_deposit` 
                                            SET `blockNumber`=%s, `confirmed_depth`=%s, `status`=%s 
                                            WHERE `txn`=%s LIMIT 1
                                            """
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
                                                msg = "You got a new deposit (it could take a few minutes to credit): ```" + \
                                                    "Coin: {}\nMoved Tx: {}\nAmount: {}".format(
                                                        coin_name, each_mv['txn'],
                                                        num_format_coin(each_mv['real_amount'])
                                                    ) + "```"
                                                try:
                                                    await log_to_channel(
                                                        "deposit",
                                                        "[DEPOSIT] {} {} from <@{}> / {}. ref: {}".format(
                                                            num_format_coin(each_mv['real_amount']),
                                                            each_mv['token_name'], each_mv['user_id'], each_mv['user_id'], each_mv['txn']
                                                        ),
                                                        self.bot.config['discord']['deposit_webhook']
                                                    )
                                                except Exception:
                                                    traceback.print_exc(file=sys.stdout)
                                                try:
                                                    await member.send(msg)
                                                    sql = """ UPDATE `sol_move_deposit` 
                                                        SET `notified_confirmation`=%s, `time_notified`=%s 
                                                        WHERE `txn`=%s AND `token_name`=%s LIMIT 1
                                                        """
                                                    await cur.execute(sql, (
                                                    "YES", int(time.time()), each_mv['txn'], coin_name))
                                                    await conn.commit()
                                                except Exception:
                                                    traceback.print_exc(file=sys.stdout)
                                                    sql = """ UPDATE `sol_move_deposit` 
                                                        SET `notified_confirmation`=%s, `failed_notification`=%s 
                                                        WHERE `txn`=%s AND `token_name`=%s LIMIT 1
                                                        """
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
                                                    await self.utils.async_set_cache_kv(
                                                        "block",
                                                        f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{each_coin.upper()}",
                                                        height
                                                    )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    await self.openConnection()
                                    async with self.pool.acquire() as conn:
                                        async with conn.cursor() as cur:
                                            sql = """ UPDATE `ada_wallets` SET `status`=%s, `updated`=%s 
                                            WHERE `wallet_id`=%s LIMIT 1
                                            """
                                            await cur.execute(sql, (
                                                json.dumps(fetch_wallet), int(time.time()), each_wallet['wallet_id']
                                            ))
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
                                                sql = """ UPDATE `ada_wallets` SET `addresses`=%s 
                                                    WHERE `wallet_id`=%s LIMIT 1
                                                    """
                                                await cur.execute(sql, (addresses, each_wallet['wallet_id']))
                                                await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                            # if synced
                            if each_wallet['syncing'] is None and each_wallet['used_address'] > 0:
                                all_addresses = each_wallet['addresses'].split("\n")
                                # fetch txes last 48h
                                time_end = str(datetime.utcnow().isoformat()).split(".")[0] + "Z"
                                time_start = str((datetime.utcnow() - timedelta(hours=24.0)).isoformat()).split(".")[0] + "Z"
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
                                                    if each_output['address'] not in all_addresses:
                                                        continue  # skip this output because no address in...
                                                    coin_name = "ADA"
                                                    coin_family = getattr(getattr(self.bot.coin_list, coin_name),
                                                                          "type")
                                                    user_tx = await store.sql_get_userwallet_by_paymentid(
                                                        each_output['address'], coin_name, coin_family)
                                                    # ADA
                                                    data_rows.append((
                                                        user_tx['user_id'], coin_name, each_tx['id'],
                                                        each_tx['inserted_at']['height']['quantity'],
                                                        each_tx['direction'],
                                                        json.dumps(each_tx['inputs']),
                                                        json.dumps(each_tx['outputs']),
                                                        each_output['address'], None, None,
                                                        each_output['amount']['quantity'] / 10 ** 6, 6,
                                                        int(time.time()), user_tx['user_server']
                                                    ))
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
                                                                    data_rows.append((
                                                                        user_tx['user_id'], coin_name,
                                                                        each_tx['id'],
                                                                        each_tx['inserted_at']['height']['quantity'],
                                                                        each_tx['direction'],
                                                                        json.dumps(each_tx['inputs']),
                                                                        json.dumps(each_tx['outputs']),
                                                                        each_output['address'],
                                                                        asset_name, policyID,
                                                                        each_asset['quantity'] / 10 ** coin_decimal,
                                                                        coin_decimal, int(time.time()),
                                                                        user_tx['user_server']
                                                                    ))
                                                                    break
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                    if len(data_rows) > 0:
                                        try:
                                            await self.openConnection()
                                            async with self.pool.acquire() as conn:
                                                async with conn.cursor() as cur:
                                                    sql = """ INSERT INTO `ada_get_transfers` 
                                                        (`user_id`, `coin_name`, `hash_id`, `inserted_at_height`, 
                                                        `direction`, `input_json`, `output_json`, `output_address`, 
                                                        `asset_name`, `policy_id`, `amount`, `coin_decimal`, 
                                                        `time_insert`, `user_server`) 
                                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                                        """
                                                    await cur.executemany(sql, data_rows)
                                                    await conn.commit()
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    # To use with update_balance_trtl_api()
    async def update_balance_tasks_trtl_api(self, coin_name: str, debug: bool):
        if debug is True:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} Check balance {coin_name}", color="yellow")
        gettopblock = await self.gettopblock(coin_name, time_out=60)
        if gettopblock is None:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} Got None for top block {coin_name}", color="yellow")
            return
        height = int(gettopblock['block_header']['height'])
        try:
            await self.utils.async_set_cache_kv(
                "block",
                f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}",
                height
            )
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
                        if len(tx['transfers']) > 0 and height >= int(tx['blockHeight']) + get_confirm_depth and \
                            tx['transfers'][0]['amount'] >= get_min_deposit_amount and 'paymentID' in tx:
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
                                                getattr(getattr(self.bot.coin_list, coin_name), "type")
                                            )
                                            u_server = None
                                            user_id = None
                                            if user_paymentId:
                                                u_server = user_paymentId['user_server']
                                                user_id = user_paymentId['user_id']
                                            sql = """ INSERT IGNORE INTO `cn_get_transfers` 
                                                (`coin_name`, `user_id`, `txid`, `payment_id`, `height`, `timestamp`, 
                                                `amount`, `fee`, `decimal`, `address`, `time_insert`, `user_server`) 
                                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                                """
                                            await cur.execute(sql, (
                                                coin_name, user_id, tx['hash'], tx['paymentID'], tx['blockHeight'],
                                                tx['timestamp'], float(int(tx['transfers'][0]['amount']) / 10 ** coin_decimal),
                                                float(int(tx['fee']) / 10 ** coin_decimal), coin_decimal,
                                                address, int(time.time()), u_server
                                            ))
                                            await conn.commit()
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
        if debug is True:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} End check balance {coin_name}", color="green")
        return True

    @tasks.loop(seconds=60.0)
    async def notify_balance_bcn(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_balance_bcn"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `cn_get_transfers` 
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
                                    key = "notify_new_tx_{}_{}_{}".format(
                                        eachTx['coin_name'], eachTx['user_id'], eachTx['txid']
                                    )
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['coin_name']), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + \
                                        "Coin: {}\nTx: {}\nAmount: {}".format(
                                            eachTx['coin_name'], eachTx['txid'],
                                            num_format_coin(eachTx['amount'])
                                        ) + "```"
                                    try:
                                        await log_to_channel(
                                            "deposit",
                                            "[DEPOSIT] {} {} from <@{}> / {}. ref: {}".format(
                                                num_format_coin(eachTx['amount']),
                                                eachTx['coin_name'], eachTx['user_id'], eachTx['user_id'], eachTx['txid']
                                            ),
                                            self.bot.config['discord']['deposit_webhook']
                                        )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    try:
                                        await member.send(msg)
                                        sql = """ UPDATE `cn_get_transfers` 
                                            SET `notified_confirmation`=%s, `time_notified`=%s 
                                            WHERE `txid`=%s LIMIT 1
                                            """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['txid']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `cn_get_transfers` 
                                            SET `notified_confirmation`=%s, `failed_notification`=%s 
                                            WHERE `txid`=%s LIMIT 1
                                            """
                                        await cur.execute(sql, ("NO", "YES", eachTx['txid']))
                                        await conn.commit()
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
            list_trtl_api = await store.get_coin_settings("TRTL-API")
            if len(list_trtl_api) > 0:
                list_coins = [each['coin_name'].upper() for each in list_trtl_api]
                tasks = []
                for coin_name in list_coins:
                    if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 1 or getattr(
                            getattr(self.bot.coin_list, coin_name), "enable_deposit") == 0:
                        continue
                    tasks.append(self.update_balance_tasks_trtl_api(coin_name, False))

                completed = 0
                for task in asyncio.as_completed(tasks):
                    fetch_updates = await task
                    if fetch_updates is True:
                        completed += 1
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    # To use with update_balance_trtl_service()
    async def update_balance_tasks_trtl_service(self, coin_name: str, debug: bool):
        if debug is True:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} Check balance {coin_name}", color="yellow")
        gettopblock = await self.gettopblock(coin_name, time_out=60)
        if gettopblock is None:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} gettopblock {coin_name} got None", color="red")
            return
        height = int(gettopblock['block_header']['height'])
        try:
            await self.utils.async_set_cache_kv(
                "block",
                f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}",
                height
            )
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
                                                    getattr(getattr(self.bot.coin_list, coin_name), "type")
                                                )
                                                u_server = None
                                                user_id = None
                                                if user_paymentId:
                                                    u_server = user_paymentId['user_server']
                                                    user_id = user_paymentId['user_id']
                                                sql = """ INSERT IGNORE INTO `cn_get_transfers` 
                                                    (`coin_name`, `user_id`, `txid`, `payment_id`, `height`, `timestamp`, `amount`, `fee`, 
                                                    `decimal`, `address`, `time_insert`, `user_server`) 
                                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                                    """
                                                await cur.execute(sql, (
                                                    coin_name, user_id, tx['transactionHash'], tx['paymentId'],
                                                    tx['blockIndex'], tx['timestamp'],
                                                    float(tx['amount'] / 10 ** coin_decimal),
                                                    float(tx['fee'] / 10 ** coin_decimal), coin_decimal,
                                                    address, int(time.time()), u_server
                                                ))
                                                await conn.commit()
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
        if debug is True:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} End check balance {coin_name}", color="green")
        return True

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
                tasks = []
                list_coins = [each['coin_name'].upper() for each in list_trtl_service + list_bcn_service]
                for coin_name in list_coins:
                    if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 1 or getattr(
                            getattr(self.bot.coin_list, coin_name), "enable_deposit") == 0:
                        continue
                    tasks.append(self.update_balance_tasks_trtl_service(coin_name, False))
            completed = 0
            for task in asyncio.as_completed(tasks):
                fetch_updates = await task
                if fetch_updates is True:
                    completed += 1
                
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    # To use with update_balance_xmr()
    async def update_balance_tasks_xmr(self, coin_name: str, debug: bool):
        if debug is True:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} Check balance {coin_name}", color="yellow")
        gettopblock = await self.gettopblock(coin_name, time_out=60)
        if gettopblock is None:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} Got None for top block {coin_name}", color="yellow")
            return
        height = int(gettopblock['block_header']['height'])
        try:
            await self.utils.async_set_cache_kv(
                "block",
                f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}",
                height
            )
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

        get_transfers = await self.wallet_api.call_aiohttp_wallet_xmr_bcn(
            'get_transfers', coin_name, payload=payload
        )
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
                                        user_id = None
                                        if user_paymentId:
                                            u_server = user_paymentId['user_server']
                                            user_id = user_paymentId['user_id']
                                        sql = """ INSERT IGNORE INTO `cn_get_transfers` (`coin_name`, `user_id`, `in_out`, `txid`, `payment_id`, 
                                            `height`, `timestamp`, `amount`, `fee`, `decimal`, `address`, `time_insert`, `user_server`) 
                                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                            """
                                        await cur.execute(sql, (
                                            coin_name, user_id, tx['type'].upper(), tx['txid'], tx['payment_id'],
                                            tx['height'], tx['timestamp'], float(tx['amount'] / 10 ** coin_decimal), 
                                            float(tx['fee'] / 10 ** coin_decimal), coin_decimal, tx_address, int(time.time()), u_server
                                        ))
                                        await conn.commit()
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
            except Exception:
                traceback.print_exc(file=sys.stdout)
        if debug is True:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} End check balance {coin_name}", color="green")
        return True

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
                tasks = []
                for coin_name in list_coins:
                    # print(f"Check balance {coin_name}")
                    if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 1 or getattr(
                            getattr(self.bot.coin_list, coin_name), "enable_deposit") == 0:
                        continue
                    tasks.append(self.update_balance_tasks_xmr(coin_name, False))
                completed = 0
                for task in asyncio.as_completed(tasks):
                    fetch_updates = await task
                    if fetch_updates is True:
                        completed += 1
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def notify_balance_btc(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_balance_btc"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `doge_get_transfers` 
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
                                    key = "notify_new_tx_{}_{}_{}".format(
                                        eachTx['coin_name'], eachTx['user_id'], eachTx['txid']
                                    )
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['coin_name']), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + \
                                        "Coin: {}\nTx: {}\nAmount: {}".format(
                                            eachTx['coin_name'], eachTx['txid'],
                                            num_format_coin(eachTx['amount'])
                                        ) + "```"
                                    try:
                                        await log_to_channel(
                                            "deposit",
                                            "[DEPOSIT] {} {} from <@{}> / {}. ref: {}".format(
                                                num_format_coin(eachTx['amount']),
                                                eachTx['coin_name'], eachTx['user_id'], eachTx['user_id'], eachTx['txid']
                                            ),
                                            self.bot.config['discord']['deposit_webhook']
                                        )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    try:
                                        await member.send(msg)
                                        sql = """ UPDATE `doge_get_transfers` 
                                            SET `notified_confirmation`=%s, `time_notified`=%s 
                                            WHERE `txid`=%s AND `address`=%s LIMIT 1
                                            """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['txid'], eachTx['address']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `doge_get_transfers` 
                                            SET `notified_confirmation`=%s, `failed_notification`=%s 
                                            WHERE `txid`=%s AND `address`=%s LIMIT 1
                                            """
                                        await cur.execute(sql, ("NO", "YES", eachTx['txid'], eachTx['address']))
                                        await conn.commit()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    # to use with update_balance_btc()
    async def update_balance_tasks_btc(self, coin_name: str, debug: bool):
        if debug is True:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} Check balance {coin_name}", color="yellow")
        gettopblock = None
        if getattr(getattr(self.bot.coin_list, coin_name), "use_getinfo_btc") == 1:
            gettopblock = await self.wallet_api.call_doge('getinfo', coin_name)
        else:
            gettopblock = await self.wallet_api.call_doge('getblockchaininfo', coin_name)
        if gettopblock is None:
            return False
        height = int(gettopblock['blocks'])
        try:
            await self.utils.async_set_cache_kv(
                "block",
                f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}",
                height
            )
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(1.0)
            return False

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
                        sql = """ SELECT * FROM `doge_get_transfers` 
                            WHERE `coin_name`=%s AND `category` IN (%s, %s)
                            """
                        await cur.execute(sql, (coin_name, 'receive', 'send'))
                        result = await cur.fetchall()
                        d = ["{}_{}".format(i['txid'], i['address']) for i in result]
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
                                    if "{}_{}".format(tx['txid'], tx['address']) not in d:
                                        user_paymentId = await store.sql_get_userwallet_by_paymentid(
                                            tx['address'], coin_name,
                                            getattr(getattr(self.bot.coin_list, coin_name), "type"))
                                        u_server = None
                                        user_id = None
                                        if user_paymentId:
                                            u_server = user_paymentId['user_server']
                                            user_id = user_paymentId['user_id']
                                        if getattr(getattr(self.bot.coin_list, coin_name), "coin_has_pos") == 1:
                                            # generate from mining
                                            if tx['category'] == 'receive' and 'generated' not in tx:
                                                sql = """ INSERT IGNORE INTO `doge_get_transfers` 
                                                    (`coin_name`, `user_id`, `txid`, `blockhash`, `address`, `blocktime`, `amount`, 
                                                    `fee`, `confirmations`, `category`, `time_insert`, `user_server`) 
                                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                                    """
                                                await cur.execute(sql, (
                                                    coin_name, user_id, tx['txid'], tx['blockhash'], tx['address'],
                                                    tx['blocktime'], float(tx['amount']),
                                                    float(tx['fee']) if 'fee' in tx else None,
                                                    tx['confirmations'], tx['category'], int(time.time()),
                                                    u_server
                                                ))
                                                await conn.commit()
                                        else:
                                            # generate from mining
                                            if tx['category'] == "receive" or tx['category'] == "generate":
                                                sql = """ INSERT IGNORE INTO `doge_get_transfers` 
                                                    (`coin_name`, `user_id`, `txid`, `blockhash`, `address`, `blocktime`, `amount`, 
                                                    `fee`, `confirmations`, `category`, `time_insert`, `user_server`) 
                                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                                    """
                                                await cur.execute(sql, (
                                                    coin_name, user_id, tx['txid'], tx['blockhash'], tx['address'],
                                                    tx['blocktime'], float(tx['amount']),
                                                    float(tx['fee']) if 'fee' in tx else None,
                                                    tx['confirmations'], tx['category'], int(time.time()),
                                                    u_server
                                                ))
                                                await conn.commit()
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
            except Exception:
                traceback.print_exc(file=sys.stdout)
        if debug is True:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} End check balance {coin_name}", color="green")

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
                tasks = []
                for coin_name in list_coins:
                    if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 1 or getattr(
                            getattr(self.bot.coin_list, coin_name), "enable_deposit") == 0:
                        continue
                    tasks.append(self.update_balance_tasks_btc(coin_name, False))
                completed = 0
                for task in asyncio.as_completed(tasks):
                    fetch_updates = await task
                    if fetch_updates is True:
                        completed += 1
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
            if gettopblock is None:
                return
            try:
                height = int(gettopblock['result'])
                await self.utils.async_set_cache_kv(
                    "block",
                    f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}",
                    height
                )
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
                            get_transfers = await self.wallet_api.call_neo(
                                'getnep17transfers', payload=[each_address['balance_wallet_address'], 0]
                            )
                            if get_transfers and 'result' in get_transfers and get_transfers['result'] \
                                and 'received' in get_transfers['result'] and get_transfers['result']['received'] \
                                    and len(get_transfers['result']['received']) > 0:
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
                                            await logchanbot("{} tx hash: {} less than minimum deposit.".format(
                                                coin_name, each_received['txhash']
                                                )
                                            )
                                            continue
                                        data_rows.append((
                                            each_address['user_id'], coin_name, coin_decimal, each_received['assethash'], 
                                            each_received['txhash'], each_address['balance_wallet_address'],
                                            each_received['timestamp'], each_received['blockindex'], 
                                            int(each_received['amount'])/10**coin_decimal, number_conf, 
                                            'received', int(time.time())
                                        ))
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
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    """
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
                    sql = """ SELECT * FROM `neo_get_transfers` 
                        WHERE `notified_confirmation`=%s AND `failed_notification`=%s AND `user_server`=%s
                        """
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
                                        msg = "You got a new deposit (it could take a few minutes to credit): ```" + \
                                            "Coin: {}\nTx: {}\nAmount: {}".format(
                                                coin_name, eachTx['txhash'],
                                                num_format_coin(eachTx['amount'])
                                            ) + "```"
                                        try:
                                            await log_to_channel(
                                                "deposit",
                                                "[DEPOSIT] {} {} from <@{}> / {}. ref: {}".format(
                                                    num_format_coin(eachTx['amount']),
                                                    eachTx['coin_name'], eachTx['user_id'], eachTx['user_id'], eachTx['txhash']
                                                ),
                                                self.bot.config['discord']['deposit_webhook']
                                            )
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                        try:
                                            await member.send(msg)
                                            sql = """ UPDATE `neo_get_transfers` 
                                                SET `notified_confirmation`=%s, `time_notified`=%s 
                                                WHERE `txhash`=%s AND `coin_name`=%s LIMIT 1
                                                """
                                            await cur.execute(sql, (
                                                "YES", int(time.time()), eachTx['txhash'], coin_name
                                            ))
                                            await conn.commit()
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                            sql = """ UPDATE `neo_get_transfers` 
                                                SET `notified_confirmation`=%s, `failed_notification`=%s 
                                                WHERE `txhash`=%s AND `coin_name`=%s LIMIT 1
                                                """
                                            await cur.execute(sql, ("NO", "YES", eachTx['txhash'], coin_name))
                                            await conn.commit()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=60.0)
    async def notify_balance_chia(self):
        time_lap = 20  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_balance_btc"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 15: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `xch_get_transfers` 
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
                                    key = "notify_new_tx_{}_{}_{}".format(
                                        eachTx['coin_name'], eachTx['user_id'], eachTx['txid']
                                    )
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['coin_name']), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + \
                                        "Coin: {}\nTx: {}\nAmount: {}".format(
                                            eachTx['coin_name'], eachTx['txid'],
                                            num_format_coin(eachTx['amount'])
                                        ) + "```"
                                    try:
                                        await log_to_channel(
                                            "deposit",
                                            "[DEPOSIT] {} {} from <@{}> / {}. ref: {}".format(
                                                num_format_coin(eachTx['amount']),
                                                eachTx['coin_name'], eachTx['user_id'], eachTx['user_id'], eachTx['txid']
                                            ),
                                            self.bot.config['discord']['deposit_webhook']
                                        )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    try:
                                        await member.send(msg)
                                        sql = """ UPDATE `xch_get_transfers`
                                            SET `notified_confirmation`=%s, `time_notified`=%s 
                                            WHERE `txid`=%s LIMIT 1
                                            """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['txid']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `xch_get_transfers` 
                                            SET `notified_confirmation`=%s, `failed_notification`=%s 
                                            WHERE `txid`=%s LIMIT 1
                                            """
                                        await cur.execute(sql, ("NO", "YES", eachTx['txid']))
                                        await conn.commit()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    # to use with update_balance_chia()
    async def update_balance_tasks_chia(self, coin_name: str, debug: bool):
        if debug is True:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} Check balance {coin_name}", color="yellow")
        gettopblock = await self.gettopblock(coin_name, time_out=60)
        if gettopblock is None:
            return False
        height = int(gettopblock['height'])
        try:
            await self.utils.async_set_cache_kv(
                "block",
                f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}",
                height
            )
        except Exception:
            traceback.print_exc(file=sys.stdout)
            return False

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
                                if height >= get_confirm_depth + int(tx['confirmed_at_height']) and \
                                    tx['amount'] >= get_min_deposit_amount:
                                    if 'to_address' in tx and tx['to_address'] in list_balance_user and tx['amount'] > 0:
                                        list_balance_user[tx['to_address']] += tx['amount']
                                    elif 'to_address' in tx and tx['to_address'] not in list_balance_user and tx['amount'] > 0:
                                        list_balance_user[tx['to_address']] = tx['amount']
                                    try:
                                        if tx['name'] not in d:
                                            # receive
                                            if len(tx['sent_to']) == 0:
                                                user_paymentId = await store.sql_get_userwallet_by_paymentid(
                                                    tx['to_address'], coin_name,
                                                    getattr(getattr(self.bot.coin_list, coin_name), "type")
                                                )
                                                u_server = None
                                                user_id = None
                                                if user_paymentId:
                                                    u_server = user_paymentId['user_server']
                                                    user_id = user_paymentId['user_id']

                                                sql = """ INSERT IGNORE INTO `xch_get_transfers` 
                                                    (`coin_name`, `user_id`, `txid`, `height`, `timestamp`, `address`, `amount`, `fee`, 
                                                    `decimal`, `time_insert`, `user_server`) 
                                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                                    """
                                                await cur.execute(sql, (
                                                    coin_name, user_id, tx['name'], tx['confirmed_at_height'], tx['created_at_time'],
                                                    tx['to_address'], float(tx['amount'] / 10 ** coin_decimal),
                                                    float(tx['fee_amount'] / 10 ** coin_decimal), coin_decimal,
                                                    int(time.time()), u_server
                                                ))
                                                await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
        if debug is True:
            print_color(f"{datetime.now():%Y-%m-%d %H:%M:%S} End check balance {coin_name}", color="green")
        return True

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
                list_coins = [each['coin_name'].upper() for each in list_chia_api if each['enable'] == 1]
                if len(list_coins) == 0:
                    return
                tasks = []
                for coin_name in list_coins:
                    if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 1 or getattr(
                            getattr(self.bot.coin_list, coin_name), "enable_deposit") == 0:
                        continue
                    tasks.append(self.update_balance_tasks_chia(coin_name, False))
                completed = 0
                for task in asyncio.as_completed(tasks):
                    fetch_updates = await task
                    if fetch_updates is True:
                        completed += 1
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=10.0)
    async def notify_balance_nano(self):
        time_lap = 5  # seconds
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "notify_balance_nano"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 5: # not running if less than 15s
            return
        await asyncio.sleep(time_lap)
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `nano_move_deposit` 
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
                                    key = "notify_new_tx_{}_{}_{}".format(
                                        eachTx['coin_name'], eachTx['user_id'], eachTx['block']
                                    )
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['coin_name']), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + \
                                        "Coin: {}\nBlock: {}\nAmount: {}".format(
                                            eachTx['coin_name'], eachTx['block'],
                                            num_format_coin(eachTx['amount'])
                                        ) + "```"
                                    try:
                                        await log_to_channel(
                                            "deposit",
                                            "[DEPOSIT] {} {} from <@{}> / {}. ref: {}".format(
                                                num_format_coin(eachTx['amount']),
                                                eachTx['coin_name'], eachTx['user_id'], eachTx['user_id'], eachTx['block']
                                            ),
                                            self.bot.config['discord']['deposit_webhook']
                                        )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    try:
                                        await member.send(msg)
                                        sql = """ UPDATE `nano_move_deposit` 
                                            SET `notified_confirmation`=%s, `time_notified`=%s 
                                            WHERE `block`=%s LIMIT 1
                                            """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['block']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `nano_move_deposit` 
                                            SET `notified_confirmation`=%s, `failed_notification`=%s 
                                            WHERE `block`=%s LIMIT 1
                                            """
                                        await cur.execute(sql, ("NO", "YES", eachTx['block']))
                                        await conn.commit()
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
                            # store in kv
                            try:
                                await self.utils.async_set_cache_kv(
                                    "block",
                                    f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}",
                                    height
                                )
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
                            if each['coin_name'] == "XDG" and float(balance['pending']) > 0:
                                 print("pending {}: {}".format(address, float(balance['pending'])/10**coin_decimal))
                            try:
                                # if bigger than minimum deposit, and no pending and the address is in user database addresses
                                real_min_deposit = getattr(getattr(self.bot.coin_list, coin_name), "real_min_deposit")
                                coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                if float(int(balance['balance']) / 10 ** coin_decimal) >= real_min_deposit and \
                                    float(int(balance['pending']) / 10 ** coin_decimal) == 0 and \
                                        address in all_deposit_address_keys:
                                    # let's move balance to main_address
                                    try:
                                        main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                                        move_to_deposit = await self.wallet_api.nano_sendtoaddress(
                                            address, main_address, int(balance['balance']), coin_name
                                        )  # atomic
                                        # add to DB
                                        if move_to_deposit:
                                            try:
                                                await self.openConnection()
                                                async with self.pool.acquire() as conn:
                                                    async with conn.cursor() as cur:
                                                        sql = """ INSERT INTO nano_move_deposit 
                                                            (`coin_name`, `user_id`, `balance_wallet_address`, 
                                                            `to_main_address`, `amount`, `decimal`, `block`, 
                                                            `time_insert`, `user_server`) 
                                                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                                            """
                                                        await cur.execute(sql, (
                                                            coin_name, all_deposit_address[address]['user_id'], address, main_address,
                                                            float(int(balance['balance']) / 10 ** coin_decimal), coin_decimal, 
                                                            move_to_deposit['block'], int(time.time()),
                                                            all_deposit_address[address]['user_server']
                                                        ))
                                                        await conn.commit()
                                                        updated += 1
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

    @tasks.loop(seconds=30.0)
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
                tasks = []
                for each_c in erc_contracts:
                    endpoint_url = self.bot.erc_node_list[each_c['net_name']]
                    if self.bot.erc_node_list.get('{}_WITHDRAW'.format(each_c['net_name'])):
                        endpoint_url = self.bot.erc_node_list['{}_WITHDRAW'.format(each_c['net_name'])]
                    check_min_deposit = functools.partial(
                        sql_check_minimum_deposit_erc20,
                        endpoint_url,
                        each_c['net_name'], each_c['coin_name'],
                        each_c['contract'], each_c['decimal'],
                        each_c['min_move_deposit'], each_c['min_gas_tx'],
                        each_c['gas_ticker'], each_c['move_gas_amount'],
                        each_c['chain_id'], each_c['real_deposit_fee'],
                        self.bot.config,
                        each_c['erc20_approve_spend'], 7200,
                        each_c['tax_fee_percent']
                    )
                    check_min_deposit_exec = await self.bot.loop.run_in_executor(None, check_min_deposit)
                    tasks.append(check_min_deposit_exec)
                completed = 0
                for task in asyncio.as_completed(tasks):
                    fetch_updates = await task
                    if fetch_updates:
                        completed += 1

            main_tokens = await self.get_all_contracts("ERC-20", True)
            if len(main_tokens) > 0:
                tasks = []
                for each_c in main_tokens:
                    endpoint_url = self.bot.erc_node_list[each_c['net_name']]
                    if self.bot.erc_node_list.get('{}_WITHDRAW'.format(each_c['net_name'])):
                        endpoint_url = self.bot.erc_node_list['{}_WITHDRAW'.format(each_c['net_name'])]
                    check_min_deposit = functools.partial(
                        sql_check_minimum_deposit_erc20,
                        endpoint_url,
                        each_c['net_name'], each_c['coin_name'], None,
                        each_c['decimal'], each_c['min_move_deposit'],
                        each_c['min_gas_tx'], each_c['gas_ticker'],
                        each_c['move_gas_amount'], each_c['chain_id'],
                        each_c['real_deposit_fee'],
                        self.bot.config,
                        0, 7200, each_c['tax_fee_percent']
                    )
                    check_min_deposit_exec = await self.bot.loop.run_in_executor(None, check_min_deposit)
                    tasks.append(check_min_deposit_exec)
                completed = 0
                for task in asyncio.as_completed(tasks):
                    fetch_updates = await task
                    if fetch_updates:
                        completed += 1
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
                        await self.utils.async_set_cache_kv(
                            "block",
                            f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{each_coin.upper()}",
                            height
                        )
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
                                await self.wallet_api.xrp_insert_deposit(
                                    coin_name, issuer, get_user['user_id'],
                                    each_tx['tx']['hash'], each_tx['tx']['inLedger'],
                                    timestamp, value, 0, main_address, destination_tag,
                                    int(time.time())
                                )
                            elif type(each_tx['tx']['Amount']) is str:
                                # XRP
                                value = float(int(each_tx['tx']['Amount'])/10**6) # XRP: 6 decimal
                                await self.wallet_api.xrp_insert_deposit(
                                    "XRP", None, get_user['user_id'], each_tx['tx']['hash'],
                                    each_tx['tx']['inLedger'], timestamp, value, 6, main_address,
                                    destination_tag, int(time.time())
                                )
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
                    sql = """ SELECT * FROM `xrp_get_transfers` 
                        WHERE `notified_confirmation`=%s AND `failed_notification`=%s AND `user_server`=%s
                        """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            coin_name = eachTx['coin_name']
                            if eachTx['user_id']:
                                if not eachTx['user_id'].isdigit():
                                    continue
                                try:
                                    key = "notify_new_tx_{}_{}_{}".format(
                                        coin_name, eachTx['user_id'], eachTx['txid']
                                    )
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + \
                                        "Coin: {}\nTx: {}\nAmount: {}".format(
                                            coin_name, eachTx['txid'],
                                            num_format_coin(eachTx['amount'])
                                        ) + "```"
                                    try:
                                        await log_to_channel(
                                            "deposit",
                                            "[DEPOSIT] {} {} from <@{}> / {}. ref: {}".format(
                                                num_format_coin(eachTx['amount']),
                                                eachTx['coin_name'], eachTx['user_id'], eachTx['user_id'], eachTx['txid']
                                            ),
                                            self.bot.config['discord']['deposit_webhook']
                                        )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    try:
                                        await member.send(msg)
                                        sql = """ UPDATE `xrp_get_transfers` 
                                            SET `notified_confirmation`=%s, `time_notified`=%s 
                                            WHERE `txid`=%s LIMIT 1
                                            """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['txid']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `xrp_get_transfers` 
                                            SET `notified_confirmation`=%s, `failed_notification`=%s 
                                            WHERE `txid`=%s LIMIT 1
                                            """
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
            coin_name = "NEAR"
            near_contracts = await self.get_all_contracts(coin_name, False)
            if not hasattr(self.bot.coin_list, coin_name):
                return
            get_head = await near_get_status(self.bot.erc_node_list['NEAR'], 12)
            try:
                if get_head:
                    height = get_head['result']['sync_info']['latest_block_height']
                    await self.utils.async_set_cache_kv(
                        "block",
                        f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}",
                        height
                    )
                    if len(near_contracts) > 0:
                        for each_coin in near_contracts:
                            name = each_coin['coin_name']
                            try:
                                await self.utils.async_set_cache_kv(
                                    "block",
                                    f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{name}",
                                    height
                                )
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
                        get_balance = await near_check_balance(
                            self.bot.erc_node_list['NEAR'], each_address['balance_wallet_address'], 60
                        )
                        if get_balance and (int(get_balance['amount']) - int(get_balance['locked']))/10**coin_decimal > real_min_deposit:
                            balance = (int(get_balance['amount']) - int(get_balance['locked']))/10**coin_decimal
                            atomic_amount = int(get_balance['amount']) - int(get_balance['locked']) - int(real_deposit_fee*10**coin_decimal)
                            # move balance
                            transaction = functools.partial(
                                self.wallet_api.near_move_balance, self.bot.erc_node_list['NEAR'], 
                                decrypt_string(each_address['privateKey']),
                                each_address['balance_wallet_address'], main_address, atomic_amount
                            )
                            tx = await self.bot.loop.run_in_executor(None, transaction)
                            if tx:
                                content = None
                                try:
                                    content = json.dumps(tx)
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                                # 
                                added = await self.wallet_api.near_insert_mv_balance(
                                    coin_name, None, each_address['user_id'],
                                    each_address['balance_wallet_address'], main_address,
                                    float(balance), real_deposit_fee, coin_decimal,
                                    tx['transaction_outcome']['id'], content, int(time.time()), SERVER_BOT, "NEAR"
                                )
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
                            get_token_balance = await near_check_balance_token(
                                self.bot.erc_node_list['NEAR'], token_contract, each_addr['balance_wallet_address'], 60
                            )
                            if get_token_balance and isinstance(get_token_balance, int) and (get_token_balance/10**coin_decimal) > real_min_deposit:
                                # Check if has enough gas
                                get_gas_balance = await near_check_balance(
                                    self.bot.erc_node_list['NEAR'], each_addr['balance_wallet_address'], 60
                                )
                                # fix coin_decimal 24 for gas
                                if get_gas_balance and (int(get_gas_balance['amount']) - int(get_gas_balance['locked']))/10**24 >= min_gas_tx:
                                    # Move token
                                    transaction = functools.partial(
                                        self.wallet_api.near_move_balance_token, self.bot.erc_node_list['NEAR'], 
                                        token_contract, decrypt_string(each_addr['privateKey']),
                                        each_addr['balance_wallet_address'], main_address, get_token_balance
                                    )
                                    tx = await self.bot.loop.run_in_executor(None, transaction)
                                    if tx:
                                        content = None
                                        try:
                                            content = json.dumps(tx)
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                        await self.wallet_api.near_insert_mv_balance(
                                            each_contract['coin_name'], token_contract,
                                            each_addr['user_id'], each_addr['balance_wallet_address'],
                                            main_address, float(get_token_balance/10**coin_decimal),
                                            real_deposit_fee, coin_decimal, tx['transaction_outcome']['id'],
                                            content, int(time.time()), SERVER_BOT, "NEAR"
                                        )
                                        await asyncio.sleep(5.0)
                                else:
                                    # Less than 1hr, do not move
                                    if each_addr['last_moved_gas'] and int(time.time()) - each_addr['last_moved_gas'] < 3600:
                                        continue
                                    # Move gas
                                    key = decrypt_string(getattr(getattr(self.bot.coin_list, "NEAR"), "walletkey"))
                                    gas_atomic_amount = int(move_gas_amount*10**24) # fix coin_decimal 24 for gas
                                    transaction = functools.partial(
                                        self.wallet_api.near_move_balance, self.bot.erc_node_list['NEAR'], 
                                        key, main_address, each_addr['balance_wallet_address'], gas_atomic_amount
                                    )
                                    tx = await self.bot.loop.run_in_executor(None, transaction)
                                    if tx:
                                        await self.wallet_api.near_update_mv_gas(
                                            each_addr['balance_wallet_address'], int(time.time())
                                        )
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

        async def near_get_tx(url: str, tx_hash: str, timeout: int=60):
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
        if not hasattr(self.bot.coin_list, coin_name):
            return
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
                            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                            if height and height - check_tx['height'] > get_confirm_depth:
                                number_conf = height - check_tx['height']
                                await self.wallet_api.near_update_mv_deposit_pending(
                                    each_tx['txn'], check_tx['height'], number_conf
                                )
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
                        AND `failed_notification`=%s AND `user_server`=%s AND `blockNumber` IS NOT NULL
                        """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            if eachTx['user_id']:
                                if not eachTx['user_id'].isdigit():
                                    continue
                                try:
                                    key = "notify_new_tx_{}_{}_{}".format(
                                        eachTx['token_name'], eachTx['user_id'], eachTx['txn']
                                    )
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['token_name']), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + \
                                        "Coin: {}\nAmount: {}".format(
                                            eachTx['token_name'],
                                            num_format_coin(eachTx['amount'])
                                        ) + "```"
                                    try:
                                        await log_to_channel(
                                            "deposit",
                                            "[DEPOSIT] {} {} from <@{}> / {}. ref: {}".format(
                                                num_format_coin(eachTx['amount']),
                                                eachTx['token_name'], eachTx['user_id'], eachTx['user_id'], eachTx['txn']
                                            ),
                                            self.bot.config['discord']['deposit_webhook']
                                        )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    try:
                                        await member.send(msg)
                                        sql = """ UPDATE `near_move_deposit` 
                                            SET `notified_confirmation`=%s, `time_notified`=%s 
                                            WHERE `txn`=%s LIMIT 1
                                            """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['txn']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `near_move_deposit` 
                                            SET `notified_confirmation`=%s, `failed_notification`=%s 
                                            WHERE `txn`=%s LIMIT 1
                                            """
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
                        AND `failed_notification`=%s AND `user_server`=%s AND `blockNumber` IS NOT NULL
                        """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            if eachTx['user_id']:
                                if not eachTx['user_id'].isdigit():
                                    continue
                                try:
                                    key = "notify_new_tx_{}_{}_{}".format(
                                        eachTx['token_name'], eachTx['user_id'], eachTx['txn']
                                    )
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['token_name']), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + \
                                        "Coin: {}\nAmount: {}".format(
                                            eachTx['token_name'],
                                            num_format_coin(eachTx['real_amount'])
                                        ) + "```"
                                    try:
                                        await log_to_channel(
                                            "deposit",
                                            "[DEPOSIT] {} {} from <@{}> / {}. ref: {}".format(
                                                num_format_coin(eachTx['real_amount']),
                                                eachTx['token_name'], eachTx['user_id'], eachTx['user_id'], eachTx['txn']
                                            ),
                                            self.bot.config['discord']['deposit_webhook']
                                        )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    try:
                                        await member.send(msg)
                                        sql = """ UPDATE `vet_move_deposit` 
                                            SET `notified_confirmation`=%s, `time_notified`=%s 
                                            WHERE `txn`=%s LIMIT 1
                                            """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['txn']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `vet_move_deposit` 
                                            SET `notified_confirmation`=%s, `failed_notification`=%s 
                                            WHERE `txn`=%s LIMIT 1
                                            """
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
        if getattr(getattr(self.bot.coin_list, coin_name), "enable_deposit") != 0:
            return
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
                            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                            if height and height - int(check_tx['meta']['blockNumber']) > get_confirm_depth:
                                number_conf = height - int(check_tx['meta']['blockNumber'])
                                await self.wallet_api.vet_update_mv_deposit_pending(
                                    each_tx['txn'], int(check_tx['meta']['blockNumber']),
                                    json.dumps(check_tx), number_conf
                                )
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
            if getattr(getattr(self.bot.coin_list, coin_name), "enable_deposit") != 0:
                return
            get_status = await vet_get_status(self.bot.erc_node_list['VET'], 16)
            if get_status:
                height = int(get_status['number'])
                await self.utils.async_set_cache_kv(
                    "block",
                    f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}",
                    height
                )
                if len(vet_contracts) > 0:
                    for each_coin in vet_contracts:
                        name = each_coin['coin_name']
                        try:
                            await self.utils.async_set_cache_kv(
                                "block",
                                f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{name}",
                                height
                            )
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
                check_balance = functools.partial(
                    vet_get_balance, self.bot.erc_node_list['VET'], each_address['balance_wallet_address']
                )
                balance = await self.bot.loop.run_in_executor(None, check_balance)
                # VET
                if balance and balance['VET']/10**coin_decimal >= real_min_deposit:
                    transaction = functools.partial(
                        vet_move_token, self.bot.erc_node_list['VET'],
                        coin_name, None, main_address,
                        decrypt_string(each_address['key']),
                        main_address_key, balance[coin_name]
                    )
                    tx = await self.bot.loop.run_in_executor(None, transaction)
                    if tx:
                        added = await self.wallet_api.vet_insert_mv_balance(
                            coin_name, None, each_address['user_id'],
                            each_address['balance_wallet_address'],
                            main_address, float(balance[coin_name]/10**coin_decimal),
                            real_deposit_fee, coin_decimal, tx, None,
                            int(time.time()), SERVER_BOT, "VET"
                        )
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
                    transaction = functools.partial(
                        vet_move_token, self.bot.erc_node_list['VET'], coin_name, None,
                        main_address, decrypt_string(each_address['key']),
                        main_address_key, balance[coin_name]
                    )
                    tx = await self.bot.loop.run_in_executor(None, transaction)
                    if tx:
                        added = await self.wallet_api.vet_insert_mv_balance(
                            coin_name, contract, each_address['user_id'],
                            each_address['balance_wallet_address'], main_address,
                            float(balance[coin_name]/10**coin_decimal),
                            real_deposit_fee, coin_decimal, tx, None, int(time.time()),
                            SERVER_BOT, "VET"
                        )
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
                                get_token_balance = functools.partial(
                                    vet_get_token_balance, self.bot.erc_node_list['VET'],
                                    token_contract, each_address['balance_wallet_address']
                                )
                                balance = await self.bot.loop.run_in_executor(None, get_token_balance)
                                if balance and balance / 10 ** coin_decimal >= real_min_deposit:
                                    # move token
                                    transaction = functools.partial(
                                        vet_move_token, self.bot.erc_node_list['VET'],
                                        each_contract['coin_name'], token_contract,
                                        main_address, decrypt_string(each_address['key']),
                                        main_address_key, balance
                                    )
                                    tx = await self.bot.loop.run_in_executor(None, transaction)
                                    if tx:
                                        added = await self.wallet_api.vet_insert_mv_balance(
                                            each_contract['coin_name'], token_contract,
                                            each_address['user_id'], each_address['balance_wallet_address'],
                                            main_address, float(balance / 10**coin_decimal), real_deposit_fee,
                                            coin_decimal, tx, None, int(time.time()), SERVER_BOT, "VET"
                                        )
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
                        AND `failed_notification`=%s AND `user_server`=%s AND `blockNumber` IS NOT NULL
                        """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            if eachTx['user_id']:
                                if not eachTx['user_id'].isdigit():
                                    continue
                                try:
                                    key = "notify_new_tx_{}_{}_{}".format(
                                        eachTx['token_name'], eachTx['user_id'], eachTx['txn']
                                    )
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['token_name']), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + \
                                        "Coin: {}\nAmount: {}".format(
                                            eachTx['token_name'],
                                            num_format_coin(eachTx['real_amount'])
                                        ) + "```"
                                    try:
                                        await log_to_channel(
                                            "deposit",
                                            "[DEPOSIT] {} {} from <@{}> / {}. ref: {}".format(
                                                num_format_coin(eachTx['real_amount']),
                                                eachTx['token_name'], eachTx['user_id'], eachTx['user_id'], eachTx['txn']
                                            ),
                                            self.bot.config['discord']['deposit_webhook']
                                        )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    try:
                                        await member.send(msg)
                                        sql = """ UPDATE `zil_move_deposit` 
                                            SET `notified_confirmation`=%s, `time_notified`=%s 
                                            WHERE `txn`=%s LIMIT 1
                                            """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['txn']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `zil_move_deposit` 
                                            SET `notified_confirmation`=%s, `failed_notification`=%s 
                                            WHERE `txn`=%s LIMIT 1
                                            """
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
        if not hasattr(self.bot.coin_list, coin_name):
            return
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
                            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                            if height and height - int(check_tx['result']['receipt']['epoch_num']) > get_confirm_depth:
                                number_conf = height - int(check_tx['result']['receipt']['epoch_num'])
                                await self.wallet_api.zil_update_mv_deposit_pending(
                                    each_tx['txn'], int(check_tx['result']['receipt']['epoch_num']), number_conf
                                )
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
            if not hasattr(self.bot.coin_list, coin_name):
                return
            get_status = await zil_get_status(self.bot.erc_node_list['ZIL'], 16)
            if get_status:
                height = int(get_status['result']['NumTxBlocks'])
                await self.utils.async_set_cache_kv(
                    "block",
                    f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}",
                    height
                )
                if len(zil_contracts) > 0:
                    for each_coin in zil_contracts:
                        name = each_coin['coin_name']
                        try:
                            await self.utils.async_set_cache_kv(
                                "block",
                                f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{name}",
                                height
                            )
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
                            transaction = functools.partial(
                                self.wallet_api.zil_transfer_native, main_address,
                                decrypt_string(each_address['key']),  amount, 600
                            )
                            tx = await self.bot.loop.run_in_executor(None, transaction)
                            if tx:
                                contents = None
                                try:
                                    contents = json.dumps(tx)
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                                added = await self.wallet_api.zil_insert_mv_balance(
                                    coin_name, None, each_address['user_id'],
                                    each_address['balance_wallet_address'], main_address,
                                    float(balance), real_deposit_fee, coin_decimal, tx['ID'],
                                    contents, int(time.time()), SERVER_BOT, "ZIL"
                                )
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
                                get_token_balance = await zil_check_token_balance(
                                    self.bot.erc_node_list['ZIL'], token_contract, account.address0x, 60
                                ) # atomic
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
                                        transaction = functools.partial(
                                            self.wallet_api.zil_transfer_token, token_contract,
                                            main_address, decrypt_string(get_zil_user['key']), amount
                                        )
                                        tx = await self.bot.loop.run_in_executor(None, transaction)
                                        if tx:
                                            contents = None
                                            try:
                                                contents = json.dumps(tx)
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                            added = await self.wallet_api.zil_insert_mv_balance(
                                                each_contract['coin_name'], token_contract,
                                                get_zil_user['user_id'], get_zil_user['balance_wallet_address'],
                                                main_address, float(int(amount) / 10 ** coin_decimal),
                                                real_deposit_fee, coin_decimal, tx['ID'], contents,
                                                int(time.time()), SERVER_BOT, "ZIL"
                                            )
                                            await asyncio.sleep(5.0)
                                    else:
                                        if get_zil_user and get_zil_user['last_moved_gas'] and \
                                            int(time.time()) - get_zil_user['last_moved_gas'] < 3600:
                                            continue
                                        # Move gas
                                        key = decrypt_string(getattr(getattr(self.bot.coin_list, "ZIL"), "walletkey"))
                                        transaction = functools.partial(
                                            self.wallet_api.zil_transfer_native, each_addr, key, move_gas_amount, 600
                                        )
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
            # If main token is disable deposit
            if getattr(getattr(self.bot.coin_list, "XTZ"), "enable_deposit") == 0:
                return
            xtz_contracts = await self.get_all_contracts("XTZ", False)
            # Check native
            coin_name = "XTZ"
            rpchost = getattr(getattr(self.bot.coin_list, coin_name), "rpchost")
            get_head = await tezos_get_head(rpchost, 8)
            try:
                if get_head:
                    height = get_head['level']
                    await self.utils.async_set_cache_kv(
                        "block",
                        f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{coin_name}",
                        height
                    )
                    if len(xtz_contracts) > 0:
                        for each_coin in xtz_contracts:
                            name = each_coin['coin_name']
                            try:
                                await self.utils.async_set_cache_kv(
                                    "block",
                                    f"{self.bot.config['kv_db']['prefix'] + self.bot.config['kv_db']['daemon_height']}{name}",
                                    height
                                )
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
                        check_balance = functools.partial(
                            tezos_check_balance,
                            self.bot.erc_node_list['XTZ'],
                            decrypt_string(each_address['key'])
                        )
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
                                        await self.wallet_api.tezos_insert_reveal(
                                            each_address['balance_wallet_address'], None, int(time.time())
                                        )
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
                                    transaction = functools.partial(
                                        self.wallet_api.tezos_move_balance,
                                        self.bot.erc_node_list['XTZ'],
                                        decrypt_string(each_address['key']),
                                        main_address, atomic_amount
                                    )
                                    tx = await self.bot.loop.run_in_executor(None, transaction)
                                    if tx:
                                        contents = None
                                        try:
                                            contents = json.dumps(tx.contents)
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                        added = await self.wallet_api.tezos_insert_mv_balance(
                                            coin_name, None, each_address['user_id'],
                                            each_address['balance_wallet_address'],
                                            main_address, float(balance), real_deposit_fee,
                                            coin_decimal, tx.hash(), contents,
                                            int(time.time()), SERVER_BOT, "XTZ"
                                        )
                                        await asyncio.sleep(5.0)
                                else:
                                    # Push to revealed & stored in DB
                                    do_reveal = functools.partial(
                                        tezos_reveal_address, self.bot.erc_node_list['XTZ'], decrypt_string(each_address['key'])
                                    )
                                    tx_reveal = await self.bot.loop.run_in_executor(None, do_reveal)
                                    if tx_reveal:
                                        # Add to DB
                                        await self.wallet_api.tezos_insert_reveal(
                                            each_address['balance_wallet_address'], tx_reveal['hash'], int(time.time())
                                        )
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
                                get_token_balances = functools.partial(
                                    tezos_check_token_balance,
                                    self.bot.erc_node_list['XTZ'],
                                    token_contract,
                                    token_addresses,
                                    coin_decimal,
                                    int(token_id)
                                )
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
                                                check_gas = functools.partial(
                                                    tezos_check_balance,
                                                    self.bot.erc_node_list['XTZ'],
                                                    decrypt_string(get_tezos_user['key'])
                                                )
                                                gas_balance = await self.bot.loop.run_in_executor(None, check_gas)
                                                if gas_balance >= min_gas_tx:
                                                    do_reveal = functools.partial(
                                                        tezos_reveal_address,
                                                        self.bot.erc_node_list['XTZ'],
                                                        decrypt_string(get_tezos_user['key'])
                                                    )
                                                    tx_reveal = await self.bot.loop.run_in_executor(None, do_reveal)
                                                    if tx_reveal:
                                                        # Add to DB
                                                        await self.wallet_api.tezos_insert_reveal(k, tx_reveal['hash'], int(time.time()))
                                                        await asyncio.sleep(1.0)
                                                        continue
                                                else:
                                                    # skip recent gas, 1hr
                                                    if get_tezos_user['last_moved_gas'] and \
                                                        int(time.time()) - get_tezos_user['last_moved_gas'] < 3600:
                                                        continue
                                                    # Move gas
                                                    key = decrypt_string(getattr(getattr(self.bot.coin_list, "XTZ"), "walletkey"))
                                                    transaction = functools.partial(
                                                        self.wallet_api.tezos_move_balance,
                                                        self.bot.erc_node_list['XTZ'],
                                                        key, k, int(move_gas_amount*10**6)
                                                    ) # Move XTZ, decimal 6
                                                    send_tx = await self.bot.loop.run_in_executor(None, transaction)
                                                    if send_tx:
                                                        await self.wallet_api.tezos_update_mv_gas(k, int(time.time()))
                                                        await asyncio.sleep(1.0)
                                                        continue
                                        # re-check gas
                                        if can_move_token is True:
                                            check_gas = functools.partial(
                                                tezos_check_balance,
                                                self.bot.erc_node_list['XTZ'],
                                                decrypt_string(get_tezos_user['key'])
                                            )
                                            gas_balance = await self.bot.loop.run_in_executor(None, check_gas)
                                            if gas_balance >= min_gas_tx:
                                                # Move token
                                                try:
                                                    ttlkey = "{}_{}".format(
                                                        each_contract['coin_name'], each_address['balance_wallet_address']
                                                    )
                                                    if self.mv_xtz_cache[ttlkey] == ttlkey:
                                                        continue
                                                    else:
                                                        self.mv_xtz_cache[ttlkey] = ttlkey
                                                except Exception:
                                                    pass
                                                if token_type == "FA2":
                                                    transaction = functools.partial(
                                                        self.wallet_api.tezos_move_token_balance,
                                                        self.bot.erc_node_list['XTZ'],
                                                        decrypt_string(get_tezos_user['key']),
                                                        main_address, contract, v, token_id
                                                    )
                                                elif token_type == "FA1.2":
                                                    transaction = functools.partial(
                                                        self.wallet_api.tezos_move_token_balance_fa12,
                                                        self.bot.erc_node_list['XTZ'],
                                                        decrypt_string(get_tezos_user['key']),
                                                        main_address,
                                                        contract, v, token_id
                                                    )
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
                                                    await self.wallet_api.tezos_insert_mv_balance(
                                                        each_contract['coin_name'],
                                                        contract,
                                                        get_tezos_user['user_id'],
                                                        k,
                                                        main_address,
                                                        float(v/10**coin_decimal),
                                                        real_deposit_fee,
                                                        coin_decimal,
                                                        tx_hash,
                                                        contents,
                                                        int(time.time()),
                                                        SERVER_BOT,
                                                        "XTZ"
                                                    )
                                                    await asyncio.sleep(5.0)
                                            else:
                                                if get_tezos_user['last_moved_gas'] and \
                                                    int(time.time()) - get_tezos_user['last_moved_gas'] < 3600:
                                                    continue
                                                # Move gas
                                                key = decrypt_string(getattr(getattr(self.bot.coin_list, "XTZ"), "walletkey"))
                                                transaction = functools.partial(
                                                    self.wallet_api.tezos_move_balance,
                                                    self.bot.erc_node_list['XTZ'], key, k, int(move_gas_amount*10**6)
                                                ) # Move XTZ, decimal 6
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

    @tasks.loop(seconds=15.0)
    async def notify_new_confirmed_tezos(self):
        time_lap = 10  # seconds
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
                    sql = """
                    SELECT * FROM `tezos_move_deposit` 
                    WHERE `notified_confirmation`=%s 
                    AND `failed_notification`=%s AND `user_server`=%s AND `blockNumber` IS NOT NULL
                    """
                    await cur.execute(sql, ("NO", "NO", SERVER_BOT))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for eachTx in result:
                            if eachTx['user_id']:
                                if not eachTx['user_id'].isdigit():
                                    continue
                                try:
                                    key = "notify_new_tx_{}_{}_{}".format(
                                        eachTx['token_name'], eachTx['user_id'], eachTx['txn']
                                    )
                                    if self.ttlcache[key] == key:
                                        continue
                                    else:
                                        self.ttlcache[key] = key
                                except Exception:
                                    pass
                                member = self.bot.get_user(int(eachTx['user_id']))
                                if member is not None:
                                    coin_decimal = getattr(getattr(self.bot.coin_list, eachTx['token_name']), "decimal")
                                    msg = "You got a new deposit (it could take a few minutes to credit): ```" + \
                                        "Coin: {}\nAmount: {}".format(
                                            eachTx['token_name'], num_format_coin(
                                                eachTx['real_amount']
                                            )
                                        ) + "```"
                                    try:
                                        await log_to_channel(
                                            "deposit",
                                            "[DEPOSIT] {} {} from <@{}> / {}. ref: {}".format(
                                                num_format_coin(eachTx['real_amount']),
                                                eachTx['token_name'], eachTx['user_id'], eachTx['user_id'], eachTx['txn']
                                            ),
                                            self.bot.config['discord']['deposit_webhook']
                                        )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    try:
                                        await member.send(msg)
                                        sql = """ UPDATE `tezos_move_deposit` 
                                            SET `notified_confirmation`=%s, `time_notified`=%s 
                                            WHERE `txn`=%s LIMIT 1
                                            """
                                        await cur.execute(sql, ("YES", int(time.time()), eachTx['txn']))
                                        await conn.commit()
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                        sql = """ UPDATE `tezos_move_deposit` 
                                            SET `notified_confirmation`=%s, `failed_notification`=%s 
                                            WHERE `txn`=%s LIMIT 1
                                            """
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
                            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
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
        # If main token is disable deposit
        if getattr(getattr(self.bot.coin_list, "TRX"), "enable_deposit") == 0:
            return
        try:
            erc_contracts = await self.get_all_contracts("TRC-20", False)
            if len(erc_contracts) > 0:
                for each_c in erc_contracts:
                    try:
                        type_name = each_c['type']
                        await store.trx_check_minimum_deposit(
                            self.bot.erc_node_list['TRX'],
                            each_c['coin_name'], type_name, each_c['contract'],
                            each_c['decimal'], each_c['min_move_deposit'],
                            each_c['min_gas_tx'], each_c['fee_limit'],
                            each_c['gas_ticker'], each_c['move_gas_amount'],
                            each_c['chain_id'], each_c['real_deposit_fee'], 7200
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
            main_tokens = await self.get_all_contracts("TRC-20", True)
            if len(main_tokens) > 0:
                for each_c in main_tokens:
                    try:
                        type_name = each_c['type']
                        await store.trx_check_minimum_deposit(
                            self.bot.erc_node_list['TRX'],
                            each_c['coin_name'], type_name, None, each_c['decimal'],
                            each_c['min_move_deposit'], each_c['min_gas_tx'],
                            each_c['fee_limit'], each_c['gas_ticker'],
                            each_c['move_gas_amount'], each_c['chain_id'],
                            each_c['real_deposit_fee'], 7200
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))
        await asyncio.sleep(time_lap)

    @tasks.loop(seconds=15.0)
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
                tasks = []
                for each_name in net_names:
                    tasks.append(store.sql_check_pending_move_deposit_erc20(
                        self.bot.erc_node_list[each_name], each_name, depth, 32
                    ))
                completed = 0
                for task in asyncio.as_completed(tasks):
                    fetch_updates = await task
                    if fetch_updates:
                        completed += 1
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
                        await store.sql_check_pending_move_deposit_trc20(
                            self.bot.erc_node_list["TRX"], each_name, depth, "PENDING"
                        )
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
                        get_recent_tx = await store.get_monit_scanning_contract_balance_address_erc20(
                            each_name, 7200
                        )
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

    async def send_external_erc20(
        self, url: str, network: str, user_id: str, to_address: str, amount: float, coin: str,
        coin_decimal: int, real_withdraw_fee: float, user_server: str, chain_id: str = None,
        contract: str = None
    ):
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
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(self.bot.config['eth']['MainAddress']), 'pending')
                else:
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(self.bot.config['eth']['MainAddress']))
                # get gas price
                gasPrice = w3.eth.gasPrice

                estimateGas = w3.eth.estimateGas(
                    {'to': w3.toChecksumAddress(to_address), 'from': w3.toChecksumAddress(self.bot.config['eth']['MainAddress']),
                     'value': int(amount * 10 ** coin_decimal)})

                atomic_amount = int(amount * 10 ** 18)
                transaction = {
                    'from': w3.toChecksumAddress(self.bot.config['eth']['MainAddress']),
                    'to': w3.toChecksumAddress(to_address),
                    'value': atomic_amount,
                    'nonce': nonce,
                    'gasPrice': gasPrice,
                    'gas': estimateGas,
                    'chainId': chain_id
                }
                try:
                    signed_txn = w3.eth.account.sign_transaction(transaction, private_key=self.bot.config['eth']['MainAddress_key'])
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
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(self.bot.config['eth']['MainAddress']), 'pending')
                else:
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(self.bot.config['eth']['MainAddress']))

                unicorn_txn = unicorns.functions.transfer(
                    w3.toChecksumAddress(to_address),
                    int(amount * 10 ** coin_decimal)  # amount to send
                ).buildTransaction({
                    'from': w3.toChecksumAddress(self.bot.config['eth']['MainAddress']),
                    'gasPrice': w3.eth.gasPrice,
                    'nonce': nonce,
                    'chainId': chain_id
                })

                acct = Account.from_mnemonic(
                    mnemonic=self.bot.config['eth']['MainAddress_seed'])
                signed_txn = w3.eth.account.signTransaction(unicorn_txn, private_key=acct.key)
                sent_tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
            if signed_txn and sent_tx:
                # Add to SQL
                try:
                    await self.openConnection()
                    async with self.pool.acquire() as conn:
                        async with conn.cursor() as cur:
                            sql = """ INSERT INTO `erc20_external_tx` 
                                (`token_name`, `contract`, `user_id`, `real_amount`, 
                                `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, 
                                `user_server`, `network`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                            await cur.execute(sql, (
                                token_name, contract, user_id, amount, real_withdraw_fee, coin_decimal,
                                to_address, int(time.time()), sent_tx.hex(), user_server, network)
                            )
                            await conn.commit()
                            return sent_tx.hex()
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot("wallet send_external_erc20 " + str(traceback.format_exc()))
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet send_external_erc20 " + str(traceback.format_exc()))

    async def send_external_trc20(
        self, user_id: str, to_address: str, amount: float, coin: str, coin_decimal: int,
        real_withdraw_fee: float, user_server: str, fee_limit: float, trc_type: str,
        contract: str = None
    ):
        token_name = coin.upper()
        user_server = user_server.upper()

        try:
            url = self.bot.erc_node_list['TRX']
            _http_client = AsyncClient(
                limits=Limits(max_connections=100, max_keepalive_connections=20),
                timeout=Timeout(timeout=10, connect=5, read=5
            ))
            TronClient = AsyncTron(provider=AsyncHTTPProvider(url, client=_http_client))
            if token_name == "TRX":
                txb = (
                    TronClient.trx.transfer(self.bot.config['trc']['MainAddress'], to_address, int(amount * 10 ** 6))
                    # .memo("test memo")
                    .fee_limit(int(fee_limit * 10 ** 6))
                )
                txn = await txb.build()
                priv_key = PrivateKey(bytes.fromhex(self.bot.config['trc']['MainAddress_key']))
                txn_ret = await txn.sign(priv_key).broadcast()
                try:
                    in_block = await txn_ret.wait()
                except Exception:
                    traceback.print_exc(file=sys.stdout)

                if txn_ret and in_block:
                    # Add to SQL
                    try:
                        await self.openConnection()
                        async with self.pool.acquire() as conn:
                            await conn.ping(reconnect=True)
                            async with conn.cursor() as cur:
                                sql = """ INSERT INTO trc20_external_tx (`token_name`, `contract`, `user_id`, `real_amount`, 
                                    `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, `user_server`) 
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    """
                                await cur.execute(sql, (
                                    token_name, contract, user_id, amount, real_withdraw_fee, coin_decimal,
                                    to_address, int(time.time()), txn_ret['txid'], user_server
                                ))
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
                        ## balance = await cntr.functions.balanceOf(self.bot.config['trc']['MainAddress']) / 10**precision
                        txb = await cntr.functions.transfer(to_address, int(amount * 10 ** coin_decimal))
                        txb = txb.with_owner(self.bot.config['trc']['MainAddress']).fee_limit(int(fee_limit * 10 ** 6))
                        txn = await txb.build()
                        priv_key = PrivateKey(bytes.fromhex(self.bot.config['trc']['MainAddress_key']))
                        txn_ret = await txn.sign(priv_key).broadcast()
                        in_block = None
                        try:
                            in_block = await txn_ret.wait()
                        except Exception:
                            traceback.print_exc(file=sys.stdout)

                        if txn_ret and in_block:
                            # Add to SQL
                            try:
                                await self.openConnection()
                                async with self.pool.acquire() as conn:
                                    await conn.ping(reconnect=True)
                                    async with conn.cursor() as cur:
                                        sql = """ INSERT INTO trc20_external_tx (`token_name`, `contract`, `user_id`, `real_amount`, 
                                            `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, `user_server`) 
                                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                            """
                                        await cur.execute(sql, (
                                            token_name, contract, user_id, amount, real_withdraw_fee, coin_decimal,
                                            to_address, int(time.time()), txn_ret['txid'], user_server
                                        ))
                                        await conn.commit()
                                        return txn_ret['txid']
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                                await logchanbot("wallet send_external_trc20 " + str(traceback.format_exc()))
                    except httpx.ConnectTimeout:
                        print("HTTPX ConnectTimeout url: {}".format(url))
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                elif trc_type == "TRC-10":
                    try:
                        precision = 10 ** coin_decimal
                        txb = (
                            TronClient.trx.asset_transfer(
                                self.bot.config['trc']['MainAddress'], to_address, int(precision * amount), token_id=int(contract)
                            )
                            .fee_limit(int(fee_limit * 10 ** 6))
                        )
                        txn = await txb.build()
                        priv_key = PrivateKey(bytes.fromhex(self.bot.config['trc']['MainAddress_key']))
                        txn_ret = await txn.sign(priv_key).broadcast()

                        in_block = None
                        try:
                            in_block = await txn_ret.wait()
                        except Exception:
                            traceback.print_exc(file=sys.stdout)

                        if txn_ret and in_block:
                            # Add to SQL
                            try:
                                await self.openConnection()
                                async with self.pool.acquire() as conn:
                                    await conn.ping(reconnect=True)
                                    async with conn.cursor() as cur:
                                        sql = """ INSERT INTO trc20_external_tx (`token_name`, `contract`, `user_id`, `real_amount`, 
                                            `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, `user_server`) 
                                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                            """
                                        await cur.execute(sql, (
                                            token_name, str(contract), user_id, amount, real_withdraw_fee, coin_decimal,
                                            to_address, int(time.time()), txn_ret['txid'], user_server
                                        ))
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

    async def trtl_api_get_transfers(
        self, url: str, key: str, coin: str, height_start: int = None,
        height_end: int = None
    ):
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
                    'trtl_api_get_transfers: TIMEOUT: {} - coin {} timeout {}'.format(method, coin, time_out)
                )
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
                    'trtl_api_get_transfers: TIMEOUT: {} - coin {} timeout {}'.format(method, coin, time_out)
                )
            except Exception:
                await logchanbot('trtl_api_get_transfers: ' + str(traceback.format_exc())
            )

    async def trtl_service_getTransactions(
        self, url: str, coin: str, firstBlockIndex: int = 2000000,
        blockCount: int = 200000
    ):
        coin_name = coin.upper()
        time_out = 60
        payload = {
            'firstBlockIndex': firstBlockIndex if firstBlockIndex > 0 else 1,
            'blockCount': blockCount,
        }
        result = await self.wallet_api.call_aiohttp_wallet_xmr_bcn(
            'getTransactions', coin_name, time_out=time_out, payload=payload
        )
        if result and 'items' in result:
            return result['items']
        return []

    # Mostly for BCN/XMR
    async def call_daemon(
        self, get_daemon_rpc_url: str, method_name: str, coin: str, time_out: int = None,
        payload: Dict = None
    ) -> Dict:
        full_payload = {
            'params': payload or {},
            'jsonrpc': '2.0',
            'id': str(uuid.uuid4()),
            'method': f'{method_name}'
        }
        timeout = time_out or 16
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    get_daemon_rpc_url + '/json_rpc',
                    json=full_payload,
                    timeout=timeout
                ) as response:
                    if response.status == 200:
                        res_data = await response.json()
                        if res_data and 'result' in res_data:
                            return res_data['result']
                        else:
                            return res_data
        except asyncio.TimeoutError:
            await logchanbot(
                'call_daemon: method: {} coin_name {} - timeout {}'.format(method_name, coin.upper(), time_out)
            )
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
                    async with session.post(
                        get_daemon_rpc_url + '/json_rpc',
                        json=full_payload,
                        timeout=timeout
                    ) as response:
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
                                        async with session.post(
                                            get_daemon_rpc_url + '/json_rpc',
                                            json=full_payload,
                                            timeout=timeout
                                        ) as response:
                                            if response.status == 200:
                                                res_data = await response.json()
                                                if 'result' in res_data:
                                                    return res_data['result']
                                                else:
                                                    print("Couldn't get result for coin: {}".format(coin_name))
                                            else:
                                                print("Coin {} got response status: {}".format(coin_name, response.status))
                                except asyncio.TimeoutError:
                                    traceback.print_exc(file=sys.stdout)
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            return None
            except asyncio.TimeoutError:
                await logchanbot(
                    'gettopblock: method: {} coin_name {} - timeout {}'.format(method_name, coin.upper(), time_out)
                )
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
                    async with session.post(
                        get_daemon_rpc_url + '/json_rpc',
                        json=full_payload,
                        timeout=timeout
                    ) as response:
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
                                        async with session.post(
                                            get_daemon_rpc_url + '/json_rpc',
                                            json=full_payload,
                                            timeout=timeout
                                        ) as response:
                                            if response.status == 200:
                                                res_data = await response.json()
                                                if res_data and 'result' in res_data:
                                                    return res_data['result']
                                                else:
                                                    return res_data
                                except asyncio.TimeoutError:
                                    await logchanbot(
                                        'gettopblock: method: {} coin_name {} - timeout {}'.format(
                                            'get_block_count', coin_name, time_out
                                        )
                                    )
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            return None
            except asyncio.TimeoutError:
                await logchanbot(
                    'gettopblock: method: {} coin_name {} - timeout {}'.format(
                        method_name, coin.upper(), time_out
                    )
                )
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return None
        elif coin_family == "CHIA":
            payload = {'wallet_id': 1}
            try:
                get_height = await self.wallet_api.call_xch('get_height_info', coin_name, payload=payload)
                if get_height and 'success' in get_height and get_height['height']:
                    return get_height
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return None

    async def get_all_contracts(self, type_token: str, main_token: bool = False):
        # type_token: ERC-20, TRC-20
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                await conn.ping(reconnect=True)
                async with conn.cursor() as cur:
                    if main_token is False:
                        sql = """
                        SELECT * FROM `coin_settings` 
                        WHERE `type`=%s AND `enable`=%s 
                        AND `contract` IS NOT NULL AND `net_name` IS NOT NULL
                        """
                        await cur.execute(sql, (type_token, 1))
                        result = await cur.fetchall()
                        if result and len(result) > 0:
                            return result
                    else:
                        sql = """ SELECT * FROM `coin_settings` WHERE `type`=%s 
                            AND `enable`=%s AND `contract` IS NULL AND `net_name` IS NOT NULL
                            """
                        await cur.execute(sql, (type_token, 1))
                        result = await cur.fetchall()
                        if result and len(result) > 0:
                            return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def generate_qr_address(
            self,
            address: str
    ):
        return await self.wallet_api.generate_qr_address(address)

    async def sql_get_userwallet(
        self, user_id, coin: str, netname: str, type_coin: str, 
        user_server: str = 'DISCORD', chat_id: int = 0
    ):
        return await self.wallet_api.sql_get_userwallet(
            user_id, coin, netname, type_coin, user_server, chat_id
        )

    async def sql_register_user(
        self, user_id, coin: str, netname: str, type_coin: str, user_server: str,
        chat_id: int = 0, is_discord_guild: int = 0
    ):
        return await self.wallet_api.sql_register_user(
            user_id, coin, netname, type_coin, user_server, chat_id, is_discord_guild
        )

    async def get_all_net_names(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_ethscan_setting` 
                    WHERE `enable`=%s
                    """
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
                    sql = """ SELECT * FROM `coin_tronscan_setting` 
                    WHERE `enable`=%s
                    """
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
            await ctx.edit_original_message(
                content=f"{ctx.author.mention}, token name is missing.")
            return
        else:
            coin_name = token.upper()
            if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
                coin_name = self.bot.coin_alias_names[coin_name]
            if not hasattr(self.bot.coin_list, coin_name):
                await ctx.edit_original_message(
                    content=f"{ctx.author.mention}, **{coin_name}** does not exist with us.")
                return
            else:
                if getattr(getattr(self.bot.coin_list, coin_name), "enable_deposit") == 0:
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, **{coin_name}** deposit disable.")
                    return
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                            str(ctx.author.id), SERVER_BOT, "/deposit", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Do the job
        try:
            coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
            coin_emoji = coin_emoji + " " if coin_emoji else ""

            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            get_deposit = await self.sql_get_userwallet(
                str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0
            )
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            if get_deposit is None:
                get_deposit = await self.sql_register_user(
                    str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 0
                )

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
                        num_format_coin(real_deposit_fee), token_display)
                fee_txt = " You must deposit at least {} {} to cover fees needed to credit your account. "\
                    "The fee{} will be deducted from your deposit amount.".format(
                        num_format_coin(real_min_deposit), token_display, real_deposit_fee_text
                        )
            elif getattr(getattr(self.bot.coin_list, coin_name), "min_move_deposit") and getattr(
                    getattr(self.bot.coin_list, coin_name), "min_move_deposit") > 0:
                min_move_deposit = getattr(getattr(self.bot.coin_list, coin_name), "min_move_deposit")
                fee_txt = " You should deposit at least {} {}.".format(
                        num_format_coin(min_move_deposit), token_display
                        )
            embed = disnake.Embed(
                title=f"{coin_emoji}Deposit for {ctx.author.name}#{ctx.author.discriminator}",
                description=description + fee_txt,
                timestamp=datetime.fromtimestamp(int(time.time()))
            )
            embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
            qr_address = wallet_address
            if coin_name == "HNT":
                address_memo = wallet_address.split()
                qr_address = '{"type":"payment","address":"' + address_memo[0] + '","memo":"' + address_memo[2] + '"}'
            elif type_coin in ["XLM", "VITE", "COSMOS"]:
                address_memo = wallet_address.split()
                qr_address = address_memo[0]
            try:
                gen_qr_address = await self.generate_qr_address(qr_address)
                address_path = qr_address.replace('{', '_').replace('}', '_').replace(
                    ':', '_').replace('"', "_").replace(',', "_").replace(' ', "_")
            except Exception:
                traceback.print_exc(file=sys.stdout)

            plain_address = wallet_address
            pointer_message = "{}, your deposit address for **{}** {}👆".format(
                ctx.author.mention, coin_name, coin_emoji
            )

            if type_coin in ["HNT", "XLM", "VITE", "COSMOS"]:
                plain_address = address_memo[0]
                plain_address += f"\n📝 MEMO (mandatory!) 👉 {address_memo[2]}"
                pointer_message += " and do not forget to include MEMO."

            main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"] and getattr(
                    getattr(self.bot.coin_list, coin_name),
                    "split_main_paymentid") == 1:  # split main and integrated address
                embed.add_field(
                    name="Main Address",
                    value="```{}```".format(main_address),
                    inline=False
                )
                embed.add_field(
                    name="PaymentID (Must include)",
                    value="{}".format(get_deposit['paymentid']),
                    inline=False
                )
            else:
                wallet_address_new = wallet_address
                if " MEMO:" in wallet_address_new:
                    wallet_address_new = wallet_address_new.replace(" MEMO:", "\n📝 MEMO:")
                embed.add_field(name="Your Deposit Address", value="```\n{}```".format(wallet_address_new), inline=False)
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"] and getattr(
                    getattr(self.bot.coin_list, coin_name),
                    "split_main_paymentid") != 1:
                    # Add optional address and payment Id
                    embed.add_field(name="Or Address + PaymentId", value="Address: ```{}```\nPaymentId: ```{}```".format(main_address, get_deposit['paymentid']), inline=False)
                embed.set_thumbnail(url=self.bot.config['storage']['deposit_url'] + address_path + ".png")

            if getattr(getattr(self.bot.coin_list, coin_name), "related_coins"):
                embed.add_field(name="Related Coins", value="```{}```".format(
                    getattr(getattr(self.bot.coin_list, coin_name), "related_coins")), inline=False)

            other_links = []
            if getattr(getattr(self.bot.coin_list, coin_name), "explorer_link") and \
                len(getattr(getattr(self.bot.coin_list, coin_name), "explorer_link")) > 0:
                other_links.append(
                    "[{}]({})".format("Explorer Link", getattr(getattr(self.bot.coin_list, coin_name), "explorer_link"))
                )
            if getattr(getattr(self.bot.coin_list, coin_name), "id_cmc"):
                other_links.append(
                    "[{}]({})".format("CoinMarketCap", "https://coinmarketcap.com/currencies/" + getattr(getattr(self.bot.coin_list, coin_name), "id_cmc"))
                )
            if getattr(getattr(self.bot.coin_list, coin_name), "id_gecko"):
                other_links.append(
                    "[{}]({})".format("CoinGecko", "https://www.coingecko.com/en/coins/" + getattr(getattr(self.bot.coin_list, coin_name), "id_gecko"))
                )
            if getattr(getattr(self.bot.coin_list, coin_name), "id_paprika"):
                other_links.append(
                    "[{}]({})".format("Coinpaprika", "https://coinpaprika.com/coin/" + getattr(getattr(self.bot.coin_list, coin_name), "id_paprika"))
                )

            if coin_name == "HNT":  # put memo and base64
                try:
                    address_memo = wallet_address.split()
                    embed.add_field(
                        name="📝 MEMO",
                        value="```Ascii: {}\nBase64: {}```".format(
                            address_memo[2], base64.b64encode(address_memo[2].encode('ascii')).decode('ascii')
                        ),
                        inline=False
                    )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            elif type_coin in ["XLM", "VITE", "COSMOS"]:
                try:
                    address_memo = wallet_address.split()
                    embed.add_field(name="📝 MEMO", value="```{}```".format(address_memo[2]), inline=False)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            embed.set_footer(text="Use: /deposit plain (for plain text)")
            # if advert enable
            if self.bot.config['discord']['enable_advert'] == 1 and len(self.bot.advert_list) > 0:
                try:
                    random.shuffle(self.bot.advert_list)
                    embed.add_field(
                        name="{}".format(self.bot.advert_list[0]['title']),
                        value="```{}```👉 <{}>".format(self.bot.advert_list[0]['content'], self.bot.advert_list[0]['link']),
                        inline=False
                    )
                    await self.utils.advert_impress(
                        self.bot.advert_list[0]['id'], str(ctx.author.id),
                        str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM"
                    )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            # end advert
            try:
                if plain and plain.lower() == 'plain':
                    await ctx.edit_original_message(content=plain_address)
                    await ctx.followup.send(pointer_message, ephemeral=True)
                else:
                    if len(other_links) > 0:
                        embed.add_field(name="Other links", value="{}".format(" | ".join(other_links)), inline=False)
                    check_fav = await self.utils.check_if_fav_coin(str(ctx.author.id), SERVER_BOT, coin_name)
                    view = DepositMenu(
                        self.bot, ctx, ctx.author.id, embed, coin_name, plain_address, pointer_message, is_fav=check_fav
                    )
                    await ctx.edit_original_message(content=None, embed=embed, view=view)
            except (disnake.Forbidden, disnake.errors.Forbidden) as e:
                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.slash_command(
        usage='deposit <token> [plain|embed]',
        options=[
            Option('token', 'token', OptionType.string, required=True),
            Option('plain', 'plain | embed', OptionType.string, required=False, choices=[
                OptionChoice("plain", "plain"),
                OptionChoice("embed", "embed")
            ]
            )
        ],
        description="Get your wallet deposit address."
    )
    async def deposit(
        self,
        ctx,
        token: str,
        plain: str = 'embed'
    ):
        await ctx.response.send_message(f"{ctx.author.mention}, checking deposit ...", ephemeral=True)
        await self.async_deposit(ctx, token, plain)

    @deposit.autocomplete("token")
    async def deposit_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]
    # End of deposit

    # Balance
    async def async_balance(self, ctx, token: str = None):
        coin_name = token.upper()
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            await ctx.edit_original_message(
                content=f"{ctx.author.mention}, **{coin_name}** does not exist with us.")
            return
        else:
            if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 1:
                await ctx.edit_original_message(
                    content=f"{ctx.author.mention}, **{coin_name}** is currently under maintenance.")
                return
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                            str(ctx.author.id), SERVER_BOT, "/balance", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Do the job
        try:
            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")

            get_deposit = await self.sql_get_userwallet(
                str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0)
            if get_deposit is None:
                get_deposit = await self.sql_register_user(
                    str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 0
                )

            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']
            elif type_coin in ["XRP"]:
                wallet_address = get_deposit['destination_tag']

            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
            description = ""
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
            embed = disnake.Embed(
                title=f'Balance for {ctx.author.name}#{ctx.author.discriminator}',
                timestamp=datetime.fromtimestamp(int(time.time()))
            )
            embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
            coin_emoji = None
            try:
                # height can be None
                userdata_balance = await self.wallet_api.user_balance(
                    str(ctx.author.id), coin_name, wallet_address, type_coin,
                    height, deposit_confirm_depth, SERVER_BOT
                )
                total_balance = userdata_balance['adjust']
                per_unit = None
                equivalent_usd = ""
                if price_with:
                    per_unit = await self.utils.get_coin_price(coin_name, price_with)
                    if per_unit and per_unit['price'] and per_unit['price'] > 0:
                        per_unit = per_unit['price']
                        amount_in_usd = float(Decimal(total_balance) * Decimal(per_unit))
                        if amount_in_usd >= 0.01:
                            equivalent_usd = " ~ {:,.2f}$".format(amount_in_usd)
                        elif amount_in_usd >= 0.0001:
                            equivalent_usd = " ~ {:,.4f}$".format(amount_in_usd)
                coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                embed.add_field(
                    name="{}Token/Coin {}{}".format(coin_emoji+" " if coin_emoji else "", token_display, equivalent_usd),
                    value="```Available: {} {}```".format(
                        num_format_coin(total_balance), token_display),
                    inline=False
                )
                try:
                    # check pool share of a coin by user
                    find_other_lp = await self.wallet_api.cexswap_get_all_poolshares(user_id=None, ticker=coin_name)
                    if len(find_other_lp) > 0:
                        user_amount = 0
                        total_pool_coin = 0
                        user_pools = [i for i in find_other_lp if i['user_id'] == str(ctx.author.id)]
                        pairs = []
                        if len(user_pools) > 0:
                            for i in find_other_lp:
                                if i['user_id'] != str(ctx.author.id):
                                    if i['ticker_1_name'] == coin_name:
                                        total_pool_coin += i['amount_ticker_1']
                                    elif i['ticker_2_name'] == coin_name:
                                        total_pool_coin += i['amount_ticker_2']
                                else:
                                    if i['ticker_1_name'] == coin_name:
                                        user_amount += i['amount_ticker_1']
                                        total_pool_coin += i['amount_ticker_1']
                                        pairs.append(i['ticker_2_name'])
                                    elif i['ticker_2_name'] == coin_name:
                                        user_amount += i['amount_ticker_2']
                                        total_pool_coin += i['amount_ticker_2']
                                        pairs.append(i['ticker_1_name'])
                            embed.description = "CEXSwap: ✅"
                            list_pairs = "\n```Locked with: " + ", ".join(list(set(pairs))) + "```"
                            embed.add_field(
                                name="CEXSwap: Locked in {} LP".format(len(user_pools)),
                                value="Amount: {} {}{}".format(
                                    num_format_coin(user_amount), coin_name,
                                    list_pairs
                                ),
                                inline=False
                            )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                if getattr(getattr(self.bot.coin_list, coin_name), "related_coins"):
                    embed.add_field(name="Related Coins", value="```{}```".format(
                        getattr(getattr(self.bot.coin_list, coin_name), "related_coins")), inline=False)

                other_links = []
                if getattr(getattr(self.bot.coin_list, coin_name), "explorer_link") and \
                    len(getattr(getattr(self.bot.coin_list, coin_name), "explorer_link")) > 0:
                    other_links.append(
                        "[{}]({})".format("Explorer Link", getattr(getattr(self.bot.coin_list, coin_name), "explorer_link"))
                    )
                if getattr(getattr(self.bot.coin_list, coin_name), "id_cmc"):
                    other_links.append(
                        "[{}]({})".format("CoinMarketCap", "https://coinmarketcap.com/currencies/" + getattr(getattr(self.bot.coin_list, coin_name), "id_cmc"))
                    )
                if getattr(getattr(self.bot.coin_list, coin_name), "id_gecko"):
                    other_links.append(
                        "[{}]({})".format("CoinGecko", "https://www.coingecko.com/en/coins/" + getattr(getattr(self.bot.coin_list, coin_name), "id_gecko"))
                    )
                if getattr(getattr(self.bot.coin_list, coin_name), "id_paprika"):
                    other_links.append(
                        "[{}]({})".format("Coinpaprika", "https://coinpaprika.com/coin/" + getattr(getattr(self.bot.coin_list, coin_name), "id_paprika"))
                    )

                # if advert enable
                if self.bot.config['discord']['enable_advert'] == 1 and len(self.bot.advert_list) > 0:
                    try:
                        random.shuffle(self.bot.advert_list)
                        embed.add_field(
                            name="{}".format(self.bot.advert_list[0]['title']),
                            value="```{}```👉 <{}>".format(self.bot.advert_list[0]['content'], self.bot.advert_list[0]['link']),
                            inline=False
                        )
                        await self.utils.advert_impress(
                            self.bot.advert_list[0]['id'], str(ctx.author.id),
                            str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM"
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                # end advert

                if len(other_links) > 0:
                    embed.add_field(name="Other links", value="{}".format(" | ".join(other_links)), inline=False)

                if getattr(getattr(self.bot.coin_list, coin_name), "deposit_note") and len(
                        getattr(getattr(self.bot.coin_list, coin_name), "deposit_note")) > 0:
                    description = getattr(getattr(self.bot.coin_list, coin_name), "deposit_note")
                    embed.set_footer(text=description)
            except Exception:
                traceback.print_exc(file=sys.stdout)

            if coin_emoji:
                extension = ".png"
                if coin_emoji.startswith("<a:"):
                    extension = ".gif"
                split_id = coin_emoji.split(":")[2]
                link = 'https://cdn.discordapp.com/emojis/' + str(split_id.replace(">", "")) + extension
                embed.set_thumbnail(url=link)

            check_fav = await self.utils.check_if_fav_coin(str(ctx.author.id), SERVER_BOT, coin_name)
            view = SingleBalanceMenu(self.bot, ctx, ctx.author.id, embed, coin_name, is_fav=check_fav)
            await ctx.edit_original_message(content=None, embed=embed, view=view)
            # Add update for future call
            try:
                await self.utils.update_user_balance_call(str(ctx.author.id), type_coin)
            except Exception:
                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    # Balances
    async def async_balances(self, ctx):
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/balances", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        zero_tokens = []
        unknown_tokens = []
        has_none_balance = True
        start_time = int(time.time())
        # do all coins/token which is not under maintenance
        mytokens = await store.get_coin_settings(coin_type=None)

        if len(mytokens) == 0:
            msg = f'{ctx.author.mention}, no token or not exist.'
            await ctx.edit_original_message(content=msg)
            return
        else:
            total_all_balance_usd = 0.0
            all_names = [each['coin_name'] for each in mytokens if each['enable'] == 1]
            page = disnake.Embed(
                title='[ YOUR BALANCE LIST ]',
                description="Thank you for using TipBot!",
                timestamp=datetime.fromtimestamp(int(time.time())),
            )
            page.set_thumbnail(url=ctx.author.display_avatar)
            page.set_footer(text="Use the reactions to flip pages.")
            original_em = page.copy()
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

            # Update balance call
            try:
                await self.utils.update_user_balance_call(str(ctx.author.id), type_coin=None)
            except Exception:
                traceback.print_exc(file=sys.stdout)
            try:
                all_userdata_balance = await self.wallet_api.all_user_balance(str(ctx.author.id), SERVER_BOT, all_names)
                if all_userdata_balance is None:
                    msg = f"{ctx.author.mention}, you don't have any balance."
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    # delete 0 balance
                    tmp = all_userdata_balance.copy()
                    for k, v in tmp.items():
                        if v == 0 or k not in all_names:
                            del all_userdata_balance[k]

                    if len(all_userdata_balance) == 0:
                        msg = f"{ctx.author.mention}, you don't have any balance."
                        await ctx.edit_original_message(content=msg)
                        return
                    
                    original_em = disnake.Embed(
                        title='[ YOUR BALANCE LIST ]',
                        description="Thank you for using TipBot!",
                        timestamp=datetime.fromtimestamp(int(time.time())),
                    )
                    original_em.set_thumbnail(url=ctx.author.display_avatar)
                    original_em.set_footer(text="Use menu to navigates.")

                    if len(all_userdata_balance) <= per_page:
                        page = original_em.copy()
                        for coin_name, v in all_userdata_balance.items():
                            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                            equivalent_usd = ""
                            per_unit = None
                            price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                            if price_with:
                                per_unit = await self.utils.get_coin_price(coin_name, price_with)
                                if per_unit and per_unit['price'] and per_unit['price'] > 0:
                                    per_unit = per_unit['price']
                                    amount_in_usd = float(Decimal(v) * Decimal(per_unit))
                                    total_all_balance_usd += amount_in_usd
                                    if amount_in_usd >= 0.01:
                                        equivalent_usd = " ~ {:,.2f}$".format(amount_in_usd)
                                    elif amount_in_usd >= 0.0001:
                                        equivalent_usd = " ~ {:,.4f}$".format(amount_in_usd)

                            coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                            page.add_field(
                                name="{}{}{}".format(coin_emoji + " " if coin_emoji else "", token_display, equivalent_usd),
                                value="{}".format(num_format_coin(v)),
                                inline=True
                            )
                        await ctx.edit_original_message(content=None, embed=page)
                        return
                    else:
                        # get favorite coins
                        fav_coins = await self.utils.check_if_fav_coin(str(ctx.author.id), SERVER_BOT, None)
                        fav_coin_list = []
                        if len(fav_coins) > 0:
                            fav_coin_list = [i['coin_name'] for i in fav_coins]
                            fav_embed = original_em.copy()
                            fav_embed.description = "Below are coins you added to favorites. "\
                                "You can remove or add more and they will list here by default. "\
                                "Please use the button sort by value or alphabet then use dropdown."
                        top_balances = []
                        for coin_name, v in all_userdata_balance.items():
                            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
                            equivalent_usd = ""
                            per_unit = None
                            amount_usd = 0.0
                            price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                            if price_with:
                                per_unit = await self.utils.get_coin_price(coin_name, price_with)
                                if per_unit and per_unit['price'] and per_unit['price'] > 0:
                                    per_unit = per_unit['price']
                                    amount_usd = float(Decimal(v) * Decimal(per_unit))
                                    total_all_balance_usd += amount_usd
                                    top_balances.append({"name": coin_name, "amount": float(Decimal(v)), "value_usd": amount_usd})
                            if len(fav_coins) > 0 and coin_name in fav_coin_list:
                                coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                                fav_embed.add_field(
                                    name="{}{}{}".format(
                                        coin_emoji + " " if coin_emoji else "",
                                        token_display,
                                        " ~ {:,.4f}$".format(amount_usd) if amount_usd > 0.001 else ""
                                    ),
                                    value="{}".format(
                                        num_format_coin(v)),
                                    inline=True
                                )
                        if len(top_balances) > 0:
                            top_balances = sorted(top_balances, key=lambda k: k.get('value_usd'), reverse=True)

                        keys = list(sorted(all_userdata_balance.keys()))
                        new_balance_list = [{i: float(all_userdata_balance[i])} for i in keys]

                        list_bl_chunks = list(chunks(new_balance_list, per_page))
                        list_index_desc = []
                        for c, value in enumerate(list_bl_chunks):
                            if len(value) > 1:
                                list_index_desc.append("{}-{}".format(list(value[0].keys())[0], list(value[-1].keys())[0]))
                            elif len(value) == 1:
                                list_index_desc.append("{}".format(list(value[0].keys())[0]))
                        embed = original_em.copy()

                        additional_text = ""
                        if len(top_balances) > 0:
                            additional_text = " Below are top coins/tokens' amount(s). "\
                                "Please use the button sort by value or alphabet then use dropdown."
                        embed.add_field(
                            name="Your coins/tokens",
                            value="You currently have {} coin(s)/token(s){}{}".format(
                                len(new_balance_list),
                                " ~ {:,.4f}$.".format(total_all_balance_usd) if total_all_balance_usd > 0 else "",
                                additional_text
                            ),
                            inline=False
                        )
                        if len(top_balances) > 0:
                            for i in top_balances[:12]:
                                coin_emoji = getattr(getattr(self.bot.coin_list, i['name']), "coin_emoji_discord")
                                if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                                    coin_emoji = None
                                token_display = getattr(getattr(self.bot.coin_list, i['name']), "display_name")
                                embed.add_field(
                                    name="{}{}{}".format(coin_emoji + " " if coin_emoji else "", token_display, " ~ {:,.4f}$".format(i['value_usd'])),
                                    value="{}".format(
                                        num_format_coin(i['amount'])),
                                    inline=True
                                )
                        bl_list_by_value_chunks = []
                        list_index_value = []
                        if len(top_balances) > 0:
                            bl_list_by_value = [{i['name']: i['value_usd']} for i in top_balances]
                            bl_list_by_value_chunks = list(chunks(bl_list_by_value, per_page))
                            list_index_value = []
                            for c, value in enumerate(bl_list_by_value_chunks):
                                if len(value) > 1:
                                    list_index_value.append("{:,.4f}$-{:,.4f}$".format(list(value[0].values())[0], list(value[-1].values())[0]))
                                elif len(value) == 1:
                                    list_index_value.append("{:,.4f}$".format(list(value[0].values())[0]))

                        view = BalancesMenu(
                            self.bot, ctx, ctx.author.id, embed, all_userdata_balance,
                            list_bl_chunks, list_index_desc,
                            bl_list_by_value_chunks, list_index_value,
                            sorted_by="ALPHA", home_embed = fav_embed if len(fav_coin_list) > 0 else embed,
                            selected_index=None
                        )
                        await ctx.edit_original_message(content=None, embed=fav_embed if len(fav_coin_list) > 0 else embed, view=view)
                        return
            except Exception:
                traceback.print_exc(file=sys.stdout)

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
        await ctx.response.send_message(content=f"{ctx.author.mention} balance loading...", ephemeral=True)
        if token.upper() == "ALL":
            await self.async_balances(ctx)
        else:
            await self.async_balance(ctx, token)

    @balance.autocomplete("token")
    async def balance_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]

    @commands.slash_command(
        usage='balances',
        description="Get all your token's balance."
    )
    async def balances(
        self,
        ctx,
    ):
        await ctx.response.send_message(content=f"{ctx.author.mention} balance loading...", ephemeral=True)
        await self.async_balances(ctx)
    # End of Balance

    # Withdraw
    async def async_withdraw(self, ctx, amount: str, token: str, address: str, extra_option: str=None):
        withdraw_tx_ephemeral = False
        coin_name = token.upper()
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
            await ctx.edit_original_message(content=msg)
            return
        else:
            if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") == 1:
                msg = f'{ctx.author.mention}, **{coin_name}** is currently under maintenance.'
                await ctx.edit_original_message(content=msg)
                return
            if getattr(getattr(self.bot.coin_list, coin_name), "enable_withdraw") != 1:
                msg = f'{ctx.author.mention}, **{coin_name}** withdraw is currently disable.'
                await ctx.edit_original_message(content=msg)
                return

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/withdraw", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        # check lock
        try:
            is_user_locked = self.utils.is_locked_user(str(ctx.author.id), SERVER_BOT)
            if is_user_locked is True:
                await ctx.edit_original_message(
                    content = f"{EMOJI_RED_NO} {ctx.author.mention}, your account is locked from using the Bot. "\
                    "Please contact bot dev by /about link."
                )
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # end check lock

        if str(ctx.author.id) in self.bot.tx_in_progress and \
            int(time.time()) - self.bot.tx_in_progress[str(ctx.author.id)] < 150 and \
                ctx.author.id != self.bot.config['discord']['owner_id']:
            msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress."
            await ctx.edit_original_message(content=msg)
            return
            
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
            price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
            try:
                check_exist = await self.check_withdraw_coin_address(type_coin, address)
                if check_exist is not None:
                    msg = f"{EMOJI_ERROR} {ctx.author.mention}, you cannot send to this address _{address}_."
                    await ctx.edit_original_message(content=msg)
                    return
            except Exception:
                traceback.print_exc(file=sys.stdout)

            if tx_fee is None:
                tx_fee = NetFee
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
            fee_limit = getattr(getattr(self.bot.coin_list, coin_name), "fee_limit")
            get_deposit = await self.sql_get_userwallet(
                str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0
            )
            if get_deposit is None:
                get_deposit = await self.sql_register_user(
                    str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 0
                )

            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']
            elif type_coin in ["XRP"]:
                wallet_address = get_deposit['destination_tag']

            # Check if tx in progress
            if str(ctx.author.id) in self.bot.tx_in_progress and \
                int(time.time()) - self.bot.tx_in_progress[str(ctx.author.id)] < 150 \
                    and ctx.author.id != self.bot.config['discord']['owner_id']:
                msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress."
                await ctx.edit_original_message(content=msg)
                return

            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
            if height is None:
                msg = f"{ctx.author.mention}, **{coin_name}** cannot pull information from network. Try again later."
                await ctx.edit_original_message(content=msg)
                return
            else:
                # check if amount is all
                all_amount = False
                if not amount.isdigit() and amount.upper() == "ALL":
                    all_amount = True
                    userdata_balance = await self.wallet_api.user_balance(
                        str(ctx.author.id), coin_name, wallet_address, type_coin,
                        height, deposit_confirm_depth, SERVER_BOT
                    )
                    amount = float(userdata_balance['adjust']) - NetFee
                # If $ is in amount, let's convert to coin/token
                elif "$" in amount[-1] or "$" in amount[0]:  # last is $
                    # Check if conversion is allowed for this coin.
                    amount = amount.replace(",", "").replace("$", "")
                    if price_with is None:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this __{coin_name}__."
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        per_unit = await self.utils.get_coin_price(coin_name, price_with)
                        if per_unit and per_unit['price'] and per_unit['price'] > 0:
                            per_unit = per_unit['price']
                            amount = float(Decimal(amount) / Decimal(per_unit))
                        else:
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. Try with different method."
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
                userdata_balance = await self.wallet_api.user_balance(
                    str(ctx.author.id), coin_name, wallet_address, type_coin,
                    height, deposit_confirm_depth, SERVER_BOT
                )
                actual_balance = float(userdata_balance['adjust'])

                # If balance 0, no need to check anything
                if actual_balance <= 0:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, please check your **{token_display}** balance."
                    await ctx.edit_original_message(content=msg)
                    return
                if amount > actual_balance:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to send out "\
                        f"{num_format_coin(amount)} {token_display}."
                    await ctx.edit_original_message(content=msg)
                    return

                if amount + NetFee > actual_balance:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to send out "\
                        f"{num_format_coin(amount)} {token_display}. "\
                        f"You need to leave at least network fee: {num_format_coin(NetFee)}"\
                        f" {token_display}."
                    await ctx.edit_original_message(content=msg)
                    return
                elif amount < min_tx or amount > max_tx:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, transaction cannot be smaller than "\
                        f"{num_format_coin(min_tx)} {token_display} or "\
                        f"bigger than {num_format_coin(max_tx)} {token_display}."
                    await ctx.edit_original_message(content=msg)
                    return

                try:
                    key_withdraw = str(ctx.author.id) + "_" + coin_name
                    if key_withdraw in self.withdraw_tx and \
                        int(time.time()) - self.withdraw_tx[key_withdraw] < 60:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you recently executed a withdraw of "\
                            f"this coin/token **{coin_name}**. Waiting till <t:{self.withdraw_tx[key_withdraw]+60}:f>."
                        await ctx.edit_original_message(content=msg)
                        return
                except Exception:
                    traceback.print_exc(file=sys.stdout)

                equivalent_usd = ""
                amount_in_usd = 0.0
                price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                if price_with:
                    per_unit = await self.utils.get_coin_price(coin_name, price_with)
                    if per_unit and per_unit['price'] and per_unit['price'] > 0:
                        per_unit = per_unit['price']
                        amount_in_usd = float(Decimal(amount) * Decimal(per_unit))
                        if amount_in_usd >= 0.01:
                            equivalent_usd = " ~ {:,.2f}$".format(amount_in_usd)
                        elif amount_in_usd >= 0.0001:
                            equivalent_usd = " ~ {:,.4f}$".format(amount_in_usd)

                if str(ctx.author.id) in self.bot.tx_in_progress and \
                    int(time.time()) - self.bot.tx_in_progress[str(ctx.author.id)] < 150 and \
                        ctx.author.id != self.bot.config['discord']['owner_id']:
                    msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress."
                    await ctx.edit_original_message(content=msg)
                    return

                if type_coin in ["ERC-20"]:
                    # Check address
                    valid_address = self.check_address_erc20(address)
                    valid = False
                    if valid_address and valid_address.upper() == address.upper():
                        valid = True
                    else:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid address:\n_{address}_'
                        await ctx.edit_original_message(content=msg)
                        return

                    send_tx = None
                    if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
                        self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())
                        # Ask for confirm
                        view = ConfirmName(self.bot, ctx.author.id)
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Do you want to withdraw "\
                            f"__{num_format_coin(amount)} {coin_name}__ with fee: __{num_format_coin(NetFee)} {coin_name}__ to "\
                            f"_{address}_?"
                        await ctx.edit_original_message(content=msg, view=view)
                        # Wait for the View to stop listening for input...
                        await view.wait()

                        # Check the value to determine which button was pressed, if any.
                        key_withdraw = str(ctx.author.id) + "_" + coin_name
                        if view.value is False:
                            await ctx.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, withdraw cancelled!", view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        elif view.value is None:
                            await ctx.edit_original_message(
                                content=msg + "\nTimeout!",
                                view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        else:
                            await ctx.edit_original_message(
                                view=None
                            )
                        self.withdraw_tx[key_withdraw] = int(time.time())
                        try:
                            endpoint_url = self.bot.erc_node_list[net_name]
                            if self.bot.erc_node_list.get('{}_WITHDRAW'.format(net_name)):
                                endpoint_url = self.bot.erc_node_list['{}_WITHDRAW'.format(net_name)]
                            chain_id = getattr(getattr(self.bot.coin_list, coin_name), "chain_id")
                            send_tx = await self.send_external_erc20(
                                endpoint_url, net_name, str(ctx.author.id), address, amount,
                                coin_name, coin_decimal, NetFee, SERVER_BOT,
                                chain_id, contract
                            )
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                            await log_to_channel(
                                "withdraw",
                                "wallet /withdraw " + str(traceback.format_exc())
                            )
                    else:
                        # reject and tell to wait
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish."
                        await ctx.edit_original_message(content=msg)
                        return
                    try:
                        del self.bot.tx_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass
                    if send_tx:
                        fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                            num_format_coin(NetFee), coin_name)
                        explorer_link = self.utils.get_explorer_link(coin_name, send_tx)
                        msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew "\
                            f"{num_format_coin(amount)} {token_display}{equivalent_usd} to "\
                            f"_{address}_.\nTransaction hash: _{send_tx}_{fee_txt}{explorer_link}"
                        await ctx.edit_original_message(content=msg, view=None)
                        await log_to_channel(
                            "withdraw",
                            f"[{SERVER_BOT}] User {ctx.author.name}#{ctx.author.discriminator} / "\
                            f"{ctx.author.mention} sucessfully withdrew {num_format_coin(amount)} "\
                            f"{token_display}{equivalent_usd}.{explorer_link}"
                        )
                        return
                    else:
                        msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw "\
                            f"{num_format_coin(amount)} {token_display}{equivalent_usd} to _{address}_."
                        await ctx.edit_original_message(content=msg, view=None)
                        await log_to_channel(
                            "withdraw",
                            f"[FAILED] User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                            f"failed to withdraw {num_format_coin(amount)} "\
                            f"{token_display}{equivalent_usd}."
                        )
                elif type_coin in ["TRC-20", "TRC-10"]:
                    # If main token is not enable for withdraw
                    if getattr(getattr(self.bot.coin_list, "TRX"), "enable_withdraw") != 1:
                        msg = f"{ctx.author.mention}, TRX/{coin_name} withdraw is currently disable."
                        await ctx.edit_original_message(content=msg)
                        return
                    send_tx = None
                    if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
                        self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())

                        # Ask for confirm
                        view = ConfirmName(self.bot, ctx.author.id)
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Do you want to withdraw "\
                            f"__{num_format_coin(amount)} {coin_name}__ with fee: __{num_format_coin(NetFee)} {coin_name}__ to "\
                            f"_{address}_?"
                        await ctx.edit_original_message(content=msg, view=view)
                        # Wait for the View to stop listening for input...
                        await view.wait()

                        # Check the value to determine which button was pressed, if any.
                        key_withdraw = str(ctx.author.id) + "_" + coin_name
                        if view.value is False:
                            await ctx.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, withdraw cancelled!", view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        elif view.value is None:
                            await ctx.edit_original_message(
                                content=msg + "\nTimeout!",
                                view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        else:
                            await ctx.edit_original_message(
                                view=None
                            )
                        self.withdraw_tx[key_withdraw] = int(time.time())

                        try:
                            send_tx = await self.send_external_trc20(
                                str(ctx.author.id), address, amount, coin_name,
                                coin_decimal, NetFee, SERVER_BOT, fee_limit,
                                type_coin, contract
                            )
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                            await log_to_channel(
                                "withdraw", 
                                "wallet /withdraw " + str(traceback.format_exc())
                            )
                    else:
                        # reject and tell to wait
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish."
                        await ctx.ctx.edit_original_message(content=msg)
                        return
                    try:
                        del self.bot.tx_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass

                    if send_tx:
                        fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                            num_format_coin(NetFee), coin_name
                        )
                        explorer_link = self.utils.get_explorer_link(coin_name, send_tx)                            
                        msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew "\
                            f"{num_format_coin(amount)} "\
                            f"{token_display}{equivalent_usd} to _{address}_.\nTransaction hash: _{send_tx}_{fee_txt}{explorer_link}"
                        await ctx.edit_original_message(content=msg, view=None)
                        await log_to_channel(
                            "withdraw",
                            f"[{SERVER_BOT}] User {ctx.author.name}#{ctx.author.discriminator} / "\
                            f"{ctx.author.mention} sucessfully withdrew "\
                            f"{num_format_coin(amount)} {token_display}{equivalent_usd}.{explorer_link}"
                        )
                        return
                    else:
                        msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw "\
                            f"{num_format_coin(amount)} "\
                            f"{token_display}{equivalent_usd} to {address}."
                        await ctx.edit_original_message(content=msg, view=None)
                        await log_to_channel(
                            "withdraw",
                            f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                            f"failed to withdraw {num_format_coin(amount)} "\
                            f"{token_display}{equivalent_usd} to address {address}."
                        )
                elif type_coin == "NANO":
                    valid_address = await self.wallet_api.nano_validate_address(coin_name, address)
                    if not valid_address is True:
                        msg = f"{EMOJI_RED_NO} Address: _{address}_ is invalid."
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
                            self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())
                            try:
                                main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                                if main_address == address:
                                    # can not send
                                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you cannot send to this address _{address}_.'
                                    await ctx.edit_original_message(content=msg)
                                    return
                                # Ask for confirm
                                view = ConfirmName(self.bot, ctx.author.id)
                                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Do you want to withdraw "\
                                    f"__{num_format_coin(amount)} {coin_name}__ with fee: `0.00 {coin_name}` to "\
                                    f"_{address}_?"
                                await ctx.edit_original_message(content=msg, view=view)
                                # Wait for the View to stop listening for input...
                                await view.wait()

                                # Check the value to determine which button was pressed, if any.
                                key_withdraw = str(ctx.author.id) + "_" + coin_name
                                if view.value is False:
                                    await ctx.edit_original_message(
                                        content=f"{EMOJI_INFORMATION} {ctx.author.mention}, withdraw cancelled!", view=None
                                    )
                                    del self.bot.tx_in_progress[str(ctx.author.id)]
                                    if key_withdraw in self.withdraw_tx:
                                        del self.withdraw_tx[key_withdraw]
                                    return
                                elif view.value is None:
                                    await ctx.edit_original_message(
                                        content=msg + "\nTimeout!",
                                        view=None
                                    )
                                    del self.bot.tx_in_progress[str(ctx.author.id)]
                                    if key_withdraw in self.withdraw_tx:
                                        del self.withdraw_tx[key_withdraw]
                                    return
                                else:
                                    await ctx.edit_original_message(
                                        view=None
                                    )
                                self.withdraw_tx[key_withdraw] = int(time.time())

                                send_tx = await self.wallet_api.send_external_nano(
                                    main_address, str(ctx.author.id), amount, address, coin_name, coin_decimal
                                )
                                if send_tx:
                                    tx_hash = send_tx['block']
                                    explorer_link = self.utils.get_explorer_link(coin_name, tx_hash)
                                    fee_txt = "\nWithdrew fee/node: `0.00 {}`.".format(coin_name)
                                    msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew "\
                                        f"{num_format_coin(amount)} "\
                                        f"{token_display}{equivalent_usd} to _{address}_.\nTransaction hash: _{tx_hash}_{fee_txt}{explorer_link}"
                                    await ctx.edit_original_message(content=msg, view=None)
                                    await log_to_channel(
                                        "withdraw",
                                        f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                        f"successfully withdrew {num_format_coin(amount)} "\
                                        f"{token_display}{equivalent_usd}.{explorer_link}"
                                    )
                                else:
                                    msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw "\
                                        f"{num_format_coin(amount)} "\
                                        f"{token_display}{equivalent_usd} to _{address}_."
                                    await ctx.edit_original_message(content=msg, view=None)
                                    await log_to_channel(
                                        "withdraw",
                                        f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                        f"failed to withdraw {num_format_coin(amount)} "\
                                        f"{token_display}{equivalent_usd} to address {address}."
                                    )
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                                await log_to_channel(
                                    "withdraw",
                                    "wallet /withdraw " + str(traceback.format_exc())
                                )
                        else:
                            # reject and tell to wait
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish."
                            await ctx.edit_original_message(content=msg)
                            return
                        try:
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                        except Exception:
                            pass
                elif type_coin == "CHIA":
                    if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
                        self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())
                        send_tx = await self.wallet_api.send_external_xch(
                            str(ctx.author.id), amount, address, coin_name,
                            coin_decimal, tx_fee, NetFee, SERVER_BOT
                        )
                        if send_tx:
                            fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                num_format_coin(NetFee), coin_name)
                            explorer_link = self.utils.get_explorer_link(coin_name, send_tx)
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew "\
                                f"{num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to _{address}_.\nTransaction hash: _{send_tx}_{fee_txt}{explorer_link}"
                            await ctx.edit_original_message(content=msg)
                            await log_to_channel(
                                "withdraw",
                                f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"successfully withdrew {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd}.{explorer_link}"
                            )
                        else:
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw "\
                                f"{num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to _{address}_."
                            await ctx.edit_original_message(content=msg)
                            await log_to_channel(
                                "withdraw",
                                f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"failed to withdraw {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to address {address}."
                            )
                    else:
                        # reject and tell to wait
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish."
                        await ctx.edit_original_message(content=msg)
                        return
                    try:
                        del self.bot.tx_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass
                elif type_coin == "HNT":
                    if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
                        self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())
                        wallet_host = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
                        main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                        password = decrypt_string(getattr(getattr(self.bot.coin_list, coin_name), "walletkey"))
                        send_tx = await self.wallet_api.send_external_hnt(
                            str(ctx.author.id), wallet_host, password,
                            main_address, address, amount, coin_decimal,
                            SERVER_BOT, coin_name, NetFee, 32
                        )
                        if send_tx:
                            fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                num_format_coin(NetFee), coin_name)
                            explorer_link = self.utils.get_explorer_link(coin_name, send_tx)
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew "\
                                f"{num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to _{address}_.\nTransaction hash: _{send_tx}_{fee_txt}{explorer_link}"
                            await ctx.edit_original_message(content=msg)
                            await log_to_channel(
                                "withdraw",
                                f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"successfully withdrew {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd}.{explorer_link}"
                            )
                        else:
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw "\
                                f"{num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to _{address}_."
                            await ctx.edit_original_message(content=msg)
                            await log_to_channel(
                                "withdraw",
                                f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"failed to withdraw {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to address {address}."
                            )
                    else:
                        # reject and tell to wait
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish."
                        await ctx.edit_original_message(content=msg)
                        return
                    try:
                        del self.bot.tx_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass
                elif type_coin == "VITE":
                    # If main token is not enable for withdraw
                    if getattr(getattr(self.bot.coin_list, "VITE"), "enable_withdraw") != 1:
                        msg = f"{ctx.author.mention}, VITE/{coin_name} withdraw is currently disable."
                        await ctx.edit_original_message(content=msg)
                        return
                    url = getattr(getattr(self.bot.coin_list, coin_name), "rpchost")
                    main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                    contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                    key = decrypt_string(getattr(getattr(self.bot.coin_list, coin_name), "walletkey"))
                    priv = base64.b64decode(key).hex()
                    atomic_amount = str(int(amount*10**coin_decimal))
                    if address == main_address:
                        # can not send
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you cannot send to this address _{address}_.'
                        await ctx.edit_original_message(content=msg)
                        return
                    if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
                        self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())
                        send_tx = await vite_send_tx(url, main_address, address, atomic_amount, "", contract, priv)
                        if send_tx:
                            tx_hash = send_tx['hash']
                            await self.wallet_api.insert_external_vite(
                                str(ctx.author.id), amount, address, coin_name, contract, coin_decimal,
                                NetFee, send_tx['hash'], json.dumps(send_tx), SERVER_BOT
                            )
                            fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                num_format_coin(NetFee), coin_name)
                            explorer_link = self.utils.get_explorer_link(coin_name, tx_hash)
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew "\
                                f"{num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to _{address}_.\nTransaction hash: _{tx_hash}_{fee_txt}{explorer_link}"
                            await ctx.edit_original_message(content=msg)
                            await log_to_channel(
                                "withdraw",
                                f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"successfully withdrew {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd}.{explorer_link}"
                            )
                        else:
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw "\
                                f"{num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to _{address}_."
                            await ctx.edit_original_message(content=msg)
                            await log_to_channel(
                                "withdraw",
                                f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"failed to withdraw {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to address {address}."
                            )
                    else:
                        # reject and tell to wait
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. "\
                            "Please wait it to finish."
                        await ctx.edit_original_message(content=msg)
                        return
                elif type_coin == "XLM":
                    # If main token is not enable for withdraw
                    if getattr(getattr(self.bot.coin_list, "XLM"), "enable_withdraw") != 1:
                        msg = f"{ctx.author.mention}, XLM/{coin_name} withdraw is currently disable."
                        await ctx.edit_original_message(content=msg)
                        return
                    url = getattr(getattr(self.bot.coin_list, coin_name), "http_address")
                    main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                    if address == main_address:
                        # can not send
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you cannot send to this address _{address}_."
                        await ctx.edit_original_message(content=msg)
                        return
                    if coin_name != "XLM":  # in case of asset
                        issuer = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                        asset_code = getattr(getattr(self.bot.coin_list, coin_name), "header")
                        check_asset = await self.wallet_api.check_xlm_asset(
                            url, asset_code, issuer, address, str(ctx.author.id), SERVER_BOT
                        )
                        if check_asset is False:
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you cannot send to this address _{address}_. "\
                                f"The destination account may not trust the asset you are attempting to send!"
                            await ctx.edit_original_message(content=msg)
                            return
                    if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
                        self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())
                        wallet_host = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
                        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                        withdraw_keypair = decrypt_string(getattr(getattr(self.bot.coin_list, coin_name), "walletkey"))
                        asset_ticker = getattr(getattr(self.bot.coin_list, coin_name), "header")
                        asset_issuer = getattr(getattr(self.bot.coin_list, coin_name), "contract")

                        # Ask for confirm
                        extra_txt = ""
                        if extra_option:
                            extra_txt = " with memo: __{}__".format(extra_option)
                        view = ConfirmName(self.bot, ctx.author.id)
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Do you want to withdraw "\
                            f"__{num_format_coin(amount)} {coin_name}__ with fee: __{num_format_coin(NetFee)} {coin_name}__ to "\
                            f"_{address}_{extra_txt}?"
                        await ctx.edit_original_message(content=msg, view=view)
                        # Wait for the View to stop listening for input...
                        await view.wait()

                        # Check the value to determine which button was pressed, if any.
                        key_withdraw = str(ctx.author.id) + "_" + coin_name
                        if view.value is False:
                            await ctx.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, withdraw cancelled!", view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        elif view.value is None:
                            await ctx.edit_original_message(
                                content=msg + "\nTimeout!",
                                view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        else:
                            await ctx.edit_original_message(
                                view=None
                            )
                        self.withdraw_tx[key_withdraw] = int(time.time())

                        send_tx = await self.wallet_api.send_external_xlm(
                            url, withdraw_keypair, str(ctx.author.id),
                            amount, address, coin_decimal, SERVER_BOT,
                            coin_name, NetFee, asset_ticker, asset_issuer,
                            90, extra_option
                        )
                        if send_tx:
                            fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                num_format_coin(NetFee), coin_name
                            )
                            explorer_link = self.utils.get_explorer_link(coin_name, send_tx)
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew "\
                                f"{num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to _{address}_.\nTransaction hash: _{send_tx}_{fee_txt}{explorer_link}"
                            if extra_option is not None:
                                msg += "\nWith memo: __{}__".format(extra_option)
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"successfully withdrew {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd}.{explorer_link}"
                            )
                        else:
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw "\
                                f"{num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to _{address}_."
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"failed to withdraw {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to address {address}."
                            )
                    else:
                        # reject and tell to wait
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish."
                        await ctx.edit_original_message(content=msg)
                        return
                    try:
                        del self.bot.tx_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass
                elif type_coin == "COSMOS":
                    url = getattr(getattr(self.bot.coin_list, coin_name), "http_address")
                    main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                    if address == main_address:
                        # can not send
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you cannot send to this address _{address}_."
                        await ctx.edit_original_message(content=msg)
                        return
                    # check address
                    if coin_name == "ATOM" and not address.startswith("cosmos"):
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid adddress _{address}_ for {coin_name}."
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        sub_type = getattr(getattr(self.bot.coin_list, coin_name), "sub_type")
                        hrp = getattr(getattr(self.bot.coin_list, coin_name), "header")
                        if sub_type and hrp and not address.startswith(hrp):
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid adddress _{address}_ for {coin_name}."
                            await ctx.edit_original_message(content=msg)
                            return
                    if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
                        self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())
                        wallet_host = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
                        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                        withdraw_keypair = decrypt_string(getattr(getattr(self.bot.coin_list, coin_name), "walletkey"))
                        rpchost = getattr(getattr(self.bot.coin_list, coin_name), "rpchost")
                        chain_id = getattr(getattr(self.bot.coin_list, coin_name), "chain_id")
                        key = decrypt_string(getattr(getattr(self.bot.coin_list, coin_name), "walletkey"))
                        hrp = getattr(getattr(self.bot.coin_list, coin_name), "header")
                        denom = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                        fee = 1000
                        if getattr(getattr(self.bot.coin_list, coin_name), "fee_limit"):
                            fee=int(getattr(getattr(self.bot.coin_list, coin_name), "fee_limit") * 10 ** coin_decimal)
                            min_tx = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tx")
                            factor = int(amount/min_tx)
                            if factor > 1 and coin_name in ["LUNC"]:
                                fee += int(2.5*factor/10 * 10 ** coin_decimal)
                            elif factor > 1:
                                fee += int(1.0*factor/10 * 10 ** coin_decimal)
                            if fee/(10**coin_decimal) > NetFee:
                                fee = int(NetFee * 10 ** coin_decimal)
                            NetFee = fee/(10 ** coin_decimal) * 2.0
                            # re-check NetFee
                            if amount + NetFee > actual_balance:
                                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to send out "\
                                    f"{num_format_coin(amount)} {token_display}. "\
                                    f"You need to leave at least (updated) network fee: {num_format_coin(NetFee)}"\
                                    f" {token_display}."
                                await ctx.edit_original_message(content=msg)
                                del self.bot.tx_in_progress[str(ctx.author.id)]
                                key_withdraw = str(ctx.author.id) + "_" + coin_name
                                if key_withdraw in self.withdraw_tx:
                                    del self.withdraw_tx[key_withdraw]
                                return
                        # Ask for confirm
                        view = ConfirmName(self.bot, ctx.author.id)
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Do you want to withdraw "\
                            f"__{num_format_coin(amount)} {coin_name}__ with fee: __{num_format_coin(NetFee)} {coin_name}__ to "\
                            f"_{address}_?"
                        await ctx.edit_original_message(content=msg, view=view)
                        # Wait for the View to stop listening for input...
                        await view.wait()

                        # Check the value to determine which button was pressed, if any.
                        key_withdraw = str(ctx.author.id) + "_" + coin_name
                        if view.value is False:
                            await ctx.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, withdraw cancelled!", view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        elif view.value is None:
                            await ctx.edit_original_message(
                                content=msg + "\nTimeout!",
                                view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        else:
                            await ctx.edit_original_message(
                                view=None
                            )
                        self.withdraw_tx[key_withdraw] = int(time.time())
                        get_wallet_seq = await cosmos_get_seq(wallet_host, main_address, 16)
                        if get_wallet_seq is None:
                            await log_to_channel(
                                "withdraw",
                                f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"failed to withdrew {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd}.\n" \
                                "ERROR: cosmos_get_seq is None."
                            )
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, internal error during withdraw, please try again later!"
                            await ctx.edit_original_message(content=msg, view=None)
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            return
                        gas=120000
                        if coin_name in ["LUNC"]:
                            gas = int(1.5*gas)
                            fee = int(1.5*fee)
                        send_tx = await self.wallet_api.cosmos_send_tx(
                            rpchost, chain_id, coin_name, int(get_wallet_seq['account']['account_number']),
                            int(get_wallet_seq['account']['sequence']), key,
                            amount, coin_decimal, str(ctx.author.id), address, SERVER_BOT,
                            NetFee, fee=fee,gas=gas, memo="", timeout=60, hrp=hrp, denom=denom
                        )
                        if send_tx:
                            # code 13
                            if send_tx['result']['code'] != 0 and "insufficient fees" in send_tx['result']['log']:
                                await log_to_channel(
                                    "withdraw",
                                    f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                    f"failed to withdraw {num_format_coin(amount)} to address {address}."\
                                    f"{token_display}{equivalent_usd}.\nERROR: {send_tx['result']}."
                                )
                                # re-send with new fee
                                if 'required' in send_tx['result']:
                                    check_fee = send_tx['result']['required'].split(",")
                                elif 'required:' in send_tx['result']['log']:
                                    check_fee = send_tx['result']['log'].split("required:")[1].repalce(":", "").split()
                                for i in check_fee:
                                    if denom in i:
                                        gas = int(int(i.replace(denom, ""))*1.20)
                                        break
                                    fee = int(1.5*fee)
                                    await log_to_channel(
                                        "withdraw",
                                        f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                        f"failed to withdraw {num_format_coin(amount)}."\
                                        f"{token_display}{equivalent_usd} to address {address}.\nERROR: {error}.\n"\
                                        f"Re-try with a new gas: {str(gas)}{denom}, fee: {str(fee)}{denom}..."
                                    )
                                send_tx = await self.wallet_api.cosmos_send_tx(
                                    rpchost, chain_id, coin_name, int(get_wallet_seq['account']['account_number']),
                                    int(get_wallet_seq['account']['sequence']), key,
                                    amount, coin_decimal, str(ctx.author.id), address, SERVER_BOT,
                                    NetFee, fee=fee,gas=gas, memo="", timeout=60, hrp=hrp, denom=denom
                                )
                            # code 11
                            elif send_tx['result']['code'] != 0 and "out of gas" in send_tx['result']['log']:
                                error = send_tx['result']['log']
                                gas = int(1.5*gas)
                                fee = int(1.5*fee)
                                await log_to_channel(
                                    "withdraw",
                                    f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                    f"failed to withdraw {num_format_coin(amount)}."\
                                    f"{token_display}{equivalent_usd} to address {address}.\nERROR: {error}.\n"\
                                    f"Re-try with a new gas: {str(gas)}{denom}, fee: {str(fee)}{denom}..."
                                )
                                send_tx = await self.wallet_api.cosmos_send_tx(
                                    rpchost, chain_id, coin_name, int(get_wallet_seq['account']['account_number']),
                                    int(get_wallet_seq['account']['sequence']), key,
                                    amount, coin_decimal, str(ctx.author.id), address, SERVER_BOT,
                                    NetFee, fee=fee,gas=gas, memo="", timeout=60, hrp=hrp, denom=denom
                                )
                            tx_hash = send_tx['result']['hash']
                            fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                num_format_coin(NetFee), coin_name
                            )
                            if send_tx['result']['code'] != 0:
                                error = send_tx['result']['log']
                                await log_to_channel(
                                    "withdraw",
                                    f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                    f"failed to withdraw {num_format_coin(amount)} "\
                                    f"{token_display}{equivalent_usd} to address {address}.\nERROR: {error}"
                                )
                                msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw "\
                                    f"{num_format_coin(amount)} "\
                                    f"{token_display}{equivalent_usd} to _{address}_.\nERROR: _{error}_"
                                if extra_option is not None:
                                    msg += "\nWith memo: __{}__".format(extra_option)
                                await ctx.edit_original_message(content=msg, view=None)
                            else:
                                explorer_link = self.utils.get_explorer_link(coin_name, tx_hash)
                                msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew "\
                                    f"{num_format_coin(amount)} "\
                                    f"{token_display}{equivalent_usd} to _{address}_.\nTransaction hash: _{tx_hash}_{fee_txt}{explorer_link}"
                                if extra_option is not None:
                                    msg += "\nWith memo: __{}__".format(extra_option)
                                await ctx.edit_original_message(content=msg, view=None)
                                await log_to_channel(
                                    "withdraw",
                                    f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                    f"successfully withdrew {num_format_coin(amount)} "\
                                    f"{token_display}{equivalent_usd}.{explorer_link}"
                                )
                        else:
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw "\
                                f"{num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to _{address}_."
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"failed to withdraw {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to address {address}."
                            )
                    else:
                        # reject and tell to wait
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish."
                        await ctx.edit_original_message(content=msg)
                        return
                    try:
                        del self.bot.tx_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass
                elif type_coin == "ADA":
                    # If main token is not enable for withdraw
                    if getattr(getattr(self.bot.coin_list, "ADA"), "enable_withdraw") != 1:
                        msg = f"{ctx.author.mention}, ADA/{coin_name} withdraw is currently disable."
                        await ctx.edit_original_message(content=msg)
                        return
                    if not address.startswith("addr1"):
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid address. It should start with `addr1`."
                        await ctx.edit_original_message(content=msg)
                        return
                    if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
                        if coin_name == "ADA":
                            self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())
                            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                            fee_limit = getattr(getattr(self.bot.coin_list, coin_name), "fee_limit")
                            # Use fee limit as NetFee

                            # Ask for confirm
                            view = ConfirmName(self.bot, ctx.author.id)
                            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Do you want to withdraw "\
                                f"__{num_format_coin(amount)} {coin_name}__ with fee: __{num_format_coin(NetFee)} {coin_name}__ to "\
                                f"_{address}_?"
                            await ctx.edit_original_message(content=msg, view=view)
                            # Wait for the View to stop listening for input...
                            await view.wait()

                            # Check the value to determine which button was pressed, if any.
                            key_withdraw = str(ctx.author.id) + "_" + coin_name
                            if view.value is False:
                                await ctx.edit_original_message(
                                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, withdraw cancelled!", view=None
                                )
                                del self.bot.tx_in_progress[str(ctx.author.id)]
                                if key_withdraw in self.withdraw_tx:
                                    del self.withdraw_tx[key_withdraw]
                                return
                            elif view.value is None:
                                await ctx.edit_original_message(
                                    content=msg + "\nTimeout!",
                                    view=None
                                )
                                del self.bot.tx_in_progress[str(ctx.author.id)]
                                if key_withdraw in self.withdraw_tx:
                                    del self.withdraw_tx[key_withdraw]
                                return
                            else:
                                await ctx.edit_original_message(
                                    view=None
                                )
                            self.withdraw_tx[key_withdraw] = int(time.time())

                            send_tx = await self.wallet_api.send_external_ada(
                                str(ctx.author.id), amount, coin_decimal, SERVER_BOT,
                                coin_name, fee_limit, address, 60
                            )
                            if "status" in send_tx and send_tx['status'] == "pending":
                                tx_hash = send_tx['id']
                                fee = send_tx['fee']['quantity'] / 10 ** coin_decimal + fee_limit
                                fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                    num_format_coin(fee), coin_name)
                                explorer_link = self.utils.get_explorer_link(coin_name, tx_hash)
                                msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew "\
                                    f"{num_format_coin(amount)} "\
                                    f"{token_display}{equivalent_usd} to _{address}_.\nTransaction hash: _{tx_hash}_{fee_txt}{explorer_link}"
                                await ctx.edit_original_message(content=msg, view=None)
                                await log_to_channel(
                                    "withdraw",
                                    f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                    f"successfully withdrew {num_format_coin(amount)} "\
                                    f"{token_display}{equivalent_usd}.{explorer_link}"
                                )
                            elif "code" in send_tx and "message" in send_tx:
                                code = send_tx['code']
                                message = send_tx['message']
                                await log_to_channel(
                                    "withdraw",
                                    f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                    f"failed to withdraw {num_format_coin(amount)} "\
                                    f"{token_display}{equivalent_usd} to address {address}.```code: {code}\nmessage: {message}```"
                                )
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, internal error, please try again later!'
                                await ctx.edit_original_message(content=msg, view=None)
                            else:
                                await log_to_channel(
                                    "withdraw",
                                    f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                    f"failed to withdraw {num_format_coin(amount)} "\
                                    f"{token_display}{equivalent_usd} to address {address}."
                                )
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, internal error, please try again later!'
                                await ctx.edit_original_message(content=msg, view=None)
                            try:
                                del self.bot.tx_in_progress[str(ctx.author.id)]
                            except Exception:
                                pass
                            return
                        else:
                            ## 
                            # Check user's ADA balance.
                            GAS_COIN = None
                            fee_limit = None
                            reserved_txt = ""
                            try:
                                if getattr(getattr(self.bot.coin_list, coin_name), "withdraw_use_gas_ticker") == 1:
                                    # add main token balance to check if enough to withdraw
                                    GAS_COIN = getattr(getattr(self.bot.coin_list, coin_name), "gas_ticker")
                                    fee_limit = getattr(getattr(self.bot.coin_list, coin_name), "fee_limit")
                                    if GAS_COIN:
                                        reserved_txt = f" and another reserved fee __{fee_limit} {GAS_COIN}__ (will be updated after tx executes) "
                                        userdata_balance = await self.wallet_api.user_balance(
                                            str(ctx.author.id), GAS_COIN,
                                            wallet_address, type_coin, height,
                                            getattr(getattr(self.bot.coin_list, GAS_COIN), "deposit_confirm_depth"),
                                            SERVER_BOT
                                        )
                                        actual_balance = userdata_balance['adjust']
                                        if actual_balance < fee_limit:  # use fee_limit to limit ADA
                                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you do not have sufficient "\
                                                f"{GAS_COIN} to withdraw {coin_name}. You need to have at least a "\
                                                f"reserved __{fee_limit} {GAS_COIN}__."
                                            await ctx.edit_original_message(content=msg, view=None)
                                            await log_to_channel(
                                                "withdraw",
                                                f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                                f"want to withdraw asset {coin_name} but having only {actual_balance} {GAS_COIN}."
                                            )
                                            return
                                    else:
                                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid main token, please report!'
                                        await ctx.edit_original_message(content=msg, view=None)
                                        await log_to_channel(
                                            "withdraw",
                                            f"[BUG] {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                            f"invalid main token for {coin_name}."
                                        )
                                        return
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, cannot check balance, please try again later!"
                                await ctx.edit_original_message(content=msg, view=None)
                                await log_to_channel(
                                    "withdraw",
                                    f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                    "failed to check balance gas coin for asset transfer..."
                                )
                                return

                            self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())

                            # Ask for confirm
                            view = ConfirmName(self.bot, ctx.author.id)
                            msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Do you want to withdraw "\
                                f"__{num_format_coin(amount)} {coin_name}__ with fee: __{num_format_coin(NetFee)} {coin_name}__{reserved_txt} to "\
                                f"_{address}_?"
                            await ctx.edit_original_message(content=msg, view=view)
                            # Wait for the View to stop listening for input...
                            await view.wait()

                            # Check the value to determine which button was pressed, if any.
                            key_withdraw = str(ctx.author.id) + "_" + coin_name
                            if view.value is False:
                                await ctx.edit_original_message(
                                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, withdraw cancelled!", view=None
                                )
                                del self.bot.tx_in_progress[str(ctx.author.id)]
                                if key_withdraw in self.withdraw_tx:
                                    del self.withdraw_tx[key_withdraw]
                                return
                            elif view.value is None:
                                await ctx.edit_original_message(
                                    content=msg + "\nTimeout!",
                                    view=None
                                )
                                del self.bot.tx_in_progress[str(ctx.author.id)]
                                if key_withdraw in self.withdraw_tx:
                                    del self.withdraw_tx[key_withdraw]
                                return
                            else:
                                await ctx.edit_original_message(
                                    view=None
                                )
                            self.withdraw_tx[key_withdraw] = int(time.time())

                            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                            asset_name = getattr(getattr(self.bot.coin_list, coin_name), "header")
                            policy_id = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                            send_tx = await self.wallet_api.send_external_ada_asset(
                                str(ctx.author.id), amount,
                                coin_decimal, SERVER_BOT, coin_name,
                                NetFee, address, asset_name,
                                policy_id, 120
                            )
                            if send_tx is not None and "status" in send_tx and send_tx['status'] == "pending":
                                tx_hash = send_tx['id']
                                gas_coin_msg = ""
                                if GAS_COIN is not None:
                                    gas_coin_msg = " and fee __{} {}__ you shall receive additional __{} {}__.".format(
                                        num_format_coin(send_tx['network_fee'] + fee_limit / 20),
                                        GAS_COIN, num_format_coin(send_tx['ada_received']), GAS_COIN)
                                fee_txt = "\nWithdrew fee/node: __{} {}__{}.".format(
                                    num_format_coin(NetFee), coin_name, gas_coin_msg)
                                explorer_link = self.utils.get_explorer_link(coin_name, tx_hash)
                                msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew "\
                                    f"{num_format_coin(amount)} {token_display}{equivalent_usd} to "\
                                    f"_{address}_.\nTransaction hash: _{tx_hash}_{fee_txt}{explorer_link}"
                                await ctx.edit_original_message(content=msg, view=None)
                                await log_to_channel(
                                    "withdraw",
                                    f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                    f"successfully withdrew {num_format_coin(amount)} "\
                                    f"{token_display}{equivalent_usd}.{explorer_link}"
                                )
                            elif "code" in send_tx and "message" in send_tx:
                                code = send_tx['code']
                                message = send_tx['message']
                                await log_to_channel(
                                    "withdraw",
                                    f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                    f"failed to withdraw {num_format_coin(amount)} "\
                                    f"{token_display}{equivalent_usd} to address {address}.```code: {code}\nmessage: {message}```"
                                )
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, internal error, please try again later!'
                                await ctx.edit_original_message(content=msg, view=None)
                            else:
                                await log_to_channel(
                                    "withdraw",
                                    f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                    f"failed to withdraw {num_format_coin(amount)} "\
                                    f"{token_display}{equivalent_usd} to address {address}."
                                )
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, internal error, please try again later!'
                                await ctx.edit_original_message(content=msg, view=None)
                    else:
                        # reject and tell to wait
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish."
                        await ctx.edit_original_message(content=msg)
                        return
                    try:
                        del self.bot.tx_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass
                elif type_coin == "XTZ":
                    # If main token is not enable for withdraw
                    if getattr(getattr(self.bot.coin_list, "XTZ"), "enable_withdraw") != 1:
                        msg = f"{ctx.author.mention}, XTZ/{coin_name} withdraw is currently disable."
                        await ctx.edit_original_message(content=msg)
                        return
                    if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
                        url = self.bot.erc_node_list['XTZ']
                        key = decrypt_string(getattr(getattr(self.bot.coin_list, "XTZ"), "walletkey"))
                        main_address = getattr(getattr(self.bot.coin_list, "XTZ"), "MainAddress")
                        if address == main_address:
                            # can not send
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you cannot send to this address _{address}_."
                            await ctx.edit_original_message(content=msg)
                            return
                        self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())

                        # Ask for confirm
                        view = ConfirmName(self.bot, ctx.author.id)
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Do you want to withdraw "\
                            f"__{num_format_coin(amount)} {coin_name}__ with fee: __{num_format_coin(NetFee)} {coin_name}__ to "\
                            f"_{address}_?"
                        await ctx.edit_original_message(content=msg, view=view)
                        # Wait for the View to stop listening for input...
                        await view.wait()

                        # Check the value to determine which button was pressed, if any.
                        key_withdraw = str(ctx.author.id) + "_" + coin_name
                        if view.value is False:
                            await ctx.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, withdraw cancelled!", view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        elif view.value is None:
                            await ctx.edit_original_message(
                                content=msg + "\nTimeout!",
                                view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        else:
                            await ctx.edit_original_message(
                                view=None
                            )
                        self.withdraw_tx[key_withdraw] = int(time.time())

                        send_tx = None
                        if self.bot.erc_node_list.get('XTZ_WITHDRAW'):
                            url = self.bot.erc_node_list['XTZ_WITHDRAW']
                        if coin_name == "XTZ":
                            send_tx = await self.wallet_api.send_external_xtz(
                                url, key, str(ctx.author.id), amount, address, coin_name,
                                coin_decimal, NetFee, type_coin, SERVER_BOT
                            )
                        else:
                            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                            token_id = int(getattr(getattr(self.bot.coin_list, coin_name), "wallet_address"))
                            token_type = getattr(getattr(self.bot.coin_list, coin_name), "header")
                            send_tx = await self.wallet_api.send_external_xtz_asset(
                                url, key, str(ctx.author.id), amount, address, coin_name,
                                coin_decimal, NetFee, type_coin, contract, token_id, token_type, SERVER_BOT
                            )
                        if send_tx:
                            explorer_link = self.utils.get_explorer_link(coin_name, send_tx)
                            fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                num_format_coin(NetFee), coin_name)
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew "\
                                f"{num_format_coin(amount)} {token_display}{equivalent_usd} to "\
                                f"_{address}_.\nTransaction hash: _{send_tx}_{fee_txt}{explorer_link}"
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"successfully withdrew {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd}.{explorer_link}"
                            )
                        else:
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw "\
                                f"{num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to _{address}_."
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"failed to withdraw {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to address {address}."
                            )
                    else:
                        # reject and tell to wait
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish."
                        await ctx.edit_original_message(content=msg)
                        return
                    try:
                        del self.bot.tx_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass
                elif type_coin == "ZIL":
                    # If main token is not enable for withdraw
                    if getattr(getattr(self.bot.coin_list, "ZIL"), "enable_withdraw") != 1:
                        msg = f"{ctx.author.mention}, ZIL/{coin_name} withdraw is currently disable."
                        await ctx.edit_original_message(content=msg)
                        return
                    if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
                        key = decrypt_string(getattr(getattr(self.bot.coin_list, "ZIL"), "walletkey"))
                        main_address = getattr(getattr(self.bot.coin_list, "ZIL"), "MainAddress")
                        if address == main_address:
                            # can not send
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you cannot send to this address _{address}_.'
                            await ctx.edit_original_message(content=msg)
                            return
                        self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())

                        # Ask for confirm
                        view = ConfirmName(self.bot, ctx.author.id)
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Do you want to withdraw "\
                            f"__{num_format_coin(amount)} {coin_name}__ with fee: __{num_format_coin(NetFee)} {coin_name}__ to "\
                            f"_{address}_?"
                        await ctx.edit_original_message(content=msg, view=view)
                        # Wait for the View to stop listening for input...
                        await view.wait()

                        # Check the value to determine which button was pressed, if any.
                        key_withdraw = str(ctx.author.id) + "_" + coin_name
                        if view.value is False:
                            await ctx.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, withdraw cancelled!", view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        elif view.value is None:
                            await ctx.edit_original_message(
                                content=msg + "\nTimeout!",
                                view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        else:
                            await ctx.edit_original_message(
                                view=None
                            )
                        self.withdraw_tx[key_withdraw] = int(time.time())

                        send_tx = None
                        if coin_name == "ZIL":
                            send_tx = await self.wallet_api.send_external_zil(
                                key, str(ctx.author.id), amount, address, coin_name,
                                coin_decimal, NetFee, type_coin, SERVER_BOT
                            )
                        else:
                            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                            send_tx = await self.wallet_api.send_external_zil_asset(
                                contract, key, str(ctx.author.id), int(amount * 10 ** coin_decimal),
                                address, coin_name, coin_decimal, NetFee, type_coin, SERVER_BOT
                            )
                        if send_tx:
                            explorer_link = self.utils.get_explorer_link(coin_name, send_tx)
                            fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                num_format_coin(NetFee), coin_name)
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew "\
                                f"{num_format_coin(amount)} {token_display}{equivalent_usd} to "\
                                f"_{address}_.\nTransaction hash: _{send_tx}_{fee_txt}{explorer_link}"
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"successfully withdrew {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd}.{explorer_link}"
                            )
                        else:
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw "\
                                f"{num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to _{address}_."
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"failed to withdraw {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to address {address}."
                            )
                    else:
                        # reject and tell to wait
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. "\
                            "Please wait it to finish."
                        await ctx.edit_original_message(content=msg)
                        return
                    try:
                        del self.bot.tx_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass
                elif type_coin == "VET":
                    # If main token is not enable for withdraw
                    if getattr(getattr(self.bot.coin_list, "VET"), "enable_withdraw") != 1:
                        msg = f"{ctx.author.mention}, VET/{coin_name} withdraw is currently disable."
                        await ctx.edit_original_message(content=msg)
                        return
                    if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
                        key = decrypt_string(getattr(getattr(self.bot.coin_list, "VET"), "walletkey"))
                        main_address = getattr(getattr(self.bot.coin_list, "VET"), "MainAddress")
                        contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                        if address == main_address:
                            # can not send
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you cannot send to this address _{address}_.'
                            await ctx.edit_original_message(content=msg)
                            return
                        self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())

                        # Ask for confirm
                        view = ConfirmName(self.bot, ctx.author.id)
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Do you want to withdraw "\
                            f"__{num_format_coin(amount)} {coin_name}__ with fee: __{num_format_coin(NetFee)} {coin_name}__ to "\
                            f"_{address}_?"
                        await ctx.edit_original_message(content=msg, view=view)
                        # Wait for the View to stop listening for input...
                        await view.wait()

                        # Check the value to determine which button was pressed, if any.
                        key_withdraw = str(ctx.author.id) + "_" + coin_name
                        if view.value is False:
                            await ctx.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, withdraw cancelled!", view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        elif view.value is None:
                            await ctx.edit_original_message(
                                content=msg + "\nTimeout!",
                                view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        else:
                            await ctx.edit_original_message(
                                view=None
                            )
                        self.withdraw_tx[key_withdraw] = int(time.time())

                        transaction = functools.partial(
                            vet_move_token, self.bot.erc_node_list['VET'], coin_name, contract,
                            address, key, key, int(amount*10**coin_decimal)
                        )
                        send_tx = await self.bot.loop.run_in_executor(None, transaction)
                        if send_tx:
                            await self.wallet_api.insert_external_vet(
                                str(ctx.author.id), amount, address, coin_name, contract,
                                coin_decimal, NetFee, send_tx, type_coin, SERVER_BOT
                            )
                            explorer_link = self.utils.get_explorer_link(coin_name, send_tx)
                            fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                num_format_coin(NetFee), coin_name)
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew "\
                                f"{num_format_coin(amount)} {token_display}{equivalent_usd} "\
                                f"to _{address}_.\nTransaction hash: _{send_tx}_{fee_txt}{explorer_link}"
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"successfully withdrew {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd}.{explorer_link}"
                            )
                        else:
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to "\
                                f"withdraw {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to _{address}_."
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"failed to withdraw {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to address {address}."
                            )
                    else:
                        # reject and tell to wait
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. "\
                            "Please wait it to finish."
                        await ctx.edit_original_message(content=msg)
                        return
                    try:
                        del self.bot.tx_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass
                elif type_coin == "XRP":
                    # If main token is not enable for withdraw
                    if getattr(getattr(self.bot.coin_list, "XRP"), "enable_withdraw") != 1:
                        msg = f"{ctx.author.mention}, XRP/{coin_name} withdraw is currently disable."
                        await ctx.edit_original_message(content=msg)
                        return
                    if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
                        url = self.bot.erc_node_list['XRP']
                        key = decrypt_string(getattr(getattr(self.bot.coin_list, "XRP"), "walletkey"))
                        main_address = getattr(getattr(self.bot.coin_list, "XRP"), "MainAddress")
                        if address == main_address:
                            # can not send
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you cannot send to this address _{address}_.'
                            await ctx.edit_original_message(content=msg)
                            return
                        self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())

                        # Ask for confirm
                        view = ConfirmName(self.bot, ctx.author.id)
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Do you want to withdraw "\
                            f"__{num_format_coin(amount)} {coin_name}__ with fee: __{num_format_coin(NetFee)} {coin_name}__ to "\
                            f"_{address}_?"
                        await ctx.edit_original_message(content=msg, view=view)
                        # Wait for the View to stop listening for input...
                        await view.wait()

                        # Check the value to determine which button was pressed, if any.
                        key_withdraw = str(ctx.author.id) + "_" + coin_name
                        if view.value is False:
                            await ctx.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, withdraw cancelled!", view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        elif view.value is None:
                            await ctx.edit_original_message(
                                content=msg + "\nTimeout!",
                                view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        else:
                            await ctx.edit_original_message(
                                view=None
                            )
                        self.withdraw_tx[key_withdraw] = int(time.time())

                        issuer = getattr(getattr(self.bot.coin_list, coin_name), "header")
                        currency_code = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                        if self.bot.erc_node_list.get('XRP_WITHDRAW'):
                            url = self.bot.erc_node_list['XRP_WITHDRAW']
                        send_tx = await self.wallet_api.send_external_xrp(
                            url, key, str(ctx.author.id), address, amount, NetFee, coin_name, issuer,
                            currency_code, coin_decimal, SERVER_BOT
                        )
                        if send_tx:
                            explorer_link = self.utils.get_explorer_link(coin_name, send_tx)
                            fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                num_format_coin(NetFee), coin_name)
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew "\
                                f"{num_format_coin(amount)} {token_display}{equivalent_usd} to "\
                                f"_{address}_.\nTransaction hash: _{send_tx}_{fee_txt}{explorer_link}"
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"successfully withdrew {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd}.{explorer_link}"
                            )
                        else:
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw "\
                                f"{num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to _{address}_."
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"failed to withdraw {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to address {address}."
                            )
                    else:
                        # reject and tell to wait
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish."
                        await ctx.edit_original_message(content=msg)
                        return
                    try:
                        del self.bot.tx_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass
                elif type_coin == "NEAR":
                    # If main token is not enable for withdraw
                    if getattr(getattr(self.bot.coin_list, "NEAR"), "enable_withdraw") != 1:
                        msg = f"{ctx.author.mention}, NEAR/{coin_name} withdraw is currently disable."
                        await ctx.edit_original_message(content=msg)
                        return
                    if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
                        url = self.bot.erc_node_list['NEAR']
                        key = decrypt_string(getattr(getattr(self.bot.coin_list, "NEAR"), "walletkey"))
                        main_address = getattr(getattr(self.bot.coin_list, "NEAR"), "MainAddress")
                        token_contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                        if address == main_address:
                            # can not send
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you cannot send to this address _{address}_.'
                            await ctx.edit_original_message(content=msg)
                            return
                        self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())

                        # Ask for confirm
                        view = ConfirmName(self.bot, ctx.author.id)
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Do you want to withdraw "\
                            f"__{num_format_coin(amount)} {coin_name}__ with fee: __{num_format_coin(NetFee)} {coin_name}__ to "\
                            f"_{address}_?"
                        await ctx.edit_original_message(content=msg, view=view)
                        # Wait for the View to stop listening for input...
                        await view.wait()

                        # Check the value to determine which button was pressed, if any.
                        key_withdraw = str(ctx.author.id) + "_" + coin_name
                        if view.value is False:
                            await ctx.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, withdraw cancelled!", view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        elif view.value is None:
                            await ctx.edit_original_message(
                                content=msg + "\nTimeout!",
                                view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        else:
                            await ctx.edit_original_message(
                                view=None
                            )
                        self.withdraw_tx[key_withdraw] = int(time.time())
                        if self.bot.erc_node_list.get('NEAR_WITHDRAW'):
                            url = self.bot.erc_node_list['NEAR_WITHDRAW']
                        send_tx = await self.wallet_api.send_external_near(
                            url, token_contract, key, str(ctx.author.id), main_address, amount,
                            address, coin_name, coin_decimal, NetFee, SERVER_BOT
                        )
                        if send_tx:
                            explorer_link = self.utils.get_explorer_link(coin_name, send_tx)
                            fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                num_format_coin(NetFee), coin_name)
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew "\
                                f"{num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to _{address}_.\nTransaction hash: _{send_tx}_{fee_txt}{explorer_link}"
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"successfully withdrew {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd}.{explorer_link}"
                            )
                        else:
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw "\
                                f"{num_format_coin(amount)} {token_display}{equivalent_usd} to _{address}_."
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"failed to withdraw {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to address {address}."
                            )
                    else:
                        # reject and tell to wait
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish."
                        await ctx.edit_original_message(content=msg)
                        return
                    try:
                        del self.bot.tx_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass
                elif type_coin == "SOL" or type_coin == "SPL":
                    # valide address
                    proxy = "http://{}:{}/validate_address".format(self.bot.config['api_helper']['connect_ip'], self.bot.config['api_helper']['port_solana'])
                    validate_addr = await self.utils.solana_validate_address(
                        proxy, address
                    )
                    if validate_addr.get('valid') and validate_addr['valid'] is True:
                        pass
                    else:
                        msg = f"{ctx.author.mention}, SOL/{coin_name} invalid address {address}."
                        await ctx.edit_original_message(content=msg)
                        return

                    # If main token is not enable for withdraw
                    if getattr(getattr(self.bot.coin_list, "SOL"), "enable_withdraw") != 1:
                        msg = f"{ctx.author.mention}, SOL/{coin_name} withdraw is currently disable."
                        await ctx.edit_original_message(content=msg)
                        return
                    if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
                        self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())
                        tx_fee = getattr(getattr(self.bot.coin_list, coin_name), "tx_fee")

                        # Ask for confirm
                        view = ConfirmName(self.bot, ctx.author.id)
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Do you want to withdraw "\
                            f"__{num_format_coin(amount)} {coin_name}__ with fee: __{num_format_coin(NetFee)} {coin_name}__ to "\
                            f"_{address}_?"
                        await ctx.edit_original_message(content=msg, view=view)
                        # Wait for the View to stop listening for input...
                        await view.wait()

                        # Check the value to determine which button was pressed, if any.
                        key_withdraw = str(ctx.author.id) + "_" + coin_name
                        if view.value is False:
                            await ctx.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, withdraw cancelled!", view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        elif view.value is None:
                            await ctx.edit_original_message(
                                content=msg + "\nTimeout!",
                                view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        else:
                            await ctx.edit_original_message(
                                view=None
                            )
                        self.withdraw_tx[key_withdraw] = int(time.time())

                        endpoint_url = self.bot.erc_node_list['SOL']
                        if self.bot.erc_node_list.get('SOL_WITHDRAW'):
                            endpoint_url = self.bot.erc_node_list['SOL_WITHDRAW']
                        send_tx = await self.wallet_api.send_external_sol(
                            "http://{}:{}/send_transaction".format(self.bot.config['api_helper']['connect_ip'], self.bot.config['api_helper']['port_solana']),
                            endpoint_url,
                            str(ctx.author.id), amount, address, coin_name,
                            coin_decimal, tx_fee, NetFee, SERVER_BOT
                        )
                        if send_tx:
                            explorer_link = self.utils.get_explorer_link(coin_name, send_tx)
                            fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                num_format_coin(NetFee), coin_name)
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew "\
                                f"{num_format_coin(amount)} {token_display}{equivalent_usd} to "\
                                f"_{address}_.\nTransaction hash: _{send_tx}_{fee_txt}{explorer_link}"
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"successfully withdrew {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd}.{explorer_link}"
                            )
                        else:
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw "\
                                f"{num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to _{address}_."
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"failed to withdraw {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to address {address}."
                            )
                    else:
                        # reject and tell to wait
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. "\
                            "Please wait it to finish."
                        await ctx.edit_original_message(content=msg)
                        return
                    try:
                        del self.bot.tx_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass
                elif type_coin == "BTC":
                    if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
                        self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())

                        # Ask for confirm
                        view = ConfirmName(self.bot, ctx.author.id)
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Do you want to withdraw "\
                            f"__{num_format_coin(amount)} {coin_name}__ with fee: __{num_format_coin(NetFee)} {coin_name}__ to "\
                            f"_{address}_?"
                        await ctx.edit_original_message(content=msg, view=view)
                        # Wait for the View to stop listening for input...
                        await view.wait()

                        # Check the value to determine which button was pressed, if any.
                        key_withdraw = str(ctx.author.id) + "_" + coin_name
                        if view.value is False:
                            await ctx.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, withdraw cancelled!", view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        elif view.value is None:
                            await ctx.edit_original_message(
                                content=msg + "\nTimeout!",
                                view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        else:
                            await ctx.edit_original_message(
                                view=None
                            )
                        self.withdraw_tx[key_withdraw] = int(time.time())

                        send_tx = await self.wallet_api.send_external_doge(
                            str(ctx.author.id), amount, address, coin_name, 0, NetFee, SERVER_BOT
                        )  # tx_fee=0
                        if send_tx:
                            explorer_link = self.utils.get_explorer_link(coin_name, send_tx)
                            fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                num_format_coin(NetFee), coin_name)
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew "\
                                f"{num_format_coin(amount)} {token_display}{equivalent_usd} to "\
                                f"_{address}_.\nTransaction hash: _{send_tx}_{fee_txt}{explorer_link}"
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"successfully withdrew {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd}.{explorer_link}"
                            )
                        else:
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw "\
                                f"{num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to _{address}_."
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"failed to withdraw {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to address {address}."
                            )
                    else:
                        # reject and tell to wait
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. "\
                            "Please wait it to finish."
                        await ctx.edit_original_message(content=msg)
                        return
                    try:
                        del self.bot.tx_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass
                elif type_coin == "NEO":
                    if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
                        self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())
                        contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                        send_tx = await self.wallet_api.send_external_neo(
                            str(ctx.author.id), coin_decimal, contract, amount, address, coin_name, NetFee, SERVER_BOT
                        )

                        # Ask for confirm
                        view = ConfirmName(self.bot, ctx.author.id)
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Do you want to withdraw "\
                            f"__{num_format_coin(amount)} {coin_name}__ with fee: __{num_format_coin(NetFee)} {coin_name}__ to "\
                            f"_{address}_?"
                        await ctx.edit_original_message(content=msg, view=view)
                        # Wait for the View to stop listening for input...
                        await view.wait()

                        # Check the value to determine which button was pressed, if any.
                        key_withdraw = str(ctx.author.id) + "_" + coin_name
                        if view.value is False:
                            await ctx.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, withdraw cancelled!", view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        elif view.value is None:
                            await ctx.edit_original_message(
                                content=msg + "\nTimeout!",
                                view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        else:
                            await ctx.edit_original_message(
                                view=None
                            )
                        self.withdraw_tx[key_withdraw] = int(time.time())

                        if send_tx:
                            explorer_link = self.utils.get_explorer_link(coin_name, send_tx)
                            fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                num_format_coin(NetFee), coin_name
                            )
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew "\
                                f"{num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to _{address}_.\n"\
                                f"Transaction hash: _{send_tx}_{fee_txt}{explorer_link}"
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} successfully "\
                                f"withdrew {num_format_coin(amount)} {token_display}{equivalent_usd}.{explorer_link}"
                            )
                        else:
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw "\
                                f"{num_format_coin(amount)} {token_display}{equivalent_usd} to _{address}_."
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"failed to withdraw {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to address {address}."
                            )
                    else:
                        # reject and tell to wait
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish."
                        await ctx.edit_original_message(content=msg)
                        return
                    try:
                        del self.bot.tx_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass
                elif type_coin == "XMR" or type_coin == "TRTL-API" or type_coin == "TRTL-SERVICE" or type_coin == "BCN":
                    if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
                        self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())
                        main_address = getattr(getattr(self.bot.coin_list, coin_name), "MainAddress")
                        mixin = getattr(getattr(self.bot.coin_list, coin_name), "mixin")
                        wallet_address = getattr(getattr(self.bot.coin_list, coin_name), "wallet_address")
                        header = getattr(getattr(self.bot.coin_list, coin_name), "header")
                        is_fee_per_byte = getattr(getattr(self.bot.coin_list, coin_name), "is_fee_per_byte")

                        # Ask for confirm
                        view = ConfirmName(self.bot, ctx.author.id)
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Do you want to withdraw "\
                            f"__{num_format_coin(amount)} {coin_name}__ with fee: __{num_format_coin(NetFee)} {coin_name}__ to "\
                            f"_{address}_?"
                        await ctx.edit_original_message(content=msg, view=view)
                        # Wait for the View to stop listening for input...
                        await view.wait()

                        # Check the value to determine which button was pressed, if any.
                        key_withdraw = str(ctx.author.id) + "_" + coin_name
                        if view.value is False:
                            await ctx.edit_original_message(
                                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, withdraw cancelled!", view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        elif view.value is None:
                            await ctx.edit_original_message(
                                content=msg + "\nTimeout!",
                                view=None
                            )
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                            if key_withdraw in self.withdraw_tx:
                                del self.withdraw_tx[key_withdraw]
                            return
                        else:
                            await ctx.edit_original_message(
                                view=None
                            )
                        self.withdraw_tx[key_withdraw] = int(time.time())

                        send_tx = await self.wallet_api.send_external_xmr(
                            type_coin, main_address, str(ctx.author.id),
                            amount, address, coin_name, coin_decimal,
                            tx_fee, NetFee, is_fee_per_byte, mixin,
                            SERVER_BOT, wallet_address, header,
                            None
                        )  # paymentId: None (end)
                        if send_tx:
                            explorer_link = self.utils.get_explorer_link(coin_name, send_tx)
                            fee_txt = "\nWithdrew fee/node: __{} {}__.".format(
                                num_format_coin(NetFee), coin_name)
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, you withdrew "\
                                f"{num_format_coin(amount)} {token_display}{equivalent_usd} "\
                                f"to _{address}_.\nTransaction hash: _{send_tx}_{fee_txt}{explorer_link}"
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"successfully executed withdraw {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd}.{explorer_link}"
                            )
                        else:
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, failed to withdraw "\
                                f"{num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to _{address}_."
                            await ctx.edit_original_message(content=msg, view=None)
                            await log_to_channel(
                                "withdraw",
                                f"🔴 User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"failed to execute to withdraw {num_format_coin(amount)} "\
                                f"{token_display}{equivalent_usd} to address {address}."
                            )
                    else:
                        # reject and tell to wait
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. "\
                            "Please wait it to finish."
                        await ctx.edit_original_message(content=msg)
                        return
                    try:
                        del self.bot.tx_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass
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
        await ctx.response.send_message(f"{EMOJI_HOURGLASS_NOT_DONE} {ctx.author.mention}, loading withdraw...", ephemeral=True)
        await self.async_withdraw(ctx, amount, token, address)

    @withdraw.autocomplete("token")
    async def withdraw_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]

    @commands.slash_command(
        usage='transfer',
        options=[
            Option('token', 'token', OptionType.string, required=True)
        ],
        description="withdraw to your external address with extra option."
    )
    async def transfer(
        self,
        ctx,
        token: str
    ):
        type_coin = getattr(getattr(self.bot.coin_list, token.upper()), "type")

        # check lock
        try:
            is_user_locked = self.utils.is_locked_user(str(ctx.author.id), SERVER_BOT)
            if is_user_locked is True:
                await ctx.response.send_message(f"{EMOJI_RED_NO} {ctx.author.mention}, your account is locked from using the Bot. "\
                    "Please contact bot dev by /about link."
                )
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # end check lock

        # Waits until the user submits the modal.
        try:
            await ctx.response.send_modal(
                modal=TransferExtra(ctx, self.bot, token.upper(), type_coin)
            )
            modal_inter: disnake.ModalInteraction = await self.bot.wait_for(
                "modal_submit",
                check=lambda i: i.custom_id == "modal_transfer_extra" and i.author.id == ctx.author.id,
                timeout=30,
            )
        except asyncio.TimeoutError:
            # The user didn't submit the modal in the specified period of time.
            # This is done since Discord doesn't dispatch any event for when a modal is closed/dismissed.
            await modal_inter.response.send_message("Timeout!", ephemeral=True)
            return
        #await modal_inter.response.send_message("modal", ephemeral=True)

    @transfer.autocomplete("token")
    async def transfer_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        coin_list = []
        for coin in self.bot.coin_name_list:
            use_extra_transfer = getattr(getattr(self.bot.coin_list, coin.upper()), "use_extra_transfer")
            if use_extra_transfer == 1:
                coin_list.append(coin)
        return [name for name in coin_list if string in name.lower()][:10]

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
        await ctx.response.send_message(f"{EMOJI_HOURGLASS_NOT_DONE} {ctx.author.mention}, loading withdraw...", ephemeral=True)
        await self.async_withdraw(ctx, amount, token, address)

    @send.autocomplete("token")
    async def send_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]
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
            embed = disnake.Embed(
                title=f'TipBot Vote Reward{title_text}',
                description=f"```1] Set your reward coin claim with any of this {list_coins_str} with command /claim "\
                    f"token_name\n\n2] Vote for TipBot in below links.\n\n```",
                timestamp=datetime.fromtimestamp(int(time.time()))
            )

            reward_list_default = []
            link_list = []
            for key in ["topgg", "discordbotlist", "botsfordiscord"]:
                reward_list = []
                for each in list_coin_sets[key]:
                    for k, v in each.items():
                        reward_list.append("{}{}".format(v, k))
                reward_list_default = reward_list
                link_list.append("Vote at: [{}]({})".format(key,  self.bot.config['bot_vote_link'][key]))
            embed.add_field(name="Vote List", value="\n".join(link_list), inline=False)
            embed.add_field(
                name="Vote rewards".format(key),
                value="```{}```".format(", ".join(reward_list_default)),
                inline=False
            )

            # if advert enable
            if self.bot.config['discord']['enable_advert'] == 1 and len(self.bot.advert_list) > 0:
                try:
                    random.shuffle(self.bot.advert_list)
                    embed.add_field(
                        name="{}".format(self.bot.advert_list[0]['title']),
                        value="```{}```👉 <{}>".format(self.bot.advert_list[0]['content'], self.bot.advert_list[0]['link']),
                        inline=False
                    )
                    await self.utils.advert_impress(
                        self.bot.advert_list[0]['id'], str(ctx.author.id),
                        str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM"
                    )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            # end advert

            embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
            embed.set_thumbnail(url=ctx.author.display_avatar)
            try:
                if get_user_coin is not None:
                    embed.set_footer(
                        text="Requested by: {}#{} | preferred: {}".format(
                            ctx.author.name, ctx.author.discriminator, get_user_coin['coin_name'])
                        )
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
                embed.add_field(
                    name="Total Vote",
                    value="```{}```".format("\n".join(coin_list_values)),
                    inline=False
                )
                embed.set_footer(
                    text="Requested by: {}#{} | Total votes: {:,.0f}".format(
                        ctx.author.name, ctx.author.discriminator, nos_vote)
                    )
                await ctx.edit_original_message(content=None, embed=embed, view=RowButtonRowCloseAnyMessage())
            return
        else:
            coin_name = token.upper()
            if coin_name not in list_coin_names:
                msg = f'{ctx.author.mention}, __{coin_name}__ is invalid or does not exist in faucet list!'
                await ctx.edit_original_message(content=msg)
                return
            else:
                # Update user setting faucet
                update = await faucet.update_faucet_user(str(ctx.author.id), coin_name, SERVER_BOT)
                if update:
                    msg = f"{ctx.author.mention}, you updated your preferred claimed reward to __{coin_name}__. "\
                        f"This preference applies only for TipBot's voting reward."\
                        f" Type {self.bot.config['command_list']['claim']} without token to see the list of voting websites."
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
            sum_sub = 0.0
            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")

            get_deposit = await self.sql_get_userwallet(
                str(self.bot.user.id), coin_name, net_name, type_coin, SERVER_BOT, 0
            )
            if get_deposit is None:
                get_deposit = await self.sql_register_user(
                    str(self.bot.user.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 0
                )

            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']
            elif type_coin in ["XRP"]:
                wallet_address = get_deposit['destination_tag']

            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
            try:
                userdata_balance = await self.wallet_api.user_balance(
                    str(self.bot.user.id), coin_name, wallet_address, type_coin,
                    height, deposit_confirm_depth, SERVER_BOT
                )
                actual_balance = float(userdata_balance['adjust'])
                if coin_name in get_game_stat:
                    sum_sub = float(get_game_stat[coin_name])

                balance_actual = num_format_coin(actual_balance)
                get_claimed_count = await store.sql_faucet_sum_count_claimed(coin_name)
                sub_claim = num_format_coin(
                        float(get_claimed_count['claimed']) + sum_sub
                    ) if get_claimed_count['count'] > 0 else f"0.00{coin_name}"
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
        try:
            cmd_name = ctx.application_command.qualified_name
            command_mention = f"__/{cmd_name}__"
            if self.bot.config['discord']['enable_command_mention'] == 1:
                cmd = self.bot.get_global_command_named(cmd_name)
                command_mention = f"</{cmd_name}:{cmd.id}>"
        except Exception:
            traceback.print_exc(file=sys.stdout)

        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing {command_mention} ...'
        await ctx.response.send_message(msg)
        await self.bot_log()

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

        if str(ctx.author.id) in self.bot.tx_in_progress and \
            int(time.time()) - self.bot.tx_in_progress[str(ctx.author.id)] < 150 \
                and ctx.author.id != self.bot.config['discord']['owner_id']:
            msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress."
            await ctx.edit_original_message(content=msg)
            return

        if not hasattr(ctx.guild, "id"):
            msg = f"{ctx.author.mention}, you can invite me to your guild with __/invite__\'s link and execute {command_mention}. "\
                f"{command_mention} is not available in Direct Message."
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
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, {coin_name} not available for {command_mention}."
                await ctx.edit_original_message(content=msg)
                return

        total_claimed = '{:,.0f}'.format(await store.sql_faucet_count_all())
        if info and info.upper() == "INFO":
            remaining = await self.bot_faucet(ctx, self.bot.faucet_coins) or ''
            msg = f"{ctx.author.mention} {command_mention} balance:\n```{remaining}```Total user claims: **{total_claimed}** times. "\
                f"Tip me if you want to feed these faucets. "\
                f"Use {self.bot.config['command_list']['claim']} to vote TipBot and get reward."
            await ctx.edit_original_message(content=msg)
            return

        claim_interval = self.bot.config['faucet']['interval']
        half_claim_interval = int(self.bot.config['faucet']['interval'] / 2)

        advert_txt = ""
        # if advert enable
        if self.bot.config['discord']['enable_advert'] == 1 and len(self.bot.advert_list) > 0:
            try:
                random.shuffle(self.bot.advert_list)
                advert_txt = "\n__**Random Message:**__ [{}](<{}>)```{}```".format(
                    self.bot.advert_list[0]['title'], self.bot.advert_list[0]['link'], self.bot.advert_list[0]['content']
                )
                await self.utils.advert_impress(
                    self.bot.advert_list[0]['id'], str(ctx.author.id),
                    str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM"
                )
            except Exception:
                traceback.print_exc(file=sys.stdout)
        # end advert

        serverinfo = None
        extra_take_text = ""
        try:
            # check if bot channel is set:
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
            if serverinfo and serverinfo['botchan'] and ctx.channel.id != int(serverinfo['botchan']):
                try:
                    botChan = self.bot.get_channel(int(serverinfo['botchan']))
                    if botChan is not None:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, {botChan.mention} was assigned for the bot channel!'
                        await ctx.edit_original_message(content=msg)
                        # add penalty:
                        try:
                            key = self.bot.config['kv_db']['prefix_faucet_take_penalty'] + SERVER_BOT + "_" + str(ctx.author.id)
                            await self.utils.async_set_cache_kv(
                                "faucet",
                                key,
                                {
                                    'penalty_at': int(time.time())
                                }
                            )
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                        return
                except Exception:
                    traceback.print_exc(file=sys.stdout)

            if serverinfo and serverinfo['enable_faucet'] == "NO":
                if self.enable_logchan:
                    await self.botLogChan.send(
                        f'{ctx.author.name} / {ctx.author.id} tried {command_mention} in {ctx.guild.name} / {ctx.guild.id} which is disable.')
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, {command_mention} in this guild is disable."
                await ctx.edit_original_message(content=msg)
                return
            elif serverinfo and serverinfo['enable_faucet'] == "YES" and serverinfo['faucet_channel'] is not None and \
                    serverinfo['faucet_coin'] is not None:
                extra_take_text = " Additional reward:\n\n⚆ You can also do /faucet in <#{}> which funded by the guild.".format(
                    serverinfo['faucet_channel'])
                if serverinfo['vote_reward_amount'] and serverinfo['vote_reward_channel']:
                    vote_reward_coin = serverinfo['vote_reward_coin']
                    vote_coin_decimal = getattr(getattr(self.bot.coin_list, vote_reward_coin), "decimal")
                    vote_reward_amount = num_format_coin(
                        serverinfo['vote_reward_amount']
                    )

                    extra_take_text += "\n⚆ Vote {} at top.gg <https://top.gg/servers/{}/vote> for {} {} each vote.".format(
                        ctx.guild.name, ctx.guild.id, vote_reward_amount, serverinfo['vote_reward_coin'])
                if serverinfo['rt_reward_amount'] and serverinfo['rt_reward_coin'] and serverinfo[
                    'rt_end_timestamp'] and serverinfo['rt_end_timestamp'] - 600 > int(time.time()) and serverinfo[
                    'rt_link']:
                    # Some RT with reward still going
                    tweet_link = serverinfo['rt_link']
                    rt_reward_coin = serverinfo['rt_reward_coin']
                    rt_coin_decimal = getattr(getattr(self.bot.coin_list, rt_reward_coin), "decimal")
                    time_left = serverinfo['rt_end_timestamp'] - int(time.time()) - 600  # reserved.
                    rt_amount = num_format_coin(serverinfo['rt_reward_amount'])

                    if time_left > 0:
                        extra_take_text += f"\n⚆ RT <{tweet_link}> and get {rt_amount} {rt_reward_coin} "\
                            f"(Be sure you verified your twitter with TipBot <https://www.youtube.com/watch?v=q79_1M0_Hsw>). "\
                            f"Time left __{seconds_str_days(time_left)}__."
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # end of bot channel check

        # check user claim:
        try:
            if info is None:
                check_claimed = await store.sql_faucet_checkuser(str(ctx.author.id), SERVER_BOT, "TAKE")
                if check_claimed is not None:
                    if int(time.time()) - check_claimed['claimed_at'] <= claim_interval * 3600:
                        # time_waiting = seconds_str(
                        #   claim_interval * 3600 - int(time.time()) + check_claimed['claimed_at']
                        # )
                        user_claims = await store.sql_faucet_count_user(str(ctx.author.id))
                        number_user_claimed = '{:,.0f}'.format(user_claims)
                        time_waiting = disnake.utils.format_dt(
                            claim_interval * 3600 + check_claimed['claimed_at'],
                            style='R'
                        )
                        last_claim_at = disnake.utils.format_dt(
                            check_claimed['claimed_at'],
                            style='f'
                        )
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you claimed {command_mention} on {last_claim_at}. "\
                            f"Waiting time {time_waiting} for next {command_mention}. Total user claims: **{total_claimed}** times. "\
                            f"You have claimed: **{number_user_claimed}** time(s). Tip me if you want to feed these faucets. "\
                            f"Use {self.bot.config['command_list']['claim']} to vote TipBot and get reward."\
                            f"{extra_take_text}{advert_txt}"
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
            remaining_time = int(account_created.timestamp()) + self.bot.config['faucet']['account_age_to_claim']
            if (datetime.utcnow().astimezone() - account_created).total_seconds() <= self.bot.config['faucet']['account_age_to_claim']:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. "\
                    f"Wait till <t:{str(remaining_time)}:f> before using {command_mention}. "\
                    f"Alternatively, vote for TipBot to get reward {self.bot.config['command_list']['claim']}."\
                    f"{extra_take_text}{advert_txt}"
                await ctx.edit_original_message(content=msg)
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            # check penalty:
            try:
                key = self.bot.config['kv_db']['prefix_faucet_take_penalty'] + SERVER_BOT + "_" + str(ctx.author.id)
                faucet_penalty = await self.utils.async_get_cache_kv("faucet",  key)
                if faucet_penalty is not None and not info:
                    if half_claim_interval * 3600 - int(time.time()) + faucet_penalty['penalty_at'] > 0:
                        time_waiting = "<t:{}:R>".format(half_claim_interval * 3600 + faucet_penalty['penalty_at'])
                        penalty_at = "<t:{}:f>".format(faucet_penalty['penalty_at'])
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention} You claimed in a wrong channel "\
                            f"{penalty_at}. Waiting time {time_waiting} for next {command_mention} "\
                            f"and be sure to be the right channel set by the guild. Use {self.bot.config['command_list']['claim']} "\
                            f"to vote TipBot and get reward.{extra_take_text}{advert_txt}"
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
        price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
        contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
        coin_emoji = ""
        try:
            if ctx.guild.get_member(int(self.bot.user.id)).guild_permissions.external_emojis is True:
                coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                coin_emoji = coin_emoji + " " if coin_emoji else ""
        except Exception:
            traceback.print_exc(file=sys.stdout)
        get_deposit = await self.sql_get_userwallet(
            str(self.bot.user.id), coin_name, net_name, type_coin, SERVER_BOT, 0
        )
        if get_deposit is None:
            get_deposit = await self.sql_register_user(
                str(self.bot.user.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 0
            )

        wallet_address = get_deposit['balance_wallet_address']
        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
            wallet_address = get_deposit['paymentid']
        elif type_coin in ["XRP"]:
            wallet_address = get_deposit['destination_tag']

        height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
        userdata_balance = await self.wallet_api.user_balance(
            str(self.bot.user.id), coin_name, wallet_address, type_coin, height,
            deposit_confirm_depth, SERVER_BOT
        )
        actual_balance = float(userdata_balance['adjust'])

        amount = random.uniform(
            getattr(getattr(self.bot.coin_list, coin_name), "faucet_min"),
            getattr(getattr(self.bot.coin_list, coin_name), "faucet_max")
        )
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
            amount_msg_zero = 'Get 0 random amount requested faucet by: {}#{} for coin {}'.format(
                ctx.author.name, ctx.author.discriminator, coin_name
            )
            await logchanbot(amount_msg_zero)
            return

        if amount > actual_balance and not info:
            msg = f'{ctx.author.mention} Please try again later. Bot runs out of **{coin_name}**{advert_txt}'
            await ctx.edit_original_message(content=msg)
            return

        tip = None
        if str(ctx.author.id) in self.bot.tx_in_progress and \
            int(time.time()) - self.bot.tx_in_progress[str(ctx.author.id)] < 150 \
                and ctx.author.id != self.bot.config['discord']['owner_id']:
            msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress."
            await ctx.edit_original_message(content=msg)
            return
        else:
            self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())
        try:
            if not info:
                amount_in_usd = 0.0
                per_unit = None
                if price_with:
                    per_unit = await self.utils.get_coin_price(coin_name, price_with)
                    if per_unit and per_unit['price'] and per_unit['price'] > 0:
                        per_unit = per_unit['price']
                if per_unit and per_unit > 0:
                    amount_in_usd = float(Decimal(per_unit) * Decimal(amount))

                tip = await store.sql_user_balance_mv_single(
                    str(self.bot.user.id), str(ctx.author.id),
                    str(ctx.guild.id), str(ctx.channel.id), amount, coin_name,
                    "FAUCET", coin_decimal, SERVER_BOT, contract,
                    amount_in_usd, None
                )
                try:
                    await store.sql_faucet_add(
                        str(ctx.author.id), str(ctx.guild.id), coin_name, amount,
                        coin_decimal, SERVER_BOT, "TAKE"
                    )
                    msg = f"{EMOJI_MONEYFACE} {ctx.author.mention}, you got a random {command_mention} "\
                        f"{coin_emoji} {num_format_coin(amount)} {coin_name}. "\
                        f"Use {self.bot.config['command_list']['claim']} to vote TipBot and get reward.{extra_take_text}{advert_txt}"
                    await ctx.edit_original_message(content=msg)
                    await logchanbot(
                        f"[DISCORD] User {ctx.author.name}#{ctx.author.discriminator} "\
                        f"claimed faucet {num_format_coin(amount)} {coin_name}"\
                        f" in guild {ctx.guild.name}/{ctx.guild.id}"
                    )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot("wallet /take_action " + str(traceback.format_exc()))
            else:
                try:
                    msg = f"Simulated faucet {coin_emoji} {num_format_coin(amount)} {coin_name}. "\
                        f"This is a test only. Use without **ticker** to do real faucet claim. Use {self.bot.config['command_list']['claim']} "\
                        f"to vote TipBot and get reward.{advert_txt}"
                    await ctx.edit_original_message(content=msg)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot("wallet /take_action " + str(traceback.format_exc()))
                try:
                    del self.bot.tx_in_progress[str(ctx.author.id)]
                except Exception:
                    pass
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("wallet /take_action " + str(traceback.format_exc()))
        try:
            del self.bot.tx_in_progress[str(ctx.author.id)]
        except Exception:
            pass

    @commands.guild_only()
    @commands.slash_command(
        name="daily",
        dm_permission=False,
        usage="daily <coin>",
        options=[
            Option('coin', 'coin', OptionType.string, required=False)
        ],
        description="Daily claim for a available coin."
    )
    async def daily_take(
        self,
        ctx,
        coin: str = None
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, executing {self.bot.config['command_list']['daily']} ..."
        await ctx.response.send_message(msg)
        await self.bot_log()

        cmd_name = ctx.application_command.qualified_name
        command_mention = f"__/{cmd_name}__"
        try:
            if self.bot.config['discord']['enable_command_mention'] == 1:
                cmd = self.bot.get_global_command_named(cmd_name.split()[0])
                command_mention = f"</{ctx.application_command.qualified_name}:{cmd.id}>"
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/daily", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        # check if user create account less than 3 days
        try:
            # x 5 account_age_to_claim
            account_created = ctx.author.created_at
            remaining_time = int(account_created.timestamp()) + self.bot.config['faucet']['account_age_to_claim']*5
            if (datetime.utcnow().astimezone() - account_created).total_seconds() <= self.bot.config['faucet']['account_age_to_claim']*5:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. "\
                    f"Wait till <t:{str(remaining_time)}:f> before using {self.bot.config['command_list']['hourly']} or {command_mention}."
                await ctx.edit_original_message(content=msg)
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)

        if str(ctx.author.id) in self.bot.tx_in_progress and \
            int(time.time()) - self.bot.tx_in_progress[str(ctx.author.id)] < 150 \
                and ctx.author.id != self.bot.config['discord']['owner_id']:
            msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress."
            await ctx.edit_original_message(content=msg)
            return

        try:
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
            if serverinfo and serverinfo['botchan'] and ctx.channel.id != int(serverinfo['botchan']):
                try:
                    botChan = self.bot.get_channel(int(serverinfo['botchan']))
                    if botChan is not None:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, {botChan.mention} was assigned for the bot channel!'
                        await ctx.edit_original_message(content=msg)
                        return
                except Exception:
                    traceback.print_exc(file=sys.stdout)

            # check if account locked
            account_lock = await alert_if_userlock(ctx, 'daily')
            if account_lock:
                msg = f"{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}"
                await ctx.edit_original_message(content=msg)
                return
            # end of check if account locked

            advert_txt = ""
            # if advert enable
            if self.bot.config['discord']['enable_advert'] == 1 and len(self.bot.advert_list) > 0:
                try:
                    random.shuffle(self.bot.advert_list)
                    advert_txt = "\n__**Random Message:**__ [{}](<{}>)```{}```".format(
                        self.bot.advert_list[0]['title'], self.bot.advert_list[0]['link'], self.bot.advert_list[0]['content']
                    )
                    await self.utils.advert_impress(
                        self.bot.advert_list[0]['id'], str(ctx.author.id),
                        str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM"
                    )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            # end advert

            if 'daily' not in self.bot.other_data:
                self.bot.other_data['daily'] = {}
                for each_coin in self.bot.coin_name_list:
                    is_daily = getattr(getattr(self.bot.coin_list, each_coin), "enable_daily")
                    amount_daily = getattr(getattr(self.bot.coin_list, each_coin), "daily_amount")
                    if is_daily == 1 and amount_daily > 0:
                        self.bot.other_data['daily'][each_coin] = amount_daily
            if coin is None:
                # show summary
                embed = disnake.Embed(
                    title=f'TipBot Daily Claim',
                    description=f"You shall only claim one token per 24h. Decide which one you want to do __/daily <token name>__.",
                    timestamp=datetime.fromtimestamp(int(time.time()))
                )
                list_daily = []
                for k, v in self.bot.other_data['daily'].items():
                    coin_name = k
                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                    amount_str = str(v).rstrip('0').rstrip('.') if '.' in str(v) else v
                    coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                    list_daily.append("{} {} {}".format(
                        coin_emoji, amount_str, coin_name
                    ))
                embed.add_field(
                    name="Daily {} Coins".format(len(list_daily)),
                    value="{}".format("\n".join(list_daily)),
                    inline=False
                )

                # if advert enable
                if self.bot.config['discord']['enable_advert'] == 1 and len(self.bot.advert_list) > 0:
                    try:
                        random.shuffle(self.bot.advert_list)
                        embed.add_field(
                            name="{}".format(self.bot.advert_list[0]['title']),
                            value="```{}```👉 <{}>".format(self.bot.advert_list[0]['content'], self.bot.advert_list[0]['link']),
                            inline=False
                        )
                        await self.utils.advert_impress(
                            self.bot.advert_list[0]['id'], str(ctx.author.id),
                            str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM"
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                # end advert

                embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
                embed.set_thumbnail(url=self.bot.user.display_avatar)
                await ctx.edit_original_message(content=None, embed=embed)
            else:
                # check user claim:
                try:
                    claim_interval = 24 # hours
                    check_claimed = await store.sql_faucet_checkuser(str(ctx.author.id), SERVER_BOT, "DAILY")
                    if check_claimed is not None:
                        if int(time.time()) - check_claimed['claimed_at'] <= claim_interval * 3600:
                            user_claims = await store.sql_faucet_count_user(str(ctx.author.id))
                            number_user_claimed = '{:,.0f}'.format(user_claims)
                            time_waiting = disnake.utils.format_dt(
                                claim_interval * 3600 + check_claimed['claimed_at'],
                                style='R'
                            )
                            last_claim_at = disnake.utils.format_dt(
                                check_claimed['claimed_at'],
                                style='f'
                            )
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you claimed {self.bot.config['command_list']['daily']} on {last_claim_at}. "\
                                f"Waiting time {time_waiting} for next {command_mention}. "\
                                f"You have claimed: **{number_user_claimed}** time(s). Tip me if you want to feed these faucets."\
                                f"{advert_txt}"
                            await ctx.edit_original_message(content=msg)
                            return
                except Exception:
                    traceback.print_exc(file=sys.stdout)

                coin_name = coin.upper()
                if coin_name not in self.bot.other_data['daily']:
                    await ctx.edit_original_message(
                        content=f"{EMOJI_RED_NO} {ctx.author.mention}, __{coin_name}__ is not available for {command_mention}."
                    )
                    return
                else:
                    amount = self.bot.other_data['daily'][coin_name]
                    net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                    type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                    deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                    price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                    contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                    coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                    get_deposit = await self.sql_get_userwallet(
                        str(self.bot.user.id), coin_name, net_name, type_coin, SERVER_BOT, 0
                    )
                    if get_deposit is None:
                        get_deposit = await self.sql_register_user(
                            str(self.bot.user.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 0
                        )

                    wallet_address = get_deposit['balance_wallet_address']
                    if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        wallet_address = get_deposit['paymentid']
                    elif type_coin in ["XRP"]:
                        wallet_address = get_deposit['destination_tag']

                    height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                    userdata_balance = await self.wallet_api.user_balance(
                        str(self.bot.user.id), coin_name, wallet_address, type_coin, height,
                        deposit_confirm_depth, SERVER_BOT
                    )
                    actual_balance = float(userdata_balance['adjust'])
                    if actual_balance < amount:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, Bot's balance is empyt! Try with other coin!"
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        equivalent_usd = ""
                        amount_in_usd = 0.0
                        per_unit = None
                        if price_with:
                            per_unit = await self.utils.get_coin_price(coin_name, price_with)
                            if per_unit and per_unit['price'] and per_unit['price'] > 0:
                                per_unit = per_unit['price']
                        if per_unit and per_unit > 0:
                            amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                            if amount_in_usd > 0.0001:
                                equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)
                        self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())
                        await store.sql_user_balance_mv_single(
                            str(self.bot.user.id), str(ctx.author.id),
                            str(ctx.guild.id), str(ctx.channel.id), amount, coin_name,
                            "DAILY", coin_decimal, SERVER_BOT, contract,
                            amount_in_usd, None
                        )
                        try:
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                        except Exception:
                            pass
                        try:
                            await store.sql_faucet_add(
                                str(ctx.author.id), str(ctx.guild.id), coin_name, amount,
                                coin_decimal, SERVER_BOT, "DAILY"
                            )
                            msg = f"{EMOJI_MONEYFACE} {ctx.author.mention}, you got {command_mention} "\
                                f"{coin_emoji} {num_format_coin(amount)} {coin_name}. "\
                                f"Use {self.bot.config['command_list']['claim']} to vote TipBot and get reward; "\
                                f"and more with {self.bot.config['command_list']['hourly']}.{advert_txt}"
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f"[DISCORD] User {ctx.author.name}#{ctx.author.discriminator} "\
                                f"claimed /daily {num_format_coin(amount)} {coin_name}"\
                                f" in guild {ctx.guild.name}/{ctx.guild.id}"
                            )
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot("wallet /daily " + str(traceback.format_exc()))
        except disnake.errors.Forbidden:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, I have no permission."
            await ctx.edit_original_message(content=msg)
            return
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @daily_take.autocomplete("coin")
    async def daily_coin_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.other_data['daily'].keys() if string in name.lower()][:10]

    @commands.guild_only()
    @commands.slash_command(
        name="hourly",
        dm_permission=False,
        usage="hourly <coin>",
        options=[
            Option('coin', 'coin', OptionType.string, required=False)
        ],
        description="Claim every hour for a available coin."
    )
    async def hourly_take(
        self,
        ctx,
        coin: str = None
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, executing {self.bot.config['command_list']['hourly']} ..."
        await ctx.response.send_message(msg)
        await self.bot_log()

        cmd_name = ctx.application_command.qualified_name
        command_mention = f"__/{cmd_name}__"
        try:
            if self.bot.config['discord']['enable_command_mention'] == 1:
                cmd = self.bot.get_global_command_named(cmd_name.split()[0])
                command_mention = f"</{ctx.application_command.qualified_name}:{cmd.id}>"
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/hourly", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        # check if user create account less than 3 days
        try:
            account_created = ctx.author.created_at
            remaining_time = int(account_created.timestamp()) + self.bot.config['faucet']['account_age_to_claim']
            if (datetime.utcnow().astimezone() - account_created).total_seconds() <= self.bot.config['faucet']['account_age_to_claim']:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. "\
                    f"Wait till <t:{str(remaining_time)}:f> before using {command_mention} or {self.bot.config['command_list']['daily']}."
                await ctx.edit_original_message(content=msg)
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)

        if str(ctx.author.id) in self.bot.tx_in_progress and \
            int(time.time()) - self.bot.tx_in_progress[str(ctx.author.id)] < 150 \
                and ctx.author.id != self.bot.config['discord']['owner_id']:
            msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress."
            await ctx.edit_original_message(content=msg)
            return

        try:
            serverinfo = self.bot.other_data['guild_list'].get(str(ctx.guild.id))
            if serverinfo and serverinfo['botchan'] and ctx.channel.id != int(serverinfo['botchan']):
                try:
                    botChan = self.bot.get_channel(int(serverinfo['botchan']))
                    if botChan is not None:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, {botChan.mention} was assigned for the bot channel!'
                        await ctx.edit_original_message(content=msg)
                        return
                except Exception:
                    traceback.print_exc(file=sys.stdout)

            # check if account locked
            account_lock = await alert_if_userlock(ctx, 'hourly')
            if account_lock:
                msg = f"{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}"
                await ctx.edit_original_message(content=msg)
                return
            # end of check if account locked

            advert_txt = ""
            # if advert enable
            if self.bot.config['discord']['enable_advert'] == 1 and len(self.bot.advert_list) > 0:
                try:
                    random.shuffle(self.bot.advert_list)
                    advert_txt = "\n__**Random Message:**__ [{}](<{}>)```{}```".format(
                        self.bot.advert_list[0]['title'], self.bot.advert_list[0]['link'], self.bot.advert_list[0]['content']
                    )
                    await self.utils.advert_impress(
                        self.bot.advert_list[0]['id'], str(ctx.author.id),
                        str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM"
                    )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            # end advert

            if 'hourly' not in self.bot.other_data:
                self.bot.other_data['hourly'] = {}
                for each_coin in self.bot.coin_name_list:
                    is_hourly = getattr(getattr(self.bot.coin_list, each_coin), "enable_hourly")
                    amount_hourly = getattr(getattr(self.bot.coin_list, each_coin), "hourly_amount")
                    if is_hourly == 1 and amount_hourly > 0:
                        self.bot.other_data['hourly'][each_coin] = amount_hourly
            if coin is None:
                # show summary
                embed = disnake.Embed(
                    title=f'TipBot Hourly Claim',
                    description=f"You shall only claim one token every 1 hour. Decide which one you want to do __/hourly <token name>__.",
                    timestamp=datetime.fromtimestamp(int(time.time()))
                )
                list_hourly = []
                for k, v in self.bot.other_data['hourly'].items():
                    coin_name = k
                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                    amount_str = str(v).rstrip('0').rstrip('.') if '.' in str(v) else v
                    coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                    list_hourly.append("{} {} {}".format(
                        coin_emoji, amount_str, coin_name
                    ))
                embed.add_field(
                    name="Hourly {} Coins".format(len(list_hourly)),
                    value="{}".format("\n".join(list_hourly)),
                    inline=False
                )

                # if advert enable
                if self.bot.config['discord']['enable_advert'] == 1 and len(self.bot.advert_list) > 0:
                    try:
                        random.shuffle(self.bot.advert_list)
                        embed.add_field(
                            name="{}".format(self.bot.advert_list[0]['title']),
                            value="```{}```👉 <{}>".format(self.bot.advert_list[0]['content'], self.bot.advert_list[0]['link']),
                            inline=False
                        )
                        await self.utils.advert_impress(
                            self.bot.advert_list[0]['id'], str(ctx.author.id),
                            str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM"
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                # end advert

                embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
                embed.set_thumbnail(url=self.bot.user.display_avatar)
                await ctx.edit_original_message(content=None, embed=embed)
            else:
                # check user claim:
                try:
                    claim_interval = 1 # hours
                    check_claimed = await store.sql_faucet_checkuser(str(ctx.author.id), SERVER_BOT, "HOURLY")
                    if check_claimed is not None:
                        if int(time.time()) - check_claimed['claimed_at'] <= claim_interval * 3600:
                            user_claims = await store.sql_faucet_count_user(str(ctx.author.id))
                            number_user_claimed = '{:,.0f}'.format(user_claims)
                            time_waiting = disnake.utils.format_dt(
                                claim_interval * 3600 + check_claimed['claimed_at'],
                                style='R'
                            )
                            last_claim_at = disnake.utils.format_dt(
                                check_claimed['claimed_at'],
                                style='f'
                            )
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you claimed {self.bot.config['command_list']['hourly']} on {last_claim_at}. "\
                                f"Waiting time {time_waiting} for next {command_mention}. "\
                                f"You have claimed: **{number_user_claimed}** time(s). Tip me if you want to feed these faucets."\
                                f"{advert_txt}"
                            await ctx.edit_original_message(content=msg)
                            return
                except Exception:
                    traceback.print_exc(file=sys.stdout)

                coin_name = coin.upper()
                if coin_name not in self.bot.other_data['hourly']:
                    await ctx.edit_original_message(
                        content=f"{EMOJI_RED_NO} {ctx.author.mention}, __{coin_name}__ is not available for {command_mention}."
                    )
                    return
                else:
                    amount = self.bot.other_data['hourly'][coin_name]
                    net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                    type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                    deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                    coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                    price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                    contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                    coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                    get_deposit = await self.sql_get_userwallet(
                        str(self.bot.user.id), coin_name, net_name, type_coin, SERVER_BOT, 0
                    )
                    if get_deposit is None:
                        get_deposit = await self.sql_register_user(
                            str(self.bot.user.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 0
                        )

                    wallet_address = get_deposit['balance_wallet_address']
                    if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                        wallet_address = get_deposit['paymentid']
                    elif type_coin in ["XRP"]:
                        wallet_address = get_deposit['destination_tag']

                    height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                    userdata_balance = await self.wallet_api.user_balance(
                        str(self.bot.user.id), coin_name, wallet_address, type_coin, height,
                        deposit_confirm_depth, SERVER_BOT
                    )
                    actual_balance = float(userdata_balance['adjust'])
                    if actual_balance < amount:
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, Bot's balance is empyt! Try with other coin!"
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        equivalent_usd = ""
                        amount_in_usd = 0.0
                        per_unit = None
                        if price_with:
                            per_unit = await self.utils.get_coin_price(coin_name, price_with)
                            if per_unit and per_unit['price'] and per_unit['price'] > 0:
                                per_unit = per_unit['price']
                        if per_unit and per_unit > 0:
                            amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                            if amount_in_usd > 0.0001:
                                equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)
                        self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())
                        await store.sql_user_balance_mv_single(
                            str(self.bot.user.id), str(ctx.author.id),
                            str(ctx.guild.id), str(ctx.channel.id), amount, coin_name,
                            "HOURLY", coin_decimal, SERVER_BOT, contract,
                            amount_in_usd, None
                        )
                        try:
                            del self.bot.tx_in_progress[str(ctx.author.id)]
                        except Exception:
                            pass
                        try:
                            await store.sql_faucet_add(
                                str(ctx.author.id), str(ctx.guild.id), coin_name, amount,
                                coin_decimal, SERVER_BOT, "HOURLY"
                            )
                            msg = f"{EMOJI_MONEYFACE} {ctx.author.mention}, you got {command_mention} "\
                                f"{coin_emoji} {num_format_coin(amount)} {coin_name}. "\
                                f"Use {self.bot.config['command_list']['claim']} to vote TipBot and get reward; "\
                                f"and more with {self.bot.config['command_list']['daily']}.{advert_txt}"
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f"[DISCORD] User {ctx.author.name}#{ctx.author.discriminator} "\
                                f"claimed /hourly {num_format_coin(amount)} {coin_name}"\
                                f" in guild {ctx.guild.name}/{ctx.guild.id}"
                            )
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot("wallet /hourly " + str(traceback.format_exc()))
        except disnake.errors.Forbidden:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, I have no permission."
            await ctx.edit_original_message(content=msg)
            return
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @hourly_take.autocomplete("coin")
    async def hourly_coin_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.other_data['hourly'].keys() if string in name.lower()][:10]

    @commands.guild_only()
    @commands.slash_command(
        dm_permission=False,
        usage="take <info>",
        options=[
            Option('info', 'info', OptionType.string, required=False)
        ],
        description="Claim a random coin faucet."
    )
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
        price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing donation check...'
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/donate", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        get_deposit = await self.wallet_api.sql_get_userwallet(
            str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0
        )
        if get_deposit is None:
            get_deposit = await self.wallet_api.sql_register_user(
                str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 0
            )

        wallet_address = get_deposit['balance_wallet_address']
        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
            wallet_address = get_deposit['paymentid']
        elif type_coin in ["XRP"]:
            wallet_address = get_deposit['destination_tag']
                    
        # Check if tx in progress
        if str(ctx.author.id) in self.bot.tx_in_progress and \
            int(time.time()) - self.bot.tx_in_progress[str(ctx.author.id)] < 150 \
                and ctx.author.id != self.bot.config['discord']['owner_id']:
            msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress."
            await ctx.edit_original_message(content=msg)
            return

        height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
        # check if amount is all
        all_amount = False
        if not amount.isdigit() and amount.upper() == "ALL":
            all_amount = True
            userdata_balance = await self.wallet_api.user_balance(
                str(ctx.author.id), coin_name, wallet_address, type_coin, height,
                deposit_confirm_depth, SERVER_BOT
            )
            amount = float(userdata_balance['adjust'])
        # If $ is in amount, let's convert to coin/token
        elif "$" in amount[-1] or "$" in amount[0]:  # last is $
            # Check if conversion is allowed for this coin.
            amount = amount.replace(",", "").replace("$", "")
            if price_with is None:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this __{coin_name}__."
                await ctx.edit_original_message(content=msg)
                return
            else:
                per_unit = await self.utils.get_coin_price(coin_name, price_with)
                if per_unit and per_unit['price'] and per_unit['price'] > 0:
                    per_unit = per_unit['price']
                    amount = float(Decimal(amount) / Decimal(per_unit))
                else:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. Try with different method."
                    await ctx.edit_original_message(content=msg)
                    return
        else:
            amount = amount.replace(",", "")
            amount = text_to_num(amount)
            if amount is None:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
                await ctx.edit_original_message(content=msg)
                return
        # end of check if amount is all
        userdata_balance = await self.wallet_api.user_balance(
            str(ctx.author.id), coin_name, wallet_address, type_coin, height,
            deposit_confirm_depth, SERVER_BOT
        )
        actual_balance = float(userdata_balance['adjust'])
        donate_factor = 10
        if amount <= 0 or actual_balance <=0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}.'
            await ctx.edit_original_message(content=msg)
            return
        elif amount > max_tip * donate_factor or amount < min_tip / donate_factor:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, transactions (donate) cannot be bigger than "\
                f"**{num_format_coin(max_tip * donate_factor)} {token_display}** "\
                f"or smaller than **{num_format_coin(min_tip / donate_factor)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return
        elif amount > actual_balance:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to donate "\
                f"**{num_format_coin(amount)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return

        # check queue
        if str(ctx.author.id) in self.bot.tx_in_progress and \
            int(time.time()) - self.bot.tx_in_progress[str(ctx.author.id)] < 150 \
                and ctx.author.id != self.bot.config['discord']['owner_id']:
            msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress."
            await ctx.edit_original_message(content=msg)
            return

        equivalent_usd = ""
        amount_in_usd = 0.0
        if price_with:
            per_unit = await self.utils.get_coin_price(coin_name, price_with)
            if per_unit and per_unit['price'] and per_unit['price'] > 0:
                per_unit = per_unit['price']
                amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                if amount_in_usd >= 0.01:
                    equivalent_usd = " ~ {:,.2f}$".format(amount_in_usd)
                elif amount_in_usd >= 0.0001:
                    equivalent_usd = " ~ {:,.4f}$".format(amount_in_usd)

        if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
            self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())
            try:
                donate = await store.sql_user_balance_mv_single(
                    str(ctx.author.id), str(self.donate_to), "DONATE",
                    "DONATE", amount, coin_name, "DONATE", coin_decimal,
                    SERVER_BOT, contract, amount_in_usd, None
                )
                if donate:
                    msg = f"{ctx.author.mention}, thank you for donate "\
                        f"{num_format_coin(amount)} "\
                        f"{token_display}{equivalent_usd}."
                    await ctx.edit_original_message(content=msg)
                    await logchanbot(
                        f"[DONATE] User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                        f"donated {num_format_coin(amount)} "\
                        f"{token_display}{equivalent_usd}."
                    )
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot("wallet /donate " + str(traceback.format_exc()))
            try:
                del self.bot.tx_in_progress[str(ctx.author.id)]
            except Exception:
                pass
        else:
            msg = f'{EMOJI_ERROR} {ctx.author.mention} {EMOJI_HOURGLASS_NOT_DONE}, you have another tx in progress.'
            await ctx.edit_original_message(content=msg)
    # End of Donate

    # Swap Tokens
    @commands.slash_command(description="Swap supporting tokens")
    async def swaptokens(self, ctx):
        msg = f"{EMOJI_INFORMATION}, this command is disable now. Please use __/cexswap__."
        await ctx.response.send_message(msg)
        return

    @swaptokens.sub_command(
        usage="swaptokens disclaimer",
        description="Show /swaptokens's disclaimer."
    )
    async def disclaimer(
        self,
        ctx
    ):
        msg = f"{EMOJI_INFORMATION} Disclaimer: No warranty or guarantee is provided, expressed, or implied "\
            "when using this bot and any funds lost, mis-used or stolen in using this bot. "\
            "TipBot and its dev does not affiliate with the swapped tokens."
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
                # embed.add_field(name="{}->{} | Ratio: {:,.2f} : {:,.2f}".format(
                # each['from_token'], each['to_token'], each['amount_from'], each['amount_to']), value="```Max. allowed 24h: {} {}\n
                # Max. allowed 24h/user: {} {}\nFee: {:,.0f}{}```".format(
                # each['max_swap_per_24h_from_token_total'], each['from_token'], 
                # each['max_swap_per_24h_from_token_user'], each['from_token'], each['fee_percent_from'], "%"), inline=False)
                embed.add_field(
                    name="{}->{} | Ratio: {:,.2f} : {:,.2f}".format(
                        each['from_token'], each['to_token'], each['amount_from'], each['amount_to']
                    ),
                    value="```Fee: {:,.0f}{}```".format(each['fee_percent_from'], "%"),
                    inline=False
                )
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

        from_coin = from_token.upper()
        to_coin = to_token.upper()
        # Check if available
        check_list = await self.swaptoken_check(from_coin, to_coin)
        if check_list is None:
            msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, {from_coin} to {to_coin} is not available. "\
                f"Please check with `/swaptokens lists`.'
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
                net_name = getattr(getattr(self.bot.coin_list, from_coin), "net_name")
                type_coin = getattr(getattr(self.bot.coin_list, from_coin), "type")
                get_deposit = await self.wallet_api.sql_get_userwallet(
                    str(ctx.author.id), from_coin, net_name, type_coin, SERVER_BOT, 0
                )
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, from_coin), "deposit_confirm_depth")
                min_tip = getattr(getattr(self.bot.coin_list, from_coin), "real_min_tip")
                max_tip = getattr(getattr(self.bot.coin_list, from_coin), "real_max_tip")
                coin_decimal = getattr(getattr(self.bot.coin_list, from_coin), "decimal")
                token_display = getattr(getattr(self.bot.coin_list, from_coin), "display_name")
                amount = float(amount)
                if amount < min_tip or amount > max_tip:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, amount must be between {min_tip} {from_coin} and {max_tip} {from_coin}."
                    await ctx.edit_original_message(content=msg)
                    return
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(
                        str(ctx.author.id), from_coin, net_name, type_coin, SERVER_BOT, 0,
                        1 if check_list['is_guild'] == 1 else 0
                    )
                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']
                elif type_coin in ["XRP"]:
                    wallet_address = get_deposit['destination_tag']
                height = await self.wallet_api.get_block_height(type_coin, from_coin, net_name)
                userdata_balance = await store.sql_user_balance_single(
                    str(ctx.author.id), from_coin, wallet_address,
                    type_coin, height, deposit_confirm_depth, SERVER_BOT
                )
                actual_balance = float(userdata_balance['adjust'])
                if actual_balance < amount:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to /swaptokens "\
                        f"**{num_format_coin(amount)} {token_display}**. "\
                        f"Having {num_format_coin(actual_balance)} {token_display}."
                    await ctx.edit_original_message(content=msg)
                    return

                # Check to_coin balance creditor
                amount_swapped = amount * check_list['amount_to'] / check_list['amount_from']
                net_name = getattr(getattr(self.bot.coin_list, to_coin), "net_name")
                type_coin = getattr(getattr(self.bot.coin_list, to_coin), "type")
                get_deposit = await self.wallet_api.sql_get_userwallet(creditor, to_coin, net_name, type_coin,
                                                                       SERVER_BOT, 0)
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, to_coin), "deposit_confirm_depth")
                coin_decimal = getattr(getattr(self.bot.coin_list, to_coin), "decimal")
                token_display = getattr(getattr(self.bot.coin_list, to_coin), "display_name")
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(
                        creditor, to_coin, net_name, type_coin, SERVER_BOT, 0,
                        1 if check_list['is_guild'] == 1 else 0
                    )
                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']
                elif type_coin in ["XRP"]:
                    wallet_address = get_deposit['destination_tag']
                height = await self.wallet_api.get_block_height(type_coin, to_coin, net_name)
                creditor_balance = await store.sql_user_balance_single(
                    creditor, to_coin, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT
                )
                actual_balance = float(creditor_balance['adjust'])
                if actual_balance < amount_swapped:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, creditor has insufficient balance to /swaptokens "\
                        f"**{num_format_coin(amount_swapped)} {token_display}**. "\
                        f"Remaining only {num_format_coin(actual_balance)} {token_display}."
                    await ctx.edit_original_message(content=msg)
                    try:
                        msg_log = f"[SWAPTOKENS] - User {ctx.author.name}#{ctx.author.discriminator} / "\
                            f"{ctx.author.id}  /swaptokens failed! Shortage of creditor's balance. "\
                            f"Remaining only {num_format_coin(actual_balance)} "\
                            f"{token_display}."
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
                    fee_taker = str(self.bot.config['discord']['owner_id'])
                    # from_coin
                    contract_from = getattr(getattr(self.bot.coin_list, from_coin), "contract")
                    token_decimal_from = getattr(getattr(self.bot.coin_list, from_coin), "decimal")
                    guild_id = str(ctx.guild.id) if hasattr(ctx.guild, "id") else "DM"
                    channel_id = str(ctx.channel.id) if hasattr(ctx.guild, "id") else "DM"
                    tiptype = "SWAPTOKENS"
                    user_server = SERVER_BOT
                    real_amount_usd = 0.0  # Leave it 0
                    extra_message = None
                    amount_after_fee = amount * (1 - check_list['fee_percent_from'] / 100)
                    fee_from = amount * check_list['fee_percent_from'] / 100

                    # Deduct amount from
                    data_rows.append((
                        from_coin, contract_from, str(ctx.author.id), creditor, guild_id, channel_id,
                        amount_after_fee, token_decimal_from, tiptype, currentTs, user_server,
                        real_amount_usd, extra_message, str(ctx.author.id), from_coin, user_server,
                        -amount_after_fee, currentTs, creditor, from_coin, user_server, amount_after_fee,
                        currentTs,)
                    )
                    # Fee to fee_taker
                    if fee_from > 0:
                        data_rows.append((
                            from_coin, contract_from, str(ctx.author.id), fee_taker, guild_id, channel_id,
                            fee_from, token_decimal_from, tiptype, currentTs, user_server,
                            real_amount_usd, extra_message, str(ctx.author.id), from_coin, user_server,
                            -fee_from, currentTs, fee_taker, from_coin, user_server, fee_from,
                            currentTs,)
                        )

                    # Deduct from creditor
                    contract_to = getattr(getattr(self.bot.coin_list, to_coin), "contract")
                    token_decimal_to = getattr(getattr(self.bot.coin_list, to_coin), "decimal")
                    amount_after_fee = amount_swapped * (1 - check_list['fee_percent_to'] / 100)
                    fee_to = amount_swapped * check_list['fee_percent_to'] / 100
                    data_rows.append((
                        to_coin, contract_to, creditor, str(ctx.author.id), guild_id, channel_id,
                        amount_after_fee, token_decimal_to, tiptype, currentTs, user_server,
                        real_amount_usd, extra_message, creditor, to_coin, user_server, -amount_after_fee,
                        currentTs, str(ctx.author.id), to_coin, user_server, amount_after_fee,
                        currentTs,)
                    )
                    # Fee to fee_taker
                    if fee_to > 0:
                        data_rows.append((
                            to_coin, contract_to, creditor, fee_taker, guild_id, channel_id, fee_to,
                            token_decimal_to, tiptype, currentTs, user_server, real_amount_usd,
                            extra_message, creditor, to_coin, user_server, -fee_to, currentTs, fee_taker,
                            to_coin, user_server, fee_to, currentTs,)
                        )

                    swap = await self.swaptoken_purchase(data_rows)
                    if swap > 0:
                        # If there is a log channel for this.
                        try:
                            msg_log = f"[SWAPTOKENS] - User {ctx.author.name}#{ctx.author.discriminator} "\
                                f"/ {ctx.author.id}  /swaptokens successfully from "\
                                f"{num_format_coin(amount)} {from_coin} "\
                                f"to {num_format_coin(amount_swapped)} {to_coin} "\
                                f"[Fee: {num_format_coin(fee_to)} {to_coin}].\n"\
                                f"CREDITOR ID: {creditor} NEW BALANCE: "\
                                f"{num_format_coin(float(creditor_balance['adjust']) - amount_swapped)}"\
                                f" {to_coin}."
                            await logchanbot(msg_log)
                            if check_list['channel_log'] and check_list['channel_log'].isdigit():
                                self.logchan_swap = self.bot.get_channel(int(check_list['channel_log']))
                                await self.logchan_swap.send(content=msg_log)
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, successfully /swaptokens from "\
                            f"**{num_format_coin(amount)} {from_coin}** to "\
                            f"**{num_format_coin(amount_swapped)}** _{to_coin} "\
                            f"[Fee: {num_format_coin(fee_to)} {to_coin}]_. Thanks!"
                        await ctx.edit_original_message(content=msg)
                    else:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, internal error, please report.'
                        await ctx.edit_original_message(content=msg)
            except Exception:
                traceback.print_exc(file=sys.stdout)
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, internal error, please report.'
                await ctx.edit_original_message(content=msg)

    # End of Swap Tokens

    # Wrap/Unwrap
    @commands.slash_command(
        name='wrap',
        usage='wrap',
        options=[
            Option('from_amount', 'from_amount', OptionType.string, required=True),
            Option('from_token', 'from_token', OptionType.string, required=True),
            Option('to_token', 'to_token', OptionType.string, required=True)
        ],
        description="Wrap/Unwrap between supported token/coin."
    )
    async def wrap(
        self,
        ctx,
        from_amount: str,
        from_token: str,
        to_token: str

    ):
        from_coin = from_token.upper()
        to_coin = to_token.upper()
        PAIR_NAME = from_coin + "-" + to_coin

        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, checking /wrap ...'
        await ctx.response.send_message(msg)

        cmd_name = ctx.application_command.qualified_name
        command_mention = f"__/{cmd_name}__"
        try:
            if self.bot.config['discord']['enable_command_mention'] == 1:
                cmd = self.bot.get_global_command_named(cmd_name.split()[0])
                command_mention = f"</{ctx.application_command.qualified_name}:{cmd.id}>"
        except Exception:
            traceback.print_exc(file=sys.stdout)
    
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/wrap", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        if self.bot.config['wrap']['enable'] != 1:
            await ctx.edit_original_message(
                content=f"{EMOJI_RED_NO} {ctx.author.mention}, this feature is currently not enabled. Try again later!")
            return

        if PAIR_NAME not in self.swap_pair:
            msg = f'{EMOJI_RED_NO}, {ctx.author.mention} __{PAIR_NAME}__ is not available.'
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
                net_name = getattr(getattr(self.bot.coin_list, from_coin), "net_name")
                type_coin = getattr(getattr(self.bot.coin_list, from_coin), "type")
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, from_coin), "deposit_confirm_depth")
                coin_decimal = getattr(getattr(self.bot.coin_list, from_coin), "decimal")
                min_tip = getattr(getattr(self.bot.coin_list, from_coin), "real_min_tip")
                max_tip = getattr(getattr(self.bot.coin_list, from_coin), "real_max_tip")
                token_display = getattr(getattr(self.bot.coin_list, from_coin), "display_name")
                contract = getattr(getattr(self.bot.coin_list, from_coin), "contract")
                to_contract = getattr(getattr(self.bot.coin_list, to_coin), "contract")
                to_coin_decimal = getattr(getattr(self.bot.coin_list, to_coin), "decimal")
                get_deposit = await self.wallet_api.sql_get_userwallet(
                    str(ctx.author.id), from_coin, net_name, type_coin, SERVER_BOT, 0
                )
                if get_deposit is None:
                    get_deposit = await self.wallet_api.sql_register_user(
                        str(ctx.author.id), from_coin, net_name, type_coin, SERVER_BOT, 0, 0
                    )

                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']
                elif type_coin in ["XRP"]:
                    wallet_address = get_deposit['destination_tag']

                # Check if tx in progress
                if str(ctx.author.id) in self.bot.tx_in_progress and \
                    int(time.time()) - self.bot.tx_in_progress[str(ctx.author.id)] < 150 \
                        and ctx.author.id != self.bot.config['discord']['owner_id']:
                    msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress."
                    await ctx.edit_original_message(content=msg)
                    return

                height = await self.wallet_api.get_block_height(type_coin, from_coin, net_name)
                userdata_balance = await self.wallet_api.user_balance(
                    str(ctx.author.id), from_coin, wallet_address, type_coin,
                    height, deposit_confirm_depth, SERVER_BOT
                )
                actual_balance = float(userdata_balance['adjust'])

                if amount > max_tip or amount < min_tip:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, swap cannot be bigger than "\
                        f"**{num_format_coin(max_tip)} {token_display}** "\
                        f"or smaller than **{num_format_coin(min_tip)} {token_display}**."
                    await ctx.edit_original_message(content=msg)
                    return
                elif amount > actual_balance:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to swap "\
                        f"**{num_format_coin(amount)} {token_display}**."
                    await ctx.edit_original_message(content=msg)
                    return

                try:
                    # test get main balance of to_coin
                    balance = await self.wallet_api.get_coin_balance(to_coin)
                    if balance / 5 < to_amount:  # We allow 20% to swap
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention} insufficient liquidity to swap "\
                            f"**{num_format_coin(amount)} {token_display}** "\
                            f"to {to_coin}. Try lower the amount of __{from_coin}__."
                        await ctx.edit_original_message(content=msg)
                        await logchanbot(
                            f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} wanted to "\
                            f"swap from __{num_format_coin(amount)} {from_coin}__ "\
                            f"to __{num_format_coin(to_amount)} {to_coin}__ "\
                            f"but shortage of liquidity. "\
                            f"Having only __{num_format_coin(balance)} {to_coin}__."
                        )
                        return
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot("wallet /swap " + str(traceback.format_exc()))

                if str(ctx.author.id) not in self.bot.tx_in_progress or ctx.author.id == self.bot.config['discord']['owner_id']:
                    self.bot.tx_in_progress[str(ctx.author.id)] = int(time.time())
                    try:
                        swap = await self.swap_coin(
                            str(ctx.author.id), from_coin, amount, contract, coin_decimal,
                            to_coin, to_amount, to_contract, to_coin_decimal, SERVER_BOT
                        )
                        if swap:
                            msg = f"{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention}, {command_mention} from "\
                                f"__{num_format_coin(amount)} "\
                                f"{from_coin}__ to __{num_format_coin(to_amount)} {to_coin}__."
                            await ctx.edit_original_message(content=msg)
                            await logchanbot(
                                f"User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                                f"{command_mention} from __{num_format_coin(amount)} {from_coin}__ "\
                                f"to __{num_format_coin(to_amount)} {to_coin}__."
                            )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot("wallet /wrap " + str(traceback.format_exc()))
                    try:
                        del self.bot.tx_in_progress[str(ctx.author.id)]
                    except Exception:
                        pass
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
        description="Get list recent withdraw(s)"
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
            msg = f"{ctx.author.mention}, **{coin_name}** does not exist with us."
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
            get_recent = await self.utils.recent_tips(str(ctx.author.id), SERVER_BOT, coin_name, coin_family, "withdraw", 10)
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
                    elif coin_family == "COSMOS":
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
                    list_tx.append("{} {} {}\n{}\n".format(
                        num_format_coin(amount),
                        coin_name,
                        disnake.utils.format_dt(each['date'], style='R'), tx)
                    )
                list_tx_str = "\n".join(list_tx)
                await ctx.edit_original_message(content=f"{ctx.author.mention}, last withdraw of {coin_name}:\n{list_tx_str}")
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @recent.sub_command(
        name="cexswaplp",
        usage="recent cexswaplp <token/coin>", 
        description="Get list recent reward from CEXSwap LP"
    )
    async def recent_cexswap_lp(
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

        await ctx.response.send_message(f"{EMOJI_HOURGLASS_NOT_DONE}, checking recent CEXSwapLP..", ephemeral=True)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/recent deposit", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        coin_family = getattr(getattr(self.bot.coin_list, coin_name), "type")
        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        try:
            get_recent = await self.utils.recent_tips(str(ctx.author.id), SERVER_BOT, coin_name, coin_family, "cexswaplp", 20)
            if len(get_recent) == 0:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, you do not CEXSwap reward for {coin_name}.")
            else:
                list_tx = []
                for each in get_recent:
                    list_tx.append("From `{}` {}, amount {} {}".format(
                        each['pairs'],
                        disnake.utils.format_dt(each['date'], style='R'),
                        num_format_coin(each['distributed_amount']), each['got_ticker']
                        )
                    )
                list_tx_str = "\n".join(list_tx)
                await ctx.edit_original_message(content=f"{ctx.author.mention}, last receive of {coin_name}:\n{list_tx_str}")
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @recent.sub_command(
        name="deposit",
        usage="recent deposit <token/coin>", 
        description="Get list recent deposit(s)"
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
            get_recent = await self.utils.recent_tips(str(ctx.author.id), SERVER_BOT, coin_name, coin_family, "deposit", 10)
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
                    elif coin_family == "COSMOS":
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
                    list_tx.append("{} {} {}\n{}\n".format(num_format_coin(amount), coin_name, disnake.utils.format_dt(time_insert, style='R'), tx))
                list_tx_str = "\n".join(list_tx)
                await ctx.edit_original_message(content=f"{ctx.author.mention}, last deposit of {coin_name}:\n{list_tx_str}")
        except Exception:
            traceback.print_exc(file=sys.stdout)


    @recent.sub_command(
        name="receive",
        usage="recent receive <token/coin>", 
        description="Get list recent receipt(s)"
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
            get_recent = await self.utils.recent_tips(str(ctx.author.id), SERVER_BOT, coin_name, coin_family, "receive", 20)
            if len(get_recent) == 0:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, you do not received any {coin_name}.")
            else:
                list_tx = []
                for each in get_recent:
                    list_tx.append("From `{}` {}, amount {} {} - {}".format(each['from_userid'], disnake.utils.format_dt(each['date'], style='R'), num_format_coin(each['real_amount']), each['token_name'], each['type']))
                list_tx_str = "\n".join(list_tx)
                await ctx.edit_original_message(content=f"{ctx.author.mention}, last receive of {coin_name}:\n{list_tx_str}")
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @recent.sub_command(
        name="expense",
        usage="recent expense <token/coin>", 
        description="Get list recent expense"
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
            get_recent = await self.utils.recent_tips(str(ctx.author.id), SERVER_BOT, coin_name, coin_family, "expense", 20)
            if len(get_recent) == 0:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, you do not received any {coin_name}.")
            else:
                list_tx = []
                for each in get_recent:
                    list_tx.append(
                        "To `{}` {}, amount {} {} - {}".format(
                            each['to_userid'],
                            disnake.utils.format_dt(each['date'], style='R'),
                            num_format_coin(each['real_amount']),
                            each['token_name'],
                            each['type']
                        )
                    )
                list_tx_str = "\n".join(list_tx)
                await ctx.edit_original_message(content=f"{ctx.author.mention}, last expense of {coin_name}:\n{list_tx_str}")
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.Cog.listener()
    async def on_ready(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            # nano, banano
            if not self.update_balance_nano.is_running():
                self.update_balance_nano.start()
            if not self.notify_balance_nano.is_running():
                self.notify_balance_nano.start()
            # TRTL-API
            if not self.notify_balance_bcn.is_running():
                self.notify_balance_bcn.start()
            if not self.update_balance_trtl_api.is_running():
                self.update_balance_trtl_api.start()
            # TRTL-SERVICE
            if not self.update_balance_trtl_service.is_running():
                self.update_balance_trtl_service.start()
            # XMR
            if not self.update_balance_xmr.is_running():
                self.update_balance_xmr.start()
            # BTC
            if not self.notify_balance_btc.is_running():
                self.notify_balance_btc.start()
            if not self.update_balance_btc.is_running():
                self.update_balance_btc.start()

            # NEO
            if not self.update_balance_neo.is_running():
                self.update_balance_neo.start()
            if not self.notify_new_confirmed_neo.is_running():
                self.notify_new_confirmed_neo.start()

            # CHIA
            if not self.notify_balance_chia.is_running():
                self.notify_balance_chia.start()
            if not self.update_balance_chia.is_running():
                self.update_balance_chia.start()
            # ERC-20
            if not self.update_balance_erc20.is_running():
                self.update_balance_erc20.start()
            if not self.unlocked_move_pending_erc20.is_running():
                self.unlocked_move_pending_erc20.start()
            if not self.update_balance_address_history_erc20.is_running():
                self.update_balance_address_history_erc20.start()
            if not self.notify_new_confirmed_spendable_erc20.is_running():
                self.notify_new_confirmed_spendable_erc20.start()

            # TRC-20
            if not self.update_balance_trc20.is_running():
                self.update_balance_trc20.start()
            if not self.unlocked_move_pending_trc20.is_running():
                self.unlocked_move_pending_trc20.start()
            if not self.notify_new_confirmed_spendable_trc20.is_running():
                self.notify_new_confirmed_spendable_trc20.start()

            # HNT
            if not self.update_balance_hnt.is_running():
                self.update_balance_hnt.start()
            if not self.notify_new_confirmed_hnt.is_running():
                self.notify_new_confirmed_hnt.start()

            # XLM
            if not self.update_balance_xlm.is_running():
                self.update_balance_xlm.start()
            if not self.notify_new_confirmed_xlm.is_running():
                self.notify_new_confirmed_xlm.start()

            # COSMOS
            if not self.update_balance_cosmos.is_running():
                self.update_balance_cosmos.start()
            if not self.notify_new_confirmed_cosmos.is_running():
                self.notify_new_confirmed_cosmos.start()

            # VITE
            if not self.update_balance_vite.is_running():
                self.update_balance_vite.start()
            if not self.notify_new_confirmed_vite.is_running():
                self.notify_new_confirmed_vite.start()

            # XTZ
            if not self.update_balance_tezos.is_running():
                self.update_balance_tezos.start()
            if not self.check_confirming_tezos.is_running():
                self.check_confirming_tezos.start()
            if not self.notify_new_confirmed_tezos.is_running():
                self.notify_new_confirmed_tezos.start()

            # ZIL
            if not self.update_balance_zil.is_running():
                self.update_balance_zil.start()
            if not self.check_confirming_zil.is_running():
                self.check_confirming_zil.start()
            if not self.notify_new_confirmed_zil.is_running():
                self.notify_new_confirmed_zil.start()

            # VET
            if not self.update_balance_vet.is_running():
                self.update_balance_vet.start()
            if not self.check_confirming_vet.is_running():
                self.check_confirming_vet.start()
            if not self.notify_new_confirmed_vet.is_running():
                self.notify_new_confirmed_vet.start()

            # NEAR
            if not self.update_balance_near.is_running():
                self.update_balance_near.start()
            if not self.check_confirming_near.is_running():
                self.check_confirming_near.start()
            if not self.notify_new_confirmed_near.is_running():
                self.notify_new_confirmed_near.start()

            # XRP
            if not self.update_balance_xrp.is_running():
                self.update_balance_xrp.start()
            if not self.notify_new_confirmed_xrp.is_running():
                self.notify_new_confirmed_xrp.start()

            # update ada wallet sync status
            if not self.update_ada_wallets_sync.is_running():
                self.update_ada_wallets_sync.start()
            if not self.notify_new_confirmed_ada.is_running():
                self.notify_new_confirmed_ada.start()

            # update sol wallet sync status
            if not self.update_sol_wallets_sync.is_running():
                self.update_sol_wallets_sync.start()
            if not self.unlocked_move_pending_sol.is_running():
                self.unlocked_move_pending_sol.start()

            # monitoring reward for RT
            if not self.monitoring_rt_rewards.is_running():
                self.monitoring_rt_rewards.start()

            # Monitoring Tweet command
            if not self.monitoring_tweet_command.is_running():
                self.monitoring_tweet_command.start()
            if not self.monitoring_tweet_mentioned_command.is_running():
                self.monitoring_tweet_mentioned_command.start()

    async def cog_load(self):
        if self.bot.config['discord']['enable_bg_tasks'] == 1:
            # nano, banano
            if not self.update_balance_nano.is_running():
                self.update_balance_nano.start()
            if not self.notify_balance_nano.is_running():
                self.notify_balance_nano.start()
            # TRTL-API, updated multiple tasks
            if not self.notify_balance_bcn.is_running():
                self.notify_balance_bcn.start()
            if not self.update_balance_trtl_api.is_running():
                self.update_balance_trtl_api.start()
            # TRTL-SERVICE, updated multiple tasks
            if not self.update_balance_trtl_service.is_running():
                self.update_balance_trtl_service.start()
            # XMR, updated multiple tasks
            if not self.update_balance_xmr.is_running():
                self.update_balance_xmr.start()
            # BTC, updated multiple tasks
            if not self.notify_balance_btc.is_running():
                self.notify_balance_btc.start()
            if not self.update_balance_btc.is_running():
                self.update_balance_btc.start()

            # NEO
            if not self.update_balance_neo.is_running():
                self.update_balance_neo.start()
            if not self.notify_new_confirmed_neo.is_running():
                self.notify_new_confirmed_neo.start()

            # CHIA, updated multiple tasks
            if not self.notify_balance_chia.is_running():
                self.notify_balance_chia.start()
            if not self.update_balance_chia.is_running():
                self.update_balance_chia.start()
            # ERC-20, multiple tasks for main token
            if not self.update_balance_erc20.is_running():
                self.update_balance_erc20.start()
            # updated multiple tasks
            if not self.unlocked_move_pending_erc20.is_running():
                self.unlocked_move_pending_erc20.start()
            if not self.update_balance_address_history_erc20.is_running():
                self.update_balance_address_history_erc20.start()
            if not self.notify_new_confirmed_spendable_erc20.is_running():
                self.notify_new_confirmed_spendable_erc20.start()

            # TRC-20
            if not self.update_balance_trc20.is_running():
                self.update_balance_trc20.start()
            if not self.unlocked_move_pending_trc20.is_running():
                self.unlocked_move_pending_trc20.start()
            if not self.notify_new_confirmed_spendable_trc20.is_running():
                self.notify_new_confirmed_spendable_trc20.start()

            # HNT
            if not self.update_balance_hnt.is_running():
                self.update_balance_hnt.start()
            if not self.notify_new_confirmed_hnt.is_running():
                self.notify_new_confirmed_hnt.start()

            # XLM
            if not self.update_balance_xlm.is_running():
                self.update_balance_xlm.start()
            if not self.notify_new_confirmed_xlm.is_running():
                self.notify_new_confirmed_xlm.start()

            # COSMOS
            if not self.update_balance_cosmos.is_running():
                self.update_balance_cosmos.start()
            if not self.notify_new_confirmed_cosmos.is_running():
                self.notify_new_confirmed_cosmos.start()

            # VITE
            if not self.update_balance_vite.is_running():
                self.update_balance_vite.start()
            if not self.notify_new_confirmed_vite.is_running():
                self.notify_new_confirmed_vite.start()

            # XTZ
            if not self.update_balance_tezos.is_running():
                self.update_balance_tezos.start()
            if not self.check_confirming_tezos.is_running():
                self.check_confirming_tezos.start()
            if not self.notify_new_confirmed_tezos.is_running():
                self.notify_new_confirmed_tezos.start()

            # ZIL
            if not self.update_balance_zil.is_running():
                self.update_balance_zil.start()
            if not self.check_confirming_zil.is_running():
                self.check_confirming_zil.start()
            if not self.notify_new_confirmed_zil.is_running():
                self.notify_new_confirmed_zil.start()

            # VET
            if not self.update_balance_vet.is_running():
                self.update_balance_vet.start()
            if not self.check_confirming_vet.is_running():
                self.check_confirming_vet.start()
            if not self.notify_new_confirmed_vet.is_running():
                self.notify_new_confirmed_vet.start()

            # NEAR
            if not self.update_balance_near.is_running():
                self.update_balance_near.start()
            if not self.check_confirming_near.is_running():
                self.check_confirming_near.start()
            if not self.notify_new_confirmed_near.is_running():
                self.notify_new_confirmed_near.start()

            # XRP
            if not self.update_balance_xrp.is_running():
                self.update_balance_xrp.start()
            if not self.notify_new_confirmed_xrp.is_running():
                self.notify_new_confirmed_xrp.start()

            # update ada wallet sync status
            if not self.update_ada_wallets_sync.is_running():
                self.update_ada_wallets_sync.start()
            if not self.notify_new_confirmed_ada.is_running():
                self.notify_new_confirmed_ada.start()

            # update sol wallet sync status
            if not self.update_sol_wallets_sync.is_running():
                self.update_sol_wallets_sync.start()
            if not self.unlocked_move_pending_sol.is_running():
                self.unlocked_move_pending_sol.start()

            # monitoring reward for RT
            if not self.monitoring_rt_rewards.is_running():
                self.monitoring_rt_rewards.start()

            # Monitoring Tweet command
            if not self.monitoring_tweet_command.is_running():
                self.monitoring_tweet_command.start()
            if not self.monitoring_tweet_mentioned_command.is_running():
                self.monitoring_tweet_mentioned_command.start()

    def cog_unload(self):
        # Ensure the task is stopped when the cog is unloaded.
        # nano, banano
        self.update_balance_nano.cancel()
        self.notify_balance_nano.cancel()

        # TRTL-API
        self.notify_balance_bcn.cancel()
        self.update_balance_trtl_api.cancel()

        # TRTL-SERVICE
        self.update_balance_trtl_service.cancel()
        # XMR
        self.update_balance_xmr.cancel()
        # BTC
        self.notify_balance_btc.cancel()
        self.update_balance_btc.cancel()

        # NEO
        self.update_balance_neo.cancel()
        self.notify_new_confirmed_neo.cancel()

        # CHIA
        self.notify_balance_chia.cancel()
        self.update_balance_chia.cancel()

        # ERC-20
        self.update_balance_erc20.cancel()
        self.unlocked_move_pending_erc20.cancel()
        self.update_balance_address_history_erc20.cancel()
        self.notify_new_confirmed_spendable_erc20.cancel()

        # TRC-20
        self.update_balance_trc20.cancel()
        self.unlocked_move_pending_trc20.cancel()
        self.notify_new_confirmed_spendable_trc20.cancel()

        # HNT
        self.update_balance_hnt.cancel()
        self.notify_new_confirmed_hnt.cancel()

        # XLM
        self.update_balance_xlm.cancel()
        self.notify_new_confirmed_xlm.cancel()

        # COSMOS
        self.update_balance_cosmos.cancel()
        self.notify_new_confirmed_cosmos.cancel()

        # VITE
        self.update_balance_vite.cancel()
        self.notify_new_confirmed_vite.cancel()

        # XTZ
        self.update_balance_tezos.cancel()
        self.check_confirming_tezos.cancel()
        self.notify_new_confirmed_tezos.cancel()

        # ZIL
        self.update_balance_zil.cancel()
        self.check_confirming_zil.cancel()
        self.notify_new_confirmed_zil.cancel()

        # VET
        self.update_balance_vet.cancel()
        self.check_confirming_vet.cancel()
        self.notify_new_confirmed_vet.cancel()

        # NEAR
        self.update_balance_near.cancel()
        self.check_confirming_near.cancel()
        self.notify_new_confirmed_near.cancel()

        # XRP
        self.update_balance_xrp.cancel()
        self.notify_new_confirmed_xrp.cancel()

        # update ada wallet sync status
        self.update_ada_wallets_sync.cancel()
        self.notify_new_confirmed_ada.cancel()

        # update sol wallet sync status
        self.update_sol_wallets_sync.cancel()
        self.unlocked_move_pending_sol.cancel()

        # monitoring reward for RT
        self.monitoring_rt_rewards.cancel()

        # Monitoring Tweet command
        self.monitoring_tweet_command.cancel()
        self.monitoring_tweet_mentioned_command.cancel()

def setup(bot):
    bot.add_cog(Wallet(bot))
    bot.add_cog(WalletAPI(bot))
