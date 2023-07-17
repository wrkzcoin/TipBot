import aiohttp
import sys
import time
import traceback
from datetime import datetime
import random

import urllib.parse
import aiofiles
from string import ascii_uppercase
import subprocess
import os

from io import BytesIO

import disnake
from disnake.ext import commands, tasks
from disnake import TextInputStyle

from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice
from disnake import ActionRow, Button, ButtonStyle
import asyncio
# python -m pip install -U pycld2
import pycld2 as cld2

# pip install edge-tts
import edge_tts

import store

from cogs.utils import MenuPage
from cogs.utils import Utils, num_format_coin

from Bot import logchanbot, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_INFORMATION, seconds_str, \
    RowButtonRowCloseAnyMessage, SERVER_BOT, EMOJI_HOURGLASS_NOT_DONE, DEFAULT_TICKER, text_to_num, log_to_channel
from cogs.wallet import WalletAPI

# example: https://github.com/rany2/edge-tts/blob/master/examples/basic_generation.py
# edge-tts --list-voices: list of available voices

async def ai_tts_edge(text: str, output_path: str, voice: str='en-GB-SoniaNeural'):
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        return output_path # mp3
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def ai_tts_edge_fetch_list():
    try:
        lists = await edge_tts.list_voices()
        list_selected = []
        for i in lists:
            if i['ShortName'].startswith('en-'):
                # print(i['ShortName'], i['Gender'])
                list_selected.append(i)
        return list_selected
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

async def ai_tts_get(
    url: str, text: str, saved_name: str, model: str, timeout: int=900
):
    text = text.strip()
    print("processing remote work model {}->{}: {}".format(model, url, text[0:100]))
    if model == "en/vctk/vits":
        url += "api/tts?text=" + urllib.parse.quote(text) + "&speaker_id=p376&style_wav=&language_id="
    else:
        url += "api/tts?text=" + urllib.parse.quote(text) + "&speaker_id=&style_wav=&language_id="
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=timeout
            ) as resp:
                if resp.status == 200:
                    f = await aiofiles.open(saved_name, mode='wb')
                    await f.write(await resp.read())
                    await f.close()
                    return saved_name
    except asyncio.TimeoutError:
        await logchanbot(
            "ai_tts_get timeout: {} for url: {}".format(timeout, url)
        )
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

class DownloadAudioMP3(disnake.ui.View):
    def __init__(self, base_url: str):
        super().__init__()
        self.add_item(disnake.ui.Button(label="📥 MP3", url=base_url + ".mp3"))

class DownloadAudio(disnake.ui.View):
    def __init__(self, base_url: str):
        super().__init__()
        self.add_item(disnake.ui.Button(label="📥 WAV", url=base_url + ".wav"))
        self.add_item(disnake.ui.Button(label="📥 MP3", url=base_url + ".mp3"))

class AiThing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.ai_tss_progress = {}

    async def insert_ai_tts(
        self, user_id: str, user_name: str, guild_id: str,
        text: str, char_len: int, timestamp: int, audio_file: str,
        time_token: int
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT INTO `ai_tts`
                    (`user_id`, `user_name`, `guild_id`, `text`,
                    `char_len`, `timestamp`, `audio_file`, `time_token`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    await cur.execute(sql, (
                        user_id, user_name, guild_id, text,
                        char_len, timestamp, audio_file, time_token
                    ))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def get_user_ai_tts(self, user_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT *
                    FROM `ai_tts`
                    WHERE `user_id`=%s
                    ORDER BY `id` DESC
                    """
                    await cur.execute(sql, (
                        user_id
                    ))
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def get_last_user_ai_tts(self, user_id: str, duration: int=3600):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                lap = int(time.time()) - duration
                async with conn.cursor() as cur:
                    sql = """
                    SELECT SUM(`char_len`) AS char_len, COUNT(*) AS count
                    FROM `ai_tts`
                    WHERE `user_id`=%s AND `timestamp`>=%s
                    """
                    await cur.execute(sql, (
                        user_id, lap
                    ))
                    result = await cur.fetchone()
                    if result:
                        return {'len': result['char_len'] if result['char_len'] else 0, 'count': result['count']}
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return {'len': 0, 'count': 0}

    # can be in DM or Guild
    @commands.slash_command(
        name="aitool",
        description="Some AI tools."
    )
    async def ai_thing(self, ctx):
        if self.bot.config['aithing']['is_private'] == 1 and ctx.author.id not in self.bot.config['aithing']['testers']:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, this command is not public yet. "\
                "Please try again later!"
            await ctx.response.send_message(msg)
            return

    @ai_thing.sub_command(
        name="edge-tts",
        usage="aitool edge-tts <text> [model]",
        options=[
            Option('text', 'text', OptionType.string, required=True),
            Option('model', 'model', OptionType.string, required=False),
        ],
        description="Create text-to-speech using Edge TTS"
    )
    async def ai_thing_edge_tts(
        self,
        ctx,
        text: str,
        model: str='en-GB-SoniaNeural',
    ):
        await ctx.response.send_message(f"{ctx.author.mention}, loading ai tools ...")    
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/aitool edge-tts", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        try:
            text = text.strip()
            if len(text) > self.bot.config['aithing']['max_len']:
                await ctx.edit_original_message(
                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, input text is longer than {str(self.bot.config['aithing']['max_len'])}!")
                return
            elif len(text) < self.bot.config['aithing']['min_len']:
                await ctx.edit_original_message(
                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, input text is shorter than {str(self.bot.config['aithing']['min_len'])}!!")
                return
            try:
                # https://github.com/aboSamoor/pycld2#example
                isReliable, textBytesFound, details = cld2.detect(text)
                if isReliable is False:
                    await ctx.edit_original_message(
                        content=f"{EMOJI_INFORMATION} {ctx.author.mention}, can't detect language or text is too short!")
                    return
                else:
                    if details[0][1] != 'en':
                        await ctx.edit_original_message(
                            content=f"{EMOJI_INFORMATION} {ctx.author.mention}, only supporting English right now!")
                        return
            except Exception:
                traceback.print_exc(file=sys.stdout)
                # check alpha numeric
                if not text.replace(" ", "").replace("!", "").replace(".", "").replace("?", "").replace("-", "").replace(":", "").isalnum():
                    await ctx.edit_original_message(
                        content=f"{EMOJI_INFORMATION} {ctx.author.mention}, error language detection!")
                    return

            # normal use
            if ctx.author.id not in self.bot.config['aithing']['testers'] and len(text) > self.bot.config['aithing']['mormal_user_len']:
                await ctx.edit_original_message(
                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, the text is too long {str(len(text))} > { self.bot.config['aithing']['mormal_user_len']}!")
                return

            model_list = self.bot.other_data['ai_edge_tts_models']
            # if model not exists
            if self.bot.other_data.get('ai_edge_tts_models') is None:
                await ctx.edit_original_message(
                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, pending model loading...")
                return
            elif model not in model_list:
                await ctx.edit_original_message(
                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, invalid given model name. Please select from list```{', '.join(model_list)}```")
                return

            if ctx.author.id in self.ai_tss_progress and self.ai_tss_progress[ctx.author.id] > int(time.time()) - 90 and \
                ctx.author.id not in self.bot.config['aithing']['testers']:
                await ctx.edit_original_message(
                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, you executed too recent of this tool! Wait a bit.")
                return
            else:
                self.ai_tss_progress[ctx.author.id] = int(time.time())

            # get records
            counts = await self.get_last_user_ai_tts(str(ctx.author.id), 24*3600)
            if counts['count'] >= self.bot.config['aithing']['max_time_day'] and ctx.author.id not in self.bot.config['aithing']['testers']:
                await ctx.edit_original_message(
                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, you reached max. usage per last 24 hours!")
                return
            await ctx.edit_original_message(
                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, processing {str(len(text))} characters ....!")

            content = text if len(text) <= 1000 else text[0:950] + " ... (more)"
            guild_id = "DM"
            guild_name = "DM"
            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                guild_id = ctx.guild.id
                guild_name = ctx.guild.name
            await log_to_channel(
                "aitool",
                f"[AI TOOL] User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                f"used TTS {str(len(text))} characters ({model}) in {guild_id} / {guild_name}.",
                self.bot.config['discord']['aitool']
            )
            start_time = int(time.time())
            path = self.bot.config['aithing']['path']
            saved_name = str(int(time.time())) + "_" + ''.join(random.choice(ascii_uppercase) for i in range(8))
            tts = await ai_tts_edge(text, path + saved_name + ".mp3", model)
            if tts:
                await ctx.edit_original_message(
                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, converting to media ....!")
                command = f'ffmpeg -i {path + saved_name + ".mp3"} -filter_complex "[0:a]showwaves=s=640x360:mode=cline:r=30,colorkey=0x000000:0.01:0.1,format=yuv420p[vid]" -map "[vid]" -map 0:a -codec:v libx264 -crf 18 -c:a copy {path + saved_name + ".mp4"}'
                process_video = subprocess.Popen(command, shell=True)
                process_video.wait(timeout=30000) # 30s waiting
                file = disnake.File(path + saved_name + ".mp4", filename=saved_name + ".mp4")
                duration = int(time.time() - start_time)
                file_size = os.stat(path + saved_name + ".mp4") # byte
                if file_size.st_size >= self.bot.config['aithing']['max_size']:
                    # send link
                    await ctx.edit_original_message(
                        content=content + "\n" + self.bot.config['aithing']['url'] + saved_name + ".mp4",
                        view=DownloadAudioMP3(self.bot.config['aithing']['url'] + saved_name)
                    )                        
                else:
                    await ctx.edit_original_message(
                        content=content,
                        file=file,
                        view=DownloadAudioMP3(self.bot.config['aithing']['url'] + saved_name)
                    )
                await self.insert_ai_tts(
                    str(ctx.author.id), "{}#{}".format(ctx.author.name, ctx.author.discriminator),
                    guild_id, text, len(text), int(time.time()), saved_name + ".mp3",
                    duration
                )
                await log_to_channel(
                    "aitool",
                    f"[AI TOOL] User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                    f"completed TTS:\n{content}\n" + self.bot.config['aithing']['url'] + saved_name + ".mp4",
                    self.bot.config['discord']['aitool']
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @ai_thing.sub_command(
        name="tts",
        usage="aitool tts <model> <text>",
        options=[
            Option('model', 'model', OptionType.string, required=True, choices=[
                OptionChoice("en/ljspeech/tacotron2-DDC", "en/ljspeech/tacotron2-DDC"),
                OptionChoice("en/vctk/vits", "en/vctk/vits"),
                OptionChoice("en/jenny/jenny", "en/jenny/jenny"),
                OptionChoice("en/ljspeech/speedy-speech", "en/ljspeech/speedy-speech"),
                OptionChoice("en/ljspeech/fast_pitch", "en/ljspeech/fast_pitch"),
                OptionChoice("en/ljspeech/glow-tts", "en/ljspeech/glow-tts"),
                OptionChoice("en/ljspeech/tacotron2-DCA", "en/ljspeech/tacotron2-DCA")
            ]),
            Option('text', 'text', OptionType.string, required=True),
        ],
        description="Create text-to-speech"
    )
    async def ai_thing_tts(
        self,
        ctx,
        model: str,
        text: str
    ):
        await ctx.response.send_message(f"{ctx.author.mention}, loading ai tools ...")

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/aitool tts", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        try:
            text = text.strip()
            if len(text) > self.bot.config['aithing']['max_len']:
                await ctx.edit_original_message(
                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, input text is longer than {str(self.bot.config['aithing']['max_len'])}!")
                return
            elif len(text) < self.bot.config['aithing']['min_len']:
                await ctx.edit_original_message(
                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, input text is shorter than {str(self.bot.config['aithing']['min_len'])}!!")
                return
            try:
                # https://github.com/aboSamoor/pycld2#example
                isReliable, textBytesFound, details = cld2.detect(text)
                if isReliable is False:
                    await ctx.edit_original_message(
                        content=f"{EMOJI_INFORMATION} {ctx.author.mention}, can't detect language or text is too short!")
                    return
                else:
                    if details[0][1] != 'en':
                        await ctx.edit_original_message(
                            content=f"{EMOJI_INFORMATION} {ctx.author.mention}, only supporting English right now!")
                        return
            except Exception:
                traceback.print_exc(file=sys.stdout)
                # check alpha numeric
                if not text.replace(" ", "").replace("!", "").replace(".", "").replace("?", "").replace("-", "").replace(":", "").isalnum():
                    await ctx.edit_original_message(
                        content=f"{EMOJI_INFORMATION} {ctx.author.mention}, error language detection!")
                    return

            if self.bot.other_data.get('ai_tts_models') is None:
                await self.utils.ai_reload_model_tts()
            if self.bot.other_data.get('ai_tts_models') is None:
                await ctx.edit_original_message(
                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, failed to load model's information!")
                return
            elif model not in self.bot.other_data['ai_tts_models']:
                await ctx.edit_original_message(
                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, invalid model or the model is not enabled!")
                return
            else:
                # normal use
                if ctx.author.id not in self.bot.config['aithing']['testers'] and len(text) > self.bot.config['aithing']['mormal_user_len']:
                    await ctx.edit_original_message(
                        content=f"{EMOJI_INFORMATION} {ctx.author.mention}, the text is too long {str(len(text))} > { self.bot.config['aithing']['mormal_user_len']}!")
                    return

                if ctx.author.id in self.ai_tss_progress and self.ai_tss_progress[ctx.author.id] > int(time.time()) - 90 and \
                    ctx.author.id not in self.bot.config['aithing']['testers']:
                    await ctx.edit_original_message(
                        content=f"{EMOJI_INFORMATION} {ctx.author.mention}, you executed too recent of this tool! Wait a bit.")
                    return
                else:
                    self.ai_tss_progress[ctx.author.id] = int(time.time())
                # get records
                counts = await self.get_last_user_ai_tts(str(ctx.author.id), 24*3600)
                if counts['count'] >= self.bot.config['aithing']['max_time_day'] and ctx.author.id not in self.bot.config['aithing']['testers']:
                    await ctx.edit_original_message(
                        content=f"{EMOJI_INFORMATION} {ctx.author.mention}, you reached max. usage per last 24 hours!")
                    return
                await ctx.edit_original_message(
                    content=f"{EMOJI_INFORMATION} {ctx.author.mention}, processing {str(len(text))} characters ....!")
                content = text if len(text) <= 1000 else text[0:950] + " ... (more)"
                guild_id = "DM"
                guild_name = "DM"
                if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                    guild_id = ctx.guild.id
                    guild_name = ctx.guild.name
                await log_to_channel(
                    "aitool",
                    f"[AI TOOL] User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                    f"used TTS {str(len(text))} characters ({model}) in {guild_id} / {guild_name}.",
                    self.bot.config['discord']['aitool']
                )
                start_time = int(time.time())
                url = self.bot.other_data['ai_tts_models'][model]
                path = self.bot.config['aithing']['path']
                saved_name = str(int(time.time())) + "_" + ''.join(random.choice(ascii_uppercase) for i in range(8))
                tts = await ai_tts_get(url, text, path + saved_name + ".wav", model, 1200)
                if tts:
                    await ctx.edit_original_message(
                        content=f"{EMOJI_INFORMATION} {ctx.author.mention}, converting to media ....!")
                    command = f'ffmpeg -i {path + saved_name + ".wav"} {path + saved_name + ".mp3"}; ffmpeg -i {path + saved_name + ".mp3"} -filter_complex "[0:a]showwaves=s=640x360:mode=cline:r=30,colorkey=0x000000:0.01:0.1,format=yuv420p[vid]" -map "[vid]" -map 0:a -codec:v libx264 -crf 18 -c:a copy {path + saved_name + ".mp4"}'
                    process_video = subprocess.Popen(command, shell=True)
                    process_video.wait(timeout=30000) # 30s waiting
                    file = disnake.File(path + saved_name + ".mp4", filename=saved_name + ".mp4")
                    duration = int(time.time() - start_time)
                    file_size = os.stat(path + saved_name + ".mp4") # byte
                    if file_size.st_size >= self.bot.config['aithing']['max_size']:
                        # send link
                        await ctx.edit_original_message(
                            content=content + "\n" + self.bot.config['aithing']['url'] + saved_name + ".mp4",
                            view=DownloadAudio(self.bot.config['aithing']['url'] + saved_name)
                        )                        
                    else:
                        await ctx.edit_original_message(
                            content=content,
                            file=file,
                            view=DownloadAudio(self.bot.config['aithing']['url'] + saved_name)
                        )
                    await self.insert_ai_tts(
                        str(ctx.author.id), "{}#{}".format(ctx.author.name, ctx.author.discriminator),
                        guild_id, text, len(text), int(time.time()), saved_name + ".wav",
                        duration
                    )
                    await log_to_channel(
                        "aitool",
                        f"[AI TOOL] User {ctx.author.name}#{ctx.author.discriminator} / {ctx.author.mention} "\
                        f"completed TTS:\n{content}\n" + self.bot.config['aithing']['url'] + saved_name + ".mp4",
                        self.bot.config['discord']['aitool']
                    )
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await ctx.edit_original_message(
                content=f"{EMOJI_INFORMATION} {ctx.author.mention}, internal error!")

    @ai_thing_edge_tts.autocomplete("model")
    async def ai_thing_edge_tts_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        if self.bot.other_data.get('ai_edge_tts_models') is None:
            return [disnake.OptionChoice(name="Failed to load...", value=0)]
        else:
            return [disnake.OptionChoice(
                name=k, value=k) for k in self.bot.other_data['ai_edge_tts_models'] if string.lower() in k.lower()
            ][0:15]

    @commands.Cog.listener()
    async def on_ready(self):
        # re-load ai tts model
        if self.bot.other_data.get('ai_tts_models') is None:
            await self.utils.ai_reload_model_tts()
        # re-load edge tts model
        if self.bot.other_data.get('ai_edge_tts_models') is None:
            list_models = await ai_tts_edge_fetch_list()
            if len(list_models) > 0:
                self.bot.other_data['ai_edge_tts_models'] = [i['ShortName'] for i in list_models]

    async def cog_load(self):
        # re-load ai tts model
        if self.bot.other_data.get('ai_tts_models') is None:
            await self.utils.ai_reload_model_tts()
        # re-load edge tts model
        if self.bot.other_data.get('ai_edge_tts_models') is None:
            list_models = await ai_tts_edge_fetch_list()
            if len(list_models) > 0:
                self.bot.other_data['ai_edge_tts_models'] = [i['ShortName'] for i in list_models]
        print("Cog AiThing loaded...")

    def cog_unload(self):
        print("Cog AiThing unloaded...")

def setup(bot):
    bot.add_cog(AiThing(bot))
