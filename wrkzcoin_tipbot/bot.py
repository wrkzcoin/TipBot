import click

import discord
from discord.ext import commands
from discord.ext.commands import Bot, AutoShardedBot, when_mentioned_or, CheckFailure

from discord.utils import get

import time, timeago, json
import pyotp

import store, daemonrpc_client, addressvalidation, walletapi
from masari.address import address as address_msr
from monero.address import address as address_xmr

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

# add logging
# CRITICAL, ERROR, WARNING, INFO, and DEBUG and if not specified defaults to WARNING.
import logging
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
BOT_INVITELINK = None
WALLET_SERVICE = None
LIST_IGNORECHAN = None

MESSAGE_HISTORY_MAX = 20 # message history to store
MESSAGE_HISTORY_TIME = 60 # duration max to put to DB
MESSAGE_HISTORY_LIST = []
MESSAGE_HISTORY_LAST = 0

# param introduce by @bobbieltd
WITHDRAW_IN_PROCESS = []

# tip-react temp storage
REACT_TIP_STORE = []

# faucet enabled coin. The faucet balance is taken from TipBot's own balance
FAUCET_COINS = ["WRKZ", "TRTL", "DEGO", "MTIP", "BTCMZ"]

# Coin using wallet-api
WALLET_API_COIN = config.Enable_Coin_WalletApi.split(",")

# DOGE will divide by 10 after random
FAUCET_MINMAX = {
    "WRKZ": [1000, 2500],
    "DEGO": [2500, 10000],
    "MTIP": [5, 15],
    "TRTL": [3, 10],
    "DOGE": [1, 3],
    "BTCMZ": [2500, 5000]
    }


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

EMOJI_COIN = {
    "WRKZ" : "\U0001F477",
    "TRTL" : "\U0001F422",
    "DEGO" : "\U0001F49B",
    "CX" : "\U0001F64F",
    "OSL" : "\U0001F381",
    "BTCMZ" : "\U0001F4A9",
    "MTIP" : "\U0001F595",
    "XCY" : "\U0001F3B2",
    "PLE" : "\U0001F388",
    "ELPH" : "\U0001F310",
    "ANX" : "\U0001F3E6",
    "NBXC" : "\U0001F5A4",
    "ARMS" : "\U0001F52B",
    "IRD" : "\U0001F538",
    "HITC" : "\U0001F691",
    "NACA" : "\U0001F355",
    "DOGE" : "\U0001F436",
    "XTOR" : "\U0001F315",
    "LOKI" : "\u2600",
    "XMR" : "\u2694",
    "XEQ" : "\U0001F30C",
    "ARQ" : "\U0001F578",
    "MSR" : "\U0001F334",
    "BLOG" : "\u270D"
    }

EMOJI_RED_NO = "\u26D4"
EMOJI_SPEAK = "\U0001F4AC"
EMOJI_ARROW_RIGHTHOOK = "\u21AA"
EMOJI_FORWARD = "\u23E9"
EMOJI_REFRESH = "\U0001F504"
EMOJI_ZIPPED_MOUTH = "\U0001F910"
EMOJI_LOCKED = "\U0001F512"

ENABLE_COIN = config.Enable_Coin.split(",")
ENABLE_COIN_DOGE = ["DOGE"]
ENABLE_XMR = config.Enable_Coin_XMR.split(",")
MAINTENANCE_COIN = config.Maintenance_Coin.split(",")

COIN_REPR = "COIN"
DEFAULT_TICKER = "WRKZ"
ENABLE_COIN_VOUCHER = config.Enable_Coin_Voucher.split(",")

# Some notice about coin that going to swap or take out.
NOTICE_COIN = {
    "WRKZ" : f"{EMOJI_INFORMATION} WRKZ new network fee 500.00WRKZ.",
    "TRTL" : getattr(getattr(config,"daemonTRTL"),"coin_notice", None),
    "DEGO" : getattr(getattr(config,"daemonDEGO"),"coin_notice", None),
    "CX" : getattr(getattr(config,"daemonCX"),"coin_notice", None),
    "BTCMZ" : getattr(getattr(config,"daemonBTCMZ"),"coin_notice", None),
    "MTIP" : getattr(getattr(config,"daemonMTIP"),"coin_notice", None),
    "XCY" : getattr(getattr(config,"daemonXCY"),"coin_notice", None),
    "PLE" : getattr(getattr(config,"daemonPLE"),"coin_notice", None),
    "ELPH" : getattr(getattr(config,"daemonELPH"),"coin_notice", None),
    "ANX" : getattr(getattr(config,"daemonANX"),"coin_notice", None),
    "NBXC" : getattr(getattr(config,"daemonNBXC"),"coin_notice", None),
    "ARMS" : getattr(getattr(config,"daemonARMS"),"coin_notice", None),
    "IRD" : getattr(getattr(config,"daemonIRD"),"coin_notice", None),
    "HITC" : getattr(getattr(config,"daemonHITC"),"coin_notice", None),
    "NACA" : getattr(getattr(config,"daemonNACA"),"coin_notice", None),
    "XTOR" : getattr(getattr(config,"daemonXTOR"),"coin_notice", None),
    "LOKI" : getattr(getattr(config,"daemonLOKI"),"coin_notice", None),
    "XEQ" : getattr(getattr(config,"daemonXEQ"),"coin_notice", None),
    "ARQ" : getattr(getattr(config,"daemonARQ"),"coin_notice", None),
    "XMR" : getattr(getattr(config,"daemonXMR"),"coin_notice", None),
    "MSR" : getattr(getattr(config,"daemonMSR"),"coin_notice", None),
    "BLOG" : getattr(getattr(config,"daemonBLOG"),"coin_notice", None),
    "DOGE" : "Please acknowledge that DOGE address is for **one-time** use only for depositing.",
    "default": "Thank you for using."
    }

# TRTL discord. Need for some specific tasks later.
TRTL_DISCORD = 388915017187328002

NOTIFICATION_OFF_CMD = 'Type: `.notifytip off` to turn off this DM notification.'
MSG_LOCKED_ACCOUNT = "Your account is locked. Please contact CapEtn#4425 in WrkzCoin discord. Check `.about` for more info."

bot_description = f"Tip {COIN_REPR} to other users on your server."
bot_help_about = "About TipBot"
bot_help_register = "Register or change your deposit address."
bot_help_info = "Get your account's info."
bot_help_withdraw = f"Withdraw {COIN_REPR} from your balance."
bot_help_balance = f"Check your {COIN_REPR} balance."
bot_help_botbalance = f"Check (only) bot {COIN_REPR} balance."
bot_help_donate = f"Donate {COIN_REPR} to a Bot Owner."
bot_help_tip = f"Give {COIN_REPR} to a user from your balance."
bot_help_forwardtip = f"Forward all your received tip of {COIN_REPR} to registered wallet."
bot_help_tipall = f"Spread a tip amount of {COIN_REPR} to all online members."
bot_help_send = f"Send {COIN_REPR} to a {COIN_REPR} address from your balance (supported integrated address)."
bot_help_optimize = f"Optimize your tip balance of {COIN_REPR} for large tip, send, tipall, withdraw"
bot_help_address = f"Check {COIN_REPR} address | Generate {COIN_REPR} integrated address."
bot_help_paymentid = "Make a random payment ID with 64 chars length."
bot_help_address_qr = "Show an input address in QR code image."
bot_help_payment_qr = f"Make QR code image for {COIN_REPR} payment."
bot_help_tag = "Display a description or a link about what it is. (-add|-del) requires permission manage_channels"
bot_help_itag = "Upload image (gif|png|jpeg) and add tag."
bot_help_stats = f"Show summary {COIN_REPR}: height, difficulty, etc."
bot_help_height = f"Show {COIN_REPR}'s current height"
bot_help_notifytip = "Toggle notify tip notification from bot ON|OFF"
bot_help_settings = "settings view and set for prefix, default coin. Requires permission manage_channels"
bot_help_invite = "Invite link of bot to your server."
bot_help_disclaimer = "Show disclaimer."
bot_help_voucher = "(Testing) make a voucher image and your friend can claim via QR code."
bot_help_take = "Get random faucet tip."


# admin commands
bot_help_admin = "Various admin commands."
bot_help_admin_save = "Save wallet file..."
bot_help_admin_shutdown = "Restart bot."
bot_help_admin_baluser = "Check a specific user's balance for verification purpose."
bot_help_admin_lockuser = "Lock a user from any tx (tip, withdraw, info, etc) by user id"
bot_help_admin_unlockuser = "Unlock a user by user id."
bot_help_admin_cleartx = "Clear pending TX in case of urgent need."

# account commands
bot_help_account = "Various user account commands. (Still testing)"
bot_help_account_twofa = "Generate a 2FA and scanned with Authenticator Program."
bot_help_account_verify = "Verify 2FA code from QR code and your Authenticator Program."
bot_help_account_unverify = "Unverify your account and disable 2FA code."
bot_help_account_secrettip = "Tip someone anonymously by their ID."


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
            return "*Any support, please approach CapEtn#4425.*"
        else:
            return NOTICE_COIN[COIN_NAME]
    else:
        return "*Any support, please approach CapEtn#4425.*"


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
        serverinfo = store.sql_info_by_server(str(message.guild.id))
    if serverinfo and ('prefix' in serverinfo):
        pre_cmd = serverinfo['prefix']
    else:
        pre_cmd =  config.discord.prefixCmd
    extras = [pre_cmd, 'tb!', 'tipbot!']
    return when_mentioned_or(*extras)(bot, message)


bot = AutoShardedBot(command_prefix = get_prefix, case_insensitive=True, owner_id = OWNER_ID_TIPBOT, pm_help = True)

@bot.event
async def on_ready():
    global LIST_IGNORECHAN, BOT_INVITELINK
    print('Ready!')
    print("Hello, I am TipBot Bot!")
    # get WALLET_SERVICE. TODO: Use that later.
    # WALLET_SERVICE = store.sql_get_walletinfo()
    LIST_IGNORECHAN = store.sql_listignorechan()
    # print(WALLET_SERVICE)
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    print("Guilds: {}".format(len(bot.guilds)))
    print("Users: {}".format(sum([x.member_count for x in bot.guilds])))
    BOT_INVITELINK = "https://discordapp.com/oauth2/authorize?client_id="+str(bot.user.id)+"&scope=bot&permissions=3072"
    print("Bot invitation link: " + BOT_INVITELINK)
    game = discord.Game(name="Tip Forever!")
    await bot.change_presence(status=discord.Status.online, activity=game)
    botLogChan = bot.get_channel(id=LOG_CHAN)
    await botLogChan.send(f'{EMOJI_REFRESH} I am back :)')


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
        traceback.print_exc(file=sys.stdout)
        return
    message = None
    author = None
    if message_id:
        try:
            message = await channel.fetch_message(message_id)
            author = message.author
        except discord.errors.NotFound as e:
            # No message found
            return
        member = bot.get_user(id=user_id)
        if emoji_partial in [EMOJI_OK_BOX] and message.author.id == bot.user.id \
            and author != member and message:
            # Delete message
            try:
                await message.delete()
                return
            except discord.errors.NotFound as e:
                # No message found
                return


@bot.event
async def on_reaction_add(reaction, user):
    global REACT_TIP_STORE, TRTL_DISCORD, EMOJI_99, EMOJI_TIP
    # If bot re-act, ignore.
    if user.id == bot.user.id:
        return
    # If other people beside bot react.
    else:
        # If re-action is OK box and message author is bot itself
        if reaction.emoji == EMOJI_OK_BOX and reaction.message.author.id == bot.user.id \
            and (not reaction.message.content.startswith("**ADDRESS REQ")):
            await reaction.message.delete()
        elif reaction.emoji == EMOJI_OK_BOX and reaction.message.author.id == bot.user.id \
            and reaction.message.content.startswith("**ADDRESS REQ") and \
            (user in reaction.message.mentions):
            # OK he confirm
            COIN_NAME = reaction.message.content.split()[2].upper()
            name_to_give = reaction.message.content.split()[5]
            to_send = reaction.message.guild.get_member_named(name_to_give)
            if COIN_NAME in (ENABLE_COIN + ENABLE_XMR):
                user_addr = await store.sql_get_userwallet(str(user.id), COIN_NAME)
                if user_addr is None:
                    userregister = await store.sql_register_user(str(user.id), COIN_NAME)
                    user_addr = await store.sql_get_userwallet(str(user.id), COIN_NAME)
                address = user_addr['balance_wallet_address'] or "NONE"
                # this one to public channel
                # msg = await reaction.message.channel.send(f'{user.mention}\'s {COIN_NAME} deposit address:\n```{address}```')
                try:
                    msg = await to_send.send(f'{str(user)}\'s {COIN_NAME} deposit address:\n```{address}```')
                    # delete message afterward to avoid loop.
                    await reaction.message.delete()
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    # If DM is failed, popup to channel.
                    await reaction.message.channel.send(f'{to_send.mention} I failed DM you for the address.')
                return
                # await msg.add_reaction(EMOJI_OK_BOX)
        # EMOJI_100
        elif reaction.emoji == EMOJI_100 \
            and user.bot == False and reaction.message.author != user and reaction.message.author.bot == False:
            # check if react_tip_100 is ON in the server
            serverinfo = store.sql_info_by_server(str(reaction.message.guild.id))
            if serverinfo['react_tip'] == "ON":
                if (str(reaction.message.id) + '.' + str(user.id)) not in REACT_TIP_STORE:
                    # OK add new message to array                  
                    pass
                else:
                    # he already re-acted and tipped once
                    return
                # get the amount of 100 from defined
                COIN_NAME = serverinfo['default_coin']
                COIN_DEC = get_decimal(COIN_NAME)
                real_amount = int(serverinfo['react_tip_100']) * COIN_DEC
                MinTx = get_min_tx_amount(COIN_NAME)
                MaxTX = get_max_tx_amount(COIN_NAME)
                NetFee = get_tx_fee(coin = COIN_NAME)
                user_from = await store.sql_get_userwallet(str(user.id), COIN_NAME)
                has_forwardtip = None
                if user_from is None:
                    return
                user_to = await store.sql_get_userwallet(str(reaction.message.author.id), COIN_NAME)
                if user_to is None:
                    userregister = await store.sql_register_user(str(reaction.message.author.id), COIN_NAME)
                    user_to = await store.sql_get_userwallet(str(reaction.message.author.id), COIN_NAME)
                if user_to['forwardtip'] == "ON":
                    has_forwardtip = True
                # process other check balance
                if (real_amount + NetFee >= user_from['actual_balance']) or \
                    (real_amount > MaxTX) or (real_amount < MinTx):
                    return
                else:
                    tip = None
                    try:
                        tip = await store.sql_send_tip(str(user.id), str(reaction.message.author.id), real_amount, 'REACTTIP', COIN_NAME)
                        tip_tx_tipper = "Transaction hash: `{}`".format(tip)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                    if tip:
                        notifyList = store.sql_get_tipnotify()
                        REACT_TIP_STORE.append((str(reaction.message.id) + '.' + str(user.id)))
                        servername = serverinfo['servername']
                        if has_forwardtip:
                            if EMOJI_FORWARD not in reaction.message.reactions:
                                await reaction.message.add_reaction(EMOJI_FORWARD)
                        else:
                            if get_emoji(COIN_NAME) not in reaction.message.reactions:
                                await reaction.message.add_reaction(get_emoji(COIN_NAME))
                        # tipper shall always get DM. Ignore notifyList
                        try:
                            await user.send(
                                f'{EMOJI_ARROW_RIGHTHOOK} Tip of {num_format_coin(real_amount, COIN_NAME)} '
                                f'{COIN_NAME} '
                                f'was sent to {reaction.message.author.name}#{reaction.message.author.discriminator} in server `{servername}` by your re-acting {EMOJI_100}\n'
                                f'{tip_tx_tipper}')
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            store.sql_toggle_tipnotify(str(user.id), "OFF")
                        if str(reaction.message.author.id) not in notifyList:
                            try:
                                await reaction.message.author.send(
                                    f'{EMOJI_MONEYFACE} You got a tip of {num_format_coin(real_amount, COIN_NAME)} '
                                    f'{COIN_NAME} from {user.name}#{user.discriminator} in server `{servername}` from their re-acting {EMOJI_100}\n'
                                    f'{tip_tx_tipper}\n'
                                    f'{NOTIFICATION_OFF_CMD}')
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                store.sql_toggle_tipnotify(str(reaction.message.author.id), "OFF")
                        return
                    else:
                        try:
                            await user.send(f'{user.mention} Can not deliver TX for {COIN_NAME} right now with {EMOJI_100}.')
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            store.sql_toggle_tipnotify(str(user.id), "OFF")
                        # add to failed tx table
                        store.sql_add_failed_tx(COIN_NAME, str(user.id), user.name, real_amount, "REACTTIP")
                        return
        # EMOJI_99 TRTL_DISCORD Only
        elif str(reaction.emoji) == EMOJI_99 and reaction.message.guild.id == TRTL_DISCORD \
            and user.bot == False and reaction.message.author != user and reaction.message.author.bot == False:
            # check if react_tip_100 is ON in the server
            serverinfo = store.sql_info_by_server(str(reaction.message.guild.id))
            if serverinfo['react_tip'] == "ON":
                if (str(reaction.message.id) + '.' + str(user.id)) not in REACT_TIP_STORE:
                    # OK add new message to array                  
                    pass
                else:
                    # he already re-acted and tipped once
                    return
                # get the amount of 100 from defined
                COIN_NAME = "TRTL"
                COIN_DEC = get_decimal(COIN_NAME)
                real_amount = 99 * COIN_DEC
                MinTx = get_min_tx_amount(COIN_NAME)
                MaxTX = get_max_tx_amount(COIN_NAME)
                NetFee = get_tx_fee(coin = COIN_NAME)
                user_from = await store.sql_get_userwallet(str(user.id), COIN_NAME)
                has_forwardtip = None
                if user_from is None:
                    return
                user_to = await store.sql_get_userwallet(str(reaction.message.author.id), COIN_NAME)
                if user_to is None:
                    userregister = await store.sql_register_user(str(reaction.message.author.id), COIN_NAME)
                    user_to = await store.sql_get_userwallet(str(reaction.message.author.id), COIN_NAME)
                if user_to['forwardtip'] == "ON":
                    has_forwardtip = True
                # process other check balance
                if (real_amount + NetFee >= user_from['actual_balance']) or \
                    (real_amount > MaxTX) or (real_amount < MinTx):
                    return
                else:
                    tip = None
                    try:
                        tip = await store.sql_send_tip(str(user.id), str(reaction.message.author.id), real_amount, 'REACTTIP', COIN_NAME)
                        tip_tx_tipper = "Transaction hash: `{}`".format(tip)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                    if tip:
                        notifyList = store.sql_get_tipnotify()
                        REACT_TIP_STORE.append((str(reaction.message.id) + '.' + str(user.id)))
                        servername = serverinfo['servername']
                        if has_forwardtip:
                            if EMOJI_FORWARD not in reaction.message.reactions:
                                await reaction.message.add_reaction(EMOJI_FORWARD)
                        else:
                            if get_emoji(COIN_NAME) not in reaction.message.reactions:
                                await reaction.message.add_reaction(get_emoji(COIN_NAME))
                        # tipper shall always get DM. Ignore notifyList
                        try:
                            await user.send(
                                f'{EMOJI_ARROW_RIGHTHOOK} Tip of {num_format_coin(real_amount, COIN_NAME)} '
                                f'{COIN_NAME} '
                                f'was sent to {reaction.message.author.name}#{reaction.message.author.discriminator} in server `{servername}` by your re-acting {EMOJI_99}\n'
                                f'{tip_tx_tipper}')
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            store.sql_toggle_tipnotify(str(user.id), "OFF")
                        if str(reaction.message.author.id) not in notifyList:
                            try:
                                await reaction.message.author.send(
                                    f'{EMOJI_MONEYFACE} You got a tip of {num_format_coin(real_amount, COIN_NAME)} '
                                    f'{COIN_NAME} from {user.name}#{user.discriminator} in server `{servername}` from their re-acting {EMOJI_99}\n'
                                    f'{tip_tx_tipper}\n'
                                    f'{NOTIFICATION_OFF_CMD}')
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                store.sql_toggle_tipnotify(str(reaction.message.author.id), "OFF")
                        return
                    else:
                        try:
                            await user.send(f'{user.mention} Can not deliver TX for {COIN_NAME} right now with {EMOJI_99}.')
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            store.sql_toggle_tipnotify(str(user.id), "OFF")
                        # add to failed tx table
                        store.sql_add_failed_tx(COIN_NAME, str(user.id), user.name, real_amount, "REACTTIP")
                        return
            else:
                return
        # EMOJI_TIP Only
        elif str(reaction.emoji) == EMOJI_TIP \
            and user.bot == False and reaction.message.author != user and reaction.message.author.bot == False:
            # They re-act TIP emoji
            # check if react_tip_100 is ON in the server
            serverinfo = store.sql_info_by_server(str(reaction.message.guild.id))
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
        if LIST_IGNORECHAN:
            if (isinstance(message.channel, discord.DMChannel) == False) and str(message.guild.id) in LIST_IGNORECHAN:
                if message.content[1:].upper().startswith(commandList) \
                    and (str(message.channel.id) in LIST_IGNORECHAN[str(message.guild.id)]):
                    await message.add_reaction(EMOJI_ERROR)
                    await message.channel.send(f'Bot not respond to #{message.channel.name}. It is set to ignore list by channel manager or discord server owner.')
                    return
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
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


@bot.command(pass_context=True, name='about', help=bot_help_about, hidden = True)
async def about(ctx):
    botdetails = discord.Embed(title='About Me', description='', colour=7047495)
    botdetails.add_field(name='Creator\'s Discord Name:', value='CapEtn#4425', inline=True)
    botdetails.add_field(name='My Github:', value='https://github.com/wrkzcoin/TipBot', inline=True)
    botdetails.add_field(name='Invite Me:', value=f'{BOT_INVITELINK}', inline=True)
    botdetails.add_field(name='Servers I am in:', value=len(bot.guilds), inline=True)
    botdetails.add_field(name='Support Me:', value=f'<@{bot.user.id}> donate AMOUNT ticker', inline=True)
    botdetails.set_footer(text='Made in Python3.6+ with discord.py library!', icon_url='http://findicons.com/files/icons/2804/plex/512/python.png')
    botdetails.set_author(name=bot.user.name, icon_url=bot.user.avatar_url)
    try:
        await ctx.send(embed=botdetails)
    except Exception as e:
        await ctx.message.author.send(embed=botdetails)
        traceback.print_exc(file=sys.stdout)


@bot.group(hidden = True, aliases=['acc'], help=bot_help_account)
async def account(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send('Invalid `account` command passed...')
    return


@account.command(aliases=['2fa'], help=bot_help_account_twofa)
async def twofa(ctx):
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'account twofa')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    # return message 2FA already ON if 2FA already validated
    # show QR for 2FA if not yet ON
    userinfo = store.sql_discord_userinfo_get(str(ctx.message.author.id))
    if userinfo is None:
        # Create userinfo
        random_secret32 = pyotp.random_base32()
        create_userinfo = store.sql_userinfo_2fa_insert(str(ctx.message.author.id), random_secret32)
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
            traceback.print_exc(file=sys.stdout)
        if verified and verified.upper() == "YES":
            await ctx.send(f'{ctx.author.mention} You already verified 2FA.')
            return

        try:
            secret_code = store.decrypt_string(userinfo['twofa_secret'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
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
            update_userinfo = store.sql_userinfo_2fa_update(str(ctx.message.author.id), random_secret32)
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


@account.command(help=bot_help_account_verify)
async def verify(ctx, codes: str):
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

    userinfo = store.sql_discord_userinfo_get(str(ctx.message.author.id))
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
            traceback.print_exc(file=sys.stdout)
        if verified and verified.upper() == "YES":
            await ctx.send(f'{ctx.author.mention} You already verified 2FA. You do not need this.')
            return
        
        try:
            secret_code = store.decrypt_string(userinfo['twofa_secret'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        if secret_code and len(secret_code) > 0:
            totp = pyotp.TOTP(secret_code, interval=30)
            if codes in [totp.now(), totp.at(for_time=int(time.time()-15)), totp.at(for_time=int(time.time()+15))]:
                update_userinfo = store.sql_userinfo_2fa_verify(str(ctx.message.author.id), 'YES')
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


@account.command(help=bot_help_account_unverify)
async def unverify(ctx, codes: str):
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

    userinfo = store.sql_discord_userinfo_get(str(ctx.message.author.id))
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
            traceback.print_exc(file=sys.stdout)
        if verified and verified.upper() == "NO":
            await ctx.send(f'{ctx.author.mention} You have not verified yet. **Unverify** stopped.')
            return
        
        try:
            secret_code = store.decrypt_string(userinfo['twofa_secret'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        if secret_code and len(secret_code) > 0:
            totp = pyotp.TOTP(secret_code, interval=30)
            if codes in [totp.now(), totp.at(for_time=int(time.time()-15)), totp.at(for_time=int(time.time()+15))]:
                update_userinfo = store.sql_userinfo_2fa_verify(str(ctx.message.author.id), 'NO')
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


@account.command(help=bot_help_account_secrettip)
async def secrettip(ctx, amount: str, coin: str, user_id: str):
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'tip')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    if isinstance(ctx.channel, discord.DMChannel) == False:
        await message.add_reaction(EMOJI_ZIPPED_MOUTH)
        await ctx.message.author.send(f'{EMOJI_RED_NO} This command can not be in public.')
        return

    amount = amount.replace(",", "")
    try:
        amount = float(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    COIN_NAME = coin.upper()

    if COIN_NAME in MAINTENANCE_COIN:
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return

    # OK DOGE in.
    if COIN_NAME not in (ENABLE_COIN+ENABLE_COIN_DOGE):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} not available or supported.')
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

    # Check if bot can find that user_id
    member = bot.get_user(id=int(user_id))
    if member:
        pass
    else:
        await ctx.message.add_reaction(EMOJI_WARNING)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} I could not find a member with id `{user_id}`')
        return

    notifyList = store.sql_get_tipnotify()
    has_forwardtip = None
    address_to = None
    # Just copy / paste lines
    if COIN_NAME in ENABLE_COIN:
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        user_to = await store.sql_get_userwallet(user_id, COIN_NAME)
        if user_to is None:
            userregister = await store.sql_register_user(user_id, COIN_NAME)
            user_to = await store.sql_get_userwallet(user_id, COIN_NAME)
        if user_to['forwardtip'] == "ON":
            has_forwardtip = True
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        NetFee = get_tx_fee(coin = COIN_NAME)
        if real_amount + NetFee >= user_from['actual_balance']:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send secret tip of '
                            f'{num_format_coin(real_amount, COIN_NAME)} '
                            f'{COIN_NAME} to {user_id}.')
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
    elif COIN_NAME in ENABLE_COIN_DOGE:
        MinTx = config.daemonDOGE.min_mv_amount
        MaxTX = config.daemonDOGE.max_mv_amount
        user_from = {}
        user_from['address'] = await DOGE_LTC_getaccountaddress(str(ctx.message.author.id), COIN_NAME)
        user_from['actual_balance'] = float(await DOGE_LTC_getbalance_acc(str(ctx.message.author.id), COIN_NAME, 6))
        user_to = {}
        user_to['address'] = await DOGE_LTC_getaccountaddress(user_id, COIN_NAME)
        real_amount = float(amount)
        userdata_balance = store.sql_doge_balance(str(ctx.message.author.id), COIN_NAME)
        if real_amount > float(user_from['actual_balance']) + float(userdata_balance['Adjust']):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send a secret tip of '
                            f'{num_format_coin(real_amount, COIN_NAME)} '
                            f'{COIN_NAME} to `{user_id}`.')
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
    tip = None
    if COIN_NAME == "DOGE":
        tip = store.sql_mv_doge_single(str(ctx.message.author.id), user_id, real_amount, COIN_NAME, "SECRETTIP")
        tip = "N/A for "+COIN_NAME
    else:
        try:
            tip = await store.sql_send_secrettip(str(ctx.message.author.id), user_id, real_amount, COIN_NAME)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    if tip:
        if has_forwardtip:
            await ctx.message.add_reaction(EMOJI_FORWARD)
        else:
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
        # tipper shall always get DM. Ignore notifyList
        try:
            await ctx.message.author.send(
                f'{EMOJI_ARROW_RIGHTHOOK} Secret tip of {num_format_coin(real_amount, COIN_NAME)} '
                f'{COIN_NAME} '
                f'was sent to {user_id} / {member.name}#{member.discriminator}\n'
                f'Transaction hash: `{tip}`')
        except (discord.Forbidden, discord.errors.Forbidden) as e:
            store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
        if str(user_id) not in notifyList:
            # member already declare above
            try:
                await member.send(
                    f'{EMOJI_MONEYFACE} You got a secret tip of {num_format_coin(real_amount, COIN_NAME)} '
                    f'{COIN_NAME}\n'
                    f'Transaction hash: `{tip}`\n'
                    f'{NOTIFICATION_OFF_CMD}')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                store.sql_toggle_tipnotify(str(member.id), "OFF")
        else:
            try:
                await ctx.message.author.send(f'{member.name}#{member.discriminator}` / {user_id} received '
                                              f'{num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}'
                                              ' but has notification **OFF** or **DM disable**.')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                pass
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Can not deliver TX for {COIN_NAME} right now. Try again soon.')
        # add to failed tx table
        store.sql_add_failed_tx(COIN_NAME, str(ctx.message.author.id), ctx.message.author.name, real_amount, "SECRETTIP")
        return


@account.command(hidden = True)
async def set(ctx, param: str, value: str):
    await ctx.send('On progress.')
    return


@bot.group(hidden = True, help=bot_help_admin)
@commands.is_owner()
async def admin(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send('Invalid `admin` command passed...')
    return


@commands.is_owner()
@admin.command(help=bot_help_admin_save)
async def save(ctx, coin: str):
    global SAVING_ALL
    botLogChan = bot.get_channel(id=LOG_CHAN)
    COIN_NAME = coin.upper()
    if COIN_NAME in MAINTENANCE_COIN:
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
            if coinItem in MAINTENANCE_COIN:
                duration_msg += "{} Maintenance.\n".format(coinItem)
            else:
                if coinItem in ["CCX", "ANX"]:
                    duration_msg += "{} Skipped.\n".format(coinItem)
                else:
                    try:
                        if coinItem in WALLET_API_COIN:
                            one_save = await walletapi.save_walletapi(coinItem)
                        else:
                            one_save = await rpc_cn_wallet_save(coinItem)
                        duration_msg += "{} saved took {}s.\n".format(coinItem, round(one_save,3))
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
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
@admin.command(pass_context=True, name='shutdown', aliases=['restart'], help=bot_help_admin_shutdown)
async def shutdown(ctx):
    botLogChan = bot.get_channel(id=LOG_CHAN)
    IS_MAINTENANCE = 1
    await ctx.send(f'{EMOJI_REFRESH} {ctx.author.mention} .. restarting .. back soon.')
    await botLogChan.send(f'{EMOJI_REFRESH} {ctx.message.author.name}#{ctx.message.author.discriminator} called `restart`. I will be back soon hopefully.')
    await bot.logout()


@commands.is_owner()
@admin.command(help=bot_help_admin_baluser)
async def baluser(ctx, user_id: str, create_wallet: str = None):
    create_acc = None
    # for verification | future restoration of lost account
    table_data = [
        ['TICKER', 'Available', 'Locked']
    ]
    for coinItem in ENABLE_COIN:
        if coinItem not in MAINTENANCE_COIN:
            COIN_DEC = get_decimal(coinItem.upper())
            wallet = await store.sql_get_userwallet(str(user_id), coinItem.upper())
            if wallet is None:
                if create_wallet and create_wallet.upper() == "ON":
                    create_acc = True
                    wallet = await store.sql_get_userwallet(str(user_id), coinItem.upper())
                    if wallet is None:
                        userregister = await store.sql_register_user(str(user_id), coinItem.upper())
                        wallet = await store.sql_get_userwallet(str(user_id), coinItem.upper())
                if wallet:
                    table_data.append([coinItem.upper(), num_format_coin(0, coinItem.upper()), num_format_coin(0, coinItem.upper())])
                else:
                    table_data.append([coinItem.upper(), "N/A", "N/A"])
            else:
                create_acc = True
                balance_actual = num_format_coin(wallet['actual_balance'], coinItem.upper())
                balance_locked = num_format_coin(wallet['locked_balance'], coinItem.upper())
                balance_total = num_format_coin((wallet['actual_balance'] + wallet['locked_balance']), coinItem.upper())
                coinName = coinItem.upper()
                if  wallet['user_wallet_address'] is None:
                    coinName += '*'
                if wallet['forwardtip'] == "ON":
                    coinName += ' >>'
                table_data.append([coinName, balance_actual, balance_locked])
                pass
        else:
            table_data.append([coinItem.upper(), "***", "***"])
    # Add DOGE
    COIN_NAME = "DOGE"
    if COIN_NAME not in MAINTENANCE_COIN and create_acc:
        depositAddress = await DOGE_LTC_getaccountaddress(str(user_id), COIN_NAME)
        actual = float(await DOGE_LTC_getbalance_acc(str(user_id), COIN_NAME, 6))
        locked = float(await DOGE_LTC_getbalance_acc(str(user_id), COIN_NAME, 1))
        userdata_balance = store.sql_doge_balance(str(user_id), COIN_NAME)

        if actual == locked:
            balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
            balance_locked = num_format_coin(0, COIN_NAME)
        else:
            balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
            if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                balance_locked =  num_format_coin(0, COIN_NAME)
            else:
                balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
        wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if wallet['user_wallet_address'] is None:
            COIN_NAME += '*'
        table_data.append([COIN_NAME, balance_actual, balance_locked])
    else:
        table_data.append([COIN_NAME, "***", "***"])
    # End of Add DOGE
    # Add XTOR
    COIN_NAME = "XTOR"
    if COIN_NAME not in MAINTENANCE_COIN:
        wallet = await store.sql_get_userwallet(str(user_id), COIN_NAME)
        if wallet is None:
            userregister = await store.sql_register_user(str(user_id), COIN_NAME)
            wallet = await store.sql_get_userwallet(str(user_id), COIN_NAME)
        if wallet:
            actual = wallet['actual_balance']
            locked = wallet['locked_balance']
            userdata_balance = store.sql_xmr_balance(str(user_id), COIN_NAME)
            balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
            if actual == locked:
                balance_locked = num_format_coin(0, COIN_NAME)
            else:
                if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                    balance_locked =  num_format_coin(0, COIN_NAME)
                else:
                    balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
            if wallet['user_wallet_address'] is None:
                COIN_NAME += '*'
            table_data.append([COIN_NAME, balance_actual, balance_locked])
        else:
            table_data.append([COIN_NAME, "***", "***"])
    # End of Add XTOR
    COIN_NAME = "LOKI"
    if COIN_NAME not in MAINTENANCE_COIN:
        wallet = await store.sql_get_userwallet(str(user_id), COIN_NAME)
        if wallet is None:
            userregister = await store.sql_register_user(str(user_id), COIN_NAME)
            wallet = await store.sql_get_userwallet(str(user_id), COIN_NAME)
        if wallet:
            actual = wallet['actual_balance']
            locked = wallet['locked_balance']
            userdata_balance = store.sql_xmr_balance(str(user_id), COIN_NAME)
            balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
            if actual == locked:
                balance_locked = num_format_coin(0, COIN_NAME)
            else:
                if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                    balance_locked =  num_format_coin(0, COIN_NAME)
                else:
                    balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
            if wallet['user_wallet_address'] is None:
                COIN_NAME += '*'
            table_data.append([COIN_NAME, balance_actual, balance_locked])
    else:
        table_data.append([COIN_NAME, "***", "***"])
    # End of Add LOKI
    COIN_NAME = "XMR"
    if COIN_NAME not in MAINTENANCE_COIN:
        wallet = await store.sql_get_userwallet(str(user_id), COIN_NAME)
        if wallet is None:
            userregister = await store.sql_register_user(str(user_id), COIN_NAME)
            wallet = await store.sql_get_userwallet(str(user_id), COIN_NAME)
        if wallet:
            actual = wallet['actual_balance']
            locked = wallet['locked_balance']
            userdata_balance = store.sql_xmr_balance(str(user_id), COIN_NAME)
            balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
            if actual == locked:
                balance_locked = num_format_coin(0, COIN_NAME)
            else:
                if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                    balance_locked =  num_format_coin(0, COIN_NAME)
                else:
                    balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
            if wallet['user_wallet_address'] is None:
                COIN_NAME += '*'
            table_data.append([COIN_NAME, balance_actual, balance_locked])
    else:
        table_data.append([COIN_NAME, "***", "***"])
    # End of Add XMR
    COIN_NAME = "XEQ"
    if COIN_NAME not in MAINTENANCE_COIN:
        wallet = await store.sql_get_userwallet(str(user_id), COIN_NAME)
        if wallet is None:
            userregister = await store.sql_register_user(str(user_id), COIN_NAME)
            wallet = await store.sql_get_userwallet(str(user_id), COIN_NAME)
        if wallet:
            actual = wallet['actual_balance']
            locked = wallet['locked_balance']
            userdata_balance = store.sql_xmr_balance(str(user_id), COIN_NAME)
            balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
            if actual == locked:
                balance_locked = num_format_coin(0, COIN_NAME)
            else:
                if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                    balance_locked =  num_format_coin(0, COIN_NAME)
                else:
                    balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
            if wallet['user_wallet_address'] is None:
                COIN_NAME += '*'
            table_data.append([COIN_NAME, balance_actual, balance_locked])
    else:
        table_data.append([COIN_NAME, "***", "***"])
    # End of Add XEQ
    COIN_NAME = "ARQ"
    if COIN_NAME not in MAINTENANCE_COIN:
        wallet = await store.sql_get_userwallet(str(user_id), COIN_NAME)
        if wallet is None:
            userregister = await store.sql_register_user(str(user_id), COIN_NAME)
            wallet = await store.sql_get_userwallet(str(user_id), COIN_NAME)
        if wallet:
            actual = wallet['actual_balance']
            locked = wallet['locked_balance']
            userdata_balance = store.sql_xmr_balance(str(user_id), COIN_NAME)
            balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
            if actual == locked:
                balance_locked = num_format_coin(0, COIN_NAME)
            else:
                if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                    balance_locked =  num_format_coin(0, COIN_NAME)
                else:
                    balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
            if wallet['user_wallet_address'] is None:
                COIN_NAME += '*'
            table_data.append([COIN_NAME, balance_actual, balance_locked])
    else:
        table_data.append([COIN_NAME, "***", "***"])
    # End of Add ARQ
    COIN_NAME = "MSR"
    if COIN_NAME not in MAINTENANCE_COIN:
        wallet = await store.sql_get_userwallet(str(user_id), COIN_NAME)
        if wallet is None:
            userregister = await store.sql_register_user(str(user_id), COIN_NAME)
            wallet = await store.sql_get_userwallet(str(user_id), COIN_NAME)
        if wallet:
            actual = wallet['actual_balance']
            locked = wallet['locked_balance']
            userdata_balance = store.sql_xmr_balance(str(user_id), COIN_NAME)
            balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
            if actual == locked:
                balance_locked = num_format_coin(0, COIN_NAME)
            else:
                if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                    balance_locked =  num_format_coin(0, COIN_NAME)
                else:
                    balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
            if wallet['user_wallet_address'] is None:
                COIN_NAME += '*'
            table_data.append([COIN_NAME, balance_actual, balance_locked])
    else:
        table_data.append([COIN_NAME, "***", "***"])
    # End of Add MSR
    COIN_NAME = "BLOG"
    if COIN_NAME not in MAINTENANCE_COIN:
        wallet = await store.sql_get_userwallet(str(user_id), COIN_NAME)
        if wallet is None:
            userregister = await store.sql_register_user(str(user_id), COIN_NAME)
            wallet = await store.sql_get_userwallet(str(user_id), COIN_NAME)
        if wallet:
            actual = wallet['actual_balance']
            locked = wallet['locked_balance']
            userdata_balance = store.sql_xmr_balance(str(user_id), COIN_NAME)
            balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
            if actual == locked:
                balance_locked = num_format_coin(0, COIN_NAME)
            else:
                if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                    balance_locked =  num_format_coin(0, COIN_NAME)
                else:
                    balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
            if wallet['user_wallet_address'] is None:
                COIN_NAME += '*'
            table_data.append([COIN_NAME, balance_actual, balance_locked])
    else:
        table_data.append([COIN_NAME, "***", "***"])
    # End of Add BLOG
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
    get_discord_userinfo = store.sql_discord_userinfo_get(user_id)
    if get_discord_userinfo is None:
        store.sql_userinfo_locked(user_id, 'YES', reason, str(ctx.message.author.id))
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        await ctx.message.author.send(f'{user_id} is locked.')
        return
    else:
        if get_discord_userinfo['locked'].upper() == "YES":
            await ctx.message.author.send(f'{user_id} was already locked.')
        else:
            store.sql_userinfo_locked(user_id, 'YES', reason, str(ctx.message.author.id))
            await ctx.message.add_reaction(EMOJI_OK_HAND)
            await ctx.message.author.send(f'Turn {user_id} to locked.')
        return


@commands.is_owner()
@admin.command(help=bot_help_admin_unlockuser)
async def unlockuser(ctx, user_id: str):
    get_discord_userinfo = store.sql_discord_userinfo_get(user_id)
    if get_discord_userinfo:
        if get_discord_userinfo['locked'].upper() == "NO":
            await ctx.message.author.send(f'**{user_id}** was already unlocked. Nothing to do.')
        else:
            store.sql_change_userinfo_single(user_id, 'locked', 'NO')
            await ctx.message.author.send(f'Unlocked {user_id} done.')
        return      
    else:
        await ctx.message.author.send(f'{user_id} not stored in **discord userinfo** yet. Nothing to unlocked.')
        return


@commands.is_owner()
@admin.command()
async def roachadd(ctx, main_id: str, user_id: str):
    if main_id == user_id:
        await ctx.message.author.send(f'{main_id} and {user_id} can not be the same.')
        await ctx.message.add_reaction(EMOJI_ERROR)
        return
    else:
        main_member = bot.get_user(id=int(main_id))
        roach_user = bot.get_user(id=int(user_id))
        if main_member and roach_user:
            add_roach = store.sql_roach_add(main_id, user_id, roach_user.name+"#"+roach_user.discriminator, main_member.name+"#"+main_member.discriminator)
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
    global WITHDRAW_IN_PROCESS
    if len(WITHDRAW_IN_PROCESS) == 0:
        await ctx.message.author.send(f'{ctx.author.mention} Nothing in tx pending to clear.')
    else:
        list_pending = '{' + ', '.join(WITHDRAW_IN_PROCESS) + '}'
        await ctx.message.add_reaction(EMOJI_WARNING)
        await ctx.message.author.send(f'{ctx.author.mention} Clearing {len(WITHDRAW_IN_PROCESS)} {list_pending} in pending...')
        WITHDRAW_IN_PROCESS = [] 
    return


@commands.is_owner()
@admin.command()
async def checkcoin(ctx, coin: str):
    # Check of wallet in SQL consistence to wallet-service
    botLogChan = bot.get_channel(id=LOG_CHAN)
    COIN_NAME = coin.upper()
    if COIN_NAME not in (ENABLE_COIN + ENABLE_XMR + ENABLE_COIN_DOGE):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.message.author.send(f'{COIN_NAME} is not in TipBot.')
        return
    if COIN_NAME in MAINTENANCE_COIN:
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family == "TRTL":
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
    elif COIN_NAME == "DOGE":
        # TODO
        total_balance_str = await store.sql_doge_checkcoin(COIN_NAME)
        if total_balance_str:
            await ctx.send(f'**{COIN_NAME}** Checking:'
                           '```'
                           f'{total_balance_str}'
                           '```')
            return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.message.author.send(f'{COIN_NAME} not supporting with this function.')
        return


@commands.is_owner()
@admin.command()
async def guild(ctx):
    # TODO
    return


@commands.is_owner()
@admin.command(hidden = True)
async def dumpinfo(ctx, coin: str):
    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_COIN:
        await ctx.message.author.send('COIN **{}** NOT SUPPORTED.'.format(COIN_NAME))
        return

    start = time.time()
    try:
        await store.sql_update_balances(COIN_NAME)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
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
    # where i always test something. Nothing to do here.
    test_str = "WrkzRNDQDwFCBynKPc459v3LDa1gEGzG3j962tMUBko1fw9xgdaS9mNiGMgA9s1q7hS1Z8SGRVWzcGc8Sh8xsvfZ6u2wJEtoZB"
    encrypted = store.encrypt_string(test_str)
    decrypted = store.decrypt_string(encrypted)
    await ctx.send('```Original: {}\nEncrypted: {}\nDecrypted: {}```'.format(test_str, encrypted, decrypted))
    return


@bot.command(pass_context=True, name='info', aliases=['wallet'], help=bot_help_info)
async def info(ctx, coin: str = None):
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

    global LIST_IGNORECHAN
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
                server_tiponly = "ALLCOIN"
            else:
                servername = serverinfo['servername']
                server_id = str(ctx.guild.id)
                server_prefix = serverinfo['prefix']
                server_coin = serverinfo['default_coin'].upper()
                server_tiponly = serverinfo['tiponly'].upper()
                if serverinfo['react_tip'].upper() == "ON":
                    COIN_NAME = serverinfo['default_coin'].upper()
                    # COIN_DEC = get_decimal(COIN_NAME)
                    # real_amount = int(amount * COIN_DEC)
                    react_tip_value = str(serverinfo['react_tip_100']) + COIN_NAME
                else:
                    react_tip_value = "N/A"
            chanel_ignore_list = ''
            if LIST_IGNORECHAN:
                if str(ctx.guild.id) in LIST_IGNORECHAN:
                    for item in LIST_IGNORECHAN[str(ctx.guild.id)]:
                        chanel_ignore = bot.get_channel(id=int(item))
                        chanel_ignore_list = chanel_ignore_list + '#'  + chanel_ignore.name + ' '

            tickers = '|'.join(ENABLE_COIN).lower()
            extra_text = f'Please add ticker after **{cmdName.lower()}**. Example: `{server_prefix}{cmdName.lower()} {server_coin}`, if you want to get your address(es).\n\n'\
                         f'Type: `{server_prefix}setting` if you want to change `prefix` or `default_coin` or `ignorechan` or `del_ignorechan` or `tiponly`. (Required permission)'
            msg = await ctx.send(
                '\n```'
                f'Server ID:      {ctx.guild.id}\n'
                f'Server Name:    {ctx.message.guild.name}\n'
                f'Default ticker: {server_coin}\n'
                f'Default prefix: {server_prefix}\n'
                f'TipOnly Coins:  {server_tiponly}\n'
                f'Re-act Tip:     {react_tip_value}\n'
                f'Ignored Tip in: {chanel_ignore_list}\n'
                f'```\n{extra_text}')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
    else:
        COIN_NAME = coin.upper()
        pass

    if COIN_NAME not in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
        return

    try:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**')
        return
    
    if (COIN_NAME in MAINTENANCE_COIN) and (ctx.message.author.id not in MAINTENANCE_OWNER):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return
    
    if coin_family == "TRTL" or coin_family == "CCX":
        wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if wallet is None:
            userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME)
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    elif coin_family == "XMR":
        wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if wallet is None:
            userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME)
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    elif COIN_NAME in ENABLE_COIN_DOGE:
        wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        depositAddress = await DOGE_LTC_getaccountaddress(str(ctx.message.author.id), COIN_NAME)
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

    if wallet['user_wallet_address']:
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        await ctx.message.author.send("**QR for your Deposit**", 
                                    file=discord.File(config.qrsettings.path + wallet['balance_wallet_address'] + ".png"))
        await ctx.message.author.send(f'**[ACCOUNT INFO]**\n\n'
                                    f'{EMOJI_MONEYBAG} Deposit Address: `' + wallet['balance_wallet_address'] + '`\n'
                                    f'{EMOJI_SCALE} Registered Wallet: `'
                                    ''+ wallet['user_wallet_address'] + '`\n'
                                    f'{get_notice_txt(COIN_NAME)}')
    else:
        await ctx.message.add_reaction(EMOJI_WARNING)
        await ctx.message.author.send("**QR for your Deposit**", 
                                    file=discord.File(config.qrsettings.path + wallet['balance_wallet_address'] + ".png"))
        await ctx.message.author.send(f'**[ACCOUNT INFO]**\n\n'
                               f'{EMOJI_MONEYBAG} Deposit Address: `' + wallet['balance_wallet_address'] + '`\n'
                               f'{EMOJI_SCALE} Registered Wallet: `NONE, Please register.`\n'
                               f'{get_notice_txt(COIN_NAME)}')
    return


@bot.command(pass_context=True, name='balance', aliases=['bal'], help=bot_help_balance)
async def balance(ctx, coin: str = None):
    serverinfo = None
    botLogChan = bot.get_channel(id=LOG_CHAN)
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'balance')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

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
    COIN_NAME = None
    if (coin is None) or (PUBMSG == "PUB") or (PUBMSG == "PUBLIC"):
        table_data = [
            ['TICKER', 'Available', 'Locked']
        ]
        for COIN_NAME in [coinItem.upper() for coinItem in ENABLE_COIN]:
            if COIN_NAME not in MAINTENANCE_COIN:
                COIN_DEC = get_decimal(COIN_NAME)
                wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
                if wallet is None:
                    userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME)
                    wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
                if wallet is None:
                    table_data.append([COIN_NAME, "N/A", "N/A"])
                    await botLogChan.send(f'A user call `{prefixChar}balance` failed with {COIN_NAME}')
                else:
                    balance_actual = num_format_coin(wallet['actual_balance'], COIN_NAME)
                    balance_locked = num_format_coin(wallet['locked_balance'], COIN_NAME)
                    balance_total = num_format_coin((wallet['actual_balance'] + wallet['locked_balance']), COIN_NAME)
                    coinName = COIN_NAME
                    if wallet['user_wallet_address'] is None:
                        coinName += '*'
                    if wallet['forwardtip'] == "ON":
                        coinName += ' >>'
                    if wallet['actual_balance'] + wallet['locked_balance'] != 0:
                        table_data.append([coinName, balance_actual, balance_locked])
                    pass
            else:
                table_data.append([COIN_NAME, "***", "***"])
        # Add DOGE
        COIN_NAME = "DOGE"
        if COIN_NAME not in MAINTENANCE_COIN:
            depositAddress = await DOGE_LTC_getaccountaddress(str(ctx.message.author.id), COIN_NAME)
            actual = float(await DOGE_LTC_getbalance_acc(str(ctx.message.author.id), COIN_NAME, 6))
            locked = float(await DOGE_LTC_getbalance_acc(str(ctx.message.author.id), COIN_NAME, 1))
            userdata_balance = store.sql_doge_balance(str(ctx.message.author.id), COIN_NAME)
            if actual == locked:
                balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
                balance_locked = num_format_coin(0, COIN_NAME)
            else:
                balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
                if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                    balance_locked =  num_format_coin(0, COIN_NAME)
                else:
                    balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
            if wallet['user_wallet_address'] is None:
                COIN_NAME += '*'
            table_data.append([COIN_NAME, balance_actual, balance_locked])
        else:
            table_data.append([COIN_NAME, "***", "***"])
        # End of Add DOGE
        # Add XTOR
        COIN_NAME = "XTOR"
        if COIN_NAME not in MAINTENANCE_COIN:
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
            if wallet is None:
                userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME)
                wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
            if wallet:
                actual = wallet['actual_balance']
                locked = wallet['locked_balance']
                userdata_balance = store.sql_xmr_balance(str(ctx.message.author.id), COIN_NAME)
                balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
                if actual == locked:
                    balance_locked = num_format_coin(0, COIN_NAME)
                else:
                    if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                        balance_locked =  num_format_coin(0, COIN_NAME)
                    else:
                        balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
                if wallet['user_wallet_address'] is None:
                    COIN_NAME += '*'
                if actual + float(userdata_balance['Adjust']) != 0:
                    table_data.append([COIN_NAME, balance_actual, balance_locked])
        else:
            table_data.append([COIN_NAME, "***", "***"])
        # End of Add XTOR
        COIN_NAME = "LOKI"
        if COIN_NAME not in MAINTENANCE_COIN:
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
            if wallet is None:
                userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME)
                wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
            if wallet:
                actual = wallet['actual_balance']
                locked = wallet['locked_balance']
                userdata_balance = store.sql_xmr_balance(str(ctx.message.author.id), COIN_NAME)
                balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
                if actual == locked:
                    balance_locked = num_format_coin(0, COIN_NAME)
                else:
                    if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                        balance_locked =  num_format_coin(0, COIN_NAME)
                    else:
                        balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
                if wallet['user_wallet_address'] is None:
                    COIN_NAME += '*'
                if actual + float(userdata_balance['Adjust']) != 0:
                    table_data.append([COIN_NAME, balance_actual, balance_locked])
        else:
            table_data.append([COIN_NAME, "***", "***"])
        # End of Add LOKI
        COIN_NAME = "XMR"
        if COIN_NAME not in MAINTENANCE_COIN:
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
            if wallet is None:
                userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME)
                wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
            if wallet:
                actual = wallet['actual_balance']
                locked = wallet['locked_balance']
                userdata_balance = store.sql_xmr_balance(str(ctx.message.author.id), COIN_NAME)
                balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
                if actual == locked:
                    balance_locked = num_format_coin(0, COIN_NAME)
                else:
                    if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                        balance_locked =  num_format_coin(0, COIN_NAME)
                    else:
                        balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
                if wallet['user_wallet_address'] is None:
                    COIN_NAME += '*'
                if actual + float(userdata_balance['Adjust']) != 0:
                    table_data.append([COIN_NAME, balance_actual, balance_locked])
        else:
            table_data.append([COIN_NAME, "***", "***"])
        # End of Add XMR
        COIN_NAME = "XEQ"
        if COIN_NAME not in MAINTENANCE_COIN:
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
            if wallet is None:
                userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME)
                wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
            if wallet:
                actual = wallet['actual_balance']
                locked = wallet['locked_balance']
                userdata_balance = store.sql_xmr_balance(str(ctx.message.author.id), COIN_NAME)
                balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
                if actual == locked:
                    balance_locked = num_format_coin(0, COIN_NAME)
                else:
                    if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                        balance_locked =  num_format_coin(0, COIN_NAME)
                    else:
                        balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
                if wallet['user_wallet_address'] is None:
                    COIN_NAME += '*'
                if actual + float(userdata_balance['Adjust']) != 0:
                    table_data.append([COIN_NAME, balance_actual, balance_locked])
        else:
            table_data.append([COIN_NAME, "***", "***"])
        # End of Add XEQ
        COIN_NAME = "BLOG"
        if COIN_NAME not in MAINTENANCE_COIN:
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
            if wallet is None:
                userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME)
                wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
            if wallet:
                actual = wallet['actual_balance']
                locked = wallet['locked_balance']
                userdata_balance = store.sql_xmr_balance(str(ctx.message.author.id), COIN_NAME)
                balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
                if actual == locked:
                    balance_locked = num_format_coin(0, COIN_NAME)
                else:
                    if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                        balance_locked =  num_format_coin(0, COIN_NAME)
                    else:
                        balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
                if wallet['user_wallet_address'] is None:
                    COIN_NAME += '*'
                if actual + float(userdata_balance['Adjust']) != 0:
                    table_data.append([COIN_NAME, balance_actual, balance_locked])
        else:
            table_data.append([COIN_NAME, "***", "***"])
        # End of Add BLOG
        COIN_NAME = "ARQ"
        if COIN_NAME not in MAINTENANCE_COIN:
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
            if wallet is None:
                userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME)
                wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
            if wallet:
                actual = wallet['actual_balance']
                locked = wallet['locked_balance']
                userdata_balance = store.sql_xmr_balance(str(ctx.message.author.id), COIN_NAME)
                balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
                if actual == locked:
                    balance_locked = num_format_coin(0, COIN_NAME)
                else:
                    if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                        balance_locked =  num_format_coin(0, COIN_NAME)
                    else:
                        balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
                if wallet['user_wallet_address'] is None:
                    COIN_NAME += '*'
                if actual + float(userdata_balance['Adjust']) != 0:
                    table_data.append([COIN_NAME, balance_actual, balance_locked])
        else:
            table_data.append([COIN_NAME, "***", "***"])
        # End of Add ARQ
        COIN_NAME = "MSR"
        if COIN_NAME not in MAINTENANCE_COIN:
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
            if wallet is None:
                userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME)
                wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
            if wallet:
                actual = wallet['actual_balance']
                locked = wallet['locked_balance']
                userdata_balance = store.sql_xmr_balance(str(ctx.message.author.id), COIN_NAME)
                balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
                if actual == locked:
                    balance_locked = num_format_coin(0, COIN_NAME)
                else:
                    if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                        balance_locked =  num_format_coin(0, COIN_NAME)
                    else:
                        balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
                if wallet['user_wallet_address'] is None:
                    COIN_NAME += '*'
                if actual + float(userdata_balance['Adjust']) != 0:
                    table_data.append([COIN_NAME, balance_actual, balance_locked])
        else:
            table_data.append([COIN_NAME, "***", "***"])
        # End of Add MSR
        table = AsciiTable(table_data)
        # table.inner_column_border = False
        # table.outer_border = False
        table.padding_left = 0
        table.padding_right = 0
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        if PUBMSG.upper() == "PUB" or PUBMSG.upper() == "PUBLIC":
            msg = await ctx.send('**[ BALANCE LIST ]**\n'
                            f'```{table.table}```\n'
                            f'Related command: `{prefixChar}balance TICKER` or `{prefixChar}info TICKER`\n')
        else:
            msg = await ctx.message.author.send('**[ BALANCE LIST ]**\n'
                            f'```{table.table}```\n'
                            f'Related command: `{prefixChar}balance TICKER` or `{prefixChar}info TICKER`\n'
                            f'{get_notice_txt(COIN_NAME)}')
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    else:
        COIN_NAME = coin.upper()

    coin_family = "TRTL"
    try:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**')
        return

    if COIN_NAME in MAINTENANCE_COIN and ctx.message.author.id not in MAINTENANCE_OWNER:
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        msg = await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} in maintenance.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    if coin_family == "TRTL" or coin_family == "CCX":
        walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
        COIN_DEC = get_decimal(COIN_NAME)
        pass
    elif coin_family == "XMR":
        wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if wallet is None:
            userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME)
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if wallet:
            actual = wallet['actual_balance']
            locked = wallet['locked_balance']
            userdata_balance = store.sql_xmr_balance(str(ctx.message.author.id), COIN_NAME)
            if actual == locked:				
                balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']) , COIN_NAME)
                balance_locked = num_format_coin(0 , COIN_NAME)
            else:
                balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
                if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                    balance_locked = num_format_coin(0, COIN_NAME)
                else:
                    balance_locked = num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
            await ctx.message.add_reaction(EMOJI_OK_HAND)
            msg = await ctx.message.author.send(f'**[YOUR {COIN_NAME} BALANCE]**\n\n'
                f'{EMOJI_MONEYBAG} Available: {balance_actual} '
                f'{COIN_NAME}\n'
                f'{EMOJI_MONEYBAG} Pending: {balance_locked} '
                f'{COIN_NAME}\n'
                f'{get_notice_txt(COIN_NAME)}')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        else:
            await message.add_reaction(EMOJI_ERROR)
            return
    elif COIN_NAME == "DOGE":
        depositAddress = await DOGE_LTC_getaccountaddress(str(ctx.message.author.id), COIN_NAME)
        actual = float(await DOGE_LTC_getbalance_acc(str(ctx.message.author.id), COIN_NAME, 6))
        locked = float(await DOGE_LTC_getbalance_acc(str(ctx.message.author.id), COIN_NAME, 1))
        userdata_balance = store.sql_doge_balance(str(ctx.message.author.id), COIN_NAME)
        if actual == locked:				
            balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']) , COIN_NAME)
            balance_locked = num_format_coin(0 , COIN_NAME)
        else:
            balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
            if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                balance_locked = num_format_coin(0, COIN_NAME)
            else:
                balance_locked = num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        msg = await ctx.message.author.send(
                               f'**[ YOUR {COIN_NAME} BALANCE ]**\n'
                               f' Deposit Address: `{depositAddress}`\n'
                               f'{EMOJI_MONEYBAG} Available: {balance_actual} '
                               f'{COIN_NAME}\n'
                               f'{EMOJI_MONEYBAG} Pending: {balance_locked} '
                               f'{COIN_NAME}\n'
                               f'{get_notice_txt(COIN_NAME)}')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    elif COIN_NAME not in ENABLE_COIN:
        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is no such ticker {COIN_NAME}.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    if walletStatus is None:
        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} I can not connect to wallet service or daemon.')
        await msg.add_reaction(EMOJI_OK_BOX)
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
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} Wallet service hasn\'t sync fully with network or being re-sync. More info:\n```'
                           f'networkBlockCount:     {t_networkBlockCount}\n'
                           f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                           f'Progress %:            {t_percent}\n```'
                           )
            await msg.add_reaction(EMOJI_OK_BOX)
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
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {config.maintenance_msg}')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
    else:
        pass
    # End Check if maintenance

    wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    if wallet is None:
        userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME)
        wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    if wallet is None:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} Internal Error for `.balance`')
        return
    ago = ""
    if 'lastUpdate' in wallet:
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        try:
            update = datetime.fromtimestamp(int(wallet['lastUpdate'])).strftime('%Y-%m-%d %H:%M:%S')
            ago = EMOJI_HOURGLASS_NOT_DONE + " update: " + timeago.format(update, datetime.now())
        except:
            pass

    balance_actual = num_format_coin(wallet['actual_balance'], COIN_NAME)
    balance_locked = num_format_coin(wallet['locked_balance'], COIN_NAME)

    msg = await ctx.message.author.send(f'**[YOUR {COIN_NAME} BALANCE]**\n\n'
        f'{EMOJI_MONEYBAG} Available: {balance_actual} '
        f'{COIN_NAME}\n'
        f'{EMOJI_MONEYBAG} Pending: {balance_locked} '
        f'{COIN_NAME}\n'
        f'{get_notice_txt(COIN_NAME)}\n{ago}')
    await msg.add_reaction(EMOJI_OK_BOX)
    return

@bot.command(pass_context=True, aliases=['botbal'], help=bot_help_botbalance)
async def botbalance(ctx, member: discord.Member, coin: str):
    global TRTL_DISCORD

    # if public and there is a bot channel
    if isinstance(ctx.channel, discord.DMChannel) == False:
        serverinfo = get_info_pref_coin(ctx)
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
    if COIN_NAME not in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
        return

    # TRTL discord
    if ctx.guild.id == TRTL_DISCORD and COIN_NAME != "TRTL":
        return

    walletStatus = None
    if COIN_NAME in MAINTENANCE_COIN:
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return

    if COIN_NAME in ENABLE_COIN:
        walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
    elif COIN_NAME in ENABLE_COIN_DOGE:
        walletStatus = await daemonrpc_client.getDaemonRPCStatus(COIN_NAME)
    elif COIN_NAME in ENABLE_XMR:
        walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
        pass

    if (walletStatus is None) and COIN_NAME in (ENABLE_COIN+ENABLE_COIN_DOGE):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} I can not connect to wallet service or daemon.')
        return
    else:
        if COIN_NAME in ENABLE_COIN_DOGE:
            localDaemonBlockCount = int(walletStatus['blocks'])
            networkBlockCount = int(walletStatus['blocks'])
        elif COIN_NAME in ENABLE_COIN:
            localDaemonBlockCount = int(walletStatus['blockCount'])
            networkBlockCount = int(walletStatus['knownBlockCount'])
        if COIN_NAME in (ENABLE_COIN+ENABLE_COIN_DOGE) and (networkBlockCount - localDaemonBlockCount >= 100):
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


    # Bypass other if they re in ENABLE_COIN_DOGE
    if COIN_NAME in ENABLE_COIN_DOGE:
        try:
            depositAddress = await DOGE_LTC_getaccountaddress(str(member.id), COIN_NAME)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        actual = float(await DOGE_LTC_getbalance_acc(str(member.id), COIN_NAME, 6))
        locked = float(await DOGE_LTC_getbalance_acc(str(member.id), COIN_NAME, 1))
        userdata_balance = store.sql_doge_balance(str(member.id), COIN_NAME)
        if actual == locked:
            balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
            balance_locked = num_format_coin(0 , COIN_NAME)
        else:
            balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
            if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                balance_locked =  num_format_coin(0, COIN_NAME)
            else:
                balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
        msg = await ctx.send(
                f'**[ MY {COIN_NAME} BALANCE]**\n'
                f' Deposit Address: `{depositAddress}`\n'
                f'{EMOJI_MONEYBAG} Available: {balance_actual} '
                f'{COIN_NAME}\n'
                f'{EMOJI_MONEYBAG} Pending: {balance_locked} '
                f'{COIN_NAME}\n'
                '**This is bot\'s tipjar address. Do not deposit here unless you want to deposit to this bot.**')
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    # XMR family botbal
    elif COIN_NAME in ENABLE_XMR:
        wallet = await store.sql_get_userwallet(str(member.id), COIN_NAME)
        if wallet is None:
            userregister = await store.sql_register_user(str(member.id), COIN_NAME)
            wallet = await store.sql_get_userwallet(str(member.id), COIN_NAME)
        if wallet:
            actual = wallet['actual_balance'] if 'actual_balance' in wallet else 0
            locked = wallet['locked_balance'] if 'locked_balance' in wallet else 0
            userdata_balance = store.sql_xmr_balance(str(member.id), COIN_NAME)
            balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
            if actual == locked:
                balance_locked = num_format_coin(0, COIN_NAME)
            else:
                if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                    balance_locked =  num_format_coin(0, COIN_NAME)
                else:
                    balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
            depositAddress = wallet['balance_wallet_address']
            msg = await ctx.send(
                f'**[INFO BOT {member.name}\'s BALANCE]**\n\n'
                f' Deposit Address: `{depositAddress}`\n'
                f'{EMOJI_MONEYBAG} Available: {balance_actual} '
                f'{COIN_NAME}\n'
                f'{EMOJI_MONEYBAG} Pending: {balance_locked} '
                f'{COIN_NAME}\n'
                '**This is bot\'s tipjar address. Do not deposit here unless you want to deposit to this bot.**')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
    elif COIN_NAME in ENABLE_COIN:
        wallet = await store.sql_get_userwallet(str(member.id), COIN_NAME)
        if wallet is None:
            botregister = await store.sql_register_user(str(member.id), COIN_NAME)
            wallet = await store.sql_get_userwallet(str(member.id), COIN_NAME)
        balance_actual = num_format_coin(wallet['actual_balance'] , COIN_NAME)
        balance_locked = num_format_coin(wallet['locked_balance'] , COIN_NAME)
        depositAddress = wallet['balance_wallet_address']
        msg = await ctx.send(
            f'**[INFO BOT {member.name}\'s BALANCE]**\n\n'
            f' Deposit Address: `{depositAddress}`\n'
            f'{EMOJI_MONEYBAG} Available: {balance_actual} '
            f'{COIN_NAME}\n'
            f'{EMOJI_MONEYBAG} Pending: {balance_locked} '
            f'{COIN_NAME}\n'
            '**This is bot\'s tipjar address. Do not deposit here unless you want to deposit to this bot.**')
        await msg.add_reaction(EMOJI_OK_BOX)
        return


@bot.command(pass_context=True, name='forwardtip', aliases=['redirecttip'],
             help=bot_help_forwardtip)
async def forwardtip(ctx, coin: str, option: str):
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'forwardtip')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    # Check to test
    # if ctx.message.author.id not in MAINTENANCE_OWNER:
        # await ctx.message.add_reaction(EMOJI_WARNING)
        # await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Still under testing. Try again in the future.')
        # return
    # End Check
    COIN_NAME = coin.upper()
    coin_family = None
    try:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    if coin_family is None:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} We don\'t know that {COIN_NAME}')
        return

    if coin_family == "XMR":
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} this {COIN_NAME} is not supported with **forwardtip**.')
        return
    elif coin_family not in ["TRTL", "CCX"]:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Please use supported ticker: '+ ', '.join(ENABLE_COIN).lower())
        return
    elif option.upper() not in ["ON", "OFF"]:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Parameter must be: **ON** or **OFF**')
        return

    userwallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    if userwallet is None:
        userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME)
        userwallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)

    # Do not allow to ON if 'user_wallet_address' is None
    if (userwallet['user_wallet_address'] is None) and option.upper() == "ON":
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} You have\'t registered an address for **{COIN_NAME}**')
        return
    if userwallet['forwardtip'].upper() == option.upper():
        await ctx.message.add_reaction(EMOJI_WARNING)
        await ctx.send(f'{ctx.author.mention} You have this forwardtip already: **{option.upper()}**')
        return
    else:
        setforward = store.sql_set_forwardtip(str(ctx.message.author.id), COIN_NAME, option.upper())
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        await ctx.send(f'{ctx.author.mention} You set forwardtip of {COIN_NAME} to: **{option.upper()}**')
        return


@bot.command(pass_context=True, name='register', aliases=['registerwallet', 'reg', 'updatewallet'],
             help=bot_help_register)
async def register(ctx, wallet_address: str):
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
        serverinfo = get_info_pref_coin(ctx)
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

    if wallet_address.isalnum() == False:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                       f'`{wallet_address}`')
        return

    COIN_NAME = get_cn_coin_from_address(wallet_address)
    if COIN_NAME:
        pass
    else:
        await ctx.message.add_reaction(EMOJI_WARNING)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Unknown Ticker.')
        return

    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    if COIN_NAME in MAINTENANCE_COIN:
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return

    user = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    if user is None:
        userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME)
        user = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)

    existing_user = user

    valid_address = None
    if COIN_NAME in ENABLE_COIN_DOGE:
        depositAddress = await DOGE_LTC_getaccountaddress(str(ctx.message.author.id), COIN_NAME)
        user['balance_wallet_address'] = depositAddress
        if COIN_NAME == "DOGE":
            valid_address = await DOGE_LTC_validaddress(str(wallet_address), COIN_NAME)
            if ('isvalid' in valid_address):
                if str(valid_address['isvalid']) == "True":
                    valid_address = wallet_address
                else:
                    valid_address = None
                pass
            pass
    else:
        if coin_family == "TRTL" or coin_family == "CCX":
            valid_address = addressvalidation.validate_address_cn(wallet_address, COIN_NAME)
        elif coin_family == "XMR":
            if COIN_NAME != "MSR":
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
                valid_address = address_msr(wallet_address)
                if type(valid_address).__name__ != "Address":
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please use {COIN_NAME} main address.')
                    return
        else:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Unknown Ticker.')
            return
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
    if existing_user['user_wallet_address']:
        prev_address = existing_user['user_wallet_address']
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
    global WITHDRAW_IN_PROCESS
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'withdraw')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    botLogChan = bot.get_channel(id=LOG_CHAN)
    amount = amount.replace(",", "")

    # Check flood of tip
    floodTip = store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration)
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
        serverinfo = get_info_pref_coin(ctx)
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
        amount = float(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount.')
        return

    if coin is None:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please have **ticker** (coin name) after amount.')
        return

    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR:
        await ctx.message.add_reaction(EMOJI_WARNING)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Unknown Ticker.')
        return

    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    if COIN_NAME in MAINTENANCE_COIN:
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return

    if coin_family == "TRTL" or coin_family == "CCX":
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        user = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        NetFee = get_tx_fee(coin = COIN_NAME)
        if user['user_wallet_address'] is None:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You do not have a withdrawal address, please use '
                           f'`{server_prefix}register wallet_address` to register.')
            return

        if real_amount + NetFee >= user['actual_balance']:
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

        withdrawal = None
        try:
            withdrawal = await store.sql_withdraw(str(ctx.message.author.id), real_amount, COIN_NAME)
            tip_tx_tipper = "Transaction hash: `{}`".format(withdrawal)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        if withdrawal:
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
            await botLogChan.send(f'A user successfully executed `.withdraw {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`')
            await ctx.message.author.send(
                f'{EMOJI_ARROW_RIGHTHOOK} You have withdrawn {num_format_coin(real_amount, COIN_NAME)} '
                f'{COIN_NAME}.\n'
                f'{tip_tx_tipper}')
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await botLogChan.send(f'A user failed to execute `.withdraw {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`')
            await ctx.send(f'{ctx.author.mention} You may need to `optimize` or try again.')
            # add to failed tx table
            store.sql_add_failed_tx(COIN_NAME, str(ctx.message.author.id), ctx.message.author.name, real_amount, "WITHDRAW")
            return

    elif coin_family == "XMR":
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        userdata_balance = store.sql_xmr_balance(str(ctx.message.author.id), COIN_NAME)

        if user_from['user_wallet_address'] is None:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} You don\'t have {COIN_NAME} withdraw address.\n')
            return

        # If balance 0, no need to check anything
        if float(user_from['actual_balance']) + float(userdata_balance['Adjust']) <= 0:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please check your **{COIN_NAME}** balance.')
            return

        NetFee = await get_tx_fee_xmr(coin = COIN_NAME, amount = real_amount, to_address = user_from['user_wallet_address'])
        if NetFee is None:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Can not get fee from network for: '
                           f'{num_format_coin(real_amount, COIN_NAME)} '
                           f'{COIN_NAME}. Please try again later in a few minutes.')
            return
        if real_amount + NetFee > float(user_from['actual_balance']) + float(userdata_balance['Adjust']):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to withdraw '
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

        withdrawTx = None
        if user_from['user_wallet_address']:
            if ctx.message.author.id not in WITHDRAW_IN_PROCESS:
                WITHDRAW_IN_PROCESS.append(ctx.message.author.id)
                try:
                    withdrawTx = await store.sql_external_xmr_single(str(ctx.message.author.id), real_amount,
                                                                     user_from['user_wallet_address'],
                                                                     COIN_NAME, "WITHDRAW")
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                WITHDRAW_IN_PROCESS.remove(ctx.message.author.id)
            else:
                # reject and tell to wait
                msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You have another tx in process. Please wait it to finish. ')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} You don\'t have {COIN_NAME} withdraw address.\n')
            return
        if withdrawTx:
            withdrawTx_hash = withdrawTx['tx_hash']
            withdrawAddress = user_from['user_wallet_address']
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
            await ctx.message.author.send(
                                   f'{EMOJI_ARROW_RIGHTHOOK} You have withdrawn {num_format_coin(real_amount, COIN_NAME)} '
                                   f'{COIN_NAME} to `{withdrawAddress}`.\n'
                                   f'Transaction hash: `{withdrawTx_hash}`\n'
                                   'Network fee deducted from your account balance.')
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            return
        return

    elif COIN_NAME == "DOGE":
        MinTx = get_min_tx_amount(coin = COIN_NAME)
        MaxTX = get_max_tx_amount(coin = COIN_NAME)
        user_from = {}
        user_from['address'] = await DOGE_LTC_getaccountaddress(str(ctx.message.author.id), COIN_NAME)
        user_from['actual_balance'] = float(await DOGE_LTC_getbalance_acc(str(ctx.message.author.id), COIN_NAME, 6))
        real_amount = float(amount)
        userdata_balance = store.sql_doge_balance(str(ctx.message.author.id), COIN_NAME)
        NetFee = get_tx_fee(coin = COIN_NAME)
        if real_amount + NetFee > float(user_from['actual_balance']) + float(userdata_balance['Adjust']):
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
        wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        withdrawTx = None
        if ctx.message.author.id not in WITHDRAW_IN_PROCESS:
            WITHDRAW_IN_PROCESS.append(ctx.message.author.id)
            try:
                if wallet['user_wallet_address']:
                    withdrawTx = await store.sql_external_doge_single(str(ctx.message.author.id), real_amount,
                                                                      NetFee, wallet['user_wallet_address'],
                                                                      COIN_NAME, "WITHDRAW")
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            WITHDRAW_IN_PROCESS.remove(ctx.message.author.id)
        else:
            msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        if withdrawTx:
            withdrawAddress = wallet['user_wallet_address']
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
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


@bot.command(pass_context=True, help=bot_help_donate)
async def donate(ctx, amount: str, coin: str = None):
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'donate')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    botLogChan = bot.get_channel(id=LOG_CHAN)
    donate_msg = ''
    if amount.upper() == "LIST":
        # if .donate list
        donate_list = store.sql_get_donate_list()
        #print(donate_list)
        item_list = []
        for key, value in donate_list.items():
            if value:
                coin_value = num_format_coin(value, key.upper())+key.upper()
                item_list.append(coin_value)
        if len(item_list) > 0:
            msg_coins = ', '.join(item_list)
            await ctx.send(f'Thank you for checking. So far, we got donations:\n```{msg_coins}```')
        return

    amount = amount.replace(",", "")

    # Check flood of tip
    floodTip = store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration)
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
        amount = float(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    COIN_NAME = None
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
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if COIN_NAME in MAINTENANCE_COIN:
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} in maintenance.')
        return

    if coin_family == "TRTL" or coin_family == "CCX":
        CoinAddress = get_donate_address(COIN_NAME)
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        NetFee = get_tx_fee(coin = COIN_NAME)
        if real_amount + NetFee >= user_from['actual_balance']:
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

        tip = None
        try:
            tip = await store.sql_donate(str(ctx.message.author.id), CoinAddress, real_amount, COIN_NAME)
            tip_tx_tipper = "Transaction hash: `{}`".format(tip)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        if tip:
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
            await botLogChan.send(f'{EMOJI_MONEYFACE} TipBot got donation: {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}')
            await ctx.message.author.send(
                                   f'{EMOJI_MONEYFACE} TipBot got donation: {num_format_coin(real_amount, COIN_NAME)} '
                                   f'{COIN_NAME} '
                                   f'\n'
                                   f'Thank you.\n {tip_tx_tipper}')
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} TX failed. Thank you but you may need to `optimize` or try again later.')
            # add to failed tx table
            store.sql_add_failed_tx(COIN_NAME, str(ctx.message.author.id), ctx.message.author.name, real_amount, "DONATE")
            return

    elif coin_family == "XMR":
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        userdata_balance = store.sql_xmr_balance(str(ctx.message.author.id), COIN_NAME)
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

        donateTx = store.sql_mv_xmr_single(str(ctx.message.author.id), 
                                           get_donate_account_name(COIN_NAME), 
                                           real_amount, COIN_NAME, "DONATE")
        if donateTx:
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
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
    elif COIN_NAME == "DOGE":
        MinTx = config.daemonDOGE.min_mv_amount
        MaxTX = config.daemonDOGE.max_mv_amount
        user_from = {}
        user_from['address'] = await DOGE_LTC_getaccountaddress(str(ctx.message.author.id), COIN_NAME)
        user_from['actual_balance'] = float(await DOGE_LTC_getbalance_acc(str(ctx.message.author.id), COIN_NAME, 6))
        real_amount = float(amount)
        userdata_balance = store.sql_doge_balance(str(ctx.message.author.id), COIN_NAME)
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

        donateTx = store.sql_mv_doge_single(str(ctx.message.author.id), get_donate_account_name(COIN_NAME), real_amount,
                                            COIN_NAME, "DONATE")
        if donateTx:
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
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


@bot.command(pass_context=True, help=bot_help_take)
async def take(ctx):
    global FAUCET_COINS, FAUCET_MINMAX, TRTL_DISCORD, WITHDRAW_IN_PROCESS
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

    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send(f'{EMOJI_RED_NO} This command can not be in private.')
        return

    # Check if user guild member less than 15 online
    num_online = sum(member.status != "offline" and not member.bot for member in ctx.message.guild.members)
    if num_online <= 15:
        await ctx.message.add_reaction(EMOJI_ERROR)
        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} This command isn\'t available with this guild.')
        return

    # check if bot channel is set:
    serverinfo = store.sql_info_by_server(str(ctx.guild.id))
    if serverinfo['botchan']:
        try: 
            if ctx.channel.id != int(serverinfo['botchan']):
                await ctx.message.add_reaction(EMOJI_ERROR)
                botChan = bot.get_channel(id=int(serverinfo['botchan']))
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention}, {botChan.mention} is the bot channel!!!')
                return
        except ValueError:
            pass
    # end of bot channel check

    # check user claim:
    check_claimed = store.sql_faucet_checkuser(str(ctx.message.author.id))
    if check_claimed:
        # limit 12 hours
        if int(time.time()) - check_claimed['claimed_at'] <= 43200:
            remaining = await bot_faucet(ctx) or ''
            time_waiting = seconds_str(43200 - int(time.time()) + check_claimed['claimed_at'])
            number_user_claimed = '{:,.0f}'.format(store.sql_faucet_count_user(str(ctx.message.author.id)))
            total_claimed = '{:,.0f}'.format(store.sql_faucet_count_all())
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You just claimed within last 12h. '
                                 f'Waiting time {time_waiting} for next **take**. Faucet balance:\n```{remaining}```'
                                 f'Total user claims: **{total_claimed}** times. '
                                 f'You have claimed: **{number_user_claimed}** time(s). '
                                 f'Tip me if you want to feed these faucets.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

    COIN_NAME = random.choice(FAUCET_COINS)
    while COIN_NAME in MAINTENANCE_COIN:
        COIN_NAME = random.choice(FAUCET_COINS)

    has_forwardtip = None
    amount = random.randint(FAUCET_MINMAX[COIN_NAME][0], FAUCET_MINMAX[COIN_NAME][1])

    # faucet only TRTL for TRTL and /number of faucet coins
    if ctx.guild.id == TRTL_DISCORD:
        COIN_NAME = "TRTL"
        amount = random.randint(FAUCET_MINMAX[COIN_NAME][0], FAUCET_MINMAX[COIN_NAME][1])
        amount = amount / len(FAUCET_COINS) / 0.4
        # if TRTL got less than 1, give 1
        if amount < 1:
            amount = 1

    wallet = None
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family == "DOGE":
        amount = float(amount / 10)

    if coin_family == "TRTL" or coin_family == "CCX":
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        user_from = await store.sql_get_userwallet(str(bot.user.id), COIN_NAME)
        user_to = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        NetFee = get_tx_fee(coin = COIN_NAME)
        if user_to is None:
            userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME)
            user_to = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if user_to['forwardtip'] == "ON":
            has_forwardtip = True

        if real_amount + NetFee >= user_from['actual_balance']:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} Please try again later. Bot runs out of **{COIN_NAME}**')
            return
        
        tip = None
        if ctx.message.author.id not in WITHDRAW_IN_PROCESS:
            WITHDRAW_IN_PROCESS.append(ctx.message.author.id)
            try:
                tip = await store.sql_send_tip(str(bot.user.id), str(ctx.message.author.id), real_amount, 'FAUCET', COIN_NAME)
                tip_tx_tipper = "Transaction hash: `{}`".format(tip)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            WITHDRAW_IN_PROCESS.remove(ctx.message.author.id)
        else:
            msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        if tip:
            faucet_add = store.sql_faucet_add(str(ctx.message.author.id), str(ctx.guild.id), COIN_NAME, real_amount, COIN_DEC, tip)
            if has_forwardtip:
                await ctx.message.add_reaction(EMOJI_FORWARD)
            else:
                await ctx.message.add_reaction(get_emoji(COIN_NAME))
            msg = await ctx.send(f'{EMOJI_MONEYFACE} {ctx.author.mention} You got a random faucet {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}.\n'
                                 f'{tip_tx_tipper}')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        else:
            await ctx.send(f'{ctx.author.mention} Please try again later. Failed during executing tx **{COIN_NAME}**.')
            await ctx.message.add_reaction(EMOJI_ERROR)

    elif coin_family == "XMR":
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        user_from = await store.sql_get_userwallet(str(bot.user.id), COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        userdata_balance = store.sql_xmr_balance(str(bot.user.id), COIN_NAME)
        if real_amount > float(user_from['actual_balance']) + float(userdata_balance['Adjust']):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} Please try again later. Bot runs out of **{COIN_NAME}**')
            return
        user_to = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if user_to is None:
            userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME)
            user_to = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        tip = store.sql_mv_xmr_single(str(bot.user.id), str(ctx.message.author.id), real_amount, COIN_NAME, "FAUCET")
        if tip:
            faucet_add = store.sql_faucet_add(str(ctx.message.author.id), str(ctx.guild.id), COIN_NAME, real_amount, COIN_DEC)
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
            msg = await ctx.send(f'{EMOJI_MONEYFACE} {ctx.author.mention} You got a random faucet {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        else:
            await ctx.send(f'{ctx.author.mention} Please try again later. Failed during executing tx **{COIN_NAME}**.')
            await ctx.message.add_reaction(EMOJI_ERROR)
            return
    elif coin_family == "DOGE":
        COIN_DEC = 1
        real_amount = float(amount * COIN_DEC)
        user_from = {}
        user_from['actual_balance'] = float(await DOGE_LTC_getbalance_acc(str(bot.user.id), COIN_NAME, 6))
        botdata_balance = store.sql_doge_balance(str(bot.user.id), COIN_NAME)
        if real_amount > float(user_from['actual_balance']) + float(botdata_balance['Adjust']):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} Please try again later. Bot runs out of **{COIN_NAME}**')
            return
        tip = store.sql_mv_doge_single(str(bot.user.id), str(ctx.message.author.id), real_amount, COIN_NAME, "FAUCET")
        if tip:
            faucet_add = store.sql_faucet_add(str(ctx.message.author.id), str(ctx.guild.id), COIN_NAME, real_amount, COIN_DEC)
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
            msg = await ctx.send(f'{EMOJI_MONEYFACE} {ctx.author.mention} You got a random faucet {num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        else:
            await ctx.send(f'{ctx.author.mention} Please try again later. Failed during executing tx **{COIN_NAME}**.')
            await ctx.message.add_reaction(EMOJI_ERROR)
            return


@bot.command(pass_context=True, help=bot_help_tip)
async def tip(ctx, amount: str, *args):
    global TRTL_DISCORD
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'tip')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    # Check if user guild member less than 5 online
    num_online = sum(member.status != "offline" and not member.bot for member in ctx.message.guild.members)
    if num_online < 5:
        await ctx.message.add_reaction(EMOJI_ERROR)
        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} This command isn\'t available with this guild.')
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

    serverinfo = store.sql_info_by_server(str(ctx.guild.id))
    COIN_NAME = None
    try:
        COIN_NAME = args[0].upper()
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
    print("COIN_NAME: " + COIN_NAME)

    # TRTL discord
    if ctx.guild.id == TRTL_DISCORD and COIN_NAME != "TRTL":
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

    if COIN_NAME in MAINTENANCE_COIN:
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return

    if len(ctx.message.mentions) == 0 or (len(ctx.message.mentions) == 1 and (bot.user in ctx.message.mentions)):
        # Use how time.
        if len(args) >= 2:
            time_given = None
            if args[0].upper() == "LAST" or args[1].upper() == "LAST":
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

                    mult = {'y': 12*30*24*60*60, 'mon': 30*24*60*60, 'w': 7*24*60*60, 'd': 24*60*60, 'h': 60*60, 'mn': 60}
                    time_second = sum(int(num) * mult.get(val, 1) for num, val in re.findall('(\d+)(\w+)', time_string))
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
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
                        message_talker = store.sql_get_messages(str(ctx.message.guild.id), str(ctx.message.channel.id), time_given)
                        if len(message_talker) == 0:
                            await ctx.message.add_reaction(EMOJI_ERROR)
                            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is no active talker in such period.')
                            return
                        else:
                            #print(message_talker)
                            await _tip_talker(ctx, amount, message_talker, COIN_NAME)
                            return
            else:
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
                return
        else:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
            return
    elif len(ctx.message.mentions) == 1 and (bot.user not in ctx.message.mentions):
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
    floodTip = store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration)
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
    else:
        pass
    # End Check if maintenance

    notifyList = store.sql_get_tipnotify()
    has_forwardtip = None
    address_to = None

    if coin_family == "TRTL" or coin_family == "CCX":
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        user_to = await store.sql_get_userwallet(str(member.id), COIN_NAME)
        if user_to is None:
            userregister = await store.sql_register_user(str(member.id), COIN_NAME)
            user_to = await store.sql_get_userwallet(str(member.id), COIN_NAME)
        if user_to['forwardtip'] == "ON":
            has_forwardtip = True
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        NetFee = get_tx_fee(coin = COIN_NAME)
        if real_amount + NetFee >= user_from['actual_balance']:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send tip of '
                            f'{num_format_coin(real_amount, COIN_NAME)} '
                            f'{COIN_NAME} to {member.name}#{member.discriminator}.')
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
        # End of wallet status

        tip = None
        try:
            tip = await store.sql_send_tip(str(ctx.message.author.id), str(member.id), real_amount, 'TIP', COIN_NAME)
            tip_tx_tipper = "Transaction hash: `{}`".format(tip)
            if ctx.message.author.bot == False and serverinfo['react_tip'] == "ON":
                await ctx.message.add_reaction(EMOJI_TIP)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if tip:
            servername = serverinfo['servername']
            if has_forwardtip:
                await ctx.message.add_reaction(EMOJI_FORWARD)
            else:
                await ctx.message.add_reaction(get_emoji(COIN_NAME))
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Tip of {num_format_coin(real_amount, COIN_NAME)} '
                    f'{COIN_NAME} '
                    f'was sent to {member.name}#{member.discriminator} in server `{servername}`\n'
                    f'{tip_tx_tipper}')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            if str(member.id) not in notifyList:
                try:
                    await member.send(
                        f'{EMOJI_MONEYFACE} You got a tip of {num_format_coin(real_amount, COIN_NAME)} '
                        f'{COIN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{servername}`\n'
                        f'{tip_tx_tipper}\n'
                        f'{NOTIFICATION_OFF_CMD}')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    store.sql_toggle_tipnotify(str(member.id), "OFF")
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} Can not deliver TX for {COIN_NAME} right now. Try again soon.')
            # add to failed tx table
            store.sql_add_failed_tx(COIN_NAME, str(ctx.message.author.id), ctx.message.author.name, real_amount, "TIP")
            return

    elif coin_family == "XMR":
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        userdata_balance = store.sql_xmr_balance(str(ctx.message.author.id), COIN_NAME)
        if real_amount > float(user_from['actual_balance']) + float(userdata_balance['Adjust']):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send tip of '
                            f'{num_format_coin(real_amount, COIN_NAME)} '
                            f'{COIN_NAME} to {member.name}#{member.discriminator}.')
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
        tip = store.sql_mv_xmr_single(str(ctx.message.author.id), str(member.id), real_amount, COIN_NAME, "TIP")
        if tip:
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
            if ctx.message.author.bot == False and serverinfo['react_tip'] == "ON":
                await ctx.message.add_reaction(EMOJI_TIP)
            servername = serverinfo['servername']
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Tip of {num_format_coin(real_amount, COIN_NAME)} '
                    f'{COIN_NAME} '
                    f'was sent to {member.name}#{member.discriminator} in server `{servername}`\n')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            if str(member.id) not in notifyList:
                try:
                    await member.send(
                        f'{EMOJI_MONEYFACE} You got a tip of {num_format_coin(real_amount, COIN_NAME)} '
                        f'{COIN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{servername}`\n'
                        f'{NOTIFICATION_OFF_CMD}')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    store.sql_toggle_tipnotify(str(member.id), "OFF")
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
        return
    elif COIN_NAME == "DOGE":
        MinTx = config.daemonDOGE.min_mv_amount
        MaxTX = config.daemonDOGE.max_mv_amount
        user_from = {}
        user_from['address'] = await DOGE_LTC_getaccountaddress(str(ctx.message.author.id), COIN_NAME)
        user_from['actual_balance'] = float(await DOGE_LTC_getbalance_acc(str(ctx.message.author.id), COIN_NAME, 6))
        user_to = {}
        user_to['address'] = await DOGE_LTC_getaccountaddress(str(member.id), COIN_NAME)
        real_amount = float(amount)
        userdata_balance = store.sql_doge_balance(str(ctx.message.author.id), COIN_NAME)
        if real_amount > float(user_from['actual_balance']) + float(userdata_balance['Adjust']):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send tip of '
                            f'{num_format_coin(real_amount, COIN_NAME)} '
                            f'{COIN_NAME} to {member.name}#{member.discriminator}.')
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
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
            if ctx.message.author.bot == False and serverinfo['react_tip'] == "ON":
                await ctx.message.add_reaction(EMOJI_TIP)
            servername = serverinfo['servername']
            # tipper shall always get DM. Ignore notifyList
            try:
                if ctx.message.author.bot == False:
                    await ctx.message.author.send(
                        f'{EMOJI_ARROW_RIGHTHOOK} Tip of {num_format_coin(real_amount, COIN_NAME)} '
                        f'{COIN_NAME} '
                        f'was sent to {member.name}#{member.discriminator} in server `{servername}`\n')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            if str(member.id) not in notifyList:
                try:
                    await member.send(
                        f'{EMOJI_MONEYFACE} You got a tip of {num_format_coin(real_amount, COIN_NAME)} '
                        f'{COIN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{servername}`\n'
                        f'{NOTIFICATION_OFF_CMD}')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    store.sql_toggle_tipnotify(str(member.id), "OFF")
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
        return


@bot.command(pass_context=True, help=bot_help_tipall)
async def tipall(ctx, amount: str, *args):
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'tipall')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    # Check if user guild member less than 5 online
    num_online = sum(member.status != "offline" and not member.bot for member in ctx.message.guild.members)
    if num_online < 5:
        await ctx.message.add_reaction(EMOJI_ERROR)
        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} This command isn\'t available with this guild.')
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

    serverinfo = store.sql_info_by_server(str(ctx.guild.id))
    COIN_NAME = None
    if len(args) == 0:
        if 'default_coin' in serverinfo:
            COIN_NAME = serverinfo['default_coin'].upper()
        else:
            COIN_NAME = "WRKZ"
    else:
        COIN_NAME = args[0].upper()
        if COIN_NAME not in ENABLE_COIN+ENABLE_COIN_DOGE+ENABLE_XMR:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
            return

        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
        if coin_family not in ["TRTL", "XMR"]:
            if (args[0].upper() in ENABLE_COIN_DOGE):
                COIN_NAME = args[0].upper()
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
                return
        else:
            COIN_NAME = args[0].upper()
    print('TIPALL COIN_NAME:' + COIN_NAME)
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

    if COIN_NAME in MAINTENANCE_COIN:
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} in maintenance.')
        return

    # Check flood of tip
    floodTip = store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration)
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

    notifyList = store.sql_get_tipnotify()

    if coin_family == "TRTL" or coin_family == "CCX":
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        NetFee = get_tx_fee(coin = COIN_NAME)
        listMembers = [member for member in ctx.guild.members if member.status != "offline"]
        # Check number of receivers.
        if len(listMembers) > config.tipallMax:
            await ctx.message.add_reaction(EMOJI_ERROR)
            try:
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} The number of receivers are too many. This command isn\'t available here.')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await ctx.message.author.send(f'{EMOJI_RED_NO} The number of receivers are too many in `{ctx.guild.name}`. This command isn\'t available here.')
            return
        # End of checking receivers numbers.

        memids = []  # list of member ID
        has_forwardtip = None
        list_receivers = []
        addresses = []
        for member in listMembers:
            # print(member.name) # you'll just print out Member objects your way.
            if ctx.message.author.id != member.id:
                user_to = await store.sql_get_userwallet(str(member.id), COIN_NAME)
                if user_to is None:
                    userregister = await store.sql_register_user(str(member.id), COIN_NAME)
                    user_to = await store.sql_get_userwallet(str(member.id), COIN_NAME)
                if str(member.status) != 'offline':
                    if member.bot == False:
                        address_to = None
                        if user_to['forwardtip'] == "ON":
                            has_forwardtip = True
                            address_to = user_to['user_wallet_address']
                        else:
                            address_to = user_to['balance_wallet_address']
                            addresses.append(address_to)
                        if address_to:
                            list_receivers.append(str(member.id))
                            memids.append(address_to)

        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)

        if real_amount + NetFee >= user_from['actual_balance']:
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
        for desti in memids:
            destinations.append({"address": desti, "amount": amountDiv})

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
        # End of wallet status

        tip = None
        try:
            tip = await store.sql_send_tipall(str(ctx.message.author.id), destinations, real_amount, amountDiv, list_receivers, 'TIPALL', COIN_NAME)
            await store.sql_update_some_balances(addresses, COIN_NAME)
            ActualSpend = int(amountDiv * len(destinations) + NetFee)
            tip_tx_tipper = "Transaction hash: `{}`".format(tip)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if tip:
            servername = serverinfo['servername']
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
            if has_forwardtip:
                await ctx.message.add_reaction(EMOJI_FORWARD)
            TotalSpend = num_format_coin(real_amount, COIN_NAME)
            ActualSpend_str =  num_format_coin(ActualSpend, COIN_NAME)
            amountDiv_str = num_format_coin(amountDiv, COIN_NAME)
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Tip of {TotalSpend} '
                    f'{COIN_NAME} '
                    f'was sent spread to ({len(destinations)}) members in server `{servername}`.\n'
                    f'{tip_tx_tipper}\n'
                    f'Each member got: `{amountDiv_str}{COIN_NAME}`\n'
                    f'Actual spending: `{ActualSpend_str}{COIN_NAME}`')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
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
                                        f'{COIN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} `.tipall` in server `{servername}`\n'
                                        f'{tip_tx_tipper}\n'
                                        f'{NOTIFICATION_OFF_CMD}')
                                    numMsg = numMsg + 1
                                except (discord.Forbidden, discord.errors.Forbidden) as e:
                                    store.sql_toggle_tipnotify(str(member.id), "OFF")
            print('Messaged to users: (.tipall): '+str(numMsg))
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} Can not deliver TX for {COIN_NAME} right now. Try again soon.')
            # add to failed tx table
            store.sql_add_failed_tx(COIN_NAME, str(ctx.message.author.id), ctx.message.author.name, real_amount, "TIPALL")
            return

    elif coin_family == "XMR":
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        userdata_balance = store.sql_xmr_balance(str(ctx.message.author.id), COIN_NAME)
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

        listMembers = [member for member in ctx.guild.members if member.status != "offline"]
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
                if (str(member.status) != 'offline'):
                    if (member.bot == False):
                        memids.append(str(member.id))
        amountDiv = round(real_amount / len(memids), 4)
        if (real_amount / len(memids)) < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                           f'{num_format_coin(MinTx, COIN_NAME)} '
                           f'{COIN_NAME} for each member. You need at least {num_format_coin(len(memids) * MinTx, COIN_NAME)}.')
            return

        tips = store.sql_mv_xmr_multiple(str(ctx.message.author.id), memids, amountDiv, COIN_NAME, "TIPALL")
        if tips:
            servername = serverinfo['servername']
            tipAmount = num_format_coin(real_amount, COIN_NAME)
            ActualSpend_str = num_format_coin(amountDiv * len(memids), COIN_NAME)
            amountDiv_str = num_format_coin(amountDiv, COIN_NAME)
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Tip of {tipAmount} '
                    f'{COIN_NAME} '
                    f'was sent spread to ({len(memids)}) members in server `{servername}`.\n'
                    f'Each member got: `{amountDiv_str}{COIN_NAME}`\n'
                    f'Actual spending: `{ActualSpend_str}{COIN_NAME}`')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            for member in listMembers:
                if ctx.message.author.id != member.id:
                    if str(member.status) != 'offline':
                        if member.bot == False:
                            if str(member.id) not in notifyList:
                                try:
                                    await member.send(
                                        f'{EMOJI_MONEYFACE} You got a tip of {amountDiv_str} '
                                        f'{COIN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} `.tipall` in server `{servername}`\n'
                                        f'{NOTIFICATION_OFF_CMD}')
                                except (discord.Forbidden, discord.errors.Forbidden) as e:
                                    store.sql_toggle_tipnotify(str(member.id), "OFF")
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
        return
    elif COIN_NAME == "DOGE":
        MinTx = config.daemonDOGE.min_mv_amount
        MaxTX = config.daemonDOGE.max_mv_amount
        user_from = {}
        user_from['address'] = await DOGE_LTC_getaccountaddress(str(ctx.message.author.id), COIN_NAME)
        user_from['actual_balance'] = float(await DOGE_LTC_getbalance_acc(str(ctx.message.author.id), COIN_NAME, 6))
        real_amount = float(amount)
        userdata_balance = store.sql_doge_balance(str(ctx.message.author.id), COIN_NAME)
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

        listMembers = [member for member in ctx.guild.members if member.status != "offline"]
        # Check number of receivers.
        if len(listMembers) > config.tipallMax:
            await ctx.message.add_reaction(EMOJI_ERROR)
            try:
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} The number of receivers are too many. This command isn\'t available here.')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await ctx.message.author.send(f'{EMOJI_RED_NO} The number of receivers are too many in `{ctx.guild.name}`. This command isn\'t available here.')
            return
        # End of checking receivers numbers.

        memids = []  # list of member ID
        for member in listMembers:
            # print(member.name) # you'll just print out Member objects your way.
            if ctx.message.author.id != member.id:
                if (str(member.status) != 'offline'):
                    if (member.bot == False):
                        memids.append(str(member.id))
        amountDiv = round(real_amount / len(memids), 4)
        if (real_amount / len(memids)) < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                           f'{num_format_coin(MinTx, COIN_NAME)} '
                           f'{COIN_NAME} for each member. You need at least {num_format_coin(len(memids) * MinTx, COIN_NAME)}.')
            return

        tips = store.sql_mv_doge_multiple(str(ctx.message.author.id), memids, amountDiv, COIN_NAME, "TIPALL")
        if tips:
            servername = serverinfo['servername']
            tipAmount = num_format_coin(real_amount, COIN_NAME)
            ActualSpend_str = num_format_coin(amountDiv * len(memids), COIN_NAME)
            amountDiv_str = num_format_coin(amountDiv, COIN_NAME)
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Tip of {tipAmount} '
                    f'{COIN_NAME} '
                    f'was sent spread to ({len(memids)}) members in server `{servername}`.\n'
                    f'Each member got: `{amountDiv_str}{COIN_NAME}`\n'
                    f'Actual spending: `{ActualSpend_str}{COIN_NAME}`')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            for member in listMembers:
                if ctx.message.author.id != member.id:
                    if str(member.status) != 'offline':
                        if member.bot == False:
                            if str(member.id) not in notifyList:
                                try:
                                    await member.send(
                                        f'{EMOJI_MONEYFACE} You got a tip of {amountDiv_str} '
                                        f'{COIN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} `.tipall` in server `{servername}`\n'
                                        f'{NOTIFICATION_OFF_CMD}')
                                except (discord.Forbidden, discord.errors.Forbidden) as e:
                                    store.sql_toggle_tipnotify(str(member.id), "OFF")
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
        return


@bot.command(pass_context=True, help=bot_help_send)
async def send(ctx, amount: str, CoinAddress: str):
    global WITHDRAW_IN_PROCESS
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'send')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    botLogChan = bot.get_channel(id=LOG_CHAN)
    amount = amount.replace(",", "")

    # if public and there is a bot channel
    if isinstance(ctx.channel, discord.DMChannel) == False:
        serverinfo = get_info_pref_coin(ctx)
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
    floodTip = store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration)
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
        amount = float(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    # Check which coinname is it.
    COIN_NAME = get_cn_coin_from_address(CoinAddress)
    coin_family = None
    if COIN_NAME:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} could not find what address it is.')
        return

    if coin_family == "TRTL" or coin_family == "CCX":
        COIN_DEC = get_decimal(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        addressLength = get_addrlen(COIN_NAME)
        IntaddressLength = get_intaddrlen(COIN_NAME)
        NetFee = get_tx_fee(coin = COIN_NAME)
        if COIN_NAME in MAINTENANCE_COIN:
            await ctx.message.add_reaction(EMOJI_MAINTENANCE)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
            return

        print('{} - {} - {}'.format(COIN_NAME, addressLength, IntaddressLength))
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

        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        if user_from['balance_wallet_address'] == CoinAddress:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You can not send to your own deposit address.')
            return

        if real_amount + NetFee >= user_from['actual_balance']:
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

        if len(valid_address) == 2:
            tip = None
            try:
                tip = await store.sql_send_tip_Ex_id(str(ctx.message.author.id), CoinAddress, real_amount, paymentid, COIN_NAME)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            if tip:
                await ctx.message.add_reaction(get_emoji(COIN_NAME))
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
                tip = await store.sql_send_tip_Ex(str(ctx.message.author.id), CoinAddress, real_amount, COIN_NAME)
                tip_tx_hash = tip
                tip_tx_tipper = "Transaction hash: `{}`".format(tip)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
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
                store.sql_add_failed_tx(COIN_NAME, str(ctx.message.author.id), ctx.message.author.name, real_amount, "SEND")
                return
    elif coin_family == "XMR":
        COIN_DEC = get_decimal(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        addressLength = get_addrlen(COIN_NAME)
        IntaddressLength = get_intaddrlen(COIN_NAME)

        # If not Masari
        if COIN_NAME != "MSR":
            valid_address = await validate_address_xmr(str(CoinAddress), COIN_NAME)
            if valid_address['valid'] == False or valid_address['nettype'] != 'mainnet':
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Address: `{CoinAddress}` '
                                   'is invalid.')
                    return
        # OK valid address
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        userdata_balance = store.sql_xmr_balance(str(ctx.message.author.id), COIN_NAME)
        # If balance 0, no need to check anything
        if float(user_from['actual_balance']) + float(userdata_balance['Adjust']) <= 0:
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
        if real_amount + NetFee > float(user_from['actual_balance']) + float(userdata_balance['Adjust']):
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
        if ctx.message.author.id not in WITHDRAW_IN_PROCESS:
            WITHDRAW_IN_PROCESS.append(ctx.message.author.id)
            try:
                SendTx = await store.sql_external_xmr_single(str(ctx.message.author.id), real_amount,
                                                             CoinAddress, COIN_NAME, "SEND")
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            WITHDRAW_IN_PROCESS.remove(ctx.message.author.id)
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
    else:
        if COIN_NAME == "DOGE":
            addressLength = get_addrlen(coin = COIN_NAME)
            MinTx = get_min_tx_amount(coin = COIN_NAME)
            MaxTX = get_max_tx_amount(coin = COIN_NAME)
            NetFee = get_tx_fee(coin = COIN_NAME)
            valid_address = await DOGE_LTC_validaddress(str(CoinAddress), COIN_NAME)
            if 'isvalid' in valid_address:
                if str(valid_address['isvalid']) == "True":
                    pass
                else:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Address: `{CoinAddress}` '
                                    'is invalid.')
                    return

            user_from = {}
            user_from['address'] = await DOGE_LTC_getaccountaddress(str(ctx.message.author.id), COIN_NAME)
            user_from['actual_balance'] = float(await DOGE_LTC_getbalance_acc(str(ctx.message.author.id), COIN_NAME, 6))
            real_amount = float(amount)
            userdata_balance = store.sql_doge_balance(str(ctx.message.author.id), COIN_NAME)
            if real_amount + NetFee > float(user_from['actual_balance']) + float(userdata_balance['Adjust']):
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
            if ctx.message.author.id not in WITHDRAW_IN_PROCESS:
                WITHDRAW_IN_PROCESS.append(ctx.message.author.id)
                try:
                    SendTx = await store.sql_external_doge_single(str(ctx.message.author.id), real_amount, NetFee,
                                                                  CoinAddress, COIN_NAME, "SEND")
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                WITHDRAW_IN_PROCESS.remove(ctx.message.author.id)
            else:
                msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
            if SendTx:
                await ctx.message.add_reaction(get_emoji(COIN_NAME))
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


@bot.command(pass_context=True, name='address', aliases=['addr'], help=bot_help_address)
async def address(ctx, *args):
    global TRTL_DISCORD
    # TRTL discord
    if (isinstance(ctx.message.channel, discord.DMChannel) == False) and ctx.guild.id == TRTL_DISCORD:
        return

    # if public and there is a bot channel
    if isinstance(ctx.channel, discord.DMChannel) == False:
        serverinfo = get_info_pref_coin(ctx)
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
            serverinfo = store.sql_info_by_server(str(ctx.guild.id))
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
            print("COIN_NAME: " + COIN_NAME)
        # TODO: change this.
        donateAddress = get_donate_address(COIN_NAME) or 'WrkzRNDQDwFCBynKPc459v3LDa1gEGzG3j962tMUBko1fw9xgdaS9mNiGMgA9s1q7hS1Z8SGRVWzcGc8Sh8xsvfZ6u2wJEtoZB'
        await ctx.send('**[ ADDRESS CHECKING EXAMPLES ]**\n\n'
                       f'`.address {donateAddress}`\n'
                       'That will check if the address is valid. Integrated address is also supported. '
                       'If integrated address is input, bot will tell you the result of :address + paymentid\n\n'
                       '`.address <coin_address> <paymentid>`\n'
                       'This will generate an integrate address.\n\n'
                       f'If you would like to get your address, please use **info {COIN_NAME}** or **info TICKER** instead.')
        return

    # Check if a user request address coin of another user
    # .addr COIN @mention
    if len(args) == 2:
        COIN_NAME = None
        member = None
        try:
            COIN_NAME = args[0].upper()
            member = ctx.message.mentions[0]
            if COIN_NAME not in (ENABLE_COIN+ENABLE_XMR):
                COIN_NAME = None
        except Exception as e:
            pass
        if COIN_NAME and member:
            # OK there is COIN_NAME and member
            if member.id == ctx.message.author.id:
                await ctx.message.add_reaction(EMOJI_ERROR)
                return
            msg = await ctx.send(f'**ADDRESS REQ {COIN_NAME} **: {member.mention}, {str(ctx.author)} would like to get your address.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

    CoinAddress = args[0]
    COIN_NAME = None

    if CoinAddress.isalnum() == False:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                       f'`{CoinAddress}`')
        return
    # Check which coinname is it.
    COIN_NAME = get_cn_coin_from_address(CoinAddress)
    coin_family = None
    if COIN_NAME:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                       f'`{CoinAddress}`')
        return

    addressLength = get_addrlen(COIN_NAME)
    if coin_family == "TRTL" or coin_family == "CCX" or coin_family == "XMR":
        IntaddressLength = get_intaddrlen(COIN_NAME)

    if len(args) == 1:
        if COIN_NAME == "DOGE":
            valid_address = await DOGE_LTC_validaddress(str(CoinAddress), COIN_NAME)
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
            valid_address = await DOGE_LTC_validaddress(str(CoinAddress), COIN_NAME)
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
        elif COIN_NAME in ENABLE_XMR:
            if COIN_NAME == "MSR":
                addr = None
                if len(CoinAddress) == 95:
                    try:
                        addr = address_msr(CoinAddress)
                    except Exception as e:
                        # traceback.print_exc(file=sys.stdout)
                        pass
                elif len(CoinAddress) == 106:
                    addr = None
                    try:
                        addr = address_msr(CoinAddress)
                    except Exception as e:
                        # traceback.print_exc(file=sys.stdout)
                        pass
                # print(addr)
                # print(type(addr))
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
                    print(address_result)
                    await ctx.message.add_reaction(EMOJI_CHECK)
                    await ctx.send(f'{EMOJI_CHECK} Address: `{CoinAddress}`\n{address_result}')
                    return
                else:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} Address: `{CoinAddress}`\n'
                                    'Checked: Invalid.')
                    return
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


@bot.command(pass_context=True, name='optimize', aliases=['opt'], help=bot_help_optimize)
async def optimize(ctx, coin: str, member: discord.Member = None):
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'optimize')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

    botLogChan = bot.get_channel(id=LOG_CHAN)
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family != "TRTL":
        await ctx.message.add_reaction(EMOJI_WARNING)
        await ctx.send(f'{EMOJI_RED_NO} You need to specify a correct TICKER. Or {COIN_NAME} not optimizable.')
        return

    if member is None:
        # Check if in logchan
        if ctx.message.channel.id == LOG_CHAN and (ctx.message.author.id in MAINTENANCE_OWNER):
            wallet_to_opt = 5
            await botLogChan.send(f'OK, I will do some optimization for this `{COIN_NAME}`..')
            opt_numb = await store.sql_optimize_admin_do(COIN_NAME, wallet_to_opt)
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
            user_from = await store.sql_get_userwallet(member.mention, COIN_NAME)
            # let's optimize and set status
            CountOpt = await store.sql_optimize_do(str(member.id), COIN_NAME)
            await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
            if CountOpt > 0:
                await ctx.message.add_reaction(EMOJI_OK_HAND)
                await ctx.send(f'***Optimize*** is being processed for {member.name}#{member.discriminator} **{COIN_NAME}**. {CountOpt} fusion tx(s).')
                return
            else:
                await ctx.message.add_reaction(EMOJI_OK_HAND)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **{COIN_NAME}** No `optimize` is needed or wait for unlock.')
                return
        else:
            await ctx.message.add_reaction(EMOJI_WARNING)
            await ctx.send(f'{EMOJI_RED_NO} **{COIN_NAME}** You only need to optimize your own tip jar.')
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
    user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    if ('lastOptimize' in user_from) and user_from['lastOptimize']:
        if int(time.time()) - int(user_from['lastOptimize']) < int(get_interval_opt(COIN_NAME)):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} **{COIN_NAME}** {ctx.author.mention} Please wait. You just did `optimize` within last 10mn.')
            return
    if int(user_from['actual_balance']) / get_decimal(COIN_NAME) < int(get_min_opt(COIN_NAME)):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} **{COIN_NAME}** Your balance may not need to optimize yet. Check again later.')
        return
    else:
        # check if optimize has done for last 30mn
        # and if last 30mn more than 5 has been done in total
        try:
            countOptimize = store.sql_optimize_check(COIN_NAME)
            print('store.sql_optimize_check {} countOptimize: {}'.format(COIN_NAME, countOptimize))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            return
        if countOptimize >= 5:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(
                f'{EMOJI_RED_NO} {COIN_NAME} {ctx.author.mention} Please wait. There are a few `optimize` within last 10mn from other people.')
            return
        else:
            # let's optimize and set status
            CountOpt = await store.sql_optimize_do(str(ctx.message.author.id), COIN_NAME)
            if CountOpt > 0:
                await ctx.message.add_reaction(EMOJI_OK_HAND)
                await ctx.send(f'***Optimize*** {ctx.author.mention} {COIN_NAME} is being processed for your wallet. {CountOpt} fusion tx(s).')
                return
            else:
                await ctx.message.add_reaction(EMOJI_OK_HAND)
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
    
    COIN_NAME = coin.upper() or "WRKZ"
    if COIN_NAME in MAINTENANCE_COIN:
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return
    print('VOUCHER: '+COIN_NAME)

    COIN_DEC = get_decimal(COIN_NAME)
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
        logo = Image.open(get_coinlogo_path(COIN_NAME))
        box = (115,115,165,165)
        qr_img.crop(box)
        region = logo
        region = region.resize((box[2] - box[0], box[3] - box[1]))
        qr_img.paste(region,box)
        # qr_img.save(config.qrsettings.path_voucher_create + unique_filename + "_2.png")
    except Exception as e: 
        traceback.print_exc(file=sys.stdout)
    # Image Frame on which we want to paste 
    img_frame = Image.open(config.qrsettings.path_voucher_defaultimg)  
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

        myFont = ImageFont.truetype(config.font.digital7, 36)
        msg_claim = "SCAN TO CLAIM IT!"
        w, h = myFont.getsize(msg_claim)
        draw.text((280-w/2,275+125+h+60), msg_claim, fill="black",font=myFont)
    except Exception as e: 
        traceback.print_exc(file=sys.stdout)
    # Saved in the same relative location 
    img_frame.save(config.qrsettings.path_voucher_create + unique_filename + ".png") 

    voucher_make = None
    voucher_make = await store.sql_send_to_voucher(str(ctx.message.author.id), str(ctx.message.author.name), 
                                                   ctx.message.content, real_amount, get_reserved_fee(COIN_NAME), 
                                                   secret_string, unique_filename + ".png", COIN_NAME)
    if voucher_make:
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.message.author.send(f"New Voucher Link (TEST):\n```{qrstring}\n"
                                f"Amount: {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}\n"
                                f"Reserved Fee: {num_format_coin(get_reserved_fee(COIN_NAME), COIN_NAME)} {COIN_NAME}\n"
                                f"Tx Deposit: {voucher_make}```",
                                file=discord.File(config.qrsettings.path_voucher_create + unique_filename + ".png"))
        #os.remove(config.qrsettings.path_voucher_create + unique_filename + ".png")
        else:
            await ctx.message.channel.send(f"New Voucher Link (TEST):\n```{qrstring}\n"
                                f"Amount: {num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}\n"
                                f"Reserved Fee: {num_format_coin(get_reserved_fee(COIN_NAME), COIN_NAME)} {COIN_NAME}\n"
                                f"Tx Deposit: {voucher_make}```",
                                file=discord.File(config.qrsettings.path_voucher_create + unique_filename + ".png"))
        #os.remove(config.qrsettings.path_voucher_create + unique_filename + ".png")
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
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
    if (coin is None) and isinstance(ctx.message.channel, discord.DMChannel) == False:
        serverinfo = get_info_pref_coin(ctx)
        COIN_NAME = serverinfo['default_coin'].upper()
    elif (coin is None) and isinstance(ctx.message.channel, discord.DMChannel):
        COIN_NAME = "BOT"
    elif coin and isinstance(ctx.message.channel, discord.DMChannel) == False:
        serverinfo = get_info_pref_coin(ctx)
        COIN_NAME = coin.upper()
    elif coin:
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

    if (COIN_NAME not in (ENABLE_COIN+ENABLE_XMR)) and COIN_NAME != "BOT":
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Please put available ticker: '+ ', '.join(ENABLE_COIN).lower())
        return

    # TRTL discord
    if isinstance(ctx.message.channel, discord.DMChannel) == False and ctx.guild.id == TRTL_DISCORD and COIN_NAME != "TRTL":
        return

    if (COIN_NAME in MAINTENANCE_COIN) and (ctx.message.author.id not in MAINTENANCE_OWNER):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} in maintenance.')
        return
    elif (COIN_NAME in MAINTENANCE_COIN) and (ctx.message.author.id in MAINTENANCE_OWNER):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        pass

    if COIN_NAME == "BOT":
        await bot.wait_until_ready()
        get_all_m = bot.get_all_members()
        embed = discord.Embed(title="[ TIPBOT ]", description="Bot Stats", color=0xDEADBF)
        embed.set_author(name=bot.user.name, icon_url=bot.user.avatar_url)
        embed.add_field(name="Bot ID", value=str(bot.user.id), inline=True)
        embed.add_field(name="Guilds", value='{:,.0f}'.format(len(bot.guilds)), inline=True)
        embed.add_field(name="Shards", value='{:,.0f}'.format(bot.shard_count), inline=True)
        embed.add_field(name="Total Online", value='{:,.0f}'.format(sum(1 for m in get_all_m if str(m.status) != 'offline')), inline=True)
        embed.add_field(name="Unique user", value='{:,.0f}'.format(len(bot.users)), inline=True)
        embed.add_field(name="Channels", value='{:,.0f}'.format(sum(1 for g in bot.guilds for _ in g.channels)), inline=True)
        embed.set_footer(text='Please add ticker: '+ ', '.join(ENABLE_COIN).lower() + ' to get stats about coin instead.')
        await ctx.send(embed=embed)
        return

    gettopblock = None
    timeout = 30
    try:
        gettopblock = await daemonrpc_client.gettopblock(COIN_NAME, time_out=timeout)
    except asyncio.TimeoutError:
        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} connection to daemon timeout after {str(timeout)} seconds. I am checking info from wallet now.')
        await msg.add_reaction(EMOJI_OK_BOX)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    walletStatus = None
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family == "TRTL" or coin_family == "CCX":
        try:
            walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    elif coin_family == "XMR":
        try:
            walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    if gettopblock:
        COIN_DEC = get_decimal(COIN_NAME)
        COIN_DIFF = get_diff_target(COIN_NAME)
        blockfound = datetime.utcfromtimestamp(int(gettopblock['block_header']['timestamp'])).strftime("%Y-%m-%d %H:%M:%S")
        ago = str(timeago.format(blockfound, datetime.utcnow()))
        difficulty = "{:,}".format(gettopblock['block_header']['difficulty'])
        hashrate = str(hhashes(int(gettopblock['block_header']['difficulty']) / int(COIN_DIFF)))
        height = "{:,}".format(gettopblock['block_header']['height'])
        reward = "{:,}".format(int(gettopblock['block_header']['reward'])/int(COIN_DEC))

        blockfound = datetime.utcfromtimestamp(int(gettopblock['block_header']['timestamp'])).strftime("%Y-%m-%d %H:%M:%S")
        ago = str(timeago.format(blockfound, datetime.utcnow()))
        difficulty = "{:,}".format(gettopblock['block_header']['difficulty'])
        hashrate = str(hhashes(int(gettopblock['block_header']['difficulty']) / int(COIN_DIFF)))
        height = "{:,}".format(gettopblock['block_header']['height'])
        reward = "{:,}".format(int(gettopblock['block_header']['reward'])/int(COIN_DEC))

        if coin_family == "XMR":
            embed = discord.Embed(title=f"[ {COIN_NAME} ]", 
                                  description=f"Tip min/max: {num_format_coin(get_min_tx_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_tx_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}", 
                                  timestamp=datetime.utcnow(), color=0xDEADBF)
            embed.set_author(name=bot.user.name, icon_url=bot.user.avatar_url)
            embed.add_field(name="NET HEIGHT", value=str(height), inline=True)
            embed.add_field(name="FOUND", value=ago, inline=True)
            embed.add_field(name="DIFFICULTY", value=difficulty, inline=True)
            embed.add_field(name="BLOCK REWARD", value=f'{reward}{COIN_NAME}', inline=True)
            embed.add_field(name="NETWORK HASH", value=hashrate, inline=True)
            if walletStatus:
                t_percent = '{:,.2f}'.format(truncate((walletStatus['height'] - 1)/gettopblock['block_header']['height']*100,2))
                embed.add_field(name="WALLET SYNC %", value=t_percent + '% (' + '{:,.0f}'.format(walletStatus['height'] - 1) + ')', inline=True)
            if NOTICE_COIN[COIN_NAME]:
                notice_txt = NOTICE_COIN[COIN_NAME]
            else:
                notice_txt = NOTICE_COIN['default']
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
                               f'[NETWORK HASH]   {hashrate}\n'
                               f'[TIP Min/Max]    {num_format_coin(get_min_tx_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_tx_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}\n'
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
            embed = discord.Embed(title=f"[ {COIN_NAME} ]", 
                                  description=f"Tip min/max: {num_format_coin(get_min_tx_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_tx_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}", 
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
                                   f'[TIP Min/Max]    {num_format_coin(get_min_tx_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_tx_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}\n'
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
                                   f'[TIP Min/Max]    {num_format_coin(get_min_tx_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_tx_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}\n'
                                   '```')
                await msg.add_reaction(EMOJI_OK_BOX)
            return
    else:
        if gettopblock is None and coin_family == "TRTL" and walletStatus:
            localDaemonBlockCount = int(walletStatus['blockCount'])
            networkBlockCount = int(walletStatus['knownBlockCount'])
            t_percent = '{:,.2f}'.format(truncate((localDaemonBlockCount - 1)/networkBlockCount*100,2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            if COIN_NAME in WALLET_API_COIN:
                walletBalance = await walletapi.walletapi_get_sum_balances(COIN_NAME)    
            else:
                walletBalance = await get_sum_balances(COIN_NAME)          
            embed = discord.Embed(title=f"[ {COIN_NAME} ]", 
                                  description=f"Tip min/max: {num_format_coin(get_min_tx_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_tx_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}", 
                                  timestamp=datetime.utcnow(), color=0xDEADBF)
            embed.set_author(name=bot.user.name, icon_url=bot.user.avatar_url)
            embed.add_field(name="LOCAL DAEMON", value=str(t_localDaemonBlockCount), inline=True)
            embed.add_field(name="NETWORK", value=str(t_networkBlockCount), inline=True)
            embed.add_field(name="WALLET SYNC %", value=t_percent + '% (' + '{:,.0f}'.format(localDaemonBlockCount - 1) + ')', inline=True)
            embed.add_field(name="TOTAL UNLOCKED", value=num_format_coin(walletBalance['unlocked'], COIN_NAME) + COIN_NAME, inline=True)
            embed.add_field(name="TOTAL LOCKED", value=num_format_coin(walletBalance['locked'], COIN_NAME) + COIN_NAME, inline=True)
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
                                   f'[TIP Min/Max]    {num_format_coin(get_min_tx_amount(COIN_NAME), COIN_NAME)}-{num_format_coin(get_max_tx_amount(COIN_NAME), COIN_NAME)}{COIN_NAME}\n'
                                   f'{balance_str}'
                                   '```'
                                   )
                await msg.add_reaction(EMOJI_OK_BOX)
            return
        else:
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME}\'s status unavailable.')
            await msg.add_reaction(EMOJI_OK_BOX)
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
            serverinfo = store.sql_info_by_server(str(ctx.guild.id))
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
        msg = await ctx.send(f'{ctx.author.mention} Please put available ticker: '+ ', '.join(ENABLE_COIN).lower())
        return
    elif COIN_NAME in MAINTENANCE_COIN:
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
        traceback.print_exc(file=sys.stdout)

    if gettopblock:
        height = ""
        if coin_family == "TRTL" or coin_family == "CCX" or coin_family == "XMR":
            height = "{:,}".format(gettopblock['block_header']['height'])
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
        server_reacttip = "OFF"
    else:
        servername = serverinfo['servername']
        server_id = str(ctx.guild.id)
        server_prefix = serverinfo['prefix']
        server_coin = serverinfo['default_coin'].upper()
        server_reacttip = serverinfo['react_tip'].upper()
    if len(args) == 0:
        msg = await ctx.send('**Available param:** to change prefix, default coin, others in your server:\n```'
                       f'{server_prefix}setting prefix .|?|*|!\n\n'
                       f'{server_prefix}setting default_coin {tickers}\n\n'
                       f'{server_prefix}setting tiponly coin1 coin2 .. \n\n'
                       f'{server_prefix}setting ignorechan (no param, ignore tipping function in said channel)\n\n'
                       f'{server_prefix}setting del_ignorechan (no param, delete ignored tipping function in said channel)\n\n'
                       '```\n\n')
        await msg.add_reaction(EMOJI_OK_BOX)
        return
    elif len(args) == 1:
        if args[0].upper() == "TIPONLY":
            await ctx.send(f'{ctx.author.mention} Please tell what coins to be allowed here. Separated by space.')
            return
        elif args[0].upper() == "IGNORE_CHAN" or args[0].upper() == "IGNORECHAN":
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
        elif args[0].upper() == "BOTCHAN" or args[0].upper() == "BOTCHANNEL" or args[0].upper() == "BOT_CHAN":
            # botChan = ctx.channel.id
            # check if bot channel exists,
            if serverinfo['botchan']:
                try: 
                    if ctx.channel.id == int(serverinfo['botchan']):
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.channel.name} is already the bot channel here!')
                        return
                    else:
                        # change channel info
                        changeinfo = store.sql_changeinfo_by_server(str(ctx.guild.id), 'botchan', str(ctx.channel.id))
                        await ctx.send(f'Bot channel has set to {ctx.channel.mention}.')
                        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} change bot channel {ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}.')
                        return
                except ValueError:
                    return
            else:
                # change channel info
                changeinfo = store.sql_changeinfo_by_server(str(ctx.guild.id), 'botchan', str(ctx.channel.id))
                await ctx.send(f'Bot channel has set to {ctx.channel.mention}.')
                await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} changed bot channel {ctx.guild.name} / {ctx.guild.id} to #{ctx.channel.name}.')
                return
    elif len(args) == 2:
        if args[0].upper() == "TIPONLY":
            if (args[1].upper() not in (ENABLE_COIN+ENABLE_COIN_DOGE)) and (args[1].upper() != "ALLCOIN"):
                await ctx.send(f'{ctx.author.mention} {args[1].upper()} is not in any known coin we set.')
                return
            else:
                changeinfo = store.sql_changeinfo_by_server(str(ctx.guild.id), 'tiponly', args[1].upper())
                if args[1].upper() == "ALLCOIN":
                    await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} changed tiponly in {ctx.guild.name} / {ctx.guild.id} to `{args[1].upper()}`')
                    await ctx.send(f'{ctx.author.mention} {args[1].upper()} is allowed here.')
                else:
                    await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} changed tiponly in {ctx.guild.name} / {ctx.guild.id} to `{args[1].upper()}`')
                    await ctx.send(f'{ctx.author.mention} {args[1].upper()} will be the only tip here.')
                return
        elif args[0].upper() == "PREFIX":
            if args[1] not in [".", "?", "*", "!", "$", "~"]:
                await ctx.send('Invalid prefix')
                return
            else:
                if server_prefix == args[1]:
                    await ctx.send(f'{ctx.author.mention} That\'s the default prefix. Nothing changed.')
                    return
                else:
                    changeinfo = store.sql_changeinfo_by_server(str(ctx.guild.id), 'prefix', args[1].lower())
                    await ctx.send(f'{ctx.author.mention} Prefix changed from `{server_prefix}` to `{args[1].lower()}`.')
                    await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} changed prefix in {ctx.guild.name} / {ctx.guild.id} to `{args[1].lower()}`')
                    return
        elif args[0].upper() == "DEFAULT_COIN" or args[0].upper() == "DEFAULTCOIN" or args[0].upper() == "COIN":
            if args[1].upper() not in (ENABLE_COIN + ENABLE_XMR):
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
                return
            else:
                if server_coin.upper() == args[1].upper():
                    await ctx.send(f'{ctx.author.mention} That\'s the default coin. Nothing changed.')
                    return
                else:
                    changeinfo = store.sql_changeinfo_by_server(str(ctx.guild.id), 'default_coin', args[1].upper())
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
                    changeinfo = store.sql_changeinfo_by_server(str(ctx.guild.id), 'react_tip', args[1].upper())
                    await ctx.send(f'React Tip changed from `{server_reacttip}` to `{args[1].upper()}`.')
                    return
        elif args[0].upper() == "REACTAMOUNT" or args[0].upper() == "REACTTIP-AMOUNT":
            amount = args[1].replace(",", "")
            try:
                amount = float(amount)
            except ValueError:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
                return
            changeinfo = store.sql_changeinfo_by_server(str(ctx.guild.id), 'react_tip_100', amount)
            await ctx.send(f'React tip amount updated to to `{amount}{server_coin}`.')
            return
        else:
            await ctx.send(f'{ctx.author.mention} Invalid command input and parameter.')
            return
    else:
        if args[0].upper() == "TIPONLY":
            # if nothing given after TIPONLY
            if len(args) == 1:
                await ctx.send(f'{ctx.author.mention} Please tell what coins to be allowed here. Separated by space.')
                return
            if args[1].upper() == "ALLCOIN":
                changeinfo = store.sql_changeinfo_by_server(str(ctx.guild.id), 'tiponly', args[1].upper())
                await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} changed tiponly in {ctx.guild.name} / {ctx.guild.id} to `ALLCOIN`')
                await ctx.send(f'{ctx.author.mention} all coins will be allowed in here.')
                return
            else:
                coins = list(args)
                del coins[0]  # del TIPONLY
                contained = [x.upper() for x in coins if x.upper() in (ENABLE_COIN+ENABLE_COIN_DOGE)]
                if len(contained) == 0:
                    await ctx.send(f'{ctx.author.mention} No known coin. TIPONLY is remained unchanged.')
                    return
                else:
                    tiponly_value = ','.join(contained)
                    await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} changed tiponly in {ctx.guild.name} / {ctx.guild.id} to `{tiponly_value}`')
                    await ctx.send(f'{ctx.author.mention} TIPONLY set to: {tiponly_value}.')
                    changeinfo = store.sql_changeinfo_by_server(str(ctx.guild.id), 'tiponly', tiponly_value.upper())
                    return
        await ctx.send(f'{ctx.author.mention} In valid command input and parameter.')
        return

@bot.command(pass_context=True, name='addressqr', aliases=['qr', 'showqr'], help=bot_help_address_qr, hidden = True)
async def addressqr(ctx, *args):
    global TRTL_DISCORD
    # TRTL discord
    if (isinstance(ctx.message.channel, discord.DMChannel) == False) and ctx.guild.id == TRTL_DISCORD:
        return

    # Check if address is valid first
    if len(args) == 0:
        COIN_NAME = 'WRKZ'
        if isinstance(ctx.message.channel, discord.DMChannel):
            COIN_NAME = 'WRKZ'
        else:
            serverinfo = store.sql_info_by_server(str(ctx.guild.id))
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
            print("COIN_NAME: " + COIN_NAME)
        # TODO: change this.
        donateAddress = get_donate_address(COIN_NAME) or 'WrkzRNDQDwFCBynKPc459v3LDa1gEGzG3j962tMUBko1fw9xgdaS9mNiGMgA9s1q7hS1Z8SGRVWzcGc8Sh8xsvfZ6u2wJEtoZB'
        await ctx.send('**[ QR ADDRESS EXAMPLES ]**\n\n'
                       f'```.qr {donateAddress}\n'
                       'This will generate a QR address.'
                       '```\n\n')
        return

    CoinAddress = args[0]
    # Check which coinname is it.
    COIN_NAME = get_cn_coin_from_address(CoinAddress)
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if COIN_NAME:
        addressLength = get_addrlen(COIN_NAME)
        if coin_family == "TRTL" or coin_family == "CCX" or coin_family == "XMR":
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
    await ctx.message.add_reaction(EMOJI_OK_HAND)
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
    global TRTL_DISCORD
    # TRTL discord
    if (isinstance(ctx.message.channel, discord.DMChannel) == False) and ctx.guild.id == TRTL_DISCORD:
        return

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
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if COIN_NAME:
        addressLength = get_addrlen(COIN_NAME)
        if coin_family == "TRTL" or coin_family == "CCX" or coin_family == "XMR":
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
    await ctx.message.add_reaction(EMOJI_OK_HAND)
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


@bot.command(pass_context=True, help=bot_help_disclaimer)
async def disclaimer(ctx, *args):
    global DISCLAIM_MSG
    await ctx.send(f'{EMOJI_INFORMATION} **THANK YOU FOR USING** {DISCLAIM_MSG_LONG}')
    return


@bot.command(pass_context=True, help=bot_help_itag, hidden = True)
async def itag(ctx, *, itag_text: str = None):
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send(f'{EMOJI_RED_NO} This command can not be in private.')
        return
    ListiTag = store.sql_itag_by_server(str(ctx.guild.id))
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
                TagIt = store.sql_itag_by_server(str(ctx.guild.id), command_del[1].upper())
                if command_del[0].upper() == "-DEL" and TagIt:
                    # check permission if there is attachment with .itag
                    if ctx.author.guild_permissions.manage_guild == False:
                        await message.add_reaction(EMOJI_ERROR) 
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **itag** Permission denied.')
                        return
                    else:
                        DeliTag = store.sql_itag_by_server_del(str(ctx.guild.id), command_del[1].upper())
                        if DeliTag:
                            await ctx.send(f'{ctx.author.mention} iTag **{command_del[1].upper()}** deleted.\n')
                        else:
                            await ctx.send(f'{ctx.author.mention} iTag **{command_del[1].upper()}** error deletion.\n')
                        return
                else:
                    await ctx.send(f'{ctx.author.mention} iTag unknow operation.\n')
                    return
            elif len(command_del) == 1:
                TagIt = store.sql_itag_by_server(str(ctx.guild.id), itag_text.upper())
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
    if not (attachment.filename.lower()).endswith(('.gif', '.jpeg', '.jpg', '.png')):
        await ctx.send(f'{EMOJI_RED_NO} Attachment type rejected.')
        return
    else:
        print('Filename: {}'.format(attachment.filename))
    if attachment.size >= config.itag.max_size:
        await ctx.send(f'{EMOJI_RED_NO} File too big.')
        return
    else:
        print('Size: {}'.format(attachment.size))
    
    if re.match('^[a-zA-Z0-9]+(-[a-zA-Z0-9]+)*$', itag_text):
        if len(itag_text) >= 16:
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
                        if resp.headers["Content-Type"] not in ["image/gif", "image/png", "image/jpeg", "image/jpg"]:
                            await ctx.send(f'{EMOJI_RED_NO} Unsupported format file.')
                            return
                        else: 
                            with open(config.itag.path + attach_save_name, 'wb') as f:
                                f.write(await resp.read())
                            # save to DB and inform
                            addiTag = store.sql_itag_by_server_add(str(ctx.guild.id), itag_text.upper(),
                                                                  str(ctx.message.author), str(ctx.message.author.id),
                                                                  attachment.filename, attach_save_name, attachment.size)
                            if addiTag is None:
                                await ctx.send(f'{ctx.author.mention} Failed to add itag **{itag_text}**')
                                return
                            elif addiTag.upper() == itag_text.upper():
                                await ctx.send(f'{ctx.author.mention} Successfully added itag **{itag_text}**')
                                return
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


@bot.command(pass_context=True, help=bot_help_tag)
async def tag(ctx, *args):
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send(f'{EMOJI_RED_NO} This command can not be in private.')
        return

    ListTag = store.sql_tag_by_server(str(ctx.guild.id))

    if len(args) == 0:
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
            if len(ListTag) > 0:
                d = [i['tag_id'] for i in ListTag]
                if tag.upper() in d:
                    await ctx.send(f'Tag **{args[1]}** already exists here.')
                    return
            addTag = store.sql_tag_by_server_add(str(ctx.guild.id), tag.strip(), tagDesc.strip(),
                                                 ctx.message.author.name, str(ctx.message.author.id))
            if addTag is None:
                await ctx.send(f'Failed to add tag **{args[1]}**')
                return
            if addTag.upper() == tag.upper():
                await ctx.send(f'Successfully added tag **{args[1]}**')
                return
            else:
                await ctx.send(f'Failed to add tag **{args[1]}**')
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


async def alert_if_userlock(ctx, cmd: str):
    botLogChan = bot.get_channel(id=LOG_CHAN)
    get_discord_userinfo = None
    try:
        get_discord_userinfo = store.sql_discord_userinfo_get(str(ctx.message.author.id))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    if get_discord_userinfo is None:
        return None
    else:
        if get_discord_userinfo['locked'].upper() == "YES":
            await botLogChan.send(f'{ctx.message.author.name}#{ctx.message.author.discriminator} locked but is commanding `{cmd}`')
            return True
        else:
            return None


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
    elif CoinAddress.startswith("btcm"):
        COIN_NAME = "BTCMZ"
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
        COIN_NAME = "NBXC"
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
        # Try XMR
        try:
            addr = address_xmr(CoinAddress)
            COIN_NAME = "XMR"
            return COIN_NAME
        except Exception as e:
            # traceback.print_exc(file=sys.stdout)
            pass
    elif CoinAddress.startswith("L") and (len(CoinAddress) == 95 or len(CoinAddress) == 106):
        COIN_NAME = "LOKI"
    elif CoinAddress.startswith("T") and (len(CoinAddress) == 97 or len(CoinAddress) == 98 or len(CoinAddress) == 109):
        COIN_NAME = "XEQ"
    elif CoinAddress.startswith("cms") and (len(CoinAddress) == 98 or len(CoinAddress) == 109):
        COIN_NAME = "BLOG"
    elif (CoinAddress.startswith("ar") or CoinAddress.startswith("aR")) and (len(CoinAddress) == 97 or len(CoinAddress) == 98 or len(CoinAddress) == 109):
        COIN_NAME = "ARQ"
    elif (CoinAddress.startswith("5") or CoinAddress.startswith("9")) and (len(CoinAddress) == 95 or len(CoinAddress) == 106):
        COIN_NAME = "MSR"
    elif CoinAddress.startswith("D") and len(CoinAddress) == 34:
        COIN_NAME = "DOGE"
    # elif (CoinAddress[0] in ["3", "M", "L"]) and (len(CoinAddress) == 34:
        # COIN_NAME = "LTC"
    print('get_cn_coin_from_address return: ')
    print(COIN_NAME)
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
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Looks like you don\'t have the permission.')


@register.error
async def register_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing your wallet address. '
                       'You need to have a supported coin **address** after `register` command')
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


@account.error
@secrettip.error
async def account_secrettip_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing argument(s). Type .help acc secrettip')
    return


@info.error
async def info_error(ctx, error):
    pass


@balance.error
async def balance_error(ctx, error):
    pass


@botbalance.error
async def botbalance_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing Bot and/or ticker. '
                       'You need to @mention_bot COIN.')
    return


@forwardtip.error
async def forwardtip_error(ctx, error):
    pass


@withdraw.error
async def withdraw_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing amount and/or ticker. '
                       'You need to tell me **AMOUNT** and/or **TICKER**.')
    return


@tip.error
async def tip_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing arguments. '
                       'You need to tell me **amount** and who you want to tip to.')
    return


@donate.error
async def donate_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing arguments. '
                       'You need to tell me **amount** and ticker.\n'
                       f'Example: <@{bot.user.id}> `donate 1,000 [ticker]`\n'
                       f'Get donation list we received: <@{bot.user.id}> `donate list`')
    return


@tipall.error
async def tipall_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing argument. '
                       'You need to tell me **amount**')
    return


@send.error
async def send_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing arguments. '
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
            store.sql_updatestat_by_server(str(g.id), num_user, num_bot, num_channel, num_online)
        await asyncio.sleep(60)


async def saving_wallet():
    global LOG_CHAN
    saving = False
    await bot.wait_until_ready()
    botLogChan = bot.get_channel(id=LOG_CHAN)
    while not bot.is_closed():
        # We use in background bot_sql_update_balances.py
        # await asyncio.sleep(15)
        # store.sql_update_balances("TRTL")
        # await asyncio.sleep(20)
        # store.sql_update_balances("WRKZ")
        while botLogChan is None:
            botLogChan = bot.get_channel(id=LOG_CHAN)
            await asyncio.sleep(10)
        COIN_SAVING = ENABLE_COIN + ENABLE_XMR
        for COIN_NAME in COIN_SAVING:
            if (COIN_NAME in MAINTENANCE_COIN) or COIN_NAME in ["CCX", "ANX"]:
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
                    traceback.print_exc(file=sys.stdout)
                if duration:
                    if duration > 5:
                        await botLogChan.send(f'INFO: AUTOSAVE FOR **{COIN_NAME}** TOOK **{round(duration, 3)}s**.')
                    else:
                        print(f'INFO: AUTOSAVE FOR **{COIN_NAME}** TOOK **{round(duration, 3)}s**.')
                else:
                    await botLogChan.send(f'WARNING: AUTOSAVE FOR **{COIN_NAME}** FAILED.')
                saving = False
            await asyncio.sleep(300)
        await asyncio.sleep(config.wallet_balance_update_interval)


# Multiple tip
async def _tip(ctx, amount, coin: str):
    serverinfo = store.sql_info_by_server(str(ctx.guild.id))
    COIN_NAME = coin.upper()

    notifyList = store.sql_get_tipnotify()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family == "TRTL" or coin_family == "CCX":
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(round(float(amount) * COIN_DEC))
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        NetFee = get_tx_fee(coin = COIN_NAME)
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)

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
        has_forwardtip = None
        list_receivers = []
        addresses = []
        for member in listMembers:
            # print(member.name) # you'll just print out Member objects your way.
            if ctx.message.author.id != member.id:
                user_to = await store.sql_get_userwallet(str(member.id), COIN_NAME)
                if user_to is None:
                    userregister = await store.sql_register_user(str(member.id), COIN_NAME)
                    user_to = await store.sql_get_userwallet(str(member.id), COIN_NAME)
                address_to = None
                if user_to['forwardtip'] == "ON":
                    address_to = user_to['user_wallet_address']
                    has_forwardtip = True
                else:
                    address_to = user_to['balance_wallet_address']
                    addresses.append(address_to)
                if address_to:
                    list_receivers.append(str(member.id))
                    memids.append(address_to)

        for desti in memids:
            destinations.append({"address": desti, "amount": real_amount})

        ActualSpend = real_amount * len(memids) + NetFee
        if ActualSpend >= user_from['actual_balance']:
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
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} Wallet service hasn\'t sync fully with network or being '
                               're-sync. More info:\n```'
                               f'networkBlockCount:     {t_networkBlockCount}\n'
                               f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                               f'Progress %:            {t_percent}\n```'
                               )
                return
        # End of wallet status
        tip = None
        try:
            tip = await store.sql_send_tipall(str(ctx.message.author.id), destinations, real_amount, real_amount, list_receivers, 'TIPS', COIN_NAME)
            tip_tx_tipper = "Transaction hash: `{}`".format(tip)
            if ctx.message.author.bot == False and serverinfo['react_tip'] == "ON":
                await ctx.message.add_reaction(EMOJI_TIP)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if tip:
            servername = serverinfo['servername']
            try:
                await store.sql_update_some_balances(addresses, COIN_NAME)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
            if has_forwardtip:
                await ctx.message.add_reaction(EMOJI_FORWARD)
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(f'{EMOJI_ARROW_RIGHTHOOK} Total tip of {num_format_coin(ActualSpend, COIN_NAME)} '
                                        f'{COIN_NAME} '
                                        f'was sent to ({len(destinations)}) members in server `{servername}`.\n'
                                        f'{tip_tx_tipper}\n'
                                        f'Each: `{num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`'
                                        f'Total spending: `{num_format_coin(ActualSpend, COIN_NAME)} {COIN_NAME}`')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            for member in ctx.message.mentions:
                if ctx.message.author.id != member.id:
                    if member.bot == False:
                        if str(member.id) not in notifyList:
                            try:
                                await member.send(f'{EMOJI_MONEYFACE} You got a tip of  {num_format_coin(real_amount, COIN_NAME)} '
                                                f'{COIN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{servername}`\n'
                                                f'{tip_tx_tipper}\n'
                                                f'{NOTIFICATION_OFF_CMD}')
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                store.sql_toggle_tipnotify(str(member.id), "OFF")
                            pass
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You may need to `optimize` or try again.')
            # add to failed tx table
            store.sql_add_failed_tx(COIN_NAME, str(ctx.message.author.id), ctx.message.author.name, real_amount, "TIPS")
            return

    elif coin_family == "XMR":
        COIN_DEC = get_decimal(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        real_amount = int(round(float(amount) * COIN_DEC))
        userdata_balance = store.sql_xmr_balance(str(ctx.message.author.id), COIN_NAME)
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
            if ctx.message.author.id != member.id:
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
            tips = store.sql_mv_xmr_multiple(str(ctx.message.author.id), memids, real_amount, COIN_NAME, "TIPS")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if tips:
            servername = serverinfo['servername']
            tipAmount = num_format_coin(TotalAmount, COIN_NAME)
            amountDiv_str = num_format_coin(real_amount, COIN_NAME)
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
            if ctx.message.author.bot == False and serverinfo['react_tip'] == "ON":
                await ctx.message.add_reaction(EMOJI_TIP)
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Tip of {tipAmount} '
                    f'{COIN_NAME} '
                    f'was sent to ({len(memids)}) members in server `{servername}`.\n'
                    f'Each member got: `{amountDiv_str}{COIN_NAME}`\n')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            for member in ctx.message.mentions:
                # print(member.name) # you'll just print out Member objects your way.
                if (ctx.message.author.id != member.id):
                    if member.bot == False:
                        if str(member.id) not in notifyList:
                            try:
                                await member.send(
                                    f'{EMOJI_MONEYFACE} You got a tip of `{amountDiv_str}{COIN_NAME}` '
                                    f'from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{servername}`\n'
                                    f'{NOTIFICATION_OFF_CMD}')
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                store.sql_toggle_tipnotify(str(member.id), "OFF")
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            return
        return
    elif COIN_NAME == "DOGE":
        MinTx = config.daemonDOGE.min_mv_amount
        MaxTX = config.daemonDOGE.max_mv_amount
        user_from = {}
        user_from['address'] = await DOGE_LTC_getaccountaddress(str(ctx.message.author.id), COIN_NAME)
        user_from['actual_balance'] = float(await DOGE_LTC_getbalance_acc(str(ctx.message.author.id), COIN_NAME, 6))
        real_amount = float(amount)
        userdata_balance = store.sql_doge_balance(str(ctx.message.author.id), COIN_NAME)
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
            if ctx.message.author.id != member.id:
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
            tips = store.sql_mv_doge_multiple(str(ctx.message.author.id), memids, real_amount, COIN_NAME, "TIPS")
            if ctx.message.author.bot == False and serverinfo['react_tip'] == "ON":
                await ctx.message.add_reaction(EMOJI_TIP)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if tips:
            servername = serverinfo['servername']
            tipAmount = num_format_coin(TotalAmount, COIN_NAME)
            amountDiv_str = num_format_coin(real_amount, COIN_NAME)
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Tip of {tipAmount} '
                    f'{COIN_NAME} '
                    f'was sent to ({len(memids)}) members in server `{servername}`.\n'
                    f'Each member got: `{amountDiv_str}{COIN_NAME}`\n')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            for member in ctx.message.mentions:
                # print(member.name) # you'll just print out Member objects your way.
                if (ctx.message.author.id != member.id):
                    if member.bot == False:
                        if str(member.id) not in notifyList:
                            try:
                                await member.send(
                                    f'{EMOJI_MONEYFACE} You got a tip of `{amountDiv_str}{COIN_NAME}` '
                                    f'from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{servername}`\n'
                                    f'{NOTIFICATION_OFF_CMD}')
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                store.sql_toggle_tipnotify(str(member.id), "OFF")
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            return
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
        return


# Multiple tip
async def _tip_talker(ctx, amount, list_talker, coin: str = None):
    serverinfo = store.sql_info_by_server(str(ctx.guild.id))
    COIN_NAME = coin.upper()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    try:
        amount = float(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    notifyList = store.sql_get_tipnotify()
    if coin_family not in ["TRTL", "CCX", "DOGE", "XMR"]:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} is restricted with this command.')
        return
    if coin_family == "TRTL" or coin_family == "CCX":
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(round(float(amount) * COIN_DEC))
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        NetFee = get_tx_fee(coin = COIN_NAME)
        if real_amount + NetFee > MaxTX:
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
        has_forwardtip = None
        list_receivers = []
        addresses = []
        for member_id in list_talker:
            if member_id != ctx.message.author.id:
                user_to = await store.sql_get_userwallet(str(member_id), COIN_NAME)
                if user_to is None:
                    userregister = await store.sql_register_user(str(member_id), COIN_NAME)
                    user_to = await store.sql_get_userwallet(str(member_id), COIN_NAME)
                address_to = None
                if user_to['forwardtip'] == "ON":
                    has_forwardtip = True
                    address_to = user_to['user_wallet_address']
                else:
                    address_to = user_to['balance_wallet_address']
                    addresses.append(address_to)
                if address_to:
                    list_receivers.append(str(member_id))
                    memids.append(address_to)


        # Check number of receivers.
        if len(memids) > config.tipallMax:
            await ctx.message.add_reaction(EMOJI_ERROR)
            try:
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} The number of receivers are too many.')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await ctx.message.author.send(f'{EMOJI_RED_NO} The number of receivers are too many in `{ctx.guild.name}`.')
            return
        # End of checking receivers numbers.

        for desti in memids:
            destinations.append({"address": desti, "amount": real_amount})

        ActualSpend = real_amount * len(memids) + NetFee

        if ActualSpend >= user_from['actual_balance']:
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
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} Wallet service hasn\'t sync fully with network or being '
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
            tip = await store.sql_send_tipall(str(ctx.message.author.id), destinations, real_amount, real_amount, list_receivers, 'TIPS', COIN_NAME)
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if tip:
            servername = serverinfo['servername']
            await store.sql_update_some_balances(addresses, COIN_NAME)
            if has_forwardtip:
                await ctx.message.add_reaction(EMOJI_FORWARD)
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(f'{EMOJI_ARROW_RIGHTHOOK} Total tip of {num_format_coin(ActualSpend, COIN_NAME)} '
                                        f'{COIN_NAME} '
                                        f'was sent to ({len(destinations)}) members in server `{servername}` for active talking.\n'
                                        f'Transaction hash: `{tip}`\n'
                                        f'Each: `{num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}`'
                                        f'Total spending: `{num_format_coin(ActualSpend, COIN_NAME)}{COIN_NAME}`')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            mention_list_name = ''
            for member_id in list_talker:
                if ctx.message.author.id != int(member_id):
                    member = bot.get_user(id=int(member_id))
                    if member.bot == False:
                        mention_list_name = mention_list_name + member.name + '#' + member.discriminator + ' '
                        if str(member_id) not in notifyList:
                            try:
                                await member.send(f'{EMOJI_MONEYFACE} You got a tip of {num_format_coin(real_amount, COIN_NAME)} '
                                                f'{COIN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{servername}` for active talking.\n'
                                                f'Transaction hash: `{tip}`\n'
                                                f'{NOTIFICATION_OFF_CMD}')
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                store.sql_toggle_tipnotify(str(member.id), "OFF")
                            pass
            try:
                await ctx.send(f'{mention_list_name}\n\nYou got tip :) for active talking in `{ctx.guild.name}` {ctx.channel.mention} :)')
                await ctx.message.add_reaction(EMOJI_SPEAK)
            except discord.errors.Forbidden:
                await ctx.message.add_reaction(EMOJI_SPEAK)
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You may need to `optimize` or try again later.')
            # add to failed tx table
            store.sql_add_failed_tx(COIN_NAME, str(ctx.message.author.id), ctx.message.author.name, real_amount, "TIPS")
            return
    elif coin_family == "XMR":
        COIN_DEC = get_decimal(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        real_amount = int(round(float(amount) * COIN_DEC))
        userdata_balance = store.sql_xmr_balance(str(ctx.message.author.id), COIN_NAME)
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
            tips = store.sql_mv_xmr_multiple(str(ctx.message.author.id), memids, real_amount, COIN_NAME, "TIPS")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if tips:
            servername = serverinfo['servername']
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Tip of {num_format_coin(TotalAmount, COIN_NAME)} '
                    f'{COIN_NAME} '
                    f'was sent to ({len(memids)}) members in server `{servername}` for active talking.\n'
                    f'Each member got: `{num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}`\n')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            mention_list_name = ''
            for member_id in list_talker:
                # print(member.name) # you'll just print out Member objects your way.
                if ctx.message.author.id != int(member_id):
                    member = bot.get_user(id=int(member_id))
                    if member.bot == False:
                        mention_list_name = mention_list_name + member.name + '#' + member.discriminator + ' '
                        if str(member_id) not in notifyList:
                            try:
                                await member.send(
                                    f'{EMOJI_MONEYFACE} You got a tip of `{num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}` '
                                    f'from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{servername}` for active talking.\n'
                                    f'{NOTIFICATION_OFF_CMD}')
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                store.sql_toggle_tipnotify(str(member.id), "OFF")
            try:
                await ctx.send(f'{mention_list_name}\n\nYou got tip :) for active talking in `{ctx.guild.name}` {ctx.channel.mention} :)')
                await ctx.message.add_reaction(EMOJI_SPEAK)
            except discord.errors.Forbidden:
                await ctx.message.add_reaction(EMOJI_SPEAK)
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            return
        return
    elif COIN_NAME == "DOGE":
        MinTx = config.daemonDOGE.min_mv_amount
        MaxTX = config.daemonDOGE.max_mv_amount
        user_from = {}
        user_from['address'] = await DOGE_LTC_getaccountaddress(str(ctx.message.author.id), COIN_NAME)
        user_from['actual_balance'] = float(await DOGE_LTC_getbalance_acc(str(ctx.message.author.id), COIN_NAME, 6))
        real_amount = float(amount)
        userdata_balance = store.sql_doge_balance(str(ctx.message.author.id), COIN_NAME)
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
            tips = store.sql_mv_doge_multiple(str(ctx.message.author.id), memids, real_amount, COIN_NAME, "TIPS")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if tips:
            servername = serverinfo['servername']
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Tip of {num_format_coin(TotalAmount, COIN_NAME)} '
                    f'{COIN_NAME} '
                    f'was sent to ({len(memids)}) members in server `{servername}` for active talking.\n'
                    f'Each member got: `{num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}`\n')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            mention_list_name = ''
            for member_id in list_talker:
                # print(member.name) # you'll just print out Member objects your way.
                if ctx.message.author.id != int(member_id):
                    member = bot.get_user(id=int(member_id))
                    if member.bot == False:
                        mention_list_name = mention_list_name + member.name + '#' + member.discriminator + ' '
                        if str(member_id) not in notifyList:
                            try:
                                await member.send(
                                    f'{EMOJI_MONEYFACE} You got a tip of `{num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}` '
                                    f'from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{servername}` for active talking.\n'
                                    f'{NOTIFICATION_OFF_CMD}')
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                store.sql_toggle_tipnotify(str(member.id), "OFF")
            try:
                await ctx.send(f'{mention_list_name}\n\nYou got tip :) for active talking in `{ctx.guild.name}` {ctx.channel.mention} :)')
                await ctx.message.add_reaction(EMOJI_SPEAK)
            except discord.errors.Forbidden:
                await ctx.message.add_reaction(EMOJI_SPEAK)
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            return
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
        return


# Multiple tip_react
async def _tip_react(reaction, user, amount, coin: str):
    global REACT_TIP_STORE
    serverinfo = store.sql_info_by_server(str(reaction.message.guild.id))
    COIN_NAME = coin.upper()

    # If only one user and he re-act
    if len(reaction.message.mentions) == 1 and user in (reaction.message.mentions):
        return
        
    notifyList = store.sql_get_tipnotify()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family == "TRTL" or coin_family == "CCX":
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(round(float(amount) * COIN_DEC))
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        NetFee = get_tx_fee(coin = COIN_NAME)
        user_from = await store.sql_get_userwallet(str(user.id), COIN_NAME)

        destinations = []
        listMembers = reaction.message.mentions

        memids = []  # list of member ID
        has_forwardtip = None
        list_receivers = []
        addresses = []
        for member in listMembers:
            # print(member.name) # you'll just print out Member objects your way.
            if user.id != member.id and reaction.message.author.id != member.id:
                user_to = await store.sql_get_userwallet(str(member.id), COIN_NAME)
                if user_to is None:
                    userregister = await store.sql_register_user(str(member.id), COIN_NAME)
                    user_to = await store.sql_get_userwallet(str(member.id), COIN_NAME)
                address_to = None
                if user_to['forwardtip'] == "ON":
                    address_to = user_to['user_wallet_address']
                    has_forwardtip = True
                else:
                    address_to = user_to['balance_wallet_address']
                    addresses.append(address_to)
                if address_to:
                    list_receivers.append(str(member.id))
                    memids.append(address_to)

        for desti in memids:
            destinations.append({"address": desti, "amount": real_amount})


        ActualSpend = real_amount * len(memids) + NetFee
        if ActualSpend >= user_from['actual_balance']:
            try:
                await user.send(f'{EMOJI_RED_NO} {user.mention} Insufficient balance {EMOJI_TIP} total of '
                               f'{num_format_coin(ActualSpend, COIN_NAME)} '
                               f'{COIN_NAME}.')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                print(f"_tip_react Can not send DM to {user.id}")
            return

        # Get wallet status
        walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
        if walletStatus is None:
            try:
                await user.send(f'{EMOJI_RED_NO} {user.mention} {COIN_NAME} I can not connect to wallet service or daemon.')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                print(f"{COIN_NAME} _tip_reactCan not send DM to {user.id}")
            return
        else:
            localDaemonBlockCount = int(walletStatus['blockCount'])
            networkBlockCount = int(walletStatus['knownBlockCount'])
            if networkBlockCount - localDaemonBlockCount >= 20:
                # if height is different by 20
                t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount / networkBlockCount * 100, 2))
                t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
                t_networkBlockCount = '{:,}'.format(networkBlockCount)
                try:
                    await user.send(f'{EMOJI_RED_NO} {user.mention} {COIN_NAME} Wallet service hasn\'t sync fully with network or being '
                                   're-sync. More info:\n```'
                                   f'networkBlockCount:     {t_networkBlockCount}\n'
                                   f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                                   f'Progress %:            {t_percent}\n```'
                                   )
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    print(f"{COIN_NAME} _tip_reactCan not send DM to {user.id}")
                return
        # End of wallet status
        tip = None
        try:
            tip = await store.sql_send_tipall(str(user.id), destinations, real_amount, real_amount, list_receivers, 'TIPS', COIN_NAME)
            tip_tx_tipper = "Transaction hash: `{}`".format(tip)
            REACT_TIP_STORE.append((str(reaction.message.id) + '.' + str(user.id)))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if tip:
            servername = serverinfo['servername']
            try:
                await store.sql_update_some_balances(addresses, COIN_NAME)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            if has_forwardtip:
                await reaction.message.add_reaction(EMOJI_FORWARD)
            # tipper shall always get DM. Ignore notifyList
            try:
                await user.send(f'{EMOJI_ARROW_RIGHTHOOK} Total {EMOJI_TIP} of {num_format_coin(ActualSpend, COIN_NAME)} '
                                f'{COIN_NAME} '
                                f'was sent to ({len(destinations)}) members in server `{servername}`.\n'
                                f'{tip_tx_tipper}\n'
                                f'Each: `{num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}`'
                                f'Total spending: `{num_format_coin(ActualSpend, COIN_NAME)} {COIN_NAME}`')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                store.sql_toggle_tipnotify(str(user.id), "OFF")
            for member in reaction.message.mentions:
                if user.id != member.id and reaction.message.author.id != member.id:
                    if member.bot == False:
                        if str(member.id) not in notifyList:
                            try:
                                await member.send(f'{EMOJI_MONEYFACE} You got a {EMOJI_TIP} of  {num_format_coin(real_amount, COIN_NAME)} '
                                                f'{COIN_NAME} from {user.name}#{user.discriminator} in server `{servername}`\n'
                                                f'{tip_tx_tipper}\n'
                                                f'{NOTIFICATION_OFF_CMD}')
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                store.sql_toggle_tipnotify(str(member.id), "OFF")
                            pass
            return
        else:
            await user.send(f'{EMOJI_RED_NO} {user.mention} You may need to `optimize` or try again for {EMOJI_TIP}.')
            # add to failed tx table
            store.sql_add_failed_tx(COIN_NAME, str(user.id), user.name, real_amount, "REACTTIP")
            return

    elif coin_family == "XMR":
        COIN_DEC = get_decimal(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        user_from = await store.sql_get_userwallet(str(user.id), COIN_NAME)
        real_amount = int(round(float(amount) * COIN_DEC))
        userdata_balance = store.sql_xmr_balance(str(user.id), COIN_NAME)
        if real_amount > user_from['actual_balance'] + userdata_balance['Adjust']:
            await user.send(f'{EMOJI_RED_NO} {user.mention} Insufficient balance to send tip of '
                            f'{num_format_coin(real_amount, COIN_NAME)} '
                            f'{COIN_NAME}.')
            return

        listMembers = reaction.message.mentions
        memids = []  # list of member ID
        for member in listMembers:
            if user.id != member.id and reaction.message.author.id != member.id:
                memids.append(str(member.id))
        TotalAmount = real_amount * len(memids)

        if user_from['actual_balance'] + userdata_balance['Adjust'] < TotalAmount:
            try:
                await user.send(f'{EMOJI_RED_NO} {user.mention} You don\'t have sufficient balance. ')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                print(f"{COIN_NAME} _tip_reactCan not send DM to {user.id}")
            return
        try:
            tips = store.sql_mv_xmr_multiple(str(user.id), memids, real_amount, COIN_NAME, "TIPS")
            REACT_TIP_STORE.append((str(reaction.message.id) + '.' + str(user.id)))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if tips:
            servername = serverinfo['servername']
            tipAmount = num_format_coin(TotalAmount, COIN_NAME)
            amountDiv_str = num_format_coin(real_amount, COIN_NAME)
            # tipper shall always get DM. Ignore notifyList
            try:
                await user.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} {EMOJI_TIP} of {tipAmount} '
                    f'{COIN_NAME} '
                    f'was sent to ({len(memids)}) members in server `{servername}`.\n'
                    f'Each member got: `{amountDiv_str}{COIN_NAME}`\n')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                store.sql_toggle_tipnotify(str(user.id), "OFF")
            for member in reaction.message.mentions:
                # print(member.name) # you'll just print out Member objects your way.
                if (user.id != member.id):
                    if member.bot == False:
                        if str(member.id) not in notifyList:
                            try:
                                await member.send(
                                    f'{EMOJI_MONEYFACE} You got a {EMOJI_TIP} of `{amountDiv_str}{COIN_NAME}` '
                                    f'from {user.name}#{user.discriminator} in server `{servername}`\n'
                                    f'{NOTIFICATION_OFF_CMD}')
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                store.sql_toggle_tipnotify(str(member.id), "OFF")
            return
        return
    elif COIN_NAME == "DOGE":
        MinTx = config.daemonDOGE.min_mv_amount
        MaxTX = config.daemonDOGE.max_mv_amount
        user_from = {}
        user_from['address'] = await DOGE_LTC_getaccountaddress(str(user.id), COIN_NAME)
        user_from['actual_balance'] = float(await DOGE_LTC_getbalance_acc(str(user.id), COIN_NAME, 6))
        real_amount = float(amount)
        userdata_balance = store.sql_doge_balance(str(user.id), COIN_NAME)
        if real_amount > user_from['actual_balance'] + userdata_balance['Adjust']:
            try:
                await user.send(f'{EMOJI_RED_NO} {user.mention} Insufficient balance to send tip of '
                                f'{num_format_coin(real_amount, COIN_NAME)} '
                                f'{COIN_NAME}.')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                print(f"{COIN_NAME} _tip_reactCan not send DM to {user.id}")
            return

        listMembers = reaction.message.mentions
        memids = []  # list of member ID
        for member in listMembers:
            if user.id != member.id and reaction.message.author.id != member.id:
                memids.append(str(member.id))
        TotalAmount = real_amount * len(memids)

        if user_from['actual_balance'] + userdata_balance['Adjust'] < TotalAmount:
            try:
                await user.send(f'{EMOJI_RED_NO} {user.mention} You don\'t have sufficient balance. ')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                print(f"{COIN_NAME} _tip_reactCan not send DM to {user.id}")
            return
        try:
            tips = store.sql_mv_doge_multiple(user.id, memids, real_amount, COIN_NAME, "TIPS")
            REACT_TIP_STORE.append((str(reaction.message.id) + '.' + str(user.id)))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        if tips:
            servername = serverinfo['servername']
            tipAmount = num_format_coin(TotalAmount, COIN_NAME)
            amountDiv_str = num_format_coin(real_amount, COIN_NAME)
            # tipper shall always get DM. Ignore notifyList
            try:
                await user.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} {EMOJI_TIP} of {tipAmount} '
                    f'{COIN_NAME} '
                    f'was sent to ({len(memids)}) members in server `{servername}`.\n'
                    f'Each member got: `{amountDiv_str}{COIN_NAME}`\n')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                store.sql_toggle_tipnotify(str(user.id), "OFF")
            for member in reaction.message.mentions:
                # print(member.name) # you'll just print out Member objects your way.
                if (user.id != member.id):
                    if member.bot == False:
                        if str(member.id) not in notifyList:
                            try:
                                await member.send(
                                    f'{EMOJI_MONEYFACE} You got {EMOJI_TIP} of `{amountDiv_str}{COIN_NAME}` '
                                    f'from {user.name}#{user.discriminator} in server `{servername}`\n'
                                    f'{NOTIFICATION_OFF_CMD}')
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                store.sql_toggle_tipnotify(str(member.id), "OFF")
            return
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


async def bot_faucet(ctx):
    global TRTL_DISCORD
    table_data = [
        ['TICKER', 'Available', 'Locked']
    ]
    # TRTL discord
    if ctx.guild.id == TRTL_DISCORD:
        COIN_NAME = "TRTL"
        wallet = await store.sql_get_userwallet(str(bot.user.id), COIN_NAME)
        balance_actual = num_format_coin(wallet['actual_balance'], COIN_NAME)
        balance_locked = num_format_coin(wallet['locked_balance'], COIN_NAME)
        balance_total = num_format_coin((wallet['actual_balance'] + wallet['locked_balance']), COIN_NAME)
        if wallet['actual_balance'] + wallet['locked_balance'] != 0:
            table_data.append([COIN_NAME, balance_actual, balance_locked])
        else:
            table_data.append([COIN_NAME, '0', '0'])
        table = AsciiTable(table_data)
        table.padding_left = 0
        table.padding_right = 0
        return table.table
    # End TRTL discord
    for COIN_NAME in [coinItem.upper() for coinItem in FAUCET_COINS]:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
        if (COIN_NAME not in MAINTENANCE_COIN) and coin_family in ["TRTL", "CCX"]:
            COIN_DEC = get_decimal(COIN_NAME)
            wallet = await store.sql_get_userwallet(str(bot.user.id), COIN_NAME)
            balance_actual = num_format_coin(wallet['actual_balance'], COIN_NAME)
            balance_locked = num_format_coin(wallet['locked_balance'], COIN_NAME)
            balance_total = num_format_coin((wallet['actual_balance'] + wallet['locked_balance']), COIN_NAME)
            if wallet['actual_balance'] + wallet['locked_balance'] != 0:
                table_data.append([COIN_NAME, balance_actual, balance_locked])
            else:
                table_data.append([COIN_NAME, '0', '0'])
    # Add DOGE
    COIN_NAME = "DOGE"
    if (COIN_NAME not in MAINTENANCE_COIN) and COIN_NAME in FAUCET_COINS:
        actual = float(await DOGE_LTC_getbalance_acc(str(bot.user.id), COIN_NAME, 6))
        locked = float(await DOGE_LTC_getbalance_acc(str(bot.user.id), COIN_NAME, 1))
        userdata_balance = store.sql_doge_balance(str(bot.user.id), COIN_NAME)
        if actual == locked:
            balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
            balance_locked = num_format_coin(0, COIN_NAME)
        else:
            balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
            if locked - actual + float(userdata_balance['Adjust']) < 0 or locked == 0:
                balance_locked =  num_format_coin(0, COIN_NAME)
            else:
                balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
        table_data.append([COIN_NAME, balance_actual, balance_locked])
    table = AsciiTable(table_data)
    table.padding_left = 0
    table.padding_right = 0
    return table.table


@click.command()
def main():
    bot.loop.create_task(saving_wallet())
    bot.loop.create_task(update_user_guild())
    bot.run(config.discord.token, reconnect=True)


if __name__ == '__main__':
    main()
