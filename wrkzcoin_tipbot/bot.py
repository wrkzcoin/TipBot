import asyncio
import click
import discord
import time, timeago, json
from discord.ext import commands

import sys
sys.path.append("..")
import store, addressvalidation
from config import config

## regex
import re
## reaction
from discord.utils import get
from datetime import datetime
import math
import qrcode
import os.path
import uuid

## ascii table
from terminaltables import AsciiTable

# CapEtn: 386761001808166912
# Need to put some
MAINTENANCE_OWNER = [ 386761001808166912 ] ## list owner
IS_MAINTENANCE = int(config.maintenance)

COIN_DIGITS = config.coin.decimal
COIN_REPR = config.coin.name
memidsRAND = [] ## list of member ID

## Get them from https://emojipedia.org
EMOJI_MONEYFACE = "\U0001F911"
EMOJI_ERROR = "\u274C"
EMOJI_OK = "\U0001F44C"
EMOJI_WARNING = "\u26A1"

LastTippers = {} ## List of tippers
MaxMute = 0

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
bot_help_optimize = f"Optimize your tip balance of {COIN_REPR} for large `.tip .send .tipall .withdraw`(still testing)."
bot_help_address = f"Check {COIN_REPR} address | Generate {COIN_REPR} integrated address `.address` more info."
bot_help_paymentid = "Make a random payment ID with 64 chars length."
bot_help_address_qr = "Show an input address in QR code image."
bot_help_payment_qr = f"Make QR code image for {COIN_REPR} payment."
bot_help_block = f"Display {COIN_REPR} block information from height or hash."
bot_help_tag = "Display a description or a link about what it is. (-add|-del) requires permission `manage_channels`"

bot = commands.Bot(case_insensitive=True, command_prefix='.', pm_help=True)

@bot.event
async def on_ready():
    print('Ready!')
    print(bot.user.name)
    print(bot.user.id)
    print('------')

    print('Servers connected to:')
    for server in bot.servers:
        print(server.name)

@bot.event
async def on_message(message):
    # do some extra stuff here
    if (int(message.author.id) in MAINTENANCE_OWNER):
        # It is better to set bot to MAINTENANCE mode before restart or stop
        args = message.content.split(" ")
        if (len(args)==2):
            if (args[0].upper()=="MAINTENANCE"):
                if (args[1].upper()=="ON"):
                    IS_MAINTENANCE = 1
                    await bot.send_message(message.author,'Maintenance ON, `maintenance off` to turn it off.')
                    return
                else:
                    IS_MAINTENANCE = 0
                    await bot.send_message(message.author,'Maintenance OFF, `maintenance on` to turn it off.')
                    return
    ## Do not remove this, otherwise, command not working.
    await bot.process_commands(message)

@bot.command(pass_context=True, name='info', aliases=['wallet', 'tipjar'], help=bot_help_info)
async def info(context: commands.Context):
    user = store.sql_register_user(context.message.author.id)
    wallet = store.sql_get_userwallet(context.message.author.id)
    if (wallet is None):
        await bot.send_message(
            context.message.author, 'Internal Error for `.info`')
        return

    if (os.path.exists("/path/to/data/qrcodes/"+wallet['balance_wallet_address']+".png")):
        pass		
    else:
        ## do some QR code
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
        img.save("/path/to/data/qrcodes/"+wallet['balance_wallet_address']+".png")

    if ('user_wallet_address' in wallet):
        await bot.add_reaction(context.message, EMOJI_OK)
        await bot.send_file(context.message.author, "/path/to/data/qrcodes/"+wallet['balance_wallet_address']+".png", 
                                content="**QR for your Deposit**")
        await bot.send_message(
            context.message.author, f'**[💁 ACCOUNT INFO]**\n\n'
            '💰 Deposit Address: `'+wallet['balance_wallet_address']+'`\n'
            '⚖️ Registered Wallet: `'+wallet['user_wallet_address']+'`')
    else:
        await bot.add_reaction(context.message, EMOJI_WARNING)
        await bot.send_file(context.message.author, "/path/to/data/qrcodes/"+wallet['balance_wallet_address']+".png", 
                                content="**QR for your Deposit**")
        await bot.send_message(
            context.message.author, f'**[💁 ACCOUNT INFO]**\n\n'
            '💰 Deposit Address: `'+wallet['balance_wallet_address']+'`\n'
            '⚖️ Registered Wallet: `NONE, Please register.`\n')
    return

@bot.command(pass_context=True, name='balance', aliases=['bal'], help=bot_help_balance)
async def balance(context: commands.Context):
    ## Get wallet status
    walletStatus = daemonrpc_client.getWalletStatus()
    if (walletStatus is None):
        await bot.reply('✋ Wallet service hasn\'t started.')
        return
    else:
        print(walletStatus)
        localDaemonBlockCount = int(walletStatus['blockCount'])
        networkBlockCount = int(walletStatus['knownBlockCount'])
        if ((networkBlockCount-localDaemonBlockCount)>=20):
            ## if height is different by 50
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount/networkBlockCount*100,2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            await bot.add_reaction(context.message, EMOJI_WARNING)
            await bot.send_message(context.message.author,
                                    '✋ Wallet service hasn\'t sync fully with network or being re-sync. More info:\n```'
                                    f'networkBlockCount:     {t_networkBlockCount}\n'
                                    f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                                    f'Progress %:            {t_percent}\n```'
                                    )
            return
        else:
            pass
    ## End of wallet status

    ## Check if maintenance
    if (IS_MAINTENANCE==1):
        if (int(context.message.author.id) in MAINTENANCE_OWNER):
            pass
        else:
            await bot.add_reaction(context.message, EMOJI_WARNING)
            await bot.send_message(context.message.author, f'✋ {config.maintenance_msg}')
            return
    else:
        pass
    ## End Check if maintenance

    user = store.sql_register_user(context.message.author.id)
    wallet = store.sql_get_userwallet(context.message.author.id)
    if ('lastUpdate' in wallet):
        await bot.add_reaction(context.message, EMOJI_OK)
        try:
            update = datetime.fromtimestamp(int(wallet['lastUpdate'])).strftime('%Y-%m-%d %H:%M:%S')
            ago = timeago.format(update, datetime.now())
            print(ago)
        except:
            pass
    balance_actual = '{:,.2f}'.format(wallet['actual_balance'] / COIN_DIGITS)
    balance_locked = '{:,.2f}'.format(wallet['locked_balance'] / COIN_DIGITS)
    await bot.send_message(
        context.message.author, '**[💰 YOUR BALANCE]**\n\n'
        f'💰 Available: {balance_actual} '
        f'{COIN_REPR}\n'
        f'💰 Pending: {balance_locked} '
        f'{COIN_REPR}\n')
    if(ago):
        await bot.send_message(
            context.message.author, f'⌛Last update: {ago}')

@bot.command(pass_context=True, aliases=['botbal'], help=bot_help_botbalance)
async def botbalance(context: commands.Context, member: discord.Member=None):
    ## Get wallet status
    walletStatus = daemonrpc_client.getWalletStatus()
    if (walletStatus is None):
        await bot.reply('✋ Wallet service hasn\'t started.')
        return
    else:
        print(walletStatus)
        localDaemonBlockCount = int(walletStatus['blockCount'])
        networkBlockCount = int(walletStatus['knownBlockCount'])
        if ((networkBlockCount-localDaemonBlockCount)>=20):
            ## if height is different by 50
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount/networkBlockCount*100,2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            await bot.add_reaction(context.message, EMOJI_WARNING)
            await bot.send_message(context.message.author,
                                    '✋ Wallet service hasn\'t sync fully with network or being re-sync. More info:\n```'
                                    f'networkBlockCount:     {t_networkBlockCount}\n'
                                    f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                                    f'Progress %:            {t_percent}\n```'
                                    )
            return
        else:
            pass
    ## End of wallet status

    ## Check if maintenance
    if (IS_MAINTENANCE==1):
        if (int(context.message.author.id) in MAINTENANCE_OWNER):
            pass
        else:
            await bot.add_reaction(context.message, EMOJI_WARNING)
            await bot.send_message(context.message.author, f'✋ {config.maintenance_msg}')
            return
    else:
        pass
    ## End Check if maintenance

    if (member is None):
        user = store.sql_register_user(bot.user.id)
        wallet = store.sql_get_userwallet(bot.user.id)
        depositAddress = wallet['balance_wallet_address']
        balance_actual = '{:,.2f}'.format(wallet['actual_balance'] / COIN_DIGITS)
        balance_locked = '{:,.2f}'.format(wallet['locked_balance'] / COIN_DIGITS)
        await bot.say(
            f'**[ MY BALANCE]**\n\n'
            f' Deposit Address: `{depositAddress}`\n'
            f'💰 Available: {balance_actual} '
            f'{COIN_REPR}\n'
            f'💰 Pending: {balance_locked} '
            f'{COIN_REPR}\n')
        return
    if (member.bot == False):
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(
            context.message.author, 'Only for bot!!')
        return
    else:
        user = store.sql_register_user(member.id)
        wallet = store.sql_get_userwallet(member.id)
        balance_actual = '{:,.2f}'.format(wallet['actual_balance'] / COIN_DIGITS)
        balance_locked = '{:,.2f}'.format(wallet['locked_balance'] / COIN_DIGITS)
        depositAddress = wallet['balance_wallet_address']
        await bot.reply(
            f'**[💰 INFO BOT {member.name}\'s BALANCE]**\n\n'
            f' Deposit Address: `{depositAddress}`\n'
            f'💰 Available: {balance_actual} '
            f'{COIN_REPR}\n'
            f'💰 Pending: {balance_locked} '
            f'{COIN_REPR}\n')
        return

@bot.command(pass_context=True, name='register', aliases=['registerwallet', 'reg', 'updatewallet'], help=bot_help_register)
async def register(context: commands.Context, wallet_address: str):
    ## Check if maintenance
    if (IS_MAINTENANCE==1):
        if (int(context.message.author.id) in MAINTENANCE_OWNER):
            pass
        else:
            await bot.add_reaction(context.message, EMOJI_WARNING)
            await bot.send_message(context.message.author, f'✋ {config.maintenance_msg}')
            return
    else:
        pass
    ## End Check if maintenance

    user_id = context.message.author.id
    user = store.sql_get_userwallet(context.message.author.id)
    if (user):
        existing_user = user
        pass

    valid_address=addressvalidation.validate_address(wallet_address)
    # correct print(valid_address)
    if (valid_address is None) :
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Invalid address:\n'
                        f'`{wallet_address}`')
        return

    if (valid_address!=wallet_address) :
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Invalid address:\n'
                        f'`{wallet_address}`')
        return

    ## if they want to register with tipjar address
    try:
        if (user['balance_wallet_address']==wallet_address) :
            await bot.add_reaction(context.message, EMOJI_ERROR)
            await bot.send_message(context.message.author,
                            '✋ You can not register with your tipjar\'s address.\n'
                            f'`{wallet_address}`')
            return
        else:
            pass
    except Exception as e:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        print('Error during register user address:'+str(e))
        return
        
    if ('user_wallet_address' in existing_user):
        prev_address = existing_user['user_wallet_address']
        store.sql_update_user(user_id, wallet_address)
        if prev_address:
            await bot.add_reaction(context.message, EMOJI_OK)
            await bot.send_message(
                context.message.author,
                f'Your withdraw address has been changed from:\n'
                f'`{prev_address}`\n to\n '
                f'`{wallet_address}`')
            return
        pass
    else:
        user = store.sql_update_user(user_id, wallet_address)
        await bot.add_reaction(context.message, EMOJI_OK)
        await bot.send_message(context.message.author,
                               'You have been registered a withdraw address.\n'
                               'You can use `.withdraw AMOUNT` anytime.')
        return


@bot.command(pass_context=True, help=bot_help_withdraw)
async def withdraw(context: commands.Context, amount: float):
    # Check flood of tip
    floodTip = store.sql_get_countLastTip(context.message.author.id, 10)
    if (floodTip >= 3):
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author, '✋ Cool down your tip or TX. or increase your amount next time.')
        return
    # End of Check flood of tip

    ## Check if maintenance
    if (IS_MAINTENANCE==1):
        if (int(context.message.author.id) in MAINTENANCE_OWNER):
            pass
        else:
            await bot.add_reaction(context.message, EMOJI_WARNING)
            await bot.send_message(context.message.author, f'✋ {config.maintenance_msg}')
            return
    else:
        pass
    ## End Check if maintenance

    try:
        amount = float(amount)
    except ValueError:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        '✋ Invalid amount.')
        return

    user = store.sql_get_userwallet(context.message.author.id)
    real_amount = int(amount * COIN_DIGITS)

    if not user['user_wallet_address']:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(
            context.message.author,
            f'You do not have a withdrawal address, please use '
            f'`.register <wallet_address>` to register.')
        return

    if real_amount + config.tx_fee >= user['actual_balance']:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                               f'✋ Insufficient balance to withdraw '
                               f'{real_amount / COIN_DIGITS:.2f} '
                               f'{COIN_REPR}.')
        return

    if real_amount > config.max_tx_amount:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Transactions cannot be bigger than '
                        f'{config.max_tx_amount / COIN_DIGITS:.2f} '
                        f'{COIN_REPR}')
        return
    elif real_amount < config.min_tx_amount:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Transactions cannot be lower than '
                        f'{config.min_tx_amount / COIN_DIGITS:.2f} '
                        f'{COIN_REPR}')
        return

    ## Get wallet status
    walletStatus = daemonrpc_client.getWalletStatus()
    if (walletStatus is None):
        await bot.reply('✋ Wallet service hasn\'t started.')
        return
    else:
        print(walletStatus)
        localDaemonBlockCount = int(walletStatus['blockCount'])
        networkBlockCount = int(walletStatus['knownBlockCount'])
        if ((networkBlockCount-localDaemonBlockCount)>=20):
            ## if height is different by 50
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount/networkBlockCount*100,2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            await bot.add_reaction(context.message, EMOJI_WARNING)
            await bot.send_message(context.message.author,
                                    '✋ Wallet service hasn\'t sync fully with network or being re-sync. More info:\n```'
                                    f'networkBlockCount:     {t_networkBlockCount}\n'
                                    f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                                    f'Progress %:            {t_percent}\n```'
                                    )
            return
        else:
            pass
    ## End of wallet status

    withdrawal = store.sql_withdraw(context.message.author.id, real_amount)
    if (withdrawal is not None):
        await bot.add_reaction(context.message, EMOJI_MONEYFACE)
        await bot.send_message(
            context.message.author,
            f'💰 You have withdrawn {real_amount / COIN_DIGITS:.2f} '
            f'{COIN_REPR}.\n'
            f'Transaction hash: `{withdrawal}`')
        return
    else:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(
            context.message.author,
            'You may need to `.optimize`')
        return

@bot.command(pass_context=True, help=bot_help_donate)
async def donate(context: commands.Context,
              amount: float):
    # Check flood of tip
    floodTip = store.sql_get_countLastTip(context.message.author.id, 10)
    if (floodTip >= 3):
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author, '✋ Cool down your tip or TX. or increase your amount next time.')
        return
    # End of Check flood of tip

    ## Check if maintenance
    if (IS_MAINTENANCE==1):
        if (int(context.message.author.id) in MAINTENANCE_OWNER):
            pass
        else:
            await bot.add_reaction(context.message, EMOJI_WARNING)
            await bot.send_message(context.message.author, f'✋ {config.maintenance_msg}')
            return
    else:
        pass
    ## End Check if maintenance

    try:
        amount = float(amount)
    except ValueError:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        '✋ Invalid amount.')
        return

    CoinAddress = f'{config.coin.DonateAddress}'
    real_amount = int(amount * COIN_DIGITS)
    user_from = store.sql_get_userwallet(context.message.author.id)

    if real_amount + config.tx_fee >= user_from['actual_balance']:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Insufficient balance to donate '
                        f'{real_amount / COIN_DIGITS:.2f} '
                        f'{COIN_REPR}.')
        return

    if real_amount > config.max_tx_amount:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Transactions cannot be bigger than '
                        f'{config.max_tx_amount / COIN_DIGITS:.2f} '
                        f'{COIN_REPR}.')
        return
    elif real_amount < config.min_tx_amount:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Transactions cannot be smaller than '
                        f'{config.min_tx_amount / COIN_DIGITS:.2f} '
                        f'{COIN_REPR}.')

        return

    ## Get wallet status
    walletStatus = daemonrpc_client.getWalletStatus()
    if (walletStatus is None):
        await bot.reply('✋ Wallet service hasn\'t started.')
        return
    else:
        print(walletStatus)
        localDaemonBlockCount = int(walletStatus['blockCount'])
        networkBlockCount = int(walletStatus['knownBlockCount'])
        if ((networkBlockCount-localDaemonBlockCount)>=20):
            ## if height is different by 50
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount/networkBlockCount*100,2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            await bot.add_reaction(context.message, EMOJI_WARNING)
            await bot.send_message(context.message.author,
                                    '✋ Wallet service hasn\'t sync fully with network or being re-sync. More info:\n```'
                                    f'networkBlockCount:     {t_networkBlockCount}\n'
                                    f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                                    f'Progress %:            {t_percent}\n```'
                                    )
            return
        else:
            pass
    ## End of wallet status

    tip = store.sql_donate(context.message.author.id, CoinAddress, real_amount)
    if (tip is not None):
        await bot.add_reaction(context.message, EMOJI_MONEYFACE)
        DonateAmount = '{:,.2f}'.format(real_amount / COIN_DIGITS)
        await bot.send_message(context.message.author,
                        f'💖 TipBot got donation: {DonateAmount} '
                        f'{COIN_REPR} '
                        f'\n'
                        f'Thank you. Transaction hash: `{tip}`')
        return
    else:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        'Thank you but you may need to `.optimize`')
        return

@bot.command(pass_context=True, help=bot_help_tip)
async def tip(context: commands.Context, amount: float,
              member: discord.Member = None):

    # Check flood of tip
    floodTip = store.sql_get_countLastTip(context.message.author.id, 10)
    if (floodTip >= 3):
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author, '✋ Cool down your tip or TX. or increase your amount next time.')
        return
    # End of Check flood of tip

    ## Check if maintenance
    if (IS_MAINTENANCE==1):
        if (int(context.message.author.id) in MAINTENANCE_OWNER):
            pass
        else:
            await bot.add_reaction(context.message, EMOJI_WARNING)
            await bot.send_message(context.message.author, f'✋ {config.maintenance_msg}')
            return
    else:
        pass
    ## End Check if maintenance

    if (str(context.message.channel.type).lower() == "private"):
        await bot.reply('✋ This command can not be in private.')
        return

    if (len(context.message.mentions) > 1):
        await _tip(context, amount)
        return

    user_from = store.sql_get_userwallet(context.message.author.id)
    user_to = store.sql_register_user(member.id)

    try:
        amount = float(amount)
    except ValueError:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        '✋ Invalid amount.')
        return

    real_amount = int(amount * COIN_DIGITS)

    if real_amount + config.tx_fee >= user_from['actual_balance']:
        print('Insufficient balance to send tip')
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Insufficient balance to send tip of '
                        f'{real_amount / COIN_DIGITS:.2f} '
                        f'{COIN_REPR} to {member.mention}.')
        return

    if real_amount > config.max_tx_amount:
        print('Transactions cannot be bigger than')
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Transactions cannot be bigger than '
                        f'{config.max_tx_amount / COIN_DIGITS:.2f} '
                        f'{COIN_REPR}.')
        return
    elif real_amount < config.min_tx_amount:
        print('Transactions cannot be smaller than')
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Transactions cannot be smaller than '
                        f'{config.min_tx_amount / COIN_DIGITS:.2f} '
                        f'{COIN_REPR}.')
        return

    ## Get wallet status
    walletStatus = daemonrpc_client.getWalletStatus()
    if (walletStatus is None):
        await bot.reply('✋ Wallet service hasn\'t started.')
        return
    else:
        print(walletStatus)
        localDaemonBlockCount = int(walletStatus['blockCount'])
        networkBlockCount = int(walletStatus['knownBlockCount'])
        if ((networkBlockCount-localDaemonBlockCount)>=20):
            ## if height is different by 50
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount/networkBlockCount*100,2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            await bot.add_reaction(context.message, EMOJI_WARNING)
            await bot.send_message(context.message.author,
                                    '✋ Wallet service hasn\'t sync fully with network or being re-sync. More info:\n```'
                                    f'networkBlockCount:     {t_networkBlockCount}\n'
                                    f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                                    f'Progress %:            {t_percent}\n```'
                                    )
            return
        else:
            pass
    ## End of wallet status

    tip = store.sql_send_tip(context.message.author.id, member.id, real_amount)
    if (tip is not None):
        tipAmount = '{:,.2f}'.format(real_amount / COIN_DIGITS)
        await bot.add_reaction(context.message, EMOJI_MONEYFACE)
        await bot.send_message(
            context.message.author,
                        f'💰 Tip of {tipAmount} '
                        f'{COIN_REPR} '
                        f'was sent to `{member.name}`\n'
                        f'Transaction hash: `{tip}`')
        await bot.send_message(
            member,
                        f'💰 You got a tip of {tipAmount} '
                        f'{COIN_REPR} from `{context.message.author.name}`\n'
                        f'Transaction hash: `{tip}`')
        return
    else:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        'You may need to `.optimize`')
        return

@bot.command(pass_context=True, help=bot_help_tipall)
async def tipall(context: commands.Context,
              amount: str):

    # Check flood of tip
    floodTip = store.sql_get_countLastTip(context.message.author.id, 10)
    if (floodTip >= 3):
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author, '✋ Cool down your tip or TX. or increase your amount next time.')
        return
    # End of Check flood of tip

    ## Check if maintenance
    if (IS_MAINTENANCE==1):
        if (int(context.message.author.id) in MAINTENANCE_OWNER):
            pass
        else:
            await bot.add_reaction(context.message, EMOJI_WARNING)
            await bot.send_message(context.message.author, f'✋ {config.maintenance_msg}')
            return
    else:
        pass
    ## End Check if maintenance

    ## More precisely, I believe it's <message>.channel.type that you should be checking.
    ## That's "text" for normal channels in servers, and "dm" or "group" for DMs and group DMs, respectively.
    #print(context.message.channel.type)

    if (str(context.message.channel.type).lower() == "private"):
        await bot.reply('✋ This command can not be in private.')
        return

    try:
        amount = float(amount)
    except ValueError:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        '✋ Invalid amount.')
        return

    real_amount = int(amount * COIN_DIGITS)
    listMembers = context.message.server.members

    memids = [] ## list of member ID       
    for member in listMembers:
        #print(member.name) # you'll just print out Member objects your way.
        if (context.message.author.id != member.id) :
            user_to = store.sql_register_user(member.id)
            if (str(member.status) != 'offline'):
                if (member.bot == False):
                    memids.append(user_to['balance_wallet_address'])

    user_from = store.sql_get_userwallet(context.message.author.id)

    if real_amount + config.tx_fee >= user_from['actual_balance']:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Insufficient balance to spread tip of '
                        f'{real_amount / COIN_DIGITS:.2f} '
                        f'{COIN_REPR}.')
        return

    if real_amount > config.max_tx_amount:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Transactions cannot be bigger than '
                        f'{config.max_tx_amount / COIN_DIGITS:.2f} '
                        f'{COIN_REPR}.')
        return
    elif real_amount < config.min_tx_amount:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Transactions cannot be smaller than '
                        f'{config.min_tx_amount / COIN_DIGITS:.2f} '
                        f'{COIN_REPR}.')
        return

    elif (real_amount / len(memids)) < config.min_tx_amount:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Transactions cannot be smaller than '
                        f'{config.min_tx_amount / COIN_DIGITS:.2f} '
                        f'{COIN_REPR} for each member. You need at least {len(memids) * config.min_tx_amount / COIN_DIGITS:.2f}.')
        return

    amountDiv = int(round(real_amount / len(memids), 2)) ## cut 2 decimal only
    destinations = []
    addresses = []
    for desti in memids:
        destinations.append({"address":desti,"amount":amountDiv})
        addresses.append(desti)

    ## Get wallet status
    walletStatus = daemonrpc_client.getWalletStatus()
    if (walletStatus is None):
        await bot.reply('✋ Wallet service hasn\'t started.')
        return
    else:
        print(walletStatus)
        localDaemonBlockCount = int(walletStatus['blockCount'])
        networkBlockCount = int(walletStatus['knownBlockCount'])
        if ((networkBlockCount-localDaemonBlockCount)>=20):
            ## if height is different by 50
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount/networkBlockCount*100,2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            await bot.add_reaction(context.message, EMOJI_WARNING)
            await bot.send_message(context.message.author,
                                    '✋ Wallet service hasn\'t sync fully with network or being re-sync. More info:\n```'
                                    f'networkBlockCount:     {t_networkBlockCount}\n'
                                    f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                                    f'Progress %:            {t_percent}\n```'
                                    )
            return
        else:
            pass
    ## End of wallet status

    #print(destinations)
    try:
        tip = store.sql_send_tipall(context.message.author.id, destinations, real_amount)
    except Exception as e:
        print(e)
    if (tip is not None):
        await bot.add_reaction(context.message, EMOJI_MONEYFACE)
        store.sql_update_some_balances(addresses)
        TotalSpend = '{:,.2f}'.format(real_amount / COIN_DIGITS)
        ActualSpend = int(amountDiv * len(destinations) + config.tx_fee)
        ActualSpend_str = '{:,.2f}'.format(ActualSpend / COIN_DIGITS)
        amountDiv_str = '{:,.2f}'.format(amountDiv / COIN_DIGITS)
        await bot.send_message(
            context.message.author,
                        f'💰 Tip of {TotalSpend} '
                        f'{COIN_REPR} '
                        f'was sent spread to ({len(destinations)}) members.\n'
                        f'Transaction hash: `{tip}`.\n'
                        f'Each member got: `{amountDiv_str}{COIN_REPR}`\n'
                        f'Actual spending: `{ActualSpend_str}{COIN_REPR}`')
        user = discord.User()
        for member in context.message.server.members:
            #print(member.name) # you'll just print out Member objects your way.
            if (context.message.author.id != member.id) :
                if (str(member.status) != 'offline'):
                    if (member.bot == False):
                        user.id=int(member.id)
                        await bot.send_message(
                            user,
                                f'💰 You got a tip of {amountDiv_str} '
                                f'{COIN_REPR} from `{context.message.author.name} .tipall`\n'
                                f'Transaction hash: `{tip}`')
                        pass
        return
    else:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        'You may need to `.optimize`')
        return

@bot.command(pass_context=True, help=bot_help_send)
async def send(context: commands.Context, amount: float, CoinAddress: str):
    # Check flood of tip
    floodTip = store.sql_get_countLastTip(context.message.author.id, 10)
    if (floodTip >= 3):
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author, '✋ Cool down your tip or TX. or increase your amount next time.')
        return
    # End of Check flood of tip

    ## Check if maintenance
    if (IS_MAINTENANCE==1):
        if (int(context.message.author.id) in MAINTENANCE_OWNER):
            pass
        else:
            await bot.add_reaction(context.message, EMOJI_WARNING)
            await bot.send_message(context.message.author, f'✋ {config.maintenance_msg}')
            return
    else:
        pass
    ## End Check if maintenance

    if(len(CoinAddress)==int(config.coin.AddrLen)):
        valid_address=addressvalidation.validate_address(CoinAddress)
        #print(valid_address)
        if (valid_address is None) :
            await bot.add_reaction(context.message, EMOJI_ERROR)
            await bot.send_message(context.message.author,
                            f'✋ Invalid address:\n'
                            f'`{CoinAddress}`')
            return
        if (valid_address!=CoinAddress) :
            await bot.add_reaction(context.message, EMOJI_ERROR)
            await bot.send_message(context.message.author,
                            f'✋ Invalid address:\n'
                            f'`{CoinAddress}`')
            return
    elif(len(CoinAddress)==int(config.coin.IntAddrLen)):
        valid_address=addressvalidation.validate_integrated(CoinAddress)
        #print(valid_address)
        if (valid_address=='invalid'):
            await bot.add_reaction(context.message, EMOJI_ERROR)
            await bot.send_message(context.message.author,
                            f'✋ Invalid integrated address:\n'
                            f'`{CoinAddress}`')
            return
        if(len(valid_address)==2):
            iCoinAddress=CoinAddress
            CoinAddress=valid_address['address']
            paymentid=valid_address['integrated_id']
    else:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Invalid address:\n'
                        f'`{CoinAddress}`')
        return

    try:
        amount = float(amount)
    except ValueError:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        '✋ Invalid amount.')
        return

    real_amount = int(amount * COIN_DIGITS)

    user_from = store.sql_get_userwallet(context.message.author.id)
    if (user_from['balance_wallet_address'] == CoinAddress):
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ You can not send to your own deposit address.')
        return

    if real_amount + config.tx_fee >= user_from['actual_balance']:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Insufficient balance to send tip of '
                        f'{real_amount / COIN_DIGITS:.2f} '
                        f'{COIN_REPR} to {CoinAddress}.')

        return

    if real_amount > config.max_tx_amount:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Transactions cannot be bigger than '
                        f'{config.max_tx_amount / COIN_DIGITS:.2f} '
                        f'{COIN_REPR}.')
        return
    elif real_amount < config.min_tx_amount:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Transactions cannot be smaller than '
                        f'{config.min_tx_amount / COIN_DIGITS:.2f} '
                        f'{COIN_REPR}.')

        return

    ## Get wallet status
    walletStatus = daemonrpc_client.getWalletStatus()
    if (walletStatus is None):
        await bot.reply('✋ Wallet service hasn\'t started.')
        return
    else:
        print(walletStatus)
        localDaemonBlockCount = int(walletStatus['blockCount'])
        networkBlockCount = int(walletStatus['knownBlockCount'])
        if ((networkBlockCount-localDaemonBlockCount)>=20):
            ## if height is different by 50
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount/networkBlockCount*100,2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            await bot.add_reaction(context.message, EMOJI_WARNING)
            await bot.send_message(context.message.author,
                                    '✋ Wallet service hasn\'t sync fully with network or being re-sync. More info:\n```'
                                    f'networkBlockCount:     {t_networkBlockCount}\n'
                                    f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                                    f'Progress %:            {t_percent}\n```'
                                    )
            return
        else:
            pass
    ## End of wallet status

    if(len(valid_address)==2):
        print(valid_address)
        print('Process integrate address...')
        tip = store.sql_send_tip_Ex_id(context.message.author.id, CoinAddress, real_amount, paymentid)
        if (tip is not None):
            await bot.add_reaction(context.message, EMOJI_MONEYFACE)
            await bot.send_message(context.message.author,
                            f'💰 Tip of {real_amount / COIN_DIGITS:.2f} '
                            f'{COIN_REPR} '
                            f'was sent to `{iCoinAddress}`\n'
                            f'Address: `{CoinAddress}`\n'
                            f'Payment ID: `{paymentid}`\n'
                            f'Transaction hash: `{tip}`')
            return
        else:
            await bot.add_reaction(context.message, EMOJI_ERROR)
            await bot.send_message(context.message.author,
                            'You may need to `.optimize`')
            return
    else:
        print('Process normal address...')
        tip = store.sql_send_tip_Ex(context.message.author.id, CoinAddress, real_amount)
        if (tip is not None):
            await bot.add_reaction(context.message, EMOJI_MONEYFACE)
            await bot.send_message(context.message.author,
                            f'💰 Tip of {real_amount / COIN_DIGITS:.2f} '
                            f'{COIN_REPR} '
                            f'was sent to `{CoinAddress}`\n'
                            f'Transaction hash: `{tip}`')
            return
        else:
            await bot.add_reaction(context.message, EMOJI_ERROR)
            await bot.send_message(context.message.author,
                            'You may need to `.optimize`')
            return

@bot.command(pass_context=True, name='address', aliases=['addr'], help=bot_help_address)
async def address(context: commands.Context, *args):
    if(len(args)==0):
        await bot.say('**[ ADDRESS CHECKING EXAMPLES ]**\n\n'
                        '`.address WrkzRNDQDwFCBynKPc459v3LDa1gEGzG3j962tMUBko1fw9xgdaS9mNiGMgA9s1q7hS1Z8SGRVWzcGc8Sh8xsvfZ6u2wJEtoZB`\n'
                        'That will check if the address is valid. Integrated address is also supported. '
                        'If integrated address is input, bot will tell you the result of :address + paymentid\n\n'
                        '`.address <coin_address> <paymentid>`\n'
                        'This will generate an integrate address.\n\n')
        return
    if(len(args)==1):
        CoinAddress=args[0]
        if(len(CoinAddress)==int(config.coin.AddrLen)):
            if not re.match(r'Wrkz[a-zA-Z0-9]{94,}', CoinAddress.strip()):
                await bot.add_reaction(context.message, EMOJI_ERROR)
                await bot.reply(f'✋ Address: `{CoinAddress}`\n'
                                'Checked: Invalid. Should start with Wrkz.')
                return
            else:
                valid_address=addressvalidation.validate_address(CoinAddress)
                if (valid_address is None) :
                    await bot.add_reaction(context.message, EMOJI_ERROR)
                    await bot.reply(f'✋ Address: `{CoinAddress}`\n'
                                    'Checked: Invalid.')
                    return
                else:
                    await bot.add_reaction(context.message, EMOJI_OK)
                    if(valid_address==CoinAddress):
                        await bot.reply(f'Address: `{CoinAddress}`\n'
                                        'Checked: Valid.')
                    return
            return
        elif(len(CoinAddress)==int(config.coin.IntAddrLen)):
            ## Integrated address
            if not re.match(r'Wrkz[a-zA-Z0-9]{182,}', CoinAddress.strip()):
                await bot.add_reaction(context.message, EMOJI_ERROR)
                await bot.reply(f'✋ Integrated Address: `{CoinAddress}`\n'
                                'Checked: Invalid. Should start with Wrkz.')
                return
            else:
                valid_address=addressvalidation.validate_integrated(CoinAddress)
                if (valid_address=='invalid'):
                    await bot.add_reaction(context.message, EMOJI_ERROR)
                    await bot.reply(f'✋ Integrated Address: `{CoinAddress}`\n'
                                    'Checked: Invalid.')
                    return
                if(len(valid_address)==2):
                    await bot.add_reaction(context.message, EMOJI_OK)
                    iCoinAddress=CoinAddress
                    CoinAddress=valid_address['address']
                    paymentid=valid_address['integrated_id']
                    await bot.reply(f'\nIntegrated Address: `{iCoinAddress}`\n\n'
                                    f'Address: `{CoinAddress}`\n'
                                    f'PaymentID: `{paymentid}`')
                    return
                return
        else:
            ## incorrect length
            await bot.add_reaction(context.message, EMOJI_ERROR)
            await bot.reply(f'✋ Address: `{CoinAddress}`\n'
                            'Checked: Incorrect length')
            return
    if(len(args)==2):
        ## generate integrated address:
        CoinAddress=args[0]
        paymentid=args[1]
        if(len(CoinAddress)==int(config.coin.AddrLen)):
            if not re.match(r'Wrkz[a-zA-Z0-9]{94,}', CoinAddress.strip()):
                await bot.add_reaction(context.message, EMOJI_ERROR)
                await bot.reply(f'✋ Address: `{CoinAddress}`\n'
                                'Checked: Invalid. Should start with Wrkz.')
                return
            else:
                valid_address=addressvalidation.validate_address(CoinAddress)
                if (valid_address is None) :
                    await bot.add_reaction(context.message, EMOJI_ERROR)
                    await bot.reply(f'✋ Address: `{CoinAddress}`\n'
                                    'Checked: Incorrect given address.')
                    return
                else:
                    pass
        else:
            await bot.add_reaction(context.message, EMOJI_ERROR)
            await bot.reply(f'✋ Address: `{CoinAddress}`\n'
                            'Checked: Incorrect length')
            return
        ## Check payment ID
        if(len(paymentid)==64):
            if not re.match(r'[a-zA-Z0-9]{64,}', paymentid.strip()):
                await bot.add_reaction(context.message, EMOJI_ERROR)
                await bot.reply(f'✋ PaymentID: `{paymentid}`\n'
                                'Checked: Invalid. Should be in 64 correct format.')
                return
            else:
                pass
        else:
            await bot.add_reaction(context.message, EMOJI_ERROR)
            await bot.reply(f'✋ PaymentID: `{paymentid}`\n'
                            'Checked: Incorrect length')
            return
        ## Make integrated address:
        integrated_address=addressvalidation.make_integrated(CoinAddress, paymentid)
        if ('integrated_address' in integrated_address):
            iCoinAddress=integrated_address['integrated_address']
            await bot.add_reaction(context.message, EMOJI_OK)
            await bot.reply(f'\nNew integrated address: `{iCoinAddress}`\n\n'
                            f'Main address: `{CoinAddress}`\n'
                            f'Payment ID: `{paymentid}`\n')
            return
        else:
            await bot.add_reaction(context.message, EMOJI_ERROR)
            await bot.reply(f'✋ ERROR Can not make integrated address.\n')
            return
    else:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.say('**[ ADDRESS CHECKING EXAMPLES ]**\n\n'
                        '`.address WrkzRNDQDwFCBynKPc459v3LDa1gEGzG3j962tMUBko1fw9xgdaS9mNiGMgA9s1q7hS1Z8SGRVWzcGc8Sh8xsvfZ6u2wJEtoZB`\n'
                        'That will check if the address is valid. Integrated address is also supported. '
                        'If integrated address is input, bot will tell you the result of :address + paymentid\n\n'
                        '`.address <coin_address> <paymentid>`\n'
                        'This will generate an integrate address.\n\n')
        return

@bot.command(pass_context=True, name='optimize', aliases=['opt'], help=bot_help_optimize)
async def optimize(context: commands.Context, member: discord.Member = None):
    if (member is None):
        pass
    else:
        ## check permission to optimize
        if (int(context.message.author.id) in MAINTENANCE_OWNER):
            user_from = store.sql_get_userwallet(member.mention)
            #let's optimize and set status
            CountOpt=store.sql_optimize_do(member.id)
            if(CountOpt>0):
                await bot.add_reaction(context.message, EMOJI_OK)
                await bot.send_message(context.message.author, f'***Optimize*** is being processed for {member.name} wallet. {CountOpt} fusion tx(s).')
                return
            else:
                await bot.add_reaction(context.message, EMOJI_OK)
                await bot.send_message(context.message.author, '✋ No `optimize` is needed.')
                return
        else:
            await bot.add_reaction(context.message, EMOJI_WARNING)
            await bot.reply('✋ You only need to optimize your own tip jar.')
            return
    ## Get wallet status
    walletStatus = daemonrpc_client.getWalletStatus()
    if (walletStatus is None):
        await bot.reply('✋ Wallet service hasn\'t started.')
        return
    else:
        print(walletStatus)
        localDaemonBlockCount = int(walletStatus['blockCount'])
        networkBlockCount = int(walletStatus['knownBlockCount'])
        if ((networkBlockCount-localDaemonBlockCount)>=20):
            ## if height is different by 50
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount/networkBlockCount*100,2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            await bot.add_reaction(context.message, EMOJI_WARNING)
            await bot.send_message(context.message.author,
                                    '✋ Wallet service hasn\'t sync fully with network or being re-sync. More info:\n```'
                                    f'networkBlockCount:     {t_networkBlockCount}\n'
                                    f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                                    f'Progress %:            {t_percent}\n```'
                                    )
            return
        else:
            pass
    ## End of wallet status

    ## Check if maintenance
    if (IS_MAINTENANCE==1):
        if (int(context.message.author.id) in MAINTENANCE_OWNER):
            pass
        else:
            await bot.add_reaction(context.message, EMOJI_WARNING)
            await bot.send_message(context.message.author, f'✋ {config.maintenance_msg}')
            return
    else:
        pass
    ## End Check if maintenance

    ## Check if user has a proper wallet with balance bigger than 100,000,000 real balance
    user_from = store.sql_get_userwallet(context.message.author.id)
    if ('lastOptimize' in user_from):
        if (int(time.time())-int(user_from['lastOptimize'])<int(config.coin.IntervalOptimize)):
            await bot.add_reaction(context.message, EMOJI_ERROR)
            await bot.reply('✋ Please wait. You just did `.optimize` within last 30mn.')
            return
        pass
    if(int(user_from['actual_balance'])/COIN_DIGITS < int(config.coin.MinToOptimize)):
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.reply('✋ Your balance may not need to optimize yet. We set that value higher.')
        return
    else:
        ## check if optimize has done for last 30mn
        ## and if last 30mn more than 5 has been done in total
        countOptimize=store.sql_optimize_check()
        if(countOptimize>=5):
            await bot.add_reaction(context.message, EMOJI_ERROR)
            await bot.reply('✋ Please wait. There are a few `.optimize` within last 30mn from other people.')
            return
        else:
            #let's optimize and set status
            CountOpt=store.sql_optimize_do(context.message.author.id)
            if(CountOpt>0):
                await bot.add_reaction(context.message, EMOJI_OK)
                await bot.send_message(context.message.author, f'***Optimize*** is being processed for your wallet. {CountOpt} fusion tx(s).')
                return
            else:
                await bot.add_reaction(context.message, EMOJI_OK)
                await bot.send_message(context.message.author, '✋ No `optimize` is needed.')
                return

@bot.command(pass_context=True, name='paymentid', aliases=['payid'], help=bot_help_paymentid)
async def paymentid(context: commands.Context):
    paymentid=addressvalidation.paymentid()
    await bot.add_reaction(context.message, EMOJI_OK)
    await bot.reply('**[ RANDOM PAYMENT ID ]**\n'
                    f'`{paymentid}`\n')
    return

@bot.command(pass_context=True, name='addressqr', aliases=['qr', 'showqr'], help=bot_help_address_qr)
async def addressqr(context: commands.Context, *args):
    ## Check if address is valid first
    if(len(args)==0):
        await bot.say('**[ QR ADDRESS EXAMPLES ]**\n\n'
                        '```.qr WrkzRNDQDwFCBynKPc459v3LDa1gEGzG3j962tMUBko1fw9xgdaS9mNiGMgA9s1q7hS1Z8SGRVWzcGc8Sh8xsvfZ6u2wJEtoZB\n'
                        'This will generate a QR address.'
                        '```\n\n')
        return

    if(len(args)==1):
        CoinAddress=args[0]
        if(len(CoinAddress)==int(config.coin.AddrLen)):
            if not re.match(r'Wrkz[a-zA-Z0-9]{94,}', CoinAddress.strip()):
                await bot.add_reaction(context.message, EMOJI_ERROR)
                await bot.reply(f'✋ Address: `{CoinAddress}`\n'
                                'Invalid address. It should start with Wrkz.')
                return
            else:
                valid_address=addressvalidation.validate_address(CoinAddress)
                if (valid_address is None) :
                    await bot.add_reaction(context.message, EMOJI_ERROR)
                    await bot.reply(f'✋ Address: `{CoinAddress}`\n'
                                    'Invalid address.')
                    return
                else:
                    pass
            pass
        elif(len(CoinAddress)==int(config.coin.IntAddrLen)):
            ## Integrated address
            if not re.match(r'Wrkz[a-zA-Z0-9]{182,}', CoinAddress.strip()):
                await bot.add_reaction(context.message, EMOJI_ERROR)
                await bot.reply(f'✋ Integrated Address: `{CoinAddress}`\n'
                                'Invalid address. It should start with Wrkz.')
                return
            else:
                valid_address=addressvalidation.validate_integrated(CoinAddress)
                if (valid_address=='invalid'):
                    await bot.add_reaction(context.message, EMOJI_ERROR)
                    await bot.reply(f'✋ Integrated Address: `{CoinAddress}`\n'
                                    'Invalid integrated address.')
                    return
                if(len(valid_address)==2):
                    pass
                pass
        else:
            ## incorrect length
            await bot.add_reaction(context.message, EMOJI_ERROR)
            await bot.reply(f'✋ Address: `{CoinAddress}`\n'
                            'Incorrect address length')
            return
    ## let's send
    print('QR: '+ args[0])
    await bot.add_reaction(context.message, EMOJI_OK)
    if (os.path.exists("/path/to/data/qrcodes/"+str(args[0])+".png")):
        if (str(context.message.channel.type).lower() == "private"):
            await bot.send_file(context.message.author, "/path/to/data/qrcodes/"+str(args[0])+".png", 
                                    content="QR Code of address: ```"+args[0]+"```")
        else:
            await bot.send_file(context.message.channel, "/path/to/data/qrcodes/"+str(args[0])+".png", 
                                    content="QR Code of address: ```"+args[0]+"```")		
        return
    else:
        ## do some QR code
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
        img.save("/path/to/data/qrcodes/"+str(args[0])+".png")
        if (str(context.message.channel.type).lower() == "private"):
            await bot.send_file(context.message.author, "/path/to/data/qrcodes/"+str(args[0])+".png", 
                                    content="QR Code of address: ```"+args[0]+"```")
        else:
            await bot.send_file(context.message.channel, "/path/to/data/qrcodes/"+str(args[0])+".png", 
                                    content="QR Code of address: ```"+args[0]+"```")
        return

@bot.command(pass_context=True, name='makeqr', aliases=['make-qr', 'paymentqr', 'payqr'], help=bot_help_payment_qr)
async def makeqr(context: commands.Context, *args):
    ## Check if address is valid first
    qrstring = 'wrkzcoin://'
    msgQR = (' '.join(args))
    try:
        msgRemark=msgQR[msgQR.index('-m') + len('-m'):].strip()[:64]
        print('msgRemark: '+msgRemark)
    except:
        pass
    if(len(args)<2):
        await bot.say('**[ MAKE QR EXAMPLES ]**\n'
                        '```'
                        '.makeqr WrkzAddress Amount\n'
                        '.makeqr WrkzAddress Amount -m AddressName\n'
                        '.makeqr WrkzAddress paymentid Amount\n'
                        '.makeqr WrkzAddress paymentid Amount -m AddressName\n'
                        'This will generate a QR code from address, paymentid, amount. Optionally with AdddressName'
                        '```\n\n')
        return

    if(len(args)==2 or len(args)==4):
        CoinAddress=args[0]
        ## Check amount
        try:
            amount = float(args[1])
        except ValueError:
            await bot.add_reaction(context.message, EMOJI_ERROR)
            await bot.reply(context.message.author,
                        '✋ Invalid amount.')
            return
        real_amount = int(amount * COIN_DIGITS)
        if(len(CoinAddress)==int(config.coin.AddrLen)):
            if not re.match(r'Wrkz[a-zA-Z0-9]{94,}', CoinAddress.strip()):
                await bot.add_reaction(context.message, EMOJI_ERROR)
                await bot.reply(f'✋ Address: `{CoinAddress}`\n'
                                'Invalid address. It should start with Wrkz.')
                return
            else:
                valid_address=addressvalidation.validate_address(CoinAddress)
                if (valid_address is None) :
                    await bot.add_reaction(context.message, EMOJI_ERROR)
                    await bot.reply(f'✋ Address: `{CoinAddress}`\n'
                                    'Invalid address.')
                    return
                else:
                    pass
            pass
        elif(len(CoinAddress)==int(config.coin.IntAddrLen)):
            ## Integrated address
            if not re.match(r'Wrkz[a-zA-Z0-9]{182,}', CoinAddress.strip()):
                await bot.add_reaction(context.message, EMOJI_ERROR)
                await bot.reply(f'✋ Integrated Address: `{CoinAddress}`\n'
                                'Invalid address. It should start with Wrkz.')
                return
            else:
                valid_address=addressvalidation.validate_integrated(CoinAddress)
                if (valid_address=='invalid'):
                    await bot.add_reaction(context.message, EMOJI_ERROR)
                    await bot.reply(f'✋ Integrated Address: `{CoinAddress}`\n'
                                    'Invalid integrated address.')
                    return
                if(len(valid_address)==2):
                    pass
                pass
        else:
            ## incorrect length
            await bot.add_reaction(context.message, EMOJI_ERROR)
            await bot.reply(f'✋ Address: `{CoinAddress}`\n'
                            'Incorrect address length')
            return
        qrstring += CoinAddress + '?amount='+str(real_amount)
        if(msgRemark is not None):
            qrstring = qrstring + '&name='+msgRemark
        print(qrstring)
        pass
    elif(len(args)==3 or len(args)==5):
        CoinAddress=args[0]
        ## Check amount
        try:
            amount = float(args[2])
        except ValueError:
            await bot.add_reaction(context.message, EMOJI_ERROR)
            await bot.reply(context.message.author,
                        '✋ Invalid amount.')
            return
        real_amount = int(amount * COIN_DIGITS)
        ## Check payment ID
        paymentid = args[1]
        if(len(paymentid)==64):
            if not re.match(r'[a-zA-Z0-9]{64,}', paymentid.strip()):
                await bot.add_reaction(context.message, EMOJI_ERROR)
                await bot.reply(f'✋ PaymentID: `{paymentid}`\n'
                                'Should be in 64 correct format.')
                return
            else:
                pass
        else:
            await bot.add_reaction(context.message, EMOJI_ERROR)
            await bot.reply(f'✋ PaymentID: `{paymentid}`\n'
                            'Incorrect length.')
            return

        if(len(CoinAddress)==int(config.coin.AddrLen)):
            if not re.match(r'Wrkz[a-zA-Z0-9]{94,}', CoinAddress.strip()):
                await bot.add_reaction(context.message, EMOJI_ERROR)
                await bot.reply(f'✋ Address: `{CoinAddress}`\n'
                                'Invalid address. It should start with Wrkz.')
                return
            else:
                valid_address=addressvalidation.validate_address(CoinAddress)
                if (valid_address is None) :
                    await bot.add_reaction(context.message, EMOJI_ERROR)
                    await bot.reply(f'✋ Address: `{CoinAddress}`\n'
                                    'Invalid address.')
                    return
                else:
                    pass
            pass
        elif(len(CoinAddress)==int(config.coin.IntAddrLen)):
            ## Integrated address
            if not re.match(r'Wrkz[a-zA-Z0-9]{182,}', CoinAddress.strip()):
                await bot.add_reaction(context.message, EMOJI_ERROR)
                await bot.reply(f'✋ Integrated Address: `{CoinAddress}`\n'
                                'Invalid address. It should start with Wrkz.')
                return
            else:
                valid_address=addressvalidation.validate_integrated(CoinAddress)
                if (valid_address=='invalid'):
                    await bot.add_reaction(context.message, EMOJI_ERROR)
                    await bot.reply(f'✋ Integrated Address: `{CoinAddress}`\n'
                                    'Invalid integrated address.')
                    return
                if(len(valid_address)==2):
                    await bot.add_reaction(context.message, EMOJI_ERROR)
                    await bot.reply('✋ You cannot use integrated address and paymentid at the same time.')
                    return
                return
        else:
            ## incorrect length
            await bot.add_reaction(context.message, EMOJI_ERROR)
            await bot.reply(f'✋ Address: `{CoinAddress}`\n'
                            'Incorrect address length')
            return
        qrstring += CoinAddress + '?amount='+str(real_amount)+'&paymentid='+paymentid
        if(msgRemark is not None):
            qrstring = qrstring + '&name='+msgRemark
        print(qrstring)
        pass
    ## let's send
    print('QR: '+ qrstring)
    await bot.add_reaction(context.message, EMOJI_OK)
    unique_filename = str(uuid.uuid4())
    ## do some QR code
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
    img.save("/path/to/data/qrcodes/"+unique_filename+".png")
    if (str(context.message.channel.type).lower() == "private"):
        await bot.send_file(context.message.author, "/path/to/data/qrcodes/"+unique_filename+".png", 
                                content=f"QR Custom Payment:\n```{qrstring}```")
        os.remove("/path/to/data/qrcodes/"+unique_filename+".png")
    else:
        await bot.send_file(context.message.channel, "/path/to/data/qrcodes/"+unique_filename+".png", 
                                content=f"QR Custom Payment:\n```{qrstring}```")
        os.remove("/path/to/data/qrcodes/"+unique_filename+".png")
    return

@bot.command(pass_context=True, help=bot_help_block)
async def block(context: commands.Context, blockHash: str):
    try:
        hashID = int(blockHash)
        hashRes = daemonrpc_client.getblock(blockHash)
        if (hashID==0):
            blockfound = datetime.utcfromtimestamp(int(1545275570)).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        if (len(blockHash) != 64) :
            await bot.say(f'✋ Invalid block hash: '
                        f'`{blockHash}`')
            return
        if not re.match(r'[a-zA-Z0-9]{64,}', blockHash.strip()):
            await bot.say(f'✋ Invalid block hash: '
                        f'`{blockHash}`')
            return
        hashRes = daemonrpc_client.getblockbyHash(blockHash)
    if (hashRes is None):
        await bot.say(f'✋ Block not found: '
                        f'`{blockHash}`')
    else:
        blockfound = datetime.utcfromtimestamp(int(hashRes['block_header']['timestamp'])).strftime("%Y-%m-%d %H:%M:%S")
        if(int(hashRes['block_header']['height'])==0):
            blockfound = datetime.utcfromtimestamp(int(1545275570)).strftime("%Y-%m-%d %H:%M:%S")
        ago = str(timeago.format(blockfound, datetime.utcnow()))
        difficulty = "{:,}".format(hashRes['block_header']['difficulty'])
        height = "{:,}".format(hashRes['block_header']['height'])
        hash = hashRes['block_header']['hash']
        await bot.say('**[ WRKZCOIN ]**\n```'
                        f'BLOCK HEIGHT {height}\n'
                        f'BLOCK HASH   {hash}\n'
                        f'FOUND        {ago}\n'
                        f'DIFFICULTY   {difficulty}```\n')

@bot.command(pass_context=True, help=bot_help_tag)
async def tag(context: commands.Context, *args):
    if (str(context.message.channel.type).lower() == "private"):
        await bot.reply('✋ This command can not be in private.')
        return

    if (len(args) == 0):
        #await bot.reply('Display list of tags.')
        ListTag = store.sql_tag_by_server(str(context.message.server.id))
        #print(ListTag)
        if (len(ListTag)>0):
            tags = (', '.join([w['tag_id'] for w in ListTag])).lower()
            await bot.say(f'Available tag: `{tags}`.\nPlease use `.tag tagname` to show it in detail.'
                          'If you have permission to manage discord server.\n'
                          'Use: `.tag -add|del tagname <Tag description ... >`')
            return
        else:
            await bot.reply('There is no tag in this server. Please add.\n'
                            'If you have permission to manage discord server.\n'
                            'Use: `.tag -add|-del tagname <Tag description ... >`')
            return
    elif (len(args) == 1):
        ## if .tag test
        TagIt = store.sql_tag_by_server(str(context.message.server.id), args[0].upper())
        print(TagIt)
        if (TagIt is not None):
            tagDesc = TagIt['tag_desc']
            await bot.say(f'{tagDesc}')
            return
        else:
            await bot.reply(f'There is no tag {args[0]} in this server.\n'
                            'If you have permission to manage discord server.\n'
                            'Use: `.tag -add|-del tagname <Tag description ... >`')
            return
    if (args[0].lower() == '-add') and ((int(context.message.author.id) in MAINTENANCE_OWNER) or (context.message.author.server_permissions.manage_channels)):
        #print (context.message.content) = > .tag -add fdfs -m message here
        if (re.match('^[a-zA-Z0-9]+(-[a-zA-Z0-9]+)*$', args[1])):
            tag=args[1].upper()
            if (len(tag)>=32):
                await bot.reply(f'Tag ***{args[1]}*** is too long.')
                return
            
            tagDesc = context.message.content.strip()[(9+len(tag)+1):]
            if (len(tagDesc)<=3):
                await bot.reply(f'Tag desc for ***{args[1]}*** is too short.')
                return
            addTag = store.sql_tag_by_server_add(str(context.message.server.id), tag.strip(), tagDesc.strip(), context.message.author.name, str(context.message.author.id))
            if (addTag is None):
                await bot.reply(f'Failed to add tag ***{args[1]}***')
                return
            if (addTag.upper()==tag.upper()):
                await bot.reply(f'Successfully added tag ***{args[1]}***')
                return
            else:
                await bot.reply(f'Failed to add tag ***{args[1]}***')
                return
        else:
            await bot.reply(f'Tag {args[1]} is not valid.')
            return
        return
    elif (args[0].lower() == '-del') and ((int(context.message.author.id) in MAINTENANCE_OWNER) or (context.message.author.server_permissions.manage_channels)):
        if (re.match('^[a-zA-Z0-9]+(-[a-zA-Z0-9]+)*$', args[1])):
            tag=args[1].upper()
            delTag = store.sql_tag_by_server_del(str(context.message.server.id), tag.strip())
            if (delTag is None):
                await bot.reply(f'Failed to delete tag ***{args[1]}***')
                return
            if (delTag.upper()==tag.upper()):
                await bot.reply(f'Successfully deleted tag ***{args[1]}***')
                return
            else:
                await bot.reply(f'Failed to delete tag ***{args[1]}***')
                return
        else:
            await bot.reply(f'Tag {args[1]} is not valid.')
            return
        return

@register.error
async def register_error(error, _: commands.Context):
    pass

@info.error
async def info_error(error, _: commands.Context):
    pass


@balance.error
async def balance_error(error, _: commands.Context):
    pass

@botbalance.error
async def botbalance_error(error, _: commands.Context):
    pass

@withdraw.error
async def withdraw_error(error, _: commands.Context):
    pass

@tip.error
async def tip_error(error, _: commands.Context):
    pass

@tipall.error
async def tipall_error(error, _: commands.Context):
    pass

@send.error
async def send_error(error, _: commands.Context):
    pass

@optimize.error
async def optimize_error(error, _: commands.Context):
    pass

@address.error
async def address_error(error, _: commands.Context):
    pass

@paymentid.error
async def payment_error(error, _: commands.Context):
    pass

@makeqr.error
async def makeqr_error(error, _: commands.Context):
    pass

@tag.error
async def tag_error(error, _: commands.Context):
    pass

@bot.event
async def on_command_error(error, _: commands.Context):
    if isinstance(error, commands.NoPrivateMessage):
        await bot.send_message(_.message.author, 'This command cannot be used in private messages.')
    elif isinstance(error, commands.DisabledCommand):
        await bot.send_message(_.message.author, 'Sorry. This command is disabled and cannot be used.')
    elif isinstance(error, commands.MissingRequiredArgument):
        command = _.message.content.split()[0].strip('.')
        await bot.send_message(_.message.author, 'Missing an argument: try `.help` or `.help ' + command + '`')
    elif isinstance(error, commands.CommandNotFound):
        pass
        #await bot.send_message(_.message.author, 'I don\'t know that command: try `.help`')

async def update_balance_wallets():
    ## open & get status
    walletStatus = daemonrpc_client.getWalletStatus()
    while not bot.is_closed:
        ## do not update yet
        await asyncio.sleep(5)
        store.sql_update_balances()
        await asyncio.sleep(config.wallet_balance_update_interval)

## Multiple tip
async def _tip(context: commands.Context, amount):
    user_from = store.sql_get_userwallet(context.message.author.id)
    try:
        amount = float(amount)
    except ValueError:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        '✋ Invalid amount.')
        return

    try:
        real_amount = int(round(float(amount) * COIN_DIGITS))
    except:
        await bot.send_message(context.message.author,
                                "Amount must be a number.")
        return

    if real_amount > config.max_tx_amount:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Transactions cannot be bigger than '
                        f'{config.max_tx_amount / COIN_DIGITS:.2f} '
                        f'{COIN_REPR}.')
        return
    elif real_amount < config.min_tx_amount:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Transactions cannot be smaller than '
                        f'{config.min_tx_amount / COIN_DIGITS:.2f} '
                        f'{COIN_REPR}.')
        return

    destinations = []
    listMembers = context.message.mentions

    memids = [] ## list of member ID
    for member in listMembers:
        #print(member.name) # you'll just print out Member objects your way.
        if (context.message.author.id != member.id) :
            user_to = store.sql_register_user(member.id)
            memids.append(user_to['balance_wallet_address'])

    addresses = []
    for desti in memids:
        destinations.append({"address":desti,"amount":real_amount})
        addresses.append(desti)

    ActualSpend = real_amount * len(memids) + config.tx_fee

    #print(str(amount)) #10.0
    #print(str(real_amount)) #1000
    if ActualSpend + config.tx_fee >= user_from['actual_balance']:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Insufficient balance to send total tip of '
                        f'{ActualSpend / COIN_DIGITS:.2f} '
                        f'{COIN_REPR}.')
        return

    if ActualSpend > config.max_tx_amount:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Total transactions cannot be bigger than '
                        f'{config.max_tx_amount / COIN_DIGITS:.2f} '
                        f'{COIN_REPR}.')
        return
    elif real_amount < config.min_tx_amount:
        print('ActualSpend: '+str(ActualSpend))
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        f'✋ Total transactions cannot be smaller than '
                        f'{config.min_tx_amount / COIN_DIGITS:.2f} '
                        f'{COIN_REPR}.')
        return

    ## Get wallet status
    walletStatus = daemonrpc_client.getWalletStatus()
    if (walletStatus is None):
        await bot.reply('✋ Wallet service hasn\'t started.')
        return
    else:
        print(walletStatus)
        localDaemonBlockCount = int(walletStatus['blockCount'])
        networkBlockCount = int(walletStatus['knownBlockCount'])
        if ((networkBlockCount-localDaemonBlockCount)>=20):
            ## if height is different by 50
            t_percent = '{:,.2f}'.format(truncate(localDaemonBlockCount/networkBlockCount*100,2))
            t_localDaemonBlockCount = '{:,}'.format(localDaemonBlockCount)
            t_networkBlockCount = '{:,}'.format(networkBlockCount)
            await bot.add_reaction(context.message, EMOJI_WARNING)
            await bot.send_message(context.message.author,
                                    '✋ Wallet service hasn\'t sync fully with network or being re-sync. More info:\n```'
                                    f'networkBlockCount:     {t_networkBlockCount}\n'
                                    f'localDaemonBlockCount: {t_localDaemonBlockCount}\n'
                                    f'Progress %:            {t_percent}\n```'
                                    )
            return
        else:
            pass
    ## End of wallet status

    #print(destinations)
    tip = store.sql_send_tipall(context.message.author.id, destinations, real_amount)
    if (tip is not None):
        store.sql_update_some_balances(addresses)
        await bot.add_reaction(context.message, EMOJI_MONEYFACE)
        await bot.send_message(
            context.message.author,
                        f'💰 Total tip of {ActualSpend / COIN_DIGITS:.2f} '
                        f'{COIN_REPR} '
                        f'was sent to ({len(destinations)}) members.\n'
                        f'Transaction hash: `{tip}`\n'
                        f'Each: `{real_amount / COIN_DIGITS:.2f}{COIN_REPR}`'
                        f'Total spending: `{ActualSpend / COIN_DIGITS:.2f}{COIN_REPR}`')
        for member in context.message.mentions:
            #print(member.name) # you'll just print out Member objects your way.
            if (context.message.author.id != member.id) :
                if (member.bot == False):
                    await bot.send_message(
                        member,
                            f'💰 You got a tip of {real_amount / COIN_DIGITS:.2f} '
                            f'{COIN_REPR} from `{context.message.author.name}`\n'
                            f'Transaction hash: `{tip}`')
                    pass
        return
    else:
        await bot.add_reaction(context.message, EMOJI_ERROR)
        await bot.send_message(context.message.author,
                        'You may need to `.optimize`')
        return

def truncate(number, digits) -> float:
    stepper = pow(10.0, digits)
    return math.trunc(stepper * number) / stepper

@click.command()
def main():
    bot.loop.create_task(update_balance_wallets())
    bot.run(config.discord.token)

if __name__ == '__main__':
    main()



