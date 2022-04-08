import asyncio
# Eth wallet py
import datetime
import json
import logging
import math
import os
# for randomString
import random
import string
import sys, traceback
import time
import click
from datetime import datetime

from decimal import Decimal
import re
# redis
import redis
import disnake
from disnake.ext import commands
from disnake.ext.commands import AutoShardedBot, when_mentioned_or
from disnake import ActionRow, Button
from disnake.enums import ButtonStyle

# linedraw
from linedraw.linedraw import *
from cairosvg import svg2png

from io import BytesIO

###
import os.path
import uuid
from PIL import Image, ImageDraw, ImageFont
# For eval
import contextlib
import io

# For hash file in case already have
import hashlib

import numpy as np
# ascii table
from terminaltables import AsciiTable

import base58

# Encrypt
from cryptography.fernet import Fernet

from discord_webhook import DiscordWebhook
import store
from config import config



async def get_token_list():
    return await store.get_all_token()

# Defines a simple view of row buttons.
class RowButton_close_message(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # Creates a row of buttons and when one of them is pressed, it will send a message with the number of the button.

    @disnake.ui.button(label="❎ Close", style=ButtonStyle.blurple, custom_id="close_message")
    async def row_close_message(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        #await interaction.response.send_message("This is the first button.")
        pass


# Defines a simple view of row buttons.
class RowButton_row_close_any_message(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.button(label="❎ Close", style=ButtonStyle.green, custom_id="close_any_message")
    async def row_close_message(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        pass


redis_pool = None
redis_conn = None
redis_expired = 120

logging.basicConfig(level=logging.INFO)

SERVER_BOT = "DISCORD"

EMOJI_ERROR = "\u274C"
EMOJI_RED_NO = "\u26D4"
EMOJI_MONEYBAG = "\U0001F4B0"
EMOJI_ARROW_RIGHTHOOK = "\u21AA"
EMOJI_ZIPPED_MOUTH = "\U0001F910"
EMOJI_MONEYFACE = "\U0001F911"
EMOJI_BELL_SLASH = "\U0001F515"
EMOJI_BELL = "\U0001F514"
EMOJI_HOURGLASS_NOT_DONE = "\u23F3"
EMOJI_PARTY = "\U0001F389"
EMOJI_SPEAK = "\U0001F4AC"
EMOJI_INFORMATION = "\u2139"
EMOJI_FLOPPY = "\U0001F4BE"
EMOJI_CHECKMARK = "\u2714"

EMOJI_UP_RIGHT = "\u2197"
EMOJI_DOWN_RIGHT = "\u2198"
EMOJI_CHART_DOWN = "\U0001F4C9"
EMOJI_CHART_UP = "\U0001F4C8"

NOTIFICATION_OFF_CMD = 'Type: `/notifytip off` to turn off this notification.'
DEFAULT_TICKER = "WRKZ"
MSG_LOCKED_ACCOUNT = "Your account is locked. Please contact pluton#8888 in WrkzCoin discord."

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


async def logchanbot(content: str):
    try:
        webhook = DiscordWebhook(url=config.discord.webhook_url, content=f'```{disnake.utils.escape_markdown(content)}```')
        webhook.execute()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


# Steal from https://github.com/cree-py/RemixBot/blob/master/bot.py#L49
async def get_prefix(bot, message):
    """Gets the prefix for the guild"""
    pre_cmd = config.discord.prefixCmd
    if isinstance(message.channel, disnake.DMChannel):
        extras = [pre_cmd, '?', '.', '+', '!', '-']
        return when_mentioned_or(*extras)(bot, message)

    serverinfo = await store.sql_info_by_server(str(message.guild.id))
    if serverinfo is None:
        # Let's add some info if guild return None
        add_server_info = await store.sql_addinfo_by_server(str(message.guild.id), message.guild.name, config.discord.prefixCmd, config.discord.default_coin, False)
        serverinfo = await store.sql_info_by_server(str(message.guild.id))
    if serverinfo and 'prefix' in serverinfo:
        pre_cmd = serverinfo['prefix']
    else:
        pre_cmd = config.discord.prefixCmd
    extras = [pre_cmd, '!', '.', '/']
    return when_mentioned_or(*extras)(bot, message)


intents = disnake.Intents.default()
intents.members = True
intents.presences = True
bot = AutoShardedBot(command_prefix=get_prefix, owner_id=config.discord.ownerID, intents=intents, sync_commands=True)
bot.remove_command('help')

bot.owner_id = config.discord.ownerID
bot.coin_list = None
bot.token_hints = None
bot.token_hint_names = None
bot.coin_name_list = None
bot.faucet_coins = None

# messages
bot.message_list = []

# Price List
bot.coin_paprika_id_list = None
bot.coin_paprika_symbol_list = None

bot.coin_coingecko_id_list = None
bot.coin_coingecko_symbol_list = None

bot.TX_IN_PROCESS = []
bot.LOG_CHAN = config.discord.logchan
bot.MINGPOOLSTAT_IN_PROCESS = []
bot.GAME_INTERACTIVE_ECO = []
bot.GAME_INTERACTIVE_PRGORESS = []
bot.GAME_SLOT_IN_PRGORESS = []
bot.GAME_MAZE_IN_PROCESS = []
bot.GAME_DICE_IN_PRGORESS = []
bot.GAME_RAFFLE_QUEUE = []


bot.erc_node_list = {
    "FTM": config.default_endpoints.ftm, 
    "BSC": config.default_endpoints.bsc, 
    "MATIC": config.default_endpoints.matic, 
    "xDai": config.default_endpoints.xdai, 
    "ETH": config.default_endpoints.eth,
    "TLOS": config.default_endpoints.tlos,
    "AVAX": config.default_endpoints.avax, 
    "TRX": config.Tron_Node.fullnode
    }


@bot.command(usage="load <cog>")
@disnake.ext.commands.is_owner()
async def load(ctx, extension):
    """Load specified cog"""
    try:
        extension = extension.lower()
        bot.load_extension(f'cogs.{extension}')
        await ctx.send('{} has been loaded.'.format(extension.capitalize()))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

@bot.command(usage="unload <cog>")
@disnake.ext.commands.is_owner()
async def unload(ctx, extension):
    """Unload specified cog"""
    try:
        extension = extension.lower()
        bot.unload_extension(f'cogs.{extension}')
        await ctx.send('{} has been unloaded.'.format(extension.capitalize()))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


@bot.command(usage="reload <cog/guilds/utils/all>")
@disnake.ext.commands.is_owner()
async def reload(ctx, extension):
    """Reload specified cog"""
    try:
        extension = extension.lower()
        bot.reload_extension(f'cogs.{extension}')
        await ctx.send('{} has been reloaded.'.format(extension.capitalize()))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def add_msg_redis(msg: str, delete_temp: bool = False):
    try:
        openRedis()
        key = config.redis.prefix + ":MSG"
        if redis_conn:
            if delete_temp:
                redis_conn.delete(key)
            else:
                redis_conn.lpush(key, msg)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())


async def store_message_list():
    while True:
        interval_msg_list = 15 # in second
        try:
            openRedis()
            key = config.redis.prefix + ":MSG"
            if redis_conn and redis_conn.llen(key) > 0 :
                temp_msg_list = []
                for each in redis_conn.lrange(key, 0, -1):
                    temp_msg_list.append(tuple(json.loads(each)))
                num_add = None
                try:
                    num_add = await store.sql_add_messages(temp_msg_list)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
                if num_add and num_add > 0:
                    redis_conn.delete(key)
                else:
                    redis_conn.delete(key)
                    print(config.redis.prefix + f":MSG: Failed delete {key}")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        await asyncio.sleep(interval_msg_list)


# function to return if input string is ascii
def is_ascii(s):
    return all(ord(c) < 128 for c in s)


# https://stackoverflow.com/questions/579310/formatting-long-numbers-as-strings-in-python/45846841
def human_format(num):
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])


def text_to_num(text):
    text = text.upper()
    try:
        text=Decimal(text)
        return text
    except Exception:
        pass

    amount = Decimal(0.0)
    for num, val in re.findall('([\d\.\d]+)(\w+)', text):
        if "-" in text: return None
        # test digits
        test_ = text
        test_ = test_.upper().replace("K", "").replace("B", "").replace("M", "").replace(",", "")
        try:
            test_=Decimal(test_)
        except Exception:
            return None

        thousand = val.count("K")
        million = val.count("M")
        billion = val.count("B")
        if (thousand > 0 and million > 0) or (thousand > 0 and billion > 0) \
        or (million > 0 and billion > 0):
            # Invalid
            return None
        elif thousand > 0:
            amount += Decimal(num) * (10**3)**thousand
        elif million > 0:
            amount += Decimal(num) * (10**6)**million
        elif billion > 0:
            amount += Decimal(num) * (10**9)**billion
    return amount


def seconds_str(time: float):
    # day = time // (24 * 3600)
    # time = time % (24 * 3600)
    hour = time // 3600
    time %= 3600
    minutes = time // 60
    time %= 60
    seconds = time
    return "{:02d}:{:02d}:{:02d}".format(hour, minutes, seconds)


def num_format_coin(amount, coin: str, coin_decimal: int, atomic: bool=False):
    COIN_NAME = coin.upper() 
    if amount == 0:
        return "0.0"

    if atomic == True:
        amount = amount / int(10**coin_decimal)
        amount_str = 'Invalid.'
        if coin_decimal == 0:
            amount_test = '{:,f}'.format(float(('%f' % amount).rstrip('0').rstrip('.')))
            if '.' in amount_test and len(amount_test.split('.')[1]) > 6:
                amount_str = '{:,.6f}'.format(amount)
            else:
                amount_str = amount_test
        elif coin_decimal < 4:
            amount = truncate(amount, 2)
            amount_str = '{:,.2f}'.format(amount)
        elif coin_decimal < 6:
            amount = truncate(amount, 6)
            amount_test = '{:,f}'.format(float(('%f' % amount).rstrip('0').rstrip('.')))
            if '.' in amount_test and len(amount_test.split('.')[1]) > 5:
                amount_str = '{:,.6f}'.format(amount)
            else:
                amount_str = amount_test
        elif coin_decimal < 18:
            amount = truncate(amount, 8)
            amount_test = '{:,f}'.format(float(('%f' % (amount)).rstrip('0').rstrip('.')))
            if '.' in amount_test and len(amount_test.split('.')[1]) > 5:
                amount_str = '{:,.8f}'.format(amount)
            else:
                amount_str = amount_test
        else:
            # > 10**18
            amount = truncate(amount, 8)
            amount_test = '{:,f}'.format(float(('%f' % (amount)).rstrip('0').rstrip('.')))
            if '.' in amount_test and len(amount_test.split('.')[1]) > 8:
                amount_str = '{:,.8f}'.format(amount)
            else:
                amount_str =  amount_test
    else:
        if amount < 0.00000001:
            amount_str = '{:,.10f}'.format(amount)
        elif amount < 0.000001:
            amount_str = '{:,.8f}'.format(amount)
        elif amount < 0.0001:
            amount_str = '{:,.7f}'.format(amount)
        elif amount < 0.01:
            amount_str = '{:,.6f}'.format(amount)
        elif amount < 1.0:
            amount_str = '{:,.5f}'.format(amount)
        elif amount < 10:
            amount_str = '{:,.4f}'.format(amount)
        elif amount < 1000.00:
            amount_str = '{:,.3f}'.format(amount)
        else:
            amount_str = '{:,.2f}'.format(amount)
    return amount_str.rstrip('0').rstrip('.') if '.' in amount_str else amount_str 


def randomString(stringLength=8):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(stringLength))


def truncate(number, digits) -> float:
    stepper = Decimal(pow(10.0, digits))
    return math.trunc(stepper * Decimal(number)) / stepper


def hex_to_base58(hex_string):
    if hex_string[:2] in ["0x", "0X"]:
        hex_string = "41" + hex_string[2:]
    bytes_str = bytes.fromhex(hex_string)
    base58_str = base58.b58encode_check(bytes_str)
    return base58_str.decode("UTF-8")


def base58_to_hex(base58_string):
    asc_string = base58.b58decode_check(base58_string)
    return asc_string.hex().upper()


async def get_guild_prefix(ctx):
    if isinstance(ctx.channel, disnake.DMChannel) == True:
        return config.discord.prefixCmd
    else:
        return config.discord.slashPrefix


# Steal from https://nitratine.net/blog/post/encryption-and-decryption-in-python/
def encrypt_string(to_encrypt: str):
    key = (config.encrypt.key).encode()

    # Encrypt
    message = to_encrypt.encode()
    f = Fernet(key)
    encrypted = f.encrypt(message)
    return encrypted.decode()


def decrypt_string(decrypted: str):
    key = (config.encrypt.key).encode()

    # Decrypt
    f = Fernet(key)
    decrypted = f.decrypt(decrypted.encode())
    return decrypted.decode()


## https://github.com/MrJacob12/StringProgressBar
def createBox(value, maxValue, size, show_percentage: bool=False):
    percentage = value / maxValue
    progress = round((size * percentage))
    emptyProgress = size - progress
        
    progressText = '█'
    emptyProgressText = '—'
    percentageText = str(round(percentage * 100)) + '%'

    if show_percentage:
        bar = '[' + progressText*progress + emptyProgressText*emptyProgress + ']' + percentageText
    else:
        bar = '[' + progressText*progress + emptyProgressText*emptyProgress + ']'
    return bar


async def alert_if_userlock(ctx, cmd: str):
    botLogChan = bot.get_channel(bot.LOG_CHAN)
    get_discord_userinfo = None
    try:
        get_discord_userinfo = await store.sql_discord_userinfo_get(str(ctx.author.id))
        if get_discord_userinfo is not None and get_discord_userinfo['locked'].upper() == "YES":
            await botLogChan.send(f'{ctx.author.name}#{ctx.author.discriminator} locked but is commanding `{cmd}`')
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

# json.dumps for turple
def remap_keys(mapping):
    return [{'key':k, 'value': v} for k, v in mapping.items()]


@click.command()
def main():
    for filename in os.listdir('./cogs/'):
        if filename.endswith('.py'):
            bot.load_extension(f'cogs.{filename[:-3]}')

    bot.run(config.discord.token, reconnect=True)

if __name__ == '__main__':
    main()