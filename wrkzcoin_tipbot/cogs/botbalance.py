import sys
import traceback
from datetime import datetime
from decimal import Decimal

import disnake
import store
from Bot import EMOJI_RED_NO, num_format_coin, SERVER_BOT
from cogs.wallet import WalletAPI
from disnake.app_commands import Option
from disnake.enums import OptionType
from disnake.ext import commands
from cogs.utils import Utils


class BotBalance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.botLogChan = None
        self.enable_logchan = True

    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)

    async def bot_bal(self, ctx, member, token: str):
        if member.bot is False:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention} Only for bot!!"
            await ctx.response.send_message(msg)
            return

        coin_name = token.upper()
        # Token name check
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
            await ctx.response.send_message(msg)
            return
        # End token name check

        msg = f'{ctx.author.mention}, checking {member.mention}\'s balance.'
        await ctx.response.send_message(msg)
        # Do the job
        try:
            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name), "usd_equivalent_enable")
            get_deposit = await self.wallet_api.sql_get_userwallet(str(member.id), coin_name, net_name, type_coin,
                                                                   SERVER_BOT, 0)
            if get_deposit is None:
                get_deposit = await self.wallet_api.sql_register_user(str(member.id), coin_name, net_name, type_coin,
                                                                      SERVER_BOT, 0, 0)

            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']

            height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
            description = ""
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
            embed = disnake.Embed(title=f'Balance for Bot {member.name}#{member.discriminator}',
                                  description="This is for Bot's! Not yours!", timestamp=datetime.now())
            embed.set_author(name=member.name, icon_url=member.display_avatar)
            try:
                # height can be None
                userdata_balance = await store.sql_user_balance_single(str(member.id), coin_name, wallet_address,
                                                                       type_coin, height, deposit_confirm_depth,
                                                                       SERVER_BOT)
                total_balance = userdata_balance['adjust']
                equivalent_usd = ""
                if usd_equivalent_enable == 1:
                    native_token_name = getattr(getattr(self.bot.coin_list, coin_name), "native_token_name")
                    coin_name_for_price = coin_name
                    if native_token_name:
                        coin_name_for_price = native_token_name
                    per_unit = None
                    if coin_name_for_price in self.bot.token_hints:
                        id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                        per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                    else:
                        per_unit = self.bot.coin_paprika_symbol_list[coin_name_for_price]['price_usd']
                    if per_unit and per_unit > 0:
                        total_in_usd = float(Decimal(total_balance) * Decimal(per_unit))
                        if total_in_usd >= 0.01:
                            equivalent_usd = " ~ {:,.2f}$".format(total_in_usd)
                        elif total_in_usd >= 0.0001:
                            equivalent_usd = " ~ {:,.4f}$".format(total_in_usd)
                embed.add_field(name="Token/Coin {}{}".format(token_display, equivalent_usd),
                                value="```Available: {} {}```".format(
                                    num_format_coin(total_balance, coin_name, coin_decimal, False), token_display),
                                inline=False)
            except Exception:
                traceback.print_exc(file=sys.stdout)
            await ctx.edit_original_message(content=None, embed=embed)
            # Add update for future call
            try:
                await self.utils.update_user_balance_call(str(member.id), type_coin)
            except Exception:
                traceback.print_exc(file=sys.stdout)
        except Exception:
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
