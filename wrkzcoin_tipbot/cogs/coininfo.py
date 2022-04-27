import sys, traceback
import time, timeago
import disnake
from disnake.ext import commands
from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice
import redis_utils
from datetime import datetime

from config import config
from Bot import num_format_coin


class Coininfo(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        redis_utils.openRedis()


    async def get_coininfo(
        self,
        ctx, 
        coin: str,
    ):
        COIN_NAME = coin.upper()
        if not hasattr(self.bot.coin_list, COIN_NAME):
            msg = f'{ctx.author.mention}, **{COIN_NAME}** does not exist with us.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        confim_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")

        Min_Tip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_tip")
        Max_Tip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_max_tip")
        Min_Tx = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_tx")
        Max_Tx = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_max_tx")
        Fee_Tx = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_withdraw_fee")
        type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
        net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
        deposit_fee = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_deposit_fee")
        contract = None
        if getattr(getattr(self.bot.coin_list, COIN_NAME), "contract") and len(getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")) > 4:
            contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")
        

        response_text = "**[ COIN/TOKEN INFO {} ]**".format(COIN_NAME)
        response_text += "```"
        try:
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "is_maintenance") != 1:
                try:
                    if type_coin in ["ERC-20", "TRC-20"]:
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{net_name}').decode())
                        if height: response_text += "Height: {:,.0f}".format(height) + "\n"
                    else:
                        height = int(redis_utils.redis_conn.get(f'{config.redis.prefix+config.redis.daemon_height}{COIN_NAME}').decode())
                        if height: response_text += "Height: {:,.0f}".format(height) + "\n"
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    response_text += "Height: N/A (*)" + "\n"
            response_text += "Confirmation: {} Blocks".format(confim_depth) + "\n"
            tip_deposit_withdraw_stat = ["ON", "ON", "ON"]
            if  getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_tip") == 0:
                tip_deposit_withdraw_stat[0] = "OFF"
            if  getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_deposit") == 0:
                tip_deposit_withdraw_stat[1] = "OFF"
            if  getattr(getattr(self.bot.coin_list, COIN_NAME), "enable_withdraw") == 0:
                tip_deposit_withdraw_stat[2] = "OFF"
            response_text += "Tipping / Depositing / Withdraw:\n   {} / {} / {}\n".format(tip_deposit_withdraw_stat[0], tip_deposit_withdraw_stat[1], tip_deposit_withdraw_stat[2])
            get_tip_min_max = "Tip Min/Max:\n   " + num_format_coin(Min_Tip, COIN_NAME, coin_decimal, False) + " / " + num_format_coin(Max_Tip, COIN_NAME, coin_decimal, False) + " " + COIN_NAME
            response_text += get_tip_min_max + "\n"
            get_tx_min_max = "Withdraw Min/Max:\n   " + num_format_coin(Min_Tx, COIN_NAME, coin_decimal, False) + " / " + num_format_coin(Max_Tx, COIN_NAME, coin_decimal, False) + " " + COIN_NAME
            response_text += get_tx_min_max + "\n"

            gas_coin_msg = ""
            if getattr(getattr(self.bot.coin_list, COIN_NAME), "withdraw_use_gas_ticker") == 1:
                GAS_COIN = getattr(getattr(self.bot.coin_list, COIN_NAME), "gas_ticker")
                fee_limit = getattr(getattr(self.bot.coin_list, COIN_NAME), "fee_limit")
                if GAS_COIN and fee_limit > 0:
                    gas_coin_msg = " and a reserved {} {} (actual tx fee is less).".format(fee_limit, GAS_COIN)
            if COIN_NAME == "ADA":
                response_text += "Withdraw Tx reserved Node Fee: {} {} (actual tx fee is less).\n".format(num_format_coin(Fee_Tx, COIN_NAME, coin_decimal, False), COIN_NAME)
            else:
                response_text += "Withdraw Tx Node Fee: {} {}{}\n".format(num_format_coin(Fee_Tx, COIN_NAME, coin_decimal, False), COIN_NAME, gas_coin_msg)
            if deposit_fee > 0:
                response_text += "Deposit Tx Fee: {} {}\n".format(num_format_coin(deposit_fee, COIN_NAME, coin_decimal, False), COIN_NAME)

            if type_coin in ["TRC-10", "TRC-20", "ERC-20"]:
                if contract and len(contract) == 42:
                    response_text += "Contract:\n   {}\n".format(contract)
                elif contract and len(contract) > 4:
                    response_text += "Contract/Token ID:\n   {}\n".format(contract)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        response_text += "```"
        if type(ctx) == disnake.ApplicationCommandInteraction:
            await ctx.response.send_message(content=response_text)
        else:
            await ctx.reply(content=response_text)


    @commands.slash_command(usage="coininfo <coin>",
                            options=[
                                Option("coin", "Enter a coin/ticker name", OptionType.string, required=True)
                            ],
                            description="Get coin's information in TipBot.")
    async def coininfo(
        self, 
        ctx, 
        coin: str
    ):
        await self.get_coininfo(ctx, coin)


    async def async_coinlist(self, ctx):
        if self.bot.coin_name_list and len(self.bot.coin_name_list) > 0:
            network = {}
            network['Others'] = []
            network['ADA'] = []
            network['SOL'] = []
            for COIN_NAME in self.bot.coin_name_list:
                net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
                type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
                if net_name is not None:
                    if net_name not in network:
                        network[net_name] = []
                        network[net_name].append(COIN_NAME)
                    else:
                        network[net_name].append(COIN_NAME)
                else:
                    if type_coin == "ADA":
                        network['ADA'].append(COIN_NAME)
                    elif type_coin == "SOL" or type_coin == "SPL":
                        network['SOL'].append(COIN_NAME)
                    else:
                        network['Others'].append(COIN_NAME)
            embed = disnake.Embed(title=f'Coin/Token list in TipBot', description="Currently, supported {} coins/tokens.".format(len(self.bot.coin_name_list)), timestamp=datetime.now())
            for k, v in network.items():
                list_coins = ", ".join(v)
                if k != "Others":
                    embed.add_field(name=f"Network: {k}", value=f"```{list_coins}```", inline=False)
            # Add Other last
            list_coins = ", ".join(network['Others'])
            embed.add_field(name="Other", value=f"```{list_coins}```", inline=False)
            embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar)
            embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}")
            await ctx.response.send_message(embed=embed)
        else:
            await ctx.response.send_message(f'{ctx.author.mention}, loading, check back later.')


    @commands.slash_command(usage="coinlist",
                            description="List of all coins supported by TipBot.")
    async def coinlist(
        self, 
        ctx
    ):
        await self.async_coinlist(ctx)


def setup(bot):
    bot.add_cog(Coininfo(bot))
