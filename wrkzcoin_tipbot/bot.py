import click
from discord_webhook import DiscordWebhook

import discord
from discord.ext import commands
from discord.ext.commands import Bot, AutoShardedBot, when_mentioned_or, CheckFailure

from discord.utils import get

import time, timeago, json
import pyotp

import store, daemonrpc_client, addressvalidation, walletapi, coin360, chart_pair_snapshot

from generic_xmr.address_msr import address_msr as address_msr
from generic_xmr.address_xmr import address_xmr as address_xmr
from generic_xmr.address_upx import address_upx as address_upx
from generic_xmr.address_wow import address_wow as address_wow
from generic_xmr.address_xol import address_xol as address_xol

# games.bagels
from games.bagels import getSecretNum as bagels_getSecretNum
from games.bagels import getClues as bagels_getClues
from games.hangman import drawHangman as hm_drawHangman
from games.hangman import load_words as hm_load_words

from games.maze2d import displayMaze as maze_displayMaze
from games.maze2d import createMazeDump as maze_createMazeDump

from games.blackjack import getDeck as blackjack_getDeck
from games.blackjack import displayHands as blackjack_displayHands
from games.blackjack import getCardValue as blackjack_getCardValue

from games.twentyfortyeight import getNewBoard as g2048_getNewBoard
from games.twentyfortyeight import drawBoard as g2048_drawBoard
from games.twentyfortyeight import getScore as g2048_getScore
from games.twentyfortyeight import addTwoToBoard as g2048_addTwoToBoard
from games.twentyfortyeight import isFull as g2048_isFull
from games.twentyfortyeight import makeMove as g2048_makeMove

# eth erc
from eth_account import Account

# linedraw
from linedraw.linedraw import *
from cairosvg import svg2png
import functools

from decimal import Decimal

# tb
from tb.tbfun import action as tb_action
# byte-oriented StringIO was moved to io.BytesIO in py3k
try:
    from io import BytesIO
except ImportError:
    from StringIO import StringIO as BytesIO

# For eval
import contextlib
import io

# For hash file in case already have
import hashlib

import cv2
import numpy as np

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

import sys, traceback
import asyncio
import aiohttp

# numexpr
import numexpr

import binascii

# add logging
# CRITICAL, ERROR, WARNING, INFO, and DEBUG and if not specified defaults to WARNING.
import logging

# redis
import redis
redis_pool = None
redis_conn = None
redis_expired = 120

logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

sys.path.append("..")

MAINTENANCE_OWNER = [386761001808166912]  # list owner
OWNER_ID_TIPBOT = 386761001808166912
TESTER = [ 288403695878537218 ]
# bingo and duckhunt
BOT_IGNORECHAN = [558173489194991626, 524572420468899860]  # list ignore chan
LOG_CHAN = 572686071771430922
NOTIFY_TRADE_CHAN = config.discord.channelNotify

WALLET_SERVICE = None
LIST_IGNORECHAN = None
MUTE_CHANNEL = None

# param introduce by @bobbieltd
TX_IN_PROCESS = []

# tip-react temp storage
REACT_TIP_STORE = []

# faucet enabled coin. The faucet balance is taken from TipBot's own balance
FAUCET_COINS = config.Enable_Faucet_Coin.split(",")

# Coin using wallet-api
WALLET_API_COIN = config.Enable_Coin_WalletApi.split(",")

# Coin allowed to trade
ENABLE_TRADE_COIN = config.trade.enable_coin.split(",")
MIN_TRADE_RATIO = float(config.trade.Min_Ratio)
TRADE_PERCENT = config.trade.Trade_Margin

# Fee per byte coin
FEE_PER_BYTE_COIN = config.Fee_Per_Byte_Coin.split(",")

# Bot invitation link
BOT_INVITELINK = "[Invite TipBot](http://invite.discord.bot.tips)"
    
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


GAME_COIN = config.game.coin_game.split(",")
# This will multiplied in result
GAME_SLOT_REWARD = {
    "WRKZ": config.game_reward.wrkz,
    "DEGO": config.game_reward.dego,
    "TRTL": config.game_reward.trtl,
    "BTCMZ": config.game_reward.btcmz,
    "NBXC": config.game_reward.nbxc,
    "XFG": config.game_reward.xfg,
    "DOGE": config.game_reward.doge,
    "PGO": config.game_reward.pgo,
    "WOW": config.game_reward.wow,
    "BAN": config.game_reward.ban,
    "NANO": config.game_reward.nano
}

GAME_INTERACTIVE_PRGORESS = []
GAME_SLOT_IN_PRGORESS = []
GAME_DICE_IN_PRGORESS = []
GAME_MAZE_IN_PROCESS = []
CHART_TRADEVIEW_IN_PROCESS = []
# miningpoolstat_progress
MINGPOOLSTAT_IN_PROCESS = []

# save all temporary
SAVING_ALL = None

# disclaimer message
DISCLAIM_MSG = """Disclaimer: No warranty or guarantee is provided, expressed, or implied \
when using this bot and any funds lost, mis-used or stolen in using this bot \
are not the responsibility of the bot creator or hoster."""

DISCLAIM_MSG_LONG = """```
Disclaimer: TipBot, its owners, service providers or any other parties providing services, \
are not in any way responsible or liable for any lost, mis-used, stolen funds, or any coin \
network's issues. TipBot's purpose is to be fun, do testing, and share tips between \
user to user, and its use is on each user’s own risks.

We operate the bot on our own rented servers. We do not charge any node fees for transactions, \
as well as no fees for depositing or withdrawing funds to the TipBot. \
Feel free to donate if you like the TipBot and the service it provides. \
Your donations will help to fund the development & maintenance. 

We commit to make it as secure as possible to the best of our expertise, \
however we accept no liability and responsibility for any loss or damage \
caused to you. Additionally, the purpose of the TipBot is to spread awareness \
of cryptocurrency through tips, which is one of our project’s main commitments.
```
"""

IS_MAINTENANCE = config.maintenance
IS_RESTARTING = False
IS_DEBUG = False

# Get them from https://emojipedia.org
EMOJI_MONEYFACE = "\U0001F911"
EMOJI_ERROR = "\u274C"
EMOJI_OK_BOX = "\U0001F197"
EMOJI_OK_HAND = "\U0001F44C"
EMOJI_WARNING = "\u26A1"
EMOJI_ALARMCLOCK = "\u23F0"
EMOJI_HOURGLASS_NOT_DONE = "\u23F3"
EMOJI_CHECK = "\u2705"
EMOJI_MONEYBAG = "\U0001F4B0"
EMOJI_SCALE = "\u2696"
EMOJI_INFORMATION = "\u2139"
EMOJI_100 = "\U0001F4AF"
EMOJI_99 = "<:almost100:405478443028054036>"
EMOJI_TIP = "<:tip:424333592102043649>"
EMOJI_MAINTENANCE = "\U0001F527"
EMOJI_QUESTEXCLAIM = "\u2049"
EMOJI_CHECKMARK = "\u2714"
EMOJI_PARTY = "\U0001F389"

TOKEN_EMOJI = "\U0001F3CC"

EMOJI_UP = "\u2B06"
EMOJI_LEFT = "\u2B05"
EMOJI_RIGHT = "\u27A1"
EMOJI_DOWN = "\u2B07"
EMOJI_FIRE = "\U0001F525"
EMOJI_BOMB = "\U0001F4A3"
EMPTY_DISPLAY = '⬛' # ⬛ :black_large_square:

EMOJI_UP_RIGHT = "\u2197"
EMOJI_DOWN_RIGHT = "\u2198"
EMOJI_CHART_DOWN = "\U0001F4C9"
EMOJI_CHART_UP = "\U0001F4C8"

EMOJI_LETTER_S = "\U0001F1F8"
EMOJI_LETTER_H = "\U0001F1ED"

EMOJI_FLOPPY = "\U0001F4BE"

EMOJI_RED_NO = "\u26D4"
EMOJI_SPEAK = "\U0001F4AC"
EMOJI_ARROW_RIGHTHOOK = "\u21AA"
EMOJI_FORWARD = "\u23E9"
EMOJI_REFRESH = "\U0001F504"
EMOJI_ZIPPED_MOUTH = "\U0001F910"
EMOJI_LOCKED = "\U0001F512"

EMOJI_HELP_HOUSE = "\U0001F3E0" # :house:
EMOJI_HELP_GUILD = "\U0001F9D9" # :mage_man:
EMOJI_HELP_TIP = "\U0001F4B8" # :money_with_wings:
EMOJI_HELP_GAME = "\U0001F3B2" # :game_die:
EMOJI_HELP_TOOL = "\U0001F6E0" # :hammer_and_wrench:
EMOJI_HELP_NOTE = "\U0001F4DD" # :memo:
EMOJI_HELP_CG = "\U0001F4C8" # :chart_with_upwards_trend: :chart_increasing:

ENABLE_COIN = config.Enable_Coin.split(",")
ENABLE_COIN_DOGE = config.Enable_Coin_Doge.split(",")
ENABLE_XMR = config.Enable_Coin_XMR.split(",")
ENABLE_COIN_NANO = config.Enable_Coin_Nano.split(",")
ENABLE_COIN_ERC = config.Enable_Coin_ERC.split(",")
MAINTENANCE_COIN = config.Maintenance_Coin.split(",")

COIN_REPR = "COIN"
DEFAULT_TICKER = "WRKZ"
ENABLE_COIN_VOUCHER = config.Enable_Coin_Voucher.split(",")
HIGH_DECIMAL_COIN = config.ManyDecimalCoin.split(",")

NOTICE_COIN = {}
for each in ENABLE_COIN+ENABLE_XMR+ENABLE_COIN_DOGE+ENABLE_COIN_NANO:
    try:
        NOTICE_COIN[each.upper()] = getattr(getattr(config,"daemon"+each.upper()),"coin_notice", None)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
NOTICE_COIN['default'] = "Thank you for using."


EMOJI_COIN = {}
for each in ENABLE_COIN+ENABLE_XMR+ENABLE_COIN_DOGE+ENABLE_COIN_NANO:
    try:
        EMOJI_COIN[each.upper()] = getattr(getattr(config,"daemon"+each.upper()),"emoji", '\U0001F4B0')
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
for each in ENABLE_COIN_ERC:
    try:
        EMOJI_COIN[each.upper()] = TOKEN_EMOJI
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

# atomic Amount
ROUND_AMOUNT_COIN = {
    "DEGO" : 4 # 10^4
    }


# TRTL discord. Need for some specific tasks later.
TRTL_DISCORD = 388915017187328002

NOTIFICATION_OFF_CMD = 'Type: `.notifytip off` to turn off this DM notification.'
MSG_LOCKED_ACCOUNT = "Your account is locked. Please contact Pluton#4425 in WrkzCoin discord. Check `.about` for more info."

bot_description = f"Tip {COIN_REPR} to other users on your server."
bot_help_about = "About TipBot"
bot_help_register = "Register or change your deposit address."
bot_help_info = "Get discord server's info for TipBot."
bot_help_deposit = "Get your wallet's deposit address."
bot_help_userinfo = "Get user info in discord server."
bot_help_withdraw = f"Withdraw {COIN_REPR} from your balance."
bot_help_balance = f"Check your {COIN_REPR} balance."
bot_help_botbalance = f"Check (only) bot {COIN_REPR} balance."
bot_help_donate = f"Donate {COIN_REPR} to a Bot Owner."
bot_help_tip = f"Give {COIN_REPR} to a user from your balance."
bot_help_freetip = f"Give {COIN_REPR} to a re-acted user from your balance."
bot_help_randomtip = "Tip to random user in the guild"

bot_help_forwardtip = f"Forward all your received tip of {COIN_REPR} to registered wallet."
bot_help_tipall = f"Spread a tip amount of {COIN_REPR} to all online members."
bot_help_send = f"Send {COIN_REPR} to a {COIN_REPR} address from your balance (supported integrated address)."
bot_help_address = f"Check {COIN_REPR} address | Generate {COIN_REPR} integrated address."
bot_help_paymentid = "Make a random payment ID with 64 chars length."
bot_help_tag = "Display a description or a link about what it is. (-add|-del) requires permission manage_channels"
bot_help_itag = "Upload image (gif|png|jpeg|mp4) and add tag."
bot_help_stats = f"Show summary {COIN_REPR}: height, difficulty, etc."
bot_help_height = f"Show {COIN_REPR}'s current height"
bot_help_notifytip = "Toggle notify tip notification from bot ON|OFF"
bot_help_settings = "settings view and set for prefix, default coin. Requires permission manage_channels"
bot_help_invite = "Invite link of bot to your server."
bot_help_random_number = "Get random number. Example .rand 1-100"
bot_help_disclaimer = "Show disclaimer."
bot_help_voucher = "Make a voucher image and your friend can claim via QR code."
bot_help_take = "Get random faucet tip."
bot_help_cal = "Use built-in calculator."
bot_help_coininfo = "List of coin status."
bot_help_feedback = "Share your feedback or inquiry about TipBot to dev team"
bot_help_view_feedback = "View feedback submit by you"
bot_help_view_feedback_list = "List of your recent feedback."

bot_help_voucher_make = "Make a voucher and you share to other friends."
bot_help_voucher_view = "View recent made voucher in a list"
bot_help_voucher_unclaim = "View list of unclaimed vouchers"
bot_help_voucher_claim = "View list of claimed vouchers"
bot_help_voucher_getunclaim = "Get a list of unclaimed vouchers as a file."
bot_help_voucher_getclaim = "Get a list of claimed vouchers as a file."
bot_help_voucher_fee = "List of fee for making voucher and including network fee."

# admin commands
bot_help_admin = "Various admin commands."
bot_help_admin_save = "Save wallet file..."
bot_help_admin_shutdown = "Restart bot."
bot_help_admin_baluser = "Check a specific user's balance for verification purpose."
bot_help_admin_lockuser = "Lock a user from any tx (tip, withdraw, info, etc) by user id"
bot_help_admin_unlockuser = "Unlock a user by user id."
bot_help_admin_cleartx = "Clear pending TX in case of urgent need."

# game command
bot_help_game = "Various game commands"
bot_help_game_slot = "Play slot game"
bot_help_game_bagel = "Bagels, a deductive logic game"
bot_help_game_hangman = "Old hangman game"
bot_help_game_maze = "Interactive 2D ascii maze game"
bot_help_game_blackjack = "Blackjack, original code by Al Sweigart al@inventwithpython.com"
bot_help_game_dice = "Simple dice game"
bot_help_game_snailrace = "Snail racing game. You bet which one."
bot_help_game_stat = "Check overall game stat"
bot_help_game_2048 = "Classic 2048 game. Slide all the tiles on the board in one of four directions."
bot_help_game_sokoban = "Sokoban interactive game."

# account commands
bot_help_account = "Various user account commands."
bot_help_account_depositlink = "Get a web deposit link for all your deposit addresses."

bot_help_account_twofa = "Generate a 2FA and scanned with Authenticator Program."
bot_help_account_verify = "Verify 2FA code from QR code and your Authenticator Program."
bot_help_account_unverify = "Unverify your account and disable 2FA code."
bot_help_account_tipemoji = "Put additional Emoji to your successful tip."


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


def get_round_amount(coin: str, amount: int):
    COIN_NAME = coin.upper()
    if COIN_NAME in ROUND_AMOUNT_COIN:
        if amount > 10**ROUND_AMOUNT_COIN[COIN_NAME]:
            n = 10**ROUND_AMOUNT_COIN[COIN_NAME]
            return amount // n * n
        else:
            # less than define, cut only decimal
            return amount // get_decimal(COIN_NAME) * get_decimal(COIN_NAME)
    else:
        return amount


def get_emoji(coin: str):
    COIN_NAME = coin.upper()
    if COIN_NAME in EMOJI_COIN:
        return EMOJI_COIN[COIN_NAME]
    else:
        return EMOJI_ERROR


def get_notice_txt(coin: str):
    COIN_NAME = coin.upper()
    if COIN_NAME in NOTICE_COIN:
        if NOTICE_COIN[COIN_NAME] is None:
            return ""
        else:
            return "`" + NOTICE_COIN[COIN_NAME] + "`"
    else:
        return "Any support for this TipBot, please join https://chat.wrkz.work"


# Steal from https://github.com/cree-py/RemixBot/blob/master/bot.py#L49
async def get_prefix(bot, message):
    """Gets the prefix for the guild"""
    pre_cmd = config.discord.prefixCmd
    if isinstance(message.channel, discord.DMChannel):
        pre_cmd = config.discord.prefixCmd
        extras = [pre_cmd, 'tb!', 'tipbot!', '?', '.', '+', '!', '-']
        return when_mentioned_or(*extras)(bot, message)

    serverinfo = await store.sql_info_by_server(str(message.guild.id))
    if serverinfo is None:
        # Let's add some info if guild return None
        add_server_info = await store.sql_addinfo_by_server(str(message.guild.id), message.guild.name,
                                                            config.discord.prefixCmd, "WRKZ")
        pre_cmd = config.discord.prefixCmd
        serverinfo = await store.sql_info_by_server(str(message.guild.id))
    if serverinfo and ('prefix' in serverinfo):
        pre_cmd = serverinfo['prefix']
    else:
        pre_cmd =  config.discord.prefixCmd
    extras = [pre_cmd, 'tb!', 'tipbot!']
    return when_mentioned_or(*extras)(bot, message)


# Create ETH
def create_eth_wallet():
    Account.enable_unaudited_hdwallet_features()
    acct, mnemonic = Account.create_with_mnemonic()
    return {'address': acct.address, 'seed': mnemonic, 'private_key': acct.privateKey.hex()}

async def create_address_eth():
    wallet_eth = functools.partial(create_eth_wallet)
    create_wallet = await bot.loop.run_in_executor(None, wallet_eth)
    return create_wallet


intents = discord.Intents.default()
intents.members = True
intents.presences = True

bot = AutoShardedBot(command_prefix = get_prefix, case_insensitive=True, owner_id = OWNER_ID_TIPBOT, pm_help = True, intents=intents)
bot.remove_command('help')


async def logchanbot(content: str):
    filterword = config.discord.logfilterword.split(",")
    for each in filterword:
        content = content.replace(each, config.discord.filteredwith)
    try:
        webhook = DiscordWebhook(url=config.discord.botdbghook, content=f'```{discord.utils.escape_markdown(content)}```')
        webhook.execute()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


@bot.event
async def on_ready():
    global LIST_IGNORECHAN, MUTE_CHANNEL, IS_RESTARTING, BOT_INVITELINK, HANGMAN_WORDS
    HANGMAN_WORDS = hm_load_words()
    print('Ready!')
    print("Hello, I am TipBot Bot!")
    LIST_IGNORECHAN = await store.sql_listignorechan()
    MUTE_CHANNEL = await store.sql_list_mutechan()
    print("Loaded ignore and mute channel list.")
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    print("Guilds: {}".format(len(bot.guilds)))
    print("Users: {}".format(sum([x.member_count for x in bot.guilds])))
    print("Bot invitation link: " + BOT_INVITELINK)
    if HANGMAN_WORDS and len(HANGMAN_WORDS) > 0: print('Loaded {} words for hangman.'.format(len(HANGMAN_WORDS)))
    game = discord.Game(name="making crypto fun!")
    await bot.change_presence(status=discord.Status.online, activity=game)
    botLogChan = bot.get_channel(id=LOG_CHAN)
    await botLogChan.send(f'{EMOJI_REFRESH} I am back :)')
    IS_RESTARTING = False


@bot.event
async def on_shard_ready(shard_id):
    print(f'Shard {shard_id} connected')


@bot.event
async def on_guild_join(guild):
    botLogChan = bot.get_channel(id=LOG_CHAN)
    add_server_info = await store.sql_addinfo_by_server(str(guild.id), guild.name,
                                                        config.discord.prefixCmd, "WRKZ", True)
    await botLogChan.send(f'Bot joins a new guild {guild.name} / {guild.id} / Users: {len(guild.members)}. Total guilds: {len(bot.guilds)}.')
    return


@bot.event
async def on_guild_remove(guild):
    botLogChan = bot.get_channel(id=LOG_CHAN)
    add_server_info = await store.sql_updateinfo_by_server(str(guild.id), "status", "REMOVED")
    await botLogChan.send(f'Bot was removed from guild {guild.name} / {guild.id}. Total guilds: {len(bot.guilds)}')
    return


@bot.event
async def on_raw_reaction_add(payload):
    global EMOJI_OK_BOX
    if payload.guild_id is None:
        return  # Reaction is on a private message
    """Handle a reaction add."""
    try:
        emoji_partial = str(payload.emoji)
        message_id = payload.message_id
        channel_id = payload.channel_id
        user_id = payload.user_id
        guild = bot.get_guild(payload.guild_id)
        channel = bot.get_channel(id=channel_id)
        if not channel:
            return
        if isinstance(channel, discord.DMChannel):
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        return
    message = None
    author = None
    if message_id:
        try:
            message = await channel.fetch_message(message_id)
            author = message.author
        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            # No message found
            return
        member = bot.get_user(id=user_id)
        if emoji_partial in [EMOJI_OK_BOX] and message.author.id == bot.user.id \
            and author != member and message:
            # Delete message
            try:
                # do not delete maze or blackjack message
                if 'MAZE' in message.content.upper() or 'BLACKJACK' in message.content.upper() or 'YOUR SCORE' in message.content.upper() \
                or 'SOKOBAN ' in message.content.upper() or 'GAME 2048' in message.content.upper():
                    return
                try:
                    await message.delete()
                except Exception as e:
                    pass
                return
            except discord.errors.NotFound as e:
                # No message found
                return


@bot.event
async def on_reaction_add(reaction, user):
    global REACT_TIP_STORE, TRTL_DISCORD, EMOJI_99, EMOJI_TIP, TX_IN_PROCESS
    # If bot re-act, ignore.
    if user.id == bot.user.id:
        return
    # If other people beside bot react.
    else:
        # If re-action is OK box and message author is bot itself
        if reaction.emoji == EMOJI_OK_BOX and reaction.message.author.id == bot.user.id:
            # do not delete maze or blackjack message
            if 'MAZE' in reaction.message.content.upper() or 'BLACKJACK' in reaction.message.content.upper():
                return
            # do not delete some embed message
            if reaction.message.embeds and len(reaction.message.embeds) > 0:
                title = reaction.message.embeds[0].title
                try:
                    if title and ('SOKOBAN' in str(title.upper()) or 'FREE TIP' in str(title.upper())):
                        return
                except Exception as e:
                    pass
            try:
                await reaction.message.delete()
            except Exception as e:
                pass
        # EMOJI_100
        elif reaction.emoji == EMOJI_100 \
            and user.bot == False and reaction.message.author != user and reaction.message.author.bot == False:
            # check if react_tip_100 is ON in the server
            serverinfo = await store.sql_info_by_server(str(reaction.message.guild.id))
            if serverinfo['react_tip'] == "ON":
                if (str(reaction.message.id) + '.' + str(user.id)) not in REACT_TIP_STORE:
                    # OK add new message to array                  
                    pass
                else:
                    # he already re-acted and tipped once
                    return
                # get the amount of 100 from defined
                COIN_NAME = serverinfo['default_coin']
                real_amount = int(serverinfo['react_tip_100']) * get_decimal(COIN_NAME)
                MinTx = get_min_mv_amount(COIN_NAME)
                MaxTX = get_max_mv_amount(COIN_NAME)

                user_from = await store.sql_get_userwallet(str(user.id), COIN_NAME)
                if user_from is None:
                    userregister = await store.sql_register_user(str(user.id), COIN_NAME, 'DISCORD', 0)
                user_to = await store.sql_get_userwallet(str(reaction.message.author.id), COIN_NAME)
                if user_to is None:
                    userregister = await store.sql_register_user(str(reaction.message.author.id), COIN_NAME, 'DISCORD', 0)
                userdata_balance = await store.sql_user_balance(str(user.id), COIN_NAME)
                xfer_in = 0
                if COIN_NAME not in ENABLE_COIN_ERC:
                    xfer_in = await store.sql_user_balance_get_xfer_in(str(user.id), COIN_NAME)
                if COIN_NAME in ENABLE_COIN_DOGE+ENABLE_COIN_ERC:
                    actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
                elif COIN_NAME in ENABLE_COIN_NANO:
                    actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                    actual_balance = round(actual_balance / get_decimal(COIN_NAME), 6) * get_decimal(COIN_NAME)
                else:
                    actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])

                coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
                # Negative check
                try:
                    if actual_balance < 0:
                        msg_negative = 'Negative balance detected:\nUser: '+str(user.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                        await logchanbot(msg_negative)
                except Exception as e:
                    await logchanbot(traceback.format_exc())
                # process other check balance
                if real_amount > actual_balance or \
                    real_amount > MaxTX or real_amount < MinTx:
                    return
                else:
                    # add queue also react-tip
                    if user.id not in TX_IN_PROCESS:
                        TX_IN_PROCESS.append(user.id)
                    else:
                        try:
                            msg = await user.send(f'{EMOJI_ERROR} You have another tx in progress. Re-act tip not proceed.')
                        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                            pass
                        return
                    tip = None
                    try:
                        tip = await store.sql_mv_cn_single(str(user.id), str(reaction.message.author.id), real_amount, 'REACTTIP', COIN_NAME)
                        tip_tx_tipper = "Fee: `{}{}`".format(num_format_coin(tip['fee'], COIN_NAME), COIN_NAME)
                    except Exception as e:
                        await logchanbot(traceback.format_exc())

                    # remove queue from react-tip
                    if user.id in TX_IN_PROCESS:
                        TX_IN_PROCESS.remove(user.id)

                    if tip:
                        notifyList = await store.sql_get_tipnotify()
                        REACT_TIP_STORE.append((str(reaction.message.id) + '.' + str(user.id)))
                        if get_emoji(COIN_NAME) not in reaction.message.reactions:
                            await reaction.message.add_reaction(get_emoji(COIN_NAME))
                        # tipper shall always get DM. Ignore notifyList
                        try:
                            await user.send(
                                f'{EMOJI_ARROW_RIGHTHOOK} Tip of {num_format_coin(real_amount, COIN_NAME)} '
                                f'{COIN_NAME} '
                                f'was sent to {reaction.message.author.name}#{reaction.message.author.discriminator} in server `{reaction.message.guild.name}` by your re-acting {EMOJI_100}\n'
                                f'{tip_tx_tipper}')
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            await store.sql_toggle_tipnotify(str(user.id), "OFF")
                        if str(reaction.message.author.id) not in notifyList:
                            try:
                                await reaction.message.author.send(
                                    f'{EMOJI_MONEYFACE} You got a tip of {num_format_coin(real_amount, COIN_NAME)} '
                                    f'{COIN_NAME} from {user.name}#{user.discriminator} in server `{reaction.message.guild.name}` #{reaction.message.channel.name} from their re-acting {EMOJI_100}\n'
                                    f'{tip_tx_tipper}\n'
                                    f'{NOTIFICATION_OFF_CMD}')
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                await store.sql_toggle_tipnotify(str(reaction.message.author.id), "OFF")
                        return
                    else:
                        try:
                            await user.send(f'{user.mention} Can not deliver TX for {COIN_NAME} right now with {EMOJI_100}.')
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            await store.sql_toggle_tipnotify(str(user.id), "OFF")
                        # add to failed tx table
                        await store.sql_add_failed_tx(COIN_NAME, str(user.id), user.name, real_amount, "REACTTIP")
                        return
        # EMOJI_99 TRTL_DISCORD Only
        elif str(reaction.emoji) == EMOJI_99 and reaction.message.guild.id == TRTL_DISCORD \
            and user.bot == False and reaction.message.author != user and reaction.message.author.bot == False:
            # check if react_tip_100 is ON in the server
            serverinfo = await store.sql_info_by_server(str(reaction.message.guild.id))
            if serverinfo['react_tip'] == "ON":
                if (str(reaction.message.id) + '.' + str(user.id)) not in REACT_TIP_STORE:
                    # OK add new message to array                  
                    pass
                else:
                    # he already re-acted and tipped once
                    return
                # get the amount of 100 from defined
                COIN_NAME = "TRTL"
                real_amount = 99 * get_decimal(COIN_NAME)
                MinTx = get_min_mv_amount(COIN_NAME)
                MaxTX = get_max_mv_amount(COIN_NAME)

                user_from = await store.sql_get_userwallet(str(user.id), COIN_NAME)
                if user_from is None:
                    userregister = await store.sql_register_user(str(user.id), COIN_NAME, 'DISCORD', 0)

                userdata_balance = await store.sql_user_balance(str(user.id), COIN_NAME)
                xfer_in = 0
                if COIN_NAME not in ENABLE_COIN_ERC:
                    xfer_in = await store.sql_user_balance_get_xfer_in(str(user.id), COIN_NAME)
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
                        msg_negative = 'Negative balance detected:\nUser: '+str(user.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                        await logchanbot(msg_negative)
                except Exception as e:
                    await logchanbot(traceback.format_exc())
                user_to = await store.sql_get_userwallet(str(reaction.message.author.id), COIN_NAME)
                if user_to is None:
                    userregister = await store.sql_register_user(str(reaction.message.author.id), COIN_NAME, 'DISCORD', 0)
                # process other check balance
                if real_amount > actual_balance or \
                    real_amount > MaxTX or real_amount < MinTx:
                    return
                else:
                    # add queue also react-tip
                    if user.id not in TX_IN_PROCESS:
                        TX_IN_PROCESS.append(user.id)
                    else:
                        try:
                            msg = await user.send(f'{EMOJI_ERROR} You have another tx in progress. Re-act tip not proceed.')
                        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                            pass
                        return

                    tip = None
                    try:
                        tip = await store.sql_mv_cn_single(str(user.id), str(reaction.message.author.id), real_amount, 'REACTTIP', COIN_NAME)
                    except Exception as e:
                        await logchanbot(traceback.format_exc())

                    # remove queue from react-tip
                    if user.id in TX_IN_PROCESS:
                        TX_IN_PROCESS.remove(user.id)

                    if tip:
                        notifyList = await store.sql_get_tipnotify()
                        REACT_TIP_STORE.append((str(reaction.message.id) + '.' + str(user.id)))
                        if get_emoji(COIN_NAME) not in reaction.message.reactions:
                            await reaction.message.add_reaction(get_emoji(COIN_NAME))
                        # tipper shall always get DM. Ignore notifyList
                        try:
                            await user.send(
                                f'{EMOJI_ARROW_RIGHTHOOK} Tip of {num_format_coin(real_amount, COIN_NAME)} '
                                f'{COIN_NAME} '
                                f'was sent to {reaction.message.author.name}#{reaction.message.author.discriminator} in server `{reaction.message.guild.name}` by your re-acting {EMOJI_99}')
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            await store.sql_toggle_tipnotify(str(user.id), "OFF")
                        if str(reaction.message.author.id) not in notifyList:
                            try:
                                await reaction.message.author.send(
                                    f'{EMOJI_MONEYFACE} You got a tip of {num_format_coin(real_amount, COIN_NAME)} '
                                    f'{COIN_NAME} from {user.name}#{user.discriminator} in server `{reaction.message.guild.name}` #{reaction.message.channel.name} from their re-acting {EMOJI_99}\n'
                                    f'{NOTIFICATION_OFF_CMD}')
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                await store.sql_toggle_tipnotify(str(reaction.message.author.id), "OFF")
                        return
                    else:
                        try:
                            await user.send(f'{user.mention} Can not deliver TX for {COIN_NAME} right now with {EMOJI_99}.')
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            await store.sql_toggle_tipnotify(str(user.id), "OFF")
                        # add to failed tx table
                        await store.sql_add_failed_tx(COIN_NAME, str(user.id), user.name, real_amount, "REACTTIP")
                        return
            else:
                return
        # EMOJI_TIP Only
        elif str(reaction.emoji) == EMOJI_TIP \
            and user.bot == False and reaction.message.author != user and reaction.message.author.bot == False:
            # They re-act TIP emoji
            # check if react_tip_100 is ON in the server
            serverinfo = await store.sql_info_by_server(str(reaction.message.guild.id))
            if serverinfo['react_tip'] == "ON":
                if (str(reaction.message.id) + '.' + str(user.id)) not in REACT_TIP_STORE:
                    # OK add new message to array                  
                    pass
                else:
                    # he already re-acted and tipped once
                    return
                # get the amount of 100 from defined
                msg = reaction.message.content
                # Check if bot re-act TIP also
                if EMOJI_TIP in reaction.message.reactions:
                    # bot in re-act list
                    users_reacted = reaction.message.reactions[reaction.message.reactions.index(EMOJI_TIP)].users()
                    if users_reacted:
                        if bot.user in users_reacted:
                            print('yes, bot also in TIP react')
                        else:
                            return
                args = reaction.message.content.split(" ")
                try:
                    amount = float(args[1].replace(",", ""))
                except ValueError:
                    return

                COIN_NAME = None
                try:
                    COIN_NAME = args[2].upper()
                    if COIN_NAME in ENABLE_XMR:
                        pass
                    elif COIN_NAME not in ENABLE_COIN:
                        if COIN_NAME in ENABLE_COIN_DOGE:
                            pass
                        elif 'default_coin' in serverinfo:
                            COIN_NAME = serverinfo['default_coin'].upper()
                except:
                    if 'default_coin' in serverinfo:
                        COIN_NAME = serverinfo['default_coin'].upper()
                print("TIP REACT COIN_NAME: " + COIN_NAME)
                await _tip_react(reaction, user, amount, COIN_NAME)
        return


@bot.event
async def on_message(message):
    global LIST_IGNORECHAN, MUTE_CHANNEL
    # should ignore webhook message
    if isinstance(message.channel, discord.DMChannel) == False and message.webhook_id:
        return

    if isinstance(message.channel, discord.DMChannel) == False and message.author.bot == False and len(message.content) > 0 and message.author != bot.user:
        if config.Enable_Message_Logging == 1:
            await add_msg_redis(json.dumps([str(message.guild.id), message.guild.name, str(message.channel.id), message.channel.name, 
                                             str(message.author.id), message.author.name, str(message.id), message.content, int(time.time())]), False)
        else:
            await add_msg_redis(json.dumps([str(message.guild.id), message.guild.name, str(message.channel.id), message.channel.name, 
                                             str(message.author.id), message.author.name, str(message.id), '', int(time.time())]), False)

    # mute channel
    if isinstance(message.channel, discord.DMChannel) == False and MUTE_CHANNEL and str(message.guild.id) in MUTE_CHANNEL:
        if str(message.channel.id) in MUTE_CHANNEL[str(message.guild.id)] and message.content[1:].upper() != "SETTING UNMUTE":
            # Ignore
            return

    # filter ignorechan
    commandList = ('TIP', 'TIPALL', 'DONATE', 'HELP', 'DONATE', 'SEND', 'WITHDRAW', 'BOTBAL', 'BAL PUB', 'GAME')
    try:
        # remove first char
        if LIST_IGNORECHAN:
            if isinstance(message.channel, discord.DMChannel) == False and str(message.guild.id) in LIST_IGNORECHAN:
                if message.content[1:].upper().startswith(commandList) \
                    and (str(message.channel.id) in LIST_IGNORECHAN[str(message.guild.id)]):
                    await message.add_reaction(EMOJI_ERROR)
                    await message.channel.send(f'Bot not respond to #{message.channel.name}. It is set to ignore list by channel manager or discord server owner.')
                    return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        pass

    # Do not remove this, otherwise, command not working.
    ctx = await bot.get_context(message)
    await bot.invoke(ctx)


@bot.command(pass_context=True, name='about', help=bot_help_about, hidden = True)
async def about(ctx):
    global BOT_INVITELINK
    botdetails = discord.Embed(title='About Me', description='', colour=7047495)
    botdetails.add_field(name='Creator\'s Discord Name:', value='pluton#8888', inline=True)
    botdetails.add_field(name='My Github:', value="[TipBot Github](https://github.com/wrkzcoin/TipBot)", inline=True)
    botdetails.add_field(name='Invite Me:', value=f'{BOT_INVITELINK}', inline=True)
    botdetails.add_field(name='Servers I am in:', value=len(bot.guilds), inline=True)
    botdetails.add_field(name='Support Me:', value=f'<@{bot.user.id}> donate AMOUNT ticker', inline=True)
    botdetails.set_footer(text='Made in Python3.8+ with discord.py library!', icon_url='http://findicons.com/files/icons/2804/plex/512/python.png')
    botdetails.set_author(name=bot.user.name, icon_url=bot.user.avatar_url)
    try:
        await ctx.send(embed=botdetails)
    except Exception as e:
        await ctx.message.author.send(embed=botdetails)
        await logchanbot(traceback.format_exc())


@bot.group(hidden = True, name='reddit', aliases=['rd'], help='Reddit random images')
async def reddit(ctx):
    prefix = await get_guild_prefix(ctx)
    # Only WrkzCoin testing. Return if DM or other guild
    if isinstance(ctx.channel, discord.DMChannel) == True:
        return
    if ctx.invoked_subcommand is None:
        await ctx.send(f'{ctx.author.mention} Invalid {prefix}reddit command.\n Please use {prefix}help reddit')
        return


@reddit.command(name='meme', aliases=['memes'], help='Get random meme')
async def meme(ctx):
    global redis_conn, redis_expired
    if isinstance(ctx.channel, discord.DMChannel) == True:
        return

    get_data = []
    key = "TIPBOT:REDDIT:MEME"
    if redis_conn and redis_conn.exists(key):
        await ctx.message.add_reaction(EMOJI_FLOPPY)
        get_data = json.loads(redis_conn.get(key).decode())
    else:
        links = ["https://www.reddit.com/r/greentext",
                "https://www.reddit.com/r/memes",
                "https://www.reddit.com/r/dankmemes",
                "https://www.reddit.com/r/cryptocurrencymemes",
                "https://www.reddit.com/r/AnimalsBeingDerps",
                "https://www.reddit.com/r/AnimalsBeingJerks",
                "https://www.reddit.com/r/funny",
                "https://www.reddit.com/r/comics",
                "https://www.reddit.com/r/adviceanimals"]

        # https://stackoverflow.com/questions/61483685/how-do-i-get-aiohttp-to-output-reddit-images
        try:
            async with ctx.typing():
                for each_link in links:
                    try:
                        async with aiohttp.ClientSession() as cs:
                            async with cs.get(each_link + "/hot/.json") as r:
                                if r.status == 200:
                                    get_data_each = await r.json()
                                    get_data += get_data_each["data"]["children"]
                                    print(f'Fetch {each_link} and got {len(get_data_each["data"]["children"])} items.')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                print(f'Got total new: {len(get_data)} memes.')    
                redis_conn.set(key, json.dumps(get_data), ex=600)
        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
            return
    if get_data and len(get_data) > 0:
        # key, value = random.choice(list(get_data["data"]["children"].items()))
        try:
            # get_item = random.choice(get_data["data"]["children"])["data"]
            get_item = random.choice(get_data)['data']
            while not (get_item['url_overridden_by_dest'].endswith('.jpg') or get_item['url_overridden_by_dest'].endswith('.png')):
                get_item = random.choice(get_data)['data']
            if 'url_overridden_by_dest' in get_item and 'permalink' in get_item and 'over_18' in get_item:
                embed = discord.Embed(title = get_item['subreddit_name_prefixed'], color = 0xFF0000)
                embed.set_image(url = get_item['url_overridden_by_dest'])
                embed.set_footer(text = "https://www.reddit.com{}".format(get_item['permalink']))
                msg = await ctx.send(embed=embed)
                await msg.add_reaction(EMOJI_OK_BOX)
        except Exception as e:
            await logchanbot(traceback.format_exc())
    else:
        await ctx.message.add_reaction(EMOJI_QUESTEXCLAIM)
    return


@bot.group(hidden = True, name='tb', aliases=['tipbot'], help='Some fun commands')
async def tb(ctx):
    prefix = await get_guild_prefix(ctx)
    # Only WrkzCoin testing. Return if DM or other guild
    if isinstance(ctx.channel, discord.DMChannel) == True:
        return
    if ctx.invoked_subcommand is None:
        await ctx.send(f'{ctx.author.mention} Invalid {prefix}tb command.\n Please use {prefix}help tb')
        return


@tb.command(name='draw')
async def draw(ctx, member: discord.Member = None):
    if isinstance(ctx.channel, discord.DMChannel) == True:
        return

    user_avatar = str(ctx.message.author.avatar_url)
    if member:
        user_avatar = str(member.avatar_url)

    # if there is attachment image, we use it to draw
    if ctx.message.attachments and len(ctx.message.attachments) >= 1:
        attachment = ctx.message.attachments[0]
        link = attachment.url # https://cdn.discordapp.com/attachments
        if (attachment.filename.lower()).endswith(('.gif', '.jpeg', '.jpg', '.png')):
            try:
                if link.startswith("https://cdn.discordapp.com/attachments"):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(link) as resp:
                            if resp.status == 200:
                                if resp.headers["Content-Type"] not in ["image/gif", "image/png", "image/jpeg", "image/jpg"]:
                                    # ignore it and we use user_avatar
                                    pass
                                else: 
                                    user_avatar = link
            except Exception as e:
                await logchanbot(traceback.format_exc())
            
    try:
        timeout = 12
        res_data = None
        async with aiohttp.ClientSession() as session:
            async with session.get(user_avatar, timeout=timeout) as response:
                if response.status == 200:
                    res_data = await response.read()
                    await session.close()

        if res_data:
            hash_object = hashlib.sha256(res_data)
            hex_dig = str(hash_object.hexdigest())
            random_img_name = hex_dig + "_draw"

            random_img_name_svg = config.fun.static_draw_path + random_img_name + ".svg"
            random_img_name_png = config.fun.static_draw_path + random_img_name + ".png"
            draw_link = config.fun.static_draw_link + random_img_name + ".png"
            # if hash exists
            if os.path.exists(random_img_name_png):
                # send the made file, no need to create new
                try:
                    e = discord.Embed(timestamp=datetime.utcnow())
                    e.set_author(name=ctx.message.author.name, icon_url=ctx.message.author.avatar_url)
                    e.set_image(url=draw_link)
                    e.set_footer(text=f"Draw requested by {ctx.message.author.name}#{ctx.message.author.discriminator}")
                    msg = await ctx.send(embed=e)
                    await msg.add_reaction(EMOJI_OK_BOX)
                    await store.sql_add_tbfun(str(ctx.message.author.id), '{}#{}'.format(ctx.message.author.name, ctx.message.author.discriminator), \
                                str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'DRAW', ctx.message.content, 'DISCORD')
                except Exception as e:
                    await logchanbot(traceback.format_exc())
                await ctx.message.add_reaction(EMOJI_FLOPPY)
                return

            img = Image.open(BytesIO(res_data)).convert("RGBA")
            
            def async_sketch_image(img, svg, png_out):
                width = 4000
                height = 4000
                line_draw = sketch_image(img, svg)

                # save from svg to png and will have some transparent
                svg2png(url=svg, write_to=png_out, output_width=width, output_height=height)

                # open the saved image
                png_image = Image.open(png_out)
                imageBox = png_image.getbbox()
                # crop transparent
                cropped = png_image.crop(imageBox)
                
                # saved replaced old PNG image
                cropped.save(png_out)

            async with ctx.typing():
                partial_img = functools.partial(async_sketch_image, img, random_img_name_svg, random_img_name_png)
                lines = await bot.loop.run_in_executor(None, partial_img)
                try:
                    e = discord.Embed(timestamp=datetime.utcnow())
                    e.set_author(name=ctx.message.author.name, icon_url=ctx.message.author.avatar_url)
                    e.set_image(url=draw_link)
                    e.set_footer(text=f"Draw requested by {ctx.message.author.name}#{ctx.message.author.discriminator}")
                    msg = await ctx.send(embed=e)
                    await msg.add_reaction(EMOJI_OK_BOX)
                    await store.sql_add_tbfun(str(ctx.message.author.id), '{}#{}'.format(ctx.message.author.name, ctx.message.author.discriminator), \
                                str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'DRAW', ctx.message.content, 'DISCORD')
                except Exception as e:
                    await logchanbot(traceback.format_exc())
                await ctx.message.add_reaction(EMOJI_OK_HAND)
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return


@tb.command(name='sketchme')
async def sketchme(ctx, member: discord.Member = None):
    if isinstance(ctx.channel, discord.DMChannel) == True:
        return
    user_avatar = str(ctx.message.author.avatar_url)
    if member:
        user_avatar = str(member.avatar_url)

    # if there is attachment image, we use it to draw
    if ctx.message.attachments and len(ctx.message.attachments) >= 1:
        attachment = ctx.message.attachments[0]
        link = attachment.url # https://cdn.discordapp.com/attachments
        if (attachment.filename.lower()).endswith(('.gif', '.jpeg', '.jpg', '.png')):
            try:
                if link.startswith("https://cdn.discordapp.com/attachments"):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(link) as resp:
                            if resp.status == 200:
                                if resp.headers["Content-Type"] not in ["image/gif", "image/png", "image/jpeg", "image/jpg"]:
                                    # ignore it and we use user_avatar
                                    pass
                                else: 
                                    user_avatar = link
            except Exception as e:
                await logchanbot(traceback.format_exc())

    def create_line_drawing_image(img):
        kernel = np.array([
            [1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1],
            ], np.uint8)
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img_dilated = cv2.dilate(img_gray, kernel, iterations=1)
        img_diff = cv2.absdiff(img_dilated, img_gray)
        contour = 255 - img_diff
        return contour

    try:
        timeout = 12
        res_data = None
        async with aiohttp.ClientSession() as session:
            async with session.get(user_avatar, timeout=timeout) as response:
                if response.status == 200:
                    res_data = await response.read()
                    await session.close()

        if res_data:
            hash_object = hashlib.sha256(res_data)
            hex_dig = str(hash_object.hexdigest())
            random_img_name = hex_dig + "_sketchme"
            draw_link = config.fun.static_draw_link + random_img_name + ".png"

            random_img_name_png = config.fun.static_draw_path + random_img_name + ".png"
            # if hash exists
            if os.path.exists(random_img_name_png):
                # send the made file, no need to create new
                try:
                    e = discord.Embed(timestamp=datetime.utcnow())
                    e.set_author(name=ctx.message.author.name, icon_url=ctx.message.author.avatar_url)
                    e.set_image(url=draw_link)
                    e.set_footer(text=f"Sketchme requested by {ctx.message.author.name}#{ctx.message.author.discriminator}")
                    msg = await ctx.send(embed=e)
                    await msg.add_reaction(EMOJI_OK_BOX)
                    await store.sql_add_tbfun(str(ctx.message.author.id), '{}#{}'.format(ctx.message.author.name, ctx.message.author.discriminator), \
                                str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'SKETCHME', ctx.message.content, 'DISCORD')
                except Exception as e:
                    await logchanbot(traceback.format_exc())
                await ctx.message.add_reaction(EMOJI_FLOPPY)
                return

            img = np.array(Image.open(BytesIO(res_data)).convert("RGBA"))
            # nparr = np.fromstring(res_data, np.uint8)
            # img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR) # cv2.IMREAD_COLOR in OpenCV 3.1

            async with ctx.typing():
                partial_contour = functools.partial(create_line_drawing_image, img)
                img_contour = await bot.loop.run_in_executor(None, partial_contour)
                if img_contour is None:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    return
                try:
                    # stuff = done.pop().result()
                    # img_contour = done.pop().result()
                    # full path of image .png
                    cv2.imwrite(random_img_name_png, img_contour)

                    try:
                        e = discord.Embed(timestamp=datetime.utcnow())
                        e.set_author(name=ctx.message.author.name, icon_url=ctx.message.author.avatar_url)
                        e.set_image(url=draw_link)
                        e.set_footer(text=f"Sketchme requested by {ctx.message.author.name}#{ctx.message.author.discriminator}")
                        msg = await ctx.send(embed=e)
                        await msg.add_reaction(EMOJI_OK_BOX)
                        await store.sql_add_tbfun(str(ctx.message.author.id), '{}#{}'.format(ctx.message.author.name, ctx.message.author.discriminator), \
                                    str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'SKETCHME', ctx.message.content, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                    await ctx.message.add_reaction(EMOJI_OK_HAND)
                except asyncio.TimeoutError:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return


@tb.command(name='spank', help='Spank someone')
async def spank(ctx, member: discord.Member = None):
    if isinstance(ctx.channel, discord.DMChannel) == True:
        return
    if member is None:
        user1 = str(bot.user.avatar_url)
        user2 = str(ctx.message.author.avatar_url)
    else:
        user1 = str(ctx.message.author.avatar_url)
        user2 = str(member.avatar_url)
        if member == ctx.message.author: user1 = str(bot.user.avatar_url)

    try:
        random_gif_name = config.fun.fun_img_path + str(uuid.uuid4()) + ".gif"
        async with ctx.typing():
            fun_image = await tb_action(user1, user2, random_gif_name, 'SPANK', config.tbfun_image.spank_gif)
            if fun_image:
                await ctx.send(file=discord.File(random_gif_name))
                os.remove(random_gif_name)
                await store.sql_add_tbfun(str(ctx.message.author.id), '{}#{}'.format(ctx.message.author.name, ctx.message.author.discriminator), \
                str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'SPANK', ctx.message.content, 'DISCORD')
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return


@tb.command(name='punch', help='Punch someone')
async def punch(ctx, member: discord.Member = None):
    if isinstance(ctx.channel, discord.DMChannel) == True:
        return
    if member is None:
        user1 = str(bot.user.avatar_url)
        user2 = str(ctx.message.author.avatar_url)
    else:
        user1 = str(ctx.message.author.avatar_url)
        user2 = str(member.avatar_url)
        if member == ctx.message.author: user1 = str(bot.user.avatar_url)

    try:
        random_gif_name = config.fun.fun_img_path + str(uuid.uuid4()) + ".gif"
        async with ctx.typing():
            fun_image = await tb_action(user1, user2, random_gif_name, 'PUNCH', config.tbfun_image.punch_gif)
            if fun_image:
                await ctx.send(file=discord.File(random_gif_name))
                os.remove(random_gif_name)
                await store.sql_add_tbfun(str(ctx.message.author.id), '{}#{}'.format(ctx.message.author.name, ctx.message.author.discriminator), \
                str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'PUNCH', ctx.message.content, 'DISCORD')
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return


@tb.command(name='slap', help='Slap someone')
async def slap(ctx, member: discord.Member = None):
    if isinstance(ctx.channel, discord.DMChannel) == True:
        return
    if member is None:
        user1 = str(bot.user.avatar_url)
        user2 = str(ctx.message.author.avatar_url)
    else:
        user1 = str(ctx.message.author.avatar_url)
        user2 = str(member.avatar_url)
        if member == ctx.message.author: user1 = str(bot.user.avatar_url)

    try:
        random_gif_name = config.fun.fun_img_path + str(uuid.uuid4()) + ".gif"
        async with ctx.typing():
            fun_image = await tb_action(user1, user2, random_gif_name, 'SLAP', config.tbfun_image.slap_gif)
            if fun_image:
                await ctx.send(file=discord.File(random_gif_name))
                os.remove(random_gif_name)
                await store.sql_add_tbfun(str(ctx.message.author.id), '{}#{}'.format(ctx.message.author.name, ctx.message.author.discriminator), \
                str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'SLAP', ctx.message.content, 'DISCORD')
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return


@tb.command(name='praise', help='Praise someone')
async def praise(ctx, member: discord.Member = None):
    if isinstance(ctx.channel, discord.DMChannel) == True:
        return
    if member is None:
        user1 = str(bot.user.avatar_url)
        user2 = str(ctx.message.author.avatar_url)
    else:
        user1 = str(ctx.message.author.avatar_url)
        user2 = str(member.avatar_url)
        if member == ctx.message.author: user1 = str(bot.user.avatar_url)

    try:
        random_gif_name = config.fun.fun_img_path + str(uuid.uuid4()) + ".gif"
        fun_image = await tb_action(user1, user2, random_gif_name, 'PRAISE', config.tbfun_image.praise_gif)
        async with ctx.typing():
            if fun_image:
                await ctx.send(file=discord.File(random_gif_name))
                os.remove(random_gif_name)
                await store.sql_add_tbfun(str(ctx.message.author.id), '{}#{}'.format(ctx.message.author.name, ctx.message.author.discriminator), \
                str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'PRAISE', ctx.message.content, 'DISCORD')
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return


@tb.command(name='shoot', help='Shoot someone')
async def shoot(ctx, member: discord.Member = None):
    if isinstance(ctx.channel, discord.DMChannel) == True:
        return
    if member is None:
        user1 = str(bot.user.avatar_url)
        user2 = str(ctx.message.author.avatar_url)
    else:
        user1 = str(ctx.message.author.avatar_url)
        user2 = str(member.avatar_url)
        if member == ctx.message.author: user1 = str(bot.user.avatar_url)

    try:
        random_gif_name = config.fun.fun_img_path + str(uuid.uuid4()) + ".gif"
        async with ctx.typing():
            fun_image = await tb_action(user1, user2, random_gif_name, 'SHOOT', config.tbfun_image.shoot_gif)
            if fun_image:
                await ctx.send(file=discord.File(random_gif_name))
                os.remove(random_gif_name)
                await store.sql_add_tbfun(str(ctx.message.author.id), '{}#{}'.format(ctx.message.author.name, ctx.message.author.discriminator), \
                str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'SHOOT', ctx.message.content, 'DISCORD')
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return


@tb.command(name='kick', help='Fun kick someone')
async def kick(ctx, member: discord.Member = None):
    if isinstance(ctx.channel, discord.DMChannel) == True:
        return
    if member is None:
        user1 = str(bot.user.avatar_url)
        user2 = str(ctx.message.author.avatar_url)
    else:
        user1 = str(ctx.message.author.avatar_url)
        user2 = str(member.avatar_url)
        if member == ctx.message.author: user1 = str(bot.user.avatar_url)

    try:
        random_gif_name = config.fun.fun_img_path + str(uuid.uuid4()) + ".gif"
        async with ctx.typing():
            fun_image = await tb_action(user1, user2, random_gif_name, 'KICK', config.tbfun_image.kick_gif)
            if fun_image:
                await ctx.send(file=discord.File(random_gif_name))
                os.remove(random_gif_name)
                await store.sql_add_tbfun(str(ctx.message.author.id), '{}#{}'.format(ctx.message.author.name, ctx.message.author.discriminator), \
                str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'KICK', ctx.message.content, 'DISCORD')
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return


@tb.command(name='fistbump', aliases=['fb'], help='Fist bump someone')
async def fistbump(ctx, member: discord.Member = None):
    if isinstance(ctx.channel, discord.DMChannel) == True:
        return
    if member is None:
        user1 = str(bot.user.avatar_url)
        user2 = str(ctx.message.author.avatar_url)
    else:
        user1 = str(ctx.message.author.avatar_url)
        user2 = str(member.avatar_url)
        if member == ctx.message.author: user1 = str(bot.user.avatar_url)

    try:
        random_gif_name = config.fun.fun_img_path + str(uuid.uuid4()) + ".gif"
        async with ctx.typing():
            fun_image = await tb_action(user1, user2, random_gif_name, 'FISTBUMP', config.tbfun_image.fistbump_gif)
            if fun_image:
                await ctx.send(file=discord.File(random_gif_name))
                os.remove(random_gif_name)
                await store.sql_add_tbfun(str(ctx.message.author.id), '{}#{}'.format(ctx.message.author.name, ctx.message.author.discriminator), \
                str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'FISTBUMP', ctx.message.content, 'DISCORD')
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return


@tb.command(name='dance', help='Bean dance')
async def dance(ctx):
    if isinstance(ctx.channel, discord.DMChannel) == True:
        return

    user1 = str(ctx.message.author.avatar_url)
    user2 = str(bot.user.avatar_url)

    try:
        random_gif_name = config.fun.fun_img_path + str(uuid.uuid4()) + ".gif"
        async with ctx.typing():
            fun_image = await tb_action(user1, user2, random_gif_name, 'DANCE', config.tbfun_image.single_dance_gif)
            if fun_image:
                await ctx.send(file=discord.File(random_gif_name))
                os.remove(random_gif_name)
                await store.sql_add_tbfun(str(ctx.message.author.id), '{}#{}'.format(ctx.message.author.name, ctx.message.author.discriminator), \
                str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'DANCE', ctx.message.content, 'DISCORD')
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return


@tb.command(name='getemoji', aliases=['get_emoji', 'emoji'])
async def getemoji(ctx, *, emoji: str):
    emoji_url = None
    timeout = 12
    try:
        async with ctx.typing():
            custom_emojis = re.findall(r'<:\w*:\d*>', emoji)
            if custom_emojis and len(custom_emojis) >= 1:
                split_id = custom_emojis[0].split(":")[2]
                link = 'https://cdn.discordapp.com/emojis/' + str(split_id.replace(">", "")) + '.png'
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(link, timeout=timeout) as response:
                            if response.status == 200 or response.status == 201:
                                emoji_url = link
                except Exception as e:
                    pass
            if emoji_url is None:
                custom_emojis = re.findall(r'<a:\w*:\d*>', emoji)
                if custom_emojis and len(custom_emojis) >= 1:
                    split_id = custom_emojis[0].split(":")[2]
                    link = 'https://cdn.discordapp.com/emojis/' + str(split_id.replace(">", "")) + '.gif'
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(link, timeout=timeout) as response:
                                if response.status == 200 or response.status == 201:
                                    emoji_url = link
                    except Exception as e:
                        pass
            if emoji_url is None:
                await ctx.message.add_reaction(EMOJI_ERROR)
                msg = await ctx.send(f'{ctx.author.mention} I could not get that emoji image or it is a unicode text and not supported.')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
            else:
                try:
                    msg = await ctx.send(f'{ctx.author.mention} {emoji_url}')
                    await msg.add_reaction(EMOJI_OK_BOX)
                    await ctx.message.add_reaction(EMOJI_OK_HAND)
                except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                    await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                return
    except Exception as e:
        await ctx.send(f'{ctx.author.mention} Internal error for getting emoji.')
        await logchanbot(traceback.format_exc())
    return


@bot.group(hidden = True, name='tool', aliases=['tools'], help='Various tool commands')
async def tool(ctx):
    prefix = await get_guild_prefix(ctx)
    # Only WrkzCoin testing. Return if DM or other guild
    if isinstance(ctx.channel, discord.DMChannel) == True or ctx.guild.id != 460755304863498250:
        return
    if ctx.invoked_subcommand is None:
        await ctx.send(f'{ctx.author.mention} Invalid {prefix}tool command.\n Please use {prefix}help tool')
        return


@tool.command(name='prime', help='Check a given number if it is a prime number')
async def prime(ctx, number_test: str):
    number_test = number_test.replace(",", "")
    if len(number_test) >= 2000:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} **{number_test}** too long.')
        return
    try:
        value = is_prime(int(number_test))
        if value:
            await ctx.message.add_reaction(EMOJI_CHECKMARK)
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
    return


@tool.command(name='emoji', help='Get emoji value by re-acting')
async def emoji(ctx):
    try:
        embed = discord.Embed(title='EMOJI INFO', description=f'{ctx.author.mention}, Re-act and getinfo', colour=7047495)
        embed.add_field(name="EMOJI", value='None', inline=True)
        embed.set_footer(text="Timeout: 60s")
        msg = await ctx.send(embed=embed)

        def check(reaction, user):
            return user == ctx.message.author and reaction.message.author == bot.user and reaction.message.id == msg.id
        while True:
            try:
                reaction, user = await bot.wait_for('reaction_add', timeout=60, check=check)
            except asyncio.TimeoutError:
                await ctx.message.add_reaction(EMOJI_ALARMCLOCK)
                try:
                    await msg.delete()
                except Exception as e:
                    pass
                break
                return
            if reaction.emoji and str(reaction.emoji) != EMOJI_OK_BOX:
                try:
                    embed = discord.Embed(title='EMOJI INFO', description=f'{ctx.author.mention}, Re-act and getinfo', colour=7047495)
                    embed.add_field(name=f'EMOJI {reaction.emoji}', value='`{}`'.format(str(reaction.emoji) if re.findall(r'<?:\w*:\d*>', str(reaction.emoji)) else f'U+{ord(reaction.emoji):X}'), inline=True)
                    embed.set_footer(text="Timeout: 60s")
                    await msg.edit(embed=embed)
                    await msg.add_reaction(EMOJI_OK_BOX)
                except Exception as e:
                    await logchanbot(traceback.format_exc())
            elif str(reaction.emoji) == EMOJI_OK_BOX:
                return
    except Exception as e:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await logchanbot(traceback.format_exc())
    return


@tool.command(name='dec2hex', help='Convert decimal to hex')
async def dec2hex(ctx, decimal: str):
    decimal = decimal.replace(",", "")
    if len(decimal) >= 32:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} **{decimal}** too long.')
        return
    try:
        value = hex(int(decimal))
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        msg = await ctx.send(f'{ctx.author.mention} decimal of **{decimal}** is equal to hex:```{value}```')
        await msg.add_reaction(EMOJI_OK_BOX)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} **{decimal}** is an invalid decimal / integer.')
    return


@tool.command(name='hex2dec', help='Convert hex to decimal')
async def hex2dec(ctx, hex_string: str):
    if len(hex_string) >= 100:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} **{hex_string}** too long.')
        return
    try:
        value = int(hex_string, 16)
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        msg = await ctx.send(f'{ctx.author.mention} hex of **{hex_string}** is equal to decimal:```{str(value)}```')
        await msg.add_reaction(EMOJI_OK_BOX)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} **{hex_string}** is an invalid hex.')
    return


@tool.command(name='hex2str', aliases=['hex2ascii'], help='Convert hex to string')
async def hex2str(ctx, hex_string: str):
    if len(hex_string) >= 1000:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} **{hex_string}** too long.')
        return
    try:
        value = int(hex_string, 16)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} **{hex_string}** is an invalid hex.')
        return
    try:
        str_value = str(bytes.fromhex(hex_string).decode())
        print(str_value)
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        msg = await ctx.send(f'{ctx.author.mention} hex of **{hex_string}** in ascii is:```{str_value}```')
        await msg.add_reaction(EMOJI_OK_BOX)
    except Exception as e:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} **{hex_string}** I can not decode.')
        await logchanbot(traceback.format_exc())
    return


@tool.command(name='str2hex', aliases=['ascii2hex'], help='Convert string to hex')
async def str2hex(ctx, str2hex: str):
    if len(str2hex) >= 1000:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} **{str2hex}** too long.')
        return
    if not is_ascii(str2hex):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} **{str2hex}** is not valid ascii.')
        return
    try:
        hex_value = str(binascii.hexlify(str2hex.encode('utf_8')).decode('utf_8'))
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        msg = await ctx.send(f'{ctx.author.mention} ascii of **{str2hex}** in hex is:```{hex_value}```')
        await msg.add_reaction(EMOJI_OK_BOX)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return


@tool.command(name='find', aliases=['search'])
async def find(ctx, *, searched_text: str):
    # bot check in the first place
    if ctx.message.author.bot == True:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is not allowed using this.')
        return

    # disable game for TRTL discord
    if ctx.guild and ctx.guild.id == TRTL_DISCORD:
        await ctx.message.add_reaction(EMOJI_LOCKED)
        return

    if not re.match('^[a-zA-Z0-9-_ ]+$', searched_text):
        await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Invalid help searching text **{searched_text}**.')
        await ctx.message.add_reaction(EMOJI_ERROR)
        return

    prefix = await get_guild_prefix(ctx)
    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    if ctx.guild and serverinfo and 'enable_find' in serverinfo and serverinfo['enable_find'] == "NO":
        ## Disable all guild first. Need to manually set
        # prefix = serverinfo['prefix']
        # await ctx.message.add_reaction(EMOJI_ERROR)
        # await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Find is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING FIND`')
        # await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}find** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
        return

    if len(searched_text) >= 100:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Searched text is too long.')
        return

    if not is_ascii(searched_text):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} **{searched_text}** is not valid text.')
        return
    try:
        # Let's search
        searching = None

        async with ctx.typing():
            # search one title first
            finding = await store.sql_help_doc_get('any', searched_text)
            if finding is None:
                searching = await store.sql_help_doc_search(searched_text, 5)
        if finding or (searching and len(searching) >= 1):
            if finding:
                first_result = finding
            else:
                first_result = searching[0]
            embed = discord.Embed(title='TipBot Find', description=f'`{searched_text}`', timestamp=datetime.utcnow())
            embed.add_field(name="Title", value="```{}```".format(first_result['what'].replace('prefix', prefix)), inline=False)
            embed.add_field(name="Content", value="```{}```".format(first_result['detail'].replace('prefix', prefix)), inline=False)
            if 'example' in first_result and first_result['example'] and len(first_result['example'].strip()) > 0:
                embed.add_field(name="More", value="```{}```".format(first_result['example'].replace('prefix', prefix)), inline=False)
            embed.add_field(name="OTHER LINKS", value="{} / {} / {}".format("[Invite TipBot](http://invite.discord.bot.tips)", "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
            embed.set_footer(text=f"Find requested by {ctx.message.author.name}#{ctx.message.author.discriminator}")
            msg = await ctx.send(embed=embed)
            await msg.add_reaction(EMOJI_OK_BOX)
            await ctx.message.add_reaction(EMOJI_OK_HAND)
            reaction_numbers = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🆗']
            if searching and len(searching) > 1:
                i = 0
                for item in searching:
                    await msg.add_reaction(reaction_numbers[i])
                    i += 1
                while True:
                    def check(reaction, user):
                        return user == ctx.message.author and reaction.message.author == bot.user and reaction.message.id == msg.id and reaction.emoji \
                        in reaction_numbers

                    done, pending = await asyncio.wait([
                                        bot.wait_for('reaction_remove', timeout=60, check=check),
                                        bot.wait_for('reaction_add', timeout=60, check=check)
                                    ], return_when=asyncio.FIRST_COMPLETED)
                    try:
                        # stuff = done.pop().result()
                        reaction, user = done.pop().result()
                    except asyncio.TimeoutError:
                        break
                        
                    try:
                        emoji_n = reaction_numbers.index(str(reaction.emoji))
                        if emoji_n <= len(searching):
                            first_result = searching[emoji_n-1]
                            embed = discord.Embed(title='TipBot Find {}/{}'.format(emoji_n+1, len(searching)), description=f'`{searched_text}`', timestamp=datetime.utcnow())
                            embed.add_field(name="Title", value="```{}```".format(first_result['what'].replace('prefix', prefix)), inline=False)
                            embed.add_field(name="Content", value="```{}```".format(first_result['detail'].replace('prefix', prefix)), inline=False)
                            if 'example' in first_result and first_result['example'] and len(first_result['example'].strip()) > 0:
                                embed.add_field(name="More", value="```{}```".format(first_result['example'].replace('prefix', prefix)), inline=False)
                            embed.add_field(name="OTHER LINKS", value="{} / {} / {}".format("[Invite TipBot](http://invite.discord.bot.tips)", "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
                            embed.set_footer(text=f"Find requested by {ctx.message.author.name}#{ctx.message.author.discriminator}")
                            await msg.edit(embed=embed)
                    except Exception as e:
                        pass
        else:
            await ctx.message.add_reaction(EMOJI_INFORMATION)
            await ctx.send(f'{ctx.author.mention} Searching.. **{searched_text}** and has no result.')
        return
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return


@bot.group(name='game', help=bot_help_game)
async def game(ctx):
    global IS_RESTARTING
    # disable game for TRTL discord
    if ctx.guild and ctx.guild.id == TRTL_DISCORD:
        await ctx.message.add_reaction(EMOJI_LOCKED)
        return

    botLogChan = bot.get_channel(id=LOG_CHAN)
    # bot check in the first place
    if ctx.message.author.bot == True:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is not allowed using this.')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} (Bot) using **game** {ctx.guild.name} / {ctx.guild.id}')
        return

    # check if bot is going to restart
    if IS_RESTARTING:
        await ctx.message.add_reaction(EMOJI_REFRESH)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
        return

    prefix = await get_guild_prefix(ctx)
    if ctx.invoked_subcommand is None:
        await ctx.send(f'{ctx.author.mention} Invalid {prefix}game command.\n Please use {prefix}help game')
        return


@game.command(name='stat', help=bot_help_game_stat)
async def stat(ctx):
    # disable game for TRTL discord
    if ctx.guild and ctx.guild.id == TRTL_DISCORD:
        await ctx.message.add_reaction(EMOJI_LOCKED)
        return

    get_game_stat = await store.sql_game_stat()
    if get_game_stat and len(get_game_stat) > 0:   
        stat = discord.Embed(title='TipBot Game Stat', description='', timestamp=datetime.utcnow(), colour=7047495)
        stat.add_field(name='Total Plays', value='{}'.format(get_game_stat['paid_play']+get_game_stat['free_play']), inline=True)
        stat.add_field(name='Total Free Plays', value='{}'.format(get_game_stat['free_play']), inline=True)
        stat.add_field(name='Total Paid Plays', value='{}'.format(get_game_stat['paid_play']), inline=True)
        for COIN_NAME in GAME_COIN:
            stat.add_field(name='Paid in {}'.format(COIN_NAME), value='{}{}'.format(num_format_coin(get_game_stat[COIN_NAME], COIN_NAME), COIN_NAME), inline=True)
        stat.add_field(name="OTHER LINKS", value="{} / {} / {}".format("[Invite TipBot](http://invite.discord.bot.tips)", "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
        try:
            msg = await ctx.send(embed=stat)
            await ctx.message.add_reaction(EMOJI_OK_HAND)
            await msg.add_reaction(EMOJI_OK_BOX)
        except Exception as e:
            await ctx.message.author.send(embed=stat)
            await logchanbot(traceback.format_exc())
    return


@game.command(name='blackjack', aliases=['bj'], help=bot_help_game_blackjack)
async def blackjack(ctx):
    global GAME_SLOT_REWARD, GAME_COIN, BOT_INVITELINK, GAME_INTERACTIVE_PRGORESS, IS_RESTARTING
    # bot check in the first place
    if ctx.message.author.bot == True:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is not allowed using this.')
        return

    # disable game for TRTL discord
    if ctx.guild and ctx.guild.id == TRTL_DISCORD:
        await ctx.message.add_reaction(EMOJI_LOCKED)
        return

    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    if serverinfo and 'enable_game' in serverinfo and serverinfo['enable_game'] == "NO":
        prefix = serverinfo['prefix']
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Game is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING GAME`')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}game** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
        return

    free_game = False
    won = False

    # check if user create account less than 3 days
    try:
        account_created = ctx.message.author.created_at
        if (datetime.utcnow() - account_created).total_seconds() <= 3*24*3600:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using this.')
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())

    try: 
        index_game = "game_blackjack_channel"
        # check if bot channel is set:
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo[index_game]:
            if ctx.channel.id != int(serverinfo[index_game]):
                await ctx.message.add_reaction(EMOJI_ERROR)
                gameChan = bot.get_channel(id=int(serverinfo[index_game]))
                if gameChan:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, {gameChan.mention} is for game **blackjack** channel!!!')
                    return
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        pass
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    # end of bot channel check

    count_played = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', False)
    count_played_free = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', True)
    if count_played and count_played >= config.game.max_daily_play:
        free_game = True
        await ctx.message.add_reaction(EMOJI_ALARMCLOCK)

    if ctx.message.author.id not in GAME_INTERACTIVE_PRGORESS:
        GAME_INTERACTIVE_PRGORESS.append(ctx.message.author.id)
    else:
        await ctx.send(f'{ctx.author.mention} You are ongoing with one **game** play.')
        await ctx.message.add_reaction(EMOJI_ERROR)
        return

    game_text = '''Blackjack, by Al Sweigart al@inventwithpython.com
Rules:
    Try to get as close to 21 without going over.
    Kings, Queens, and Jacks are worth 10 points.
    Aces are worth 1 or 11 points.
    Cards 2 through 10 are worth their face value.
    (H)it to take another card.
    (S)tand to stop taking cards.
    The dealer stops hitting at 17.'''
    await ctx.send(f'{ctx.author.mention} ```{game_text}```')

    time_start = int(time.time())
    game_over = False
    player_over = False

    deck = blackjack_getDeck()
    dealerHand = [deck.pop(), deck.pop()]
    playerHand = [deck.pop(), deck.pop()]

    while not game_over:
        # check if bot is going to restart
        if IS_RESTARTING:
            await ctx.message.add_reaction(EMOJI_REFRESH)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
            return
        while not player_over:  # Keep looping until player stands or busts.
            # check if bot is going to restart
            if IS_RESTARTING:
                await ctx.message.add_reaction(EMOJI_REFRESH)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
                return
            get_display = blackjack_displayHands(playerHand, dealerHand, False)
            # Sometimes bot sending failure. If fails, we finish it.
            try:
                msg = await ctx.send('{} **BLACKJACK**\n'
                                     '```DEALER: {}\n'
                                     '{}\n'
                                     'PLAYER:  {}\n'
                                     '{}```Please re-act {}: Stand, {}: Hit'.format(ctx.author.mention, get_display['dealer_header'], 
                                     get_display['dealer'], get_display['player_header'], get_display['player'], EMOJI_LETTER_S, EMOJI_LETTER_H))
                await msg.add_reaction(EMOJI_LETTER_S)
                await msg.add_reaction(EMOJI_LETTER_H)
            except Exception as e:
                await logchanbot(traceback.format_exc())
                game_over = True
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot failed to start BlackJack message. Please re-try.')
                await ctx.message.add_reaction(EMOJI_ERROR)
                break
                return
            # Check if the player has bust:
            if blackjack_getCardValue(playerHand) >= 21:
                player_over = True
                break
            
            def check(reaction, user):
                return user == ctx.message.author and reaction.message.author == bot.user and reaction.message.id == msg.id and str(reaction.emoji) \
                in (EMOJI_LETTER_S, EMOJI_LETTER_H)
            try:
                reaction, user = await bot.wait_for('reaction_add', timeout=60, check=check)
            except asyncio.TimeoutError:
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                await ctx.send(f'{ctx.author.mention} **BLACKJACK GAME ** has waited you too long. Game exits.')
                try:
                    await msg.delete()
                except Exception as e:
                    pass
                return
            if str(reaction.emoji) == EMOJI_LETTER_H:
                # Hit/doubling down takes another card.
                newCard = deck.pop()
                rank, suit = newCard
                await ctx.send('{} **BLACKJACK** You drew a {} of {}'.format(ctx.author.mention, rank, suit))
                playerHand.append(newCard)

                if blackjack_getCardValue(playerHand) >= 21:
                    # The player has busted:
                    player_over = True
                    break
            elif str(reaction.emoji) == EMOJI_LETTER_S:
                player_over = True
                break

        # Handle the dealer's actions:
        if blackjack_getCardValue(playerHand) <= 21:
            if blackjack_getCardValue(dealerHand) >= 17:
                game_over = True
                break
            else:
                while blackjack_getCardValue(dealerHand) < 17:
                    # The dealer hits:
                    dealer_msg = await ctx.send('{} **BLACKJACK**\n'
                                                '```Dealer hits...```'.format(ctx.author.mention))
                    newCard = deck.pop()
                    rank, suit = newCard
                    dealerHand.append(newCard)
                    await asyncio.sleep(2)
                    await dealer_msg.edit(content='{} **BLACKJACK** Dealer drew a {} of {}'.format(ctx.author.mention, rank, suit))
                    if blackjack_getCardValue(dealerHand) > 21:
                        game_over = True  # The dealer has busted.
                        break
                    else:
                        await asyncio.sleep(2)
        else:
            game_over = True
            break

    dealer_get_display = blackjack_displayHands(playerHand, dealerHand, True)
    await ctx.send('{} **BLACKJACK**\n'
                   '```DEALER: {}\n'
                   '{}\n'
                   'PLAYER:  {}\n'
                   '{}```'.format(ctx.author.mention, dealer_get_display['dealer_header'], 
                   dealer_get_display['dealer'], dealer_get_display['player_header'], dealer_get_display['player']))
                                 
    playerValue = blackjack_getCardValue(playerHand)
    dealerValue = blackjack_getCardValue(dealerHand)
    # Handle whether the player won, lost, or tied:
    COIN_NAME = random.choice(GAME_COIN)
    amount = GAME_SLOT_REWARD[COIN_NAME]
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
    result = f'You got reward of **{num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}** to Tip balance!'
    if free_game == True:
        result = f'You do not get any reward because it is a free game! Waiting to refresh your paid plays (24h max).'
    if dealerValue > 21:
        won = True
        await ctx.send('{} **BLACKJACK**\n'
                       '```Dealer busts! You win! {}```'.format(ctx.author.mention, result))
    elif (playerValue > 21) or (playerValue < dealerValue):
        await ctx.send('{} **BLACKJACK**\n'
                       '```You lost!```'.format(ctx.author.mention))
    elif playerValue > dealerValue:
        won = True
        await ctx.send('{} **BLACKJACK**\n'
                       '```You won! {}```'.format(ctx.author.mention, result))
    elif playerValue == dealerValue:
        await ctx.send('{} **BLACKJACK**\n'
                       '```It\'s a tie!```'.format(ctx.author.mention))

    if free_game == True:
        try:
            await store.sql_game_free_add('BLACKJACK: PLAYER={}, DEALER={}'.format(playerValue, dealerValue), str(ctx.message.author.id), \
            'WIN' if won else 'LOSE', str(ctx.guild.id), 'BLACKJACK', int(time.time()) - time_start, 'DISCORD')
        except Exception as e:
            await logchanbot(traceback.format_exc())
    else:
        try:
            reward = await store.sql_game_add('BLACKJACK: PLAYER={}, DEALER={}'.format(playerValue, dealerValue), str(ctx.message.author.id), \
            COIN_NAME, 'WIN' if won else 'LOSE', real_amount if won else 0, get_decimal(COIN_NAME) if won else 0, str(ctx.guild.id), 'BLACKJACK', int(time.time()) - time_start, 'DISCORD')
        except Exception as e:
            await logchanbot(traceback.format_exc())
                        
    if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
        GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)


@game.command(name='slot', aliases=['slots'], help=bot_help_game_slot)
async def slot(ctx):
    global GAME_SLOT_REWARD, GAME_COIN, BOT_INVITELINK, GAME_SLOT_IN_PRGORESS
    botLogChan = bot.get_channel(id=LOG_CHAN)
    # bot check in the first place
    if ctx.message.author.bot == True:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is not allowed using this.')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} (Bot) using **take** {ctx.guild.name} / {ctx.guild.id}')
        return

    # disable game for TRTL discord
    if ctx.guild and ctx.guild.id == TRTL_DISCORD:
        await ctx.message.add_reaction(EMOJI_LOCKED)
        return

    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    if serverinfo and 'enable_game' in serverinfo and serverinfo['enable_game'] == "NO":
        prefix = serverinfo['prefix']
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Game is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING GAME`')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}game** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
        return

    free_game = False
    # Only WrkzCoin testing. Return if DM or other guild

    # check if user create account less than 3 days
    try:
        account_created = ctx.message.author.created_at
        if (datetime.utcnow() - account_created).total_seconds() <= 3*24*3600:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using this.')
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())

    try: 
        index_game = "game_slot_channel"
        # check if bot channel is set:
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo[index_game]:
            if ctx.channel.id != int(serverinfo[index_game]):
                await ctx.message.add_reaction(EMOJI_ERROR)
                gameChan = bot.get_channel(id=int(serverinfo[index_game]))
                if gameChan:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, {gameChan.mention} is for game **slot** channel!!!')
                    return
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        pass
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    # end of bot channel check

    count_played = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', False)
    count_played_free = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', True)
    if count_played and count_played >= config.game.max_daily_play:
        free_game = True
        await ctx.message.add_reaction(EMOJI_ALARMCLOCK)

    # Portion from https://github.com/MitchellAW/Discord-Bot/blob/master/features/rng.py
    slots = ['chocolate_bar', 'bell', 'tangerine', 'apple', 'cherries', 'seven']
    slot1 = slots[random.randint(0, 5)]
    slot2 = slots[random.randint(0, 5)]
    slot3 = slots[random.randint(0, 5)]
    slotOutput = '|\t:{}:\t|\t:{}:\t|\t:{}:\t|'.format(slot1, slot2, slot3)

    time_start = int(time.time())

    if ctx.message.author.id not in GAME_SLOT_IN_PRGORESS:
        GAME_SLOT_IN_PRGORESS.append(ctx.message.author.id)
    else:
        await ctx.send(f'{ctx.author.mention} You are ongoing with one **game** play.')
        await ctx.message.add_reaction(EMOJI_ERROR)
        return
    won = False
    won_x = 1
    slotOutput_2 = '$ TRY AGAIN! $'
    result = 'You lose! Good luck later!'
    if slot1 == slot2 == slot3 == 'seven':
        slotOutput_2 = '$$ JACKPOT $$\n'
        won = True
        won_x = 25
    elif slot1 == slot2 == slot3:
        slotOutput_2 = '$$ GREAT $$'
        won = True
        won_x = 10
    try:
        if free_game == False:
            if won:
                COIN_NAME = random.choice(GAME_COIN)
                amount = GAME_SLOT_REWARD[COIN_NAME] * won_x
                coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
                real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
                reward = await store.sql_game_add(slotOutput, str(ctx.message.author.id), COIN_NAME, 'WIN', real_amount, get_decimal(COIN_NAME), str(ctx.guild.id), 'SLOT', int(time.time()) - time_start, 'DISCORD')
                result = f'You won! {ctx.author.mention} got reward of **{num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}** to Tip balance!'
            else:
                reward = await store.sql_game_add(slotOutput, str(ctx.message.author.id), 'None', 'LOSE', 0, 0, str(ctx.guild.id), 'SLOT', int(time.time()) - time_start, 'DISCORD')
        else:
            if won:
                result = f'You won! but this is a free game without **reward**! Waiting to refresh your paid plays (24h max).'
            try:
                await store.sql_game_free_add(slotOutput, str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'SLOT', int(time.time()) - time_start, 'DISCORD')
            except Exception as e:
                await logchanbot(traceback.format_exc())
    except Exception as e:
        await logchanbot(traceback.format_exc())
    embed = discord.Embed(title="TIPBOT FREE SLOT ({} REWARD)".format("WITHOUT" if free_game else "WITH"), description="Anyone can freely play!", color=0x00ff00)
    embed.add_field(name="Player", value="{}#{}".format(ctx.message.author.name, ctx.message.author.discriminator), inline=False)
    embed.add_field(name="Last 24h you played", value=str(count_played_free+count_played+1), inline=False)
    embed.add_field(name="Result", value=slotOutput, inline=False)
    embed.add_field(name="Comment", value=slotOutput_2, inline=False)
    embed.add_field(name="Reward", value=result, inline=False)
    embed.add_field(name='More', value=f'[TipBot Github](https://github.com/wrkzcoin/TipBot) | {BOT_INVITELINK} ', inline=False)
    if won == False:
        embed.set_footer(text="Randomed Coin: {} | Message shall be deleted after 5s.".format(config.game.coin_game))
    else:
        embed.set_footer(text="Randomed Coin: {}".format(config.game.coin_game))
    try:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        await asyncio.sleep(config.game.game_slot_sleeping) # sleep 5s
        if ctx.message.author.id in GAME_SLOT_IN_PRGORESS:
            GAME_SLOT_IN_PRGORESS.remove(ctx.message.author.id)
        msg = await ctx.send(embed=embed)
        await msg.add_reaction(EMOJI_OK_BOX)
        if won == False:
            # Delete lose game after 10s
            await asyncio.sleep(10)
            try:
                await msg.delete()
            except discord.errors.NotFound as e:
                pass
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await logchanbot(traceback.format_exc())
    except discord.errors.NotFound as e:
        pass
    if ctx.message.author.id in GAME_SLOT_IN_PRGORESS:
        GAME_SLOT_IN_PRGORESS.remove(ctx.message.author.id)
    return


@game.command(name='bagel', aliases=['bagel1'], help=bot_help_game_bagel)
async def bagel(ctx):
    global GAME_INTERACTIVE_PRGORESS, GAME_COIN, GAME_SLOT_REWARD, BOT_INVITELINK, IS_RESTARTING
    # bot check in the first place
    if ctx.message.author.bot == True:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is not allowed using this.')
        return

    # disable game for TRTL discord
    if ctx.guild and ctx.guild.id == TRTL_DISCORD:
        await ctx.message.add_reaction(EMOJI_LOCKED)
        return

    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    if serverinfo and 'enable_game' in serverinfo and serverinfo['enable_game'] == "NO":
        prefix = serverinfo['prefix']
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Game is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING GAME`')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}game** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
        return

    # Credit: https://github.com/asweigart/PythonStdioGames
    free_game = False

    # check if user create account less than 3 days
    try:
        account_created = ctx.message.author.created_at
        if (datetime.utcnow() - account_created).total_seconds() <= 3*24*3600:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using this.')
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())

    try: 
        index_game = "game_bagel_channel"
        # check if bot channel is set:
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo[index_game]:
            if ctx.channel.id != int(serverinfo[index_game]):
                await ctx.message.add_reaction(EMOJI_ERROR)
                gameChan = bot.get_channel(id=int(serverinfo[index_game]))
                if gameChan:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, {gameChan.mention} is for game **bagel** channel!!!')
                    return
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        pass
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    # end of bot channel check

    if ctx.message.author.id not in GAME_INTERACTIVE_PRGORESS:
        GAME_INTERACTIVE_PRGORESS.append(ctx.message.author.id)
    else:
        await ctx.send(f'{ctx.author.mention} You are ongoing with one **game** play.')
        await ctx.message.add_reaction(EMOJI_ERROR)
        return

    count_played = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', False)
    count_played_free = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', True)
    if count_played and count_played >= config.game.max_daily_play:
        free_game = True
        await ctx.message.add_reaction(EMOJI_ALARMCLOCK)

    won = False
    NUM_DIGITS = 3  # (!) Try setting this to 1 or 10.
    MAX_GUESSES = 10  # (!) Try setting this to 1 or 100.
    game_text = '''Bagels, a deductive logic game.
By Al Sweigart al@inventwithpython.com

I am thinking of a {}-digit number with no repeated digits.
Try to guess what it is. Here are some clues:
When I say:    That means:
  Pico         One digit is correct but in the wrong position.
  Fermi        One digit is correct and in the right position.
  Bagels       No digit is correct.

For example, if the secret number was 248 and your guess was 843, the
clues would be Fermi Pico.'''.format(NUM_DIGITS)

    time_start = int(time.time())

    await ctx.send(f'{ctx.author.mention} ```{game_text}```')
    secretNum = bagels_getSecretNum(NUM_DIGITS)

    try:
        await ctx.send(f'{ctx.author.mention} I have thought up a number. You have {MAX_GUESSES} guesses to get it.')
        guess = None
        numGuesses = 0
        while guess is None:
            # check if bot is going to restart
            if IS_RESTARTING:
                await ctx.message.add_reaction(EMOJI_REFRESH)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
                return
            waiting_numbmsg = None
            def check(m):
                return m.author == ctx.author and m.guild.id == ctx.guild.id
            try:
                waiting_numbmsg = await bot.wait_for('message', timeout=60, check=check)
            except asyncio.TimeoutError:
                await ctx.message.add_reaction(EMOJI_ALARMCLOCK)
                await ctx.send(f'{ctx.author.mention} **Bagel Timeout**. The answer was **{secretNum}**.')
                if free_game == True:
                    try:
                        await store.sql_game_free_add(str(secretNum), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                else:
                    try:
                        reward = await store.sql_game_add(str(secretNum), str(ctx.message.author.id), 'None', 'WIN' if won else 'LOSE', 0, 0, str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                return
            if waiting_numbmsg is None:
                await ctx.message.add_reaction(EMOJI_ALARMCLOCK)
                await ctx.send(f'{ctx.author.mention} **Bagel Timeout**. The answer was **{secretNum}**.')
                if free_game == True:
                    try:
                        await store.sql_game_free_add(str(secretNum), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                else:
                    try:
                        reward = await store.sql_game_add(str(secretNum), str(ctx.message.author.id), 'None', 'LOSE', 0, 0, str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                return
            else:
                guess = waiting_numbmsg.content.strip()
                try:
                    guess_chars = [str(char) for char in str(guess)]
                    if len(guess) != NUM_DIGITS or not guess.isdecimal():
                        guess = None
                        await ctx.send(f'{ctx.author.mention} **Bagel: ** Please use {NUM_DIGITS} numbers!')
                    elif len([x for x in guess_chars if guess_chars.count(x) >= 2]) > 0:
                        guess = None
                        await ctx.send(f'{ctx.author.mention} **Bagel: ** Please do not use repeated numbers!')
                    else:
                        if guess == secretNum:
                            result = 'But this is a free game without **reward**! Waiting to refresh your paid plays (24h max).'
                            won = True
                            if won and free_game == False:
                                won_x = 5
                                COIN_NAME = random.choice(GAME_COIN)
                                amount = GAME_SLOT_REWARD[COIN_NAME] * won_x
                                coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
                                real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
                                reward = await store.sql_game_add(str(secretNum), str(ctx.message.author.id), COIN_NAME, 'WIN', real_amount, get_decimal(COIN_NAME), str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                                result = f'{ctx.author.mention} got reward of **{num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}** to Tip balance!'
                            elif won == False and free_game == True:
                                reward = await store.sql_game_add(str(secretNum), str(ctx.message.author.id), 'None', 'LOSE', 0, 0, str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                            elif free_game == True:
                                try:
                                    await store.sql_game_free_add(str(secretNum), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                            if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                                GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                            await ctx.send(f'{ctx.author.mention} **Bagel: ** You won! The answer was **{secretNum}**. You had guessed **{numGuesses+1}** times only. {result}')
                            return
                        else:
                            clues = bagels_getClues(guess, secretNum)
                            await ctx.send(f'{ctx.author.mention} **Bagel: #{numGuesses+1} ** {clues}')
                            guess = None
                            numGuesses += 1
                except Exception as e:
                    await logchanbot(traceback.format_exc())
            if numGuesses >= MAX_GUESSES:
                await ctx.send(f'{ctx.author.mention} **Bagel: ** You run out of guesses and you did it **{numGuesses}** times. Game over! The answer was **{secretNum}**')
                if free_game == True:
                    try:
                        await store.sql_game_free_add(str(secretNum), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                else:
                    try:
                        reward = await store.sql_game_add(str(secretNum), str(ctx.message.author.id), 'None', 'LOSE', 0, 0, str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                return
    except (discord.Forbidden, discord.errors.Forbidden) as e:
        await ctx.message.add_reaction(EMOJI_ERROR)
        return
    if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
        GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)


@game.command(name='bagel2', aliases=['bagels2'], help=bot_help_game_bagel)
async def bagel2(ctx):
    global GAME_INTERACTIVE_PRGORESS, GAME_COIN, GAME_SLOT_REWARD, BOT_INVITELINK, IS_RESTARTING
    # bot check in the first place
    if ctx.message.author.bot == True:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is not allowed using this.')
        return

    # disable game for TRTL discord
    if ctx.guild and ctx.guild.id == TRTL_DISCORD:
        await ctx.message.add_reaction(EMOJI_LOCKED)
        return

    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    if serverinfo and 'enable_game' in serverinfo and serverinfo['enable_game'] == "NO":
        prefix = serverinfo['prefix']
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Game is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING GAME`')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}game** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
        return

    # Credit: https://github.com/asweigart/PythonStdioGames
    free_game = False

    # check if user create account less than 3 days
    try:
        account_created = ctx.message.author.created_at
        if (datetime.utcnow() - account_created).total_seconds() <= 3*24*3600:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using this.')
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())

    try: 
        index_game = "game_bagel_channel"
        # check if bot channel is set:
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo[index_game]:
            if ctx.channel.id != int(serverinfo[index_game]):
                await ctx.message.add_reaction(EMOJI_ERROR)
                gameChan = bot.get_channel(id=int(serverinfo[index_game]))
                if gameChan:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, {gameChan.mention} is for game **bagel** channel!!!')
                    return
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        pass
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    # end of bot channel check

    if ctx.message.author.id not in GAME_INTERACTIVE_PRGORESS:
        GAME_INTERACTIVE_PRGORESS.append(ctx.message.author.id)
    else:
        await ctx.send(f'{ctx.author.mention} You are ongoing with one **game** play.')
        await ctx.message.add_reaction(EMOJI_ERROR)
        return

    count_played = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', False)
    count_played_free = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', True)
    if count_played and count_played >= config.game.max_daily_play:
        free_game = True
        await ctx.message.add_reaction(EMOJI_ALARMCLOCK)

    won = False
    NUM_DIGITS = 4  # (!) Try setting this to 1 or 10.
    MAX_GUESSES = 15  # (!) Try setting this to 1 or 100.
    secretNum = bagels_getSecretNum(NUM_DIGITS)
    split_number = [int(d) for d in str(secretNum)]
    hint = []
    hint.append('First number + Second number = {}'.format(split_number[0] + split_number[1]))
    hint.append('First number + Third number = {}'.format(split_number[0] + split_number[2]))
    hint.append('First number + Forth number = {}'.format(split_number[0] + split_number[3]))
    hint.append('Second number + Third number = {}'.format(split_number[1] + split_number[2]))
    hint.append('Second number + Forth number = {}'.format(split_number[1] + split_number[3]))
    hint.append('Third number + Forth number = {}'.format(split_number[2] + split_number[3]))

    hint.append('First number * Second number = {}'.format(split_number[0] * split_number[1]))
    hint.append('First number * Third number = {}'.format(split_number[0] * split_number[2]))
    hint.append('First number * Forth number = {}'.format(split_number[0] * split_number[3]))
    hint.append('Second number * Third number = {}'.format(split_number[1] * split_number[2]))
    hint.append('Second number * Forth number = {}'.format(split_number[1] * split_number[3]))
    hint.append('Third number * Forth number = {}'.format(split_number[2] * split_number[3]))
    numb_hint = 2
    random.shuffle(hint)
    if numb_hint > 0:
        i = 0
        hint_string = ''
        while i < numb_hint:
            hint_string += hint[i] + '\n'
            i += 1

    game_text = '''Bagels, a deductive logic game.
By Al Sweigart al@inventwithpython.com

I am thinking of a {}-digit number with no repeated digits.
Try to guess what it is. Here are some clues:
When I say:    That means:
  Pico         One digit is correct but in the wrong position.
  Fermi        One digit is correct and in the right position.
  Bagels       No digit is correct.

For example, if the secret number was 248 and your guess was 843, the
clues would be Fermi Pico.

Hints:
{}
'''.format(NUM_DIGITS, hint_string)
    await ctx.send(f'{ctx.author.mention} ```{game_text}```')

    time_start = int(time.time())

    try:
        await ctx.send(f'{ctx.author.mention} I have thought up a number. You have {MAX_GUESSES} guesses to get it.')
        guess = None
        numGuesses = 0
        while guess is None:
            # check if bot is going to restart
            if IS_RESTARTING:
                await ctx.message.add_reaction(EMOJI_REFRESH)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
                return
            waiting_numbmsg = None
            def check(m):
                return m.author == ctx.author and m.guild.id == ctx.guild.id
            try:
                waiting_numbmsg = await bot.wait_for('message', timeout=60, check=check)
            except asyncio.TimeoutError:
                await ctx.message.add_reaction(EMOJI_ALARMCLOCK)
                await ctx.send(f'{ctx.author.mention} **Bagel Timeout**. The answer was **{secretNum}**.')
                if free_game == True:
                    try:
                        await store.sql_game_free_add(str(secretNum), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                else:
                    try:
                        reward = await store.sql_game_add(str(secretNum), str(ctx.message.author.id), 'None', 'WIN' if won else 'LOSE', 0, 0, str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                return
            if waiting_numbmsg is None:
                await ctx.message.add_reaction(EMOJI_ALARMCLOCK)
                await ctx.send(f'{ctx.author.mention} **Bagel Timeout**. The answer was **{secretNum}**.')
                if free_game == True:
                    try:
                        await store.sql_game_free_add(str(secretNum), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                else:
                    try:
                        reward = await store.sql_game_add(str(secretNum), str(ctx.message.author.id), 'None', 'LOSE', 0, 0, str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                return
            else:
                guess = waiting_numbmsg.content.strip()
                try:
                    guess_chars = [str(char) for char in str(guess)]
                    if len(guess) != NUM_DIGITS or not guess.isdecimal():
                        guess = None
                        await ctx.send(f'{ctx.author.mention} **Bagel: ** Please use {NUM_DIGITS} numbers!')
                    elif len([x for x in guess_chars if guess_chars.count(x) >= 2]) > 0:
                        guess = None
                        await ctx.send(f'{ctx.author.mention} **Bagel: ** Please do not use repeated numbers!')
                    else:
                        if guess == secretNum:
                            result = 'But this is a free game without **reward**! Waiting to refresh your paid plays (24h max).'
                            won = True
                            if won and free_game == False:
                                won_x = 5
                                COIN_NAME = random.choice(GAME_COIN)
                                amount = GAME_SLOT_REWARD[COIN_NAME] * won_x
                                coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
                                real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
                                reward = await store.sql_game_add(str(secretNum), str(ctx.message.author.id), COIN_NAME, 'WIN', real_amount, get_decimal(COIN_NAME), str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                                result = f'{ctx.author.mention} got reward of **{num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}** to Tip balance!'
                            elif won == False and free_game == True:
                                reward = await store.sql_game_add(str(secretNum), str(ctx.message.author.id), 'None', 'LOSE', 0, 0, str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                            elif free_game == True:
                                try:
                                    await store.sql_game_free_add(str(secretNum), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                            if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                                GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                            await ctx.send(f'{ctx.author.mention} **Bagel: ** You won! The answer was **{secretNum}**. You had guessed **{numGuesses+1}** times only. {result}')
                            return
                        else:
                            clues = bagels_getClues(guess, secretNum)
                            await ctx.send(f'{ctx.author.mention} **Bagel: #{numGuesses+1} ** {clues}')
                            guess = None
                            numGuesses += 1
                except Exception as e:
                    await logchanbot(traceback.format_exc())
            if numGuesses >= MAX_GUESSES:
                await ctx.send(f'{ctx.author.mention} **Bagel: ** You run out of guesses and you did it **{numGuesses}** times. Game over! The answer was **{secretNum}**')
                if free_game == True:
                    try:
                        await store.sql_game_free_add(str(secretNum), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                else:
                    try:
                        reward = await store.sql_game_add(str(secretNum), str(ctx.message.author.id), 'None', 'LOSE', 0, 0, str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                return
    except (discord.Forbidden, discord.errors.Forbidden) as e:
        await ctx.message.add_reaction(EMOJI_ERROR)
        return
    if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
        GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)


@game.command(name='bagel3', aliases=['bagels3'], help=bot_help_game_bagel)
async def bagel3(ctx):
    global GAME_INTERACTIVE_PRGORESS, GAME_COIN, GAME_SLOT_REWARD, BOT_INVITELINK, IS_RESTARTING
    # bot check in the first place
    if ctx.message.author.bot == True:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is not allowed using this.')
        return

    # disable game for TRTL discord
    if ctx.guild and ctx.guild.id == TRTL_DISCORD:
        await ctx.message.add_reaction(EMOJI_LOCKED)
        return

    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    if serverinfo and 'enable_game' in serverinfo and serverinfo['enable_game'] == "NO":
        prefix = serverinfo['prefix']
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Game is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING GAME`')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}game** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
        return

    # Credit: https://github.com/asweigart/PythonStdioGames
    free_game = False

    # check if user create account less than 3 days
    try:
        account_created = ctx.message.author.created_at
        if (datetime.utcnow() - account_created).total_seconds() <= 3*24*3600:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using this.')
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())

    try: 
        index_game = "game_bagel_channel"
        # check if bot channel is set:
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo[index_game]:
            if ctx.channel.id != int(serverinfo[index_game]):
                await ctx.message.add_reaction(EMOJI_ERROR)
                gameChan = bot.get_channel(id=int(serverinfo[index_game]))
                if gameChan:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, {gameChan.mention} is for game **bagel** channel!!!')
                    return
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        pass
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    # end of bot channel check

    if ctx.message.author.id not in GAME_INTERACTIVE_PRGORESS:
        GAME_INTERACTIVE_PRGORESS.append(ctx.message.author.id)
    else:
        await ctx.send(f'{ctx.author.mention} You are ongoing with one **game** play.')
        await ctx.message.add_reaction(EMOJI_ERROR)
        return

    count_played = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', False)
    count_played_free = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', True)
    if count_played and count_played >= config.game.max_daily_play:
        free_game = True
        await ctx.message.add_reaction(EMOJI_ALARMCLOCK)

    won = False
    NUM_DIGITS = 5  # (!) Try setting this to 1 or 10.
    MAX_GUESSES = 15  # (!) Try setting this to 1 or 100.
    secretNum = bagels_getSecretNum(NUM_DIGITS)
    split_number = [int(d) for d in str(secretNum)]
    hint = []
    hint.append('First number + Second number = {}'.format(split_number[0] + split_number[1]))
    hint.append('First number + Third number = {}'.format(split_number[0] + split_number[2]))
    hint.append('First number + Forth number = {}'.format(split_number[0] + split_number[3]))
    hint.append('First number + Fifth number = {}'.format(split_number[0] + split_number[4]))
    hint.append('Second number + Third number = {}'.format(split_number[1] + split_number[2]))
    hint.append('Second number + Forth number = {}'.format(split_number[1] + split_number[3]))
    hint.append('Second number + Fifth number = {}'.format(split_number[1] + split_number[4]))
    hint.append('Third number + Forth number = {}'.format(split_number[2] + split_number[3]))
    hint.append('Third number + Fifth number = {}'.format(split_number[2] + split_number[4]))
    hint.append('Forth number + Fifth number = {}'.format(split_number[3] + split_number[4]))
    
    hint.append('First number * Second number = {}'.format(split_number[0] * split_number[1]))
    hint.append('First number * Third number = {}'.format(split_number[0] * split_number[2]))
    hint.append('First number * Forth number = {}'.format(split_number[0] * split_number[3]))
    hint.append('First number * Fifth number = {}'.format(split_number[0] * split_number[4]))
    hint.append('Second number * Third number = {}'.format(split_number[1] * split_number[2]))
    hint.append('Second number * Forth number = {}'.format(split_number[1] * split_number[3]))
    hint.append('Second number * Fifth number = {}'.format(split_number[1] * split_number[4]))
    hint.append('Third number * Forth number = {}'.format(split_number[2] * split_number[3]))
    hint.append('Third number * Fifth number = {}'.format(split_number[2] * split_number[4]))
    hint.append('Forth number * Fifth number = {}'.format(split_number[3] * split_number[4]))
    numb_hint = 2
    random.shuffle(hint)
    if numb_hint > 0:
        i = 0
        hint_string = ''
        while i < numb_hint:
            hint_string += hint[i] + '\n'
            i += 1

    game_text = '''Bagels, a deductive logic game.
By Al Sweigart al@inventwithpython.com

I am thinking of a {}-digit number with no repeated digits.
Try to guess what it is. Here are some clues:
When I say:    That means:
  Pico         One digit is correct but in the wrong position.
  Fermi        One digit is correct and in the right position.
  Bagels       No digit is correct.

For example, if the secret number was 248 and your guess was 843, the
clues would be Fermi Pico.

Hints:
{}
'''.format(NUM_DIGITS, hint_string)
    await ctx.send(f'{ctx.author.mention} ```{game_text}```')

    time_start = int(time.time())

    try:
        await ctx.send(f'{ctx.author.mention} I have thought up a number. You have {MAX_GUESSES} guesses to get it.')
        guess = None
        numGuesses = 0
        while guess is None:
            # check if bot is going to restart
            if IS_RESTARTING:
                await ctx.message.add_reaction(EMOJI_REFRESH)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
                return
            waiting_numbmsg = None
            def check(m):
                return m.author == ctx.author and m.guild.id == ctx.guild.id
            try:
                waiting_numbmsg = await bot.wait_for('message', timeout=60, check=check)
            except asyncio.TimeoutError:
                await ctx.message.add_reaction(EMOJI_ALARMCLOCK)
                await ctx.send(f'{ctx.author.mention} **Bagel Timeout**. The answer was **{secretNum}**.')
                if free_game == True:
                    try:
                        await store.sql_game_free_add(str(secretNum), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                else:
                    try:
                        reward = await store.sql_game_add(str(secretNum), str(ctx.message.author.id), 'None', 'WIN' if won else 'LOSE', 0, 0, str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                return
            if waiting_numbmsg is None:
                await ctx.message.add_reaction(EMOJI_ALARMCLOCK)
                await ctx.send(f'{ctx.author.mention} **Bagel Timeout**. The answer was **{secretNum}**.')
                if free_game == True:
                    try:
                        await store.sql_game_free_add(str(secretNum), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                else:
                    try:
                        reward = await store.sql_game_add(str(secretNum), str(ctx.message.author.id), 'None', 'LOSE', 0, 0, str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                return
            else:
                guess = waiting_numbmsg.content.strip()
                try:
                    guess_chars = [str(char) for char in str(guess)]
                    if len(guess) != NUM_DIGITS or not guess.isdecimal():
                        guess = None
                        await ctx.send(f'{ctx.author.mention} **Bagel: ** Please use {NUM_DIGITS} numbers!')
                    elif len([x for x in guess_chars if guess_chars.count(x) >= 2]) > 0:
                        guess = None
                        await ctx.send(f'{ctx.author.mention} **Bagel: ** Please do not use repeated numbers!')
                    else:
                        if guess == secretNum:
                            result = 'But this is a free game without **reward**! Waiting to refresh your paid plays (24h max).'
                            won = True
                            if won and free_game == False:
                                won_x = 5
                                COIN_NAME = random.choice(GAME_COIN)
                                amount = GAME_SLOT_REWARD[COIN_NAME] * won_x
                                coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
                                real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
                                reward = await store.sql_game_add(str(secretNum), str(ctx.message.author.id), COIN_NAME, 'WIN', real_amount, get_decimal(COIN_NAME), str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                                result = f'{ctx.author.mention} got reward of **{num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}** to Tip balance!'
                            elif won == False and free_game == True:
                                reward = await store.sql_game_add(str(secretNum), str(ctx.message.author.id), 'None', 'LOSE', 0, 0, str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                            elif free_game == True:
                                try:
                                    await store.sql_game_free_add(str(secretNum), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                            if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                                GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                            await ctx.send(f'{ctx.author.mention} **Bagel: ** You won! The answer was **{secretNum}**. You had guessed **{numGuesses+1}** times only. {result}')
                            return
                        else:
                            clues = bagels_getClues(guess, secretNum)
                            await ctx.send(f'{ctx.author.mention} **Bagel: #{numGuesses+1} ** {clues}')
                            guess = None
                            numGuesses += 1
                except Exception as e:
                    await logchanbot(traceback.format_exc())
            if numGuesses >= MAX_GUESSES:
                await ctx.send(f'{ctx.author.mention} **Bagel: ** You run out of guesses and you did it **{numGuesses}** times. Game over! The answer was **{secretNum}**')
                if free_game == True:
                    try:
                        await store.sql_game_free_add(str(secretNum), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                else:
                    try:
                        reward = await store.sql_game_add(str(secretNum), str(ctx.message.author.id), 'None', 'LOSE', 0, 0, str(ctx.guild.id), 'BAGEL', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                return
    except (discord.Forbidden, discord.errors.Forbidden) as e:
        await ctx.message.add_reaction(EMOJI_ERROR)
        return
    if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
        GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)


@game.command(name='maze', aliases=['mazes'], help=bot_help_game_maze)
async def maze(ctx):
    global GAME_INTERACTIVE_PRGORESS, GAME_COIN, GAME_SLOT_REWARD, BOT_INVITELINK, GAME_MAZE_IN_PROCESS, IS_RESTARTING
    # bot check in the first place
    if ctx.message.author.bot == True:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is not allowed using this.')
        return

    # disable game for TRTL discord
    if ctx.guild and ctx.guild.id == TRTL_DISCORD:
        await ctx.message.add_reaction(EMOJI_LOCKED)
        return

    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    if serverinfo and 'enable_game' in serverinfo and serverinfo['enable_game'] == "NO":
        prefix = serverinfo['prefix']
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Game is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING GAME`')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}game** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
        return

    # Credit: https://github.com/asweigart/PythonStdioGames
    free_game = False
    won = False

    try: 
        index_game = "game_maze_channel"
        # check if bot channel is set:
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo[index_game]:
            if ctx.channel.id != int(serverinfo[index_game]):
                await ctx.message.add_reaction(EMOJI_ERROR)
                gameChan = bot.get_channel(id=int(serverinfo[index_game]))
                if gameChan:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, {gameChan.mention} is for game **maze** channel!!!')
                    return
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        pass
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    # end of bot channel check

    if ctx.message.author.id not in GAME_INTERACTIVE_PRGORESS:
        GAME_INTERACTIVE_PRGORESS.append(ctx.message.author.id)
    else:
        await ctx.send(f'{ctx.author.mention} You are ongoing with one **game** play.')
        await ctx.message.add_reaction(EMOJI_ERROR)
        return

    count_played = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', False)
    if count_played and count_played >= config.game.max_daily_play:
        free_game = True
        await ctx.message.add_reaction(EMOJI_ALARMCLOCK)

    # Make random height and width
    try:
        if ctx.guild.id not in GAME_MAZE_IN_PROCESS:
            GAME_MAZE_IN_PROCESS.append(ctx.guild.id)
        else:
            await ctx.send(f'{ctx.author.mention} There is one **MAZE** started by a user in this guild already.')
            await ctx.message.add_reaction(EMOJI_ERROR)
            return
        WALL = '#'
        WIDTH = random.choice([25, 27, 29, 31, 33, 35])
        HEIGHT = random.choice([15, 17, 19, 21, 23, 25])
        SEED = random.randint(25, 50)
        EMPTY = ' '
        maze_data = await maze_createMazeDump(WIDTH, HEIGHT, SEED)
        playerx, playery = 1, 1
        exitx, exity = WIDTH - 2, HEIGHT - 2
        maze_created = maze_displayMaze(maze_data, WIDTH, HEIGHT, playerx, playery, exitx, exity)
        msg = await ctx.send(f'{ctx.author.mention} New Maze:\n```{maze_created}```')
        await msg.add_reaction(EMOJI_UP)
        await msg.add_reaction(EMOJI_DOWN)
        await msg.add_reaction(EMOJI_LEFT)
        await msg.add_reaction(EMOJI_RIGHT)
        await msg.add_reaction(EMPTY_DISPLAY)
        await msg.add_reaction(EMOJI_OK_BOX)

        time_start = int(time.time())
        while (playerx, playery) != (exitx, exity):
            # check if bot is going to restart
            if IS_RESTARTING:
                await ctx.message.add_reaction(EMOJI_REFRESH)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
                return
            def check(reaction, user):
                return user == ctx.message.author and reaction.message.author == bot.user and reaction.message.id == msg.id and str(reaction.emoji) \
                in (EMOJI_UP, EMOJI_DOWN, EMOJI_LEFT, EMOJI_RIGHT, EMOJI_OK_BOX)

            done, pending = await asyncio.wait([
                                bot.wait_for('reaction_remove', timeout=60, check=check),
                                bot.wait_for('reaction_add', timeout=60, check=check)
                            ], return_when=asyncio.FIRST_COMPLETED)
            try:
                # stuff = done.pop().result()
                reaction, user = done.pop().result()
            except asyncio.TimeoutError:
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                if ctx.guild.id in GAME_MAZE_IN_PROCESS:
                    GAME_MAZE_IN_PROCESS.remove(ctx.guild.id)

                if free_game == True:
                    try:
                        await store.sql_game_free_add(json.dumps(remap_keys(maze_data)), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'MAZE', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                else:
                    try:
                        reward = await store.sql_game_add(json.dumps(remap_keys(maze_data)), str(ctx.message.author.id), 'None', 'WIN' if won else 'LOSE', 0, 0, str(ctx.guild.id), 'MAZE', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                await ctx.send(f'{ctx.author.mention} **MAZE GAME** has waited you too long. Game exits.')
                try:
                    await msg.delete()
                except Exception as e:
                    pass
                return
            for future in pending:
                future.cancel()  # we don't need these anymore
                
            if str(reaction.emoji) == EMOJI_OK_BOX:
                await ctx.send(f'{ctx.author.mention} You gave up the current game.')
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                if ctx.guild.id in GAME_MAZE_IN_PROCESS:
                    GAME_MAZE_IN_PROCESS.remove(ctx.guild.id)

                if free_game == True:
                    try:
                        await store.sql_game_free_add(json.dumps(remap_keys(maze_data)), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'MAZE', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                else:
                    try:
                        reward = await store.sql_game_add(json.dumps(remap_keys(maze_data)), str(ctx.message.author.id), 'None', 'WIN' if won else 'LOSE', 0, 0, str(ctx.guild.id), 'MAZE', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                await asyncio.sleep(1)
                try:
                    await msg.delete()
                except Exception as e:
                    pass
                break
                return
            
            if (str(reaction.emoji) == EMOJI_UP and maze_data[(playerx, playery - 1)] == EMPTY) \
            or (str(reaction.emoji) == EMOJI_DOWN and maze_data[(playerx, playery + 1)] == EMPTY) \
            or (str(reaction.emoji) == EMOJI_LEFT and maze_data[(playerx - 1, playery)] == EMPTY) \
            or (str(reaction.emoji) == EMOJI_RIGHT and maze_data[(playerx + 1, playery)] == EMPTY):
                if str(reaction.emoji) == EMOJI_UP:
                    while True:
                        playery -= 1
                        if (playerx, playery) == (exitx, exity):
                            break
                        if maze_data[(playerx, playery - 1)] == WALL:
                            break  # Break if we've hit a wall.
                        if (maze_data[(playerx - 1, playery)] == EMPTY
                            or maze_data[(playerx + 1, playery)] == EMPTY):
                            break  # Break if we've reached a branch point.
                elif str(reaction.emoji) == EMOJI_DOWN:
                    while True:
                        playery += 1
                        if (playerx, playery) == (exitx, exity):
                            break
                        if maze_data[(playerx, playery + 1)] == WALL:
                            break  # Break if we've hit a wall.
                        if (maze_data[(playerx - 1, playery)] == EMPTY
                            or maze_data[(playerx + 1, playery)] == EMPTY):
                            break  # Break if we've reached a branch point.
                elif str(reaction.emoji) == EMOJI_LEFT:
                    while True:
                        playerx -= 1
                        if (playerx, playery) == (exitx, exity):
                            break
                        if maze_data[(playerx - 1, playery)] == WALL:
                            break  # Break if we've hit a wall.
                        if (maze_data[(playerx, playery - 1)] == EMPTY
                            or maze_data[(playerx, playery + 1)] == EMPTY):
                            break  # Break if we've reached a branch point.
                elif str(reaction.emoji) == EMOJI_RIGHT:
                    while True:
                        playerx += 1
                        if (playerx, playery) == (exitx, exity):
                            break
                        if maze_data[(playerx + 1, playery)] == WALL:
                            break  # Break if we've hit a wall.
                        if (maze_data[(playerx, playery - 1)] == EMPTY
                            or maze_data[(playerx, playery + 1)] == EMPTY):
                            break  # Break if we've reached a branch point.
            try:
                maze_edit = maze_displayMaze(maze_data, WIDTH, HEIGHT, playerx, playery, exitx, exity)
                await msg.edit(content=f'{ctx.author.mention} Maze:\n```{maze_edit}```')
            except Exception as e:
                await logchanbot(traceback.format_exc())
        if (playerx, playery) == (exitx, exity):
            won = True
            # Handle whether the player won, lost, or tied:
            COIN_NAME = random.choice(GAME_COIN)
            amount = GAME_SLOT_REWARD[COIN_NAME]
            coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
            real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
            result = f'You got reward of **{num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}** to Tip balance!'
            if free_game == True:
                result = f'You do not get any reward because it is a free game!'
                try:
                    await store.sql_game_free_add(json.dumps(remap_keys(maze_data)), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'MAZE', int(time.time()) - time_start, 'DISCORD')
                except Exception as e:
                    await logchanbot(traceback.format_exc())
            else:
                try:
                    reward = await store.sql_game_add(json.dumps(remap_keys(maze_data)), str(ctx.message.author.id), COIN_NAME, 'WIN' if won else 'LOSE', real_amount if won else 0, get_decimal(COIN_NAME) if won else 0, str(ctx.guild.id), 'MAZE', int(time.time()) - time_start, 'DISCORD')
                except Exception as e:
                    await logchanbot(traceback.format_exc())
            duration = seconds_str(int(time.time()) - time_start)
            if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
            if ctx.guild.id in GAME_MAZE_IN_PROCESS:
                GAME_MAZE_IN_PROCESS.remove(ctx.guild.id)
            await ctx.send(f'{ctx.author.mention} **MAZE** Grats! You completed! You completed in: **{duration}\n{result}**')
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())
    if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
        GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
    if ctx.guild.id in GAME_MAZE_IN_PROCESS:
        GAME_MAZE_IN_PROCESS.remove(ctx.guild.id)


@game.command(name='hangman', aliases=['hm'], help=bot_help_game_hangman)
async def hangman(ctx):
    global GAME_INTERACTIVE_PRGORESS, GAME_COIN, GAME_SLOT_REWARD, HANGMAN_WORDS, IS_RESTARTING
    # bot check in the first place
    if ctx.message.author.bot == True:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is not allowed using this.')
        return

    # disable game for TRTL discord
    if ctx.guild and ctx.guild.id == TRTL_DISCORD:
        await ctx.message.add_reaction(EMOJI_LOCKED)
        return

    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    if serverinfo and 'enable_game' in serverinfo and serverinfo['enable_game'] == "NO":
        prefix = serverinfo['prefix']
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Game is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING GAME`')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}game** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
        return

    # Credit: https://github.com/asweigart/PythonStdioGames
    free_game = False

    # check if user create account less than 3 days
    try:
        account_created = ctx.message.author.created_at
        if (datetime.utcnow() - account_created).total_seconds() <= 3*24*3600:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using this.')
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())

    try: 
        index_game = "game_hangman_channel"
        # check if bot channel is set:
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo[index_game]:
            if ctx.channel.id != int(serverinfo[index_game]):
                await ctx.message.add_reaction(EMOJI_ERROR)
                gameChan = bot.get_channel(id=int(serverinfo[index_game]))
                if gameChan:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, {gameChan.mention} is for game **hangman** channel!!!')
                    return
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        pass
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    # end of bot channel check

    if ctx.message.author.id not in GAME_INTERACTIVE_PRGORESS:
        GAME_INTERACTIVE_PRGORESS.append(ctx.message.author.id)
    else:
        await ctx.send(f'{ctx.author.mention} You are ongoing with one **game** play.')
        await ctx.message.add_reaction(EMOJI_ERROR)
        return

    count_played = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', False)
    count_played_free = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', True)
    if count_played and count_played >= config.game.max_daily_play:
        free_game = True
        await ctx.message.add_reaction(EMOJI_ALARMCLOCK)

    won = False

    time_start = int(time.time())
    # Setup variables for a new game:
    missedLetters = []  # List of incorrect letter guesses.
    correctLetters = []  # List of correct letter guesses.
    secretWord = random.choice(HANGMAN_WORDS).upper()  # The word the player must guess.
    game_text = '''Hangman, original code / idea by Al Sweigart al@inventwithpython.com.'''
    hm_draw = hm_drawHangman(missedLetters, correctLetters, secretWord)
    hm_picture = hm_draw['picture']
    hm_word_line = hm_draw['word_line']
    await ctx.send(f'{ctx.author.mention} ```{game_text}\n{hm_picture}\n\n{hm_word_line}```')
    try:
        await ctx.send(f'{ctx.author.mention} **HANGMAN** Please enter a single letter:')
        guess = None
        while guess is None:
            # check if bot is going to restart
            if IS_RESTARTING:
                await ctx.message.add_reaction(EMOJI_REFRESH)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
                return
            waiting_numbmsg = None
            def check(m):
                return m.author == ctx.author and m.guild.id == ctx.guild.id
            try:
                waiting_numbmsg = await bot.wait_for('message', timeout=60, check=check)
            except asyncio.TimeoutError:
                await ctx.message.add_reaction(EMOJI_ALARMCLOCK)
                await ctx.send(f'{ctx.author.mention} **HANGMAN Timeout**. The answer was **{secretWord}**.')
                if free_game == True:
                    try:
                        await store.sql_game_free_add(secretWord, str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'HANGMAN', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                else:
                    try:
                        reward = await store.sql_game_add(secretWord, str(ctx.message.author.id), 'None', 'LOSE', 0, 0, str(ctx.guild.id), 'HANGMAN', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                return
            if waiting_numbmsg is None:
                await ctx.message.add_reaction(EMOJI_ALARMCLOCK)
                await ctx.send(f'{ctx.author.mention} **HANGMAN Timeout**. The answer was **{secretWord}**.')
                if free_game == True:
                    try:
                        await store.sql_game_free_add(secretWord, str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'HANGMAN', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                else:
                    try:
                        reward = await store.sql_game_add(secretWord, str(ctx.message.author.id), 'None', 'LOSE', 0, 0, str(ctx.guild.id), 'HANGMAN', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                return
            else:
                guess = waiting_numbmsg.content.strip().upper()
                if guess in missedLetters + correctLetters:
                    await ctx.send(f'{ctx.author.mention} **HANGMAN**. You already guessed **{guess}**.')
                    guess = None
                elif not guess.isalpha():
                    guess = None
                    await ctx.send(f'{ctx.author.mention} **HANGMAN**. Please use letter.')
                elif guess in secretWord:
                    # Add the correct guess to correctLetters:
                    correctLetters.append(guess)
                    # Check if the player has won:
                    foundAllLetters = True  # Start off assuming they've won.
                    result = 'But this is a free game without **reward**! Waiting to refresh your paid plays (24h max).'
                    for secretWordLetter in secretWord:
                        if secretWordLetter not in correctLetters:
                            # There's a letter in the secret word that isn't
                            # yet in correctLetters, so the player hasn't won:
                            foundAllLetters = False
                    if foundAllLetters and free_game == False:
                        COIN_NAME = random.choice(GAME_COIN)
                        amount = GAME_SLOT_REWARD[COIN_NAME]
                        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
                        real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
                        reward = await store.sql_game_add(secretWord, str(ctx.message.author.id), COIN_NAME, 'WIN', real_amount, get_decimal(COIN_NAME), str(ctx.guild.id), 'HANGMAN', int(time.time()) - time_start, 'DISCORD')
                        result = f'{ctx.author.mention} got reward of **{num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}** to Tip balance!'
                    elif foundAllLetters and free_game == True:
                        reward = await store.sql_game_free_add(secretWord, str(ctx.message.author.id), 'WIN', str(ctx.guild.id), 'HANGMAN', int(time.time()) - time_start, 'DISCORD')
                    if foundAllLetters:
                        if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                            GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                        await ctx.send(f'{ctx.author.mention} **HANGMAN**: You won! The answer was **{secretWord}**. {result}')
                        return
                    else:
                        hm_draw = hm_drawHangman(missedLetters, correctLetters, secretWord)
                        hm_picture = hm_draw['picture']
                        hm_missed = hm_draw['missed_letter']
                        hm_word_line = hm_draw['word_line']
                        await ctx.send(f'{ctx.author.mention} **HANGMAN: **```{hm_picture}\n\n{hm_word_line}\n{hm_missed}```')
                    guess = None
                else:
                    # The player has guessed incorrectly:
                    missedLetters.append(guess)
                    guess = None
                    # Check if player has guessed too many times and lost. (The
                    # "- 1" is because we don't count the empty gallows in
                    # HANGMAN_PICS.)
                    hm_draw = hm_drawHangman(missedLetters, correctLetters, secretWord)
                    if len(missedLetters) == 6: # len(HANGMAN_PICS) = 7
                        hm_picture = hm_draw['picture']
                        hm_missed = hm_draw['missed_letter']
                        if free_game:
                            await store.sql_game_free_add(secretWord, str(ctx.message.author.id), 'LOSE', str(ctx.guild.id), 'HANGMAN', int(time.time()) - time_start, 'DISCORD')
                        else:
                            await store.sql_game_add(secretWord, str(ctx.message.author.id), 'None', 'LOSE', 0, 0, str(ctx.guild.id), 'HANGMAN', int(time.time()) - time_start, 'DISCORD')
                        await ctx.send(f'{ctx.author.mention} **HANGMAN: ** You run out of guesses. Game over! The answer was **{secretWord}**```{hm_picture}```')
                        if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                            GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                        return
                    else:
                        hm_picture = hm_draw['picture']
                        hm_missed = hm_draw['missed_letter']
                        hm_word_line = hm_draw['word_line']
                        await ctx.send(f'{ctx.author.mention} ```{hm_picture}\n\n{hm_word_line}\n{hm_missed}```')
    except (discord.Forbidden, discord.errors.Forbidden) as e:
        await ctx.message.add_reaction(EMOJI_ERROR)
        return
    if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
        GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)


@game.command(name='dice', aliases=['dices'], help=bot_help_game_dice)
async def dice(ctx):
    global GAME_INTERACTIVE_PRGORESS, GAME_COIN, GAME_SLOT_REWARD, HANGMAN_WORDS, IS_RESTARTING
    # bot check in the first place
    if ctx.message.author.bot == True:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is not allowed using this.')
        return

    # disable game for TRTL discord
    if ctx.guild and ctx.guild.id == TRTL_DISCORD:
        await ctx.message.add_reaction(EMOJI_LOCKED)
        return

    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    if serverinfo and 'enable_game' in serverinfo and serverinfo['enable_game'] == "NO":
        prefix = serverinfo['prefix']
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Game is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING GAME`')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}game** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
        return

    # Credit: https://github.com/asweigart/PythonStdioGames
    free_game = False

    # check if user create account less than 3 days
    try:
        account_created = ctx.message.author.created_at
        if (datetime.utcnow() - account_created).total_seconds() <= 3*24*3600:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using this.')
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())

    try: 
        index_game = "game_dice_channel"
        # check if bot channel is set:
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo[index_game]:
            if ctx.channel.id != int(serverinfo[index_game]):
                await ctx.message.add_reaction(EMOJI_ERROR)
                gameChan = bot.get_channel(id=int(serverinfo[index_game]))
                if gameChan:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, {gameChan.mention} is for game **dice** channel!!!')
                    return
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        pass
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    # end of bot channel check

    if ctx.message.author.id not in GAME_INTERACTIVE_PRGORESS:
        GAME_INTERACTIVE_PRGORESS.append(ctx.message.author.id)
    else:
        await ctx.send(f'{ctx.author.mention} You are ongoing with one **game** play.')
        await ctx.message.add_reaction(EMOJI_ERROR)
        return

    count_played = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', False)
    count_played_free = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', True)
    if count_played and count_played >= config.game.max_daily_play:
        free_game = True
        await ctx.message.add_reaction(EMOJI_ALARMCLOCK)

    won = False
    game_text = '''A player rolls two dice. Each die has six faces. 
These faces contain 1, 2, 3, 4, 5, and 6 spots. 
After the dice have come to rest, the sum of the spots on the two upward faces is calculated. 

* If the sum is 7 or 11 on the first throw, the player wins.
 
* If the sum is not 7 or 11 on the first throw, then the sum becomes the player's "point." 
To win, you must continue rolling the dice until you "make your point." 

* The player loses if they got 7 or 11 for their points.'''
    time_start = int(time.time())
    msg = await ctx.send(f'{ctx.author.mention} ```{game_text}```')
    await msg.add_reaction(EMOJI_OK_BOX)

    if ctx.message.author.id not in GAME_DICE_IN_PRGORESS:
        GAME_DICE_IN_PRGORESS.append(ctx.message.author.id)
    else:
        await ctx.send(f'{ctx.author.mention} You are ongoing with one **game dice** play.')
        await ctx.message.add_reaction(EMOJI_ERROR)
        return
    # sleep 3s
    await asyncio.sleep(3)

    try:
        game_over = False
        sum_dice = 0
        dice_time = 0
        while not game_over:
            dice1 = random.randint(1, 6)
            dice2 = random.randint(1, 6)
            dice_time += 1
            msg = await ctx.send(f'#{dice_time} {ctx.author.mention} your dices: **{dice1}** and **{dice2}**')
            if sum_dice == 0:
                # first dice
                sum_dice = dice1 + dice2
                if sum_dice == 7 or sum_dice == 11:
                    won = True
                    game_over = True
                    break
            else:
                # not first dice
                if dice1 + dice2 == 7 or dice1 + dice2 == 11:
                    game_over = True
                elif dice1 + dice2 == sum_dice:
                    won = True
                    game_over = True
                    break
            if game_over == False:
                msg = await ctx.send(f'{ctx.author.mention} re-throwing dices...')
                await msg.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
                await asyncio.sleep(2)
        # game end, check win or lose
        try:
            result = ''
            if free_game == False:
                won_x = 2
                if won:
                    COIN_NAME = random.choice(GAME_COIN)
                    amount = GAME_SLOT_REWARD[COIN_NAME] * won_x
                    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
                    real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
                    reward = await store.sql_game_add('{}:{}:{}:{}'.format(dice_time, sum_dice, dice1, dice2), str(ctx.message.author.id), COIN_NAME, 'WIN', real_amount, get_decimal(COIN_NAME), str(ctx.guild.id), 'DICE', int(time.time()) - time_start, 'DISCORD')
                    result = f'You won! {ctx.author.mention} got reward of **{num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}** to Tip balance!'
                else:
                    reward = await store.sql_game_add('{}:{}:{}:{}'.format(dice_time, sum_dice, dice1, dice2), str(ctx.message.author.id), 'None', 'LOSE', 0, 0, str(ctx.guild.id), 'DICE', int(time.time()) - time_start, 'DISCORD')
                    result = f'You lose!'
            else:
                if won:
                    result = f'You won! but this is a free game without **reward**! Waiting to refresh your paid plays (24h max).'
                else:
                    result = f'You lose!'
                try:
                    await store.sql_game_free_add('{}:{}:{}:{}'.format(dice_time, sum_dice, dice1, dice2), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'DICE', int(time.time()) - time_start, 'DISCORD')
                except Exception as e:
                    await logchanbot(traceback.format_exc())
            await ctx.send(f'{ctx.author.mention} **Dice: ** You threw dices **{dice_time}** times. {result}')
            if ctx.message.author.id in GAME_DICE_IN_PRGORESS:
                GAME_DICE_IN_PRGORESS.remove(ctx.message.author.id)
            if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
            return
        except Exception as e:
            await logchanbot(traceback.format_exc())
    except (discord.Forbidden, discord.errors.Forbidden) as e:
        await ctx.message.add_reaction(EMOJI_ERROR)
        return
    except Exception as e:
        await logchanbot(traceback.format_exc())
    if ctx.message.author.id in GAME_DICE_IN_PRGORESS:
        GAME_DICE_IN_PRGORESS.remove(ctx.message.author.id)
    if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
        GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)


@game.command(name='snail', aliases=['snailrace'], help=bot_help_game_snailrace)
async def snail(ctx, bet_numb: str=None):
    global GAME_INTERACTIVE_PRGORESS, GAME_COIN, GAME_SLOT_REWARD, HANGMAN_WORDS, IS_RESTARTING
    # bot check in the first place
    if ctx.message.author.bot == True:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is not allowed using this.')
        return

    # disable game for TRTL discord
    if ctx.guild and ctx.guild.id == TRTL_DISCORD:
        await ctx.message.add_reaction(EMOJI_LOCKED)
        return

    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    if serverinfo and 'enable_game' in serverinfo and serverinfo['enable_game'] == "NO":
        prefix = serverinfo['prefix']
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Game is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING GAME`')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}game** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
        return

    # Credit: https://github.com/asweigart/PythonStdioGames
    free_game = False

    # check if user create account less than 3 days
    try:
        account_created = ctx.message.author.created_at
        if (datetime.utcnow() - account_created).total_seconds() <= 3*24*3600:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using this.')
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())

    try: 
        index_game = "game_snail_channel"
        # check if bot channel is set:
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo[index_game]:
            if ctx.channel.id != int(serverinfo[index_game]):
                await ctx.message.add_reaction(EMOJI_ERROR)
                gameChan = bot.get_channel(id=int(serverinfo[index_game]))
                if gameChan:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, {gameChan.mention} is for game **snail** channel!!!')
                    return
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        pass
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    # end of bot channel check

    if ctx.message.author.id not in GAME_INTERACTIVE_PRGORESS:
        GAME_INTERACTIVE_PRGORESS.append(ctx.message.author.id)
    else:
        await ctx.send(f'{ctx.author.mention} You are ongoing with one **game** play.')
        await ctx.message.add_reaction(EMOJI_ERROR)
        return

    count_played = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', False)
    count_played_free = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', True)
    if count_played and count_played >= config.game.max_daily_play:
        free_game = True
        await ctx.message.add_reaction(EMOJI_ALARMCLOCK)

    time_start = int(time.time())
    won = False
    game_text = '''Snail Race, by Al Sweigart al@inventwithpython.com
Fast-paced snail racing action!'''
    # We do not always show credit
    if random.randint(1,100) < 30:
        msg = await ctx.send(f'{ctx.author.mention} ```{game_text}```')
        await msg.add_reaction(EMOJI_OK_BOX)

    if bet_numb is None:
        if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
            GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
        await ctx.send(f'{ctx.author.mention} There are 8 snail racers. Please put your snail number **(1 to 8)**')
        await ctx.message.add_reaction(EMOJI_ERROR)
        return
    else:
        your_snail = 0
        try:
            your_snail = int(bet_numb)
        except ValueError:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please put a valid snail number **(1 to 8)**')
            return
        if 1 <= your_snail <= 8:
            # valid betting
            # Set up the constants:
            MAX_NUM_SNAILS = 8
            MAX_NAME_LENGTH = 20
            FINISH_LINE = 36  # (!) Try modifying this number.
            # sleep 1s
            await asyncio.sleep(1)
            try:
                game_over = False
                # Enter the names of each snail:
                snailNames = []  # List of the string snail names.
                for i in range(1, MAX_NUM_SNAILS + 1):
                    snailNames.append("#" + str(i))
                start_line_mention = '{}#{} bet for #{}\n'.format(ctx.author.name, ctx.author.discriminator, your_snail)
                
                start_line = 'START' + (' ' * (FINISH_LINE - len('START')) + 'FINISH') + '\n'
                start_line += '|' + (' ' * (FINISH_LINE - len('|')) + '|')
                try:
                    msg_racing = await ctx.send(f'{start_line_mention}```{start_line}```')
                except Exception as e:
                    if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                        GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                    await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} **GAME SNAIL** failed to send message in {ctx.guild.name} / {ctx.guild.id}')
                    return

                # sleep 2s
                await asyncio.sleep(2)
                snailProgress = {}
                list_snails = ''
                for snailName in snailNames:
                    list_snails += snailName[:MAX_NAME_LENGTH] + '\n'
                    list_snails += '@v'
                    snailProgress[snailName] = 0
                await msg_racing.edit(content=f'{start_line_mention}```{start_line}\n{list_snails}```')

                while not game_over:
                    # Pick random snails to move forward:
                    for i in range(random.randint(1, MAX_NUM_SNAILS // 2)):
                        randomSnailName = random.choice(snailNames)
                        snailProgress[randomSnailName] += 1

                        # Check if a snail has reached the finish line:
                        if snailProgress[randomSnailName] == FINISH_LINE:
                            game_over = True
                            if '#' + str(your_snail) == randomSnailName:
                                # You won
                                won = True
                            # add to DB, game end, check win or lose
                            try:
                                result = ''
                                if free_game == False:
                                    won_x = 10
                                    if won:
                                        COIN_NAME = random.choice(GAME_COIN)
                                        amount = GAME_SLOT_REWARD[COIN_NAME] * won_x
                                        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
                                        real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
                                        reward = await store.sql_game_add('BET:#{}/WINNER:{}'.format(your_snail, randomSnailName), str(ctx.message.author.id), COIN_NAME, 'WIN', real_amount, get_decimal(COIN_NAME), str(ctx.guild.id), 'SNAIL', int(time.time()) - time_start, 'DISCORD')
                                        result = f'You won **snail#{str(your_snail)}**! {ctx.author.mention} got reward of **{num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}** to Tip balance!'
                                    else:
                                        reward = await store.sql_game_add('BET:#{}/WINNER:{}'.format(your_snail, randomSnailName), str(ctx.message.author.id), 'None', 'LOSE', 0, 0, str(ctx.guild.id), 'SNAIL', int(time.time()) - time_start, 'DISCORD')
                                        result = f'You lose! **snail{randomSnailName}** is the winner!!! You bet for **snail#{str(your_snail)}**'
                                else:
                                    if won:
                                        result = f'You won! **snail#{str(your_snail)}** but this is a free game without **reward**! Waiting to refresh your paid plays (24h max).'
                                    else:
                                        result = f'You lose! **snail{randomSnailName}** is the winner!!! You bet for **snail#{str(your_snail)}**'
                                    try:
                                        await store.sql_game_free_add('BET:#{}/WINNER:{}'.format(your_snail, randomSnailName), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'SNAIL', int(time.time()) - time_start, 'DISCORD')
                                    except Exception as e:
                                        await logchanbot(traceback.format_exc())
                                await ctx.send(f'{ctx.author.mention} **Snail Racing** {result}')
                                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                                return
                            except Exception as e:
                                await logchanbot(traceback.format_exc())
                            break
                    # (!) EXPERIMENT: Add a cheat here that increases a snail's progress
                    # if it has your name.

                    await asyncio.sleep(0.5)  # (!) EXPERIMENT: Try changing this value.
                    # Display the snails (with name tags):
                    list_snails = ''
                    for snailName in snailNames:
                        spaces = snailProgress[snailName]
                        list_snails += (' ' * spaces) + snailName[:MAX_NAME_LENGTH]
                        list_snails += '\n'
                        list_snails += ('.' * snailProgress[snailName]) + '@v'
                        list_snails += '\n'
                    try:
                        await msg_racing.edit(content=f'{start_line_mention}```{start_line}\n{list_snails}```')
                    except Exception as e:
                        if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                            GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                        await logchanbot(traceback.format_exc())
                        return
                return
            except Exception as e:
                await logchanbot(traceback.format_exc())
            if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
        else:
            # invalid betting
            if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please put a valid snail number **(1 to 8)**')
            return


@game.command(name='g2048', aliases=['2048'], help=bot_help_game_2048)
async def g2048(ctx):
    global GAME_INTERACTIVE_PRGORESS, GAME_COIN, GAME_SLOT_REWARD, HANGMAN_WORDS, IS_RESTARTING
    # bot check in the first place
    if ctx.message.author.bot == True:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is not allowed using this.')
        return

    # disable game for TRTL discord
    if ctx.guild and ctx.guild.id == TRTL_DISCORD:
        await ctx.message.add_reaction(EMOJI_LOCKED)
        return

    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    if serverinfo and 'enable_game' in serverinfo and serverinfo['enable_game'] == "NO":
        prefix = serverinfo['prefix']
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Game is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING GAME`')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}game** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
        return

    # Credit: https://github.com/asweigart/PythonStdioGames
    free_game = False

    # check if user create account less than 3 days
    try:
        account_created = ctx.message.author.created_at
        if (datetime.utcnow() - account_created).total_seconds() <= 3*24*3600:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using this.')
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())

    try: 
        index_game = "game_2048_channel"
        # check if bot channel is set:
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo[index_game]:
            if ctx.channel.id != int(serverinfo[index_game]):
                await ctx.message.add_reaction(EMOJI_ERROR)
                gameChan = bot.get_channel(id=int(serverinfo[index_game]))
                if gameChan:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, {gameChan.mention} is for game **2048** channel!!!')
                    return
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        pass
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    # end of bot channel check

    if ctx.message.author.id not in GAME_INTERACTIVE_PRGORESS:
        GAME_INTERACTIVE_PRGORESS.append(ctx.message.author.id)
    else:
        await ctx.send(f'{ctx.author.mention} You are ongoing with one **game** play.')
        await ctx.message.add_reaction(EMOJI_ERROR)
        return

    count_played = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', False)
    count_played_free = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', True)
    if count_played and count_played >= config.game.max_daily_play:
        free_game = True
        await ctx.message.add_reaction(EMOJI_ALARMCLOCK)

    won = False
    score = 0
    game_text = '''Twenty Forty Eight, by Al Sweigart al@inventwithpython.com

Slide all the tiles on the board in one of four directions. Tiles with
like numbers will combine into larger-numbered tiles. A new 2 tile is
added to the board on each move. You win if you can create a 2048 tile.
You lose if the board fills up the tiles before then.'''
    # We do not always show credit
    if random.randint(1,100) < 30:
        msg = await ctx.send(f'{ctx.author.mention} ```{game_text}```')
        await msg.add_reaction(EMOJI_OK_BOX)

    game_over = False
    gameBoard = g2048_getNewBoard()
    try:
        board = g2048_drawBoard(gameBoard) # string
        try:
            msg = await ctx.send(f'**GAME 2048 starts**...')
        except Exception as e:
            if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
            await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} **GAME 2048** failed to send message in {ctx.guild.name} / {ctx.guild.id}')
            return

        await msg.add_reaction(EMOJI_UP)
        await msg.add_reaction(EMOJI_DOWN)
        await msg.add_reaction(EMOJI_LEFT)
        await msg.add_reaction(EMOJI_RIGHT)
        await msg.add_reaction(EMPTY_DISPLAY)
        await msg.add_reaction(EMOJI_OK_BOX)
        time_start = int(time.time())

        while not game_over:
            await msg.edit(content=f'{ctx.author.mention}```GAME 2048\n{board}```Your score: **{score}**')
            score = g2048_getScore(gameBoard)
            if IS_RESTARTING:
                await ctx.message.add_reaction(EMOJI_REFRESH)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
                return
            def check(reaction, user):
                return user == ctx.message.author and reaction.message.author == bot.user and reaction.message.id == msg.id and str(reaction.emoji) \
                in (EMOJI_UP, EMOJI_DOWN, EMOJI_LEFT, EMOJI_RIGHT, EMOJI_OK_BOX)

            done, pending = await asyncio.wait([
                                bot.wait_for('reaction_remove', timeout=120, check=check),
                                bot.wait_for('reaction_add', timeout=120, check=check)
                            ], return_when=asyncio.FIRST_COMPLETED)
            try:
                # stuff = done.pop().result()
                reaction, user = done.pop().result()
            except asyncio.TimeoutError:
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                if free_game == True:
                    try:
                        await store.sql_game_free_add(board, str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), '2048', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                else:
                    try:
                        reward = await store.sql_game_add(board, str(ctx.message.author.id), 'None', 'WIN' if won else 'LOSE', 0, 0, str(ctx.guild.id), '2048', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                await ctx.send(f'{ctx.author.mention} **2048 GAME** has waited you too long. Game exits. Your score **{score}**.')
                game_over = True
                return
            for future in pending:
                future.cancel()  # we don't need these anymore

            if str(reaction.emoji) == EMOJI_OK_BOX:
                await ctx.send(f'{ctx.author.mention} You gave up the current game. Your score **{score}**.')
                game_over = True
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)

                if free_game == True:
                    try:
                        await store.sql_game_free_add(board, str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), '2048', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                else:
                    try:
                        reward = await store.sql_game_add(board, str(ctx.message.author.id), 'None', 'WIN' if won else 'LOSE', 0, 0, str(ctx.guild.id), '2048', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                await asyncio.sleep(1)
                try:
                    await msg.delete()
                except Exception as e:
                    pass
                break
                return

            playerMove = None
            if str(reaction.emoji) == EMOJI_UP:
                playerMove = 'W'
            elif str(reaction.emoji) == EMOJI_DOWN:
                playerMove = 'S'
            elif str(reaction.emoji) == EMOJI_LEFT:
                playerMove = 'A'
            elif str(reaction.emoji) == EMOJI_RIGHT:
                playerMove = 'D'
            if playerMove in ('W', 'A', 'S', 'D'):
                gameBoard = g2048_makeMove(gameBoard, playerMove)
                g2048_addTwoToBoard(gameBoard)
                board = g2048_drawBoard(gameBoard)
            if g2048_isFull(gameBoard):
                game_over = True
                won = True # we assume won but it is not a winner
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                board = g2048_drawBoard(gameBoard)

                # Handle whether the player won, lost, or tied:
                COIN_NAME = random.choice(GAME_COIN)
                amount = GAME_SLOT_REWARD[COIN_NAME] * (int(score / 100) if score / 100 > 1 else 1) # testing first
                coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
                real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
                result = f'You got reward of **{num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}** to Tip balance!'
                duration = seconds_str(int(time.time()) - time_start)
                if free_game == True:
                    result = f'You do not get any reward because it is a free game! Waiting to refresh your paid plays (24h max).'
                    try:
                        await store.sql_game_free_add(board, str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), '2048', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                else:
                    try:
                        reward = await store.sql_game_add(board, str(ctx.message.author.id), COIN_NAME, 'WIN' if won else 'LOSE', real_amount if won else 0, get_decimal(COIN_NAME) if won else 0, str(ctx.guild.id), '2048', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                await msg.edit(content=f'**{ctx.author.mention} Game Over**```{board}```Your score: **{score}**\nYou have spent time: **{duration}**\n{result}')
                await msg.add_reaction(EMOJI_OK_BOX)
                return

    except Exception as e:
        await logchanbot(traceback.format_exc())
    if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
        GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)


@commands.is_owner()
@game.command(name='sokotest', hidden = True)
async def sokotest(ctx, level:int=0):
    # For testing display
    global GAME_INTERACTIVE_PRGORESS, GAME_COIN, GAME_SLOT_REWARD, HANGMAN_WORDS, IS_RESTARTING
    # bot check in the first place
    if ctx.message.author.bot == True:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is not allowed using this.')
        return

    # disable game for TRTL discord
    if ctx.guild and ctx.guild.id == TRTL_DISCORD:
        await ctx.message.add_reaction(EMOJI_LOCKED)
        return

    # Set up the constants:
    WIDTH = 'width'
    HEIGHT = 'height'

    # Characters in level files that represent objects:
    WALL = '#'
    FACE = '@'
    CRATE = '$'
    GOAL = '.'
    CRATE_ON_GOAL = '*'
    PLAYER_ON_GOAL = '+'
    EMPTY = ' '

    # How objects should be displayed on the screen:
    # WALL_DISPLAY = random.choice([':red_square:', ':orange_square:', ':yellow_square:', ':blue_square:', ':purple_square:']) # '#' # chr(9617)   # Character 9617 is '░'
    WALL_DISPLAY = random.choice(['🟥', '🟧', '🟨', '🟦', '🟪'])
    FACE_DISPLAY = '<:smiling_face:700888455877754991>'
    # CRATE_DISPLAY = ':brown_square:'  # Character 9679 is '▪'
    CRATE_DISPLAY = '🟫'
    # GOAL_DISPLAY = ':negative_squared_cross_mark:'
    GOAL_DISPLAY = '❎'
    # A list of chr() codes is at https://inventwithpython.com/chr
    # CRATE_ON_GOAL_DISPLAY = ':green_square:'
    CRATE_ON_GOAL_DISPLAY = '🟩'
    PLAYER_ON_GOAL_DISPLAY = '<:grinning_face:700888456028487700>'
    # EMPTY_DISPLAY = ':black_large_square:'
    # EMPTY_DISPLAY = '⬛' # already initial

    CHAR_MAP = {WALL: WALL_DISPLAY, FACE: FACE_DISPLAY,
                CRATE: CRATE_DISPLAY, PLAYER_ON_GOAL: PLAYER_ON_GOAL_DISPLAY,
                GOAL: GOAL_DISPLAY, CRATE_ON_GOAL: CRATE_ON_GOAL_DISPLAY,
                EMPTY: EMPTY_DISPLAY}

    won = False
    game_text = f'''Push the solid crates {CRATE_DISPLAY} onto the {GOAL_DISPLAY}. You can only push,
you cannot pull. Re-act with direction to move up-left-down-right,
respectively. You can also reload game level.'''
    # We do not always show credit
    if random.randint(1,100) < 30:
        msg = await ctx.send(f'{ctx.author.mention} ```{game_text}```')
        await msg.add_reaction(EMOJI_OK_BOX)

    get_level = await store.sql_game_get_level_tpl(level, 'SOKOBAN')
    
    if get_level is None:
        await ctx.send(f'{ctx.author.mention} Check back later.')
        await ctx.message.add_reaction(EMOJI_INFORMATION)
        return

    def loadLevel(level_str: str):
        level_str = level_str
        currentLevel = {WIDTH: 0, HEIGHT: 0}
        y = 0

        # Add the line to the current level.
        # We use line[:-1] so we don't include the newline:
        for line in level_str.splitlines():
            line += "\n"
            for x, levelChar in enumerate(line[:-1]):
                currentLevel[(x, y)] = levelChar
            y += 1

            if len(line) - 1 > currentLevel[WIDTH]:
                currentLevel[WIDTH] = len(line) - 1
            if y > currentLevel[HEIGHT]:
                currentLevel[HEIGHT] = y

        return currentLevel

    def displayLevel(levelData):
        # Draw the current level.
        solvedCrates = 0
        unsolvedCrates = 0

        level_display = ''
        for y in range(levelData[HEIGHT]):
            for x in range(levelData[WIDTH]):
                if levelData.get((x, y), EMPTY) == CRATE:
                    unsolvedCrates += 1
                elif levelData.get((x, y), EMPTY) == CRATE_ON_GOAL:
                    solvedCrates += 1
                prettyChar = CHAR_MAP[levelData.get((x, y), EMPTY)]
                level_display += prettyChar
            level_display += '\n'
        totalCrates = unsolvedCrates + solvedCrates
        level_display += "\nSolved: {}/{}".format(solvedCrates, totalCrates)
        return level_display

    currentLevel = loadLevel(get_level['template_str'])
    display_level = displayLevel(currentLevel)

    embed = discord.Embed(title=f'SOKOBAN GAME TEST RUN {ctx.author.name}#{ctx.author.discriminator}', description=f'{display_level}', timestamp=datetime.utcnow(), colour=7047495)
    embed.add_field(name="LEVEL", value=f'{level}')
    embed.add_field(name="OTHER LINKS", value="{} / {} / {}".format("[Invite TipBot](http://invite.discord.bot.tips)", 
                    "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
    try:
        msg = await ctx.send(embed=embed)
    except Exception as e:
        await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} **GAME SOKOBAN** failed to send embed in {ctx.guild.name} / {ctx.guild.id}')
        return


@game.command(name='sokoban', aliases=['soko'], help=bot_help_game_sokoban)
async def sokoban(ctx):
    global GAME_INTERACTIVE_PRGORESS, GAME_COIN, GAME_SLOT_REWARD, HANGMAN_WORDS, IS_RESTARTING
    # bot check in the first place
    if ctx.message.author.bot == True:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is not allowed using this.')
        return

    # disable game for TRTL discord
    if ctx.guild and ctx.guild.id == TRTL_DISCORD:
        await ctx.message.add_reaction(EMOJI_LOCKED)
        return

    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    if serverinfo and 'enable_game' in serverinfo and serverinfo['enable_game'] == "NO":
        prefix = serverinfo['prefix']
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Game is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING GAME`')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}game** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
        return

    free_game = False

    # check if user create account less than 3 days
    try:
        account_created = ctx.message.author.created_at
        if (datetime.utcnow() - account_created).total_seconds() <= 3*24*3600:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using this.')
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())

    try: 
        index_game = "game_sokoban_channel"
        # check if bot channel is set:
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo[index_game]:
            if ctx.channel.id != int(serverinfo[index_game]):
                await ctx.message.add_reaction(EMOJI_ERROR)
                gameChan = bot.get_channel(id=int(serverinfo[index_game]))
                if gameChan:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, {gameChan.mention} is for game **sokoban** channel!!!')
                    return
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        pass
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    # end of bot channel check

    if ctx.message.author.id not in GAME_INTERACTIVE_PRGORESS:
        GAME_INTERACTIVE_PRGORESS.append(ctx.message.author.id)
    else:
        await ctx.send(f'{ctx.author.mention} You are ongoing with one **game** play.')
        await ctx.message.add_reaction(EMOJI_ERROR)
        return

    count_played = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', False)
    count_played_free = await store.sql_game_count_user(str(ctx.message.author.id), config.game.duration_24h, 'DISCORD', True)
    if count_played and count_played >= config.game.max_daily_play:
        free_game = True
        await ctx.message.add_reaction(EMOJI_ALARMCLOCK)

    # Set up the constants:
    WIDTH = 'width'
    HEIGHT = 'height'

    # Characters in level files that represent objects:
    WALL = '#'
    FACE = '@'
    CRATE = '$'
    GOAL = '.'
    CRATE_ON_GOAL = '*'
    PLAYER_ON_GOAL = '+'
    EMPTY = ' '

    # How objects should be displayed on the screen:
    # WALL_DISPLAY = random.choice([':red_square:', ':orange_square:', ':yellow_square:', ':blue_square:', ':purple_square:']) # '#' # chr(9617)   # Character 9617 is '░'
    WALL_DISPLAY = random.choice(['🟥', '🟧', '🟨', '🟦', '🟪'])
    FACE_DISPLAY = ':zany_face:' # '<:smiling_face:700888455877754991>' some guild not support having this
    # CRATE_DISPLAY = ':brown_square:'  # Character 9679 is '▪'
    CRATE_DISPLAY = '🟫'
    # GOAL_DISPLAY = ':negative_squared_cross_mark:'
    GOAL_DISPLAY = '❎'
    # A list of chr() codes is at https://inventwithpython.com/chr
    # CRATE_ON_GOAL_DISPLAY = ':green_square:'
    CRATE_ON_GOAL_DISPLAY = '🟩'
    PLAYER_ON_GOAL_DISPLAY = '😁' # '<:grinning_face:700888456028487700>'
    # EMPTY_DISPLAY = ':black_large_square:'
    # EMPTY_DISPLAY = '⬛' already initial

    CHAR_MAP = {WALL: WALL_DISPLAY, FACE: FACE_DISPLAY,
                CRATE: CRATE_DISPLAY, PLAYER_ON_GOAL: PLAYER_ON_GOAL_DISPLAY,
                GOAL: GOAL_DISPLAY, CRATE_ON_GOAL: CRATE_ON_GOAL_DISPLAY,
                EMPTY: EMPTY_DISPLAY}

    won = False
    game_text = f'''Push the solid crates {CRATE_DISPLAY} onto the {GOAL_DISPLAY}. You can only push,
you cannot pull. Re-act with direction to move up-left-down-right,
respectively. You can also reload game level.'''
    # We do not always show credit
    if random.randint(1,100) < 30:
        msg = await ctx.send(f'{ctx.author.mention} ```{game_text}```')
        await msg.add_reaction(EMOJI_OK_BOX)

    # get max level user already played.
    level = 0
    get_level_user = await store.sql_game_get_level_user(str(ctx.message.author.id), 'SOKOBAN')
    print(get_level_user)
    if get_level_user < 0:
        level = 0
    elif get_level_user >= 0:
        level = get_level_user + 1

    get_level = await store.sql_game_get_level_tpl(level, 'SOKOBAN')
    
    if get_level is None:
        if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
            GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
        await ctx.send(f'{ctx.author.mention} Check back later.')
        await ctx.message.add_reaction(EMOJI_INFORMATION)
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} **GAME SOKOBAN** failed get level **{str(level)}** in {ctx.guild.name} / {ctx.guild.id}')
        return


    def loadLevel(level_str: str):
        level_str = level_str
        currentLevel = {WIDTH: 0, HEIGHT: 0}
        y = 0

        # Add the line to the current level.
        # We use line[:-1] so we don't include the newline:
        for line in level_str.splitlines():
            line += "\n"
            for x, levelChar in enumerate(line[:-1]):
                currentLevel[(x, y)] = levelChar
            y += 1

            if len(line) - 1 > currentLevel[WIDTH]:
                currentLevel[WIDTH] = len(line) - 1
            if y > currentLevel[HEIGHT]:
                currentLevel[HEIGHT] = y

        return currentLevel

    def displayLevel(levelData):
        # Draw the current level.
        solvedCrates = 0
        unsolvedCrates = 0

        level_display = ''
        for y in range(levelData[HEIGHT]):
            for x in range(levelData[WIDTH]):
                if levelData.get((x, y), EMPTY) == CRATE:
                    unsolvedCrates += 1
                elif levelData.get((x, y), EMPTY) == CRATE_ON_GOAL:
                    solvedCrates += 1
                prettyChar = CHAR_MAP[levelData.get((x, y), EMPTY)]
                level_display += prettyChar
            level_display += '\n'
        totalCrates = unsolvedCrates + solvedCrates
        level_display += "\nSolved: {}/{}".format(solvedCrates, totalCrates)
        return level_display

    game_over = False

    try:
        currentLevel = loadLevel(get_level['template_str'])
        display_level = displayLevel(currentLevel)

        embed = discord.Embed(title=f'SOKOBAN GAME {ctx.author.name}#{ctx.author.discriminator}', description='**SOKOBAN GAME** starts...', timestamp=datetime.utcnow(), colour=7047495)
        embed.add_field(name="LEVEL", value=f'{level}')
        embed.add_field(name="OTHER LINKS", value="{} / {} / {}".format("[Invite TipBot](http://invite.discord.bot.tips)", 
                        "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
        try:
            msg = await ctx.send(embed=embed)
        except Exception as e:
            if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
            await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
            await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} **GAME SOKOBAN** failed to send embed in {ctx.guild.name} / {ctx.guild.id}')
            return
        await msg.add_reaction(EMOJI_UP)
        await msg.add_reaction(EMOJI_DOWN)
        await msg.add_reaction(EMOJI_LEFT)
        await msg.add_reaction(EMOJI_RIGHT)
        await msg.add_reaction(EMPTY_DISPLAY)
        await msg.add_reaction(EMOJI_REFRESH)
        await msg.add_reaction(EMOJI_OK_BOX)
        time_start = int(time.time())
        while not game_over:
            if IS_RESTARTING:
                await ctx.message.add_reaction(EMOJI_REFRESH)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
                return

            display_level = displayLevel(currentLevel)
            embed = discord.Embed(title=f'SOKOBAN GAME {ctx.author.name}#{ctx.author.discriminator}', description=f'{display_level}', timestamp=datetime.utcnow(), colour=7047495)
            embed.add_field(name="LEVEL", value=f'{level}')
            embed.add_field(name="OTHER LINKS", value="{} / {} / {}".format("[Invite TipBot](http://invite.discord.bot.tips)", 
                            "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
            await msg.edit(embed=embed)

            # Find the player position:
            for position, character in currentLevel.items():
                if character in (FACE, PLAYER_ON_GOAL):
                    playerX, playerY = position

            def check(reaction, user):
                return user == ctx.message.author and reaction.message.author == bot.user and reaction.message.id == msg.id and str(reaction.emoji) \
                in (EMOJI_UP, EMOJI_DOWN, EMOJI_LEFT, EMOJI_RIGHT, EMOJI_OK_BOX, EMOJI_REFRESH)

            done, pending = await asyncio.wait([
                                bot.wait_for('reaction_remove', timeout=120, check=check),
                                bot.wait_for('reaction_add', timeout=120, check=check)
                            ], return_when=asyncio.FIRST_COMPLETED)
            try:
                # stuff = done.pop().result()
                reaction, user = done.pop().result()
            except (asyncio.TimeoutError, asyncio.exceptions.TimeoutError) as e:
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
                await ctx.send(f'{ctx.author.mention} **SOKOBAN GAME** has waited you too long. Game exits.')
                game_over = True

                if free_game == True:
                    try:
                        await store.sql_game_free_add(str(level), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'SOKOBAN', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                else:
                    try:
                        reward = await store.sql_game_add(str(level), str(ctx.message.author.id), 'None', 'WIN' if won else 'LOSE', 0, 0, str(ctx.guild.id), 'SOKOBAN', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                return
            for future in pending:
                future.cancel()  # we don't need these anymore

            if str(reaction.emoji) == EMOJI_OK_BOX:
                await ctx.send(f'{ctx.author.mention} **SOKOBAN GAME** You gave up the current game.')
                game_over = True
                if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                    GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)

                if free_game == True:
                    try:
                        await store.sql_game_free_add(str(level), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'SOKOBAN', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                else:
                    try:
                        reward = await store.sql_game_add(str(level), str(ctx.message.author.id), 'None', 'WIN' if won else 'LOSE', 0, 0, str(ctx.guild.id), 'SOKOBAN', int(time.time()) - time_start, 'DISCORD')
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                await asyncio.sleep(1)
                try:
                    await msg.delete()
                except Exception as e:
                    pass
                break
                return
            elif str(reaction.emoji) == EMOJI_REFRESH:
                embed = discord.Embed(title=f'SOKOBAN GAME {ctx.author.name}#{ctx.author.discriminator}', description=f'**SOKOBAN GAME** reloading level **{level}**', timestamp=datetime.utcnow(), colour=7047495)
                embed.add_field(name="LEVEL", value=f'{level}')
                embed.add_field(name="OTHER LINKS", value="{} / {} / {}".format("[Invite TipBot](http://invite.discord.bot.tips)", 
                                "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
                await msg.edit(embed=embed)
                currentLevel = loadLevel(get_level['template_str'])
                await asyncio.sleep(2)
                continue
            elif str(reaction.emoji) == EMOJI_UP:
                moveX, moveY = 0, -1
            elif str(reaction.emoji) == EMOJI_DOWN:
                moveX, moveY = 0, 1
            elif str(reaction.emoji) == EMOJI_LEFT:
                moveX, moveY = -1, 0
            elif str(reaction.emoji) == EMOJI_RIGHT:
                 moveX, moveY = 1, 0
 
            moveToX = playerX + moveX
            moveToY = playerY + moveY
            moveToSpace = currentLevel.get((moveToX, moveToY), EMPTY)

            # If the move-to space is empty or a goal, just move there:
            if moveToSpace == EMPTY or moveToSpace == GOAL:
                # Change the player's old position:
                if currentLevel[(playerX, playerY)] == FACE:
                    currentLevel[(playerX, playerY)] = EMPTY
                elif currentLevel[(playerX, playerY)] == PLAYER_ON_GOAL:
                    currentLevel[(playerX, playerY)] = GOAL

                # Set the player's new position:
                if moveToSpace == EMPTY:
                    currentLevel[(moveToX, moveToY)] = FACE
                elif moveToSpace == GOAL:
                    currentLevel[(moveToX, moveToY)] = PLAYER_ON_GOAL

            # If the move-to space is a wall, don't move at all:
            elif moveToSpace == WALL:
                pass

            # If the move-to space has a crate, see if we can push it:
            elif moveToSpace in (CRATE, CRATE_ON_GOAL):
                behindMoveToX = playerX + (moveX * 2)
                behindMoveToY = playerY + (moveY * 2)
                behindMoveToSpace = currentLevel.get((behindMoveToX, behindMoveToY), EMPTY)
                if behindMoveToSpace in (WALL, CRATE, CRATE_ON_GOAL):
                    # Can't push the crate because there's a wall or
                    # crate behind it:
                    continue
                if behindMoveToSpace in (GOAL, EMPTY):
                    # Change the player's old position:
                    if currentLevel[(playerX, playerY)] == FACE:
                        currentLevel[(playerX, playerY)] = EMPTY
                    elif currentLevel[(playerX, playerY)] == PLAYER_ON_GOAL:
                        currentLevel[(playerX, playerY)] = GOAL

                    # Set the player's new position:
                    if moveToSpace == CRATE:
                        currentLevel[(moveToX, moveToY)] = FACE
                    elif moveToSpace == CRATE_ON_GOAL:
                        currentLevel[(moveToX, moveToY)] = PLAYER_ON_GOAL

                    # Set the crate's new position:
                    if behindMoveToSpace == EMPTY:
                        currentLevel[(behindMoveToX, behindMoveToY)] = CRATE
                    elif behindMoveToSpace == GOAL:
                        currentLevel[(behindMoveToX, behindMoveToY)] = CRATE_ON_GOAL

            # Check if the player has finished the level:
            levelIsSolved = True
            for position, character in currentLevel.items():
                if character == CRATE:
                    levelIsSolved = False
                    break
            display_level = displayLevel(currentLevel)
            if levelIsSolved:
                won = True
                # game end, check win or lose
                try:
                    result = ''
                    if free_game == False:
                        won_x = 2
                        if won:
                            COIN_NAME = random.choice(GAME_COIN)
                            amount = GAME_SLOT_REWARD[COIN_NAME] * won_x
                            coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
                            real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
                            reward = await store.sql_game_add(str(level), str(ctx.message.author.id), COIN_NAME, 'WIN', real_amount, get_decimal(COIN_NAME), str(ctx.guild.id), 'SOKOBAN', int(time.time()) - time_start, 'DISCORD')
                            result = f'You won! {ctx.author.mention} got reward of **{num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}** to Tip balance!'
                        else:
                            reward = await store.sql_game_add(str(level), 'None', 'LOSE', 0, 0, str(ctx.guild.id), 'SOKOBAN', int(time.time()) - time_start, 'DISCORD')
                            result = f'You lose!'
                    else:
                        if won:
                            result = f'You won! but this is a free game without **reward**! Waiting to refresh your paid plays (24h max).'
                        else:
                            result = f'You lose!'
                        try:
                            await store.sql_game_free_add(str(level), str(ctx.message.author.id), 'WIN' if won else 'LOSE', str(ctx.guild.id), 'SOKOBAN', int(time.time()) - time_start, 'DISCORD')
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                    await ctx.send(f'{ctx.author.mention} **SOKOBAN GAME** {result}')
                    if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
                        GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)

                except Exception as e:
                    await logchanbot(traceback.format_exc())
                embed = discord.Embed(title=f'SOKOBAN GAME FINISHED {ctx.author.name}#{ctx.author.discriminator}', description=f'{display_level}', timestamp=datetime.utcnow(), colour=7047495)
                embed.add_field(name="LEVEL", value=f'{level}')
                duration = seconds_str(int(time.time()) - time_start)
                embed.add_field(name="DURATION", value=f'{duration}')
                embed.add_field(name="OTHER LINKS", value="{} / {} / {}".format("[Invite TipBot](http://invite.discord.bot.tips)", 
                                "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
                await msg.edit(embed=embed)
                game_over = True
                break
                return

        if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
            GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)
        return
    except Exception as e:
        await logchanbot(traceback.format_exc())
    if ctx.message.author.id in GAME_INTERACTIVE_PRGORESS:
        GAME_INTERACTIVE_PRGORESS.remove(ctx.message.author.id)


@bot.group(aliases=['acc'], help=bot_help_account)
async def account(ctx):
    prefix = await get_guild_prefix(ctx)
    if ctx.invoked_subcommand is None:
        await ctx.send(f'{ctx.author.mention} Invalid {prefix}account command')
        return


@account.command(name='deposit_link', aliases=['deposit'], help=bot_help_account_depositlink)
async def deposit_link(ctx, disable: str=None):
    async def create_qr_on_remote(ctx, coin):
        COIN_NAME = coin.upper()
        if not is_maintenance_coin(COIN_NAME):
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
            if wallet is None:
                userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)
                wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
            try:
                if os.path.exists(config.deposit_qr.path_deposit_qr_create + wallet['balance_wallet_address'] + ".png"):
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
                    img.save(config.deposit_qr.path_deposit_qr_create + wallet['balance_wallet_address'] + ".png")
            except Exception as e:
                await logchanbot(traceback.format_exc())
    prefix = await get_guild_prefix(ctx)
    local_address = await store.sql_deposit_getall_address_user(str(ctx.message.author.id), 'DISCORD')
    remote_address = await store.sql_deposit_getall_address_user_remote(str(ctx.message.author.id), 'DISCORD')
    diff_address = local_address
    get_depositlink = await store.sql_depositlink_user(str(ctx.message.author.id), 'DISCORD')
    if remote_address and len(remote_address) > 0:
        # https://stackoverflow.com/questions/35187165/python-how-to-subtract-2-dictionaries
        all(map( diff_address.pop, remote_address))

    if diff_address and len(diff_address) > 0:
        for key, value in diff_address.items():
            if key in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR and not is_maintenance_coin(key):
                await store.sql_depositlink_user_insert_address(str(ctx.message.author.id), key, value, 'DISCORD')
                await create_qr_on_remote(ctx, key)

    if remote_address and len(remote_address) > 0:
        diff_address = remote_address
        removing_address = {}
        for k, v in remote_address.items():
            if k not in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR or is_maintenance_coin(k):
                removing_address[k] = v
            elif k in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR and not is_maintenance_coin(k):
                # check if exist in remote, or create QR
                await create_qr_on_remote(ctx, k)

        if removing_address and len(removing_address) > 0:
            for key, value in removing_address.items():
                await store.sql_depositlink_user_delete_address(str(ctx.message.author.id), key, 'DISCORD')

    if get_depositlink:
        # if we have result, show link or disable if there id disable
        if get_depositlink['enable'] == 'YES' and disable and disable.upper() in ["DISABLE", "OFF", "0", "FALSE", "HIDE"]:
            # Turn it off
            update = await store.sql_depositlink_user_update(str(ctx.message.author.id), "enable", "NO", "DISCORD")
            if update:
                await ctx.message.add_reaction(EMOJI_OK_HAND) 
                msg = await ctx.send(f'{ctx.author.mention} Your deposit link status successfully and **not be accessible by public**.')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR) 
                await ctx.send(f'{ctx.author.mention} Internal error during update status from ENABLE to DISABLE. Try again later.')
                return
        elif get_depositlink['enable'] == 'YES' and disable and disable.upper() in ["ENABLE", "ON", "1", "TRUE", "SHOW"]:
            await ctx.message.add_reaction(EMOJI_ERROR) 
            await ctx.send(f'{ctx.author.mention} Your deposit link is already public. Nothing to do.')
            return
        elif get_depositlink['enable'] == 'NO' and disable and disable.upper() in ["ENABLE", "ON", "1", "TRUE", "SHOW"]:
            # Turn it on
            update = await store.sql_depositlink_user_update(str(ctx.message.author.id), "enable", "YES", "DISCORD")
            if update:
                await ctx.message.add_reaction(EMOJI_OK_HAND)
                msg = await ctx.send(f'{ctx.author.mention} Your deposit link status successfully and **will be accessible by public**.')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR) 
                await ctx.send(f'{ctx.author.mention} Internal error during update status from DISABLE to ENABLE. Try again later.')
                return
        elif get_depositlink['enable'] == 'NO' and disable and disable.upper() in ["DISABLE", "OFF", "0", "FALSE", "HIDE"]:
            await ctx.message.add_reaction(EMOJI_ERROR) 
            await ctx.send(f'{ctx.author.mention} Your deposit link is already private. Nothing to do.')
            return
        elif disable and (disable.upper() == "PUB" or disable.upper() == "PUBLIC"):
            # display link
            status = "public" if get_depositlink['enable'] == 'YES' else "private"
            link = config.deposit_qr.deposit_url + '/key/' + get_depositlink['link_key']
            await ctx.message.add_reaction(EMOJI_OK_HAND)
            msg = await ctx.send(f'{ctx.author.mention} Your deposit link can be accessed from (**{status}**):\n{link}')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        else:
            # display link
            status = "public" if get_depositlink['enable'] == 'YES' else "private"
            link = config.deposit_qr.deposit_url + '/key/' + get_depositlink['link_key']
            try:
                msg = await ctx.message.author.send(f'{ctx.author.mention} Your deposit link can be accessed from (**{status}**):\n{link}')
                await ctx.message.add_reaction(EMOJI_OK_HAND)
                await msg.add_reaction(EMOJI_OK_BOX)
            except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                await msg.add_reaction(EMOJI_ERROR)
                msg = await ctx.send(f'{ctx.author.mention} I failed to DM you. You can also use **{prefix}account deposit pub**, if you want it to be in public.')
                await msg.add_reaction(EMOJI_OK_BOX)
            return
    else:
        # generate a deposit link for him but need QR first
        for COIN_NAME in [coinItem.upper() for coinItem in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR]:
            await create_qr_on_remote(ctx, COIN_NAME)
        # link stuff
        random_string = str(uuid.uuid4())
        create_link = await store.sql_depositlink_user_create(str(ctx.message.author.id), '{}#{}'.format(ctx.message.author.name, ctx.message.author.discriminator), random_string, 'DISCORD')
        if create_link:
            link = config.deposit_qr.deposit_url + '/key/' + random_string
            try:
                msg = await ctx.message.author.send(f'{ctx.author.mention} Link generate successfully.\n{link}')
                await msg.add_reaction(EMOJI_OK_BOX)
                await ctx.message.add_reaction(EMOJI_OK_HAND)
            except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                await ctx.message.add_reaction(EMOJI_ERROR)
                msg = await ctx.send(f'{ctx.author.mention} I failed to DM you. You can also use **{prefix}account deposit pub**, if you want it to be in public.')
                await msg.add_reaction(EMOJI_OK_BOX)
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR) 
            await ctx.send(f'{ctx.author.mention} Internal error during link generation. Try later.')
            return


@account.command(aliases=['emojitip'], help=bot_help_account_tipemoji, hidden = True)
async def tipemoji(ctx):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return
    if ctx.invoked_subcommand is None:
        await ctx.send('Invalid `account` command passed...')
    return


@account.command(aliases=['2fa'], help=bot_help_account_twofa, hidden = True)
async def twofa(ctx):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'account twofa')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    # return message 2FA already ON if 2FA already validated
    # show QR for 2FA if not yet ON
    userinfo = await store.sql_discord_userinfo_get(str(ctx.message.author.id))
    if userinfo is None:
        # Create userinfo
        random_secret32 = pyotp.random_base32()
        create_userinfo = await store.sql_userinfo_2fa_insert(str(ctx.message.author.id), random_secret32)
        totp = pyotp.TOTP(random_secret32, interval=30)
        google_str = pyotp.TOTP(random_secret32, interval=30).provisioning_uri(f"{ctx.message.author.id}@tipbot.wrkz.work", issuer_name="Discord TipBot")
        if create_userinfo:
            # do some QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=2,
            )
            qr.add_data(google_str)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img = img.resize((256, 256))
            img.save(config.qrsettings.path + random_secret32 + ".png")
            await ctx.message.author.send("**Please use Authenticator to scan**", 
                                        file=discord.File(config.qrsettings.path + random_secret32 + ".png"))
            await ctx.message.author.send('**[NEX STEP]**\n'
                                          'From your Authenticator Program, please get code and verify by: ```.account verify XXXXXX```'
                                          f'Or use **code** below to add manually:```{random_secret32}```')
            return
        else:
            await ctx.send(f'{ctx.author.mention} Internal error during create 2FA.')
            return
    else:
        # Check if 2FA secret has or not
        # If has secret but not verified yet, show QR
        # If has both secret and verify, tell you already verify
        secret_code = None
        verified = None
        try:
            verified = userinfo['twofa_verified']
        except Exception as e:
            await logchanbot(traceback.format_exc())
        if verified and verified.upper() == "YES":
            await ctx.send(f'{ctx.author.mention} You already verified 2FA.')
            return

        try:
            secret_code = store.decrypt_string(userinfo['twofa_secret'])
        except Exception as e:
            await logchanbot(traceback.format_exc())
        if secret_code and len(secret_code) > 0:
            if os.path.exists(config.qrsettings.path + secret_code + ".png"):
                pass
            else:
                google_str = pyotp.TOTP(secret_code, interval=30).provisioning_uri(f"{ctx.message.author.id}@tipbot.wrkz.work", issuer_name="Discord TipBot")
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=2,
                )
                qr.add_data(google_str)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                img = img.resize((256, 256))
                img.save(config.qrsettings.path + secret_code + ".png")
            await ctx.message.author.send("**Please use Authenticator to scan**", 
                                          file=discord.File(config.qrsettings.path + secret_code + ".png"))
            await ctx.message.author.send('**[NEX STEP]**\n'
                                          'From your Authenticator Program, please get code and verify by: ```.account verify XXXXXX```'
                                          f'Or use **code** below to add manually:```{secret_code}```')
        else:
            # Create userinfo
            random_secret32 = pyotp.random_base32()
            update_userinfo = await store.sql_userinfo_2fa_update(str(ctx.message.author.id), random_secret32)
            totp = pyotp.TOTP(random_secret32, interval=30)
            google_str = pyotp.TOTP(random_secret32, interval=30).provisioning_uri(f"{ctx.message.author.id}@tipbot.wrkz.work", issuer_name="Discord TipBot")
            if update_userinfo:
                # do some QR code
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=2,
                )
                qr.add_data(google_str)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                img = img.resize((256, 256))
                img.save(config.qrsettings.path + random_secret32 + ".png")
                await ctx.message.author.send("**Please use Authenticator to scan**", 
                                              file=discord.File(config.qrsettings.path + random_secret32 + ".png"))
                await ctx.message.author.send('**[NEX STEP]**\n'
                                              'From your Authenticator Program, please get code and verify by: ```.account verify XXXXXX```'
                                              f'Or use **code** below to add manually:```{random_secret32}```')
                return
            else:
                await ctx.send(f'{ctx.author.mention} Internal error during create 2FA.')
                return
    return


@account.command(help=bot_help_account_verify, hidden = True)
async def verify(ctx, codes: str):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'account verify')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    if len(codes) != 6:
        await ctx.send(f'{ctx.author.mention} Incorrect code length.')
        return

    userinfo = await store.sql_discord_userinfo_get(str(ctx.message.author.id))
    if userinfo is None:
        await ctx.send(f'{ctx.author.mention} You have not created 2FA code to scan yet.\n'
                       'Please execute **account twofa** to generate 2FA scan code.')
        return
    else:
        secret_code = None
        verified = None
        try:
            verified = userinfo['twofa_verified']
        except Exception as e:
            await logchanbot(traceback.format_exc())
        if verified and verified.upper() == "YES":
            await ctx.send(f'{ctx.author.mention} You already verified 2FA. You do not need this.')
            return
        
        try:
            secret_code = store.decrypt_string(userinfo['twofa_secret'])
        except Exception as e:
            await logchanbot(traceback.format_exc())

        if secret_code and len(secret_code) > 0:
            totp = pyotp.TOTP(secret_code, interval=30)
            if codes in [totp.now(), totp.at(for_time=int(time.time()-15)), totp.at(for_time=int(time.time()+15))]:
                update_userinfo = await store.sql_userinfo_2fa_verify(str(ctx.message.author.id), 'YES')
                if update_userinfo:
                    await ctx.send(f'{ctx.author.mention} Thanks for verification with 2FA.')
                    return
                else:
                    await ctx.send(f'{ctx.author.mention} Error verification 2FA.')
                    return
            else:
                await ctx.send(f'{ctx.author.mention} Incorrect 2FA code. Please re-check.\n')
                return
        else:
            await ctx.send(f'{ctx.author.mention} You have not created 2FA code to scan yet.\n'
                           'Please execute **account twofa** to generate 2FA scan code.')
            return


@account.command(help=bot_help_account_unverify, hidden = True)
async def unverify(ctx, codes: str):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'account verify')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    if len(codes) != 6:
        await ctx.send(f'{ctx.author.mention} Incorrect code length.')
        return

    userinfo = await store.sql_discord_userinfo_get(str(ctx.message.author.id))
    if userinfo is None:
        await ctx.send(f'{ctx.author.mention} You have not created 2FA code to scan yet.\n'
                       'Nothing to **unverify**.')
        return
    else:
        secret_code = None
        verified = None
        try:
            verified = userinfo['twofa_verified']
        except Exception as e:
            await logchanbot(traceback.format_exc())
        if verified and verified.upper() == "NO":
            await ctx.send(f'{ctx.author.mention} You have not verified yet. **Unverify** stopped.')
            return
        
        try:
            secret_code = store.decrypt_string(userinfo['twofa_secret'])
        except Exception as e:
            await logchanbot(traceback.format_exc())

        if secret_code and len(secret_code) > 0:
            totp = pyotp.TOTP(secret_code, interval=30)
            if codes in [totp.now(), totp.at(for_time=int(time.time()-15)), totp.at(for_time=int(time.time()+15))]:
                update_userinfo = await store.sql_userinfo_2fa_verify(str(ctx.message.author.id), 'NO')
                if update_userinfo:
                    await ctx.send(f'{ctx.author.mention} You clear verification 2FA. You will need to add to your authentication program again later.')
                    return
                else:
                    await ctx.send(f'{ctx.author.mention} Error unverify 2FA.')
                    return
            else:
                await ctx.send(f'{ctx.author.mention} Incorrect 2FA code. Please re-check.\n')
                return
        else:
            await ctx.send(f'{ctx.author.mention} You have not created 2FA code to scan yet.\n'
                           'Nothing to **unverify**.')
            return


@account.command(hidden = True)
async def set(ctx, param: str, value: str):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return
    await ctx.send('On progress.')
    return


@bot.group(hidden = True, help=bot_help_admin)
@commands.is_owner()
async def admin(ctx):
    prefix = await get_guild_prefix(ctx)
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    if ctx.invoked_subcommand is None:
        await ctx.send(f'{ctx.author.mention} Invalid {prefix}admin command')
    return


@commands.is_owner()
@admin.command()
async def echo(ctx, *, text: str):
    await logchanbot(text)
    return


@commands.is_owner()
@admin.command()
async def eval(ctx, *, code):
    if config.discord.enable_eval != 1:
        return

    no_filter_word = True
    filterword = config.eval_code.logfilterword.split(",")
    for each in filterword:
        if each.lower() in code.lower():
            no_filter_word = False
            break

    if no_filter_word == False:
        await ctx.send(f"```There is some filtered words in your code.```")
        return

    await logchanbot('{}#{} is executing dangerous command of eval:'.format(ctx.author.name, ctx.author.discriminator))
    await logchanbot('py\n{}'.format(code))
    str_obj = io.StringIO() #Retrieves a stream of data
    try:
        with contextlib.redirect_stdout(str_obj):
            exec(code)
    except Exception as e:
        return await ctx.send(f"```{e.__class__.__name__}: {e}```")
    await ctx.author.send(f'```{str_obj.getvalue()}```')


@commands.is_owner()
@admin.command(aliases=['addbalance'])
async def credit(ctx, amount: str, coin: str, to_userid: str):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    COIN_NAME = coin.upper()
    if COIN_NAME not in (ENABLE_COIN + ENABLE_XMR + ENABLE_COIN_DOGE + ENABLE_COIN_NANO):
        await ctx.send(f'{EMOJI_ERROR} **{COIN_NAME}** is not in our list.')
        return

    # check if bot can find user
    member = bot.get_user(id=int(to_userid))
    if member is None:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} I cannot find user with userid **{to_userid}**.')
        return
    # check if user / address exist in database
    amount = amount.replace(",", "")

    coin_family = None
    wallet = None
    try:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    except Exception as e:
        await logchanbot(traceback.format_exc())
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**')
        return
    if coin_family in ["BCN", "XMR", "TRTL", "NANO", "DOGE"]:
        wallet = await store.sql_get_userwallet(to_userid, COIN_NAME)
        if wallet is None:
            userregister = await store.sql_register_user(to_userid, COIN_NAME, 'DISCORD', 0)
            wallet = await store.sql_get_userwallet(to_userid, COIN_NAME)
    else:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} not support ticker **{COIN_NAME}**')
        return

    try:
        real_amount = int(Decimal(amount) * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else Decimal(amount)
        credit_to = await store.sql_credit(str(ctx.message.author.id), to_userid, real_amount, COIN_NAME, ctx.message.content)
        if credit_to:
            msg = await ctx.send(f'{ctx.author.mention} amount **{num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}** has been credited to userid **{to_userid}**.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid credit amount.')
        return


@commands.is_owner()
@admin.command(aliases=['maintenance'])
async def maint(ctx, coin: str):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    COIN_NAME = coin.upper()
    if is_maintenance_coin(COIN_NAME):
        await ctx.send(f'{EMOJI_OK_BOX} Set **{COIN_NAME}** to maintenance **OFF**.')
        set_main = set_maintenance_coin(COIN_NAME, False)
    else:
        await ctx.send(f'{EMOJI_OK_BOX} Set **{COIN_NAME}** to maintenance **ON**.')
        set_main = set_maintenance_coin(COIN_NAME, True)
    return


@commands.is_owner()
@admin.command(aliases=['tx'])
async def txable(ctx, coin: str):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    COIN_NAME = coin.upper()
    if is_coin_txable(COIN_NAME):
        await ctx.send(f'{EMOJI_OK_BOX} Set **{COIN_NAME}** **DISABLE** TX.')
        set_main = set_coin_txable(COIN_NAME, False)
    else:
        await ctx.send(f'{EMOJI_OK_BOX} Set **{COIN_NAME}** **ENABLE** TX.')
        set_main = set_coin_txable(COIN_NAME, True)
    return


@commands.is_owner()
@admin.command(aliases=['trade'])
async def tradeable(ctx, coin: str):
    global ENABLE_TRADE_COIN
    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_TRADE_COIN:
        await ctx.send(f'{EMOJI_ERROR} **{COIN_NAME}** is not in our tradable list.')
        return

    if is_tradeable_coin(COIN_NAME):
        await ctx.send(f'{EMOJI_OK_BOX} Set **{COIN_NAME}** **DISABLE** trade.')
        set_main = set_tradeable_coin(COIN_NAME, False)
    else:
        await ctx.send(f'{EMOJI_OK_BOX} Set **{COIN_NAME}** **ENABLE** trade.')
        set_main = set_tradeable_coin(COIN_NAME, True)
    return


@commands.is_owner()
@admin.command(aliases=['tip'])
async def tipable(ctx, coin: str):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    COIN_NAME = coin.upper()
    if is_coin_tipable(COIN_NAME):
        await ctx.send(f'{EMOJI_OK_BOX} Set **{COIN_NAME}** **DISABLE** TIP.')
        set_main = set_coin_tipable(COIN_NAME, False)
    else:
        await ctx.send(f'{EMOJI_OK_BOX} Set **{COIN_NAME}** **ENABLE** TIP.')
        set_main = set_coin_tipable(COIN_NAME, True)
    return


@commands.is_owner()
@admin.command(aliases=['deposit'])
async def depositable(ctx, coin: str):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    COIN_NAME = coin.upper()
    if is_coin_depositable(COIN_NAME):
        await ctx.send(f'{EMOJI_OK_BOX} Set **{COIN_NAME}** **DISABLE** DEPOSIT.')
        set_main = set_coin_depositable(COIN_NAME, False)
    else:
        await ctx.send(f'{EMOJI_OK_BOX} Set **{COIN_NAME}** **ENABLE** DEPOSIT.')
        set_main = set_coin_depositable(COIN_NAME, True)
    return


@commands.is_owner()
@admin.command(help=bot_help_admin_save)
async def save(ctx, coin: str):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    global SAVING_ALL
    botLogChan = bot.get_channel(id=LOG_CHAN)
    COIN_NAME = coin.upper()
    if is_maintenance_coin(COIN_NAME):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} in maintenance. But I will try to **save** as per your command.')
        pass
    
    if COIN_NAME in (ENABLE_COIN+ENABLE_XMR):
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        if COIN_NAME in WALLET_API_COIN:
            duration = await walletapi.save_walletapi(COIN_NAME)
            await botLogChan.send(f'{ctx.message.author.name}#{ctx.message.author.discriminator} called `save` for {COIN_NAME}')
            if duration:
                await ctx.message.author.send(f'{get_emoji(COIN_NAME)} {COIN_NAME} `save` took {round(duration, 3)}s.')
            else:
                await ctx.message.author.send(f'{get_emoji(COIN_NAME)} {COIN_NAME} `save` calling error.')
            return
        else:
            duration = await rpc_cn_wallet_save(COIN_NAME)
            await botLogChan.send(f'{ctx.message.author.name}#{ctx.message.author.discriminator} called `save` for {COIN_NAME}')
            if duration:
                await ctx.message.author.send(f'{get_emoji(COIN_NAME)} {COIN_NAME} `save` took {round(duration, 3)}s.')
            else:
                await ctx.message.author.send(f'{get_emoji(COIN_NAME)} {COIN_NAME} `save` calling error.')
            return
    elif COIN_NAME == "ALL" or COIN_NAME == "ALLCOIN":
        if SAVING_ALL:
            await ctx.send(f'{ctx.author.mention} {EMOJI_RED_NO} another of this process is running. Wait to complete.')
            return
        start = time.time()
        duration_msg = "```"
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        await botLogChan.send(f'{ctx.message.author.name}#{ctx.message.author.discriminator} called `save all`')
        SAVING_ALL = True
        for coinItem in (ENABLE_COIN+ENABLE_XMR):
            if is_maintenance_coin(coinItem):
                duration_msg += "{} Maintenance.\n".format(coinItem)
            else:
                if coinItem in ["BCN"]:
                    duration_msg += "{} Skipped.\n".format(coinItem)
                else:
                    try:
                        if coinItem in WALLET_API_COIN:
                            one_save = await walletapi.save_walletapi(coinItem)
                        else:
                            one_save = await rpc_cn_wallet_save(coinItem)
                        duration_msg += "{} saved took {}s.\n".format(coinItem, round(one_save,3))
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                        duration_msg += "{} internal error. {}\n".format(coinItem, str(e))
        SAVING_ALL = None
        end = time.time()
        duration_msg += "Total took: {}s".format(round(end - start, 3))
        duration_msg += "```"
        await ctx.message.author.send(f'{ctx.author.mention} `save all`:\n{duration_msg}')
        return
    else:
        await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} not exists with this command.')
        return


@commands.is_owner()
@admin.command(pass_context=True, name='debug', aliases=['debugging'], help='Set debug on/off')
async def debug(ctx):
    global IS_DEBUG
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    botLogChan = bot.get_channel(id=LOG_CHAN)
    if IS_DEBUG:
        IS_DEBUG == False
        await ctx.send(f'{EMOJI_REFRESH} {ctx.author.mention} Switch debug from **ON** to **OFF**')
        return
    else:
        IS_DEBUG == True
        await ctx.send(f'{EMOJI_REFRESH} {ctx.author.mention} Switch debug from **OFF** to **ON**')
    return


@commands.is_owner()
@admin.command(pass_context=True, name='shutdown', aliases=['restart'], help=bot_help_admin_shutdown)
async def shutdown(ctx):
    global IS_RESTARTING
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    botLogChan = bot.get_channel(id=LOG_CHAN)
    if IS_RESTARTING:
        await ctx.send(f'{EMOJI_REFRESH} {ctx.author.mention} I already got this command earlier.')
        return
    IS_MAINTENANCE = 1
    IS_RESTARTING = True
    await ctx.send(f'{EMOJI_REFRESH} {ctx.author.mention} .. I will restarting in 30s.. back soon.')
    await botLogChan.send(f'{EMOJI_REFRESH} {ctx.message.author.name}#{ctx.message.author.discriminator} called `restart`. I am restarting in 30s and will back soon hopefully.')
    await asyncio.sleep(30)
    await bot.logout()


@commands.is_owner()
@admin.command()
async def addhelp(ctx, section: str, what: str, *, desc: str):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    if len(desc) < 16:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} descriotion too short.')
        return

    check_exist = await store.sql_help_doc_get(section, what)
    if check_exist:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} **{what.upper()}** already existed in **{section.upper()}**')
        return
    else:
        # not existed, added. Split desc by ;
        desc_items = desc.split(";")
        detail_1 = ''
        detail_2 = ''
        if len(desc_items) >= 2:
            detail_1 = desc_items[0]
            detail_2 = desc_items[1]
        else:
            detail_1 = desc_items[0]
            detail_2 = ''
            
        add_help = await store.sql_help_doc_add(section, what, detail_1, '{}#{}'.format(ctx.message.author.name, ctx.message.author.discriminator), str(ctx.message.author.id), detail_2)
        if add_help:
            await ctx.message.add_reaction(EMOJI_OK_HAND) 
            await ctx.send(f'{ctx.author.mention} added **{what.upper()}** from **{section.upper()}**')
        else:
            await ctx.message.add_reaction(EMOJI_ERROR) 
            await ctx.send(f'{ctx.author.mention} internal error to add **{what.upper()}** to **{section.upper()}**')
        return


@commands.is_owner()
@admin.command()
async def delhelp(ctx, section: str, what: str):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    check_exist = await store.sql_help_doc_get(section, what)
    if check_exist is None:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} **{what.upper()}** does not exist in **{section.upper()}**')
        return
    else:
        # OK, exist, delete
        del_help = await store.sql_help_doc_del(section, what)
        if del_help:
            await ctx.message.add_reaction(EMOJI_OK_HAND) 
            await ctx.send(f'{ctx.author.mention} deleted **{what.upper()}** from **{section.upper()}**')
        else:
            await ctx.message.add_reaction(EMOJI_ERROR) 
            await ctx.send(f'{ctx.author.mention} internal error to delete **{what.upper()}** from **{section.upper()}**')
        return


@commands.is_owner()
@admin.command()
async def update_balance(ctx, coin: str):
    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_ERC:
        await ctx.author.send(f'{ctx.author.mention} COIN **{COIN_NAME}** NOT SUPPORTED.')
        return

    if COIN_NAME in ENABLE_COIN_ERC:
        start = time.time()
        check_min = "N/A"
        try:
            await store.erc_check_pending_move_deposit(COIN_NAME, 'ALL')
            check_min = await store.erc_check_minimum_deposit(COIN_NAME)
        except Exception as e:
            await logchanbot(traceback.format_exc())
        end = time.time()
        await ctx.author.send(f'{ctx.author.mention} Done update balance: ' + COIN_NAME+ ' duration (s): '+str(end - start) + f"```\n{check_min}\n```")
    else:
        start = time.time()
        try:
            await store.sql_update_balances(COIN_NAME)
        except Exception as e:
            await logchanbot(traceback.format_exc())
        end = time.time()
        await ctx.author.send(f'{ctx.author.mention} Done update balance: ' + COIN_NAME+ ' duration (s): '+str(end - start))
    return


@commands.is_owner()
@admin.command(help=bot_help_admin_baluser)
async def baluser(ctx, user_id: str, create_wallet: str = None):
    global IS_DEBUG
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    create_acc = None
    # check if there is that user
    try:
        user_id = int(user_id)
        member = bot.get_user(id=user_id)
        if member is None:
            await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} I cannot find that user.')
            return
    except ValueError:
        await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Invalid user.')
        return

    # for verification | future restoration of lost account
    table_data = [
        ['TICKER', 'Available']
    ]
    if create_wallet:
        if create_wallet.upper() == "ON":
            create_acc = True
        else:
            COIN_NAME = create_wallet.upper()
            if COIN_NAME in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC:
                wallet = await store.sql_get_userwallet(str(user_id), COIN_NAME)
                try:
                    xfer_in = 0
                    if COIN_NAME not in ENABLE_COIN_ERC:
                        xfer_in = await store.sql_user_balance_get_xfer_in(str(user_id), COIN_NAME)
                    userdata_balance = await store.sql_user_balance(str(user_id), COIN_NAME)
                    msg_balance = f"Balance User ID **{str(user_id)}** for: " + COIN_NAME + "\n"
                    msg_balance += "```"
                    msg_balance += "xfer_in: " + str(xfer_in) + "\n"
                    msg_balance += "userdata_balance:\n" + str(userdata_balance)
                    msg_balance += "```"
                    await ctx.author.send(msg_balance)
                except Exception as e:
                    print(traceback.format_exc())
                    await logchanbot(traceback.format_exc())
            else:
                await ctx.author.send(f'{EMOJI_ERROR} {ctx.author.mention} Unknown COIN_NAME **{COIN_NAME}**.')
            return
    else:
        for COIN_NAME in [coinItem.upper() for coinItem in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC]:
            if not is_maintenance_coin(COIN_NAME):
                wallet = await store.sql_get_userwallet(str(user_id), COIN_NAME)
                if wallet is None and create_acc:
                    if COIN_NAME in ENABLE_COIN_ERC:
                        w = await create_address_eth()
                        userregister = await store.sql_register_user(str(user_id), COIN_NAME, 'DISCORD', 0, w)
                    else:
                        userregister = await store.sql_register_user(str(user_id), COIN_NAME, 'DISCORD', 0)
                    wallet = await store.sql_get_userwallet(str(user_id), COIN_NAME)
                if wallet:
                    try:
                        xfer_in = 0
                        if COIN_NAME not in ENABLE_COIN_ERC:
                            xfer_in = await store.sql_user_balance_get_xfer_in(str(user_id), COIN_NAME)
                    except Exception as e:
                        print(traceback.format_exc())
                        await logchanbot(traceback.format_exc())

                    userdata_balance = await store.sql_user_balance(str(user_id), COIN_NAME)
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
                            msg_negative = 'Negative balance detected:\nUser: '+str(user_id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                            await logchanbot(msg_negative)
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                    if COIN_NAME in ENABLE_COIN_DOGE+ENABLE_COIN+ENABLE_XMR+ENABLE_COIN_ERC:
                        balance_actual = num_format_coin(actual_balance, COIN_NAME)
                    elif COIN_NAME in ENABLE_COIN_NANO:
                        actual = round(actual_balance / get_decimal(COIN_NAME), 6) * get_decimal(COIN_NAME)
                        balance_actual = num_format_coin(actual, COIN_NAME)
                    if wallet['user_wallet_address'] is None:
                        COIN_NAME += '*'
                    table_data.append([COIN_NAME, balance_actual])
                else:
                    table_data.append([COIN_NAME, "N/A"])
            else:
                table_data.append([COIN_NAME, "***"])
        table = AsciiTable(table_data)
        table.padding_left = 0
        table.padding_right = 0
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        await ctx.message.author.send(f'**[ BALANCE LIST OF {user_id} ]**\n'
                                      f'```{table.table}```\n')
    return


@commands.is_owner()
@admin.command(help=bot_help_admin_lockuser)
async def lockuser(ctx, user_id: str, *, reason: str):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    get_discord_userinfo = await store.sql_discord_userinfo_get(user_id)
    if get_discord_userinfo is None:
        await store.sql_userinfo_locked(user_id, 'YES', reason, str(ctx.message.author.id))
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        await ctx.message.author.send(f'{user_id} is locked.')
        return
    else:
        if get_discord_userinfo['locked'].upper() == "YES":
            await ctx.message.author.send(f'{user_id} was already locked.')
        else:
            await store.sql_userinfo_locked(user_id, 'YES', reason, str(ctx.message.author.id))
            await ctx.message.add_reaction(EMOJI_OK_HAND)
            await ctx.message.author.send(f'Turn {user_id} to locked.')
        return


@commands.is_owner()
@admin.command(help=bot_help_admin_unlockuser)
async def unlockuser(ctx, user_id: str):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    get_discord_userinfo = await store.sql_discord_userinfo_get(user_id)
    if get_discord_userinfo:
        if get_discord_userinfo['locked'].upper() == "NO":
            await ctx.message.author.send(f'**{user_id}** was already unlocked. Nothing to do.')
        else:
            await store.sql_change_userinfo_single(user_id, 'locked', 'NO')
            await ctx.message.author.send(f'Unlocked {user_id} done.')
        return      
    else:
        await ctx.message.author.send(f'{user_id} not stored in **discord userinfo** yet. Nothing to unlocked.')
        return


@commands.is_owner()
@admin.command()
async def roachadd(ctx, main_id: str, user_id: str):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    if main_id == user_id:
        await ctx.message.author.send(f'{main_id} and {user_id} can not be the same.')
        await ctx.message.add_reaction(EMOJI_ERROR)
        return
    else:
        main_member = bot.get_user(id=int(main_id))
        roach_user = bot.get_user(id=int(user_id))
        if main_member and roach_user:
            add_roach = await store.sql_roach_add(main_id, user_id, roach_user.name+"#"+roach_user.discriminator, main_member.name+"#"+main_member.discriminator)
            if add_roach:
                await ctx.message.author.send(f'Succesfully add new roach **{user_id}** / {roach_user.name}#{roach_user.discriminator} to Main ID: **{main_id}** / {main_member.name}#{main_member.discriminator}.')
                await ctx.message.add_reaction(EMOJI_OK_BOX)
            else:
                await ctx.message.author.send(f'{main_id} and {user_id} added fail or already existed.')
                await ctx.message.add_reaction(EMOJI_ERROR)
            return   
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.message.author.send(f'{main_id} and/or {user_id} not found.')
            return


@commands.is_owner()
@admin.command(help=bot_help_admin_cleartx)
async def cleartx(ctx):
    global TX_IN_PROCESS
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    if len(TX_IN_PROCESS) == 0 and len(GAME_INTERACTIVE_PRGORESS) == 0 and len(GAME_SLOT_IN_PRGORESS) == 0 \
and len(GAME_DICE_IN_PRGORESS) == 0 and len(GAME_MAZE_IN_PROCESS) == 0 and len(CHART_TRADEVIEW_IN_PROCESS) == 0:
        await ctx.message.author.send(f'{ctx.author.mention} Nothing in pending to clear.')
    else:
        try:
            pending_msg = []
            count = 0
            if len(TX_IN_PROCESS) > 0:
                string_ints = [str(num) for num in TX_IN_PROCESS]
                list_pending += ', '.join(string_ints)
                pending_msg.append(f"TX_IN_PROCESS: {list_pending}")
                count += len(TX_IN_PROCESS)
            if len(GAME_INTERACTIVE_PRGORESS) > 0:
                string_ints = [str(num) for num in GAME_INTERACTIVE_PRGORESS]
                list_pending += ', '.join(string_ints)
                pending_msg.append(f"GAME_INTERACTIVE_PRGORESS: {list_pending}")
                count += len(GAME_INTERACTIVE_PRGORESS)
            if len(GAME_SLOT_IN_PRGORESS) > 0:
                string_ints = [str(num) for num in GAME_SLOT_IN_PRGORESS]
                list_pending += ', '.join(string_ints)
                pending_msg.append(f"GAME_SLOT_IN_PRGORESS: {list_pending}")
                count += len(GAME_SLOT_IN_PRGORESS)
            if len(GAME_DICE_IN_PRGORESS) > 0:
                string_ints = [str(num) for num in GAME_DICE_IN_PRGORESS]
                list_pending += ', '.join(string_ints)
                pending_msg.append(f"GAME_DICE_IN_PRGORESS: {list_pending}")
                count += len(GAME_DICE_IN_PRGORESS)
            if len(GAME_MAZE_IN_PROCESS) > 0:
                string_ints = [str(num) for num in GAME_MAZE_IN_PROCESS]
                list_pending += ', '.join(string_ints)
                pending_msg.append(f"GAME_MAZE_IN_PROCESS: {list_pending}")
                count += len(GAME_MAZE_IN_PROCESS)
            if len(CHART_TRADEVIEW_IN_PROCESS) > 0:
                string_ints = [str(num) for num in CHART_TRADEVIEW_IN_PROCESS]
                list_pending += ', '.join(string_ints)
                pending_msg.append(f"CHART_TRADEVIEW_IN_PROCESS: {list_pending}")
                count += len(CHART_TRADEVIEW_IN_PROCESS)
            pending_all = '\n'.join(pending_msg)
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.message.author.send(f'{ctx.author.mention} Clearing:\n```{pending_all}```\nTotal: {str(count)}')
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        TX_IN_PROCESS = [] 
        GAME_INTERACTIVE_PRGORESS = []
        GAME_SLOT_IN_PRGORESS = []
        GAME_DICE_IN_PRGORESS = []
        GAME_MAZE_IN_PROCESS = []
    return


@commands.is_owner()
@admin.command(help='Check pending things')
async def pending(ctx):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return
    ts = datetime.utcnow()
    embed = discord.Embed(title='Pending Actions', timestamp=ts)
    embed.add_field(name="TX_IN_PROCESS", value=str(len(TX_IN_PROCESS)), inline=True)
    embed.add_field(name="GAME_INTERACTIVE", value=str(len(GAME_INTERACTIVE_PRGORESS)), inline=True)
    embed.add_field(name="GAME_SLOT", value=str(len(GAME_SLOT_IN_PRGORESS)), inline=True)
    embed.add_field(name="GAME_DICE", value=str(len(GAME_DICE_IN_PRGORESS)), inline=True)
    embed.add_field(name="GAME_MAZE", value=str(len(GAME_MAZE_IN_PROCESS)), inline=True)
    embed.set_footer(text=f"Pending requested by {ctx.message.author.name}#{ctx.message.author.discriminator}")
    try:
        msg = await ctx.send(embed=embed)
        await msg.add_reaction(EMOJI_OK_BOX)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return


@commands.is_owner()
@admin.command(aliases=['check_coin'])
async def checkcoin(ctx, coin: str):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    # Check of wallet in SQL consistence to wallet-service
    botLogChan = bot.get_channel(id=LOG_CHAN)
    COIN_NAME = coin.upper()
    if COIN_NAME not in (ENABLE_COIN + ENABLE_XMR + ENABLE_COIN_DOGE + ENABLE_COIN_NANO + ENABLE_COIN_ERC):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.message.author.send(f'{COIN_NAME} is not in TipBot.')
        return
    if is_maintenance_coin(COIN_NAME):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family in ["TRTL", "BCN"]:
        in_existing = 0
        get_addresses = await store.get_all_user_balance_address(COIN_NAME)
        if len(get_addresses) > 0:
            list_in_wallet_service = await get_all_addresses(COIN_NAME)
            for address in get_addresses:
                if address['address'] not in list_in_wallet_service:
                    in_existing += 1
                    # print(address['address']+' scanHeight: '+str(address['scanHeight'])+' is NOT IN Wallet-Service')
            await ctx.send(f'**{COIN_NAME}** Sub-wallets:'
                           '```'
                           f'In MySQL database: {len(get_addresses)}\n'
                           f'In Wallet-Service: {len(list_in_wallet_service)}'
                           '```'
                           f'There is {str(in_existing)} subwallet(s) in MySQL which is not in Wallet-Service.')
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.message.author.send(f'{COIN_NAME} return no address.')
            return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.message.author.send(f'{COIN_NAME} not supporting with this function.')
        return


@bot.group(name='guild')
@commands.has_permissions(manage_channels=True)
async def guild(ctx):
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be DM.')
        return

    prefix = await get_guild_prefix(ctx)
    if ctx.invoked_subcommand is None:
        await ctx.send(f'{ctx.author.mention} Invalid {prefix}guild command.\n Please use {prefix}help guild')
        return


@guild.command(name='tipmsg', aliases=['tipmessage'])
@commands.has_permissions(manage_channels=True)
async def tipmsg(ctx, *, tipmessage):
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be DM.')
        return

    if 1000 <= len(tipmessage) <= 5:
        await ctx.send(f'{ctx.author.mention} Tip message is too short or too long.')
        return
    else:
        changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'tip_message', tipmessage)
        changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'tip_message_by', "{}#{}".format(ctx.author.name, ctx.author.discriminator))
        botLogChan = bot.get_channel(id=LOG_CHAN)
        try:
            await ctx.send(f'{ctx.author.mention} Tip message for this guild is updated.')
        except Exception as e:
            await logchanbot(traceback.format_exc())
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} changed tipmessage in {str(ctx.guild.id)}/{ctx.guild.name}.')
        return


@guild.command(name='botchan', aliases=['botchannel', 'bot_chan'])
@commands.has_permissions(manage_channels=True)
async def botchan(ctx):
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be DM.')
        return

    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    if serverinfo['botchan']:
        try: 
            botLogChan = bot.get_channel(id=LOG_CHAN)
            if ctx.channel.id == int(serverinfo['botchan']):
                await ctx.send(f'{EMOJI_RED_NO} {ctx.channel.mention} is already the bot channel here!')
                return
            else:
                # change channel info
                changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'botchan', str(ctx.channel.id))
                await ctx.send(f'Bot channel has set to {ctx.channel.mention}.')
                await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} change bot channel {ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}.')
                return
        except ValueError:
            return
    else:
        # change channel info
        changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'botchan', str(ctx.channel.id))
        await ctx.send(f'Bot channel has set to {ctx.channel.mention}.')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} changed bot channel {ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}.')
        return


@guild.command(name='gamechan', aliases=['gamechannel', 'game_chan'])
@commands.has_permissions(manage_channels=True)
async def gamechan(ctx, game: str=None):
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be DM.')
        return

    game_list = config.game.game_list.split(",")
    if game is None:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.channel.mention} please mention a game name to set game channel for it. Game list: {config.game.game_list}.')
        return
    else:
        game = game.lower()
        if game not in game_list:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.channel.mention} please mention a game name within this list: {config.game.game_list}.')
            return
        else:
            botLogChan = bot.get_channel(id=LOG_CHAN)
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            index_game = "game_" + game + "_channel"
            if serverinfo[index_game]:
                try: 
                    if ctx.channel.id == int(serverinfo[index_game]):
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.channel.mention} is already for game **{game}** channel here!')
                        return
                    else:
                        # change channel info
                        changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), index_game, str(ctx.channel.id))
                        await ctx.send(f'{ctx.channel.mention} Game **{game}** channel has set to {ctx.channel.mention}.')
                        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} changed game **{game}** in channel {ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}.')
                        return
                except ValueError:
                    return
            else:
                # change channel info
                changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), index_game, str(ctx.channel.id))
                await ctx.send(f'{ctx.channel.mention} Game **{game}** channel has set to {ctx.channel.mention}.')
                await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} set game **{game}** channel in {ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}.')
                return


@guild.command(name='prefix')
@commands.has_permissions(manage_channels=True)
async def prefix(ctx, prefix_char: str=None):
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be DM.')
        return

    if prefix_char not in [".", "?", "*", "!", "$", "~"]:
        await ctx.send(f'{ctx.author.mention} Invalid prefix **{prefix_char}**')
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} wanted to changed prefix in {ctx.guild.name} / {ctx.guild.id} to `{prefix_char.lower()}`')
        return
    else:
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        server_prefix = serverinfo['server_prefix']
        if server_prefix == prefix_char:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} That\'s the default prefix. Nothing changed.')
            return
        else:
            changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'prefix', prefix_char.lower())
            await ctx.send(f'{ctx.author.mention} Prefix changed from `{server_prefix}` to `{prefix_char.lower()}`.')
            await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} changed prefix in {ctx.guild.name} / {ctx.guild.id} to `{prefix_char.lower()}`')
            return

                    
@commands.is_owner()
@admin.command(hidden = True)
async def dumpinfo(ctx, coin: str):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_COIN:
        await ctx.message.author.send('COIN **{}** NOT SUPPORTED.'.format(COIN_NAME))
        return

    start = time.time()
    try:
        await store.sql_update_balances(COIN_NAME)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    end = time.time()
    await ctx.message.author.send('Done update balance: '+ COIN_NAME+ ' duration (s): '+str(end - start))

    # get all balance
    random_filename = str(uuid.uuid4()) + "_" + COIN_NAME + ".csv"
    write_csv_coin = await store.sql_get_alluser_balance(COIN_NAME, random_filename)
    if os.path.exists(random_filename) and write_csv_coin:
        await ctx.message.author.send(f"Dump created for: **{COIN_NAME}**",
                                      file=discord.File(random_filename))
        os.remove(random_filename)
    else:
        await ctx.message.author.send('Internal Error for dump info - FILE NOT FOUND: **{}**'.format(COIN_NAME))
        return

    # Saving
    await ctx.message.author.send('*Calling wallet saving for*: **{}**'.format(COIN_NAME))
    duration = None
    if COIN_NAME in ENABLE_COIN:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        if COIN_NAME in WALLET_API_COIN:
            duration = await walletapi.save_walletapi(COIN_NAME)
        else:
            duration = await rpc_cn_wallet_save(COIN_NAME)

        if duration:
            await ctx.message.author.send(f'{get_emoji(COIN_NAME)} {COIN_NAME} `save` took {round(duration, 3)}s.')
        else:
            await ctx.message.author.send(f'{get_emoji(COIN_NAME)} {COIN_NAME} `save` calling error.')
    return


@commands.is_owner()
@admin.command(hidden = True)
async def test(ctx):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return

    # where i always test something. Nothing to do here.
    test_str = "WrkzRNDQDwFCBynKPc459v3LDa1gEGzG3j962tMUBko1fw9xgdaS9mNiGMgA9s1q7hS1Z8SGRVWzcGc8Sh8xsvfZ6u2wJEtoZB"
    encrypted = store.encrypt_string(test_str)
    decrypted = store.decrypt_string(encrypted)
    await ctx.send('```Original: {}\nEncrypted: {}\nDecrypted: {}```'.format(test_str, encrypted, decrypted))
    return


@bot.command(hidden = True, pass_context=True, name='prefix')
async def prefix(ctx):
    prefix = await get_guild_prefix(ctx)
    try:
        msg = await ctx.send(f'{EMOJI_INFORMATION} {ctx.author.mention}, the prefix here is **{prefix}**')
        await msg.add_reaction(EMOJI_OK_BOX)
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        await msg.add_reaction(EMOJI_ERROR)
        await logchanbot(traceback.format_exc())
    return


@bot.command(pass_context=True, name='userinfo', aliases=['user'], help=bot_help_userinfo)
async def userinfo(ctx, member: discord.Member = None):
    global TRTL_DISCORD
    if isinstance(ctx.channel, discord.DMChannel) == True:
        await ctx.send(f'{ctx.author.mention} This command can not be in Direct Message.')
        return
    if member is None:
        member = ctx.message.author
    try:
        embed = discord.Embed(title="{}'s info".format(member.name), description="Here's what I could find.", color=0x00ff00)
        embed.add_field(name="Name", value="{}#{}".format(member.name, member.discriminator), inline=True)
        embed.add_field(name="Display Name", value=member.display_name, inline=True)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Status", value=member.status, inline=True)
        embed.add_field(name="Highest role", value=member.top_role)
        if ctx.guild.id != TRTL_DISCORD:
            user_claims = await store.sql_faucet_count_user(str(ctx.message.author.id))
            if user_claims and user_claims > 0:
                take_level = get_roach_level(user_claims)
                embed.add_field(name="Faucet Taking Level", value=take_level)
        embed.add_field(name="Joined", value=str(member.joined_at.strftime("%d-%b-%Y") + ': ' + timeago.format(member.joined_at, datetime.utcnow())))
        embed.add_field(name="Created", value=str(member.created_at.strftime("%d-%b-%Y") + ': ' + timeago.format(member.created_at, datetime.utcnow())))
        embed.set_thumbnail(url=member.avatar_url)
        await ctx.send(embed=embed)
    except:
        error = discord.Embed(title=":exclamation: Error", description=" :warning: You need to mention the user you want this info for!", color=0xe51e1e)
        await ctx.send(embed=error)


@bot.command(pass_context=True, name='tradeview', aliases=['tv'], help='View market trade view')
async def tradeview(ctx, market: str, pair: str):
    global TRTL_DISCORD, CHART_TRADEVIEW_IN_PROCESS
    # TRTL discord
    if isinstance(ctx.message.channel, discord.DMChannel) == False and ctx.guild and ctx.guild.id == TRTL_DISCORD:
        return

    # Check if tx in progress
    if ctx.message.author.id in CHART_TRADEVIEW_IN_PROCESS:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another chart in progress.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    try:
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if isinstance(ctx.message.channel, discord.DMChannel) == False and serverinfo \
        and 'enable_market' in serverinfo and serverinfo['enable_market'] == "NO":
            prefix = serverinfo['prefix']
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Market Command is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING MARKET`')
            await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}cg** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
            return
    except Exception as e:
        if isinstance(ctx.message.channel, discord.DMChannel) == False:
            return
        pass
    
    market = market.upper()
    if market == "ALT": market = "ALTILLY"
    if market not in config.chart.market_enable.split(","):
        msg = await ctx.send(f'{ctx.author.mention} market **{market}** is not available right now. Available **{config.chart.market_enable}**')
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    
    # Check if ticker in DB
    separator = "."
    if '/' in pair:
        separator = "/"
    elif '-' in pair:
        separator = "-"
    elif ',' in pair:
        separator = ","
    
    pairs = pair.split(separator)
    if len(pairs) != 2:
        msg = await ctx.send(f'{ctx.author.mention} Invalid given separator between coin pairs.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    else:
        get_market_setting = await store.sql_get_tradeview_market_setting(market)
        get_link_pair = await store.sql_get_tradeview_available(market, pairs[0], pairs[1])
        if get_market_setting and get_link_pair:
            async with ctx.typing():
                try:
                    if ctx.message.author.id not in CHART_TRADEVIEW_IN_PROCESS:
                        CHART_TRADEVIEW_IN_PROCESS.append(ctx.message.author.id )
                    run_snap = functools.partial(chart_pair_snapshot.get_snapshot_market, market, \
get_link_pair['pair_url_snap'], get_market_setting['filter_by'], get_market_setting['select_area_id_name'], \
get_market_setting['visible_list'], pairs[0]+pairs[1])
                    fetch_image = await bot.loop.run_in_executor(None, run_snap)
                    if fetch_image:
                        try:
                            msg = await ctx.send(f'{config.chart.static_chart_image_link + fetch_image}')
                            await ctx.message.add_reaction(EMOJI_OK_HAND)
                            await msg.add_reaction(EMOJI_OK_BOX)
                            insert_fetch = await store.sql_get_tradeview_insert_fetch(market, pair.upper(), get_link_pair['pair_url_snap'], str(ctx.author.id), fetch_image)
                        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                            if ctx.message.author.id in CHART_TRADEVIEW_IN_PROCESS:
                                CHART_TRADEVIEW_IN_PROCESS.remove(ctx.message.author.id)
                            await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                    else:
                        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Internal error during fetch image.')
                        await msg.add_reaction(EMOJI_OK_BOX)
                        if ctx.message.author.id in CHART_TRADEVIEW_IN_PROCESS:
                            CHART_TRADEVIEW_IN_PROCESS.remove(ctx.message.author.id)
                except Exception as e:
                    await logchanbot(traceback.format_exc())
                if ctx.message.author.id in CHART_TRADEVIEW_IN_PROCESS:
                    CHART_TRADEVIEW_IN_PROCESS.remove(ctx.message.author.id)
        else:
            msg = await ctx.send(f'{ctx.author.mention} can not find pair **{pair}** in market **{market}** or it is not enabled.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return


@bot.command(pass_context=True, name='cg', aliases=['coingecko'], help='Get coin information from CoinGecko')
async def cg(ctx, ticker: str):
    global TRTL_DISCORD
    # TRTL discord
    if isinstance(ctx.message.channel, discord.DMChannel) == False and ctx.guild and ctx.guild.id == TRTL_DISCORD:
        return

    try:
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if isinstance(ctx.message.channel, discord.DMChannel) == False and serverinfo \
        and 'enable_market' in serverinfo and serverinfo['enable_market'] == "NO":
            prefix = serverinfo['prefix']
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Market Command is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING MARKET`')
            await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}cg** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
            return
    except Exception as e:
        if isinstance(ctx.message.channel, discord.DMChannel) == False:
            return
        pass

    get_cg = await store.get_coingecko_coin(ticker)
    def format_amount(amount: float):
        if amount > 1:
            return '{:,.2f}'.format(amount)
        elif amount > 0.01:
            return '{:,.4f}'.format(amount)
        elif amount > 0.0001:
            return '{:,.6f}'.format(amount)
        elif amount > 0.000001:
            return '{:,.8f}'.format(amount)
        else:
            return '{:,.10f}'.format(amount)
    if get_cg and len(get_cg) > 0:
        rank = ''
        if 'name' in get_cg and 'mcap_ranking' in get_cg and get_cg['mcap_ranking']:
            rank = '{} Rank #{}'.format(get_cg['name'], get_cg['mcap_ranking'])
        embed = discord.Embed(title='{} at CoinGecko'.format(ticker.upper()), description='{}'.format(rank), timestamp=datetime.utcnow(), colour=7047495)
        if isinstance(get_cg['marketcap_USD'], float) and get_cg['marketcap_USD'] > 0:
            embed.add_field(name="MarketCap", value='{}USD'.format(format_amount(get_cg['marketcap_USD'])), inline=True)
        embed.add_field(name="High 24h", value='{}USD'.format(format_amount(get_cg['high24h_USD'])), inline=True)
        embed.add_field(name="Low 24h", value='{}USD'.format(format_amount(get_cg['low24h_USD'])), inline=True)
        embed.add_field(name="Market Price", value='{}USD'.format(format_amount(get_cg['marketprice_USD'])), inline=True)
        embed.add_field(name="Change (24h)", value='{:,.2f}%{}'.format(get_cg['price_change24h_percent'], EMOJI_CHART_DOWN if float(get_cg['price_change24h_percent']) < 0 else EMOJI_CHART_UP), inline=True)
        embed.add_field(name="Change (7d)", value='{:,.2f}%{}'.format(get_cg['price_change7d_percent'], EMOJI_CHART_DOWN if float(get_cg['price_change7d_percent']) < 0 else EMOJI_CHART_UP), inline=True)
        embed.add_field(name="Change (14d)", value='{:,.2f}%{}'.format(get_cg['price_change14d_percent'], EMOJI_CHART_DOWN if float(get_cg['price_change14d_percent']) < 0 else EMOJI_CHART_UP), inline=True)
        embed.add_field(name="Change (30d)", value='{:,.2f}%{}'.format(get_cg['price_change30d_percent'], EMOJI_CHART_DOWN if float(get_cg['price_change30d_percent']) < 0 else EMOJI_CHART_UP), inline=True)
        embed.add_field(name="OTHER LINKS", value="{} / {} / {}".format("[Invite TipBot](http://invite.discord.bot.tips)", "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
        
        # Add image
        name_png = 'tmp_' + str(uuid.uuid4())
        random_file = config.cg_cmc_setting.static_file + name_png + '.png'
        url_png = config.cg_cmc_setting.url_file + name_png + '.png'
        graph_price = await store.cg_plot_price(ticker, 14, random_file)
        if graph_price:
            embed.set_image(url = url_png)
        try:
            embed.set_footer(text=f"Fetched from CoinGecko requested by {ctx.message.author.name}#{ctx.message.author.discriminator}")
        except Exception as e:
            await logchanbot(traceback.format_exc())
        try:
            msg = await ctx.send(embed=embed)
            await ctx.message.add_reaction(EMOJI_OK_HAND)
            await msg.add_reaction(EMOJI_OK_BOX)
        except (discord.Forbidden, discord.errors.Forbidden) as e:
            message_price = '{} at CoinGecko\n'.format(ticker.upper())
            if 'name' in get_cg and 'mcap_ranking' in get_cg and get_cg['mcap_ranking']:
                message_price += '{} Rank #{}'.format(get_cg['name'], get_cg['mcap_ranking'])
            if isinstance(get_cg['marketcap_USD'], float) and get_cg['marketcap_USD'] > 0:
                message_price += 'MarketCap:    {}USD\n'.format(format_amount(get_cg['marketcap_USD']))
            message_price += 'High 24h:     {}USD\n'.format(format_amount(get_cg['high24h_USD']))
            message_price += 'Low 24h:      {}USD\n'.format(format_amount(get_cg['low24h_USD']))
            message_price += 'Market Price: {}USD\n'.format(format_amount(get_cg['marketprice_USD']))
            message_price += 'Change 24h/7d/14d/30d:  {}%/{}%/{}%/{}%\n'.format(format_amount(get_cg['price_change24h_percent'], get_cg['price_change7d_percent'], get_cg['price_change14d_percent'], get_cg['price_change30d_percent']))
            try:
                fetch = datetime.utcfromtimestamp(int(get_cg['fetch_date'])).strftime("%Y-%m-%d %H:%M:%S")
                ago = str(timeago.format(fetch, datetime.utcnow()))
                message_price += f"Fetched from CoinGecko {ago} requested by {ctx.message.author.name}#{ctx.message.author.discriminator}"
            except Exception as e:
                await logchanbot(traceback.format_exc())
            try:
                msg = await ctx.send(f'{ctx.author.mention}```{message_price}```')
                await ctx.message.add_reaction(EMOJI_OK_HAND)
                await msg.add_reaction(EMOJI_OK_BOX)
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await logchanbot(traceback.format_exc())
                return
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} I can not find the ticker **{ticker}** in CoinGecko.')
    return


@bot.command(pass_context=True, name='pricelist', aliases=['pricetable', 'pt', 'pl'], help='Get price list')
async def pricelist(ctx, *, coin_list):
    prefix = await get_guild_prefix(ctx)
    coin_list = ' '.join(coin_list.split())

    # disable game for TRTL discord
    if isinstance(ctx.message.channel, discord.DMChannel) == False and ctx.guild and ctx.guild.id == TRTL_DISCORD:
        return

    try:
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if isinstance(ctx.message.channel, discord.DMChannel) == False and serverinfo \
        and 'enable_market' in serverinfo and serverinfo['enable_market'] == "NO":
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Market command is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING MARKET`')
            await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}price** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
            return
    except Exception as e:
        if isinstance(ctx.message.channel, discord.DMChannel) == False:
            return
        pass

    def format_amount(amount: float):
        if amount > 1:
            return '{:,.2f}'.format(amount)
        elif amount > 0.01:
            return '{:,.4f}'.format(amount)
        elif amount > 0.0001:
            return '{:,.6f}'.format(amount)
        else:
            return '{:,.8f}'.format(amount)

    has_none = True
    coin_list_call = coin_list.split(" ")
    if 10 >= len(coin_list_call) >= 1:
        table_data = [
            ["COIN", "CMC [USD]", "CG [USD]", "Remark"]
            ]
        for each_coin in coin_list_call:
            ticker = each_coin.upper()
            market_price = await store.market_value_in_usd(1, ticker)
            if market_price:
                has_none = False
                cmc_p = "N/A"
                cg_p = "N/A"
                cmc_ago = "N/A"
                cg_ago = "N/A"
                if 'cmc_price' in market_price and market_price['cmc_price'] > 0.00000001:
                    cmc_p = format_amount(market_price['cmc_price'])
                    update = datetime.strptime(market_price['cmc_update'].split(".")[0], '%Y-%m-%dT%H:%M:%S')
                    cmc_ago = timeago.format(update, datetime.utcnow())
                if 'cg_price' in market_price and market_price['cg_price'] > 0.00000001:
                    cg_p = format_amount(market_price['cg_price'])
                    update = datetime.strptime(market_price['cg_update'].split(".")[0], '%Y-%m-%dT%H:%M:%S')
                    cg_ago = timeago.format(update, datetime.utcnow())
                table_data.append([ticker, cmc_p, cg_p, ""])
        table = AsciiTable(table_data)
        table.padding_left = 0
        table.padding_right = 0
        try:
            embed = discord.Embed(title='Price List Command', description='Price Information', timestamp=datetime.utcnow(), colour=7047495)
            if has_none == True:
                embed.add_field(name=coin_list.upper(), value='```N/A for {}```'.format(coin_list), inline=False)
            else:
                embed.add_field(name=coin_list.upper(), value='```{}```'.format(table.table), inline=False)
                embed.add_field(name="INFO", value='```CMC updated: {}\nCG updated: {}```'.format(cmc_ago, cg_ago), inline=False)
            embed.add_field(name="OTHER LINKS", value="{} / {} / {}".format("[Invite TipBot](http://invite.discord.bot.tips)", "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
            embed.set_footer(text=f"Market command requested by {ctx.message.author.name}#{ctx.message.author.discriminator}. To disable Market Command, {prefix}setting market")
            try:
                msg = await ctx.send(embed=embed)
                await ctx.message.add_reaction(EMOJI_OK_HAND)
                await msg.add_reaction(EMOJI_OK_BOX)
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                await logchanbot(traceback.format_exc())
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Too many tickers.')
        return


@bot.command(pass_context=True)
async def price(ctx, *args):
    prefix = await get_guild_prefix(ctx)
    PriceQ = (' '.join(args)).split()

    # disable game for TRTL discord
    if isinstance(ctx.message.channel, discord.DMChannel) == False and ctx.guild and ctx.guild.id == TRTL_DISCORD:
        return

    try:
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if isinstance(ctx.message.channel, discord.DMChannel) == False and serverinfo \
        and 'enable_market' in serverinfo and serverinfo['enable_market'] == "NO":
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Market command is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING MARKET`')
            await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}price** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
            return
    except Exception as e:
        if isinstance(ctx.message.channel, discord.DMChannel) == False:
            return
        pass

    def format_amount(amount: float):
        if amount > 1:
            return '{:,.2f}'.format(amount)
        elif amount > 0.01:
            return '{:,.4f}'.format(amount)
        elif amount > 0.0001:
            return '{:,.6f}'.format(amount)
        elif amount > 0.000001:
            return '{:,.8f}'.format(amount)
        else:
            return '{:,.10f}'.format(amount)

    if len(PriceQ) == 1:
        # Only ticker accepted
        if not re.match('^[a-zA-Z0-9]+$', PriceQ[0]):
            await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Invalid **{ticker}**.')
            await ctx.message.add_reaction(EMOJI_ERROR)
            return
        
        ticker = PriceQ[0].upper()
        market_price = await store.market_value_in_usd(1, ticker)
        if market_price is None:
            await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} I can not find price information for **{ticker}** in CoinGecko and CMC.')
            await ctx.message.add_reaction(EMOJI_ERROR)
            return
        else:
            try:
                embed = discord.Embed(title='{} Price'.format(ticker), description='Price Information', timestamp=datetime.utcnow(), colour=7047495)
                if 'cmc_price' in market_price and market_price['cmc_price'] > 0.00000001:
                    update = datetime.strptime(market_price['cmc_update'].split(".")[0], '%Y-%m-%dT%H:%M:%S')
                    ago = timeago.format(update, datetime.utcnow())
                    embed.add_field(name="From CoinMarketCap", value='`{}USD. Updated {} from CoinMarketCap`'.format(format_amount(market_price['cmc_price']), ago), inline=False)
                if 'cg_price' in market_price and market_price['cg_price'] > 0.00000001:
                    update = datetime.strptime(market_price['cg_update'].split(".")[0], '%Y-%m-%dT%H:%M:%S')
                    ago = timeago.format(update, datetime.utcnow())
                    embed.add_field(name="From CoinGecko", value='`{}USD. Updated {} from CoinGecko`'.format(format_amount(market_price['cg_price']), ago), inline=False)
                    
                embed.add_field(name="OTHER LINKS", value="{} / {} / {}".format("[Invite TipBot](http://invite.discord.bot.tips)", "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
                embed.set_footer(text=f"Market command requested by {ctx.message.author.name}#{ctx.message.author.discriminator}. To disable Market Command, {prefix}setting market")
                try:
                    msg = await ctx.send(embed=embed)
                    await ctx.message.add_reaction(EMOJI_OK_HAND)
                    await msg.add_reaction(EMOJI_OK_BOX)
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    await logchanbot(traceback.format_exc())
                return
            except Exception as e:
                await logchanbot(traceback.format_exc())
            return
    elif len(PriceQ) == 2:
        # Only ticker accepted sample 10 btc, 15.2 btc
        # price 10.0 btc
        ticker = PriceQ[1].upper()
        if not re.match('^[a-zA-Z0-9]+$', ticker):
            await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Invalid **{ticker}**.')
            await ctx.message.add_reaction(EMOJI_ERROR)
            return
        # check if valid number
        amount = None
        PriceQ[0] = PriceQ[0].replace(",", "")
        try:
            amount = int(PriceQ[0])
        except ValueError:
            pass
        try:
            amount = float(PriceQ[0])
        except ValueError:
            pass

        if amount is None:
            await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Invalid amount **{PriceQ[0]}**.')
            await ctx.message.add_reaction(EMOJI_ERROR)
            return

        market_price = await store.market_value_in_usd(amount, ticker)
        if market_price is None:
            await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} I can not find price information for **{ticker}** in CoinGecko and CMC.')
            await ctx.message.add_reaction(EMOJI_ERROR)
            return
        else:
            try:
                embed = discord.Embed(title='{}{} Price'.format(PriceQ[0], ticker), description='Price Information', timestamp=datetime.utcnow(), colour=7047495)
                if 'cmc_price' in market_price and market_price['cmc_price'] > 0.00000001:
                    update = datetime.strptime(market_price['cmc_update'].split(".")[0], '%Y-%m-%dT%H:%M:%S')
                    ago = timeago.format(update, datetime.utcnow())
                    embed.add_field(name="From CoinMarketCap", value='`{}{} = {}USD. Updated {} from CoinMarketCap`'.format(PriceQ[0], PriceQ[1].upper(), format_amount(market_price['cmc_price'] * float(PriceQ[0])), ago), inline=False)
                if 'cg_price' in market_price and market_price['cg_price'] > 0.00000001:
                    update = datetime.strptime(market_price['cg_update'].split(".")[0], '%Y-%m-%dT%H:%M:%S')
                    ago = timeago.format(update, datetime.utcnow())
                    embed.add_field(name="From CoinGecko", value='`{}{} = {}USD. Updated {} from CoinGecko`'.format(PriceQ[0], PriceQ[1].upper(), format_amount(market_price['cg_price'] * float(PriceQ[0])), ago), inline=False)

                embed.add_field(name="OTHER LINKS", value="{} / {} / {}".format("[Invite TipBot](http://invite.discord.bot.tips)", "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
                embed.set_footer(text=f"Market command requested by {ctx.message.author.name}#{ctx.message.author.discriminator}. To disable Market Command, {prefix}setting market")
                try:
                    msg = await ctx.send(embed=embed)
                    await ctx.message.add_reaction(EMOJI_OK_HAND)
                    await msg.add_reaction(EMOJI_OK_BOX)
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    await logchanbot(traceback.format_exc())
                return
            except Exception as e:
                await logchanbot(traceback.format_exc())
            return
    elif len(PriceQ) == 3:
        # .price xmr in btc
        if not re.match('^[a-zA-Z0-9]+$', PriceQ[0]) or not re.match('^[a-zA-Z0-9]+$', PriceQ[2]):
            await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Invalid pairs **{PriceQ[0]}** and **{PriceQ[2]}**.')
            await ctx.message.add_reaction(EMOJI_ERROR)
            return

        if PriceQ[1].lower() == "in":
            ### A1 / B1 or A2 / B2
            tmpA1 = await store.market_value_cmc_usd(PriceQ[0])
            tmpA2 = await store.market_value_cg_usd(PriceQ[0])

            tmpB1 = await store.market_value_cmc_usd(PriceQ[2])
            tmpB2 = await store.market_value_cg_usd(PriceQ[2])

            try:
                embed = discord.Embed(title='{} IN {}'.format(PriceQ[0].upper(), PriceQ[2].upper()), description='Price Information', timestamp=datetime.utcnow(), colour=7047495)
                if any(x is None for x in [tmpA1, tmpB1]) and any(x is None for x in [tmpA2, tmpB2]):
                    embed.add_field(name="From CoinMarketCap", value='`No data from CoinMarketCap`', inline=True)
                    embed.add_field(name="From CoinGecko", value='`No data from Coingecko`', inline=True)
                if tmpA1 and tmpB1:
                    totalValue = float(tmpA1 / tmpB1)
                    embed.add_field(name="From CoinMarketCap", value='`1 {} = {:,.8f}{} from CoinMarketCap`'.format(PriceQ[0].upper(), totalValue, PriceQ[2].upper()), inline=False)
                if tmpA2 and tmpB2:
                    totalValue = float(tmpA2 / tmpB2)
                    embed.add_field(name="From CoinGecko", value='`1 {} = {:,.8f}{} from CoinGecko`'.format(PriceQ[0].upper(), totalValue, PriceQ[2].upper()), inline=False)
                embed.add_field(name="OTHER LINKS", value="{} / {} / {}".format("[Invite TipBot](http://invite.discord.bot.tips)", "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
                embed.set_footer(text=f"Market command requested by {ctx.message.author.name}#{ctx.message.author.discriminator}. To disable Market Command, {prefix}setting market")
                try:
                    msg = await ctx.send(embed=embed)
                    await ctx.message.add_reaction(EMOJI_OK_HAND)
                    await msg.add_reaction(EMOJI_OK_BOX)
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    await logchanbot(traceback.format_exc())
            except Exception as e:
                await logchanbot(traceback.format_exc())
            return
    elif len(PriceQ) >= 4:
        # .price 10 xmr in btc
        if not re.match('^[a-zA-Z0-9]+$', PriceQ[1]) or not re.match('^[a-zA-Z0-9]+$', PriceQ[3]):
            await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Invalid pairs **{PriceQ[1]}** and **{PriceQ[3]}**.')
            await ctx.message.add_reaction(EMOJI_ERROR)
            return

        if PriceQ[2].lower() != "in":
            await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Invalid syntax.')
            await ctx.message.add_reaction(EMOJI_ERROR)
            return
        else:
            # check if valid number
            amount = None
            PriceQ[0] = PriceQ[0].replace(",", "")
            try:
                amount = int(PriceQ[0])
            except ValueError:
                message = 'Invalid given number.'
                pass
            if amount is None:
                try:
                    amount = float(PriceQ[0])
                except ValueError:
                    message = 'Invalid given number.'

            if amount is None:
                await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Invalid amount **{PriceQ[0]}**.')
                await ctx.message.add_reaction(EMOJI_ERROR)
                return

            ### A1 / B1 or A2 / B2
            tmpA1 = await store.market_value_cmc_usd(PriceQ[1])
            tmpA2 = await store.market_value_cg_usd(PriceQ[1])

            tmpB1 = await store.market_value_cmc_usd(PriceQ[3])
            tmpB2 = await store.market_value_cg_usd(PriceQ[3])

            try:
                embed = discord.Embed(title='{}{} IN {}'.format(PriceQ[0], PriceQ[1].upper(), PriceQ[3].upper()), description='Price Information', timestamp=datetime.utcnow(), colour=7047495)
                if any(x is None for x in [tmpA1, tmpB1]) and any(x is None for x in [tmpA2, tmpB2]):
                    embed.add_field(name="From CoinMarketCap", value='`No data from CoinMarketCap`', inline=True)
                    embed.add_field(name="From CoinGecko", value='`No data from Coingecko`', inline=True)
                if tmpA1 and tmpB1:
                    totalValue = float(float(PriceQ[0]) * tmpA1 / tmpB1)
                    if tmpA1 == 0 or tmpB1 == 0:
                        embed.add_field(name="From CoinMarketCap", value='`Not sufficient data from CoinMarketCap`', inline=True)
                    else:
                        embed.add_field(name="From CoinMarketCap", value='`{} {} = {}{} from CoinMarketCap`'.format(PriceQ[0], PriceQ[1].upper(), format_amount(totalValue), PriceQ[3].upper()), inline=False)
                if tmpA2 and tmpB2:
                    totalValue = float(float(PriceQ[0]) * tmpA2 / tmpB2)
                    if tmpA2 == 0 or tmpB2 == 0:
                        embed.add_field(name="From CoinGecko", value='`Not sufficient data from CoinGecko`', inline=True)
                    else:
                        embed.add_field(name="From CoinGecko", value='`{} {} = {}{} from CoinGecko`'.format(PriceQ[0], PriceQ[1].upper(), format_amount(totalValue), PriceQ[3].upper()), inline=False)
                embed.add_field(name="OTHER LINKS", value="{} / {} / {}".format("[Invite TipBot](http://invite.discord.bot.tips)", "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
                embed.set_footer(text=f"Market command requested by {ctx.message.author.name}#{ctx.message.author.discriminator}. To disable Market Command, {prefix}setting market")
                try:
                    msg = await ctx.send(embed=embed)
                    await ctx.message.add_reaction(EMOJI_OK_HAND)
                    await msg.add_reaction(EMOJI_OK_BOX)
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    await logchanbot(traceback.format_exc())
            except Exception as e:
                await logchanbot(traceback.format_exc())
            return


@bot.command(pass_context=True, name='cal', aliases=['calcule', 'calculator', 'calc'], help=bot_help_cal)
async def cal(ctx, eval_string: str = None):
    if isinstance(ctx.channel, discord.DMChannel) == True:
        return
    if eval_string is None:
        await ctx.send(f'{EMOJI_INFORMATION} {ctx.author.mention}, Example: `cal 2+3+4/2`')
        return
    else:
        eval_string_original = eval_string
        eval_string = eval_string.replace(",", "")
        supported_function = ['+', '-', '*', '/', '(', ')', '.', ',']
        additional_support = ['exp', 'sqrt', 'abs', 'log10', 'log', 'sinh', 'cosh', 'tanh', 'sin', 'cos', 'tan']
        test_string = eval_string
        for each in additional_support:
            test_string = test_string.replace(each, "")
        if all([c.isdigit() or c in supported_function for c in test_string]):
            try:
                result = numexpr.evaluate(eval_string).item()
                msg = await ctx.send(f'{EMOJI_INFORMATION} {ctx.author.mention} result of `{eval_string_original}`:```{result}```')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
            except Exception as e:
                await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} I can not find the result for `{eval_string_original}`.')
                return
        else:
            await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Unsupported usage for `{eval_string_original}`.')
            return


@bot.command(pass_context=True, name='deposit', help=bot_help_deposit)
async def deposit(ctx, coin_name: str, option: str=None):
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'deposit')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    # Check if maintenance
    if IS_MAINTENANCE == 1:
        if int(ctx.message.author.id) in MAINTENANCE_OWNER:
            await ctx.message.add_reaction(EMOJI_MAINTENANCE)
            pass
        else:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {config.maintenance_msg}')
            return
    else:
        pass
    # End Check if maintenance

    COIN_NAME = coin_name.upper()
    if COIN_NAME not in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
        return

    if not is_coin_depositable(COIN_NAME):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} DEPOSITING is currently disable for {COIN_NAME}.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    else:
        try:
            coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
        except Exception as e:
            await logchanbot(traceback.format_exc())
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**')
            return
    
    if is_maintenance_coin(COIN_NAME) and (ctx.message.author.id not in MAINTENANCE_OWNER):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return

    if coin_family in ["TRTL", "BCN"]:
        wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if wallet is None:
            userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    elif coin_family == "XMR":
        wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if wallet is None:
            userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    elif coin_family == "DOGE":
        wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if wallet is None:
            wallet = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    elif coin_family == "NANO":
        wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if wallet is None:
            wallet = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    elif coin_family == "ERC-20":
        wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if wallet is None:
            w = await create_address_eth()
            wallet = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0, w)
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    else:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**')
        return
    if wallet is None:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Internal Error for `.info`')
        return
    if not os.path.exists(config.deposit_qr.path_deposit_qr_create + wallet['balance_wallet_address'] + ".png"):
        try:
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
            img.save(config.deposit_qr.path_deposit_qr_create + wallet['balance_wallet_address'] + ".png")
        except Exception as e:
            await logchanbot(traceback.format_exc())
        # https://deposit.bot.tips/
    if not os.path.exists(config.qrsettings.path + wallet['balance_wallet_address'] + ".png"):
        try:
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
        except Exception as e:
            await logchanbot(traceback.format_exc())
    if option and option.upper() in ["PLAIN", "TEXT", "NOEMBED"]:
        deposit = wallet['balance_wallet_address']
        try:
            msg = await ctx.send(f'{ctx.author.mention} Your **{COIN_NAME}**\'s deposit address: ```{deposit}```')
            await msg.add_reaction(EMOJI_OK_BOX)
            await ctx.message.add_reaction(EMOJI_OK_HAND)
            return
        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            if isinstance(ctx.channel, discord.DMChannel) == False:
                try:
                    msg = await ctx.message.author.send(f'{ctx.author.mention} Your **{COIN_NAME}**\'s deposit address: ```{deposit}```')
                    await msg.add_reaction(EMOJI_OK_BOX)
                    await ctx.message.add_reaction(EMOJI_OK_HAND)
                    return
                except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                    await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                    return
            else:
                await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                return

    embed = discord.Embed(title=f'Your Deposit {ctx.message.author.name}#{ctx.message.author.discriminator} / **{COIN_NAME}**', description='{}'.format(get_notice_txt(COIN_NAME)), timestamp=datetime.utcnow(), colour=7047495)
    embed.set_author(name=ctx.message.author.name, icon_url=ctx.message.author.avatar_url)
    embed.add_field(name="Deposit Address", value="`{}`".format(wallet['balance_wallet_address']), inline=False)
    if 'user_wallet_address' in wallet and wallet['user_wallet_address'] and isinstance(ctx.channel, discord.DMChannel) == True:
        embed.add_field(name="Withdraw Address", value="`{}`".format(wallet['user_wallet_address']), inline=False)
    elif 'user_wallet_address' in wallet and wallet['user_wallet_address'] and isinstance(ctx.channel, discord.DMChannel) == False:
        embed.add_field(name="Withdraw Address", value="`(Only in DM)`", inline=False)
    if COIN_NAME in ENABLE_COIN_ERC:
        token_info = await store.get_token_info(COIN_NAME)
        if token_info and token_info['deposit_note']:
            embed.add_field(name="{} Deposit Note".format(COIN_NAME), value="`{}`".format(token_info['deposit_note']), inline=False)
    embed.set_thumbnail(url=config.deposit_qr.deposit_url + "/tipbot_deposit_qr/" + wallet['balance_wallet_address'] + ".png")
    prefix = await get_guild_prefix(ctx)
    embed.set_footer(text=f"Use:{prefix}deposit {COIN_NAME} plain (for plain text)")
    try:
        msg = await ctx.send(embed=embed)
        await msg.add_reaction(EMOJI_OK_BOX)
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        return
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        try:
            msg = await ctx.send(embed=embed)
            await msg.add_reaction(EMOJI_OK_BOX)
            await ctx.message.add_reaction(EMOJI_OK_HAND)
            return
        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
            return


@bot.command(pass_context=True, name='mdeposit')
async def mdeposit(ctx, coin_name: str, option: str=None):
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'mdeposit')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    # disable guild tip for TRTL discord
    if ctx.guild and ctx.guild.id == TRTL_DISCORD:
        await ctx.message.add_reaction(EMOJI_LOCKED)
        return

    # Check if maintenance
    if IS_MAINTENANCE == 1:
        if int(ctx.message.author.id) in MAINTENANCE_OWNER:
            await ctx.message.add_reaction(EMOJI_MAINTENANCE)
            pass
        else:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {config.maintenance_msg}')
            return
    else:
        pass
    # End Check if maintenance

    COIN_NAME = coin_name.upper()
    if COIN_NAME not in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
        return

    if not is_coin_depositable(COIN_NAME):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} DEPOSITING is currently disable for {COIN_NAME}.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    try:
        if COIN_NAME in ENABLE_COIN_ERC:
            coin_family = "ERC-20"
        else:
            coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    except Exception as e:
        await logchanbot(traceback.format_exc())
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**')
        return
    
    if is_maintenance_coin(COIN_NAME) and (ctx.message.author.id not in MAINTENANCE_OWNER):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return

    if coin_family in ["TRTL", "BCN"]:
        wallet = await store.sql_get_userwallet(str(ctx.guild.id), COIN_NAME)
        if wallet is None:
            userregister = await store.sql_register_user(str(ctx.guild.id), COIN_NAME, 'DISCORD', 0)
            wallet = await store.sql_get_userwallet(str(ctx.guild.id), COIN_NAME)
    elif coin_family == "XMR":
        wallet = await store.sql_get_userwallet(str(ctx.guild.id), COIN_NAME)
        if wallet is None:
            userregister = await store.sql_register_user(str(ctx.guild.id), COIN_NAME, 'DISCORD', 0)
            wallet = await store.sql_get_userwallet(str(ctx.guild.id), COIN_NAME)
    elif coin_family == "DOGE":
        wallet = await store.sql_get_userwallet(str(ctx.guild.id), COIN_NAME)
        if wallet is None:
            wallet = await store.sql_register_user(str(ctx.guild.id), COIN_NAME, 'DISCORD', 0)
            wallet = await store.sql_get_userwallet(str(ctx.guild.id), COIN_NAME)
    elif coin_family == "NANO":
        wallet = await store.sql_get_userwallet(str(ctx.guild.id), COIN_NAME)
        if wallet is None:
            wallet = await store.sql_register_user(str(ctx.guild.id), COIN_NAME, 'DISCORD', 0)
            wallet = await store.sql_get_userwallet(str(ctx.guild.id), COIN_NAME)
    elif coin_family == "ERC-20":
        wallet = await store.sql_get_userwallet(str(ctx.guild.id), COIN_NAME)
        if wallet is None:
            w = await create_address_eth()
            wallet = await store.sql_register_user(str(ctx.guild.id), COIN_NAME, 'DISCORD', 0, w)
            wallet = await store.sql_get_userwallet(str(ctx.guild.id), COIN_NAME)
    else:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**')
        return
    if wallet is None:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Internal Error for `.info`')
        return
    if not os.path.exists(config.deposit_qr.path_deposit_qr_create + wallet['balance_wallet_address'] + ".png"):
        try:
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
            img.save(config.deposit_qr.path_deposit_qr_create + wallet['balance_wallet_address'] + ".png")
        except Exception as e:
            await logchanbot(traceback.format_exc())
        # https://deposit.bot.tips/
    if not os.path.exists(config.qrsettings.path + wallet['balance_wallet_address'] + ".png"):
        try:
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
        except Exception as e:
            await logchanbot(traceback.format_exc())
    if option and option.upper() in ["PLAIN", "TEXT", "NOEMBED"]:
        deposit = wallet['balance_wallet_address']
        try:
            msg = await ctx.send(f'{ctx.author.mention} Guild {ctx.guild.name} **{COIN_NAME}**\'s deposit address (not yours): ```{deposit}```')
            await msg.add_reaction(EMOJI_OK_BOX)
            await ctx.message.add_reaction(EMOJI_OK_HAND)
        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
        return

    embed = discord.Embed(title=f'**Guild {ctx.guild.name}** deposit / **{COIN_NAME}**', description='`This is guild\'s tipjar address. Do not deposit here unless you want to deposit to this guild and not yours!`', timestamp=datetime.utcnow(), colour=7047495)
    embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
    embed.add_field(name="Deposit Address", value="`{}`".format(wallet['balance_wallet_address']), inline=False)

    embed.set_thumbnail(url=config.deposit_qr.deposit_url + "/tipbot_deposit_qr/" + wallet['balance_wallet_address'] + ".png")
    prefix = await get_guild_prefix(ctx)
    embed.set_footer(text=f"Use:{prefix}mdeposit {COIN_NAME} plain (for plain text)")
    try:
        msg = await ctx.send(embed=embed)
        await msg.add_reaction(EMOJI_OK_BOX)
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        return
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        try:
            msg = await ctx.send(embed=embed)
            await msg.add_reaction(EMOJI_OK_BOX)
            await ctx.message.add_reaction(EMOJI_OK_HAND)
            return
        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
            return


async def help_main_embed(ctx, prefix, section: str='MAIN'):
    prefix = await get_guild_prefix(ctx)
    embed = discord.Embed(title="List of commands", description="To avoid spamming other, you can do in Direct Message or Bot Channel", timestamp=datetime.utcnow(), color=0xDEADBF)
    help_specific = False

    if section.upper() == "GUILDSETTING":
        cmd_setting = ["setting prefix <.>", "setting default_coin <coin_name>", "setting tiponly <coin1> [coin2] [coin3] ..", "setting ignorechan", "setting del_ignorechan", \
        "setting <mute/unmute>", "setting game", "guild botchan", "guild tipmsg", "guild gamechan [name]"]
        embed.add_field(name="SERVER [GUILD]", value="`{}`".format(", ".join(cmd_setting)), inline=False)
        
        cmd_tag = ["tag", "tag <-add> <tag_name> <tag description>", "tag <-del> <tag_name>", "itag", "itag <itag_name> (need attachement)", "itag -del <tag_name>"]
        embed.add_field(name="TAG / ITAG", value="`{}`".format(", ".join(cmd_tag)), inline=False)

    elif section.upper() == "TIPPING":
        cmd_tip = ["tip <amount> [coin_name] @mention1 @mention2", "tipall <amount> [coin_name]", "tip <amount> [coin_name] [last 2h]",  "tip <amount> [coin_name] [last 10u]", "freetip <amount> <coin_name>", "randtip <amount> <coin_name>", "take"]
        embed.add_field(name="TIP COMMAND", value="`{}`".format(", ".join(cmd_tip)), inline=False)

        cmd_tip = ["mtip|gtip <amount> [coin_name] @mention1 @mention2", "mtip|gtip <amount> [coin_name] [last 2h]",  "mtip|gtip <amount> [coin_name] [last 10u]", "(Required permission)"]
        embed.add_field(name="GUILD TIP COMMAND", value="`{}`".format(", ".join(cmd_tip)), inline=False)

        cmd_user = ["balance [list]", "botbalance @mention_bot <coin_name>", "deposit <coin_name>", "notifytip <on/off>", "reg <coin_address>", "send <amount> <coin_address>", "withdraw <amount> <coin_name>", "account deposit"]
        embed.add_field(name="USER", value="`{}`".format(", ".join(cmd_user)), inline=False)

        cmd_voucher = ["voucher claim", "voucher fee", "voucher getclaim", "voucher getunclaim", "voucher make <amount> <coin_name> <comment>"]
        embed.add_field(name="VOUCHER", value="`{}`".format(", ".join(cmd_voucher)), inline=False)

    elif section.upper() == "GAMING":
        cmd_game = ["game bagel", "game bagel2", "game bagel3", "game blackjack", "game dice", "game 2048", "game hangman", "game maze", "game slot", "game snail <number>", "game sokoban", "game stat"]
        embed.add_field(name="GAMES", value="`{}`".format(", ".join(cmd_game)), inline=False)

    elif section.upper() == "TOOLING":
        cmd_fun = ["tb spank <@mention>", "tb punch <@mention>", "tb slap <@mention>", "tb praise <@mention>", "tb shoot <@mention>", "tb kick <@mention>", "tb fistbump <@mention>", "tb dance", "tb sketchme [@mention]", "tb draw [@mention]"]
        embed.add_field(name="FUN COMMAND", value="`{}`".format(", ".join(cmd_fun)), inline=False)

        cmd_dev = ["tool dec2hex <number>", "tool hex2dec <hex>", "tool hex2str <hex>", "tool str2hex <string>", "tool emoji"]
        embed.add_field(name="DEV COMMAND", value="`{}`".format(", ".join(cmd_dev)), inline=False)

        cmd_other = ["disclaimer", "cal <1+2+3>", "coininfo <coin_name>", "feedback", "paymentid", "rand <1-100>", "stats", "userinfo @mention", "pools <coin_name_full>"]
        embed.add_field(name="OTHER COMMAND", value="`{}`".format(", ".join(cmd_other)), inline=False)

    elif section.upper() == "MARKETING":
        cmd_market = ["cg <ticker>", "price <ticker>", "price <amount> <ticker>", "price <amount> <coin1> in <coin2>", "pricelist <ticker1> [ticker2].."]
        embed.add_field(name="MARKET COMMAND", value="`{}`".format(", ".join(cmd_market)), inline=False)

    elif section.upper() == "DISCLAIMER":
        embed.add_field(name="DISCLAIMER", value="{}".format(DISCLAIM_MSG_LONG), inline=False)

    else:
        # Try to find if there is a help to that
        help_item = await store.sql_help_doc_get('help', section)
        if help_item:
            embed = discord.Embed(title=f"Help {section.upper()}", description="To avoid spamming other, you can do in a bot channel", timestamp=datetime.utcnow(), color=0xDEADBF)
            embed.add_field(name="Explanation", value="```{}```".format(discord.utils.escape_markdown(help_item['detail'].replace('prefix', prefix))), inline=False)
            help_specific = True
            try:
                if 'example' in help_item and help_item['example'] and len(help_item['example'].strip()) > 0:
                    embed.add_field(name="Example", value="`{}`".format(discord.utils.escape_markdown(help_item['example'].replace('prefix', prefix))), inline=False)
                else:
                    embed.add_field(name="Example", value="`N/A`", inline=False)
            except Exception as e:
                pass
        else:
            embed.add_field(name="What is this", value="`It's a cool cryptocurrency tipping bot`", inline=False)
            embed.add_field(name="Why is it here", value="`Guild Manager or Owner invited it`", inline=False)
            embed.add_field(name="What is it for", value="`Tipping cryptocurrency to other people, playing some discord text games and earning crypto, depositing and withdrawing is so easy, tipping is off-chain (no fee), and more`", inline=False)
            embed.add_field(name="Tell me how to use it", value="`Re-act on each EMOJI for help commands`", inline=False)
            embed.add_field(name="Any other info?", value="`Check link in the footer`", inline=False)
            embed.add_field(name="It's not working", value="`We appreciate for any feedback such as submitting an issue in our Github, using feedback command, joining our discord and say it`", inline=False)

    # add donation to every section
    cmd_donation = ["donate <amount> <coin_name>", "donate list"]
    embed.add_field(name="DONATION", value="`{}`".format(", ".join(cmd_donation)), inline=False)

    if isinstance(ctx.message.channel, discord.DMChannel) == False:
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        coin_name = serverinfo['default_coin'].upper() if serverinfo else "WRKZ"
        embed.add_field(name="GUILD INFO", value="`ID: {}, Name: {}, Default Coin: {}, Prefix: {}`".format(ctx.guild.id, ctx.guild.name, coin_name, prefix), inline=False)

    if help_specific == False:
        embed.add_field(name="OTHER LINKS", value="{} / {} / {}".format("[Invite TipBot](http://invite.discord.bot.tips)", "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
        embed.set_footer(text=f"Required - <>, Optional - [], Help: {EMOJI_HELP_HOUSE} Home, Help: {EMOJI_HELP_GUILD} Guild, {EMOJI_HELP_TIP} Tipping, {EMOJI_HELP_GAME} Game, {EMOJI_HELP_CG} Market, {EMOJI_HELP_TOOL} Tool, {EMOJI_HELP_NOTE} Disclaimer")
    else:
        embed.set_footer(text=f"Help requested by {ctx.message.author.name}#{ctx.message.author.discriminator}")
    return embed


@bot.command(pass_context=True, name='help')
async def help(ctx, *, section: str='MAIN'):
    global LOG_CHAN
    botLogChan = bot.get_channel(id=LOG_CHAN)
    prefix = await get_guild_prefix(ctx)

    if not re.match('^[a-zA-Z0-9-_ ]+$', section):
        await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Invalid help topic.')
        await ctx.message.add_reaction(EMOJI_ERROR)
        return

    try:
        embed = await help_main_embed(ctx, prefix, section)
        if isinstance(ctx.message.channel, discord.DMChannel) == False:
            msg = await ctx.send(embed=embed)
        else:
            msg = await ctx.message.author.send(embed=embed)
        help_item = await store.sql_help_doc_get('help', section.upper())

        if section.upper() in ["MAIN", "GUILDSETTING", "TIPPING", "GAMING", "TOOLING", "MARKETING", "DISCLAIMER"] or help_item is None:
            await msg.add_reaction(EMOJI_HELP_HOUSE)    
            await msg.add_reaction(EMOJI_HELP_GUILD)
            await msg.add_reaction(EMOJI_HELP_TIP)
            await msg.add_reaction(EMOJI_HELP_GAME)
            await msg.add_reaction(EMOJI_HELP_TOOL)
            await msg.add_reaction(EMOJI_HELP_CG)
            await msg.add_reaction(EMOJI_HELP_NOTE)
            await msg.add_reaction(EMOJI_OK_BOX)
        else:
            # No need interactive if single help
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        while True:
            def check(reaction, user):
                return user == ctx.message.author and reaction.message.author == bot.user and reaction.message.id == msg.id and str(reaction.emoji) \
                in (EMOJI_HELP_HOUSE, EMOJI_HELP_GUILD, EMOJI_HELP_TIP, EMOJI_HELP_GAME, EMOJI_HELP_TOOL, EMOJI_HELP_NOTE, EMOJI_HELP_CG, EMOJI_OK_BOX)

            done, pending = await asyncio.wait([
                                bot.wait_for('reaction_remove', timeout=90, check=check),
                                bot.wait_for('reaction_add', timeout=90, check=check)
                            ], return_when=asyncio.FIRST_COMPLETED)
            try:
                # stuff = done.pop().result()
                reaction, user = done.pop().result()
            except Exception as e:
                # timeout pass, just let it pass
                pass
                return

            if str(reaction.emoji) == EMOJI_OK_BOX:
                await asyncio.sleep(1)
                try:
                    await msg.delete()
                except Exception as e:
                    pass
                return
            elif str(reaction.emoji) == EMOJI_HELP_HOUSE:
                section = "MAIN"
            elif str(reaction.emoji) == EMOJI_HELP_GUILD:
                section = "GUILDSETTING"
            elif str(reaction.emoji) == EMOJI_HELP_TIP:
                section = "TIPPING"
            elif str(reaction.emoji) == EMOJI_HELP_GAME:
                section = "GAMING"
            elif str(reaction.emoji) == EMOJI_HELP_TOOL:
                section = "TOOLING"
            elif str(reaction.emoji) == EMOJI_HELP_CG:
                section = "MARKETING"
            elif str(reaction.emoji) == EMOJI_HELP_NOTE:
                section = "DISCLAIMER"
            embed = await help_main_embed(ctx, prefix, section)
            await msg.edit(embed=embed)
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        await botLogChan.send(f'**Failed** Missing Permissions for sending help in guild {ctx.guild.id} / {ctx.guild.name} / # {ctx.message.channel.name}')
        await message.add_reaction(EMOJI_ERROR)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    return


async def help_setting(message, prefix):
    global LOG_CHAN
    botLogChan = bot.get_channel(id=LOG_CHAN)
    embed = discord.Embed(title=f"List of SETTING command {message.guild.name}", description="Required Managed Channel Permission", timestamp=datetime.utcnow())
    if isinstance(message.channel, discord.DMChannel) == True:
        await message.add_reaction(EMOJI_ERROR) 
        await message.author.send('This command can not be in private.')
        return
    else:
        embed.add_field(name=f"{prefix}setting prefix <prefix>", value="`Change bot prefix. Supported prefix: . ? * !`", inline=False)
        embed.add_field(name=f"{prefix}setting tiponly <coin1> [coin2] [coin3] ..", value="`Set tip-only to these coins`", inline=False)
        embed.add_field(name=f"{prefix}setting ignorechan", value="`Ignore this channel from tipping`", inline=False)
        embed.add_field(name=f"{prefix}setting del_ignorechan", value="`Delete this channel from ignored tipping channel`", inline=False)
        embed.add_field(name=f"{prefix}setting botchan #channel_name", value="`Restrict most bot command in #channel_name`", inline=False)
        embed.add_field(name=f"{prefix}setting game", value="`Enable / Disable game feature / command`", inline=False)
        embed.add_field(name=f"{prefix}setting <mute/unmute>", value="`Mute / Unmute the said text channel`", inline=False)
        embed.add_field(name="OTHER LINKS", value="{} / {} / {}".format("[Invite TipBot](http://invite.discord.bot.tips)", "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
        embed.set_footer(text="Required - <>, Optional - []")
    try:
        msg = await message.channel.send(embed=embed)
        await msg.add_reaction(EMOJI_OK_BOX)
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        await botLogChan.send(f'**Failed** Missing Permissions for sending help_setting in guild {message.guild.id} / {message.guild.name} / # {message.channel.name}')
        await message.add_reaction(EMOJI_ERROR)
    return


@bot.command(pass_context=True, name='pools', aliases=['pool'])
async def pools(ctx, coin: str):
    global redis_conn, redis_expired, TRTL_DISCORD, MINGPOOLSTAT_IN_PROCESS
    requested_date = int(time.time())
    COIN_NAME = coin.upper()
    if config.miningpoolstat.enable != 1:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Command temporarily disable')
        return
    if isinstance(ctx.message.channel, discord.DMChannel) == False and ctx.guild.id == TRTL_DISCORD and COIN_NAME != "TURTLECOIN":
        await ctx.message.add_reaction(EMOJI_ERROR)
        return
    key = "TIPBOT:MININGPOOL:" + COIN_NAME
    key_hint = "TIPBOT:MININGPOOL:SHORTNAME:" + COIN_NAME
    if redis_conn and not redis_conn.exists(key):
        if redis_conn.exists(key_hint):
            await ctx.message.add_reaction(EMOJI_QUESTEXCLAIM)
            await ctx.send(f'{ctx.author.mention} Did you mean **{redis_conn.get(key_hint).decode().lower()}**.')
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} Unknown coin **{COIN_NAME}**.')
        return
    elif redis_conn and redis_conn.exists(key):
        # check if already in redis
        key_p = key + ":POOLS" # TIPBOT:MININGPOOL:COIN_NAME:POOLS
        key_data = "TIPBOT:MININGPOOLDATA:" + COIN_NAME
        get_pool_data = None
        is_cache = 'NO'
        if redis_conn and redis_conn.exists(key_data):
            await ctx.message.add_reaction(EMOJI_FLOPPY)
            get_pool_data = json.loads(redis_conn.get(key_data).decode())
            is_cache = 'YES'
        else:
            if ctx.message.author.id not in MINGPOOLSTAT_IN_PROCESS:
                MINGPOOLSTAT_IN_PROCESS.append(ctx.message.author.id)
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{ctx.author.mention} You have another check of pools stats in progress.')
                return
            try:
                async with ctx.typing():
                    await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
                    get_pool_data = await get_miningpoolstat_coin(COIN_NAME)
            except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                return
        if get_pool_data and 'data' in get_pool_data:
            try:
                embed = discord.Embed(title='Mining Pools for {}'.format(COIN_NAME), description='', timestamp=datetime.utcnow(), colour=7047495)
                if 'symbol' in get_pool_data:
                    embed.add_field(name="Ticker", value=get_pool_data['symbol'], inline=True)
                if 'algo' in get_pool_data:
                    embed.add_field(name="Algo", value=get_pool_data['algo'], inline=True)
                if 'hashrate' in get_pool_data:
                    embed.add_field(name="Hashrate", value=hhashes(get_pool_data['hashrate']), inline=True)
                i = 1
                if len(get_pool_data['data']) > 0:
                    async def sorted_pools(pool_list):
                        # https://web.archive.org/web/20150222160237/stygianvision.net/updates/python-sort-list-object-dictionary-multiple-key/
                        mylist = sorted(pool_list, key=lambda k: -k['hashrate'])
                        return mylist
                    pool_links = ''
                    pool_list = await sorted_pools(get_pool_data['data'])

                    for each_pool in pool_list:
                        if i <= 15:
                            try:
                                hash_rate = hhashes(each_pool['hashrate'])
                            except Exception as e:
                                pass
                            pool_name = None
                            if 'pool_id' in each_pool:
                                pool_name = each_pool['pool_id']
                            elif 'text' in each_pool:
                                pool_name = each_pool['text']
                            if pool_name is None:
                                pool_name = each_pool['url'].replace("https://", "").replace("http://", "").replace("www", "")
                            pool_links += "#{}. [{}]({}) - {}\n".format(i, pool_name, each_pool['url'], hash_rate if hash_rate else '0H/s')
                            i += 1
                    try:
                        embed.add_field(name="Pool List", value=pool_links)
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                embed.add_field(name="OTHER LINKS", value="{} / {} / {} / {}".format("[More pools](https://miningpoolstats.stream/{})".format(COIN_NAME.lower()), "[Invite TipBot](http://invite.discord.bot.tips)", "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
                embed.set_footer(text="Data from https://miningpoolstats.stream")
                try:
                    msg = await ctx.send(embed=embed)
                    respond_date = int(time.time())
                    await store.sql_miningpoolstat_fetch(COIN_NAME, str(ctx.message.author.id), 
                                                        '{}#{}'.format(ctx.message.author.name, ctx.message.author.discriminator), 
                                                        requested_date, respond_date, json.dumps(get_pool_data), str(ctx.guild.id) if isinstance(ctx.channel, discord.DMChannel) == False else 'DM', 
                                                        ctx.guild.name if isinstance(ctx.channel, discord.DMChannel) == False else 'DM', 
                                                        str(ctx.message.channel.id), is_cache, 'DISCORD', 'NO')
                    # sleep 3s
                    await asyncio.sleep(3)
                    await msg.add_reaction(EMOJI_OK_BOX)
                except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                    await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                    await logchanbot(traceback.format_exc())
            except Exception as e:
                await logchanbot(traceback.format_exc())
            if ctx.message.author.id in MINGPOOLSTAT_IN_PROCESS:
                MINGPOOLSTAT_IN_PROCESS.remove(ctx.message.author.id)
        else:
            # Try old way
            # if not exist, add to queue in redis
            key_queue = "TIPBOT:MININGPOOL2:QUEUE"
            if redis_conn and redis_conn.llen(key_queue) > 0:
                list_coin_queue = redis_conn.lrange(key_queue, 0, -1)
                if COIN_NAME not in list_coin_queue:
                    redis_conn.lpush(key_queue, COIN_NAME)
            elif redis_conn and redis_conn.llen(key_queue) == 0:
                redis_conn.lpush(key_queue, COIN_NAME)
            try:
                async with ctx.typing():
                    # loop and waiting for another fetch
                    retry = 0
                    await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
                    while True:
                        key = "TIPBOT:MININGPOOL2:" + COIN_NAME
                        key_p = key + ":POOLS" # TIPBOT:MININGPOOL2:COIN_NAME:POOLS
                        await asyncio.sleep(5)
                        if redis_conn and redis_conn.exists(key_p):
                            result = json.loads(redis_conn.get(key_p).decode())
                            is_cache = 'NO'
                            try:
                                embed = discord.Embed(title='Mining Pools for {}'.format(COIN_NAME), description='', timestamp=datetime.utcnow(), colour=7047495)
                                i = 0
                                if result and len(result) > 0:
                                    pool_links = ''
                                    hash_rate = ''
                                    for each in result:
                                        if i < 15 and i < len(result):
                                            if len(each) >= 4:
                                                hash_list = ['H/s', 'KH/s', 'MH/s', 'GH/s', 'TH/s', 'PH/s', 'EH/s']
                                                if [ele for ele in hash_list if((ele in each[2]) and ('Hashrate' not in each[2]))]:
                                                    hash_rate = each[2]
                                                elif [ele for ele in hash_list if((ele in each[3]) and ('Hashrate' not in each[3]))]:
                                                    hash_rate = each[3]
                                                else:
                                                    hash_rate = ''
                                                if hash_rate == '' and len(each) >= 5 and [ele for ele in hash_list if((ele in each[4]) and ('Hashrate' not in each[4]))]:
                                                    hash_rate = each[4]
                                                elif hash_rate == '' and len(each) >= 6 and [ele for ele in hash_list if((ele in each[5]) and ('Hashrate' not in each[5]))]:
                                                    hash_rate = each[5]
                                                elif hash_rate == '' and len(each) >= 7 and [ele for ele in hash_list if((ele in each[6]) and ('Hashrate' not in each[6]))]:
                                                    hash_rate = each[6]
                                                pool_links += each[0] + ' ' + each[1] + ' ' + hash_rate + '\n'
                                            else:
                                                pool_links += each[0] + ' ' + each[1] + '\n'
                                            i += 1
                                    try:
                                        embed.add_field(name="List", value=pool_links)
                                    except Exception as e:
                                        await logchanbot(traceback.format_exc())
                                embed.add_field(name="OTHER LINKS", value="{} / {} / {} / {}".format("[More pools](https://miningpoolstats.stream/{})".format(COIN_NAME.lower()), "[Invite TipBot](http://invite.discord.bot.tips)", "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
                                embed.set_footer(text="Data from https://miningpoolstats.stream")
                                msg = await ctx.send(embed=embed)
                                respond_date = int(time.time())
                                await store.sql_miningpoolstat_fetch(COIN_NAME, str(ctx.message.author.id), 
                                                                    '{}#{}'.format(ctx.message.author.name, ctx.message.author.discriminator), 
                                                                    requested_date, respond_date, json.dumps(result), str(ctx.guild.id) if isinstance(ctx.channel, discord.DMChannel) == False else 'DM', 
                                                                    ctx.guild.name if isinstance(ctx.channel, discord.DMChannel) == False else 'DM', 
                                                                    str(ctx.message.channel.id), is_cache, 'DISCORD', 'YES')
                                # sleep 3s
                                await msg.add_reaction(EMOJI_OK_BOX)
                                await ctx.message.add_reaction(EMOJI_OK_HAND)
                                break
                                if ctx.message.author.id in MINGPOOLSTAT_IN_PROCESS:
                                    MINGPOOLSTAT_IN_PROCESS.remove(ctx.message.author.id)
                                return
                            except Exception as e:
                                await ctx.message.add_reaction(EMOJI_ERROR)
                                await logchanbot(traceback.format_exc())
                                if ctx.message.author.id in MINGPOOLSTAT_IN_PROCESS:
                                    MINGPOOLSTAT_IN_PROCESS.remove(ctx.message.author.id)
                                return
                        elif redis_conn and not redis_conn.exists(key_p):
                            retry += 1
                        if retry >= 5:
                            redis_conn.lrem(key_queue, 0, COIN_NAME)
                            await ctx.message.add_reaction(EMOJI_ERROR)
                            await ctx.send(f'{ctx.author.mention} We can not fetch data for **{COIN_NAME}**.')
                            break
                            if ctx.message.author.id in MINGPOOLSTAT_IN_PROCESS:
                                MINGPOOLSTAT_IN_PROCESS.remove(ctx.message.author.id)
                            return
            except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                if ctx.message.author.id in MINGPOOLSTAT_IN_PROCESS:
                    MINGPOOLSTAT_IN_PROCESS.remove(ctx.message.author.id)
                await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                return
            except Exception as e:
                await logchanbot(traceback.format_exc())
    if ctx.message.author.id in MINGPOOLSTAT_IN_PROCESS:
        MINGPOOLSTAT_IN_PROCESS.remove(ctx.message.author.id)
    return


@bot.command(pass_context=True, name='info', help=bot_help_info)
async def info(ctx, coin: str = None):
    global LIST_IGNORECHAN, MUTE_CHANNEL
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'info')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    # Check if maintenance
    if IS_MAINTENANCE == 1:
        if int(ctx.message.author.id) in MAINTENANCE_OWNER:
            await ctx.message.add_reaction(EMOJI_MAINTENANCE)
            pass
        else:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {config.maintenance_msg}')
            return
    else:
        pass
    # End Check if maintenance

    wallet = None
    COIN_NAME = None
    if coin is None:
        if len(ctx.message.mentions) == 0:
            cmdName = ctx.message.content
        else:
            cmdName = ctx.message.content.split(" ")[0]
        cmdName = cmdName[1:]

        if cmdName.lower() not in ['wallet', 'info']:
            cmdName = ctx.message.content.split(" ")[1]
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} This command can not be in DM. If you want to deposit, use **DEPOSIT** command instead.')
            return
        else:
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            prefix = config.discord.prefixCmd
            server_coin = DEFAULT_TICKER
            server_tiponly = "ALLCOIN"
            react_tip_value = "N/A"
            if serverinfo is None:
                # Let's add some info if server return None
                add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id),
                                                                    ctx.message.guild.name, config.discord.prefixCmd, "WRKZ")
            else:
                prefix = serverinfo['prefix']
                server_coin = serverinfo['default_coin'].upper()
                server_tiponly = serverinfo['tiponly'].upper()
                if serverinfo['react_tip'].upper() == "ON":
                    COIN_NAME = serverinfo['default_coin'].upper()
                    react_tip_value = str(serverinfo['react_tip_100']) + COIN_NAME
            try:
                MUTE_CHANNEL = await store.sql_list_mutechan()
                LIST_IGNORECHAN = await store.sql_listignorechan()
                chanel_ignore_list = ''
                if LIST_IGNORECHAN and str(ctx.guild.id) in LIST_IGNORECHAN:
                    for item in LIST_IGNORECHAN[str(ctx.guild.id)]:
                        try:
                            chanel_ignore = bot.get_channel(id=int(item))
                            chanel_ignore_list += '#'  + chanel_ignore.name + ' '
                        except Exception as e:
                            pass
                if chanel_ignore_list == '': chanel_ignore_list = 'N/A'

                chanel_mute_list = ''
                if MUTE_CHANNEL and str(ctx.guild.id) in MUTE_CHANNEL:
                    for item in MUTE_CHANNEL[str(ctx.guild.id)]:
                        try:
                            chanel_mute = bot.get_channel(id=int(item))
                            chanel_mute_list += '#'  + chanel_mute.name + ' '
                        except Exception as e:
                            pass
                if chanel_mute_list == '': chanel_mute_list = 'N/A'
            except Exception as e:
                await logchanbot(traceback.format_exc())
            extra_text = f'Type: {prefix}setting or {prefix}help setting for more info. (Required permission)'
            try:
                embed = discord.Embed(title=f'Guild {ctx.guild.id} / {ctx.guild.name}', timestamp=datetime.utcnow())
                embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
                embed.add_field(name="Default Ticker", value=f'`{server_coin}`', inline=True)
                embed.add_field(name="Default Prefix", value=f'`{prefix}`', inline=True)
                embed.add_field(name="TipOnly Coins", value=f'`{server_tiponly}`', inline=True)
                embed.add_field(name=f"Re-act Tip {EMOJI_TIP}", value=f'`{react_tip_value}`', inline=True)
                embed.add_field(name="Ignored Tip", value=f'`{chanel_ignore_list}`', inline=True)
                embed.add_field(name="Mute in", value=f'`{chanel_mute_list}`', inline=True)
                embed.set_footer(text=f"{extra_text}")
                msg = await ctx.send(embed=embed)
                await msg.add_reaction(EMOJI_OK_BOX)
                await ctx.message.add_reaction(EMOJI_OK_HAND)
            except (discord.errors.NotFound, discord.errors.Forbidden, Exception) as e:
                msg = await ctx.send(
                    '\n```'
                    f'Server ID:      {ctx.guild.id}\n'
                    f'Server Name:    {ctx.message.guild.name}\n'
                    f'Default Ticker: {server_coin}\n'
                    f'Default Prefix: {prefix}\n'
                    f'TipOnly Coins:  {server_tiponly}\n'
                    f'Re-act Tip:     {react_tip_value}\n'
                    f'Ignored Tip in: {chanel_ignore_list}\n'
                    f'Mute in:        {chanel_mute_list}\n'
                    f'```{extra_text}')
                await msg.add_reaction(EMOJI_OK_BOX)
                await ctx.message.add_reaction(EMOJI_OK_HAND)
            return
    else:
        COIN_NAME = coin.upper()
        pass

    if COIN_NAME:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please use **DEPOSIT** command instead.')
        return


@bot.command(pass_context=True, name='coinmap', aliases=['coin360', 'c360', 'cmap'], help='')
async def coinmap(ctx):
    global TRTL_DISCORD
    if isinstance(ctx.channel, discord.DMChannel) == False and ctx.guild.id == TRTL_DISCORD:
        return

    async with ctx.typing():
        try:
            map_image = await bot.loop.run_in_executor(None, coin360.get_coin360)
            if map_image:
                msg = await ctx.send(f'{config.coin360.static_coin360_link + map_image}')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
            else:
                msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Internal error during fetch image.')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
        except Exception as e:
            await logchanbot(traceback.format_exc())


@bot.command(pass_context=True, name='coininfo', aliases=['coinf_info', 'coin'], help=bot_help_coininfo)
async def coininfo(ctx, coin: str = None):
    global TRTL_DISCORD
    if coin is None:
        if isinstance(ctx.channel, discord.DMChannel) == False and ctx.guild.id == TRTL_DISCORD:
            return
        table_data = [
            ["TICKER", "Height", "Tip", "Wdraw", "Depth"]
            ]
        for COIN_NAME in [coinItem.upper() for coinItem in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC]:
            height = None
            if COIN_NAME in ENABLE_COIN_ERC:
                token_info = await store.get_token_info(COIN_NAME)
                confim_depth = token_info['deposit_confirm_depth']
            else:
                confim_depth = get_confirm_depth(COIN_NAME)
            try:
                openRedis()
                if redis_conn and redis_conn.exists(f'TIPBOT:DAEMON_HEIGHT_{COIN_NAME}'):
                    height = int(redis_conn.get(f'TIPBOT:DAEMON_HEIGHT_{COIN_NAME}'))
                    if not is_maintenance_coin(COIN_NAME):
                        table_data.append([COIN_NAME,  '{:,.0f}'.format(height), "ON" if is_coin_tipable(COIN_NAME) else "OFF"\
                        , "ON" if is_coin_txable(COIN_NAME) else "OFF"\
                        , confim_depth])
                    else:
                        table_data.append([COIN_NAME, "***", "***", "***", confim_depth])
            except Exception as e:
                await logchanbot(traceback.format_exc())

        table = AsciiTable(table_data)
        table.padding_left = 0
        table.padding_right = 0
        msg = await ctx.send('**[ TIPBOT COIN LIST ]**\n'
                             f'```{table.table}```')
        
        return
    else:
        COIN_NAME = coin.upper()
        if COIN_NAME in ENABLE_COIN_ERC:
            token_info = await store.get_token_info(COIN_NAME)
            confim_depth = token_info['deposit_confirm_depth']
            Min_Tip = token_info['real_min_tip']
            Max_Tip = token_info['real_max_tip']
            Min_Tx = token_info['real_min_tx']
            Max_Tx = token_info['real_max_tx']
        elif COIN_NAME in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO:
            confim_depth = get_confirm_depth(COIN_NAME)
            Min_Tip = get_min_mv_amount(COIN_NAME)
            Max_Tip = get_max_mv_amount(COIN_NAME)
            Min_Tx = get_min_tx_amount(COIN_NAME)
            Max_Tx = get_max_tx_amount(COIN_NAME)
        if COIN_NAME not in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC:
            await ctx.message.author.send(f'{ctx.author.mention} **{COIN_NAME}** is not in our list.')
            return
        else:
            response_text = "**[ COIN INFO {} ]**".format(COIN_NAME)
            response_text += "```"
            try:
                openRedis()
                if redis_conn and redis_conn.exists(f'TIPBOT:DAEMON_HEIGHT_{COIN_NAME}'):
                    height = int(redis_conn.get(f'TIPBOT:DAEMON_HEIGHT_{COIN_NAME}'))
                    response_text += "Height: {:,.0f}".format(height) + "\n"
                response_text += "Confirmation: {} Blocks".format(confim_depth) + "\n"
                if is_coin_tipable(COIN_NAME): 
                    response_text += "Tipping: ON\n"
                else:
                    response_text += "Tipping: OFF\n"
                if is_coin_depositable(COIN_NAME): 
                    response_text += "Deposit: ON\n"
                else:
                    response_text += "Deposit: OFF\n"
                if isinstance(ctx.channel, discord.DMChannel) == True:
                    if COIN_NAME in ENABLE_TRADE_COIN and is_tradeable_coin(COIN_NAME): 
                        response_text += "Trade: ON\n"
                        response_text += f"Trade Min/Max: {num_format_coin(get_min_sell(COIN_NAME), COIN_NAME)}{COIN_NAME} / {num_format_coin(get_max_sell(COIN_NAME), COIN_NAME)}{COIN_NAME}\n"
                elif isinstance(ctx.channel, discord.DMChannel) == False and COIN_NAME in ENABLE_TRADE_COIN and is_tradeable_coin(COIN_NAME):
                    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
                    if 'enable_trade' in serverinfo and serverinfo['enable_trade'] == "YES":
                        response_text += "Trade: ON\n"
                        response_text += f"Trade Min/Max: {num_format_coin(get_min_sell(COIN_NAME), COIN_NAME)}{COIN_NAME} / {num_format_coin(get_max_sell(COIN_NAME), COIN_NAME)}{COIN_NAME}\n"
                if is_coin_txable(COIN_NAME): 
                    response_text += "Withdraw: ON\n"
                else:
                    response_text += "Withdraw: OFF\n"
                if COIN_NAME in FEE_PER_BYTE_COIN + ENABLE_COIN_DOGE:
                    response_text += "Reserved Fee: {}{}\n".format(num_format_coin(get_reserved_fee(COIN_NAME), COIN_NAME), COIN_NAME)
                elif COIN_NAME in ENABLE_XMR:
                    response_text += "Withdraw Tx Fee: Dynamic\n"
                elif COIN_NAME in ENABLE_COIN_ERC:
                    if token_info['contract'] and len(token_info['contract']) == 42:
                        response_text += "Contract:\n   {}\n".format(token_info['contract'])
                    response_text += "Withdraw Tx Fee: {}{}\n".format(num_format_coin(token_info['real_withdraw_fee'], COIN_NAME), COIN_NAME)
                    if token_info['real_deposit_fee'] and token_info['real_deposit_fee'] > 0:
                        response_text += "Deposit Tx Fee: {}{}\n".format(num_format_coin(token_info['real_deposit_fee'], COIN_NAME), COIN_NAME)
                elif COIN_NAME in ENABLE_COIN_NANO:
                    # nothing
                    response_text += "Withdraw Tx Fee: Zero\n"
                else:
                    response_text += "Withdraw Tx Fee: {}{}\n".format(num_format_coin(get_tx_fee(COIN_NAME), COIN_NAME), COIN_NAME)
                get_tip_min_max = "Tip Min/Max:\n   " + num_format_coin(Min_Tip, COIN_NAME) + " / " + num_format_coin(Max_Tip, COIN_NAME) + COIN_NAME
                response_text += get_tip_min_max + "\n"
                get_tx_min_max = "Withdraw Min/Max:\n   " + num_format_coin(Min_Tx, COIN_NAME) + " / " + num_format_coin(Max_Tx, COIN_NAME) + COIN_NAME
                response_text += get_tx_min_max
                if COIN_NAME in ENABLE_COIN_ERC and token_info['coininfo_note']:
                    response_text += "\nNote:\n   {}\n".format(token_info['coininfo_note'])
            except Exception as e:
                await logchanbot(traceback.format_exc())
            response_text += "```"
            await ctx.send(response_text)
            return


@bot.command(pass_context=True, name='balance', aliases=['bal'], help=bot_help_balance)
async def balance(ctx, coin: str = None):
    prefix = await get_guild_prefix(ctx)
    botLogChan = bot.get_channel(id=LOG_CHAN)
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'balance')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    PUBMSG = ctx.message.content.strip().split(" ")[-1].upper()

    # Get wallet status
    walletStatus = None
    COIN_NAME = None
    embed = discord.Embed(title='[ YOUR BALANCE LIST ]', timestamp=datetime.utcnow())
    if (coin is None) or (PUBMSG == "PUB") or (PUBMSG == "PUBLIC") or (PUBMSG == "LIST"):
        table_data = [
            ['TICKER', 'Available', 'Tx']
        ]
        table_data_str = []
        for COIN_NAME in [coinItem.upper() for coinItem in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC]:
            if not is_maintenance_coin(COIN_NAME):
                wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
                if wallet is None:
                    if COIN_NAME in ENABLE_COIN_ERC:
                        w = await create_address_eth()
                        userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0, w)
                    else:
                        userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)
                    wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
                if wallet is None:
                    if coin: table_data.append([COIN_NAME, "N/A", "N/A"])
                    await botLogChan.send(f'A user call `{prefix}balance` failed with {COIN_NAME}')
                else:
                    userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), COIN_NAME)
                    xfer_in = 0
                    if COIN_NAME not in ENABLE_COIN_ERC:
                        xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.message.author.id), COIN_NAME)
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
                            msg_negative = 'Negative balance detected:\nUser: '+str(ctx.message.author.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                            await logchanbot(msg_negative)
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                    balance_actual = num_format_coin(actual_balance, COIN_NAME)
                    coinName = COIN_NAME
                    if actual_balance != 0:
                        if coin:
                            table_data.append([coinName, balance_actual, "YES" if is_coin_txable(COIN_NAME) else "NO"])
                        else:
                            if actual_balance > 0:
                                table_data_str.append("{}{}".format(balance_actual, coinName))
                                embed.add_field(name=COIN_NAME, value=balance_actual+COIN_NAME, inline=True)
                    pass
            else:
                if coin: table_data.append([COIN_NAME, "***", "***"])
        table = AsciiTable(table_data)
        # table.inner_column_border = False
        # table.outer_border = False
        table.padding_left = 0
        table.padding_right = 0
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        if coin is None:
            # table_data_str = ", ".join(table_data_str)
            embed.add_field(name='Related commands', value=f'`{prefix}balance TICKER` or `{prefix}deposit TICKER` or `{prefix}balance LIST`', inline=False)
            try:
                msg = await ctx.message.author.send(embed=embed)
            except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                return
        else:
            if PUBMSG.upper() == "PUB" or PUBMSG.upper() == "PUBLIC":
                msg = await ctx.send('**[ BALANCE LIST ]**\n'
                                f'```{table.table}```'
                                f'Related command: `{prefix}balance TICKER` or `{prefix}deposit TICKER`\n`***`: On Maintenance\n')
            else:
                msg = await ctx.message.author.send('**[ BALANCE LIST ]**\n'
                                f'```{table.table}```'
                                f'Related command: `{prefix}balance TICKER` or `{prefix}deposit TICKER`\n`***`: On Maintenance\n'
                                f'{get_notice_txt(COIN_NAME)}')
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME not in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
        return

    if is_maintenance_coin(COIN_NAME) and ctx.message.author.id not in MAINTENANCE_OWNER:
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        msg = await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} in maintenance.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    if COIN_NAME in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC:
        wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if wallet is None:
            if COIN_NAME in ENABLE_COIN_ERC:
                w = await create_address_eth()
                userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0, w)
            else:
                userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if COIN_NAME in ENABLE_COIN_ERC:
            token_info = await store.get_token_info(COIN_NAME)
            deposit_balance = await store.http_wallet_getbalance(wallet['balance_wallet_address'], COIN_NAME)
            real_deposit_balance = round(deposit_balance / 10**token_info['token_decimal'], 6)
        userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), COIN_NAME, 'DISCORD')
        if COIN_NAME in ENABLE_COIN_ERC:
            xfer_in = wallet['real_actual_balance']
        else:
            xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.message.author.id), COIN_NAME)
        if COIN_NAME in ENABLE_COIN_DOGE:
            actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
        elif COIN_NAME in ENABLE_COIN_NANO:
            actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
            actual_balance = round(actual_balance / get_decimal(COIN_NAME), 6) * get_decimal(COIN_NAME)
        if COIN_NAME in ENABLE_COIN_ERC:
            actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
        else:
            actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])

        # Negative check
        try:
            if actual_balance < 0:
                msg_negative = 'Negative balance detected:\nUser: '+str(ctx.message.author.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                await logchanbot(msg_negative)
        except Exception as e:
            await logchanbot(traceback.format_exc())

        balance_actual = num_format_coin(actual_balance, COIN_NAME)
        locked_openorder = userdata_balance['OpenOrder']
        embed = discord.Embed(title=f'[ {ctx.author.name}#{ctx.author.discriminator}\'s {COIN_NAME} balance ]', timestamp=datetime.utcnow())
        if COIN_NAME in ENABLE_COIN_ERC:
            embed.add_field(name="Deposited", value="`{}{}`".format(num_format_coin(real_deposit_balance, COIN_NAME), COIN_NAME), inline=True)
        embed.add_field(name="Spendable", value=balance_actual+COIN_NAME, inline=True)
        if locked_openorder > 0 and COIN_NAME not in ENABLE_COIN_ERC:
            embed.add_field(name="Opened Order", value=num_format_coin(locked_openorder, COIN_NAME)+COIN_NAME, inline=True)
            embed.add_field(name="Total", value=num_format_coin(actual_balance+locked_openorder, COIN_NAME)+COIN_NAME, inline=True)
        elif locked_openorder > 0 and COIN_NAME in ENABLE_COIN_ERC:
            embed.add_field(name="Opened Order", value=num_format_coin(locked_openorder, COIN_NAME)+COIN_NAME, inline=True)
            embed.add_field(name="Total", value=num_format_coin(actual_balance+locked_openorder+real_deposit_balance, COIN_NAME)+COIN_NAME, inline=True)
        elif locked_openorder == 0 and COIN_NAME in ENABLE_COIN_ERC:
            embed.add_field(name="Total", value=num_format_coin(actual_balance+real_deposit_balance, COIN_NAME)+COIN_NAME, inline=True)
        embed.add_field(name='Related commands', value=f'`{prefix}balance` or `{prefix}deposit {COIN_NAME}` or `{prefix}balance LIST`', inline=False)
        if COIN_NAME in ENABLE_COIN_ERC:
            min_deposit_txt = " Min. deposit for moving to spendable: " + num_format_coin(token_info['min_move_deposit'], COIN_NAME) + COIN_NAME
            embed.set_footer(text=f"{token_info['deposit_note'] + min_deposit_txt}")
        else:
            embed.set_footer(text=f"{get_notice_txt(COIN_NAME)}")
        try:
            msg = await ctx.message.author.send(embed=embed)
            await ctx.message.add_reaction(EMOJI_OK_HAND)
            await msg.add_reaction(EMOJI_OK_BOX)
        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            try:
                msg = await ctx.send(embed=embed)
                await ctx.message.add_reaction(EMOJI_OK_HAND)
                await msg.add_reaction(EMOJI_OK_BOX)
            except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
            return
    else:
        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is no such ticker {COIN_NAME}.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return


@bot.command(pass_context=True, name='mbalance', aliases=['mbal'])
async def mbalance(ctx, coin: str = None):
    prefix = await get_guild_prefix(ctx)
    botLogChan = bot.get_channel(id=LOG_CHAN)
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'mbalance')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    # disable guild tip for TRTL discord
    if ctx.guild and ctx.guild.id == TRTL_DISCORD:
        await ctx.message.add_reaction(EMOJI_LOCKED)
        return

    # If DM, error
    if isinstance(ctx.message.channel, discord.DMChannel) == True:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} This command is available only in public channel (Guild).')
        await ctx.message.add_reaction(EMOJI_ERROR)
        return

    COIN_NAME = None
    embed = discord.Embed(title=f'[ GUILD {ctx.guild.name} BALANCE ]', timestamp=datetime.utcnow())
    any_balance = 0
    if coin is None:
        for COIN_NAME in [coinItem.upper() for coinItem in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC]:
            if not is_maintenance_coin(COIN_NAME):
                wallet = await store.sql_get_userwallet(str(ctx.guild.id), COIN_NAME)
                if wallet is None:
                    if COIN_NAME in ENABLE_COIN_ERC:
                        w = await create_address_eth()
                        userregister = await store.sql_register_user(str(ctx.guild.id), COIN_NAME, 'DISCORD', 0, w)
                    else:
                        userregister = await store.sql_register_user(str(ctx.guild.id), COIN_NAME, 'DISCORD', 0)
                    wallet = await store.sql_get_userwallet(str(ctx.guild.id), COIN_NAME)
                if wallet is None:
                    await botLogChan.send(f'A user call `{prefix}mbalance` failed with {COIN_NAME} in guild {ctx.guild.id} / {ctx.guild.name} / # {ctx.message.channel.name} ')
                    return
                else:
                    userdata_balance = await store.sql_user_balance(str(ctx.guild.id), COIN_NAME)
                    xfer_in = 0
                    if COIN_NAME not in ENABLE_COIN_ERC:
                        xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.guild.id), COIN_NAME)
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
                            msg_negative = 'Negative balance detected:\nGuild: '+str(ctx.guild.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                            await logchanbot(msg_negative)
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                    balance_actual = num_format_coin(actual_balance, COIN_NAME)
                    coinName = COIN_NAME
                    if actual_balance > 0:
                        any_balance += 1
                        embed.add_field(name=COIN_NAME, value=balance_actual+COIN_NAME, inline=True)
        if any_balance == 0:
            embed.add_field(name="INFO", value='`This guild has no balance for any coin yet.`', inline=True)
        embed.add_field(name='Related commands', value=f'`{prefix}mbalance TICKER` or `{prefix}mdeposit TICKER`', inline=False)
        embed.set_footer(text=f"Guild balance requested by {ctx.message.author.name}#{ctx.message.author.discriminator}")
        try:
            msg = await ctx.send(embed=embed)
            await msg.add_reaction(EMOJI_OK_BOX)
        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
        return
    else:
        COIN_NAME = coin.upper()

    if COIN_NAME not in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
        return

    try:
        if COIN_NAME in ENABLE_COIN_ERC:
            coin_family = "ERC-20"
        else:
            coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    except Exception as e:
        await logchanbot(traceback.format_exc())
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**')
        return

    if is_maintenance_coin(COIN_NAME) and ctx.message.author.id not in MAINTENANCE_OWNER:
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        msg = await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} in maintenance.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    if COIN_NAME in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC:
        wallet = await store.sql_get_userwallet(str(ctx.guild.id), COIN_NAME)
        if wallet is None:
            if COIN_NAME in ENABLE_COIN_ERC:
                w = await create_address_eth()
                userregister = await store.sql_register_user(str(ctx.guild.id), COIN_NAME, 'DISCORD', 0, w)
            else:
                userregister = await store.sql_register_user(str(ctx.guild.id), COIN_NAME, 'DISCORD', 0)
        userdata_balance = await store.sql_user_balance(str(ctx.guild.id), COIN_NAME)
        xfer_in = 0
        if COIN_NAME not in ENABLE_COIN_ERC:
            xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.guild.id), COIN_NAME)
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
                msg_negative = 'Negative balance detected:\nGuild: '+str(ctx.guild.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                await logchanbot(msg_negative)
        except Exception as e:
            await logchanbot(traceback.format_exc())

        balance_actual = num_format_coin(actual_balance, COIN_NAME)
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        msg = await ctx.send(f'**[GUILD {ctx.guild.name} - {COIN_NAME} BALANCE ]**\n\n'
                f'{EMOJI_MONEYBAG} Available: {balance_actual} '
                f'{COIN_NAME}\n'
                f'{get_notice_txt(COIN_NAME)}')
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    else:
        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is no such ticker {COIN_NAME}.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return


@bot.command(pass_context=True, aliases=['botbal'], help=bot_help_botbalance)
async def botbalance(ctx, member: discord.Member, coin: str):
    global TRTL_DISCORD

    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} This command can not be in DM.')
        return
        
    # if public and there is a bot channel
    if isinstance(ctx.channel, discord.DMChannel) == False:
        serverinfo = await get_info_pref_coin(ctx)
        server_prefix = serverinfo['server_prefix']
        # check if bot channel is set:
        if serverinfo and serverinfo['botchan']:
            try: 
                if ctx.channel.id != int(serverinfo['botchan']):
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    botChan = bot.get_channel(id=int(serverinfo['botchan']))
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, {botChan.mention} is the bot channel!!!')
                    return
            except ValueError:
                pass
        # end of bot channel check

    if member.bot == False:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Only for bot!!')
        return

    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER {COIN_NAME}**!')
        return

    # TRTL discord
    if ctx.guild.id == TRTL_DISCORD and COIN_NAME != "TRTL":
        return

    if is_maintenance_coin(COIN_NAME):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
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

    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if COIN_NAME in ENABLE_COIN+ENABLE_XMR+ENABLE_COIN_DOGE+ENABLE_COIN_NANO+ENABLE_COIN_ERC:
        try:
            userwallet = await store.sql_get_userwallet(str(member.id), COIN_NAME)
            if userwallet is None:
                if coin_family == "ERC-20":
                    w = await create_address_eth()
                    userregister = await store.sql_register_user(str(member.id), COIN_NAME, 'DISCORD', 0, w)
                else:
                    userregister = await store.sql_register_user(str(member.id), COIN_NAME, 'DISCORD', 0)
                userwallet = await store.sql_get_userwallet(str(member.id), COIN_NAME)
            depositAddress = userwallet['balance_wallet_address']
        except Exception as e:
            await logchanbot(traceback.format_exc())
        
        actual = int(userwallet['actual_balance'])
        balance_actual = "0.00"

        userdata_balance = await store.sql_user_balance(str(member.id), COIN_NAME)
        xfer_in = 0
        if COIN_NAME not in ENABLE_COIN_ERC:
            xfer_in = await store.sql_user_balance_get_xfer_in(str(member.id), COIN_NAME)
        if COIN_NAME in ENABLE_COIN_DOGE+ENABLE_COIN_ERC:
            actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
        elif COIN_NAME in ENABLE_COIN_NANO:
            actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
            actual_balance = round(actual_balance / get_decimal(COIN_NAME), 6) * get_decimal(COIN_NAME)
        else:
            actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
        balance_actual = num_format_coin(actual_balance, COIN_NAME)

        # Negative check
        try:
            if actual_balance < 0:
                msg_negative = 'Negative balance detected:\nBot User: '+str(member.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                await logchanbot(msg_negative)
        except Exception as e:
            await logchanbot(traceback.format_exc())

        embed = discord.Embed(title=f'Deposit for {member.name}#{member.discriminator}', description='`This is bot\'s tipjar address. Do not deposit here unless you want to deposit to this bot`', timestamp=datetime.utcnow(), colour=7047495)
        embed.set_author(name=member.name, icon_url=member.avatar_url)
        embed.add_field(name="Deposit Address", value="`{}`".format(userwallet['balance_wallet_address']), inline=False)
        embed.add_field(name=f"Balance {COIN_NAME}", value="`{}{}`".format(balance_actual, COIN_NAME), inline=False)
        try:
            msg = await ctx.send(embed=embed)
            await msg.add_reaction(EMOJI_OK_BOX)
            await ctx.message.add_reaction(EMOJI_OK_HAND)
        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            msg = await ctx.send(
                    f'**[ <@{member.id}> BALANCE]**\n'
                    f' Deposit Address: `{depositAddress}`\n'
                    f'{EMOJI_MONEYBAG} Available: {balance_actual} '
                    f'{COIN_NAME}\n'
                    '**This is bot\'s tipjar address. Do not deposit here unless you want to deposit to this bot.**')
            await msg.add_reaction(EMOJI_OK_BOX)
            await ctx.message.add_reaction(EMOJI_OK_HAND)
        return


@bot.command(pass_context=True, name='register', aliases=['registerwallet', 'reg', 'updatewallet'],
             help=bot_help_register)
async def register(ctx, wallet_address: str, coin: str=None):
    global IS_RESTARTING
    # check if bot is going to restart
    if IS_RESTARTING:
        await ctx.message.add_reaction(EMOJI_REFRESH)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
        return

    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'register')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

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

    # if public and there is a bot channel
    if isinstance(ctx.channel, discord.DMChannel) == False:
        serverinfo = await get_info_pref_coin(ctx)
        server_prefix = serverinfo['server_prefix']
        # check if bot channel is set:
        if serverinfo and serverinfo['botchan']:
            try: 
                if ctx.channel.id != int(serverinfo['botchan']):
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    botChan = bot.get_channel(id=int(serverinfo['botchan']))
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, {botChan.mention} is the bot channel!!!')
                    return
            except ValueError:
                pass
        # end of bot channel check

    if not re.match(r'^[A-Za-z0-9_]+$', wallet_address):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                       f'`{wallet_address}`')
        return

    COIN_NAME = get_cn_coin_from_address(wallet_address)
    if COIN_NAME:
        pass
    else:
        if wallet_address.startswith("0x"):
            if wallet_address.upper().startswith("0X00000000000000000000000000000"):
                await ctx.message.add_reaction(EMOJI_ERROR)
                msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid token:\n'
                                     f'`{wallet_address}`')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
            if coin is None:
                await ctx.message.add_reaction(EMOJI_WARNING)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} you need to add **TOKEN NAME** address.')
                return
            else:
                COIN_NAME = coin.upper()
                if COIN_NAME not in ENABLE_COIN_ERC:
                    await ctx.message.add_reaction(EMOJI_WARNING)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Unsupported Token.')
                    return
                else:
                    # validate
                    valid_address = await store.erc_validate_address(wallet_address, COIN_NAME)
                    valid = False
                    if valid_address and valid_address.upper() == wallet_address.upper():
                        valid = True
                    else:
                        await ctx.message.add_reaction(EMOJI_ERROR)
                        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid token address:\n'
                                             f'`{wallet_address}`')
                        await msg.add_reaction(EMOJI_OK_BOX)
                        return
        else:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Unknown Ticker.')
            return
    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    if is_maintenance_coin(COIN_NAME):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return

    if coin_family in ["TRTL", "BCN", "XMR", "NANO"]:
        main_address = getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
        if wallet_address == main_address:
            await ctx.message.add_reaction(EMOJI_QUESTEXCLAIM)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} do not register with main address. You could lose your coin when withdraw.')
            return
    elif coin_family == "ERC-20":
        # Check if register address in any of user balance address
        check_in_balance_users = await store.erc_check_balance_address_in_users(wallet_address, COIN_NAME)
        if check_in_balance_users:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You can not register with any of user\'s tipjar\'s token address.\n'
                                 f'`{wallet_address}`')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

    user = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    if user is None:
        if coin_family == "ERC-20":
            w = await create_address_eth()
            userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0, w)
        else:
            userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)
        user = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)

    existing_user = user

    valid_address = None
    if COIN_NAME in ENABLE_COIN_DOGE:
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if user_from is None:
            user_from = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)
            user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        user_from['address'] = user_from['balance_wallet_address']
        if COIN_NAME in ENABLE_COIN_DOGE:
            valid_address = await doge_validaddress(str(wallet_address), COIN_NAME)
            if ('isvalid' in valid_address):
                if str(valid_address['isvalid']) == "True":
                    valid_address = wallet_address
                else:
                    valid_address = None
                pass
            pass
    elif COIN_NAME in ENABLE_COIN_ERC:
        # already validated above
        pass
    else:
        if coin_family in ["TRTL", "BCN"]:
            valid_address = addressvalidation.validate_address_cn(wallet_address, COIN_NAME)
        elif coin_family in ["NANO"]:
            valid_address = await nano_validate_address(COIN_NAME, wallet_address)
            if valid_address == True:
                valid_address = wallet_address
        elif coin_family == "XMR":
            if COIN_NAME not in ["MSR", "UPX", "XAM"]:
                valid_address = await validate_address_xmr(str(wallet_address), COIN_NAME)
                if valid_address is None:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                                   f'`{wallet_address}`')
                if valid_address['valid'] == True and valid_address['integrated'] == False \
                    and valid_address['subaddress'] == False and valid_address['nettype'] == 'mainnet':
                    # re-value valid_address
                    valid_address = str(wallet_address)
                else:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please use {COIN_NAME} main address.')
                    return
            else:
                if COIN_NAME == "MSR":
                    valid_address = address_msr(wallet_address)
                    if type(valid_address).__name__ != "Address":
                        await ctx.message.add_reaction(EMOJI_ERROR)
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please use {COIN_NAME} main address.')
                        return
                elif COIN_NAME == "WOW":
                    valid_address = address_wow(wallet_address)
                    if type(valid_address).__name__ != "Address":
                        await ctx.message.add_reaction(EMOJI_ERROR)
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please use {COIN_NAME} main address.')
                        return
                elif COIN_NAME == "XOL":
                    valid_address = address_xol(wallet_address)
                    if type(valid_address).__name__ != "Address":
                        await ctx.message.add_reaction(EMOJI_ERROR)
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please use {COIN_NAME} main address.')
                        return
                elif COIN_NAME == "UPX":	
                    valid_address = address_upx(wallet_address)	
                    if type(valid_address).__name__ != "Address":	
                        await ctx.message.add_reaction(EMOJI_ERROR)	
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please use {COIN_NAME} main address.')	
                        return
        else:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Unknown Ticker.')
            return
    # correct print(valid_address)
    if COIN_NAME not in ENABLE_COIN_ERC:
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

    serverinfo = await get_info_pref_coin(ctx)
    server_prefix = serverinfo['server_prefix']
    if existing_user['user_wallet_address']:
        prev_address = existing_user['user_wallet_address']
        if COIN_NAME in ENABLE_COIN_ERC:
            if prev_address.upper() != wallet_address.upper():
                await store.sql_update_user(str(ctx.message.author.id), wallet_address, COIN_NAME)
                await ctx.message.add_reaction(EMOJI_OK_HAND)
                await ctx.send(f'Your {COIN_NAME} {ctx.author.mention} withdraw address has changed from:\n'
                               f'`{prev_address}`\n to\n '
                               f'`{wallet_address}`')
                return
            else:
                await ctx.message.add_reaction(EMOJI_WARNING)
                await ctx.send(f'{ctx.author.mention} Your {COIN_NAME} previous and new address is the same.')
                return

        else:
            if prev_address != valid_address:
                await store.sql_update_user(str(ctx.message.author.id), wallet_address, COIN_NAME)
                await ctx.message.add_reaction(EMOJI_OK_HAND)
                await ctx.send(f'Your {COIN_NAME} {ctx.author.mention} withdraw address has changed from:\n'
                               f'`{prev_address}`\n to\n '
                               f'`{wallet_address}`')
                return
            else:
                await ctx.message.add_reaction(EMOJI_WARNING)
                await ctx.send(f'{ctx.author.mention} Your {COIN_NAME} previous and new address is the same.')
                return
    else:
        await store.sql_update_user(str(ctx.message.author.id), wallet_address, COIN_NAME)
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        await ctx.send(f'{ctx.author.mention} You have registered {COIN_NAME} withdraw address.\n'
                       f'You can use `{server_prefix}withdraw AMOUNT {COIN_NAME}` anytime.')
        return


@bot.command(pass_context=True, help=bot_help_withdraw)
async def withdraw(ctx, amount: str, coin: str = None):
    global TX_IN_PROCESS, IS_RESTARTING
    # check if bot is going to restart
    if IS_RESTARTING:
        await ctx.message.add_reaction(EMOJI_REFRESH)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
        return

    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'withdraw')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    # Check if tx in progress
    if ctx.message.author.id in TX_IN_PROCESS:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    botLogChan = bot.get_channel(id=LOG_CHAN)
    amount = amount.replace(",", "")

    # Check flood of tip
    floodTip = await store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration)
    if floodTip >= config.floodTip:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Cool down your tip or TX. or increase your amount next time.')
        await botLogChan.send('A user reached max. TX threshold. Currently halted: `.withdraw`')
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

    if isinstance(ctx.channel, discord.DMChannel):
        server_prefix = '.'
    else:
        serverinfo = await get_info_pref_coin(ctx)
        server_prefix = serverinfo['server_prefix']
        # check if bot channel is set:
        if serverinfo and serverinfo['botchan']:
            try: 
                if ctx.channel.id != int(serverinfo['botchan']):
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    botChan = bot.get_channel(id=int(serverinfo['botchan']))
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, {botChan.mention} is the bot channel!!!')
                    return
            except ValueError:
                pass
        # end of bot channel check
    try:
        amount = Decimal(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount for `withdraw`.')
        return

    if coin is None:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please have **ticker** (coin name) after amount for `withdraw`.')
        return

    COIN_NAME = coin.upper()
    if not is_coin_txable(COIN_NAME):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} TX is currently disable for {COIN_NAME}.')
        await msg.add_reaction(EMOJI_OK_BOX)
        await logchanbot(f'User {ctx.author.id} tried to withdraw {amount}{COIN_NAME} while it tx not enable.')
        return

    if COIN_NAME not in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC:
        await ctx.message.add_reaction(EMOJI_WARNING)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Unknown Ticker.')
        return

    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
        real_amount = float(amount)
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
        real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
    if is_maintenance_coin(COIN_NAME):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return

    user = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    if user is None:
        if COIN_NAME in ENABLE_COIN_ERC:
            w = await create_address_eth()
            user = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0, w)
        else:
            user = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)
        user = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)

    if user['user_wallet_address'] is None:
        extra_txt = ""
        if COIN_NAME in ENABLE_COIN_ERC:
            extra_txt = " " + COIN_NAME
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You do not have a withdrawal address for **{COIN_NAME}**, please use '
                       f'`{server_prefix}register wallet_address{extra_txt}` to register.')
        return

    NetFee = 0
    userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), COIN_NAME)
    xfer_in = 0
    if COIN_NAME not in ENABLE_COIN_ERC:
        xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.message.author.id), COIN_NAME)
    if COIN_NAME in ENABLE_COIN_DOGE+ENABLE_COIN_ERC:
        actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
    elif COIN_NAME in ENABLE_COIN_NANO:
        actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
        actual_balance = round(actual_balance / get_decimal(COIN_NAME), 6) * get_decimal(COIN_NAME)
    else:
        actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])

    if coin_family in ["TRTL", "BCN"]:
        if coin_family == "BCN":
            NetFee = get_tx_fee(coin = COIN_NAME)
        else:
            NetFee = get_reserved_fee(coin = COIN_NAME)
    elif coin_family == "XMR":
        NetFee = await get_tx_fee_xmr(coin = COIN_NAME, amount = real_amount, to_address = user['user_wallet_address'])
        if NetFee is None:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Can not get fee from network for: '
                           f'{num_format_coin(real_amount, COIN_NAME)} '
                           f'{COIN_NAME}. Please try again later in a few minutes.')
            return
    elif coin_family == "DOGE":
        NetFee = get_tx_fee(coin = COIN_NAME)
    elif coin_family == "ERC-20":
        token_info = await store.get_token_info(COIN_NAME)
        NetFee = token_info['real_withdraw_fee']
        MinTx = token_info['real_min_tx']
        MaxTX = token_info['real_max_tx']
    # Negative check
    try:
        if actual_balance < 0:
            msg_negative = 'Negative balance detected:\nUser: '+str(ctx.message.author.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
            await logchanbot(msg_negative)
    except Exception as e:
        await logchanbot(traceback.format_exc())

    # add redis action
    random_string = str(uuid.uuid4())
    await add_tx_action_redis(json.dumps([random_string, "WITHDRAW", str(ctx.message.author.id), ctx.message.author.name, float("%.3f" % time.time()), ctx.message.content, "DISCORD", "START"]), False)

    # If balance 0, no need to check anything
    if actual_balance <= 0:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please check your **{COIN_NAME}** balance.')
        return
    elif real_amount + NetFee > actual_balance:
        extra_fee_txt = ''
        if NetFee > 0:
            extra_fee_txt = f'You need to leave at least a network or a reserved fee: {num_format_coin(NetFee, COIN_NAME)}{COIN_NAME}'
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to withdraw '
                       f'{num_format_coin(real_amount, COIN_NAME)} '
                       f'{COIN_NAME}. {extra_fee_txt}')
        return
    elif real_amount > MaxTX:
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

    withdrawTx = None
    withdraw_txt = ''
    # add to queue withdraw
    if ctx.message.author.id not in TX_IN_PROCESS:
        TX_IN_PROCESS.append(ctx.message.author.id)
    else:
        # reject and tell to wait
        await botLogChan.send(f'A user tried to executed `.withdraw {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}` while there is in queue of **TX_IN_PROCESS**.')
        try:
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You have another tx in process. Please wait it to finish. ')
        except Exception as e:
            pass
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    try:
        if coin_family in ["TRTL", "BCN"]:
            withdrawTx = await store.sql_external_cn_single_withdraw(str(ctx.message.author.id), real_amount, COIN_NAME)
            withdraw_txt = "Transaction hash: `{}`".format(withdrawTx['transactionHash'])
            withdraw_txt += "\nTx Fee: `{}{}`".format(num_format_coin(withdrawTx['fee'], COIN_NAME), COIN_NAME)
        elif coin_family == "XMR":
            withdrawTx = await store.sql_external_xmr_single(str(ctx.message.author.id),
                                                            real_amount,
                                                            user['user_wallet_address'],
                                                            COIN_NAME, "WITHDRAW")
            withdraw_txt = "Transaction hash: `{}`".format(withdrawTx['tx_hash'])
            withdraw_txt += "\nNetwork fee deducted from your account balance."
        elif coin_family == "NANO":
            withdrawTx = await store.sql_external_nano_single(str(ctx.message.author.id), real_amount,
                                                            user['user_wallet_address'],
                                                            COIN_NAME, "WITHDRAW")
            withdraw_txt = "Block: `{}`".format(withdrawTx['block'])
        elif coin_family == "DOGE": 
            withdrawTx = await store.sql_external_doge_single(str(ctx.message.author.id), real_amount,
                                                            NetFee, user['user_wallet_address'],
                                                            COIN_NAME, "WITHDRAW")
            withdraw_txt = f'Transaction hash: `{withdrawTx}`\nNetwork fee deducted from the amount.'
        elif coin_family == "ERC-20": 
            withdrawTx = await store.sql_external_erc_single(str(ctx.author.id), user['user_wallet_address'], real_amount, COIN_NAME, 'WITHDRAW', 'DISCORD')
            withdraw_txt = f'Transaction hash: `{withdrawTx}`\nFee `{NetFee}{COIN_NAME}` deducted from your balance.'
        # add redis action
        await add_tx_action_redis(json.dumps([random_string, "WITHDRAW", str(ctx.message.author.id), ctx.message.author.name, float("%.3f" % time.time()), ctx.message.content, "DISCORD", "COMPLETE"]), False)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    # remove to queue withdraw
    if ctx.message.author.id in TX_IN_PROCESS:
        TX_IN_PROCESS.remove(ctx.message.author.id)

    if withdrawTx:
        withdrawAddress = user['user_wallet_address']
        if coin_family == "ERC-20":
            await ctx.message.add_reaction(TOKEN_EMOJI)
        else:
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
        try:
            await ctx.message.author.send(
                                f'{EMOJI_ARROW_RIGHTHOOK} You have withdrawn {num_format_coin(real_amount, COIN_NAME)} '
                                f'{COIN_NAME} to `{withdrawAddress}`.\n'
                                f'{withdraw_txt}')
        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            try:
                await ctx.send(f'{EMOJI_ARROW_RIGHTHOOK} You have withdrawn {num_format_coin(real_amount, COIN_NAME)} '
                               f'{COIN_NAME} to `{withdrawAddress}`.\n'
                               f'{withdraw_txt}')
            except Exception as e:
                pass
        await botLogChan.send(f'A user successfully executed `.withdraw {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`')
        return
    else:
        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Internal error during your withdraw, please report.')
        await botLogChan.send(f'A user failed to executed `.withdraw {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`')
        await ctx.message.add_reaction(EMOJI_ERROR)
        return


@bot.command(pass_context=True, help=bot_help_donate)
async def donate(ctx, amount: str, coin: str=None):
    global IS_RESTARTING, TX_IN_PROCESS
    # check if bot is going to restart
    if IS_RESTARTING:
        await ctx.message.add_reaction(EMOJI_REFRESH)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
        return
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'donate')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    # Check if tx in progress
    if ctx.message.author.id in TX_IN_PROCESS:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    botLogChan = bot.get_channel(id=LOG_CHAN)
    donate_msg = ''
    if amount.upper() == "LIST":
        # if .donate list
        donate_list = await store.sql_get_donate_list()
        item_list = []
        embed = discord.Embed(title='Donation List', timestamp=datetime.utcnow())
        for key, value in donate_list.items():
            if value:
                coin_value = num_format_coin(value, key.upper())+key.upper()
                item_list.append(coin_value)
                embed.add_field(name=key.upper(), value=num_format_coin(value, key.upper())+key.upper(), inline=True)
        embed.add_field(name="OTHER LINKS", value="{} / {} / {}".format("[Invite TipBot](http://invite.discord.bot.tips)", "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
        if len(item_list) > 0:
            try:
                await ctx.send(embed=embed)
            except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                msg_coins = ', '.join(item_list)
                try:
                    await ctx.send(f'Thank you for checking. So far, we got donations:\n```{msg_coins}```')
                except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                    return
        return

    amount = amount.replace(",", "")

    # Check flood of tip
    floodTip = await store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration)
    if floodTip >= config.floodTip:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Cool down your tip or TX. or increase your amount next time.')
        await botLogChan.send('A user reached max. TX threshold. Currently halted: `.donate`')
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
        amount = Decimal(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    COIN_NAME = coin.upper()
    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
        real_amount = float(amount)
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
        real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
    if is_maintenance_coin(COIN_NAME):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} in maintenance.')
        return
 
    user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    if user_from is None:
        if COIN_NAME in ENABLE_COIN_ERC:
            w = await create_address_eth()
            user_from = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0, w)
        else:
            user_from = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)

    userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), COIN_NAME)
    xfer_in = 0
    if COIN_NAME not in ENABLE_COIN_ERC:
        xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.message.author.id), COIN_NAME)
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
            msg_negative = 'Negative balance detected:\nUser: '+str(ctx.message.author.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
            await logchanbot(msg_negative)
    except Exception as e:
        await logchanbot(traceback.format_exc())

    if real_amount > actual_balance:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to donate '
                       f'{num_format_coin(real_amount, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return

    donateTx = None
    try:
        if coin_family in ["TRTL", "BCN"]:
            donateTx = await store.sql_donate(str(ctx.message.author.id), get_donate_address(COIN_NAME), real_amount, COIN_NAME)
        elif coin_family == "XMR":
            donateTx = await store.sql_mv_xmr_single(str(ctx.message.author.id), 
                                                    get_donate_account_name(COIN_NAME), 
                                                    real_amount, COIN_NAME, "DONATE")
        elif coin_family == "NANO":
            donateTx = await store.sql_mv_nano_single(str(ctx.message.author.id), 
                                                      get_donate_account_name(COIN_NAME), 
                                                      real_amount, COIN_NAME, "DONATE")
        elif coin_family == "DOGE":
            donateTx = await store.sql_mv_doge_single(str(ctx.message.author.id), get_donate_account_name(COIN_NAME), real_amount,
                                                      COIN_NAME, "DONATE")
        elif coin_family == "ERC-20":
            token_info = await store.get_token_info(COIN_NAME)
            donateTx = await store.sql_mv_erc_single(str(ctx.message.author.id), token_info['donate_name'], real_amount, COIN_NAME, "DONATE", token_info['contract'])
    except Exception as e:
        await logchanbot(traceback.format_exc())
    if donateTx:
        await ctx.message.add_reaction(get_emoji(COIN_NAME))
        await botLogChan.send(f'{EMOJI_MONEYFACE} TipBot got donation: {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}')
        await ctx.message.author.send(
                                f'{EMOJI_MONEYFACE} TipBot got donation: {num_format_coin(real_amount, COIN_NAME)} '
                                f'{COIN_NAME} '
                                f'\n'
                                f'Thank you.')
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        msg = await ctx.send(f'{ctx.author.mention} Donating failed, try again. Thank you.')
        await botLogChan.send(f'A user failed to donate `{num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`.')
        await msg.add_reaction(EMOJI_OK_BOX)
        # add to failed tx table
        await store.sql_add_failed_tx(COIN_NAME, str(ctx.message.author.id), ctx.message.author.name, real_amount, "DONATE")
        return


@bot.command(pass_context=True, help=bot_help_notifytip)
async def notifytip(ctx, onoff: str):
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'forwardtip')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    if onoff.upper() not in ["ON", "OFF"]:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} You need to use only `ON` or `OFF`.')
        return

    onoff = onoff.upper()
    notifyList = await store.sql_get_tipnotify()
    if onoff == "ON":
        if str(ctx.message.author.id) in notifyList:
            await store.sql_toggle_tipnotify(str(ctx.message.author.id), "ON")
            await ctx.send(f'{ctx.author.mention} OK, you will get all notification when tip.')
            return
        else:
            await ctx.send(f'{ctx.author.mention} You already have notification ON by default.')
            return
    elif onoff == "OFF":
        if str(ctx.message.author.id) in notifyList:
            await ctx.send(f'{ctx.author.mention} You already have notification OFF.')
            return
        else:
            await store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            await ctx.send(f'{ctx.author.mention} OK, you will not get any notification when anyone tips.')
            return


@bot.command(pass_context=True, help=bot_help_take)
async def take(ctx, info: str=None):
    global FAUCET_COINS, FAUCET_MINMAX, TRTL_DISCORD, TX_IN_PROCESS, IS_RESTARTING
    botLogChan = bot.get_channel(id=LOG_CHAN)
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send(f'{EMOJI_RED_NO} This command can not be in private.')
        return

    # bot check in the first place
    if ctx.message.author.bot == True:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is not allowed using this.')
        await botLogChan.send(f'{ctx.author.name} / {ctx.author.id} (Bot) using **take** {ctx.guild.name} / {ctx.guild.id}')
        return

    # Check if tx in progress
    if ctx.author.id in TX_IN_PROCESS:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    remaining = ''
    try:
        remaining = await bot_faucet(ctx) or ''
    except Exception as e:
        await logchanbot(traceback.format_exc())
    total_claimed = '{:,.0f}'.format(await store.sql_faucet_count_all())
    if info:
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        msg = await ctx.send(f'{ctx.author.mention} Faucet balance:\n```{remaining}```'
                             f'Total user claims: **{total_claimed}** times. '
                             f'Tip me if you want to feed these faucets.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    # check if bot is going to restart
    if IS_RESTARTING:
        await ctx.message.add_reaction(EMOJI_REFRESH)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
        return

    # disable faucet for TRTL discord
    if ctx.guild.id == TRTL_DISCORD:
        await ctx.message.add_reaction(EMOJI_LOCKED)
        return

    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'take')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    # check if user create account less than 3 days
    try:
        account_created = ctx.message.author.created_at
        if (datetime.utcnow() - account_created).total_seconds() <= 3*24*3600:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Your account is very new. Wait a few days before using .take')
            return
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        pass
    except Exception as e:
        await logchanbot(traceback.format_exc())

    try: 
        # check if bot channel is set:
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo['botchan']:
            if ctx.channel.id != int(serverinfo['botchan']):
                await ctx.message.add_reaction(EMOJI_ERROR)
                botChan = bot.get_channel(id=int(serverinfo['botchan']))
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, {botChan.mention} is the bot channel!!!')
                return
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        pass
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    # end of bot channel check

    try:
        # check user claim:
        claim_interval = config.faucet.interval
        check_claimed = await store.sql_faucet_checkuser(str(ctx.message.author.id), 'DISCORD')
        if check_claimed:
            # limit 12 hours
            if int(time.time()) - check_claimed['claimed_at'] <= claim_interval*3600:
                time_waiting = seconds_str(claim_interval*3600 - int(time.time()) + check_claimed['claimed_at'])
                user_claims = await store.sql_faucet_count_user(str(ctx.message.author.id))
                number_user_claimed = '{:,.0f}'.format(user_claims, 'DISCORD')
                await ctx.message.add_reaction(EMOJI_ERROR)
                msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You just claimed within last {claim_interval}h. '
                                     f'Waiting time {time_waiting} for next **take**. Faucet balance:\n```{remaining}```'
                                     f'Total user claims: **{total_claimed}** times. '
                                     f'You have claimed: **{number_user_claimed}** time(s). '
                                     f'Tip me if you want to feed these faucets.')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
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

    if COIN_NAME in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC:
        real_amount = float(amount * get_decimal(COIN_NAME)) if coin_family == "DOGE" else int(amount) # already real amount
        user_from = await store.sql_get_userwallet(str(bot.user.id), COIN_NAME)
        if user_from is None:
            if COIN_NAME in ENABLE_COIN_ERC:
                w = await create_address_eth()
                user_from = await store.sql_register_user(str(bot.user.id), COIN_NAME, 'DISCORD', 0, w)
            else:
                user_from = await store.sql_register_user(str(bot.user.id), COIN_NAME, 'DISCORD', 0)
        userdata_balance = await store.sql_user_balance(str(bot.user.id), COIN_NAME)
        xfer_in = 0
        if COIN_NAME not in ENABLE_COIN_ERC:
            xfer_in = await store.sql_user_balance_get_xfer_in(str(bot.user.id), COIN_NAME)
        if COIN_NAME in ENABLE_COIN_DOGE+ENABLE_COIN_ERC:
            actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
        elif COIN_NAME in ENABLE_COIN_NANO:
            actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
            actual_balance = round(actual_balance / get_decimal(COIN_NAME), 6) * get_decimal(COIN_NAME)
        else:
            actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
        user_to = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        # Negative check
        try:
            if actual_balance < 0:
                msg_negative = 'Negative balance detected:\nBot User: '+str(bot.user.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                await logchanbot(msg_negative)
        except Exception as e:
            await logchanbot(traceback.format_exc())
        
        if user_to is None:
            if COIN_NAME in ENABLE_COIN_ERC:
                w = await create_address_eth()
                userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0, w)
            else:
                userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)
            user_to = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)

        if real_amount > actual_balance:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} Please try again later. Bot runs out of **{COIN_NAME}**')
            return
        
        tip = None
        if ctx.message.author.id not in TX_IN_PROCESS:
            TX_IN_PROCESS.append(ctx.message.author.id)
            try:
                if coin_family in ["TRTL", "BCN"]:
                    tip = await store.sql_mv_cn_single(str(bot.user.id), str(ctx.message.author.id), real_amount, 'FAUCET', COIN_NAME)
                elif coin_family == "XMR":
                    tip = await store.sql_mv_xmr_single(str(bot.user.id), str(ctx.message.author.id), real_amount, COIN_NAME, "FAUCET")
                elif coin_family == "NANO":
                    tip = await store.sql_mv_nano_single(str(bot.user.id), str(ctx.message.author.id), real_amount, COIN_NAME, "FAUCET")
                elif coin_family == "DOGE":
                    tip = await store.sql_mv_doge_single(str(bot.user.id), str(ctx.message.author.id), real_amount, COIN_NAME, "FAUCET")
                elif coin_family == "ERC-20":
                    token_info = await store.get_token_info(COIN_NAME)
                    tip = await store.sql_mv_erc_single(str(bot.user.id), str(ctx.message.author.id), real_amount, COIN_NAME, "FAUCET", token_info['contract'])
            except Exception as e:
                await logchanbot(traceback.format_exc())
            TX_IN_PROCESS.remove(ctx.message.author.id)
        else:
            await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
            msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        if tip:
            try:
                faucet_add = await store.sql_faucet_add(str(ctx.message.author.id), str(ctx.guild.id), COIN_NAME, real_amount, get_decimal(COIN_NAME), 'DISCORD')
                await ctx.message.add_reaction(get_emoji(COIN_NAME))
                msg = await ctx.send(f'{EMOJI_MONEYFACE} {ctx.author.mention} You got a random faucet {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}')
                await msg.add_reaction(EMOJI_OK_BOX)
            except Exception as e:
                await logchanbot(traceback.format_exc())
        else:
            await ctx.send(f'{ctx.author.mention} Please try again later. Failed during executing tx **{COIN_NAME}**.')
            await ctx.message.add_reaction(EMOJI_ERROR)


@bot.command(pass_context=True, aliases=['randomtip'], help=bot_help_randomtip)
async def randtip(ctx, amount: str, coin: str, *, rand_option: str=None):
    global TRTL_DISCORD, IS_RESTARTING
    # check if bot is going to restart
    if IS_RESTARTING:
        await ctx.message.add_reaction(EMOJI_REFRESH)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
        return
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'tip')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    # Check if tx in progress
    if ctx.message.author.id in TX_IN_PROCESS:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    botLogChan = bot.get_channel(id=LOG_CHAN)
    amount = amount.replace(",", "")

    try:
        amount = Decimal(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send(f'{EMOJI_RED_NO} This command can not be in private.')
        return

    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    COIN_NAME = coin.upper()
    print("COIN_NAME: " + COIN_NAME)

    # TRTL discord
    if ctx.guild.id == TRTL_DISCORD and COIN_NAME != "TRTL":
        return

    if COIN_NAME not in (ENABLE_COIN + ENABLE_XMR + ENABLE_COIN_DOGE + ENABLE_COIN_NANO):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} **{COIN_NAME}** is not in our supported coins.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    if not is_coin_tipable(COIN_NAME):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} TIPPING is currently disable for {COIN_NAME}.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    # Check allowed coins
    tiponly_coins = serverinfo['tiponly'].split(",")
    if COIN_NAME == serverinfo['default_coin'].upper() or serverinfo['tiponly'].upper() == "ALLCOIN":
        pass
    elif COIN_NAME not in tiponly_coins:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} not in allowed coins set by server manager.')
        return
    # End of checking allowed coins

    if is_maintenance_coin(COIN_NAME):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return

    # Check flood of tip
    floodTip = await store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration)
    if floodTip >= config.floodTip:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Cool down your tip or TX. or increase your amount next time.')
        await botLogChan.send('A user reached max. TX threshold. Currently halted: `.tip`')
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
    # End Check if maintenance

    # Get a random user in the guild, except bots. At least 3 members for random.
    has_last = False
    message_talker = None
    listMembers = None
    minimum_users = 3
    try:
        # Check random option
        if rand_option is None or rand_option.upper().startswith("ALL"):
            listMembers = [member for member in ctx.guild.members if member.bot == False]
        elif rand_option and rand_option.upper().startswith("ONLINE"):
            listMembers = [member for member in ctx.guild.members if member.bot == False and member.status != discord.Status.offline]
        elif rand_option and rand_option.upper().strip().startswith("LAST "):
            argument = rand_option.strip().split(" ")            
            if len(argument) == 2:
                # try if the param is 1111u
                num_user = argument[1].lower()
                if 'u' in num_user or 'user' in num_user or 'users' in num_user or 'person' in num_user or 'people' in num_user:
                    num_user = num_user.replace("people", "")
                    num_user = num_user.replace("person", "")
                    num_user = num_user.replace("users", "")
                    num_user = num_user.replace("user", "")
                    num_user = num_user.replace("u", "")
                    try:
                        num_user = int(num_user)
                        if num_user < minimum_users:
                            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Number of random users cannot below **{minimum_users}**.')
                            return
                        elif num_user >= minimum_users:
                            message_talker = await store.sql_get_messages(str(ctx.message.guild.id), str(ctx.message.channel.id), 0, num_user + 1)
                            if ctx.message.author.id in message_talker:
                                message_talker.remove(ctx.message.author.id)
                            else:
                                # remove the last one
                                message_talker.pop()
                            if len(message_talker) < minimum_users:
                                await ctx.message.add_reaction(EMOJI_ERROR)
                                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is not sufficient user to count for random tip.')
                                return
                            elif len(message_talker) < num_user:
                                try:
                                    await ctx.message.add_reaction(EMOJI_INFORMATION)
                                    await ctx.send(f'{EMOJI_INFORMATION} {ctx.author.mention} I could not find sufficient talkers up to **{num_user}**. I found only **{len(message_talker)}**'
                                                   f' and will random to one of those **{len(message_talker)}** users.')
                                except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                    # No need to tip if failed to message
                                    await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                    # Let it still go through
                                    #return
                        has_last = True
                    except ValueError:
                        await ctx.message.add_reaction(EMOJI_ERROR)
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid param after **LAST** for random tip. Support only *LAST* **X**u right now.')
                        return
                else:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid param after **LAST** for random tip. Support only *LAST* **X**u right now.')
                    return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid param after **LAST** for random tip. Support only *LAST* **X**u right now.')
                return
        if has_last == False and listMembers and len(listMembers) >= minimum_users:
            rand_user = random.choice(listMembers)
            max_loop = 0
            while True:
                if rand_user != ctx.message.author and rand_user.bot == False:
                    break
                else:
                    rand_user = random.choice(listMembers)
                max_loop += 1
                if max_loop >= 5:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} Please try again, maybe guild doesnot have so many users.')
                    return
                    break
        elif has_last == True and message_talker and len(message_talker) >= minimum_users:
            rand_user_id = random.choice(message_talker)
            max_loop = 0
            while True:
                rand_user = bot.get_user(id=rand_user_id)
                if rand_user and rand_user != ctx.message.author and rand_user.bot == False and rand_user in ctx.guild.members:
                    break
                else:
                    rand_user_id = random.choice(message_talker)
                    rand_user = bot.get_user(id=rand_user_id)
                max_loop += 1
                if max_loop >= 10:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} Please try again, maybe guild doesnot have so many users.')
                    return
                    break
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} not enough member for random tip.')
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        return
        
    notifyList = await store.sql_get_tipnotify()

    if COIN_NAME in ENABLE_COIN_ERC:
        real_amount = float(amount)
        token_info = await store.get_token_info(COIN_NAME)
        MinTx = token_info['real_min_tx']
        MaxTX = token_info['real_max_tx']
    else:
        real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["XMR", "TRTL", "BCN", "NANO"] else float(amount)
        MinTx = get_min_mv_amount(COIN_NAME)
        MaxTX = get_max_mv_amount(COIN_NAME)

    user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    if user_from is None:
        if COIN_NAME in ENABLE_COIN_ERC:
            w = await create_address_eth()
            user_from = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0, w)
        else:
            user_from = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)

    userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), COIN_NAME)
    xfer_in = 0
    if COIN_NAME not in ENABLE_COIN_ERC:
        xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.message.author.id), COIN_NAME)
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
            msg_negative = 'Negative balance detected:\nUser: '+str(ctx.message.author.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
            await logchanbot(msg_negative)
    except Exception as e:
        await logchanbot(traceback.format_exc())

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
    elif real_amount > actual_balance:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to do a random tip of '
                       f'{num_format_coin(real_amount, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return

    # add queue also randtip
    if ctx.message.author.id not in TX_IN_PROCESS:
        TX_IN_PROCESS.append(ctx.message.author.id)
    else:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    print('random get user: {}/{}'.format(rand_user.name, rand_user.id))

    tip = None
    user_to = await store.sql_get_userwallet(str(rand_user.id), COIN_NAME)
    if user_to is None:
        userregister = await store.sql_register_user(str(rand_user.id), COIN_NAME, 'DISCORD', 0)
        user_to = await store.sql_get_userwallet(str(rand_user.id), COIN_NAME)

    if coin_family in ["TRTL", "BCN"]:
        tip = await store.sql_mv_cn_single(str(ctx.message.author.id), str(rand_user.id), real_amount, 'RANDTIP', COIN_NAME)
    elif coin_family == "XMR":
        tip = await store.sql_mv_xmr_single(str(ctx.message.author.id), str(rand_user.id), real_amount, COIN_NAME, "RANDTIP")
    elif coin_family == "NANO":
        tip = await store.sql_mv_nano_single(str(ctx.message.author.id), str(rand_user.id), real_amount, COIN_NAME, "RANDTIP")
    elif coin_family == "DOGE":
        tip = await store.sql_mv_doge_single(str(ctx.message.author.id), str(rand_user.id), real_amount, COIN_NAME, "RANDTIP")
    elif coin_family == "ERC-20":
        tip = await store.sql_mv_erc_single(str(ctx.message.author.id), str(rand_user.id), real_amount, COIN_NAME, "RANDTIP", token_info['contract'])
    # remove queue from randtip
    if ctx.message.author.id in TX_IN_PROCESS:
        TX_IN_PROCESS.remove(ctx.message.author.id)

    if tip:
        randtip_public_respond = False
        # tipper shall always get DM. Ignore notifyList
        try:
            await ctx.message.author.send(
                f'{EMOJI_ARROW_RIGHTHOOK} {rand_user.name}#{rand_user.discriminator} got your random tip of {num_format_coin(real_amount, COIN_NAME)} '
                f'{COIN_NAME} in server `{ctx.guild.name}`')
        except (discord.Forbidden, discord.errors.Forbidden) as e:
            await store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
        if str(rand_user.id) not in notifyList:
            try:
                await rand_user.send(
                    f'{EMOJI_MONEYFACE} You got a random tip of {num_format_coin(real_amount, COIN_NAME)} '
                    f'{COIN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{ctx.guild.name}`\n'
                    f'{NOTIFICATION_OFF_CMD}')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await store.sql_toggle_tipnotify(str(user.id), "OFF")
        try:
            # try message in public also
            msg = await ctx.send(
                            f'{rand_user.name}#{rand_user.discriminator} got a random tip of {num_format_coin(real_amount, COIN_NAME)} '
                            f'{COIN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator}')
            await msg.add_reaction(EMOJI_OK_BOX)
            randtip_public_respond = True
        except (discord.Forbidden, discord.errors.Forbidden) as e:
            pass
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if randtip_public_respond == False and serverinfo and 'botchan' in serverinfo and serverinfo['botchan']:
            # It has bot channel, let it post in bot channel
            try:
                bot_channel = bot.get_channel(id=int(serverinfo['botchan']))
                msg = await bot_channel.send(
                            f'{rand_user.name}#{rand_user.discriminator} got a random tip of {num_format_coin(real_amount, COIN_NAME)} '
                            f'{COIN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} in {ctx.channel.mention}')
                await msg.add_reaction(EMOJI_OK_BOX)
            except Exception as e:
                await logchanbot(traceback.format_exc())
        await ctx.message.add_reaction(EMOJI_OK_BOX)
        return


@bot.command(pass_context=True, help=bot_help_freetip)
async def freetip(ctx, amount: str, coin: str, duration: str='60s', *, comment: str=None):
    global TRTL_DISCORD, IS_RESTARTING
    # check if bot is going to restart
    if IS_RESTARTING:
        await ctx.message.add_reaction(EMOJI_REFRESH)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
        return
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'tip')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    # Check if tx in progress
    if ctx.message.author.id in TX_IN_PROCESS:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    botLogChan = bot.get_channel(id=LOG_CHAN)
    amount = amount.replace(",", "")

    try:
        amount = Decimal(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    def hms_to_seconds(time_string):
        duration_in_second = 0
        try:
            time_string = time_string.replace("hours", "h")
            time_string = time_string.replace("hour", "h")
            time_string = time_string.replace("hrs", "h")
            time_string = time_string.replace("hr", "h")

            time_string = time_string.replace("minutes", "mn")
            time_string = time_string.replace("mns", "mn")
            time_string = time_string.replace("mins", "mn")
            time_string = time_string.replace("min", "mn")
            time_string = time_string.replace("m", "mn")
            mult = {'h': 60*60, 'mn': 60}
            duration_in_second = sum(int(num) * mult.get(val, 1) for num, val in re.findall('(\d+)(\w+)', time_string))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return duration_in_second

    duration_s = 0
    try:
        duration_s = hms_to_seconds(duration)
    except Exception as e:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid duration.')
        return

    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send(f'{EMOJI_RED_NO} This command can not be in private.')
        return

    if duration_s == 0:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid time given. Please use time format: XXs')
        return
    elif duration_s < config.freetip.duration_min or duration_s > config.freetip.duration_max:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid duration. Please use between {str(config.freetip.duration_min)}s to {str(config.freetip.duration_max)}s.')
        return

    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    COIN_NAME = coin.upper()
    print("COIN_NAME: " + COIN_NAME)

    # TRTL discord
    if ctx.guild.id == TRTL_DISCORD and COIN_NAME != "TRTL":
        return

    if COIN_NAME not in (ENABLE_COIN + ENABLE_XMR + ENABLE_COIN_DOGE + ENABLE_COIN_NANO + ENABLE_COIN_ERC):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} **{COIN_NAME}** is not in our supported coins.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    if not is_coin_tipable(COIN_NAME):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} TIPPING is currently disable for {COIN_NAME}.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    # Check allowed coins
    tiponly_coins = serverinfo['tiponly'].split(",")
    if COIN_NAME == serverinfo['default_coin'].upper() or serverinfo['tiponly'].upper() == "ALLCOIN":
        pass
    elif COIN_NAME not in tiponly_coins:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} not in allowed coins set by server manager.')
        return
    # End of checking allowed coins

    if is_maintenance_coin(COIN_NAME):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return

    # Check flood of tip
    floodTip = await store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration)
    if floodTip >= config.floodTip:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Cool down your tip or TX. or increase your amount next time.')
        await botLogChan.send('A user reached max. TX threshold. Currently halted: `.tip`')
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
    # End Check if maintenance

    notifyList = await store.sql_get_tipnotify()
    if coin_family == "ERC-20":
        token_info = await store.get_token_info(COIN_NAME)
        real_amount = float(amount)
        MinTx = token_info['real_min_tip']
        MaxTX = token_info['real_max_tip']
    else:
        real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["XMR", "TRTL", "BCN", "NANO"] else float(amount)
        MinTx = get_min_mv_amount(COIN_NAME)
        MaxTX = get_max_mv_amount(COIN_NAME)
    if comment and len(comment) > 0:
        MinTx = MinTx * config.freetip.with_comment_x_amount
        MaxTX = MaxTX * config.freetip.with_comment_x_amount

    user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    if user_from is None:
        if COIN_NAME in ENABLE_COIN_ERC:
            w = await create_address_eth()
            user_from = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0, w)
        else:
            user_from = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)
    userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), COIN_NAME)
    xfer_in = 0
    if COIN_NAME not in ENABLE_COIN_ERC:
        xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.message.author.id), COIN_NAME)
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
            msg_negative = 'Negative balance detected:\nUser: '+str(ctx.message.author.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
            await logchanbot(msg_negative)
    except Exception as e:
        await logchanbot(traceback.format_exc())

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
    elif real_amount > actual_balance:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to do a free tip of '
                       f'{num_format_coin(real_amount, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return

    attend_list_id = []
    attend_list_names = []
    ts = timestamp=datetime.utcnow()

    if ctx.message.author.id not in TX_IN_PROCESS:
        TX_IN_PROCESS.append(ctx.message.author.id)
    try:
        embed = discord.Embed(title=f"Free Tip appears {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}", description=f"Re-act {EMOJI_PARTY} to collect", timestamp=ts, color=0x00ff00)
        msg = await ctx.send(embed=embed)
        await msg.add_reaction(EMOJI_PARTY)
        if comment and len(comment) > 0:
            embed.add_field(name="Comment", value=comment, inline=False)
        embed.set_footer(text=f"Free tip by {ctx.message.author.name}#{ctx.message.author.discriminator}, timeout: {seconds_str(duration_s)}")
        await msg.edit(embed=embed)
        await ctx.message.add_reaction(EMOJI_OK_HAND)
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        if ctx.message.author.id in TX_IN_PROCESS:
            TX_IN_PROCESS.remove(ctx.message.author.id)
        await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
        return
    def check(reaction, user):
        return user != ctx.message.author and user.bot == False and reaction.message.author == bot.user \
and reaction.message.id == msg.id and str(reaction.emoji) == EMOJI_PARTY
    
    if comment and len(comment) > 0:
        # multiple free tip
        while True:
            start_time = int(time.time())
            try:
                reaction, user = await bot.wait_for('reaction_add', timeout=duration_s, check=check)
            except asyncio.TimeoutError:
                if ctx.message.author.id in TX_IN_PROCESS:
                    TX_IN_PROCESS.remove(ctx.message.author.id)
                if len(attend_list_id) == 0:
                    embed = discord.Embed(title=f"Free Tip appears {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}", description=f"Already expired", timestamp=ts, color=0x00ff00)
                    embed.add_field(name="Comment", value=comment, inline=False)
                    embed.set_footer(text=f"Free tip by {ctx.message.author.name}#{ctx.message.author.discriminator}, and no one collected!")
                    await msg.edit(embed=embed)
                    await msg.add_reaction(EMOJI_OK_BOX)
                    return
                break

            if str(reaction.emoji) == EMOJI_PARTY and user.id not in attend_list_id:
                attend_list_id.append(user.id)
                attend_list_names.append('{}#{}'.format(user.name, user.discriminator))
                embed = discord.Embed(title=f"Free Tip appears {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}", description=f"Re-act {EMOJI_PARTY} to collect", timestamp=ts, color=0x00ff00)
                embed.add_field(name="Comment", value=comment, inline=False)
                embed.add_field(name="Attendees", value=", ".join(attend_list_names), inline=False)
                embed.set_footer(text=f"Free tip by {ctx.message.author.name}#{ctx.message.author.discriminator}, timeout: {seconds_str(duration_s)}")
                await msg.edit(embed=embed)
                duration_s -= int(time.time()) - start_time
                if duration_s <= 1:
                    break

        # re-check balance
        userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), COIN_NAME)
        xfer_in = 0
        if COIN_NAME not in ENABLE_COIN_ERC:
            xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.message.author.id), COIN_NAME)
        if COIN_NAME in ENABLE_COIN_DOGE+ENABLE_COIN_ERC:
            actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
        elif COIN_NAME in ENABLE_COIN_NANO:
            actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
            actual_balance = round(actual_balance / get_decimal(COIN_NAME), 6) * get_decimal(COIN_NAME)
        else:
            actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])

        if real_amount > actual_balance:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to do a free tip of '
                           f'{num_format_coin(real_amount, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return
        # end of re-check balance

        # Multiple tip here
        notifyList = await store.sql_get_tipnotify()

        if len(attend_list_id) == 0:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} divided by 0!!!')
            return

        amountDiv = int(round(real_amount / len(attend_list_id), 2))  # cut 2 decimal only
        if coin_family == "DOGE" or coin_family == "ERC-20":
            amountDiv = round(real_amount / len(attend_list_id), 4)

        tip = None
        try:
            if coin_family in ["TRTL", "BCN"]:
                tip = await store.sql_mv_cn_multiple(str(ctx.message.author.id), amountDiv, attend_list_id, 'TIPALL', COIN_NAME)
            elif coin_family == "XMR":
                tip = await store.sql_mv_xmr_multiple(str(ctx.message.author.id), attend_list_id, amountDiv, COIN_NAME, "TIPALL")
            elif coin_family == "NANO":
                tip = await store.sql_mv_nano_multiple(str(ctx.message.author.id), attend_list_id, amountDiv, COIN_NAME, "TIPALL")
            elif coin_family == "DOGE":
                tip = await store.sql_mv_doge_multiple(str(ctx.message.author.id), attend_list_id, amountDiv, COIN_NAME, "TIPALL")
            elif coin_family == "ERC-20":
                tip = await store.sql_mv_erc_multiple(str(ctx.message.author.id), attend_list_id, amountDiv, COIN_NAME, "TIPALL", token_info['contract'])
        except Exception as e:
            await logchanbot(traceback.format_exc())

        # remove queue from tipall
        if ctx.message.author.id in TX_IN_PROCESS:
            TX_IN_PROCESS.remove(ctx.message.author.id)
        if tip:
            tipAmount = num_format_coin(real_amount, COIN_NAME)
            ActualSpend_str = num_format_coin(amountDiv * len(attend_list_id), COIN_NAME)
            amountDiv_str = num_format_coin(amountDiv, COIN_NAME)
            if COIN_NAME in ENABLE_COIN_ERC:
                await ctx.message.add_reaction(TOKEN_EMOJI)
            else:
                await ctx.message.add_reaction(get_emoji(COIN_NAME))
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Free Tip of {tipAmount} '
                    f'{COIN_NAME} '
                    f'was collected by ({len(attend_list_id)}) members in server `{ctx.guild.name}`.\n'
                    f'Each member got: `{amountDiv_str}{COIN_NAME}`\n'
                    f'Actual spending: `{ActualSpend_str}{COIN_NAME}`')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            numMsg = 0
            for member_id in attend_list_id:
                member = bot.get_user(id=member_id)
                if ctx.message.author.id != member.id and member.id != bot.user.id:
                    if str(member.id) not in notifyList:
                        # random user to DM
                        dm_user = bool(random.getrandbits(1)) if len(attend_list_id) > config.tipallMax_LimitDM else True
                        if dm_user:
                            try:
                                await member.send(
                                    f'{EMOJI_MONEYFACE} You collected a free tip of {amountDiv_str} '
                                    f'{COIN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{ctx.guild.name}` #{ctx.channel.name}\n'
                                    f'{NOTIFICATION_OFF_CMD}')
                                numMsg += 1
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                await store.sql_toggle_tipnotify(str(member.id), "OFF")
                if numMsg >= config.tipallMax_LimitDM:
                    # stop DM if reaches
                    break
            # Edit embed
            try:
                embed = discord.Embed(title=f"Free Tip appears {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}", description=f"Re-act {EMOJI_PARTY} to collect", timestamp=ts, color=0x00ff00)
                embed.add_field(name="Comment", value=comment, inline=False)
                embed.add_field(name="Attendees", value=", ".join(attend_list_names), inline=False)
                embed.set_footer(text=f"Free tip by {ctx.message.author.name}#{ctx.message.author.discriminator}, completed! Collected by {len(attend_list_id)} member(s)")
                await msg.edit(embed=embed)
                await msg.add_reaction(EMOJI_OK_BOX)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            await ctx.message.add_reaction(EMOJI_OK_HAND)
            return
    else:
        # single free tip
        try:
            reaction, user = await bot.wait_for('reaction_add', timeout=duration_s, check=check)
        except asyncio.TimeoutError:
            if ctx.message.author.id in TX_IN_PROCESS:
                TX_IN_PROCESS.remove(ctx.message.author.id)
            embed = discord.Embed(title=f"Free Tip appears {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}", description=f"Already expired", timestamp=ts, color=0x00ff00)
            embed.set_footer(text=f"Free tip by {ctx.message.author.name}#{ctx.message.author.discriminator}, and no one collected!")
            await msg.edit(embed=embed)
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        if str(reaction.emoji) == EMOJI_PARTY:
            # re-check balance
            userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), COIN_NAME)
            xfer_in = 0
            if COIN_NAME not in ENABLE_COIN_ERC:
                xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.message.author.id), COIN_NAME)
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
                    msg_negative = 'Negative balance detected:\nUser: '+str(ctx.message.author.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                    await logchanbot(msg_negative)
            except Exception as e:
                await logchanbot(traceback.format_exc())

            if real_amount > actual_balance:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to do a free tip of '
                               f'{num_format_coin(real_amount, COIN_NAME)} '
                               f'{COIN_NAME}.')
                return
            # end of re-check balance

            tip = None
            user_to = await store.sql_get_userwallet(str(user.id), COIN_NAME)
            if user_to is None:
                if COIN_NAME in ENABLE_COIN_ERC:
                    w = await create_address_eth()
                    userregister = await store.sql_register_user(str(user.id), COIN_NAME, 'DISCORD', 0, w)
                else:
                    userregister = await store.sql_register_user(str(user.id), COIN_NAME, 'DISCORD', 0)
                user_to = await store.sql_get_userwallet(str(user.id), COIN_NAME)
            if coin_family in ["TRTL", "BCN"]:
                tip = await store.sql_mv_cn_single(str(ctx.message.author.id), str(user.id), real_amount, 'FREETIP', COIN_NAME)
            elif coin_family == "XMR":
                tip = await store.sql_mv_xmr_single(str(ctx.message.author.id), str(user.id), real_amount, COIN_NAME, "FREETIP")
            elif coin_family == "NANO":
                tip = await store.sql_mv_nano_single(str(ctx.message.author.id), str(user.id), real_amount, COIN_NAME, "FREETIP")
            elif coin_family == "DOGE":
                tip = await store.sql_mv_doge_single(str(ctx.message.author.id), str(user.id), real_amount, COIN_NAME, "FREETIP")
            elif coin_family == "ERC-20":
                tip = await store.sql_mv_erc_single(str(ctx.message.author.id), str(user.id), real_amount, COIN_NAME, "FREETIP", token_info['contract'])
            # remove queue from freetip
            if ctx.message.author.id in TX_IN_PROCESS:
                TX_IN_PROCESS.remove(ctx.message.author.id)

            if tip:
                embed = discord.Embed(title=f"Free Tip appeared {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}", description=f"Already collected", color=0x00ff00)
                embed.set_footer(text=f"Free tip by {ctx.message.author.name}#{ctx.message.author.discriminator}, collected by: {user.name}#{user.discriminator}")
                await msg.edit(embed=embed)
                # tipper shall always get DM. Ignore notifyList
                try:
                    await ctx.message.author.send(
                        f'{EMOJI_ARROW_RIGHTHOOK} Tip of {num_format_coin(real_amount, COIN_NAME)} '
                        f'{COIN_NAME} '
                        f'has been collected by {user.name}#{user.discriminator} in server `{ctx.guild.name}`')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    await store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
                if str(user.id) not in notifyList:
                    try:
                        await user.send(
                            f'{EMOJI_MONEYFACE} You had collected a tip of {num_format_coin(real_amount, COIN_NAME)} '
                            f'{COIN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{ctx.guild.name}`\n'
                            f'{NOTIFICATION_OFF_CMD}')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        await store.sql_toggle_tipnotify(str(user.id), "OFF")
                await msg.add_reaction(EMOJI_OK_BOX)
                return
        

@bot.command(pass_context=True, help=bot_help_tip)
async def tip(ctx, amount: str, *args):
    global TRTL_DISCORD, IS_RESTARTING, TX_IN_PROCESS
    # check if bot is going to restart
    if IS_RESTARTING:
        await ctx.message.add_reaction(EMOJI_REFRESH)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
        return
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'tip')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    # Check if tx in progress
    if ctx.message.author.id in TX_IN_PROCESS:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

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

    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    COIN_NAME = None
    try:
        COIN_NAME = args[0].upper()
        if COIN_NAME in ENABLE_XMR:
            pass
        elif COIN_NAME in ENABLE_COIN_NANO:
            pass
        elif COIN_NAME not in ENABLE_COIN:
            if COIN_NAME in ENABLE_COIN_DOGE+ENABLE_COIN_ERC:
                pass
            elif 'default_coin' in serverinfo:
                COIN_NAME = serverinfo['default_coin'].upper()
    except:
        if 'default_coin' in serverinfo:
            COIN_NAME = serverinfo['default_coin'].upper()
    print("COIN_NAME: " + COIN_NAME)

    # TRTL discord
    if ctx.guild.id == TRTL_DISCORD and COIN_NAME != "TRTL":
        return

    if not is_coin_tipable(COIN_NAME):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} TIPPING is currently disable for {COIN_NAME}.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    # Check allowed coins
    tiponly_coins = serverinfo['tiponly'].split(",")
    if COIN_NAME == serverinfo['default_coin'].upper() or serverinfo['tiponly'].upper() == "ALLCOIN":
        pass
    elif COIN_NAME not in tiponly_coins:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} not in allowed coins set by server manager.')
        return
    # End of checking allowed coins

    if is_maintenance_coin(COIN_NAME):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return

    if len(ctx.message.mentions) == 0 and len(ctx.message.role_mentions) == 0:
        # Use how time.
        if len(args) >= 2:
            time_given = None
            if args[0].upper() == "LAST" or args[1].upper() == "LAST":
                # try if the param is 1111u
                num_user = None
                if args[0].upper() == "LAST":
                    num_user = args[1].lower()
                elif args[1].upper() == "LAST":
                    num_user = args[2].lower()
                if 'u' in num_user or 'user' in num_user or 'users' in num_user or 'person' in num_user or 'people' in num_user:
                    num_user = num_user.replace("people", "")
                    num_user = num_user.replace("person", "")
                    num_user = num_user.replace("users", "")
                    num_user = num_user.replace("user", "")
                    num_user = num_user.replace("u", "")
                    try:
                        num_user = int(num_user)
                        if len(ctx.guild.members) <= 10:
                            await ctx.message.add_reaction(EMOJI_ERROR)
                            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please use normal tip command. There are only few users.')
                            return
                        # Check if we really have that many user in the guild 20%
                        elif num_user >= len(ctx.guild.members):
                            try:
                                await ctx.message.add_reaction(EMOJI_INFORMATION)
                                await ctx.send(f'{ctx.author.mention} Boss, you want to tip more than the number of people in this guild!?.'
                                               ' Can be done :). Wait a while.... I am doing it. (**counting..**)')
                            except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                # No need to tip if failed to message
                                await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                return
                            message_talker = await store.sql_get_messages(str(ctx.message.guild.id), str(ctx.message.channel.id), 0, len(ctx.guild.members))
                            if ctx.message.author.id in message_talker:
                                message_talker.remove(ctx.message.author.id)
                            if len(message_talker) == 0:
                                await ctx.message.add_reaction(EMOJI_ERROR)
                                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is not sufficient user to count.')
                            elif len(message_talker) < len(ctx.guild.members) - 1: # minus bot
                                await ctx.send(f'{EMOJI_INFORMATION} {ctx.author.mention} I could not find sufficient talkers up to **{num_user}**. I found only **{len(message_talker)}**'
                                               f' and tip to those **{len(message_talker)}** users if they are still here.')
                                # tip all user who are in the list
                                try:
                                    async with ctx.typing():
                                        await _tip_talker(ctx, amount, message_talker, False, COIN_NAME)
                                except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                    await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                    # zipped mouth but still need to do tip talker
                                    await _tip_talker(ctx, amount, message_talker, False, COIN_NAME)
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                            return
                        elif num_user > 0:
                            message_talker = await store.sql_get_messages(str(ctx.message.guild.id), str(ctx.message.channel.id), 0, num_user + 1)
                            if ctx.message.author.id in message_talker:
                                message_talker.remove(ctx.message.author.id)
                            else:
                                # remove the last one
                                message_talker.pop()
                            if len(message_talker) == 0:
                                await ctx.message.add_reaction(EMOJI_ERROR)
                                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is not sufficient user to count.')
                            elif len(message_talker) < num_user:
                                try:
                                    await ctx.message.add_reaction(EMOJI_INFORMATION)
                                    await ctx.send(f'{EMOJI_INFORMATION} {ctx.author.mention} I could not find sufficient talkers up to **{num_user}**. I found only **{len(message_talker)}**'
                                                   f' and tip to those **{len(message_talker)}** users if they are still here.')
                                except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                    # No need to tip if failed to message
                                    await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                    return
                                # tip all user who are in the list
                                try:
                                    async with ctx.typing():
                                        await _tip_talker(ctx, amount, message_talker, False, COIN_NAME)
                                except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                    await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                    # zipped mouth but still need to do tip talker
                                    await _tip_talker(ctx, amount, message_talker, False, COIN_NAME)
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                            else:
                                try:
                                    async with ctx.typing():
                                        await _tip_talker(ctx, amount, message_talker, False, COIN_NAME)
                                except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                    await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                    # zipped mouth but still need to do tip talker
                                    await _tip_talker(ctx, amount, message_talker, False, COIN_NAME)
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                                return
                            return
                        else:
                            await ctx.message.add_reaction(EMOJI_ERROR)
                            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} What is this **{num_user}** number? Please give a number bigger than 0 :) ')
                            return
                    except ValueError:
                        await ctx.message.add_reaction(EMOJI_ERROR)
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid param after **LAST**.')
                    return
                time_string = ctx.message.content.lower().split("last", 1)[1].strip()
                time_second = None
                try:
                    time_string = time_string.replace("years", "y")
                    time_string = time_string.replace("yrs", "y")
                    time_string = time_string.replace("yr", "y")
                    time_string = time_string.replace("year", "y")
                    time_string = time_string.replace("months", "mon")
                    time_string = time_string.replace("month", "mon")
                    time_string = time_string.replace("mons", "mon")
                    time_string = time_string.replace("weeks", "w")
                    time_string = time_string.replace("week", "w")

                    time_string = time_string.replace("day", "d")
                    time_string = time_string.replace("days", "d")

                    time_string = time_string.replace("hours", "h")
                    time_string = time_string.replace("hour", "h")
                    time_string = time_string.replace("hrs", "h")
                    time_string = time_string.replace("hr", "h")

                    time_string = time_string.replace("minutes", "mn")
                    time_string = time_string.replace("mns", "mn")
                    time_string = time_string.replace("mins", "mn")
                    time_string = time_string.replace("min", "mn")
                    time_string = time_string.replace("m", "mn")

                    mult = {'y': 12*30*24*60*60, 'mon': 30*24*60*60, 'w': 7*24*60*60, 'd': 24*60*60, 'h': 60*60, 'mn': 60}
                    time_second = sum(int(num) * mult.get(val, 1) for num, val in re.findall('(\d+)(\w+)', time_string))
                except Exception as e:
                    await logchanbot(traceback.format_exc())
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid time given. Please use this example: `.tip 1,000 last 5h 12mn`')
                    return
                try:
                    time_given = int(time_second)
                except ValueError:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid time given check.')
                    return
                if time_given:
                    if time_given < 5*60 or time_given > 60*24*60*60:
                        await ctx.message.add_reaction(EMOJI_ERROR)
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please try time inteval between 5minutes to 24hours.')
                        return
                    else:
                        message_talker = await store.sql_get_messages(str(ctx.message.guild.id), str(ctx.message.channel.id), time_given, None)
                        if len(message_talker) == 0:
                            await ctx.message.add_reaction(EMOJI_ERROR)
                            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is no active talker in such period.')
                            return
                        else:
                            try:
                                async with ctx.typing():
                                    await _tip_talker(ctx, amount, message_talker, False, COIN_NAME)
                            except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                # zipped mouth but still need to do tip talker
                                await _tip_talker(ctx, amount, message_talker, False, COIN_NAME)
                            except Exception as e:
                                await logchanbot(traceback.format_exc())
                            return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                try:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    try:
                        await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        return
                return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            try:
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                try:
                    await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    return
            return
    elif len(ctx.message.mentions) == 1 and (bot.user in ctx.message.mentions):
        # Tip to TipBot
        member = ctx.message.mentions[0]
        print('TipBot is receiving tip from {} amount: {}{}'.format(ctx.message.author.name, amount, COIN_NAME))
    elif len(ctx.message.mentions) == 1 and (bot.user not in ctx.message.mentions):
        member = ctx.message.mentions[0]
        if ctx.message.author.id == member.id:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Tip me if you want.')
            return
        pass
    elif len(ctx.message.role_mentions) >= 1:
        mention_roles = ctx.message.role_mentions
        if "@everyone" in mention_roles:
            mention_roles.remove("@everyone")
            if len(mention_roles) < 1:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Can not find user to tip to.')
                return
        await _tip(ctx, amount, COIN_NAME)
        return
    elif len(ctx.message.mentions) > 1:
        await _tip(ctx, amount, COIN_NAME)
        return


    # Check flood of tip
    floodTip = await store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration)
    if floodTip >= config.floodTip:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Cool down your tip or TX. or increase your amount next time.')
        await botLogChan.send('A user reached max. TX threshold. Currently halted: `.tip`')
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
    # End Check if maintenance

    notifyList = await store.sql_get_tipnotify()

    user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    if user_from is None:
        if COIN_NAME in ENABLE_COIN_ERC:
            w = await create_address_eth()
            user_from = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0, w)
        else:
            user_from = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)
    userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), COIN_NAME)
    xfer_in = 0
    if COIN_NAME not in ENABLE_COIN_ERC:
        xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.message.author.id), COIN_NAME)
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
            msg_negative = 'Negative balance detected:\nUser: '+str(ctx.message.author.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
            await logchanbot(msg_negative)
    except Exception as e:
        await logchanbot(traceback.format_exc())

    user_to = await store.sql_get_userwallet(str(member.id), COIN_NAME)
    if user_to is None:
        if coin_family == "ERC-20":
            w = await create_address_eth()
            userregister = await store.sql_register_user(str(member.id), COIN_NAME, 'DISCORD', 0, w)
        else:
            userregister = await store.sql_register_user(str(member.id), COIN_NAME, 'DISCORD', 0)
        user_to = await store.sql_get_userwallet(str(member.id), COIN_NAME)

    if coin_family == "ERC-20":
        real_amount = float(amount)
        token_info = await store.get_token_info(COIN_NAME)
        MinTx = token_info['real_min_tip']
        MaxTX = token_info['real_max_tip']
    else:
        real_amount = int(Decimal(amount) * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
        MinTx = get_min_mv_amount(COIN_NAME)
        MaxTX = get_max_mv_amount(COIN_NAME)

    if real_amount > MaxTX:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                       f'{num_format_coin(MaxTX, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return
    elif real_amount > actual_balance:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send tip of '
                       f'{num_format_coin(real_amount, COIN_NAME)} '
                       f'{COIN_NAME} to {member.name}#{member.discriminator}.')
        return
    elif real_amount < MinTx:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                       f'{num_format_coin(MinTx, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return

    # add queue also tip
    if ctx.message.author.id not in TX_IN_PROCESS:
        TX_IN_PROCESS.append(ctx.message.author.id)
    else:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    tip = None
    try:
        if coin_family in ["TRTL", "BCN"]:
            tip = await store.sql_mv_cn_single(str(ctx.message.author.id), str(member.id), real_amount, 'TIP', COIN_NAME)
        elif coin_family == "XMR":
            tip = await store.sql_mv_xmr_single(str(ctx.message.author.id), str(member.id), real_amount, COIN_NAME, "TIP")
        elif coin_family == "DOGE":
            tip = await store.sql_mv_doge_single(str(ctx.message.author.id), str(member.id), real_amount, COIN_NAME, "TIP")
        elif coin_family == "NANO":
            tip = await store.sql_mv_nano_single(str(ctx.message.author.id), str(member.id), real_amount, COIN_NAME, "TIP")
        elif coin_family == "ERC-20":
            tip = await store.sql_mv_erc_single(str(ctx.message.author.id), str(member.id), real_amount, COIN_NAME, "TIP", token_info['contract'])
        if ctx.message.author.bot == False and serverinfo['react_tip'] == "ON":
            await ctx.message.add_reaction(EMOJI_TIP)
    except Exception as e:
        await logchanbot(traceback.format_exc())

    # remove queue from tip
    if ctx.message.author.id in TX_IN_PROCESS:
        TX_IN_PROCESS.remove(ctx.message.author.id)

    if tip:
        await ctx.message.add_reaction(get_emoji(COIN_NAME))
        # tipper shall always get DM. Ignore notifyList
        try:
            await ctx.message.author.send(
                f'{EMOJI_ARROW_RIGHTHOOK} Tip of {num_format_coin(real_amount, COIN_NAME)} '
                f'{COIN_NAME} '
                f'was sent to {member.name}#{member.discriminator} in server `{ctx.guild.name}`')
        except (discord.Forbidden, discord.errors.Forbidden) as e:
            await store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
        if bot.user.id != member.id and str(member.id) not in notifyList:
            try:
                await member.send(
                    f'{EMOJI_MONEYFACE} You got a tip of {num_format_coin(real_amount, COIN_NAME)} '
                    f'{COIN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{ctx.guild.name}` #{ctx.channel.name}\n'
                    f'{NOTIFICATION_OFF_CMD}\n')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await store.sql_toggle_tipnotify(str(member.id), "OFF")
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Can not deliver TX for {COIN_NAME} right now. Try again soon.')
        # add to failed tx table
        await store.sql_add_failed_tx(COIN_NAME, str(ctx.message.author.id), ctx.message.author.name, real_amount, "TIP")
        return


@bot.command(pass_context=True, aliases=['gtip', 'modtip', 'guildtip'])
@commands.has_permissions(manage_channels=True)
async def mtip(ctx, amount: str, *args):
    global TRTL_DISCORD, IS_RESTARTING, TX_IN_PROCESS
    # check if bot is going to restart
    if IS_RESTARTING:
        await ctx.message.add_reaction(EMOJI_REFRESH)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
        return
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'tip')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    # disable guild tip for TRTL discord
    if ctx.guild and ctx.guild.id == TRTL_DISCORD:
        await ctx.message.add_reaction(EMOJI_LOCKED)
        return

    # Check if tx in progress
    if ctx.guild.id in TX_IN_PROCESS:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} This guild have another tx in progress.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

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

    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    COIN_NAME = None
    try:
        COIN_NAME = args[0].upper()
        if COIN_NAME in ENABLE_XMR:
            pass
        elif COIN_NAME in ENABLE_COIN_NANO:
            pass
        elif COIN_NAME not in ENABLE_COIN:
            if COIN_NAME in ENABLE_COIN_DOGE+ENABLE_COIN_ERC:
                pass
            elif 'default_coin' in serverinfo:
                COIN_NAME = serverinfo['default_coin'].upper()
    except:
        if 'default_coin' in serverinfo:
            COIN_NAME = serverinfo['default_coin'].upper()
    print("COIN_NAME: " + COIN_NAME)

    # TRTL discord
    if ctx.guild.id == TRTL_DISCORD and COIN_NAME != "TRTL":
        return

    if not is_coin_tipable(COIN_NAME):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} TIPPING is currently disable for {COIN_NAME}.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    # Check allowed coins
    tiponly_coins = serverinfo['tiponly'].split(",")
    if COIN_NAME == serverinfo['default_coin'].upper() or serverinfo['tiponly'].upper() == "ALLCOIN":
        pass
    elif COIN_NAME not in tiponly_coins:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} not in allowed coins set by server manager.')
        return
    # End of checking allowed coins

    if is_maintenance_coin(COIN_NAME):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return

    if len(ctx.message.mentions) == 0 and len(ctx.message.role_mentions) == 0:
        # Use how time.
        if len(args) >= 2:
            time_given = None
            if args[0].upper() == "LAST" or args[1].upper() == "LAST":
                # try if the param is 1111u
                num_user = None
                if args[0].upper() == "LAST":
                    num_user = args[1].lower()
                elif args[1].upper() == "LAST":
                    num_user = args[2].lower()
                if 'u' in num_user or 'user' in num_user or 'users' in num_user or 'person' in num_user or 'people' in num_user:
                    num_user = num_user.replace("people", "")
                    num_user = num_user.replace("person", "")
                    num_user = num_user.replace("users", "")
                    num_user = num_user.replace("user", "")
                    num_user = num_user.replace("u", "")
                    try:
                        num_user = int(num_user)
                        if len(ctx.guild.members) <= 10:
                            await ctx.message.add_reaction(EMOJI_ERROR)
                            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please use normal tip command. There are only few users.')
                            return
                        # Check if we really have that many user in the guild 20%
                        elif num_user >= len(ctx.guild.members):
                            try:
                                await ctx.message.add_reaction(EMOJI_INFORMATION)
                                await ctx.send(f'{ctx.author.mention} Boss, you want to tip more than the number of people in this guild!?.'
                                               ' Can be done :). Wait a while.... I am doing it. (**counting..**)')
                            except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                # No need to tip if failed to message
                                await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                return
                            message_talker = await store.sql_get_messages(str(ctx.message.guild.id), str(ctx.message.channel.id), 0, len(ctx.guild.members))
                            if ctx.message.author.id in message_talker:
                                message_talker.remove(ctx.message.author.id)
                            if len(message_talker) == 0:
                                await ctx.message.add_reaction(EMOJI_ERROR)
                                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is not sufficient user to count.')
                            elif len(message_talker) < len(ctx.guild.members) - 1: # minus bot
                                await ctx.send(f'{EMOJI_INFORMATION} {ctx.author.mention} I could not find sufficient talkers up to **{num_user}**. I found only **{len(message_talker)}**'
                                               f' and tip to those **{len(message_talker)}** users if they are still here.')
                                # tip all user who are in the list
                                try:
                                    async with ctx.typing():
                                        await _tip_talker(ctx, amount, message_talker, True, COIN_NAME)
                                except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                    await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                    # zipped mouth but still need to do tip talker
                                    await _tip_talker(ctx, amount, message_talker, True, COIN_NAME)
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                            return
                        elif num_user > 0:
                            message_talker = await store.sql_get_messages(str(ctx.message.guild.id), str(ctx.message.channel.id), 0, num_user + 1)
                            if ctx.message.author.id in message_talker:
                                message_talker.remove(ctx.message.author.id)
                            else:
                                # remove the last one
                                message_talker.pop()
                            if len(message_talker) == 0:
                                await ctx.message.add_reaction(EMOJI_ERROR)
                                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is not sufficient user to count.')
                            elif len(message_talker) < num_user:
                                try:
                                    await ctx.message.add_reaction(EMOJI_INFORMATION)
                                    await ctx.send(f'{EMOJI_INFORMATION} {ctx.author.mention} I could not find sufficient talkers up to **{num_user}**. I found only **{len(message_talker)}**'
                                                   f' and tip to those **{len(message_talker)}** users if they are still here.')
                                except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                    # No need to tip if failed to message
                                    await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                    return
                                # tip all user who are in the list
                                try:
                                    async with ctx.typing():
                                        await _tip_talker(ctx, amount, message_talker, True, COIN_NAME)
                                except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                    await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                    # zipped mouth but still need to do tip talker
                                    await _tip_talker(ctx, amount, message_talker, True, COIN_NAME)
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                            else:
                                try:
                                    async with ctx.typing():
                                        await _tip_talker(ctx, amount, message_talker, True, COIN_NAME)
                                except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                    await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                    # zipped mouth but still need to do tip talker
                                    await _tip_talker(ctx, amount, message_talker, True, COIN_NAME)
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                                return
                            return
                        else:
                            await ctx.message.add_reaction(EMOJI_ERROR)
                            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} What is this **{num_user}** number? Please give a number bigger than 0 :) ')
                            return
                    except ValueError:
                        await ctx.message.add_reaction(EMOJI_ERROR)
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid param after **LAST**.')
                    return
                time_string = ctx.message.content.lower().split("last", 1)[1].strip()
                time_second = None
                try:
                    time_string = time_string.replace("years", "y")
                    time_string = time_string.replace("yrs", "y")
                    time_string = time_string.replace("yr", "y")
                    time_string = time_string.replace("year", "y")
                    time_string = time_string.replace("months", "mon")
                    time_string = time_string.replace("month", "mon")
                    time_string = time_string.replace("mons", "mon")
                    time_string = time_string.replace("weeks", "w")
                    time_string = time_string.replace("week", "w")

                    time_string = time_string.replace("day", "d")
                    time_string = time_string.replace("days", "d")

                    time_string = time_string.replace("hours", "h")
                    time_string = time_string.replace("hour", "h")
                    time_string = time_string.replace("hrs", "h")
                    time_string = time_string.replace("hr", "h")

                    time_string = time_string.replace("minutes", "mn")
                    time_string = time_string.replace("mns", "mn")
                    time_string = time_string.replace("mins", "mn")
                    time_string = time_string.replace("min", "mn")
                    time_string = time_string.replace("m", "mn")

                    mult = {'y': 12*30*24*60*60, 'mon': 30*24*60*60, 'w': 7*24*60*60, 'd': 24*60*60, 'h': 60*60, 'mn': 60}
                    time_second = sum(int(num) * mult.get(val, 1) for num, val in re.findall('(\d+)(\w+)', time_string))
                except Exception as e:
                    await logchanbot(traceback.format_exc())
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid time given. Please use this example: `.tip 1,000 last 5h 12mn`')
                    return
                try:
                    time_given = int(time_second)
                except ValueError:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid time given check.')
                    return
                if time_given:
                    if time_given < 5*60 or time_given > 60*24*60*60:
                        await ctx.message.add_reaction(EMOJI_ERROR)
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please try time inteval between 5minutes to 24hours.')
                        return
                    else:
                        message_talker = await store.sql_get_messages(str(ctx.message.guild.id), str(ctx.message.channel.id), time_given, None)
                        if len(message_talker) == 0:
                            await ctx.message.add_reaction(EMOJI_ERROR)
                            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is no active talker in such period.')
                            return
                        else:
                            try:
                                async with ctx.typing():
                                    await _tip_talker(ctx, amount, message_talker, True, COIN_NAME)
                            except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                # zipped mouth but still need to do tip talker
                                await _tip_talker(ctx, amount, message_talker, True, COIN_NAME)
                            except Exception as e:
                                await logchanbot(traceback.format_exc())
                            return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                try:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    try:
                        await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        return
                return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            try:
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                try:
                    await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    return
            return
    elif len(ctx.message.mentions) == 1 and (bot.user in ctx.message.mentions):
        # Tip to TipBot
        member = ctx.message.mentions[0]
        print('TipBot is receiving tip from {} amount: {}{}'.format(ctx.message.author.name, amount, COIN_NAME))
    elif len(ctx.message.mentions) == 1 and (bot.user not in ctx.message.mentions):
        member = ctx.message.mentions[0]
        if ctx.message.author.id == member.id:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Tip me if you want.')
            return
    elif len(ctx.message.role_mentions) >= 1:
        mention_roles = ctx.message.role_mentions
        if "@everyone" in mention_roles:
            mention_roles.remove("@everyone")
            if len(mention_roles) < 1:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Can not find user to tip to.')
                return
        await _tip(ctx, amount, COIN_NAME, True)
        return
    elif len(ctx.message.mentions) > 1:
        await _tip(ctx, amount, COIN_NAME, True)
        return

    # Check flood of tip
    floodTip = await store.sql_get_countLastTip(str(ctx.guild.id), config.floodTipDuration)
    if floodTip >= config.floodTip:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Cool down your tip or TX. or increase your amount next time.')
        await botLogChan.send('A guild reached max. TX threshold. Currently halted: `.tip`')
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
    # End Check if maintenance

    notifyList = await store.sql_get_tipnotify()
    address_to = None

    user_from = await store.sql_get_userwallet(str(ctx.guild.id), COIN_NAME)
    if user_from is None:
        user_from = await store.sql_register_user(str(ctx.guild.id), COIN_NAME, 'DISCORD', 0)
    # get user balance
    userdata_balance = await store.sql_user_balance(str(ctx.guild.id), COIN_NAME)
    xfer_in = 0
    if COIN_NAME not in ENABLE_COIN_ERC:
        xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.guild.id), COIN_NAME)
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
            msg_negative = 'Negative balance detected:\nGuild: '+str(ctx.guild.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
            await logchanbot(msg_negative)
    except Exception as e:
        await logchanbot(traceback.format_exc())

    user_to = await store.sql_get_userwallet(str(member.id), COIN_NAME)
    if user_to is None:
        userregister = await store.sql_register_user(str(member.id), COIN_NAME, 'DISCORD', 0)
        user_to = await store.sql_get_userwallet(str(member.id), COIN_NAME)
 
    real_amount = int(Decimal(amount) * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
    MinTx = get_min_mv_amount(COIN_NAME)
    MaxTX = get_max_mv_amount(COIN_NAME)

    if real_amount > MaxTX:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                       f'{num_format_coin(MaxTX, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return
    elif real_amount > actual_balance:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send tip of '
                       f'{num_format_coin(real_amount, COIN_NAME)} '
                       f'{COIN_NAME} to {member.name}#{member.discriminator}.')
        return
    elif real_amount < MinTx:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                       f'{num_format_coin(MinTx, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return

    tipmsg = ""
    try:
        if serverinfo['tip_message']: tipmsg = "**Guild Message:**\n" + serverinfo['tip_message']
    except Exception as e:
        pass

    tip = None
    try:
        if coin_family in ["TRTL", "BCN"]:
            tip = await store.sql_mv_cn_single(str(ctx.guild.id), str(member.id), real_amount, 'TIP', COIN_NAME)
        elif coin_family == "XMR":
            tip = await store.sql_mv_xmr_single(str(ctx.guild.id), str(member.id), real_amount, COIN_NAME, "TIP")
        elif coin_family == "DOGE":
            tip = await store.sql_mv_doge_single(str(ctx.guild.id), str(member.id), real_amount, COIN_NAME, "TIP")
        elif coin_family == "NANO":
            tip = await store.sql_mv_nano_single(str(ctx.guild.id), str(member.id), real_amount, COIN_NAME, "TIP")
        elif coin_family == "ERC-20":
            token_info = await store.get_token_info(COIN_NAME)
            tip = await store.sql_mv_erc_single(str(ctx.guild.id), str(member.id), real_amount, COIN_NAME, "TIP", token_info['contract'])
        if ctx.message.author.bot == False and serverinfo['react_tip'] == "ON":
            await ctx.message.add_reaction(EMOJI_TIP)
    except Exception as e:
        await logchanbot(traceback.format_exc())
    if tip:
        await ctx.message.add_reaction(get_emoji(COIN_NAME))
        # tipper shall always get DM. Ignore notifyList
        try:
            await ctx.message.author.send(
                f'{EMOJI_ARROW_RIGHTHOOK} Guild tip of {num_format_coin(real_amount, COIN_NAME)} '
                f'{COIN_NAME} '
                f'was sent to {member.name}#{member.discriminator} in server `{ctx.guild.name}`\n')
        except (discord.Forbidden, discord.errors.Forbidden) as e:
            await store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
        if bot.user.id != member.id and str(member.id) not in notifyList:
            try:
                await member.send(
                    f'{EMOJI_MONEYFACE} You got a guild tip of {num_format_coin(real_amount, COIN_NAME)} '
                    f'{COIN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{ctx.guild.name}` #{ctx.channel.name}\n'
                    f'{NOTIFICATION_OFF_CMD}\n{tipmsg}')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await store.sql_toggle_tipnotify(str(member.id), "OFF")
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Can not deliver TX for {COIN_NAME} right now. Try again soon.')
        # add to failed tx table
        await store.sql_add_failed_tx(COIN_NAME, str(ctx.message.author.id), ctx.message.author.name, real_amount, "TIP")
        return


@bot.command(pass_context=True, help=bot_help_tipall, hidden = True)
async def tipall(ctx, amount: str, coin: str, option: str=None):
    global IS_RESTARTING, TX_IN_PROCESS
    # check if bot is going to restart
    if IS_RESTARTING:
        await ctx.message.add_reaction(EMOJI_REFRESH)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
        return
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'tipall')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    # Check if tx in progress
    if ctx.message.author.id in TX_IN_PROCESS:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    botLogChan = bot.get_channel(id=LOG_CHAN)
    amount = amount.replace(",", "")

    try:
        amount = Decimal(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send(f'{EMOJI_RED_NO} This command can not be in private.')
        return

    COIN_NAME = coin.upper()

    # TRTL discord
    if ctx.guild.id == TRTL_DISCORD and COIN_NAME != "TRTL":
        return

    if COIN_NAME not in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
        return

    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    option = option.upper() if option else "ONLINE"
    option_list = ["ALL", "ONLINE"]
    if option not in option_list:
        allow_option = ", ".join(option_list)
        await ctx.message.add_reaction(EMOJI_ERROR)
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} TIPALL is currently support only option **{allow_option}**.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    print('TIPALL COIN_NAME:' + COIN_NAME)
    if not is_coin_tipable(COIN_NAME):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} TIPPING is currently disable for {COIN_NAME}.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    if is_maintenance_coin(COIN_NAME):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} in maintenance.')
        return

    # Check allowed coins
    tiponly_coins = serverinfo['tiponly'].split(",")
    if COIN_NAME == serverinfo['default_coin'].upper() or serverinfo['tiponly'].upper() == "ALLCOIN":
        pass
    elif COIN_NAME not in tiponly_coins:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} not in allowed coins set by server manager.')
        return
    # End of checking allowed coins

    # Check flood of tip
    floodTip = await store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration)
    if floodTip >= config.floodTip:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Cool down your tip or TX. or increase your amount next time.')
        await botLogChan.send('A user reached max. TX threshold. Currently halted: `.tipall`')
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

    notifyList = await store.sql_get_tipnotify()
    if coin_family == "ERC-20":
        real_amount = float(amount)
        token_info = await store.get_token_info(COIN_NAME)
        MinTx = token_info['real_min_tip']
        MaxTX = token_info['real_max_tip']
    else:
        real_amount = int(Decimal(amount) * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
        MinTx = get_min_mv_amount(COIN_NAME)
        MaxTX = get_max_mv_amount(COIN_NAME)

    # [x.guild for x in [g.members for g in bot.guilds] if x.id = useridyourelookingfor]
    if option == "ONLINE":
        listMembers = [member for member in ctx.guild.members if member.status != discord.Status.offline and member.bot == False]
    elif option == "ALL":
        listMembers = [member for member in ctx.guild.members if member.bot == False]
    print("Number of tip-all in {}: {}".format(ctx.guild.name, len(listMembers)))
    # Check number of receivers.
    if len(listMembers) > config.tipallMax_Offchain:
        await ctx.message.add_reaction(EMOJI_ERROR)
        try:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} The number of receivers are too many. This command isn\'t available here.')
        except (discord.Forbidden, discord.errors.Forbidden) as e:
            await ctx.message.author.send(f'{EMOJI_RED_NO} The number of receivers are too many in `{ctx.guild.name}`. This command isn\'t available here.')
        return
    # End of checking receivers numbers.
    await logchanbot("{}#{} issuing TIPALL {}{} in {}/{} with {} users.".format(ctx.author.name, ctx.author.discriminator, 
                                                                                num_format_coin(real_amount, COIN_NAME), COIN_NAME,
                                                                                ctx.guild.id, ctx.guild.name, len(listMembers)))
    list_receivers = []
    addresses = []
    for member in listMembers:
        # print(member.name) # you'll just print out Member objects your way.
        if ctx.message.author.id != member.id and member.id != bot.user.id:
            user_to = await store.sql_get_userwallet(str(member.id), COIN_NAME)
            if user_to is None:
                if coin_family == "ERC-20":
                    w = await create_address_eth()
                    userregister = await store.sql_register_user(str(member.id), COIN_NAME, 'DISCORD', 0, w)
                else:
                    userregister = await store.sql_register_user(str(member.id), COIN_NAME, 'DISCORD', 0)
                user_to = await store.sql_get_userwallet(str(member.id), COIN_NAME)
            list_receivers.append(str(member.id))

    user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    if user_from is None:
        if coin_family == "ERC-20":
            w = await create_address_eth()
            user_from = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0, w)
        else:
            user_from = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)

    # get user balance
    userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), COIN_NAME)
    xfer_in = 0
    if COIN_NAME not in ENABLE_COIN_ERC: 
        xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.message.author.id), COIN_NAME)
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
            msg_negative = 'Negative balance detected:\nUser: '+str(ctx.message.author.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
            await logchanbot(msg_negative)
    except Exception as e:
        await logchanbot(traceback.format_exc())

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
    elif real_amount > actual_balance:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to spread tip of '
                       f'{num_format_coin(real_amount, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return
    elif (real_amount / len(list_receivers)) < MinTx:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                       f'{num_format_coin(MinTx, COIN_NAME)} '
                       f'{COIN_NAME} for each member. You need at least {num_format_coin(len(list_receivers) * MinTx, COIN_NAME)}{COIN_NAME}.')
        return

    amountDiv = int(round(real_amount / len(list_receivers), 2))  # cut 2 decimal only
    if coin_family == "DOGE" or coin_family == "ERC-20":
        amountDiv = round(real_amount / len(list_receivers), 4)
        if (real_amount / len(list_receivers)) < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                           f'{num_format_coin(MinTx, COIN_NAME)} '
                           f'{COIN_NAME} for each member. You need at least {num_format_coin(len(list_receivers) * MinTx, COIN_NAME)}{COIN_NAME}.')
            return

    if len(list_receivers) < 1:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is no one to tip to.')
        return

    # add queue also tipall
    if ctx.message.author.id not in TX_IN_PROCESS:
        TX_IN_PROCESS.append(ctx.message.author.id)
    else:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    tip = None
    try:
        if coin_family in ["TRTL", "BCN"]:
            tip = await store.sql_mv_cn_multiple(str(ctx.message.author.id), amountDiv, list_receivers, 'TIPALL', COIN_NAME)
        elif coin_family == "XMR":
            tip = await store.sql_mv_xmr_multiple(str(ctx.message.author.id), list_receivers, amountDiv, COIN_NAME, "TIPALL")
        elif coin_family == "NANO":
            tip = await store.sql_mv_nano_multiple(str(ctx.message.author.id), list_receivers, amountDiv, COIN_NAME, "TIPALL")
        elif coin_family == "DOGE":
            tip = await store.sql_mv_doge_multiple(str(ctx.message.author.id), list_receivers, amountDiv, COIN_NAME, "TIPALL")
        elif coin_family == "ERC-20":
            tip = await store.sql_mv_erc_multiple(str(ctx.message.author.id), list_receivers, amountDiv, COIN_NAME, "TIPALL", token_info['contract'])
    except Exception as e:
        await logchanbot(traceback.format_exc())
    await asyncio.sleep(config.interval.tx_lap_each)

    # remove queue from tipall
    if ctx.message.author.id in TX_IN_PROCESS:
        TX_IN_PROCESS.remove(ctx.message.author.id)

    if tip:
        tipAmount = num_format_coin(real_amount, COIN_NAME)
        ActualSpend_str = num_format_coin(amountDiv * len(list_receivers), COIN_NAME)
        amountDiv_str = num_format_coin(amountDiv, COIN_NAME)
        await ctx.message.add_reaction(get_emoji(COIN_NAME))
        # tipper shall always get DM. Ignore notifyList
        try:
            await ctx.message.author.send(
                f'{EMOJI_ARROW_RIGHTHOOK} Tip of {tipAmount} '
                f'{COIN_NAME} '
                f'was sent spread to ({len(list_receivers)}) members in server `{ctx.guild.name}`.\n'
                f'Each member got: `{amountDiv_str}{COIN_NAME}`\n'
                f'Actual spending: `{ActualSpend_str}{COIN_NAME}`')
        except (discord.Forbidden, discord.errors.Forbidden) as e:
            await store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
        numMsg = 0
        for member in listMembers:
            if ctx.message.author.id != member.id and member.id != bot.user.id:
                if str(member.id) not in notifyList:
                    # random user to DM
                    dm_user = bool(random.getrandbits(1)) if len(listMembers) > config.tipallMax_LimitDM else True
                    if dm_user:
                        try:
                            await member.send(
                                f'{EMOJI_MONEYFACE} You got a tip of {amountDiv_str} '
                                f'{COIN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} `.tipall` in server `{ctx.guild.name}` #{ctx.channel.name}\n'
                                f'{NOTIFICATION_OFF_CMD}')
                            numMsg += 1
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            await store.sql_toggle_tipnotify(str(member.id), "OFF")
            if numMsg >= config.tipallMax_LimitDM:
                # stop DM if reaches
                break
        return


@bot.command(pass_context=True, help=bot_help_send)
async def send(ctx, amount: str, CoinAddress: str, coin: str=None):
    global TX_IN_PROCESS, IS_RESTARTING
    # check if bot is going to restart
    if IS_RESTARTING:
        await ctx.message.add_reaction(EMOJI_REFRESH)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
        return
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'send')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    botLogChan = bot.get_channel(id=LOG_CHAN)
    amount = amount.replace(",", "")

    # Check if tx in progress
    if ctx.message.author.id in TX_IN_PROCESS:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    # if public and there is a bot channel
    if isinstance(ctx.channel, discord.DMChannel) == False:
        serverinfo = await get_info_pref_coin(ctx)
        server_prefix = serverinfo['server_prefix']
        # check if bot channel is set:
        if serverinfo and serverinfo['botchan']:
            try: 
                if ctx.channel.id != int(serverinfo['botchan']):
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    botChan = bot.get_channel(id=int(serverinfo['botchan']))
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, {botChan.mention} is the bot channel!!!')
                    return
            except ValueError:
                pass
        # end of bot channel check

    # Check flood of tip
    floodTip = await store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration)
    if floodTip >= config.floodTip:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO}{ctx.author.mention} Cool down your tip or TX. or increase your amount next time.')
        await botLogChan.send('A user reached max. TX threshold. Currently halted: `.send`')
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
        amount = Decimal(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    # Check which coinname is it.
    COIN_NAME = get_cn_coin_from_address(CoinAddress)
    if COIN_NAME is None and CoinAddress.startswith("0x"):
        if coin is None:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} you need to add **TOKEN NAME** address.')
            return
        else:
            COIN_NAME = coin.upper()
            if COIN_NAME not in ENABLE_COIN_ERC:
                await ctx.message.add_reaction(EMOJI_WARNING)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Unsupported Token.')
                return
        if CoinAddress.upper().startswith("0X00000000000000000000000000000"):
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid token address:\n'
                                 f'`{CoinAddress}`')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        else:
            try:
                valid_address = await store.erc_validate_address(CoinAddress, COIN_NAME)
                if valid_address and valid_address.upper() == CoinAddress.upper():
                    valid = True
                else:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid token address:\n'
                                         f'`{CoinAddress}`')
                    await msg.add_reaction(EMOJI_OK_BOX)
                    return
            except Exception as e:
                print(traceback.format_exc())
                await logchanbot(traceback.format_exc())
                await ctx.message.add_reaction(EMOJI_ERROR)
                msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} internal error checking address:\n'
                                     f'`{CoinAddress}`')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
    coin_family = None
    if not is_coin_txable(COIN_NAME):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} TX is currently disable for {COIN_NAME}.')
        await msg.add_reaction(EMOJI_OK_BOX)
        await logchanbot(f'User {ctx.author.id} tried to send {amount}{COIN_NAME} while it tx not enable.')
        return
    if COIN_NAME:
        if COIN_NAME in ENABLE_COIN_ERC:
            coin_family = "ERC-20"
        else:
            coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    else:
        await ctx.message.add_reaction(EMOJI_QUESTEXCLAIM)
        try:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} could not find what address it is.')
        except (discord.Forbidden, discord.errors.Forbidden) as e:
            try:
                await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} could not find what address it is.')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                return
        return

    # add redis action
    random_string = str(uuid.uuid4())
    await add_tx_action_redis(json.dumps([random_string, "SEND", str(ctx.message.author.id), ctx.message.author.name, float("%.3f" % time.time()), ctx.message.content, "DISCORD", "START"]), False)

    if coin_family in ["TRTL", "BCN"]:
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        real_amount = int(amount * get_decimal(COIN_NAME))
        addressLength = get_addrlen(COIN_NAME)
        IntaddressLength = get_intaddrlen(COIN_NAME)
        NetFee = get_reserved_fee(coin = COIN_NAME)
        # Currently we have two BCN coins
        if coin_family == "BCN":
            NetFee = get_tx_fee(coin = COIN_NAME)
        if is_maintenance_coin(COIN_NAME):
            await ctx.message.add_reaction(EMOJI_MAINTENANCE)
            try:
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                try:
                    await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    return
            return

        print('{} - {} - {}'.format(COIN_NAME, addressLength, IntaddressLength))
        if len(CoinAddress) == int(addressLength):
            valid_address = addressvalidation.validate_address_cn(CoinAddress, COIN_NAME)
            # print(valid_address)
            if valid_address != CoinAddress:
                valid_address = None

            if valid_address is None:
                await ctx.message.add_reaction(EMOJI_QUESTEXCLAIM)
                try:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                                   f'`{CoinAddress}`')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    try:
                        await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                                                      f'`{CoinAddress}`')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        return
                return
        elif len(CoinAddress) == int(IntaddressLength):
            valid_address = addressvalidation.validate_integrated_cn(CoinAddress, COIN_NAME)
            # print(valid_address)
            if valid_address == 'invalid':
                await ctx.message.add_reaction(EMOJI_QUESTEXCLAIM)
                try:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid integrated address:\n'
                                   f'`{CoinAddress}`')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    try:
                        await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid integrated address:\n'
                                                      f'`{CoinAddress}`')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        return
                return
            if len(valid_address) == 2:
                iCoinAddress = CoinAddress
                CoinAddress = valid_address['address']
                paymentid = valid_address['integrated_id']
        elif len(CoinAddress) == int(addressLength) + 64 + 1:
            valid_address = {}
            check_address = CoinAddress.split(".")
            if len(check_address) != 2:
                await ctx.message.add_reaction(EMOJI_QUESTEXCLAIM)
                try:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid {COIN_NAME} address + paymentid')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    try:
                        await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid {COIN_NAME} address + paymentid')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        return
                return
            else:
                valid_address_str = addressvalidation.validate_address_cn(check_address[0], COIN_NAME)
                paymentid = check_address[1].strip()
                if valid_address_str is None:
                    await ctx.message.add_reaction(EMOJI_QUESTEXCLAIM)
                    try:
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                                       f'`{check_address[0]}`')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        try:
                            await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                                                          f'`{check_address[0]}`')
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            return
                    return
                else:
                    valid_address['address'] = valid_address_str
            # Check payment ID
                if len(paymentid) == 64:
                    if not re.match(r'[a-zA-Z0-9]{64,}', paymentid.strip()):
                        await ctx.message.add_reaction(EMOJI_QUESTEXCLAIM)
                        try:
                            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} PaymentID: `{paymentid}`\n'
                                            'Should be in 64 correct format.')
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            try:
                                await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} PaymentID: `{paymentid}`\n'
                                                              'Should be in 64 correct format.')
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                return
                        return
                    else:
                        CoinAddress = valid_address['address']
                        valid_address['paymentid'] = paymentid
                        iCoinAddress = addressvalidation.make_integrated_cn(valid_address['address'], COIN_NAME, paymentid)['integrated_address']
                        pass
                else:
                    await ctx.message.add_reaction(EMOJI_QUESTEXCLAIM)
                    try:
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} PaymentID: `{paymentid}`\n'
                                        'Incorrect length')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        try:
                            await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} PaymentID: `{paymentid}`\n'
                                                         'Incorrect length')
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            return
                    return
        else:
            await ctx.message.add_reaction(EMOJI_QUESTEXCLAIM)
            try:
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                               f'`{CoinAddress}`')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                try:
                    await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                                                  f'`{CoinAddress}`')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    return
            return

        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if user_from is None:
            user_from = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)
        if user_from['balance_wallet_address'] == CoinAddress:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You can not send to your own deposit address.')
            return

        userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), COIN_NAME)
        xfer_in = 0
        if COIN_NAME not in ENABLE_COIN_ERC:
            xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.message.author.id), COIN_NAME)
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
                msg_negative = 'Negative balance detected:\nUser: '+str(ctx.message.author.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                await logchanbot(msg_negative)
        except Exception as e:
            await logchanbot(traceback.format_exc())

        if real_amount + NetFee > actual_balance:
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
        walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
        if walletStatus is None:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} I can not connect to wallet service or daemon.')
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
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} Wallet service hasn\'t sync fully with network or being re-sync. More info:\n```'
                               f'networkBlockCount:     {t_networkBlockCount}\n'
                               f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                               f'Progress %:            {t_percent}\n```'
                               )
                return
            else:
                pass
        # End of wallet status

        main_address = getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
        if CoinAddress == main_address:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, Can not send to this address:\n```{CoinAddress}``` ')
            return
        
        if len(valid_address) == 2:
            tip = None
            try:
                if ctx.message.author.id not in TX_IN_PROCESS:
                    TX_IN_PROCESS.append(ctx.message.author.id)
                    try:
                        tip = await store.sql_external_cn_single_id(str(ctx.message.author.id), CoinAddress, real_amount, paymentid, COIN_NAME)
                        tip_tx_tipper = "Transaction hash: `{}`".format(tip['transactionHash'])
                        tip_tx_tipper += "\nTx Fee: `{}{}`".format(num_format_coin(tip['fee'], COIN_NAME), COIN_NAME)
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                    await asyncio.sleep(config.interval.tx_lap_each)
                    TX_IN_PROCESS.remove(ctx.message.author.id)
                else:
                    await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
                    msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
                    await msg.add_reaction(EMOJI_OK_BOX)
                    return                    
            except Exception as e:
                await logchanbot(traceback.format_exc())
            if tip:
                await ctx.message.add_reaction(get_emoji(COIN_NAME))
                await botLogChan.send(f'A user successfully executed `.send {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}` with paymentid.')
                await ctx.message.author.send(
                                       f'{EMOJI_ARROW_RIGHTHOOK} You have sent {num_format_coin(real_amount, COIN_NAME)} '
                                       f'{COIN_NAME} '
                                       f'to `{iCoinAddress}`\n\n'
                                       f'Address: `{CoinAddress}`\n'
                                       f'Payment ID: `{paymentid}`\n'
                                       f'{tip_tx_tipper}')
                return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await botLogChan.send(f'A user failed to execute send `{num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}` with paymentid.')
                msg = await ctx.send(f'{ctx.author.mention} Please try again or report.')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
        else:
            tip = None
            try:
                if ctx.message.author.id not in TX_IN_PROCESS:
                    TX_IN_PROCESS.append(ctx.message.author.id)
                    try:
                        tip = await store.sql_external_cn_single(str(ctx.message.author.id), CoinAddress, real_amount, COIN_NAME)
                        tip_tx_tipper = "Transaction hash: `{}`".format(tip['transactionHash'])
                        tip_tx_tipper += "\nTx Fee: `{}{}`".format(num_format_coin(tip['fee'], COIN_NAME), COIN_NAME)
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                    await asyncio.sleep(config.interval.tx_lap_each)
                    TX_IN_PROCESS.remove(ctx.message.author.id)
                    # add redis
                    await add_tx_action_redis(json.dumps([random_string, "SEND", str(ctx.message.author.id), ctx.message.author.name, float("%.3f" % time.time()), ctx.message.content, "DISCORD", "COMPLETE"]), False)
                else:
                    await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
                    msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
                    await msg.add_reaction(EMOJI_OK_BOX)
                    return
            except Exception as e:
                await logchanbot(traceback.format_exc())
            if tip:
                await ctx.message.add_reaction(get_emoji(COIN_NAME))
                await botLogChan.send(f'A user successfully executed `.send {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`.')
                await ctx.message.author.send(f'{EMOJI_ARROW_RIGHTHOOK} You have sent {num_format_coin(real_amount, COIN_NAME)} '
                                              f'{COIN_NAME} '
                                              f'to `{CoinAddress}`\n'
                                              f'{tip_tx_tipper}')
                return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await botLogChan.send(f'A user failed to execute `.send {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`.')
                await ctx.send(f'{ctx.author.mention} Can not deliver TX for {COIN_NAME} right now. Try again soon.')
                # add to failed tx table
                await store.sql_add_failed_tx(COIN_NAME, str(ctx.message.author.id), ctx.message.author.name, real_amount, "SEND")
                return
    elif coin_family == "XMR":
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        real_amount = int(amount * get_decimal(COIN_NAME))
        addressLength = get_addrlen(COIN_NAME)
        IntaddressLength = get_intaddrlen(COIN_NAME)

        # If not Masari
        if COIN_NAME not in ["MSR", "UPX"]:
            valid_address = await validate_address_xmr(str(CoinAddress), COIN_NAME)
            if valid_address['valid'] == False or valid_address['nettype'] != 'mainnet':
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Address: `{CoinAddress}` '
                                   'is invalid.')
                    return
        # OK valid address
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if user_from is None:
            user_from = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)
        userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), COIN_NAME)
        xfer_in = 0
        if COIN_NAME not in ENABLE_COIN_ERC:
            xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.message.author.id), COIN_NAME)
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
                msg_negative = 'Negative balance detected:\nUser: '+str(ctx.message.author.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                await logchanbot(msg_negative)
        except Exception as e:
            await logchanbot(traceback.format_exc())

        # If balance 0, no need to check anything
        if actual_balance <= 0:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please check your **{COIN_NAME}** balance.')
            return
        NetFee = await get_tx_fee_xmr(coin = COIN_NAME, amount = real_amount, to_address = CoinAddress)
        if NetFee is None:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Can not get fee from network for: '
                           f'{num_format_coin(real_amount, COIN_NAME)} '
                           f'{COIN_NAME}. Please try again later in a few minutes.')
            return
        if real_amount + NetFee > actual_balance:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send out '
                           f'{num_format_coin(real_amount, COIN_NAME)} '
                           f'{COIN_NAME}. You need to leave at least network fee: {num_format_coin(NetFee, COIN_NAME)}{COIN_NAME}')
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

        SendTx = None
        if ctx.message.author.id not in TX_IN_PROCESS:
            TX_IN_PROCESS.append(ctx.message.author.id)
            try:
                SendTx = await store.sql_external_xmr_single(str(ctx.message.author.id), real_amount,
                                                             CoinAddress, COIN_NAME, "SEND")
                # add redis
                await add_tx_action_redis(json.dumps([random_string, "SEND", str(ctx.message.author.id), ctx.message.author.name, float("%.3f" % time.time()), ctx.message.content, "DISCORD", "COMPLETE"]), False)
            except Exception as e:
                await logchanbot(traceback.format_exc())
            await asyncio.sleep(config.interval.tx_lap_each)
            TX_IN_PROCESS.remove(ctx.message.author.id)
        else:
            # reject and tell to wait
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You have another tx in process. Please wait it to finish. ')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        if SendTx:
            SendTx_hash = SendTx['tx_hash']
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
            await botLogChan.send(f'A user successfully executed `.send {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`.')
            await ctx.message.author.send(f'{EMOJI_ARROW_RIGHTHOOK} You have sent {num_format_coin(real_amount, COIN_NAME)} '
                                          f'{COIN_NAME} to `{CoinAddress}`.\n'
                                          f'Transaction hash: `{SendTx_hash}`\n'
                                          'Network fee deducted from your account balance.')
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await botLogChan.send(f'A user failed to execute `.send {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`.')
            return
        return
    elif coin_family == "NANO":
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        real_amount = int(amount * get_decimal(COIN_NAME))
        addressLength = get_addrlen(COIN_NAME)

        # Validate address
        valid_address = await nano_validate_address(COIN_NAME, str(CoinAddress))
        if not valid_address == True:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}` is invalid.')
            return

        # OK valid address
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if user_from is None:
            user_from = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)
        userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), COIN_NAME)
        xfer_in = 0
        if COIN_NAME not in ENABLE_COIN_ERC:
            xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.message.author.id), COIN_NAME)
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
                msg_negative = 'Negative balance detected:\nUser: '+str(ctx.message.author.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                await logchanbot(msg_negative)
        except Exception as e:
            await logchanbot(traceback.format_exc())

        # If balance 0, no need to check anything
        if actual_balance <= 0:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please check your **{COIN_NAME}** balance.')
            return

        if real_amount > actual_balance:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send out '
                           f'{num_format_coin(real_amount, COIN_NAME)}')
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

        SendTx = None
        if ctx.message.author.id not in TX_IN_PROCESS:
            TX_IN_PROCESS.append(ctx.message.author.id)
            try:
                SendTx = await store.sql_external_nano_single(str(ctx.message.author.id), real_amount,
                                                              CoinAddress, COIN_NAME, "SEND")
                # add redis
                await add_tx_action_redis(json.dumps([random_string, "SEND", str(ctx.message.author.id), ctx.message.author.name, float("%.3f" % time.time()), ctx.message.content, "DISCORD", "COMPLETE"]), False)
            except Exception as e:
                await logchanbot(traceback.format_exc())
            await asyncio.sleep(config.interval.tx_lap_each)
            TX_IN_PROCESS.remove(ctx.message.author.id)
        else:
            # reject and tell to wait
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You have another tx in process. Please wait it to finish. ')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        if SendTx:
            SendTx_hash = SendTx['block']
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
            await botLogChan.send(f'A user successfully executed `.send {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`.')
            await ctx.message.author.send(f'{EMOJI_ARROW_RIGHTHOOK} You have sent {num_format_coin(real_amount, COIN_NAME)} '
                                          f'{COIN_NAME} to `{CoinAddress}`.\n'
                                          f'Transaction hash: `{SendTx_hash}`')
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await botLogChan.send(f'A user failed to execute `.send {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`.')
            return
        return
    if coin_family == "DOGE" or coin_family == "ERC-20":
        if coin_family == "ERC-20":
            token_info = await store.get_token_info(COIN_NAME)
            MinTx = token_info['real_min_tx']
            MaxTX = token_info['real_max_tx']
            NetFee = token_info['real_withdraw_fee']
        else:
            MinTx = get_min_tx_amount(coin = COIN_NAME)
            MaxTX = get_max_tx_amount(coin = COIN_NAME)
            NetFee = get_tx_fee(coin = COIN_NAME)
            valid_address = await doge_validaddress(str(CoinAddress), COIN_NAME)
            if 'isvalid' in valid_address:
                if str(valid_address['isvalid']) == "True":
                    pass
                else:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Address: `{CoinAddress}` '
                                    'is invalid.')
                    return
    
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if user_from is None:
            if coin_family == "ERC-20":
                w = await create_address_eth()
                userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0, w)
            else:
                user_from = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)
        real_amount = float(amount)
        userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), COIN_NAME)
        xfer_in = 0
        if COIN_NAME not in ENABLE_COIN_ERC:
            xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.message.author.id), COIN_NAME)
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
                msg_negative = 'Negative balance detected:\nUser: '+str(ctx.message.author.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                await logchanbot(msg_negative)
        except Exception as e:
            await logchanbot(traceback.format_exc())

        if real_amount + NetFee > actual_balance:
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
        SendTx = None
        if ctx.message.author.id not in TX_IN_PROCESS:
            TX_IN_PROCESS.append(ctx.message.author.id)
            try:
                if COIN_NAME in ENABLE_COIN_ERC:
                    SendTx = await store.sql_external_erc_single(str(ctx.author.id), CoinAddress, real_amount, COIN_NAME, 'SEND', 'DISCORD')
                else:
                    SendTx = await store.sql_external_doge_single(str(ctx.message.author.id), real_amount, NetFee,
                                                                  CoinAddress, COIN_NAME, "SEND")
                # add redis
                await add_tx_action_redis(json.dumps([random_string, "SEND", str(ctx.message.author.id), ctx.message.author.name, float("%.3f" % time.time()), ctx.message.content, "DISCORD", "COMPLETE"]), False)
            except Exception as e:
                await logchanbot(traceback.format_exc())
            await asyncio.sleep(config.interval.tx_lap_each)
            TX_IN_PROCESS.remove(ctx.message.author.id)
        else:
            await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
            msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        if SendTx:
            if COIN_NAME in ENABLE_COIN_ERC:
                extra_txt = f"Fee `{NetFee}{COIN_NAME}` deducted from your balance."
                await ctx.message.add_reaction(TOKEN_EMOJI)
            else:
                await ctx.message.add_reaction(get_emoji(COIN_NAME))
                extra_txt = "Network fee deducted from the amount."
            await botLogChan.send(f'A user successfully executed `.send {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`.')
            await ctx.message.author.send(f'{EMOJI_ARROW_RIGHTHOOK} You have sent {num_format_coin(real_amount, COIN_NAME)} '
                                          f'{COIN_NAME} to `{CoinAddress}`.\n'
                                          f'Transaction hash: `{SendTx}`\n'
                                          f'{extra_txt}')
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


@bot.command(pass_context=True, name='address', aliases=['addr'], help=bot_help_address)
async def address(ctx, *args):
    prefix = await get_guild_prefix(ctx)

    # if public and there is a bot channel
    if isinstance(ctx.channel, discord.DMChannel) == False:
        serverinfo = await get_info_pref_coin(ctx)
        server_prefix = serverinfo['server_prefix']
        # check if bot channel is set:
        if serverinfo and serverinfo['botchan']:
            try: 
                if ctx.channel.id != int(serverinfo['botchan']):
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    botChan = bot.get_channel(id=int(serverinfo['botchan']))
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, {botChan.mention} is the bot channel!!!')
                    return
            except ValueError:
                pass
        # end of bot channel check

    if len(args) == 0:
        if isinstance(ctx.message.channel, discord.DMChannel):
            COIN_NAME = 'WRKZ'
        else:
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            try:
                COIN_NAME = args[0].upper()
                if COIN_NAME not in ENABLE_COIN:
                    if COIN_NAME in ENABLE_COIN_DOGE+ENABLE_COIN_ERC:
                        pass
                    elif 'default_coin' in serverinfo:
                        COIN_NAME = serverinfo['default_coin'].upper()
                else:
                    pass
            except:
                if 'default_coin' in serverinfo:
                    COIN_NAME = serverinfo['default_coin'].upper()
            print("COIN_NAME: " + COIN_NAME)
        # TODO: change this.
        if COIN_NAME:
            main_address = getattr(getattr(config,"daemon"+COIN_NAME),"MainAddress")
            await ctx.send('**[ ADDRESS CHECKING EXAMPLES ]**\n\n'
                           f'```.address {main_address}\n'
                           'That will check if the address is valid. Integrated address is also supported. '
                           'If integrated address is input, bot will tell you the result of :address + paymentid\n\n'
                           f'{prefix}address <coin_address> <paymentid>\n'
                           'This will generate an integrate address.\n\n'
                           f'If you would like to get your address, please use {prefix}deposit {COIN_NAME} instead.```')
        else:
            await ctx.send('**[ ADDRESS CHECKING EXAMPLES ]**\n\n'
                           f'```.address coin_address\n'
                           'That will check if the address is valid. '
                           f'If you would like to get your address, please use {prefix}deposit {COIN_NAME} instead.```')
        return

    # Check if a user request address coin of another user
    # .addr COIN @mention
    if len(args) == 2 and len(ctx.message.mentions) == 1:
        COIN_NAME = None
        member = None
        try:
            COIN_NAME = args[0].upper()
            member = ctx.message.mentions[0]
            if COIN_NAME not in (ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_COIN_NANO+ENABLE_XMR+ENABLE_COIN_ERC):
                COIN_NAME = None
        except Exception as e:
            pass

        if COIN_NAME not in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO+ENABLE_COIN_ERC:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
            return

        if not is_coin_depositable(COIN_NAME):
            msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} DEPOSITING is currently disable for {COIN_NAME}.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        if COIN_NAME and member and isinstance(ctx.channel, discord.DMChannel) == False and member.bot == False:
            # OK there is COIN_NAME and member
            if member.id == ctx.message.author.id:
                await ctx.message.add_reaction(EMOJI_ERROR)
                return
            msg = await ctx.send(f'**ADDRESS REQ {COIN_NAME} **: {member.mention}, {str(ctx.author)} would like to get your address.')
            await msg.add_reaction(EMOJI_CHECKMARK)
            await msg.add_reaction(EMOJI_ZIPPED_MOUTH)
            def check(reaction, user):
                return user == member and reaction.message.author == bot.user and reaction.message.id == msg.id and str(reaction.emoji) \
                in (EMOJI_CHECKMARK, EMOJI_ZIPPED_MOUTH)
            try:
                reaction, user = await bot.wait_for('reaction_add', timeout=120, check=check)
            except asyncio.TimeoutError:
                await ctx.send(f'{ctx.author.mention} address requested timeout (120s) from {str(member.mention)}.')
                try:
                    await msg.delete()
                except Exception as e:
                    pass
                return
                
            if str(reaction.emoji) == EMOJI_CHECKMARK:
                await ctx.message.add_reaction(EMOJI_OK_HAND)
                wallet = await store.sql_get_userwallet(str(member.id), COIN_NAME)
                if wallet is None:
                    if COIN_NAME in ENABLE_COIN_ERC:
                        w = await create_address_eth()
                        userregister = await store.sql_register_user(str(member.id), COIN_NAME, 'DISCORD', 0, w)
                    else:
                        userregister = await store.sql_register_user(str(member.id), COIN_NAME, 'DISCORD', 0)
                    wallet = await store.sql_get_userwallet(str(member.id), COIN_NAME)
                user_address = wallet['balance_wallet_address']
                msg = await ctx.send(f'{ctx.author.mention} Here is the deposit **{COIN_NAME}** of {member.mention}:```{user_address}```')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
            elif str(reaction.emoji) == EMOJI_ZIPPED_MOUTH:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{ctx.author.mention} your address request is rejected.')
                return

    CoinAddress = args[0]
    COIN_NAME = None

    if not re.match(r'^[A-Za-z0-9_]+$', CoinAddress):
        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                             f'`{CoinAddress}`')
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    # Check which coinname is it.
    COIN_NAME = get_cn_coin_from_address(CoinAddress)

    if COIN_NAME:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    else:
        if CoinAddress.startswith("0x"):
            if CoinAddress.upper().startswith("0X00000000000000000000000000000"):
                await ctx.message.add_reaction(EMOJI_ERROR)
                msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid token:\n'
                                     f'`{CoinAddress}`')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
            else:
                valid_address = await store.erc_validate_address(CoinAddress, "XMOON") # placeholder
                if valid_address and valid_address.upper() == CoinAddress.upper():
                    await ctx.message.add_reaction(EMOJI_CHECK)
                    msg = await ctx.send(f'Token address: `{CoinAddress}`\n'
                                         'Checked: Valid.')
                    await msg.add_reaction(EMOJI_OK_BOX)
                    return
                else:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid token address:\n'
                                         f'`{CoinAddress}`')
                    await msg.add_reaction(EMOJI_OK_BOX)
                    return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                                f'`{CoinAddress}`')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

    addressLength = get_addrlen(COIN_NAME)
    if coin_family in [ "BCN", "TRTL", "XMR"]:
        IntaddressLength = get_intaddrlen(COIN_NAME)

    if len(args) == 1:
        if coin_family == "DOGE":
            valid_address = await doge_validaddress(str(CoinAddress), COIN_NAME)
            if 'isvalid' in valid_address:
                if str(valid_address['isvalid']) == "True":
                    await ctx.message.add_reaction(EMOJI_CHECK)
                    msg = await ctx.send(f'Address: `{CoinAddress}`\n'
                                         f'Checked: Valid {COIN_NAME}.')
                    await msg.add_reaction(EMOJI_OK_BOX)
                    return
                else:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    msg = await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                                         'Checked: Invalid.')
                    await msg.add_reaction(EMOJI_OK_BOX)
                    return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                msg = await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                                    'Checked: Invalid.')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
        if coin_family == "NANO":
            valid_address = await nano_validate_address(COIN_NAME, str(CoinAddress))
            if valid_address == True:
                await ctx.message.add_reaction(EMOJI_CHECK)
                msg = await ctx.send(f'Address: `{CoinAddress}`\n'
                                     f'Checked: Valid {COIN_NAME}.')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                msg = await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                                     'Checked: Invalid.')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
        elif COIN_NAME == "LTC":
            valid_address = await doge_validaddress(str(CoinAddress), COIN_NAME)
            if 'isvalid' in valid_address:
                if str(valid_address['isvalid']) == "True":
                    await ctx.message.add_reaction(EMOJI_CHECK)
                    msg = await ctx.send(f'Address: `{CoinAddress}`\n'
                                         f'Checked: Valid {COIN_NAME}.')
                    await msg.add_reaction(EMOJI_OK_BOX)
                    return
                else:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    msg = await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                                         'Checked: Invalid.')
                    await msg.add_reaction(EMOJI_OK_BOX)
                    return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                                'Checked: Invalid.')
                return
        elif COIN_NAME == "PGO":
            valid_address = await doge_validaddress(str(CoinAddress), COIN_NAME)
            if 'isvalid' in valid_address:
                if str(valid_address['isvalid']) == "True":
                    await ctx.message.add_reaction(EMOJI_CHECK)
                    msg = await ctx.send(f'Address: `{CoinAddress}`\n'
                                         f'Checked: Valid {COIN_NAME}.')
                    await msg.add_reaction(EMOJI_OK_BOX)
                    return
                else:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    msg = await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                                         'Checked: Invalid.')
                    await msg.add_reaction(EMOJI_OK_BOX)
                    return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                msg = await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                                    'Checked: Invalid.')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
        elif COIN_NAME in ENABLE_XMR:
            if COIN_NAME == "MSR":
                addr = None
                if len(CoinAddress) == 95:
                    try:
                        addr = address_msr(CoinAddress)
                    except Exception as e:
                        # await logchanbot(traceback.format_exc())
                        pass
                elif len(CoinAddress) == 106:
                    addr = None
                    try:
                        addr = address_msr(CoinAddress)
                    except Exception as e:
                        # await logchanbot(traceback.format_exc())
                        pass
                if addr == CoinAddress:
                    address_result = 'Valid: `{}`\n'.format(addr)                    
                    if type(addr).__name__ == "Address":
                        address_result += 'Main Address: `{}`\n'.format('True')
                    else:
                        address_result += 'Main Address: `{}`\n'.format('False')
                    if type(addr).__name__ == "IntegratedAddress":
                        address_result += 'Integrated: `{}`\n'.format('True')
                    else:
                        address_result += 'Integrated: `{}`\n'.format('False')
                    if type(addr).__name__ == "SubAddress":
                        address_result += 'Subaddress: `{}`\n'.format('True')
                    else:
                        address_result += 'Subaddress: `{}`\n'.format('False')
                    await ctx.message.add_reaction(EMOJI_CHECK)
                    await ctx.send(f'{EMOJI_CHECK} Address: `{CoinAddress}`\n{address_result}')
                    return
                else:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                                    'Checked: Invalid.')
                    return
            elif COIN_NAME == "UPX":	
                addr = None	
                if len(CoinAddress) == 98 or len(CoinAddress) == 97:	
                    try:	
                        addr = address_upx(CoinAddress)	
                    except Exception as e:	
                        traceback.print_exc(file=sys.stdout)	
                        pass	
                elif len(CoinAddress) == 109:	
                    addr = None	
                    try:	
                        addr = address_upx(CoinAddress)	
                    except Exception as e:	
                        traceback.print_exc(file=sys.stdout)	
                        pass	
                if addr == CoinAddress:	
                    address_result = 'Valid: `{}`\n'.format(addr)                    	
                    if type(addr).__name__ == "Address":	
                        address_result += 'Main Address: `{}`\n'.format('True')	
                    else:	
                        address_result += 'Main Address: `{}`\n'.format('False')	
                    if type(addr).__name__ == "IntegratedAddress":	
                        address_result += 'Integrated: `{}`\n'.format('True')	
                    else:	
                        address_result += 'Integrated: `{}`\n'.format('False')	
                    if type(addr).__name__ == "SubAddress":	
                        address_result += 'Subaddress: `{}`\n'.format('True')	
                    else:	
                        address_result += 'Subaddress: `{}`\n'.format('False')	
                    await ctx.message.add_reaction(EMOJI_CHECK)	
                    await ctx.send(f'{EMOJI_CHECK} Address: `{CoinAddress}`\n{address_result}')	
                    return	
                else:	
                    await ctx.message.add_reaction(EMOJI_ERROR)	
                    await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'	
                                    'Checked: Invalid.')	
                    return
            else:
                valid_address = await validate_address_xmr(str(CoinAddress), COIN_NAME)
                if valid_address is None:
                    await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                                    'Checked: Invalid.')
                    return
                elif valid_address['valid'] == True:
                    address_result = 'Valid: `{}`\n'.format(str(valid_address['valid'])) + \
                                   'Integrated: `{}`\n'.format(str(valid_address['integrated'])) + \
                                   'Net Type: `{}`\n'.format(str(valid_address['nettype'])) + \
                                   'Subaddress: `{}`\n'.format(str(valid_address['subaddress']))
                    await ctx.message.add_reaction(EMOJI_CHECK)
                    await ctx.send(f'{EMOJI_CHECK} Address: `{CoinAddress}`\n{address_result}')
                    return

        if len(CoinAddress) == int(addressLength):
            valid_address = addressvalidation.validate_address_cn(CoinAddress, COIN_NAME)
            print(valid_address)
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
                await ctx.message.add_reaction(EMOJI_OK_HAND)
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
            await ctx.message.add_reaction(EMOJI_OK_HAND)
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


@bot.group(pass_context=True, name='voucher', aliases=['redeem'], help=bot_help_voucher)
async def voucher(ctx):
    prefix = await get_guild_prefix(ctx)
    if ctx.invoked_subcommand is None:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Required some command. Please use {prefix}help voucher')
        return


@voucher.command(aliases=['gen'], help=bot_help_voucher_make)
async def make(ctx, amount: str, coin: str, *, comment):
    global IS_RESTARTING, TRTL_DISCORD, TX_IN_PROCESS
    # check if bot is going to restart
    if IS_RESTARTING:
        await ctx.message.add_reaction(EMOJI_REFRESH)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
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

    # Check if tx in progress
    if ctx.message.author.id in TX_IN_PROCESS:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    amount = amount.replace(",", "")
    
    voucher_numb = 1
    if 'x' in amount.lower():
        # This is a batch
        voucher_numb = amount.lower().split("x")[0]
        voucher_each = amount.lower().split("x")[1]
        try:
            voucher_numb = int(voucher_numb)
            voucher_each = float(voucher_each)
            if voucher_numb > config.voucher.max_batch:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Too many. Maximum allowed: **{config.voucher.max_batch}**')
                return
        except ValueError:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid number or amount to create vouchers.')
            return
    elif '*' in amount.lower():
        # This is a batch
        voucher_numb = amount.lower().split("*")[0]
        voucher_each = amount.lower().split("*")[1]
        try:
            voucher_numb = int(voucher_numb)
            voucher_each = Decimal(voucher_each)
            if voucher_numb > config.voucher.max_batch:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Too many. Maximum allowed: **{config.voucher.max_batch}**')
                return
        except ValueError:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid number or amount to create vouchers.')
            return
    else:
        try:
            amount = Decimal(amount)
            voucher_each = amount
        except ValueError:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount to create a voucher.')
            return

    total_amount = voucher_numb * voucher_each

    COIN_NAME = coin.upper()
    if is_maintenance_coin(COIN_NAME):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return
    if COIN_NAME not in ENABLE_COIN_VOUCHER:
        await ctx.message.add_reaction(EMOJI_INFORMATION)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} we do not have voucher feature for **{COIN_NAME}** yet. Try with **{config.Enable_Coin_Voucher}**.')
        return

    if isinstance(ctx.channel, discord.DMChannel) == False:
        if COIN_NAME != "TRTL" and ctx.guild.id == TRTL_DISCORD:
            # TRTL discord not allowed
            await ctx.message.add_reaction(EMOJI_ERROR)
            return

    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    real_amount = int(voucher_each * get_decimal(COIN_NAME)) if coin_family in ["XMR", "TRTL", "BCN", "NANO"] else float(voucher_each)
    total_real_amount = int(total_amount * get_decimal(COIN_NAME)) if coin_family in ["XMR", "TRTL", "BCN", "NANO"] else float(total_amount)
    secret_string = str(uuid.uuid4())
    unique_filename = str(uuid.uuid4())

    user = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    if user is None:
        user = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)

    userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), COIN_NAME)
    xfer_in = 0
    if COIN_NAME not in ENABLE_COIN_ERC:
        xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.message.author.id), COIN_NAME)
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
            msg_negative = 'Negative balance detected:\nUser: '+str(ctx.message.author.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
            await logchanbot(msg_negative)
    except Exception as e:
        await logchanbot(traceback.format_exc())
            
    if real_amount < get_min_tx_amount(COIN_NAME) or real_amount > get_max_tx_amount(COIN_NAME):
        min_amount = num_format_coin(get_min_tx_amount(COIN_NAME), COIN_NAME) + COIN_NAME
        max_amount = num_format_coin(get_max_tx_amount(COIN_NAME), COIN_NAME) + COIN_NAME
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Voucher amount must between {min_amount} and {max_amount}.')
        return

    if actual_balance < real_amount + get_voucher_fee(COIN_NAME):
        having_amount = num_format_coin(actual_balance, COIN_NAME)
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to create voucher.\n'
                       f'A voucher needed amount + fee: {num_format_coin(real_amount + get_voucher_fee(COIN_NAME), COIN_NAME)}{COIN_NAME}\n'
                       f'Having: {having_amount}{COIN_NAME}.')
        return

    comment = comment.strip().replace('\n', ' ').replace('\r', '')
    if len(comment) > config.voucher.max_comment:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please limit your comment to max. **{config.voucher.max_comment}** chars.')
        return
    if not is_ascii(comment):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Unsupported char(s) detected in comment.')
        return
        
    print('VOUCHER: ' + COIN_NAME) 
    # If it is a batch oir not
    if voucher_numb > 1:
        # Check if sufficient balance
        if actual_balance < (real_amount + get_voucher_fee(COIN_NAME)) * voucher_numb:
            having_amount = num_format_coin(actual_balance, COIN_NAME)
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to create **{voucher_numb}** vouchers.\n'
                           f'**{voucher_numb}** vouchers needed amount + fee: {num_format_coin((real_amount + get_voucher_fee(COIN_NAME)*voucher_numb), COIN_NAME)}{COIN_NAME}\n'
                           f'Having: {having_amount}{COIN_NAME}.')
            return

        # Check if bot can DM him first. If failed reject
        try:
            await ctx.message.author.send(f'{ctx.author.mention} I am creating a voucher for you and will direct message to you the pack of vouchers.')
        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            # If failed to DM, message we stop
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Voucher batch will not work if you disable DM or I failed to DM you.')
            return
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        if isinstance(ctx.channel, discord.DMChannel) == False:
            try:
                await ctx.send(f'{EMOJI_INFORMATION} {ctx.author.mention} You should do this in Direct Message.')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                pass   
        for i in range(voucher_numb):
            secret_string = str(uuid.uuid4())
            unique_filename = str(uuid.uuid4())
            # loop voucher_numb times
            # do some QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=2,
            )
            qrstring = config.voucher.voucher_url + "/claim/" + secret_string
            qr.add_data(qrstring)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_img = qr_img.resize((280, 280))
            qr_img = qr_img.convert("RGBA")
            # qr_img.save(config.voucher.path_voucher_create + unique_filename + "_1.png")

            #Logo
            try:
                logo = Image.open(config.voucher.coin_logo_path + COIN_NAME.lower() + ".png")
                box = (115,115,165,165)
                qr_img.crop(box)
                region = logo
                region = region.resize((box[2] - box[0], box[3] - box[1]))
                qr_img.paste(region,box)
                # qr_img.save(config.voucher.path_voucher_create + unique_filename + "_2.png")
            except Exception as e: 
                await logchanbot(traceback.format_exc())
            # Image Frame on which we want to paste 
            img_frame = Image.open(config.voucher.path_voucher_defaultimg)  
            img_frame.paste(qr_img, (150, 150)) 

            # amount font
            try:
                msg = str(num_format_coin(real_amount, COIN_NAME)) + COIN_NAME
                W, H = (1123,644)
                draw =  ImageDraw.Draw(img_frame)
                myFont = ImageFont.truetype(config.font.digital7, 44)
                # w, h = draw.textsize(msg, font=myFont)
                w, h = myFont.getsize(msg)
                # draw.text(((W-w)/2,(H-h)/2), msg, fill="black",font=myFont)
                draw.text((280-w/2,275+125+h), msg, fill="black",font=myFont)

                # Instruction to claim
                myFont = ImageFont.truetype(config.font.digital7, 36)
                msg_claim = "SCAN TO CLAIM IT!"
                w, h = myFont.getsize(msg_claim)
                draw.text((280-w/2,275+125+h+60), msg_claim, fill="black",font=myFont)

                # comment part
                comment_txt = "COMMENT: " + comment.upper()
                myFont = ImageFont.truetype(config.font.digital7, 24)
                w, h = myFont.getsize(comment_txt)
                draw.text((561-w/2,275+125+h+120), comment_txt, fill="black",font=myFont)
            except Exception as e: 
                await logchanbot(traceback.format_exc())
            # Saved in the same relative location 
            img_frame.save(config.voucher.path_voucher_create + unique_filename + ".png")
            if ctx.message.author.id not in TX_IN_PROCESS:
                TX_IN_PROCESS.append(ctx.message.author.id)
                try:
                    voucher_make = await store.sql_send_to_voucher(str(ctx.message.author.id), '{}#{}'.format(ctx.message.author.name, ctx.message.author.discriminator), 
                                                                   ctx.message.content, real_amount, get_voucher_fee(COIN_NAME), comment, 
                                                                   secret_string, unique_filename + ".png", COIN_NAME, 'DISCORD')
                except Exception as e: 
                    await logchanbot(traceback.format_exc())
                await asyncio.sleep(config.interval.tx_lap_each)
                TX_IN_PROCESS.remove(ctx.message.author.id)
            else:
                # reject and tell to wait
                msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You have another tx in process. Please wait it to finish. ')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
                
            if voucher_make:             
                try:
                    msg = await ctx.message.author.send(f'New Voucher Link ({i+1} of {voucher_numb}): {qrstring}\n'
                                        '```'
                                        f'Amount: {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}\n'
                                        f'Voucher Fee (Incl. network fee): {num_format_coin(get_voucher_fee(COIN_NAME), COIN_NAME)} {COIN_NAME}\n'
                                        f'Voucher comment: {comment}```')
                    await msg.add_reaction(EMOJI_OK_BOX)
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    await logchanbot(traceback.format_exc())
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{ctx.author.mention} Sorry, I failed to DM you.')
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
        return
    elif voucher_numb == 1:
        # do some QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
        )
        qrstring = config.voucher.voucher_url + "/claim/" + secret_string
        qr.add_data(qrstring)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_img = qr_img.resize((280, 280))
        qr_img = qr_img.convert("RGBA")
        # qr_img.save(config.voucher.path_voucher_create + unique_filename + "_1.png")

        #Logo
        try:
            logo = Image.open(config.voucher.coin_logo_path + COIN_NAME.lower() + ".png")
            box = (115,115,165,165)
            qr_img.crop(box)
            region = logo
            region = region.resize((box[2] - box[0], box[3] - box[1]))
            qr_img.paste(region,box)
            # qr_img.save(config.voucher.path_voucher_create + unique_filename + "_2.png")
        except Exception as e: 
            await logchanbot(traceback.format_exc())
        # Image Frame on which we want to paste 
        img_frame = Image.open(config.voucher.path_voucher_defaultimg)  
        img_frame.paste(qr_img, (150, 150)) 

        # amount font
        try:
            msg = str(num_format_coin(real_amount, COIN_NAME)) + COIN_NAME
            W, H = (1123,644)
            draw =  ImageDraw.Draw(img_frame)
            myFont = ImageFont.truetype(config.font.digital7, 44)
            # w, h = draw.textsize(msg, font=myFont)
            w, h = myFont.getsize(msg)
            # draw.text(((W-w)/2,(H-h)/2), msg, fill="black",font=myFont)
            draw.text((280-w/2,275+125+h), msg, fill="black",font=myFont)

            # Instruction to claim
            myFont = ImageFont.truetype(config.font.digital7, 36)
            msg_claim = "SCAN TO CLAIM IT!"
            w, h = myFont.getsize(msg_claim)
            draw.text((280-w/2,275+125+h+60), msg_claim, fill="black",font=myFont)

            # comment part
            comment_txt = "COMMENT: " + comment.upper()
            myFont = ImageFont.truetype(config.font.digital7, 24)
            w, h = myFont.getsize(comment_txt)
            draw.text((561-w/2,275+125+h+120), comment_txt, fill="black",font=myFont)
        except Exception as e: 
            await logchanbot(traceback.format_exc())
        # Saved in the same relative location 
        img_frame.save(config.voucher.path_voucher_create + unique_filename + ".png")
        if ctx.message.author.id not in TX_IN_PROCESS:
            TX_IN_PROCESS.append(ctx.message.author.id)
            try:
                voucher_make = await store.sql_send_to_voucher(str(ctx.message.author.id), '{}#{}'.format(ctx.message.author.name, ctx.message.author.discriminator), 
                                                               ctx.message.content, real_amount, get_voucher_fee(COIN_NAME), comment, 
                                                               secret_string, unique_filename + ".png", COIN_NAME, 'DISCORD')
            except Exception as e: 
                await logchanbot(traceback.format_exc())
            await asyncio.sleep(config.interval.tx_lap_each)
            TX_IN_PROCESS.remove(ctx.message.author.id)
        else:
            # reject and tell to wait
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You have another tx in process. Please wait it to finish. ')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        if voucher_make:
            await ctx.message.add_reaction(EMOJI_OK_HAND)
            if isinstance(ctx.channel, discord.DMChannel) == False:
                try:
                    await ctx.send(f'{EMOJI_INFORMATION} {ctx.author.mention} You should do this in Direct Message.')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    pass                
            try:
                msg = await ctx.send(f'New Voucher Link: {qrstring}\n'
                                    '```'
                                    f'Amount: {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}\n'
                                    f'Voucher Fee (Incl. network fee): {num_format_coin(get_voucher_fee(COIN_NAME), COIN_NAME)} {COIN_NAME}\n'
                                    f'Voucher comment: {comment}```')
                await msg.add_reaction(EMOJI_OK_BOX)
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await logchanbot(traceback.format_exc())
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{ctx.author.mention} Sorry, I failed to DM you.')
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
        return


@voucher.command(help=bot_help_voucher_fee)
async def fee(ctx):
    fee_str = "VOUCHER FEE FOR COINS:\n"
    for each_coin in ENABLE_COIN_VOUCHER:
        fee = num_format_coin(get_voucher_fee(each_coin), each_coin) + each_coin
        fee_str += "    + {}: {}\n".format(each_coin, fee)
    fee_str += "* Fee also includes network fee."
    await ctx.message.add_reaction(EMOJI_OK_HAND)
    msg = await ctx.send(f'{ctx.author.mention}'
                         f'```{fee_str}```\n')
    await msg.add_reaction(EMOJI_OK_BOX)
    return


@voucher.command(help=bot_help_voucher_view)
async def view(ctx):
    get_vouchers = await store.sql_voucher_get_user(str(ctx.message.author.id), 'DISCORD', 15, 'YESNO')
    if get_vouchers and len(get_vouchers) > 0:
        table_data = [
            ['Ref Link', 'Amount', 'Claimed?', 'Created']
        ]
        for each in get_vouchers:
            table_data.append([each['secret_string'], num_format_coin(each['amount'], each['coin_name'])+each['coin_name'], 
                               'YES' if each['already_claimed'] == 'YES' else 'NO', 
                               datetime.fromtimestamp(each['date_create']).strftime('%Y-%m-%d')])
        table = AsciiTable(table_data)
        table.padding_left = 1
        table.padding_right = 1
        if isinstance(ctx.channel, discord.DMChannel) == False:
            try:
                await ctx.send(f'{EMOJI_INFORMATION} {ctx.author.mention} You should do this in Direct Message.')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                pass
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        msg = await ctx.send(f'**[ YOUR VOUCHER LIST ]**\n'
                             f'```{table.table}```\n')
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} You did not create any voucher yet.')
    return


@voucher.command(help=bot_help_voucher_unclaim)
async def unclaim(ctx):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return
    get_vouchers = await store.sql_voucher_get_user(str(ctx.message.author.id), 'DISCORD', 50, 'NO')
    if get_vouchers and len(get_vouchers) >= 25:
        # list them in text
        unclaim = ', '.join([each['secret_string'] for each in get_vouchers])
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        await ctx.send(f'{ctx.author.mention} You have many unclaimed vouchers: {unclaim}')
        return
    elif get_vouchers and len(get_vouchers) > 0:
        table_data = [
            ['Ref Link', 'Amount', 'Claimed?', 'Created']
        ]
        for each in get_vouchers:
            table_data.append([each['secret_string'], num_format_coin(each['amount'], each['coin_name'])+each['coin_name'], 
                               'YES' if each['already_claimed'] == 'YES' else 'NO', 
                               datetime.fromtimestamp(each['date_create']).strftime('%Y-%m-%d')])
        table = AsciiTable(table_data)
        table.padding_left = 1
        table.padding_right = 1
        if isinstance(ctx.channel, discord.DMChannel) == False:
            try:
                await ctx.send(f'{EMOJI_INFORMATION} {ctx.author.mention} You should do this in Direct Message.')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                pass
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        msg = await ctx.send(f'**[ YOUR VOUCHER LIST ]**\n'
                             f'```{table.table}```\n')
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} You did not create any voucher yet.')
    return


@voucher.command(help=bot_help_voucher_claim)
async def claim(ctx):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return
    get_vouchers = await store.sql_voucher_get_user(str(ctx.message.author.id), 'DISCORD', 50, 'YES')
    if get_vouchers and len(get_vouchers) >= 25:
        # list them in text
        unclaim = ', '.join([each['secret_string'] for each in get_vouchers])
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        await ctx.send(f'{ctx.author.mention} You have many claimed vouchers: {unclaim}')
        return
    elif get_vouchers and len(get_vouchers) > 0:
        table_data = [
            ['Ref Link', 'Amount', 'Claimed?', 'Created']
        ]
        for each in get_vouchers:
            table_data.append([each['secret_string'], num_format_coin(each['amount'], each['coin_name'])+each['coin_name'], 
                               'YES' if each['already_claimed'] == 'YES' else 'NO', 
                               datetime.fromtimestamp(each['date_create']).strftime('%Y-%m-%d')])
        table = AsciiTable(table_data)
        table.padding_left = 1
        table.padding_right = 1
        if isinstance(ctx.channel, discord.DMChannel) == False:
            try:
                await ctx.send(f'{EMOJI_INFORMATION} {ctx.author.mention} You should do this in Direct Message.')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                pass
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        msg = await ctx.send(f'**[ YOUR VOUCHER LIST ]**\n'
                             f'```{table.table}```\n')
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} You did not create any voucher yet.')
    return


@voucher.command(help=bot_help_voucher_getunclaim)
async def getunclaim(ctx):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return
    get_vouchers = await store.sql_voucher_get_user(str(ctx.message.author.id), 'DISCORD', 10000, 'NO')
    if get_vouchers and len(get_vouchers) > 0:
        try:
            filename = config.voucher.claim_csv_tmp + str(uuid.uuid4()) + '_unclaimed.csv'
            write_csv_dumpinfo = open(filename, "w")
            for item in get_vouchers:
                write_csv_dumpinfo.write(config.voucher.voucher_url + '/claim/' + item['secret_string'] + '\n')
            write_csv_dumpinfo.close()
            if os.path.exists(filename):
                try:
                    await ctx.message.author.send(f"YOUR UNCLAIMED VOUCHER LIST IN CSV FILE:",
                                                  file=discord.File(filename))
                except Exception as e:
                    await ctx.message.add_reaction(EMOJI_ERROR) 
                    await ctx.send(f'{ctx.author.mention} I failed to send CSV file to you.')
                    await logchanbot(traceback.format_exc())
                os.remove(filename)
        except Exception as e:
            await logchanbot(traceback.format_exc())
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} You did not create any voucher yet.')
    return


@voucher.command(help=bot_help_voucher_getclaim)
async def getclaim(ctx):
    if isinstance(ctx.channel, discord.DMChannel) == False:
        await ctx.message.add_reaction(EMOJI_ERROR) 
        await ctx.send(f'{ctx.author.mention} This command can not be in public.')
        return
    get_vouchers = await store.sql_voucher_get_user(str(ctx.message.author.id), 'DISCORD', 10000, 'YES')
    if get_vouchers and len(get_vouchers) > 0:
        try:
            filename = config.voucher.claim_csv_tmp + str(uuid.uuid4()) + '_claimed.csv'
            write_csv_dumpinfo = open(filename, "w")
            for item in get_vouchers:
                write_csv_dumpinfo.write(config.voucher.voucher_url + '/claim/' + item['secret_string'] + '\n')
            write_csv_dumpinfo.close()
            if os.path.exists(filename):
                try:
                    await ctx.message.author.send(f"YOUR CLAIMED VOUCHER LIST IN CSV FILE:",
                                                  file=discord.File(filename))
                except Exception as e:
                    await ctx.message.add_reaction(EMOJI_ERROR) 
                    await ctx.send(f'{ctx.author.mention} I failed to send CSV file to you.')
                    await logchanbot(traceback.format_exc())
                os.remove(filename)
        except Exception as e:
            await logchanbot(traceback.format_exc())
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} You did not create any voucher yet.')
    return


@bot.command(pass_context=True, name='paymentid', aliases=['payid'], help=bot_help_paymentid)
async def paymentid(ctx, coin: str = None):
    paymentid = None
    if coin and (coin.upper() in ENABLE_XMR):
        paymentid = addressvalidation.paymentid(8)
    else:
        paymentid = addressvalidation.paymentid()
    await ctx.message.add_reaction(EMOJI_OK_HAND)
    await ctx.send('**[ RANDOM PAYMENT ID ]**\n'
                   f'`{paymentid}`\n')
    return


@bot.command(pass_context=True, aliases=['stat'], help=bot_help_stats)
async def stats(ctx, coin: str = None):
    global TRTL_DISCORD, NOTICE_COIN
    COIN_NAME = None
    serverinfo = None
    if coin is None and isinstance(ctx.message.channel, discord.DMChannel) == False:
        serverinfo = await get_info_pref_coin(ctx)
        COIN_NAME = serverinfo['default_coin'].upper()
    elif coin is None and isinstance(ctx.message.channel, discord.DMChannel):
        COIN_NAME = "BOT"
    elif coin and isinstance(ctx.message.channel, discord.DMChannel) == False:
        serverinfo = await get_info_pref_coin(ctx)
        COIN_NAME = coin.upper()
    elif coin:
        COIN_NAME = coin.upper()

    if COIN_NAME not in (ENABLE_COIN+ENABLE_XMR+ENABLE_COIN_ERC) and COIN_NAME != "BOT":
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Unsupported or Unknown Ticker: **{COIN_NAME}**')
        return

    # TRTL discord
    if isinstance(ctx.message.channel, discord.DMChannel) == False and ctx.guild.id == TRTL_DISCORD and COIN_NAME != "TRTL":
        return

    if is_maintenance_coin(COIN_NAME) and (ctx.message.author.id not in MAINTENANCE_OWNER):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} in maintenance.')
        return
    elif is_maintenance_coin(COIN_NAME) and (ctx.message.author.id in MAINTENANCE_OWNER):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)

    if COIN_NAME == "BOT":
        await bot.wait_until_ready()
        get_all_m = bot.get_all_members()
        total_claimed = '{:,.0f}'.format(await store.sql_faucet_count_all())
        total_tx = await store.sql_count_tx_all()
        embed = discord.Embed(title="[ TIPBOT ]", description="TipBot Stats", timestamp=datetime.utcnow(), color=0xDEADBF)
        embed.set_author(name=bot.user.name, icon_url=bot.user.avatar_url)
        embed.add_field(name="Bot ID", value=str(bot.user.id), inline=True)
        embed.add_field(name="Guilds", value='{:,.0f}'.format(len(bot.guilds)), inline=True)
        embed.add_field(name="Shards", value='{:,.0f}'.format(bot.shard_count), inline=True)
        embed.add_field(name="Total Online", value='{:,.0f}'.format(sum(1 for m in get_all_m if m.status == discord.Status.online)), inline=True)
        embed.add_field(name="Users", value='{:,.0f}'.format(sum([x.member_count for x in bot.guilds])), inline=True)
        embed.add_field(name="Channels", value='{:,.0f}'.format(sum(1 for g in bot.guilds for _ in g.channels)), inline=True)
        embed.add_field(name="Total faucet claims", value=total_claimed, inline=True)
        embed.add_field(name="Total tip operations", value='{:,.0f} off-chain, {:,.0f} on-chain'.format(total_tx['off_chain'], total_tx['on_chain']), inline=False)
        try:
            your_tip_count_10mn = await store.sql_get_countLastTip(str(ctx.message.author.id), 10*60)
            your_tip_count_24h = await store.sql_get_countLastTip(str(ctx.message.author.id), 24*3600)
            your_tip_count_7d = await store.sql_get_countLastTip(str(ctx.message.author.id), 7*24*3600)
            your_tip_count_30d = await store.sql_get_countLastTip(str(ctx.message.author.id), 30*24*3600)
            embed.add_field(name="You have tipped", value='Last 10mn: {:,.0f}, 24h: {:,.0f}, 7d: {:,.0f}, 30d: {:,.0f}'.format(your_tip_count_10mn, your_tip_count_24h, your_tip_count_7d, your_tip_count_30d), inline=False)
        except Exception as e:
            await logchanbot(traceback.format_exc())
        embed.add_field(name="OTHER LINKS", value="{} / {} / {}".format("[Invite TipBot](http://invite.discord.bot.tips)", "[Support Server](https://discord.com/invite/GpHzURM)", "[TipBot Github](https://github.com/wrkzcoin/TipBot)"), inline=False)
        try:
            msg = await ctx.send(embed=embed)
            await msg.add_reaction(EMOJI_OK_BOX)
        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            await logchanbot(traceback.format_exc())
            await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
        return

    gettopblock = None
    timeout = 60
    try:
        if COIN_NAME in ENABLE_COIN_ERC:
            gettopblock = await store.erc_get_block_number(COIN_NAME, timeout)
        else:
            gettopblock = await daemonrpc_client.gettopblock(COIN_NAME, time_out=timeout)
    except asyncio.TimeoutError:
        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} connection to daemon timeout after {str(timeout)} seconds. I am checking info from wallet now.')
        await msg.add_reaction(EMOJI_OK_BOX)
    except Exception as e:
        await logchanbot(traceback.format_exc())

    walletStatus = None
    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family in ["TRTL", "BCN"]:
        try:
            walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
        except Exception as e:
            await logchanbot(traceback.format_exc())
    elif coin_family == "XMR":
        try:
            walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
        except Exception as e:
            await logchanbot(traceback.format_exc())

    prefix = await get_guild_prefix(ctx)
    if gettopblock and COIN_NAME not in ENABLE_COIN_ERC:
        COIN_DIFF = get_diff_target(COIN_NAME)
        if COIN_NAME != "TRTL":
            blockfound = datetime.utcfromtimestamp(int(gettopblock['block_header']['timestamp'])).strftime("%Y-%m-%d %H:%M:%S")
            ago = str(timeago.format(blockfound, datetime.utcnow()))
            difficulty = "{:,}".format(gettopblock['block_header']['difficulty'])
            hashrate = str(hhashes(int(gettopblock['block_header']['difficulty']) / int(COIN_DIFF)))
            height = "{:,}".format(gettopblock['block_header']['height'])
            reward = "{:,}".format(int(gettopblock['block_header']['reward'])/int(get_decimal(COIN_NAME)))
        else:
            # TRTL use daemon API
            blockfound = datetime.utcfromtimestamp(int(gettopblock['timestamp'])).strftime("%Y-%m-%d %H:%M:%S")
            ago = str(timeago.format(blockfound, datetime.utcnow()))
            difficulty = "{:,}".format(gettopblock['difficulty'])
            hashrate = str(hhashes(int(gettopblock['difficulty']) / int(COIN_DIFF)))
            height = "{:,}".format(gettopblock['height'])
            reward = "{:,}".format(int(gettopblock['reward'])/int(get_decimal(COIN_NAME)))
        if coin_family == "XMR":
            desc = f"Tip min/max: {num_format_coin(get_min_mv_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_mv_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}\n"
            desc += f"Tx min/max: {num_format_coin(get_min_tx_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_tx_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}\n"
            embed = discord.Embed(title=f"[ {COIN_NAME} ]", 
                                  description=desc, 
                                  timestamp=datetime.utcnow(), color=0xDEADBF)
            embed.set_author(name=bot.user.name, icon_url=bot.user.avatar_url)
            embed.add_field(name="NET HEIGHT", value=str(height), inline=True)
            embed.add_field(name="FOUND", value=ago, inline=True)
            embed.add_field(name="DIFFICULTY", value=difficulty, inline=True)
            embed.add_field(name="BLOCK REWARD", value=f'{reward}{COIN_NAME}', inline=True)
            if COIN_NAME not in ["XWP"]:
                embed.add_field(name="NETWORK HASH", value=hashrate, inline=True)
            if walletStatus:
                if COIN_NAME != "TRTL":
                    t_percent = '{:,.2f}'.format(truncate((walletStatus['height'] - 1)/gettopblock['block_header']['height']*100,2))
                else:
                    t_percent = '{:,.2f}'.format(truncate((walletStatus['height'] - 1)/gettopblock['height']*100,2))
                embed.add_field(name="WALLET SYNC %", value=t_percent + '% (' + '{:,.0f}'.format(walletStatus['height'] - 1) + ')', inline=True)
            if NOTICE_COIN[COIN_NAME]:
                notice_txt = NOTICE_COIN[COIN_NAME]
            else:
                notice_txt = NOTICE_COIN['default']
            embed.add_field(name='Related commands', value=f'`{prefix}coininfo {COIN_NAME}`, `{prefix}deposit {COIN_NAME}`, `{prefix}balance {COIN_NAME}`', inline=False)
            embed.set_footer(text=notice_txt)
            try:
                msg = await ctx.send(embed=embed)
                await msg.add_reaction(EMOJI_OK_BOX)
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                # if embedded denied
                msg = await ctx.send(f'**[ {COIN_NAME} ]**\n'
                               f'```[NETWORK HEIGHT] {height}\n'
                               f'[TIME]           {ago}\n'
                               f'[DIFFICULTY]     {difficulty}\n'
                               f'[BLOCK REWARD]   {reward}{COIN_NAME}\n'
                               f'[TIP Min/Max]    {num_format_coin(get_min_mv_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_mv_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}\n'
                               f'[TX Min/Max]     {num_format_coin(get_min_tx_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_tx_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}\n'
                               '```')
                await msg.add_reaction(EMOJI_OK_BOX)
            return
        else:
            walletBalance = None
            if walletStatus:
                localDaemonBlockCount = int(walletStatus['blockCount'])
                networkBlockCount = int(walletStatus['knownBlockCount'])
                t_percent = '{:,.2f}'.format(truncate((localDaemonBlockCount - 1)/networkBlockCount*100,2))
                t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
                t_networkBlockCount = '{:,}'.format(networkBlockCount)
                if COIN_NAME in WALLET_API_COIN:
                    walletBalance = await walletapi.walletapi_get_sum_balances(COIN_NAME)    
                else:
                    walletBalance = await get_sum_balances(COIN_NAME)
            desc = f"Tip min/max: {num_format_coin(get_min_mv_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_mv_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}\n"
            desc += f"Tx min/max: {num_format_coin(get_min_tx_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_tx_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}\n"
            embed = discord.Embed(title=f"[ {COIN_NAME} ]", 
                                  description=desc, 
                                  timestamp=datetime.utcnow(), color=0xDEADBF)
            embed.set_author(name=bot.user.name, icon_url=bot.user.avatar_url)
            embed.add_field(name="NET HEIGHT", value=str(height), inline=True)
            embed.add_field(name="FOUND", value=ago, inline=True)
            embed.add_field(name="DIFFICULTY", value=difficulty, inline=True)
            embed.add_field(name="BLOCK REWARD", value=f'{reward}{COIN_NAME}', inline=True)
            embed.add_field(name="NETWORK HASH", value=hashrate, inline=True)
            if walletStatus:
                embed.add_field(name="WALLET SYNC %", value=t_percent + '% (' + '{:,.0f}'.format(localDaemonBlockCount - 1) + ')', inline=True)
                embed.add_field(name="TOTAL UNLOCKED", value=num_format_coin(walletBalance['unlocked'], COIN_NAME) + COIN_NAME, inline=True)
                embed.add_field(name="TOTAL LOCKED", value=num_format_coin(walletBalance['locked'], COIN_NAME) + COIN_NAME, inline=True)
            if NOTICE_COIN[COIN_NAME]:
                notice_txt = NOTICE_COIN[COIN_NAME]
            else:
                notice_txt = NOTICE_COIN['default']
            embed.add_field(name='Related commands', value=f'`{prefix}coininfo {COIN_NAME}`, `{prefix}deposit {COIN_NAME}`, `{prefix}balance {COIN_NAME}`', inline=False)
            embed.set_footer(text=notice_txt)
            try:
                msg = await ctx.send(embed=embed)
                await msg.add_reaction(EMOJI_OK_BOX)
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                # if embedded denied
                balance_str = ''
                if walletBalance and ('unlocked' in walletBalance) and ('locked' in walletBalance) and walletStatus:
                    balance_actual = num_format_coin(walletBalance['unlocked'], COIN_NAME)
                    balance_locked = num_format_coin(walletBalance['locked'], COIN_NAME)
                    balance_str = f'[TOTAL UNLOCKED] {balance_actual}{COIN_NAME}\n'
                    balance_str = balance_str + f'[TOTAL LOCKED]   {balance_locked}{COIN_NAME}'
                    msg = await ctx.send(f'**[ {COIN_NAME} ]**\n'
                                   f'```[NETWORK HEIGHT] {height}\n'
                                   f'[TIME]           {ago}\n'
                                   f'[DIFFICULTY]     {difficulty}\n'
                                   f'[BLOCK REWARD]   {reward}{COIN_NAME}\n'
                                   f'[NETWORK HASH]   {hashrate}\n'
                                   f'[TIP Min/Max]    {num_format_coin(get_min_mv_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_mv_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}\n'
                                   f'[TX Min/Max]     {num_format_coin(get_min_tx_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_tx_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}\n'
                                   f'[WALLET SYNC %]: {t_percent}' + '% (' + '{:,.0f}'.format(localDaemonBlockCount - 1) + ')\n'
                                   f'{balance_str}'
                                   '```')
                else:
                    msg = await ctx.send(f'**[ {COIN_NAME} ]**\n'
                                   f'```[NETWORK HEIGHT] {height}\n'
                                   f'[TIME]           {ago}\n'
                                   f'[DIFFICULTY]     {difficulty}\n'
                                   f'[BLOCK REWARD]   {reward}{COIN_NAME}\n'
                                   f'[NETWORK HASH]   {hashrate}\n'
                                   f'[TIP Min/Max]    {num_format_coin(get_min_mv_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_mv_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}\n'
                                   f'[TX Min/Max]     {num_format_coin(get_min_tx_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_tx_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}\n'
                                   '```')
                await msg.add_reaction(EMOJI_OK_BOX)
            return
    elif COIN_NAME not in ENABLE_COIN_ERC:
        if gettopblock is None and coin_family in ["TRTL", "BCN"] and walletStatus:
            localDaemonBlockCount = int(walletStatus['blockCount'])
            networkBlockCount = int(walletStatus['knownBlockCount'])
            t_percent = '{:,.2f}'.format(truncate((localDaemonBlockCount - 1)/networkBlockCount*100,2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            if COIN_NAME in WALLET_API_COIN:
                walletBalance = await walletapi.walletapi_get_sum_balances(COIN_NAME)    
            else:
                walletBalance = await get_sum_balances(COIN_NAME)     
            desc = f"Tip min/max: {num_format_coin(get_min_mv_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_mv_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}\n"
            desc += f"Tx min/max: {num_format_coin(get_min_tx_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_tx_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}\n"
            embed = discord.Embed(title=f"[ {COIN_NAME} ]", 
                                  description=desc, 
                                  timestamp=datetime.utcnow(), color=0xDEADBF)
            embed.set_author(name=bot.user.name, icon_url=bot.user.avatar_url)
            embed.add_field(name="LOCAL DAEMON", value=str(t_localDaemonBlockCount), inline=True)
            embed.add_field(name="NETWORK", value=str(t_networkBlockCount), inline=True)
            embed.add_field(name="WALLET SYNC %", value=t_percent + '% (' + '{:,.0f}'.format(localDaemonBlockCount - 1) + ')', inline=True)
            embed.add_field(name="TOTAL UNLOCKED", value=num_format_coin(walletBalance['unlocked'], COIN_NAME) + COIN_NAME, inline=True)
            embed.add_field(name="TOTAL LOCKED", value=num_format_coin(walletBalance['locked'], COIN_NAME) + COIN_NAME, inline=True)
            embed.add_field(name='Related commands', value=f'`{prefix}coininfo {COIN_NAME}`, `{prefix}deposit {COIN_NAME}`, `{prefix}balance {COIN_NAME}`', inline=False)
            if NOTICE_COIN[COIN_NAME]:
                notice_txt = NOTICE_COIN[COIN_NAME] + " | Daemon RPC not available"
            else:
                notice_txt = NOTICE_COIN['default'] + " | Daemon RPC not available"
            embed.set_footer(text=notice_txt)
            try:
                msg = await ctx.send(embed=embed)
                await msg.add_reaction(EMOJI_OK_BOX)
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                # if embedded denied
                balance_str = ''
                if ('unlocked' in walletBalance) and ('locked' in walletBalance):
                    balance_actual = num_format_coin(walletBalance['unlocked'], COIN_NAME)
                    balance_locked = num_format_coin(walletBalance['locked'], COIN_NAME)
                    balance_str = f'[TOTAL UNLOCKED] {balance_actual}{COIN_NAME}\n'
                    balance_str = balance_str + f'[TOTAL LOCKED]   {balance_locked}{COIN_NAME}'
                    msg = await ctx.send(f'**[ {COIN_NAME} ]**\n'
                                   f'```[LOCAL DAEMON]   {t_localDaemonBlockCount}\n'
                                   f'[NETWORK]        {t_networkBlockCount}\n'
                                   f'[WALLET SYNC %]: {t_percent}' + '% (' + '{:,.0f}'.format(localDaemonBlockCount - 1) + ')\n'
                                   f'[TIP Min/Max]    {num_format_coin(get_min_mv_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_mv_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}\n'
                                   f'[TX Min/Max]     {num_format_coin(get_min_tx_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_tx_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}\n'
                                   f'{balance_str}'
                                   '```'
                                   )
                await msg.add_reaction(EMOJI_OK_BOX)
            return
        else:
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME}\'s status unavailable.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
    elif COIN_NAME in ENABLE_COIN_ERC:
        try:
            token_info = await store.get_token_info(COIN_NAME)
            desc = f"Tip min/max: {num_format_coin(token_info['real_min_tip'], COIN_NAME)}-{num_format_coin(token_info['real_max_tip'], COIN_NAME)}{COIN_NAME}\n"
            desc += f"Tx min/max: {num_format_coin(token_info['real_min_tx'], COIN_NAME)}-{num_format_coin(token_info['real_max_tx'], COIN_NAME)}{COIN_NAME}\n"
            embed = discord.Embed(title=f"[ {COIN_NAME} ]", 
                                  description=desc, 
                                  timestamp=datetime.utcnow(), color=0xDEADBF)
            embed.set_author(name=bot.user.name, icon_url=bot.user.avatar_url)
            topBlock = await store.erc_get_block_number(COIN_NAME)
            embed.add_field(name="NETWORK", value='{:,}'.format(topBlock), inline=True)
            try:
                get_main_balance = await store.http_wallet_getbalance(token_info['withdraw_address'], COIN_NAME)
                if get_main_balance:
                    embed.add_field(name="MAIN BALANCE", value=num_format_coin(get_main_balance / 10**token_info['token_decimal'], COIN_NAME) + COIN_NAME, inline=True)
            except Exception as e:
                await logchanbot(traceback.format_exc())
            try:
                embed.add_field(name="COININFO", value=token_info['coininfo_note'], inline=True)
                embed.add_field(name="EXPLORER", value=token_info['explorer_link'], inline=True)
                embed.add_field(name='Related commands', value=f'`{prefix}coininfo {COIN_NAME}`, `{prefix}deposit {COIN_NAME}`, `{prefix}balance {COIN_NAME}`', inline=False)
            except Exception as e:
                pass
            embed.set_footer(text=f"{token_info['deposit_note']}")
            try:
                msg = await ctx.send(embed=embed)
                await msg.add_reaction(EMOJI_OK_BOX)
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                pass
        except Exception as e:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await logchanbot(traceback.format_exc())
            print(traceback.format_exc())


@bot.group(pass_context=True, aliases=['fb'], help=bot_help_feedback)
async def feedback(ctx):
    prefix = await get_guild_prefix(ctx)
    if ctx.invoked_subcommand is None:
        if config.feedback_setting.enable != 1:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} Feedback is not enable right now. Check back later.')
            return

        # Check if user has submitted any and reach limit
        check_feedback_user = await store.sql_get_feedback_count_last(str(ctx.message.author.id), config.feedback_setting.intervial_last_10mn_s)
        if check_feedback_user and check_feedback_user >= config.feedback_setting.intervial_last_10mn:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} You had submitted {config.feedback_setting.intervial_last_10mn} already. '
                           'Waiting a bit before next submission.')
            return
        check_feedback_user = await store.sql_get_feedback_count_last(str(ctx.message.author.id), config.feedback_setting.intervial_each_user)
        if check_feedback_user and check_feedback_user >= 1:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} You had submitted one feedback already for the last {config.feedback_setting.intervial_each_user}s.'
                           'Waiting a bit before next submission.')
            return
        # OK he can submitted
        try:
            msg = await ctx.send(f'{ctx.author.mention} We are welcome for all feedback, inquiry or suggestion. '
                                 f'You can also join our support server as in {prefix}about command.\n'
                                 f'Please type in your feedback here (timeout {config.feedback_setting.waiting_for_feedback_text}s):')
            # DESC
            feedback = None
            while feedback is None:
                waiting_feedbackmsg = None
                try:
                    waiting_feedbackmsg = await bot.wait_for('message', timeout=config.feedback_setting.waiting_for_feedback_text, check=lambda msg: msg.author == ctx.author)
                except asyncio.TimeoutError:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{ctx.author.mention} **Timeout** for feedback submission. '
                                   'You can try again later.')
                    return
                if waiting_feedbackmsg is None:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{ctx.author.mention} **Timeout** for feedback submission. '
                                   'You can try again later.')
                    return
                else:
                        feedback = waiting_feedbackmsg.content.strip()
                        if len(feedback) <= config.feedback_setting.min_chars:
                            await ctx.message.add_reaction(EMOJI_ERROR)
                            msg = await ctx.send(f'{ctx.author.mention}, feedback message is too short.')
                            return
                        else:
                            # OK, let's add
                            feedback_id = str(uuid.uuid4())
                            text_in = "DM"
                            if isinstance(ctx.channel, discord.DMChannel) == False: text_in = str(ctx.message.channel.id)
                            howto_contact_back = "N/A"
                            msg = await ctx.send(f'{ctx.author.mention} (Optional) Please let us know if and how we can contact you back '
                                                 f'(timeout {config.feedback_setting.waiting_for_feedback_text}s) - default N/A:')
                            try:
                                waiting_howtoback = await bot.wait_for('message', timeout=config.feedback_setting.waiting_for_feedback_text, check=lambda msg: msg.author == ctx.author)
                            except asyncio.TimeoutError:
                                pass
                            else:
                                if len(waiting_howtoback.content.strip()) > 0: howto_contact_back = waiting_howtoback.content.strip()
                            add = await store.sql_feedback_add(str(ctx.message.author.id), '{}#{}'.format(ctx.message.author.name, ctx.message.author.discriminator), 
                                                               feedback_id, text_in, feedback, howto_contact_back)
                            if add:
                                msg = await ctx.send(f'{ctx.author.mention} Thank you for your feedback / inquiry. Your feedback ref: **{feedback_id}**')
                                await msg.add_reaction(EMOJI_OK_BOX)
                                try:
                                    botLogChan = bot.get_channel(id=LOG_CHAN)
                                    await botLogChan.send(f'{EMOJI_INFORMATION} A user has submitted a feedback `{feedback_id}`')
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                                return
                            else:
                                msg = await ctx.send(f'{ctx.author.mention} Internal Error.')
                                await msg.add_reaction(EMOJI_OK_BOX)
        except (discord.Forbidden, discord.errors.Forbidden) as e:
            await ctx.message.add_reaction(EMOJI_ERROR)
            return


@feedback.command(aliases=['vfb'], help=bot_help_view_feedback)
async def view(ctx, ref: str):
    if config.feedback_setting.enable != 1:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Feedback is not enable right now. Check back later.')
        return
    get_feedback = await store.sql_feedback_by_ref(ref)
    if get_feedback is None:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} We can not find feedback reference **{ref}**.')
        return
    else:
        # If he is bot owner or feedback owner:
        if int(get_feedback['user_id']) == ctx.message.author.id or ctx.message.author.id == OWNER_ID_TIPBOT:
            response_txt = 'Feedback ref: **{}** submitted by user id: {}, name: {}\n'.format(ref, get_feedback['user_id'], get_feedback['user_name'])
            response_txt += 'Content:\n\n{}\n\n'.format(get_feedback['feedback_text'])
            response_txt += 'Submitted date: {}'.format(datetime.fromtimestamp(get_feedback['feedback_date']))
            await ctx.message.add_reaction(EMOJI_OK_HAND)
            msg = await ctx.send(f'{response_txt}')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} You do not have permission to view **{ref}**.')
            return


@feedback.command(aliases=['ls'], help=bot_help_view_feedback_list)
async def list(ctx, userid: str=None):
    if config.feedback_setting.enable != 1:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Feedback is not enable right now. Check back later.')
        return
    if userid is None:
        get_feedback_list = await store.sql_feedback_list_by_user(str(ctx.message.author.id), 10)
        if get_feedback_list and len(get_feedback_list) > 0:
            table_data = [['Ref', 'Brief']]
            for each in get_feedback_list:
                table_data.append([each['feedback_id'], each['feedback_text'][0:48]])
            table = AsciiTable(table_data)
            await ctx.message.add_reaction(EMOJI_OK_HAND)
            msg = await ctx.send(f'{ctx.author.mention} Your feedback list:```{table.table}```')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} You do not have any feedback submitted.')
            return
    else:
        if ctx.message.author.id != OWNER_ID_TIPBOT:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} You have no permission.')
            return
        else:
            get_feedback_list = await store.sql_feedback_list_by_user(userid, 10)
            if get_feedback_list and len(get_feedback_list) > 0:
                table_data = [['Ref', 'Brief']]
                for each in get_feedback_list:
                    table_data.append([each['feedback_id'], each['feedback_text'][0:48]])
                table = AsciiTable(table_data)
                await ctx.message.add_reaction(EMOJI_OK_HAND)
                msg = await ctx.send(f'{ctx.author.mention} Feedback user {userid} list:```{table.table}```')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{ctx.author.mention} There is no feedback by {userid}.')
                return


@bot.command(pass_context=True, help=bot_help_height, hidden = True)
async def height(ctx, coin: str = None):
    global TRTL_DISCORD
    COIN_NAME = None
    serverinfo = None
    if coin is None:
        if isinstance(ctx.message.channel, discord.DMChannel):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send('Please add ticker: '+ ', '.join(ENABLE_COIN).lower() + ' with this command if in DM.')
            return
        else:
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            try:
                COIN_NAME = args[0].upper()
                if COIN_NAME not in ENABLE_COIN:
                    if COIN_NAME in ENABLE_COIN_DOGE:
                        pass
                    elif 'default_coin' in serverinfo:
                        COIN_NAME = serverinfo['default_coin'].upper()
                else:
                    pass
            except:
                if 'default_coin' in serverinfo:
                    COIN_NAME = serverinfo['default_coin'].upper()
            pass
    else:
        COIN_NAME = coin.upper()

    # check if bot channel is set:
    if serverinfo and serverinfo['botchan']:
        try: 
            if ctx.channel.id != int(serverinfo['botchan']):
                await ctx.message.add_reaction(EMOJI_ERROR)
                botChan = bot.get_channel(id=int(serverinfo['botchan']))
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, {botChan.mention} is the bot channel!!!')
                return
        except ValueError:
            pass
    # end of bot channel check

    # TRTL discord
    if isinstance(ctx.message.channel, discord.DMChannel) == False and ctx.guild.id == TRTL_DISCORD and COIN_NAME != "TRTL":
        return

    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if COIN_NAME not in (ENABLE_COIN + ENABLE_XMR):
        await ctx.message.add_reaction(EMOJI_ERROR)
        msg = await ctx.send(f'{ctx.author.mention} Unsupported or Unknown Ticker: **{COIN_NAME}**')
        return
    elif is_maintenance_coin(COIN_NAME):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} is under maintenance.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    gettopblock = None
    timeout = 60
    try:
        gettopblock = await daemonrpc_client.gettopblock(COIN_NAME, time_out=timeout)
    except asyncio.TimeoutError:
        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} connection to daemon timeout after {str(timeout)} seconds.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    except Exception as e:
        await logchanbot(traceback.format_exc())

    if gettopblock:
        height = ""
        if coin_family in [ "BCN", "TRTL", "XMR"] and COIN_NAME != "TRTL":
            height = "{:,}".format(gettopblock['block_header']['height'])
        else:
            height = "{:,}".format(gettopblock['height'])
        msg = await ctx.send(f'**[ {COIN_NAME} HEIGHT]**: {height}\n')
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    else:
        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME}\'s status unavailable.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return


@bot.command(pass_context=True, name='setting', aliases=['settings', 'set'], help=bot_help_settings)
@commands.has_permissions(manage_channels=True)
async def setting(ctx, *args):
    global LIST_IGNORECHAN, MUTE_CHANNEL
    # Check if address is valid first
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send('This command is not available in DM.')
        return
    botLogChan = bot.get_channel(id=LOG_CHAN)
    tickers = '|'.join(ENABLE_COIN).lower()
    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    server_prefix = config.discord.prefixCmd
    if serverinfo is None:
        # Let's add some info if server return None
        add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id),
                                                            ctx.message.guild.name, config.discord.prefixCmd, "WRKZ")
        server_id = str(ctx.guild.id)
        server_coin = DEFAULT_TICKER
        server_reacttip = "OFF"
    else:
        server_id = str(ctx.guild.id)
        server_prefix = serverinfo['prefix']
        server_coin = serverinfo['default_coin'].upper()
        server_reacttip = serverinfo['react_tip'].upper()
    
    if len(args) == 0:
        embed = discord.Embed(title = "CHANGE {} SETTING".format(ctx.guild.name), timestamp=datetime.utcnow())
        embed.add_field(name="Change Prefix", value=f'`{server_prefix}setting prefix .|?|*|!`', inline=False)
        embed.add_field(name="Change Default Coin", value=f'`{server_prefix}setting default_coin <coin_name> Use allcoin for every supported coin`', inline=False)
        embed.add_field(name="Tip Only", value=f'`{server_prefix}setting tiponly <coin1> [coin2] ..`', inline=False)
        embed.add_field(name="Bot Channel", value=f'`{server_prefix}setting botchan #channel_name`', inline=False)
        embed.add_field(name="Ignore Tipping this Channel", value=f'`{server_prefix}setting ignorechan`', inline=False)
        embed.add_field(name="Delete Ignored Channel", value=f'`{server_prefix}setting del_ignorechan`', inline=False)
        n_mute = 0
        n_ignore = 0
        
        MUTE_CHANNEL = await store.sql_list_mutechan()
        LIST_IGNORECHAN = await store.sql_listignorechan()
        if MUTE_CHANNEL and str(ctx.guild.id) in MUTE_CHANNEL:
            n_mute = len(MUTE_CHANNEL[str(ctx.guild.id)])
        if LIST_IGNORECHAN and str(ctx.guild.id) in LIST_IGNORECHAN:
            n_ignore = len(LIST_IGNORECHAN[str(ctx.guild.id)])
        embed.add_field(name="Num. Mute/Ignore Channel", value=f'`{n_mute} / {n_ignore}`', inline=False)
        try:
            msg = await ctx.send(embed=embed)
            await msg.add_reaction(EMOJI_OK_BOX)
        except Exception as e:
            await logchanbot(traceback.format_exc())
            await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
        return
    elif len(args) == 1:
        if args[0].upper() == "TIPONLY":
            await ctx.send(f'{ctx.author.mention} Please tell what coins to be allowed here. Separated by space.')
            return
        # enable / disable trade
        elif args[0].upper() == "TRADE":
            if serverinfo['enable_trade'] == "YES":
                changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_trade', 'NO')
                await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} DISABLE trade in their guild {ctx.guild.name} / {ctx.guild.id}')
                await ctx.send(f'{ctx.author.mention} DISABLE TRADE feature in this guild {ctx.guild.name}.')
                return
            elif serverinfo['enable_trade'] == "NO":
                changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_trade', 'YES')
                await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} ENABLE trade in their guild {ctx.guild.name} / {ctx.guild.id}')
                await ctx.send(f'{ctx.author.mention} ENABLE TRADE feature in this guild {ctx.guild.name}.')
            return
        # enable / disable game
        elif args[0].upper() == "GAME":
            if serverinfo['enable_game'] == "YES":
                changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_game', 'NO')
                await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} DISABLE game in their guild {ctx.guild.name} / {ctx.guild.id}')
                await ctx.send(f'{ctx.author.mention} DISABLE GAME feature in this guild {ctx.guild.name}.')
                return
            elif serverinfo['enable_game'] == "NO":
                changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_game', 'YES')
                await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} ENABLE game in their guild {ctx.guild.name} / {ctx.guild.id}')
                await ctx.send(f'{ctx.author.mention} ENABLE GAME feature in this guild {ctx.guild.name}.')
            return
        # enable / disable game
        elif args[0].upper() == "MARKET":
            if serverinfo['enable_market'] == "YES":
                changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_market', 'NO')
                await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} DISABLE market command in their guild {ctx.guild.name} / {ctx.guild.id}')
                await ctx.send(f'{ctx.author.mention} DISABLE market command in this guild {ctx.guild.name}.')
                return
            elif serverinfo['enable_market'] == "NO":
                changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'enable_market', 'YES')
                await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} ENABLE market command in their guild {ctx.guild.name} / {ctx.guild.id}')
                await ctx.send(f'{ctx.author.mention} ENABLE market command in this guild {ctx.guild.name}.')
            return
        elif args[0].upper() == "IGNORE_CHAN" or args[0].upper() == "IGNORECHAN":
            if LIST_IGNORECHAN is None:
                await store.sql_addignorechan_by_server(str(ctx.guild.id), str(ctx.channel.id), str(ctx.message.author.id), ctx.message.author.name)
                LIST_IGNORECHAN = await store.sql_listignorechan()
                await ctx.send(f'{ctx.author.mention} Added #{ctx.channel.name} to ignore tip action list.')
                return
            if str(ctx.guild.id) in LIST_IGNORECHAN:
                if str(ctx.channel.id) in LIST_IGNORECHAN[str(ctx.guild.id)]:
                    await ctx.send(f'{ctx.author.mention} This channel #{ctx.channel.name} is already in ignore list.')
                    return
                else:
                    await store.sql_addignorechan_by_server(str(ctx.guild.id), str(ctx.channel.id), str(ctx.message.author.id), ctx.message.author.name)
                    LIST_IGNORECHAN = await store.sql_listignorechan()
                    await ctx.send(f'{ctx.author.mention} Added #{ctx.channel.name} to ignore tip action list.')
                    return
            else:
                await store.sql_addignorechan_by_server(str(ctx.guild.id), str(ctx.channel.id), str(ctx.message.author.id), ctx.message.author.name)
                await ctx.send(f'{ctx.author.mention} Added #{ctx.channel.name} to ignore tip action list.')
                return
        elif args[0].upper() == "DEL_IGNORE_CHAN" or args[0].upper() == "DEL_IGNORECHAN" or args[0].upper() == "DELIGNORECHAN":
            if str(ctx.guild.id) in LIST_IGNORECHAN:
                if str(ctx.channel.id) in LIST_IGNORECHAN[str(ctx.guild.id)]:
                    await store.sql_delignorechan_by_server(str(ctx.guild.id), str(ctx.channel.id))
                    LIST_IGNORECHAN = await store.sql_listignorechan()
                    await ctx.send(f'{ctx.author.mention} This channel #{ctx.channel.name} is deleted from ignore tip list.')
                    return
                else:
                    await ctx.send(f'{ctx.author.mention} Channel #{ctx.channel.name} is not in ignore tip action list.')
                    return
            else:
                await ctx.send(f'{ctx.author.mention} Channel #{ctx.channel.name} is not in ignore tip action list.')
                return
        elif args[0].upper() == "MUTE":
            if MUTE_CHANNEL is None:
                await store.sql_add_mutechan_by_server(str(ctx.guild.id), str(ctx.channel.id), str(ctx.message.author.id), ctx.message.author.name)
                MUTE_CHANNEL = await store.sql_list_mutechan()
                await ctx.send(f'{ctx.author.mention} Added #{ctx.channel.name} to mute. I will ignore anything here.')
                return
            if str(ctx.guild.id) in MUTE_CHANNEL:
                if str(ctx.channel.id) in MUTE_CHANNEL[str(ctx.guild.id)]:
                    await ctx.send(f'{ctx.author.mention} This channel #{ctx.channel.name} is already in mute mode.')
                    return
                else:
                    await store.sql_add_mutechan_by_server(str(ctx.guild.id), str(ctx.channel.id), str(ctx.message.author.id), ctx.message.author.name)
                    MUTE_CHANNEL = await store.sql_list_mutechan()
                    await ctx.send(f'{ctx.author.mention} Added #{ctx.channel.name} to mute. I will ignore anything here.')
                    return
            else:
                await store.sql_add_mutechan_by_server(str(ctx.guild.id), str(ctx.channel.id), str(ctx.message.author.id), ctx.message.author.name)
                await ctx.send(f'{ctx.author.mention} Added #{ctx.channel.name} to mute. I will ignore anything here.')
                return
        elif args[0].upper() == "UNMUTE":
            if str(ctx.guild.id) in MUTE_CHANNEL:
                if str(ctx.channel.id) in MUTE_CHANNEL[str(ctx.guild.id)]:
                    await store.sql_del_mutechan_by_server(str(ctx.guild.id), str(ctx.channel.id))
                    MUTE_CHANNEL = await store.sql_list_mutechan()
                    await ctx.send(f'{ctx.author.mention} This channel #{ctx.channel.name} is unmute.')
                    return
                else:
                    await ctx.send(f'{ctx.author.mention} Channel #{ctx.channel.name} is not mute right now!')
                    return
            else:
                await ctx.send(f'{ctx.author.mention} Channel #{ctx.channel.name} is not mute right now!')
                return
        elif args[0].upper() == "BOTCHAN" or args[0].upper() == "BOTCHANNEL" or args[0].upper() == "BOT_CHAN":
            if serverinfo['botchan']:
                try: 
                    if ctx.channel.id == int(serverinfo['botchan']):
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.channel.name} is already the bot channel here!')
                        return
                    else:
                        # change channel info
                        changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'botchan', str(ctx.channel.id))
                        await ctx.send(f'Bot channel has set to {ctx.channel.mention}.')
                        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} change bot channel {ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}.')
                        return
                except ValueError:
                    return
            else:
                # change channel info
                changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'botchan', str(ctx.channel.id))
                await ctx.send(f'Bot channel has set to {ctx.channel.mention}.')
                await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} changed bot channel {ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}.')
                return
    elif len(args) == 2:
        if args[0].upper() == "TIPONLY":
            if (args[1].upper() not in (ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_COIN_ERC+ENABLE_COIN_NANO+ENABLE_XMR)) and (args[1].upper() not in ["ALLCOIN", "*", "ALL", "TIPALL", "ANY"]):
                await ctx.send(f'{ctx.author.mention} {args[1].upper()} is not in any known coin we set.')
                return
            else:
                set_coin = args[1].upper()
                if set_coin in ["ALLCOIN", "*", "ALL", "TIPALL", "ANY"]:
                    set_coin = "ALLCOIN"
                changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'tiponly', set_coin)
                if set_coin == "ALLCOIN":
                    await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} changed tiponly in {ctx.guild.name} / {ctx.guild.id} to `ALLCOIN`')
                    await ctx.send(f'{ctx.author.mention} Any coin is **allowed** here.')
                else:
                    await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} changed tiponly in {ctx.guild.name} / {ctx.guild.id} to `{args[1].upper()}`')
                    await ctx.send(f'{ctx.author.mention} {set_coin} will be the only tip here.')
                return
        elif args[0].upper() == "PREFIX":
            if args[1] not in [".", "?", "*", "!", "$", "~"]:
                await ctx.send(f'{ctx.author.mention} Invalid prefix **{args[1]}**')
                await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} wanted to changed prefix in {ctx.guild.name} / {ctx.guild.id} to `{args[1].lower()}`')
                return
            else:
                if server_prefix == args[1]:
                    await ctx.send(f'{ctx.author.mention} That\'s the default prefix. Nothing changed.')
                    return
                else:
                    changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'prefix', args[1].lower())
                    await ctx.send(f'{ctx.author.mention} Prefix changed from `{server_prefix}` to `{args[1].lower()}`.')
                    await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} changed prefix in {ctx.guild.name} / {ctx.guild.id} to `{args[1].lower()}`')
                    return
        elif args[0].upper() == "DEFAULT_COIN" or args[0].upper() == "DEFAULTCOIN" or args[0].upper() == "COIN":
            if args[1].upper() not in (ENABLE_COIN + ENABLE_XMR + ENABLE_COIN_DOGE + ENABLE_COIN_ERC + ENABLE_COIN_NANO + ENABLE_COIN_ERC):
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
                return
            else:
                if server_coin.upper() == args[1].upper():
                    await ctx.send(f'{ctx.author.mention} That\'s the default coin. Nothing changed.')
                    return
                else:
                    changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'default_coin', args[1].upper())
                    await ctx.send(f'Default Coin changed from `{server_coin}` to `{args[1].upper()}`.')
                    await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} changed default coin in {ctx.guild.name} / {ctx.guild.id} to {args[1].upper()}.')
                    return
        elif args[0].upper() == "REACTTIP":
            if args[1].upper() not in ["ON", "OFF"]:
                await ctx.send('Invalid Option. **ON OFF** Only.')
                return
            else:
                if server_reacttip == args[1].upper():
                    await ctx.send(f'{ctx.author.mention} That\'s the default option already. Nothing changed.')
                    return
                else:
                    changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'react_tip', args[1].upper())
                    await ctx.send(f'React Tip changed from `{server_reacttip}` to `{args[1].upper()}`.')
                    return
        elif args[0].upper() == "REACTAMOUNT" or args[0].upper() == "REACTTIP-AMOUNT":
            amount = args[1].replace(",", "")
            try:
                amount = Decimal(amount)
            except ValueError:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
                return
            changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'react_tip_100', amount)
            await ctx.send(f'React tip amount updated to to `{amount}{server_coin}`.')
            return
        else:
            await ctx.send(f'{ctx.author.mention} Invalid command input and parameter.')
            return
    elif len(args) >= 3:
        # If argument is more than 3, such as setting tiponly X Y ..
        if args[0].upper() == "TIPONLY":
            if args[1].upper() == "ALLCOIN" or args[1].upper() == "ALL" or args[1].upper() == "TIPALL" or args[1].upper() == "ANY" or args[1].upper() == "*":
                changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'tiponly', "ALLCOIN")
                await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} changed tiponly in {ctx.guild.name} / {ctx.guild.id} to `ALLCOIN`')
                await ctx.message.add_reaction(EMOJI_OK_HAND)
                await ctx.send(f'{ctx.author.mention} all coins will be allowed in here.')
                return
            else:
                try:
                    contained = [x.upper() for x in args if x.upper() in (ENABLE_COIN+ENABLE_XMR+ENABLE_COIN_DOGE+ENABLE_COIN_ERC+ENABLE_COIN_NANO)]
                    if contained and len(contained) >= 2:
                        tiponly_value = ','.join(contained)
                        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} changed tiponly in {ctx.guild.name} / {ctx.guild.id} to `{tiponly_value}`')
                        await ctx.send(f'{ctx.author.mention} TIPONLY set to: **{tiponly_value}**.')
                        changeinfo = await store.sql_changeinfo_by_server(str(ctx.guild.id), 'tiponly', tiponly_value.upper())
                        await ctx.message.add_reaction(EMOJI_OK_HAND)
                    else:
                        # Delete tiponly
                        del args[0]
                        list_coin = ', '.join(args)
                        await ctx.message.add_reaction(EMOJI_INFORMATION)
                        await ctx.send(f'{ctx.author.mention} No known coin in **{list_coin}**. TIPONLY is remained unchanged.')
                    return
                except Exception as e:
                    await logchanbot(traceback.format_exc())
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} In valid setting command input and parameter(s).')
        return


@bot.command(pass_context=True, help=bot_help_disclaimer)
async def disclaimer(ctx):
    global DISCLAIM_MSG
    await ctx.send(f'{EMOJI_INFORMATION} **THANK YOU FOR USING** {DISCLAIM_MSG_LONG}')
    return


@bot.command(pass_context=True, help=bot_help_itag, hidden = True)
async def itag(ctx, *, itag_text: str = None):
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send(f'{EMOJI_RED_NO} This command can not be in private.')
        return
    ListiTag = await store.sql_itag_by_server(str(ctx.guild.id))
    if not ctx.message.attachments:
        # Find available tag
        if itag_text is None:
            if len(ListiTag) > 0:
                itags = (', '.join([w['itag_id'] for w in ListiTag])).lower()
                await ctx.send(f'Available itag: `{itags}`.\nPlease use `.itag tagname` to show it.')
                return
            else:
                await ctx.send('There is no **itag** in this server. Please add.\n')
                return
        else:
            # .itag -del tagid
            command_del = itag_text.split(" ")
            if len(command_del) >= 2:
                TagIt = await store.sql_itag_by_server(str(ctx.guild.id), command_del[1].upper())
                if command_del[0].upper() == "-DEL" and TagIt:
                    # check permission if there is attachment with .itag
                    if ctx.author.guild_permissions.manage_guild == False:
                        await message.add_reaction(EMOJI_ERROR) 
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **itag** Permission denied.')
                        return
                    else:
                        DeliTag = await store.sql_itag_by_server_del(str(ctx.guild.id), command_del[1].upper())
                        if DeliTag:
                            await ctx.send(f'{ctx.author.mention} iTag **{command_del[1].upper()}** deleted.\n')
                        else:
                            await ctx.send(f'{ctx.author.mention} iTag **{command_del[1].upper()}** error deletion.\n')
                        return
                else:
                    await ctx.send(f'{ctx.author.mention} iTag unknow operation.\n')
                    return
            elif len(command_del) == 1:
                TagIt = await store.sql_itag_by_server(str(ctx.guild.id), itag_text.upper())
                if TagIt:
                    tagLink = config.itag.static_link + TagIt['stored_name']
                    await ctx.send(f'{tagLink}')
                    return
                else:
                    await ctx.send(f'There is no itag **{itag_text}** in this server.\n')
                    return
    else:
        if itag_text is None:
            await ctx.send(f'{EMOJI_RED_NO} You need to include **tag** for this image.')
            return
        else:
            # check permission if there is attachment with .itag
            if ctx.author.guild_permissions.manage_guild == False:
                await message.add_reaction(EMOJI_ERROR) 
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **itag** Permission denied.')
                return
            d = [i['itag_id'] for i in ListiTag]
            if itag_text.upper() in d:
                await ctx.send(f'{EMOJI_RED_NO} iTag **{itag_text}** already exists here.')
                return
            else:
                pass
    # we passed of no attachment
    attachment = ctx.message.attachments[0]
    if not (attachment.filename.lower()).endswith(('.gif', '.jpeg', '.jpg', '.png', '.mp4')):
        await ctx.send(f'{EMOJI_RED_NO} Attachment type rejected.')
        return
    else:
        print('Filename: {}'.format(attachment.filename))
    if attachment.size >= config.itag.max_size:
        await ctx.send(f'{EMOJI_RED_NO} File too big.')
        return
    else:
        print('Size: {}'.format(attachment.size))
    print("iTag: {}".format(itag_text))
    if re.match(r'^[a-zA-Z0-9_-]*$', itag_text):
        if len(itag_text) >= 32:
            await ctx.send(f'itag **{itag_text}** is too long.')
            return
    else:
        await ctx.send(f'{EMOJI_RED_NO} iTag id not accepted.')
        return
    link = attachment.url # https://cdn.discordapp.com/attachments
    attach_save_name = str(uuid.uuid4()) + '.' + link.split(".")[-1].lower()
    try:
        if link.startswith("https://cdn.discordapp.com/attachments"):
            async with aiohttp.ClientSession() as session:
                async with session.get(link) as resp:
                    if resp.status == 200:
                        if resp.headers["Content-Type"] not in ["image/gif", "image/png", "image/jpeg", "image/jpg", "video/mp4"]:
                            await ctx.send(f'{EMOJI_RED_NO} Unsupported format file.')
                            return
                        else: 
                            with open(config.itag.path + attach_save_name, 'wb') as f:
                                f.write(await resp.read())
                            # save to DB and inform
                            addiTag = await store.sql_itag_by_server_add(str(ctx.guild.id), itag_text.upper(),
                                                                         str(ctx.message.author), str(ctx.message.author.id),
                                                                         attachment.filename, attach_save_name, attachment.size)
                            if addiTag is None:
                                await ctx.send(f'{ctx.author.mention} Failed to add itag **{itag_text}**')
                                return
                            elif addiTag.upper() == itag_text.upper():
                                await ctx.send(f'{ctx.author.mention} Successfully added itag **{itag_text}**')
                                return
    except Exception as e:
        await logchanbot(traceback.format_exc())


@bot.command(pass_context=True, help=bot_help_tag)
async def tag(ctx, *args):
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send(f'{ctx.author.mention} {EMOJI_RED_NO} This command can not be in private.')
        return

    ListTag = await store.sql_tag_by_server(str(ctx.guild.id), None)

    if len(args) == 0:
        if len(ListTag) > 0:
            tags = (', '.join([w['tag_id'] for w in ListTag])).lower()
            msg = await ctx.send(f'{ctx.author.mention} Available tag: `{tags}`.\nPlease use `.tag tagname` to show it in detail.'
                                'If you have permission to manage discord server.\n'
                                'Use: `.tag -add|del tagname <Tag description ... >`')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        else:
            msg = await ctx.send(f'{ctx.author.mention} There is no tag in this server. Please add.\n'
                                'If you have permission to manage discord server.\n'
                                'Use: `.tag -add|-del tagname <Tag description ... >`')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
    elif len(args) == 1:
        # if .tag test
        TagIt = await store.sql_tag_by_server(str(ctx.guild.id), args[0].upper())
        # print(TagIt)
        if TagIt:
            tagDesc = TagIt['tag_desc']
            msg = await ctx.send(f'{ctx.author.mention} {tagDesc}')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        else:
            msg = await ctx.send(f'{ctx.author.mention} There is no tag {args[0]} in this server.\n'
                                'If you have permission to manage discord server.\n'
                                'Use: ```.tag -add|-del tagname <Tag description ... >```')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
    if (args[0].lower() in ['-add', '-del']) and ctx.author.guild_permissions.manage_guild == False:
        msg = await ctx.send(f'{ctx.author.mention} Permission denied.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    if args[0].lower() == '-add' and ctx.author.guild_permissions.manage_guild:
        if re.match('^[a-zA-Z0-9]+(-[a-zA-Z0-9]+)*$', args[1]):
            tag = args[1].upper()
            if len(tag) >= 32:
                await ctx.send(f'{ctx.author.mention} Tag ***{args[1]}*** is too long.')
                return

            tagDesc = ctx.message.content.strip()[(9 + len(tag) + 1):]
            if len(tagDesc) <= 3:
                msg = await ctx.send(f'{ctx.author.mention} Tag desc for ***{args[1]}*** is too short.')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
            if len(ListTag) > 0:
                d = [i['tag_id'] for i in ListTag]
                if tag.upper() in d:
                    await ctx.send(f'{ctx.author.mention} Tag **{args[1]}** already exists here.')
                    return
            addTag = await store.sql_tag_by_server_add(str(ctx.guild.id), tag.strip(), tagDesc.strip(),
                                                       ctx.message.author.name, str(ctx.message.author.id))
            if addTag is None:
                msg = await ctx.send(f'{ctx.author.mention} Failed to add tag **{args[1]}**')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
            if addTag.upper() == tag.upper():
                msg = await ctx.send(f'{ctx.author.mention} Successfully added tag **{args[1]}**')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
            else:
                msg = await ctx.send(f'{ctx.author.mention} Failed to add tag **{args[1]}**')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
        else:
            msg = await ctx.send(f'{ctx.author.mention} Tag {args[1]} is not valid.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        return
    elif args[0].lower() == '-del' and ctx.author.guild_permissions.manage_guild:
        #print('Has permission:' + str(ctx.message.content))
        if re.match('^[a-zA-Z0-9]+(-[a-zA-Z0-9]+)*$', args[1]):
            tag = args[1].upper()
            delTag = await store.sql_tag_by_server_del(str(ctx.guild.id), tag.strip())
            if delTag is None:
                await ctx.send(f'{ctx.author.mention} Failed to delete tag ***{args[1]}***')
                return
            if delTag.upper() == tag.upper():
                await ctx.send(f'{ctx.author.mention} Successfully deleted tag ***{args[1]}***')
                return
            else:
                await ctx.send(f'{ctx.author.mention} Failed to delete tag ***{args[1]}***')
                return
        else:
            await ctx.send(f'Tag {args[1]} is not valid.')
            return
        return


@bot.command(pass_context=True, name='invite', aliases=['inviteme'], help=bot_help_invite)
async def invite(ctx):
    global BOT_INVITELINK
    await ctx.send('**[INVITE LINK]**\n\n'
                f'{BOT_INVITELINK}')


@bot.command(pass_context=True, help=bot_help_random_number)
async def rand(ctx, randstring: str = None):
    rand_numb = None
    if randstring is None:
        rand_numb = random.randint(1,100)
    else:
        randstring = randstring.replace(",", "")
        rand_min_max = randstring.split("-")
        if len(rand_min_max) <= 1:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid range given. Example, use: `rand 1-50`')
            return
        try:
            min_numb = int(rand_min_max[0])
            max_numb = int(rand_min_max[1])
            if max_numb - min_numb <= 0:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid range given. Example, use: `rand 1-50`')
                return
            else:
                rand_numb = random.randint(min_numb,max_numb)
        except ValueError:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid range given. Example, use: `rand 1-50`')
            return
    if rand_numb:
        await ctx.message.add_reaction(EMOJI_OK_BOX)
        try:
            msg = await ctx.send('{} Random number: **{:,}**'.format(ctx.author.mention, rand_numb))
            await msg.add_reaction(EMOJI_OK_BOX)
        except (discord.Forbidden, discord.errors.Forbidden) as e:
            return


## Section of Trade
@bot.command(pass_context=True, aliases=['selling'])
async def sell(ctx, sell_amount: str, sell_ticker: str, buy_amount: str, buy_ticker: str):
    global IS_RESTARTING, ENABLE_TRADE_COIN, NOTIFY_TRADE_CHAN, TRTL_DISCORD

    # TRTL discord
    if isinstance(ctx.message.channel, discord.DMChannel) == False and ctx.guild and ctx.guild.id == TRTL_DISCORD:
        return

    botLogChan = bot.get_channel(id=LOG_CHAN)
    try:
        if isinstance(ctx.message.channel, discord.DMChannel) == True:
            pass
        else:
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if isinstance(ctx.message.channel, discord.DMChannel) == False and serverinfo \
            and 'enable_trade' in serverinfo and serverinfo['enable_trade'] == "NO":
                prefix = serverinfo['prefix']
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Trade Command is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING TRADE`')
                await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}sell command** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
                return
    except Exception as e:
        if isinstance(ctx.message.channel, discord.DMChannel) == False:
            return
        await logchanbot(traceback.format_exc())
        return

    # check if bot is going to restart
    if IS_RESTARTING:
        await ctx.message.add_reaction(EMOJI_REFRESH)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
        return

    sell_ticker = sell_ticker.upper()
    buy_ticker = buy_ticker.upper()
    sell_amount = sell_amount.replace(",", "")
    buy_amount = buy_amount.replace(",", "")
    try:
        sell_amount = Decimal(sell_amount)
        buy_amount = Decimal(buy_amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid sell/buy amount.')
        return
    if (sell_ticker not in ENABLE_TRADE_COIN) or (buy_ticker not in ENABLE_TRADE_COIN):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid trade ticker (buy/sell). Available right now: **{config.trade.enable_coin}**')
        return

    if not is_tradeable_coin(sell_ticker):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} **{sell_ticker}** trading is currently disable.')
        return

    if not is_tradeable_coin(buy_ticker):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} **{buy_ticker}** trading is currently disable.')
        return

    if buy_ticker == sell_ticker:
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {buy_ticker} you cannot trade the same coins.')
        return

    # get opened order:
    user_count_order = await store.sql_count_open_order_by_sellerid(str(ctx.message.author.id), 'DISCORD')
    if user_count_order >= config.trade.Max_Open_Order:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You have maximum opened selling **{config.trade.Max_Open_Order}**. Please cancel some or wait.')
        return

    coin_family_sell = getattr(getattr(config,"daemon"+sell_ticker),"coin_family","TRTL")
    real_amount_sell = int(sell_amount * get_decimal(sell_ticker)) if coin_family_sell in ["BCN", "XMR", "TRTL", "NANO"] else float(sell_amount)

    if real_amount_sell == 0:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {sell_amount}{sell_ticker} = 0 {sell_ticker} (below smallest unit).')
        return

    if real_amount_sell < get_min_sell(sell_ticker):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **{sell_amount}{sell_ticker}** below minimum trade **{num_format_coin(get_min_sell(sell_ticker), sell_ticker)}{sell_ticker}**.')
        return
    if real_amount_sell > get_max_sell(sell_ticker):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **{sell_amount}{sell_ticker}** above maximum trade **{num_format_coin(get_max_sell(sell_ticker), sell_ticker)}{sell_ticker}**.')
        return

    coin_family_buy = getattr(getattr(config,"daemon"+buy_ticker),"coin_family","TRTL")
    real_amount_buy = int(buy_amount * get_decimal(buy_ticker)) if coin_family_buy in ["BCN", "XMR", "TRTL", "NANO"] else float(buy_amount)
    if real_amount_buy == 0:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {buy_amount}{buy_ticker} = 0 {buy_ticker} (below smallest unit).')
        return
    if real_amount_buy < get_min_sell(buy_ticker):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **{buy_amount}{buy_ticker}** below minimum trade **{num_format_coin(get_min_sell(buy_ticker), buy_ticker)}{buy_ticker}**.')
        return
    if real_amount_buy > get_max_sell(buy_ticker):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **{buy_amount}{buy_ticker}** above maximum trade **{num_format_coin(get_max_sell(buy_ticker), buy_ticker)}{buy_ticker}**.')
        return

    if not is_maintenance_coin(sell_ticker):
        balance_actual = 0
        wallet = await store.sql_get_userwallet(str(ctx.message.author.id), sell_ticker, 'DISCORD')
        if wallet is None:
            userregister = await store.sql_register_user(str(ctx.message.author.id), sell_ticker, 'DISCORD', 0)
        userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), sell_ticker)
        xfer_in = 0
        if sell_ticker not in ENABLE_COIN_ERC:
            xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.message.author.id), sell_ticker)
        if sell_ticker in ENABLE_COIN_DOGE+ENABLE_COIN_ERC:
            actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
        elif sell_ticker in ENABLE_COIN_NANO:
            actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
            actual_balance = round(actual_balance / get_decimal(sell_ticker), 6) * get_decimal(sell_ticker)
        else:
            actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])

        # Negative check
        try:
            if actual_balance < 0:
                msg_negative = 'Negative balance detected:\nUser: '+str(ctx.message.author.id)+'\nCoin: '+sell_ticker+'\nAtomic Balance: '+str(actual_balance)
                await logchanbot(msg_negative)
        except Exception as e:
            await logchanbot(traceback.format_exc())

        if actual_balance < real_amount_sell:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You do not have enough '
                           f'**{sell_ticker}**. You have currently: {num_format_coin(actual_balance, sell_ticker)}{sell_ticker}.')
            return
        if (sell_amount / buy_amount) < MIN_TRADE_RATIO or (buy_amount / sell_amount) < MIN_TRADE_RATIO:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} ratio buy/sell rate is so low.')
            return
        # call other function
        return await sell_process(ctx, real_amount_sell, sell_ticker, real_amount_buy, buy_ticker)


async def sell_process(ctx, real_amount_sell: float, sell_ticker: str, real_amount_buy: float, buy_ticker: str):
    global NOTIFY_TRADE_CHAN
    botLogChan = bot.get_channel(id=LOG_CHAN)

    sell_ticker = sell_ticker.upper()
    buy_ticker = buy_ticker.upper()
    if sell_ticker in ["NANO", "BAN"]:
        real_amount_sell = round(real_amount_sell, 20)
    else:
        real_amount_sell = round(real_amount_sell, 8)
    if buy_ticker in ["NANO", "BAN"]:
        real_amount_buy = round(real_amount_buy, 20)
    else:
        real_amount_buy = round(real_amount_buy, 8)
    sell_div_get = round(real_amount_sell / real_amount_buy, 32)
    fee_sell = round(TRADE_PERCENT * real_amount_sell, 8)
    fee_buy = round(TRADE_PERCENT * real_amount_buy, 8)
    if fee_sell == 0: fee_sell = 0.00000100
    if fee_buy == 0: fee_buy = 0.00000100
    # Check if user already have another open order with the same rate
    # Check if user make a sell process of his buy coin which already in open order
    check_if_same_rate = await store.sql_get_order_by_sellerid_pair_rate('DISCORD', str(ctx.message.author.id), sell_ticker, 
                         buy_ticker, sell_div_get, real_amount_sell, real_amount_buy, fee_sell, fee_buy, 'OPEN')
    if check_if_same_rate and check_if_same_rate['error'] == True and check_if_same_rate['msg']:
        get_message = check_if_same_rate['msg']
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {get_message}')
        return
    elif check_if_same_rate and check_if_same_rate['error'] == False:
        get_message = check_if_same_rate['msg']
        await ctx.message.add_reaction(EMOJI_OK_BOX)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {get_message}')
        return
    elif check_if_same_rate == False:
        await logchanbot(f'Interal error: selling real amount {real_amount_sell}{sell_ticker} '
                         f'for real amount {real_amount_buy}{buy_ticker} and sell_div_get {sell_div_get}')
        await ctx.send(f'{EMOJI_INFORMATION} {ctx.author.mention} internal error to create open order, please report this.')
        return

    order_add = await store.sql_store_openorder(str(ctx.message.id), (ctx.message.content)[:120], sell_ticker, 
                            real_amount_sell, real_amount_sell-fee_sell, str(ctx.message.author.id), 
                            buy_ticker, real_amount_buy, real_amount_buy-fee_buy, sell_div_get, 'DISCORD')
    if order_add:
        get_message = "New open order created: #**{}**```Selling: {}{}\nFor: {}{}\nFee: {}{}```".format(order_add, 
                                                                        num_format_coin(real_amount_sell, sell_ticker), sell_ticker,
                                                                        num_format_coin(real_amount_buy, buy_ticker), buy_ticker,
                                                                        num_format_coin(fee_sell, sell_ticker), sell_ticker)
        await ctx.message.add_reaction(EMOJI_OK_BOX)
        try:
            await ctx.send(f'{ctx.author.mention} {get_message}')
        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            await logchanbot(traceback.format_exc())
        # add message to trade channel as well.
        if ctx.message.channel.id != NOTIFY_TRADE_CHAN or isinstance(ctx.message.channel, discord.DMChannel) == True:
            botLogChan = bot.get_channel(id=NOTIFY_TRADE_CHAN)
            await botLogChan.send(get_message)
        return


@bot.command(pass_context=True, aliases=['buying'])
async def buy(ctx, ref_number: str):
    global IS_RESTARTING, ENABLE_TRADE_COIN, NOTIFY_TRADE_CHAN, TRTL_DISCORD
    # TRTL discord
    if isinstance(ctx.message.channel, discord.DMChannel) == False and ctx.guild and ctx.guild.id == TRTL_DISCORD:
        return

    botLogChan = bot.get_channel(id=LOG_CHAN)
    try:
        if isinstance(ctx.message.channel, discord.DMChannel) == True:
            pass
        else:
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if isinstance(ctx.message.channel, discord.DMChannel) == False and serverinfo \
            and 'enable_trade' in serverinfo and serverinfo['enable_trade'] == "NO":
                prefix = serverinfo['prefix']
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Trade Command is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING TRADE`')
                await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}buy command** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
                return
    except Exception as e:
        if isinstance(ctx.message.channel, discord.DMChannel) == False:
            return
        await logchanbot(traceback.format_exc())
        return

    # check if bot is going to restart
    if IS_RESTARTING:
        await ctx.message.add_reaction(EMOJI_REFRESH)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
        return

    # check if the argument is ref or ticker by length
    if len(ref_number) < 6:
        # assume it is ticker
        # ,buy trtl (example)
        COIN_NAME = ref_number.upper()
        if COIN_NAME not in ENABLE_TRADE_COIN:
            await ctx.send(f'{EMOJI_ERROR} **{COIN_NAME}** is not in our list.')
            return
        
        # get list of all coin where they sell XXX
        get_markets = await store.sql_get_open_order_by_alluser_by_coins(COIN_NAME, 'ALL', 'OPEN')
        if get_markets and len(get_markets) > 0:
            list_numb = 0
            table_data = [
                ['PAIR', 'Selling', 'For', 'Rate', 'Order #']
                ]
            for order_item in get_markets:
                list_numb += 1
                if is_tradeable_coin(order_item['coin_get']) and is_tradeable_coin(order_item['coin_sell']):
                    table_data.append([order_item['pair_name'], num_format_coin(order_item['amount_sell_after_fee'], order_item['coin_sell'])+order_item['coin_sell'],
                                      num_format_coin(order_item['amount_get_after_fee'], order_item['coin_get'])+order_item['coin_get'], 
                                      '{:.8f}'.format(round(order_item['amount_sell']/order_item['amount_get']/get_decimal(order_item['coin_sell'])*get_decimal(order_item['coin_get']), 8)), 
                                      order_item['order_id']])
                else:
                    table_data.append([order_item['pair_name']+"*", num_format_coin(order_item['amount_sell_after_fee'], order_item['coin_sell'])+order_item['coin_sell'],
                                      num_format_coin(order_item['amount_get_after_fee'], order_item['coin_get'])+order_item['coin_get'], 
                                      '{:.8f}'.format(round(order_item['amount_sell']/order_item['amount_get']/get_decimal(order_item['coin_sell'])*get_decimal(order_item['coin_get']), 8)), 
                                      order_item['order_id']])
                if list_numb > 20:
                    break
            table = AsciiTable(table_data)
            # table.inner_column_border = False
            # table.outer_border = False
            table.padding_left = 0
            table.padding_right = 0
            title = "MARKET SELLING **{}**".format(COIN_NAME)
            await ctx.send(f'[ {title} ]\n'
                           f'```{table.table}```')
            return
        else:
            await ctx.send(f'{ctx.author.mention} Currently, no opening selling **{COIN_NAME}**. Please make some open order for others.')
            return
    else:
        # assume reference number
        get_order_num = await store.sql_get_order_numb(ref_number)
        if get_order_num:
            # check if own order
            if get_order_num['sell_user_server'] == "DISCORD" and ctx.message.author.id == int(get_order_num['userid_sell']):
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} #**{ref_number}** is your own selling order.')
                return
            else:
                # check if sufficient balance
                balance_actual = 0
                wallet = await store.sql_get_userwallet(str(ctx.message.author.id), get_order_num['coin_get'], 'DISCORD')
                if wallet is None:
                    userregister = await store.sql_register_user(str(ctx.message.author.id), get_order_num['coin_get'], 'DISCORD', 0)
                    wallet = await store.sql_get_userwallet(str(ctx.message.author.id), get_order_num['coin_get'], 'DISCORD')
                if wallet:
                    userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), get_order_num['coin_get'], 'DISCORD')
                    xfer_in = 0
                    if get_order_num['coin_get'] not in ENABLE_COIN_ERC:
                        xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.message.author.id), get_order_num['coin_get'])
                    if get_order_num['coin_get'] in ENABLE_COIN_DOGE+ENABLE_COIN_ERC:
                        actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
                    elif get_order_num['coin_get'] in ENABLE_COIN_NANO:
                        actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                        actual_balance = round(actual_balance / get_decimal(get_order_num['coin_get']), 6) * get_decimal(get_order_num['coin_get'])
                    else:
                        actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                    # Negative check
                    try:
                        if actual_balance < 0:
                            msg_negative = 'Negative balance detected:\nUser: '+str(ctx.message.author.id)+'\nCoin: '+get_order_num['coin_get']+'\nAtomic Balance: '+str(actual_balance)
                            await logchanbot(msg_negative)
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                if actual_balance < get_order_num['amount_get_after_fee']:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send('{} {} You do not have sufficient balance.'
                                   '```Needed: {}{}\n'
                                   'Have:   {}{}```'.format(EMOJI_RED_NO, ctx.author.mention, 
                                                     num_format_coin(get_order_num['amount_get'], 
                                                     get_order_num['coin_get']), get_order_num['coin_get'],
                                                     num_format_coin(actual_balance, get_order_num['coin_get']), 
                                                     get_order_num['coin_get']))
                    return
                else:
                    # let's make order update
                    match_order = await store.sql_match_order_by_sellerid(str(ctx.message.author.id), ref_number, 'DISCORD')
                    if match_order:
                        await ctx.message.add_reaction(EMOJI_OK_BOX)
                        try:
                            await ctx.send('{} #**{}** Order completed!'
                                           '```'
                                           'Get: {}{}\n'
                                           'From selling: {}{}\n'
                                           'Fee: {}{}\n'
                                           '```'.format(ctx.author.mention, ref_number, num_format_coin(get_order_num['amount_sell_after_fee'], 
                                                        get_order_num['coin_sell']), get_order_num['coin_sell'], 
                                                        num_format_coin(get_order_num['amount_get_after_fee'], 
                                                        get_order_num['coin_get']), get_order_num['coin_get'],
                                                        num_format_coin(get_order_num['amount_get']-get_order_num['amount_get_after_fee'], 
                                                        get_order_num['coin_get']), get_order_num['coin_get']))
                            try:
                                sold = num_format_coin(get_order_num['amount_sell'], get_order_num['coin_sell']) + get_order_num['coin_sell']
                                bought = num_format_coin(get_order_num['amount_get_after_fee'], get_order_num['coin_get']) + get_order_num['coin_get']
                                fee = str(num_format_coin(get_order_num['amount_get']-get_order_num['amount_get_after_fee'], get_order_num['coin_get']))
                                fee += get_order_num['coin_get']
                                if get_order_num['sell_user_server'] == "DISCORD":
                                    member = bot.get_user(id=int(get_order_num['userid_sell']))
                                    if member:
                                        try:
                                            await member.send(f'A user has bought #**{ref_number}**\n```Sold: {sold}\nGet: {bought}```')
                                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                                            pass
                                # add message to trade channel as well.
                                if ctx.message.channel.id != NOTIFY_TRADE_CHAN:
                                    botLogChan = bot.get_channel(id=NOTIFY_TRADE_CHAN)
                                    await botLogChan.send(f'A user has bought #**{ref_number}**\n```Sold: {sold}\nGet: {bought}\nFee: {fee}```')
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                pass
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            pass
                        return
                    else:
                        await ctx.message.add_reaction(EMOJI_ERROR)
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **{ref_number}** internal error, please report.')
                        return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} #**{ref_number}** does not exist or already completed.')
            return


@bot.command(pass_context=True, aliases=['market'])
async def trade(ctx, coin: str = None):
    global ENABLE_TRADE_COIN, TRTL_DISCORD
    # TRTL discord
    if isinstance(ctx.message.channel, discord.DMChannel) == False and ctx.guild and ctx.guild.id == TRTL_DISCORD:
        return

    botLogChan = bot.get_channel(id=LOG_CHAN)
    try:
        if isinstance(ctx.message.channel, discord.DMChannel) == True:
            pass
        else:
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if isinstance(ctx.message.channel, discord.DMChannel) == False and serverinfo \
            and 'enable_trade' in serverinfo and serverinfo['enable_trade'] == "NO":
                prefix = serverinfo['prefix']
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Trade Command is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING TRADE`')
                await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}trade/market command** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
                return
    except Exception as e:
        if isinstance(ctx.message.channel, discord.DMChannel) == False:
            return
        await logchanbot(traceback.format_exc())
        return

    if coin is None:
        get_markets = await store.sql_get_open_order_by_alluser('ALL', 'OPEN')
        if get_markets and len(get_markets) > 0:
            table_data = [
                ['PAIR', 'Selling', 'For', 'Rate', 'Order #']
                ]
            list_numb = 0
            for order_item in get_markets:
                list_numb += 1
                if is_tradeable_coin(order_item['coin_get']) and is_tradeable_coin(order_item['coin_sell']):
                    table_data.append([order_item['pair_name'], num_format_coin(order_item['amount_sell_after_fee'], order_item['coin_sell'])+order_item['coin_sell'],
                                      num_format_coin(order_item['amount_get_after_fee'], order_item['coin_get'])+order_item['coin_get'], 
                                      '{:.8f}'.format(round(order_item['amount_sell']/order_item['amount_get']/get_decimal(order_item['coin_sell'])*get_decimal(order_item['coin_get']), 8)), 
                                      order_item['order_id']])
                else:
                    table_data.append([order_item['pair_name']+"*", num_format_coin(order_item['amount_sell_after_fee'], order_item['coin_sell'])+order_item['coin_sell'],
                                      num_format_coin(order_item['amount_get_after_fee'], order_item['coin_get'])+order_item['coin_get'], 
                                      '{:.8f}'.format(round(order_item['amount_sell']/order_item['amount_get']/get_decimal(order_item['coin_sell'])*get_decimal(order_item['coin_get']), 8)), order_item['order_id']])
                if list_numb > 15:
                    break
            table = AsciiTable(table_data)
            # table.inner_column_border = False
            # table.outer_border = False
            table.padding_left = 0
            table.padding_right = 0
            extra_text = f"Check specifically for a coin *{config.trade.enable_coin}*."
            await ctx.send(f'**[ MARKET LIST ]**\n'
                           f'```{table.table}```{extra_text}')
            return
        else:
            await ctx.send(f'{ctx.author.mention} Currently, no opening selling market. Please make some open order for others.')
            return
    else:
        # check if there is / or -
        coin_pair = None
        COIN_NAME = None
        get_markets = None
        coin = coin.upper()
        if "/" in coin:
            coin_pair = coin.split("/")
        elif "." in coin:
            coin_pair = coin.split(".")
        elif "-" in coin:
            coin_pair = coin.split(".")
        if coin_pair is None:
            COIN_NAME = coin.upper()
            if COIN_NAME not in ENABLE_TRADE_COIN:
                await ctx.message.add_reaction(EMOJI_RED_NO)
                await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} in not in our list.')
                return
            else:
                get_markets = await store.sql_get_open_order_by_alluser(COIN_NAME, 'OPEN')
        elif coin_pair and len(coin_pair) == 2:
            if coin_pair[0] not in ENABLE_TRADE_COIN:
                await ctx.send(f'{EMOJI_ERROR} **{coin_pair[0]}** is not in our list. Available right now: **{config.trade.enable_coin}**')
                return
            elif coin_pair[1] not in ENABLE_TRADE_COIN:
                await ctx.send(f'{EMOJI_ERROR} **{coin_pair[1]}** is not in our list. Available right now: **{config.trade.enable_coin}**')
                return
            else:
                get_markets = await store.sql_get_open_order_by_alluser_by_coins(coin_pair[0], coin_pair[1], 'OPEN')
        if get_markets and len(get_markets) > 0:
            list_numb = 0
            table_data = [
                ['PAIR', 'Selling', 'For', 'Rate', 'Order #']
                ]
            for order_item in get_markets:
                list_numb += 1
                if is_tradeable_coin(order_item['coin_get']) and is_tradeable_coin(order_item['coin_sell']):
                    table_data.append([order_item['pair_name'], num_format_coin(order_item['amount_sell_after_fee'], order_item['coin_sell'])+order_item['coin_sell'],
                                      num_format_coin(order_item['amount_get_after_fee'], order_item['coin_get'])+order_item['coin_get'], 
                                      '{:.8f}'.format(round(order_item['amount_sell']/order_item['amount_get']/get_decimal(order_item['coin_sell'])*get_decimal(order_item['coin_get']), 8)), 
                                      order_item['order_id']])
                else:
                    table_data.append([order_item['pair_name']+"*", num_format_coin(order_item['amount_sell_after_fee'], order_item['coin_sell'])+order_item['coin_sell'],
                                      num_format_coin(order_item['amount_get_after_fee'], order_item['coin_get'])+order_item['coin_get'], 
                                      '{:.8f}'.format(round(order_item['amount_sell']/order_item['amount_get']/get_decimal(order_item['coin_sell'])*get_decimal(order_item['coin_get']), 8)), 
                                      order_item['order_id']])
                if list_numb > 15:
                    break
            table = AsciiTable(table_data)
            # table.inner_column_border = False
            # table.outer_border = False
            table.padding_left = 0
            table.padding_right = 0
            extra_text = f"Check specifically for a coin *{config.trade.enable_coin}*."
            if coin_pair:
                title = "**MARKET {}/{}**".format(coin_pair[0], coin_pair[1])
            else:
                title = "**MARKET {}**".format(COIN_NAME)
            await ctx.send(f'[ {title} ]\n'
                           f'```{table.table}```{extra_text}')
            return
        else:
            if coin_pair is None:
                # get another buy of ticker
                get_markets = await store.sql_get_open_order_by_alluser(COIN_NAME, 'OPEN', need_to_buy = True)
                if get_markets and len(get_markets) > 0:
                    list_numb = 0
                    table_data = [
                        ['PAIR', 'Selling', 'For', 'Rate', 'Order #']
                        ]
                    for order_item in get_markets:
                        list_numb += 1
                        if is_tradeable_coin(order_item['coin_get']) and is_tradeable_coin(order_item['coin_sell']):
                            table_data.append([order_item['pair_name'], num_format_coin(order_item['amount_sell_after_fee'], order_item['coin_sell'])+order_item['coin_sell'],
                                              num_format_coin(order_item['amount_get_after_fee'], order_item['coin_get'])+order_item['coin_get'], 
                                              '{:.8f}'.format(round(order_item['amount_sell']/order_item['amount_get']/get_decimal(order_item['coin_sell'])*get_decimal(order_item['coin_get']), 8)), 
                                              order_item['order_id']])
                        else:
                            table_data.append([order_item['pair_name']+"*", num_format_coin(order_item['amount_sell_after_fee'], order_item['coin_sell'])+order_item['coin_sell'],
                                              num_format_coin(order_item['amount_get_after_fee'], order_item['coin_get'])+order_item['coin_get'], 
                                              '{:.8f}'.format(round(order_item['amount_sell']/order_item['amount_get']/get_decimal(order_item['coin_sell'])*get_decimal(order_item['coin_get']), 8)), 
                                              order_item['order_id']])
                        if list_numb > 15:
                            break
                    table = AsciiTable(table_data)
                    table.padding_left = 0
                    table.padding_right = 0
                    title = "MARKET **{}**".format(COIN_NAME)
                    extra_text = f"Check specifically for a coin *{config.trade.enable_coin}*."
                    await ctx.send(f'There is no selling for {COIN_NAME} but there are buy order of {COIN_NAME}.\n[ {title} ]\n'
                                   f'```{table.table}```{extra_text}')
                    return
                else:
                    await ctx.send(f'{ctx.author.mention} Currently, no opening selling or buying market for {COIN_NAME}. Please make some open order for others.')
            else:
                await ctx.send(f'{ctx.author.mention} Currently, no opening selling market pair for {coin}. Please make some open order for others.')
            return


@bot.command(pass_context=True)
async def cancel(ctx, order_num: str = 'ALL'):
    global TRTL_DISCORD, ENABLE_TRADE_COIN
    # TRTL discord
    if isinstance(ctx.message.channel, discord.DMChannel) == False and ctx.guild and ctx.guild.id == TRTL_DISCORD:
        return

    botLogChan = bot.get_channel(id=LOG_CHAN)
    try:
        if isinstance(ctx.message.channel, discord.DMChannel) == True:
            pass
        else:
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if isinstance(ctx.message.channel, discord.DMChannel) == False and serverinfo \
            and 'enable_trade' in serverinfo and serverinfo['enable_trade'] == "NO":
                prefix = serverinfo['prefix']
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Trade Command is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING TRADE`')
                await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}cancel trade command** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
                return
    except Exception as e:
        if isinstance(ctx.message.channel, discord.DMChannel) == False:
            return
        await logchanbot(traceback.format_exc())
        return

    if order_num.upper() == 'ALL':
        get_open_order = await store.sql_get_open_order_by_sellerid_all(str(ctx.message.author.id), 'OPEN')
        if len(get_open_order) == 0:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You do not have any open order.')
            return
        else:
            cancel_order = await store.sql_cancel_open_order_by_sellerid(str(ctx.message.author.id), 'ALL')
            await ctx.message.add_reaction(EMOJI_OK_BOX)
            await ctx.send(f'{ctx.author.mention} You have cancelled all opened order(s).')
            return
    else:
        if len(order_num) < 6:
            # use coin name
            COIN_NAME = order_num.upper()
            if COIN_NAME not in ENABLE_TRADE_COIN:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **{COIN_NAME}** is not valid.')
                return
            else:
                get_open_order = await store.sql_get_open_order_by_sellerid(str(ctx.message.author.id), COIN_NAME, 'OPEN')
                if len(get_open_order) == 0:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{ctx.author.mention} You do not have any open order for **{COIN_NAME}**.')
                    return
                else:
                    cancel_order = await store.sql_cancel_open_order_by_sellerid(str(ctx.message.author.id), COIN_NAME)
                    await ctx.message.add_reaction(EMOJI_OK_BOX)
                    await ctx.send(f'{ctx.author.mention} You have cancelled all opened sell(s) for **{COIN_NAME}**.')
                    return
        else:
            # open order number
            get_open_order = await store.sql_get_open_order_by_sellerid_all(str(ctx.message.author.id), 'OPEN')
            if len(get_open_order) == 0:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You do not have any open order.')
                return
            else:
                cancelled = False
                for open_order_list in get_open_order:
                    if order_num == str(open_order_list['order_id']):
                        cancel_order = await store.sql_cancel_open_order_by_sellerid(str(ctx.message.author.id), order_num) 
                        if cancel_order: cancelled = True
                if cancelled == False:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You do not have sell #**{order_num}**. Please check command `myorder`')
                    return
                else:
                    await ctx.message.add_reaction(EMOJI_OK_BOX)
                    await ctx.send(f'{ctx.author.mention} You cancelled #**{order_num}**.')
                    return


@bot.command(pass_context=True, aliases=['order_num'])
async def order(ctx, order_num: str):
    global TRTL_DISCORD
    # TRTL discord
    if isinstance(ctx.message.channel, discord.DMChannel) == False and ctx.guild and ctx.guild.id == TRTL_DISCORD:
        return

    botLogChan = bot.get_channel(id=LOG_CHAN)
    try:
        if isinstance(ctx.message.channel, discord.DMChannel) == True:
            pass
        else:
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if isinstance(ctx.message.channel, discord.DMChannel) == False and serverinfo \
            and 'enable_trade' in serverinfo and serverinfo['enable_trade'] == "NO":
                prefix = serverinfo['prefix']
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Trade Command is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING TRADE`')
                await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}order command** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
                return
    except Exception as e:
        if isinstance(ctx.message.channel, discord.DMChannel) == False:
            return
        await logchanbot(traceback.format_exc())
        return

    # assume this is reference number
    try:
        ref_number = int(order_num)
        ref_number = str(ref_number)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid # number.')
        return
    get_order_num = await store.sql_get_order_numb(ref_number, 'ANY')
    if get_order_num:
        # check if own order
        response_text = "```"
        response_text += "Order #: " + ref_number + "\n"
        response_text += "Sell (After Fee): " + num_format_coin(get_order_num['amount_sell_after_fee'], get_order_num['coin_sell'])+get_order_num['coin_sell'] + "\n"
        response_text += "For (After Fee): " + num_format_coin(get_order_num['amount_get_after_fee'], get_order_num['coin_get'])+get_order_num['coin_get'] + "\n"
        if get_order_num['status'] == "COMPLETE":
            response_text = response_text.replace("Sell", "Sold")
            response_text += "Status: COMPLETED"
        elif get_order_num['status'] == "OPEN":
            response_text += "Status: OPENED"
        elif get_order_num['status'] == "CANCEL":
            response_text += "Status: CANCELLED"
        response_text += "```"

        if get_order_num['sell_user_server'] == "DISCORD" and ctx.message.author.id == int(get_order_num['userid_sell']):
            # if he is the seller
            response_text = response_text.replace("Sell", "You sell")
            response_text = response_text.replace("Sold", "You sold")
        if get_order_num['buy_user_server'] and get_order_num['buy_user_server'] == "DISCORD" \
        and 'userid_get' in get_order_num and (ctx.message.author.id == int(get_order_num['userid_get'] if get_order_num['userid_get'] else 0)):
            # if he bought this
            response_text = response_text.replace("Sold", "You bought: ")
            response_text = response_text.replace("For (After Fee):", "From selling (After Fee): ")
        await ctx.send(f'{ctx.author.mention} {response_text}')
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} I could not find #**{ref_number}**.')
    return


@bot.command(pass_context=True, aliases=['myorders'])
async def myorder(ctx, ticker: str = None):
    global ENABLE_TRADE_COIN, TRTL_DISCORD
    # TRTL discord
    if isinstance(ctx.message.channel, discord.DMChannel) == False and ctx.guild and ctx.guild.id == TRTL_DISCORD:
        return

    botLogChan = bot.get_channel(id=LOG_CHAN)
    try:
        if isinstance(ctx.message.channel, discord.DMChannel) == True:
            pass
        else:
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if isinstance(ctx.message.channel, discord.DMChannel) == False and serverinfo \
            and 'enable_trade' in serverinfo and serverinfo['enable_trade'] == "NO":
                prefix = serverinfo['prefix']
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Trade Command is not ENABLE yet in this guild. Please request Guild owner to enable by `{prefix}SETTING TRADE`')
                await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} tried **{prefix}myorder command** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
                return
    except Exception as e:
        if isinstance(ctx.message.channel, discord.DMChannel) == False:
            return
        await logchanbot(traceback.format_exc())
        return

    if ticker:
        if len(ticker) < 6:
            # assume it is a coin
            COIN_NAME = ticker.upper()
            if COIN_NAME not in ENABLE_TRADE_COIN:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid ticker **{COIN_NAME}**.')
                return
            else:
                get_open_order = await store.sql_get_open_order_by_sellerid(str(ctx.message.author.id), COIN_NAME, 'OPEN')
                if get_open_order and len(get_open_order) > 0:
                    table_data = [
                        ['PAIR', 'Selling', 'For', 'Order #']
                        ]
                    for order_item in get_open_order:
                        if is_tradeable_coin(order_item['coin_get']) and is_tradeable_coin(order_item['coin_sell']):
                            table_data.append([order_item['pair_name'], num_format_coin(order_item['amount_sell'], order_item['coin_sell'])+order_item['coin_sell'],
                                              num_format_coin(order_item['amount_get_after_fee'], order_item['coin_get'])+order_item['coin_get'], 
                                              order_item['order_id']])
                        else:
                            table_data.append([order_item['pair_name']+"*", num_format_coin(order_item['amount_sell'], order_item['coin_sell'])+order_item['coin_sell'],
                                              num_format_coin(order_item['amount_get_after_fee'], order_item['coin_get'])+order_item['coin_get'], 
                                              order_item['order_id']])
                    table = AsciiTable(table_data)
                    # table.inner_column_border = False
                    # table.outer_border = False
                    table.padding_left = 0
                    table.padding_right = 0
                    msg = await ctx.message.author.send(f'**[ OPEN SELLING LIST {COIN_NAME}]**\n'
                                                        f'```{table.table}```')
                    
                    return
                else:
                    await ctx.send(f'{ctx.author.mention} You do not have any active selling of **{COIN_NAME}**.')
                    return
        else:
            # assume this is reference number
            try:
                ref_number = int(ticker)
                ref_number = str(ref_number)
            except ValueError:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid # number.')
                return
            get_order_num = await store.sql_get_order_numb(ref_number)
            if get_order_num:
                # check if own order
                response_text = "```"
                response_text += "Order #: " + ref_number + "\n"
                response_text += "Sell (After Fee): " + num_format_coin(get_order_num['amount_sell_after_fee'], get_order_num['coin_sell'])+get_order_num['coin_sell'] + "\n"
                response_text += "For (After Fee): " + num_format_coin(get_order_num['amount_get_after_fee'], get_order_num['coin_get'])+get_order_num['coin_get'] + "\n"
                if get_order_num['status'] == "COMPLETE":
                    response_text = response_text.replace("Sell", "Sold")
                    response_text += "Status: COMPLETED"
                elif get_order_num['status'] == "OPEN":
                    response_text += "Status: OPENED"
                elif get_order_num['status'] == "CANCEL":
                    response_text += "Status: CANCELLED"
                response_text += "```"

                if get_order_num['sell_user_server'] == "DISCORD" and ctx.message.author.id == int(get_order_num['userid_sell']):
                    # if he is the seller
                    response_text = response_text.replace("Sell", "You sell")
                    response_text = response_text.replace("Sold", "You sold")
                if get_order_num['sell_user_server'] and get_order_num['sell_user_server'] == "DISCORD" and \
                    'userid_get' in get_order_num and (ctx.message.author.id == int(get_order_num['userid_get'] if get_order_num['userid_get'] else 0)):
                    # if he bought this
                    response_text = response_text.replace("Sold", "You bought: ")
                    response_text = response_text.replace("For (After Fee):", "From selling (After Fee): ")
                await ctx.send(f'{ctx.author.mention} {response_text}')
                return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} I could not find #**{ref_number}**.')
            return
    else:
        get_open_order = await store.sql_get_open_order_by_sellerid_all(str(ctx.message.author.id), 'OPEN')
        if get_open_order and len(get_open_order) > 0:
            table_data = [
                ['PAIR', 'Selling', 'For', 'Order #']
                ]
            for order_item in get_open_order:
                if is_tradeable_coin(order_item['coin_get']) and is_tradeable_coin(order_item['coin_sell']):
                    table_data.append([order_item['pair_name'], num_format_coin(order_item['amount_sell'], order_item['coin_sell'])+order_item['coin_sell'],
                                      num_format_coin(order_item['amount_get_after_fee'], order_item['coin_get'])+order_item['coin_get'], order_item['order_id']])
                else:
                    table_data.append([order_item['pair_name']+"*", num_format_coin(order_item['amount_sell'], order_item['coin_sell'])+order_item['coin_sell'],
                                      num_format_coin(order_item['amount_get_after_fee'], order_item['coin_get'])+order_item['coin_get'], order_item['order_id']])
            table = AsciiTable(table_data)
            # table.inner_column_border = False
            # table.outer_border = False
            table.padding_left = 0
            table.padding_right = 0
            msg = await ctx.message.author.send(f'**[ OPEN SELLING LIST ]**\n'
                                                f'```{table.table}```')
            
            return
        else:
            await ctx.send(f'{ctx.author.mention} You do not have any active selling.')
            return
## END of Section of Trade

def hhashes(num) -> str:
    for x in ['H/s', 'KH/s', 'MH/s', 'GH/s', 'TH/s', 'PH/s', 'EH/s']:
        if num < 1000.0:
            return "%3.1f%s" % (num, x)
        num /= 1000.0
    return "%3.1f%s" % (num, 'TH/s')


async def alert_if_userlock(ctx, cmd: str):
    botLogChan = bot.get_channel(id=LOG_CHAN)
    get_discord_userinfo = None
    try:
        get_discord_userinfo = await store.sql_discord_userinfo_get(str(ctx.message.author.id))
    except Exception as e:
        await logchanbot(traceback.format_exc())
    if get_discord_userinfo is None:
        return None
    else:
        if get_discord_userinfo['locked'].upper() == "YES":
            await botLogChan.send(f'{ctx.message.author.name}#{ctx.message.author.discriminator} locked but is commanding `{cmd}`')
            return True
        else:
            return None


async def get_info_pref_coin(ctx):
    if isinstance(ctx.channel, discord.DMChannel):
        prefixChar = '.'
        return {'server_prefix': prefixChar}
    else:
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo is None:
            # Let's add some info if server return None
            add_server_info = await store.sql_addinfo_by_server(str(ctx.guild.id),
                                                                ctx.message.guild.name, config.discord.prefixCmd, "WRKZ")
            server_id = str(ctx.guild.id)
            server_prefix = config.discord.prefixCmd
            server_coin = DEFAULT_TICKER
        else:
            server_id = str(ctx.guild.id)
            server_prefix = serverinfo['prefix']
            server_coin = serverinfo['default_coin'].upper()
            botchan = serverinfo['botchan'] or None
        return {'server_prefix': server_prefix, 'default_coin': server_coin, 'server_id': server_id, 'servername': ctx.guild.name, 'botchan': botchan}


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


async def check_guild_permissions(ctx, perms, *, check=all):
    is_owner = await ctx.bot.is_owner(ctx.author)
    if is_owner:
        return True

    if ctx.guild is None:
        return False

    resolved = ctx.author.guild_permissions
    return check(getattr(resolved, name, None) == value for name, value in perms.items())


@admin.error
async def admin_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Looks like you don\'t have the permission.')


@setting.error
async def setting_error(ctx, error):
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send('This command is not available in DM.')
        return
    if isinstance(error, commands.MissingPermissions):
        prefix = await get_guild_prefix(ctx)
        embed = discord.Embed(title=f'Guild {ctx.guild.id} / {ctx.guild.name}', timestamp=datetime.utcnow())
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
        embed.add_field(name="Default Prefix", value=f'`{prefix}`', inline=True)
        embed.set_footer(text=f"You don\'t have the permission to change anything. Use {prefix}info also.")
        try:
            msg = await ctx.send(embed=embed)
            await msg.add_reaction(EMOJI_OK_BOX)
        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            pass
        return


@register.error
async def register_error(ctx, error):
    prefix = await get_guild_prefix(ctx)
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing your wallet address. '
                       f'You need to have a supported coin **address** after `register` command. Example: {prefix}register coin_address')
    return


@account.error
@verify.error
async def account_verify_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing 2FA codes.')
    return


@account.error
@unverify.error
async def account_unverify_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing 2FA codes.')
    return


@info.error
async def info_error(ctx, error):
    pass


@randtip.error
async def randtip_error(ctx, error):
    prefix = await get_guild_prefix(ctx)
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing coin ticker and/or amount. '
                       f'Example: {prefix}randtip 10 doge')
    return


@balance.error
async def balance_error(ctx, error):
    pass


@pools.error
async def pools_error(ctx, error):
    prefix = await get_guild_prefix(ctx)
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing **full coin name**. '
                       f'Example: {prefix}pools **coin_name**')
    return


@botbalance.error
async def botbalance_error(ctx, error):
    prefix = await get_guild_prefix(ctx)
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing Bot and/or ticker. '
                       f'You need to @mention_bot COIN.\nExample: {prefix}botbalance <@{bot.user.id}> **coin_name**')
    return


@withdraw.error
async def withdraw_error(ctx, error):
    prefix = await get_guild_prefix(ctx)
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing amount and/or ticker. '
                       f'You need to tell me **AMOUNT** and/or **TICKER**.\nExample: {prefix}withdraw **1,000 coin_name**')
    return


@notifytip.error
async def notifytip_error(ctx, error):
    prefix = await get_guild_prefix(ctx)
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Use {prefix}notifytip **on** or {prefix}notifytip **off**')
    return


@freetip.error
async def freetip_error(ctx, error):
    prefix = await get_guild_prefix(ctx)
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing arguments. '
                       f'You need to tell me **amount** and **coin name**.\nExample: {prefix}freetip **1,000 coin_name**')
    return


@tip.error
async def tip_error(ctx, error):
    prefix = await get_guild_prefix(ctx)
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing arguments. '
                       f'You need to tell me **amount** and who you want to tip to.\nExample: {prefix}tip **1,000 coin_name** <@{bot.user.id}>')
    return


@mtip.error
async def mtip_error(ctx, error):
    prefix = await get_guild_prefix(ctx)
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send('This command is not available in DM.')
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(f'{ctx.author.mention} You do not have permission in this guild **{ctx.guild.name}** Please use normal {prefix}tip command.')
        return


@deposit.error
async def deposit_error(ctx, error):
    prefix = await get_guild_prefix(ctx)
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing argument **ticker/coin_name**.\nExample: {prefix}deposit **coin_name**')
    return


@donate.error
async def donate_error(ctx, error):
    prefix = await get_guild_prefix(ctx)
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing arguments. '
                       'You need to tell me **amount** and ticker.\n'
                       f'Example: {prefix}donate **1,000 coin_name**\n'
                       f'Get donation list we received: {prefix}donate list')
    return


@tipall.error
async def tipall_error(ctx, error):
    prefix = await get_guild_prefix(ctx)
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing argument. '
                       f'You need to tell me **amount**.\nExample: {prefix}tipall **1,000 coin_name**')
    return


@userinfo.error
async def userinfo_error(ctx, error):
    prefix = await get_guild_prefix(ctx)
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing arguments. \n'
                       f'Example: `{prefix}userinfo @mention`')
    return


@send.error
async def send_error(ctx, error):
    prefix = await get_guild_prefix(ctx)
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing arguments. \n'
                       f'Example: {prefix}send **amount coin_address**')
    return


@voucher.error
async def voucher_error(ctx, error):
    prefix = await get_guild_prefix(ctx)
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing arguments. \n'
                       f'Example: {prefix}voucher **make amount coin_name some comments**')
    return


@voucher.error
@make.error
async def voucher_make_error(ctx, error):
    prefix = await get_guild_prefix(ctx)
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing arguments. \n'
                       f'Example: {prefix}voucher **make amount coin_name some comments**')
    return


@address.error
async def address_error(ctx, error):
    pass


@paymentid.error
async def payment_error(ctx, error):
    pass


@tag.error
async def tag_error(ctx, error):
    pass


@height.error
async def height_error(ctx, error):
    pass


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send('This command cannot be used in private messages.')
    elif isinstance(error, commands.DisabledCommand):
        await ctx.send('Sorry. This command is disabled and cannot be used.')
    elif isinstance(error, commands.MissingRequiredArgument):
        #command = ctx.message.content.split()[0].strip('.')
        #await ctx.send('Missing an argument: try `.help` or `.help ' + command + '`')
        pass
    elif isinstance(error, commands.CommandNotFound):
        pass


# Update number of user, bot, channel
async def update_user_guild():
    await bot.wait_until_ready()
    while not bot.is_closed():
        for g in bot.guilds:
            num_channel = sum(1 for _ in g.channels)
            num_user = sum(1 for _ in g.members)
            num_bot = sum(1 for member in g.members if member.bot == True)
            num_online = sum(1 for member in g.members if member.status != "offline")
            await store.sql_updatestat_by_server(str(g.id), num_user, num_bot, num_channel, num_online, g.name)
        await asyncio.sleep(300)



async def update_block_height():
    sleep_time = 5
    while True:
        for coinItem in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR:
            if is_maintenance_coin(coinItem):
                pass
            elif not is_coin_depositable(coinItem):
                pass
            else:
                start = time.time()
                try:
                    await store.sql_block_height(coinItem)
                except Exception as e:
                    await logchanbot(traceback.format_exc())
                end = time.time()
            if end - start > config.interval.log_longduration:
                await logchanbot('update_block_height {} longer than {}s'.format(coinItem, config.interval.log_longduration))
        for coinItem in ENABLE_COIN_ERC:
            if is_maintenance_coin(coinItem):
                pass
            elif not is_coin_depositable(coinItem):
                pass
            else:
                start = time.time()
                try:
                    await store.erc_get_block_number(coinItem)
                except Exception as e:
                    await logchanbot(traceback.format_exc())
                end = time.time()
            if end - start > config.interval.log_longduration:
                await logchanbot('update_block_height {} longer than {}s'.format(coinItem, config.interval.log_longduration))
        await asyncio.sleep(sleep_time)


# Let's run balance update by a separate process
async def update_balance_erc():
    while True:
        await asyncio.sleep(config.interval.update_balance)
        for coinItem in ENABLE_COIN_ERC:
            if is_maintenance_coin(coinItem) or not is_coin_depositable(coinItem):
                continue
            start = time.time()
            try:
                check_min = await store.erc_check_minimum_deposit(coinItem)
            except Exception as e:
                print(traceback.format_exc())
                await logchanbot(traceback.format_exc())
            end = time.time()
        await asyncio.sleep(config.interval.update_balance)


async def unlocked_move_pending_erc():
    while True:
        await asyncio.sleep(config.interval.update_balance)
        for coinItem in ENABLE_COIN_ERC:
            if is_maintenance_coin(coinItem) or not is_coin_depositable(coinItem):
                continue
            start = time.time()
            try:
                await store.erc_check_pending_move_deposit(coinItem)
            except Exception as e:
                print(traceback.format_exc())
                await logchanbot(traceback.format_exc())
            end = time.time()
        await asyncio.sleep(config.interval.update_balance)


async def erc_notify_new_confirmed_spendable():
    while True:
        await asyncio.sleep(config.interval.update_balance)
        for coinItem in ENABLE_COIN_ERC:
            if is_maintenance_coin(coinItem) or not is_coin_depositable(coinItem):
                continue
            start = time.time()
            try:
                notify_list = await store.erc_get_pending_notification_users(coinItem)
                if notify_list and len(notify_list) > 0:
                    for each_notify in notify_list:
                        is_notify_failed = False
                        member = bot.get_user(id=int(each_notify['user_id']))
                        if member:
                            msg = "You got a new deposit confirmed: ```" + "Amount: {}{}".format(each_notify['real_amount'], coinItem) + "```"
                            try:
                                await member.send(msg)
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                is_notify_failed = True
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                                await logchanbot(traceback.format_exc())
                            update_status = await store.erc_updating_pending_move_deposit(True, is_notify_failed, each_notify['txn'])
            except Exception as e:
                await logchanbot(traceback.format_exc())
            end = time.time()
        await asyncio.sleep(config.interval.update_balance)


# Let's run balance update by a separate process
async def update_balance():
    while True:
        for coinItem in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR:
            if is_maintenance_coin(coinItem) or not is_coin_depositable(coinItem):
                continue
            start = time.time()
            try:
                await store.sql_update_balances(coinItem)
            except Exception as e:
                await logchanbot(traceback.format_exc())
            end = time.time()
            if end - start > config.interval.log_longduration:
                await logchanbot('update_balance {} longer than {}s'.format(coinItem, config.interval.log_longduration))
        await asyncio.sleep(config.interval.update_balance)

# notify_new_tx_user_noconfirmation
async def notify_new_tx_user_noconfirmation():
    global redis_conn
    INTERVAL_EACH = config.interval.notify_tx
    await bot.wait_until_ready()
    while True:
        if config.notify_new_tx.enable_new_no_confirm == 1:
            key_tx_new = 'TIPBOT:NEWTX:NOCONFIRM'
            key_tx_no_confirmed_sent = 'TIPBOT:NEWTX:NOCONFIRM:SENT'
            try:
                openRedis()
                if redis_conn and redis_conn.llen(key_tx_new) > 0:
                    list_new_tx = redis_conn.lrange(key_tx_new, 0, -1)
                    list_new_tx_sent = redis_conn.lrange(key_tx_no_confirmed_sent, 0, -1) # byte list with b'xxx'
                    for tx in list_new_tx:
                        try:
                            if tx not in list_new_tx_sent:
                                tx = tx.decode() # decode byte from b'xxx to xxx
                                key_tx_json = 'TIPBOT:NEWTX:' + tx
                                eachTx = None
                                try:
                                    if redis_conn.exists(key_tx_json): eachTx = json.loads(redis_conn.get(key_tx_json).decode())
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                                if eachTx and eachTx['coin_name'] in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR:
                                    user_tx = await store.sql_get_userwallet_by_paymentid(eachTx['payment_id'], eachTx['coin_name'], 'DISCORD')
                                    if user_tx and eachTx['coin_name'] in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR:
                                        user_found = bot.get_user(id=int(user_tx['user_id']))
                                        if user_found:
                                            try:
                                                msg = None
                                                confirmation_number_txt = "{} needs {} confirmations.".format(eachTx['coin_name'], get_confirm_depth(eachTx['coin_name']))
                                                if eachTx['coin_name'] not in ENABLE_COIN_DOGE:
                                                    msg = "You got a new **pending** deposit: ```" + "Coin: {}\nTx: {}\nAmount: {}\nHeight: {:,.0f}\n{}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name']), eachTx['height'], confirmation_number_txt) + "```"
                                                else:
                                                    msg = "You got a new **pending** deposit: ```" + "Coin: {}\nTx: {}\nAmount: {}\nBlock Hash: {}\n{}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name']), eachTx['blockhash'], confirmation_number_txt) + "```"
                                                await user_found.send(msg)
                                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                                pass
                                            redis_conn.lpush(key_tx_no_confirmed_sent, tx)
                                        else:
                                            # try to find if it is guild
                                            guild_found = bot.get_guild(id=int(user_tx['user_id']))
                                            if guild_found: user_found = bot.get_user(id=guild_found.owner.id)
                                            if guild_found and user_found:
                                                try:
                                                    msg = None
                                                    confirmation_number_txt = "{} needs {} confirmations.".format(eachTx['coin_name'], get_confirm_depth(eachTx['coin_name']))
                                                    if eachTx['coin_name'] not in ENABLE_COIN_DOGE:
                                                        msg = "Your guild got a new **pending** deposit: ```" + "Coin: {}\nTx: {}\nAmount: {}\nHeight: {:,.0f}\n{}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name']), eachTx['height'], confirmation_number_txt) + "```"
                                                    else:
                                                        msg = "Your guild got a new **pending** deposit: ```" + "Coin: {}\nTx: {}\nAmount: {}\nBlock Hash: {}\n{}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name']), eachTx['blockhash'], confirmation_number_txt) + "```"
                                                    await user_found.send(msg)
                                                except (discord.Forbidden, discord.errors.Forbidden) as e:
                                                    pass
                                                except Exception as e:
                                                    await logchanbot(traceback.format_exc())
                                                redis_conn.lpush(key_tx_no_confirmed_sent, tx)
                                            else:
                                                print('Can not find user id {} to notification **pending** tx: {}'.format(user_tx['user_id'], eachTx['txid']))
                                    # TODO: if no user
                                    # elif eachTx['coin_name'] in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR:
                                    #    redis_conn.lpush(key_tx_no_confirmed_sent, tx)
                                # if disable coin
                                else:
                                    redis_conn.lpush(key_tx_no_confirmed_sent, tx)
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
            except Exception as e:
                await logchanbot(traceback.format_exc())
        await asyncio.sleep(INTERVAL_EACH)


# Notify user
async def notify_new_tx_user():
    INTERVAL_EACH = config.interval.notify_tx
    await bot.wait_until_ready()
    while True:
        pending_tx = await store.sql_get_new_tx_table('NO', 'NO')
        if pending_tx and len(pending_tx) > 0:
            # let's notify_new_tx_user
            for eachTx in pending_tx:
                try:
                    if eachTx['coin_name'] in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR+ENABLE_COIN_NANO:
                        user_tx = await store.sql_get_userwallet_by_paymentid(eachTx['payment_id'], eachTx['coin_name'], 'DISCORD')
                        if user_tx:
                            user_found = bot.get_user(id=int(user_tx['user_id']))
                            if user_found:
                                is_notify_failed = False
                                try:
                                    msg = None
                                    if eachTx['coin_name'] in ENABLE_COIN_NANO:
                                        msg = "You got a new deposit: ```" + "Coin: {}\nAmount: {}".format(eachTx['coin_name'], num_format_coin(eachTx['amount'], eachTx['coin_name'])) + "```"   
                                    elif eachTx['coin_name'] not in ENABLE_COIN_DOGE:
                                        msg = "You got a new deposit confirmed: ```" + "Coin: {}\nTx: {}\nAmount: {}\nHeight: {:,.0f}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name']), eachTx['height']) + "```"                         
                                    else:
                                        msg = "You got a new deposit confirmed: ```" + "Coin: {}\nTx: {}\nAmount: {}\nBlock Hash: {}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name']), eachTx['blockhash']) + "```"
                                    await user_found.send(msg)
                                except (discord.Forbidden, discord.errors.Forbidden) as e:
                                    is_notify_failed = True
                                    pass
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                                update_notify_tx = await store.sql_update_notify_tx_table(eachTx['payment_id'], user_tx['user_id'], user_found.name, 'YES', 'NO' if is_notify_failed == False else 'YES')
                            else:
                                # try to find if it is guild
                                guild_found = bot.get_guild(id=int(user_tx['user_id']))
                                if guild_found: user_found = bot.get_user(id=guild_found.owner.id)
                                if guild_found and user_found:
                                    is_notify_failed = False
                                    try:
                                        msg = None
                                        if eachTx['coin_name'] in ENABLE_COIN_NANO:
                                            msg = "Your guild got a new deposit: ```" + "Coin: {}\nAmount: {}".format(eachTx['coin_name'], num_format_coin(eachTx['amount'], eachTx['coin_name'])) + "```"   
                                        elif eachTx['coin_name'] not in ENABLE_COIN_DOGE:
                                            msg = "Your guild got a new deposit confirmed: ```" + "Coin: {}\nTx: {}\nAmount: {}\nHeight: {:,.0f}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name']), eachTx['height']) + "```"                         
                                        else:
                                            msg = "Your guild got a new deposit confirmed: ```" + "Coin: {}\nTx: {}\nAmount: {}\nBlock Hash: {}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name']), eachTx['blockhash']) + "```"
                                        await user_found.send(msg)
                                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                                        is_notify_failed = True
                                        pass
                                    except Exception as e:
                                        await logchanbot(traceback.format_exc())
                                    update_notify_tx = await store.sql_update_notify_tx_table(eachTx['payment_id'], user_tx['user_id'], guild_found.name, 'YES', 'NO' if is_notify_failed == False else 'YES')
                                else:
                                    print('Can not find user id {} to notification tx: {}'.format(user_tx['user_id'], eachTx['txid']))
                except Exception as e:
                    await logchanbot(traceback.format_exc())
        await asyncio.sleep(INTERVAL_EACH)


async def saving_wallet():
    global LOG_CHAN
    saving = False
    await bot.wait_until_ready()
    botLogChan = bot.get_channel(id=LOG_CHAN)
    while not bot.is_closed():
        while botLogChan is None:
            botLogChan = bot.get_channel(id=LOG_CHAN)
            await asyncio.sleep(10)
        COIN_SAVING = ENABLE_COIN + ENABLE_XMR
        for COIN_NAME in COIN_SAVING:
            if is_maintenance_coin(COIN_NAME) or (COIN_NAME in ["BCN"]):
                continue
            if (COIN_NAME in ENABLE_COIN + ENABLE_XMR) and saving == False:
                duration = None
                saving = True
                try:
                    if COIN_NAME in WALLET_API_COIN:
                        duration = await walletapi.save_walletapi(COIN_NAME)
                    else:
                        duration = await rpc_cn_wallet_save(COIN_NAME)
                except Exception as e:
                    await logchanbot(traceback.format_exc())
                if duration:
                    if duration > 30:
                        await botLogChan.send(f'INFO: AUTOSAVE FOR **{COIN_NAME}** TOOK **{round(duration, 3)}s**.')
                    elif duration > 5:
                        print(f'INFO: AUTOSAVE FOR **{COIN_NAME}** TOOK **{round(duration, 3)}s**.')
                else:
                    await botLogChan.send(f'WARNING: AUTOSAVE FOR **{COIN_NAME}** FAILED.')
                saving = False
            await asyncio.sleep(config.interval.saving_wallet_sleep)
        await asyncio.sleep(config.interval.wallet_balance_update_interval)


# Multiple tip
async def _tip(ctx, amount, coin: str, if_guild: bool=False):
    global TX_IN_PROCESS
    guild_name = '**{}**'.format(ctx.guild.name) if if_guild == True else ''
    tip_type_text = 'guild tip' if if_guild == True else 'tip'
    guild_or_tip = 'GUILDTIP' if if_guild == True else 'TIPS'
    id_tipper = str(ctx.guild.id) if if_guild == True else str(ctx.message.author.id)
    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    tipmsg = ""
    if if_guild:
        try:
            if serverinfo['tip_message']: tipmsg = "**Guild Message:**\n" + serverinfo['tip_message']
        except Exception as e:
            pass
    botLogChan = bot.get_channel(id=LOG_CHAN)

    COIN_NAME = coin.upper()
    notifyList = await store.sql_get_tipnotify()
    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    if coin_family == "ERC-20":
        real_amount = float(amount)
        token_info = await store.get_token_info(COIN_NAME)
        MinTx = token_info['real_min_tip']
        MaxTX = token_info['real_max_tip']
    else:
        real_amount = int(Decimal(amount) * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
        MinTx = get_min_mv_amount(COIN_NAME)
        MaxTX = get_max_mv_amount(COIN_NAME)

    user_from = await store.sql_get_userwallet(id_tipper, COIN_NAME)
    if user_from is None:
        if coin_family == "ERC-20":
            w = await create_address_eth()
            user_from = await store.sql_register_user(id_tipper, COIN_NAME, 'DISCORD', 0, w)
        else:
            user_from = await store.sql_register_user(id_tipper, COIN_NAME, 'DISCORD', 0)

    userdata_balance = await store.sql_user_balance(id_tipper, COIN_NAME)
    xfer_in = 0
    if COIN_NAME not in ENABLE_COIN_ERC:
        xfer_in = await store.sql_user_balance_get_xfer_in(id_tipper, COIN_NAME)
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
            msg_negative = 'Negative balance detected:\nUser: '+id_tipper+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
            await logchanbot(msg_negative)
    except Exception as e:
        await logchanbot(traceback.format_exc())

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

    listMembers = []

    guild_members = ctx.guild.members
    if ctx.message.role_mentions and len(ctx.message.role_mentions) >= 1:
        mention_roles = ctx.message.role_mentions
        if "@everyone" in mention_roles:
            mention_roles.remove("@everyone")
        if len(mention_roles) >= 1:
            for each_role in mention_roles:
                role_listMember = [member for member in guild_members if member.bot == False and each_role in member.roles]
                if len(role_listMember) >= 1:
                    for each_member in role_listMember:
                        if each_member not in listMembers:
                            listMembers.append(each_member)
    else:
        listMembers = ctx.message.mentions
    list_receivers = []

    for member in listMembers:
        # print(member.name) # you'll just print out Member objects your way.
        if ctx.message.author.id != member.id and member in guild_members:
            user_to = await store.sql_get_userwallet(str(member.id), COIN_NAME)
            if user_to is None:
                if coin_family == "ERC-20":
                    w = await create_address_eth()
                    userregister = await store.sql_register_user(str(member.id), COIN_NAME, 'DISCORD', 0, w)
                else:
                    userregister = await store.sql_register_user(str(member.id), COIN_NAME, 'DISCORD', 0)
                user_to = await store.sql_get_userwallet(str(member.id), COIN_NAME)
            list_receivers.append(str(member.id))

    TotalAmount = real_amount * len(list_receivers)
    print('_tip TotalAmount: {}'.format(TotalAmount))
    if TotalAmount > MaxTX:
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
    elif TotalAmount > actual_balance:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send total {tip_type_text} of '
                       f'{num_format_coin(TotalAmount, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return

    # add queue also tip
    if int(id_tipper) not in TX_IN_PROCESS:
        TX_IN_PROCESS.append(int(id_tipper))
    else:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    tip = None
    if len(list_receivers) < 1:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is no one to {tip_type_text} to.')
        return
    try:
        if coin_family in ["TRTL", "BCN"]:
            tip = await store.sql_mv_cn_multiple(id_tipper, real_amount, list_receivers, guild_or_tip, COIN_NAME)
        elif coin_family == "XMR":
            tip = await store.sql_mv_xmr_multiple(id_tipper, list_receivers, real_amount, COIN_NAME, guild_or_tip)
        elif coin_family == "NANO":
            tip = await store.sql_mv_nano_multiple(id_tipper, list_receivers, real_amount, COIN_NAME, guild_or_tip)
        elif coin_family == "DOGE":
            tip = await store.sql_mv_doge_multiple(id_tipper, list_receivers, real_amount, COIN_NAME, guild_or_tip)
        elif coin_family == "ERC-20":
            tip = await store.sql_mv_erc_multiple(id_tipper, list_receivers, real_amount, COIN_NAME, "TIPS", token_info['contract'])
        if ctx.message.author.bot == False and serverinfo['react_tip'] == "ON":
            try:
                await ctx.message.add_reaction(EMOJI_TIP)
            except Exception as e:
                pass
    except Exception as e:
        await logchanbot(traceback.format_exc())

    # remove queue from tip
    if int(id_tipper) in TX_IN_PROCESS:
        TX_IN_PROCESS.remove(int(id_tipper))

    if tip:
        try:
            for member in listMembers:
                if ctx.message.author.id != member.id and bot.user.id != member.id and str(member.id) not in notifyList:
                    try:
                        await member.send(f'{EMOJI_MONEYFACE} You got a {tip_type_text} of  {num_format_coin(real_amount, COIN_NAME)} '
                                          f'{COIN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{ctx.guild.name} #{ctx.channel.name}`\n'
                                          f'{NOTIFICATION_OFF_CMD}\n{tipmsg}')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        await logchanbot(traceback.format_exc())
                        await store.sql_toggle_tipnotify(str(member.id), "OFF")
        except Exception as e:
            await logchanbot(traceback.format_exc())
        await ctx.message.add_reaction(get_emoji(COIN_NAME))
        # tipper shall always get DM. Ignore notifyList
        try:
            if if_guild == True:
                await ctx.send(f'{EMOJI_ARROW_RIGHTHOOK} Total {tip_type_text} of {num_format_coin(TotalAmount, COIN_NAME)} '
                               f'{COIN_NAME} '
                               f'was sent to ({len(list_receivers)}) members in server `{ctx.guild.name}`.\n'
                               f'Each: `{num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`'
                               f'Total spending: `{num_format_coin(TotalAmount, COIN_NAME)} {COIN_NAME}`')
            else:
                await ctx.message.author.send(f'{EMOJI_ARROW_RIGHTHOOK} Total {tip_type_text} of {num_format_coin(TotalAmount, COIN_NAME)} '
                                        f'{COIN_NAME} '
                                        f'was sent to ({len(list_receivers)}) members in server `{ctx.guild.name}`.\n'
                                        f'Each: `{num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`'
                                        f'Total spending: `{num_format_coin(TotalAmount, COIN_NAME)} {COIN_NAME}`')
        except (discord.Forbidden, discord.errors.Forbidden) as e:
            try:
                if if_guild == True:
                    await ctx.message.author.send(f'{EMOJI_ARROW_RIGHTHOOK} Total {tip_type_text} of {num_format_coin(TotalAmount, COIN_NAME)} '
                                            f'{COIN_NAME} '
                                            f'was sent to ({len(list_receivers)}) members in server `{ctx.guild.name}`.\n'
                                            f'Each: `{num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`'
                                            f'Total spending: `{num_format_coin(TotalAmount, COIN_NAME)} {COIN_NAME}`')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await logchanbot(traceback.format_exc())
            await logchanbot(traceback.format_exc())
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Tipping failed, try again.')
        await botLogChan.send(f'A user failed to _tip `{num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`.')
        await msg.add_reaction(EMOJI_OK_BOX)
        # add to failed tx table
        await store.sql_add_failed_tx(COIN_NAME, str(ctx.message.author.id), ctx.message.author.name, real_amount, guild_or_tip)
        return


# Multiple tip
async def _tip_talker(ctx, amount, list_talker, if_guild: bool=False, coin: str = None):
    global TX_IN_PROCESS
    guild_or_tip = 'GUILDTIP' if if_guild == True else 'TIPS'
    guild_name = '**{}**'.format(ctx.guild.name) if if_guild == True else ''
    tip_type_text = 'guild tip' if if_guild == True else 'tip'
    id_tipper = str(ctx.guild.id) if if_guild == True else str(ctx.message.author.id)

    botLogChan = bot.get_channel(id=LOG_CHAN)
    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    tipmsg = ""
    if if_guild:
        try:
            if serverinfo['tip_message']: tipmsg = "**Guild Message:**\n" + serverinfo['tip_message']
        except Exception as e:
            pass
    COIN_NAME = coin.upper()
    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    try:
        amount = Decimal(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    notifyList = await store.sql_get_tipnotify()
    if coin_family not in ["BCN", "TRTL", "DOGE", "XMR", "NANO", "ERC-20"]:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} is restricted with this command.')
        return

    if coin_family == "ERC-20":
        real_amount = float(amount)
        token_info = await store.get_token_info(COIN_NAME)
        MinTx = token_info['real_min_tip']
        MaxTX = token_info['real_max_tip']
    else:
        real_amount = int(amount * get_decimal(COIN_NAME)) if coin_family in ["XMR", "TRTL", "BCN", "NANO"] else float(amount)
        MinTx = get_min_mv_amount(COIN_NAME)
        MaxTX = get_max_mv_amount(COIN_NAME)

    user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    if user_from is None:
        if coin_family == "ERC-20":
            w = await create_address_eth()
            user_from = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0, w)
        else:
            user_from = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD', 0)

    userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), COIN_NAME)
    xfer_in = 0
    if COIN_NAME not in ENABLE_COIN_ERC:
        xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.message.author.id), COIN_NAME)
    if COIN_NAME in ENABLE_COIN_DOGE+ENABLE_COIN_ERC:
        actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
    elif COIN_NAME in ENABLE_COIN_NANO:
        actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
        actual_balance = round(actual_balance / get_decimal(COIN_NAME), 6) * get_decimal(COIN_NAME)
    else:
        actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])

    # Negative check
    try:
        if actual_balance< 0:
            msg_negative = 'Negative balance detected:\nUser: '+str(ctx.message.author.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
            await logchanbot(msg_negative)
    except Exception as e:
        await logchanbot(traceback.format_exc())

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
    elif real_amount > actual_balance:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send {tip_type_text} of '
                       f'{num_format_coin(real_amount, COIN_NAME)} '
                        f'{COIN_NAME}.')
        return

    list_receivers = []
    addresses = []
    guild_members = ctx.guild.members
    for member_id in list_talker:
        try:
            member = bot.get_user(id=int(member_id))
            if member and member in guild_members and ctx.message.author.id != member.id:
                user_to = await store.sql_get_userwallet(str(member_id), COIN_NAME)
                if user_to is None:
                    if coin_family == "ERC-20":
                        w = await create_address_eth()
                        userregister = await store.sql_register_user(str(member_id), COIN_NAME, 'DISCORD', 0, w)
                    else:
                        userregister = await store.sql_register_user(str(member_id), COIN_NAME, 'DISCORD', 0)
                    user_to = await store.sql_get_userwallet(str(member_id), COIN_NAME)
                try:
                    list_receivers.append(str(member_id))
                except Exception as e:
                    await logchanbot(traceback.format_exc())
                    print('Failed creating wallet for tip talk for userid: {}'.format(member_id))
        except Exception as e:
            await logchanbot(traceback.format_exc())

    # Check number of receivers.
    if len(list_receivers) > config.tipallMax:
        await ctx.message.add_reaction(EMOJI_ERROR)
        try:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} The number of receivers are too many.')
        except (discord.Forbidden, discord.errors.Forbidden) as e:
            await ctx.message.author.send(f'{EMOJI_RED_NO} The number of receivers are too many in `{ctx.guild.name}`.')
        return
    # End of checking receivers numbers.

    TotalAmount = real_amount * len(list_receivers)

    if TotalAmount > MaxTX:
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
    elif TotalAmount > actual_balance:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {guild_name} Insufficient balance to send total {tip_type_text} of '
                       f'{num_format_coin(TotalAmount, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return

    if len(list_receivers) < 1:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is no active talker in such period. Please increase more duration or tip directly!')
        return

    # add queue also tip
    if int(id_tipper) not in TX_IN_PROCESS:
        TX_IN_PROCESS.append(int(id_tipper))
    else:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    tip = None
    try:
        if coin_family in ["TRTL", "BCN"]:
            tip = await store.sql_mv_cn_multiple(id_tipper, real_amount, list_receivers, guild_or_tip, COIN_NAME)
        elif coin_family == "XMR":
            tip = await store.sql_mv_xmr_multiple(id_tipper, list_receivers, real_amount, COIN_NAME, guild_or_tip)
        elif coin_family == "NANO":
            tip = await store.sql_mv_nano_multiple(id_tipper, list_receivers, real_amount, COIN_NAME, guild_or_tip)
        elif coin_family == "DOGE":
            tip = await store.sql_mv_doge_multiple(id_tipper, list_receivers, real_amount, COIN_NAME, guild_or_tip)
        elif coin_family == "ERC-20":
            tip = await store.sql_mv_erc_multiple(id_tipper, list_receivers, real_amount, COIN_NAME, "TIPS", token_info['contract'])
    except Exception as e:
        await logchanbot(traceback.format_exc())

    # remove queue from tip
    if int(id_tipper) in TX_IN_PROCESS:
        TX_IN_PROCESS.remove(int(id_tipper))

    if tip:
        # tipper shall always get DM. Ignore notifyList
        try:
            await ctx.message.author.send(
                f'{EMOJI_ARROW_RIGHTHOOK} {tip_type_text} of {num_format_coin(TotalAmount, COIN_NAME)} '
                f'{COIN_NAME} '
                f'was sent to ({len(list_receivers)}) members in server `{ctx.guild.name}` for active talking.\n'
                f'Each member got: `{num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}`\n')
        except (discord.Forbidden, discord.errors.Forbidden) as e:
            await store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
        mention_list_name = ''
        guild_members = ctx.guild.members
        for member_id in list_talker:
            # print(member.name) # you'll just print out Member objects your way.
            if ctx.message.author.id != int(member_id):
                member = bot.get_user(id=int(member_id))
                if member and member.bot == False and member in guild_members:
                    mention_list_name += '{}#{} '.format(member.name, member.discriminator)
                    if str(member_id) not in notifyList:
                        try:
                            await member.send(
                                f'{EMOJI_MONEYFACE} You got a {tip_type_text} of `{num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}` '
                                f'from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{ctx.guild.name}` #{ctx.channel.name} for active talking.\n'
                                f'{NOTIFICATION_OFF_CMD}\n{tipmsg}')
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            await store.sql_toggle_tipnotify(str(member.id), "OFF")
        await ctx.message.add_reaction(get_emoji(COIN_NAME))
        try:
            await ctx.send(f'{discord.utils.escape_markdown(mention_list_name)}\n\n**({len(list_receivers)})** members got {tip_type_text} :) for active talking in `{ctx.guild.name}` {ctx.channel.mention} :)')
            await ctx.message.add_reaction(EMOJI_SPEAK)
        except discord.errors.Forbidden:
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if serverinfo and 'botchan' in serverinfo and serverinfo['botchan']:
                bot_channel = bot.get_channel(id=int(serverinfo['botchan']))
                try:
                    msg = await bot_channel.send(f'{discord.utils.escape_markdown(mention_list_name)}\n\n**({len(list_receivers)})** members got {tip_type_text} :) for active talking in `{ctx.guild.name}` {ctx.channel.mention} :)')
                    await msg.add_reaction(EMOJI_OK_BOX)
                    await ctx.message.add_reaction(EMOJI_SPEAK)
                except Exception as e:
                    await logchanbot(traceback.format_exc())
                    await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                except discord.errors.HTTPException:
                    msg = await bot_channel.send(f'**({len(list_receivers)})** members got {tip_type_text} :) for active talking in `{ctx.guild.name}` {ctx.channel.mention} :)')
                    await msg.add_reaction(EMOJI_OK_BOX)
                    await ctx.message.add_reaction(EMOJI_SPEAK)
            else:
                await ctx.message.add_reaction(EMOJI_SPEAK)
                await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
        except discord.errors.HTTPException:
            await ctx.message.add_reaction(EMOJI_SPEAK)
            await ctx.send(f'**({len(list_receivers)})** members got {tip_type_text} :) for active talking in `{ctx.guild.name}` {ctx.channel.mention} :)')
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        return


# Multiple tip_react
async def _tip_react(reaction, user, amount, coin: str):
    global REACT_TIP_STORE
    botLogChan = bot.get_channel(id=LOG_CHAN)
    serverinfo = await store.sql_info_by_server(str(reaction.message.guild.id))
    COIN_NAME = coin.upper()

    # If only one user and he re-act
    if len(reaction.message.mentions) == 1 and user in (reaction.message.mentions):
        return
        
    notifyList = await store.sql_get_tipnotify()
    if COIN_NAME in ENABLE_COIN_ERC:
        coin_family = "ERC-20"
    else:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    if COIN_NAME in ENABLE_COIN_ERC:
        token_info = await store.get_token_info(COIN_NAME)
        real_amount = float(amount)
        MinTx = token_info['real_min_tip']
        MaxTX = token_info['real_max_tip']
    else:
        real_amount = int(Decimal(amount) * get_decimal(COIN_NAME)) if coin_family in ["BCN", "XMR", "TRTL", "NANO"] else float(amount)
        MinTx = get_min_mv_amount(COIN_NAME)
        MaxTX = get_max_mv_amount(COIN_NAME)

    user_from = await store.sql_get_userwallet(str(user.id), COIN_NAME)
    if user_from is None:
        if COIN_NAME in ENABLE_COIN_ERC:
            w = await create_address_eth()
            user_from = await store.sql_register_user(str(user.id), COIN_NAME, 'DISCORD', 0, w)
        else:
            user_from = await store.sql_register_user(str(user.id), COIN_NAME, 'DISCORD', 0)

    # get user balance
    userdata_balance = await store.sql_user_balance(str(user.id), COIN_NAME)
    xfer_in = 0
    if COIN_NAME not in ENABLE_COIN_ERC:
        xfer_in = await store.sql_user_balance_get_xfer_in(str(user.id), COIN_NAME)
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
            msg_negative = 'Negative balance detected:\nUser: '+str(user.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
            await logchanbot(msg_negative)
    except Exception as e:
        await logchanbot(traceback.format_exc())

    listMembers = reaction.message.mentions
    list_receivers = []
    addresses = []

    for member in listMembers:
        # print(member.name) # you'll just print out Member objects your way.
        if user.id != member.id and reaction.message.author.id != member.id:
            user_to = await store.sql_get_userwallet(str(member.id), COIN_NAME)
            if user_to is None:
                userregister = await store.sql_register_user(str(member.id), COIN_NAME, 'DISCORD', 0)
                user_to = await store.sql_get_userwallet(str(member.id), COIN_NAME)

            list_receivers.append(str(member.id))

    TotalAmount = real_amount * len(list_receivers)
    if TotalAmount >= actual_balance:
        try:
            await user.send(f'{EMOJI_RED_NO} {user.mention} Insufficient balance {EMOJI_TIP} total of '
                            f'{num_format_coin(TotalAmount, COIN_NAME)} '
                            f'{COIN_NAME}.')
        except (discord.Forbidden, discord.errors.Forbidden) as e:
            print(f"_tip_react Can not send DM to {user.id}")
        return

    tip = None
    if len(list_receivers) < 1:
        await reaction.message.add_reaction(EMOJI_ERROR)
        return
    try:
        if coin_family in ["TRTL", "BCN"]:
            tip = await store.sql_mv_cn_multiple(str(user.id), real_amount, list_receivers, 'TIPS', COIN_NAME)
        elif coin_family == "XMR":
            tip = await store.sql_mv_xmr_multiple(str(user.id), list_receivers, real_amount, COIN_NAME, "TIPS")
        elif coin_family == "NANO":
            tip = await store.sql_mv_nano_multiple(str(user.id), list_receivers, real_amount, COIN_NAME, "TIPS")
        elif coin_family == "DOGE":
            tip = await store.sql_mv_doge_multiple(user.id, list_receivers, real_amount, COIN_NAME, "TIPS")
        REACT_TIP_STORE.append((str(reaction.message.id) + '.' + str(user.id)))
    except Exception as e:
        await logchanbot(traceback.format_exc())
    if tip:
        # tipper shall always get DM. Ignore notifyList
        try:
            await user.send(f'{EMOJI_ARROW_RIGHTHOOK} Total {EMOJI_TIP} of {num_format_coin(TotalAmount, COIN_NAME)} '
                            f'{COIN_NAME} '
                            f'was sent to ({len(list_receivers)}) members in server `{reaction.message.guild.name}`.\n'
                            f'Each: `{num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`'
                            f'Total spending: `{num_format_coin(TotalAmount, COIN_NAME)} {COIN_NAME}`')
        except (discord.Forbidden, discord.errors.Forbidden) as e:
            await store.sql_toggle_tipnotify(str(user.id), "OFF")
        for member in reaction.message.mentions:
            if user.id != member.id and reaction.message.author.id != member.id and member.bot == False:
                if str(member.id) not in notifyList:
                    try:
                        await member.send(f'{EMOJI_MONEYFACE} You got a {EMOJI_TIP} of  {num_format_coin(real_amount, COIN_NAME)} '
                                          f'{COIN_NAME} from {user.name}#{user.discriminator} in server `{reaction.message.guild.name}`\n'
                                          f'{NOTIFICATION_OFF_CMD}')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        await store.sql_toggle_tipnotify(str(member.id), "OFF")
        return
    else:
        msg = await user.send(f'{EMOJI_RED_NO} {user.mention} Try again for {EMOJI_TIP}.')
        await botLogChan.send(f'A user failed to _tip_react `{num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`.')
        await msg.add_reaction(EMOJI_OK_BOX)
        # add to failed tx table
        await store.sql_add_failed_tx(COIN_NAME, str(user.id), user.name, real_amount, "REACTTIP")
        return


def truncate(number, digits) -> float:
    stepper = pow(10.0, digits)
    return math.trunc(stepper * number) / stepper


def seconds_str(time: float):
    # day = time // (24 * 3600)
    # time = time % (24 * 3600)
    hour = time // 3600
    time %= 3600
    minutes = time // 60
    time %= 60
    seconds = time
    return "{:02d}:{:02d}:{:02d}".format(hour, minutes, seconds)


def is_maintenance_coin(coin: str):
    global redis_conn, redis_expired, MAINTENANCE_COIN
    COIN_NAME = coin.upper()
    if COIN_NAME in MAINTENANCE_COIN:
        return True
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


def set_maintenance_coin(coin: str, set_maint: bool = True):
    global redis_conn, redis_expired, MAINTENANCE_COIN
    COIN_NAME = coin.upper()
    if COIN_NAME in MAINTENANCE_COIN:
        return True

    # Check if exist in redis
    try:
        openRedis()
        key = 'TIPBOT:COIN_' + COIN_NAME + '_MAINT'
        if set_maint == True:
            if redis_conn and redis_conn.exists(key):
                return True
            else:
                redis_conn.set(key, "ON")
                return True
        else:
            if redis_conn and redis_conn.exists(key):
                redis_conn.delete(key)
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def is_coin_txable(coin: str):
    global redis_conn, redis_expired, MAINTENANCE_COIN
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


def set_coin_txable(coin: str, set_txable: bool = True):
    global redis_conn, redis_expired, MAINTENANCE_COIN
    COIN_NAME = coin.upper()
    if COIN_NAME in MAINTENANCE_COIN:
        return False

    # Check if exist in redis
    try:
        openRedis()
        key = 'TIPBOT:COIN_' + COIN_NAME + '_TX'
        if set_txable == True:
            if redis_conn and redis_conn.exists(key):
                redis_conn.delete(key)
                return True
        else:
            if redis_conn and not redis_conn.exists(key):
                redis_conn.set(key, "ON")                
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


def set_coin_depositable(coin: str, set_deposit: bool = True):
    global redis_conn, redis_expired
    COIN_NAME = coin.upper()
    if is_maintenance_coin(COIN_NAME):
        return False

    # Check if exist in redis
    try:
        openRedis()
        key = 'TIPBOT:COIN_' + COIN_NAME + '_DEPOSIT'
        if set_deposit == True:
            if redis_conn and redis_conn.exists(key):
                redis_conn.delete(key)
                return True
        else:
            if redis_conn and not redis_conn.exists(key):
                redis_conn.set(key, "ON")                
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


def set_coin_tipable(coin: str, set_tipable: bool = True):
    global redis_conn, redis_expired
    COIN_NAME = coin.upper()
    if is_maintenance_coin(COIN_NAME):
        return False

    # Check if exist in redis
    try:
        openRedis()
        key = 'TIPBOT:COIN_' + COIN_NAME + '_TIP'
        if set_tipable == True:
            if redis_conn and redis_conn.exists(key):
                redis_conn.delete(key)
                return True
        else:
            if redis_conn and not redis_conn.exists(key):
                redis_conn.set(key, "ON")                
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def is_tradeable_coin(coin: str):
    global redis_conn, redis_expired
    COIN_NAME = coin.upper()

    # Check if exist in redis
    try:
        openRedis()
        key = 'TIPBOT:COIN_' + COIN_NAME + '_TRADEABLE'
        if redis_conn and redis_conn.exists(key):
            return True
        else:
            return False
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def set_tradeable_coin(coin: str, set_trade: bool = True):
    global redis_conn, redis_expired 
    COIN_NAME = coin.upper()

    # Check if exist in redis
    try:
        openRedis()
        key = 'TIPBOT:COIN_' + COIN_NAME + '_TRADEABLE'
        if set_trade == True:
            if redis_conn and redis_conn.exists(key):
                return True
            else:
                redis_conn.set(key, "ON")
                return True
        else:
            if redis_conn and redis_conn.exists(key):
                redis_conn.delete(key)
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def bot_faucet(ctx):
    global TRTL_DISCORD
    get_game_stat = await store.sql_game_stat()
    table_data = [
        ['TICKER', 'Available', 'Claimed / Game']
    ]
    for COIN_NAME in [coinItem.upper() for coinItem in FAUCET_COINS]:
        sum_sub = 0
        wallet = await store.sql_get_userwallet(str(bot.user.id), COIN_NAME)
        if wallet is None:
            wallet = await store.sql_register_user(str(bot.user.id), COIN_NAME, 'DISCORD', 0)
        userdata_balance = await store.sql_user_balance(str(bot.user.id), COIN_NAME)
        xfer_in = 0
        if COIN_NAME not in ENABLE_COIN_ERC:
            xfer_in = await store.sql_user_balance_get_xfer_in(str(bot.user.id), COIN_NAME)
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


async def store_action_list():
    while True:
        interval_action_list = 60
        try:
            openRedis()
            key = "TIPBOT:ACTIONTX"
            if redis_conn and redis_conn.llen(key) > 0:
                temp_action_list = []
                for each in redis_conn.lrange(key, 0, -1):
                    temp_action_list.append(tuple(json.loads(each)))
                num_add = await store.sql_add_logs_tx(temp_action_list)
                if num_add > 0:
                    redis_conn.delete(key)
                else:
                    print(f"Failed delete {key}")
        except Exception as e:
            await logchanbot(traceback.format_exc())
        await asyncio.sleep(interval_action_list)


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
        await logchanbot(traceback.format_exc())


async def get_guild_prefix(ctx):
    if isinstance(ctx.channel, discord.DMChannel) == True: return "."
    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    if serverinfo is None:
        return "."
    else:
        return serverinfo['prefix']


async def get_guild_prefix_msg(message):
    if isinstance(message.channel, discord.DMChannel) == True: return "."
    serverinfo = await store.sql_info_by_server(str(message.guild.id))
    if serverinfo is None:
        return "."
    else:
        return serverinfo['prefix']


async def add_msg_redis(msg: str, delete_temp: bool = False):
    try:
        openRedis()
        key = "TIPBOT:MSG"
        if redis_conn:
            if delete_temp:
                redis_conn.delete(key)
            else:
                redis_conn.lpush(key, msg)
    except Exception as e:
        await logchanbot(traceback.format_exc())


async def store_message_list():
    while True:
        interval_msg_list = 15 # in second
        try:
            openRedis()
            key = "TIPBOT:MSG"
            if redis_conn and redis_conn.llen(key) > 0 :
                temp_msg_list = []
                for each in redis_conn.lrange(key, 0, -1):
                    temp_msg_list.append(tuple(json.loads(each)))
                try:
                    num_add = await store.sql_add_messages(temp_msg_list)
                except Exception as e:
                    await logchanbot(traceback.format_exc())
                if num_add and num_add > 0:
                    redis_conn.delete(key)
                else:
                    redis_conn.delete(key)
                    print(f"Failed delete {key}")
        except Exception as e:
            await logchanbot(traceback.format_exc())
        await asyncio.sleep(interval_msg_list)


async def get_miningpool_coinlist():
    global redis_conn, redis_expired
    while True:
        interval_msg_list = 1800 # in second
        try:
            openRedis()
            try:
                async with aiohttp.ClientSession() as cs:
                    async with cs.get(config.miningpoolstat.coinlist_link, timeout=config.miningpoolstat.timeout) as r:
                        if r.status == 200:
                            res_data = await r.read()
                            res_data = res_data.decode('utf-8')
                            res_data = res_data.replace("var coin_list = ", "").replace(";", "")
                            decoded_data = json.loads(res_data)
                            await cs.close()
                            key = "TIPBOT:MININGPOOL:"
                            key_hint = "TIPBOT:MININGPOOL:SHORTNAME:"
                            if decoded_data and len(decoded_data) > 0:
                                # print(decoded_data)
                                for kc, cat in decoded_data.items():
                                    if not isinstance(cat, int) and not isinstance(cat, str):
                                        for k, v in cat.items():
                                            # Should have no expire.
                                            redis_conn.set((key+k).upper(), json.dumps(v))
                                            redis_conn.set((key_hint+v['s']).upper(), k.upper())
            except asyncio.TimeoutError:
                print('TIMEOUT: Fetching from miningpoolstats')
            except Exception:
                await logchanbot(traceback.format_exc())
        except Exception as e:
            await logchanbot(traceback.format_exc())
        await asyncio.sleep(interval_msg_list)


async def get_miningpoolstat_coin(coin: str):
    global redis_conn, redis_expired
    COIN_NAME = coin.upper()
    key = "TIPBOT:MININGPOOLDATA:" + COIN_NAME
    if redis_conn and redis_conn.exists(key):
        return json.loads(redis_conn.get(key).decode())
    else:
        try:
            openRedis()
            try:
                link = config.miningpoolstat.coinapi.replace("COIN_NAME", coin.lower())
                print(f"Fetching {link}")
                async with aiohttp.ClientSession() as cs:
                    async with cs.get(link, timeout=config.miningpoolstat.timeout) as r:
                        if r.status == 200:
                            res_data = await r.read()
                            res_data = res_data.decode('utf-8')
                            decoded_data = json.loads(res_data)
                            await cs.close()
                            if decoded_data and len(decoded_data) > 0 and 'data' in decoded_data:
                                redis_conn.set(key, json.dumps(decoded_data), ex=config.miningpoolstat.expired)
                                return decoded_data
                            else:
                                print(f'MININGPOOLSTAT: Error {link} Fetching from miningpoolstats')
                                return None
            except asyncio.TimeoutError:
                print(f'TIMEOUT: Fetching from miningpoolstats {COIN_NAME}')
            except Exception:
                await logchanbot(traceback.format_exc())
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return None


# function to return if input string is ascii
def is_ascii(s):
    return all(ord(c) < 128 for c in s)


# https://en.wikipedia.org/wiki/Primality_test
def is_prime(n: int) -> bool:
    """Primality test using 6k+-1 optimization."""
    if n <= 3:
        return n > 1
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i ** 2 <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


# json.dumps for turple
def remap_keys(mapping):
    return [{'key':k, 'value': v} for k, v in mapping.items()]


def get_roach_level(takes: int):
    if takes > 2000:
        return "Great Ultimate Master"
    elif takes > 1500:
        return "Great Supreme Master"
    elif takes > 1000:
        return "Great Grand Master"
    elif takes > 750:
        return "Great Master"
    elif takes > 500:
        return "Ultimate Master"
    elif takes > 250:
        return "Grand Master"
    elif takes > 100:
        return "Master"
    elif takes > 50:
        return "Specialist"
    elif takes > 25:
        return "Licensed"
    elif takes > 10:
        return "Learning"
    elif takes > 0:
        return "Baby"
    else:
        return None


@click.command()
def main():
    bot.loop.create_task(saving_wallet())
    bot.loop.create_task(update_user_guild())
    bot.loop.create_task(update_balance())
    bot.loop.create_task(update_block_height())
    bot.loop.create_task(notify_new_tx_user())
    bot.loop.create_task(notify_new_tx_user_noconfirmation())
    bot.loop.create_task(store_action_list())
    bot.loop.create_task(store_message_list())
    bot.loop.create_task(get_miningpool_coinlist())
    
    bot.loop.create_task(update_balance_erc())
    bot.loop.create_task(unlocked_move_pending_erc())
    bot.loop.create_task(erc_notify_new_confirmed_spendable())

    bot.run(config.discord.token, reconnect=True)


if __name__ == '__main__':
    main()
