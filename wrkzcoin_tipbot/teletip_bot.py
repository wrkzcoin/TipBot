import logging

from aiogram import Bot, types
from aiogram.utils import exceptions, executor
from aiogram.utils.emoji import emojize
from aiogram.dispatcher import Dispatcher
from aiogram.types.message import ContentType
from aiogram.utils.markdown import text, bold, italic, code, pre, quote_html
from aiogram.utils.markdown import markdown_decoration as markdown
from aiogram.types import ParseMode, InputMediaPhoto, InputMediaVideo, ChatActions
from config import config
from wallet import *
import store, daemonrpc_client, addressvalidation, walletapi
import sys, traceback
# redis
import redis, json
import uuid

# eth erc
from eth_account import Account
from decimal import Decimal

import math, random
# ascii table
from terminaltables import AsciiTable

from aiogram.types import InlineQuery, \
    InputTextMessageContent, InlineQueryResultArticle

logging.basicConfig(format=u'%(filename)s [ LINE:%(lineno)+3s ]#%(levelname)+8s [%(asctime)s]  %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

ENABLE_COIN = config.telegram.Enabe_Telegram_Coin.split(",")
ENABLE_COIN_DOGE = config.telegram.Enable_Coin_Doge.split(",")
ENABLE_COIN_ERC = config.telegram.Enable_Coin_ERC.split(",")
ENABLE_COIN_NANO = config.telegram.Enable_Coin_Nano.split(",")
ENABLE_XMR = config.telegram.Enable_Coin_XMR.split(",")
HIGH_DECIMAL_COIN = config.ManyDecimalCoin.split(",")

# faucet enabled coin. The faucet balance is taken from TipBot's own balance
FAUCET_COINS = config.telegram.Enable_Faucet_Coin.split(",")

# DOGE will divide by 10 after random
FAUCET_MINMAX = {
    "WRKZ": [config.Faucet_min_max.wrkz_min, config.Faucet_min_max.wrkz_max],
    "DEGO": [config.Faucet_min_max.dego_min, config.Faucet_min_max.dego_max],
    "TRTL": [config.Faucet_min_max.trtl_min, config.Faucet_min_max.trtl_max],
    "DOGE": [config.Faucet_min_max.doge_min, config.Faucet_min_max.doge_max],
    "PGO": [config.Faucet_min_max.pgo_min, config.Faucet_min_max.pgo_max],
    "BTCMZ": [config.Faucet_min_max.btcmz_min, config.Faucet_min_max.btcmz_max],
    "NBXC": [config.Faucet_min_max.nbxc_min, config.Faucet_min_max.nbxc_max],
    "XFG": [config.Faucet_min_max.xfg_min, config.Faucet_min_max.xfg_max],
    "WOW": [config.Faucet_min_max.wow_min, config.Faucet_min_max.wow_max],
    "BAN": [config.Faucet_min_max.ban_min, config.Faucet_min_max.ban_max],
    "NANO": [config.Faucet_min_max.nano_min, config.Faucet_min_max.nano_max]
}

WITHDRAW_IN_PROCESS = []
redis_pool = None
redis_conn = None
redis_expired = 120

API_TOKEN = config.telegram.Token

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

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
    try:
        webhook = DiscordWebhook(url=config.discord.botdbghook, content=f'```{discord.utils.escape_markdown(content)}```')
        webhook.execute()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


@dp.message_handler(commands='start')
async def start_cmd_handler(message: types.Message):
    keyboard_markup = types.ReplyKeyboardMarkup(row_width=3)
    # default row_width is 3, so here we can omit it actually
    # kept for clearness
    await message.reply("Hello, Welcome to TipBot by WrkzCoin team!\nAvailable command: /balance, /register, /send, /tip, /deposit, /coin, /donate, /about", 
                        reply_markup=keyboard_markup)


@dp.message_handler(commands='deposit')
async def start_cmd_handler(message: types.Message):
    content = ' '.join(message.text.split())
    args = content.split(" ")
    if message.chat.type != "private":
        return
    if message.from_user.username is None:
        reply_text = "I can not get your username."
        await message.reply(reply_text)
        return
    supported_coins = ", ".join(ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_COIN_ERC+ENABLE_COIN_NANO+ENABLE_XMR)
    if len(args) == 1:
        message_text = text(markdown.bold(f"Invalid COIN NAME after /deposit.\nPlease use any of this:") + markdown.pre(supported_coins))
        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
        return
    else:
        # /deposit WRKZ
        COIN_NAME = args[1].upper()
        if COIN_NAME not in ENABLE_COIN + ENABLE_COIN_DOGE + ENABLE_COIN_ERC + ENABLE_COIN_NANO + ENABLE_XMR:
            message_text = text(markdown.bold(f"Invalid COIN NAME after /deposit.\nPlease use any of this:") + markdown.pre(supported_coins))
            await message.reply(message_text,
                                parse_mode=ParseMode.MARKDOWN)
            return
        else:
            if not is_coin_depositable(COIN_NAME):
                message_text = text(bold(f"DEPOSITING is currently disable for {COIN_NAME}."))
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
                return

            user_addr = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')
            if user_addr is None:
                if COIN_NAME in ENABLE_COIN_ERC:
                    w = create_eth_wallet()
                    userregister = await store.sql_register_user(message.from_user.username, COIN_NAME, 'TELEGRAM', message.chat.id, w)
                else:
                    userregister = await store.sql_register_user(message.from_user.username, COIN_NAME, 'TELEGRAM', message.chat.id)
                user_addr = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')

            if user_addr is None:
                await logchanbot(f'[Telegram] A user call /deposit {COIN_NAME} failed.')
            else:
                message_text = text(markdown.bold(f"DEPOSIT {COIN_NAME} INFO:") + \
                                    markdown.pre("\nDeposit: " + user_addr['balance_wallet_address'] + \
                                                 "\n\nRegistered: " + (user_addr['user_wallet_address'] if ('user_wallet_address' in user_addr) and user_addr['user_wallet_address'] else "NONE, Please register.")))
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
            return


@dp.message_handler(commands='coin')
async def start_cmd_handler(message: types.Message):
    content = ' '.join(message.text.split())
    args = content.split(" ")
    supported_coins = ", ".join(ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_COIN_ERC+ENABLE_COIN_NANO+ENABLE_XMR)
    if len(args) == 1:
        deposit_cmd_text = text(bold(f"Invalid COIN NAME after /coin") + markdown.pre(f"\nPlease use /coin COIN NAME. Supported COIN_NAME: {supported_coins}"))
        await message.reply(deposit_cmd_text, parse_mode=ParseMode.MARKDOWN)
        return
    else:
        # /coin WRKZ
        COIN_NAME = args[1].upper()
        if COIN_NAME not in ENABLE_COIN + ENABLE_COIN_DOGE + ENABLE_COIN_ERC + ENABLE_COIN_NANO + ENABLE_XMR:
            message_text = text(bold(f"Invalid COIN NAME after /coin") + markdown.pre(f"\nPlease use /coin COIN NAME. Supported COIN_NAME: {supported_coins}"))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
            return
        else:
            response_text = "\n"
            try:
                openRedis()
                if redis_conn and redis_conn.exists(f'{config.redis_setting.prefix_daemon_height}{COIN_NAME}'):
                    height = int(redis_conn.get(f'{config.redis_setting.prefix_daemon_height}{COIN_NAME}'))
                    response_text = "\nHeight: {:,.0f}".format(height) + "\n"
                if COIN_NAME in ENABLE_COIN_ERC:
                    token_info = await store.get_token_info(COIN_NAME)
                    confim_depth = token_info['deposit_confirm_depth']
                    Min_Tip = token_info['real_min_tip']
                    Max_Tip = token_info['real_max_tip']
                    Min_Tx = token_info['real_min_tx']
                    Max_Tx = token_info['real_max_tx']
                else:
                    confim_depth = get_confirm_depth(COIN_NAME)
                    Min_Tip = get_min_mv_amount(COIN_NAME)
                    Max_Tip = get_max_mv_amount(COIN_NAME)
                    Min_Tx = get_min_tx_amount(COIN_NAME)
                    Max_Tx = get_max_tx_amount(COIN_NAME)
                response_text += "Confirmation: {} Blocks".format(confim_depth) + "\n"
                if is_coin_tipable(COIN_NAME): 
                    response_text += "Tipping: ON\n"
                else:
                    response_text += "Tipping: OFF\n"
                if is_coin_depositable(COIN_NAME): 
                    response_text += "Deposit: ON\n"
                else:
                    response_text += "Deposit: OFF\n"
                if is_coin_txable(COIN_NAME): 
                    response_text += "Withdraw: ON\n"
                else:
                    response_text += "Withdraw: OFF\n"
                get_tip_min_max = "Tip Min/Max:\n   " + num_format_coin(Min_Tip, COIN_NAME) + (" / ") + num_format_coin(Max_Tip, COIN_NAME) + COIN_NAME
                response_text += get_tip_min_max + "\n"
                get_tx_min_max = "Withdraw Min/Max:\n   " + num_format_coin(Min_Tx, COIN_NAME) + (" / ") + num_format_coin(Max_Tx, COIN_NAME) + COIN_NAME
                response_text += get_tx_min_max
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.print_exc(file=sys.stdout))
            message_text = text(bold("COIN INFO {}".format(COIN_NAME)) + markdown.pre(response_text))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
            return


@dp.message_handler(commands='balance')
async def start_cmd_handler(message: types.Message):
    content = ' '.join(message.text.split())
    args = content.split(" ")
    if message.chat.type != "private":
        return
    if message.from_user.username is None:
        reply_text = "I can not get your username."
        await message.reply(reply_text)
        return
    supported_coins = ", ".join(ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_COIN_ERC+ENABLE_COIN_NANO+ENABLE_XMR)
    if len(args) == 1:
        deposit_cmd_text = text(bold(f"Invalid COIN NAME after /balance") + markdown.pre(f"\nPlease use /balance COIN NAME. Supported COIN_NAME: {supported_coins}"))
        await message.reply(deposit_cmd_text, parse_mode=ParseMode.MARKDOWN)
        return
    else:
        # /balance WRKZ
        COIN_NAME = args[1].upper()
        if COIN_NAME == "LIST":
            message_text = ""
            coin_str = "\n"
            for COIN_ITEM in [coinItem.upper() for coinItem in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_COIN_ERC+ENABLE_COIN_NANO+ENABLE_XMR]:
                wallet = await store.sql_get_userwallet(message.from_user.username, COIN_ITEM, 'TELEGRAM')
                if wallet is None:
                    if COIN_ITEM in ENABLE_COIN_ERC:
                        w = create_eth_wallet()
                        userregister = await store.sql_register_user(message.from_user.username, COIN_ITEM, 'TELEGRAM', message.chat.id, w)
                    else:
                        userregister = await store.sql_register_user(message.from_user.username, COIN_ITEM, 'TELEGRAM', message.chat.id)
                    wallet = await store.sql_get_userwallet(message.from_user.username, COIN_ITEM, 'TELEGRAM')
                if COIN_ITEM in ENABLE_COIN_ERC:
                    coin_family = "ERC-20"
                else:
                    coin_family = getattr(getattr(config,"daemon"+COIN_ITEM),"coin_family","TRTL")

                if wallet is None:
                    await logchanbot(f'[Telegram] A user call /balance {COIN_ITEM} failed')
                    balance_actual = "N/A"
                else:
                    userdata_balance = await store.sql_user_balance(message.from_user.username, COIN_ITEM, 'TELEGRAM')
                    xfer_in = 0
                    if COIN_ITEM not in ENABLE_COIN_ERC:
                        xfer_in = await store.sql_user_balance_get_xfer_in(message.from_user.username, COIN_ITEM, 'TELEGRAM')
                    if COIN_ITEM in ENABLE_COIN_DOGE+ENABLE_COIN_ERC:
                        actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
                    elif COIN_ITEM in ENABLE_COIN_NANO:
                        actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                        actual_balance = round(actual_balance / get_decimal(COIN_ITEM), 6) * get_decimal(COIN_ITEM)
                    else:
                        actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                    # Negative check
                    try:
                        if actual_balance < 0:
                            msg_negative = '[Telegram] Negative balance detected:\nUser: '+message.from_user.username+'\nCoin: '+COIN_ITEM+'\nAtomic Balance: '+str(actual_balance)
                            await logchanbot(msg_negative)
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                    balance_actual = num_format_coin(actual_balance, COIN_ITEM)
                coin_str += COIN_ITEM + ": " + balance_actual + COIN_ITEM + "\n"
            message_text = text(bold(f'YOUR BALANCE SHEET:\n'), markdown.pre(coin_str))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
            return
        elif COIN_NAME not in ENABLE_COIN + ENABLE_COIN_DOGE + ENABLE_COIN_ERC + ENABLE_COIN_NANO + ENABLE_XMR:
            message_text = text(bold(f"Invalid COIN NAME after /balance") + markdown.pre(f"\nPlease use /balance COIN NAME. Supported COIN_NAME: {supported_coins}"))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
            return
        else:    
            # get balance user for a specific coin
            if COIN_NAME in ENABLE_COIN_ERC:
                coin_family = "ERC-20"
            else:
                coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
            userwallet = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')
            if userwallet is None:
                if COIN_NAME in ENABLE_COIN_ERC:
                    w = create_eth_wallet()
                    userregister = await store.sql_register_user(message.from_user.username, COIN_NAME, 'TELEGRAM', message.chat.id, w)
                else:
                    userregister = await store.sql_register_user(message.from_user.username, COIN_NAME, 'TELEGRAM', message.chat.id)
                userwallet = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')

            userdata_balance = await store.sql_user_balance(message.from_user.username, COIN_NAME, 'TELEGRAM')
            xfer_in = 0
            if COIN_NAME not in ENABLE_COIN_ERC:
                xfer_in = await store.sql_user_balance_get_xfer_in(message.from_user.username, COIN_NAME, 'TELEGRAM')
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
                    msg_negative = '[Telegram] Negative balance detected:\nUser: '+message.from_user.username+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                    await logchanbot(msg_negative)
            except Exception as e:
                await logchanbot(traceback.format_exc())

            message_text = text(bold(f'YOUR {COIN_NAME} BALANCE:') +
                                markdown.pre("\nAvailable: " + num_format_coin(actual_balance, COIN_NAME) + COIN_NAME))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
            return


@dp.message_handler(commands='botbal')
async def start_cmd_handler(message: types.Message):
    content = ' '.join(message.text.split())
    args = content.split(" ")
    # If private, return
    if message.chat.type == "private":
        return
    if message.from_user.username is None:
        reply_text = "I can not get your username."
        await message.reply(reply_text)
        return
    if len(args) == 1:
        reply_text = "Please mention a bot username starting with @."
        await message.reply(reply_text)
        return
    if len(args) == 2:
        # /botbal @botusername
        # Find user if exist
        user_to = None
        if len(args) == 2 and args[1].startswith("@"):
            user_to = (args[1])[1:]
        else:
            reply_text = "Please mention a bot username starting with @."
            await message.reply(reply_text)
            return
            
        if user_to is None:
            reply_text = "I can not get bot username."
            await message.reply(reply_text)
            return
        else:
            if user_to != "teletip_bot":
                reply_text = f"Unavailable for this bot {user_to}."
                await message.reply(reply_text)
                return
            else:
                message_text = ""
                coin_str = "\n"
                for COIN_ITEM in [coinItem.upper() for coinItem in ENABLE_COIN + ENABLE_COIN_DOGE + ENABLE_COIN_ERC + ENABLE_COIN_NANO + ENABLE_XMR]:
                    wallet = await store.sql_get_userwallet(user_to, COIN_ITEM, 'TELEGRAM')
                    if wallet is None:
                        # this will be public
                        if COIN_ITEM in ENABLE_COIN_ERC:
                            w = create_eth_wallet()
                            userregister = await store.sql_register_user(user_to, COIN_ITEM, 'TELEGRAM', message.chat.id, w)
                        else:
                            userregister = await store.sql_register_user(user_to, COIN_ITEM, 'TELEGRAM', message.chat.id)
                        wallet = await store.sql_get_userwallet(user_to, COIN_ITEM, 'TELEGRAM')
                    if COIN_ITEM in ENABLE_COIN_ERC:
                        coin_family = "ERC-20"
                    else:
                        coin_family = getattr(getattr(config,"daemon"+COIN_ITEM),"coin_family","TRTL")

                    userdata_balance = await store.sql_user_balance(user_to, COIN_ITEM, 'TELEGRAM')
                    xfer_in = 0
                    if COIN_ITEM not in ENABLE_COIN_ERC:
                        xfer_in = await store.sql_user_balance_get_xfer_in(user_to, COIN_ITEM, 'TELEGRAM')
                    if COIN_ITEM in ENABLE_COIN_DOGE+ENABLE_COIN_ERC:
                        actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
                    elif COIN_ITEM in ENABLE_COIN_NANO:
                        actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                        actual_balance = round(actual_balance / get_decimal(COIN_ITEM), 6) * get_decimal(COIN_ITEM)
                    else:
                        actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                        # Negative check
                    try:
                        if actual_balance < 0:
                            msg_negative = '[Telegram] Negative balance detected:\nBot User: '+user_to+'\nCoin: '+COIN_ITEM+'\nAtomic Balance: '+str(actual_balance)
                            await logchanbot(msg_negative)
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                    balance_actual = num_format_coin(actual_balance, COIN_ITEM)
                    coin_str += COIN_ITEM + ": " + balance_actual + COIN_ITEM + "\n"
                message_text = text(bold(f'@{user_to} BALANCE SHEET:\n') + markdown.pre(coin_str))
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
                return


@dp.message_handler(commands='register')
async def start_cmd_handler(message: types.Message):
    content = ' '.join(message.text.split())
    args = content.split(" ")
    if message.chat.type != "private":
        reply_text = "This can be done in Private only."
        await message.reply(reply_text)
        return
    if message.from_user.username is None:
        reply_text = "I can not get your username."
        await message.reply(reply_text)
        return
    if len(args) == 1:
        reply_text = "Please use /register YOUR_WALLET_ADDRESS"
        await message.reply(reply_text)
        return
    else:
        # /register XXXX
        wallet_address = args[1]
        if len(args) >= 3:
            coin = args[2].upper()
        else:
            coin = None
        if wallet_address.isalnum() == False:
            message_text = text(bold("Invalid address:\n"),
                                markdown.pre(wallet_address))
            await message.reply(message_text,
                                parse_mode=ParseMode.MARKDOWN)
            return
        else:
            COIN_NAME = get_cn_coin_from_address(wallet_address)
            if COIN_NAME:
                pass
            else:
                if wallet_address.startswith("0x"):
                    if wallet_address.upper().startswith("0X00000000000000000000000000000"):
                        reply_text = f"Invalid token:\n{wallet_address}"
                        await message.reply(reply_text,
                                            parse_mode=ParseMode.MARKDOWN)
                        return
                    if coin is None:
                        reply_text = "You need to add **TOKEN NAME** address."
                        await message.reply(reply_text,
                                            parse_mode=ParseMode.MARKDOWN)
                        return
                    else:
                        COIN_NAME = coin.upper()
                        if COIN_NAME not in ENABLE_COIN_ERC:
                            reply_text = f"Unsupported Token **{coin}**."
                            await message.reply(reply_text,
                                                parse_mode=ParseMode.MARKDOWN)
                            return
                        else:
                            # validate
                            valid_address = await store.erc_validate_address(wallet_address, COIN_NAME)
                            valid = False
                            if valid_address and valid_address.upper() == wallet_address.upper():
                                valid = True
                            else:
                                reply_text = f"Invalid token address:\n{wallet_address}."
                                await message.reply(reply_text,
                                                    parse_mode=ParseMode.MARKDOWN)
                                return
                else:
                    reply_text = f"Unknown Ticker:\n{wallet_address}."
                    await message.reply(reply_text,
                                        parse_mode=ParseMode.MARKDOWN)
                    return

            if COIN_NAME in ENABLE_COIN_ERC:
                coin_family = "ERC-20"
            else:
                coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
            if COIN_NAME not in ENABLE_COIN + ENABLE_COIN_DOGE + ENABLE_COIN_NANO:
                message_text = text(bold("Invalid or unsupported coin address."))
                await message.reply(message_text,
                                    parse_mode=ParseMode.MARKDOWN)
                return
            if coin_family == "TRTL" or coin_family == "BCN":
                addressLength = get_addrlen(COIN_NAME)
                IntaddressLength = 0
                if coin_family == "TRTL" or coin_family == "XMR":
                    IntaddressLength = get_intaddrlen(COIN_NAME)
                if len(wallet_address) == int(addressLength):
                    valid_address = addressvalidation.validate_address_cn(wallet_address, COIN_NAME)
                    if valid_address is None:
                        message_text = text(bold("Invalid address:\n"),
                                            markdown.pre(wallet_address))
                        await message.reply(message_text,
                                            parse_mode=ParseMode.MARKDOWN)
                        return
                    else:
                        user_addr = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')
                        if user_addr is None:
                            userregister = await store.sql_register_user(message.from_user.username, COIN_NAME, 'TELEGRAM', message.chat.id)
                            user_addr = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')

                        prev_address = user_addr['user_wallet_address']
                        if prev_address != valid_address:
                            await store.sql_update_user(message.from_user.username, wallet_address, COIN_NAME, 'TELEGRAM')
                            message_text = text(bold("You registered a withdrawn address:\n"),
                                                markdown.pre(wallet_address))
                            await message.reply(message_text,
                                                parse_mode=ParseMode.MARKDOWN)
                            return
                        else:
                            message_text = text("Your previous registered address is the same as new address. Action not taken.")
                            await message.reply(message_text)
                            return
                elif len(wallet_address) == int(IntaddressLength): 
                    # Not allowed integrated address
                    message_text = text(bold("Integrated address not allowed:\n"),
                                        markdown.pre(wallet_address))
                    await message.reply(message_text,
                                        parse_mode=ParseMode.MARKDOWN)
                    return
            elif coin_family == "DOGE":
                valid_address = None
                user_from = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')
                if user_from is None:
                    user_from = await store.sql_register_user(message.from_user.username, COIN_NAME, 'TELEGRAM')
                    user_from = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')
                user_from['address'] = user_from['balance_wallet_address']
                prev_address = user_from['user_wallet_address']

                valid_address = await doge_validaddress(str(wallet_address), COIN_NAME)
                if ('isvalid' in valid_address):
                    if str(valid_address['isvalid']) == "True":
                        valid_address = wallet_address
                    else:
                        message_text = text(bold("Unknown address:\n"),
                                            markdown.pre(wallet_address))
                        await message.reply(message_text,
                                            parse_mode=ParseMode.MARKDOWN)
                        return
                if user_from['balance_wallet_address'] == wallet_address:
                    message_text = text(bold("Can not register with your deposit address:\n"),
                                        markdown.pre(wallet_address))
                    await message.reply(message_text,
                                        parse_mode=ParseMode.MARKDOWN)
                    return
                elif prev_address and prev_address == wallet_address:
                    message_text = text(bold("Previous and new address is the same:\n"),
                                        markdown.pre(wallet_address))
                    await message.reply(message_text,
                                        parse_mode=ParseMode.MARKDOWN)
                    return
                else:
                    await store.sql_update_user(message.from_user.username, wallet_address, COIN_NAME, 'TELEGRAM')
                    message_text = text(bold("You registered a withdrawn address:\n"),
                                        markdown.pre(wallet_address))
                    await message.reply(message_text,
                                        parse_mode=ParseMode.MARKDOWN)
                    return


@dp.message_handler(commands='tip')
async def start_cmd_handler(message: types.Message):
    if message.from_user.username is None:
        reply_text = "I can not get your username."
        await message.reply(reply_text)
        return

    content = ' '.join(message.text.split())
    args = content.split(" ")

    if len(args) != 4 and len(args) != 3:
        reply_text = "Please use /tip amount coin_name @telegramuser"
        await message.reply(reply_text)
        return
    elif len(args) == 3 and message.reply_to_message is None:
        reply_text = "Please use /tip amount coin_name @telegramuser"
        await message.reply(reply_text)
        return

    supported_coins = ", ".join(ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_COIN_ERC+ENABLE_XMR)
    COIN_NAME = args[2].upper()
    if COIN_NAME not in ENABLE_COIN + ENABLE_COIN_DOGE + ENABLE_COIN_ERC + ENABLE_COIN_NANO + ENABLE_XMR:
        message_text = text(bold(f"Invalid {COIN_NAME}") + markdown.pre("\nSupported coins:"+supported_coins))
        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
        return

    if not is_coin_tipable(COIN_NAME):
        message_text = text(bold(f"TIPPING is currently disable for {COIN_NAME}."))
        await message.reply(message_text,
                            parse_mode=ParseMode.MARKDOWN)
        return


    amount = args[1].replace(",", "")
    try:
        amount = float(amount)
    except ValueError:
        message_text = text(bold("Invalid amount."))
        await message.reply(message_text,
                            parse_mode=ParseMode.MARKDOWN)
        return

    # Find user if exist
    user_to = None
    if len(args) == 4 and args[3].startswith("@"):
        user_to = (args[3])[1:]
    elif len(args) == 3 and message.reply_to_message:
        user_to = message.reply_to_message.from_user.username
        
    if user_to is None:
        reply_text = "I can not get username to tip to."
        await message.reply(reply_text)
        return
    else:
        # if tip to himself
        if user_to == message.from_user.username:
            reply_text = "You can not tip to yourself."
            await message.reply(reply_text)
            return
            
        to_teleuser = await store.sql_get_userwallet(user_to, COIN_NAME, 'TELEGRAM')
        if to_teleuser is None:
            message_text = text(bold(f"Can not find user {user_to} in our DB"))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
            return
        else:
            to_user = to_teleuser['chat_id']
            if COIN_NAME in ENABLE_COIN_ERC:
                coin_family = "ERC-20"
            else:
                coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
            user_from = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')
            userdata_balance = await store.sql_user_balance(message.from_user.username, COIN_NAME, 'TELEGRAM')
            xfer_in = 0
            if COIN_NAME not in ENABLE_COIN_ERC:
                xfer_in = await store.sql_user_balance_get_xfer_in(message.from_user.username, COIN_NAME, 'TELEGRAM')
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
                    msg_negative = '[Telegram] Negative balance detected:\nUser: '+message.from_user.username+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
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
            else:
                confim_depth = get_confirm_depth(COIN_NAME)
                Min_Tip = get_min_mv_amount(COIN_NAME)
                Max_Tip = get_max_mv_amount(COIN_NAME)
                Min_Tx = get_min_tx_amount(COIN_NAME)
                Max_Tx = get_max_tx_amount(COIN_NAME)
                real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)

            message_text = ''
            valid_amount = True
            if real_amount > actual_balance:
                message_text = 'Insufficient balance to send tip of ' + num_format_coin(real_amount, COIN_NAME) + COIN_NAME + ' to ' + args[3]
                valid_amount = False
            elif real_amount > Max_Tip:
                message_text = 'Transactions cannot be bigger than ' + num_format_coin(Max_Tip, COIN_NAME) + COIN_NAME
                valid_amount = False
            elif real_amount < Min_Tip:
                message_text = 'Transactions cannot be bigger than ' + num_format_coin(Min_Tip, COIN_NAME) + COIN_NAME
                valid_amount = False
            if valid_amount == False:
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
                return
            else:
                tip = None
                try:
                    if message.from_user.username not in WITHDRAW_IN_PROCESS:
                        WITHDRAW_IN_PROCESS.append(message.from_user.username)
                    else:
                        message_text = text(bold("You have another tx in progress.\n"))
                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
                        return
                    tip = None
                    try:
                        if coin_family in ["TRTL", "BCN"]:
                            tip = await store.sql_mv_cn_single(message.from_user.username, user_to, real_amount, 'TIP', COIN_NAME, "TELEGRAM")
                        elif coin_family == "XMR":
                            tip = await store.sql_mv_xmr_single(message.from_user.username, user_to, real_amount, COIN_NAME, "TIP", "TELEGRAM")
                        elif coin_family == "DOGE":
                            tip = await store.sql_mv_doge_single(message.from_user.username, user_to, real_amount, COIN_NAME, "TIP", "TELEGRAM")
                        elif coin_family == "NANO":
                            tip = await store.sql_mv_nano_single(message.from_user.username, user_to, real_amount, COIN_NAME, "TIP", "TELEGRAM")
                        elif coin_family == "ERC-20":
                            tip = await store.sql_mv_erc_single(message.from_user.username, user_to, real_amount, COIN_NAME, "TIP", token_info['contract'], "TELEGRAM")
                    except Exception as e:
                        await logchanbot(traceback.format_exc())

                    message_text = text(bold(f"You sent a new tip to {user_to}:\n\n") + markdown.pre("\nAmount: {}{}".format(num_format_coin(real_amount, COIN_NAME), COIN_NAME)))
                    to_message_text = text(bold(f"You got a new tip from {message.from_user.username}:\n\n"), markdown.pre("Amount: {}{}".format(num_format_coin(real_amount, COIN_NAME), COIN_NAME)))
                    if user_to in ["teletip_bot"]:
                        to_message_text = to_message_text.replace("You ", f"@{user_to} ")
                    try:
                        await message.reply(message_text,
                                                            parse_mode=ParseMode.MARKDOWN)
                        send_msg = await bot.send_message(chat_id=to_user, text=to_message_text, parse_mode=ParseMode.MARKDOWN)
                    except exceptions.BotBlocked:
                        await logchanbot(f"Target [ID:{to_user}]: blocked by user")
                    except exceptions.ChatNotFound:
                        await logchanbot(f"Target [ID:{to_user}]: invalid user ID")
                    except exceptions.RetryAfter as e:
                        await logchanbot(f"Target [ID:{to_user}]: Flood limit is exceeded. Sleep {e.timeout} seconds.")
                        await asyncio.sleep(e.timeout)
                        return await bot.send_message(chat_id=to_user, text=message_text, parse_mode=ParseMode.MARKDOWN)  # Recursive call
                    except exceptions.UserDeactivated:
                        await logchanbot(f"Target [ID:{to_user}]: user is deactivated")
                    except exceptions.TelegramAPIError:
                        await logchanbot(f"Target [ID:{to_user}]: failed")
                    except Exception as e:
                        await logchanbot(traceback.print_exc(file=sys.stdout))
                except Exception as e:
                    await logchanbot(traceback.print_exc(file=sys.stdout))
                if message.from_user.username in WITHDRAW_IN_PROCESS:
                    WITHDRAW_IN_PROCESS.remove(message.from_user.username)
                return


@dp.message_handler(commands='send')
async def start_cmd_handler(message: types.Message):
    if message.from_user.username is None:
        reply_text = "I can not get your username."
        await message.reply(reply_text)
        return

    content = ' '.join(message.text.split())
    args = content.split(" ")
    if len(args) != 4:
        reply_text = "Please use /send amount coin_name address"
        await message.reply(reply_text)
        return
   
    COIN_NAME = args[2].upper()
    supported_coins = ", ".join(ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_COIN_ERC+ENABLE_XMR)
    if COIN_NAME not in ENABLE_COIN + ENABLE_COIN_DOGE + ENABLE_COIN_ERC + ENABLE_COIN_NANO + ENABLE_XMR:
        message_text = text(bold(f"Invalid {COIN_NAME}") + markdown.pre("\nSupported coins:"+supported_coins))
        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
        return

    if not is_coin_txable(COIN_NAME):
        message_text = text(bold(f"TX is currently disable for {COIN_NAME}."))
        await message.reply(message_text,
                            parse_mode=ParseMode.MARKDOWN)
        return

    amount = args[1].replace(",", "")
    try:
        amount = float(amount)
    except ValueError:
        message_text = text(bold("Invalid amount."))
        await message.reply(message_text,
                            parse_mode=ParseMode.MARKDOWN)
        return

    # add redis action
    random_string = str(uuid.uuid4())
    await add_tx_action_redis(json.dumps([random_string, "SEND", message.from_user.username, message.from_user.username, float("%.3f" % time.time()), message.text, "TELEGRAM", "START"]), False)

    wallet_address = args[3]
    if wallet_address.isalnum() == False:
        message_text = text(bold("Invalid address:\n"),
                            markdown.pre(wallet_address))
        await message.reply(message_text,
                            parse_mode=ParseMode.MARKDOWN)
        return
    else:
        check_in = await store.coin_check_balance_address_in_users(wallet_address, COIN_NAME)
        if check_in:
            message_text = text(bold("Can not send to this address::\n") + markdown.pre(wallet_address))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
            return
        COIN_NAME_CHECK = get_cn_coin_from_address(wallet_address)
        if not COIN_NAME_CHECK:
            message_text = text(bold("Unknown coin name:\n") + markdown.pre(wallet_address))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
            return
        elif COIN_NAME_CHECK != COIN_NAME:
            message_text = text(bold("Error getting address and coin name from:\n") + markdown.pre(wallet_address))
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
            return
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

            userdata_balance = await store.sql_user_balance(message.from_user.username, COIN_NAME, 'TELEGRAM')
            xfer_in = 0
            if COIN_NAME not in ENABLE_COIN_ERC:
                xfer_in = await store.sql_user_balance_get_xfer_in(message.from_user.username, COIN_NAME, 'TELEGRAM')
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
                    msg_negative = '[Telegram] Negative balance detected:\nUser: '+message.from_user.username+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
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
                message_text = '\nTransactions cannot be bigger than ' + num_format_coin(Min_Tx, COIN_NAME) + COIN_NAME
                valid_amount = False
            if valid_amount == False:
                await message.reply(markdown.pre(message_text), parse_mode=ParseMode.MARKDOWN)
                return

            if coin_family == "TRTL" or coin_family == "XMR":
                IntaddressLength = get_intaddrlen(COIN_NAME)
                if len(wallet_address) == int(addressLength):
                    valid_address = addressvalidation.validate_address_cn(wallet_address, COIN_NAME)
                    if valid_address is None:
                        message_text = text(bold("Invalid address:\n") + markdown.pre(wallet_address))
                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
                        return
                    else:
                        user_from = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')
                        if user_from is None:
                            userregister = await store.sql_register_user(message.from_user.username, COIN_NAME, 'TELEGRAM', message.chat.id)
                            user_from = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')
                        CoinAddress = wallet_address
                elif len(wallet_address) == int(IntaddressLength): 
                    # use integrated address
                    valid_address = addressvalidation.validate_integrated_cn(wallet_address, COIN_NAME)
                    if valid_address == 'invalid':
                        message_text = text(bold("Invalid address:\n") + markdown.pre(wallet_address))
                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
                        return
                    elif len(valid_address) == 2:
                        address_paymentID = wallet_address
                        CoinAddress = valid_address['address']
                        paymentid = valid_address['integrated_id']

                main_address = getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
                if CoinAddress and CoinAddress == main_address:
                    # Not allow to send to own main address
                    message_text = text(bold("Can not send to:\n") + markdown.pre(wallet_address))
                    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
                    return
                else:
                    tip = None
                    if message.from_user.username not in WITHDRAW_IN_PROCESS:
                        WITHDRAW_IN_PROCESS.append(message.from_user.username)
                    else:
                        message_text = text(bold("You have another tx in progress.\n"))
                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
                        return

                    if paymentid:
                        try:
                            tip = await store.sql_external_cn_single_id(str(ctx.message.author.id), CoinAddress, real_amount, paymentid, COIN_NAME, 'TELEGRAM')
                            await logchanbot(f'[Telegram] User {message.from_user.username} send tx out {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}')
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                    else:
                        try:
                            tip = await store.sql_external_cn_single(message.from_user.username, CoinAddress, real_amount, COIN_NAME, 'TELEGRAM')
                            await logchanbot(f'[Telegram] User {message.from_user.username} send tx out {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}')
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                    if message.from_user.username in WITHDRAW_IN_PROCESS:
                        WITHDRAW_IN_PROCESS.remove(message.from_user.username)
                    if tip:
                        tip_tx_tipper = "\nTransaction hash: {}".format(tip['transactionHash'])
                        tip_tx_tipper += "\nTx Fee: {}{}".format(num_format_coin(tip['fee'], COIN_NAME), COIN_NAME)
                        await add_tx_action_redis(json.dumps([random_string, "SEND", message.from_user.username, message.from_user.username, float("%.3f" % time.time()), message.text, "TELEGRAM", "COMPLETE"]), False)
                        message_text = text(bold(f"You have sent {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}:\n") + markdown.pre(tip_tx_tipper))
                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
                        return
                    else:
                        message_text = text(bold(f"Internal error for sending {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}"))
                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
                        return
            elif coin_family == "DOGE":
                valid_address = await doge_validaddress(str(wallet_address), COIN_NAME)
                if 'isvalid' in valid_address:
                    if str(valid_address['isvalid']) != "True":
                        message_text = text(bold("Invalid address:\n") + markdown.pre(wallet_address))
                        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
                        return
                    else:
                        sendTx = None
                        if message.from_user.username not in WITHDRAW_IN_PROCESS:
                            WITHDRAW_IN_PROCESS.append(message.from_user.username)
                        else:
                            message_text = text(bold("You have another tx in progress.\n"))
                            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
                            return

                        try:
                            NetFee = get_tx_fee(coin = COIN_NAME)
                            sendTx = await store.sql_external_doge_single(message.from_user.username, real_amount, NetFee, wallet_address, COIN_NAME, 'SEND', 'TELEGRAM')
                            await logchanbot(f'[Telegram] User {message.from_user.username} send tx out {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}')
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)

                        if message.from_user.username in WITHDRAW_IN_PROCESS:
                            WITHDRAW_IN_PROCESS.remove(message.from_user.username)
                        if sendTx:
                            tx_text = "\nTransaction hash: {}".format(sendTx)
                            tx_text += "\nNetwork fee deducted from the amount."
                            
                            message_text = text(bold(f"You have sent {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}:\n") + markdown.pre(tx_text))
                            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
                            return
                        else:
                            message_text = text(bold(f"Internal error for sending {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}"))
                            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
                            return
            else:
                message_text = text("Not supported yet. Check back later.")
                await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
                return


@dp.message_handler(commands='withdraw')
async def start_cmd_handler(message: types.Message):
    if message.from_user.username is None:
        reply_text = "I can not get your username."
        await message.reply(reply_text)
        return

    # Temporary to use send instead
    reply_text = "Please use send instead."
    await message.reply(reply_text)
    return

    content = ' '.join(message.text.split())
    args = content.split(" ")
    if len(args) != 3:
        reply_text = "Please use /withdraw amount coin_name"
        await message.reply(reply_text)
        return
   
    COIN_NAME = args[2].upper()
    supported_coins = ", ".join(ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_COIN_ERC+ENABLE_XMR)
    if COIN_NAME not in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_COIN_ERC:
        message_text = text(bold(f"Invalid {COIN_NAME}") + markdown.pre("\nSupported coins:"+supported_coins))
        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
        return

    if not is_coin_txable(COIN_NAME):
        message_text = text(bold(f"TX is currently disable for {COIN_NAME}."))
        await message.reply(message_text,
                            parse_mode=ParseMode.MARKDOWN)
        return

    amount = args[1].replace(",", "")
    try:
        amount = float(amount)
    except ValueError:
        message_text = text(bold("Invalid amount."))
        await message.reply(message_text,
                            parse_mode=ParseMode.MARKDOWN)
        return

    # add redis action
    random_string = str(uuid.uuid4())
    await add_tx_action_redis(json.dumps([random_string, "WITHDRAW", message.from_user.username, message.from_user.username, float("%.3f" % time.time()), message.text, "TELEGRAM", "START"]), False)

    # get coin family
    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    user_from = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')
    if user_from is None:
        message_text = text(bold(f"You have not registered {COIN_NAME}"))
        await message.reply(message_text,
                            parse_mode=ParseMode.MARKDOWN)
        return
    elif user_from and user_from['user_wallet_address'] is None:
        message_text = text(bold(f"You have not registered {COIN_NAME} address"))
        await message.reply(message_text,
                            parse_mode=ParseMode.MARKDOWN)
        return
    elif user_from['user_wallet_address']:
        if COIN_NAME in ENABLE_COIN_ERC:
            token_info = await store.get_token_info(COIN_NAME)
            confim_depth = token_info['deposit_confirm_depth']
            Min_Tip = token_info['real_min_tip']
            Max_Tip = token_info['real_max_tip']
            Min_Tx = token_info['real_min_tx']
            Max_Tx = token_info['real_max_tx']
            NetFee = token_info['real_withdraw_fee']
            real_amount = amount
        else:
            confim_depth = get_confirm_depth(COIN_NAME)
            Min_Tip = get_min_mv_amount(COIN_NAME)
            Max_Tip = get_max_mv_amount(COIN_NAME)
            Min_Tx = get_min_tx_amount(COIN_NAME)
            Max_Tx = get_max_tx_amount(COIN_NAME)
            NetFee = get_reserved_fee(coin = COIN_NAME)
            real_amount = int(amount * get_decimal(COIN_NAME)) if (coin_family == "TRTL" or coin_family == "XMR") else amount
        wallet_address = user_from['user_wallet_address']
        message_text = ''
        valid_amount = True


        userdata_balance = await store.sql_user_balance(message.from_user.username, COIN_NAME, 'TELEGRAM')
        xfer_in = 0
        if COIN_NAME not in ENABLE_COIN_ERC:
            xfer_in = await store.sql_user_balance_get_xfer_in(message.from_user.username, COIN_NAME, 'TELEGRAM')
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
                msg_negative = '[Telegram] Negative balance detected:\nUser: '+message.from_user.username+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                await logchanbot(msg_negative)
        except Exception as e:
            await logchanbot(traceback.format_exc())

        if real_amount + NetFee > actual_balance:
            message_text = 'Not enough reserved fee / Insufficient balance to withdraw ' + num_format_coin(real_amount, COIN_NAME) + COIN_NAME + ' to ' + wallet_address
            valid_amount = False
        elif real_amount > MaxTX:
            message_text = 'Transactions cannot be bigger than ' + num_format_coin(MaxTX, COIN_NAME) + COIN_NAME
            valid_amount = False
        elif real_amount < MinTx:
            message_text = 'Transactions cannot be bigger than ' + num_format_coin(MinTx, COIN_NAME) + COIN_NAME
            valid_amount = False
        if valid_amount == False:
            await message.reply(message_text,
                                parse_mode=ParseMode.MARKDOWN)
            return
        
        if coin_family == "TRTL":
            main_address = getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
            if wallet_address and wallet_address == main_address:
                # Not allow to send to own main address
                message_text = text(bold("Can not send to:\n"),
                                    markdown.pre(wallet_address))
                await message.reply(message_text,
                                    parse_mode=ParseMode.MARKDOWN)
                return
            else:
                tip = None
                if message.from_user.username not in WITHDRAW_IN_PROCESS:
                    WITHDRAW_IN_PROCESS.append(message.from_user.username)
                else:
                    message_text = text(bold("You have another tx in progress.\n"))
                    await message.reply(message_text,
                                        parse_mode=ParseMode.MARKDOWN)
                    return

                try:
                    withdrawTx = await store.sql_external_cn_single_withdraw(message.from_user.username, real_amount, COIN_NAME, "TELEGRAM")
                    withdraw_txt = "Transaction hash: {}".format(withdrawTx['transactionHash'])
                    withdraw_txt += "\nTx Fee: {}{}".format(num_format_coin(withdrawTx['fee'], COIN_NAME), COIN_NAME)
                except Exception as e:
                    await logchanbot(traceback.print_exc(file=sys.stdout))

                if message.from_user.username in WITHDRAW_IN_PROCESS:
                    WITHDRAW_IN_PROCESS.remove(message.from_user.username)
                if tip:
                    await add_tx_action_redis(json.dumps([random_string, "WITHDRAW", message.from_user.username, message.from_user.username, float("%.3f" % time.time()), message.text, "TELEGRAM", "COMPLETE"]), False)
                    message_text = text(bold(f"You have withdrawn {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}:\n"),
                                        markdown.pre(withdraw_txt))
                    await message.reply(message_text,
                                        parse_mode=ParseMode.MARKDOWN)
                    return
                else:
                    message_text = text(bold(f"Internal error for sending {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}"))
                    await message.reply(message_text,
                                        parse_mode=ParseMode.MARKDOWN)
                    await logchanbot(message_text)
                    return
        elif coin_family == "DOGE":
            withdrawTx = None
            if message.from_user.username not in WITHDRAW_IN_PROCESS:
                WITHDRAW_IN_PROCESS.append(message.from_user.username)
            else:
                message_text = text(bold("You have another tx in progress.\n"))
                await message.reply(message_text,
                                    parse_mode=ParseMode.MARKDOWN)
                return

            try:
                NetFee = get_tx_fee(coin = COIN_NAME)
                withdrawTx = await store.sql_external_doge_single(message.from_user.username, real_amount,
                                                                NetFee, wallet_address,
                                                                COIN_NAME, "WITHDRAW", "TELEGRAM")
                withdraw_txt = f'Transaction hash: {withdrawTx}\nNetwork fee deducted from the amount.'
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

            if message.from_user.username in WITHDRAW_IN_PROCESS:
                WITHDRAW_IN_PROCESS.remove(message.from_user.username)
            if withdrawTx:
                await add_tx_action_redis(json.dumps([random_string, "WITHDRAW", message.from_user.username, message.from_user.username, float("%.3f" % time.time()), message.text, "TELEGRAM", "COMPLETE"]), False)
                message_text = text(bold(f"You have withdrawn {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}:\n"),
                                    markdown.pre(withdraw_txt))
                await message.reply(message_text,
                                    parse_mode=ParseMode.MARKDOWN)
                return
            else:
                message_text = text(bold(f"Internal error for sending {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}"))
                await message.reply(message_text,
                                    parse_mode=ParseMode.MARKDOWN)
                await logchanbot(message_text)
                return


@dp.message_handler(commands='take')
async def start_cmd_handler(message: types.Message):
    if message.from_user.username is None:
        reply_text = "I can not get your username."
        await message.reply(reply_text)
        return
    if message.chat.type != "private":
        reply_text = "Can not do here. Please do it privately with my direct message."
        await message.reply(reply_text)
        return

    # check user claim:
    claim_interval = 24
    check_claimed = await store.sql_faucet_checkuser(message.from_user.username, 'TELEGRAM')
    if check_claimed:
        # limit 12 hours
        if int(time.time()) - check_claimed['claimed_at'] <= claim_interval*3600:
            remaining = await bot_faucet() or ''
            time_waiting = seconds_str(claim_interval*3600 - int(time.time()) + check_claimed['claimed_at'])
            number_user_claimed = '{:,.0f}'.format(await store.sql_faucet_count_user(message.from_user.username, 'TELEGRAM'))
            total_claimed = '{:,.0f}'.format(await store.sql_faucet_count_all())

            reply_text = text(markdown.pre(f'\nYou just claimed within last {claim_interval}h. \n'
                                           f'Waiting time {time_waiting} for next /take.\nFaucet balance:\n{remaining}\n'
                                           f'Total user claims: {total_claimed} times. '
                                           f'You have claimed: {number_user_claimed} time(s). '
                                           f'Tip me if you want to feed these faucets.\n Any support, join https://t.me/wrkzcoinchat'))
            await message.reply(reply_text, parse_mode=ParseMode.MARKDOWN)
            return

    COIN_NAME = random.choice(FAUCET_COINS)
    while is_maintenance_coin(COIN_NAME):
        COIN_NAME = random.choice(FAUCET_COINS)

    amount = random.randint(FAUCET_MINMAX[COIN_NAME][0]*get_decimal(COIN_NAME), FAUCET_MINMAX[COIN_NAME][1]*get_decimal(COIN_NAME))

    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if COIN_NAME == "DOGE":
        amount = float(amount / 50)
    elif COIN_NAME in HIGH_DECIMAL_COIN:
        amount = float("%.5f" % (amount / get_decimal(COIN_NAME))) * get_decimal(COIN_NAME)

    def myround_number(x, base=5):
        return base * round(x/base)

    if COIN_NAME in ENABLE_COIN_ERC:
        token_info = await store.get_token_info(COIN_NAME)
        confim_depth = token_info['deposit_confirm_depth']
        Min_Tip = token_info['real_min_tip']
        Max_Tip = token_info['real_max_tip']
        Min_Tx = token_info['real_min_tx']
        Max_Tx = token_info['real_max_tx']
        coin_decimal = 10**token_info['token_decimal']
    else:
        confim_depth = get_confirm_depth(COIN_NAME)
        Min_Tip = get_min_mv_amount(COIN_NAME)
        Max_Tip = get_max_mv_amount(COIN_NAME)
        Min_Tx = get_min_tx_amount(COIN_NAME)
        Max_Tx = get_max_tx_amount(COIN_NAME)
        coin_decimal = get_decimal(COIN_NAME)

    real_amount = amount
    userdata_balance = await store.sql_user_balance('teletip_bot', COIN_NAME, 'TELEGRAM')
    xfer_in = 0
    if COIN_NAME not in ENABLE_COIN_ERC:
        xfer_in = await store.sql_user_balance_get_xfer_in('teletip_bot', COIN_NAME, 'TELEGRAM')
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
                msg_negative = '[Telegram] Negative balance detected:\nUser: '+message.from_user.username+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                await logchanbot(msg_negative)
        except Exception as e:
            await logchanbot(traceback.format_exc())

    user_to = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')
    if user_to is None:
        reply_text = f"You get random coin {COIN_NAME}. But I can not get you in DB. Please create your account with /balance {COIN_NAME}"
        await message.reply(reply_text)
        return
    else:
        try:
            if real_amount > actual_balance:
                reply_text = f"Bot runs out of {COIN_NAME}."
                await message.reply(reply_text)
                return

            tip = None
            try:
                if coin_family in ["TRTL", "BCN"]:
                    tip = await store.sql_mv_cn_single("teletip_bot", message.from_user.username, real_amount, "FAUCET", COIN_NAME, "TELEGRAM")
                elif coin_family == "XMR":
                    tip = await store.sql_mv_xmr_single("teletip_bot", message.from_user.username, real_amount, COIN_NAME, "FAUCET", "TELEGRAM")
                elif coin_family == "NANO":
                    tip = await store.sql_mv_nano_single("teletip_bot", message.from_user.username, real_amount, COIN_NAME, "FAUCET", "TELEGRAM")
                elif coin_family == "DOGE":
                    tip = await store.sql_mv_doge_single("teletip_bot", message.from_user.username, real_amount, COIN_NAME, "FAUCET", "TELEGRAM")
                elif coin_family == "ERC-20":
                    token_info = await store.get_token_info(COIN_NAME)
                    tip = await store.sql_mv_erc_single("teletip_bot", message.from_user.username, real_amount, COIN_NAME, "FAUCET", token_info['contract'], "TELEGRAM")
                await logchanbot(f'[Telegram] User {message.from_user.username} claimed faucet {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}')
            except Exception as e:
                await logchanbot(traceback.format_exc())
            if tip:
                get_decimal(COIN_NAME)
                faucet_add = await store.sql_faucet_add(message.from_user.username, message.chat.id, COIN_NAME, real_amount, coin_decimal, "TELEGRAM")
                message_text = text(bold("You received free coin:"), markdown.pre("\nAmount: {}{}".format(num_format_coin(real_amount, COIN_NAME), COIN_NAME)), "\nConsider tipping me if you like this :).")
                await message.reply(message_text,
                                    parse_mode=ParseMode.MARKDOWN)
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


@dp.message_handler(commands='donate')
async def start_cmd_handler(message: types.Message):
    if message.from_user.username is None:
        reply_text = "I can not get your username."
        await message.reply(reply_text)
        return

    content = ' '.join(message.text.split())
    args = content.split(" ")
    if len(args) != 3:
        reply_text = "Please use /donate amount COIN NAME"
        await message.reply(reply_text)
        return
   
    COIN_NAME = args[2].upper()
    supported_coins = ", ".join(ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_COIN_ERC+ENABLE_XMR)
    if COIN_NAME not in supported_coins:
        message_text = text(bold(f"Invalid {COIN_NAME}") + markdown.pre("\nSupported coins:"+supported_coins))
        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
        return

    amount = args[1].replace(",", "")
    try:
        amount = float(amount)
    except ValueError:
        message_text = text(bold("Invalid amount."))
        await message.reply(message_text,
                            parse_mode=ParseMode.MARKDOWN)
        return

    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    user_from = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')

    if COIN_NAME in ENABLE_COIN_ERC:
        token_info = await store.get_token_info(COIN_NAME)
        confim_depth = token_info['deposit_confirm_depth']
        Min_Tip = token_info['real_min_tip']
        Max_Tip = token_info['real_max_tip']
        Min_Tx = token_info['real_min_tx']
        Max_Tx = token_info['real_max_tx']
        real_amount = amount
        coin_decimal = 10**token_info['token_decimal']
    else:
        confim_depth = get_confirm_depth(COIN_NAME)
        Min_Tip = get_min_mv_amount(COIN_NAME)
        Max_Tip = get_max_mv_amount(COIN_NAME)
        Min_Tx = get_min_tx_amount(COIN_NAME)
        Max_Tx = get_max_tx_amount(COIN_NAME)
        real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
        coin_decimal = get_decimal(COIN_NAME)

    userdata_balance = await store.sql_user_balance(message.from_user.username, COIN_NAME, 'TELEGRAM')
    xfer_in = 0
    if COIN_NAME not in ENABLE_COIN_ERC:
        xfer_in = await store.sql_user_balance_get_xfer_in(message.from_user.username, COIN_NAME, 'TELEGRAM')
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
            msg_negative = '[Telegram] Negative balance detected:\nUser: '+message.from_user.username+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
            await logchanbot(msg_negative)
    except Exception as e:
        await logchanbot(traceback.format_exc())

    message_text = ''
    valid_amount = True
    if real_amount > actual_balance:
        message_text = 'Insufficient balance to donate ' + num_format_coin(real_amount, COIN_NAME) + COIN_NAME
        valid_amount = False
    elif real_amount < Min_Tip:
        message_text = 'Transactions cannot be bigger than ' + num_format_coin(Min_Tip, COIN_NAME) + COIN_NAME
        valid_amount = False
    if valid_amount == False:
        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
        return


    if message.from_user.username not in WITHDRAW_IN_PROCESS:
        WITHDRAW_IN_PROCESS.append(message.from_user.username)
        tip = None
        donateTx = None
        try:
            CoinAddress = get_donate_address(COIN_NAME)
            try:
                if coin_family in ["TRTL", "BCN"]:
                    donateTx = await store.sql_donate(message.from_user.username, get_donate_address(COIN_NAME), real_amount, COIN_NAME, "TELEGRAM")
                elif coin_family == "XMR":
                    donateTx = await store.sql_mv_xmr_single(message.from_user.username, get_donate_account_name(COIN_NAME), real_amount, COIN_NAME, "DONATE", "TELEGRAM")
                elif coin_family == "NANO":
                    donateTx = await store.sql_mv_nano_single(message.from_user.username, get_donate_account_name(COIN_NAME), real_amount, COIN_NAME, "DONATE", "TELEGRAM")
                elif coin_family == "DOGE":
                    donateTx = await store.sql_mv_doge_single(message.from_user.username, get_donate_account_name(COIN_NAME), real_amount, COIN_NAME, "DONATE", "TELEGRAM")
                elif coin_family == "ERC-20":
                    token_info = await store.get_token_info(COIN_NAME)
                    donateTx = await store.sql_mv_erc_single(message.from_user.username, token_info['donate_name'], real_amount, COIN_NAME, "DONATE", token_info['contract'], "TELEGRAM")
            except Exception as e:
                await logchanbot(traceback.format_exc())
            message_text = text(bold("You donated:") + markdown.pre("\nAmount: {}{}".format(num_format_coin(real_amount, COIN_NAME), COIN_NAME)), "Thank you very much.")
            await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
            await logchanbot(f'[Telegram] TipBot got donation: {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}')
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if message.from_user.username in WITHDRAW_IN_PROCESS:
            WITHDRAW_IN_PROCESS.remove(message.from_user.username)
    else:
        message_text = text(bold("You have another tx in progress.\n"))
        await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)
        return


@dp.message_handler(commands='about')
async def start_cmd_handler(message: types.Message):
    reply_text = text(bold("Thank you for checking:\n"),
                      markdown.pre("\nTwitter dev: https://twitter.com/wrkzdev\n"
                                   "Discord: https://chat.wrkz.work\n"
                                   "Telegram: https://t.me/wrkzcoinchat\n"
                                   "Donation: via /donate amount coin_name\n"
                                   "Run by WrkzCoin team\n"))
    await message.reply(reply_text, parse_mode=ParseMode.MARKDOWN)
    return


@dp.message_handler()
async def all_msg_handler(message: types.Message):
    # pressing of a KeyboardButton is the same as sending the regular message with the same text
    # so, to handle the responses from the keyboard, we need to use a message_handler
    # in real bot, it's better to define message_handler(text="...") for each button
    # but here for the simplicity only one handler is defined

    button_text = message.text
    logger.debug('The answer is %r', button_text)  # print the text we've got

    reply_command = True
    if button_text.upper() == 'XXXX':
        reply_text = "balance start"
    else:
        reply_text = "Unknown Command!"
        reply_command = False
    if reply_command:
        await message.reply(reply_text)
    # with message, we send types.ReplyKeyboardRemove() to hide the keyboard



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


# Notify user
async def notify_new_tx_user():
    INTERVAL_EACH = config.interval.notify_tx
    while True:
        pending_tx = await store.sql_get_new_tx_table('NO', 'NO')
        #print(pending_tx)
        if pending_tx and len(pending_tx) > 0:
            # let's notify_new_tx_user
            for eachTx in pending_tx:
                try:
                    user_tx = None
                    if len(eachTx['payment_id']) > 0:
                        user_tx = await store.sql_get_userwallet_by_paymentid(eachTx['payment_id'], eachTx['coin_name'], 'TELEGRAM')
                    if user_tx:
                        #get_user_chat = await bot.get_chat_member()
                        is_notify_failed = False
                        to_user = user_tx['chat_id']
                        message_text = None
                        if eachTx['coin_name'] in ENABLE_COIN_NANO:
                            message_text = "You got a new deposit: " + "Coin: {}\nAmount: {}".format(eachTx['coin_name'], num_format_coin(eachTx['amount'], eachTx['coin_name']))  
                        elif eachTx['coin_name'] not in ENABLE_COIN_DOGE:
                            message_text = text(bold(f"You got a new deposit {eachTx['coin_name']}:\n"), markdown.pre("\nTx: {}\nAmount: {}\nHeight: {:,.0f}".format(eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name']), eachTx['height'])))
                        else:
                            message_text = text(bold(f"You got a new deposit {eachTx['coin_name']}:\n"), markdown.pre("\nTx: {}\nAmount: {}\nBlock Hash: {}".format(eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name']), eachTx['blockhash'])))
                        try:
                            send_msg = await bot.send_message(chat_id=to_user, text=message_text, parse_mode=ParseMode.MARKDOWN)
                            if send_msg:
                                is_notify_failed = False
                            else:
                                await logchanbot("[Telegram] Can not send message to {}".format(user_tx['chat_id']))
                                is_notify_failed = True
                        except exceptions.BotBlocked:
                            await logchanbot(f"[Telegram] Target [ID:{to_user}]: blocked by user")
                        except exceptions.ChatNotFound:
                            await logchanbot(f"[Telegram] Target [ID:{to_user}]: invalid user ID")
                        except exceptions.RetryAfter as e:
                            await logchanbot(f"[Telegram] Target [ID:{to_user}]: Flood limit is exceeded. Sleep {e.timeout} seconds")
                            await asyncio.sleep(e.timeout)
                            return await bot.send_message(chat_id=to_user, text=message_text)  # Recursive call
                        except exceptions.UserDeactivated:
                            await logchanbot(f"[Telegram] Target [ID:{to_user}]: user is deactivated")
                        except exceptions.TelegramAPIError:
                            await logchanbot(f"[Telegram] Target [ID:{to_user}]: failed")
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                            is_notify_failed = True
                        finally:
                             update_notify_tx = await store.sql_update_notify_tx_table(eachTx['payment_id'], user_tx['user_id'], user_tx['user_id'], 'YES', 'NO' if is_notify_failed == False else 'YES')
 
                except Exception as e:
                    print(traceback.format_exc())
                    await logchanbot(traceback.format_exc())
        await asyncio.sleep(INTERVAL_EACH)


async def bot_faucet():
    get_game_stat = await store.sql_game_stat()
    table_data = [
        ['TICKER', 'Available', 'Claimed / Game']
    ]
    for COIN_NAME in [coinItem.upper() for coinItem in FAUCET_COINS]:
        sum_sub = 0
        wallet = await store.sql_get_userwallet('teletip_bot', COIN_NAME, 'TELEGRAM')
        if wallet is None:
            if COIN_NAME in ENABLE_COIN_ERC:
                w = create_eth_wallet()
                userregister = await store.sql_register_user(message.from_user.username, COIN_NAME, 'TELEGRAM', message.chat.id, w)
            else:
                userregister = await store.sql_register_user(message.from_user.username, COIN_NAME, 'TELEGRAM', message.chat.id)
        userdata_balance = await store.sql_user_balance('teletip_bot', COIN_NAME)
        xfer_in = 0
        if COIN_NAME not in ENABLE_COIN_ERC:
            xfer_in = await store.sql_user_balance_get_xfer_in('teletip_bot', COIN_NAME, 'TELEGRAM')
        if COIN_NAME in ENABLE_COIN_DOGE+ENABLE_COIN_ERC:
            actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
        elif COIN_NAME in ENABLE_COIN_NANO:
            actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
            actual_balance = round(actual_balance / get_decimal(COIN_NAME), 6) * get_decimal(COIN_NAME)
        else:
            actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
        if COIN_NAME in ENABLE_COIN_ERC:
            coin_family = "ERC-20"
        else:
            coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")           
        try:
            if COIN_NAME in get_game_stat and coin_family in ["TRTL", "BCN", "XMR", "NANO"]:
                actual_balance = actual_balance - int(get_game_stat[COIN_NAME])
                sum_sub = int(get_game_stat[COIN_NAME])
            elif COIN_NAME in get_game_stat and coin_family in ["DOGE", "ERC-20"]:
                actual_balance = actual_balance - float(get_game_stat[COIN_NAME])
                sum_sub = float(get_game_stat[COIN_NAME])
        except Exception as e:
            await logchanbot(traceback.format_exc())
        balance_actual = num_format_coin(actual_balance, COIN_NAME)
        get_claimed_count = await store.sql_faucet_sum_count_claimed(COIN_NAME)
        if coin_family in ["TRTL", "BCN", "XMR", "NANO"]:
            sub_claim = num_format_coin(int(get_claimed_count['claimed']) + sum_sub, COIN_NAME) if get_claimed_count['count'] > 0 else f"0.00{COIN_NAME}"
        elif coin_family in ["DOGE", "ERC-20"]:
            sub_claim = num_format_coin(float(get_claimed_count['claimed']) + sum_sub, COIN_NAME) if get_claimed_count['count'] > 0 else f"0.00{COIN_NAME}"
        if actual_balance != 0:
            table_data.append([COIN_NAME, balance_actual, sub_claim])
        else:
            table_data.append([COIN_NAME, '0', sub_claim])
    table = AsciiTable(table_data)
    table.padding_left = 0
    table.padding_right = 0
    return table.table


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


def seconds_str(time: float):
    # day = time // (24 * 3600)
    # time = time % (24 * 3600)
    hour = time // 3600
    time %= 3600
    minutes = time // 60
    time %= 60
    seconds = time
    return "{:02d}:{:02d}:{:02d}".format(hour, minutes, seconds)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(notify_new_tx_user())
    executor.start_polling(dp, skip_updates=True)
