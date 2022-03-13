import asyncio
import sys
import time
import traceback
from datetime import datetime
import random
import re
from decimal import Decimal
import numexpr
from typing import List, Dict

import disnake
from disnake.ext import commands, tasks
from disnake import ActionRow, Button

from disnake.enums import OptionType
from disnake.app_commands import Option

from disnake.enums import ButtonStyle
import copy

# numexpr
import numexpr

import store
from Bot import num_format_coin, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_ARROW_RIGHTHOOK, EMOJI_MONEYFACE, NOTIFICATION_OFF_CMD, EMOJI_SPEAK, EMOJI_BELL, EMOJI_BELL_SLASH, EMOJI_HOURGLASS_NOT_DONE, EMOJI_INFORMATION, EMOJI_PARTY, SERVER_BOT, seconds_str, RowButton_close_message, RowButton_row_close_any_message, text_to_num, truncate
from config import config
import redis_utils

from cogs.wallet import WalletAPI


class MyMathBtn(disnake.ui.Button):
    def __init__(self, label, _style, _custom_id):
        super().__init__(label=label, style=_style, custom_id= _custom_id)


class MathButton(disnake.ui.View):
    message: disnake.Message
    a_index: int
    coin_list: Dict

    def __init__(self, answer_list, answer_index: int, timeout: float, coin_list):
        super().__init__(timeout=timeout)
        i = 0
        self.a_index = answer_index
        self.coin_list = coin_list
        for name in answer_list:
            custom_id = "mathtip_answers_"+str(i)
            self.add_item(MyMathBtn(name, ButtonStyle.green, custom_id))
            i += 1


    async def on_timeout(self):
        i = 0
        for child in self.children:
            if isinstance(child, disnake.ui.Button):
                child.disabled = True
                if i == self.a_index:
                    child.style = ButtonStyle.red
                i += 1
        ## Update content
        get_mathtip = await store.get_discord_mathtip_by_msgid(str(self.message.id))
        if get_mathtip['status'] == "ONGOING":
            answered_msg_id = await store.get_math_responders_by_message_id(str(self.message.id))
            amount = get_mathtip['real_amount']
            COIN_NAME = get_mathtip['token_name']
            owner_displayname = get_mathtip['from_username']
            total_answer = answered_msg_id['total']
            coin_decimal = getattr(getattr(self.coin_list, COIN_NAME), "decimal")
            contract = getattr(getattr(self.coin_list, COIN_NAME), "contract")
            token_display = getattr(getattr(self.coin_list, COIN_NAME), "display_name")
            usd_equivalent_enable = getattr(getattr(self.coin_list, COIN_NAME), "usd_equivalent_enable")

            indiv_amount_str = num_format_coin(truncate(amount / len(answered_msg_id['right_ids']), 4), COIN_NAME, coin_decimal, False) if len(answered_msg_id['right_ids']) > 0 else num_format_coin(truncate(amount, 4), COIN_NAME, coin_decimal, False)
            indiv_amount = truncate(amount / len(answered_msg_id['right_ids']), 4) if len(answered_msg_id['right_ids']) > 0 else truncate(amount, 4)

            amount_in_usd = 0.0
            each_amount_in_usd = 0.0

            total_equivalent_usd = ""
            per_unit = None
            if usd_equivalent_enable == 1:
                per_unit = get_mathtip['unit_price_usd']
                if per_unit and per_unit > 0 and len(answered_msg_id['right_ids']) > 0:
                    each_amount_in_usd = per_unit * float(indiv_amount)
                    if each_amount_in_usd > 0.0001:
                        num = len(answered_msg_id['right_ids']) if len(answered_msg_id['right_ids']) > 0 else 1
                        total_equivalent_usd = " ~ {:,.4f} USD".format(each_amount_in_usd * num)
                elif per_unit and per_unit > 0 and len(answered_msg_id['right_ids']) == 0:
                    each_amount_in_usd = per_unit * float(indiv_amount)
                    total_equivalent_usd = " ~ {:,.4f} USD".format(each_amount_in_usd)
                        

            embed = disnake.Embed(title=f"🧮 Math Tip {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display} {total_equivalent_usd} - Total answer {total_answer}", description=get_mathtip['eval_content'], timestamp=datetime.fromtimestamp(get_mathtip['math_endtime']))
            embed.add_field(name="Correct answer", value=get_mathtip['eval_answer'], inline=False)
            embed.add_field(name="Correct ( {} )".format(len(answered_msg_id['right_ids'])), value="{}".format(" | ".join(answered_msg_id['right_names']) if len(answered_msg_id['right_names']) > 0 else "N/A"), inline=False)
            embed.add_field(name="Incorrect ( {} )".format(len(answered_msg_id['wrong_ids'])), value="{}".format(" | ".join(answered_msg_id['wrong_names']) if len(answered_msg_id['wrong_names']) > 0 else "N/A"), inline=False)
            if len(answered_msg_id['right_ids']) > 0:
                embed.add_field(name='Each Winner Receives:', value=f"{indiv_amount_str} {token_display}", inline=True)
            embed.set_footer(text=f"Trivia tip by {owner_displayname}")

            if len(answered_msg_id['right_ids']) > 0:
                trivia_tipping = await store.sql_user_balance_mv_multiple(get_mathtip['from_userid'], answered_msg_id['right_ids'], get_mathtip['guild_id'], get_mathtip['channel_id'], float(indiv_amount), COIN_NAME, "MATHTIP", coin_decimal, SERVER_BOT, contract, float(each_amount_in_usd))
            # Change status
            change_status = await store.discord_mathtip_update(get_mathtip['message_id'], "COMPLETED")
            await self.message.edit(embed=embed, view=self)
        else:
            await self.message.edit(view=self)


class MathTips(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    @commands.guild_only()
    @commands.command(usage='mathtips', aliases=['mathtips'], description="List ongoing math tips")
    async def _mathtips(self, ctx):
        get_mathtips = await store.get_discord_mathtip_by_chanid(str(ctx.channel.id))
        if len(get_mathtips) > 0:
            is_are = "is" if len(get_mathtips) == 1 else "are"
            tip_tips = "tip" if len(get_mathtips) == 1 else "tips"
            embed = disnake.Embed(title=f"🧮 Math Tip", description=f"There {is_are} math {tip_tips} in {ctx.channel.mention}")
            for each_q in get_mathtips:
                embed.add_field(name="By: {} / Left: {}s".format(each_q['from_username'], each_q['math_endtime'] - int(time.time()) if each_q['math_endtime'] - int(time.time()) > 0 else 0), value="```Exp: {}\nAmount: {} {}```".format(each_q['eval_content'], each_q['real_amount'], each_q['token_name']), inline=False)
            embed.set_footer(text=f"🧮 Use .mathtip (without s) with parameters to create math quiz.")
            msg = await ctx.reply(embed=embed)
        else:
            await ctx.reply(f'{EMOJI_INFORMATION} {ctx.author.mention} There is no ongoing math tip(s) in {ctx.channel.mention}.')
        return


    async def async_mathtip(self, ctx, amount: str, token: str, duration: str, math_exp: str=None):
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

        try:
            token_display = getattr(getattr(self.bot.coin_list, COIN_NAME), "display_name")
            contract = getattr(getattr(self.bot.coin_list, COIN_NAME), "contract")

            net_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, COIN_NAME), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, COIN_NAME), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, COIN_NAME), "decimal")
            MinTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_min_tip")
            MaxTip = getattr(getattr(self.bot.coin_list, COIN_NAME), "real_max_tip")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, COIN_NAME), "usd_equivalent_enable")
            
            User_WalletAPI = WalletAPI(self.bot)
            get_deposit = await User_WalletAPI.sql_get_userwallet(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)
            if get_deposit is None:
                get_deposit = await User_WalletAPI.sql_register_user(str(ctx.author.id), COIN_NAME, net_name, type_coin, SERVER_BOT, 0)

            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

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
        # If $ is in amount, let's convert to coin/token
        elif "$" in amount[-1] or "$" in amount[0]: # last is $
            # Check if conversion is allowed for this coin.
            amount = amount.replace(",", "").replace("$", "")
            if usd_equivalent_enable == 0:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{COIN_NAME}`."
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
            else:
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
                    amount = float(Decimal(amount) / Decimal(per_unit))
                else:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. Try with different method.'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
        else:
            amount = amount.replace(",", "")
            amount = text_to_num(amount)
            if amount is None:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
        # end of check if amount is all

        # Check if tx in progress
        if ctx.author.id in self.bot.TX_IN_PROCESS:
            msg = f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        try:
            amount = float(amount)
        except ValueError:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        if amount <= 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        def hms_to_seconds(time_string):
            duration_in_second = 0
            try:
                time_string = time_string.replace("hours", "h")
                time_string = time_string.replace("hour", "h")
                time_string = time_string.replace("hrs", "h")
                time_string = time_string.replace("hr", "h")

                time_string = time_string.replace("minutes", "mn")
                time_string = time_string.replace("mns", "mn")
                time_string = time_string.replace("mins", "mn")
                time_string = time_string.replace("min", "mn")
                time_string = time_string.replace("mn", "mn")
                mult = {'h': 60*60, 'mn': 60, 's': 1}
                duration_in_second = sum(int(num) * mult.get(val, 1) for num, val in re.findall('(\d+)(\w+)', time_string))
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            return duration_in_second

        default_duration = 60
        duration_s = 0
        try:
            duration_s = hms_to_seconds(duration)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid duration.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        if duration_s == 0:
            # Skip message
            # msg = await ctx.reply(f'{ctx.author.mention} Invalid time given. Please use time format: XXs. I take default: {default_duration}s.')
            duration_s = default_duration
            # Just info, continue
        elif duration_s < config.mathtip.duration_min or duration_s > config.mathtip.duration_max:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid duration. Please use between {str(config.mathtip.duration_min)}s to {str(config.mathtip.duration_max)}s.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        try:
            amount = float(amount)
        except ValueError:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        result_float = None
        wrong_answer_1 = None
        wrong_answer_2 = None
        wrong_answer_3 = None
        eval_string_original = ""
        if math_exp and len(math_exp) > 0:
            eval_string_original = math_exp
            math_exp = math_exp.replace(",", "").replace(" ", "")
            supported_function = ['+', '-', '*', '/', '(', ')', '.', ',', '!', '^']
            additional_support = ['exp', 'sqrt', 'abs', 'log10', 'log', 'sinh', 'cosh', 'tanh', 'sin', 'cos', 'tan']
            has_operation = False
            for each_op in ['exp', 'sqrt', 'abs', 'log10', 'log', 'sinh', 'cosh', 'tanh', 'sin', 'cos', 'tan', '+', '-', '*', '/', '!', '^']:
                if each_op in math_exp: has_operation = True
            if has_operation == False:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, nothing to calculate.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
            test_string = math_exp
            for each in additional_support:
                test_string = test_string.replace(each, "")
            if all([c.isdigit() or c in supported_function for c in test_string]):
                try:
                    result = numexpr.evaluate(math_exp).item()
                    listrand = [2, 3, 4, 5, 6, 7, 8, 9, 10]
                    # OK have result. Check it if it's bigger than 10**10 or below 0.0001
                    if abs(result) > 10**10:
                        msg = f'{EMOJI_RED_NO} Result for `{eval_string_original}` is too big.'
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg)
                        else:
                            await ctx.reply(msg)
                        return
                    elif abs(result) < 0.0001:
                        msg = f'{EMOJI_RED_NO} Result for `{eval_string_original}` is too small.'
                        if type(ctx) == disnake.ApplicationCommandInteraction:
                            await ctx.response.send_message(msg)
                        else:
                            await ctx.reply(msg)
                        return
                    else:
                        # store result in float XX.XXXX
                        if result >= 0:
                            result_float = truncate(float(result), 4)
                            wrong_answer_1 = truncate(float(result*random.choice(listrand)), 4)
                            wrong_answer_2 = truncate(float(result+random.choice(listrand)), 4)
                            wrong_answer_3 = truncate(float(result-random.choice(listrand)), 4)
                        else:
                            result_float = - abs(truncate(float(result), 4))
                            wrong_answer_1 = - abs(truncate(float(result*random.choice(listrand)), 4))
                            wrong_answer_2 = - abs(truncate(float(result+random.choice(listrand)), 4))
                            wrong_answer_3 = - abs(truncate(float(result-random.choice(listrand)), 4))
                except Exception as e:
                    msg = f'{EMOJI_RED_NO} Invalid result for `{eval_string_original}`.'
                    if type(ctx) == disnake.ApplicationCommandInteraction:
                        await ctx.response.send_message(msg)
                    else:
                        await ctx.reply(msg)
                    return
            else:
                msg = f'{EMOJI_ERROR} {ctx.author.mention} Unsupported usage for `{eval_string_original}`.'
                if type(ctx) == disnake.ApplicationCommandInteraction:
                    await ctx.response.send_message(msg)
                else:
                    await ctx.reply(msg)
                return
        else:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Invalid math expression.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

       
        userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), COIN_NAME, wallet_address, type_coin, height, deposit_confirm_depth, SERVER_BOT)
        actual_balance = float(userdata_balance['adjust'])

        if amount > MaxTip or amount < MinTip:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than **{num_format_coin(MaxTip, COIN_NAME, coin_decimal, False)} {token_display}** or smaller than **{num_format_coin(MinTip, COIN_NAME, coin_decimal, False)} {token_display}**.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return
        elif amount > actual_balance:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to do a math tip of **{num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display}**.'
            if type(ctx) == disnake.ApplicationCommandInteraction:
                await ctx.response.send_message(msg)
            else:
                await ctx.reply(msg)
            return

        ## add to DB
        if ctx.author.id not in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.append(ctx.author.id)

        equivalent_usd = ""
        total_in_usd = 0.0
        per_unit = None
        if usd_equivalent_enable == 1:
            native_token_name = getattr(getattr(self.bot.coin_list, COIN_NAME), "native_token_name")
            COIN_NAME_FOR_PRICE = COIN_NAME
            if native_token_name:
                COIN_NAME_FOR_PRICE = native_token_name
            if COIN_NAME_FOR_PRICE in self.bot.token_hints:
                id = self.bot.token_hints[COIN_NAME_FOR_PRICE]['ticker_name']
                per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
            else:
                per_unit = self.bot.coin_paprika_symbol_list[COIN_NAME_FOR_PRICE]['price_usd']
            if per_unit and per_unit > 0:
                total_in_usd = float(Decimal(amount) * Decimal(per_unit))
                if total_in_usd >= 0.0001:
                    equivalent_usd = " ~ {:,.4f} USD".format(total_in_usd)

        owner_displayname = "{}#{}".format(ctx.author.name, ctx.author.discriminator)
        embed = disnake.Embed(title=f"🧮 Math Tip {num_format_coin(amount, COIN_NAME, coin_decimal, False)} {token_display} {equivalent_usd}", description=eval_string_original, timestamp=datetime.fromtimestamp(int(time.time())+duration_s))
        embed.add_field(name="Answering", value="None", inline=False)
        embed.set_footer(text=f"Math tip by {owner_displayname}")

        answers = [str(result_float), str(wrong_answer_1), str(wrong_answer_2), str(wrong_answer_3)]
        random.shuffle(answers)
        index_answer = answers.index(str(result_float))
        
        view = MathButton(answers, index_answer, duration_s, self.bot.coin_list)
        await asyncio.sleep(0.2)

        if type(ctx) == disnake.ApplicationCommandInteraction:
            view.message = await ctx.channel.send(embed=embed, view=view)
            await ctx.response.send_message("Math Tip ID: {} created!".format(view.message.id), ephemeral=True)
        else:
            view.message = await ctx.reply(embed=embed, view=view)

        insert_mathtip = await store.insert_discord_mathtip(COIN_NAME, contract, str(ctx.author.id), owner_displayname, str(view.message.id), eval_string_original, result_float, wrong_answer_1, wrong_answer_2, wrong_answer_3, str(ctx.guild.id), str(ctx.channel.id), amount, total_in_usd, equivalent_usd, per_unit, coin_decimal, int(time.time())+duration_s, net_name)
        if insert_mathtip and type(ctx) != disnake.ApplicationCommandInteraction:
            await ctx.message.add_reaction("🧮")
        if ctx.author.id in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.remove(ctx.author.id)


    @commands.guild_only()
    @commands.slash_command(
        usage='mathtip <amount> <token> <duration> <math expression>', 
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('token', 'token', OptionType.string, required=True),
            Option('duration', 'duration', OptionType.string, required=True),
            Option('math_exp', 'math_exp', OptionType.string, required=True)
        ],
        description="Spread math tip by user's answer"
    )
    async def mathtip(
        self, 
        ctx, 
        amount: str, 
        token: str, 
        duration: str, 
        math_exp: str
    ):
        await self.async_mathtip(ctx, amount, token, duration, math_exp)


    @commands.guild_only()
    @commands.command(usage='mathtip <amount> <token> <duration> <math expression>', aliases=['tipmath', 'mathtip'], description="Spread math tip by user's answer")
    async def _mathtip(self, ctx, amount: str, token: str, duration: str, *, math_exp: str = None):
        await self.async_mathtip(ctx, amount, token, duration, math_exp)


    @mathtip.error
    async def mathtip_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(f'{EMOJI_RED_NO} {ctx.author.mention} Missing arguments. You need to tell me **amount** **token** and **duration** in seconds (with s).\nExample: {config.discord.prefixCmd}{ctx.command} **1000 token 300s** or {config.discord.prefixCmd}{ctx.command} **10 token 300s 2+3-1**')
        elif isinstance(error, commands.errors.CommandInvokeError):
            await ctx.reply(f'{EMOJI_RED_NO} {ctx.author.mention} Error arguments. '
                            f'You need to tell me **amount** **token** and **duration** in seconds (with s).\nExample: {config.discord.prefixCmd}{ctx.command} **100 token 300s** or {config.discord.prefixCmd}{ctx.command} **10 token 300s 2+3-1**')
        return


def setup(bot):
    bot.add_cog(MathTips(bot))
