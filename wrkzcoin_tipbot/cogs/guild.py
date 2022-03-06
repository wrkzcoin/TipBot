import asyncio
import re
import sys
import time
import traceback
from datetime import datetime
import random
import qrcode
import uuid

import disnake
from disnake.ext import tasks, commands

from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

import store
from Bot import get_token_list, num_format_coin, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_ARROW_RIGHTHOOK, SERVER_BOT, RowButton_close_message, RowButton_row_close_any_message, human_format, text_to_num, truncate, NOTIFICATION_OFF_CMD

from config import config
from cogs.wallet import Wallet
import redis_utils
from utils import MenuPage


class Guild(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        redis_utils.openRedis()


    async def guild_find_by_key(self, guild_id: str, secret: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT `"""+secret+"""` FROM `discord_server` WHERE `serverid`=%s """
                    await cur.execute(sql, ( guild_id ))
                    result = await cur.fetchone()
                    if result: return result[secret]
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None


    async def guild_insert_key(self, guild_id: str, key: str, secret: str, update: bool=False):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE discord_server SET `"""+secret+"""`=%s WHERE `serverid`=%s LIMIT 1 """
                    await cur.execute(sql, (key, guild_id))
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None


    @commands.guild_only()
    @commands.slash_command(description="Various guild's commands.")
    async def guild(self, ctx):
        pass


    @guild.sub_command(
        usage="guild balance", 
        description="Show guild's balance"
    )
    async def balance(
        self,
        ctx
    ):
        mytokens = await store.get_coin_settings(coin_type=None)
        if type(ctx) != disnake.ApplicationCommandInteraction:
            tmp_msg = await ctx.reply("Loading...")
        coin_balance_list = {}
        for each_token in mytokens:
            TOKEN_NAME = each_token['coin_name']
            type_coin = getattr(getattr(self.bot.coin_list, TOKEN_NAME), "type")
            net_name = getattr(getattr(self.bot.coin_list, TOKEN_NAME), "net_name")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, TOKEN_NAME), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, TOKEN_NAME), "decimal")
            token_display = getattr(getattr(self.bot.coin_list, TOKEN_NAME), "display_name")

            WalletAPI = Wallet(self.bot)
            get_deposit = await WalletAPI.sql_get_userwallet(str(ctx.guild.id), TOKEN_NAME, net_name, type_coin, SERVER_BOT, 0)
            if get_deposit is None:
                get_deposit = await WalletAPI.sql_register_user(str(ctx.guild.id), TOKEN_NAME, net_name, type_coin, SERVER_BOT, 0, 1)
            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']

            height = None
            try:
                if type_coin in ["ERC-20", "TRC-20"]:
                    height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
                else:
                    height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{TOKEN_NAME}').decode())
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

            # height can be None
            userdata_balance = await store.sql_user_balance_single(str(ctx.guild.id), TOKEN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
            total_balance = userdata_balance['adjust']
            if total_balance > 0:
                coin_balance_list[TOKEN_NAME] = "{} {}".format(num_format_coin(total_balance, TOKEN_NAME, coin_decimal, False), token_display)

        ## add page
        all_pages = []
        num_coins = 0
        per_page = 8
        for k, v in coin_balance_list.items():
            if num_coins == 0 or num_coins % per_page == 0:
                page = disnake.Embed(title=f'[ GUILD **{ctx.guild.name.upper()}** BALANCE LIST ]',
                                     description="Thank you for using TipBot!",
                                     color=disnake.Color.red(),
                                     timestamp=datetime.utcnow(), )
                page.set_thumbnail(url=ctx.author.display_avatar)
                page.set_footer(text="Use the reactions to flip pages.")
            ##
            page.add_field(name=k, value="```{}```".format(v), inline=True)
            num_coins += 1
            if num_coins > 0 and num_coins % per_page == 0:
                all_pages.append(page)
                if num_coins < len(coin_balance_list):
                    page = disnake.Embed(title=f'[ GUILD **{ctx.guild.name.upper()}** BALANCE LIST ]',
                                         description="Thank you for using TipBot!",
                                         color=disnake.Color.red(),
                                         timestamp=datetime.utcnow(), )
                    page.set_thumbnail(url=ctx.author.display_avatar)
                    page.set_footer(text="Use the reactions to flip pages.")
                else:
                    all_pages.append(page)
                    break
            elif num_coins == len(coin_balance_list):
                all_pages.append(page)
                break

        if len(all_pages) == 1:
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(embed=all_pages[0], view=RowButton_close_message())
            else:
                await tmp_msg.delete()
                await ctx.reply(content=None, embed=all_pages[0], view=RowButton_close_message())
        else:
            view = MenuPage(ctx, all_pages, timeout=30)
            if type(ctx) == disnake.ApplicationCommandInteraction:
                view.message = await ctx.response.send_message(embed=all_pages[0], view=view)
            else:
                await tmp_msg.delete()
                view.message = await ctx.reply(content=None, embed=all_pages[0], view=view)


    @guild.sub_command(
        usage="guild deposit <amount> <coin/token>", 
        options=[
            Option('amount', 'amount', OptionType.string, required=True), 
            Option('coin', 'coin', OptionType.string, required=True) 
        ],
        description="Deposit from your balance to the said guild"
    )
    async def deposit(
        self,
        ctx,
        amount: str, 
        coin: str
    ):
        COIN_NAME = coin.upper()
        if not hasattr(self.bot.coin_list, COIN_NAME):
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
            else:
                await ctx.reply(f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.')
            return
        # Do the job
        try:
            net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
            token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
            MinTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_tip")
            MaxTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_max_tip")
            WalletAPI = Wallet(self.bot)
            
            get_deposit = await WalletAPI.sql_get_userwallet(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
            if get_deposit is None:
                get_deposit = await WalletAPI.sql_register_user(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)

            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']

            height = None
            try:
                if type_coin in ["ERC-20", "TRC-20"]:
                    height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
                else:
                    height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

            # check if amount is all
            all_amount = False
            if not amount.isdigit() and amount.upper() == "ALL":
                all_amount = True
                userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                amount = float(userdata_balance['adjust'])
            else:
                amount = amount.replace(",", "")
                amount = text_to_num(amount)
                if amount is None:
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount.')
                    else:
                        await ctx.reply(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount.')
                    return
            # end of check if amount is all
            userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
            actual_balance = float(userdata_balance['adjust'])
            amount = float(amount)
            if amount <= 0:
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(f'{EMOJI_RED_NO} {ctx.author.mention}, please topup more {COIN_NAME}')
                else:
                    await ctx.reply(f'{EMOJI_RED_NO} {ctx.author.mention}, please topup more {COIN_NAME}')
                return
                
            if amount > actual_balance:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to deposit {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg, ephemeral=True)
                else:
                    await ctx.reply(msg)
                return

            elif amount < MinTip or amount > MaxTip:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention} Transaction cannot be smaller than {num_format_coin(MinTip, COIN_NAME, coin_decimal, False)} {token_display} or bigger than {num_format_coin(MaxTip, COIN_NAME, coin_decimal, False)} {token_display}.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg, ephemeral=True)
                else:
                    await ctx.reply(msg)
                return

            # OK, move fund
            if ctx.author.id in self.bot.TX_IN_PROCESS:
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
                else:
                    await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
                    msg = await ctx.reply(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
                return
            else:
                self.bot.TX_IN_PROCESS.append(ctx.author.id)
                try:
                    tip = await store.sql_user_balance_mv_single(str(ctx.author.id), str(ctx.guild.id), str(ctx.guild.id), str(ctx.channel.id), amount, COIN_NAME, 'GUILDDEPOSIT', coin_decimal, contract)
                    if tip:
                        try:
                            msg = f'{EMOJI_ARROW_RIGHTHOOK} {ctx.author.mention} **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {COIN_NAME}** was transferred to {ctx.guild.name}.'
                            if type(ctx) == disnake.ApplicationCommandInteraction:
                                await ctx.response.send_message(msg)
                            else:
                                await ctx.reply(msg)
                        except (disnake.Forbidden, disnake.errors.Forbidden, disnake.errors.HTTPException) as e:
                            pass
                        guild_found = self.bot.get_guild(ctx.guild.id)
                        if guild_found: user_found = self.bot.get_user(guild_found.owner.id)
                        if user_found:
                            notifyList = await store.sql_get_tipnotify()
                            if str(guild_found.owner.id) not in notifyList:
                                try:
                                    await user_found.send(f'Your guild **{ctx.guild.name}** got a deposit of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} '
                                                          f'{COIN_NAME}** from {ctx.author.name}#{ctx.author.discriminator} in `#{ctx.channel.name}`\n'
                                                          f'{NOTIFICATION_OFF_CMD}\n')
                                except (disnake.Forbidden, disnake.errors.Forbidden, disnake.errors.HTTPException) as e:
                                    pass
                        return
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                if ctx.author.id in self.bot.TX_IN_PROCESS:
                    self.bot.TX_IN_PROCESS.remove(ctx.author.id)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @guild.sub_command(
        usage="guild topgg [resetkey]", 
        options=[
            Option('resetkey', 'resetkey', OptionType.string, required=False, choices=[
                OptionChoice("YES", "YES"),
                OptionChoice("NO", "NO")
            ])
        ],
        description="Get token key to set for topgg vote in bot channel."
    )
    async def topgg(
        self,
        ctx,
        resetkey: str=None
    ):
        secret = "topgg_vote_secret"
        if resetkey is None: resetkey = "NO"
        get_guild_by_key = await self.guild_find_by_key(str(ctx.guild.id), secret)
        if get_guild_by_key is None:
            # Generate
            random_string = str(uuid.uuid4())
            insert_key = await self.guild_insert_key(str(ctx.guild.id), random_string, secret, False)
            if insert_key:
                try:
                    await ctx.response.send_message(f'Your guild {ctx.guild.name}\'s topgg key: `{random_string}`\nWebook URL: `{config.topgg.guild_vote_url}`', ephemeral=True)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            else:
                try:
                    await ctx.response.send_message(f'Internal error! Please report!', ephemeral=True)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
        elif get_guild_by_key and resetkey == "NO":
            # Just display
            try:
                await ctx.response.send_message(f'Your guild {ctx.guild.name}\'s topgg key: `{get_guild_by_key}`\nWebook URL: `{config.topgg.guild_vote_url}`', ephemeral=True)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        elif get_guild_by_key and resetkey == "YES":
            # Update a new key and say to it. Do not forget to update
            random_string = str(uuid.uuid4())
            insert_key = await self.guild_insert_key(str(ctx.guild.id), random_string, secret, True)
            if insert_key:
                try:
                    await ctx.response.send_message(f'Your guild {ctx.guild.name}\'s topgg updated key: `{random_string}`\nWebook URL: `{config.topgg.guild_vote_url}`', ephemeral=True)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            else:
                try:
                    await ctx.response.send_message(f'Internal error! Please report!', ephemeral=True)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)


    @guild.sub_command(
        usage="guild discordlist [resetkey]", 
        options=[
            Option('resetkey', 'resetkey', OptionType.string, required=False, choices=[
                OptionChoice("YES", "YES"),
                OptionChoice("NO", "NO")
            ])
        ],
        description="Get token key to set for discordlist vote in bot channel."
    )
    async def discordlist(
        self,
        ctx,
        resetkey: str=None
    ):
        secret = "discordlist_vote_secret"
        if resetkey is None: resetkey = "NO"
        get_guild_by_key = await self.guild_find_by_key(str(ctx.guild.id), secret)
        if get_guild_by_key is None:
            # Generate
            random_string = str(uuid.uuid4())
            insert_key = await self.guild_insert_key(str(ctx.guild.id), random_string, secret, False)
            if insert_key:
                try:
                    await ctx.response.send_message(f'Your guild {ctx.guild.name}\'s discordlist key: `{random_string}`\nWebook URL: `{config.discordlist.guild_vote_url}`', ephemeral=True)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            else:
                try:
                    await ctx.response.send_message(f'Internal error! Please report!', ephemeral=True)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
        elif get_guild_by_key and resetkey == "NO":
            # Just display
            try:
                await ctx.response.send_message(f'Your guild {ctx.guild.name}\'s discordlist key: `{get_guild_by_key}`\nWebook URL: `{config.discordlist.guild_vote_url}`', ephemeral=True)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        elif get_guild_by_key and resetkey == "YES":
            # Update a new key and say to it. Do not forget to update
            random_string = str(uuid.uuid4())
            insert_key = await self.guild_insert_key(str(ctx.guild.id), random_string, secret, True)
            if insert_key:
                try:
                    await ctx.response.send_message(f'Your guild {ctx.guild.name}\'s discordlist updated key: `{random_string}`\nWebook URL: `{config.discordlist.guild_vote_url}`', ephemeral=True)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            else:
                try:
                    await ctx.response.send_message(f'Internal error! Please report!', ephemeral=True)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)


def setup(bot):
    bot.add_cog(Guild(bot))