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
from Bot import logchanbot, EMOJI_ERROR, EMOJI_RED_NO, SERVER_BOT, num_format_coin, text_to_num, is_ascii
from PIL import Image, ImageDraw, ImageFont
from cogs.wallet import WalletAPI
from config import config
from disnake.app_commands import Option
from disnake.enums import OptionType
from disnake.ext import commands
from terminaltables import AsciiTable


class Voucher(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
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
                    sql = """ SELECT * FROM cn_voucher_settings WHERE `coin_name`=%s LIMIT 1 """
                    await cur.execute(sql, (coin_name,))
                    result = await cur.fetchone()
                    return result
        except Exception:
            await logchanbot("voucher " +str(traceback.format_exc()))
        return None

    async def sql_send_to_voucher(self, user_id: str, user_name: str, amount: float, reserved_fee: float, comment: str,
                                  secret_string: str, voucher_image_name: str, coin: str, coin_decimal: int,
                                  contract: str, per_unit_usd: float, user_server: str = 'DISCORD'):
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
                              `decimal`, `reserved_fee`, `date_create`, `comment`, `secret_string`, `voucher_image_name`, `user_server`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (coin_name, user_id, user_name, amount, coin_decimal, reserved_fee,
                                            int(time.time()), comment, secret_string, voucher_image_name, user_server))
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

    async def sql_voucher_get_user(self, user_id: str, user_server: str = 'DISCORD', last: int = 10,
                                   already_claimed: str = 'YESNO'):
        user_server = user_server.upper()
        already_claimed = already_claimed.upper()
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if already_claimed == 'YESNO':
                        sql = """ SELECT * FROM cn_voucher WHERE `user_id`=%s AND `user_server`=%s 
                                  ORDER BY `date_create` DESC LIMIT """ + str(last) + """ """
                        await cur.execute(sql, (user_id, user_server,))
                        result = await cur.fetchall()
                        return result
                    elif already_claimed == 'YES' or already_claimed == 'NO':
                        sql = """ SELECT * FROM cn_voucher WHERE `user_id`=%s AND `user_server`=%s AND `already_claimed`=%s
                                  ORDER BY `date_create` DESC LIMIT """ + str(last) + """ """
                        await cur.execute(sql, (user_id, user_server, already_claimed))
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
        await self.bot_log()
        coin_name = coin.upper()
        # Token name check
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
            await ctx.response.send_message(msg)
            return
        else:
            if getattr(getattr(self.bot.coin_list, coin_name), "enable_voucher") != 1:
                msg = f'{ctx.author.mention}, **{coin_name}** voucher is disable for this coin.'
                await ctx.response.send_message(msg)
                return
        # End token name check

        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
        token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")

        MinTip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
        MaxTip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
        usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name), "usd_equivalent_enable")
        get_deposit = await self.wallet_api.sql_get_userwallet(str(ctx.author.id), coin_name, net_name, type_coin,
                                                               SERVER_BOT, 0)
        if get_deposit is None:
            get_deposit = await self.wallet_api.sql_register_user(str(ctx.author.id), coin_name, net_name, type_coin,
                                                                  SERVER_BOT, 0, 0)

        wallet_address = get_deposit['balance_wallet_address']
        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
            wallet_address = get_deposit['paymentid']
        elif type_coin in ["XRP"]:
            wallet_address = get_deposit['destination_tag']
        # Check if tx in progress
        if ctx.author.id in self.bot.TX_IN_PROCESS:
            msg = f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.'
            await ctx.response.send_message(msg)
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
                    await ctx.response.send_message(msg)
                    return
            except ValueError:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid number or amount to create vouchers.'
                await ctx.response.send_message(msg, ephemeral=False)
                return
        else:
            # check if amount is all
            all_amount = False
            if not amount.isdigit() and amount.upper() == "ALL":
                all_amount = True
                userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), coin_name, wallet_address,
                                                                       type_coin, height, deposit_confirm_depth,
                                                                       SERVER_BOT)
                amount = float(userdata_balance['adjust'])
            # If $ is in amount, let's convert to coin/token
            elif "$" in amount[-1] or "$" in amount[0]:  # last is $
                # Check if conversion is allowed for this coin.
                amount = amount.replace(",", "").replace("$", "")
                if usd_equivalent_enable == 0:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{coin_name}`."
                    await ctx.response.send_message(msg)
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
                        await ctx.response.send_message(msg)
                        return
            else:
                amount = amount.replace(",", "")
                amount = text_to_num(amount)
                if amount is None:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount.'
                    await ctx.response.send_message(msg)
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

        userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), coin_name, wallet_address, type_coin,
                                                               height, deposit_confirm_depth, SERVER_BOT)
        actual_balance = userdata_balance['adjust']
        if actual_balance <= 0:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please check your **{token_display}** balance.'
            await ctx.response.send_message(msg)
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
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, transaction cannot be smaller than {num_format_coin(min_voucher_amount, coin_name, coin_decimal, False)} {token_display} or bigger than {num_format_coin(max_voucher_amount, coin_name, coin_decimal, False)} {token_display}.'
            await ctx.response.send_message(msg)
            return

        if actual_balance < total_amount + total_fee_amount:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to create voucher.A voucher needed amount + fee: {num_format_coin(total_amount + total_fee_amount, coin_name)} {token_display}\nHaving: {num_format_coin(actual_balance, coin_name, coin_decimal, False)} {token_display}.'
            await ctx.response.send_message(msg)
            return

        comment_str = ""
        if comment:
            comment_str = comment.strip().replace('\n', ' ').replace('\r', '')

        if len(comment_str) > self.max_comment:
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please limit your comment to max. **{self.max_comment}** chars.'
            await ctx.response.send_message(msg)
            return
        elif not is_ascii(comment_str):
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, unsupported char(s) detected in comment.'
            await ctx.response.send_message(msg)
            return

        # Test if can DM. If failed, returrn
        try:
            tmp_msg = await ctx.author.send(f"{ctx.author.mention}, we are making voucher, hold on...")
        except Exception:
            traceback.print_exc(file=sys.stdout)
            msg = f'{EMOJI_RED_NO} {ctx.author.mention}, failed to direct message with you.'
            await ctx.response.send_message(msg)
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
                        msg = num_format_coin(voucher_each, coin_name, coin_decimal, False) + coin_name
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
                        if ctx.author.id not in self.bot.TX_IN_PROCESS:
                            self.bot.TX_IN_PROCESS.append(ctx.author.id)
                            try:
                                voucher_make = await self.sql_send_to_voucher(str(ctx.author.id),
                                                                              '{}#{}'.format(ctx.author.name,
                                                                                             ctx.author.discriminator),
                                                                              voucher_each, fee_voucher_amount,
                                                                              comment_str, secret_string,
                                                                              unique_filename + ".png", coin_name,
                                                                              coin_decimal, contract, per_unit_usd,
                                                                              SERVER_BOT)
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                                await logchanbot("voucher " +str(traceback.format_exc()))
                            self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                        else:
                            # reject and tell to wait
                            msg = f'{EMOJI_RED_NO} {ctx.author.mention} You have another tx in process. Please wait it to finish.'
                            await ctx.response.send_message(msg)
                            return
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot("voucher " +str(traceback.format_exc()))

                    if voucher_make:
                        try:
                            await ctx.author.send(f'New Voucher Link ({i + 1} of {voucher_numb}): {qrstring}\n'
                                                  '```'
                                                  f'Amount: {num_format_coin(voucher_each, coin_name, coin_decimal, False)} {coin_name}\n'
                                                  f'Voucher Fee (Incl. network fee): {num_format_coin(fee_voucher_amount, coin_name, coin_decimal, False)} {coin_name}\n'
                                                  f'Voucher comment: {comment_str}```')
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                    else:
                        msg = f'{EMOJI_ERROR} {ctx.author.mention}, error voucher creation!'
                        await ctx.response.send_message(msg)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot("voucher " +str(traceback.format_exc()))
            if voucher_make is not None and hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                msg = f'{ctx.author.mention}, new vouchers sent to your DM.'
                await ctx.response.send_message(msg)
            elif voucher_make is not None:
                msg = f'{ctx.author.mention}, thank you for using our TipBot!'
                await ctx.response.send_message(msg)
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
                    msg = str(num_format_coin(voucher_each, coin_name, coin_decimal, False)) + coin_name
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
                    if ctx.author.id not in self.bot.TX_IN_PROCESS:
                        self.bot.TX_IN_PROCESS.append(ctx.author.id)
                        try:
                            voucher_make = await self.sql_send_to_voucher(str(ctx.author.id),
                                                                          '{}#{}'.format(ctx.author.name,
                                                                                         ctx.author.discriminator),
                                                                          voucher_each, fee_voucher_amount, comment_str,
                                                                          secret_string, unique_filename + ".png",
                                                                          coin_name, coin_decimal, contract,
                                                                          per_unit_usd, SERVER_BOT)
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot("voucher " +str(traceback.format_exc()))
                        self.bot.TX_IN_PROCESS.remove(ctx.author.id)
                    else:
                        # reject and tell to wait
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, you have another tx in process. Please wait it to finish.'
                        await ctx.response.send_message(msg)
                        return
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot("voucher " +str(traceback.format_exc()))

                if voucher_make:
                    try:
                        msg = await ctx.author.send(f'New Voucher Link: {qrstring}\n'
                                                    '```'
                                                    f'Amount: {num_format_coin(voucher_each, coin_name, coin_decimal, False)} {coin_name}\n'
                                                    f'Voucher Fee (Incl. network fee): {num_format_coin(fee_voucher_amount, coin_name, coin_decimal, False)} {coin_name}\n'
                                                    f'Voucher comment: {comment_str}```')
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot("voucher " +str(traceback.format_exc()))
                else:
                    msg = f'{EMOJI_ERROR} {ctx.author.mention}, error voucher creation!'
                    await ctx.response.send_message(msg)
                if voucher_make is not None and hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                    msg = f'{ctx.author.mention}, new vouchers sent to your DM.'
                    await ctx.response.send_message(msg)
                elif voucher_make is not None:
                    msg = f'{ctx.author.mention}, thank you for using our TipBot!'
                    await ctx.response.send_message(msg)
                await tmp_msg.delete()
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot("voucher " +str(traceback.format_exc()))

    @voucher.sub_command(
        usage="voucher unclaim",
        description="View list of unclaimed vouchers."
    )
    async def unclaim(
            self,
            ctx
    ):
        await self.bot_log()
        get_vouchers = await self.sql_voucher_get_user(str(ctx.author.id), SERVER_BOT, 50, 'NO')

        if get_vouchers and len(get_vouchers) >= 25:
            # list them in text
            unclaim = ', '.join([each['secret_string'] for each in get_vouchers])
            await ctx.response.send_message(f'{ctx.author.mention} You have many unclaimed vouchers: {unclaim}',
                                            ephemeral=True)
            return
        elif get_vouchers and len(get_vouchers) > 0:
            table_data = [
                ['Ref Link', 'Amount', 'Claimed?', 'Created']
            ]
            for each in get_vouchers:
                coin_decimal = getattr(getattr(self.bot.coin_list, each['coin_name']), "decimal")
                table_data.append([each['secret_string'],
                                   num_format_coin(each['amount'], each['coin_name'], coin_decimal, False) + " " + each[
                                       'coin_name'], 'YES' if each['already_claimed'] == 'YES' else 'NO',
                                   datetime.fromtimestamp(each['date_create']).strftime('%Y-%m-%d')])
            table = AsciiTable(table_data)
            table.padding_left = 1
            table.padding_right = 1
            msg = f'**[ YOUR VOUCHER LIST ]**\n```{table.table}```'
            await ctx.response.send_message(msg)
        else:
            await ctx.response.send_message(f'{ctx.author.mention}, you did not create any voucher yet.')
        return

    @voucher.sub_command(
        usage="voucher getunclaim",
        description="Get a list of unclaimed vouchers as a file."
    )
    async def getunclaim(
            self,
            ctx
    ):
        await self.bot_log()
        get_vouchers = await self.sql_voucher_get_user(str(ctx.author.id), SERVER_BOT, 10000, 'NO')
        if get_vouchers and len(get_vouchers) > 0:
            try:
                voucher_url_list = []
                for item in get_vouchers:
                    voucher_url_list.append(self.voucher_url + '/claim/' + item['secret_string'])
                voucher_url_list_str = "\n".join(voucher_url_list)
                combined_vouchers = "Total unclaimed: " + str(len(voucher_url_list)) + "\n\n" + voucher_url_list_str
                data_file = disnake.File(BytesIO(combined_vouchers.encode()),
                                         filename=f"unclaimed_voucher_{str(ctx.author.id)}_{str(int(time.time()))}.csv")
                await ctx.response.send_message(file=data_file, ephemeral=True)
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot("voucher " +str(traceback.format_exc()))
        else:
            await ctx.response.send_message(f'{ctx.author.mention}, you did not create any voucher yet.')
        return

    @voucher.sub_command(
        usage="voucher claim",
        description="View list of claimed vouchers."
    )
    async def claim(
            self,
            ctx
    ):
        await self.bot_log()
        get_vouchers = await self.sql_voucher_get_user(str(ctx.author.id), SERVER_BOT, 50, 'YES')

        if get_vouchers and len(get_vouchers) >= 25:
            # list them in text
            claimed = ', '.join([each['secret_string'] for each in get_vouchers])
            await ctx.response.send_message(f'{ctx.author.mention}, you have many claimed vouchers: {claimed}',
                                            ephemeral=True)
            return
        elif get_vouchers and len(get_vouchers) > 0:
            table_data = [
                ['Ref Link', 'Amount', 'Claimed?', 'Created']
            ]
            for each in get_vouchers:
                coin_decimal = getattr(getattr(self.bot.coin_list, each['coin_name']), "decimal")
                table_data.append([each['secret_string'],
                                   num_format_coin(each['amount'], each['coin_name'], coin_decimal, False) + " " + each[
                                       'coin_name'], 'YES' if each['already_claimed'] == 'YES' else 'NO',
                                   datetime.fromtimestamp(each['date_create']).strftime('%Y-%m-%d')])
            table = AsciiTable(table_data)
            table.padding_left = 1
            table.padding_right = 1
            msg = f'**[ YOUR VOUCHER LIST ]**\n```{table.table}```'
            await ctx.response.send_message(msg)
            return
        else:
            await ctx.response.send_message(f'{ctx.author.mention}, you did not create any voucher yet.')
        return

    @voucher.sub_command(
        usage="voucher getclaim",
        description="Get a list of claimed vouchers as a file."
    )
    async def getclaim(
            self,
            ctx
    ):
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
                await ctx.response.send_message(file=data_file, ephemeral=True)
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot("voucher " +str(traceback.format_exc()))
        else:
            await ctx.response.send_message(f'{ctx.author.mention}, you did not create any voucher yet.')
        return

    @voucher.sub_command(
        usage="voucher listcoins",
        description="List coins/tokens supported /voucher"
    )
    async def listcoins(
            self,
            ctx
    ):
        await self.bot_log()
        if self.bot.coin_name_list and len(self.bot.coin_name_list) > 0:
            voucher_coins = []
            for coin_name in self.bot.coin_name_list:
                if getattr(getattr(self.bot.coin_list, coin_name), "enable_voucher") == 1:
                    voucher_coins.append(coin_name)
            coin_list_names = ", ".join(voucher_coins)
            if len(voucher_coins) > 0:
                await ctx.response.send_message(
                    f'{ctx.author.mention}, list of supported coins/tokens for /voucher:```{coin_list_names}```')
            else:
                await ctx.response.send_message(f'{ctx.author.mention}, please check again later. I got none now.')
        else:
            await ctx.response.send_message(f'{ctx.author.mention}, please check again later. I got none now.')


def setup(bot):
    bot.add_cog(Voucher(bot))
