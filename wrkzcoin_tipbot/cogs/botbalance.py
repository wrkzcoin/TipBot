import sys, traceback

import disnake
from disnake.ext import commands
from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice
from decimal import Decimal
from datetime import datetime

from config import config
from Bot import EMOJI_RED_NO, RowButton_row_close_any_message, num_format_coin, logchanbot, SERVER_BOT
from cogs.wallet import WalletAPI
import redis_utils
from utils import MenuPage
import store


class BotBalance(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)

        redis_utils.openRedis()
        self.botLogChan = None
        self.enable_logchan = True


    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)


    async def bot_bal(self, ctx, member, token: str):
        if member.bot == False:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention} Only for bot!!"
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        COIN_NAME = token.upper()
        # Token name check
        if not hasattr(self.bot.coin_list, COIN_NAME):
            msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        # End token name check

        # Do the job
        try:
            net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
            get_deposit = await self.wallet_api.sql_get_userwallet(str(member.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
            if get_deposit is None:
                get_deposit = await self.wallet_api.sql_register_user(str(member.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0, 0)

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

            description = ""
            token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
            embed = disnake.Embed(title=f'Balance for Bot {member.name}#{member.discriminator}', description="This is for Bot's! Not yours!", timestamp=datetime.now())
            embed.set_author(name=member.name, icon_url=member.display_avatar)
            try:
                # height can be None
                userdata_balance = await store.sql_user_balance_single(str(member.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
                total_balance = userdata_balance['adjust']
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
                        if total_in_usd >= 0.01:
                            equivalent_usd = " ~ {:,.2f}$".format(total_in_usd)
                        elif total_in_usd >= 0.0001:
                            equivalent_usd = " ~ {:,.4f}$".format(total_in_usd)
                embed.add_field(name="Token/Coin {}{}".format(token_display, equivalent_usd), value="```Available: {} {}```".format(num_format_coin(total_balance, COIN_NAME, coin_decimal, False), token_display), inline=False)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(embed=embed, ephemeral=False)
            else:
                await ctx.reply(embed=embed, view=RowButton_row_close_any_message())
            # Add update for future call
            try:
                if type_coin == "ERC-20":
                    update_call = await store.sql_update_erc20_user_update_call(str(member.id))
                elif type_coin == "TRC-10" or type_coin == "TRC-20":
                    update_call = await store.sql_update_trc20_user_update_call(str(member.id))
                elif type_coin == "SOL" or type_coin == "SPL":
                    update_call = await store.sql_update_sol_user_update_call(str(member.id))
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @commands.slash_command(usage="botbalance <bot> <coin>",
                            options=[
                                Option("botname", "Enter a bot", OptionType.user, required=True),
                                Option("coin", "Enter coin ticker/name", OptionType.string, required=True),
                            ],
                            description="Get Bot's balance by mention it.")
    async def botbalance(
        self, 
        ctx, 
        botname: disnake.Member, 
        coin: str
    ):
        await self.bot_bal(ctx, botname, coin)


def setup(bot):
    bot.add_cog(BotBalance(bot))
