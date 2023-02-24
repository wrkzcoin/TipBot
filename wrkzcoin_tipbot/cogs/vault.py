import sys
import traceback
from datetime import datetime
import time
import json
import asyncio, aiohttp

from Bot import encrypt_string, decrypt_string, SERVER_BOT, EMOJI_RED_NO, EMOJI_INFORMATION
from cogs.utils import Utils
from cogs.wallet import WalletAPI
import disnake
from disnake.app_commands import Option
from disnake.enums import OptionType
from disnake.enums import ButtonStyle
from disnake import TextInputStyle
from disnake.ext import commands
# wallet thing
from pywallet import wallet as ethwallet

import store
from cogs.utils import Utils, num_format_coin
from cogs.wallet import WalletAPI


def create_address_eth():
    seed = ethwallet.generate_mnemonic()
    w = ethwallet.create_wallet(network="ETH", seed=seed, children=1)
    return w

async def get_address_bcn(
    coin_name: str, wallet_api_url: str, header: str, timeout: int=30
):
    try:
        if coin_name in ["WRKZ", "DEGO"]:
            headers = {
                'X-API-KEY': header,
                'Content-Type': 'application/json'
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    wallet_api_url + "/addresses/create",
                    headers=headers,
                    timeout=timeout
                ) as response:
                    if response.status == 201:
                        json_resp = await response.json()
                        # call save wallet
                        async with session.put(
                            wallet_api_url + "/save",
                            headers=headers,
                            timeout=timeout
                        ) as save_resp:
                            if save_resp.status == 200:
                                return json_resp
                            else:
                                print(f"internal error during save wallet {coin_name}")
                    else:
                        print(f"internal error during create wallet {coin_name}")
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def vault_insert(
    user_id: str, user_server: str, coin_name: str, coin_type: str,
    address: str, spend_key: str, view_key: str, private_key: str,
    seed: str, dump: str
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                INSERT INTO `vaults` 
                (`coin_name`, `type`, `user_id`, `user_server`, `address`, `spend_key`,
                `view_key`, `private_key`, `seed`, `dump`, `address_ts`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """
                await cur.execute(sql, (
                    coin_name, coin_type, user_id, user_server, address,
                    spend_key, view_key, private_key, seed, dump, int(time.time())
                ))
                await conn.commit()
                return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def get_a_user_vault_list(user_id: str, user_server: str):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT * FROM `vaults`
                WHERE `user_id`=%s AND `user_server`=%s
                """
                await cur.execute(sql, (user_id, user_server))
                result = await cur.fetchall()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

async def get_a_user_vault_coin(user_id: str, coin_name: str, user_server: str):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT * FROM `vaults`
                WHERE `user_id`=%s AND `user_server`=%s AND `coin_name`=%s
                LIMIT 1
                """
                await cur.execute(sql, (user_id, user_server, coin_name))
                result = await cur.fetchone()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

async def get_coin_vault_setting(coin_name: str):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT * FROM `vaults_coin_setting`
                WHERE `coin_name`=%s
                LIMIT 1
                """
                await cur.execute(sql, coin_name)
                result = await cur.fetchone()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

class DropdownVaultCoin(disnake.ui.StringSelect):
    def __init__(self, ctx, owner_id, bot, embed, list_coins, selected_coin):
        self.ctx = ctx
        self.owner_id = owner_id
        self.bot = bot
        self.embed = embed
        self.list_coins = list_coins
        self.selected_coin = selected_coin
        self.utils = Utils(self.bot)

        options = [
            disnake.SelectOption(
                label=each, description="Select {}".format(each.upper()),
                emoji=getattr(getattr(self.bot.coin_list, each), "coin_emoji_discord")
            ) for each in list_coins
        ]

        super().__init__(
            placeholder="Choose menu..." if self.selected_coin is None else self.selected_coin,
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, inter: disnake.MessageInteraction):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, that is not your menu!", delete_after=3.0)
            return
        else:
            await inter.response.send_message(f"{inter.author.mention}, checking...", delete_after=1.0)
            # check if user has that coin
            get_a_vault = None
            if self.values[0] is not None:
                get_a_vault = await get_a_user_vault_coin(str(self.owner_id), self.values[0], SERVER_BOT)
            self.embed.clear_fields()
            self.embed.add_field(
                name="Selected coins",
                value=self.values[0],
                inline=False
            )
            if get_a_vault is not None:
                self.embed.add_field(
                    name="Address",
                    value=get_a_vault['address'],
                    inline=False
                )
            self.embed.add_field(
                name="NOTE",
                value=self.bot.config['vault']['note_msg'],
                inline=False
            )
            if get_a_vault is None:
                disable_update = False
                disable_withdraw = True
                disable_viewkey = True
            else:
                disable_update = True
                disable_withdraw = False
                disable_viewkey = False
            view = VaultMenu(
                self.bot, self.ctx, inter.author.id, self.embed, self.bot.config['vault']['enable_vault'],
                self.values[0], disable_update, disable_withdraw, disable_viewkey
            )
            await self.ctx.edit_original_message(content=None, embed=self.embed, view=view)


class VaultMenu(disnake.ui.View):
    def __init__(
        self, bot,
        ctx,
        owner_id: int,
        embed,
        list_coins,
        selected_coin: str=None,
        disable_create_update: bool=True, disable_withdraw: bool=True,
        disable_viewkey: bool=True
    ):
        super().__init__()
        self.bot = bot
        self.ctx = ctx
        self.owner_id = owner_id
        self.embed = embed
        self.selected_coin = selected_coin
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)

        self.btn_vault_update.disabled = disable_create_update
        self.btn_vault_withdraw.disabled = disable_withdraw
        self.btn_vault_viewkey.disabled = disable_viewkey

        self.add_item(DropdownVaultCoin(
            ctx, owner_id, self.bot, self.embed, list_coins, self.selected_coin
        ))

    @disnake.ui.button(label="Create/Update", style=ButtonStyle.green, custom_id="vault_update")
    async def btn_vault_update(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        # In case future this is public
        if interaction.author.id != self.owner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, that's not yours!", ephemeral=True)
        else:
            await interaction.response.send_message(f"{interaction.author.mention}, creating...", ephemeral=True)
            inserting = False
            address = ""
            if self.selected_coin == "ETH":
                type_coin = "ERC-20"
                w = create_address_eth()
                inserting = await vault_insert(
                    str(self.owner_id), SERVER_BOT, self.selected_coin, type_coin,
                    w['address'], None, None, encrypt_string(w['private_key']), encrypt_string(w['seed']), encrypt_string(str(w))
                )
                address = w['address']
            elif self.selected_coin in ["WRKZ", "DEGO"]:
                type_coin = "TRTL-API"
                coin_setting = await get_coin_vault_setting(self.selected_coin)
                if coin_setting is None:
                    await interaction.edit_original_message(f"{interaction.author.mention}, internal error when creating {self.selected_coin} address!")
                    return
                create_wallet = await get_address_bcn(self.selected_coin, coin_setting['wallet_address'], coin_setting['header'], 30)
                if create_wallet is not None:
                    inserting = await vault_insert(
                        str(self.owner_id), SERVER_BOT, self.selected_coin, type_coin,
                        create_wallet['address'], spend_key=encrypt_string(create_wallet['privateSpendKey']),
                        view_key=coin_setting['view_key'], private_key=None, seed=None, dump=encrypt_string(json.dumps(create_wallet))
                    )
                    address = create_wallet['address']
                else:
                    await interaction.edit_original_message(f"{interaction.author.mention}, internal error when creating {self.selected_coin} address!")            
            if inserting is True:
                self.embed.clear_fields()
                self.embed.add_field(
                    name="Selected coins",
                    value=self.selected_coin,
                    inline=False
                )
                self.embed.add_field(
                    name="Address",
                    value=address,
                    inline=False
                )
                self.embed.add_field(
                    name="NOTE",
                    value=self.bot.config['vault']['note_msg'],
                    inline=False
                )
                disable_update = True
                disable_withdraw = False
                disable_viewkey = False
                view = VaultMenu(
                    self.bot, self.ctx, self.owner_id, self.embed, self.bot.config['vault']['enable_vault'],
                    self.selected_coin, disable_update, disable_withdraw, disable_viewkey
                )
                await interaction.edit_original_message(f"{interaction.author.mention}, successfully created your {self.selected_coin} address!")
                await self.ctx.edit_original_message(content=None, embed=self.embed, view=view)
            else:
                disable_update = True
                disable_withdraw = True
                disable_viewkey = True
                view = VaultMenu(
                    self.bot, self.ctx, self.owner_id, self.embed, self.bot.config['vault']['enable_vault'],
                    self.selected_coin, disable_update, disable_withdraw, disable_viewkey
                )
                await interaction.edit_original_message(f"{interaction.author.mention}, internal error when creating {self.selected_coin} address!")
                await self.ctx.edit_original_message(content=None, embed=self.embed, view=view)

    @disnake.ui.button(label="Withdraw", style=ButtonStyle.primary, custom_id="vault_withdraw")
    async def btn_vault_withdraw(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        # In case future this is public
        if interaction.author.id != self.owner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, that's not yours!", ephemeral=True)
        else:
            await interaction.response.send_message(f"{interaction.author.mention}, TODO!", ephemeral=True)

    @disnake.ui.button(label="View Key/Seed", style=ButtonStyle.red, custom_id="vault_viewkey")
    async def btn_vault_viewkey(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        # In case future this is public
        if interaction.author.id != self.owner_id:
            await interaction.response.send_message(f"{interaction.author.mention}, that's not yours!", ephemeral=True)
        else:
            await interaction.response.send_message(f"{interaction.author.mention}, loading data...", ephemeral=True)
            get_a_vault = None
            if self.selected_coin is not None:
                get_a_vault = await get_a_user_vault_coin(str(self.owner_id), self.selected_coin, SERVER_BOT)
            if get_a_vault is None:
                await interaction.edit_original_message(f"{interaction.author.mention}, internal error when loading your {self.selected_coin} data!")
            else:
                coin_setting = await get_coin_vault_setting(self.selected_coin)
                data = ""
                if self.selected_coin == "ETH":
                    data = "Address: {}\n".format(get_a_vault['address'])
                    data += "Seed: {}\n".format(decrypt_string(get_a_vault['seed']))
                elif self.selected_coin in ["WRKZ", "DEGO"]:
                    data = "Address: {}\n".format(get_a_vault['address'])
                    data += "View key: {}\n".format(decrypt_string(get_a_vault['view_key']))
                    data += "Spend key: {}\n".format(decrypt_string(get_a_vault['spend_key']))
                if coin_setting['note'] is not None:
                    data += coin_setting['note']
                await interaction.edit_original_message(f"{interaction.author.mention}, your {self.selected_coin} data! Keep for yourself and don't share!```{data}```")

class Vault(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)

    @commands.slash_command(
        name="vault",
        dm_permission=True,
        description="Various crypto vault commands in TipBot."
    )
    async def vault(self, ctx):
        try:
            if self.bot.config['vault']['is_private'] == 1 and ctx.author.id not in self.bot.config['vault']['private_user_list']:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, this command is not public yet. "\
                    "Please try again later!"
                await ctx.response.send_message(msg, ephemeral=True)
                return
            # If command is in public
            if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, this command needs to be in DM."
                await ctx.response.send_message(msg, ephemeral=True)
                return
            is_user_locked = self.utils.is_locked_user(str(ctx.author.id), SERVER_BOT)
            if is_user_locked is True:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, your account is locked for using the Bot. Please contact bot dev by /about link."
                await ctx.response.send_message(msg, ephemeral=True)
                return
            if self.bot.config['vault']['disable'] == 1 and ctx.author.id != self.bot.config['discord']['owner_id']:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, Vault is currently on maintenance. Be back soon!"
                await ctx.response.send_message(msg, ephemeral=True)
                return
        except Exception:
            return

    @vault.sub_command(
        name="intro",
        usage="vault intro",
        description="Introduction of /vault."
    )
    async def vault_intro(
        self,
        ctx
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /vault loading..."
        await ctx.response.send_message(msg, ephemeral=True)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/vault intro", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            embed = disnake.Embed(
                title="Your TipBot's Vault",
                description=f"{ctx.author.mention}, You can join our supported guild for #help.",
                timestamp=datetime.now(),
            )
            embed.add_field(
                name="BRIEF",
                value=self.bot.config['vault']['brief_msg'],
                inline=False
            )
            embed.add_field(
                name="NOTE",
                value=self.bot.config['vault']['note_msg'],
                inline=False
            )
            embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
            embed.set_thumbnail(url=self.bot.user.display_avatar)
            await ctx.edit_original_message(content=None, embed=embed)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @vault.sub_command(
        name="view",
        usage="vault view",
        description="View your /vault."
    )
    async def vault_view(
        self,
        ctx
    ):
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /vault loading..."
        await ctx.response.send_message(msg, ephemeral=True)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/vault view", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            embed = disnake.Embed(
                title="Your TipBot's Vault",
                description=f"{ctx.author.mention}, You can join our supported guild for #help.",
                timestamp=datetime.now(),
            )
            embed.add_field(
                name="Supported coins",
                value=", ".join(self.bot.config['vault']['enable_vault']),
                inline=False
            )
            get_user_vaults = await get_a_user_vault_list(str(ctx.author.id), SERVER_BOT)
            if len(get_user_vaults) == 0:
                embed.add_field(
                    name="Your vault",
                    value="Empty",
                    inline=False
                )
            else:
                coin_list = [i['coin_name'] for i in get_user_vaults]
                embed.add_field(
                    name="Your vault",
                    value=", ".join(coin_list),
                    inline=False
                )
            embed.add_field(
                name="NOTE",
                value=self.bot.config['vault']['note_msg'],
                inline=False
            )
            embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
            embed.set_thumbnail(url=self.bot.user.display_avatar)
            disable_update = True
            disable_withdraw = True
            disable_viewkey = True
            selected_coin = None
            view = VaultMenu(self.bot, ctx, ctx.author.id, embed, self.bot.config['vault']['enable_vault'], selected_coin, disable_update, disable_withdraw, disable_viewkey)
            await ctx.edit_original_message(content=None, embed=embed, view=view)
        except Exception:
            traceback.print_exc(file=sys.stdout)

def setup(bot):
    bot.add_cog(Vault(bot))
