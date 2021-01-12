from config import config
from wallet import *
import store, daemonrpc_client, addressvalidation, walletapi
import sys, traceback
# redis
import redis, json
import uuid, time
import asyncio


from generic_xmr.address_msr import address_msr as address_msr
from generic_xmr.address_xmr import address_xmr as address_xmr
from generic_xmr.address_upx import address_upx as address_upx
from generic_xmr.address_wow import address_wow as address_wow
from generic_xmr.address_xol import address_xol as address_xol

# eth erc
from eth_account import Account
from decimal import Decimal

import math, random
# ascii table
from terminaltables import AsciiTable

# reddit
import praw

reddit = praw.Reddit(user_agent=config.reddit.user_agent,
                     client_id=config.reddit.client_id,
                     client_secret=config.reddit.client_secret,
                     username=config.reddit.username,
                     password=config.reddit.password)

# db = dataset.connect('sqlite:///reddit.db')
# get a reference to the table 'user'
#comment_table = db['comments']
#user_table = db['user']
#message_table = db['message']

ENABLE_COIN = config.reddit.Enabe_Reddit_Coin.split(",")
ENABLE_COIN_DOGE = config.telegram.Enable_Coin_Doge.split(",")
ENABLE_COIN_ERC = config.reddit.Enable_Coin_ERC.split(",")
ENABLE_COIN_NANO = config.telegram.Enable_Coin_Nano.split(",")
SERVER = 'REDDIT'
WITHDRAW_IN_PROCESS = []
redis_pool = None
redis_conn = None
redis_expired = 120

def init():
    global redis_pool
    print("PID %d: initializing redis pool..." % os.getpid())
    redis_pool = redis.ConnectionPool(host='localhost', port=6379, decode_responses=True, db=8)


def openRedis():
    global redis_pool, redis_conn
    if redis_conn is None:
        try:
            redis_conn = redis.Redis(connection_pool=redis_pool)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


# Create ETH
def create_eth_wallet():
    Account.enable_unaudited_hdwallet_features()
    acct, mnemonic = Account.create_with_mnemonic()
    return {'address': acct.address, 'seed': mnemonic, 'private_key': acct.privateKey.hex()}


async def logchanbot(content: str):
    filterword = config.discord.logfilterword.split(",")
    for each in filterword:
        content = content.replace(each, config.discord.filteredwith)
    if len(content) > 1500: content = content[:1500]
    try:
        webhook = DiscordWebhook(url=config.discord.botdbghook, content=f'```{discord.utils.escape_markdown(content)}```')
        webhook.execute()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

async def run_inbox_monitor():
    while True:
        try:
            for item in reddit.inbox.stream():
                #print(vars(item))
                #print("============")
                #print(item)
                check_msg = await store.reddit_check_exist(item.name)
                if check_msg:
                    continue
                else:
                    #print('Found Author %s' % item.author.name)
                    commands = item.body.split(" ")
                    #print(commands[0])
                    if commands[0].lower() == '!help':
                        reply_message = 'Help\n\n Reply with command in the body of text:\n\n  '
                        reply_message += '!balance - get your balance\n\n  '
                        reply_message += '!tip <amount> <coin name> <user>\n\n  '
                        reply_message += '!deposit <coin name>\n\n  '
                        reply_message += '!send <amount> <address> [coin name]\n\n  '
                        reply_message += '!tipto <amount> <coinname> <user@discord|telegram>\n\n  '
                        item.reply(reply_message)

                    elif commands[0].lower() == '!deposit':
                        if commands[1]:
                            COIN_NAME = commands[1].upper()
                            if COIN_NAME not in ENABLE_COIN:
                                reply_message = f'{COIN_NAME} is not supported. Please choose one of {config.reddit.Enabe_Reddit_Coin}'
                            else:
                                user_addr = await store.sql_get_userwallet(item.author.name, COIN_NAME, SERVER)
                                if user_addr is None:
                                    if COIN_NAME in ENABLE_COIN_ERC:
                                        w = create_eth_wallet()
                                        userregister = await store.sql_register_user(item.author.name, COIN_NAME, SERVER, 0, w)
                                    else:
                                        userregister = await store.sql_register_user(item.author.name, COIN_NAME, SERVER, 0)
                                    user_addr = await store.sql_get_userwallet(item.author.name, COIN_NAME, SERVER)
                                reply_message = f'DEPOSIT {COIN_NAME} INFO:\n\n  '
                                reply_message += 'Deposit:\n\n' + user_addr['balance_wallet_address']            
                        else:
                            reply_message = 'Please use !deposit <coin name>'
                        item.reply(reply_message)

                    elif commands[0].lower() == '!balance' or commands[0].lower() == '!bal':
                        message_text = ""
                        coin_str = "\n"
                        for COIN_ITEM in [coinItem.upper() for coinItem in ENABLE_COIN]:
                            wallet = await store.sql_get_userwallet(item.author.name, COIN_ITEM, SERVER)
                            if wallet is None:
                                if COIN_ITEM in ENABLE_COIN_ERC:
                                    w = create_eth_wallet()
                                    userregister = await store.sql_register_user(item.author.name, COIN_ITEM, SERVER, 0, w)
                                else:
                                    userregister = await store.sql_register_user(item.author.name, COIN_ITEM, SERVER,0)
                                wallet = await store.sql_get_userwallet(item.author.name, COIN_ITEM, SERVER)
                            if COIN_ITEM in ENABLE_COIN_ERC:
                                coin_family = "ERC-20"
                            else:
                                coin_family = getattr(getattr(config,"daemon"+COIN_ITEM),"coin_family","TRTL")
                            if wallet is None:
                                await logchanbot(f'[Reddit] A user call !balance {COIN_ITEM} failed')
                                balance_actual = "N/A"
                            else:
                                userdata_balance = await store.sql_user_balance(item.author.name, COIN_ITEM, SERVER)
                                xfer_in = 0
                                if COIN_ITEM not in ENABLE_COIN_ERC:
                                    xfer_in = await store.sql_user_balance_get_xfer_in(item.author.name, COIN_ITEM, SERVER)
                                if COIN_ITEM in ENABLE_COIN_DOGE+ENABLE_COIN_ERC:
                                    actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
                                elif COIN_ITEM in ENABLE_COIN_NANO:
                                    actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                                    actual_balance = round(actual_balance / get_decimal(COIN_ITEM), 6) * get_decimal(COIN_ITEM)
                                else:
                                    actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                                balance_actual = num_format_coin(actual_balance, COIN_ITEM)
                                # Negative check
                                try:
                                    if actual_balance < 0:
                                        msg_negative = '[Reddit] Negative balance detected:\nUser: '+item.author.name+'\nCoin: '+COIN_ITEM+'\nAtomic Balance: '+str(actual_balance)
                                        await logchanbot(msg_negative)
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                            coin_str += COIN_ITEM + ": " + balance_actual + COIN_ITEM + "\n\n"
                        message_text = 'YOUR BALANCE SHEET:\n\n' + coin_str
                        item.reply(message_text)
                        add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                        continue
                    elif commands[0].lower() == '!send':
                        # !send amount coin address
                        try:
                            if len(commands) < 4:
                                reply_message = "Please use !send amount coin address"
                                item.reply(reply_message)
                                add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                                continue
                            else:
                                amount = commands[1].replace(",", "")
                                wallet_address = commands[3]
                                if wallet_address.isalnum() == False:
                                    wallet_address = None
                                try:
                                    amount = Decimal(amount)
                                except ValueError:
                                    reply_message = "Invalid amount."
                                    amount = None
                                    item.reply(reply_message)
                                    add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                                    continue
                                COIN_NAME = commands[2].upper()
                                if COIN_NAME not in ENABLE_COIN:
                                    reply_message = f'{COIN_NAME} is not supported. Please choose one of {config.reddit.Enabe_Reddit_Coin}'
                                    COIN_NAME = None
                                else:
                                    if is_maintenance_coin(COIN_NAME) or not is_coin_txable(COIN_NAME):
                                        reply_message = f"{COIN_NAME} under maintenance or disable."
                                        item.reply(reply_message)
                                        add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                                        continue
                                    else:
                                        if amount is None or wallet_address is None or COIN_NAME is None:
                                            reply_message = "Please use !send amount coin address"
                                            item.reply(reply_message)
                                            add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                                            continue
                                        else:
                                            # add redis action
                                            random_string = str(uuid.uuid4())
                                            await add_tx_action_redis(json.dumps([random_string, "SEND", item.author.name, item.author.name, float("%.3f" % time.time()), item.body, SERVER, "START"]), False)
                                            check_in = await store.coin_check_balance_address_in_users(wallet_address, COIN_NAME)
                                            if check_in:
                                                reply_message = "You can not send to this address:\n\n" + wallet_address
                                                item.reply(reply_message)
                                                add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                                                continue
                                            else:
                                                COIN_NAME_CHECK = get_cn_coin_from_address(wallet_address)
                                                if not COIN_NAME_CHECK:
                                                    reply_message = "Unknown coin name:\n\n" + wallet_address
                                                    item.reply(reply_message)
                                                    add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                                                    continue
                                                elif COIN_NAME_CHECK != COIN_NAME:
                                                    reply_message = "Error getting address and coin name from:\n\n" + wallet_address
                                                    item.reply(reply_message)
                                                    add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                                                    continue
                                                else:
                                                    # get coin family
                                                    if COIN_NAME in ENABLE_COIN_ERC:
                                                        coin_family = "ERC-20"
                                                    else:
                                                        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
                                                    if coin_family == "TRTL" or coin_family == "DOGE":
                                                        addressLength = get_addrlen(COIN_NAME)
                                                        IntaddressLength = 0
                                                        paymentid = None
                                                        CoinAddress = None

                                                        userdata_balance = await store.sql_user_balance(item.author.name, COIN_NAME, SERVER)
                                                        xfer_in = 0
                                                        if COIN_NAME not in ENABLE_COIN_ERC:
                                                            xfer_in = await store.sql_user_balance_get_xfer_in(item.author.name, COIN_NAME, SERVER)
                                                        if COIN_NAME in ENABLE_COIN_DOGE+ENABLE_COIN_ERC:
                                                            actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
                                                        elif COIN_NAME in ENABLE_COIN_NANO:
                                                            actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                                                            actual_balance = round(actual_balance / get_decimal(COIN_NAME), 6) * get_decimal(COIN_NAME)
                                                        else:
                                                            actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                                                        # Negative check
                                                        try:
                                                            if actual_balance < 0:
                                                                msg_negative = '[Reddit] Negative balance detected:\nUser: '+item.author.name+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                                                                await logchanbot(msg_negative)
                                                        except Exception as e:
                                                            await logchanbot(traceback.format_exc())

                                                        if COIN_NAME in ENABLE_COIN_ERC:
                                                            token_info = await store.get_token_info(COIN_NAME)
                                                            confim_depth = token_info['deposit_confirm_depth']
                                                            Min_Tip = token_info['real_min_tip']
                                                            Max_Tip = token_info['real_max_tip']
                                                            Min_Tx = token_info['real_min_tx']
                                                            Max_Tx = token_info['real_max_tx']
                                                            real_amount = amount
                                                            NetFee = token_info['real_withdraw_fee']
                                                        else:
                                                            confim_depth = get_confirm_depth(COIN_NAME)
                                                            Min_Tip = get_min_mv_amount(COIN_NAME)
                                                            Max_Tip = get_max_mv_amount(COIN_NAME)
                                                            Min_Tx = get_min_tx_amount(COIN_NAME)
                                                            Max_Tx = get_max_tx_amount(COIN_NAME)
                                                            real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
                                                            NetFee = get_reserved_fee(coin = COIN_NAME)
                                                        message_text = ''
                                                        valid_amount = True
                                                        if real_amount + NetFee > actual_balance:
                                                            message_text = '\nNot enough reserved fee / Insufficient balance to send ' + num_format_coin(real_amount, COIN_NAME) + COIN_NAME + ' to ' + wallet_address
                                                            valid_amount = False
                                                        elif real_amount > Max_Tx:
                                                            message_text = '\nTransactions cannot be bigger than ' + num_format_coin(Max_Tx, COIN_NAME) + COIN_NAME
                                                            valid_amount = False
                                                        elif real_amount < Min_Tx:
                                                            message_text = '\nTransactions cannot be smaller than ' + num_format_coin(Min_Tx, COIN_NAME) + COIN_NAME
                                                            valid_amount = False
                                                        if valid_amount == False:
                                                            item.reply(message_text)
                                                            add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                                                            continue
                                                        else:
                                                            if coin_family == "TRTL":
                                                                IntaddressLength = get_intaddrlen(COIN_NAME)
                                                                if len(wallet_address) == int(addressLength):
                                                                    valid_address = addressvalidation.validate_address_cn(wallet_address, COIN_NAME)
                                                                    if valid_address is None:
                                                                        message_text = "Invalid address:\n\n: " + wallet_address
                                                                        item.reply(message_text)
                                                                        add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                                                                        continue
                                                                    else:
                                                                        user_from = await store.sql_get_userwallet(item.author.name, COIN_NAME, SERVER)
                                                                        if user_from is None:
                                                                            userregister = await store.sql_register_user(item.author.name, COIN_NAME, SERVER, 0)
                                                                            user_from = await store.sql_get_userwallet(item.author.name, COIN_NAME, SERVER)
                                                                        CoinAddress = wallet_address
                                                                elif len(wallet_address) == int(IntaddressLength): 
                                                                    # use integrated address
                                                                    valid_address = addressvalidation.validate_integrated_cn(wallet_address, COIN_NAME)
                                                                    if valid_address == 'invalid':
                                                                        message_text = "Invalid address:\n\n" + wallet_address
                                                                        item.reply(message_text)
                                                                        add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                                                                        continue
                                                                    elif len(valid_address) == 2:
                                                                        address_paymentID = wallet_address
                                                                        CoinAddress = valid_address['address']
                                                                        paymentid = valid_address['integrated_id']

                                                                main_address = getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
                                                                if CoinAddress and CoinAddress == main_address:
                                                                    # Not allow to send to own main address
                                                                    message_text = "You can not send to:\n\n" + wallet_address
                                                                    item.reply(message_text)
                                                                    add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                                                                    continue
                                                                else:
                                                                    tip = None
                                                                    if item.author.name not in WITHDRAW_IN_PROCESS:
                                                                        WITHDRAW_IN_PROCESS.append(item.author.name)
                                                                    else:
                                                                        message_text = "You have another tx in progress."
                                                                        item.reply(message_text)
                                                                        add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                                                                        continue
                                                                    if paymentid:
                                                                        try:
                                                                            tip = await store.sql_external_cn_single_id(item.author.name, CoinAddress, real_amount, paymentid, COIN_NAME, SERVER)
                                                                            await logchanbot(f'[Reddit] User {item.author.name} send tx out {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}')
                                                                        except Exception as e:
                                                                            traceback.print_exc(file=sys.stdout)
                                                                    else:
                                                                        try:
                                                                            tip = await store.sql_external_cn_single(item.author.name, CoinAddress, real_amount, COIN_NAME, SERVER)
                                                                            await logchanbot(f'[Reddit] User {item.author.name} send tx out {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}')
                                                                        except Exception as e:
                                                                            traceback.print_exc(file=sys.stdout)
                                                                    if item.author.name in WITHDRAW_IN_PROCESS:
                                                                        await asyncio.sleep(1)
                                                                        WITHDRAW_IN_PROCESS.remove(item.author.name)
                                                                    if tip:
                                                                        tip_tx_tipper = "\nTransaction hash: {}".format(tip['transactionHash'])
                                                                        tip_tx_tipper += "\nTx Fee: {}{}".format(num_format_coin(tip['fee'], COIN_NAME), COIN_NAME)
                                                                        await add_tx_action_redis(json.dumps([random_string, "SEND", item.author.name, item.author.name, float("%.3f" % time.time()), item.body, SERVER, "COMPLETE"]), False)
                                                                        message_text = f"You have sent {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}:\n\n" + tip_tx_tipper
                                                                        item.reply(message_text)
                                                                        add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                                                                        continue
                                                                    else:
                                                                        message_text = f"Internal error for sending {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}"
                                                                        item.reply(message_text)
                                                                        add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                                                                        continue
                                                            elif coin_family == "DOGE":
                                                                valid_address = await doge_validaddress(str(wallet_address), COIN_NAME)
                                                                if 'isvalid' in valid_address:
                                                                    if str(valid_address['isvalid']) != "True":
                                                                        message_text = "Invalid address:\n\n" + wallet_address
                                                                        item.reply(message_text)
                                                                        add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                                                                        continue
                                                                    else:
                                                                        sendTx = None
                                                                        if item.author.name not in WITHDRAW_IN_PROCESS:
                                                                            WITHDRAW_IN_PROCESS.append(mitem.author.name)
                                                                        else:
                                                                            message_text = "You have another tx in progress."
                                                                            item.reply(message_text)
                                                                            add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                                                                            continue
                                                                        try:
                                                                            NetFee = get_tx_fee(coin = COIN_NAME)
                                                                            sendTx = await store.sql_external_doge_single(item.author.name, real_amount, NetFee, wallet_address, COIN_NAME, 'SEND', SERVER)
                                                                            await logchanbot(f'[Reddit] User {item.author.name} send tx out {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}')
                                                                        except Exception as e:
                                                                            traceback.print_exc(file=sys.stdout)

                                                                        if item.author.name in WITHDRAW_IN_PROCESS:
                                                                            await asyncio.sleep(1)
                                                                            WITHDRAW_IN_PROCESS.remove(item.author.name)
                                                                        if sendTx:
                                                                            tx_text = "\nTransaction hash: {}".format(sendTx)
                                                                            tx_text += "\nNetwork fee deducted from the amount."
                                                                            
                                                                            message_text = f"You have sent {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}:\n\n" + tx_text
                                                                            item.reply(message_text)
                                                                            add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                                                                            continue
                                                                        else:
                                                                            message_text = f"Internal error for sending {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}"
                                                                            item.reply(message_text)
                                                                            add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                                                                            continue
                                                    else:
                                                        message_text = "Not supported yet. Check back later."
                                                        item.reply(message_text)
                                                        add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                                                        continue
                        except Exception as e:
                            print(traceback.format_exc())
                            await logchanbot(traceback.format_exc())
                    elif commands[0].lower() == '!tipto':
                        # !tipto amount coin user@server
                        try:
                            if len(commands) < 4:
                                reply_message = "Please use !tipto amount coin user@server\n\nExample: !tipto 10,000 wrkz xxxxx@discord"
                            else:
                                amount = commands[1].replace(",", "")
                                try:
                                    amount = Decimal(amount)
                                except ValueError:
                                    reply_message = "Invalid amount."
                                    amount = None
                                COIN_NAME = commands[2].upper()
                                if COIN_NAME not in ENABLE_COIN:
                                    reply_message = f'{COIN_NAME} is not supported. Please choose one of {config.reddit.Enabe_Reddit_Coin}'
                                    COIN_NAME = None
                                else:
                                    if not is_coin_tipable(COIN_NAME) or is_maintenance_coin(COIN_NAME):
                                        reply_message = f"TIPPING is currently disable for {COIN_NAME}."
                                        item.reply(reply_message)
                                    else:
                                        to_user = commands[3]
                                        userid = None
                                        serverto = None
                                        try:
                                            userid = to_user.split("@")[0]
                                            serverto = to_user.split("@")[1].upper()
                                        except Exception as e:
                                            pass
                                        if serverto and serverto not in ["DISCORD", "TELEGRAM"]:
                                            reply_message = f'Unsupported or unknown **{serverto}**'
                                            item.reply(reply_message)
                                        if userid is None or serverto is None or amount is None or COIN_NAME is None:
                                            reply_message = "Please use !tipto amount coin user@server\n\nExample: !tipto 10,000 wrkz xxxxx@discord"
                                            item.reply(reply_message)
                                        else:
                                            to_otheruser = await store.sql_get_userwallet(userid, COIN_NAME, serverto)
                                            if to_otheruser is None:
                                                reply_message = f'User {userid} is not in our DB for {serverto}!'
                                                item.reply(reply_message)
                                            else:
                                                if COIN_NAME in ENABLE_COIN_ERC:
                                                    coin_family = "ERC-20"
                                                else:
                                                    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
                                                userdata_balance = await store.sql_user_balance(item.author.name, COIN_NAME, SERVER)
                                                xfer_in = 0
                                                if COIN_NAME not in ENABLE_COIN_ERC:
                                                    xfer_in = await store.sql_user_balance_get_xfer_in(item.author.name, COIN_NAME, SERVER)
                                                if COIN_NAME in ENABLE_COIN_DOGE+ENABLE_COIN_ERC:
                                                    actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
                                                elif COIN_NAME in ENABLE_COIN_NANO:
                                                    actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                                                    actual_balance = round(actual_balance / get_decimal(COIN_NAME), 6) * get_decimal(COIN_NAME)
                                                else:
                                                    actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                                                # Negative check
                                                try:
                                                    if actual_balance < 0:
                                                        msg_negative = '[Reddit] Negative balance detected:\nUser: '+item.author.name+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                                                        await logchanbot(msg_negative)
                                                except Exception as e:
                                                     await logchanbot(traceback.format_exc())
                                                if COIN_NAME in ENABLE_COIN_ERC:
                                                    token_info = await store.get_token_info(COIN_NAME)
                                                    confim_depth = token_info['deposit_confirm_depth']
                                                    Min_Tip = token_info['real_min_tip']
                                                    Max_Tip = token_info['real_max_tip']
                                                    Min_Tx = token_info['real_min_tx']
                                                    Max_Tx = token_info['real_max_tx']
                                                    real_amount = amount
                                                    decimal_pts = token_info['token_decimal']
                                                else:
                                                    confim_depth = get_confirm_depth(COIN_NAME)
                                                    Min_Tip = get_min_mv_amount(COIN_NAME)
                                                    Max_Tip = get_max_mv_amount(COIN_NAME)
                                                    Min_Tx = get_min_tx_amount(COIN_NAME)
                                                    Max_Tx = get_max_tx_amount(COIN_NAME)
                                                    real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
                                                    decimal_pts = int(math.log10(get_decimal(COIN_NAME)))
                                                valid_amount = True
                                                if real_amount > actual_balance:
                                                    reply_message = 'Insufficient balance to send tip of ' + num_format_coin(real_amount, COIN_NAME) + COIN_NAME + ' to ' + userid
                                                    valid_amount = False
                                                elif real_amount > Max_Tip:
                                                    reply_message = 'Transactions cannot be bigger than ' + num_format_coin(Max_Tip, COIN_NAME) + COIN_NAME
                                                    valid_amount = False
                                                elif real_amount < Min_Tip:
                                                    reply_message = 'Transactions cannot be smaller than ' + num_format_coin(Min_Tip, COIN_NAME) + COIN_NAME
                                                    valid_amount = False
                                                if valid_amount == False:
                                                    item.reply(reply_message)
                                                else:
                                                    tipto = None
                                                    try:
                                                        if item.author.name not in WITHDRAW_IN_PROCESS:
                                                            WITHDRAW_IN_PROCESS.append(item.author.name)
                                                        else:
                                                            reply_message = "You have another tx in progress."
                                                            item.reply(reply_message)
                                                        try:
                                                            tipto = await store.sql_tipto_crossing(COIN_NAME, item.author.name, item.author.name, 
                                                                                                   SERVER, userid, userid, serverto, real_amount, decimal_pts)
                                                            # Update tipstat
                                                            try:
                                                                update_tipstat = await store.sql_user_get_tipstat(item.author.name, COIN_NAME, True, SERVER)
                                                                update_tipstat = await store.sql_user_get_tipstat(userid, COIN_NAME, True, serverto)
                                                            except Exception as e:
                                                                await logchanbot(traceback.format_exc())
                                                            await logchanbot('[Reddit] {} tipto {}{} to **{}**'.format(item.author.name, num_format_coin(real_amount, COIN_NAME), COIN_NAME, to_user))
                                                        except Exception as e:
                                                            await logchanbot(traceback.format_exc())
                                                    except Exception as e:
                                                        await logchanbot(traceback.format_exc())
                                                    if tipto:
                                                        reply_message = f"You sent a new tip to {to_user}:\n\n"+ "Amount: {}{}".format(num_format_coin(real_amount, COIN_NAME), COIN_NAME)
                                                        try:
                                                            item.reply(reply_message)
                                                        except Exception as e:
                                                            await logchanbot(traceback.print_exc(file=sys.stdout))
                                                        if item.author.name in WITHDRAW_IN_PROCESS:
                                                            await asyncio.sleep(1)
                                                            WITHDRAW_IN_PROCESS.remove(item.author.name)
                        except Exception as e:
                            print(traceback.format_exc())
                            await logchanbot(traceback.format_exc())
                    elif commands[0].lower() == '!tip':
                        # !tip amount coin user
                        try:
                            if len(commands) < 4:
                                reply_message = "Please use !tip amount coin user\n\nExample: !tip 10,000 wrkz wrkzdev"
                            else:
                                amount = commands[1].replace(",", "")
                                try:
                                    amount = Decimal(amount)
                                except ValueError:
                                    reply_message = "Invalid amount."
                                    amount = None
                                COIN_NAME = commands[2].upper()
                                if COIN_NAME not in ENABLE_COIN:
                                    reply_message = f'{COIN_NAME} is not supported. Please choose one of {config.reddit.Enabe_Reddit_Coin}'
                                    COIN_NAME = None
                                else:
                                    if not is_coin_tipable(COIN_NAME) or is_maintenance_coin(COIN_NAME):
                                        reply_message = f"TIPPING is currently disable for {COIN_NAME}."
                                        item.reply(reply_message)
                                    else:
                                        to_user = commands[3]
                                        userto = await store.sql_get_userwallet(to_user, COIN_NAME, SERVER)
                                        if userto is None:
                                            reply_message = f"Can not find user {to_user} in our DB"
                                            to_user = None
                                    if amount is None or COIN_NAME is None or to_user is None:
                                        reply_message = "Please use !tip amount coin user\n\nExample: !tip 10,000 wrkz wrkzdev"
                                    else:
                                        if COIN_NAME in ENABLE_COIN_ERC:
                                            coin_family = "ERC-20"
                                        else:
                                            coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
                                        user_from = await store.sql_get_userwallet(item.author.name, COIN_NAME, SERVER)
                                        userdata_balance = await store.sql_user_balance(item.author.name, COIN_NAME, SERVER)
                                        xfer_in = 0
                                        if COIN_NAME not in ENABLE_COIN_ERC:
                                            xfer_in = await store.sql_user_balance_get_xfer_in(item.author.name, COIN_NAME, SERVER)
                                        if COIN_NAME in ENABLE_COIN_DOGE+ENABLE_COIN_ERC:
                                            actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
                                        elif COIN_NAME in ENABLE_COIN_NANO:
                                            actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                                            actual_balance = round(actual_balance / get_decimal(COIN_NAME), 6) * get_decimal(COIN_NAME)
                                        else:
                                            actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                                        # Negative check
                                        try:
                                            if actual_balance < 0:
                                                msg_negative = '[Reddit] Negative balance detected:\nUser: '+item.author.name+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                                                await logchanbot(msg_negative)
                                        except Exception as e:
                                            await logchanbot(traceback.format_exc())
                                        if COIN_NAME in ENABLE_COIN_ERC:
                                            token_info = await store.get_token_info(COIN_NAME)
                                            confim_depth = token_info['deposit_confirm_depth']
                                            Min_Tip = token_info['real_min_tip']
                                            Max_Tip = token_info['real_max_tip']
                                            Min_Tx = token_info['real_min_tx']
                                            Max_Tx = token_info['real_max_tx']
                                            real_amount = amount
                                            decimal_pts = token_info['token_decimal']
                                        else:
                                            confim_depth = get_confirm_depth(COIN_NAME)
                                            Min_Tip = get_min_mv_amount(COIN_NAME)
                                            Max_Tip = get_max_mv_amount(COIN_NAME)
                                            Min_Tx = get_min_tx_amount(COIN_NAME)
                                            Max_Tx = get_max_tx_amount(COIN_NAME)
                                            real_amount = int(Decimal(amount) * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
                                            decimal_pts = int(math.log10(get_decimal(COIN_NAME)))
                                        message_text = ''
                                        valid_amount = True
                                        if real_amount > actual_balance:
                                            message_text = 'Insufficient balance to send tip of ' + num_format_coin(real_amount, COIN_NAME) + COIN_NAME + ' to ' + to_user
                                            valid_amount = False
                                        elif real_amount > Max_Tip:
                                            message_text = 'Transactions cannot be bigger than ' + num_format_coin(Max_Tip, COIN_NAME) + COIN_NAME
                                            valid_amount = False
                                        elif real_amount < Min_Tip:
                                            message_text = 'Transactions cannot be smaller than ' + num_format_coin(Min_Tip, COIN_NAME) + COIN_NAME
                                            valid_amount = False
                                        if valid_amount == False:
                                            item.reply(reply_message)
                                        else:
                                            tip = None
                                            try:
                                                if item.author.name not in WITHDRAW_IN_PROCESS:
                                                    WITHDRAW_IN_PROCESS.append(item.author.name)
                                                else:
                                                    message_text = "You have another tx in progress."
                                                    item.reply(reply_message)
                                                try:
                                                    if coin_family in ["TRTL", "BCN"]:
                                                        tip = await store.sql_mv_cn_single(item.author.name, to_user, real_amount, 'TIP', COIN_NAME, SERVER)
                                                    elif coin_family == "XMR":
                                                        tip = await store.sql_mv_xmr_single(item.author.name, to_user, real_amount, COIN_NAME, "TIP", SERVER)
                                                    elif coin_family == "DOGE":
                                                        tip = await store.sql_mv_doge_single(item.author.name, to_user, real_amount, COIN_NAME, "TIP", SERVER)
                                                    elif coin_family == "NANO":
                                                        tip = await store.sql_mv_nano_single(item.author.name, to_user, real_amount, COIN_NAME, "TIP", SERVER)
                                                    elif coin_family == "ERC-20":
                                                        tip = await store.sql_mv_erc_single(item.author.name, to_user, real_amount, COIN_NAME, "TIP", token_info['contract'], SERVER)
                                                except Exception as e:
                                                    await logchanbot(traceback.format_exc())

                                                message_text = f"You sent a new tip to {to_user}:\n\n" + "Amount: {}{}".format(num_format_coin(real_amount, COIN_NAME), COIN_NAME)
                                                to_message_text = f"You got a new tip from /u/{item.author.name}:\n\n" + "Amount: {}{}".format(num_format_coin(real_amount, COIN_NAME), COIN_NAME)
                                                if tip:
                                                    if to_user not in ["BotTips"]:
                                                        try:
                                                            reddit.redditor(to_user).message(f"You get a new tip from /u/{item.author.name}", to_message_text)
                                                        except Exception as e:
                                                            await logchanbot(traceback.print_exc(file=sys.stdout))
                                                    if item.author.name not in ["BotTips"]:
                                                        try:
                                                            item.reply(message_text)
                                                        except Exception as e:
                                                            await logchanbot(traceback.print_exc(file=sys.stdout))
                                            except Exception as e:
                                                await logchanbot(traceback.print_exc(file=sys.stdout))
                                            if item.author.name in WITHDRAW_IN_PROCESS:
                                                await asyncio.sleep(1)
                                                WITHDRAW_IN_PROCESS.remove(item.author.name)
                        except Exception as e:
                            print(traceback.format_exc())
                            await logchanbot(traceback.format_exc())
                            reply_message = "Please use !tip amount coin user\n\nExample: !tip 10,000 wrkz wrkzdev"
                            item.reply(reply_message)
                #Add message to database
                try:
                    add_msg = await store.reddit_insert_msg(item.id, item.name, item.author.name, item.dest.name, item.body, item.body_html, int(item.created))
                except Exception as e:
                    print(traceback.format_exc())
                    await logchanbot(traceback.format_exc())
        except:
            print(traceback.format_exc())
            await logchanbot(traceback.format_exc())
            print('Lost connection - restart')
    return True


def is_maintenance_coin(coin: str):
    global redis_conn, redis_expired
    COIN_NAME = coin.upper()
    # Check if exist in redis
    try:
        openRedis()
        key = config.redis_setting.prefix_coin_setting + COIN_NAME + '_MAINT'
        if redis_conn and redis_conn.exists(key):
            return True
        else:
            return False
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def is_coin_txable(coin: str):
    global redis_conn, redis_expired
    COIN_NAME = coin.upper()
    if is_maintenance_coin(COIN_NAME):
        return False
    # Check if exist in redis
    try:
        openRedis()
        key = config.redis_setting.prefix_coin_setting + COIN_NAME + '_TX'
        if redis_conn and redis_conn.exists(key):
            return False
        else:
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def is_coin_depositable(coin: str):
    global redis_conn, redis_expired
    COIN_NAME = coin.upper()
    if is_maintenance_coin(COIN_NAME):
        return False
    # Check if exist in redis
    try:
        openRedis()
        key = config.redis_setting.prefix_coin_setting + COIN_NAME + '_DEPOSIT'
        if redis_conn and redis_conn.exists(key):
            return False
        else:
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def is_coin_tipable(coin: str):
    global redis_conn, redis_expired
    COIN_NAME = coin.upper()
    if is_maintenance_coin(COIN_NAME):
        return False
    # Check if exist in redis
    try:
        openRedis()
        key = config.redis_setting.prefix_coin_setting + COIN_NAME + '_TIP'
        if redis_conn and redis_conn.exists(key):
            return False
        else:
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def add_tx_action_redis(action: str, delete_temp: bool = False):
    try:
        openRedis()
        key = config.redis_setting.prefix_action_tx
        if redis_conn:
            if delete_temp:
                redis_conn.delete(key)
            else:
                redis_conn.lpush(key, action)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def get_cn_coin_from_address(CoinAddress: str):
    COIN_NAME = None
    if CoinAddress.startswith("Wrkz"):
        COIN_NAME = "WRKZ"
    elif CoinAddress.startswith("dg"):
        COIN_NAME = "DEGO"
    elif CoinAddress.startswith("cat1"):
        COIN_NAME = "CX"
    elif CoinAddress.startswith("XCR"):
        COIN_NAME = "NBXC"
    elif CoinAddress.startswith("ccx7"):
        COIN_NAME = "CCX"
    elif CoinAddress.startswith("fango"):
        COIN_NAME = "XFG"
    elif CoinAddress.startswith("btcm"):
        COIN_NAME = "BTCMZ"
    elif CoinAddress.startswith("PLe"):
        COIN_NAME = "PLE"
    elif CoinAddress.startswith("TRTL"):
        COIN_NAME = "TRTL"
    elif CoinAddress.startswith("bit") and (len(CoinAddress) == 98 or len(CoinAddress) == 109):
        COIN_NAME = "XTOR"
    elif (CoinAddress.startswith("4") or CoinAddress.startswith("8") or CoinAddress.startswith("5") or CoinAddress.startswith("9")) \
        and (len(CoinAddress) == 95 or len(CoinAddress) == 106):
        # XMR / MSR
        # 5, 9: MSR
        # 4, 8: XMR
        addr = None
        # Try MSR
        try:
            addr = address_msr(CoinAddress)
            COIN_NAME = "MSR"
            return COIN_NAME
        except Exception as e:
            # await logchanbot(traceback.format_exc())
            pass
        # Try XMR
        try:
            addr = address_xmr(CoinAddress)
            COIN_NAME = "XMR"
            return COIN_NAME
        except Exception as e:
            # await logchanbot(traceback.format_exc())
            pass
        # Try UPX	
        try:	
            addr = address_upx(CoinAddress)	
            COIN_NAME = "UPX"	
            return COIN_NAME	
        except Exception as e:	
            # traceback.print_exc(file=sys.stdout)	
            pass
    elif CoinAddress.startswith("L") and (len(CoinAddress) == 95 or len(CoinAddress) == 106):
        COIN_NAME = "LOKI"
    elif CoinAddress.startswith("cms") and (len(CoinAddress) == 98 or len(CoinAddress) == 109):
        COIN_NAME = "BLOG"
    elif (CoinAddress.startswith("WW") and len(CoinAddress) == 97) or \
    (CoinAddress.startswith("Wo") and len(CoinAddress) == 97) or \
    (CoinAddress.startswith("So") and len(CoinAddress) == 108):
        COIN_NAME = "WOW"
    elif (CoinAddress.startswith("Xw") and len(CoinAddress) == 97) or \
    (CoinAddress.startswith("iz") and len(CoinAddress) == 108):
        COIN_NAME = "XOL"
    elif ((CoinAddress.startswith("UPX") and len(CoinAddress) == 98) or (CoinAddress.startswith("UPi") and len(CoinAddress) == 109) or (CoinAddress.startswith("Um") and len(CoinAddress) == 97)):
        COIN_NAME = "UPX"
    elif (CoinAddress.startswith("5") or CoinAddress.startswith("9")) and (len(CoinAddress) == 95 or len(CoinAddress) == 106):
        COIN_NAME = "MSR"
    elif (CoinAddress.startswith("fh") and len(CoinAddress) == 97) or \
    (CoinAddress.startswith("fi") and len(CoinAddress) == 108) or \
    (CoinAddress.startswith("fs") and len(CoinAddress) == 97):
        COIN_NAME = "XWP"
    elif CoinAddress.startswith("D") and len(CoinAddress) == 34:
        COIN_NAME = "DOGE"
    elif (CoinAddress[0] in ["M", "L"]) and len(CoinAddress) == 34:
        COIN_NAME = "LTC"
    elif (CoinAddress[0] in ["P", "Q"]) and len(CoinAddress) == 34:
        COIN_NAME = "PGO"
    elif (CoinAddress[0] in ["3", "1"]) and len(CoinAddress) == 34:
        COIN_NAME = "BTC"
    elif (CoinAddress[0] in ["X"]) and len(CoinAddress) == 34:
        COIN_NAME = "DASH"
    elif CoinAddress.startswith("ban_") and len(CoinAddress) == 64:
        COIN_NAME = "BAN"
    elif CoinAddress.startswith("nano_") and len(CoinAddress) == 65:
        COIN_NAME = "NANO"
    print('get_cn_coin_from_address return {}: {}'.format(CoinAddress, COIN_NAME))
    return COIN_NAME


if __name__ == "__main__":
    loop = asyncio.get_event_loop()  
    loop.run_until_complete(run_inbox_monitor())  
    loop.close()  
