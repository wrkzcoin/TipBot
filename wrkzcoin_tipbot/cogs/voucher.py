import sys
import time
import traceback
import uuid
from datetime import datetime
from decimal import Decimal
from io import BytesIO

import disnake
import qrcode
import store
from Bot import logchanbot, EMOJI_ERROR, EMOJI_RED_NO, SERVER_BOT, EMOJI_INFORMATION, \
    text_to_num, is_ascii
from PIL import Image, ImageDraw, ImageFont
from cogs.wallet import WalletAPI
from disnake.app_commands import Option
from disnake.enums import OptionType
from disnake.ext import commands
from terminaltables import AsciiTable
from cogs.utils import Utils, num_format_coin


class Voucher(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.botLogChan = None

        # voucher
        self.max_batch = 4
        self.voucher_url = "https://redeem.bot.tips"
        self.coin_logo_path = "./coin_logo/"
        self.path_voucher_create = "./tipbot_voucher/"
        self.path_voucher_defaultimg = "./images/voucher_frame1.png"
        self.max_comment = 32
        self.pathfont = "./fonts/digital-7_(mono).ttf"

    async def sql_voucher_get_setting(self, coin: str):
        coin_name = coin.upper()
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM cn_voucher_settings 
                    WHERE `coin_name`=%s LIMIT 1
                    """
                    await cur.execute(sql, (coin_name,))
                    result = await cur.fetchone()
                    return result
        except Exception:
            await logchanbot("voucher " +str(traceback.format_exc()))
        return None

    async def sql_send_to_voucher(
        self, user_id: str, user_name: str, amount: float, reserved_fee: float, comment: str,
        secret_string: str, voucher_image_name: str, coin: str, coin_decimal: int,
        contract: str, per_unit_usd: float, user_server: str = 'DISCORD'
    ):
        coin_name = coin.upper()
        currentTs = int(time.time())
        tiptype = "VOUCHER"
        guild = "VOUCHER"
        channel = "VOUCHER"
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO cn_voucher (`coin_name`, `user_id`, `user_name`, `amount`, 
                    `decimal`, `reserved_fee`, `date_create`, `comment`, `secret_string`, 
                    `voucher_image_name`, `user_server`) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    await cur.execute(sql, (
                        coin_name, user_id, user_name, amount, coin_decimal, reserved_fee,
                        int(time.time()), comment, secret_string, voucher_image_name, user_server
                    ))
                    # voucher balance
                    data_rows = []
                    # create voucher
                    data_rows.append((coin_name, contract, user_id, "VOUCHER", guild, channel, amount,
                                      float(per_unit_usd) * float(amount), coin_decimal, tiptype, currentTs,
                                      user_server, user_id, coin_name, user_server, -amount, currentTs, "VOUCHER",
                                      coin_name, user_server, amount, currentTs))
                    # fee
                    data_rows.append((coin_name, contract, user_id, "VOUCHER_FEE", guild, channel, reserved_fee,
                                      float(per_unit_usd) * float(reserved_fee), coin_decimal, tiptype, currentTs,
                                      user_server, user_id, coin_name, user_server, -reserved_fee, currentTs,
                                      "VOUCHER_FEE", coin_name, user_server, reserved_fee, currentTs))

                    sql = """ INSERT INTO user_balance_mv 
                              (`token_name`, `contract`, `from_userid`, `to_userid`, `guild_id`, `channel_id`, `real_amount`, `real_amount_usd`, `token_decimal`, `type`, `date`, `user_server`) 
                              VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS DECIMAL(32,8)), CAST(%s AS DECIMAL(32,8)), %s, %s, %s, %s);

                              INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                              VALUES (%s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s) ON DUPLICATE KEY 
                              UPDATE 
                              `balance`=`balance`+VALUES(`balance`), 
                              `update_date`=VALUES(`update_date`);

                              INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                              VALUES (%s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s) ON DUPLICATE KEY 
                              UPDATE 
                              `balance`=`balance`+VALUES(`balance`), 
                              `update_date`=VALUES(`update_date`);
                              """
                    await cur.executemany(sql, data_rows)
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("voucher " +str(traceback.format_exc()))
        return None

    async def sql_voucher_get_user(
        self, user_id: str, user_server: str = 'DISCORD', last: int = 10,
        already_claimed: str = 'YESNO'
    ):
        user_server = user_server.upper()
        already_claimed = already_claimed.upper()
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if already_claimed == 'YESNO':
                        sql = """ SELECT * FROM cn_voucher 
                        WHERE `user_id`=%s AND `user_server`=%s 
                        ORDER BY `date_create` DESC LIMIT %s
                        """
                        await cur.execute(sql, (user_id, user_server, last))
                        result = await cur.fetchall()
                        return result
                    elif already_claimed == 'YES' or already_claimed == 'NO':
                        sql = """ SELECT * FROM cn_voucher 
                        WHERE `user_id`=%s AND `user_server`=%s AND `already_claimed`=%s
                        ORDER BY `date_create` DESC LIMIT %s
                        """
                        await cur.execute(sql, (user_id, user_server, already_claimed, last))
                        result = await cur.fetchall()
                        return result
        except Exception:
            await logchanbot("voucher " +str(traceback.format_exc()))
        return None

    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)

    @commands.slash_command(description="Various voucher's commands.")
    async def voucher(self, ctx):
        pass

    @voucher.sub_command(
        usage="voucher make <amount> <coin> <comment>",
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('coin', 'coin', OptionType.string, required=True),
            Option('comment', 'comment', OptionType.string, required=False)
        ],
        description="Make a voucher and share to other friends."
    )
    async def make(
        self,
        ctx,
        amount: str,
        coin: str,
        comment: str = None
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Bot's checking voucher..."
        await ctx.response.send_message(msg, ephemeral=True)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/voucher make", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            await self.bot_log()
            coin_name = coin.upper()
            # Token name check
            if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
                coin_name = self.bot.coin_alias_names[coin_name]
            if not hasattr(self.bot.coin_list, coin_name):
                msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
                await ctx.edit_original_message(content=msg)
                return
            else:
                if getattr(getattr(self.bot.coin_list, coin_name), "enable_voucher") != 1:
                    msg = f'{ctx.author.mention}, **{coin_name}** voucher is disable for this coin.'
                    await ctx.edit_original_message(content=msg)
                    return
            # End token name check

            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")

            min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
            max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name), "usd_equivalent_enable")
            get_deposit = await self.wallet_api.sql_get_userwallet(
                str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0
            )
            if get_deposit is None:
                get_deposit = await self.wallet_api.sql_register_user(
                    str(ctx.author.id), coin_name, net_name, type_coin,
                    SERVER_BOT, 0, 0
                )

            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']
            elif type_coin in ["XRP"]:
                wallet_address = get_deposit['destination_tag']
            # Check if tx in progress
            if str(ctx.author.id) in self.bot.tipping_in_progress and \
                int(time.time()) - self.bot.tipping_in_progress[str(ctx.author.id)] < 150:
                msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another transaction in progress."
                await ctx.edit_original_message(content=msg)
                return

            height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)

            # Numb voucher
            amount = amount.replace(",", "")
            voucher_numb = 1
            if 'x' in amount.lower() or '*' in amount:
                # This is a batch
                if 'x' in amount.lower():
                    voucher_numb = amount.lower().split("x")[0]
                    voucher_each = amount.lower().split("x")[1]
                elif '*' in amount:
                    voucher_numb = amount.lower().split("*")[0]
                    voucher_each = amount.lower().split("*")[1]
                try:
                    voucher_numb = int(voucher_numb)
                    voucher_each = float(voucher_each)
                    if voucher_numb > self.max_batch:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, too many. Maximum allowed: **{self.max_batch}**'
                        await ctx.edit_original_message(content=msg)
                        return
                except ValueError:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid number or amount to create vouchers.'
                    await ctx.edit_original_message(content=msg)
                    return
            else:
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
                        msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{coin_name}`."
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
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. Try with different method.'
                            await ctx.edit_original_message(content=msg)
                            return
                else:
                    amount = amount.replace(",", "")
                    amount = text_to_num(amount)
                    if amount is None:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
                        await ctx.edit_original_message(content=msg)
                        return
                    voucher_each = float(amount)
                # end of check if amount is all

            total_amount = voucher_numb * voucher_each
            min_voucher_amount = getattr(getattr(self.bot.coin_list, coin_name), "voucher_min")
            max_voucher_amount = getattr(getattr(self.bot.coin_list, coin_name), "voucher_max")
            fee_voucher_amount = getattr(getattr(self.bot.coin_list, coin_name), "real_voucher_fee")
            total_fee_amount = voucher_numb * fee_voucher_amount

            per_unit_usd = 0.0
            if usd_equivalent_enable == 1:
                native_token_name = getattr(getattr(self.bot.coin_list, coin_name), "native_token_name")
                coin_name_for_price = coin_name
                if native_token_name:
                    coin_name_for_price = native_token_name
                if coin_name_for_price in self.bot.token_hints:
                    id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                    per_unit_usd = self.bot.coin_paprika_id_list[id]['price_usd']
                else:
                    per_unit_usd = self.bot.coin_paprika_symbol_list[coin_name_for_price]['price_usd']

            userdata_balance = await store.sql_user_balance_single(
                str(ctx.author.id), coin_name, wallet_address, type_coin,
                height, deposit_confirm_depth, SERVER_BOT
            )
            actual_balance = userdata_balance['adjust']
            if actual_balance <= 0:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please check your **{token_display}** balance.'
                await ctx.edit_original_message(content=msg)
                return

            # If voucher in setting
            voucher_setting = await self.sql_voucher_get_setting(coin_name)
            if isinstance(voucher_setting, dict):
                logo = Image.open(voucher_setting['logo_image_path'])
                img_frame = Image.open(voucher_setting['frame_image_path'])
            else:
                logo = Image.open(self.coin_logo_path + coin_name.lower() + ".png")
                img_frame = Image.open(self.path_voucher_defaultimg)

            if voucher_each < min_voucher_amount or voucher_each > max_voucher_amount:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, transaction cannot be smaller than "\
                    f"{num_format_coin(min_voucher_amount)} {token_display} or bigger than "\
                    f"{num_format_coin(max_voucher_amount)} {token_display}."
                await ctx.edit_original_message(content=msg)
                return

            if actual_balance < total_amount + total_fee_amount:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to create voucher. "\
                    f"A voucher needed amount + fee: {num_format_coin(total_amount + total_fee_amount)} "\
                    f"{token_display}\nHaving: {num_format_coin(actual_balance)} {token_display}."
                await ctx.edit_original_message(content=msg)
                return

            comment_str = ""
            if comment:
                comment_str = comment.strip().replace('\n', ' ').replace('\r', '')

            if len(comment_str) > self.max_comment:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, please limit your comment to max. "\
                    f"**{self.max_comment}** chars."
                await ctx.edit_original_message(content=msg)
                return
            elif not is_ascii(comment_str):
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, unsupported char(s) detected in comment.'
                await ctx.edit_original_message(content=msg)
                return

            # Test if can DM. If failed, returrn
            try:
                tmp_msg = await ctx.author.send(f"{ctx.author.mention}, we are making voucher, hold on...")
            except Exception:
                traceback.print_exc(file=sys.stdout)
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, failed to direct message with you.'
                await ctx.edit_original_message(content=msg)
                return

            voucher_make = None
            # If it is a batch or not
            if voucher_numb > 1:
                for i in range(voucher_numb):
                    try:
                        secret_string = str(uuid.uuid4())
                        unique_filename = str(uuid.uuid4())
                        # loop voucher_numb times
                        # do some QR code
                        qr = qrcode.QRCode(
                            version=1,
                            error_correction=qrcode.constants.ERROR_CORRECT_L,
                            box_size=10,
                            border=2,
                        )
                        qrstring = self.voucher_url + "/claim/" + secret_string  # config
                        qr.add_data(qrstring)
                        qr.make(fit=True)
                        qr_img = qr.make_image(fill_color="black", back_color="white")
                        qr_img = qr_img.resize((280, 280))
                        qr_img = qr_img.convert("RGBA")

                        # Logo
                        try:
                            box = (115, 115, 165, 165)
                            qr_img.crop(box)
                            region = logo
                            region = region.resize((box[2] - box[0], box[3] - box[1]))
                            qr_img.paste(region, box)
                        except Exception:
                            await logchanbot("voucher " +str(traceback.format_exc()))
                        # Image Frame on which we want to paste  
                        img_frame.paste(qr_img, (100, 150))

                        # amount font
                        try:
                            msg = num_format_coin(voucher_each) + coin_name
                            W, H = (1123, 644)
                            draw = ImageDraw.Draw(img_frame)
                            myFont = ImageFont.truetype(self.pathfont, 44)
                            w, h = myFont.getsize(msg)
                            draw.text((250 - w / 2, 275 + 125 + h), msg, fill="black", font=myFont)

                            # Instruction to claim
                            myFont = ImageFont.truetype(self.pathfont, 36)
                            msg_claim = "SCAN TO CLAIM IT!"
                            w, h = myFont.getsize(msg_claim)
                            draw.text((250 - w / 2, 275 + 125 + h + 60), msg_claim, fill="black", font=myFont)

                            # comment part
                            comment_txt = "COMMENT: " + comment_str.upper()
                            myFont = ImageFont.truetype(self.pathfont, 24)
                            w, h = myFont.getsize(comment_txt)
                            draw.text((561 - w / 2, 275 + 125 + h + 120), comment_txt, fill="black", font=myFont)
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot("voucher " +str(traceback.format_exc()))
                        voucher_make = None
                        try:
                            img_frame.save(self.path_voucher_create + unique_filename + ".png")
                            if str(ctx.author.id) not in self.bot.tipping_in_progress:
                                self.bot.tipping_in_progress[str(ctx.author.id)] = int(time.time())
                                try:
                                    voucher_make = await self.sql_send_to_voucher(
                                        str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                                        voucher_each, fee_voucher_amount,
                                        comment_str, secret_string,
                                        unique_filename + ".png", coin_name,
                                        coin_decimal, contract, per_unit_usd,
                                        SERVER_BOT
                                    )
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                                    await logchanbot("voucher " +str(traceback.format_exc()))
                            else:
                                # reject and tell to wait
                                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                                await ctx.edit_original_message(content=msg)
                                return
                            try:
                                del self.bot.tipping_in_progress[str(ctx.author.id)]
                            except Exception:
                                pass
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot("voucher " +str(traceback.format_exc()))

                        if voucher_make:
                            try:
                                await ctx.author.send(
                                    f"New Voucher Link ({i + 1} of {voucher_numb}): {qrstring}\n"
                                    "```"
                                    f"Amount: {num_format_coin(voucher_each)} {coin_name}\n"
                                    f"Voucher Fee (Incl. network fee): {num_format_coin(fee_voucher_amount)} {coin_name}\n"
                                    f"Voucher comment: {comment_str}```"
                                )
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                        else:
                            msg = f'{EMOJI_ERROR} {ctx.author.mention}, error voucher creation!'
                            await ctx.edit_original_message(content=msg)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot("voucher " +str(traceback.format_exc()))
                if voucher_make is not None and hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                    msg = f'{ctx.author.mention}, new vouchers sent to your DM.'
                    await ctx.edit_original_message(content=msg)
                elif voucher_make is not None:
                    msg = f'{ctx.author.mention}, thank you for using our TipBot!'
                    await ctx.edit_original_message(content=msg)
                await tmp_msg.delete()
            elif voucher_numb == 1:
                try:
                    # do some QR code
                    secret_string = str(uuid.uuid4())
                    unique_filename = str(uuid.uuid4())
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=10,
                        border=2,
                    )
                    qrstring = self.voucher_url + "/claim/" + secret_string
                    qr.add_data(qrstring)
                    qr.make(fit=True)
                    qr_img = qr.make_image(fill_color="black", back_color="white")
                    qr_img = qr_img.resize((280, 280))
                    qr_img = qr_img.convert("RGBA")

                    # Logo
                    try:
                        box = (115, 115, 165, 165)
                        qr_img.crop(box)
                        region = logo
                        region = region.resize((box[2] - box[0], box[3] - box[1]))
                        qr_img.paste(region, box)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot("voucher " +str(traceback.format_exc()))
                    # Image Frame on which we want to paste 
                    img_frame.paste(qr_img, (100, 150))

                    # amount font
                    try:
                        msg = num_format_coin(voucher_each) + coin_name
                        W, H = (1123, 644)
                        draw = ImageDraw.Draw(img_frame)
                        myFont = ImageFont.truetype(self.pathfont, 44)
                        # w, h = draw.textsize(msg, font=myFont)
                        w, h = myFont.getsize(msg)
                        # draw.text(((W-w)/2,(H-h)/2), msg, fill="black",font=myFont)
                        draw.text((250 - w / 2, 275 + 125 + h), msg, fill="black", font=myFont)

                        # Instruction to claim
                        myFont = ImageFont.truetype(self.pathfont, 36)
                        msg_claim = "SCAN TO CLAIM IT!"
                        w, h = myFont.getsize(msg_claim)
                        draw.text((250 - w / 2, 275 + 125 + h + 60), msg_claim, fill="black", font=myFont)

                        # comment part
                        comment_txt = "COMMENT: " + comment_str.upper()
                        myFont = ImageFont.truetype(self.pathfont, 24)
                        w, h = myFont.getsize(comment_txt)
                        draw.text((561 - w / 2, 275 + 125 + h + 120), comment_txt, fill="black", font=myFont)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot("voucher " +str(traceback.format_exc()))
                    # Saved in the same relative location 
                    voucher_make = None
                    try:
                        img_frame.save(self.path_voucher_create + unique_filename + ".png")
                        if str(ctx.author.id) not in self.bot.tipping_in_progress:
                            self.bot.tipping_in_progress[str(ctx.author.id)] = int(time.time())
                            try:
                                voucher_make = await self.sql_send_to_voucher(
                                    str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                                    voucher_each, fee_voucher_amount, comment_str,
                                    secret_string, unique_filename + ".png",
                                    coin_name, coin_decimal, contract,
                                    per_unit_usd, SERVER_BOT
                                )
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                                await logchanbot("voucher " +str(traceback.format_exc()))
                        else:
                            # reject and tell to wait
                            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. "\
                                "Please wait it to finish."
                            await ctx.edit_original_message(content=msg)
                            return
                        try:
                            del self.bot.tipping_in_progress[str(ctx.author.id)]
                        except Exception:
                            pass
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot("voucher " +str(traceback.format_exc()))

                    if voucher_make:
                        try:
                            msg = await ctx.author.send(
                                f"New Voucher Link: {qrstring}\n"
                                "```"
                                f"Amount: {num_format_coin(voucher_each)} {coin_name}\n"
                                f"Voucher Fee (Incl. network fee): {num_format_coin(fee_voucher_amount)} {coin_name}\n"
                                f"Voucher comment: {comment_str}```"
                            )
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot("voucher " +str(traceback.format_exc()))
                    else:
                        msg = f'{EMOJI_ERROR} {ctx.author.mention}, error voucher creation!'
                        await ctx.edit_original_message(content=msg)
                    if voucher_make is not None and hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                        msg = f'{ctx.author.mention}, new vouchers sent to your DM.'
                        await ctx.edit_original_message(content=msg)
                    elif voucher_make is not None:
                        msg = f'{ctx.author.mention}, thank you for using our TipBot!'
                        await ctx.edit_original_message(content=msg)
                    await tmp_msg.delete()
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot("voucher " +str(traceback.format_exc()))
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @make.autocomplete("coin")
    async def voucher_make_token_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]

    @voucher.sub_command(
        usage="voucher unclaim",
        description="View list of unclaimed vouchers."
    )
    async def unclaim(
        self,
        ctx
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Bot's checking voucher..."
        await ctx.response.send_message(msg, ephemeral=True)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/voucher unclaim", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        await self.bot_log()
        get_vouchers = await self.sql_voucher_get_user(str(ctx.author.id), SERVER_BOT, 50, 'NO')

        if get_vouchers and len(get_vouchers) >= 25:
            # list them in text
            unclaim = ', '.join([each['secret_string'] for each in get_vouchers])
            await ctx.edit_original_message(content=f'{ctx.author.mention} You have many unclaimed vouchers: {unclaim}')
            return
        elif get_vouchers and len(get_vouchers) > 0:
            table_data = [
                ['Ref Link', 'Amount', 'Claimed?', 'Created']
            ]
            for each in get_vouchers:
                table_data.append([
                    each['secret_string'],
                    num_format_coin(each['amount']) + " " + each['coin_name'], 'YES' if each['already_claimed'] == 'YES' else 'NO',
                    datetime.fromtimestamp(each['date_create']).strftime('%Y-%m-%d')
                ])
            table = AsciiTable(table_data)
            table.padding_left = 1
            table.padding_right = 1
            msg = f'**[ YOUR VOUCHER LIST ]**\n```{table.table}```'
            await ctx.edit_original_message(content=msg)
        else:
            await ctx.edit_original_message(content=f'{ctx.author.mention}, you did not create any voucher yet.')
        return

    @voucher.sub_command(
        usage="voucher getunclaim",
        description="Get a list of unclaimed vouchers as a file."
    )
    async def getunclaim(
        self,
        ctx
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Bot's checking voucher..."
        await ctx.response.send_message(msg, ephemeral=True)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/voucher getunclaim", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        await self.bot_log()
        get_vouchers = await self.sql_voucher_get_user(str(ctx.author.id), SERVER_BOT, 10000, 'NO')
        if get_vouchers and len(get_vouchers) > 0:
            try:
                voucher_url_list = []
                for item in get_vouchers:
                    # check if voucher is enable here
                    if not hasattr(self.bot.coin_list, item['coin_name']):
                        continue
                    is_voucher = getattr(getattr(self.bot.coin_list, item['coin_name']), "enable_voucher")
                    if is_voucher != 1:
                        continue
                    voucher_url_list.append(self.voucher_url + '/claim/' + item['secret_string'])
                if len(voucher_url_list) > 0:
                    voucher_url_list_str = "\n".join(voucher_url_list)
                    combined_vouchers = "Total unclaimed: " + str(len(voucher_url_list)) + "\n\n" + voucher_url_list_str
                    data_file = disnake.File(
                        BytesIO(combined_vouchers.encode()),
                        filename=f"unclaimed_voucher_{str(ctx.author.id)}_{str(int(time.time()))}.csv"
                    )
                    await ctx.edit_original_message(content=None, file=data_file)
                else:
                    await ctx.edit_original_message(content=f"{ctx.author.mention}, you don't have any unclaimed voucher.")
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot("voucher " +str(traceback.format_exc()))
        else:
            await ctx.edit_original_message(content=f"{ctx.author.mention}, you don't have any unclaimed voucher.")

    @voucher.sub_command(
        usage="voucher claim",
        description="View list of claimed vouchers."
    )
    async def claim(
        self,
        ctx
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Bot's checking voucher..."
        await ctx.response.send_message(msg, ephemeral=True)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/voucher claim", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        await self.bot_log()
        get_vouchers = await self.sql_voucher_get_user(str(ctx.author.id), SERVER_BOT, 50, 'YES')

        if get_vouchers and len(get_vouchers) >= 25:
            # list them in text
            claimed = ', '.join([each['secret_string'] for each in get_vouchers])
            await ctx.edit_original_message(content=f'{ctx.author.mention}, you have many claimed vouchers: {claimed}')
            return
        elif get_vouchers and len(get_vouchers) > 0:
            table_data = [
                ['Ref Link', 'Amount', 'Claimed?', 'Created']
            ]
            for each in get_vouchers:
                table_data.append([
                    each['secret_string'],
                    num_format_coin(each['amount']) + " " + each['coin_name'],
                    'YES' if each['already_claimed'] == 'YES' else 'NO',
                    datetime.fromtimestamp(each['date_create']).strftime('%Y-%m-%d')
                ])
            table = AsciiTable(table_data)
            table.padding_left = 1
            table.padding_right = 1
            msg = f'**[ YOUR VOUCHER LIST ]**\n```{table.table}```'
            await ctx.edit_original_message(content=msg)
            return
        else:
            await ctx.edit_original_message(content=f"{ctx.author.mention}, you don't have any claimed voucher.")

    @voucher.sub_command(
        usage="voucher getclaim",
        description="Get a list of claimed vouchers as a file."
    )
    async def getclaim(
        self,
        ctx
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Bot's checking voucher..."
        await ctx.response.send_message(msg, ephemeral=True)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/voucher getclaim", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        await self.bot_log()
        get_vouchers = await self.sql_voucher_get_user(str(ctx.author.id), SERVER_BOT, 10000, 'YES')
        if get_vouchers and len(get_vouchers) > 0:
            try:
                voucher_url_list = []
                for item in get_vouchers:
                    voucher_url_list.append(self.voucher_url + '/claim/' + item['secret_string'])
                voucher_url_list_str = "\n".join(voucher_url_list)
                combined_vouchers = "Total claimed: " + str(len(voucher_url_list)) + "\n\n" + voucher_url_list_str
                data_file = disnake.File(BytesIO(combined_vouchers.encode()),
                                         filename=f"claimed_voucher_{str(ctx.author.id)}_{str(int(time.time()))}.csv")
                await ctx.edit_original_message(content=None, file=data_file)
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot("voucher " +str(traceback.format_exc()))
        else:
            await ctx.edit_original_message(content=f'{ctx.author.mention}, you did not create any voucher yet.')
        return

    @voucher.sub_command(
        usage="voucher listcoins",
        description="List coins/tokens supported /voucher"
    )
    async def listcoins(
        self,
        ctx
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, Bot's checking voucher..."
        await ctx.response.send_message(msg, ephemeral=True)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/voucher listcoins", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        await self.bot_log()
        if self.bot.coin_name_list and len(self.bot.coin_name_list) > 0:
            voucher_coins = []
            for coin_name in self.bot.coin_name_list:
                if getattr(getattr(self.bot.coin_list, coin_name), "enable_voucher") == 1:
                    voucher_coins.append(coin_name)
            coin_list_names = ", ".join(voucher_coins)
            if len(voucher_coins) > 0:
                await ctx.edit_original_message(
                    content=f'{ctx.author.mention}, list of supported coins/tokens for /voucher:```{coin_list_names}```')
            else:
                await ctx.edit_original_message(content=f'{ctx.author.mention}, please check again later. I got none now.')
        else:
            await ctx.edit_original_message(content=f'{ctx.author.mention}, please check again later. I got none now.')


def setup(bot):
    bot.add_cog(Voucher(bot))
