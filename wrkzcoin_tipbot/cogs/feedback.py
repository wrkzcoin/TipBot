import time
import traceback, sys
import random
from string import ascii_uppercase

from datetime import datetime
import disnake
import store
from Bot import logchanbot, SERVER_BOT, log_to_channel, EMOJI_INFORMATION
from disnake import TextInputStyle
from disnake.app_commands import Option, OptionChoice
from disnake.enums import OptionType
from disnake.ext import commands

from cogs.utils import Utils


# https://stackoverflow.com/questions/312443/how-do-i-split-a-list-into-equally-sized-chunks
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

async def sql_feedback_add(
    user_id: str, user_name: str, feedback_id: str, 
    topic: str, feedback_text: str, howto_contact_back: str
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO `discord_feedback` 
                (`user_id`, `user_name`, `feedback_id`, `topic`, `feedback_text`, `feedback_date`, `howto_contact_back`)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                await cur.execute(sql, (
                    user_id, user_name, feedback_id, topic, 
                    feedback_text, int(time.time()), howto_contact_back
                ))
                await conn.commit()
                return True
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return False

async def sql_feedback_list(
    limit: int=10
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT * FROM `discord_feedback` 
                ORDER BY `feedback_date` DESC LIMIT %s"""
                await cur.execute(sql, limit)
                result = await cur.fetchall()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return []

async def sql_feedback_get(
    ref: str
):
    try:
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT * FROM `discord_feedback` 
                WHERE `feedback_id`=%s LIMIT 1
                """
                await cur.execute(sql, (ref))
                result = await cur.fetchone()
                if result:
                    return result
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return None

class FeedbackAdd(disnake.ui.Modal):
    inquiry_type: str

    def __init__(self, bot, inquiry_type: str) -> None:
        self.inquiry_type = inquiry_type
        self.bot = bot
        components = [
            disnake.ui.TextInput(
                label="Topic",
                placeholder="Some short topic",
                custom_id="topic_id",
                style=TextInputStyle.short,
                max_length=64
            ),
            disnake.ui.TextInput(
                label="Description",
                placeholder="Detail about it",
                custom_id="desc_id",
                style=TextInputStyle.paragraph
            ),
            disnake.ui.TextInput(
                label="Need respond?",
                placeholder="How can we contact you back?",
                custom_id="contact_id",
                style=TextInputStyle.paragraph
            ),
        ]
        super().__init__(title="Feedback/Request our TipBot", custom_id="modal_addtrivia_question",
                         components=components)

    # Feedback

    async def callback(self, inter: disnake.ModalInteraction) -> None:
        # Check if type of question is bool or multiple
        topic = inter.text_values['topic_id'].strip()
        if topic == "":
            await inter.response.send_message("Topic is empty!", ephemeral=True)
            return
        desc_id = inter.text_values['desc_id'].strip()
        if desc_id == "" or len(desc_id) < 8:
            await inter.response.send_message("Description is empty or too short!", ephemeral=True)
            return
        contact_id = inter.text_values['contact_id'].strip()
        if contact_id == "" or len(contact_id) < 4:
            await inter.response.send_message("Contact back is empty or too short!", ephemeral=True)
            return

        # We have enough data, let's add
        feedback_id = ''.join(random.choice(ascii_uppercase) for i in range(8))
        add = await sql_feedback_add(
            str(inter.author.id), '{}#{}'.format(inter.author.name, inter.author.discriminator), 
            feedback_id, topic, desc_id, contact_id
        )
        if add:
            await inter.response.send_message(
                f"{inter.author.mention} Thank you for your feedback / inquiry. "\
                f"Your feedback ref: **{feedback_id}**"
            )
            try:
                await log_to_channel(
                    "feedback",
                    f"[FEEDBACK]: User {inter.author.mention} / {inter.author.name}#{inter.author.discriminator} " \
                    f"has submitted a feedback {feedback_id}\n------------------\n{desc_id}\n------------------\n{contact_id}",
                    self.bot.config['discord']['general_report_webhook']
                )
            except Exception:
                traceback.print_exc(file=sys.stdout)
        else:
            await inter.response.send_message(f"{inter.author.mention}, internal error, please report!")

        try:
            self.bot.commandings.append((str(inter.guild.id) if hasattr(inter, "guild") and hasattr(inter.guild, "id") else "DM",
                                         str(inter.author.id), SERVER_BOT, "/feedback", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)


class BotFeedback(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.slash_command(
        name="feedback",
        description="Various feedback commands and subs."
    )
    async def feedback_main(self, ctx):
        pass

    @feedback_main.sub_command(
        name="list",
        usage='feedback list',
        description='Admin to list all feedback'
    )
    async def feedback_list(
        self,
        ctx
    ) -> None:
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /feedback loading..."
        await ctx.response.send_message(msg, ephemeral=True)
        if ctx.author.id != self.bot.config['discord']['owner_id']:
            await ctx.edit_original_message(content="Permission denied!")
            return
        get_feedbacks = await sql_feedback_list(20)
        if len(get_feedbacks) == 0:
            await ctx.edit_original_message(content="There is no records of feedback!")
            return
        else:
            list_fb = []
            for i in get_feedbacks:
                list_fb.append("topic: {}, ref: {}, from: <@{}>".format(
                    i['topic'], i['feedback_id'], i['user_id']
                ))
            list_chunks = list(chunks(list_fb, 5))
            await ctx.edit_original_message(content="The {} records:".format(len(get_feedbacks)))
            for i in list_chunks:
                list_fb_str = "\n----\n".join(i)
                await ctx.followup.send(list_fb_str)

    @feedback_main.sub_command(
        name="view",
        options=[
            Option('ref', 'reference id', OptionType.string, required=True),
        ],
        usage='feedback view',
        description='Admin to view a feedback'
    )
    async def feedback_view(
        self,
        ctx,
        ref: str,
    ) -> None:
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, /feedback loading..."
        await ctx.response.send_message(msg, ephemeral=True)
        if ctx.author.id != self.bot.config['discord']['owner_id']:
            await ctx.edit_original_message(content="Permission denied!")
            return
        ref = ref.strip()
        get_fb = await sql_feedback_get(ref)
        if get_fb is None:
            await ctx.edit_original_message(content="There is no such feedback `ref`. Check with `/feedback list`!")
            return
        else:
            try:
                embed = disnake.Embed(
                    title="Feedback with TipBot",
                    description="Given by <@{}> ref: {} <t:{}:f>".format(
                        get_fb['user_id'], get_fb['feedback_id'], get_fb['feedback_date']
                    ),
                    timestamp=datetime.now(),
                )
                embed.add_field(
                    name="Topic",
                    value=get_fb['topic'] if get_fb['topic'] else "N/A",
                    inline=False
                )
                embed.add_field(
                    name="Feedback",
                    value=get_fb['feedback_text'],
                    inline=False
                )
                embed.add_field(
                    name="Contact",
                    value=get_fb['howto_contact_back'],
                    inline=False
                )
                embed.set_footer(text="Requested by: {}#{}".format(ctx.author.name, ctx.author.discriminator))
                embed.set_thumbnail(url=self.bot.user.display_avatar)
                await ctx.edit_original_message(content=None, embed=embed)
            except Exception:
                traceback.print_exc(file=sys.stdout)

    @feedback_main.sub_command(
        name="add",
        usage='feedback add',
        options=[
            Option('inquiry_type', 'inquiry_type', OptionType.string, required=True, choices=[
                OptionChoice("General Help", "General Help"),
                OptionChoice("Deposit/Withdraw issue", "Deposit/Withdraw issue"),
                OptionChoice("Tipping Issue", "Tipping Issue"),
                OptionChoice("Suggest a New Coin", "Suggest a New Coin"),
                OptionChoice("Bug Report", "Bug Report"),
                OptionChoice("Others", "Others")
            ])
        ],
        description='Give feedback/comment/request'
    )
    async def feedback_add(
        self,
        ctx,
        inquiry_type: str
    ) -> None:
        """Sends a Modal to create a new feedback."""
        try:
            await ctx.response.send_modal(modal=FeedbackAdd(self.bot, inquiry_type=inquiry_type))
        except Exception:
            traceback.print_exc(file=sys.stdout)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(BotFeedback(bot))
