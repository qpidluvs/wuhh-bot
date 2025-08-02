from aiohttp import web
import discord
from discord import app_commands, ui, Interaction, SelectOption
from discord.ext import commands
import asyncio
import sqlite3
import os

QUEUE_CHANNEL_ID = 1400893779648577536
STICKY_CHANNEL_ID = 1349182117040488502
SPECIAL_ROLE_ID = 1334217816039231593
ROLE_ID = 1336063813123965020
EMBED_COLOR = discord.Color(int("FFFFFF", 16))
CARD_FOLDER = "./cards"
DB_FILE = "punches.sqlite"

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

        self.conn = sqlite3.connect(DB_FILE)
        self.c = self.conn.cursor()
        self.c.execute('''
            CREATE TABLE IF NOT EXISTS punches (
                user_id TEXT PRIMARY KEY,
                count INTEGER NOT NULL
            )
        ''')
        self.conn.commit()

        self.sticky_message = None
        self.sticky_message_id = None

    def get_punches(self, user_id):
        self.c.execute("SELECT count FROM punches WHERE user_id = ?", (str(user_id),))
        row = self.c.fetchone()
        return row[0] if row else 0

    def add_punch(self, user_id):
        punches = self.get_punches(user_id)
        punches += 1
        if punches > 8:
            punches = 8
        self.c.execute("INSERT OR REPLACE INTO punches (user_id, count) VALUES (?, ?)", (str(user_id), punches))
        self.conn.commit()
        return punches

    async def setup_hook(self):
        await self.tree.sync()
        self.loop.create_task(self.ensure_sticky_message())

    async def on_ready(self):
        print(f"Logged in as {self.user} ({self.user.id})")

    async def ensure_sticky_message(self):
        await self.wait_until_ready()
        channel = self.get_channel(STICKY_CHANNEL_ID)
        if not channel:
            print("Sticky channel not found")
            return

        sticky_embed = discord.Embed(
            color=EMBED_COLOR,
            description=(
                "<:00000004whitepaw_cxa:1372680035710009454> <:000_hrt:1371303750937083904> How To Vouch <:000_hrt:1371303750937083904> <:00000004whitepaw_cxa:1372680035710009454>\n\n"
                f"Vouch <@{SPECIAL_ROLE_ID}> {{what you bought}} and any comments u might have about ur service\n\n"
                "<:00000004whitepaw_cxa:1372680035710009454> <a:white_stars:1372469592764715060> Thank You for your patience <a:white_stars:1372469592764715060> <:00000004whitepaw_cxa:1372680035710009454>\n"
                "<a:Z_arrow_white:1372469533817966643>                 Please purchase soon again"
            )
        )
        sticky_embed.set_author(name="/wuhh")

        async for msg in channel.history(limit=50):
            if msg.author == self.user and msg.embeds:
                embed = msg.embeds[0]
                if embed.description == sticky_embed.description:
                    self.sticky_message = msg
                    self.sticky_message_id = msg.id
                    break

        if not self.sticky_message:
            self.sticky_message = await channel.send(embed=sticky_embed)
            self.sticky_message_id = self.sticky_message.id

        self.loop.create_task(self.monitor_sticky(channel, sticky_embed))

    async def monitor_sticky(self, channel, sticky_embed):
        await self.wait_until_ready()
        while not self.is_closed():
            await asyncio.sleep(5)
            messages = [m async for m in channel.history(limit=10)]

            for msg in messages:
                if msg.author == self.user and msg.id != self.sticky_message_id:
                    try:
                        await msg.delete()
                    except:
                        pass

            last_msg = messages[0] if messages else None
            if last_msg and last_msg.id != self.sticky_message_id:
                try:
                    new_msg = await channel.send(embed=sticky_embed)
                    try:
                        await self.sticky_message.delete()
                    except:
                        pass
                    self.sticky_message = new_msg
                    self.sticky_message_id = new_msg.id
                except:
                    pass

bot = MyBot()

class StatusDropdown(ui.Select):
    def __init__(self):
        options = [
            SelectOption(label="𒌲 ๋๋อะรรร need uploading", value="**Need uploading**"),
            SelectOption(label="𒌲 ๋๋อะรรร done", value="**Done**")
        ]
        super().__init__(placeholder="Update ticket status...", options=options)

    async def callback(self, interaction: Interaction):
        if not any(role.id == ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("You don't have permission to update the status.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        lines = embed.description.split("\n")
        lines[-1] = f"<:000bow:1371303813536940084> Ticket status : {self.values[0]}"
        embed.description = "\n".join(lines)

        await interaction.response.edit_message(embed=embed, view=self.view)

class StatusView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(StatusDropdown())

class QueueCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="queue", description="add an order to the queue")
    @app_commands.describe(customer="The customer this ticket is for", product="Product bought", payment="Payment method")
    async def queue(self, interaction: Interaction, customer: discord.User, product: str, payment: str):
        if not any(role.id == ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("You can't use this command.", ephemeral=True)
            return

        embed = discord.Embed(title="queue status", color=EMBED_COLOR)
        embed.description = (
            f"<:000bow:1371303813536940084> Customer : {customer.mention}\n"
            f"<:000bow:1371303813536940084> Ticket : {interaction.channel.mention}\n"
            f"<:000bow:1371303813536940084> Product bought : **{product}**\n"
            f"<:000bow:1371303813536940084> Payment : **{payment}**\n"
            f"<:000bow:1371303813536940084> Ticket status : **Pending**"
        )

        await interaction.response.send_message(embed=embed, view=StatusView())

async def handle(request):
    return web.Response(text="Bot is running")

port = int(os.getenv("PORT", 8080))
app = web.Application()
app.add_routes([web.get('/', handle)])

async def main():
    await bot.add_cog(QueueCommand(bot))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server running on port {port}")

    await bot.start(os.getenv("DISCORD_TOKEN"))

asyncio.run(main())
