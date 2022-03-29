import logging
import traceback

import disnake
from disnake.ext import commands

from Bot import logchanbot, RowButton_close_message, RowButton_row_close_any_message


class Error(commands.Cog):
    def __init__(self, client):
        self.client = client


    @commands.Cog.listener()
    async def on_slash_command_error(self, ctx: disnake.ext.commands.Context, error):
        """Handles command errors"""

        error = getattr(error, "original", error)  # get original error

        if isinstance(error, commands.DisabledCommand):
            await ctx.response.send_message(f'{ctx.author.mention} Sorry. This command is disabled and cannot be used.')

        if isinstance(error, commands.MissingPermissions):
            await logchanbot(f"{ctx.author.mention} / {ctx.author.name}#{ctx.author.discriminator} tried {ctx.data.name} but lack of permission [MissingPermissions].")
            return await ctx.response.send_message(f'{ctx.author.mention} Does not have the perms to use this: `{ctx.data.name}` command.')

        if isinstance(error, commands.MissingRole):
            return await ctx.response.send_message(f'{ctx.author.mention}: ' + str(error), view=RowButton_row_close_any_message())

        if isinstance(error, commands.NoPrivateMessage):
            await logchanbot(f"{ctx.author.mention} / {ctx.author.name}#{ctx.author.discriminator} tried {ctx.data.name} in DM.")
            return await ctx.response.send_message(f"{ctx.author.mention} This command cannot be used in a DM.", view=RowButton_row_close_any_message())

        if isinstance(error, commands.CheckFailure) or isinstance(error, commands.CheckAnyFailure):
            await logchanbot(f"{ctx.author.mention} / {ctx.author.name}#{ctx.author.discriminator} tried {ctx.data.name} but lack of permission [CheckAnyFailure].")
            await ctx.response.send_message(f"{ctx.author.mention} You do not have permission to use this command (`{ctx.prefix}{ctx.data.name}`).", view=RowButton_row_close_any_message())  # \nCheck(s) failed: {failed}")
            return

        if isinstance(error, commands.CommandOnCooldown):
            await ctx.response.send_message(
                f"To prevent overload, this command is on cooldown for: ***{round(error.retry_after)}*** more seconds. Retry the command then.",
                delete_after=5)
            return

        if isinstance(error, commands.MaxConcurrencyReached):
            return await ctx.response.send_message(f"The maximum number of concurrent usages of this command has been reached ({error.number}/{error.number})! Please wait until the previous execution of the command `{ctx.prefix}{ctx.data.name}` is completed!")

        if isinstance(error, commands.MissingRequiredArgument):
            embed = disnake.Embed(title="Error!", description="You appear to be missing a required argument!", color=disnake.Color.red())
            embed.add_field(name="Missing argument", value=f'`{error.args[0]}`', inline=False)
            embed.add_field(name="Command Usage", value=f'`{ctx.command.usage}`', inline=False)
            if ctx.command.aliases:
                aliases = "`" + "".join("!" + c + ", " for c in ctx.command.aliases) + "`"
                embed.add_field(name="Command Aliases", value=f"{aliases}", inline=False)
            return await ctx.response.send_message(embed=embed, view=RowButton_row_close_any_message())

        if isinstance(error, commands.BadArgument):
            embed = disnake.Embed(title="Error!", description="An argument you entered is invalid!", color=disnake.Color.red())
            embed.add_field(name="Bad Argument", value=f'`{error.args[0]}`', inline=False)
            embed.add_field(name="Command Usage", value=f'`{ctx.command.usage}`', inline=False)
            if ctx.command.aliases:
                aliases = "`" + "".join("!" + c for c in ctx.command.aliases) + "`"
                embed.add_field(name="Command Aliases", value=f"{aliases}", inline=False)
            return await ctx.response.send_message(embed=embed, view=RowButton_row_close_any_message())

        if isinstance(error, disnake.ext.commands.errors.ExtensionNotLoaded):
            embed = disnake.Embed(title="Error!", description="Cog not found!", color=disnake.Color.red())
            embed.add_field(name="Bad Argument", value=f'`{error.args[0]}`', inline=False)
            embed.add_field(name="Command Usage", value=f'`{ctx.command.usage}`', inline=False)
            embed.add_field(name='Loaded Cogs:', value="".join("`" + c + "`\n" for c in sorted(self.client.cogs)), inline=False)
            return await ctx.response.send_message(embed=embed, view=RowButton_row_close_any_message())

        if isinstance(error, commands.CommandError):
            if ctx.command: return await ctx.response.send_message(f"Unhandled error while executing command `{ctx.data.name}`: {str(error)}", view=RowButton_row_close_any_message())

        logging.error("Ignoring exception in command {}:".format(ctx.data.name))
        logging.error("\n" + "".join(traceback.format_exception(type(error), error, error.__traceback__)))


    @commands.Cog.listener()
    async def on_command_error(self, ctx: disnake.ext.commands.Context, error):
        """Handles command errors"""
        if hasattr(ctx.command, "on_error"):
            return  # Don't interfere with custom error handlers

        error = getattr(error, "original", error)  # get original error

        if isinstance(error, commands.NoPrivateMessage):
            await ctx.reply(f'{ctx.author.mention} This command cannot be used in private messages.')

        elif isinstance(error, commands.DisabledCommand):
            await ctx.reply(f'{ctx.author.mention} Sorry. This command is disabled and cannot be used.')

        if isinstance(error, commands.MissingPermissions):
            return await ctx.reply(f'{ctx.author.mention} Does not have the perms to use this: `{ctx.command.name}` command.')

        if isinstance(error, commands.MissingRole):
            return await ctx.reply(f'{ctx.author.mention}: ' + str(error), view=RowButton_row_close_any_message())

        if isinstance(error, commands.NoPrivateMessage):
            return await ctx.reply(f"{ctx.author.mention} This command cannot be used in a DM.", view=RowButton_row_close_any_message())

        if isinstance(error, commands.CheckFailure) or isinstance(error, commands.CheckAnyFailure):
            await ctx.reply(f"{ctx.author.mention} You do not have permission to use this command (`{ctx.prefix}{ctx.command.name}`).", view=RowButton_row_close_any_message())  # \nCheck(s) failed: {failed}")
            return

        if isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(
                f"To prevent overload, this command is on cooldown for: ***{round(error.retry_after)}*** more seconds. Retry the command then.",
                delete_after=5)
            return

        if isinstance(error, commands.MaxConcurrencyReached):
            return await ctx.reply(f"The maximum number of concurrent usages of this command has been reached ({error.number}/{error.number})! Please wait until the previous execution of the command `{ctx.prefix}{ctx.command.name}` is completed!")

        if isinstance(error, commands.MissingRequiredArgument):
            embed = disnake.Embed(title="Error!", description="You appear to be missing a required argument!", color=disnake.Color.red())
            embed.add_field(name="Missing argument", value=f'`{error.args[0]}`', inline=False)
            embed.add_field(name="Command Usage", value=f'`{ctx.command.usage}`', inline=False)
            if ctx.command.aliases:
                aliases = "`" + "".join("!" + c + ", " for c in ctx.command.aliases) + "`"
                embed.add_field(name="Command Aliases", value=f"{aliases}", inline=False)
            return await ctx.reply(embed=embed, view=RowButton_row_close_any_message())

        if isinstance(error, commands.BadArgument):
            embed = disnake.Embed(title="Error!", description="An argument you entered is invalid!", color=disnake.Color.red())
            embed.add_field(name="Bad Argument", value=f'`{error.args[0]}`', inline=False)
            embed.add_field(name="Command Usage", value=f'`{ctx.command.usage}`', inline=False)
            if ctx.command.aliases:
                aliases = "`" + "".join("!" + c for c in ctx.command.aliases) + "`"
                embed.add_field(name="Command Aliases", value=f"{aliases}", inline=False)
            return await ctx.reply(embed=embed, view=RowButton_row_close_any_message())

        if isinstance(error, disnake.ext.commands.errors.ExtensionNotLoaded):
            embed = disnake.Embed(title="Error!", description="Cog not found!", color=disnake.Color.red())
            embed.add_field(name="Bad Argument", value=f'`{error.args[0]}`', inline=False)
            embed.add_field(name="Command Usage", value=f'`{ctx.command.usage}`', inline=False)
            embed.add_field(name='Loaded Cogs:', value="".join("`" + c + "`\n" for c in sorted(self.client.cogs)), inline=False)
            return await ctx.reply(embed=embed, view=RowButton_row_close_any_message())

        if isinstance(error, commands.CommandError):
            if ctx.command: return await ctx.reply(f"Unhandled error while executing command `{ctx.command.name}`: {str(error)}", view=RowButton_row_close_any_message())

        #logging.error("Ignoring exception in command {}:".format(ctx.command))
        #logging.error("\n" + "".join(traceback.format_exception(type(error), error, error.__traceback__)))


def setup(client):
    client.add_cog(Error(client))
