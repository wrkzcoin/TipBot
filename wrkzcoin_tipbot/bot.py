import click

import discord
from discord.ext import commands
from discord.ext.commands import Bot, AutoShardedBot, when_mentioned_or, CheckFailure

from discord.utils import get

import time, timeago, json


import store, daemonrpc_client, addressvalidation
from config import config
from wallet import *

# regex
import re
# reaction
from discord.utils import get
from datetime import datetime
import math, random
import qrcode
import os.path
import uuid
from PIL import Image, ImageDraw, ImageFont

# ascii table
from terminaltables import AsciiTable

import sys

# Setting up asyncio to use uvloop if possible, a faster implementation on the event loop
import asyncio

# Importing and creating a logger

import logging

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

try:
    # noinspection PyUnresolvedReferences
    import uvloop
except ImportError:
    logger.warning("Using the not-so-fast default asyncio event loop. Consider installing uvloop.")
    pass
else:
    logger.info("Using the fast uvloop asyncio event loop")
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


sys.path.append("..")

MAINTENANCE_OWNER = [386761001808166912]  # list owner
# bingo and duckhunt
BOT_IGNORECHAN = [558173489194991626, 524572420468899860]  # list ignore chan
LOG_CHAN = 572686071771430922
BOT_INVITELINK = 'https://discordapp.com/oauth2/authorize?client_id=474841349968101386&scope=bot&permissions=3072'
WALLET_SERVICE = None
LIST_IGNORECHAN = None

MESSAGE_HISTORY_MAX = 20 # message history to store
MESSAGE_HISTORY_TIME = 60 # duration max to put to DB
MESSAGE_HISTORY_LIST = []
MESSAGE_HISTORY_LAST = 0

IS_MAINTENANCE = config.maintenance

# Get them from https://emojipedia.org
EMOJI_MONEYFACE = "\U0001F911"
EMOJI_ERROR = "\u274C"
EMOJI_OK = "\U0001F44C"
EMOJI_WARNING = "\u26A1"
EMOJI_ALARMCLOCK = "\u23F0"
EMOJI_HOURGLASS_NOT_DONE = "\u23F3"
EMOJI_CHECK = "\u2705"
EMOJI_MONEYBAG = "\U0001F4B0"
EMOJI_SCALE = "\u2696"

EMOJI_TIP = EMOJI_MONEYFACE
EMOJI_WRKZ = "\U0001F477"
EMOJI_TRTL = "\U0001F422"
EMOJI_DEGO = "\U0001F49B"
EMOJI_LCX = "\U0001F517"
EMOJI_CX = "\U0001F64F"
EMOJI_OSL = "\U0001F381"
EMOJI_BTCM = "\U0001F4A9"
EMOJI_MTIP = "\U0001F595"
EMOJI_XCY = "\U0001F3B2"
EMOJI_PLE = "\U0001F388"
EMOJI_ELPH = "\U0001F310"
EMOJI_ANX = "\U0001F3E6"
EMOJI_NBX = "\U0001F5A4"
EMOJI_ARMS = "\U0001F52B"
EMOJI_IRD = "\U0001F538"
EMOJI_HITC = "\U0001F691"
EMOJI_NACA = "\U0001F355"

EMOJI_DOGE = "\U0001F436"

EMOJI_RED_NO = "\u26D4"
EMOJI_SPEAK = "\U0001F4AC"
EMOJI_ARROW_RIGHTHOOK = "\u21AA"


ENABLE_COIN = config.Enable_Coin.split(",")
ENABLE_COIN_DOGE = ["DOGE"]
MAINTENANCE_COIN = [""]
COIN_REPR = "COIN"
DEFAULT_TICKER = "WRKZ"
ENABLE_COIN_VOUCHER = config.Enable_Coin_Voucher.split(",")

# Some notice about coin that going to swap or take out.
NOTICE_TRTL = None
NOTICE_DEGO = None
NOTICE_WRKZ = None
NOTICE_LCX = None
NOTICE_CX = None
NOTICE_OSL = None
NOTICE_BTCM = None
NOTICE_MTIP = None
NOTICE_XCY = None
NOTICE_PLE = None
NOTICE_ELPH = None
NOTICE_ANX = None
NOTICE_NBX = None
NOTICE_ARMS = None
NOTICE_IRD = None
NOTICE_HITC = None
NOTICE_NACA = None

NOTICE_DOGE = "Please acknowledge that DOGE address is for **one-time** use only for depositing."
NOTIFICATION_OFF_CMD = 'Type: `.notifytip off` to turn off this DM notification.'

bot_description = f"Tip {COIN_REPR} to other users on your server."
bot_help_register = "Register or change your deposit address."
bot_help_info = "Get your account's info."
bot_help_withdraw = f"Withdraw {COIN_REPR} from your balance."
bot_help_balance = f"Check your {COIN_REPR} balance."
bot_help_botbalance = f"Check (only) bot {COIN_REPR} balance."
bot_help_donate = f"Donate {COIN_REPR} to a Bot Owner."
bot_help_tip = f"Give {COIN_REPR} to a user from your balance."
bot_help_tipall = f"Spread a tip amount of {COIN_REPR} to all online members."
bot_help_send = f"Send {COIN_REPR} to a {COIN_REPR} address from your balance (supported integrated address)."
bot_help_optimize = f"Optimize your tip balance of {COIN_REPR} for large tip, send, tipall, withdraw"
bot_help_address = f"Check {COIN_REPR} address | Generate {COIN_REPR} integrated address."
bot_help_paymentid = "Make a random payment ID with 64 chars length."
bot_help_address_qr = "Show an input address in QR code image."
bot_help_payment_qr = f"Make QR code image for {COIN_REPR} payment."
bot_help_tag = "Display a description or a link about what it is. (-add|-del) requires permission manage_channels"
bot_help_stats = f"Show summary {COIN_REPR}: height, difficulty, etc."
bot_help_height = f"Show {COIN_REPR}'s current height"
bot_help_notifytip = "Toggle notify tip notification from bot ON|OFF"
bot_help_settings = "settings view and set for prefix, default coin. Requires permission manage_channels"
bot_help_invite = "Invite link of bot to your server."
bot_help_voucher = "(Testing) make a voucher image and your friend can claim via QR code."


def get_emoji(coin: str):
    if coin is None:
        coin = "WRKZ"
    if coin.upper() == "TRTL":
        emoji = EMOJI_TRTL
    elif coin.upper() == "DEGO":
        emoji = EMOJI_DEGO
    elif coin.upper() == "LCX":
        emoji = EMOJI_LCX
    elif coin.upper() == "CX":
        emoji = EMOJI_CX
    elif coin.upper() == "WRKZ":
        emoji = EMOJI_WRKZ
    elif coin.upper() == "OSL":
        emoji = EMOJI_OSL
    elif coin.upper() == "BTCM":
        emoji = EMOJI_BTCM
    elif coin.upper() == "MTIP":
        emoji = EMOJI_MTIP
    elif coin.upper() == "XCY":
        emoji = EMOJI_XCY
    elif coin.upper() == "PLE":
        emoji = EMOJI_PLE
    elif coin.upper() == "ELPH":
        emoji = EMOJI_ELPH
    elif coin.upper() == "ANX":
        emoji = EMOJI_ANX
    elif coin.upper() == "NBX":
        emoji = EMOJI_NBX
    elif coin.upper() == "ARMS":
        emoji = EMOJI_ARMS
    elif coin.upper() == "IRD":
        emoji = EMOJI_IRD
    elif coin.upper() == "HITC":
        emoji = EMOJI_HITC
    elif coin.upper() == "NACA":
        emoji = EMOJI_NACA
    else:
        emoji = EMOJI_WRKZ
    return emoji


def get_notice_txt(coin: str):
    if coin is None:
        coin = "WRKZ"
    else:
        coin = coin.upper()
    if coin.upper() == "TRTL":
        notice_txt = NOTICE_TRTL
    elif coin.upper() == "DEGO":
        notice_txt = NOTICE_DEGO
    elif coin.upper() == "LCX":
        notice_txt = NOTICE_LCX
    elif coin.upper() == "CX":
        notice_txt = NOTICE_CX
    elif coin.upper() == "WRKZ":
        notice_txt = NOTICE_WRKZ
    elif coin.upper() == "OSL":
        notice_txt = NOTICE_OSL
    elif coin.upper() == "BTCM":
        notice_txt = NOTICE_BTCM
    elif coin.upper() == "MTIP":
        notice_txt = NOTICE_MTIP
    elif coin.upper() == "XCY":
        notice_txt = NOTICE_XCY
    elif coin.upper() == "PLE":
        notice_txt = NOTICE_PLE
    elif coin.upper() == "ELPH":
        notice_txt = NOTICE_ELPH
    elif coin.upper() == "ANX":
        notice_txt = NOTICE_ANX
    elif coin.upper() == "NBX":
        notice_txt = NOTICE_NBX
    elif coin.upper() == "ARMS":
        notice_txt = NOTICE_ARMS
    elif coin.upper() == "IRD":
        notice_txt = NOTICE_IRD
    elif coin.upper() == "HITC":
        notice_txt = NOTICE_HITC
    elif coin.upper() == "NACA":
        notice_txt = NOTICE_NACA
    elif coin.upper() == "DOGE":
        notice_txt = NOTICE_DOGE
    else:
        notice_txt = NOTICE_WRKZ
    if notice_txt is None:
        notice_txt = "*Any support, please approach CapEtn#4425.*"
    return notice_txt


# Steal from https://github.com/cree-py/RemixBot/blob/master/bot.py#L49
async def get_prefix(bot, message):
    """Gets the prefix for the guild"""
    pre_cmd = config.discord.prefixCmd
    if isinstance(message.channel, discord.DMChannel):
        pre_cmd = config.discord.prefixCmd
        extras = [pre_cmd, 'tb!', 'tipbot!', '?', '.', '+', '!', '-']
        return when_mentioned_or(*extras)(bot, message)

    serverinfo = store.sql_info_by_server(str(message.guild.id))
    if serverinfo is None:
        # Let's add some info if guild return None
        add_server_info = store.sql_addinfo_by_server(str(message.guild.id), message.guild.name,
                                                      config.discord.prefixCmd, "WRKZ")
        pre_cmd = config.discord.prefixCmd

    if 'prefix' in serverinfo:
        pre_cmd = serverinfo['prefix']
    else:
        pre_cmd =  config.discord.prefixCmd
    extras = [pre_cmd, 'tb!', 'tipbot!']
    return when_mentioned_or(*extras)(bot, message)


logger.debug("Creating a bot instance of commands.AutoShardedBot")
bot = AutoShardedBot(command_prefix = get_prefix, case_insensitive=True, pm_help = True)


@bot.event
async def on_ready():
    global LIST_IGNORECHAN
    print('Ready!')
    print("Hello, I am TipBot Bot!")
    # get WALLET_SERVICE
    WALLET_SERVICE = store.sql_get_walletinfo()
    LIST_IGNORECHAN = store.sql_listignorechan()
    #print(WALLET_SERVICE)
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    print("Guilds: {}".format(len(bot.guilds)))
    print("Users: {}".format(sum([x.member_count for x in bot.guilds])))
    game = discord.Game(name="Tip Forever!")
    await bot.change_presence(status=discord.Status.online, activity=game)


@bot.event
async def on_shard_ready(shard_id):
    print(f'Shard {shard_id} connected')


@bot.event
async def on_guild_join(guild):
    botLogChan = bot.get_channel(id=LOG_CHAN)
    add_server_info = store.sql_addinfo_by_server(str(guild.id), guild.name,
                                                  config.discord.prefixCmd, "WRKZ")
    await botLogChan.send(f'Bot joins a new guild {guild.name} / {guild.id}')
    return


@bot.event
async def on_message(message):
    global MESSAGE_HISTORY_LIST, MESSAGE_HISTORY_TIME, MESSAGE_HISTORY_MAX, MESSAGE_HISTORY_LAST, LIST_IGNORECHAN
    # record message for .tip XXX ticker -m last 5mn (example)
    if len(MESSAGE_HISTORY_LIST) > 0:
        if len(MESSAGE_HISTORY_LIST) > MESSAGE_HISTORY_MAX or time.time() - MESSAGE_HISTORY_LAST > MESSAGE_HISTORY_TIME:
            # add to DB
            numb_message = store.sql_add_messages(MESSAGE_HISTORY_LIST)
            MESSAGE_HISTORY_LIST = []
            MESSAGE_HISTORY_LAST == 0
    if isinstance(message.channel, discord.DMChannel) == False and message.author.bot == False and len(message.content) > 0 and message.author != bot.user:
        if config.Enable_Message_Logging == 1:
            MESSAGE_HISTORY_LIST.append((str(message.guild.id), message.guild.name, str(message.channel.id), message.channel.name, 
                str(message.author.id), message.author.name, str(message.id), message.content, int(time.time())))
        else:
            MESSAGE_HISTORY_LIST.append((str(message.guild.id), message.guild.name, str(message.channel.id), message.channel.name, 
                str(message.author.id), message.author.name, str(message.id), '', int(time.time())))
        if MESSAGE_HISTORY_LAST == 0:
            MESSAGE_HISTORY_LAST = int(time.time())
    # filter ignorechan
    commandList = ('TIP', 'TIPALL', 'DONATE', 'HELP', 'STATS', 'DONATE', 'SEND', 'WITHDRAW', 'BOTBAL', 'BAL PUB')
    try:
        # remove first char
        if (isinstance(message.channel, discord.DMChannel) == False) and message.content[1:].upper().startswith(commandList) and (str(message.channel.id) in LIST_IGNORECHAN[str(message.guild.id)]):
            await message.add_reaction(EMOJI_ERROR)
            await message.channel.send(f'Bot not respond to #{message.channel.name}. It is set to ignore list by channel manager or discord server owner.')
            return
        else:
            pass
    except Exception as e:
        print(e)
        pass

    if message.content.upper().startswith('.HELP') or message.content.upper().startswith('.STAT'):
        if int(message.channel.id) in BOT_IGNORECHAN:
            return
    if int(message.author.id) in MAINTENANCE_OWNER:
        # It is better to set bot to MAINTENANCE mode before restart or stop
        args = message.content.split(" ")
        if len(args) == 2:
            if args[0].upper() == "MAINTENANCE":
                if args[1].upper() == "ON":
                    IS_MAINTENANCE = 1
                    await message.author.send('Maintenance ON, `maintenance off` to turn it off.')
                    return
                else:
                    IS_MAINTENANCE = 0
                    await message.author.send('Maintenance OFF, `maintenance on` to turn it off.')
                    return
    # Do not remove this, otherwise, command not working.
    # await bot.process_commands(message)
    ctx = await bot.get_context(message)
    await bot.invoke(ctx)


@bot.command(pass_context=True, name='info', aliases=['wallet'], help=bot_help_info)
async def info(ctx, coin: str = None):
    global LIST_IGNORECHAN
    wallet = None
    if coin is None:
        cmdName = ctx.message.content.split(" ")[0]
        cmdName = cmdName[1:]
        if cmdName.lower not in ['wallet', 'info']:
            cmdName = ctx.message.content.split(" ")[1]
        if isinstance(ctx.channel, discord.DMChannel):
            prefixChar = '.'
            tickers = '|'.join(ENABLE_COIN).lower()
            await ctx.send(
                f'Please add ticker after **{cmdName.lower()}**. Example: `{prefixChar}{cmdName.lower()} {tickers}`')
            return
        else:
            serverinfo = store.sql_info_by_server(str(ctx.guild.id))
            if serverinfo is None:
                # Let's add some info if server return None
                add_server_info = store.sql_addinfo_by_server(str(ctx.guild.id),
                                                              ctx.message.guild.name, config.discord.prefixCmd,
                                                              "WRKZ")
                servername = ctx.message.guild.name
                server_id = str(ctx.guild.id)
                server_prefix = config.discord.prefixCmd
                server_coin = DEFAULT_TICKER
            else:
                servername = serverinfo['servername']
                server_id = str(ctx.guild.id)
                server_prefix = serverinfo['prefix']
                server_coin = serverinfo['default_coin'].upper()

            chanel_ignore_list = ''
            if LIST_IGNORECHAN:
                if str(ctx.guild.id) in LIST_IGNORECHAN:
                    for item in LIST_IGNORECHAN[str(ctx.guild.id)]:
                        chanel_ignore = bot.get_channel(id=int(item))
                        chanel_ignore_list = chanel_ignore_list + '#'  + chanel_ignore.name + ' '

            await ctx.send(
                '\n```'
                f'Server ID:      {ctx.guild.id}\n'
                f'Server Name:    {ctx.message.guild.name}\n'
                f'Default ticker: {server_coin}\n'
                f'Default prefix: {server_prefix}\n'
                f'Ignored Tip in: {chanel_ignore_list}\n'
                '```')
            tickers = '|'.join(ENABLE_COIN).lower()
            await ctx.send(
                f'Please add ticker after **{cmdName.lower()}**. Example: `{server_prefix}{cmdName.lower()} {server_coin}`, if you want to get your address(es).\n\n'
                f'Type: `{server_prefix}setting` if you want to change `prefix` or `default_coin` or `ignorechan` or `del_ignorechan`. (Required permission)')
            return
    elif coin.upper() in ENABLE_COIN:
        user = store.sql_register_user(ctx.message.author.id, coin.upper())
        wallet = store.sql_get_userwallet(ctx.message.author.id, coin.upper())
    elif coin.upper() in ENABLE_COIN_DOGE:
        # user = store.sql_register_user(ctx.message.author.id, "DOGE")
        wallet = store.sql_get_userwallet(ctx.message.author.id, coin.upper())
        depositAddress = DOGE_getaccountaddress(ctx.message.author.id)
        wallet['balance_wallet_address'] = depositAddress
    else:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**')
        return
    if wallet is None:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Internal Error for `.info`')
        return
    if os.path.exists(config.qrsettings.path + wallet['balance_wallet_address'] + ".png"):
        pass
    else:
        # do some QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
        )
        qr.add_data(wallet['balance_wallet_address'])
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img = img.resize((256, 256))
        img.save(config.qrsettings.path + wallet['balance_wallet_address'] + ".png")

    if 'user_wallet_address' in wallet:
        await ctx.message.add_reaction(EMOJI_OK)
        await ctx.message.author.send("**QR for your Deposit**", 
                                    file=discord.File(config.qrsettings.path + wallet['balance_wallet_address'] + ".png"))
        await ctx.message.author.send(f'**[ACCOUNT INFO]**\n\n'
                                    f'{EMOJI_MONEYBAG} Deposit Address: `' + wallet['balance_wallet_address'] + '`\n'
                                    f'{EMOJI_SCALE} Registered Wallet: `'
                                    ''+ wallet['user_wallet_address'] + '`\n'
                                    f'{get_notice_txt(coin.upper())}')
    else:
        await ctx.message.add_reaction(EMOJI_WARNING)
        await ctx.message.author.send("**QR for your Deposit**", 
                                    file=discord.File(config.qrsettings.path + wallet['balance_wallet_address'] + ".png"))
        await ctx.message.author.send(f'**[ACCOUNT INFO]**\n\n'
                               f'{EMOJI_MONEYBAG} Deposit Address: `' + wallet['balance_wallet_address'] + '`\n'
                               f'{EMOJI_SCALE} Registered Wallet: `NONE, Please register.`\n'
                               f'{get_notice_txt(coin.upper())}')
    return


@bot.command(pass_context=True, name='balance', aliases=['bal'], help=bot_help_balance)
async def balance(ctx, coin: str = None):
    PUBMSG = ctx.message.content.strip().split(" ")[-1].upper()
    prefixChar = '.'
    if isinstance(ctx.channel, discord.DMChannel):
        prefixChar = '.'
    else:
        serverinfo = store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            add_server_info = store.sql_addinfo_by_server(str(ctx.guild.id),
                                                          ctx.message.guild.name, config.discord.prefixCmd,
                                                          "WRKZ")
            servername = ctx.message.guild.name
            server_id = str(ctx.guild.id)
            server_prefix = config.discord.prefixCmd
            server_coin = DEFAULT_TICKER
        else:
            servername = serverinfo['servername']
            server_id = str(ctx.guild.id)
            server_prefix = serverinfo['prefix']
            server_coin = serverinfo['default_coin'].upper()
        prefixChar = server_prefix
    # Get wallet status
    walletStatus = None
    if (coin is None) or (PUBMSG == "PUB"):
        table_data = [
            ['TICKER', 'Available', 'Locked']
        ]
        for coinItem in ENABLE_COIN:
            if coinItem not in MAINTENANCE_COIN:
                COIN_DEC = get_decimal(coinItem.upper())
                try:
                    user = store.sql_register_user(ctx.message.author.id, coinItem.upper())
                except:
                    pass
                wallet = store.sql_get_userwallet(ctx.message.author.id, coinItem.upper())
                if wallet is None:
                    await ctx.send(f'{ctx.author.mention} Internal Error for `{prefixChar}balance`')
                    pass
                else:
                    balance_actual = num_format_coin(wallet['actual_balance'], coinItem.upper())
                    balance_locked = num_format_coin(wallet['locked_balance'], coinItem.upper())
                    balance_total = num_format_coin((wallet['actual_balance'] + wallet['locked_balance']), coinItem.upper())
                    table_data.append([coinItem.upper(), balance_actual, balance_locked])
                    pass
            else:
                table_data.append([coinItem.upper(), "***", "***"])
        # Add DOGE
        COIN_NAME = "DOGE"
        if COIN_NAME not in MAINTENANCE_COIN:
            depositAddress = DOGE_getaccountaddress(ctx.message.author.id)
            actual = float(DOGE_getbalance_acc(ctx.message.author.id, 6))
            locked = float(DOGE_getbalance_acc(ctx.message.author.id, 1))
            userdata_balance = store.sql_doge_balance(ctx.message.author.id, COIN_NAME)

            if actual == locked:
                balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
                balance_locked = num_format_coin(0, COIN_NAME)
            else:
                balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
                if locked - actual + float(userdata_balance['Adjust']) < 0:
                    balance_locked =  num_format_coin(0, COIN_NAME)
                else:
                    balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
            table_data.append([COIN_NAME, balance_actual, balance_locked])
        else:
            table_data.append([COIN_NAME, "***", "***"])
        # End of Add DOGE

        table = AsciiTable(table_data)
        # table.inner_column_border = False
        # table.outer_border = False
        table.padding_left = 0
        table.padding_right = 0
        await ctx.message.add_reaction(EMOJI_OK)
        if PUBMSG.upper() == "PUB":
            await ctx.send('**[ BALANCE LIST ]**\n'
                            f'```{table.table}```\n'
                            f'Related command: `{prefixChar}balance TICKER` or `{prefixChar}info TICKER`\n')
        else:
            await ctx.message.author.send('**[ BALANCE LIST ]**\n'
                            f'```{table.table}```\n'
                            f'Related command: `{prefixChar}balance TICKER` or `{prefixChar}info TICKER`\n'
                            f'{get_notice_txt(COIN_NAME)}')
        return
    elif coin.upper() in MAINTENANCE_COIN:
        await ctx.send(f'{EMOJI_RED_NO} {coin.upper()} in maintenance.')
        return
    elif coin.upper() in ENABLE_COIN:
        walletStatus = daemonrpc_client.getWalletStatus(coin.upper())
        COIN_NAME = coin.upper()
        COIN_DEC = get_decimal(COIN_NAME)
        pass
    elif coin.upper() == "DOGE":
        COIN_NAME = "DOGE"
        depositAddress = DOGE_getaccountaddress(ctx.message.author.id)
        actual = float(DOGE_getbalance_acc(ctx.message.author.id, 6))
        locked = float(DOGE_getbalance_acc(ctx.message.author.id, 1))
        userdata_balance = store.sql_doge_balance(ctx.message.author.id, COIN_NAME)
        if actual == locked:				
            balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']) , COIN_NAME)
            balance_locked = num_format_coin(0 , COIN_NAME)
        else:
            balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
            if locked - actual + float(userdata_balance['Adjust']) < 0:
                balance_locked = num_format_coin(0, COIN_NAME)
            else:
                balance_locked = num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
        await ctx.message.add_reaction(EMOJI_OK)
        await ctx.message.author.send(
                               f'**[ YOUR {COIN_NAME} BALANCE ]**\n'
                               f' Deposit Address: `{depositAddress}`\n'
                               f'{EMOJI_MONEYBAG} Available: {balance_actual} '
                               f'{COIN_NAME}\n'
                               f'{EMOJI_MONEYBAG} Pending: {balance_locked} '
                               f'{COIN_NAME}\n'
                               f'{get_notice_txt(COIN_NAME)}')
        return

    if coin.upper() not in ENABLE_COIN:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is no such ticker {coin.upper()}.')
        return

    if walletStatus is None:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Wallet service hasn\'t started.')
        return
    else:
        localDaemonBlockCount = int(walletStatus['blockCount'])
        networkBlockCount = int(walletStatus['knownBlockCount'])
        if networkBlockCount - localDaemonBlockCount >= 20:
            # if height is different by 20
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount / networkBlockCount * 100, 2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Wallet service hasn\'t sync fully with network or being re-sync. More info:\n```'
                           f'networkBlockCount:     {t_networkBlockCount}\n'
                           f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                           f'Progress %:            {t_percent}\n```'
                           )
            return
        else:
            pass
    # End of wallet status

    # Check if maintenance
    if IS_MAINTENANCE == 1:
        if int(ctx.message.author.id) in MAINTENANCE_OWNER:
            pass
        else:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {config.maintenance_msg}')
            return
    else:
        pass
    # End Check if maintenance
    try:
        user = store.sql_register_user(ctx.message.author.id, COIN_NAME)
    except:
        pass
    wallet = store.sql_get_userwallet(ctx.message.author.id, COIN_NAME)
    if wallet is None:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Internal Error for `.balance`')
        return
    if 'lastUpdate' in wallet:
        await ctx.message.add_reaction(EMOJI_OK)
        try:
            update = datetime.fromtimestamp(int(wallet['lastUpdate'])).strftime('%Y-%m-%d %H:%M:%S')
            ago = timeago.format(update, datetime.now())
            print(ago)
        except:
            pass

    balance_actual = num_format_coin(wallet['actual_balance'], COIN_NAME)
    balance_locked = num_format_coin(wallet['locked_balance'], COIN_NAME)

    await ctx.message.author.send(f'**[YOUR {COIN_NAME} BALANCE]**\n\n'
        f'{EMOJI_MONEYBAG} Available: {balance_actual} '
        f'{COIN_NAME}\n'
        f'{EMOJI_MONEYBAG} Pending: {balance_locked} '
        f'{COIN_NAME}\n'
        f'{get_notice_txt(COIN_NAME)}')
    if ago:
        await ctx.message.author.send(f'{EMOJI_HOURGLASS_NOT_DONE} update: {ago}')


@bot.command(pass_context=True, aliases=['botbal'], help=bot_help_botbalance)
async def botbalance(ctx, member: discord.Member = None, *args):
    # Get wallet status
    COIN_NAME = ""
    if (len(args) > 0) and (args[-1].upper() in ENABLE_COIN):
        COIN_NAME = args[-1].upper()
        pass
    elif (len(args) > 0) and (args[-1].upper() in ENABLE_COIN_DOGE):
        if (args[-1].upper() == "DOGE") or (args[-1].upper() == "DOGECOIN"):
            COIN_NAME = "DOGE"
        else:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
            return
    else:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
        return

    walletStatus = None
    if COIN_NAME.upper() in MAINTENANCE_COIN:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return
    if COIN_NAME.upper() in ENABLE_COIN:
        walletStatus = daemonrpc_client.getWalletStatus(COIN_NAME)
    elif COIN_NAME.upper() in ENABLE_COIN_DOGE:
        walletStatus = daemonrpc_client.getDaemonRPCStatus(COIN_NAME)

    if walletStatus is None:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}  Wallet service hasn\'t started.')
        return
    else:
        if COIN_NAME in ENABLE_COIN_DOGE:
            localDaemonBlockCount = int(walletStatus['blocks'])
            networkBlockCount = int(walletStatus['blocks'])
        elif COIN_NAME in ENABLE_COIN:
            localDaemonBlockCount = int(walletStatus['blockCount'])
            networkBlockCount = int(walletStatus['knownBlockCount'])
        if networkBlockCount - localDaemonBlockCount >= 20:
            # if height is different by 20
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount / networkBlockCount * 100, 2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Wallet service hasn\'t sync fully with network or being re-sync. More info:\n```'
                           f'networkBlockCount:     {t_networkBlockCount}\n'
                           f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                           f'Progress %:            {t_percent}\n```'
                           )
            return
        else:
            pass
    # End of wallet status

    # Check if maintenance
    if IS_MAINTENANCE == 1:
        if int(ctx.message.author.id) in MAINTENANCE_OWNER:
            pass
        else:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {config.maintenance_msg}')
            return
    else:
        pass
    # End Check if maintenance
    COIN_DEC = 10
    if COIN_NAME in ENABLE_COIN:
        COIN_DEC = get_decimal(COIN_NAME)

    if member is None:
        # user = store.sql_register_user(bot.user.id, COIN_NAME)
        # Bypass other if they re in ENABLE_COIN_DOGE
        if COIN_NAME in ENABLE_COIN_DOGE:
            depositAddress = DOGE_getaccountaddress(bot.user.id)
            actual = float(DOGE_getbalance_acc(bot.user.id, 6))
            locked = float(DOGE_getbalance_acc(bot.user.id, 1))
            userdata_balance = store.sql_doge_balance(bot.user.id, COIN_NAME)
            if actual == locked:
                balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
                balance_locked = num_format_coin(0 , COIN_NAME)
            else:
                balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
                if locked - actual + float(userdata_balance['Adjust']) < 0:
                    balance_locked =  num_format_coin(0, COIN_NAME)
                else:
                    balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
            await ctx.send(
                f'**[ MY {COIN_NAME} BALANCE]**\n'
                f' Deposit Address: `{depositAddress}`\n'
                f'{EMOJI_MONEYBAG} Available: {balance_actual} '
                f'{COIN_NAME}\n'
                f'{EMOJI_MONEYBAG} Pending: {balance_locked} '
                f'{COIN_NAME}\n'
                '**This is bot\'s tipjar address. Do not deposit here unless you want to deposit to this bot.**')
            return

        wallet = store.sql_get_userwallet(bot.user.id, COIN_NAME)
        if wallet is None:
            botregister = store.sql_register_user(str(member.id), COIN_NAME)
            wallet = store.sql_get_userwallet(str(member.id), COIN_NAME)
        depositAddress = wallet['balance_wallet_address']
        balance_actual = num_format_coin(wallet['actual_balance'] , COIN_NAME)
        balance_locked = num_format_coin(wallet['locked_balance'] , COIN_NAME)
        await ctx.send(
            f'**[ MY BALANCE]**\n\n'
            f' Deposit Address: `{depositAddress}`\n'
            f'{EMOJI_MONEYBAG} Available: {balance_actual} '
            f'{COIN_NAME}\n'
            f'{EMOJI_MONEYBAG} Pending: {balance_locked} '
            f'{COIN_NAME}\n'
            '**This is bot\'s tipjar address. Do not deposit here unless you want to deposit to this bot.**')
        return
    if member.bot == False:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Only for bot!!')
        return
    else:
        user = store.sql_register_user(bot.user.id, COIN_NAME)
        # Bypass other if they re in ENABLE_COIN_DOGE
        if COIN_NAME in ENABLE_COIN_DOGE:
            try:
                depositAddress = DOGE_getaccountaddress(str(member.id))
            except Exception as e:
                print(e)
            actual = float(DOGE_getbalance_acc(bot.user.id, 6))
            locked = float(DOGE_getbalance_acc(bot.user.id, 1))
            userdata_balance = store.sql_doge_balance(member.id, COIN_NAME)
            if actual == locked:
                balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
                balance_locked = num_format_coin(0 , COIN_NAME)
            else:
                balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
                if locked - actual + float(userdata_balance['Adjust']) < 0:
                    balance_locked =  num_format_coin(0, COIN_NAME)
                else:
                    balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
            await ctx.send(
                f'**[ MY {COIN_NAME} BALANCE]**\n'
                f' Deposit Address: `{depositAddress}`\n'
                f'{EMOJI_MONEYBAG} Available: {balance_actual} '
                f'{COIN_NAME}\n'
                f'{EMOJI_MONEYBAG} Pending: {balance_locked} '
                f'{COIN_NAME}\n'
                '**This is bot\'s tipjar address. Do not deposit here unless you want to deposit to this bot.**')
            return

        wallet = store.sql_get_userwallet(str(member.id), COIN_NAME)
        if wallet is None:
            botregister = store.sql_register_user(str(member.id), COIN_NAME)
            wallet = store.sql_get_userwallet(str(member.id), COIN_NAME)
        balance_actual = num_format_coin(wallet['actual_balance'] , COIN_NAME)
        balance_locked = num_format_coin(wallet['locked_balance'] , COIN_NAME)
        depositAddress = wallet['balance_wallet_address']
        await ctx.send(
            f'**[INFO BOT {member.name}\'s BALANCE]**\n\n'
            f' Deposit Address: `{depositAddress}`\n'
            f'{EMOJI_MONEYBAG} Available: {balance_actual} '
            f'{COIN_NAME}\n'
            f'{EMOJI_MONEYBAG} Pending: {balance_locked} '
            f'{COIN_NAME}\n'
            '**This is bot\'s tipjar address. Do not deposit here unless you want to deposit to this bot.**')
        return


@bot.command(pass_context=True, name='register', aliases=['registerwallet', 'reg', 'updatewallet'],
             help=bot_help_register)
async def register(ctx, wallet_address: str):
    # Check if maintenance
    if IS_MAINTENANCE == 1:
        if int(ctx.message.author.id) in MAINTENANCE_OWNER:
            pass
        else:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {config.maintenance_msg}')
            return
    else:
        pass
    # End Check if maintenance

    if wallet_address.isalnum() == False:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                       f'`{wallet_address}`')
        return

    COIN_NAME = get_cn_coin_from_address(wallet_address)
    if COIN_NAME:
        pass
    else:
        if (len(wallet_address) == 34) and wallet_address.startswith("D"):
            COIN_NAME = "DOGE"
            pass
        else:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Unknown Ticker.')
            return

    if COIN_NAME in MAINTENANCE_COIN:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return

    user_id = ctx.message.author.id
    user = store.sql_get_userwallet(ctx.message.author.id, COIN_NAME)
    if user:
        existing_user = user
        pass

    valid_address = None
    if COIN_NAME in ENABLE_COIN_DOGE:
        depositAddress = DOGE_getaccountaddress(ctx.message.author.id)
        user['balance_wallet_address'] = depositAddress
        if COIN_NAME == "DOGE":
            valid_address = DOGE_validaddress(str(wallet_address))
            if ('isvalid' in valid_address):
                if str(valid_address['isvalid']) == "True":
                    valid_address = wallet_address
                else:
                    valid_address = None
                pass
            pass
    else:
        if COIN_NAME in ENABLE_COIN:
            valid_address = addressvalidation.validate_address_cn(wallet_address, COIN_NAME)
    # correct print(valid_address)
    if valid_address is None:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid {COIN_NAME} address:\n'
                       f'`{wallet_address}`')
        return

    if valid_address != wallet_address:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid {COIN_NAME} address:\n'
                       f'`{wallet_address}`')
        return

    # if they want to register with tipjar address
    try:
        if user['balance_wallet_address'] == wallet_address:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You can not register with your {COIN_NAME} tipjar\'s address.\n'
                           f'`{wallet_address}`')
            return
        else:
            pass
    except Exception as e:
        await ctx.message.add_reaction(EMOJI_ERROR)
        print('Error during register user address:' + str(e))
        return

    serverinfo = get_info_pref_coin(ctx)
    server_prefix = serverinfo['server_prefix']
    if 'user_wallet_address' in existing_user:
        prev_address = existing_user['user_wallet_address']
        store.sql_update_user(user_id, wallet_address, COIN_NAME)
        if prev_address:
            await ctx.message.add_reaction(EMOJI_OK)
            await ctx.send(f'Your {COIN_NAME} {ctx.author.mention} withdraw address has been changed from:\n'
                           f'`{prev_address}`\n to\n '
                           f'`{wallet_address}`')
            return
        pass
    else:
        user = store.sql_update_user(user_id, wallet_address, COIN_NAME)
        await ctx.message.add_reaction(EMOJI_OK)
        await ctx.send(f'{ctx.author.mention} You have been registered {COIN_NAME} withdraw address.\n'
                       f'You can use `{server_prefix}withdraw AMOUNT {COIN_NAME}` anytime.')
        return


@bot.command(pass_context=True, help=bot_help_withdraw)
async def withdraw(ctx, amount: str, coin: str = None):
    botLogChan = bot.get_channel(id=LOG_CHAN)
    amount = amount.replace(",", "")

    # Check flood of tip
    repeatTx = 0
    for itemCoin in ENABLE_COIN:
        floodTip = store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration, itemCoin.upper())
        repeatTx = repeatTx + floodTip
    if repeatTx >= config.floodTip:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Cool down your tip or TX. or increase your amount next time.')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} reached max. TX threshold. Currently halted: `.withdraw`')
        return
    # End of Check flood of tip

    # Check if maintenance
    if IS_MAINTENANCE == 1:
        if int(ctx.message.author.id) in MAINTENANCE_OWNER:
            pass
        else:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {config.maintenance_msg}')
            return
    else:
        pass
    # End Check if maintenance

    try:
        amount = float(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    if coin is None:
        coin = "WRKZ"

    if coin.upper() in MAINTENANCE_COIN:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {coin.upper()} in maintenance.')
        return

    if coin.upper() in ENABLE_COIN:
        COIN_NAME = coin.upper()
        COIN_DEC = get_decimal(coin.upper())
        real_amount = int(amount * COIN_DEC)
        user = store.sql_get_userwallet(ctx.message.author.id, COIN_NAME)
        netFee = get_tx_fee(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        EMOJI_TIP = get_emoji(COIN_NAME)
    elif coin.upper() == "DOGE" or coin.upper() == "DOGECOIN":
        COIN_NAME = "DOGE"
        EMOJI_TIP = EMOJI_DOGE
        MinTx = config.daemonDOGE.min_tx_amount
        MaxTX = config.daemonDOGE.max_tx_amount
        netFee = config.daemonDOGE.tx_fee
        user_from = {}
        user_from['address'] = DOGE_getaccountaddress(ctx.message.author.id)
        user_from['actual_balance'] = float(DOGE_getbalance_acc(ctx.message.author.id, 6))
        real_amount = float(amount)
        userdata_balance = store.sql_doge_balance(ctx.message.author.id, COIN_NAME)
        if real_amount + netFee > float(user_from['actual_balance']) + float(userdata_balance['Adjust']):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to withdraw '
                           f'{num_format_coin(real_amount, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return
        if real_amount < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transaction cannot be smaller than '
                           f'{num_format_coin(MinTx, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return
        if real_amount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transaction cannot be bigger than '
                           f'{num_format_coin(MaxTX, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return
        wallet = store.sql_get_userwallet(ctx.message.author.id, "DOGE")
        withdrawTx = None
        if 'user_wallet_address' in wallet:
            withdrawTx = store.sql_external_doge_single(ctx.message.author.id, real_amount,
                                                        config.daemonDOGE.tx_fee, wallet['user_wallet_address'],
                                                        COIN_NAME, "WITHDRAW")
        if withdrawTx:
            withdrawAddress = wallet['user_wallet_address']
            await ctx.message.add_reaction(EMOJI_TIP)
            await ctx.message.author.send(
                                   f'{EMOJI_ARROW_RIGHTHOOK} You have withdrawn {num_format_coin(real_amount, COIN_NAME)} '
                                   f'{COIN_NAME} to `{withdrawAddress}`.\n'
                                   f'Transaction hash: `{withdrawTx}`\n'
                                   'Network fee deducted from the amount.')
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            return
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} INVALID TICKER!')
        return

    if not user['user_wallet_address']:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You do not have a withdrawal address, please use '
                       f'`.register wallet_address` to register.')
        return

    if real_amount + netFee >= user['actual_balance']:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to withdraw '
                       f'{num_format_coin(real_amount, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return

    if real_amount > MaxTX:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                       f'{num_format_coin(MaxTX, COIN_NAME)} '
                       f'{COIN_NAME}')
        return
    elif real_amount < MinTx:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be lower than '
                       f'{num_format_coin(MinTx, COIN_NAME)} '
                       f'{COIN_NAME}')
        return

    # Get wallet status
    walletStatus = daemonrpc_client.getWalletStatus(COIN_NAME)

    if walletStatus is None:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Wallet service hasn\'t started.')
        return
    else:
        localDaemonBlockCount = int(walletStatus['blockCount'])
        networkBlockCount = int(walletStatus['knownBlockCount'])
        if networkBlockCount - localDaemonBlockCount >= 20:
            # if height is different by 20
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount / networkBlockCount * 100, 2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Wallet service hasn\'t sync fully with network or being re-sync. More info:\n```'
                           f'networkBlockCount:     {t_networkBlockCount}\n'
                           f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                           f'Progress %:            {t_percent}\n```'
                           )
            return
        else:
            pass
    # End of wallet status

    withdrawal = await store.sql_withdraw(ctx.message.author.id, real_amount, COIN_NAME)

    if withdrawal:
        await ctx.message.add_reaction(EMOJI_TIP)
        await botLogChan.send(f'A user successfully executed `.withdraw {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`')
        await ctx.message.author.send(
            f'{EMOJI_ARROW_RIGHTHOOK} You have withdrawn {num_format_coin(real_amount, COIN_NAME)} '
            f'{COIN_NAME}.\n'
            f'Transaction hash: `{withdrawal}`')
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await botLogChan.send(f'A user failed to execute `.withdraw {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`')
        await ctx.send(f'{ctx.author.mention} You may need to `optimize` or try again.')
        return


@bot.command(pass_context=True, help=bot_help_donate)
async def donate(ctx, amount: str, coin: str = None):
    botLogChan = bot.get_channel(id=LOG_CHAN)
    amount = amount.replace(",", "")

    # Check flood of tip
    repeatTx = 0
    for itemCoin in ENABLE_COIN:
        floodTip = store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration, itemCoin.upper())
        repeatTx = repeatTx + floodTip
    if repeatTx >= config.floodTip:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Cool down your tip or TX. or increase your amount next time.')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} reached max. TX threshold. Currently halted: `.donate`')
        return
    # End of Check flood of tip

    # Check if maintenance
    if IS_MAINTENANCE == 1:
        if int(ctx.message.author.id) in MAINTENANCE_OWNER:
            pass
        else:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {config.maintenance_msg}')
            return
    else:
        pass
    # End Check if maintenance

    try:
        amount = float(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    if coin is None:
        # If private
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send(f'{EMOJI_RED_NO} You need to specify ticker if in DM or private.')
            return
        # If public
        serverinfo = store.sql_info_by_server(str(ctx.guild.id))
        if 'default_coin' in serverinfo:
            if serverinfo['default_coin'].upper() in ENABLE_COIN:
                coin = serverinfo['default_coin'].upper()
            else:
                coin = "WRKZ"
        else:
            coin = "WRKZ"
    if coin.upper() in MAINTENANCE_COIN:
        await ctx.send(f'{EMOJI_RED_NO} {coin.upper()} in maintenance.')
        return

    if coin.upper() in ENABLE_COIN:
        CoinAddress = get_donate_address(coin.upper())
        COIN_NAME = coin.upper()
        COIN_DEC = get_decimal(coin.upper())
        real_amount = int(amount * COIN_DEC)
        user_from = store.sql_get_userwallet(ctx.message.author.id, COIN_NAME)
        netFee = get_tx_fee(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        EMOJI_TIP = get_emoji(COIN_NAME)
    elif coin.upper() == "DOGE" or coin.upper() == "DOGECOIN":
        COIN_NAME = "DOGE"
        EMOJI_TIP = EMOJI_DOGE
        MinTx = config.daemonDOGE.min_mv_amount
        MaxTX = config.daemonDOGE.max_mv_amount
        user_from = {}
        user_from['address'] = DOGE_getaccountaddress(ctx.message.author.id)
        user_from['actual_balance'] = float(DOGE_getbalance_acc(ctx.message.author.id, 6))
        real_amount = float(amount)
        userdata_balance = store.sql_doge_balance(ctx.message.author.id, COIN_NAME)
        if real_amount > float(user_from['actual_balance']) + float(userdata_balance['Adjust']):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to donate '
                           f'{num_format_coin(real_amount, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return
        if real_amount < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                           f'{num_format_coin(MinTx, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return
        if real_amount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                           f'{num_format_coin(MaxTX, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return

        donateTx = store.sql_mv_doge_single(ctx.message.author.id, config.daemonDOGE.DonateAccount, real_amount,
                                            COIN_NAME, "DONATE")
        if donateTx:
            await ctx.message.add_reaction(EMOJI_TIP)
            await botLogChan.send(f'{EMOJI_MONEYFACE} TipBot got donation: {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}')
            await ctx.message.author.send(
                                   f'{EMOJI_MONEYFACE} TipBot got donation: {num_format_coin(real_amount, COIN_NAME)}'
                                   f'{COIN_NAME} '
                                   f'\n'
                                   f'Thank you.')
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            return
        return

    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} INVALID TICKER!')
        return

    if real_amount + netFee >= user_from['actual_balance']:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to donate '
                       f'{num_format_coin(real_amount, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return

    if real_amount > MaxTX:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                       f'{num_format_coin(MaxTX, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return
    elif real_amount < MinTx:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                       f'{num_format_coin(MinTx, COIN_NAME)} '
                       f'{COIN_NAME}.')

        return

    # Get wallet status
    walletStatus = daemonrpc_client.getWalletStatus(COIN_NAME)
    if walletStatus is None:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Wallet service hasn\'t started.')
        return
    else:
        localDaemonBlockCount = int(walletStatus['blockCount'])
        networkBlockCount = int(walletStatus['knownBlockCount'])
        if networkBlockCount - localDaemonBlockCount >= 20:
            # if height is different by 20
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount / networkBlockCount * 100, 2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Wallet service hasn\'t sync fully with network or being re-sync. More info:\n```'
                           f'networkBlockCount:     {t_networkBlockCount}\n'
                           f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                           f'Progress %:            {t_percent}\n```'
                           )
            return
        else:
            pass
    # End of wallet status

    tip = await store.sql_donate(ctx.message.author.id, CoinAddress, real_amount, COIN_NAME)

    if tip:
        await ctx.message.add_reaction(EMOJI_TIP)
        await botLogChan.send(f'{EMOJI_MONEYFACE} TipBot got donation: {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}')
        await ctx.message.author.send(
                               f'{EMOJI_MONEYFACE} TipBot got donation: {num_format_coin(real_amount, COIN_NAME)} '
                               f'{COIN_NAME} '
                               f'\n'
                               f'Thank you. Transaction hash: `{tip}`')
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Thank you but you may need to `optimize` or try again later.')
        return


@bot.command(pass_context=True, help=bot_help_notifytip)
async def notifytip(ctx, onoff: str):
    if onoff.upper() not in ["ON", "OFF"]:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send('You need to use only `ON` or `OFF`.')
        return

    onoff = onoff.upper()
    notifyList = store.sql_get_tipnotify()
    if onoff == "ON":
        if str(ctx.message.author.id) in notifyList:
            store.sql_toggle_tipnotify(str(ctx.message.author.id), "ON")
            await ctx.send('OK, you will get all notification when tip.')
            return
        else:
            await ctx.send('You already have notification ON by default.')
            return
    elif onoff == "OFF":
        if str(ctx.message.author.id) in notifyList:
            await ctx.send('You already have notification OFF.')
            return
        else:
            store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            await ctx.send('OK, you will not get any notification when anyone tips.')
            return


@bot.command(pass_context=True, help=bot_help_tip)
async def tip(ctx, amount: str, *args):
    botLogChan = bot.get_channel(id=LOG_CHAN)
    amount = amount.replace(",", "")

    try:
        amount = float(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send(f'{EMOJI_RED_NO} This command can not be in private.')
        return

    serverinfo = store.sql_info_by_server(str(ctx.guild.id))
    try:
        COIN_NAME = args[0]
        if COIN_NAME.upper() not in ENABLE_COIN:
            if (COIN_NAME.upper() in ENABLE_COIN_DOGE):
                COIN_NAME = COIN_NAME.upper()
            elif ('default_coin' in serverinfo):
                COIN_NAME = serverinfo['default_coin'].upper()
        else:
            COIN_NAME = COIN_NAME.upper()
    except:
        if ('default_coin' in serverinfo):
            COIN_NAME = serverinfo['default_coin'].upper()
    print("COIN_NAME: " + COIN_NAME)

    if COIN_NAME.upper() in MAINTENANCE_COIN:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME.upper()} in maintenance.')
        return

    if len(ctx.message.mentions) == 0:
        # Use how time.
        if len(args) >= 2:
            time_given = None
            if args[0].upper() == "LAST" or args[1].upper() == "LAST":
                time_string = ctx.message.content.lower().split("last",1)[1].strip()
                time_second = None
                try:
                    time_string = time_string.replace("hours", "h")
                    time_string = time_string.replace("minutes", "mn")
                    time_string = time_string.replace("hrs", "h")
                    time_string = time_string.replace("hr", "h")
                    time_string = time_string.replace("mns", "mn")
                    mult = {'h': 60*60, 'mn': 60}
                    time_second = sum(int(num) * mult.get(val, 1) for num, val in re.findall('(\d+)(\w+)', time_string))
                except Exception as e:
                    print(e)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid time given. Please use this example: `.tip 1,000 last 5h 12mn`')
                    return
                try:
                    time_given = int(time_second)
                except ValueError:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid time given check.')
                    return
                if time_given:
                    if time_given < 5*60 or time_given > 24*60*60:
                        await ctx.message.add_reaction(EMOJI_ERROR)
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please try time inteval between 5 minutes to 24 hours.')
                        return
                    else:
                        message_talker = store.sql_get_messages(str(ctx.message.guild.id), str(ctx.message.channel.id), time_given)
                        if len(message_talker) == 0:
                            await ctx.message.add_reaction(EMOJI_ERROR)
                            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is no active talker in such period.')
                            return
                        else:
                            print(message_talker)
                            await _tip_talker(ctx, amount, message_talker, COIN_NAME)
                            return
            else:
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
                return
        else:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
            return
    elif len(ctx.message.mentions) == 1:
        member = ctx.message.mentions[0]
        if ctx.message.author.id == member.id:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Tip me if you want.')
            return
        pass
    elif len(ctx.message.mentions) > 1:
        await _tip(ctx, amount, COIN_NAME)
        return

    # Check flood of tip
    repeatTx = 0
    for itemCoin in ENABLE_COIN:
        floodTip = store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration, itemCoin.upper())
        repeatTx = repeatTx + floodTip
    if repeatTx >= config.floodTip:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Cool down your tip or TX. or increase your amount next time.')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} reached max. TX threshold. Currently halted: `.tip`')
        return
    # End of Check flood of tip

    # Check if maintenance
    if IS_MAINTENANCE == 1:
        if int(ctx.message.author.id) in MAINTENANCE_OWNER:
            pass
        else:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {config.maintenance_msg}')
            return
    else:
        pass
    # End Check if maintenance

    notifyList = store.sql_get_tipnotify()
    if COIN_NAME in ENABLE_COIN:
        user_from = store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        user_to = store.sql_register_user(str(member.id), COIN_NAME)
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        netFee = get_tx_fee(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        EMOJI_TIP = get_emoji(COIN_NAME)
    elif COIN_NAME.upper() == "DOGE" or COIN_NAME.upper() == "DOGECOIN":
        COIN_NAME = "DOGE"
        EMOJI_TIP = EMOJI_DOGE
        MinTx = config.daemonDOGE.min_mv_amount
        MaxTX = config.daemonDOGE.max_mv_amount
        user_from = {}
        user_from['address'] = DOGE_getaccountaddress(str(ctx.message.author.id))
        user_from['actual_balance'] = float(DOGE_getbalance_acc(str(ctx.message.author.id), 6))
        user_to = {}
        user_to['address'] = DOGE_getaccountaddress(str(member.id))
        real_amount = float(amount)
        userdata_balance = store.sql_doge_balance(str(ctx.message.author.id), COIN_NAME)
        if real_amount > float(user_from['actual_balance']) + float(userdata_balance['Adjust']):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send tip of '
                            f'{num_format_coin(real_amount, COIN_NAME)} '
                            f'{COIN_NAME} to {member.name}.')
            return
        if real_amount < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} Transactions cannot be smaller than '
                           f'{num_format_coin(MinTx, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return
        if real_amount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} Transactions cannot be bigger than '
                           f'{num_format_coin(MaxTX, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return

        tip = store.sql_mv_doge_single(str(ctx.message.author.id), str(member.id), real_amount, COIN_NAME, "TIP")
        if tip:
            servername = serverinfo['servername']
            await ctx.message.add_reaction(EMOJI_TIP)
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Tip of {num_format_coin(real_amount, COIN_NAME)} '
                    f'{COIN_NAME} '
                    f'was sent to `{member.name}` in server `{servername}`\n')
            except Exception as e:
                print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
                print(e)
            if str(member.id) not in notifyList:
                try:
                    await member.send(
                        f'{EMOJI_MONEYFACE} You got a tip of {num_format_coin(real_amount, COIN_NAME)} '
                        f'{COIN_NAME} from `{ctx.message.author.name}` in server `{servername}`\n'
                        f'{NOTIFICATION_OFF_CMD}')
                except Exception as e:
                    print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
                    store.sql_toggle_tipnotify(str(member.id), "OFF")
                    print(e)
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
        return

    if real_amount + netFee >= user_from['actual_balance']:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send tip of '
                        f'{num_format_coin(real_amount, COIN_NAME)} '
                        f'{COIN_NAME} to {member.name}.')
        return

    if real_amount > MaxTX:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                       f'{num_format_coin(MaxTX, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return
    elif real_amount < MinTx:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                       f'{num_format_coin(MinTx, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return

    # Get wallet status
    walletStatus = daemonrpc_client.getWalletStatus(COIN_NAME)
    if walletStatus is None:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Wallet service hasn\'t started.')
        return
    else:
        localDaemonBlockCount = int(walletStatus['blockCount'])
        networkBlockCount = int(walletStatus['knownBlockCount'])
        if networkBlockCount - localDaemonBlockCount >= 20:
            # if height is different by 20
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount / networkBlockCount * 100, 2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Wallet service hasn\'t sync fully with network or being re-sync. More info:\n```'
                           f'networkBlockCount:     {t_networkBlockCount}\n'
                           f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                           f'Progress %:            {t_percent}\n```'
                           )
            return
        else:
            pass
    # End of wallet status
    tip = None
    try:
        tip = await store.sql_send_tip(str(ctx.message.author.id), str(member.id), real_amount, COIN_NAME)
    except Exception as e:
        print(e)
    if tip:
        servername = serverinfo['servername']
        await ctx.message.add_reaction(EMOJI_TIP)
        # tipper shall always get DM. Ignore notifyList
        try:
            await ctx.message.author.send(
                f'{EMOJI_ARROW_RIGHTHOOK} Tip of {num_format_coin(real_amount, COIN_NAME)} '
                f'{COIN_NAME} '
                f'was sent to `{member.name}` in server `{servername}`\n'
                f'Transaction hash: `{tip}`')
        except Exception as e:
            # add user to notifyList
            print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
            store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            print(e)
        if str(member.id) not in notifyList:
            try:
                await member.send(
                    f'{EMOJI_MONEYFACE} You got a tip of {num_format_coin(real_amount, COIN_NAME)} '
                    f'{COIN_NAME} from `{ctx.message.author.name}` in server `{servername}`\n'
                    f'Transaction hash: `{tip}`\n'
                    f'{NOTIFICATION_OFF_CMD}')
            except Exception as e:
                # add user to notifyList
                print('Adding: ' + str(member.id) + ' not to receive DM tip')
                store.sql_toggle_tipnotify(str(member.id), "OFF")
                print(e)
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Can not deliver TX for {COIN_NAME} right now. Try again soon.')
        return


@bot.command(pass_context=True, help=bot_help_tipall)
async def tipall(ctx, amount: str, *args):
    botLogChan = bot.get_channel(id=LOG_CHAN)
    amount = amount.replace(",", "")

    try:
        amount = float(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send(f'{EMOJI_RED_NO} This command can not be in private.')
        return

    serverinfo = store.sql_info_by_server(str(ctx.guild.id))
    if len(args) == 0:
        if 'default_coin' in serverinfo:
            COIN_NAME = serverinfo['default_coin'].upper()
        else:
            COIN_NAME = "WRKZ"
    else:
        if args[0].upper() not in ENABLE_COIN:
            if (args[0].upper() in ENABLE_COIN_DOGE):
                COIN_NAME = args[0].upper()
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
                return
        else:
            COIN_NAME = args[0].upper()
    print('TIPALL COIN_NAME:' + COIN_NAME)

    if COIN_NAME.upper() in MAINTENANCE_COIN:
        await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME.upper()} in maintenance.')
        return

    # Check flood of tip
    repeatTx = 0
    for itemCoin in ENABLE_COIN:
        floodTip = store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration, itemCoin.upper())
        repeatTx = repeatTx + floodTip
    if repeatTx >= config.floodTip:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Cool down your tip or TX. or increase your amount next time.')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} reached max. TX threshold. Currently halted: `.tipall`')
        return
    # End of Check flood of tip

    # Check if maintenance
    if IS_MAINTENANCE == 1:
        if int(ctx.message.author.id) in MAINTENANCE_OWNER:
            pass
        else:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {config.maintenance_msg}')
            return
    else:
        pass
    # End Check if maintenance

    notifyList = store.sql_get_tipnotify()

    if COIN_NAME in ENABLE_COIN:
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        netFee = get_tx_fee(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        EMOJI_TIP = get_emoji(COIN_NAME)
    elif COIN_NAME.upper() == "DOGE" or COIN_NAME.upper() == "DOGECOIN":
        COIN_NAME = "DOGE"
        EMOJI_TIP = EMOJI_DOGE
        MinTx = config.daemonDOGE.min_mv_amount
        MaxTX = config.daemonDOGE.max_mv_amount
        user_from = {}
        user_from['address'] = DOGE_getaccountaddress(ctx.message.author.id)
        user_from['actual_balance'] = float(DOGE_getbalance_acc(ctx.message.author.id, 6))
        real_amount = float(amount)
        userdata_balance = store.sql_doge_balance(ctx.message.author.id, COIN_NAME)
        if real_amount > float(user_from['actual_balance']) + float(userdata_balance['Adjust']):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send tip of '
                            f'{num_format_coin(real_amount, COIN_NAME)} '
                            f'{COIN_NAME}.')
            return
        if real_amount < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                           f'{num_format_coin(MinTx, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return
        if real_amount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                           f'{num_format_coin(MaxTX, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return

        listMembers = [member for member in ctx.guild.members if member.status != discord.Status.offline]
        # Check number of receivers.
        if len(listMembers) > config.tipallMax:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} The number of receivers are too many. This command isn\'t available here.')
            return
        # End of checking receivers numbers.

        memids = []  # list of member ID
        for member in listMembers:
            # print(member.name) # you'll just print out Member objects your way.
            if ctx.message.author.id != member.id:
                # user_to = DOGE_getaccountaddress(str(member.id))
                if (str(member.status) != 'offline'):
                    if (member.bot == False):
                        memids.append(str(member.id))
        amountDiv = round(real_amount / len(memids), 4)
        # print(memids)
        if (real_amount / len(memids)) < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                           f'{num_format_coin(MinTx, COIN_NAME)} '
                           f'{COIN_NAME} for each member. You need at least {num_format_coin(len(memids) * MinTx, COIN_NAME)}.')
            return

        tips = store.sql_mv_doge_multiple(ctx.message.author.id, memids, amountDiv, COIN_NAME, "TIPALL")
        if tips:
            servername = serverinfo['servername']
            tipAmount = num_format_coin(real_amount, COIN_NAME)
            ActualSpend_str = num_format_coin(amountDiv * len(memids), COIN_NAME)
            amountDiv_str = num_format_coin(amountDiv, COIN_NAME)
            await ctx.message.add_reaction(EMOJI_TIP)
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Tip of {tipAmount} '
                    f'{COIN_NAME} '
                    f'was sent spread to ({len(memids)}) members in server `{servername}`.\n'
                    f'Each member got: `{amountDiv_str}{COIN_NAME}`\n'
                    f'Actual spending: `{ActualSpend_str}{COIN_NAME}`')
            except Exception as e:
                # add user to notifyList
                print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
                print(e)
            for member in listMembers:
                if ctx.message.author.id != member.id:
                    if str(member.status) != 'offline':
                        if member.bot == False:
                            if str(member.id) not in notifyList:
                                try:
                                    await member.send(
                                        f'{EMOJI_MONEYFACE} You got a tip of {amountDiv_str} '
                                        f'{COIN_NAME} from `{ctx.message.author.name}` `.tipall` in server `{servername}`\n'
                                        f'{NOTIFICATION_OFF_CMD}')
                                except Exception as e:
                                    # add user to notifyList
                                    print('Adding: ' + str(member.id) + ' not to receive DM tip')
                                    store.sql_toggle_tipnotify(str(member.id), "OFF")
                                    print(e)
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
        return

    listMembers = [member for member in ctx.guild.members if member.status != discord.Status.offline]
    # Check number of receivers.
    if len(listMembers) > config.tipallMax:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} The number of receivers are too many. This command isn\'t available here.')
        return
    # End of checking receivers numbers.
    memids = []  # list of member ID
    for member in listMembers:
        # print(member.name) # you'll just print out Member objects your way.
        if ctx.message.author.id != member.id:
            user_to = store.sql_register_user(str(member.id), COIN_NAME)
            if str(member.status) != 'offline':
                if member.bot == False:
                    memids.append(user_to['balance_wallet_address'])

    user_from = store.sql_get_userwallet(ctx.message.author.id, COIN_NAME)

    if real_amount + netFee >= user_from['actual_balance']:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to spread tip of '
                       f'{num_format_coin(real_amount, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return

    if real_amount > MaxTX:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                       f'{num_format_coin(MaxTX, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return
    elif real_amount < MinTx:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                       f'{num_format_coin(MinTx, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return

    elif (real_amount / len(memids)) < MinTx:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                       f'{num_format_coin(MinTx, COIN_NAME)} '
                       f'{COIN_NAME} for each member. You need at least {num_format_coin(len(memids) * MinTx, COIN_NAME)}.')
        return

    amountDiv = int(round(real_amount / len(memids), 2))  # cut 2 decimal only
    destinations = []
    addresses = []
    for desti in memids:
        destinations.append({"address": desti, "amount": amountDiv})
        addresses.append(desti)

    # Get wallet status
    walletStatus = daemonrpc_client.getWalletStatus(COIN_NAME)
    if walletStatus is None:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Wallet service hasn\'t started.')
        return
    else:
        localDaemonBlockCount = int(walletStatus['blockCount'])
        networkBlockCount = int(walletStatus['knownBlockCount'])
        if networkBlockCount - localDaemonBlockCount >= 20:
            # if height is different by 20
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount / networkBlockCount * 100, 2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Wallet service hasn\'t sync fully with network or being re-sync. More info:\n```'
                           f'networkBlockCount:     {t_networkBlockCount}\n'
                           f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                           f'Progress %:            {t_percent}\n```'
                           )
            return
        else:
            pass
    # End of wallet status

    # print(destinations)
    tip = None
    try:
        tip = await store.sql_send_tipall(ctx.message.author.id, destinations, real_amount, COIN_NAME)
    except Exception as e:
        print(e)
    if tip:
        servername = serverinfo['servername']
        await ctx.message.add_reaction(EMOJI_TIP)
        store.sql_update_some_balances(addresses, COIN_NAME)
        TotalSpend = num_format_coin(real_amount, COIN_NAME)
        ActualSpend = int(amountDiv * len(destinations) + netFee)
        ActualSpend_str =  num_format_coin(ActualSpend, COIN_NAME)
        amountDiv_str = num_format_coin(amountDiv, COIN_NAME)
        # tipper shall always get DM. Ignore notifyList
        try:
            await ctx.message.author.send(
                f'{EMOJI_ARROW_RIGHTHOOK} Tip of {TotalSpend} '
                f'{COIN_NAME} '
                f'was sent spread to ({len(destinations)}) members in server `{servername}`.\n'
                f'Transaction hash: `{tip}`.\n'
                f'Each member got: `{amountDiv_str}{COIN_NAME}`\n'
                f'Actual spending: `{ActualSpend_str}{COIN_NAME}`')
        except Exception as e:
            # add user to notifyList
            print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
            store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            print(e)
        numMsg = 0
        for member in listMembers:
            # print(member.name) # you'll just print out Member objects your way.
            if ctx.message.author.id != member.id:
                if str(member.status) != 'offline':
                    if member.bot == False:
                        if str(member.id) not in notifyList:
                            try:
                                user = bot.get_user(id=member.id)
                                await user.send(
                                    f'{EMOJI_MONEYFACE} You got a tip of {amountDiv_str} '
                                    f'{COIN_NAME} from `{ctx.message.author.name}` `.tipall` in server `{servername}`\n'
                                    f'Transaction hash: `{tip}`\n'
                                    f'{NOTIFICATION_OFF_CMD}')
                                numMsg = numMsg + 1
                            except Exception as e:
                                # add user to notifyList
                                print('Adding: ' + str(member.id) + ' not to receive DM tip')
                                store.sql_toggle_tipnotify(str(member.id), "OFF")
                                print(e)
        print('Messaged to users: (.tipall): '+str(numMsg))
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Can not deliver TX for {COIN_NAME} right now. Try again soon.')
        return


@bot.command(pass_context=True, help=bot_help_send)
async def send(ctx, amount: str, CoinAddress: str):
    botLogChan = bot.get_channel(id=LOG_CHAN)
    amount = amount.replace(",", "")

    # Check flood of tip
    repeatTx = 0
    for itemCoin in ENABLE_COIN:
        floodTip = store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration, itemCoin.upper())
        repeatTx = repeatTx + floodTip
    if repeatTx >= config.floodTip:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO}{ctx.author.mention} Cool down your tip or TX. or increase your amount next time.')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} reached max. TX threshold. Currently halted: `.send`')
        return
    # End of Check flood of tip

    # Check if maintenance
    if IS_MAINTENANCE == 1:
        if int(ctx.message.author.id) in MAINTENANCE_OWNER:
            pass
        else:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {config.maintenance_msg}')
            return
    else:
        pass
    # End Check if maintenance

    try:
        amount = float(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    # Check which coinname is it.
    COIN_NAME = get_cn_coin_from_address(CoinAddress)
    if COIN_NAME:
        pass
    else:
        if (len(CoinAddress) == 34) and CoinAddress.startswith("D"):
            COIN_NAME = "DOGE"
            addressLength = config.daemonDOGE.AddrLen
            EMOJI_TIP = EMOJI_DOGE
            MinTx = config.daemonDOGE.min_tx_amount
            MaxTX = config.daemonDOGE.max_tx_amount
            netFee = config.daemonDOGE.tx_fee
            valid_address = DOGE_validaddress(str(CoinAddress))
            if 'isvalid' in valid_address:
                if str(valid_address['isvalid']) == "True":
                    pass
                else:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Address: `{CoinAddress}` '
                                    'is invalid.')
                    return

            user_from = {}
            user_from['address'] = DOGE_getaccountaddress(ctx.message.author.id)
            user_from['actual_balance'] = float(DOGE_getbalance_acc(ctx.message.author.id, 6))
            real_amount = float(amount)
            userdata_balance = store.sql_doge_balance(ctx.message.author.id, COIN_NAME)
            if real_amount + netFee > float(user_from['actual_balance']) + float(userdata_balance['Adjust']):
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send out '
                               f'{num_format_coin(real_amount, COIN_NAME)} '
                               f'{COIN_NAME}.')
                return
            if real_amount < MinTx:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transaction cannot be smaller than '
                               f'{num_format_coin(MinTx, COIN_NAME)} '
                               f'{COIN_NAME}.')
                return
            if real_amount > MaxTX:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transaction cannot be bigger than '
                               f'{num_format_coin(MaxTX, COIN_NAME)} '
                               f'{COIN_NAME}.')
                return

            SendTx = store.sql_external_doge_single(ctx.message.author.id, real_amount, config.daemonDOGE.tx_fee,
                                                    CoinAddress, COIN_NAME, "SEND")
            if SendTx:
                await ctx.message.add_reaction(EMOJI_TIP)
                await botLogChan.send(f'A user successfully executed `.send {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`.')
                await ctx.message.author.send(f'{EMOJI_ARROW_RIGHTHOOK} You have sent {num_format_coin(real_amount, COIN_NAME)} '
                                              f'{COIN_NAME} to `{CoinAddress}`.\n'
                                              f'Transaction hash: `{SendTx}`\n'
                                              'Network fee deducted from the amount.')
                return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await botLogChan.send(f'A user failed to execute `.send {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`.')
                return
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                           f'`{CoinAddress}`')
            return

    COIN_DEC = get_decimal(COIN_NAME)
    netFee = get_tx_fee(COIN_NAME)
    MinTx = get_min_tx_amount(COIN_NAME)
    MaxTX = get_max_tx_amount(COIN_NAME)
    real_amount = int(amount * COIN_DEC)
    addressLength = get_addrlen(COIN_NAME)
    IntaddressLength = get_intaddrlen(COIN_NAME)
    EMOJI_TIP = get_emoji(COIN_NAME)

    if COIN_NAME.upper() in MAINTENANCE_COIN:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME.upper()} in maintenance.')
        return

    if len(CoinAddress) == int(addressLength):
        valid_address = addressvalidation.validate_address_cn(CoinAddress, COIN_NAME)
        # print(valid_address)
        if valid_address is None:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                           f'`{CoinAddress}`')
            return
        if valid_address != CoinAddress:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                           f'`{CoinAddress}`')
            return
    elif len(CoinAddress) == int(IntaddressLength):
        valid_address = addressvalidation.validate_integrated_cn(CoinAddress, COIN_NAME)
        # print(valid_address)
        if (valid_address == 'invalid'):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid integrated address:\n'
                           f'`{CoinAddress}`')
            return
        if (len(valid_address) == 2):
            iCoinAddress = CoinAddress
            CoinAddress = valid_address['address']
            paymentid = valid_address['integrated_id']
    elif len(CoinAddress) == int(addressLength) + 64 + 1:
        valid_address = {}
        check_address = CoinAddress.split(".")
        if len(check_address) != 2:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid {COIN_NAME} address + paymentid')
            return
        else:
            valid_address_str = addressvalidation.validate_address_cn(check_address[0], COIN_NAME)
            paymentid = check_address[1].strip()
            if valid_address_str is None:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                               f'`{check_address[0]}`')
                return
            else:
                valid_address['address'] = valid_address_str
        # Check payment ID
            if len(paymentid) == 64:
                if not re.match(r'[a-zA-Z0-9]{64,}', paymentid.strip()):
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} PaymentID: `{paymentid}`\n'
                                    'Should be in 64 correct format.')
                    return
                else:
                    CoinAddress = valid_address['address']
                    valid_address['paymentid'] = paymentid
                    iCoinAddress = addressvalidation.make_integrated_cn(valid_address['address'], COIN_NAME, paymentid)['integrated_address']
                    pass
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} PaymentID: `{paymentid}`\n'
                                'Incorrect length')
                return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                       f'`{CoinAddress}`')
        return

    real_amount = int(amount * COIN_DEC)

    user_from = store.sql_get_userwallet(ctx.message.author.id, COIN_NAME)
    if user_from['balance_wallet_address'] == CoinAddress:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You can not send to your own deposit address.')
        return

    if real_amount + get_tx_fee(COIN_NAME) >= user_from['actual_balance']:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send tip of '
                       f'{num_format_coin(real_amount, COIN_NAME)} '
                       f'{COIN_NAME} to {CoinAddress}.')

        return

    if real_amount > MaxTX:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                       f'{num_format_coin(MaxTX, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return
    elif real_amount < MinTx:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                       f'{num_format_coin(MinTx, COIN_NAME)} '
                       f'{COIN_NAME}.')

        return

    # Get wallet status
    walletStatus = daemonrpc_client.getWalletStatus(COIN_NAME)
    if walletStatus is None:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Wallet service hasn\'t started.')
        return
    else:
        localDaemonBlockCount = int(walletStatus['blockCount'])
        networkBlockCount = int(walletStatus['knownBlockCount'])
        if networkBlockCount - localDaemonBlockCount >= 20:
            # if height is different by 20
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount / networkBlockCount * 100, 2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Wallet service hasn\'t sync fully with network or being re-sync. More info:\n```'
                           f'networkBlockCount:     {t_networkBlockCount}\n'
                           f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                           f'Progress %:            {t_percent}\n```'
                           )
            return
        else:
            pass
    # End of wallet status

    if len(valid_address) == 2:
        tip = None
        try:
            tip = await store.sql_send_tip_Ex_id(ctx.message.author.id, CoinAddress, real_amount, paymentid, COIN_NAME)
        except Exception as e:
            print(e)
        if tip:
            await ctx.message.add_reaction(EMOJI_TIP)
            await botLogChan.send(f'A user successfully executed `.send {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}` with paymentid.')
            await ctx.message.author.send(
                                   f'{EMOJI_ARROW_RIGHTHOOK} You have sent {num_format_coin(real_amount, COIN_NAME)} '
                                   f'{COIN_NAME} '
                                   f'to `{iCoinAddress}`\n\n'
                                   f'Address: `{CoinAddress}`\n'
                                   f'Payment ID: `{paymentid}`\n'
                                   f'Transaction hash: `{tip}`')
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await botLogChan.send(f'A user failed to execute `.send {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}` with paymentid.')
            await ctx.send('{ctx.author.mention} You may need to `optimize` or retry.')
            return
    else:
        tip = None
        try:
            tip = await store.sql_send_tip_Ex(ctx.message.author.id, CoinAddress, real_amount, COIN_NAME)
        except Exception as e:
            print(e)
        if tip:
            await ctx.message.add_reaction(EMOJI_TIP)
            await botLogChan.send(f'A user successfully executed `.send {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`.')
            await ctx.message.author.send(f'{EMOJI_ARROW_RIGHTHOOK} You have sent {num_format_coin(real_amount, COIN_NAME)} '
                                          f'{COIN_NAME} '
                                          f'to `{CoinAddress}`\n'
                                          f'Transaction hash: `{tip}`')
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await botLogChan.send(f'A user failed to execute `.send {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`.')
            await ctx.send(f'{ctx.author.mention} Can not deliver TX for {COIN_NAME} right now. Try again soon.')
            return


@bot.command(pass_context=True, name='address', aliases=['addr'], help=bot_help_address)
async def address(ctx, *args):
    if len(args) == 0:
        if isinstance(ctx.message.channel, discord.DMChannel):
            COIN_NAME = 'WRKZ'
        else:
            serverinfo = store.sql_info_by_server(str(ctx.guild.id))
            try:
                COIN_NAME = args[0]
                if COIN_NAME.upper() not in ENABLE_COIN:
                    if COIN_NAME.upper() in ENABLE_COIN_DOGE:
                        COIN_NAME = COIN_NAME.upper()
                    elif 'default_coin' in serverinfo:
                        COIN_NAME = serverinfo['default_coin'].upper()
                else:
                    COIN_NAME = COIN_NAME.upper()
            except:
                if 'default_coin' in serverinfo:
                    COIN_NAME = serverinfo['default_coin'].upper()
            print("COIN_NAME: " + COIN_NAME)
        donateAddress = get_donate_address(COIN_NAME.upper()) or 'WrkzRNDQDwFCBynKPc459v3LDa1gEGzG3j962tMUBko1fw9xgdaS9mNiGMgA9s1q7hS1Z8SGRVWzcGc8Sh8xsvfZ6u2wJEtoZB'
        await ctx.send('**[ ADDRESS CHECKING EXAMPLES ]**\n\n'
                       f'`.address {donateAddress}`\n'
                       'That will check if the address is valid. Integrated address is also supported. '
                       'If integrated address is input, bot will tell you the result of :address + paymentid\n\n'
                       '`.address <coin_address> <paymentid>`\n'
                       'This will generate an integrate address.\n\n')
        return

    CoinAddress = args[0]
    COIN_NAME = None

    if CoinAddress.isalnum() == False:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                       f'`{CoinAddress}`')
        return
    # Check which coinname is it.
    COIN_NAME = get_cn_coin_from_address(CoinAddress)
    if COIN_NAME:
        pass
    else:
        if len(CoinAddress) == 34:
            if CoinAddress.startswith("D"):
                COIN_NAME = "DOGE"
                addressLength = config.daemonDOGE.AddrLen
            if CoinAddress[0] in ["3", "M", "L"]:
                COIN_NAME = "LTC"
                addressLength = config.daemonLTC.AddrLen
            pass
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                           f'`{CoinAddress}`')
            return

    addressLength = get_addrlen(COIN_NAME)
    IntaddressLength = get_intaddrlen(COIN_NAME)

    if len(args) == 1:
        CoinAddress = args[0]
        if COIN_NAME == "DOGE":
            valid_address = DOGE_validaddress(str(CoinAddress))
            if 'isvalid' in valid_address:
                if str(valid_address['isvalid']) == "True":
                    await ctx.message.add_reaction(EMOJI_CHECK)
                    await ctx.send(f'Address: `{CoinAddress}`\n'
                                    f'Checked: Valid {COIN_NAME}.')
                    return
                else:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                                    'Checked: Invalid.')
                    return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                                'Checked: Invalid.')
                return
        elif COIN_NAME == "LTC":
            valid_address = LTC_validaddress(str(CoinAddress))
            if 'isvalid' in valid_address:
                if str(valid_address['isvalid']) == "True":
                    await ctx.message.add_reaction(EMOJI_CHECK)
                    await ctx.send(f'Address: `{CoinAddress}`\n'
                                    f'Checked: Valid {COIN_NAME}.')
                    return
                else:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                                    'Checked: Invalid.')
                    return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                                'Checked: Invalid.')
                return

        if len(CoinAddress) == int(addressLength):
            valid_address = addressvalidation.validate_address_cn(CoinAddress, COIN_NAME)
            if valid_address is None:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                                'Checked: Invalid.')
                return
            else:
                await ctx.message.add_reaction(EMOJI_CHECK)
                if (valid_address == CoinAddress):
                    await ctx.send(f'Address: `{CoinAddress}`\n'
                                    'Checked: Valid.')
                return
            return
        elif len(CoinAddress) == int(IntaddressLength):
            # Integrated address
            valid_address = addressvalidation.validate_integrated_cn(CoinAddress, COIN_NAME)
            if valid_address == 'invalid':
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} Integrated Address: `{CoinAddress}`\n'
                                'Checked: Invalid.')
                return
            if len(valid_address) == 2:
                await ctx.message.add_reaction(EMOJI_OK)
                iCoinAddress = CoinAddress
                CoinAddress = valid_address['address']
                paymentid = valid_address['integrated_id']
                await ctx.send(f'\nIntegrated Address: `{iCoinAddress}`\n\n'
                                f'Address: `{CoinAddress}`\n'
                                f'PaymentID: `{paymentid}`')
                return
        else:
            # incorrect length
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                            'Checked: Incorrect length')
            return
    if len(args) == 2:
        CoinAddress = args[0]
        paymentid = args[1]
        # generate integrated address:
        if len(CoinAddress) == int(addressLength):
            valid_address = addressvalidation.validate_address_cn(CoinAddress, COIN_NAME)
            if (valid_address is None):
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                                'Checked: Incorrect given address.')
                return
            else:
                pass
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                            'Checked: Incorrect length')
            return
        # Check payment ID
        if len(paymentid) == 64:
            if not re.match(r'[a-zA-Z0-9]{64,}', paymentid.strip()):
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} PaymentID: `{paymentid}`\n'
                                'Checked: Invalid. Should be in 64 correct format.')
                return
            else:
                pass
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} PaymentID: `{paymentid}`\n'
                            'Checked: Incorrect length')
            return
        # Make integrated address:
        integrated_address = addressvalidation.make_integrated_cn(CoinAddress, COIN_NAME, paymentid)
        if 'integrated_address' in integrated_address:
            iCoinAddress = integrated_address['integrated_address']
            await ctx.message.add_reaction(EMOJI_OK)
            await ctx.send(f'\nNew integrated address: `{iCoinAddress}`\n\n'
                            f'Main address: `{CoinAddress}`\n'
                            f'Payment ID: `{paymentid}`\n')
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} ERROR Can not make integrated address.\n')
            return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send('**[ ADDRESS CHECKING EXAMPLES ]**\n\n'
                       '`.address WrkzRNDQDwFCBynKPc459v3LDa1gEGzG3j962tMUBko1fw9xgdaS9mNiGMgA9s1q7hS1Z8SGRVWzcGc8Sh8xsvfZ6u2wJEtoZB`\n'
                       'That will check if the address is valid. Integrated address is also supported. '
                       'If integrated address is input, bot will tell you the result of :address + paymentid\n\n'
                       '`.address <coin_address> <paymentid>`\n'
                       'This will generate an integrate address.\n\n')
        return


@bot.command(pass_context=True, name='optimize', aliases=['opt'], help=bot_help_optimize)
async def optimize(ctx, coin: str, member: discord.Member = None):
    botLogChan = bot.get_channel(id=LOG_CHAN)
    if coin.upper() not in ENABLE_COIN:
        await ctx.message.add_reaction(EMOJI_WARNING)
        await ctx.send(f'{EMOJI_RED_NO} You need to specify a correct TICKER.')
        return

    COIN_NAME = coin.upper()
    if member is None:
        # Check if in logchan
        if ctx.message.channel.id == LOG_CHAN and (ctx.message.author.id in MAINTENANCE_OWNER):
            wallet_to_opt = 5
            await botLogChan.send(f'OK, I will do some optimization for this `{COIN_NAME}`..')
            opt_numb = store.sql_optimize_admin_do(COIN_NAME, wallet_to_opt)
            if opt_numb:
                await botLogChan.send(f'I optimized only {opt_numb} wallets of `{COIN_NAME}`..')
            else:
                await botLogChan.send('Forgive me! Something wrong...')
            return
        else:
            pass
    else:
        # check permission to optimize
        if int(ctx.message.author.id) in MAINTENANCE_OWNER:
            user_from = store.sql_get_userwallet(member.mention, COIN_NAME)
            # let's optimize and set status
            CountOpt = store.sql_optimize_do(str(member.id), COIN_NAME)
            if CountOpt > 0:
                await ctx.message.add_reaction(EMOJI_OK)
                await ctx.send(f'***Optimize*** is being processed for {member.name} **{COIN_NAME}**. {CountOpt} fusion tx(s).')
                return
            else:
                await ctx.message.add_reaction(EMOJI_OK)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **{COIN_NAME}** No `optimize` is needed or wait for unlock.')
                return
        else:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} **{COIN_NAME}** You only need to optimize your own tip jar.')
            return
    # Get wallet status
    walletStatus = daemonrpc_client.getWalletStatus(COIN_NAME)
    if walletStatus is None:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Wallet service hasn\'t started.')
        return
    else:
        localDaemonBlockCount = int(walletStatus['blockCount'])
        networkBlockCount = int(walletStatus['knownBlockCount'])
        if networkBlockCount - localDaemonBlockCount >= 20:
            # if height is different by 20
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount / networkBlockCount * 100, 2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Wallet service hasn\'t sync fully with network or being re-sync. More info:\n```'
                           f'networkBlockCount:     {t_networkBlockCount}\n'
                           f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                           f'Progress %:            {t_percent}\n```'
                           )
            return
        else:
            pass
    # End of wallet status

    # Check if maintenance
    if IS_MAINTENANCE == 1:
        if int(ctx.message.author.id) in MAINTENANCE_OWNER:
            pass
        else:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {config.maintenance_msg}')
            return
    else:
        pass
    # End Check if maintenance

    # Check if user has a proper wallet with balance bigger than setting balance
    user_from = store.sql_get_userwallet(ctx.message.author.id, COIN_NAME)
    if 'lastOptimize' in user_from:
        if int(time.time()) - int(user_from['lastOptimize']) < int(get_interval_opt(COIN_NAME)):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} **{COIN_NAME}** {ctx.author.mention} Please wait. You just did `optimize` within last 10mn.')
            return
        pass
    if int(user_from['actual_balance']) / get_decimal(COIN_NAME) < int(get_min_opt(COIN_NAME)):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} **{COIN_NAME}** Your balance may not need to optimize yet. Check again later.')
        return
    else:
        # check if optimize has done for last 30mn
        # and if last 30mn more than 5 has been done in total
        countOptimize = store.sql_optimize_check(COIN_NAME)
        if countOptimize >= 5:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(
                f'{EMOJI_RED_NO} {COIN_NAME} {ctx.author.mention} Please wait. There are a few `optimize` within last 10mn from other people.')
            return
        else:
            # let's optimize and set status
            CountOpt = store.sql_optimize_do(ctx.message.author.id, COIN_NAME)
            if CountOpt > 0:
                await ctx.message.add_reaction(EMOJI_OK)
                await ctx.send(f'***Optimize*** {ctx.author.mention} {COIN_NAME} is being processed for your wallet. {CountOpt} fusion tx(s).')
                return
            else:
                await ctx.message.add_reaction(EMOJI_OK)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} No `optimize` is needed or wait for unlock.')
                return


@bot.command(pass_context=True, name='voucher', aliases=['redeem'], help=bot_help_voucher, hidden = True)
async def voucher(ctx, command: str, amount: str, coin: str = None):
    # This is still ongoing work
    botLogChan = bot.get_channel(id=LOG_CHAN)
    amount = amount.replace(",", "")

    # Turn this off when public
    if int(ctx.message.author.id) not in MAINTENANCE_OWNER:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Currently under testing.')
        return

    # Check if maintenance
    if IS_MAINTENANCE == 1:
        if int(ctx.message.author.id) in MAINTENANCE_OWNER:
            pass
        else:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {config.maintenance_msg}')
            return
    else:
        pass
    # End Check if maintenance

    if command.upper() not in ["MAKE", "GEN"]:
        await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid command, please use `.voucher make|gen amount TICKER`')
        return

    try:
        amount = float(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    if coin is None:
        # If private
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send(f'{EMOJI_RED_NO} You need to specify ticker if in DM or private.')
            return
        # If public
        serverinfo = store.sql_info_by_server(str(ctx.guild.id))
        if 'default_coin' in serverinfo:
            if serverinfo['default_coin'].upper() in ENABLE_COIN:
                coin = serverinfo['default_coin'].upper()
            else:
                coin = "WRKZ"
        else:
            coin = "WRKZ"
    if coin.upper() in MAINTENANCE_COIN:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {coin.upper()} in maintenance.')
        return
    print('VOUCHER: '+coin)

    COIN_DEC = get_decimal(coin.upper())
    real_amount = int(amount * COIN_DEC)
    secret_string = str(uuid.uuid4())
    unique_filename = str(uuid.uuid4())

    # do some QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2,
    )
    qrstring = "https://redeem.wrkz.work/" + secret_string
    print(qrstring)
    qr.add_data(qrstring)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_img = qr_img.resize((280, 280))
    qr_img = qr_img.convert("RGBA")
    # qr_img.save(config.qrsettings.path_voucher_create + unique_filename + "_1.png")

    #Logo
    try:
        logo = Image.open(get_coinlogo_path(coin.upper()))
        box = (115,115,165,165)
        qr_img.crop(box)
        region = logo
        region = region.resize((box[2] - box[0], box[3] - box[1]))
        qr_img.paste(region,box)
        # qr_img.save(config.qrsettings.path_voucher_create + unique_filename + "_2.png")
    except Exception as e: 
        print(e)
    # Image Frame on which we want to paste 
    img_frame = Image.open(config.qrsettings.path_voucher_defaultimg)  
    img_frame.paste(qr_img, (150, 150)) 

    # amount font
    try:
        msg = str(num_format_coin(real_amount, coin.upper())) + coin.upper()
        W, H = (1123,644)
        draw =  ImageDraw.Draw(img_frame)
        print(config.font.digital7)
        myFont = ImageFont.truetype(config.font.digital7, 44)
        # w, h = draw.textsize(msg, font=myFont)
        w, h = myFont.getsize(msg)
        # draw.text(((W-w)/2,(H-h)/2), msg, fill="black",font=myFont)
        draw.text((280-w/2,275+125+h), msg, fill="black",font=myFont)

        myFont = ImageFont.truetype(config.font.digital7, 36)
        msg_claim = "SCAN TO CLAIM IT!"
        w, h = myFont.getsize(msg_claim)
        draw.text((280-w/2,275+125+h+60), msg_claim, fill="black",font=myFont)
    except Exception as e: 
        print(e)
    # Saved in the same relative location 
    img_frame.save(config.qrsettings.path_voucher_create + unique_filename + ".png") 

    voucher_make = None
    voucher_make = await store.sql_send_to_voucher(str(ctx.message.author.id), str(ctx.message.author.name), 
                                                   ctx.message.content, real_amount, get_reserved_fee(coin.upper()), 
                                                   secret_string, unique_filename + ".png", coin.upper())
    if voucher_make:
        await ctx.message.add_reaction(EMOJI_OK)
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.message.author.send(f"New Voucher Link (TEST):\n```{qrstring}\n"
                                f"Amount: {num_format_coin(real_amount, coin.upper())} {coin.upper()}\n"
                                f"Reserved Fee: {num_format_coin(get_reserved_fee(coin.upper()), coin.upper())} {coin.upper()}\n"
                                f"Tx Deposit: {voucher_make}```",
                                file=discord.File(config.qrsettings.path_voucher_create + unique_filename + ".png"))
        #os.remove(config.qrsettings.path_voucher_create + unique_filename + ".png")
        else:
            await ctx.message.channel.send(f"New Voucher Link (TEST):\n```{qrstring}\n"
                                f"Amount: {num_format_coin(real_amount, coin.upper())} {coin.upper()}\n"
                                f"Reserved Fee: {num_format_coin(get_reserved_fee(coin.upper()), coin.upper())} {coin.upper()}\n"
                                f"Tx Deposit: {voucher_make}```",
                                file=discord.File(config.qrsettings.path_voucher_create + unique_filename + ".png"))
        #os.remove(config.qrsettings.path_voucher_create + unique_filename + ".png")
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
    return



@bot.command(pass_context=True, name='paymentid', aliases=['payid'], help=bot_help_paymentid)
async def paymentid(ctx):
    paymentid = addressvalidation.paymentid()
    await ctx.message.add_reaction(EMOJI_OK)
    await ctx.send('**[ RANDOM PAYMENT ID ]**\n'
                   f'`{paymentid}`\n')
    return


@bot.command(pass_context=True, aliases=['stat'], help=bot_help_stats)
async def stats(ctx, coin: str = None):
    if coin is None or coin.upper() == 'BOT':
        await bot.wait_until_ready()
        #membercount = '[Members] ' + '{:,.0f}'.format(sum([x.member_count for x in bot.guilds]))
        guildnumber = '[Guilds]        ' + '{:,.0f}'.format(len(bot.guilds))
        shardcount = '[Shards]        ' + '{:,.0f}'.format(bot.shard_count)
        totalonline = '[Total Online]  ' + '{:,.0f}'.format(sum(1 for m in bot.get_all_members() if str(m.status) != 'offline'))
        uniqmembers = '[Unique user]   ' + '{:,.0f}'.format(len(set(bot.get_all_members())))
        uniqonlines = '[Unique Online] ' + '{:,.0f}'.format(sum(1 for m in set(bot.get_all_members()) if str(m.status) != 'offline'))
        botid = '[Bot ID]        ' + str(bot.user.id)
        botstats = '**[ TIPBOT ]**\n'
        botstats = botstats + '```'
        botstats = botstats + botid + '\n' + guildnumber + '\n' + shardcount + '\n' + totalonline + '\n' + uniqmembers + '\n' + uniqonlines
        botstats = botstats + '```'	
        if isinstance(ctx.message.channel, discord.DMChannel):	
            try:
                await ctx.send(f'{botstats}')
                await ctx.send('Please add ticker: '+ ', '.join(ENABLE_COIN).lower() + ' to get stats about coin instead.')
            except Exception as e:
                print(e)
            return
        else:
            if coin and coin.upper() == 'BOT':
                try:
                    await ctx.send(f'{botstats}')
                    await ctx.send('Please add ticker: '+ ', '.join(ENABLE_COIN).lower() + ' to get stats about coin instead.')
                except Exception as e:
                    print(e)
                return
            serverinfo = store.sql_info_by_server(str(ctx.guild.id))
            try:
                COIN_NAME = args[0]
                if COIN_NAME.upper() not in ENABLE_COIN:
                    if COIN_NAME.upper() in ENABLE_COIN_DOGE:
                        COIN_NAME = COIN_NAME.upper()
                    elif 'default_coin' in serverinfo:
                        COIN_NAME = serverinfo['default_coin'].upper()
                else:
                    COIN_NAME = COIN_NAME.upper()
            except:
                if 'default_coin' in serverinfo:
                    COIN_NAME = serverinfo['default_coin'].upper()
            print("COIN_NAME: " + COIN_NAME)
            coin = COIN_NAME
            pass

    if coin.upper() not in ENABLE_COIN:
        if coin == "*":
            await ctx.message.add_reaction(EMOJI_OK)
            await ctx.send('Not available yet. TODO.')
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send('Please put available ticker: '+ ', '.join(ENABLE_COIN).lower())
            return
    else:
        coin = coin.upper()

    if coin.upper() in MAINTENANCE_COIN:
        await ctx.send(f'{EMOJI_RED_NO} {coin.upper()} in maintenance.')
        return

    gettopblock = None
    try:
        gettopblock = await daemonrpc_client.gettopblock(coin)
    except Exception as e:
        print(e)
    walletStatus = None
    try:
        walletStatus = daemonrpc_client.getWalletStatus(coin)
    except Exception as e:
        print(e)
    if gettopblock:
        COIN_NAME = coin.upper()
        COIN_DEC = get_decimal(coin.upper())
        COIN_DIFF = get_diff_target(coin.upper())
        blockfound = datetime.utcfromtimestamp(int(gettopblock['block_header']['timestamp'])).strftime("%Y-%m-%d %H:%M:%S")
        ago = str(timeago.format(blockfound, datetime.utcnow()))
        difficulty = "{:,}".format(gettopblock['block_header']['difficulty'])
        hashrate = str(hhashes(int(gettopblock['block_header']['difficulty']) / int(COIN_DIFF)))
        height = "{:,}".format(gettopblock['block_header']['height'])
        reward = "{:,}".format(int(gettopblock['block_header']['reward'])/int(COIN_DEC))
        if walletStatus is None:
            await ctx.send(f'**[ {COIN_NAME} ]**\n'
                           f'```[NETWORK HEIGHT] {height}\n'
                           f'[TIME]           {ago}\n'
                           f'[DIFFICULTY]     {difficulty}\n'
                           f'[BLOCK REWARD]   {reward}{COIN_NAME}\n'
                           f'[NETWORK HASH]   {hashrate}\n```')
            return
        else:
            localDaemonBlockCount = int(walletStatus['blockCount'])
            networkBlockCount = int(walletStatus['knownBlockCount'])
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount/networkBlockCount*100,2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            walletBalance = get_sum_balances(COIN_NAME)
            COIN_DEC = get_decimal(COIN_NAME)
            balance_str = ''
            if ('unlocked' in walletBalance) and ('locked' in walletBalance):
                balance_actual = num_format_coin(walletBalance['unlocked'], COIN_NAME)
                balance_locked = num_format_coin(walletBalance['locked'], COIN_NAME)
                balance_str = f'[TOTAL UNLOCKED] {balance_actual}{COIN_NAME}\n'
                balance_str = balance_str + f'[TOTAL LOCKED]   {balance_locked}{COIN_NAME}'
            await ctx.send(f'**[ {COIN_NAME} ]**\n'
                           f'```[NETWORK HEIGHT] {height}\n'
                           f'[TIME]           {ago}\n'
                           f'[DIFFICULTY]     {difficulty}\n'
                           f'[BLOCK REWARD]   {reward}{coin.upper()}\n'
                           f'[NETWORK HASH]   {hashrate}\n'
                           f'[WALLET SYNC %]: {t_percent}\n'
                           f'{balance_str}'
                           '```'
                           )
            return
    else:
        await ctx.send('`Unavailable.`')
        return


@bot.command(pass_context=True, help=bot_help_height, hidden = True)
async def height(ctx, coin: str = None):
    COIN_NAME = None
    if coin is None:
        if isinstance(ctx.message.channel, discord.DMChannel):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send('Please add ticker: '+ ', '.join(ENABLE_COIN).lower() + ' with this command if in DM.')
            return
        else:
            serverinfo = store.sql_info_by_server(str(ctx.guild.id))
            try:
                COIN_NAME = args[0]
                if COIN_NAME.upper() not in ENABLE_COIN:
                    if COIN_NAME.upper() in ENABLE_COIN_DOGE:
                        COIN_NAME = COIN_NAME.upper()
                    elif 'default_coin' in serverinfo:
                        COIN_NAME = serverinfo['default_coin'].upper()
                else:
                    COIN_NAME = COIN_NAME.upper()
            except:
                if 'default_coin' in serverinfo:
                    COIN_NAME = serverinfo['default_coin'].upper()
            coin = COIN_NAME
            pass
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME not in ENABLE_COIN:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Please put available ticker: '+ ', '.join(ENABLE_COIN).lower())
        return
    elif COIN_NAME in MAINTENANCE_COIN:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} is under maintenance.')
        return

    gettopblock = None
    try:
        gettopblock = await daemonrpc_client.gettopblock(COIN_NAME)
    except Exception as e:
        print(e)

    if gettopblock:
        height = "{:,}".format(gettopblock['block_header']['height'])
        await ctx.send(f'**[ {COIN_NAME} HEIGHT]**: {height}\n')
        return
    else:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME}\'s status unavailable.')
        return


@bot.command(pass_context=True, name='setting', aliases=['settings', 'set'], help=bot_help_settings)
@commands.has_permissions(manage_channels=True)
async def setting(ctx, *args):
    global LIST_IGNORECHAN
    LIST_IGNORECHAN = store.sql_listignorechan()
    # Check if address is valid first
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send('This command is not available in DM.')
        return
    botLogChan = bot.get_channel(id=LOG_CHAN)
    tickers = '|'.join(ENABLE_COIN).lower()
    serverinfo = store.sql_info_by_server(str(ctx.guild.id))
    if serverinfo is None:
        # Let's add some info if server return None
        add_server_info = store.sql_addinfo_by_server(str(ctx.guild.id),
                                                    ctx.message.guild.name, config.discord.prefixCmd,
                                                    "WRKZ")
        servername = ctx.message.guild.name
        server_id = str(ctx.guild.id)
        server_prefix = config.discord.prefixCmd
        server_coin = DEFAULT_TICKER
    else:
        servername = serverinfo['servername']
        server_id = str(ctx.guild.id)
        server_prefix = serverinfo['prefix']
        server_coin = serverinfo['default_coin'].upper()

    if len(args) == 0:
        await ctx.send('**Available param:** to change prefix, default coin, others in your server:\n```'
                       f'{server_prefix}setting prefix .|?|*|!\n\n'
                       f'{server_prefix}setting default_coin {tickers}\n\n'
                       f'{server_prefix}setting ignorechan (no param, ignore tipping function in said channel)\n\n'
                       f'{server_prefix}setting del_ignorechan (no param, delete ignored tipping function in said channel)\n\n'
                       '```\n\n')
        return
    elif len(args) == 1:
        if args[0].upper() == "IGNORE_CHAN" or args[0].upper() == "IGNORECHAN":
            if LIST_IGNORECHAN is None:
                #print('ok added..')
                store.sql_addignorechan_by_server(str(ctx.guild.id), str(ctx.channel.id), str(ctx.message.author.id), ctx.message.author.name)
                LIST_IGNORECHAN = store.sql_listignorechan()
                await ctx.send(f'Added #{ctx.channel.name} to ignore tip action list.')
                return
            # print(LIST_IGNORECHAN)
            if str(ctx.guild.id) in LIST_IGNORECHAN:
                if str(ctx.channel.id) in LIST_IGNORECHAN[str(ctx.guild.id)]:
                    await ctx.send(f'This channel #{ctx.channel.name} is already in ignore list.')
                    return
                else:
                    #print('ok added..222')
                    store.sql_addignorechan_by_server(str(ctx.guild.id), str(ctx.channel.id), str(ctx.message.author.id), ctx.message.author.name)
                    LIST_IGNORECHAN = store.sql_listignorechan()
                    await ctx.send(f'Added #{ctx.channel.name} to ignore tip action list.')
                    return
            else:
                store.sql_addignorechan_by_server(str(ctx.guild.id), str(ctx.channel.id), str(ctx.message.author.id), ctx.message.author.name)
                await ctx.send(f'Added #{ctx.channel.name} to ignore tip action list.')
                return
        elif args[0].upper() == "DEL_IGNORE_CHAN" or args[0].upper() == "DEL_IGNORECHAN" or args[0].upper() == "DELIGNORECHAN":
            if str(ctx.guild.id) in LIST_IGNORECHAN:
                if str(ctx.channel.id) in LIST_IGNORECHAN[str(ctx.guild.id)]:
                    store.sql_delignorechan_by_server(str(ctx.guild.id), str(ctx.channel.id))
                    LIST_IGNORECHAN = store.sql_listignorechan()
                    await ctx.send(f'This channel #{ctx.channel.name} is deleted from ignore tip list.')
                    return
                else:
                    await ctx.send(f'Channel #{ctx.channel.name} is not in ignore tip action list.')
                    return
            else:
                await ctx.send(f'Channel #{ctx.channel.name} is not in ignore tip action list.')
                return
    elif len(args) == 2:
        if args[0].upper() == "PREFIX":
            if args[1] not in [".", "?", "*", "!"]:
                await ctx.send('Invalid prefix')
                return
            else:
                if server_prefix == args[1]:
                    await ctx.send('That\'s the default prefix. Nothing changed.')
                    return
                else:
                    changeinfo = store.sql_changeinfo_by_server(str(ctx.guild.id), 'prefix', args[1].lower())
                    await ctx.send(f'Prefix changed from `{server_prefix}` to `{args[1].lower()}`.')
                    await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} changed prefix in {ctx.guild.name} / {ctx.guild.id} to `{args[1].lower()}`')
                    return
        elif args[0].upper() == "DEFAULT_COIN" or args[0].upper() == "DEFAULTCOIN" or args[0].upper() == "COIN":
            if args[1].upper() not in ENABLE_COIN:
                await ctx.send('{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
                return
            else:
                if server_coin.upper() == args[1].upper():
                    await ctx.send('That\'s the default coin. Nothing changed.')
                    return
                else:
                    changeinfo = store.sql_changeinfo_by_server(str(ctx.guild.id), 'default_coin', args[1].upper())
                    await ctx.send(f'Default Coin changed from `{server_coin}` to `{args[1].upper()}`.')
                    await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} changed default coin in {ctx.guild.name} / {ctx.guild.id} to {args[1].upper()}.')
                    return
        else:
            await ctx.send('Invalid command input and parameter.')
            return
    else:
        await ctx.send('In valid command input and parameter.')
        return

@bot.command(pass_context=True, name='addressqr', aliases=['qr', 'showqr'], help=bot_help_address_qr, hidden = True)
async def addressqr(ctx, *args):
    # Check if address is valid first
    if len(args) == 0:
        if isinstance(ctx.message.channel, discord.DMChannel):
            COIN_NAME = 'WRKZ'
        else:
            serverinfo = store.sql_info_by_server(str(ctx.guild.id))
            try:
                COIN_NAME = args[0]
                if COIN_NAME.upper() not in ENABLE_COIN:
                    if COIN_NAME.upper() in ENABLE_COIN_DOGE:
                        COIN_NAME = COIN_NAME.upper()
                    elif 'default_coin' in serverinfo:
                        COIN_NAME = serverinfo['default_coin'].upper()
                else:
                    COIN_NAME = COIN_NAME.upper()
            except:
                if 'default_coin' in serverinfo:
                    COIN_NAME = serverinfo['default_coin'].upper()
            print("COIN_NAME: " + COIN_NAME)
        donateAddress = get_donate_address(COIN_NAME.upper()) or 'WrkzRNDQDwFCBynKPc459v3LDa1gEGzG3j962tMUBko1fw9xgdaS9mNiGMgA9s1q7hS1Z8SGRVWzcGc8Sh8xsvfZ6u2wJEtoZB'
        await ctx.send('**[ QR ADDRESS EXAMPLES ]**\n\n'
                       f'```.qr {donateAddress}\n'
                       'This will generate a QR address.'
                       '```\n\n')
        return

    CoinAddress = args[0]
    # Check which coinname is it.
    COIN_NAME = get_cn_coin_from_address(CoinAddress)
    if COIN_NAME:
        addressLength = get_addrlen(COIN_NAME)
        IntaddressLength = get_intaddrlen(COIN_NAME)
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                       f'`{CoinAddress}`')
        return

    if len(args) == 1:
        CoinAddress = args[0]
        if len(CoinAddress) == int(addressLength):
            valid_address = addressvalidation.validate_address_cn(CoinAddress, COIN_NAME)
            if valid_address is None:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                                'Invalid address.')
                return
            else:
                pass
        elif len(CoinAddress) == int(IntaddressLength):
            # Integrated address
            valid_address = addressvalidation.validate_integrated_cn(CoinAddress, COIN_NAME)
            if valid_address == 'invalid':
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} Integrated Address: `{CoinAddress}`\n'
                                'Invalid integrated address.')
                return
            if len(valid_address) == 2:
                pass
        else:
            # incorrect length
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                            'Incorrect address length')
            return
    # let's send
    await ctx.message.add_reaction(EMOJI_OK)
    if os.path.exists(config.qrsettings.path + str(args[0]) + ".png"):
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.message.author.send("QR Code of address: ```" + args[0] + "```", 
                                          file=discord.File(config.qrsettings.path + str(args[0]) + ".png"))
        else:
            await ctx.send("QR Code of address: ```" + args[0] + "```",
                           file=discord.File(config.qrsettings.path + str(args[0]) + ".png"))
        return
    else:
        # do some QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
        )
        qr.add_data(args[0])
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img = img.resize((256, 256))
        img.save(config.qrsettings.path + str(args[0]) + ".png")
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.message.author.send("QR Code of address: ```" + args[0] + "```",
                                          file=discord.File(config.qrsettings.path + str(args[0]) + ".png"))
        else:
            await ctx.send("QR Code of address: ```" + args[0] + "```",
                           file=discord.File(config.qrsettings.path + str(args[0]) + ".png"))
        return


@bot.command(pass_context=True, name='makeqr', aliases=['make-qr', 'paymentqr', 'payqr'], help=bot_help_payment_qr, hidden = True)
async def makeqr(ctx, *args):
    if len(args) < 2:
        await ctx.send('**[ MAKE QR EXAMPLES ]**\n'
                       '```'
                       '.makeqr Address Amount\n'
                       '.makeqr Address Amount -m AddressName\n'
                       '.makeqr Address paymentid Amount\n'
                       '.makeqr Address paymentid Amount -m AddressName\n'
                       'This will generate a QR code from address, paymentid, amount. Optionally with AdddressName'
                       '```\n\n')
        return

    # Check which coinname is it.
    CoinAddress = args[0]
    COIN_NAME = get_cn_coin_from_address(CoinAddress)
    if COIN_NAME:
        addressLength = get_addrlen(COIN_NAME)
        IntaddressLength = get_intaddrlen(COIN_NAME)
        COIN_DEC = get_decimal(COIN_NAME)
        qrstring = get_coin_fullname(COIN_NAME) + '://'
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                       f'`{CoinAddress}`')
        return

    # Check if address is valid first
    msgQR = (' '.join(args))
    try:
        if "-m" in args:
            msgRemark = msgQR[msgQR.index('-m') + len('-m'):].strip()[:64]
            if len(msgRemark) < 1:
                msgRemark = "No Name"
            print('msgRemark: ' + msgRemark)
        else:
            pass
    except:
        pass

    if len(args) == 2 or len(args) == 4:
        CoinAddress = args[0]
        # Check amount
        try:
            amount = float(args[1])
        except ValueError:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} Invalid amount.')
            return
        real_amount = int(amount * COIN_DEC)
        if len(CoinAddress) == int(addressLength):
            valid_address = addressvalidation.validate_address_cn(CoinAddress, COIN_NAME)
            if (valid_address is None):
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                                'Invalid address.')
                return
            else:
                pass
        elif len(CoinAddress) == int(IntaddressLength):
            # Integrated address
            valid_address = addressvalidation.validate_integrated_cn(CoinAddress, COIN_NAME)
            if valid_address == 'invalid':
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} Integrated Address: `{CoinAddress}`\n'
                                'Invalid integrated address.')
                return
            if len(valid_address) == 2:
                pass
        else:
            # incorrect length
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                            'Incorrect address length')
            return
        qrstring += CoinAddress + '?amount=' + str(real_amount)
        if ("-m" in args):
            qrstring = qrstring + '&name=' + msgRemark
        print(qrstring)
        pass
    elif len(args) == 3 or len(args) == 5:
        CoinAddress = args[0]
        # Check amount
        try:
            amount = float(args[2])
        except ValueError:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} Invalid amount.')
            return
        real_amount = int(amount * COIN_DEC)
        # Check payment ID
        paymentid = args[1]
        if len(paymentid) == 64:
            if not re.match(r'[a-zA-Z0-9]{64,}', paymentid.strip()):
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} PaymentID: `{paymentid}`\n'
                                'Should be in 64 correct format.')
                return
            else:
                pass
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} PaymentID: `{paymentid}`\n'
                            'Incorrect length.')
            return

        if len(CoinAddress) == int(addressLength):
            valid_address = addressvalidation.validate_address_cn(CoinAddress, COIN_NAME)
            if valid_address is None:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                                'Invalid address.')
                return
            else:
                pass
        elif len(CoinAddress) == int(IntaddressLength):
            # Integrated address
            valid_address = addressvalidation.validate_integrated_cn(CoinAddress, COIN_NAME)
            if valid_address == 'invalid':
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} Integrated Address: `{CoinAddress}`\n'
                                'Invalid integrated address.')
                return
            if len(valid_address) == 2:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} You cannot use integrated address and paymentid at the same time.')
                return
            return
        else:
            # incorrect length
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                            'Incorrect address length')
            return
        qrstring += CoinAddress + '?amount=' + str(real_amount) + '&paymentid=' + paymentid
        if "-m" in args:
            qrstring = qrstring + '&name=' + msgRemark
        print(qrstring)
        pass
    # let's send
    await ctx.message.add_reaction(EMOJI_OK)
    unique_filename = str(uuid.uuid4())
    # do some QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2,
    )
    qr.add_data(qrstring)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img = img.resize((256, 256))
    img.save(config.qrsettings.path + unique_filename + ".png")
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.message.author.send(f"QR Custom Payment:\n```{qrstring}```",
                                      file=discord.File(config.qrsettings.path + unique_filename + ".png"))
        os.remove(config.qrsettings.path + unique_filename + ".png")
    else:
        await ctx.send(f"QR Custom Payment:\n```{qrstring}```",
                       file=discord.File(config.qrsettings.path + unique_filename + ".png"))
        os.remove(config.qrsettings.path + unique_filename + ".png")
    return


@bot.command(pass_context=True, help=bot_help_tag)
async def tag(ctx, *args):
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send(f'{EMOJI_RED_NO} This command can not be in private.')
        return

    if len(args) == 0:
        ListTag = store.sql_tag_by_server(str(ctx.guild.id))
        if len(ListTag) > 0:
            tags = (', '.join([w['tag_id'] for w in ListTag])).lower()
            await ctx.send(f'Available tag: `{tags}`.\nPlease use `.tag tagname` to show it in detail.'
                           'If you have permission to manage discord server.\n'
                           'Use: `.tag -add|del tagname <Tag description ... >`')
            return
        else:
            await ctx.send('There is no tag in this server. Please add.\n'
                            'If you have permission to manage discord server.\n'
                            'Use: `.tag -add|-del tagname <Tag description ... >`')
            return
    elif len(args) == 1:
        # if .tag test
        TagIt = store.sql_tag_by_server(str(ctx.guild.id), args[0].upper())
        # print(TagIt)
        if (TagIt is not None):
            tagDesc = TagIt['tag_desc']
            await ctx.send(f'{tagDesc}')
            return
        else:
            await ctx.send(f'There is no tag {args[0]} in this server.\n'
                            'If you have permission to manage discord server.\n'
                            'Use: `.tag -add|-del tagname <Tag description ... >`')
            return
    if (args[0].lower() in ['-add', '-del']) and ctx.author.guild_permissions.manage_guild == False:
        await ctx.send('Permission denied.')
        return
    if args[0].lower() == '-add' and ctx.author.guild_permissions.manage_guild:
        # print('Has permission:' + str(ctx.message.content))
        if re.match('^[a-zA-Z0-9]+(-[a-zA-Z0-9]+)*$', args[1]):
            tag = args[1].upper()
            if len(tag) >= 32:
                await ctx.send(f'Tag ***{args[1]}*** is too long.')
                return

            tagDesc = ctx.message.content.strip()[(9 + len(tag) + 1):]
            if len(tagDesc) <= 3:
                await ctx.send(f'Tag desc for ***{args[1]}*** is too short.')
                return
            addTag = store.sql_tag_by_server_add(str(ctx.guild.id), tag.strip(), tagDesc.strip(),
                                                ctx.message.author.name, str(ctx.message.author.id))
            if addTag is None:
                await ctx.send(f'Failed to add tag ***{args[1]}***')
                return
            if addTag.upper() == tag.upper():
                await ctx.send(f'Successfully added tag ***{args[1]}***')
                return
            else:
                await ctx.send(f'Failed to add tag ***{args[1]}***')
                return
        else:
            await ctx.send(f'Tag {args[1]} is not valid.')
            return
        return
    elif args[0].lower() == '-del' and ctx.author.guild_permissions.manage_guild:
        #print('Has permission:' + str(ctx.message.content))
        if re.match('^[a-zA-Z0-9]+(-[a-zA-Z0-9]+)*$', args[1]):
            tag = args[1].upper()
            delTag = store.sql_tag_by_server_del(str(ctx.guild.id), tag.strip())
            if delTag is None:
                await ctx.send(f'Failed to delete tag ***{args[1]}***')
                return
            if delTag.upper() == tag.upper():
                await ctx.send(f'Successfully deleted tag ***{args[1]}***')
                return
            else:
                await ctx.send(f'Failed to delete tag ***{args[1]}***')
                return
        else:
            await ctx.send(f'Tag {args[1]} is not valid.')
            return
        return


@bot.command(pass_context=True, name='invite', aliases=['inviteme'], help=bot_help_invite)
async def invite(ctx):
    await ctx.send('**[INVITE LINK]**\n\n'
                f'{BOT_INVITELINK}')

def hhashes(num) -> str:
    for x in ['H/s', 'KH/s', 'MH/s', 'GH/s']:
        if num < 1000.0:
            return "%3.1f%s" % (num, x)
        num /= 1000.0
    return "%3.1f%s" % (num, 'TH/s')


def get_info_pref_coin(ctx):
    if isinstance(ctx.channel, discord.DMChannel):
        prefixChar = '.'
        return {'server_prefix': prefixChar}
    else:
        serverinfo = store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            add_server_info = store.sql_addinfo_by_server(str(ctx.guild.id),
                                                          ctx.message.guild.name, config.discord.prefixCmd,
                                                          "WRKZ")
            servername = ctx.message.guild.name
            server_id = str(ctx.guild.id)
            server_prefix = config.discord.prefixCmd
            server_coin = DEFAULT_TICKER
        else:
            servername = serverinfo['servername']
            server_id = str(ctx.guild.id)
            server_prefix = serverinfo['prefix']
            server_coin = serverinfo['default_coin'].upper()
        return {'server_prefix': server_prefix, 'server_coin': server_coin, 'server_id': server_id, 'servername': ctx.guild.name}


def get_cn_coin_from_address(CoinAddress: str):
    COIN_NAME = None
    if CoinAddress.startswith("Wrkz"):
        COIN_NAME = "WRKZ"
    elif CoinAddress.startswith("dg"):
        COIN_NAME = "DEGO"
    elif CoinAddress.startswith("Xw"):
        COIN_NAME = "LCX"
    elif CoinAddress.startswith("cat1"):
        COIN_NAME = "CX"
    elif CoinAddress.startswith("hannw"):
        COIN_NAME = "OSL"
    elif CoinAddress.startswith("btcm"):
        COIN_NAME = "BTCM"
    elif CoinAddress.startswith("dicKTiPZ"):
        COIN_NAME = "MTIP"
    elif CoinAddress.startswith("XCY1"):
        COIN_NAME = "XCY"
    elif CoinAddress.startswith("PLe"):
        COIN_NAME = "PLE"
    elif CoinAddress.startswith("Phyrex"):
        COIN_NAME = "ELPH"
    elif CoinAddress.startswith("aNX1"):
        COIN_NAME = "ANX"
    elif CoinAddress.startswith("Nib1"):
        COIN_NAME = "NBX"
    elif CoinAddress.startswith("guns"):
        COIN_NAME = "ARMS"
    elif CoinAddress.startswith("ir"):
        COIN_NAME = "IRD"
    elif CoinAddress.startswith("hi"):
        COIN_NAME = "HITC"
    elif CoinAddress.startswith("NaCa"):
        COIN_NAME = "NACA"
    elif CoinAddress.startswith("TRTL"):
        COIN_NAME = "TRTL"
    return COIN_NAME


async def check_guild_permissions(ctx, perms, *, check=all):
    is_owner = await ctx.bot.is_owner(ctx.author)
    if is_owner:
        return True

    if ctx.guild is None:
        return False

    resolved = ctx.author.guild_permissions
    return check(getattr(resolved, name, None) == value for name, value in perms.items())


@setting.error
async def setting_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Looks like you don\'t have the permission.')


@register.error
async def register_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing your wallet address.\n'
                       'You need to have a supported coin **address** after `register` command')
    return


@info.error
async def info_error(ctx, error):
    pass


@balance.error
async def balance_error(ctx, error):
    pass


@botbalance.error
async def botbalance_error(ctx, error):
    pass


@withdraw.error
async def withdraw_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing amount and/or ticker.\n'
                       'You need to tell me **AMOUNT** and/or **TICKER**.')
    return


@tip.error
async def tip_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing arguments.\n'
                       'You need to tell me **amount** and who you want to tip to.')
    return


@tipall.error
async def tipall_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing argument.\n'
                       'You need to tell me **amount**')
    return


@send.error
async def send_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing arguments.\n'
                       'SEND **amount** **address**')
    return


@voucher.error
async def voucher_error(ctx, error):
    pass


@optimize.error
async def optimize_error(ctx, error):
    pass


@address.error
async def address_error(ctx, error):
    pass


@paymentid.error
async def payment_error(ctx, error):
    pass


@makeqr.error
async def makeqr_error(ctx, error):
    pass


@tag.error
async def tag_error(ctx, error):
    pass


@height.error
async def height_error(ctx, error):
    pass


@bot.event
async def on_command_error(ctx, error):
    print(error)
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send('This command cannot be used in private messages.')
    elif isinstance(error, commands.DisabledCommand):
        await ctx.send('Sorry. This command is disabled and cannot be used.')
    elif isinstance(error, commands.MissingRequiredArgument):
        command = _.message.content.split()[0].strip('.')
        await ctx.send('Missing an argument: try `.help` or `.help ' + command + '`')
    elif isinstance(error, commands.CommandNotFound):
        pass


async def update_balance_wallets():
    while not bot.is_closed:
        # do not update yet
        await asyncio.sleep(15)
        store.sql_update_balances("TRTL")
        await asyncio.sleep(20)
        store.sql_update_balances("WRKZ")
        await asyncio.sleep(20)
        store.sql_update_balances("CX")
        await asyncio.sleep(20)
        store.sql_update_balances("DEGO")
        await asyncio.sleep(20)
        store.sql_update_balances("LCX")
        await asyncio.sleep(20)
        store.sql_update_balances("OSL")
        await asyncio.sleep(20)
        store.sql_update_balances("BTCM")
        await asyncio.sleep(20)
        store.sql_update_balances("MTIP")
        await asyncio.sleep(20)
        store.sql_update_balances("XCY")
        await asyncio.sleep(20)
        store.sql_update_balances("PLE")
        await asyncio.sleep(20)
        store.sql_update_balances("ELPH")
        await asyncio.sleep(20)
        store.sql_update_balances("ANX")
        await asyncio.sleep(20)
        store.sql_update_balances("NBX")
        await asyncio.sleep(20)
        store.sql_update_balances("ARMS")
        await asyncio.sleep(20)
        store.sql_update_balances("IRD")
        await asyncio.sleep(20)
        store.sql_update_balances("HITC")
        await asyncio.sleep(20)
        store.sql_update_balances("NACA")
        await asyncio.sleep(20)
        await asyncio.sleep(config.wallet_balance_update_interval)


# Multiple tip
async def _tip(ctx, amount, coin: str = None):
    serverinfo = store.sql_info_by_server(str(ctx.guild.id))
    COIN_NAME = coin.upper()
    try:
        amount = float(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    notifyList = store.sql_get_tipnotify()

    if COIN_NAME in ENABLE_COIN:
        COIN_DEC = get_decimal(COIN_NAME)
        netFee = get_tx_fee(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        EMOJI_TIP = get_emoji(COIN_NAME)
    elif COIN_NAME.upper() == "DOGE" or COIN_NAME.upper() == "DOGECOIN":
        COIN_NAME = "DOGE"
        EMOJI_TIP = EMOJI_DOGE
        MinTx = config.daemonDOGE.min_mv_amount
        MaxTX = config.daemonDOGE.max_mv_amount
        user_from = {}
        user_from['address'] = DOGE_getaccountaddress(ctx.message.author.id)
        user_from['actual_balance'] = float(DOGE_getbalance_acc(ctx.message.author.id, 6))
        real_amount = float(amount)
        userdata_balance = store.sql_doge_balance(ctx.message.author.id, COIN_NAME)
        if real_amount > user_from['actual_balance'] + userdata_balance['Adjust']:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send tip of '
                            f'{num_format_coin(real_amount, COIN_NAME)} '
                            f'{COIN_NAME}.')
            return
        if real_amount < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                           f'{num_format_coin(MinTx, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return
        if real_amount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                           f'{num_format_coin(MaxTX, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return

        listMembers = ctx.message.mentions
        memids = []  # list of member ID
        for member in listMembers:
            # print(member.name) # you'll just print out Member objects your way.
            if ctx.message.author.id != member.id:
                # user_to = DOGE_getaccountaddress(str(member.id))
                memids.append(str(member.id))
        TotalAmount = real_amount * len(memids)

        if TotalAmount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Total transaction cannot be bigger than '
                           f'{num_format_coin(MaxTX, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return
        if user_from['actual_balance'] + userdata_balance['Adjust'] < TotalAmount:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You don\'t have sufficient balance. ')
            return
        try:
            tips = store.sql_mv_doge_multiple(ctx.message.author.id, memids, real_amount, COIN_NAME, "TIPS")
        except Exception as e:
            print(e)
        if tips:
            servername = serverinfo['servername']
            tipAmount = num_format_coin(TotalAmount, COIN_NAME)
            amountDiv_str = num_format_coin(real_amount, COIN_NAME)
            await ctx.message.add_reaction(EMOJI_TIP)
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Tip of {tipAmount} '
                    f'{COIN_NAME} '
                    f'was sent to ({len(memids)}) members in server `{servername}`.\n'
                    f'Each member got: `{amountDiv_str}{COIN_NAME}`\n')
            except Exception as e:
                print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
                print(e)
            for member in ctx.message.mentions:
                # print(member.name) # you'll just print out Member objects your way.
                if (ctx.message.author.id != member.id):
                    if member.bot == False:
                        if str(member.id) not in notifyList:
                            try:
                                await member.send(
                                    f'{EMOJI_MONEYFACE} You got a tip of `{amountDiv_str}{COIN_NAME}` '
                                    f'from `{ctx.message.author.name}` in server `{servername}`\n'
                                    f'{NOTIFICATION_OFF_CMD}')
                            except Exception as e:
                                print('Adding: ' + str(member.id) + ' not to receive DM tip')
                                store.sql_toggle_tipnotify(str(member.id), "OFF")
                                print(e)
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            return
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
        return
    try:
        real_amount = int(round(float(amount) * COIN_DEC))
    except:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Amount must be a number.')
        return

    user_from = store.sql_get_userwallet(ctx.message.author.id, COIN_NAME)

    if real_amount > MaxTX:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                       f'{num_format_coin(MaxTX, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return
    elif real_amount < MinTx:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                       f'{num_format_coin(MinTx, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return

    destinations = []
    listMembers = ctx.message.mentions

    memids = []  # list of member ID
    for member in listMembers:
        # print(member.name) # you'll just print out Member objects your way.
        if (ctx.message.author.id != member.id):
            user_to = store.sql_register_user(str(member.id), COIN_NAME)
            memids.append(user_to['balance_wallet_address'])

    addresses = []
    for desti in memids:
        destinations.append({"address": desti, "amount": real_amount})
        addresses.append(desti)

    ActualSpend = real_amount * len(memids) + netFee
    if ActualSpend + netFee >= user_from['actual_balance']:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send total tip of '
                       f'{num_format_coin(ActualSpend, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return

    if ActualSpend > MaxTX:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Total transactions cannot be bigger than '
                       f'{num_format_coin(MaxTX, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return
    elif real_amount < MinTx:
        #print('ActualSpend: ' + str(ActualSpend))
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Total transactions cannot be smaller than '
                       f'{num_format_coin(MinTx, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return

    # Get wallet status
    walletStatus = daemonrpc_client.getWalletStatus(COIN_NAME)
    if walletStatus is None:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Wallet service hasn\'t started.')
        return
    else:
        localDaemonBlockCount = int(walletStatus['blockCount'])
        networkBlockCount = int(walletStatus['knownBlockCount'])
        if networkBlockCount - localDaemonBlockCount >= 20:
            # if height is different by 20
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount / networkBlockCount * 100, 2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} Wallet service hasn\'t sync fully with network or being '
                           're-sync. More info:\n```'
                           f'networkBlockCount:     {t_networkBlockCount}\n'
                           f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                           f'Progress %:            {t_percent}\n```'
                           )
            return
        else:
            pass
    # End of wallet status

    tip = None
    try:
        tip = await store.sql_send_tipall(ctx.message.author.id, destinations, real_amount, COIN_NAME)
    except Exception as e:
        print(e)
    if tip:
        servername = serverinfo['servername']
        store.sql_update_some_balances(addresses, COIN_NAME)
        await ctx.message.add_reaction(EMOJI_TIP)
        # tipper shall always get DM. Ignore notifyList
        try:
            await ctx.message.author.send(f'{EMOJI_ARROW_RIGHTHOOK} Total tip of {num_format_coin(ActualSpend, COIN_NAME)} '
                                    f'{COIN_NAME} '
                                    f'was sent to ({len(destinations)}) members in server `{servername}`.\n'
                                    f'Transaction hash: `{tip}`\n'
                                    f'Each: `{num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`'
                                    f'Total spending: `{num_format_coin(ActualSpend, COIN_NAME)} {COIN_NAME}`')
        except Exception as e:
            print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
            store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            print(e)
        for member in ctx.message.mentions:
            if ctx.message.author.id != member.id:
                if member.bot == False:
                    if str(member.id) not in notifyList:
                        try:
                            await member.send(f'{EMOJI_MONEYFACE} You got a tip of  {num_format_coin(real_amount, COIN_NAME)} '
                                            f'{COIN_NAME} from `{ctx.message.author.name}` in server `{servername}`\n'
                                            f'Transaction hash: `{tip}`\n'
                                            f'{NOTIFICATION_OFF_CMD}')
                        except Exception as e:
                            print('Adding: ' + str(member.id) + ' not to receive DM tip')
                            store.sql_toggle_tipnotify(str(member.id), "OFF")
                            print(e)
                        pass
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You may need to `optimize` or try again.')
        return


# Multiple tip
async def _tip_talker(ctx, amount, list_talker, coin: str = None):
    serverinfo = store.sql_info_by_server(str(ctx.guild.id))
    COIN_NAME = coin.upper()
    try:
        amount = float(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    notifyList = store.sql_get_tipnotify()

    if COIN_NAME in ENABLE_COIN:
        COIN_DEC = get_decimal(COIN_NAME)
        netFee = get_tx_fee(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        EMOJI_TIP = get_emoji(COIN_NAME)
    elif COIN_NAME.upper() == "DOGE" or COIN_NAME.upper() == "DOGECOIN":
        COIN_NAME = "DOGE"
        EMOJI_TIP = EMOJI_DOGE
        MinTx = config.daemonDOGE.min_mv_amount
        MaxTX = config.daemonDOGE.max_mv_amount
        user_from = {}
        user_from['address'] = DOGE_getaccountaddress(ctx.message.author.id)
        user_from['actual_balance'] = float(DOGE_getbalance_acc(ctx.message.author.id, 6))
        real_amount = float(amount)
        userdata_balance = store.sql_doge_balance(ctx.message.author.id, COIN_NAME)
        if real_amount > user_from['actual_balance'] + userdata_balance['Adjust']:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send tip of '
                            f'{num_format_coin(real_amount, COIN_NAME)} '
                            f'{COIN_NAME}.')
            return
        if real_amount < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                           f'{num_format_coin(MinTx, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return
        if real_amount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                           f'{num_format_coin(MaxTX, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return

        memids = []  # list of member ID
        for member_id in list_talker:
            if member_id != ctx.message.author.id:
                # user_to = DOGE_getaccountaddress(str(member_id))
                memids.append(str(member_id))
        TotalAmount = real_amount * len(memids)

        if TotalAmount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Total transaction cannot be bigger than '
                           f'{num_format_coin(MaxTX, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return
        if user_from['actual_balance'] + userdata_balance['Adjust'] < TotalAmount:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You don\'t have sufficient balance. ')
            return
        try:
            tips = store.sql_mv_doge_multiple(ctx.message.author.id, memids, real_amount, COIN_NAME, "TIPS")
        except Exception as e:
            print(e)
        if tips:
            servername = serverinfo['servername']
            await ctx.message.add_reaction(EMOJI_TIP)
            await ctx.message.add_reaction(EMOJI_SPEAK)
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Tip of {num_format_coin(TotalAmount, COIN_NAME)} '
                    f'{COIN_NAME} '
                    f'was sent to ({len(memids)}) members in server `{servername}` for active talking.\n'
                    f'Each member got: `{num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}`\n')
            except Exception as e:
                print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
                print(e)
            mention_list_name = ''
            for member_id in list_talker:
                # print(member.name) # you'll just print out Member objects your way.
                if ctx.message.author.id != int(member_id):
                    member = bot.get_user(id=int(member_id))
                    if member.bot == False:
                        mention_list_name = mention_list_name + '`'+member.name + '` '
                        if str(member_id) not in notifyList:
                            try:
                                await member.send(
                                    f'{EMOJI_MONEYFACE} You got a tip of `{num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}` '
                                    f'from `{ctx.message.author.name}` in server `{servername}` for active talking.\n'
                                    f'{NOTIFICATION_OFF_CMD}')
                            except Exception as e:
                                print('Adding: ' + str(member.id) + ' not to receive DM tip')
                                store.sql_toggle_tipnotify(str(member.id), "OFF")
                                print(e)
            await ctx.send(f'{mention_list_name}\n\nYou got tip :) for active talking in `{ctx.guild.name}` {ctx.channel.mention} :)')
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            return
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
        return
    try:
        real_amount = int(round(float(amount) * COIN_DEC))
    except:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Amount must be a number.')
        return

    user_from = store.sql_get_userwallet(ctx.message.author.id, COIN_NAME)

    if real_amount > MaxTX:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                       f'{num_format_coin(MaxTX, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return
    elif real_amount < MinTx:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                       f'{num_format_coin(MinTx, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return

    destinations = []
    memids = []  # list of member ID
    for member_id in list_talker:
        if member_id != ctx.message.author.id:
            user_to = store.sql_register_user(str(member_id), COIN_NAME)
            memids.append(user_to['balance_wallet_address'])

    addresses = []
    for desti in memids:
        destinations.append({"address": desti, "amount": real_amount})
        addresses.append(desti)

    ActualSpend = real_amount * len(memids) + netFee

    if ActualSpend + netFee >= user_from['actual_balance']:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send total tip of '
                       f'{num_format_coin(ActualSpend, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return

    if ActualSpend > MaxTX:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Total transactions cannot be bigger than '
                       f'{num_format_coin(MaxTX, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return
    elif real_amount < MinTx:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Total transactions cannot be smaller than '
                       f'{num_format_coin(MinTx, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return

    # Get wallet status
    walletStatus = daemonrpc_client.getWalletStatus(COIN_NAME)
    if walletStatus is None:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Wallet service hasn\'t started.')
        return
    else:
        localDaemonBlockCount = int(walletStatus['blockCount'])
        networkBlockCount = int(walletStatus['knownBlockCount'])
        if networkBlockCount - localDaemonBlockCount >= 20:
            # if height is different by 20
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount / networkBlockCount * 100, 2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} Wallet service hasn\'t sync fully with network or being '
                           're-sync. More info:\n```'
                           f'networkBlockCount:     {t_networkBlockCount}\n'
                           f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                           f'Progress %:            {t_percent}\n```'
                           )
            return
        else:
            pass
    # End of wallet status

    tip = None
    try:
        tip = await store.sql_send_tipall(ctx.message.author.id, destinations, real_amount, COIN_NAME)
    except Exception as e:
        print(e)
    if tip:
        servername = serverinfo['servername']
        store.sql_update_some_balances(addresses, COIN_NAME)
        await ctx.message.add_reaction(EMOJI_TIP)
        await ctx.message.add_reaction(EMOJI_SPEAK)
        # tipper shall always get DM. Ignore notifyList
        try:
            await ctx.message.author.send(f'{EMOJI_ARROW_RIGHTHOOK} Total tip of {num_format_coin(ActualSpend, COIN_NAME)} '
                                    f'{COIN_NAME} '
                                    f'was sent to ({len(destinations)}) members in server `{servername}` for active talking.\n'
                                    f'Transaction hash: `{tip}`\n'
                                    f'Each: `{num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}`'
                                    f'Total spending: `{num_format_coin(ActualSpend, COIN_NAME)}{COIN_NAME}`')
        except Exception as e:
            print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
            store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            print(e)
        mention_list_name = ''
        for member_id in list_talker:
            if ctx.message.author.id != int(member_id):
                member = bot.get_user(id=int(member_id))
                if member.bot == False:
                    mention_list_name = mention_list_name + '`'+member.name + '` '
                    if str(member_id) not in notifyList:
                        try:
                            await member.send(f'{EMOJI_MONEYFACE} You got a tip of {tipAmount} '
                                            f'{COIN_NAME} from `{ctx.message.author.name}` in server `{servername}` for active talking.\n'
                                            f'Transaction hash: `{tip}`\n'
                                            f'{NOTIFICATION_OFF_CMD}')
                        except Exception as e:
                            print('Adding: ' + str(member.id) + ' not to receive DM tip')
                            store.sql_toggle_tipnotify(str(member.id), "OFF")
                            print(e)
                        pass
        await ctx.send(f'{mention_list_name}\n\nYou got tip :) for active talking in `{ctx.guild.name}` {ctx.channel.mention} :)')
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You may need to `optimize` or try again later.')
        return


def truncate(number, digits) -> float:
    stepper = pow(10.0, digits)
    return math.trunc(stepper * number) / stepper


@click.command()
def main():
    #bot.loop.create_task(update_balance_wallets())
    bot.run(config.discord.token, reconnect=True)


if __name__ == '__main__':
    main()
