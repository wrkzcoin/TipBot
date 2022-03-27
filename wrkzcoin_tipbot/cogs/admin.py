import sys
import traceback
from datetime import datetime

import disnake
from disnake.ext import commands
import time
from attrdict import AttrDict

# For eval
import contextlib
import io
from decimal import Decimal

from web3 import Web3
from web3.middleware import geth_poa_middleware
from ethtoken.abi import EIP20_ABI

from tronpy import AsyncTron
from tronpy.async_contract import AsyncContract, ShieldedTRC20, AsyncContractMethod
from tronpy.providers.async_http import AsyncHTTPProvider
from tronpy.exceptions import AddressNotFound
from tronpy.keys import PrivateKey

from httpx import AsyncClient, Timeout, Limits
from eth_account import Account
from pywallet import wallet as ethwallet

import functools
import store
from Bot import get_token_list, num_format_coin, EMOJI_ERROR, SERVER_BOT, logchanbot, encrypt_string, decrypt_string, RowButton_row_close_any_message
from config import config
import redis_utils
from utils import MenuPage
from cogs.wallet import WalletAPI

Account.enable_unaudited_hdwallet_features()

class Admin(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return commands.is_owner()

    async def get_coin_setting(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    coin_list = {}
                    sql = """ SELECT * FROM `coin_settings` """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each in result:
                            coin_list[each['coin_name']] = each
                        return AttrDict(coin_list)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None


    async def enable_disable_coin(self, coin: str, what: str, toggle: int):
        COIN_NAME = coin.upper()
        what = what.lower()
        if what not in ["withdraw", "deposit", "tip"]:
            return 0
        if what == "withdraw":
            what = "enable_withdraw"
        elif what == "deposit":
            what = "enable_deposit"
        elif what == "tip":
            what = "enable_tip"
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE coin_settings SET `"""+what+"""`=%s WHERE `coin_name`=%s AND `"""+what+"""`<>%s LIMIT 1 """               
                    await cur.execute(sql, ( toggle, COIN_NAME, toggle ))
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return 0


    async def create_address_eth(self):
        def create_eth_wallet():
            seed = ethwallet.generate_mnemonic()
            w = ethwallet.create_wallet(network="ETH", seed=seed, children=1)
            return w

        wallet_eth = functools.partial(create_eth_wallet)
        create_wallet = await self.bot.loop.run_in_executor(None, wallet_eth)
        return create_wallet


    async def create_address_trx(self):
        try:
            _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                       timeout=Timeout(timeout=10, connect=5, read=5))
            TronClient = AsyncTron(provider=AsyncHTTPProvider(config.Tron_Node.fullnode, client=_http_client))
            create_wallet = TronClient.generate_address()
            await TronClient.close()
            return create_wallet
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.is_owner()
    @commands.dm_only()
    @commands.group(
        usage="admin <subcommand>", 
        hidden = True, 
        description="Various admin commands."
    )
    async def admin(self, ctx):
        if ctx.invoked_subcommand is None: await ctx.reply(f'{ctx.author.mention} Invalid admin command')
        return

    @commands.is_owner()
    @admin.command(hidden=True, usage='baluser', description='Check user balances')
    async def baluser(self, ctx, member_id: str):
        try:
            zero_tokens = []
            has_none_balance = True
            mytokens = await store.get_coin_settings(coin_type=None)
            total_all_balance_usd = 0.0
            all_pages = []
            all_names = [each['coin_name'] for each in mytokens]
            total_coins = len(mytokens)
            page = disnake.Embed(title=f'[ BALANCE LIST {member_id} ]',
                                  color=disnake.Color.blue(),
                                  timestamp=datetime.utcnow(), )
            page.add_field(name="Coin/Tokens: [{}]".format(len(all_names)), 
                           value="```"+", ".join(all_names)+"```", inline=False)
            page.set_thumbnail(url=ctx.author.display_avatar)
            page.set_footer(text="Use the reactions to flip pages.")
            all_pages.append(page)
            num_coins = 0
            per_page = 8
            if type(ctx) != disnake.ApplicationCommandInteraction:
                tmp_msg = await ctx.reply(f"{ctx.author.mention} balance loading...")
            else:
                tmp_msg = await ctx.response.send_message(f"{ctx.author.mention} balance loading...", delete_after=60.0) # delete_after=3600.0
            for each_token in mytokens:
                COIN_NAME = each_token['coin_name']
                type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
                deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
                coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
                token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
                usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
                User_WalletAPI = WalletAPI(self.bot)
                get_deposit = await User_WalletAPI.sql_get_userwallet(member_id, COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
                if get_deposit is None:
                    get_deposit = await User_WalletAPI.sql_register_user(member_id, COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)
                wallet_address = get_deposit['balance_wallet_address']
                if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                    wallet_address = get_deposit['paymentid']

                height = None
                try:
                    if type_coin in ["ERC-20", "TRC-20"]:
                        # Add update for future call
                        try:
                            if type_coin == "ERC-20":
                                update_call = await store.sql_update_erc20_user_update_call(member_id)
                            elif type_coin == "TRC-10" or type_coin == "TRC-20":
                                update_call = await store.sql_update_trc20_user_update_call(member_id)
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
                    else:
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)

                if num_coins == 0 or num_coins % per_page == 0:
                    page = disnake.Embed(title=f'[ BALANCE LIST {member_id} ]',
                                         description="Thank you for using TipBot!",
                                         color=disnake.Color.blue(),
                                         timestamp=datetime.utcnow(), )
                    page.set_thumbnail(url=ctx.author.display_avatar)
                    page.set_footer(text="Use the reactions to flip pages.")
                # height can be None
                userdata_balance = await store.sql_user_balance_single(member_id, COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                total_balance = userdata_balance['adjust']
                if total_balance == 0:
                    zero_tokens.append(COIN_NAME)
                    continue
                elif total_balance > 0:
                    has_none_balance = False
                equivalent_usd = ""
                if usd_equivalent_enable == 1:
                    native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
                    COIN_NAME_FOR_PRICE = COIN_NAME
                    if native_token_name:
                        COIN_NAME_FOR_PRICE = native_token_name
                    per_unit = None
                    if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                        id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                        per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                    else:
                        per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
                    if per_unit and per_unit > 0:
                        total_in_usd = float(Decimal(total_balance) * Decimal(per_unit))
                        total_all_balance_usd += total_in_usd
                        if total_in_usd >= 0.01:
                            equivalent_usd = " ~ {:,.2f}$".format(total_in_usd)
                        elif total_in_usd >= 0.0001:
                            equivalent_usd = " ~ {:,.4f}$".format(total_in_usd)
                         
                page.add_field(name="{}{}".format(token_display, equivalent_usd) , value="```{}```".format(num_format_coin(total_balance, COIN_NAME, coin_decimal, False)), inline=True)
                num_coins += 1
                if num_coins > 0 and num_coins % per_page == 0:
                    all_pages.append(page)
                    if num_coins < total_coins - len(zero_tokens):
                        page = disnake.Embed(title=f'[ BALANCE LIST {member_id} ]',
                                             description="Thank you for using TipBot!",
                                             color=disnake.Color.blue(),
                                             timestamp=datetime.utcnow(), )
                        page.set_thumbnail(url=ctx.author.display_avatar)
                        page.set_footer(text="Use the reactions to flip pages.")
                    else:
                        all_pages.append(page)
                        break
                elif num_coins == total_coins:
                    all_pages.append(page)
                    break
            # remaining
            if (total_coins - len(zero_tokens)) % per_page > 0:
                all_pages.append(page)
            # Replace first page
            if total_all_balance_usd > 0.01:
                total_all_balance_usd = "Having ~ {:,.2f}$".format(total_all_balance_usd)
            elif total_all_balance_usd > 0.0001:
                total_all_balance_usd = "Having ~ {:,.4f}$".format(total_all_balance_usd)
            else:
                total_all_balance_usd = "Thank you for using TipBot!"
            page = disnake.Embed(title=f'[ BALANCE LIST {member_id} ]',
                                  description=f"`{total_all_balance_usd}`",
                                  color=disnake.Color.blue(),
                                  timestamp=datetime.utcnow(), )
            # Remove zero from all_names
            if has_none_balance == True:
                msg = f'{member_id} does not have any balance.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
            else:
                all_names = [each for each in all_names if each not in zero_tokens]
                page.add_field(name="Coin/Tokens: [{}]".format(len(all_names)), 
                               value="```"+", ".join(all_names)+"```", inline=False)
                if len(zero_tokens) > 0:
                    zero_tokens = list(set(zero_tokens))
                    page.add_field(name="Zero Balances: [{}]".format(len(zero_tokens)), 
                                   value="```"+", ".join(zero_tokens)+"```", inline=False)
                page.set_thumbnail(url=ctx.author.display_avatar)
                page.set_footer(text="Use the reactions to flip pages.")
                all_pages[0] = page

                view = MenuPage(ctx, all_pages, timeout=30)
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    view.message = await ctx.followup.send(embed=all_pages[0], view=view, ephemeral=True)
                else:
                    await tmp_msg.delete()
                    view.message = await ctx.reply(content=None, embed=all_pages[0], view=view)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.is_owner()
    @admin.command(hidden=True, usage='pending', description='Check pending things')
    async def pending(self, ctx):
        ts = datetime.utcnow()
        embed = disnake.Embed(title='Pending Actions', timestamp=ts)
        embed.add_field(name="Pending Tx", value=str(len(self.bot.TX_IN_PROCESS)), inline=True)
        if len(self.bot.TX_IN_PROCESS) > 0:
            string_ints = [str(num) for num in self.bot.TX_IN_PROCESS]
            list_pending = '{' + ', '.join(string_ints) + '}'
            embed.add_field(name="List Pending By", value=list_pending, inline=True)
        embed.set_footer(text=f"Pending requested by {ctx.author.name}#{ctx.author.discriminator}")
        try:
            await ctx.reply(embed=embed)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return


    @commands.is_owner()
    @admin.command(hidden=True, usage='withdraw', description='Enable/Disable withdraw for a coin')
    async def withdraw(self, ctx, coin: str):
        COIN_NAME = coin.upper()
        command = "withdraw"
        if not hasattr(self.bot.coin_list, COIN_NAME):
            msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        else:
            enable_withdraw = getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_withdraw")
            new_value = 1
            new_text = "enable"
            if enable_withdraw == 1:
                new_value = 0
                new_text = "disable"
            toggle = await self.enable_disable_coin(COIN_NAME, command, new_value)
            if toggle > 0:
                msg = f"{ctx.author.mention}, **{COIN_NAME}** `{command}` is `{new_text}` now."
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
            else:
                msg = f"{ctx.author.mention}, **{COIN_NAME}** `{command}` is `{new_text}` failed to update."
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
            coin_list = await self.get_coin_setting()
            if coin_list:
                self.bot.coin_list = coin_list
            coin_list_name = await self.get_coin_list_name()
            if coin_list_name:
                self.bot.coin_name_list = coin_list_name

    @commands.is_owner()
    @admin.command(hidden=True, usage='tip', description='Enable/Disable tip for a coin')
    async def tip(self, ctx, coin: str):
        COIN_NAME = coin.upper()
        command = "tip"
        if not hasattr(self.bot.coin_list, COIN_NAME):
            msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        else:
            enable_tip = getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_tip")
            new_value = 1
            new_text = "enable"
            if enable_tip == 1:
                new_value = 0
                new_text = "disable"
            toggle = await self.enable_disable_coin(COIN_NAME, command, new_value)
            if toggle > 0:
                msg = f"{ctx.author.mention}, **{COIN_NAME}** `{command}` is `{new_text}` now."
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
            else:
                msg = f"{ctx.author.mention}, **{COIN_NAME}** `{command}` is `{new_text}` failed to update."
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
            coin_list = await self.get_coin_setting()
            if coin_list:
                self.bot.coin_list = coin_list
            coin_list_name = await self.get_coin_list_name()
            if coin_list_name:
                self.bot.coin_name_list = coin_list_name

    @commands.is_owner()
    @admin.command(hidden=True, usage='deposit', description='Enable/Disable deposit for a coin')
    async def deposit(self, ctx, coin: str):
        COIN_NAME = coin.upper()
        command = "deposit"
        if not hasattr(self.bot.coin_list, COIN_NAME):
            msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        else:
            enable_deposit = getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_deposit")
            new_value = 1
            new_text = "enable"
            if enable_deposit == 1:
                new_value = 0
                new_text = "disable"
            toggle = await self.enable_disable_coin(COIN_NAME, command, new_value)
            if toggle > 0:
                msg = f"{ctx.author.mention}, **{COIN_NAME}** `{command}` is `{new_text}` now."
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
            else:
                msg = f"{ctx.author.mention}, **{COIN_NAME}** `{command}` is `{new_text}` failed to update."
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
            coin_list = await self.get_coin_setting()
            if coin_list:
                self.bot.coin_list = coin_list
            coin_list_name = await self.get_coin_list_name()
            if coin_list_name:
                self.bot.coin_name_list = coin_list_name

    @commands.is_owner()
    @commands.command(hidden=True, usage='cleartx', description='Clear TX_IN_PROCESS')
    async def cleartx(self, ctx):
        if len(self.bot.TX_IN_PROCESS) == 0:
            await ctx.reply(f'{ctx.author.mention} Nothing in tx pending to clear.')
        else:
            try:
                string_ints = [str(num) for num in self.bot.TX_IN_PROCESS]
                list_pending = '{' + ', '.join(string_ints) + '}'
                await ctx.reply(f'Clearing {str(len(self.bot.TX_IN_PROCESS))} {list_pending} in pending...')
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            self.bot.TX_IN_PROCESS = []
        return


    @commands.is_owner()
    @admin.command(
        usage="eval <expression>", 
        description="Do some eval."
    )
    async def eval(
        self, 
        ctx, 
        *, 
        code
    ):
        if config.discord.enable_eval != 1:
            return

        str_obj = io.StringIO() #Retrieves a stream of data
        try:
            with contextlib.redirect_stdout(str_obj):
                exec(code)
        except Exception as e:
            return await ctx.reply(f"```{e.__class__.__name__}: {e}```")
        await ctx.reply(f'```{str_obj.getvalue()}```')


    @commands.is_owner()
    @admin.command(hidden=True, usage='create', description='Create an address')
    async def create(self, ctx, token: str):
        if token.upper() not in ["ERC-20", "TRC-20"]:
            await ctx.reply(f'{ctx.author.mention}, only with ERC-20 and TRC-20.')
            return
        elif token.upper() == "ERC-20":
            w = await self.create_address_eth()
            await ctx.reply(f'{ctx.author.mention}, ```{str(w)}```', view=RowButton_row_close_any_message())
            return
        elif token.upper() == "TRC-20":
            w = await self.create_address_trx()
            await ctx.reply(f'{ctx.author.mention}, ```{str(w)}```', view=RowButton_row_close_any_message())
            return


    @commands.is_owner()
    @admin.command(
        usage="encrypt <expression>", 
        description="Encrypt text."
    )
    async def encrypt(
        self, 
        ctx, 
        *, 
        text
    ):
        encrypt = encrypt_string(text)
        if encrypt: return await ctx.reply(f"```{encrypt}```", view=RowButton_row_close_any_message())


    @commands.is_owner()
    @admin.command(
        usage="decrypt <expression>", 
        description="Decrypt text."
    )
    async def decrypt(
        self, 
        ctx, 
        *, 
        text
    ):
        decrypt = decrypt_string(text)
        if decrypt: return await ctx.reply(f"```{decrypt}```", view=RowButton_row_close_any_message())


def setup(bot):
    bot.add_cog(Admin(bot))
