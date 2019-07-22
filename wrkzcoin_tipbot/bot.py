import click

import discord
from discord.ext import commands
from discord.ext.commands import Bot, AutoShardedBot, when_mentioned_or, CheckFailure

from discord.utils import get

import time, timeago, json
import pyotp

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
import asyncio


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

EMOJI_COIN = {
    "WRKZ" : "\U0001F477",
    "TRTL" : "\U0001F422",
    "DEGO" : "\U0001F49B",
    "LCX" : "\U0001F517",
    "CX" : "\U0001F64F",
    "OSL" : "\U0001F381",
    "BTCM" : "\U0001F4A9",
    "MTIP" : "\U0001F595",
    "XCY" : "\U0001F3B2",
    "PLE" : "\U0001F388",
    "ELPH" : "\U0001F310",
    "ANX" : "\U0001F3E6",
    "NBX" : "\U0001F5A4",
    "ARMS" : "\U0001F52B",
    "IRD" : "\U0001F538",
    "HITC" : "\U0001F691",
    "NACA" : "\U0001F355",
    "DOGE" : "\U0001F436",
    "XTOR" : "\U0001F315",
    "LOKI" : "\u2600",
    "XMR" : "\u2694",
    "XTRI" : "\U0001F30C"
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
ENABLE_XMR = ["XTOR", "LOKI", "XMR", "XTRI"]
MAINTENANCE_COIN = [""]
COIN_REPR = "COIN"
DEFAULT_TICKER = "WRKZ"
ENABLE_COIN_VOUCHER = config.Enable_Coin_Voucher.split(",")

# Some notice about coin that going to swap or take out.
NOTICE_COIN = {
    "WRKZ" : None,
    "TRTL" : None,
    "DEGO" : None,
    "LCX" : EMOJI_INFORMATION + " LCX Project / service shutdown announced on July 10th, 2019.",
    "CX" : None,
    "OSL" : None,
    "BTCM" : None,
    "MTIP" : None,
    "XCY" : None,
    "PLE" : None,
    "ELPH" : None,
    "ANX" : None,
    "NBX" : None,
    "ARMS" : None,
    "IRD" : None,
    "HITC" : None,
    "NACA" : None,
    "XTOR" : None,
    "LOKI" : None,
    "XTRI" : "XTRI still testing.",
    "XMR" : "XMR still testing.",
    "DOGE" : "Please acknowledge that DOGE address is for **one-time** use only for depositing."
    }

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
bot_help_stats = f"Show summary {COIN_REPR}: height, difficulty, etc."
bot_help_height = f"Show {COIN_REPR}'s current height"
bot_help_notifytip = "Toggle notify tip notification from bot ON|OFF"
bot_help_settings = "settings view and set for prefix, default coin. Requires permission manage_channels"
bot_help_invite = "Invite link of bot to your server."
bot_help_voucher = "(Testing) make a voucher image and your friend can claim via QR code."

# admin commands
bot_help_admin = "Various admin commands."
bot_help_admin_save = "Save wallet file..."
bot_help_admin_shutdown = "Restart bot."
bot_help_admin_baluser = "Check a specific user's balance for verification purpose."
bot_help_admin_lockuser = "Lock a user from any tx (tip, withdraw, info, etc) by user id"
bot_help_admin_unlockuser = "Unlock a user by user id."

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

    if 'prefix' in serverinfo:
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
async def on_reaction_add(reaction, user):
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
                except discord.Forbidden:
                    # If DM is failed, popup to channel.
                    await reaction.message.channel.send(f'{to_send.mention} I failed DM you for the address.')
                return
                # await msg.add_reaction(EMOJI_OK_BOX)
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
        print(e)


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
            print(e)
        if verified and verified.upper() == "YES":
            await ctx.send(f'{ctx.author.mention} You already verified 2FA.')
            return

        try:
            secret_code = store.decrypt_string(userinfo['twofa_secret'])
        except Exception as e:
            print(e)
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
            print(e)
        if verified and verified.upper() == "YES":
            await ctx.send(f'{ctx.author.mention} You already verified 2FA. You do not need this.')
            return
        
        try:
            secret_code = store.decrypt_string(userinfo['twofa_secret'])
        except Exception as e:
            print(e)

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
            print(e)
        if verified and verified.upper() == "NO":
            await ctx.send(f'{ctx.author.mention} You have not verified yet. **Unverify** stopped.')
            return
        
        try:
            secret_code = store.decrypt_string(userinfo['twofa_secret'])
        except Exception as e:
            print(e)

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
        netFee = get_tx_fee(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        if real_amount + netFee >= user_from['actual_balance']:
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
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} Wallet service hasn\'t started.')
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
            tip = await store.sql_send_secrettip(str(ctx.message.author.id), user_id, real_amount, COIN_NAME, COIN_DEC)
        except Exception as e:
            print(e)
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
                f'was sent to `{user_id} / {member.name}`\n'
                f'Transaction hash: `{tip}`')
        except discord.Forbidden:
            # add user to notifyList
            print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
            store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
        if str(user_id) not in notifyList:
            # member already declare above
            try:
                await member.send(
                    f'{EMOJI_MONEYFACE} You got a secret tip of {num_format_coin(real_amount, COIN_NAME)} '
                    f'{COIN_NAME}\n'
                    f'Transaction hash: `{tip}`\n'
                    f'{NOTIFICATION_OFF_CMD}')
            except discord.Forbidden:
                # add user to notifyList
                print('Adding: ' + str(member.id) + ' not to receive DM tip')
                store.sql_toggle_tipnotify(str(member.id), "OFF")
        else:
            try:
                await ctx.message.author.send(f'`{member.name} / {user_id}` received '
                                              f'{num_format_coin(real_amount, COIN_NAME)} {COIN_NAME}'
                                              ' but has notification **OFF** or **DM disable**.')
            except discord.Forbidden:
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
    botLogChan = bot.get_channel(id=LOG_CHAN)
    COIN_NAME = coin.upper()
    if COIN_NAME in MAINTENANCE_COIN:
        await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} in maintenance.')
        return
    
    if COIN_NAME in (ENABLE_COIN+ENABLE_XMR):
        duration = await rpc_cn_wallet_save(COIN_NAME)
        await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} called `save` for {COIN_NAME}')
        if duration:
            await ctx.send(f'{get_emoji(COIN_NAME)} {COIN_NAME} `save` took {round(duration,3)}s.')
        else:
            await ctx.send(f'{get_emoji(COIN_NAME)} {COIN_NAME} `save` calling error.')
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
    await botLogChan.send(f'{EMOJI_REFRESH} {ctx.message.author.name} / {ctx.message.author.id} called `restart`. I will be back soon hopefully.')
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
            if locked - actual + float(userdata_balance['Adjust']) < 0:
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
                if locked - actual + float(userdata_balance['Adjust']) < 0:
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
                if locked - actual + float(userdata_balance['Adjust']) < 0:
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
                if locked - actual + float(userdata_balance['Adjust']) < 0:
                    balance_locked =  num_format_coin(0, COIN_NAME)
                else:
                    balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
            table_data.append([COIN_NAME, balance_actual, balance_locked])
            if wallet['user_wallet_address'] is None:
                COIN_NAME += '*'
    else:
        table_data.append([COIN_NAME, "***", "***"])
    # End of Add XMR
    COIN_NAME = "XTRI"
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
                if locked - actual + float(userdata_balance['Adjust']) < 0:
                    balance_locked =  num_format_coin(0, COIN_NAME)
                else:
                    balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
            table_data.append([COIN_NAME, balance_actual, balance_locked])
    else:
        table_data.append([COIN_NAME, "***", "***"])
    # End of Add XTRI
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


@bot.command(pass_context=True, name='info', aliases=['wallet'], help=bot_help_info)
async def info(ctx, coin: str = None):
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'info')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

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
                f'Ignored Tip in: {chanel_ignore_list}\n'
                f'```\n{extra_text}')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
    else:
        COIN_NAME = coin.upper()
        pass

    try:
        coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    except Exception as e:
        print(e)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**')
        return
    
    if (COIN_NAME in MAINTENANCE_COIN) and (ctx.message.author.id not in MAINTENANCE_OWNER):
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
        wallet = await store.sql_get_userwallet(ctx.message.author.id, COIN_NAME)
        depositAddress = await DOGE_LTC_getaccountaddress(ctx.message.author.id, COIN_NAME)
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
    if (coin is None) or (PUBMSG == "PUB"):
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
                    return
                else:
                    balance_actual = num_format_coin(wallet['actual_balance'], COIN_NAME)
                    balance_locked = num_format_coin(wallet['locked_balance'], COIN_NAME)
                    balance_total = num_format_coin((wallet['actual_balance'] + wallet['locked_balance']), COIN_NAME)
                    coinName = COIN_NAME
                    if wallet['user_wallet_address'] is None:
                        coinName += '*'
                    if wallet['forwardtip'] == "ON":
                        coinName += ' >>'
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
                if locked - actual + float(userdata_balance['Adjust']) < 0:
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
                    if locked - actual + float(userdata_balance['Adjust']) < 0:
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
                    if locked - actual + float(userdata_balance['Adjust']) < 0:
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
                    if locked - actual + float(userdata_balance['Adjust']) < 0:
                        balance_locked =  num_format_coin(0, COIN_NAME)
                    else:
                        balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
                if wallet['user_wallet_address'] is None:
                    COIN_NAME += '*'
                table_data.append([COIN_NAME, balance_actual, balance_locked])
        else:
            table_data.append([COIN_NAME, "***", "***"])
        # End of Add XMR
        COIN_NAME = "XTRI"
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
                    if locked - actual + float(userdata_balance['Adjust']) < 0:
                        balance_locked =  num_format_coin(0, COIN_NAME)
                    else:
                        balance_locked =  num_format_coin(locked - actual + float(userdata_balance['Adjust']), COIN_NAME)
                table_data.append([COIN_NAME, balance_actual, balance_locked])
        else:
            table_data.append([COIN_NAME, "***", "***"])
        # End of Add XTRI

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
        print(e)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**')
        return

    if COIN_NAME in MAINTENANCE_COIN:
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
                if locked - actual + float(userdata_balance['Adjust']) < 0:
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
            if locked - actual + float(userdata_balance['Adjust']) < 0:
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
        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} Wallet service hasn\'t started.')
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


@bot.command(pass_context=True, aliases=['botbal'], help=bot_help_botbalance)
async def botbalance(ctx, member: discord.Member, coin: str):
    if member.bot == False:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Only for bot!!')
        return

    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_COIN+ENABLE_COIN_DOGE:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
        return

    walletStatus = None
    if COIN_NAME in MAINTENANCE_COIN:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return

    if COIN_NAME in ENABLE_COIN:
        walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
    elif COIN_NAME in ENABLE_COIN_DOGE:
        walletStatus = await daemonrpc_client.getDaemonRPCStatus(COIN_NAME)

    if walletStatus is None:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} Wallet service hasn\'t started.')
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
            print(e)
        actual = float(await DOGE_LTC_getbalance_acc(bot.user.id, COIN_NAME, 6))
        locked = float(await DOGE_LTC_getbalance_acc(bot.user.id, COIN_NAME, 1))
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
    if COIN_NAME not in ENABLE_COIN:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Please use available ticker: '+ ', '.join(ENABLE_COIN).lower())
        return
    if option.upper() not in ["ON", "OFF"]:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Parameter must be: **ON** or **OFF**')
        return

    userwallet = await store.sql_get_userwallet(ctx.message.author.id, COIN_NAME)
    if userwallet is None:
        userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME)
        userwallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
    #print(userwallet)
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

    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    if COIN_NAME in MAINTENANCE_COIN:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return

    user_id = ctx.message.author.id
    user = await store.sql_get_userwallet(ctx.message.author.id, COIN_NAME)
    if user:
        existing_user = user
        pass

    valid_address = None
    if COIN_NAME in ENABLE_COIN_DOGE:
        depositAddress = await DOGE_LTC_getaccountaddress(ctx.message.author.id, COIN_NAME)
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
            await store.sql_update_user(user_id, wallet_address, COIN_NAME)
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
        user = await store.sql_update_user(user_id, wallet_address, COIN_NAME)
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        await ctx.send(f'{ctx.author.mention} You have registered {COIN_NAME} withdraw address.\n'
                       f'You can use `{server_prefix}withdraw AMOUNT {COIN_NAME}` anytime.')
        return


@bot.command(pass_context=True, help=bot_help_withdraw)
async def withdraw(ctx, amount: str, coin: str = None):
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
    repeatTx = 0
    for itemCoin in ENABLE_COIN:
        floodTip = store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration, itemCoin.upper())
        repeatTx = repeatTx + floodTip
    if repeatTx >= config.floodTip:
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
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")

    if COIN_NAME in MAINTENANCE_COIN:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return
    user = None
    if coin_family == "TRTL" or coin_family == "CCX":
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        user = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        netFee = get_tx_fee(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
    elif coin_family == "XMR":
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        netFee = get_tx_fee(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        userdata_balance = store.sql_xmr_balance(str(ctx.message.author.id), COIN_NAME)

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

        withdrawTx = None
        print(user_from)
        if user_from['user_wallet_address']:
            withdrawTx = await store.sql_external_xmr_single(str(ctx.message.author.id), real_amount,
                                                             user_from['user_wallet_address'],
                                                             COIN_NAME, "WITHDRAW")
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
        MinTx = config.daemonDOGE.min_tx_amount
        MaxTX = config.daemonDOGE.max_tx_amount
        netFee = config.daemonDOGE.tx_fee
        user_from = {}
        user_from['address'] = await DOGE_LTC_getaccountaddress(ctx.message.author.id, COIN_NAME)
        user_from['actual_balance'] = float(await DOGE_LTC_getbalance_acc(ctx.message.author.id, COIN_NAME, 6))
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
        wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        withdrawTx = None
        if wallet['user_wallet_address']:
            withdrawTx = await store.sql_external_doge_single(ctx.message.author.id, real_amount,
                                                              config.daemonDOGE.tx_fee, wallet['user_wallet_address'],
                                                              COIN_NAME, "WITHDRAW")
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

    if user['user_wallet_address'] is None:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You do not have a withdrawal address, please use '
                       f'`{server_prefix}register wallet_address` to register.')
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
    if coin_family == "TRTL" or coin_family == "CCX":
        walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)

        if walletStatus is None:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} Wallet service hasn\'t started.')
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
    elif coin_family == "XMR":
        pass

    withdraw = None
    try:
        if coin_family == "TRTL" or coin_family == "CCX":
            withdrawal = await store.sql_withdraw(str(ctx.message.author.id), real_amount, COIN_NAME)
            tip_tx_hash = withdrawal
            tip_tx_tipper = "Transaction hash: `{}`".format(withdrawal)
    except Exception as e:
        print(e)

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
    repeatTx = 0
    for itemCoin in ENABLE_COIN:
        floodTip = store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration, itemCoin.upper())
        repeatTx = repeatTx + floodTip
    if repeatTx >= config.floodTip:
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
        await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} in maintenance.')
        return

    if coin_family == "TRTL" or coin_family == "CCX":
        CoinAddress = get_donate_address(COIN_NAME)
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        netFee = get_tx_fee(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
    elif coin_family == "XMR":
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        netFee = get_tx_fee(COIN_NAME)
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
    if coin_family == "TRTL" or coin_family == "CCX":
        walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
        if walletStatus is None:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} Wallet service hasn\'t started.')
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
    elif coin_family == "XMR":
        pass

    tip = None
    try:
        tip = await store.sql_donate(str(ctx.message.author.id), CoinAddress, real_amount, COIN_NAME)
        if coin_family == "XMR":
            tip_tx_hash = tip['tx_hash']
            tip_tx_key = tip['tx_key']
            tip_tx_fee = num_format_coin(tip['fee'], COIN_NAME)
            tip_tx_tipper = "Transaction hash: `{}`".format(tip_tx_hash) + "\n" + \
                            "Transaction key: `{}`".format(tip_tx_key) + "\n" + \
                            "Transaction fee: `{}{}`".format(tip_tx_fee, COIN_NAME)
        elif coin_family == "TRTL" or coin_family == "CCX":
            tip_tx_hash = tip
            tip_tx_tipper = "Transaction hash: `{}`".format(tip)
    except Exception as e:
        print(e)

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
        await ctx.send(f'{ctx.author.mention} Thank you but you may need to `optimize` or try again later.')
        # add to failed tx table
        store.sql_add_failed_tx(COIN_NAME, str(ctx.message.author.id), ctx.message.author.name, real_amount, "DONATE")
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


@bot.command(pass_context=True, help=bot_help_tip)
async def tip(ctx, amount: str, *args):
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'tip')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

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
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
        return

    if len(ctx.message.mentions) == 0:
        # Use how time.
        if len(args) >= 2:
            time_given = None
            if args[0].upper() == "LAST" or args[1].upper() == "LAST":
                time_string = ctx.message.content.lower().split("last",1)[1].strip()
                time_second = None
                try:
                    time_string = time_string.replace("day", "d")
                    time_string = time_string.replace("days", "d")
                    time_string = time_string.replace("hours", "h")
                    time_string = time_string.replace("minutes", "mn")
                    time_string = time_string.replace("hrs", "h")
                    time_string = time_string.replace("hr", "h")
                    time_string = time_string.replace("mns", "mn")
                    mult = {'d': 24*60*60, 'h': 60*60, 'mn': 60}
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
        netFee = get_tx_fee(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
    elif coin_family == "XMR":
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        netFee = 0 # get_tx_fee(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        userdata_balance = store.sql_xmr_balance(str(ctx.message.author.id), COIN_NAME)
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
        tip = store.sql_mv_xmr_single(str(ctx.message.author.id), str(member.id), real_amount, COIN_NAME, "TIP")
        if tip:
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
            servername = serverinfo['servername']
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Tip of {num_format_coin(real_amount, COIN_NAME)} '
                    f'{COIN_NAME} '
                    f'was sent to `{member.name}` in server `{servername}`\n')
            except discord.Forbidden:
                print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            if str(member.id) not in notifyList:
                try:
                    await member.send(
                        f'{EMOJI_MONEYFACE} You got a tip of {num_format_coin(real_amount, COIN_NAME)} '
                        f'{COIN_NAME} from `{ctx.message.author.name}` in server `{servername}`\n'
                        f'{NOTIFICATION_OFF_CMD}')
                except discord.Forbidden:
                    print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
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
            await ctx.message.add_reaction(get_emoji(COIN_NAME))
            servername = serverinfo['servername']
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Tip of {num_format_coin(real_amount, COIN_NAME)} '
                    f'{COIN_NAME} '
                    f'was sent to `{member.name}` in server `{servername}`\n')
            except discord.Forbidden:
                print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            if str(member.id) not in notifyList:
                try:
                    await member.send(
                        f'{EMOJI_MONEYFACE} You got a tip of {num_format_coin(real_amount, COIN_NAME)} '
                        f'{COIN_NAME} from `{ctx.message.author.name}` in server `{servername}`\n'
                        f'{NOTIFICATION_OFF_CMD}')
                except discord.Forbidden:
                    print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
                    store.sql_toggle_tipnotify(str(member.id), "OFF")
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
    if coin_family == "TRTL" or coin_family == "CCX":
        walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
        if walletStatus is None:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} Wallet service hasn\'t started.')
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
    elif coin_family == "XMR":
        tip = store.sql_mv_xmr_single(str(ctx.message.author.id), str(member.id), real_amount, COIN_NAME, "TIP")
        if tip:
            servername = serverinfo['servername']
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Tip of {num_format_coin(real_amount, COIN_NAME)} '
                    f'{COIN_NAME} '
                    f'was sent to `{member.name}` in server `{servername}`\n')
            except discord.Forbidden:
                print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            if str(member.id) not in notifyList:
                try:
                    await member.send(
                        f'{EMOJI_MONEYFACE} You got a tip of {num_format_coin(real_amount, COIN_NAME)} '
                        f'{COIN_NAME} from `{ctx.message.author.name}` in server `{servername}`\n'
                        f'{NOTIFICATION_OFF_CMD}')
                except discord.Forbidden:
                    print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
                    store.sql_toggle_tipnotify(str(member.id), "OFF")
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            return

    tip = None
    try:
        if coin_family == "TRTL" or coin_family == "CCX":
            tip = await store.sql_send_tip(str(ctx.message.author.id), str(member.id), real_amount, COIN_NAME)
            tip_tx_hash = tip
            tip_tx_tipper = "Transaction hash: `{}`".format(tip)
    except Exception as e:
        print(e)
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
                f'was sent to `{member.name}` in server `{servername}`\n'
                f'{tip_tx_tipper}')
        except discord.Forbidden:
            # add user to notifyList
            print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
            store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
        if str(member.id) not in notifyList:
            try:
                await member.send(
                    f'{EMOJI_MONEYFACE} You got a tip of {num_format_coin(real_amount, COIN_NAME)} '
                    f'{COIN_NAME} from `{ctx.message.author.name}` in server `{servername}`\n'
                    f'Transaction hash: `{tip_tx_hash}`\n'
                    f'{NOTIFICATION_OFF_CMD}')
            except discord.Forbidden:
                # add user to notifyList
                print('Adding: ' + str(member.id) + ' not to receive DM tip')
                store.sql_toggle_tipnotify(str(member.id), "OFF")
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Can not deliver TX for {COIN_NAME} right now. Try again soon.')
        # add to failed tx table
        store.sql_add_failed_tx(COIN_NAME, str(ctx.message.author.id), ctx.message.author.name, real_amount, "TIP")
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
        await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} in maintenance.')
        return

    # Check flood of tip
    repeatTx = 0
    for itemCoin in ENABLE_COIN:
        floodTip = store.sql_get_countLastTip(str(ctx.message.author.id), config.floodTipDuration, itemCoin.upper())
        repeatTx = repeatTx + floodTip
    if repeatTx >= config.floodTip:
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
        netFee = get_tx_fee(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
    if coin_family == "XMR":
        COIN_DEC = get_decimal(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        netFee = 0 # get_tx_fee(COIN_NAME)
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
            except discord.Forbidden:
                # add user to notifyList
                print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
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
                                except discord.Forbidden:
                                    # add user to notifyList
                                    print('Adding: ' + str(member.id) + ' not to receive DM tip')
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
        user_from['actual_balance'] = float(await DOGE_LTC_getbalance_acc(ctx.message.author.id, COIN_NAME, 6))
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

        listMembers = [member for member in ctx.guild.members if member.status != discord.Status.offline]
        # Check number of receivers.
        if len(listMembers) > config.tipallMax:
            await ctx.message.add_reaction(EMOJI_ERROR)
            try:
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} The number of receivers are too many. This command isn\'t available here.')
            except discord.Forbidden:
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
            except discord.Forbidden:
                # add user to notifyList
                print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
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
                                except discord.Forbidden:
                                    # add user to notifyList
                                    print('Adding: ' + str(member.id) + ' not to receive DM tip')
                                    store.sql_toggle_tipnotify(str(member.id), "OFF")
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
        return

    listMembers = [member for member in ctx.guild.members if member.status != discord.Status.offline]
    # Check number of receivers.
    if len(listMembers) > config.tipallMax:
        await ctx.message.add_reaction(EMOJI_ERROR)
        try:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} The number of receivers are too many. This command isn\'t available here.')
        except discord.Forbidden:
            await ctx.message.author.send(f'{EMOJI_RED_NO} The number of receivers are too many in `{ctx.guild.name}`. This command isn\'t available here.')
        return
    # End of checking receivers numbers.

    memids = []  # list of member ID
    has_forwardtip = None
    list_receivers = []
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
                    if address_to:
                        list_receivers.append(str(member.id))
                        memids.append(address_to)

    user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)

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

    if coin_family == "TRTL" or coin_family == "CCX":
    # Get wallet status
        walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
        if walletStatus is None:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} Wallet service hasn\'t started.')
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
    elif coin_family == "XMR":
        pass
    # print(destinations)
    tip = None
    try:
        if coin_family == "TRTL" or coin_family == "CCX":
            tip = await store.sql_send_tipall(str(ctx.message.author.id), destinations, real_amount, amountDiv, list_receivers, 'TIPALL', COIN_NAME)
            await store.sql_update_some_balances(addresses, COIN_NAME)
            ActualSpend = int(amountDiv * len(destinations) + netFee)
            tip_tx_hash = tip
            tip_tx_tipper = "Transaction hash: `{}`".format(tip)
    except Exception as e:
        print(e)
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
        except discord.Forbidden:
            # add user to notifyList
            print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
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
                                    f'{COIN_NAME} from `{ctx.message.author.name}` `.tipall` in server `{servername}`\n'
                                    f'{tip_tx_tipper}\n'
                                    f'{NOTIFICATION_OFF_CMD}')
                                numMsg = numMsg + 1
                            except discord.Forbidden:
                                # add user to notifyList
                                print('Adding: ' + str(member.id) + ' not to receive DM tip')
                                store.sql_toggle_tipnotify(str(member.id), "OFF")
        print('Messaged to users: (.tipall): '+str(numMsg))
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Can not deliver TX for {COIN_NAME} right now. Try again soon.')
        # add to failed tx table
        store.sql_add_failed_tx(COIN_NAME, str(ctx.message.author.id), ctx.message.author.name, real_amount, "TIPALL")
        return


@bot.command(pass_context=True, help=bot_help_send)
async def send(ctx, amount: str, CoinAddress: str):
    # check if account locked
    account_lock = await alert_if_userlock(ctx, 'send')
    if account_lock:
        await ctx.message.add_reaction(EMOJI_LOCKED) 
        await ctx.send(f'{EMOJI_RED_NO} {MSG_LOCKED_ACCOUNT}')
        return
    # end of check if account locked

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
        netFee = get_tx_fee(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        addressLength = get_addrlen(COIN_NAME)
        IntaddressLength = get_intaddrlen(COIN_NAME)

        if COIN_NAME in MAINTENANCE_COIN:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} in maintenance.')
            return

        print('{} - {} - {}'.format(COIN_NAME, addressLength, IntaddressLength))
        if len(CoinAddress) == int(addressLength):
            if coin_family == "TRTL" or coin_family == "CCX":
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
            elif COIN_NAME in ENABLE_XMR:
                valid_address = await validate_address_xmr(str(CoinAddress), COIN_NAME)
                if valid_address['valid'] == True:
                    valid_address = CoinAddress
                    pass
                else:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                                   f'`{CoinAddress}`')
                    return
        elif len(CoinAddress) == int(IntaddressLength):
            if coin_family == "TRTL" or coin_family == "CCX":
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
        walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
        if walletStatus is None:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} Wallet service hasn\'t started.')
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
                print(e)
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
                print(e)
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
        netFee = get_tx_fee(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
        real_amount = int(amount * COIN_DEC)
        addressLength = get_addrlen(COIN_NAME)
        IntaddressLength = get_intaddrlen(COIN_NAME)

        valid_address = await validate_address_xmr(str(CoinAddress), COIN_NAME)
        if valid_address['valid'] == False or valid_address['nettype'] != 'mainnet':
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Address: `{CoinAddress}` '
                               'is invalid.')
                return
        # OK valid address
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME)
        userdata_balance = store.sql_xmr_balance(str(ctx.message.author.id), COIN_NAME)
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

        SendTx = await store.sql_external_xmr_single(str(ctx.message.author.id), real_amount,
                                                     CoinAddress, COIN_NAME, "SEND")
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
        if (len(CoinAddress) == 34) and CoinAddress.startswith("D"):
            COIN_NAME = "DOGE"
            addressLength = config.daemonDOGE.AddrLen
            MinTx = config.daemonDOGE.min_tx_amount
            MaxTX = config.daemonDOGE.max_tx_amount
            netFee = config.daemonDOGE.tx_fee
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
            user_from['address'] = await DOGE_LTC_getaccountaddress(ctx.message.author.id, COIN_NAME)
            user_from['actual_balance'] = float(await DOGE_LTC_getbalance_acc(ctx.message.author.id, COIN_NAME, 6))
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

            SendTx = await store.sql_external_doge_single(ctx.message.author.id, real_amount, config.daemonDOGE.tx_fee,
                                                          CoinAddress, COIN_NAME, "SEND")
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
            valid_address = await validate_address_xmr(str(CoinAddress), COIN_NAME)
            if valid_address['valid'] == True:
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
            if CountOpt > 0:
                await ctx.message.add_reaction(EMOJI_OK_HAND)
                await ctx.send(f'***Optimize*** is being processed for {member.name} **{COIN_NAME}**. {CountOpt} fusion tx(s).')
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
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} Wallet service hasn\'t started.')
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
    user_from = await store.sql_get_userwallet(ctx.message.author.id, COIN_NAME)
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
            CountOpt = await store.sql_optimize_do(ctx.message.author.id, COIN_NAME)
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
        print(e)
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
        print(e)
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
    COIN_NAME = None
    if (coin is None) and isinstance(ctx.message.channel, discord.DMChannel) == False:
            serverinfo = get_info_pref_coin(ctx)
            COIN_NAME = serverinfo['default_coin'].upper()
    elif (coin is None) and isinstance(ctx.message.channel, discord.DMChannel):
        COIN_NAME = "BOT"
    elif coin:
        COIN_NAME = coin.upper()

    if (COIN_NAME not in (ENABLE_COIN+ENABLE_XMR)) and COIN_NAME != "BOT":
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} Please put available ticker: '+ ', '.join(ENABLE_COIN).lower())
        return

    if COIN_NAME in MAINTENANCE_COIN:
        await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} in maintenance.')
        return

    if COIN_NAME == "BOT":
        await bot.wait_until_ready()
        get_all_m = bot.get_all_members()
        #membercount = '[Members] ' + '{:,.0f}'.format(sum([x.member_count for x in bot.guilds]))
        guildnumber = '[Guilds]        ' + '{:,.0f}'.format(len(bot.guilds))
        shardcount = '[Shards]        ' + '{:,.0f}'.format(bot.shard_count)
        totalonline = '[Total Online]  ' + '{:,.0f}'.format(sum(1 for m in get_all_m if str(m.status) != 'offline'))
        uniqmembers = '[Unique user]   ' + '{:,.0f}'.format(len(bot.users))
        channelnumb = '[Channels]      ' + '{:,.0f}'.format(sum(1 for g in bot.guilds for _ in g.channels))
        botid = '[Bot ID]        ' + str(bot.user.id)
        botstats = '**[ TIPBOT ]**\n'
        botstats = botstats + '```'
        botstats = botstats + botid + '\n' + guildnumber + '\n' + shardcount + '\n' + totalonline + '\n' + uniqmembers + '\n' + channelnumb
        botstats = botstats + '```'
        await ctx.send(f'{botstats}')
        await ctx.send('Please add ticker: '+ ', '.join(ENABLE_COIN).lower() + ' to get stats about coin instead.')
        return

    gettopblock = None
    try:
        gettopblock = await daemonrpc_client.gettopblock(COIN_NAME)
    except Exception as e:
        print(e)
    walletStatus = None
    try:
        walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
    except Exception as e:
        print(e)
    
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    
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
        if (walletStatus is None) or coin_family == "XMR":
            msg = await ctx.send(f'**[ {COIN_NAME} ]**\n'
                           f'```[NETWORK HEIGHT] {height}\n'
                           f'[TIME]           {ago}\n'
                           f'[DIFFICULTY]     {difficulty}\n'
                           f'[BLOCK REWARD]   {reward}{COIN_NAME}\n'
                           f'[NETWORK HASH]   {hashrate}\n```')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        else:
            localDaemonBlockCount = int(walletStatus['blockCount'])
            networkBlockCount = int(walletStatus['knownBlockCount'])
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount/networkBlockCount*100,2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            walletBalance = await get_sum_balances(COIN_NAME)
            COIN_DEC = get_decimal(COIN_NAME)
            balance_str = ''
            if ('unlocked' in walletBalance) and ('locked' in walletBalance):
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
                           f'[WALLET SYNC %]: {t_percent}\n'
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
    COIN_NAME = None
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

    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if COIN_NAME not in (ENABLE_COIN + ENABLE_XMR):
        await ctx.message.add_reaction(EMOJI_ERROR)
        msg = await ctx.send(f'{ctx.author.mention} Please put available ticker: '+ ', '.join(ENABLE_COIN).lower())
        return
    elif COIN_NAME in MAINTENANCE_COIN:
        await ctx.message.add_reaction(EMOJI_ERROR)
        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} is under maintenance.')
        await msg.add_reaction(EMOJI_OK_BOX)
        return

    gettopblock = None
    try:
        gettopblock = await daemonrpc_client.gettopblock(COIN_NAME)
    except Exception as e:
        print(e)

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
    else:
        servername = serverinfo['servername']
        server_id = str(ctx.guild.id)
        server_prefix = serverinfo['prefix']
        server_coin = serverinfo['default_coin'].upper()

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
            if args[1] not in [".", "?", "*", "!"]:
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
            if args[1].upper() not in ENABLE_COIN:
                await ctx.send('{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**!')
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


async def alert_if_userlock(ctx, cmd: str):
    botLogChan = bot.get_channel(id=LOG_CHAN)
    get_discord_userinfo = None
    try:
        get_discord_userinfo = store.sql_discord_userinfo_get(str(ctx.message.author.id))
    except Exception as e:
        print(e)
    if get_discord_userinfo is None:
        return None
    else:
        if get_discord_userinfo['locked'].upper() == "YES":
            await botLogChan.send(f'{ctx.message.author.name} / {ctx.message.author.id} locked but is commanding `{cmd}`')
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
        return {'server_prefix': server_prefix, 'default_coin': server_coin, 'server_id': server_id, 'servername': ctx.guild.name}


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
    elif CoinAddress.startswith("bit") and (len(CoinAddress) == 98 or len(CoinAddress) == 109):
        COIN_NAME = "XTOR"
    elif (CoinAddress.startswith("4") or CoinAddress.startswith("8")) and (len(CoinAddress) == 95 or len(CoinAddress) == 106):
        COIN_NAME = "XMR"
    elif CoinAddress.startswith("L") and (len(CoinAddress) == 95 or len(CoinAddress) == 106):
        COIN_NAME = "LOKI"
    elif CoinAddress.startswith("T") and (len(CoinAddress) == 97 or len(CoinAddress) == 98 or len(CoinAddress) == 109):
        COIN_NAME = "XTRI"
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
    print(error)
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
async def _tip(ctx, amount, coin: str):
    serverinfo = store.sql_info_by_server(str(ctx.guild.id))
    COIN_NAME = coin.upper()
    try:
        amount = float(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    notifyList = store.sql_get_tipnotify()
    coin_family = getattr(getattr(config,"daemon"+COIN_NAME),"coin_family","TRTL")
    if coin_family == "TRTL" or coin_family == "CCX":
        COIN_DEC = get_decimal(COIN_NAME)
        netFee = get_tx_fee(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
    elif coin_family == "XMR":
        COIN_DEC = get_decimal(COIN_NAME)
        netFee = 0 # get_tx_fee(COIN_NAME)
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
            tips = store.sql_mv_xmr_multiple(ctx.message.author.id, memids, real_amount, COIN_NAME, "TIPS")
        except Exception as e:
            print(e)
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
            except discord.Forbidden:
                print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
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
                            except discord.Forbidden:
                                print('Adding: ' + str(member.id) + ' not to receive DM tip')
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
        user_from['actual_balance'] = float(await DOGE_LTC_getbalance_acc(ctx.message.author.id, COIN_NAME, 6))
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
            tips = store.sql_mv_doge_multiple(ctx.message.author.id, memids, real_amount, COIN_NAME, "TIPS")
        except Exception as e:
            print(e)
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
            except discord.Forbidden:
                print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
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
                            except discord.Forbidden:
                                print('Adding: ' + str(member.id) + ' not to receive DM tip')
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
    try:
        real_amount = int(round(float(amount) * COIN_DEC))
    except:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Amount must be a number.')
        return

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
            if address_to:
                list_receivers.append(str(member.id))
                memids.append(address_to)

    addresses = []
    for desti in memids:
        destinations.append({"address": desti, "amount": real_amount})
        addresses.append(desti)

    #print('destinations: ')
    #print(destinations)
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
    if coin_family == "TRTL" or coin_family == "CCX":
        walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
        if walletStatus is None:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} Wallet service hasn\'t started.')
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
    elif coin_family == "XMR":
        tips = store.sql_xmr_multiple(str(ctx.message.author.id), memids, real_amount, COIN_NAME, "TIPS")
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
            except discord.Forbidden:
                # add user to notifyList
                print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
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
                                except discord.Forbidden:
                                    # add user to notifyList
                                    print('Adding: ' + str(member.id) + ' not to receive DM tip')
                                    store.sql_toggle_tipnotify(str(member.id), "OFF")
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
        return
    # TRTL fam
    tip = None
    try:
        tip = await store.sql_send_tipall(str(ctx.message.author.id), destinations, real_amount, real_amount, list_receivers, 'TIPS', COIN_NAME)
        if coin_family == "XMR":
            ActualSpend = real_amount * len(memids) + tip['fee']
            tip_tx_hash = tip['tx_hash']
            tip_tx_fee = num_format_coin(tip['fee'], COIN_NAME)
            tip_tx_tipper = "Transaction hash: `{}`".format(tip_tx_hash) + "\n" + \
                            "Transaction fee: `{}{}`".format(tip_tx_fee, COIN_NAME)
        elif coin_family == "TRTL" or coin_family == "CCX":
            tip_tx_hash = tip
            tip_tx_tipper = "Transaction hash: `{}`".format(tip)
    except Exception as e:
        print(e)
    if tip:
        servername = serverinfo['servername']
        try:
            await store.sql_update_some_balances(addresses, COIN_NAME)
        except Exception as e:
            print(e)
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
        except discord.Forbidden:
            print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
            store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
        for member in ctx.message.mentions:
            if ctx.message.author.id != member.id:
                if member.bot == False:
                    if str(member.id) not in notifyList:
                        try:
                            await member.send(f'{EMOJI_MONEYFACE} You got a tip of  {num_format_coin(real_amount, COIN_NAME)} '
                                            f'{COIN_NAME} from `{ctx.message.author.name}` in server `{servername}`\n'
                                            f'{tip_tx_tipper}\n'
                                            f'{NOTIFICATION_OFF_CMD}')
                        except discord.Forbidden:
                            print('Adding: ' + str(member.id) + ' not to receive DM tip')
                            store.sql_toggle_tipnotify(str(member.id), "OFF")
                        pass
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You may need to `optimize` or try again.')
        # add to failed tx table
        store.sql_add_failed_tx(COIN_NAME, str(ctx.message.author.id), ctx.message.author.name, real_amount, "TIPS")
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
    if coin_family not in ["TRTL", "CCX", "DOGE"]:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} is restricted with this command.')
        return
    if coin_family == "TRTL" or coin_family == "CCX":
        COIN_DEC = get_decimal(COIN_NAME)
        netFee = get_tx_fee(COIN_NAME)
        MinTx = get_min_tx_amount(COIN_NAME)
        MaxTX = get_max_tx_amount(COIN_NAME)
    elif coin_family == "XMR":
        COIN_DEC = get_decimal(COIN_NAME)
        netFee = 0 # get_tx_fee(COIN_NAME)
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
            print(e)
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
            except discord.Forbidden:
                print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
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
                            except discord.Forbidden:
                                print('Adding: ' + str(member.id) + ' not to receive DM tip')
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
            print(e)
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
            except discord.Forbidden:
                print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
                store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
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
                            except discord.Forbidden:
                                print('Adding: ' + str(member.id) + ' not to receive DM tip')
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
    try:
        real_amount = int(round(float(amount) * COIN_DEC))
    except:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Amount must be a number.')
        return

    user_from = await store.sql_get_userwallet(ctx.message.author.id, COIN_NAME)

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
    has_forwardtip = None
    list_receivers = []
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
            if address_to:
                list_receivers.append(str(member_id))
                memids.append(address_to)


    # Check number of receivers.
    if len(memids) > config.tipallMax:
        await ctx.message.add_reaction(EMOJI_ERROR)
        try:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} The number of receivers are too many.')
        except discord.Forbidden:
            await ctx.message.author.send(f'{EMOJI_RED_NO} The number of receivers are too many in `{ctx.guild.name}`.')
        return
    # End of checking receivers numbers.

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
    walletStatus = await daemonrpc_client.getWalletStatus(COIN_NAME)
    if walletStatus is None:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {COIN_NAME} Wallet service hasn\'t started.')
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
    except Exception as e:
        print(e)
    if tip:
        servername = serverinfo['servername']
        await store.sql_update_some_balances(addresses, COIN_NAME)
        await ctx.message.add_reaction(get_emoji(COIN_NAME))
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
        except discord.Forbidden:
            print('Adding: ' + str(ctx.message.author.id) + ' not to receive DM tip')
            store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
        mention_list_name = ''
        for member_id in list_talker:
            if ctx.message.author.id != int(member_id):
                member = bot.get_user(id=int(member_id))
                if member.bot == False:
                    mention_list_name = mention_list_name + '`'+member.name + '` '
                    if str(member_id) not in notifyList:
                        try:
                            await member.send(f'{EMOJI_MONEYFACE} You got a tip of {num_format_coin(real_amount, COIN_NAME)} '
                                            f'{COIN_NAME} from `{ctx.message.author.name}` in server `{servername}` for active talking.\n'
                                            f'Transaction hash: `{tip}`\n'
                                            f'{NOTIFICATION_OFF_CMD}')
                        except discord.Forbidden:
                            print('Adding: ' + str(member.id) + ' not to receive DM tip')
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


def truncate(number, digits) -> float:
    stepper = pow(10.0, digits)
    return math.trunc(stepper * number) / stepper


@click.command()
def main():
    #bot.loop.create_task(update_balance_wallets())
    bot.run(config.discord.token, reconnect=True)


if __name__ == '__main__':
    main()
