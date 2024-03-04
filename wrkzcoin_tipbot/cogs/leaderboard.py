import sys
import traceback
from datetime import datetime
from decimal import Decimal
import time
import disnake
from disnake.app_commands import Option
from disnake.enums import OptionType
from disnake.ext import commands
from cogs.utils import Utils, num_format_coin
from cogs.wallet import WalletAPI
from Bot import SERVER_BOT


class DropdownViewLeaderboard(disnake.ui.StringSelect):
    def __init__(
            self, ctx, bot, embed,
            menu: str="tipper",
            selected_duration: str="1d",
            token_name: str="WRKZ"
        ):
        """
        selected_duration: 1d, 7d, 30d, 180d
        """
        self.ctx = ctx
        self.bot = bot
        self.embed = embed
        self.menu = menu
        self.selected_duration = selected_duration
        self.token_name = token_name
        self.utils = Utils(self.bot)

        options = [
            disnake.SelectOption(
                label=each.lower(), description="Select {}".format(each.lower())
            ) for each in ["1d", "7d", "30d", "180d", "365d", "all time"]
        ]

        super().__init__(
            placeholder=self.selected_duration,
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, inter: disnake.MessageInteraction):
        if inter.author.id != self.ctx.user.id:
            await inter.response.defer()
            return
        else:
            await inter.response.defer(ephemeral=True)
            self.embed.clear_fields()
            embed = self.embed.copy()
            lap = 0
            if self.values[0] != "all time":
                lap = int(self.values[0].replace("d", "")) * 3600 * 24
            if self.menu == "tipper":
                get_leaderboard = await self.utils.get_tipper_leaderboard(str(inter.guild.id), self.token_name, lap)
            elif self.menu == "receiver":
                get_leaderboard = await self.utils.get_receiver_leaderboard(str(inter.guild.id), self.token_name, lap)
            if get_leaderboard and len(get_leaderboard) > 0:
                embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar)
                list_tippers = []
                count = 1
                index_name = "from_userid"
                if self.menu == "receiver":
                    index_name = "to_userid"
                for i, tipper in enumerate(get_leaderboard[0:25], start=1):
                    if int(tipper[index_name]) == self.bot.user.id:
                        continue
                    list_tippers.append("{}) <@{}>: {} {}".format(
                        count, tipper[index_name], num_format_coin(tipper['sum_tip']), self.token_name
                    ))
                    count += 1
                    if count > 20:
                        break
                embed.add_field(
                    name="Top Tippers" if self.menu == "tipper" else "Top Receivers",
                    value="{}".format("\n".join(list_tippers)),
                    inline=False
                )
                embed.set_footer(text="Requested by: {}#{}".format(inter.author.name, inter.author.discriminator))
                view = LeaderboardTipMenu(inter, self.bot, inter.author.id, str(inter.guild.id), self.token_name, embed, self.menu, self.values[0])
                await self.ctx.edit_original_message(content=None, embed=embed, view=view)
            else:
                view = LeaderboardTipMenu(inter, self.bot, inter.author.id, str(inter.guild.id), self.token_name, embed, self.menu, self.values[0])
                await self.ctx.edit_original_message(
                    content=f"{inter.author.mention}, there's no record of {self.token_name.upper()} in guild {inter.guild.name} within selected duration.",
                    embed=None,
                    view=view
                )


class LeaderboardTipMenu(disnake.ui.View):
    def __init__(self, ctx, bot, owner_id: int, guild_id: str, token_name: str, embed, menu: str="tipper", selected_duration: str="1d"):
        super().__init__(timeout=60.0)
        self.bot = bot
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.token_name = token_name
        self.ctx = ctx
        self.selected_duration = selected_duration
        self.embed = embed
        self.utils = Utils(self.bot)
        self.lap = 0
        if selected_duration != "all time":
            self.lap = int(self.selected_duration.replace("d", "")) * 3600 * 24
        self.menu = menu
        if menu == "tipper":
            self.top_tipper.disabled = True
            self.top_receiver.disabled = False
        elif menu == "receiver":
            self.top_tipper.disabled = False
            self.top_receiver.disabled = True

        self.add_item(DropdownViewLeaderboard(
            self.ctx, self.bot, embed, self.menu, self.selected_duration, token_name
        ))

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, disnake.ui.Button) or isinstance(child, disnake.ui.StringSelect):
                child.disabled = True
        await self.ctx.edit_original_message(
            view=self
        )

    @disnake.ui.button(label="Top Tippers", emoji="💸", style=disnake.ButtonStyle.green)
    async def top_tipper(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, this is not your menu!", delete_after=5.0)
        else:
            await inter.response.defer(ephemeral=True)
            get_leaderboard = await self.utils.get_tipper_leaderboard(self.guild_id, self.token_name, self.lap)
            if get_leaderboard and len(get_leaderboard) == 0:
                view = LeaderboardTipMenu(inter, self.bot, inter.author.id, str(inter.guild.id), self.token_name, self.embed, "tipper", self.values[0])
                await self.ctx.edit_original_message(
                    content=f"{inter.author.mention}, there's no record of {self.token_name.upper()} in guild {inter.guild.name} within selected duration.",
                    embed=None,
                    view=view
                )
            elif get_leaderboard and len(get_leaderboard) > 0:
                coin_emoji = getattr(getattr(self.bot.coin_list, self.token_name), "coin_emoji_discord")
                embed = disnake.Embed(
                    title=f"Leaderboard For {inter.guild.name}",
                    description="{}{}{}{}{}{}".format(coin_emoji, coin_emoji, coin_emoji, coin_emoji, coin_emoji, coin_emoji),
                    timestamp=datetime.now()
                )
                if coin_emoji:
                    extension = ".png"
                    if coin_emoji.startswith("<a:"):
                        extension = ".gif"
                    split_id = coin_emoji.split(":")[2]
                    link = 'https://cdn.discordapp.com/emojis/' + str(split_id.replace(">", "")) + extension
                    embed.set_thumbnail(url=link)

                embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar)
                list_tippers = []
                count = 1
                for i, tipper in enumerate(get_leaderboard[0:25], start=1):
                    if int(tipper['from_userid']) == self.bot.user.id:
                        continue
                    list_tippers.append("{}) <@{}>: {} {}".format(
                        count, tipper['from_userid'], num_format_coin(tipper['sum_tip']), self.token_name
                    ))
                    count += 1
                    if count > 20:
                        break
                embed.add_field(
                    name="Top Tippers",
                    value="{}".format("\n".join(list_tippers)),
                    inline=False
                )
                embed.set_footer(text="Requested by: {}#{}".format(inter.author.name, inter.author.discriminator))
                view = LeaderboardTipMenu(inter, self.bot, inter.author.id, str(inter.guild.id), self.token_name, embed, "tipper", self.selected_duration)
                await self.ctx.edit_original_message(content=None, embed=embed, view=view)

    @disnake.ui.button(label="Top Receivers", emoji="💰", style=disnake.ButtonStyle.grey)
    async def top_receiver(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, this is not your menu!", delete_after=5.0)
        else:
            await inter.response.defer(ephemeral=True)
            get_leaderboard = await self.utils.get_receiver_leaderboard(self.guild_id, self.token_name, self.lap)
            if get_leaderboard and len(get_leaderboard) == 0:
                view = LeaderboardTipMenu(inter, self.bot, inter.author.id, str(inter.guild.id), self.token_name, self.embed, "receiver", self.values[0])
                await self.ctx.edit_original_message(
                    content=f"{inter.author.mention}, there's no record of {self.token_name.upper()} in guild {inter.guild.name} within selected duration.",
                    embed=None,
                    view=view
                )
            elif get_leaderboard and len(get_leaderboard) > 0:
                coin_emoji = getattr(getattr(self.bot.coin_list, self.token_name), "coin_emoji_discord")
                embed = disnake.Embed(
                    title=f"Leaderboard For {inter.guild.name}",
                    description="{}{}{}{}{}{}".format(coin_emoji, coin_emoji, coin_emoji, coin_emoji, coin_emoji, coin_emoji),
                    timestamp=datetime.now()
                )
                if coin_emoji:
                    extension = ".png"
                    if coin_emoji.startswith("<a:"):
                        extension = ".gif"
                    split_id = coin_emoji.split(":")[2]
                    link = 'https://cdn.discordapp.com/emojis/' + str(split_id.replace(">", "")) + extension
                    embed.set_thumbnail(url=link)

                embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar)
                list_users = []
                count = 1
                for i, tipper in enumerate(get_leaderboard[0:25], start=1):
                    if int(tipper['to_userid']) == self.bot.user.id:
                        continue
                    list_users.append("{}) <@{}>: {} {}".format(
                        count, tipper['to_userid'], num_format_coin(tipper['sum_tip']), self.token_name
                    ))
                    count += 1
                    if count > 20:
                        break
                embed.add_field(
                    name="Top Receivers",
                    value="{}".format("\n".join(list_users)),
                    inline=False
                )
                embed.set_footer(text="Requested by: {}#{}".format(inter.author.name, inter.author.discriminator))
                view = LeaderboardTipMenu(inter, self.bot, inter.author.id, str(inter.guild.id), self.token_name, embed, "receiver", self.selected_duration)
                await self.ctx.edit_original_message(content=None, embed=embed, view=view)

    @disnake.ui.button(label="Close", emoji="❌", style=disnake.ButtonStyle.red)
    async def close(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.owner_id:
            await inter.response.send_message(f"{inter.author.mention}, this is not your menu!", delete_after=5.0)
        else:
            await self.ctx.delete_original_message()

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)

    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @commands.slash_command(
        dm_permission=False,
        usage="leaderboard <token_name>",
        options=[
            Option("token_name", "Enter ticker/name", OptionType.string, required=True),
        ],
        description="Get top tippers/receivers")
    async def leaderboard(
        self,
        ctx,
        token_name: str
    ):
        coin_name = token_name.upper()
        # Token name check
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f"{ctx.author.mention}, **{coin_name}** does not exist with us."
            await ctx.response.send_message(msg)
            return
        # End token name check

        await ctx.response.send_message(f"{ctx.author.mention}, loading leaderboard for **{token_name.upper()}** in guild {ctx.guild.name}.")

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/leaderboard", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Do the job
        try:
            get_leaderboard = await self.utils.get_tipper_leaderboard(str(ctx.guild.id), token_name, 30*24*3600)
            if len(get_leaderboard) == 0:
                await ctx.edit_original_message(content=f"{ctx.author.mention}, there's no record of {token_name.upper()} in guild {ctx.guild.name}.")
                return
            else:
                coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                embed = disnake.Embed(
                    title=f"Leaderboard For {ctx.guild.name}",
                    description="{}{}{}{}{}{}".format(coin_emoji, coin_emoji, coin_emoji, coin_emoji, coin_emoji, coin_emoji),
                    timestamp=datetime.now()
                )
                if coin_emoji:
                    extension = ".png"
                    if coin_emoji.startswith("<a:"):
                        extension = ".gif"
                    split_id = coin_emoji.split(":")[2]
                    link = 'https://cdn.discordapp.com/emojis/' + str(split_id.replace(">", "")) + extension
                    embed.set_thumbnail(url=link)

                embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar)
                list_tippers = []
                count = 1
                for i, tipper in enumerate(get_leaderboard[0:25], start=1):
                    if int(tipper['from_userid']) == self.bot.user.id:
                        continue
                    list_tippers.append("{}) <@{}>: {} {}".format(
                        count, tipper['from_userid'], num_format_coin(tipper['sum_tip']), coin_name
                    ))
                    count += 1
                    if count > 20:
                        break
                embed.add_field(
                    name="Top Tippers",
                    value="{}".format("\n".join(list_tippers)),
                    inline=False
                )
                embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
                view = LeaderboardTipMenu(ctx, self.bot, ctx.author.id, str(ctx.guild.id), coin_name, embed, "tipper", "30d")
                await ctx.edit_original_message(content=None, embed=embed, view=view)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @leaderboard.autocomplete("token_name")
    async def coin_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]

def setup(bot):
    bot.add_cog(Leaderboard(bot))
