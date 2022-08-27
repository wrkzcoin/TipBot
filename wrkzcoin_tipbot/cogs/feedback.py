import time
import traceback
import uuid

import disnake
import store
from Bot import logchanbot, SERVER_BOT
from disnake import TextInputStyle
from disnake.app_commands import Option, OptionChoice
from disnake.enums import OptionType
from disnake.ext import commands

from cogs.utils import Utils


class FeedbackAdd(disnake.ui.Modal):
    inquiry_type: str

    def __init__(self, inquiry_type: str) -> None:
        self.inquiry_type = inquiry_type
        self.utils = Utils(self.bot)
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
    async def sql_feedback_add(self, user_id: str, user_name: str, feedback_id: str, topic: str, feedback_text: str,
                               howto_contact_back: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `discord_feedback` (`user_id`, `user_name`, `feedback_id`, `topic`, `feedback_text`, `feedback_date`, `howto_contact_back`)
                              VALUES (%s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (
                        user_id, user_name, feedback_id, topic, feedback_text, int(time.time()), howto_contact_back))
                    await conn.commit()
                    return True
        except Exception:
            await logchanbot(traceback.format_exc())
        return False

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
        feedback_id = str(uuid.uuid4())
        add = await self.sql_feedback_add(str(inter.author.id),
                                          '{}#{}'.format(inter.author.name, inter.author.discriminator), feedback_id,
                                          topic, desc_id, contact_id)
        if add:
            await inter.response.send_message(
                f'{inter.author.mention} Thank you for your feedback / inquiry. Your feedback ref: **{feedback_id}**')
            try:
                await logchanbot(
                    f'[FEEDBACK] A user {inter.author.mention} / {inter.author.name}#{inter.author.discriminator} has submitted a feedback {feedback_id}')
            except Exception:
                await logchanbot(traceback.format_exc())
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
        usage='feedback',
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
    async def feedback(
            self,
            inter: disnake.AppCmdInter,
            inquiry_type: str
    ) -> None:
        """Sends a Modal to create a new feedback."""
        await inter.response.send_modal(modal=FeedbackAdd(inquiry_type=inquiry_type))


def setup(bot: commands.Bot) -> None:
    bot.add_cog(BotFeedback(bot))
