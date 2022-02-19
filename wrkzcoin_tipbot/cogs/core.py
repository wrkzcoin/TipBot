import sys
import traceback
from datetime import datetime, timedelta

import disnake
from disnake.ext import commands

from Bot import logchanbot
from utils import MenuPage


class Core(commands.Cog):
    """Houses core commands & listeners for the bot"""

    def __init__(self, bot):
        self.bot = bot


    @commands.command(usage="uptime", description="Tells how long the bot has been running.")
    async def uptime(self, ctx):
        uptime_seconds = round((datetime.now() - self.bot.start_time).total_seconds())
        await ctx.reply(f"Current Uptime: {'{:0>8}'.format(str(timedelta(seconds=uptime_seconds)))}")


    @commands.bot_has_permissions(add_reactions=True)
    @commands.command(usage="help [command/cog]",
                      aliases=["h"], description="Shows the help menu or information for a specific command or cog when specified.")
    async def help(self, ctx, *, opt: str = None):
        if opt:
            cog = self.bot.get_cog(opt.capitalize())
            if not cog:
                command = self.bot.get_command(opt.lower())
                if not command:
                    return await ctx.reply(
                        embed=disnake.Embed(description=f"That command/cog does not exist. Use `{ctx.prefix}help` to see all the commands.",
                                            color=disnake.Color.red(), ))

                embed = disnake.Embed(title=command.name, description=command.description, colour=disnake.Color.blue())
                usage = "\n".join([ctx.prefix + x.strip() for x in command.usage.split("\n")])
                embed.add_field(name="Usage", value=f"```{usage}```", inline=False)
                if len(command.aliases) > 1:
                    embed.add_field(name="Aliases", value=f"`{'`, `'.join(command.aliases)}`")
                elif len(command.aliases) > 0:
                    embed.add_field(name="Alias", value=f"`{command.aliases[0]}`")
                return await ctx.reply(embed=embed)
            cog_commands = cog.get_commands()
            embed = disnake.Embed(title=opt.capitalize(), description=f"{cog.description}\n\n`<>` Indicates a required argument.\n"
                                                                      "`[]` Indicates an optional argument.\n", color=disnake.Color.blue(), )
            embed.set_author(name=f"{self.bot.user.name} Help Menu", icon_url=self.bot.user.display_avatar)
            embed.set_thumbnail(url=self.bot.user.display_avatar)
            embed.set_footer(
                text=f"Use {ctx.prefix}help <command> for more information on a command.")
            for cmd in cog_commands:
                if cmd.hidden is False:
                    name = ctx.prefix + cmd.usage
                    if len(cmd.aliases) > 1:
                        name += f" | Aliases – `{'`, `'.join([ctx.prefix + a for a in cmd.aliases])}`"
                    elif len(cmd.aliases) > 0:
                        name += f" | Alias – {ctx.prefix + cmd.aliases[0]}"
                    embed.add_field(name=name, value=cmd.description, inline=False)
            return await ctx.reply(embed=embed)

        all_pages = []
        page = disnake.Embed(title=f"{self.bot.user.name} Help Menu",
                             description="Thank you for using This TipBot!",
                             color=disnake.Color.blue(), )
        page.add_field(name="About the bot",
                       value="This bot was built to enable convenient tipping within discord!", inline=False, )
        page.add_field(name="Getting Started",
                       value=f"For a full list of commands, see `{ctx.prefix}help`. Browse through the various commands to get comfortable with using "
                             f"them, and do `{ctx.prefix}help <command>` for more info on specific commands!", inline=False, )
        page.set_thumbnail(url=self.bot.user.display_avatar)
        page.set_footer(text="Use the reactions to flip pages.")
        all_pages.append(page)
        for _, cog_name in enumerate(sorted(self.bot.cogs)):
            if cog_name in ["Owner", "Admin"]:
                continue
            cog = self.bot.get_cog(cog_name)
            cog_commands = cog.get_commands()
            if len(cog_commands) == 0:
                continue
            page = disnake.Embed(title=cog_name, description=f"{cog.description}\n\n`<>` Indicates a required argument.\n"
                                                             "`[]` Indicates an optional argument.\n",
                                 color=disnake.Color.blue(), )
            page.set_author(name=f"{self.bot.user.name} Help Menu", icon_url=self.bot.user.display_avatar)
            page.set_thumbnail(url=self.bot.user.display_avatar)
            page.set_footer(text=f"Use the reactions to flip pages | Use {ctx.prefix}help <command> for more information on a command.")
            for cmd in cog_commands:
                if cmd.hidden is False:
                    name = ctx.prefix + cmd.usage
                    if len(cmd.aliases) > 1:
                        name += f" | Aliases – `{'`, `'.join([ctx.prefix + a for a in cmd.aliases])}`"
                    elif len(cmd.aliases) > 0:
                        name += f" | Alias – `{ctx.prefix + cmd.aliases[0]}`"
                    page.add_field(name=name, value=cmd.description, inline=False)
            all_pages.append(page)
        await ctx.send(embed=all_pages[0], view=MenuPage(ctx, all_pages))


    @commands.command(name='commands', usage="commands", description="View a full list of all available commands.",
                      aliases=["cmd"])
    async def commandlist(self, ctx):
        embed = disnake.Embed(title="Command List", description="A full list of all available commands.\n", color=disnake.Color.teal())
        for _, cog_name in enumerate(sorted(self.bot.cogs)):
            if cog_name in ["Owner", "Admin"]:
                continue
            cog = self.bot.get_cog(cog_name)
            cog_commands = cog.get_commands()
            if len(cog_commands) == 0:
                continue
            cmds = "```yml\n" + ", ".join([ctx.prefix + cmd.name for cmd in cog_commands]) + "```"
            embed.add_field(name=cog.qualified_name + " Commands", value=cmds, inline=False)
        await ctx.reply(embed=embed)


def setup(bot):
    bot.add_cog(Core(bot))
