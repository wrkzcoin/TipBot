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

import store
from Bot import num_format_coin, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_ARROW_RIGHTHOOK, \
    EMOJI_MONEYFACE, NOTIFICATION_OFF_CMD, EMOJI_SPEAK, EMOJI_BELL, EMOJI_BELL_SLASH, EMOJI_HOURGLASS_NOT_DONE, \
    EMOJI_INFORMATION, EMOJI_PARTY, SERVER_BOT, seconds_str, RowButtonCloseMessage, RowButtonRowCloseAnyMessage, \
    text_to_num, truncate

from cogs.wallet import WalletAPI
from cogs.utils import Utils

class MyMathBtn(disnake.ui.Button):
    def __init__(self, label, _style, _custom_id):
        super().__init__(label=label, style=_style, custom_id=_custom_id)


class MathButton(disnake.ui.View):
    message: disnake.Message
    a_index: int
    coin_list: Dict

    def __init__(self, ctx, answer_list, answer_index: int, timeout: float, coin_list):
        super().__init__(timeout=timeout)
        i = 0
        self.a_index = answer_index
        self.coin_list = coin_list
        self.ctx = ctx
        for name in answer_list:
            custom_id = "mathtip_answers_" + str(i)
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
        get_mathtip = None
        try:
            original_message = await self.ctx.original_message()
            get_mathtip = await store.get_discord_mathtip_by_msgid(str(original_message.id))
        except Exception:
            traceback.print_exc(file=sys.stdout)
            return

        if get_mathtip is None:
            await logchanbot(f"[ERROR MATH TIP] Failed timeout in guild {self.ctx.guild.name} / {self.ctx.guild.id}!")
            return
        if get_mathtip['status'] == "ONGOING":
            answered_msg_id = await store.get_math_responders_by_message_id(str(self.message.id))
            amount = get_mathtip['real_amount']
            coin_name = get_mathtip['token_name']
            owner_displayname = get_mathtip['from_username']
            total_answer = answered_msg_id['total']
            coin_decimal = getattr(getattr(self.coin_list, coin_name), "decimal")
            contract = getattr(getattr(self.coin_list, coin_name), "contract")
            token_display = getattr(getattr(self.coin_list, coin_name), "display_name")
            usd_equivalent_enable = getattr(getattr(self.coin_list, coin_name), "usd_equivalent_enable")

            coin_emoji = getattr(getattr(self.coin_list, coin_name), "coin_emoji_discord")
            coin_emoji = coin_emoji + " " if coin_emoji else ""

            indiv_amount_str = num_format_coin(truncate(amount / len(answered_msg_id['right_ids']), 4), coin_name,
                                               coin_decimal, False) if len(
                answered_msg_id['right_ids']) > 0 else num_format_coin(truncate(amount, 4), coin_name, coin_decimal,
                                                                       False)
            indiv_amount = truncate(amount / len(answered_msg_id['right_ids']), 4) if len(
                answered_msg_id['right_ids']) > 0 else truncate(amount, 4)

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

            embed = disnake.Embed(
                title=f"🧮 Math Tip {coin_emoji}{num_format_coin(amount, coin_name, coin_decimal, False)} "\
                    f"{token_display} {total_equivalent_usd} - Total answer {total_answer}",
                description=get_mathtip['eval_content'],
                timestamp=datetime.fromtimestamp(get_mathtip['math_endtime']
            )
            )
            embed.add_field(
                name="Correct answer",
                value=get_mathtip['eval_answer'],
                inline=False
            )
            embed.add_field(
                name="Correct ( {} )".format(len(answered_msg_id['right_ids'])),
                value="{}".format(
                    " | ".join(answered_msg_id['right_names']) if len(answered_msg_id['right_names']) > 0 else "N/A"),
                inline=False
            )
            embed.add_field(
                name="Incorrect ( {} )".format(len(answered_msg_id['wrong_ids'])),
                value="{}".format(
                    " | ".join(answered_msg_id['wrong_names']) if len(answered_msg_id['wrong_names']) > 0 else "N/A"),
                inline=False
            )
            if len(answered_msg_id['right_ids']) > 0:
                embed.add_field(
                    name='Each Winner Receives:',
                    value=f"{coin_emoji}{indiv_amount_str} {token_display}",
                    inline=True
                )
            embed.set_footer(text=f"MathTip by {owner_displayname}")

            if len(answered_msg_id['right_ids']) > 0:
                try:
                    key_coin = get_mathtip['from_userid'] + "_" + coin_name + "_" + SERVER_BOT
                    if key_coin in self.bot.user_balance_cache:
                        del self.bot.user_balance_cache[key_coin]

                    for each in answered_msg_id['right_ids']:
                        key_coin = each + "_" + coin_name + "_" + SERVER_BOT
                        if key_coin in self.bot.user_balance_cache:
                            del self.bot.user_balance_cache[key_coin]
                except Exception:
                    pass
                await store.sql_user_balance_mv_multiple(
                    get_mathtip['from_userid'], answered_msg_id['right_ids'],
                    get_mathtip['guild_id'], get_mathtip['channel_id'],
                    float(indiv_amount), coin_name, "MATHTIP", coin_decimal, SERVER_BOT, contract,
                    float(each_amount_in_usd), None
                )
            # Change status
            change_status = await store.discord_mathtip_update(get_mathtip['message_id'], "COMPLETED")
            await original_message.edit(embed=embed, view=self)
        else:
            await original_message.edit(view=self)


class MathTips(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)

        self.math_duration_min = 5
        self.math_duration_max = 45

        self.max_ongoing_by_user = 3
        self.max_ongoing_by_guild = 5


    async def async_mathtip(self, ctx, amount: str, token: str, duration: str, math_exp: str = None):
        coin_name = token.upper()
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        # Token name check
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
            await ctx.response.send_message(msg)
            return
        # End token name check

        await ctx.response.send_message(f"{ctx.author.mention}, /mathtip preparation... ")

        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo['tiponly'] and serverinfo['tiponly'] != "ALLCOIN" and coin_name not in serverinfo[
            'tiponly'].split(","):
            allowed_coins = serverinfo['tiponly']
            msg = f"{ctx.author.mention}, **{coin_name}** is not allowed here. Currently, allowed `{allowed_coins}`. "\
                "You can ask guild owner to allow. `/SETTING TIPONLY coin1,coin2,...`"
            await ctx.edit_original_message(content=msg)
            return

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/mathtip", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        # Check if there is many airdrop/mathtip/triviatip
        try:
            count_ongoing = await store.discord_freetip_ongoing(str(ctx.author.id), "ONGOING")
            if count_ongoing >= self.max_ongoing_by_user and \
                ctx.author.id != self.bot.config['discord']['owner_id']:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, you still have some ongoing tips. "\
                    f"Please wait for them to complete first!"
                await ctx.edit_original_message(content=msg)
                return
            count_ongoing = await store.discord_freetip_ongoing_guild(str(ctx.guild.id), "ONGOING")
            # Check max if set in guild
            if serverinfo and count_ongoing >= serverinfo['max_ongoing_drop'] and\
                 ctx.author.id != self.bot.config['discord']['owner_id']:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, there are still some ongoing drops"\
                    f" or tips in this guild. Please wait for them to complete first!"
                await ctx.edit_original_message(content=msg)
                return
            elif serverinfo is None and count_ongoing >= self.max_ongoing_by_guild and\
                 ctx.author.id != self.bot.config['discord']['owner_id']:
                msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, there are still some ongoing drops or"\
                    f" tips in this guild. Please wait for them to complete first!"
                await ctx.edit_original_message(content=msg)
                await logchanbot(f"[MATHTIP] server {str(ctx.guild.id)} has no data in discord_server.")
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # End of ongoing check

        try:
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")

            coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
            coin_emoji = coin_emoji + " " if coin_emoji else ""

            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
            max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name), "usd_equivalent_enable")
            get_deposit = await self.wallet_api.sql_get_userwallet(
                str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0
            )
            if get_deposit is None:
                get_deposit = await self.wallet_api.sql_register_user(
                    str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0
                )

            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']
            elif type_coin in ["XRP"]:
                wallet_address = get_deposit['destination_tag']

        except Exception:
            traceback.print_exc(file=sys.stdout)
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, some internal error. Please try again."
            await ctx.edit_original_message(content=msg)
            return

        height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
        # check if amount is all
        all_amount = False
        if not amount.isdigit() and amount.upper() == "ALL":
            all_amount = True
            userdata_balance = await store.sql_user_balance_single(
                str(ctx.author.id), coin_name, wallet_address, type_coin, 
                height, deposit_confirm_depth, SERVER_BOT
            )
            amount = float(userdata_balance['adjust'])
        # If $ is in amount, let's convert to coin/token
        elif "$" in amount[-1] or "$" in amount[0]:  # last is $
            # Check if conversion is allowed for this coin.
            amount = amount.replace(",", "").replace("$", "")
            if usd_equivalent_enable == 0:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not "\
                    f"enabled for this `{coin_name}`."
                await ctx.edit_original_message(content=msg)
                return
            else:
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
                    amount = float(Decimal(amount) / Decimal(per_unit))
                else:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. "\
                        f"Try with different method."
                    await ctx.edit_original_message(content=msg)
                    return
        else:
            amount = amount.replace(",", "")
            amount = text_to_num(amount)
            if amount is None:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
                await ctx.edit_original_message(content=msg)
                return
        # end of check if amount is all

        # Check if tx in progress
        if str(ctx.author.id) in self.bot.tipping_in_progress and \
            int(time.time()) - self.bot.tipping_in_progress[str(ctx.author.id)] < 150:
            msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another transaction in progress."
            await ctx.edit_original_message(content=msg)
            return

        try:
            amount = float(amount)
        except ValueError:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid amount.'
            await ctx.edit_original_message(content=msg)
            return

        if amount <= 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}.'
            await ctx.edit_original_message(content=msg)
            return

        def hms_to_seconds(time_string):
            duration_in_second = 0
            if time_string.isdigit():
                return int(time_string)
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
                mult = {'h': 60 * 60, 'mn': 60, 's': 1}
                duration_in_second = sum(
                    int(num) * mult.get(val, 1) for num, val in re.findall('(\d+)(\w+)', time_string))
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return duration_in_second

        default_duration = 60
        duration_s = 0
        try:
            duration_s = hms_to_seconds(duration)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid duration.'
            await ctx.edit_original_message(content=msg)
            return

        if duration_s == 0:
            # Skip message
            duration_s = default_duration
            # Just info, continue
        elif duration_s < self.math_duration_min or duration_s > self.math_duration_max:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid duration. "\
                f"Please use between {str(self.math_duration_min)}s to {str(self.math_duration_max)}s."
            await ctx.edit_original_message(content=msg)
            return

        try:
            amount = float(amount)
        except ValueError:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid amount.'
            await ctx.edit_original_message(content=msg)
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
            for each_op in ['exp', 'sqrt', 'abs', 'log10', 'log', 'sinh', 'cosh', 'tanh', 'sin', 'cos', 'tan', '+', '-',
                            '*', '/', '!', '^']:
                if each_op in math_exp: has_operation = True
            if has_operation is False:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, nothing to calculate.'
                await ctx.edit_original_message(content=msg)
                return
            test_string = math_exp
            for each in additional_support:
                test_string = test_string.replace(each, "")
            if all([c.isdigit() or c in supported_function for c in test_string]):
                try:
                    result = numexpr.evaluate(math_exp).item()
                    listrand = [2, 3, 4, 5, 6, 7, 8, 9, 10]
                    # OK have result. Check it if it's bigger than 10**10 or below 0.0001
                    if abs(result) > 10 ** 10:
                        msg = f'{EMOJI_RED_NO} Result for `{eval_string_original}` is too big.'
                        await ctx.edit_original_message(content=msg)
                        return
                    elif abs(result) < 0.0001:
                        msg = f'{EMOJI_RED_NO} Result for `{eval_string_original}` is too small.'
                        await ctx.edit_original_message(content=msg)
                        return
                    else:
                        # store result in float XX.XXXX
                        if result >= 0:
                            result_float = truncate(float(result), 4)
                            wrong_answer_1 = truncate(float(result * random.choice(listrand)), 4)
                            wrong_answer_2 = truncate(float(result + random.choice(listrand)), 4)
                            wrong_answer_3 = truncate(float(result - random.choice(listrand)), 4)
                        else:
                            result_float = - abs(truncate(float(result), 4))
                            wrong_answer_1 = - abs(truncate(float(result * random.choice(listrand)), 4))
                            wrong_answer_2 = - abs(truncate(float(result + random.choice(listrand)), 4))
                            wrong_answer_3 = - abs(truncate(float(result - random.choice(listrand)), 4))
                except Exception:
                    msg = f'{EMOJI_RED_NO}, invalid result for `{eval_string_original}`.'
                    await ctx.edit_original_message(content=msg)
                    return
            else:
                msg = f'{EMOJI_ERROR} {ctx.author.mention}, unsupported usage for `{eval_string_original}`.'
                await ctx.edit_original_message(content=msg)
                return
        else:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid math expression.'
            await ctx.edit_original_message(content=msg)
            return

        userdata_balance = await store.sql_user_balance_single(
            str(ctx.author.id), coin_name, wallet_address, type_coin,
            height, deposit_confirm_depth, SERVER_BOT
        )
        actual_balance = float(userdata_balance['adjust'])

        if amount > max_tip or amount < min_tip:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, transactions cannot be bigger "\
                f"than **{num_format_coin(max_tip, coin_name, coin_decimal, False)} {token_display}** "\
                f"or smaller than **{num_format_coin(min_tip, coin_name, coin_decimal, False)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return
        elif amount > actual_balance:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to do a math tip of "\
                f"**{num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}**."
            await ctx.edit_original_message(content=msg)
            return

        ## add to queue
        if str(ctx.author.id) not in self.bot.tipping_in_progress:
            self.bot.tipping_in_progress[str(ctx.author.id)] = int(time.time())

        equivalent_usd = ""
        total_in_usd = 0.0
        per_unit = None
        if usd_equivalent_enable == 1:
            native_token_name = getattr(getattr(self.bot.coin_list, coin_name), "native_token_name")
            coin_name_for_price = coin_name
            if native_token_name:
                coin_name_for_price = native_token_name
            if coin_name_for_price in self.bot.token_hints:
                id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
            else:
                per_unit = self.bot.coin_paprika_symbol_list[coin_name_for_price]['price_usd']
            if per_unit and per_unit > 0:
                total_in_usd = float(Decimal(amount) * Decimal(per_unit))
                if total_in_usd >= 0.0001:
                    equivalent_usd = " ~ {:,.4f} USD".format(total_in_usd)

        owner_displayname = "{}#{}".format(ctx.author.name, ctx.author.discriminator)
        embed = disnake.Embed(
            title=f"🧮 Math Tip {coin_emoji}{num_format_coin(amount, coin_name, coin_decimal, False)} {token_display} {equivalent_usd}",
            description=eval_string_original, timestamp=datetime.fromtimestamp(int(time.time()) + duration_s))
        embed.add_field(
            name="Answering",
            value="None",
            inline=False
        )
        embed.set_footer(text=f"Math tip by {owner_displayname}")

        answers = [str(result_float), str(wrong_answer_1), str(wrong_answer_2), str(wrong_answer_3)]
        random.shuffle(answers)
        index_answer = answers.index(str(result_float))
        try:
            view = MathButton(ctx, answers, index_answer, duration_s, self.bot.coin_list)
            view.message = await ctx.original_message()
            await store.insert_discord_mathtip(
                coin_name, contract, str(ctx.author.id),
                owner_displayname, str(view.message.id),
                eval_string_original, result_float, wrong_answer_1,
                wrong_answer_2, wrong_answer_3, str(ctx.guild.id),
                str(ctx.channel.id), amount, total_in_usd,
                equivalent_usd, per_unit, coin_decimal,
                int(time.time()) + duration_s, net_name
            )
            await ctx.edit_original_message(content=None, embed=embed, view=view)
        except disnake.errors.Forbidden:
            await ctx.edit_original_message(content="Missing permission! Or failed to send embed message.")
        except Exception:
            traceback.print_exc(file=sys.stdout)
        try:
            del self.bot.tipping_in_progress[str(ctx.author.id)]
        except Exception:
            pass

    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.slash_command(
        dm_permission=False,
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

    @mathtip.autocomplete("token")
    async def mathtip_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]

def setup(bot):
    bot.add_cog(MathTips(bot))
