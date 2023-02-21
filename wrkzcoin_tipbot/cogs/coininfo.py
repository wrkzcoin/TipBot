import sys
import traceback
from datetime import datetime
import time

import disnake
from Bot import SERVER_BOT
from cogs.utils import Utils
from cogs.wallet import WalletAPI
from disnake.app_commands import Option
from disnake.enums import OptionType
from disnake.ext import commands
from cogs.utils import num_format_coin


class Coininfo(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)

    async def get_coininfo(
        self,
        ctx, 
        coin: str,
    ):
        await ctx.response.send_message(f"{ctx.author.mention} getting coin info...")
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                        str(ctx.author.id), SERVER_BOT, "/coininfo", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        coin_name = coin.upper()
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f"{ctx.author.mention}, **{coin_name}** does not exist with us."
            await ctx.response.edit_original_message(content=msg)
            return

        confim_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
        min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
        max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
        min_tx = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tx")
        max_tx = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tx")
        fee_tx = getattr(getattr(self.bot.coin_list, coin_name), "real_withdraw_fee")
        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
        deposit_fee = getattr(getattr(self.bot.coin_list, coin_name), "real_deposit_fee")
        contract = None
        if getattr(getattr(self.bot.coin_list, coin_name), "contract") and len(getattr(getattr(self.bot.coin_list, coin_name), "contract")) > 4:
            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
        

        response_text = "**[ COIN/TOKEN INFO {} ]**".format(coin_name)
        response_text += "```"
        try:
            if getattr(getattr(self.bot.coin_list, coin_name), "is_maintenance") != 1:
                try:
                    height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                    if height: response_text += "Height: {:,.0f}".format(height) + "\n"
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    response_text += "Height: N/A (*)" + "\n"
            response_text += "Confirmation: {} Blocks".format(confim_depth) + "\n"
            tip_deposit_withdraw_stat = ["✅ON", "✅ON", "✅ON"]
            if  getattr(getattr(self.bot.coin_list, coin_name), "enable_tip") == 0:
                tip_deposit_withdraw_stat[0] = "🔴OFF"
            if  getattr(getattr(self.bot.coin_list, coin_name), "enable_deposit") == 0:
                tip_deposit_withdraw_stat[1] = "🔴OFF"
            if  getattr(getattr(self.bot.coin_list, coin_name), "enable_withdraw") == 0:
                tip_deposit_withdraw_stat[2] = "🔴OFF"
            response_text += "Tipping / Depositing / Withdraw:\n   {} / {} / {}\n".format(
                tip_deposit_withdraw_stat[0], tip_deposit_withdraw_stat[1], tip_deposit_withdraw_stat[2]
            )
            get_tip_min_max = "Tip Min/Max:\n   " + num_format_coin(min_tip) + " / " + num_format_coin(max_tip) + " " + coin_name
            response_text += get_tip_min_max + "\n"
            if coin_name in self.bot.cexswap_coins:
                response_text += "\nCEXSwap:\n   ✅ON\n"
                min_initialized_liq_1 = getattr(getattr(self.bot.coin_list, coin_name), "cexswap_min_initialized_liq")
                min_add_liq = getattr(getattr(self.bot.coin_list, coin_name), "cexswap_min_add_liq")
                cexswap_min = getattr(getattr(self.bot.coin_list, coin_name), "cexswap_min")
                min_initialized_liq_1 = num_format_coin(min_initialized_liq_1)
                min_add_liq = num_format_coin(min_add_liq)
                cexswap_min = num_format_coin(cexswap_min)
                response_text += "Mininimum:\n   " + f"Sell: {cexswap_min} {coin_name}\n" + f"   Add: {min_add_liq} {coin_name}\n" \
                    + f"   Init. LP: {min_initialized_liq_1} {coin_name}\n\n"


            get_tx_min_max = "Withdraw Min/Max:\n   " + num_format_coin(min_tx) + " / " + num_format_coin(max_tx) + " " + coin_name
            response_text += get_tx_min_max + "\n"

            gas_coin_msg = ""
            if getattr(getattr(self.bot.coin_list, coin_name), "withdraw_use_gas_ticker") == 1:
                GAS_COIN = getattr(getattr(self.bot.coin_list, coin_name), "gas_ticker")
                fee_limit = getattr(getattr(self.bot.coin_list, coin_name), "fee_limit")
                if GAS_COIN and fee_limit > 0:
                    gas_coin_msg = " and a reserved {} {} (actual tx fee is less).".format(fee_limit, GAS_COIN)
            if coin_name == "ADA":
                response_text += "Withdraw Tx reserved Node Fee: {} {} (actual tx fee is less).\n".format(num_format_coin(fee_tx), coin_name)
            else:
                response_text += "Withdraw Tx Node Fee: {} {}{}\n".format(num_format_coin(fee_tx), coin_name, gas_coin_msg)
            if deposit_fee > 0:
                response_text += "Deposit Tx Fee: {} {}\n".format(num_format_coin(deposit_fee), coin_name)

            if type_coin in ["TRC-10", "TRC-20", "ERC-20"]:
                if contract and len(contract) == 42:
                    response_text += "Contract:\n   {}\n".format(contract)
                elif contract and len(contract) > 4:
                    response_text += "Contract/Token ID:\n   {}\n".format(contract)
            price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
            if price_with:
                per_unit = await self.utils.get_coin_price(coin_name, price_with)
                if per_unit and per_unit['price'] and per_unit['price'] > 0:
                    per_unit = per_unit['price']
                    if per_unit >= 0.0001:
                        equivalent_usd = " ~ {:,.4f}$".format(per_unit)
                        response_text += "Price 1 {} {} based on {}\n".format(coin_name, equivalent_usd, price_with.lower())
        except Exception:
            traceback.print_exc(file=sys.stdout)
        response_text += "```"

        other_links = []
        if getattr(getattr(self.bot.coin_list, coin_name), "explorer_link") and \
            len(getattr(getattr(self.bot.coin_list, coin_name), "explorer_link")) > 0:
            other_links.append(
                "[{}]({})".format("Explorer Link", "<" + getattr(getattr(self.bot.coin_list, coin_name), "explorer_link") + ">")
            )
        if getattr(getattr(self.bot.coin_list, coin_name), "id_cmc"):
            other_links.append(
                "[{}]({})".format("CoinMarketCap", "<https://coinmarketcap.com/currencies/" + getattr(getattr(self.bot.coin_list, coin_name), "id_cmc") + ">")
            )
        if getattr(getattr(self.bot.coin_list, coin_name), "id_gecko"):
            other_links.append(
                "[{}]({})".format("CoinGecko", "<https://www.coingecko.com/en/coins/" + getattr(getattr(self.bot.coin_list, coin_name), "id_gecko") + ">")
            )
        if getattr(getattr(self.bot.coin_list, coin_name), "id_paprika"):
            other_links.append(
                "[{}]({})".format("Coinpaprika", "<https://coinpaprika.com/coin/" + getattr(getattr(self.bot.coin_list, coin_name), "id_paprika") + ">")
            )
        if getattr(getattr(self.bot.coin_list, coin_name), "repo_link"):
            other_links.append(
                "[{}]({})".format("Repo", "<" + getattr(getattr(self.bot.coin_list, coin_name), "repo_link") + ">")
            )

        if len(other_links) > 0:
            response_text += "{}".format(" | ".join(other_links))
        await ctx.edit_original_message(content=response_text)

    @commands.slash_command(
        usage="coininfo <coin>",
        options=[
            Option("coin", "Enter a coin/ticker name", OptionType.string, required=True)
        ],
        description="Get coin's information in TipBot."
    )
    async def coininfo(
        self, 
        ctx, 
        coin: str
    ):
        await self.get_coininfo(ctx, coin)

    @coininfo.autocomplete("coin")
    async def coin_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]

    async def async_coinlist(self, ctx):
        await ctx.response.send_message(f"{ctx.author.mention} getting coin list...")
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                        str(ctx.author.id), SERVER_BOT, "/coinlist", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        if self.bot.coin_name_list and len(self.bot.coin_name_list) > 0:
            network = {
                'Others': [],
                'ADA': [],
                'SOL': [],
                'COSMOS': []
            }
            for coin_name in self.bot.coin_name_list:
                net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                if net_name is not None:
                    if net_name not in network:
                        network[net_name] = []
                        network[net_name].append(coin_name)
                    else:
                        network[net_name].append(coin_name)
                else:
                    if type_coin == "ADA":
                        network['ADA'].append(coin_name)
                    elif type_coin == "SOL" or type_coin == "SPL":
                        network['SOL'].append(coin_name)
                    elif type_coin == "COSMOS":
                        network['COSMOS'].append(coin_name)
                    else:
                        network['Others'].append(coin_name)
            embed = disnake.Embed(
                title=f"Coin/Token list in TipBot",
                description="Currently, [supported {} coins/tokens](https://coininfo.bot.tips/).".format(
                    len(self.bot.coin_name_list)
                ),
                timestamp=datetime.now()
            )
            for k, v in network.items():
                list_coins = ", ".join(v)
                if k != "Others":
                    embed.add_field(name=f"Network: {k}", value=f"{list_coins}", inline=False)
            # Add Other last
            list_coins = ", ".join(network['Others'])
            embed.add_field(name="Other", value=f"{list_coins}", inline=False)
            try:
                bot_settings = await self.utils.get_bot_settings()
                embed.add_field(name='Add Coin/Token', value=bot_settings['link_listing_form'], inline=False)
            except Exception:
                traceback.print_exc(file=sys.stdout)
            embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar)
            embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator} | Total: {str(len(self.bot.coin_name_list))} ")
            await ctx.edit_original_message(content=None, embed=embed)
        else:
            await ctx.edit_original_message(content=f"{ctx.author.mention}, error loading. check back later.")

    @commands.slash_command(
        usage="coinlist",
        description="List of all coins supported by TipBot."
    )
    async def coinlist(
        self, 
        ctx
    ):
        await self.async_coinlist(ctx)


def setup(bot):
    bot.add_cog(Coininfo(bot))
