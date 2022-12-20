from PIL import Image, ImageSequence
from io import BytesIO
import sys, traceback
import asyncio
import aiohttp
from shutil import copyfile
import os
import os.path
import hashlib

from Bot import *
config = load_config()


async def action(url_image1: str, url_image2: str, saved_path: str, funcmd: str, gif_image: str):
    funcmd = funcmd.upper()
    timeout = 12
    res_data1 = None
    res_data2 = None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url_image1, timeout=timeout) as response:
                if response.status == 200:
                    res_data1 = await response.read()
                    await session.close()
        async with aiohttp.ClientSession() as session:
            async with session.get(url_image2, timeout=timeout) as response:
                if response.status == 200:
                    res_data2 = await response.read()
                    await session.close()
    except asyncio.TimeoutError:
        print('TIMEOUT: spank')
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

    
    if res_data1 and res_data2:
        hash_object1 = hashlib.sha256(res_data1)
        hex_dig1 = str(hash_object1.hexdigest())

        hash_object2 = hashlib.sha256(res_data2)
        hex_dig2 = str(hash_object2.hexdigest())
        cache_path = config['fun']['fun_img_path'] + funcmd.upper() + "_" + hex_dig1 + hex_dig2 + ".gif"
        if os.path.exists(cache_path):
            # copyfile(cache_path, saved_path)
            print("usge cache")
            return cache_path

        animated_gif = Image.open(gif_image)
        frames = []
        basewidth = 85
        if funcmd == 'PRAISE':
            basewidth = 60
        elif funcmd == 'SHOOT':
            basewidth = 65
        elif funcmd == 'KICK':
            basewidth = 65
        elif funcmd == 'FISTBUMP':
            basewidth = 80
        elif funcmd == 'DANCE':
            basewidth = 35
        img1 = Image.open(BytesIO(res_data1)).convert("RGBA")
        img2 = Image.open(BytesIO(res_data2)).convert("RGBA")
        wpercent = (basewidth/float(img1.size[0]))
        hsize = int((float(img1.size[1])*float(wpercent)))
        img1 = img1.resize((basewidth,hsize), Image.ANTIALIAS)

        if funcmd == 'PRAISE':
            basewidth = 100
        wpercent = (basewidth/float(img2.size[0]))
        hsize = int((float(img2.size[1])*float(wpercent)))
        img2 = img2.resize((basewidth,hsize), Image.ANTIALIAS)
        if funcmd == 'SPANK':
            for frame in ImageSequence.Iterator(animated_gif):
                frame = frame.convert('RGBA') # new
                frame = frame.copy()
                frame.paste(img1, (190, 80), mask=img1)
                frame.paste(img2, (160, 240), mask=img2)
                size = 320, 240
                frame.thumbnail(size, Image.ANTIALIAS)
                frames.append(frame)
            frames[0].save(saved_path, format='GIF', save_all=True, append_images=frames[1:], optimize=True, quality=75)
            # Copy to cache
            copyfile(saved_path, cache_path)
            os.remove(saved_path)
            return cache_path
        elif funcmd == 'PUNCH':
            for frame in ImageSequence.Iterator(animated_gif):
                frame = frame.convert('RGBA') # new
                frame = frame.copy()
                size = 320, 240
                frame.thumbnail(size, Image.ANTIALIAS)
                frame.paste(img1, (0, 0), mask=img1)
                frame.paste(img2, (220, 30), mask=img2)
                frames.append(frame)
            frames[0].save(saved_path, format='GIF', save_all=True, append_images=frames[1:], optimize=True, quality=75)
            # Copy to cache
            copyfile(saved_path, cache_path)
            os.remove(saved_path)
            return cache_path
        elif funcmd == 'SLAP':
            for frame in ImageSequence.Iterator(animated_gif):
                frame = frame.convert('RGBA') # new
                frame = frame.copy()
                size = 320, 240
                frame.thumbnail(size, Image.ANTIALIAS)
                frame.paste(img1, (130, 40), mask=img1)
                frame.paste(img2, (30, 110), mask=img2)
                frames.append(frame)
            frames[0].save(saved_path, format='GIF', save_all=True, append_images=frames[1:], optimize=True, quality=75)
            # Copy to cache
            copyfile(saved_path, cache_path)
            os.remove(saved_path)
            return cache_path
        elif funcmd == 'PRAISE':
            for frame in ImageSequence.Iterator(animated_gif):
                frame = frame.convert('RGBA') # new
                frame = frame.copy()
                size = 320, 240
                frame.thumbnail(size, Image.ANTIALIAS)

                border_im = Image.new('RGBA', (img2.width+12, img2.height+12), 'grey')
                border_im.paste(img2, (6, 6))

                # https://stackoverflow.com/questions/14177744/how-does-perspective-transformation-work-in-pil
                # width, height = border_im.size
                # m = 0.2
                # xshift = abs(m) * width
                # new_width = width + int(round(xshift))
                # border_im = border_im.transform((new_width, height), Image.AFFINE,
                        # (1, m, -xshift if m > 0 else 0, 0, 1, 0), Image.BICUBIC)

                border_im=border_im.rotate(-9, expand=True)
                frame.paste(border_im, (170, 0), mask=border_im)
                frame.paste(img1, (10, 140), mask=img1)
                frames.append(frame)
            frames[0].save(saved_path, format='GIF', save_all=True, append_images=frames[1:], optimize=True, quality=75)
            # Copy to cache
            copyfile(saved_path, cache_path)
            os.remove(saved_path)
            return cache_path
        elif funcmd == 'SHOOT':
            for frame in ImageSequence.Iterator(animated_gif):
                frame = frame.convert('RGBA') # new
                frame = frame.copy()
                size = 320, 180
                frame.thumbnail(size, Image.ANTIALIAS)
                frame.paste(img1, (190, 5), mask=img1)
                frame.paste(img2, (50, 100), mask=img2)

                # size = 160, 80
                # frame.thumbnail(size, Image.ANTIALIAS)
                frames.append(frame)
            frames[0].save(saved_path, format='GIF', save_all=True, append_images=frames[1:], optimize=True, quality=75)
            # Copy to cache
            copyfile(saved_path, cache_path)
            os.remove(saved_path)
            return cache_path
        elif funcmd == 'KICK':
            for frame in ImageSequence.Iterator(animated_gif):
                frame = frame.convert('RGBA') # new
                frame = frame.copy()
                size = 320, 180
                frame.thumbnail(size, Image.ANTIALIAS)
                frame.paste(img1, (50, 15), mask=img1)
                frame.paste(img2, (100, 100), mask=img2)

                frames.append(frame)
            frames[0].save(saved_path, format='GIF', save_all=True, append_images=frames[1:], optimize=True, quality=75)
            # Copy to cache
            copyfile(saved_path, cache_path)
            os.remove(saved_path)
            return cache_path
        elif funcmd == 'FISTBUMP':
            for frame in ImageSequence.Iterator(animated_gif):
                frame = frame.convert('RGBA') # new
                frame = frame.copy()
                size = 320, 180
                frame.thumbnail(size, Image.ANTIALIAS)
                frame.paste(img1, (20, 25), mask=img1)
                frame.paste(img2, (155, 35), mask=img2)

                frames.append(frame)
            frames[0].save(saved_path, format='GIF', save_all=True, append_images=frames[1:], optimize=True, quality=75)
            # Copy to cache
            copyfile(saved_path, cache_path)
            os.remove(saved_path)
            return cache_path
        elif funcmd == 'DANCE':
            for frame in ImageSequence.Iterator(animated_gif):
                frame = frame.convert('RGBA') # new
                frame = frame.copy()
                size = 480, 240
                frame.thumbnail(size, Image.ANTIALIAS)
                frame.paste(img1, (60, 20), mask=img1)
                ## frame.paste(img2, (155, 35), mask=img2)

                frames.append(frame)
            frames[0].save(saved_path, format='GIF', save_all=True, append_images=frames[1:], optimize=True, quality=75)
            # Copy to cache
            copyfile(saved_path, cache_path)
            os.remove(saved_path)
            return cache_path
        else:
            return None
    else:
        return None
