import logging

from aiogram import Bot, types
from aiogram.utils import exceptions, executor
from aiogram.utils.emoji import emojize
from aiogram.dispatcher import Dispatcher
from aiogram.types.message import ContentType
from aiogram.utils.markdown import text, bold, italic, code, pre
from aiogram.types import ParseMode, InputMediaPhoto, InputMediaVideo, ChatActions
from config import config
from wallet import *
import store, daemonrpc_client, addressvalidation, walletapi
import sys, traceback
# redis
import redis, json
import uuid

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
MAINTENANCE_COIN = config.Maintenance_Coin.split(",")

# faucet enabled coin. The faucet balance is taken from TipBot's own balance
FAUCET_COINS = config.Enable_Faucet_Coin.split(",")
FAUCET_COINS_ROUND_NUMBERS = config.Enable_Faucet_Coin_round_number.split(",")
# DOGE will divide by 10 after random
FAUCET_MINMAX = {
    "WRKZ": [1000, 2000],
    "DEGO": [2500, 10000],
    "TRTL": [15, 25],
    "DOGE": [1, 3],
    "BTCMZ": [2500, 5000]
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


@dp.message_handler(commands='start')
async def start_cmd_handler(message: types.Message):
    keyboard_markup = types.ReplyKeyboardMarkup(row_width=3)
    # default row_width is 3, so here we can omit it actually
    # kept for clearness

    btns_text = ('/bal', '/register')
    keyboard_markup.row(*(types.KeyboardButton(text) for text in btns_text))
    # adds buttons as a new row to the existing keyboard
    # the behaviour doesn't depend on row_width attribute

    more_btns_text = (
        "/send",
        "/tip",
        "/deposit",
        "/coininfo",
        "/donate",
        "/about",
    )
    keyboard_markup.add(*(types.KeyboardButton(text) for text in more_btns_text))
    # adds buttons. New rows are formed according to row_width parameter

    await message.reply("Hello, Welcome to TipBot by WrkzCoin team!", reply_markup=keyboard_markup)


@dp.message_handler(commands='deposit')
async def start_cmd_handler(message: types.Message):
    content = ' '.join(message.text.split())
    args = content.split(" ")
    if message.chat.type != "private":
        return
    if message.from_user.username is None:
        reply_text = "I can not get your username."
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
        return
    if len(args) == 1:
        keyboard_markup = types.ReplyKeyboardMarkup(row_width=3)
        # default row_width is 3, so here we can omit it actually
        # kept for clearness

        btns_text1 = tuple(["/deposit " + item for item in ENABLE_COIN])
        btns_text2 = tuple(["/deposit " + item for item in ENABLE_COIN_DOGE])

        more_btns_text = (
            "/start",
        )
        keyboard_markup.add(*(types.KeyboardButton(text) for text in more_btns_text))
        keyboard_markup.row(*(types.KeyboardButton(text) for text in btns_text1))
        keyboard_markup.row(*(types.KeyboardButton(text) for text in btns_text2))

        await message.reply("Select coin to display information or type /deposit coin_name", reply_markup=keyboard_markup)
    else:
        # /deposit WRKZ
        COIN_NAME = args[1].upper()
        if COIN_NAME not in ENABLE_COIN + ENABLE_COIN_DOGE:
            message_text = text(bold("Invalid command /deposit"))
            await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                parse_mode=ParseMode.MARKDOWN)
            return
        else:
            if not is_coin_depositable(COIN_NAME):
                message_text = text(bold(f"DEPOSITING is currently disable for {COIN_NAME}."))
                await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                    parse_mode=ParseMode.MARKDOWN)
                return

            user_addr = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')
            if user_addr is None:
                userregister = await store.sql_register_user(message.from_user.username, COIN_NAME, 'TELEGRAM', message.chat.id)
                user_addr = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')

            message_text = text(bold(f"{COIN_NAME} INFO:\n\n"),
                                "Deposit: ", code(user_addr['balance_wallet_address']), "\n\n",
                                "Registered: ", code(user_addr['user_wallet_address'] if ('user_wallet_address' in user_addr) and user_addr['user_wallet_address'] else "NONE, Please register."))
            await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                parse_mode=ParseMode.MARKDOWN)
            return


@dp.message_handler(commands='coininfo')
async def start_cmd_handler(message: types.Message):
    content = ' '.join(message.text.split())
    args = content.split(" ")

    if len(args) == 1:
        keyboard_markup = types.ReplyKeyboardMarkup(row_width=3)
        # default row_width is 3, so here we can omit it actually
        # kept for clearness

        btns_text1 = tuple(["/coininfo " + item for item in ENABLE_COIN])
        btns_text2 = tuple(["/coininfo " + item for item in ENABLE_COIN_DOGE])
        more_btns_text = (
            "/start",
        )
        keyboard_markup.add(*(types.KeyboardButton(text) for text in more_btns_text))
        keyboard_markup.row(*(types.KeyboardButton(text) for text in btns_text1))
        keyboard_markup.row(*(types.KeyboardButton(text) for text in btns_text2))

        await message.reply("Select coin to display information", reply_markup=keyboard_markup)
    else:
        # /coininfo WRKZ
        COIN_NAME = args[1].upper()
        if COIN_NAME not in ENABLE_COIN + ENABLE_COIN_DOGE:
            message_text = text(bold("Invalid command /coininfo"))
            await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                parse_mode=ParseMode.MARKDOWN)
            return
        else:
            response_text = ""
            try:
                openRedis()
                if redis_conn and redis_conn.exists(f'TIPBOT:DAEMON_HEIGHT_{COIN_NAME}'):
                    height = int(redis_conn.get(f'TIPBOT:DAEMON_HEIGHT_{COIN_NAME}'))
                    response_text = "\nHeight: {:,.0f}".format(height) + "\n"
                response_text += "Confirmation: {} Blocks".format(get_confirm_depth(COIN_NAME)) + "\n"
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
                get_tip_min_max = "Tip Min/Max:\n   " + num_format_coin(get_min_mv_amount(COIN_NAME), COIN_NAME) + " / " + num_format_coin(get_max_mv_amount(COIN_NAME), COIN_NAME) + COIN_NAME
                response_text += get_tip_min_max + "\n"
                get_tx_min_max = "Withdraw Min/Max:\n   " + num_format_coin(get_min_tx_amount(COIN_NAME), COIN_NAME) + " / " + num_format_coin(get_max_tx_amount(COIN_NAME), COIN_NAME) + COIN_NAME
                response_text += get_tx_min_max
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            message_text = text(bold("[ COIN INFO {} ]".format(COIN_NAME)), "\n", code(response_text))
            await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                parse_mode=ParseMode.MARKDOWN)
            return


@dp.message_handler(commands='bal')
async def start_cmd_handler(message: types.Message):
    content = ' '.join(message.text.split())
    args = content.split(" ")
    if message.chat.type != "private":
        return
    if message.from_user.username is None:
        reply_text = "I can not get your username."
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
        return
    if len(args) == 1:
        keyboard_markup = types.ReplyKeyboardMarkup(row_width=3)
        # default row_width is 3, so here we can omit it actually
        # kept for clearness

        btns_text1 = tuple(["/bal " + item for item in ENABLE_COIN])
        btns_text2 = tuple(["/bal " + item for item in ENABLE_COIN_DOGE + ["list"]])

        more_btns_text = (
            "/start",
        )
        keyboard_markup.add(*(types.KeyboardButton(text) for text in more_btns_text))
        keyboard_markup.row(*(types.KeyboardButton(text) for text in btns_text1))
        keyboard_markup.row(*(types.KeyboardButton(text) for text in btns_text2))

        await message.reply("Select coin to display information", reply_markup=keyboard_markup)
    else:
        # /bal WRKZ
        COIN_NAME = args[1].upper()
        if COIN_NAME == "LIST":
            message_text = ""
            coin_str = "\n"
            for COIN_ITEM in [coinItem.upper() for coinItem in ENABLE_COIN + ENABLE_COIN_DOGE]:
                COIN_DEC = get_decimal(COIN_ITEM)
                wallet = await store.sql_get_userwallet(message.from_user.username, COIN_ITEM, 'TELEGRAM')
                if wallet is None:
                    userregister = await store.sql_register_user(message.from_user.username, COIN_ITEM, 'TELEGRAM', message.chat.id)
                    wallet = await store.sql_get_userwallet(message.from_user.username, COIN_ITEM, 'TELEGRAM')
                coin_family = getattr(getattr(config,"daemon"+COIN_ITEM),"coin_family","TRTL")
                if coin_family == "TRTL":
                    userdata_balance = await store.sql_cnoff_balance(message.from_user.username, COIN_ITEM, 'TELEGRAM')
                    wallet['actual_balance'] = wallet['actual_balance'] + int(userdata_balance['Adjust'])
                elif coin_family == "DOGE":
                    userdata_balance = await store.sql_doge_balance(message.from_user.username, COIN_ITEM, 'TELEGRAM')
                    wallet['actual_balance'] = wallet['actual_balance'] + float(userdata_balance['Adjust'])
                balance_actual = num_format_coin(wallet['actual_balance'], COIN_ITEM)
                coin_str += COIN_ITEM + ": " + balance_actual + COIN_ITEM + "\n"
            message_text = text(bold(f'[YOUR BALANCE SHEET]:\n'),
                                code(coin_str))
            await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                parse_mode=ParseMode.MARKDOWN)
            return
        elif COIN_NAME not in ENABLE_COIN + ENABLE_COIN_DOGE:
            message_text = text(bold(f"Invalid coin /bal {COIN_NAME}"))
            await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                parse_mode=ParseMode.MARKDOWN)
            return
        else:    
            # get balance user for a specific coin
            coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
            userwallet = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')

            if userwallet is None:
                userwallet = await store.sql_register_user(message.from_user.username, COIN_NAME, 'TELEGRAM', message.chat.id)
                userwallet = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')
            if coin_family == "TRTL":
                userdata_balance = await store.sql_cnoff_balance(message.from_user.username, COIN_NAME, 'TELEGRAM')
                userwallet['actual_balance'] = userwallet['actual_balance'] + int(userdata_balance['Adjust'])
            elif coin_family == "DOGE":
                userdata_balance = await store.sql_doge_balance(message.from_user.username, COIN_NAME, 'TELEGRAM')
                userwallet['actual_balance'] = userwallet['actual_balance'] + float(userdata_balance['Adjust'])

            message_text = text(bold(f'[YOUR {COIN_NAME} BALANCE]:\n'),
                                "Available: ", code(num_format_coin(userwallet['actual_balance'], COIN_NAME) + COIN_NAME))
            await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                parse_mode=ParseMode.MARKDOWN)
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
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
        return
    if len(args) == 1:
        reply_text = "Please mention a bot username starting with @."
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
        return
    if len(args) == 2:
        # /botbal @botusername
        # Find user if exist
        user_to = None
        if len(args) == 2 and args[1].startswith("@"):
            user_to = (args[1])[1:]
        else:
            reply_text = "Please mention a bot username starting with @."
            await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
            return
            
        if user_to is None:
            reply_text = "I can not get bot username."
            await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
            return
        else:
            if user_to != "teletip_bot":
                reply_text = f"Unavailable for this bot {user_to}."
                await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
                return
            else:
                message_text = ""
                coin_str = "\n"
                for COIN_ITEM in [coinItem.upper() for coinItem in ENABLE_COIN + ENABLE_COIN_DOGE]:
                    COIN_DEC = get_decimal(COIN_ITEM)
                    wallet = await store.sql_get_userwallet(user_to, COIN_ITEM, 'TELEGRAM')
                    if wallet is None:
                        # this will be public
                        userregister = await store.sql_register_user(user_to, COIN_ITEM, 'TELEGRAM', message.chat.id)
                        wallet = await store.sql_get_userwallet(user_to, COIN_ITEM, 'TELEGRAM')
                    coin_family = getattr(getattr(config,"daemon"+COIN_ITEM),"coin_family","TRTL")
                    if coin_family == "TRTL":
                        userdata_balance = await store.sql_cnoff_balance(user_to, COIN_ITEM, 'TELEGRAM')
                        wallet['actual_balance'] = wallet['actual_balance'] + int(userdata_balance['Adjust'])
                    elif coin_family == "DOGE":
                        userdata_balance = await store.sql_doge_balance(user_to, COIN_ITEM, 'TELEGRAM')
                        wallet['actual_balance'] = wallet['actual_balance'] + float(userdata_balance['Adjust'])
                    balance_actual = num_format_coin(wallet['actual_balance'], COIN_ITEM)
                    coin_str += COIN_ITEM + ": " + balance_actual + COIN_ITEM + "\n"
                message_text = text(bold(f'[@{user_to} BALANCE SHEET]:\n'),
                                    code(coin_str))
                await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                    parse_mode=ParseMode.MARKDOWN)
                return


@dp.message_handler(commands='register')
async def start_cmd_handler(message: types.Message):
    content = ' '.join(message.text.split())
    args = content.split(" ")
    if message.chat.type != "private":
        return
    if message.from_user.username is None:
        reply_text = "I can not get your username."
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
        return
    if len(args) == 1:
        reply_text = "Please use /register YOUR_WALLET_ADDRESS"
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
        return
    else:
        # /register XXXX
        wallet_address = args[1]
        if wallet_address.isalnum() == False:
            message_text = text(bold("Invalid address:\n"),
                                code(wallet_address))
            await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                parse_mode=ParseMode.MARKDOWN)
            return
        else:
            COIN_NAME = await get_cn_coin_from_address(wallet_address)
            if not COIN_NAME:
                message_text = text(bold("Unknown coin name:\n"),
                                    code(wallet_address))
                await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                    parse_mode=ParseMode.MARKDOWN)
                return
            if COIN_NAME not in ENABLE_COIN + ENABLE_COIN_DOGE:
                message_text = text(bold("Invalid or unsupported coin address."))
                await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                    parse_mode=ParseMode.MARKDOWN)
                return
            # get coin family
            coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
            if coin_family == "TRTL":
                addressLength = get_addrlen(COIN_NAME)
                IntaddressLength = 0
                if coin_family == "TRTL" or coin_family == "XMR":
                    IntaddressLength = get_intaddrlen(COIN_NAME)
                if len(wallet_address) == int(addressLength):
                    valid_address = addressvalidation.validate_address_cn(wallet_address, COIN_NAME)
                    if valid_address is None:
                        message_text = text(bold("Invalid address:\n"),
                                            code(wallet_address))
                        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
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
                                                code(wallet_address))
                            await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                                parse_mode=ParseMode.MARKDOWN)
                            return
                        else:
                            message_text = text("Your previous registered address is the same as new address. Action not taken.")
                            await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove())
                            return
                elif len(wallet_address) == int(IntaddressLength): 
                    # Not allowed integrated address
                    message_text = text(bold("Integrated address not allowed:\n"),
                                        code(wallet_address))
                    await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
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
                                            code(wallet_address))
                        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                            parse_mode=ParseMode.MARKDOWN)
                        return
                if user_from['balance_wallet_address'] == wallet_address:
                    message_text = text(bold("Can not register with your deposit address:\n"),
                                        code(wallet_address))
                    await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                        parse_mode=ParseMode.MARKDOWN)
                    return
                elif prev_address and prev_address == wallet_address:
                    message_text = text(bold("Previous and new address is the same:\n"),
                                        code(wallet_address))
                    await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                        parse_mode=ParseMode.MARKDOWN)
                    return
                else:
                    await store.sql_update_user(message.from_user.username, wallet_address, COIN_NAME, 'TELEGRAM')
                    message_text = text(bold("You registered a withdrawn address:\n"),
                                        code(wallet_address))
                    await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                        parse_mode=ParseMode.MARKDOWN)
                    return


@dp.message_handler(commands='tip')
async def start_cmd_handler(message: types.Message):
    if message.from_user.username is None:
        reply_text = "I can not get your username."
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
        return

    content = ' '.join(message.text.split())
    args = content.split(" ")

    if len(args) != 4 and len(args) != 3:
        reply_text = "Please use /tip amount coin_name @telegramuser"
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
        return
    elif len(args) == 3 and message.reply_to_message is None:
        reply_text = "Please use /tip amount coin_name @telegramuser"
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
        return

    COIN_NAME = args[2].upper()
    if COIN_NAME not in ENABLE_COIN + ENABLE_COIN_DOGE:
        message_text = text(bold(f"Invalid {COIN_NAME}\n\n"), 
                            "Supported coins: ", code(", ".join(ENABLE_COIN + ENABLE_COIN_DOGE)))
        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                            parse_mode=ParseMode.MARKDOWN)
        return

    if not is_coin_tipable(COIN_NAME):
        message_text = text(bold(f"TIPPING is currently disable for {COIN_NAME}."))
        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                            parse_mode=ParseMode.MARKDOWN)
        return


    amount = args[1].replace(",", "")
    try:
        amount = float(amount)
    except ValueError:
        message_text = text(bold("Invalid amount."))
        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
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
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
        return
    else:
        # if tip to himself
        if user_to == message.from_user.username:
            reply_text = "You can not tip to yourself."
            await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
            return
            
        to_teleuser = await store.sql_get_userwallet(user_to, COIN_NAME, 'TELEGRAM')
        if to_teleuser is None:
            message_text = text(bold(f"Can not find user {user_to} in our DB."))
            await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                parse_mode=ParseMode.MARKDOWN)
            return
        else:
            to_user = to_teleuser['chat_id']
            coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
            user_from = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')
            if coin_family == "TRTL":
                userdata_balance = await store.sql_cnoff_balance(message.from_user.username, COIN_NAME, 'TELEGRAM')
                user_from['actual_balance'] = user_from['actual_balance'] + int(userdata_balance['Adjust'])
            elif coin_family == "DOGE":
                userdata_balance = await store.sql_doge_balance(message.from_user.username, COIN_NAME, 'TELEGRAM')
                user_from['actual_balance'] = user_from['actual_balance'] + float(userdata_balance['Adjust'])
            COIN_DEC = get_decimal(COIN_NAME)
            real_amount = int(amount * COIN_DEC) if (coin_family == "TRTL" or coin_family == "XMR") else amount
            MinTx = get_min_mv_amount(COIN_NAME)
            MaxTX = get_max_mv_amount(COIN_NAME)

            message_text = ''
            valid_amount = True
            if real_amount > user_from['actual_balance']:
                message_text = 'Insufficient balance to send tip of ' + num_format_coin(real_amount, COIN_NAME) + COIN_NAME + ' to ' + args[3]
                valid_amount = False
            elif real_amount > MaxTX:
                message_text = 'Transactions cannot be bigger than ' + num_format_coin(MaxTX, COIN_NAME) + COIN_NAME
                valid_amount = False
            elif real_amount < MinTx:
                message_text = 'Transactions cannot be bigger than ' + num_format_coin(MinTx, COIN_NAME) + COIN_NAME
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
                        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                            parse_mode=ParseMode.MARKDOWN)
                        return
                    if coin_family == "TRTL":
                        tip = await store.sql_send_tip(message.from_user.username, user_to, real_amount, 'TIP', COIN_NAME, 'TELEGRAM')
                    elif coin_family == "DOGE":
                        tip = await store.sql_mv_doge_single(message.from_user.username, user_to, real_amount, COIN_NAME, 'TIP', 'TELEGRAM')

                    message_text = text(bold(f"You sent a new tip to {user_to}:\n\n"), code("Amount: {}{}".format(num_format_coin(real_amount, COIN_NAME), COIN_NAME)))
                    to_message_text = text(bold(f"You got a new tip from {message.from_user.username}:\n\n"), code("Amount: {}{}".format(num_format_coin(real_amount, COIN_NAME), COIN_NAME)))
                    if user_to in ["teletip_bot"]:
                        to_message_text = to_message_text.replace("You ", f"@{user_to} ")
                    try:
                        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                                            parse_mode=ParseMode.MARKDOWN)
                        send_msg = await bot.send_message(chat_id=to_user, text=to_message_text, parse_mode=ParseMode.MARKDOWN)
                    except exceptions.BotBlocked:
                        print(f"Target [ID:{to_user}]: blocked by user")
                    except exceptions.ChatNotFound:
                        print(f"Target [ID:{to_user}]: invalid user ID")
                    except exceptions.RetryAfter as e:
                        print(f"Target [ID:{to_user}]: Flood limit is exceeded. Sleep {e.timeout} seconds.")
                        await asyncio.sleep(e.timeout)
                        return await bot.send_message(chat_id=to_user, text=message_text, parse_mode=ParseMode.MARKDOWN)  # Recursive call
                    except exceptions.UserDeactivated:
                        print(f"Target [ID:{to_user}]: user is deactivated")
                    except exceptions.TelegramAPIError:
                        print(f"Target [ID:{to_user}]: failed")
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                if message.from_user.username in WITHDRAW_IN_PROCESS:
                    WITHDRAW_IN_PROCESS.remove(message.from_user.username)
                return


@dp.message_handler(commands='send')
async def start_cmd_handler(message: types.Message):
    if message.from_user.username is None:
        reply_text = "I can not get your username."
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
        return

    content = ' '.join(message.text.split())
    args = content.split(" ")
    if len(args) != 4:
        reply_text = "Please use /send amount coin_name address"
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
        return
   
    COIN_NAME = args[2].upper()
    if COIN_NAME not in ENABLE_COIN + ENABLE_COIN_DOGE:
        message_text = text(bold(f"Invalid {COIN_NAME}\n\n"), 
                            "Supported coins: ", code(", ".join(ENABLE_COIN + ENABLE_COIN_DOGE)))
        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                            parse_mode=ParseMode.MARKDOWN)
        return

    if not is_coin_txable(COIN_NAME):
        message_text = text(bold(f"TX is currently disable for {COIN_NAME}."))
        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                            parse_mode=ParseMode.MARKDOWN)
        return

    amount = args[1].replace(",", "")
    try:
        amount = float(amount)
    except ValueError:
        message_text = text(bold("Invalid amount."))
        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                            parse_mode=ParseMode.MARKDOWN)
        return

    # add redis action
    random_string = str(uuid.uuid4())
    await add_tx_action_redis(json.dumps([random_string, "SEND", message.from_user.username, message.from_user.username, float("%.3f" % time.time()), message.text, "TELEGRAM", "START"]), False)

    wallet_address = args[3]
    if wallet_address.isalnum() == False:
        message_text = text(bold("Invalid address:\n"),
                            code(wallet_address))
        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                            parse_mode=ParseMode.MARKDOWN)
        return
    else:
        COIN_NAME_CHECK = await get_cn_coin_from_address(wallet_address)
        if not COIN_NAME_CHECK:
            message_text = text(bold("Unknown coin name:\n"),
                                code(wallet_address))
            await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                parse_mode=ParseMode.MARKDOWN)
            return
        elif COIN_NAME_CHECK != COIN_NAME:
            message_text = text(bold("Error getting address and coin name from:\n"),
                                code(wallet_address))
            await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                parse_mode=ParseMode.MARKDOWN)
            return
        # get coin family
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
        if coin_family == "TRTL" or coin_family == "DOGE":
            addressLength = get_addrlen(COIN_NAME)
            IntaddressLength = 0
            paymentid = None
            CoinAddress = None

            user_from = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')
            if coin_family == "TRTL":
                userdata_balance = await store.sql_cnoff_balance(message.from_user.username, COIN_NAME, 'TELEGRAM')
                user_from['actual_balance'] = user_from['actual_balance'] + int(userdata_balance['Adjust'])
            elif coin_family == "DOGE":
                userdata_balance = await store.sql_doge_balance(message.from_user.username, COIN_NAME, 'TELEGRAM')
                user_from['actual_balance'] = user_from['actual_balance'] + float(userdata_balance['Adjust'])

            COIN_DEC = get_decimal(COIN_NAME)
            real_amount = int(amount * COIN_DEC) if (coin_family == "TRTL" or coin_family == "XMR") else amount
            MinTx = get_min_tx_amount(COIN_NAME)
            MaxTX = get_max_tx_amount(COIN_NAME)
            NetFee = get_reserved_fee(coin = COIN_NAME)
            message_text = ''
            valid_amount = True
            if real_amount + NetFee > user_from['actual_balance']:
                message_text = 'Not enough reserved fee / Insufficient balance to send ' + num_format_coin(real_amount, COIN_NAME) + COIN_NAME + ' to ' + wallet_address
                valid_amount = False
            elif real_amount > MaxTX:
                message_text = 'Transactions cannot be bigger than ' + num_format_coin(MaxTX, COIN_NAME) + COIN_NAME
                valid_amount = False
            elif real_amount < MinTx:
                message_text = 'Transactions cannot be bigger than ' + num_format_coin(MinTx, COIN_NAME) + COIN_NAME
                valid_amount = False
            if valid_amount == False:
                await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                    parse_mode=ParseMode.MARKDOWN)
                return

            if coin_family == "TRTL" or coin_family == "XMR":
                IntaddressLength = get_intaddrlen(COIN_NAME)
                if len(wallet_address) == int(addressLength):
                    valid_address = addressvalidation.validate_address_cn(wallet_address, COIN_NAME)
                    if valid_address is None:
                        message_text = text(bold("Invalid address:\n"),
                                            code(wallet_address))
                        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                            parse_mode=ParseMode.MARKDOWN)
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
                        message_text = text(bold("Invalid address:\n"),
                                            code(wallet_address))
                        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                            parse_mode=ParseMode.MARKDOWN)
                        return
                    elif len(valid_address) == 2:
                        address_paymentID = wallet_address
                        CoinAddress = valid_address['address']
                        paymentid = valid_address['integrated_id']

                main_address = getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
                if CoinAddress and CoinAddress == main_address:
                    # Not allow to send to own main address
                    message_text = text(bold("Can not send to:\n"),
                                        code(wallet_address))
                    await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                        parse_mode=ParseMode.MARKDOWN)
                    return
                else:
                    tip = None
                    if message.from_user.username not in WITHDRAW_IN_PROCESS:
                        WITHDRAW_IN_PROCESS.append(message.from_user.username)
                    else:
                        message_text = text(bold("You have another tx in progress.\n"))
                        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                            parse_mode=ParseMode.MARKDOWN)
                        return

                    if paymentid:
                        try:
                            tip = await store.sql_send_tip_Ex_id(message.from_user.username, CoinAddress, real_amount, paymentid, COIN_NAME, 'TELEGRAM')
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                    else:
                        try:
                            tip = await store.sql_send_tip_Ex(message.from_user.username, CoinAddress, real_amount, COIN_NAME, 'TELEGRAM')
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                    if message.from_user.username in WITHDRAW_IN_PROCESS:
                        WITHDRAW_IN_PROCESS.remove(message.from_user.username)
                    if tip:
                        tip_tx_tipper = "Transaction hash: {}".format(tip['transactionHash'])
                        tip_tx_tipper += "\nTx Fee: {}{}".format(num_format_coin(tip['fee'], COIN_NAME), COIN_NAME)
                        await add_tx_action_redis(json.dumps([random_string, "SEND", message.from_user.username, message.from_user.username, float("%.3f" % time.time()), message.text, "TELEGRAM", "COMPLETE"]), False)
                        message_text = text(bold(f"You have sent {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}:\n"),
                                            code(tip_tx_tipper))
                        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                            parse_mode=ParseMode.MARKDOWN)
                        return
                    else:
                        message_text = text(bold(f"Internal error for sending {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}"))
                        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                            parse_mode=ParseMode.MARKDOWN)
                        return
            elif coin_family == "DOGE":
                valid_address = await doge_validaddress(str(wallet_address), COIN_NAME)
                if 'isvalid' in valid_address:
                    if str(valid_address['isvalid']) != "True":
                        message_text = text(bold("Invalid address:\n"),
                                            code(wallet_address))
                        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                            parse_mode=ParseMode.MARKDOWN)
                        return
                    else:
                        sendTx = None
                        if message.from_user.username not in WITHDRAW_IN_PROCESS:
                            WITHDRAW_IN_PROCESS.append(message.from_user.username)
                        else:
                            message_text = text(bold("You have another tx in progress.\n"))
                            await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                                parse_mode=ParseMode.MARKDOWN)
                            return

                        try:
                            NetFee = get_tx_fee(coin = COIN_NAME)
                            sendTx = await store.sql_external_doge_single(message.from_user.username, real_amount, NetFee, wallet_address, COIN_NAME, 'SEND', 'TELEGRAM')
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)

                        if message.from_user.username in WITHDRAW_IN_PROCESS:
                            WITHDRAW_IN_PROCESS.remove(message.from_user.username)
                        if sendTx:
                            tx_text = "Transaction hash: {}".format(sendTx)
                            tx_text += "\nNetwork fee deducted from the amount."
                            
                            message_text = text(bold(f"You have sent {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}:\n"),
                                                code(tx_text))
                            await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                                parse_mode=ParseMode.MARKDOWN)
                            return
                        else:
                            message_text = text(bold(f"Internal error for sending {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}"))
                            await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                                parse_mode=ParseMode.MARKDOWN)
                            return



@dp.message_handler(commands='withdraw')
async def start_cmd_handler(message: types.Message):
    if message.from_user.username is None:
        reply_text = "I can not get your username."
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
        return

    content = ' '.join(message.text.split())
    args = content.split(" ")
    if len(args) != 3:
        reply_text = "Please use /withdraw amount coin_name"
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
        return
   
    COIN_NAME = args[2].upper()
    if COIN_NAME not in ENABLE_COIN + ENABLE_COIN_DOGE:
        message_text = text(bold(f"Invalid {COIN_NAME}\n\n"), 
                            "Supported coins: ", code(", ".join(ENABLE_COIN + ENABLE_COIN_DOGE)))
        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                            parse_mode=ParseMode.MARKDOWN)
        return

    if not is_coin_txable(COIN_NAME):
        message_text = text(bold(f"TX is currently disable for {COIN_NAME}."))
        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                            parse_mode=ParseMode.MARKDOWN)
        return

    amount = args[1].replace(",", "")
    try:
        amount = float(amount)
    except ValueError:
        message_text = text(bold("Invalid amount."))
        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                            parse_mode=ParseMode.MARKDOWN)
        return

    # add redis action
    random_string = str(uuid.uuid4())
    await add_tx_action_redis(json.dumps([random_string, "WITHDRAW", message.from_user.username, message.from_user.username, float("%.3f" % time.time()), message.text, "TELEGRAM", "START"]), False)

    # get coin family
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    user_from = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')
    if coin_family == "TRTL":
        userdata_balance = await store.sql_cnoff_balance(message.from_user.username, COIN_NAME, 'TELEGRAM')
        user_from['actual_balance'] = user_from['actual_balance'] + int(userdata_balance['Adjust'])
    elif coin_family == "DOGE":
        userdata_balance = await store.sql_doge_balance(message.from_user.username, COIN_NAME, 'TELEGRAM')
        user_from['actual_balance'] = user_from['actual_balance'] + float(userdata_balance['Adjust'])

    if user_from is None:
        message_text = text(bold(f"You have not registered {COIN_NAME}"))
        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                            parse_mode=ParseMode.MARKDOWN)
        return
    elif user_from and user_from['user_wallet_address'] is None:
        message_text = text(bold(f"You have not registered {COIN_NAME}"))
        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                            parse_mode=ParseMode.MARKDOWN)
        return
    elif user_from['user_wallet_address']:
        wallet_address = user_from['user_wallet_address']
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC) if (coin_family == "TRTL" or coin_family == "XMR") else amount
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        NetFee = get_reserved_fee(coin = COIN_NAME)
        message_text = ''
        valid_amount = True
        if real_amount + NetFee > user_from['actual_balance']:
            message_text = 'Not enough reserved fee / Insufficient balance to withdraw ' + num_format_coin(real_amount, COIN_NAME) + COIN_NAME + ' to ' + wallet_address
            valid_amount = False
        elif real_amount > MaxTX:
            message_text = 'Transactions cannot be bigger than ' + num_format_coin(MaxTX, COIN_NAME) + COIN_NAME
            valid_amount = False
        elif real_amount < MinTx:
            message_text = 'Transactions cannot be bigger than ' + num_format_coin(MinTx, COIN_NAME) + COIN_NAME
            valid_amount = False
        if valid_amount == False:
            await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                parse_mode=ParseMode.MARKDOWN)
            return
        
        if coin_family == "TRTL":
            main_address = getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
            if wallet_address and wallet_address == main_address:
                # Not allow to send to own main address
                message_text = text(bold("Can not send to:\n"),
                                    code(wallet_address))
                await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                    parse_mode=ParseMode.MARKDOWN)
                return
            else:
                tip = None
                if message.from_user.username not in WITHDRAW_IN_PROCESS:
                    WITHDRAW_IN_PROCESS.append(message.from_user.username)
                else:
                    message_text = text(bold("You have another tx in progress.\n"))
                    await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                        parse_mode=ParseMode.MARKDOWN)
                    return

                try:
                    tip = await store.sql_withdraw(message.from_user.username, real_amount, COIN_NAME, 'TELEGRAM')
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)

                if message.from_user.username in WITHDRAW_IN_PROCESS:
                    WITHDRAW_IN_PROCESS.remove(message.from_user.username)
                if tip:
                    tip_tx_tipper = "Transaction hash: {}".format(tip['transactionHash'])
                    tip_tx_tipper += "\nTx Fee: {}{}".format(num_format_coin(tip['fee'], COIN_NAME), COIN_NAME)
                    await add_tx_action_redis(json.dumps([random_string, "WITHDRAW", message.from_user.username, message.from_user.username, float("%.3f" % time.time()), message.text, "TELEGRAM", "COMPLETE"]), False)
                    message_text = text(bold(f"You have withdrawn {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}:\n"),
                                        code(tip_tx_tipper))
                    await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                        parse_mode=ParseMode.MARKDOWN)
                    return
                else:
                    message_text = text(bold(f"Internal error for sending {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}"))
                    await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                        parse_mode=ParseMode.MARKDOWN)
                    return
        elif coin_family == "DOGE":
            withdrawTx = None
            if message.from_user.username not in WITHDRAW_IN_PROCESS:
                WITHDRAW_IN_PROCESS.append(message.from_user.username)
            else:
                message_text = text(bold("You have another tx in progress.\n"))
                await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                    parse_mode=ParseMode.MARKDOWN)
                return

            try:
                NetFee = get_tx_fee(coin = COIN_NAME)
                withdrawTx = await store.sql_external_doge_single(message.from_user.username, real_amount,
                                                                  NetFee, wallet_address,
                                                                  COIN_NAME, 'WITHDRAW', 'TELEGRAM')
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

            if message.from_user.username in WITHDRAW_IN_PROCESS:
                WITHDRAW_IN_PROCESS.remove(message.from_user.username)
            if withdrawTx:
                tx_text = "Transaction hash: {}\n".format(withdrawTx)
                tx_text += "To: {}".format(wallet_address)
                tx_text += "Network fee deducted from the amount."
                await add_tx_action_redis(json.dumps([random_string, "WITHDRAW", message.from_user.username, message.from_user.username, float("%.3f" % time.time()), message.text, "TELEGRAM", "COMPLETE"]), False)
                message_text = text(bold(f"You have withdrawn {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}:\n"),
                                    code(tx_text))
                await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                    parse_mode=ParseMode.MARKDOWN)
                return
            else:
                message_text = text(bold(f"Internal error for sending {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}"))
                await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                    parse_mode=ParseMode.MARKDOWN)
                return


@dp.message_handler(commands='take')
async def start_cmd_handler(message: types.Message):
    if message.from_user.username is None:
        reply_text = "I can not get your username."
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
        return
    if message.chat.type != "private":
        reply_text = "Can not do here. Please do it privately with my direct message."
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
        return

    # check user claim:
    claim_interval = 24
    check_claimed = store.sql_faucet_checkuser(message.from_user.username, 'TELEGRAM')
    if check_claimed:
        # limit 12 hours
        if int(time.time()) - check_claimed['claimed_at'] <= claim_interval*3600:
            remaining = await bot_faucet() or ''
            time_waiting = seconds_str(claim_interval*3600 - int(time.time()) + check_claimed['claimed_at'])
            number_user_claimed = '{:,.0f}'.format(store.sql_faucet_count_user(message.from_user.username, 'TELEGRAM'))
            total_claimed = '{:,.0f}'.format(store.sql_faucet_count_all())

            reply_text = text(code(f'You just claimed within last {claim_interval}h. '),
                         code(f'Waiting time {time_waiting} for next'), bold('/take'), code(f'.\nFaucet balance:\n{remaining}\n'),
                         code(f'Total user claims: {total_claimed} times. '),
                         code(f'You have claimed: {number_user_claimed} time(s). '),
                         code(f'Tip me if you want to feed these faucets.\n Any support, join https://t.me/wrkzcoinchat'))
            await message.reply(reply_text, parse_mode=ParseMode.MARKDOWN)
            return


    COIN_NAME = random.choice(FAUCET_COINS)
    loop = 0
    while is_maintenance_coin(COIN_NAME):
        COIN_NAME = random.choice(FAUCET_COINS)
        loop += 1
        # stop loop if more than 3 times
        if loop > 3:
            break
    amount = random.randint(FAUCET_MINMAX[COIN_NAME][0], FAUCET_MINMAX[COIN_NAME][1])

    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if COIN_NAME == "DOGE":
        amount = float(amount / 10)

    def myround_number(x, base=5):
        return base * round(x/base)

    if COIN_NAME in FAUCET_COINS_ROUND_NUMBERS:
        amount = myround_number(amount)
        if amount == 0: amount = 5 

    COIN_DEC = get_decimal(COIN_NAME)
    real_amount = int(amount * COIN_DEC) if (coin_family == "TRTL" or coin_family == "XMR") else amount
    user_from = await store.sql_get_userwallet('teletip_bot', COIN_NAME, 'TELEGRAM')
    if coin_family == "TRTL":
        userdata_balance = await store.sql_cnoff_balance('teletip_bot', COIN_NAME, 'TELEGRAM')
        user_from['actual_balance'] = user_from['actual_balance'] + int(userdata_balance['Adjust'])
    elif coin_family == "DOGE":
        userdata_balance = await store.sql_doge_balance('teletip_bot', COIN_NAME, 'TELEGRAM')
        user_from['actual_balance'] = user_from['actual_balance'] + float(userdata_balance['Adjust'])
    user_to = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')
    if user_to is None:
        reply_text = f"You get random coin {COIN_NAME}. But I can not get you in DB. Please create your account with /bal list"
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
        return
    else:
        try:
            if real_amount > user_from['actual_balance']:
                reply_text = f"Bot runs out of {COIN_NAME}."
                await message.reply(reply_text)
                return

            tip = None
            if coin_family == "TRTL":
                tip = await store.sql_send_tip('teletip_bot', message.from_user.username, real_amount, 'FAUCET', COIN_NAME, 'TELEGRAM')
            elif coin_family == "DOGE":
                tip = await store.sql_mv_doge_single('teletip_bot', message.from_user.username, real_amount, COIN_NAME, 'FAUCET', 'TELEGRAM')
            if tip:
                faucet_add = store.sql_faucet_add(message.from_user.username, message.chat.id, COIN_NAME, real_amount, COIN_DEC, tip, 'TELEGRAM')
                message_text = text(bold("You received free coin:"), code("\nAmount: {}{}".format(num_format_coin(real_amount, COIN_NAME), COIN_NAME)), "\nConsider tipping me if you like this :).")
                await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                    parse_mode=ParseMode.MARKDOWN)
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


@dp.message_handler(commands='donate')
async def start_cmd_handler(message: types.Message):
    if message.from_user.username is None:
        reply_text = "I can not get your username."
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
        return

    content = ' '.join(message.text.split())
    args = content.split(" ")
    if len(args) != 3:
        reply_text = "Please use /donate amount coin_name"
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
        return
   
    COIN_NAME = args[2].upper()
    if COIN_NAME not in ENABLE_COIN + ENABLE_COIN_DOGE:
        message_text = text(bold(f"Invalid {COIN_NAME}\n\n"), 
                            "Supported coins: ", code(", ".join(ENABLE_COIN + ENABLE_COIN_DOGE)))
        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                            parse_mode=ParseMode.MARKDOWN)
        return

    amount = args[1].replace(",", "")
    try:
        amount = float(amount)
    except ValueError:
        message_text = text(bold("Invalid amount."))
        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                            parse_mode=ParseMode.MARKDOWN)
        return

    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    user_from = await store.sql_get_userwallet(message.from_user.username, COIN_NAME, 'TELEGRAM')
    if coin_family == "TRTL":
        userdata_balance = await store.sql_cnoff_balance(message.from_user.username, COIN_NAME, 'TELEGRAM')
        user_from['actual_balance'] = user_from['actual_balance'] + int(userdata_balance['Adjust'])
    elif coin_family == "DOGE":
        userdata_balance = await store.sql_doge_balance(message.from_user.username, COIN_NAME, 'TELEGRAM')
        user_from['actual_balance'] = user_from['actual_balance'] + float(userdata_balance['Adjust'])
    COIN_DEC = get_decimal(COIN_NAME)
    real_amount = int(amount * COIN_DEC) if (coin_family == "TRTL" or coin_family == "XMR") else amount
    MinTx = get_min_mv_amount(COIN_NAME)
    MaxTX = get_max_mv_amount(COIN_NAME)

    message_text = ''
    valid_amount = True
    if real_amount > user_from['actual_balance']:
        message_text = 'Insufficient balance to donate ' + num_format_coin(real_amount, COIN_NAME) + COIN_NAME
        valid_amount = False
    elif real_amount > MaxTX:
        message_text = 'Transactions cannot be bigger than ' + num_format_coin(MaxTX, COIN_NAME) + COIN_NAME
        valid_amount = False
    elif real_amount < MinTx:
        message_text = 'Transactions cannot be bigger than ' + num_format_coin(MinTx, COIN_NAME) + COIN_NAME
        valid_amount = False
    if valid_amount == False:
        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                            parse_mode=ParseMode.MARKDOWN)
        return


    if message.from_user.username not in WITHDRAW_IN_PROCESS:
        WITHDRAW_IN_PROCESS.append(message.from_user.username)
        tip = None
        try:
            CoinAddress = get_donate_address(COIN_NAME)
            if coin_family == "TRTL":
                tip = await store.sql_donate(message.from_user.username, CoinAddress, real_amount, COIN_NAME, 'TELEGRAM')
            elif coin_family == "DOGE":
                tip = await store.sql_mv_doge_single(message.from_user.username, CoinAddress, real_amount, COIN_NAME, 'DONATE', 'TELEGRAM')
            message_text = text(bold("You donated:"), code("\nAmount: {}{}".format(num_format_coin(real_amount, COIN_NAME), COIN_NAME)), "Thank you very much.")
            await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                                parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if message.from_user.username in WITHDRAW_IN_PROCESS:
            WITHDRAW_IN_PROCESS.remove(message.from_user.username)
    else:
        message_text = text(bold("You have another tx in progress.\n"))
        await message.reply(message_text, reply_markup=types.ReplyKeyboardRemove(),
                            parse_mode=ParseMode.MARKDOWN)
        return


@dp.message_handler(commands='about')
async def start_cmd_handler(message: types.Message):
    reply_text = text(bold("Thank you for checking:\n"),
                      code("Twitter dev: https://twitter.com/wrkzdev\n"),
                      code("Discord: https://chat.wrkz.work\n"),
                      code("Telegram: https://t.me/wrkzcoinchat\n"),
                      code("Donation: via /donate amount coin_name\n"),
                      code("Run by WrkzCoin team\n"))
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
        await message.reply(reply_text, reply_markup=types.ReplyKeyboardRemove())
    # with message, we send types.ReplyKeyboardRemove() to hide the keyboard



async def get_cn_coin_from_address(CoinAddress: str):
    COIN_NAME = None
    if CoinAddress.startswith("Wrkz"):
        COIN_NAME = "WRKZ"
    elif CoinAddress.startswith("dg"):
        COIN_NAME = "DEGO"
    elif CoinAddress.startswith("cat1"):
        COIN_NAME = "CX"
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
            # traceback.print_exc(file=sys.stdout)
            pass
        # Try XAM
        try:
            addr = address_xam(CoinAddress)
            COIN_NAME = "XAM"
            return COIN_NAME
        except Exception as e:
            # traceback.print_exc(file=sys.stdout)
            pass
        # Try XMR
        try:
            addr = address_xmr(CoinAddress)
            COIN_NAME = "XMR"
            return COIN_NAME
        except Exception as e:
            # traceback.print_exc(file=sys.stdout)
            pass
    elif (CoinAddress.startswith("amit") and len(CoinAddress) == 98) or (CoinAddress.startswith("aint") and len(CoinAddress) == 109)  or \
        (CoinAddress.startswith("asub") and len(CoinAddress) == 99):
        COIN_NAME = "XAM"
    elif CoinAddress.startswith("L") and (len(CoinAddress) == 95 or len(CoinAddress) == 106):
        COIN_NAME = "LOKI"
    elif CoinAddress.startswith("cms") and (len(CoinAddress) == 98 or len(CoinAddress) == 109):
        COIN_NAME = "BLOG"
    elif (CoinAddress.startswith("ar") or CoinAddress.startswith("aR")) and (len(CoinAddress) == 97 or len(CoinAddress) == 98 or len(CoinAddress) == 109):
        COIN_NAME = "ARQ"
    elif (CoinAddress.startswith("5") or CoinAddress.startswith("9")) and (len(CoinAddress) == 95 or len(CoinAddress) == 106):
        COIN_NAME = "MSR"
    elif CoinAddress.startswith("D") and len(CoinAddress) == 34:
        COIN_NAME = "DOGE"
    elif (CoinAddress[0] in ["M", "L"]) and len(CoinAddress) == 34:
        COIN_NAME = "LTC"
    elif (CoinAddress[0] in ["3", "1"]) and len(CoinAddress) == 34:
        COIN_NAME = "BTC"
    elif CoinAddress.startswith("bitcoincash") and len(CoinAddress) == 54:
        COIN_NAME = "BCH"
    elif (CoinAddress[0] in ["X"]) and len(CoinAddress) == 34:
        COIN_NAME = "DASH"
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
                user_tx = None
                if len(eachTx['payment_id']) > 0:
                    user_tx = await store.sql_get_userwallet_by_paymentid(eachTx['payment_id'], eachTx['coin_name'], 'TELEGRAM')
                if user_tx:
                    #get_user_chat = await bot.get_chat_member()
                    is_notify_failed = False
                    to_user = user_tx['chat_id']
                    message_text = None
                    if eachTx['coin_name'] not in ENABLE_COIN_DOGE:
                        message_text = text(bold(f"You got a new deposit {eachTx['coin_name']}:\n"), code("Tx: {}\nAmount: {}\nHeight: {:,.0f}".format(eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name']), eachTx['height'])))
                    else:
                        message_text = text(bold(f"You got a new deposit {eachTx['coin_name']}:\n"), code("Tx: {}\nAmount: {}\nBlock Hash: {}".format(eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name']), eachTx['blockhash'])))
                    try:
                        send_msg = await bot.send_message(chat_id=to_user, text=message_text, parse_mode=ParseMode.MARKDOWN)
                        if send_msg:
                            is_notify_failed = False
                        else:
                            print("Can not send message")
                            is_notify_failed = True
                    except exceptions.BotBlocked:
                        print(f"Target [ID:{to_user}]: blocked by user")
                    except exceptions.ChatNotFound:
                        print(f"Target [ID:{to_user}]: invalid user ID")
                    except exceptions.RetryAfter as e:
                        print(f"Target [ID:{to_user}]: Flood limit is exceeded. Sleep {e.timeout} seconds.")
                        await asyncio.sleep(e.timeout)
                        return await bot.send_message(chat_id=to_user, text=message_text, parse_mode=ParseMode.MARKDOWN)  # Recursive call
                    except exceptions.UserDeactivated:
                        print(f"Target [ID:{to_user}]: user is deactivated")
                    except exceptions.TelegramAPIError:
                        print(f"Target [ID:{to_user}]: failed")
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        is_notify_failed = True
                    finally:
                         update_notify_tx = await store.sql_update_notify_tx_table(eachTx['payment_id'], user_tx['user_id'], user_tx['user_id'], 'YES', 'NO' if is_notify_failed == False else 'YES')
        await asyncio.sleep(INTERVAL_EACH)


async def bot_faucet():
    table_data = [
        ['TICKER', 'Available']
    ]

    for COIN_NAME in [coinItem.upper() for coinItem in FAUCET_COINS]:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
        if (not is_maintenance_coin(COIN_NAME)) and coin_family in ["TRTL"]:
            COIN_DEC = get_decimal(COIN_NAME)
            wallet = await store.sql_get_userwallet('teletip_bot', COIN_NAME, 'TELEGRAM')
            userdata_balance = await store.sql_cnoff_balance('teletip_bot', COIN_NAME, 'TELEGRAM')
            wallet['actual_balance'] = wallet['actual_balance'] + int(userdata_balance['Adjust'])
            balance_actual = num_format_coin(wallet['actual_balance'], COIN_NAME)
            if wallet['actual_balance'] + wallet['locked_balance'] != 0:
                table_data.append([COIN_NAME, balance_actual])
            else:
                table_data.append([COIN_NAME, '0'])
        elif (not is_maintenance_coin(COIN_NAME)) and COIN_NAME == "DOGE":
            COIN_DEC = get_decimal(COIN_NAME)
            wallet = await store.sql_get_userwallet('teletip_bot', COIN_NAME, 'TELEGRAM')
            userdata_balance = await store.sql_doge_balance('teletip_bot', COIN_NAME, 'TELEGRAM')
            wallet['actual_balance'] = wallet['actual_balance'] + float(userdata_balance['Adjust'])
            balance_actual = num_format_coin(wallet['actual_balance'], COIN_NAME)
            if wallet['actual_balance'] + wallet['locked_balance'] != 0:
                table_data.append([COIN_NAME, balance_actual])
            else:
                table_data.append([COIN_NAME, '0'])
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
        key = 'TIPBOT:COIN_' + COIN_NAME + '_MAINT'
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
        key = 'TIPBOT:COIN_' + COIN_NAME + '_TX'
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
        key = 'TIPBOT:COIN_' + COIN_NAME + '_DEPOSIT'
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
        key = 'TIPBOT:COIN_' + COIN_NAME + '_TIP'
        if redis_conn and redis_conn.exists(key):
            return False
        else:
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def add_tx_action_redis(action: str, delete_temp: bool = False):
    try:
        openRedis()
        key = "TIPBOT:ACTIONTX"
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
    dp.loop.create_task(notify_new_tx_user())
    executor.start_polling(dp, skip_updates=True)