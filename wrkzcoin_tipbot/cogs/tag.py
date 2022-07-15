import re
import sys
import time
import traceback

import disnake
import store
from disnake import TextInputStyle
from disnake.app_commands import Option
from disnake.enums import OptionType
from disnake.ext import commands


# TODO: add back itag for media


class database_tag():
    async def sql_tag_by_server(self, server_id: str, tag_id: str = None):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if tag_id is None:
                        sql = """ SELECT * FROM `discord_tag` WHERE `tag_serverid` = %s """
                        await cur.execute(sql, (server_id,))
                        result = await cur.fetchall()
                        tag_list = result
                        return tag_list
                    else:
                        try:
                            sql = """ SELECT `tag_id`, `tag_desc`, `date_added`, `tag_serverid`, `added_byname`, 
                                      `added_byuid`, `num_trigger` FROM `discord_tag` WHERE `tag_serverid` = %s AND `tag_id`=%s """
                            await cur.execute(sql, (server_id, tag_id,))
                            result = await cur.fetchone()
                            if result: return result
                        except Exception:
                            traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def sql_tag_by_server_add(self, server_id: str, tag_id: str, tag_desc: str, added_byname: str,
                                    added_byuid: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT COUNT(*) FROM `discord_tag` WHERE `tag_serverid`=%s """
                    await cur.execute(sql, (server_id,))
                    counting = await cur.fetchone()
                    if counting:
                        if counting['COUNT(*)'] > 50:
                            return None
                    sql = """ SELECT `tag_id`, `tag_desc`, `date_added`, `tag_serverid`, `added_byname`, `added_byuid`, 
                              `num_trigger` 
                              FROM discord_tag WHERE tag_serverid = %s AND tag_id=%s """
                    await cur.execute(sql, (server_id, tag_id.upper(),))
                    result = await cur.fetchone()
                    if result is None:
                        sql = """ INSERT INTO `discord_tag` (`tag_id`, `tag_desc`, `date_added`, `tag_serverid`, 
                                  `added_byname`, `added_byuid`) 
                                  VALUES (%s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (
                        tag_id.upper(), tag_desc, int(time.time()), server_id, added_byname, added_byuid,))
                        await conn.commit()
                        return tag_id.upper()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def sql_tag_by_server_del(self, server_id: str, tag_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT `tag_id`, `tag_desc`, `date_added`, `tag_serverid`, `added_byname`, 
                              `added_byuid`, `num_trigger` 
                              FROM `discord_tag` WHERE `tag_serverid` = %s AND `tag_id`=%s """
                    await cur.execute(sql, (server_id, tag_id.upper(),))
                    result = await cur.fetchone()
                    if result:
                        sql = """ DELETE FROM `discord_tag` WHERE `tag_id`=%s AND `tag_serverid`=%s """
                        await cur.execute(sql, (tag_id.upper(), server_id,))
                        await conn.commit()
                        return tag_id.upper()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None


class ModTagGuildAdd(disnake.ui.Modal):
    def __init__(self) -> None:
        components = [
            disnake.ui.TextInput(
                label="Tag name",
                placeholder="A short name",
                custom_id="tag_name",
                style=TextInputStyle.short,
                max_length=32
            ),
            disnake.ui.TextInput(
                label="Description",
                placeholder="What you want it to display for a tag call",
                custom_id="tag_desc",
                style=TextInputStyle.paragraph
            ),
        ]
        super().__init__(title="Add a new tag to guild", custom_id="modal_add_tag", components=components)

    async def callback(self, inter: disnake.ModalInteraction) -> None:
        # Check if type of question is bool or multipe
        tag_name = inter.text_values['tag_name'].strip()
        tag_desc = inter.text_values['tag_desc'].strip()
        if tag_name == "":
            await inter.response.send_message("Tag name is empty!", ephemeral=False)
            return
        elif re.match('^[a-zA-Z0-9]+(-[a-zA-Z0-9]+)*$', tag_name):
            if tag_desc == "" or len(tag_desc) <= 3:
                await inter.response.send_message(f"{inter.author.mention}, tag description is empty or too short!",
                                                  ephemeral=False)
                return

            tagging = database_tag()
            # Check if tag already exist!
            ListTag = await tagging.sql_tag_by_server(str(inter.guild.id), None)
            if len(ListTag) > 0:
                d = [i['tag_id'] for i in ListTag]
                if tag_name.upper() in d:
                    await inter.response.send_message(f"{inter.author.mention}, tag `{tag_name}` already exists here.")
                    return
            # Let's add
            addTag = await tagging.sql_tag_by_server_add(str(inter.guild.id), tag_name, tag_desc, inter.author.name,
                                                         str(inter.author.id))
            if addTag is None:
                await inter.response.send_message(f"{inter.author.mention}, failed to add tag `{tag_name}`.")
            if addTag.upper() == tag_name.upper():
                await inter.response.send_message(f"{inter.author.mention}, successfully added tag `{tag_name}`.")
            else:
                await inter.response.send_message(f"{inter.author.mention}, failed to add tag `{tag_name}`.")
        else:
            await inter.response.send_message(f"{inter.author.mention}, tag `{tag_name}` is not valid.")


class Tag(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.guild_only()
    @commands.slash_command(description="Manage or display tag(s).")
    async def tag(self, ctx):
        # Check if tag available
        pass

    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @tag.sub_command(
        usage="tag add",
        description="Add a tag to the guild."
    )
    async def add(
            self,
            ctx
    ):
        await ctx.response.send_modal(modal=ModTagGuildAdd())

    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @tag.sub_command(
        usage="tag delete <tag_name>",
        options=[
            Option('tag_name', 'tag_name', OptionType.string, required=True)
        ],
        description="Remove a tag from the guild."
    )
    async def delete(
            self,
            ctx,
            tag_name: str
    ):
        if re.match('^[a-zA-Z0-9]+(-[a-zA-Z0-9]+)*$', tag_name):
            tag = tag_name.upper()
            tagging = database_tag()
            delTag = await tagging.sql_tag_by_server_del(str(ctx.guild.id), tag.strip())
            if delTag is None:
                await ctx.response.send_message(f"{ctx.author.mention}, failed to delete tag `{tag_name}`.")
            elif delTag.upper() == tag.upper():
                await ctx.response.send_message(f"{ctx.author.mention}, successfully deleted tag `{tag_name}`.")
            else:
                await ctx.response.send_message(f"{ctx.author.mention}, failed to delete tag `{tag_name}`.")
        else:
            await ctx.response.send_message(f"{ctx.author.mention}, tag `{tag_name}` is not valid.")

    @commands.guild_only()
    @tag.sub_command(
        usage="tag show <tag_name>",
        options=[
            Option('tag_name', 'tag_name', OptionType.string, required=False)
        ],
        description="Show a saved tag."
    )
    async def show(
            self,
            ctx,
            tag_name: str = None
    ):
        tagging = database_tag()
        if tag_name is None:
            ListTag = await tagging.sql_tag_by_server(str(ctx.guild.id), None)
            if len(ListTag) > 0:
                tags = (', '.join([w['tag_id'] for w in ListTag])).lower()
                await ctx.response.send_message(f"{ctx.author.mention}, available tag:```{tags}```")
            else:
                await ctx.response.send_message(f"{ctx.author.mention}, there is not any tag in this server.")
        else:
            TagIt = await tagging.sql_tag_by_server(str(ctx.guild.id), tag_name.upper())
            if TagIt:
                tagDesc = TagIt['tag_desc'].replace("\n", "\r\n")
                try:
                    await ctx.response.send_message(f"{ctx.author.mention}, `{tag_name}`:\n{tagDesc}")
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            else:
                await ctx.response.send_message(f"{ctx.author.mention}, there is no tag `{tag_name}` in this server.")


def setup(bot):
    bot.add_cog(Tag(bot))
