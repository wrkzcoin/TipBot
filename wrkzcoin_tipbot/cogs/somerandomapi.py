import hashlib
import json
import sys
import time
import traceback
from datetime import datetime
from io import BytesIO
import time
import aiohttp
import disnake
import magic
import store
from Bot import logchanbot, EMOJI_INFORMATION, SERVER_BOT
from disnake.app_commands import Option, OptionChoice
from disnake.enums import OptionType
from disnake.ext import commands
from cogs.utils import Utils


class SomeRandomAPI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.utils = Utils(self.bot)
        self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)
        self.poweredby = "https://some-random-api.ml/"
        # animal
        self.some_random_api_path_animal = "some_random_api/animal/"

    async def add_fact_db(self, name: str, fact: str, requested_by_uid: str, requested_by_name: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `some_random_api_fact` 
                    (`name`, `fact`, `requested_by_uid`, `requested_by_name`, `requested_time`) 
                    VALUES (%s, %s, %s, %s, %s)
                    """
                    await cur.execute(sql, (name, fact, requested_by_uid, requested_by_name, int(time.time())))
                    await conn.commit()
                    return cur.rowcount
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return 0

    async def add_joke_db(self, joke: str, requested_by_uid: str, requested_by_name: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `some_random_api_joke` 
                    (`joke`, `requested_by_uid`, `requested_by_name`, `requested_time`) 
                    VALUES (%s, %s, %s, %s)
                    """
                    await cur.execute(sql, (joke, requested_by_uid, requested_by_name, int(time.time())))
                    await conn.commit()
                    return cur.rowcount
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return 0

    async def add_animal_db(
        self, image_url: str, local_path: str, sha256: str, requested_by_uid: str,
        requested_by_name: str, jsondump: str
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `some_random_api_animal` 
                    (`image_url`, `local_path`, `sha256`, `jsondump`, 
                    `requested_by_uid`, `requested_by_name`, `inserted_date`) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    await cur.execute(sql, (
                    image_url, local_path, sha256, jsondump, requested_by_uid, requested_by_name, int(time.time())))

                    await conn.commit()
                    return cur.rowcount
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return 0

    async def check_animal_db(self, image_url: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `some_random_api_animal` 
                    WHERE `image_url`=%s LIMIT 1 """
                    await cur.execute(sql, image_url)
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)

    async def fetch_image(self, image_url: str, saved_path: str, timeout):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, headers=headers, timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        hash_object = hashlib.sha256(res_data)
                        hex_dig = str(hash_object.hexdigest())
                        mime_type = magic.from_buffer(res_data, mime=True)
                        file_name = image_url.split("/")[-1] + "." + mime_type.split("/")[1]
                        with open(saved_path + file_name, "wb") as f:
                            f.write(BytesIO(res_data).getbuffer())
                        return {
                            "saved_location": saved_path + file_name,
                            "image_type": mime_type,
                            "sha256": hex_dig
                        }
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def fetch_sra(self, url, timeout):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        decoded_data = json.loads(res_data)
                        return decoded_data
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    @commands.slash_command(description="Various Some Random API things.")
    async def random(self, ctx):
        # This is just a parent for subcommands
        # It's not necessary to do anything here,
        # but if you do, it runs for any subcommand nested below
        pass

    @random.sub_command(
        usage="random animal <name>",
        options=[
            Option('name', 'name', OptionType.string, required=True, choices=[
                OptionChoice("🐕 dog", "dog"),
                OptionChoice("🐈 cat", "cat"),
                OptionChoice("🐼 panda", "panda"),
                OptionChoice("🦊 fox", "fox"),
                OptionChoice("🐼 red panda", "red_panda"),
                OptionChoice("🐨 koala", "koala"),
                OptionChoice("🐦 bird", "bird"),
                OptionChoice("🦝 raccoon", "raccoon"),
                OptionChoice("🦘 kangaroo", "kangaroo")
            ])
        ],
        description="Get random animal from some-random-api"
    )
    async def animal(
        self,
        ctx,
        name: str
    ):
        await ctx.response.send_message(f"{ctx.author.mention}, random preparation... ")

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, f"/random animal", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            url = "https://some-random-api.ml/animal/" + name
            fetch = await self.fetch_sra(url, 16)
            if fetch:
                if "image" in fetch:
                    embed = disnake.Embed(title=f"Animal {name}", description=f"Random Animal",
                                          timestamp=datetime.now())
                    fact = None
                    if "fact" in fetch:
                        embed.add_field(name="Fact", value=fetch['fact'], inline=False)
                        fact = fetch['fact']
                    embed.set_image(url=fetch["image"])
                    embed.set_footer(
                        text=f"Requested by {ctx.author.name}#{ctx.author.discriminator} | Powered by {self.poweredby}")
                    await ctx.edit_original_message(content=None, embed=embed)
                    # Insert DB # Check if DB exists
                    try:
                        check = await self.check_animal_db(fetch["image"])
                        if check is None:
                            fetch_img = await self.fetch_image(fetch["image"], self.some_random_api_path_animal, 32)
                            if fetch_img:
                                await self.add_animal_db(
                                    fetch["image"], fetch_img['saved_location'],
                                    fetch_img['sha256'], str(ctx.author.id),
                                    "{}#{}".format(ctx.author.name, ctx.author.discriminator),
                                    json.dumps(fetch)
                                )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                else:
                    error = disnake.Embed(title=":exclamation: Error", description=" :warning: internal error!")
                    await ctx.edit_original_message(content=None, embed=error)
            else:
                error = disnake.Embed(title=":exclamation: Error", description=" :warning: internal error!")
                await ctx.edit_original_message(content=None, embed=error)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

    @random.sub_command(
        usage="random fact <name>",
        options=[
            Option('name', 'name', OptionType.string, required=True, choices=[
                OptionChoice("🐕 dog", "dog"),
                OptionChoice("🐈 cat", "cat"),
                OptionChoice("🐼 panda", "panda"),
                OptionChoice("🦊 fox", "fox"),
                OptionChoice("🐨 koala", "koala"),
                OptionChoice("🐦 bird", "bird")
            ])
        ],
        description="Get random fact from some-random-api"
    )
    async def fact(
        self,
        ctx,
        name: str
    ):
        await ctx.response.send_message(f"{ctx.author.mention}, random fact preparation... ")

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, f"/random fact", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            url = "https://some-random-api.ml/facts/" + name
            fetch = await self.fetch_sra(url, 16)
            if fetch:
                if "fact" in fetch:
                    fact = fetch['fact']
                    embed = disnake.Embed(title=f"Fact {name}", description=f"Random Fact", timestamp=datetime.now())
                    embed.add_field(name="Fact", value=fact, inline=False)
                    embed.set_footer(
                        text=f"Requested by {ctx.author.name}#{ctx.author.discriminator} | Powered by {self.poweredby}")
                    await ctx.edit_original_message(content=None, embed=embed)
                    # Insert DB # Check if DB exists
                    try:
                        await self.add_fact_db(
                            name, fact, str(ctx.author.id),
                            "{}#{}".format(ctx.author.name, ctx.author.discriminator)
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                else:
                    error = disnake.Embed(title=":exclamation: Error", description=" :warning: internal error!")
                    await ctx.edit_original_message(content=None, embed=error)
            else:
                error = disnake.Embed(title=":exclamation: Error", description=" :warning: internal error!")
                await ctx.edit_original_message(content=None, embed=error)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

    @random.sub_command(
        usage="random image <name>",
        options=[
            Option('name', 'name', OptionType.string, required=True, choices=[
                OptionChoice("🐕 dog", "dog"),
                OptionChoice("🐈 cat", "cat"),
                OptionChoice("🐼 panda", "panda"),
                OptionChoice("🦊 fox", "fox"),
                OptionChoice("🐼 red panda", "red_panda"),
                OptionChoice("🐨 koala", "koala"),
                OptionChoice("🐦 bird", "bird")
            ])
        ],
        description="Get random image from some-random-api"
    )
    async def image(
        self,
        ctx,
        name: str
    ):
        await ctx.response.send_message(f"{ctx.author.mention}, random image preparation... ")
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, f"/random image", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            url = "https://some-random-api.ml/img/" + name
            fetch = await self.fetch_sra(url, 16)
            if fetch:
                if "link" in fetch:
                    embed = disnake.Embed(
                        title=f"Image {name}",
                        description=f"Random Image",
                        timestamp=datetime.now()
                    )
                    embed.set_image(url=fetch["link"])
                    embed.set_footer(
                        text=f"Requested by {ctx.author.name}#{ctx.author.discriminator} "\
                            f"| Powered by {self.poweredby}"
                    )
                    await ctx.edit_original_message(content=None, embed=embed)
                    # Insert DB # Check if DB exists
                    try:
                        check = await self.check_animal_db(fetch["link"])
                        if check is None:
                            fetch_img = await self.fetch_image(fetch["link"], self.some_random_api_path_animal, 32)
                            if fetch_img:
                                await self.add_animal_db(
                                    fetch["link"], fetch_img['saved_location'],
                                    fetch_img['sha256'], str(ctx.author.id),
                                    "{}#{}".format(ctx.author.name, ctx.author.discriminator),
                                    json.dumps(fetch)
                                )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                else:
                    error = disnake.Embed(title=":exclamation: Error", description=" :warning: internal error!")
                    await ctx.edit_original_message(content=None, embed=error)
            else:
                error = disnake.Embed(title=":exclamation: Error", description=" :warning: internal error!")
                await ctx.edit_original_message(content=None, embed=error)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

    @random.sub_command(
        usage="random joke",
        description="Get random joke from some-random-api"
    )
    async def joke(
        self,
        ctx
    ):
        await ctx.response.send_message(f"{ctx.author.mention}, random joke preparation... ")
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, f"/random joke", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            url = "https://some-random-api.ml/joke"
            fetch = await self.fetch_sra(url, 16)
            if fetch:
                if "joke" in fetch:
                    joke = fetch['joke']
                    embed = disnake.Embed(title=f"RANDOM JOKE", description=joke, timestamp=datetime.now())
                    embed.set_footer(
                        text=f"Requested by {ctx.author.name}#{ctx.author.discriminator} | Powered by {self.poweredby}")
                    await ctx.edit_original_message(content=None, embed=embed)
                    try:
                        await self.add_joke_db(
                            joke, str(ctx.author.id), "{}#{}".format(ctx.author.name, ctx.author.discriminator)
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                else:
                    error = disnake.Embed(title=":exclamation: Error", description=" :warning: internal error!")
                    await ctx.edit_original_message(content=None, embed=error)
            else:
                error = disnake.Embed(title=":exclamation: Error", description=" :warning: internal error!")
                await ctx.edit_original_message(content=None, embed=error)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

def setup(bot):
    bot.add_cog(SomeRandomAPI(bot))
