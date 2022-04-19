import sys, traceback
from datetime import datetime, timedelta

import disnake
from disnake.ext import commands

from disnake.enums import OptionType
from disnake.app_commands import Option

from Bot import logchanbot
from utils import MenuPage


class Core(commands.Cog):
    """Houses core commands & listeners for the bot"""

    def __init__(self, bot):
        self.bot = bot


    @commands.user_command()
    async def ping(self, ctx):
        await ctx.response.send_message(f"Pong! ({self.bot.latency*1000}ms)", ephemeral=True)


    async def async_uptime(self, ctx):
        uptime_seconds = round((datetime.now() - self.bot.start_time).total_seconds())
        msg = f"Current Uptime: {'{:0>8}'.format(str(timedelta(seconds=uptime_seconds)))}"
        if type(ctx) == disnake.ApplicationCommandInteraction:
            await ctx.response.send_message(content=msg)
        else:
            await ctx.reply(content=msg)


    @commands.slash_command(
        usage="uptime",
        description="Tells how long the bot has been running."
    )
    async def uptime(
        self, 
        ctx
    ):
        return await self.async_uptime(ctx)


    async def async_help(self, ctx, cmd):
        all_slash_cmds = [cmd for cmd in self.bot.all_slash_commands]
        slash_help = {
            "about": {
                "usage": "/about",
                "desc": "Check information about TipBot.", 
                "related": ["invite", "feedback", "uptime"],
                "subcmd": []
            },
            "rand": {
                "usage": "/rand <min>-<max>",
                "desc": "Generate a random number between two numbers.", 
                "related": ["cal"],
                "subcmd": []
            },
            "cal": {
                "usage": "/cal <math expression>",
                "desc": "Use TipBot's built-in calculator.", 
                "related": ["rand"],
                "subcmd": []
            },
            "stats": {
                "usage": "/stats <coin_name>",
                "desc": "Show statistic about coin.", 
                "related": ["coininfo"],
                "subcmd": []
            },
            "notifytip": {
                "usage": "/notifytip ON|OFF",
                "desc": "Turn tip notification or ping ON or OFF.", 
                "related": [],
                "subcmd": []
            },
            "randtip": {
                "usage": "/randtip <amount> <coin>",
                "desc": "Tip to a ranndom discord users from your balance.", 
                "related": ["tip", "tipall"],
                "subcmd": []
            },
            "freetip": {
                "usage": "/freetip <amount> <coin> <duration> [comment]",
                "desc": "Do airdrop with clickable buttom and every can collect.", 
                "related": ["tip", "tipall", "mathtip", "triviatip"],
                "subcmd": []
            },
            "tipall": {
                "usage": "/tipall <amount> <coin> [online|all]",
                "desc": "Tip all online users or every users in the guild from your balance.", 
                "related": ["tip", "randtip", "randtip"],
                "subcmd": []
            },
            "feedback": {
                "usage": "/feedback",
                "desc": "Give us your feedback and other comment, suggestion for TipBot.", 
                "related": ["about", "invite", "uptime"],
                "subcmd": []
            },
            "triviatip": {
                "usage": "/triviatip <amount> <coin> <duration>",
                "desc": "Drop a Trivia Tip to discord users in the guild.", 
                "related": ["mathtip", "freetip"],
                "subcmd": []
            },
            "deposit": {
                "usage": "/deposit <coin> [plain]",
                "desc": "Get your deposit address.", 
                "related": ["withdraw", "coininfo"],
                "subcmd": []
            },
            "balance": {
                "usage": "/balance <coin>",
                "desc": "Show a coin's balance.", 
                "related": ["balances", "coininfo"],
                "subcmd": []
            },
            "balances": {
                "usage": "/balances [coin1, coin2]",
                "desc": "Show your coins' balances. Without coin names, it will show you all balances.", 
                "related": ["balance", "deposit", "coininfo"],
                "subcmd": []
            },
            "withdraw": {
                "usage": "/withdraw <amount> <coin> <address>",
                "desc": "Withdraw to an address.", 
                "related": ["deposit", "coininfo"],
                "subcmd": []
            },
            "claim": {
                "usage": "/claim [coin]",
                "desc": "Show reward amount for TipBpt's voting. Or set <coin> as your preferred reward.", 
                "related": ["take", "faucet"],
                "subcmd": []
            },
            "take": {
                "usage": "/take [info]",
                "desc": "Get a random faucet from TipBot's faucet.", 
                "related": ["claim", "faucet"],
                "subcmd": []
            },
            "donate": {
                "usage": "/donate <amount> <coin>",
                "desc": "Donate from your balance to TipBpt's dev.", 
                "related": ["deposit", "withdraw"],
                "subcmd": []
            },
            "swap": {
                "usage": "/swap <amount> <coin> <to coin>",
                "desc": "Swap from a coin/token to another coin. Only few supported.", 
                "related": ["deposit", "withdraw", "coininfo"],
                "subcmd": []
            },
            "coininfo": {
                "usage": "/coininfo <coin>",
                "desc": "Show information about a coin setting within TipBot.", 
                "related": ["tip", "deposit", "withdraw"],
                "subcmd": []
            },
            "tb": {
                "usage": "/tb <action> [member]",
                "desc": "Some images or gif command with other discord member.", 
                "related": [],
                "subcmd": ["draw", "sketchme", "punch", "spank", "slap", "praise", "shoot", "kick", "dance", "fistbump", "getemoji"]
            },
            "paprika": {
                "usage": "/paprika <coin>",
                "desc": "Show a summary of a coin from coinpaprika API.", 
                "related": ["price", "market"],
                "subcmd": []
            },
            "invite": {
                "usage": "/invite",
                "desc": "Show TipBot's invitation link.", 
                "related": ["about", "feedback"],
                "subcmd": []
            },
            "tool": {
                "usage": "/tool [option]",
                "desc": "Some basic tool which rarely used.", 
                "related": ["cal", "rand"],
                "subcmd": []
            },
            "tag": {
                "usage": "/tag show|add|delete",
                "desc": "Tag tool for your discord.", 
                "related": ["guild info"],
                "subcmd": ["avatar", "prime"]
            },
            "coinmap": {
                "usage": "/coinmap",
                "desc": "Fetch screen from coin360", 
                "related": ["price", "paprika"],
                "subcmd": []
            },
            "guild": {
                "usage": "/guild <commands>",
                "desc": "Various guild's command. Type to show them all.", 
                "related": ["guildtip"],
                "subcmd": ["createraffle", "raffle", "balance", "votereward", "deposit", "topgg", "mdeposit", "faucetclaim", "info"]
            },
            "mdeposit": {
                "usage": "/mdeposit <coin>",
                "desc": "Get guild's deposit address.", 
                "related": ["guildtip", "guild balance", "guild info", "guild deposit"],
                "subcmd": []
            },
            "faucet": {
                "usage": "/faucet",
                "desc": "Claim guild's faucet. Only if guild's owner enable this.", 
                "related": ["take", "claim"],
                "subcmd": []
            },
            "setting": {
                "usage": "/setting <commands>",
                "desc": "Various guild's setting command. Type to show them all. For Moderator & Guild owner.", 
                "related": ["guild info", "mdeposit", "guild balance", "guild deposit"],
                "subcmd": ["tiponly", "trade", "nsfw", "game", "botchan", "economychan", "setfaucet", "gamechan"]
            },
            "voucher": {
                "usage": "/voucher <commands>",
                "desc": "Various voucher's command including create, list, etc. Type to show them all.", 
                "related": ["deposit", "balances"],
                "subcmd": ["make", "unclaim", "getunclaim", "claim", "getclaim", "listcoins"]
            },
            "market": {
                "usage": "/market <commands>",
                "desc": "Various market's command including sell, buy, etc. Type to show them all.", 
                "related": ["price", "paprika"],
                "subcmd": ["sell", "myorder", "cancel", "buy", "list", "listcoins", "listpairs"]
            },
            "botbalance": {
                "usage": "/botbalance <bot name> <coin>",
                "desc": "Get a bot's deposit address.", 
                "related": ["balance", "balances"],
                "subcmd": []
            },
            "mathtip": {
                "usage": "/mathtip <amount> <coin> <duration> <math expression>",
                "desc": "Similiar to Trivia Tip, create a math expression to discord users in the guild.", 
                "related": ["triviatip", "freetip"],
                "subcmd": []
            },
            "eco": {
                "usage": "/eco <commands>",
                "desc": "Various economy game's command. Type to show them all. Require TipBot's dev to enable based on guild.", 
                "related": ["guild info"],
                "subcmd": ["info", "items", "sell", "buy", "lumber", "fish", "plant", "collect", "dairy", "chicken", "farm", "harvest", "fish", "fishing", "woodcutting", "search", "eat", "work", "leaderboard", "upgrade"]
            },
            "game": {
                "usage": "/game <game name>",
                "desc": "Various game's command. Type to show them all.", 
                "related": ["tb"],
                "subcmd": ["blackjack", "slot", "maze", "dice", "snail", "g2048", "sokoban"]
            },
            "price": {
                "usage": "/price <amount> <coin name>",
                "desc": "Get a price of a coin from coinpaprika API.", 
                "related": ["paprika", "market"],
                "subcmd": []
            },
            "pools": {
                "usage": "/pools <coin name>",
                "desc": "Get miningpoolstats of a mineable coin.", 
                "related": ["coininfo"],
                "subcmd": []
            },
            "userinfo": {
                "usage": "/userinfo [@user]",
                "desc": "Get some basic information of a user.", 
                "related": [],
                "subcmd": []
            },
            "uptime": {
                "usage": "/uptime",
                "desc": "Show bot's uptime.", 
                "related": ["about", "help"],
                "subcmd": []
            },
            "help": {
                "usage": "/help",
                "desc": "This command.", 
                "related": ["about"],
                "subcmd": []
            },
            "tip": {
                "usage": "/tip <amount> <coin> @mention @role | last 10u | last 10mn",
                "desc": "Tip discord users from your balance.", 
                "related": ["tipall", "randtip", "freetip", "mathtip", "triviatip"],
                "subcmd": []
            },
            "guildtip": {
                "usage": "/guildtip <amount> <coin> @mention @role | last 10u | last 10mn",
                "desc": "Tip discord users from guild's balance.", 
                "related": ["tip", "mdeposit", "guild info", "guild deposit"],
                "subcmd": []
            },
            "coinlist": {
                "usage": "/coinlist",
                "desc": "List all coins/tokens within TipBot.", 
                "related": ["coininfo"],
                "subcmd": []
            }
        }
        if cmd is None:
            page = disnake.Embed(title=f"{self.bot.user.name} Help Menu",
                                 description="Thank you for using This TipBot!",
                                 color=disnake.Color.blue(), )
            page.add_field(name="Getting Started",
                           value="For each commands, see `/help command`", inline=False )
            page.add_field(name="All command", value="```{}```".format(", ".join(all_slash_cmds)), inline=False, )
            page.set_thumbnail(url=self.bot.user.display_avatar)
            page.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}")
            await ctx.response.send_message(embed=page)
        elif cmd and cmd not in all_slash_cmds:
            msg = f"{ctx.author.mention}, command `{cmd}` is not available in TipBot."
            await ctx.response.send_message(msg)
        elif cmd and cmd in all_slash_cmds:
            command_usage = slash_help[cmd]['usage']
            command_desc = slash_help[cmd]['desc']
            command_related = None
            sub_command = None
            # sub
            try:
                if len(slash_help[cmd]['subcmd']) > 0:
                    sub_command = ", ".join(slash_help[cmd]['subcmd'])
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            # related
            try:
                if len(slash_help[cmd]['related']) > 0:
                    command_related = ", ".join(slash_help[cmd]['related'])
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            embed = disnake.Embed(
                colour=disnake.Colour.random(),
                title=f"Help for {cmd}",
                timestamp=disnake.utils.utcnow(),
            ).set_footer(
                text=f"Requested by {ctx.author.display_name}",
                icon_url=ctx.author.display_avatar.url,
            )
            embed.add_field(
                name="Usage",
                value="```{}```".format(command_usage),
            )
            embed.add_field(
                name="Description",
                value="```{}```".format(command_desc),
                inline=False,
            )
            if command_related:
                embed.add_field(
                    name="Related cmd(s)",
                    value="```{}```".format(command_related),
                    inline=False,
                )
            if sub_command:
                embed.add_field(
                    name="Sub cmd(s)",
                    value="```{}```".format(sub_command),
                    inline=False,
                )
            await ctx.response.send_message(embed=embed)
            

    @commands.slash_command(
        usage="help [command]",
        options=[
            Option('command', 'command', OptionType.string, required=False)
        ],
        description="Help with TipBot various commands."
    )
    async def help(
        self, 
        ctx, 
        command: str=None
    ):
        return await self.async_help(ctx, command)


def setup(bot):
    bot.add_cog(Core(bot))
