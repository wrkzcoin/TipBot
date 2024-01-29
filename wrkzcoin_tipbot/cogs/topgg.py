from aiohttp import web
import asyncio
import traceback, sys

import disnake
from disnake.ext import commands
import json, time
from decimal import Decimal
import time
from datetime import datetime
import random
import store
from Bot import SERVER_BOT, log_to_channel
from cogs.wallet import Faucet
from cogs.wallet import WalletAPI
from cogs.utils import Utils, num_format_coin


class TopGGVote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.reward_channel = self.bot.config['bot_vote_link']['reward_channel']
        self.utils = Utils(self.bot)

    async def guild_find_by_key(self, guild_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ SELECT `topgg_vote_secret` 
                    FROM `discord_server` WHERE `serverid`=%s
                    """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchone()
                    if result:
                        return result['topgg_vote_secret']
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def guild_find_by_id(self, guild_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ SELECT * FROM `discord_server` 
                    WHERE `serverid`=%s
                    """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchone()
                    if result:
                        sql = """ SELECT * FROM `discord_feature_roles` 
                        WHERE `guild_id`=%s
                        """
                        await cur.execute(sql, guild_id)
                        feature_roles = await cur.fetchall()
                        list_roles_feature = None
                        if feature_roles and len(feature_roles) > 0:
                            list_roles_feature = {}
                            for each in feature_roles:
                                list_roles_feature[each['role_id']] = {
                                    'faucet_multipled_by': each['faucet_multipled_by'],
                                    'guild_vote_multiplied_by': each['guild_vote_multiplied_by'],
                                    'faucet_cut_time_percent': each['faucet_cut_time_percent']
                                }
                        result['feature_roles'] = list_roles_feature
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def insert_guild_vote(
        self, user_id: str, directory: str, guild_id: str, type_vote: str
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ INSERT IGNORE INTO guild_vote 
                    (`user_id`, `directory`, `guild_id`, `type`, `date_voted`) 
                    VALUES (%s, %s, %s, %s, %s)
                    """
                    await cur.execute(sql, (user_id, directory, guild_id, type_vote, date_vote))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def check_last_guild_vote(self, user_id: str, directory: str, guild_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ SELECT * FROM `guild_vote` 
                    WHERE `user_id`=%s AND `directory`=%s AND `guild_id`=%s 
                    ORDER BY `date_voted` DESC LIMIT 1
                    """
                    await cur.execute(sql, (user_id, directory, guild_id))
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def insert_bot_vote(self, user_id: str, directory: str, bot_id: str, type_vote: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ INSERT IGNORE INTO bot_vote 
                    (`user_id`, `directory`, `bot_id`, `type`, `date_voted`) 
                    VALUES (%s, %s, %s, %s, %s) """
                    await cur.execute(sql, (user_id, directory, bot_id, type_vote, date_vote))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def check_last_bot_vote(self, user_id: str, directory: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    date_vote = int(time.time())
                    sql = """ SELECT * FROM `bot_vote` WHERE `user_id`=%s AND `directory`=%s 
                    ORDER BY `date_voted` DESC LIMIT 1
                    """
                    await cur.execute(sql, (user_id, directory))
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def webserver(self):
        async def handler_get(request):
            return web.Response(status=200, text="Hello, world")

        async def handler_post(request):
            try:
                if request.body_exists:
                    payload = await request.read()
                    headers = request.headers
                    full_payload = json.loads(payload)
                    user_vote = full_payload['user']
                    type_vote = full_payload['type']
                    if str(request.rel_url).startswith("/topgg_server_vote/"):
                        if 'Authorization' in request.headers:
                            # Find Authorization correspond to server ID
                            key = request.headers['Authorization']
                            guild_id = full_payload['guild']
                            get_guild_by_key = await self.guild_find_by_key(guild_id)
                            # Check vote
                            try:
                                # Check if user just vote less than 1h. Sometimes top.gg 
                                # just push too fast multiple times.
                                check_last_vote = await self.check_last_guild_vote(user_vote, "topgg", guild_id)
                                if check_last_vote is not None and int(time.time()) - check_last_vote[
                                    'date_voted'] < 3600 and type_vote != "test":
                                    await log_to_channel(
                                        "vote",
                                        f"[{SERVER_BOT}] User <@{user_vote}> voted for guild `{guild_id}` at top.gg "\
                                        f"type `{type_vote}` but less than 1h."
                                    )
                                    return web.Response(status=200, text="Thank you!")
                            except Exception:
                                traceback.print_exc(file=sys.stdout)

                            # Insert in DB no matter what
                            try:
                                insert_vote = await self.insert_guild_vote(
                                    full_payload['user'], "topgg", full_payload['guild'], full_payload['type']
                                )
                            except Exception:
                                traceback.print_exc(file=sys.stdout)

                            if get_guild_by_key and get_guild_by_key == key.strip():
                                # Check if bot is in that guild, if not post in log chan vote
                                guild = self.bot.get_guild(int(guild_id))
                                # Check if user in that Guild
                                if guild and int(user_vote) not in [m.id for m in guild.members]:
                                    try:
                                        guild_owner = self.bot.get_user(guild.owner.id)
                                        try:
                                            await guild_owner.send(
                                                f"User <@{user_vote}> / `{user_vote}` voted for your guild {guild.name} "\
                                                f"at top.gg but he/she's not in your Guild. No reward."
                                            )
                                        except Exception:
                                            pass
                                        try:
                                            await log_to_channel(
                                                "vote",
                                                f"[{SERVER_BOT}] User <@{user_vote}> voted a guild `{guild_id}` / "\
                                                f"{guild.name} type `{type_vote}` in top.gg but he/she's not in the Guild. No reward."
                                            )
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                    return web.Response(status=200, text="Thank you anyway!")
                                elif guild and int(user_vote) in [m.id for m in guild.members]:
                                    get_guild = await self.guild_find_by_id(guild_id)
                                    if get_guild['vote_reward_amount'] and get_guild['vote_reward_amount'] > 0:
                                        amount = get_guild['vote_reward_amount']
                                        extra_amount = 0.0
                                        previous_amount = 0.0
                                        if get_guild['feature_roles'] is not None:
                                            try:
                                                member = guild.get_member(int(user_vote))
                                                if member and member.roles and len(member.roles) > 0:
                                                    for r in member.roles:
                                                        if str(r.id) in get_guild['feature_roles']:
                                                            extra_amount = amount * get_guild['feature_roles'][str(r.id)]['guild_vote_multiplied_by'] - amount
                                                            if extra_amount > previous_amount:
                                                                previous_amount = extra_amount
                                                    extra_amount = previous_amount
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                        # Tip
                                        coin_name = get_guild['vote_reward_coin']
                                        if not hasattr(self.bot.coin_list, coin_name):
                                            return web.Response(status=200, text="Thank you!")
                                        # Check balance of guild
                                        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                                        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                                        deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                                        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                                        contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                                        price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                                        user_from = await self.wallet_api.sql_get_userwallet(
                                            guild_id, coin_name, net_name, type_coin, SERVER_BOT, 0
                                        )
                                        if user_from is None:
                                            user_from = await self.wallet_api.sql_register_user(
                                                guild_id, coin_name, net_name, type_coin, SERVER_BOT, 0
                                            )
                                        wallet_address = user_from['balance_wallet_address']
                                        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                            wallet_address = user_from['paymentid']
                                        elif type_coin in ["XRP"]:
                                            wallet_address = user_from['destination_tag']

                                        height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
                                        # height can be None
                                        userdata_balance = await store.sql_user_balance_single(
                                            guild_id, coin_name, wallet_address, type_coin,
                                            height, deposit_confirm_depth, SERVER_BOT
                                        )
                                        total_balance = userdata_balance['adjust']
                                        if total_balance < amount + extra_amount:
                                            # Alert guild owner
                                            guild_owner = self.bot.get_user(guild.owner.id)
                                            await guild_owner.send(
                                                f'Your guild run out of guild\'s reward for {coin_name}. Deposit more!')
                                            return web.Response(status=200, text="Thank you!")
                                        else:
                                            # Tip
                                            member = None
                                            try:
                                                member = self.bot.get_user(int(user_vote))
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                            try:
                                                amount_in_usd = 0.0
                                                if price_with:
                                                    per_unit = await self.utils.get_coin_price(coin_name, price_with)
                                                    if per_unit and per_unit['price'] and per_unit['price'] > 0:
                                                        per_unit = per_unit['price']
                                                        amount_in_usd = float(Decimal(per_unit) * Decimal(amount + extra_amount))
                                                tip = await store.sql_user_balance_mv_single(
                                                    guild_id, user_vote, "TOPGG", "VOTE", amount + extra_amount, coin_name,
                                                    "GUILDVOTE", coin_decimal, SERVER_BOT, contract, amount_in_usd, None
                                                )
                                                if member is not None:
                                                    extra_msg = ""
                                                    if extra_amount > 0:
                                                        extra_msg = " You have a guild's role that give you additional "\
                                                            f"bonus **" + num_format_coin(extra_amount) \
                                                            + " " + coin_name + "**."
                                                    msg = f"Thank you for voting for guild `{guild.name}` at top.gg. "\
                                                        f"You got a reward {num_format_coin(amount + extra_amount)} "\
                                                        f"{coin_name}.{extra_msg}"
                                                    try:
                                                        await member.send(msg)
                                                        guild_owner = self.bot.get_user(guild.owner.id)
                                                        try:
                                                            await guild_owner.send(
                                                                f"User {member.name}#{member.discriminator} / `{user_vote}` voted for your guild {guild.name} "\
                                                                f"at top.gg. They got a reward "\
                                                                f"{num_format_coin(amount + extra_amount)} {coin_name}."
                                                            )
                                                        except Exception:
                                                            pass
                                                        # Log channel if there is
                                                        try:
                                                            serverinfo = self.bot.other_data['guild_list'].get(guild_id)
                                                            if serverinfo and serverinfo['vote_reward_channel']:
                                                                channel = self.bot.get_channel(
                                                                    int(serverinfo['vote_reward_channel'])
                                                                )
                                                                try:
                                                                    coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                                                                    coin_emoji = coin_emoji + " " if coin_emoji else ""
                                                                    if channel and channel.guild.get_member(int(self.bot.user.id)).guild_permissions.external_emojis is False:
                                                                        coin_emoji = ""
                                                                except Exception:
                                                                    traceback.print_exc(file=sys.stdout)
                                                                embed = disnake.Embed(
                                                                    title="NEW GUILD VOTE!",
                                                                    timestamp=datetime.now()
                                                                )
                                                                embed.add_field(
                                                                    name="User",
                                                                    value="<@{}>".format(user_vote),
                                                                    inline=True
                                                                )
                                                                embed.add_field(
                                                                    name=f"{coin_emoji}Reward",
                                                                    value="{} {}".format(
                                                                        num_format_coin(amount),
                                                                        coin_name
                                                                    ),
                                                                    inline=True
                                                                )
                                                                if extra_amount > 0:
                                                                    embed.add_field(name="Extra Reward", value="{} {}".format(
                                                                        num_format_coin(extra_amount),
                                                                        coin_name), inline=True)
                                                                embed.add_field(
                                                                    name="Link",
                                                                    value="https://top.gg/servers/{}".format(guild_id),
                                                                    inline=False
                                                                )
                                                                # if advert enable
                                                                if self.bot.config['discord']['enable_advert'] == 1 and len(self.bot.advert_list) > 0:
                                                                    try:
                                                                        random.shuffle(self.bot.advert_list)
                                                                        embed.add_field(
                                                                            name="{}".format(self.bot.advert_list[0]['title']),
                                                                            value="```{}```👉 <{}>".format(self.bot.advert_list[0]['content'], self.bot.advert_list[0]['link']),
                                                                            inline=False
                                                                        )
                                                                        await self.utils.advert_impress(
                                                                            self.bot.advert_list[0]['id'], user_vote,
                                                                            "GUILD VOTE"
                                                                        )
                                                                    except Exception:
                                                                        traceback.print_exc(file=sys.stdout)
                                                                # end advert
                                                                embed.set_author(
                                                                    name=self.bot.user.name,
                                                                    icon_url=self.bot.user.display_avatar
                                                                )
                                                                embed.set_thumbnail(url=member.display_avatar)
                                                                await channel.send(embed=embed)
                                                        except Exception:
                                                            traceback.print_exc(file=sys.stdout)
                                                            await log_to_channel(
                                                                "vote",
                                                                f"[{SERVER_BOT}] Failed to send message to "\
                                                                f"reward channel in guild: `{guild_id}` / {guild.name}."
                                                            )
                                                            try:
                                                                if serverinfo['vote_reward_channel']:
                                                                    await guild_owner.send(
                                                                        f"I can't publish an embed message to channel <#{serverinfo['vote_reward_channel']}> in your guild {guild.name} "\
                                                                        f"which a user just voted at top.gg. You received this message because you are the owner of the guild and "\
                                                                        f"please help to fix the permission."
                                                                    )
                                                            except Exception:
                                                                pass
                                                    except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                                        await log_to_channel(
                                                            "vote",
                                                            f'[{SERVER_BOT}] Failed to thank message to <@{user_vote}>.'
                                                        )
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                if guild:
                                    try:
                                        await log_to_channel(
                                            "vote",
                                            f"[{SERVER_BOT}] User <@{user_vote}> voted a guild `{guild_id}` / "\
                                            f"{guild.name} type `{type_vote}` in top.gg."
                                        )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                else:
                                    try:
                                        await log_to_channel(
                                            "vote",
                                            f"[{SERVER_BOT}] User <@{user_vote}> voted a guild `{guild_id}` / "\
                                            f"type `{type_vote}` in top.gg but I am not in that server or I can't find bot channel."
                                        )
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                return web.Response(status=200, text="Thank you!")
                            else:
                                try:
                                    await log_to_channel(
                                        "vote",
                                        f"[{SERVER_BOT}] User <@{user_vote}> voted a guild `{guild_id}` type `{type_vote}` "\
                                        f"in top.gg but I am not in that guild or I cannot find it. Given key: `{key}`/ Guild key: `{get_guild_by_key}`"
                                    )
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                                return web.Response(status=404, text="No such server by this key! Or not up to date!")
                        else:
                            return web.Response(status=500, text="No Authorization! Or not up to date!")
                    elif str(request.rel_url).startswith("/topgg_bot_vote/"):
                        # Bot: {'user': '386761001808166912', 'type': 'test', 'query': '', 'bot': '474841349968101386'}
                        if 'Authorization' in request.headers and request.headers['Authorization'] == self.bot.config['topgg']['auth']:
                            vote_to = full_payload['bot']
                            try:
                                # Check if user just vote less than 1h. Sometimes top.gg just push too fast multiple times.
                                check_last_vote = await self.check_last_bot_vote(user_vote, "topgg")
                                if check_last_vote is not None and int(time.time()) - check_last_vote['date_voted'] < 3600:
                                    await log_to_channel(
                                        "vote",
                                        f"[{SERVER_BOT}] User <@{user_vote}> voted for bot <@{vote_to}> at top.gg "\
                                        f"type `{type_vote}` but less than 1h."
                                    )
                                    return web.Response(status=200, text="Thank you!")
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                            insert_vote = await self.insert_bot_vote(
                                full_payload['user'], "topgg", full_payload['bot'], full_payload['type']
                            )
                            if insert_vote:
                                try:
                                    await log_to_channel(
                                        "vote",
                                        f"[{SERVER_BOT}] User <@{user_vote}> voted a bot "\
                                        f"<@{vote_to}> type `{type_vote}` in top.gg."
                                    )
                                    if int(vote_to) == self.bot.config['discord']['bot_id']:
                                        # It's TipBot
                                        try:
                                            faucet = Faucet(self.bot)
                                            # get user preferred coin
                                            get_user_coin = await faucet.get_user_faucet_coin(user_vote, SERVER_BOT)
                                            member = None
                                            try:
                                                member = self.bot.get_user(int(user_vote))
                                            except Exception:
                                                traceback.print_exc(file=sys.stdout)
                                            if get_user_coin is not None:
                                                # add reward
                                                list_coins = await faucet.get_faucet_coin_list()
                                                amount = 0.0
                                                coin_name = get_user_coin['coin_name']
                                                for each_coin in list_coins:
                                                    if each_coin['coin_name'].upper() == coin_name.upper() and \
                                                            each_coin['reward_for'] == "topgg":
                                                        coin_name = each_coin['coin_name'].upper()
                                                        amount = each_coin['reward_amount']
                                                        break
                                                if coin_name is not None:
                                                    await faucet.insert_reward(
                                                        user_vote, "topgg", amount, coin_name, int(time.time()), SERVER_BOT
                                                    )
                                                    # Check balance of bot
                                                    net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                                                    type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                                                    deposit_confirm_depth = getattr(
                                                        getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
                                                    user_from = await self.wallet_api.sql_get_userwallet(
                                                        str(self.bot.config['discord']['bot_id']), coin_name, 
                                                        net_name, type_coin, SERVER_BOT, 0
                                                    )
                                                    if user_from is None:
                                                        user_from = await self.wallet_api.sql_register_user(
                                                            str(self.bot.config['discord']['bot_id']), coin_name, 
                                                            net_name, type_coin, SERVER_BOT, 0
                                                        )
                                                    wallet_address = user_from['balance_wallet_address']
                                                    if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                                                        wallet_address = user_from['paymentid']
                                                    elif type_coin in ["XRP"]:
                                                        wallet_address = user_from['destination_tag']

                                                    height = await self.wallet_api.get_block_height(
                                                        type_coin, coin_name, net_name
                                                    )

                                                    # height can be None
                                                    userdata_balance = await store.sql_user_balance_single(
                                                        str(self.bot.config['discord']['bot_id']), coin_name, wallet_address,
                                                        type_coin, height, deposit_confirm_depth, SERVER_BOT
                                                    )
                                                    total_balance = userdata_balance['adjust']
                                                    if total_balance <= amount:
                                                        await log_to_channel(
                                                            "vote",
                                                            f'[{SERVER_BOT}] vote reward for but TipBot for {coin_name} but empty!!!')
                                                        return web.Response(status=200, text="Thank you!")
                                                    else:
                                                        # move reward
                                                        try:
                                                            coin_decimal = getattr(
                                                                getattr(self.bot.coin_list, coin_name), "decimal")
                                                            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
                                                            price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
                                                            amount_in_usd = 0.0
                                                            if price_with:
                                                                per_unit = await self.utils.get_coin_price(coin_name, price_with)
                                                                if per_unit and per_unit['price'] and per_unit['price'] > 0:
                                                                    per_unit = per_unit['price']
                                                                    amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                                                            await store.sql_user_balance_mv_single(
                                                                self.bot.config['discord']['bot_id'], user_vote, "TOPGG", "VOTE",
                                                                amount, coin_name, "BOTVOTE", coin_decimal, SERVER_BOT,
                                                                contract, amount_in_usd, None
                                                            )
                                                            if member is not None:
                                                                advert_txt = ""
                                                                # if advert enable
                                                                if self.bot.config['discord']['enable_advert'] == 1 and len(self.bot.advert_list) > 0:
                                                                    try:
                                                                        random.shuffle(self.bot.advert_list)
                                                                        advert_txt = "\n__**Random Message:**__ {} 👉 <{}>```{}```".format(
                                                                            self.bot.advert_list[0]['title'], self.bot.advert_list[0]['link'], self.bot.advert_list[0]['content']
                                                                        )
                                                                        await self.utils.advert_impress(
                                                                            self.bot.advert_list[0]['id'], user_vote,
                                                                            "TOPGG BOT VOTE"
                                                                        )
                                                                    except Exception:
                                                                        traceback.print_exc(file=sys.stdout)
                                                                # end advert
                                                                msg = f"Thank you for voting for our TipBot at <{self.bot.config['bot_vote_link']['topgg']}>. "\
                                                                    f"You just got a reward {num_format_coin(amount)} {coin_name}. "\
                                                                    f"Check with `/claim` for voting list at other websites.{advert_txt}"
                                                                try:
                                                                    await member.send(msg)
                                                                except (
                                                                disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                                                    await log_to_channel(
                                                                        "vote",
                                                                        f'[{SERVER_BOT}] Failed to thank message to <@{user_vote}>.')
                                                                try:
                                                                    channel = self.bot.get_channel(self.reward_channel)
                                                                    try:
                                                                        coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                                                                        coin_emoji = coin_emoji + " " if coin_emoji else ""
                                                                        if channel and channel.guild.get_member(int(self.bot.user.id)).guild_permissions.external_emojis is False:
                                                                            coin_emoji = ""
                                                                    except Exception:
                                                                        traceback.print_exc(file=sys.stdout)
                                                                    embed = disnake.Embed(
                                                                        title="NEW BOT VOTE!",
                                                                        timestamp=datetime.now()
                                                                    )
                                                                    embed.add_field(
                                                                        name="User",
                                                                        value="<@{}>".format(user_vote),
                                                                        inline=True
                                                                    )
                                                                    embed.add_field(
                                                                        name=f"{coin_emoji}Reward", value="{} {}".format(
                                                                            num_format_coin(amount),
                                                                            coin_name),
                                                                        inline=True
                                                                    )
                                                                    embed.add_field(
                                                                        name="Link",
                                                                        value=self.bot.config['bot_vote_link']['topgg'],
                                                                        inline=False
                                                                    )
                                                                    embed.set_author(
                                                                        name=self.bot.user.name,
                                                                        icon_url=self.bot.user.display_avatar
                                                                    )
                                                                    embed.set_thumbnail(url=member.display_avatar)
                                                                    await channel.send(embed=embed)
                                                                except Exception:
                                                                    traceback.print_exc(file=sys.stdout)
                                                        except Exception:
                                                            traceback.print_exc(file=sys.stdout)
                                            else:
                                                # User didn't put any prefer coin. Message him he could reward
                                                if member is not None:
                                                    msg = f"Thank you for voting for our TipBot at "\
                                                        f"<{self.bot.config['bot_vote_link']['topgg']}>. "\
                                                        f"You can get a reward! Know more by `/claim` or `/claim token_name` "\
                                                        f"to set your preferred coin/token reward."
                                                    try:
                                                        await member.send(msg)
                                                    except (disnake.errors.NotFound, disnake.errors.Forbidden) as e:
                                                        await log_to_channel(
                                                            "vote",
                                                            f'[{SERVER_BOT}] Failed to inform message to <@{user_vote}>.')
                                        except Exception:
                                            traceback.print_exc(file=sys.stdout)
                                except Exception:
                                    traceback.print_exc(file=sys.stdout)
                            return web.Response(status=200, text="Thank you!")
                    else:
                        await log_to_channel(
                            "vote",
                            f"[{SERVER_BOT}] User <@{user_vote}> voted type `{type_vote}` but not true from top.gg.")
                        return web.Response(status=200, text="Thank you but not topgg!")
            except Exception:
                traceback.print_exc(file=sys.stdout)

        app = web.Application()
        app.router.add_get('/{tail:.*}', handler_get)
        app.router.add_post('/{tail:.*}', handler_post)
        runner = web.AppRunner(app)
        await runner.setup()
        self.site = web.TCPSite(
            runner,
            self.bot.config['bot_vote_link']['binding_ip'],
            self.bot.config['bot_vote_link']['topgg_port']
        )
        await self.bot.wait_until_ready()
        await self.site.start()

    async def cog_load(self):
        # Automatically called when the cog is loaded
        # with the added benefit of being async!

        # Ensure the task is started when the cog is loaded,
        # and only after the bot is ready.
        await self.bot.wait_until_ready()

    def cog_unload(self):
        asyncio.ensure_future(self.site.stop())


def setup(bot):
    topgg = TopGGVote(bot)
    bot.add_cog(topgg)
    bot.loop.create_task(topgg.webserver())
