import aiohttp
import asyncio
import functools
# For hash file in case already have
import hashlib
import os
import os.path
import re
import sys
import time
import traceback
import uuid
from datetime import datetime
from io import BytesIO
import time

import cv2
import disnake
import numpy as np
import store
from Bot import logchanbot, SERVER_BOT, EMOJI_RED_NO, RowButtonRowCloseAnyMessage, EMOJI_INFORMATION
from PIL import Image
from cairosvg import svg2png
from config import config
from disnake.app_commands import Option
from disnake.enums import OptionType
from disnake.ext import commands
# linedraw
from linedraw.linedraw import *
# tb
from tb.tbfun import action as tb_action
from cogs.utils import Utils

class Tb(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.utils = Utils(self.bot)

    async def sql_add_tbfun(
            self,
            user_id: str,
            user_name: str,
            channel_id: str,
            guild_id: str,
            guild_name: str,
            funcmd: str,
            user_server: str = 'DISCORD'
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `discord_tbfun` (`user_id`, `user_name`, `channel_id`, `guild_id`, `guild_name`, 
                              `funcmd`, `time`, `user_server`)
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (
                    user_id, user_name, channel_id, guild_id, guild_name, funcmd, int(time.time()), user_server))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def tb_draw(
            self,
            ctx,
            user_avatar: str
    ):
        try:
            msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing tb command...'
            await ctx.response.send_message(msg)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await ctx.response.send_message(
                f"{EMOJI_INFORMATION} {ctx.author.mention}, failed to execute tb command...", ephemeral=True)
            return
        try:
            timeout = 12
            res_data = None
            async with aiohttp.ClientSession() as session:
                async with session.get(user_avatar, timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        await session.close()

            if res_data:
                hash_object = hashlib.sha256(res_data)
                hex_dig = str(hash_object.hexdigest())
                random_img_name = hex_dig + "_draw"

                random_img_name_svg = config.fun.static_draw_path + random_img_name + ".svg"
                random_img_name_png = config.fun.static_draw_path + random_img_name + ".png"
                draw_link = config.fun.static_draw_link + random_img_name + ".png"
                # if hash exists
                if os.path.exists(random_img_name_png):
                    # send the made file, no need to create new
                    try:
                        e = disnake.Embed(timestamp=datetime.now())
                        e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                        e.set_image(url=draw_link)
                        e.set_footer(text=f"Draw requested by {ctx.author.name}#{ctx.author.discriminator}")
                        await ctx.edit_original_message(content=None, embed=e)
                        await self.sql_add_tbfun(str(ctx.author.id),
                                                 '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                                                 str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'DRAW',
                                                 SERVER_BOT)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    return

                img = Image.open(BytesIO(res_data)).convert("RGBA")

                def async_sketch_image(img, svg, png_out):
                    width = 4000
                    height = 4000
                    line_draw = sketch_image(img, svg)

                    # save from svg to png and will have some transparent
                    svg2png(url=svg, write_to=png_out, output_width=width, output_height=height)

                    # open the saved image
                    png_image = Image.open(png_out)
                    imageBox = png_image.getbbox()
                    # crop transparent
                    cropped = png_image.crop(imageBox)

                    # saved replaced old PNG image
                    cropped.save(png_out)

                partial_img = functools.partial(async_sketch_image, img, random_img_name_svg, random_img_name_png)
                lines = await self.bot.loop.run_in_executor(None, partial_img)
                try:
                    e = disnake.Embed(timestamp=datetime.now())
                    e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                    e.set_image(url=draw_link)
                    e.set_footer(text=f"Draw requested by {ctx.author.name}#{ctx.author.discriminator}")
                    await ctx.edit_original_message(content=None, embed=e)
                    await self.sql_add_tbfun(str(ctx.author.id),
                                             '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                                             str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'DRAW', SERVER_BOT)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            else:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, internal error.'
                await ctx.edit_original_message(content=msg)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def tb_sketchme(
            self,
            ctx,
            user_avatar: str
    ):
        try:
            msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing tb command...'
            await ctx.response.send_message(msg)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await ctx.response.send_message(
                f"{EMOJI_INFORMATION} {ctx.author.mention}, failed to execute tb command...", ephemeral=True)
            return

        def create_line_drawing_image(img):
            kernel = np.array([
                [1, 1, 1, 1, 1],
                [1, 1, 1, 1, 1],
                [1, 1, 1, 1, 1],
                [1, 1, 1, 1, 1],
                [1, 1, 1, 1, 1],
            ], np.uint8)
            img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            img_dilated = cv2.dilate(img_gray, kernel, iterations=1)
            img_diff = cv2.absdiff(img_dilated, img_gray)
            contour = 255 - img_diff
            return contour

        try:
            timeout = 12
            res_data = None
            async with aiohttp.ClientSession() as session:
                async with session.get(user_avatar, timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        await session.close()

            if res_data:
                hash_object = hashlib.sha256(res_data)
                hex_dig = str(hash_object.hexdigest())
                random_img_name = hex_dig + "_sketchme"
                draw_link = config.fun.static_draw_link + random_img_name + ".png"

                random_img_name_png = config.fun.static_draw_path + random_img_name + ".png"
                # if hash exists
                if os.path.exists(random_img_name_png):
                    # send the made file, no need to create new
                    try:
                        e = disnake.Embed(timestamp=datetime.now())
                        e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                        e.set_image(url=draw_link)
                        e.set_footer(text=f"Sketchme requested by {ctx.author.name}#{ctx.author.discriminator}")
                        await ctx.edit_original_message(content=None, embed=e)
                        await self.sql_add_tbfun(str(ctx.author.id),
                                                 '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                                                 str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'SKETCHME',
                                                 SERVER_BOT)
                    except Exception:
                        await logchanbot("tb " +str(traceback.format_exc()))
                    return

                img = np.array(Image.open(BytesIO(res_data)).convert("RGBA"))
                # nparr = np.fromstring(res_data, np.uint8)
                # img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR) # cv2.IMREAD_COLOR in OpenCV 3.1

                partial_contour = functools.partial(create_line_drawing_image, img)
                img_contour = await self.bot.loop.run_in_executor(None, partial_contour)
                if img_contour is None:
                    return
                try:
                    # stuff = done.pop().result()
                    # img_contour = done.pop().result()
                    # full path of image .png
                    cv2.imwrite(random_img_name_png, img_contour)

                    try:
                        e = disnake.Embed(timestamp=datetime.now())
                        e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                        e.set_image(url=draw_link)
                        e.set_footer(text=f"Sketchme requested by {ctx.author.name}#{ctx.author.discriminator}")
                        msg = await ctx.edit_original_message(content=None, embed=e)
                        await self.sql_add_tbfun(str(ctx.author.id),
                                                 '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                                                 str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'SKETCHME',
                                                 SERVER_BOT)
                    except Exception:
                        await logchanbot("tb " +str(traceback.format_exc()))
                except asyncio.TimeoutError:
                    return
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def tb_punch(
            self,
            ctx,
            user1: str,
            user2: str
    ):
        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing tb command...'
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/tb punch", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            action = "PUNCH"
            random_gif_name = config.fun.fun_img_path + str(uuid.uuid4()) + ".gif"
            fun_image = await tb_action(user1, user2, random_gif_name, action, config.tbfun_image.punch_gif)
            if fun_image:
                e = disnake.Embed(timestamp=datetime.now())
                e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                e.set_image(url=config.fun.fun_img_www + os.path.basename(fun_image))
                e.set_footer(text=f"{action} requested by {ctx.author.name}#{ctx.author.discriminator}")
                await ctx.edit_original_message(content=None, embed=e)
                await self.sql_add_tbfun(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                                         str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, action, SERVER_BOT)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def tb_spank(
            self,
            ctx,
            user1: str,
            user2: str
    ):
        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing tb command...'
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/tb spank", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            action = "SPANK"
            random_gif_name = config.fun.fun_img_path + str(uuid.uuid4()) + ".gif"
            fun_image = await tb_action(user1, user2, random_gif_name, action, config.tbfun_image.spank_gif)
            if fun_image:
                e = disnake.Embed(timestamp=datetime.now())
                e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                e.set_image(url=config.fun.fun_img_www + os.path.basename(fun_image))
                e.set_footer(text=f"{action} requested by {ctx.author.name}#{ctx.author.discriminator}")
                await ctx.edit_original_message(content=None, embed=e)
                await self.sql_add_tbfun(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                                         str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, action, SERVER_BOT)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def tb_slap(
            self,
            ctx,
            user1: str,
            user2: str
    ):
        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing tb command...'
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/tb slap", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            action = "SLAP"
            random_gif_name = config.fun.fun_img_path + str(uuid.uuid4()) + ".gif"
            fun_image = await tb_action(user1, user2, random_gif_name, action, config.tbfun_image.slap_gif)
            if fun_image:
                e = disnake.Embed(timestamp=datetime.now())
                e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                e.set_image(url=config.fun.fun_img_www + os.path.basename(fun_image))
                e.set_footer(text=f"{action} requested by {ctx.author.name}#{ctx.author.discriminator}")
                await ctx.edit_original_message(content=None, embed=e)
                await self.sql_add_tbfun(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                                         str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, action, SERVER_BOT)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def tb_praise(
            self,
            ctx,
            user1: str,
            user2: str
    ):
        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing tb command...'
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/tb praise", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            action = "PRAISE"
            random_gif_name = config.fun.fun_img_path + str(uuid.uuid4()) + ".gif"
            fun_image = await tb_action(user1, user2, random_gif_name, action, config.tbfun_image.praise_gif)
            if fun_image:
                e = disnake.Embed(timestamp=datetime.now())
                e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                e.set_image(url=config.fun.fun_img_www + os.path.basename(fun_image))
                e.set_footer(text=f"{action} requested by {ctx.author.name}#{ctx.author.discriminator}")
                await ctx.edit_original_message(content=None, embed=e)
                await self.sql_add_tbfun(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                                         str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, action, SERVER_BOT)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def tb_shoot(
            self,
            ctx,
            user1: str,
            user2: str
    ):
        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing tb command...'
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/tb shoot", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            action = "SHOOT"
            random_gif_name = config.fun.fun_img_path + str(uuid.uuid4()) + ".gif"
            fun_image = await tb_action(user1, user2, random_gif_name, action, config.tbfun_image.shoot_gif)
            if fun_image:
                e = disnake.Embed(timestamp=datetime.now())
                e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                e.set_image(url=config.fun.fun_img_www + os.path.basename(fun_image))
                e.set_footer(text=f"{action} requested by {ctx.author.name}#{ctx.author.discriminator}")
                await ctx.edit_original_message(content=None, embed=e)
                await self.sql_add_tbfun(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                                         str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, action, SERVER_BOT)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def tb_kick(
            self,
            ctx,
            user1: str,
            user2: str
    ):
        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing tb command...'
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/tb kick", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            action = "KICK"
            random_gif_name = config.fun.fun_img_path + str(uuid.uuid4()) + ".gif"
            fun_image = await tb_action(user1, user2, random_gif_name, action, config.tbfun_image.kick_gif)
            if fun_image:
                e = disnake.Embed(timestamp=datetime.now())
                e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                e.set_image(url=config.fun.fun_img_www + os.path.basename(fun_image))
                e.set_footer(text=f"{action} requested by {ctx.author.name}#{ctx.author.discriminator}")
                await ctx.edit_original_message(content=None, embed=e)
                await self.sql_add_tbfun(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                                         str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, action, SERVER_BOT)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def tb_fistbump(
            self,
            ctx,
            user1: str,
            user2: str
    ):
        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing tb command...'
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/tb fistbump", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            action = "FISTBUMP"
            random_gif_name = config.fun.fun_img_path + str(uuid.uuid4()) + ".gif"
            fun_image = await tb_action(user1, user2, random_gif_name, action, config.tbfun_image.fistbump_gif)
            if fun_image:
                e = disnake.Embed(timestamp=datetime.now())
                e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                e.set_image(url=config.fun.fun_img_www + os.path.basename(fun_image))
                e.set_footer(text=f"{action} requested by {ctx.author.name}#{ctx.author.discriminator}")
                await ctx.edit_original_message(content=None, embed=e)
                await self.sql_add_tbfun(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                                         str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, action, SERVER_BOT)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def tb_dance(
            self,
            ctx,
            user1: str,
            user2: str  # Not used
    ):
        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing tb command...'
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/tb dance", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            action = "DANCE"
            random_gif_name = config.fun.fun_img_path + str(uuid.uuid4()) + ".gif"
            fun_image = await tb_action(user1, user2, random_gif_name, action, config.tbfun_image.single_dance_gif)
            if fun_image:
                e = disnake.Embed(timestamp=datetime.now())
                e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                e.set_image(url=config.fun.fun_img_www + os.path.basename(fun_image))
                e.set_footer(text=f"{action} requested by {ctx.author.name}#{ctx.author.discriminator}")
                await ctx.edit_original_message(content=None, embed=e)
                await self.sql_add_tbfun(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                                         str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, action, SERVER_BOT)
        except Exception:
            await logchanbot("tb " +str(traceback.format_exc()))
        return

    async def tb_getemoji(
            self,
            ctx,
            emoji: str
    ):
        msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, executing tb command...'
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, f"/tb getemoji", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        emoji_url = None
        timeout = 12
        try:
            custom_emojis = re.findall(r'<:\w*:\d*>', emoji)
            if custom_emojis and len(custom_emojis) >= 1:
                split_id = custom_emojis[0].split(":")[2]
                link = 'https://cdn.discordapp.com/emojis/' + str(split_id.replace(">", "")) + '.png'
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(link, timeout=timeout) as response:
                            if response.status == 200 or response.status == 201:
                                emoji_url = link
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            if emoji_url is None:
                custom_emojis = re.findall(r'<a:\w*:\d*>', emoji)
                if custom_emojis and len(custom_emojis) >= 1:
                    split_id = custom_emojis[0].split(":")[2]
                    link = 'https://cdn.discordapp.com/emojis/' + str(split_id.replace(">", "")) + '.gif'
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(link, timeout=timeout) as response:
                                if response.status == 200 or response.status == 201:
                                    emoji_url = link
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
            if emoji_url is None:
                msg = f'{ctx.author.mention}, I could not get that emoji image or it is a unicode text and not supported.'
                await ctx.edit_original_message(content=msg)
            else:
                try:
                    await ctx.edit_original_message(content=f'{ctx.author.mention} {emoji_url}',
                                                    view=RowButtonRowCloseAnyMessage())
                except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                    traceback.print_exc(file=sys.stdout)
            return
        except Exception:
            msg = f'{ctx.author.mention}, internal error for getting emoji.'
            await ctx.edit_original_message(content=msg)
            traceback.print_exc(file=sys.stdout)

    @commands.guild_only()
    @commands.slash_command(description="Some fun commands.")
    async def tb(self, ctx):
        pass

    @tb.sub_command(
        usage="tb draw",
        options=[
            Option('member', 'member', OptionType.user, required=False)
        ],
        description="Use TipBot to draw someone's avatar."
    )
    async def draw(
            self,
            ctx,
            member: disnake.Member = None
    ):
        user_avatar = str(ctx.author.display_avatar)
        if member:
            user_avatar = str(member.display_avatar)
        await self.tb_draw(ctx, user_avatar)

    @tb.sub_command(
        usage="tb sketchme",
        options=[
            Option('member', 'member', OptionType.user, required=False)
        ],
        description="Use TipBot to sketch someone's avatar."
    )
    async def sketchme(
            self,
            ctx,
            member: disnake.Member = None
    ):
        user_avatar = str(ctx.author.display_avatar)
        if member:
            user_avatar = str(member.display_avatar)
        await self.tb_sketchme(ctx, user_avatar)

    @tb.sub_command(
        usage="tb spank",
        options=[
            Option('member', 'member', OptionType.user, required=False)
        ],
        description="Use TipBot to spank someone."
    )
    async def spank(
            self,
            ctx,
            member: disnake.Member = None
    ):
        if member is None:
            user1 = str(self.bot.user.display_avatar)
            user2 = str(ctx.author.display_avatar)
        else:
            user1 = str(ctx.author.display_avatar)
            user2 = str(member.display_avatar)
            if member == ctx.author: user1 = str(self.bot.user.display_avatar)
        await self.tb_spank(ctx, user1, user2)

    @tb.sub_command(
        usage="tb punch",
        options=[
            Option('member', 'member', OptionType.user, required=False)
        ],
        description="Use TipBot to punch someone."
    )
    async def punch(
            self,
            ctx,
            member: disnake.Member = None
    ):
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and 'enable_nsfw' in serverinfo and serverinfo['enable_nsfw'] == "NO":
            prefix = serverinfo['prefix']
            return

        if member is None:
            user1 = str(self.bot.user.display_avatar)
            user2 = str(ctx.author.display_avatar)
        else:
            user1 = str(ctx.author.display_avatar)
            user2 = str(member.display_avatar)
            if member == ctx.author: user1 = str(self.bot.user.display_avatar)
        await self.tb_punch(ctx, user1, user2)

    @tb.sub_command(
        usage="tb slap",
        options=[
            Option('member', 'member', OptionType.user, required=False)
        ],
        description="Use TipBot to slap someone."
    )
    async def slap(
            self,
            ctx,
            member: disnake.Member = None
    ):
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and 'enable_nsfw' in serverinfo and serverinfo['enable_nsfw'] == "NO":
            prefix = serverinfo['prefix']
            return

        if member is None:
            user1 = str(self.bot.user.display_avatar)
            user2 = str(ctx.author.display_avatar)
        else:
            user1 = str(ctx.author.display_avatar)
            user2 = str(member.display_avatar)
            if member == ctx.author: user1 = str(self.bot.user.display_avatar)
        await self.tb_slap(ctx, user1, user2)

    @tb.sub_command(
        usage="tb praise",
        options=[
            Option('member', 'member', OptionType.user, required=False)
        ],
        description="Use TipBot to praise someone."
    )
    async def praise(
            self,
            ctx,
            member: disnake.Member = None
    ):
        if member is None:
            user1 = str(self.bot.user.display_avatar)
            user2 = str(ctx.author.display_avatar)
        else:
            user1 = str(ctx.author.display_avatar)
            user2 = str(member.display_avatar)
            if member == ctx.author: user1 = str(self.bot.user.display_avatar)
        await self.tb_praise(ctx, user1, user2)

    @tb.sub_command(
        usage="tb shoot",
        options=[
            Option('member', 'member', OptionType.user, required=False)
        ],
        description="Use TipBot to shoot someone."
    )
    async def shoot(
            self,
            ctx,
            member: disnake.Member = None
    ):
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and 'enable_nsfw' in serverinfo and serverinfo['enable_nsfw'] == "NO":
            prefix = serverinfo['prefix']
            return

        if member is None:
            user1 = str(self.bot.user.display_avatar)
            user2 = str(ctx.author.display_avatar)
        else:
            user1 = str(ctx.author.display_avatar)
            user2 = str(member.display_avatar)
            if member == ctx.author: user1 = str(self.bot.user.display_avatar)
        await self.tb_shoot(ctx, user1, user2)

    @tb.sub_command(
        usage="tb kick",
        options=[
            Option('member', 'member', OptionType.user, required=False)
        ],
        description="Use TipBot to fun kick someone."
    )
    async def kick(
            self,
            ctx,
            member: disnake.Member = None
    ):
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and 'enable_nsfw' in serverinfo and serverinfo['enable_nsfw'] == "NO":
            prefix = serverinfo['prefix']
            return

        if member is None:
            user1 = str(self.bot.user.display_avatar)
            user2 = str(ctx.author.display_avatar)
        else:
            user1 = str(ctx.author.display_avatar)
            user2 = str(member.display_avatar)
            if member == ctx.author: user1 = str(self.bot.user.display_avatar)
        await self.tb_kick(ctx, user1, user2)

    @tb.sub_command(
        usage="tb fistbump",
        options=[
            Option('member', 'member', OptionType.user, required=False)
        ],
        description="Use TipBot to fistbump someone."
    )
    async def fistbump(
            self,
            ctx,
            member: disnake.Member = None
    ):
        if member is None:
            user1 = str(self.bot.user.display_avatar)
            user2 = str(ctx.author.display_avatar)
        else:
            user1 = str(ctx.author.display_avatar)
            user2 = str(member.display_avatar)
            if member == ctx.author: user1 = str(self.bot.user.display_avatar)
        await self.tb_fistbump(ctx, user1, user2)

    @tb.sub_command(
        usage="tb dance",
        description="Bean dance's style."
    )
    async def dance(
            self,
            ctx
    ):
        user1 = str(ctx.author.display_avatar)
        user2 = str(self.bot.user.display_avatar)
        await self.tb_dance(ctx, user1, user2)

    @tb.sub_command(
        usage="tb getemoji <emoji>",
        options=[
            Option('emoji', 'emoji', OptionType.string, required=True)
        ],
        description="Get emoji's url."
    )
    async def getemoji(
            self,
            ctx,
            emoji: str
    ):
        await self.tb_getemoji(ctx, emoji)


def setup(bot):
    bot.add_cog(Tb(bot))
