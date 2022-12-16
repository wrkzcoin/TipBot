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
import imageio
import cv2
import pygame
from pyvirtualdisplay import Display

import store
from Bot import logchanbot, SERVER_BOT, EMOJI_RED_NO, RowButtonRowCloseAnyMessage, EMOJI_INFORMATION
from PIL import ImageDraw, Image, ImageFilter
from cairosvg import svg2png
from disnake.app_commands import Option
from disnake.enums import OptionType
from disnake.ext import commands
# linedraw
from linedraw.linedraw import *
# tb
from tb.tbfun import action as tb_action
from cogs.utils import Utils

if not hasattr(Image, 'Resampling'):  # Pillow<9.0
    Image.Resampling = Image

# Thanks to: https://github.com/tdrmk/pygame_recorder
class ScreenRecorder:
    def __init__(self, fps, output, interval: int=3):
        self.list_pngs = []
        self.fps = fps
        self.output = output
        self.interval = interval

    def capture_frame(self, surf):
        # transform the pixels to the format used by open-cv
        pixels = cv2.rotate(pygame.surfarray.pixels3d(surf), cv2.ROTATE_90_CLOCKWISE)
        pixels = cv2.flip(pixels, 1)
        # pixels = cv2.cvtColor(pixels, cv2.COLOR_RGB2BGR)

        # write the frame
        self.list_pngs.append(pixels)
    
    def total_frames(self):
        return self.list_pngs

    def create_gif(self):
        images = []
        i = 0
        for each_png in self.list_pngs:
            if i > 0 and  i % self.interval == 0:
                images.append(each_png)
            i += 1
        try:
            imageio.mimsave(self.output, images, fps=self.fps)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

# Thanks to: https://github.com/RasPiPkr/fireworks/
def start_firework(in_image, out_path: str, tmp_image: str, width: int, height: int, screen_size):
    os.environ['DISPLAY'] = choice([f":{str(i)}" for i in range(300, 400)])
    display = Display(visible=0, size=screen_size)
    display.start()

    pygame.init()

    screen = pygame.display.set_mode((width, height))

    pygame.display.set_caption('Fireworks') # Window title
    clock = pygame.time.Clock()
    fps = 120 # Frames per second

    # RGB variables for rocket etc.
    white = (255, 255, 255)
    yellow = (255, 255, 0)
    black = (0, 0, 0)

    stopDisplay = 1 # How many fireworks to be used, if missing any check in kaBoom function.
    rocketSize = 5 # Pixel size of rocket head
    tail = 7 # how many pixels trailing from the rocket head
    recorder = ScreenRecorder(fps, out_path, 4)

    def crop_center(pil_img, crop_width, crop_height):
        img_width, img_height = pil_img.size
        return pil_img.crop(((img_width - crop_width) // 2,
                             (img_height - crop_height) // 2,
                             (img_width + crop_width) // 2,
                             (img_height + crop_height) // 2))

    def crop_max_square(pil_img):
        return crop_center(pil_img, min(pil_img.size), min(pil_img.size))

    def mask_circle_transparent(pil_img, blur_radius, offset=0):
        offset = blur_radius * 2 + offset
        mask = Image.new("L", pil_img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((offset, offset, pil_img.size[0] - offset, pil_img.size[1] - offset), fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(blur_radius))

        result = pil_img.copy()
        result.putalpha(mask)

        return result

    def rocket(rocketSize, litRocket):
        i = 0
        for xandy in litRocket:
            if i % 2 == 0:
                pygame.draw.rect(screen, yellow, [xandy[0], xandy[1], rocketSize, rocketSize])
            else:
                pygame.draw.rect(screen, white, [xandy[0], xandy[1], rocketSize, rocketSize])
            i += 1

    def pic(file, x, y, newWidth, newHeight, fade, explode):
        if newWidth >= explode: # Starting picture size for picture to explode.
            for i in range(fade): # How many times to explode picture per frame of explosions.
                randX = randint(0, leedsW - 5) # X position to make transparent.
                randY = randint(0, leedsH - 5) # Y position to make transparent.
                leedsData.rectangle((randX, randY, randX + 5, randY + 5), fill=(0, 0, 0, 0)) # Transparent random pixel
            leeds.save(file) # Saves the temporary picture.
        picFile = pygame.image.load(file) # Pygame loads the saved picture
        newMe = pygame.transform.scale(picFile, (newWidth, newHeight)) # Pygame scales the picture
        screen.blit(newMe, ((x - (newMe.get_width() / 2), (y - (newMe.get_height() / 2))))) # Displays image

    def kaBoom(goes, rocketX, rocketY):
        global leedsW; global leedsH; global leedsData; global leeds
        if goes == 1: # Starting set picture of display
            totalSize = 600 # Total size picture will grow to in exploding.
            fade = 100 # How many times to break up picture per frame of explosion.
            explode = 100 # Starting picture size for picture to explode.
        elif goes == 8: # Could have specific picture in a set point.
            totalSize = 600; fade = 100; explode = 50 # Settings on one line for how to run.
        else:
            totalSize = 300; fade = 200; explode = 10 # Settings on one line for how to run.

        im_square = crop_max_square(in_image).resize((300, 300), Image.Resampling.LANCZOS)
        im_thumb = mask_circle_transparent(im_square, 4)
        im_thumb.save(tmp_image)

        leeds = Image.open(tmp_image) # PIL Imaging opens up a fresh random picture.
        leeds.convert('RGBA') # If not RGBA already

        leedsW, leedsH = leeds.size # Gets picture size
        leedsData = ImageDraw.Draw(leeds) # PIL ImageDraw used to manipulate the explosion
        newWidth = 1 # Picture starting width
        newHeight = 1 # Picture starting height
        while newWidth <= totalSize: # As image is square only checks width
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:                    
                    if event.key == pygame.K_q:
                        pygame.quit()
                        sys.exit()
            screen.fill(black) # Clears background or would leave a trail of picture growing
            if newWidth >= explode:
                rocketY += 1; newWidth += 5; newHeight += 5;
            pic(tmp_image, rocketX, rocketY, newWidth, newHeight, fade, explode)
            pygame.display.update()
            recorder.capture_frame(screen)
            newWidth += 5; newHeight += 5 # Increments width and height so increase size.

    def gameLoop():
        rocketX = int(width /2) # Starting X point for rocket setting off point.
        rocketY = height - 50 # Starting Y point for rocket setting off point.
        yChange = 3 # Pixels for rocket to climb per frame
        litRocket = [] # List for trailing X and Y positions for rocket tail.
        rocketLength = 1

        goes = 1 # Variable to utilize having specific pictures in the firework display.
        while True:
            xChange = choice([-1, 0, 1]) # Makes rocket go left right slightly whilst going up.
            rocketX += xChange
            rocketY -= yChange
            screen.fill(black)
            rocketHead = []
            rocketHead.append(rocketX)
            rocketHead.append(rocketY)
            litRocket.append(rocketHead)
            for event in pygame.event.get(): # Pygame events
                if event.type == pygame.QUIT: # Closing of window
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q: # Waiting for q key to quit
                        pygame.quit()
                        sys.exit()
            if len(litRocket) == tail: # Keeps the tail at a constant length or it would leave a trail.
                del litRocket[0]
            if rocketY <= 180: # 180 being the Y coordinate for when to explode
                kaBoom(goes, rocketX, rocketY)
                rocketX = int(width /2) # Resets rocket firing X position
                rocketY = height - 100 # Resets rocket firing Y position
                litRocket.clear() # Clears the rocket tail list so it sets off creating a new tail.
                goes += 1 # Goes + 1 for use of set display patterns
            elif goes == stopDisplay + 1: # + 1 so your last firework in patter set in kaBoom will happen.
                pygame.quit()
                try:
                    recorder.create_gif() # smaller, will be faster
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                break
            else:
                rocket(rocketSize, litRocket)
            pygame.display.update()
            # Capture the frame
            recorder.capture_frame(screen)
            clock.tick(fps)

    gameLoop()
    display.stop()


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
                    sql = """ INSERT INTO `discord_tbfun` 
                    (`user_id`, `user_name`, `channel_id`, `guild_id`, `guild_name`, `funcmd`, `time`, `user_server`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """
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

                random_img_name_svg = self.bot.config['fun']['static_draw_path'] + random_img_name + ".svg"
                random_img_name_png = self.bot.config['fun']['static_draw_path'] + random_img_name + ".png"
                draw_link = self.bot.config['fun']['static_draw_link'] + random_img_name + ".png"
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
                draw_link = self.bot.config['fun']['static_draw_link'] + random_img_name + ".png"
                random_img_name_png = self.bot.config['fun']['static_draw_path'] + random_img_name + ".png"
                # if hash exists
                if os.path.exists(random_img_name_png):
                    # send the made file, no need to create new
                    try:
                        e = disnake.Embed(timestamp=datetime.now())
                        e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                        e.set_image(url=draw_link)
                        e.set_footer(text=f"Sketchme requested by {ctx.author.name}#{ctx.author.discriminator}")
                        await ctx.edit_original_message(content=None, embed=e)
                        await self.sql_add_tbfun(
                            str(ctx.author.id),
                            '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                            str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'SKETCHME',
                            SERVER_BOT
                        )
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
                        await self.sql_add_tbfun(
                            str(ctx.author.id),
                            '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                            str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'SKETCHME',
                            SERVER_BOT
                        )
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
            random_gif_name = self.bot.config['fun']['fun_img_path'] + str(uuid.uuid4()) + ".gif"
            fun_image = await tb_action(user1, user2, random_gif_name, action, self.bot.config['tbfun_image']['punch_gif'])
            if fun_image:
                e = disnake.Embed(timestamp=datetime.now())
                e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                e.set_image(url=self.bot.config['fun']['fun_img_www'] + os.path.basename(fun_image))
                e.set_footer(text=f"{action} requested by {ctx.author.name}#{ctx.author.discriminator}")
                await ctx.edit_original_message(content=None, embed=e)
                await self.sql_add_tbfun(
                    str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                    str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, action, SERVER_BOT
                )
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
            random_gif_name = self.bot.config['fun']['fun_img_path'] + str(uuid.uuid4()) + ".gif"
            fun_image = await tb_action(user1, user2, random_gif_name, action, self.bot.config['tbfun_image']['spank_gif'])
            if fun_image:
                e = disnake.Embed(timestamp=datetime.now())
                e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                e.set_image(url=self.bot.config['fun']['fun_img_www'] + os.path.basename(fun_image))
                e.set_footer(text=f"{action} requested by {ctx.author.name}#{ctx.author.discriminator}")
                await ctx.edit_original_message(content=None, embed=e)
                await self.sql_add_tbfun(
                    str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                    str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, action, SERVER_BOT
                )
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
            random_gif_name = self.bot.config['fun']['fun_img_path'] + str(uuid.uuid4()) + ".gif"
            fun_image = await tb_action(user1, user2, random_gif_name, action, self.bot.config['tbfun_image']['slap_gif'])
            if fun_image:
                e = disnake.Embed(timestamp=datetime.now())
                e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                e.set_image(url=self.bot.config['fun']['fun_img_www'] + os.path.basename(fun_image))
                e.set_footer(text=f"{action} requested by {ctx.author.name}#{ctx.author.discriminator}")
                await ctx.edit_original_message(content=None, embed=e)
                await self.sql_add_tbfun(
                    str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                    str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, action, SERVER_BOT
                )
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
            random_gif_name = self.bot.config['fun']['fun_img_path'] + str(uuid.uuid4()) + ".gif"
            fun_image = await tb_action(user1, user2, random_gif_name, action, self.bot.config['tbfun_image']['praise_gif'])
            if fun_image:
                e = disnake.Embed(timestamp=datetime.now())
                e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                e.set_image(url=self.bot.config['fun']['fun_img_www'] + os.path.basename(fun_image))
                e.set_footer(text=f"{action} requested by {ctx.author.name}#{ctx.author.discriminator}")
                await ctx.edit_original_message(content=None, embed=e)
                await self.sql_add_tbfun(
                    str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                    str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, action, SERVER_BOT
                )
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
            random_gif_name = self.bot.config['fun']['fun_img_path'] + str(uuid.uuid4()) + ".gif"
            fun_image = await tb_action(user1, user2, random_gif_name, action, self.bot.config['tbfun_image']['shoot_gif'])
            if fun_image:
                e = disnake.Embed(timestamp=datetime.now())
                e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                e.set_image(url=self.bot.config['fun']['fun_img_www'] + os.path.basename(fun_image))
                e.set_footer(text=f"{action} requested by {ctx.author.name}#{ctx.author.discriminator}")
                await ctx.edit_original_message(content=None, embed=e)
                await self.sql_add_tbfun(
                    str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                    str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, action, SERVER_BOT
                )
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
            random_gif_name = self.bot.config['fun']['fun_img_path'] + str(uuid.uuid4()) + ".gif"
            fun_image = await tb_action(user1, user2, random_gif_name, action, self.bot.config['tbfun_image']['kick_gif'])
            if fun_image:
                e = disnake.Embed(timestamp=datetime.now())
                e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                e.set_image(url=self.bot.config['fun']['fun_img_www'] + os.path.basename(fun_image))
                e.set_footer(text=f"{action} requested by {ctx.author.name}#{ctx.author.discriminator}")
                await ctx.edit_original_message(content=None, embed=e)
                await self.sql_add_tbfun(
                    str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                    str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, action, SERVER_BOT
                )
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
            random_gif_name = self.bot.config['fun']['fun_img_path'] + str(uuid.uuid4()) + ".gif"
            fun_image = await tb_action(user1, user2, random_gif_name, action, self.bot.config['tbfun_image']['fistbump_gif'])
            if fun_image:
                e = disnake.Embed(timestamp=datetime.now())
                e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                e.set_image(url=self.bot.config['fun']['fun_img_www'] + os.path.basename(fun_image))
                e.set_footer(text=f"{action} requested by {ctx.author.name}#{ctx.author.discriminator}")
                await ctx.edit_original_message(content=None, embed=e)
                await self.sql_add_tbfun(
                    str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                    str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, action, SERVER_BOT
                )
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
            random_gif_name = self.bot.config['fun']['fun_img_path'] + str(uuid.uuid4()) + ".gif"
            fun_image = await tb_action(user1, user2, random_gif_name, action, self.bot.config['tbfun_image']['single_dance_gif'])
            if fun_image:
                e = disnake.Embed(timestamp=datetime.now())
                e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                e.set_image(url=self.bot.config['fun']['fun_img_www'] + os.path.basename(fun_image))
                e.set_footer(text=f"{action} requested by {ctx.author.name}#{ctx.author.discriminator}")
                await ctx.edit_original_message(content=None, embed=e)
                await self.sql_add_tbfun(
                    str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                    str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, action, SERVER_BOT
                )
        except Exception:
            await logchanbot("tb " +str(traceback.format_exc()))
        return

    async def tb_firework(
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
                random_img_name = hex_dig + "_firework"
                random_img_name_gif = self.bot.config['fun']['static_draw_path'] + random_img_name + ".gif"
                firework_link = self.bot.config['fun']['static_draw_link'] + random_img_name + ".gif"
                # if hash exists
                if os.path.exists(random_img_name_gif):
                    # send the made file, no need to create new
                    try:
                        e = disnake.Embed(timestamp=datetime.now())
                        e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                        e.set_image(url=firework_link)
                        e.set_footer(text=f"Firework requested by {ctx.author.name}#{ctx.author.discriminator}")
                        await ctx.edit_original_message(content=None, embed=e)
                        await self.sql_add_tbfun(
                            str(ctx.author.id),
                            '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                            str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'FIREWORK',
                            SERVER_BOT
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    return
                else:
                    img = Image.open(BytesIO(res_data)).convert("RGBA")
                    tmp_png = "tmp/" + str(uuid.uuid4()) + ".png"
                    make_firework = functools.partial(start_firework, img, random_img_name_gif, tmp_png, 800, 600, (1366, 768))
                    await self.bot.loop.run_in_executor(None, make_firework)
                    if os.path.exists(tmp_png):
                        os.remove(tmp_png)
                    try:
                        e = disnake.Embed(timestamp=datetime.now())
                        e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                        e.set_image(url=firework_link)
                        e.set_footer(text=f"Firework requested by {ctx.author.name}#{ctx.author.discriminator}")
                        await ctx.edit_original_message(content=None, embed=e)
                        await self.sql_add_tbfun(
                            str(ctx.author.id),
                            '{}#{}'.format(ctx.author.name, ctx.author.discriminator),
                            str(ctx.channel.id), str(ctx.guild.id), ctx.guild.name, 'FIREWORK', SERVER_BOT
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
            else:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, internal error.'
                await ctx.edit_original_message(content=msg)
        except Exception:
            traceback.print_exc(file=sys.stdout)

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
        emoji_code = ""
        try:
            custom_emojis = re.findall(r'<:\w*:\d*>', emoji)
            if custom_emojis and len(custom_emojis) >= 1:
                emoji_code = ", `{}`".format(custom_emojis[0])
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
                    emoji_code = ", `{}`".format(custom_emojis[0])
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
                    await ctx.edit_original_message(
                        content=f'{ctx.author.mention}{emoji_code} {emoji_url}',
                        view=RowButtonRowCloseAnyMessage()
                    )
                except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                    traceback.print_exc(file=sys.stdout)
            return
        except Exception:
            msg = f'{ctx.author.mention}, internal error for getting emoji.'
            await ctx.edit_original_message(content=msg)
            traceback.print_exc(file=sys.stdout)

    @commands.guild_only()
    @commands.slash_command(
        dm_permission=False,
        description="Some fun commands."
    )
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
        usage="tb firework",
        options=[
            Option('member', 'member', OptionType.user, required=False)
        ],
        description="Make firework"
    )
    async def firework(
        self,
        ctx,
        member: disnake.Member = None
    ):
        if member is None:
            member = str(ctx.author.display_avatar)
        else:
            member = str(member.display_avatar)
        await self.tb_firework(ctx, member)

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
