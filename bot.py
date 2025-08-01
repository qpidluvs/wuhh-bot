from aiohttp import web
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import sqlite3
import os

QUEUE_CHANNEL_ID = 1400893779648577536
STICKY_CHANNEL_ID = 1349182117040488502
SPECIAL_ROLE_ID = 1334217816039231593  # Role that can check other users' cards
EMBED_COLOR = discord.Color(int("FFFFFF", 16))
CARD_FOLDER = "./cards"  # Your cards folder path
DB_FILE = "punches.sqlite"

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="/", intents=intents)

        # Setup SQLite
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
            punches = 8  # max 8 punches
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

@bot.tree.command(name="pay", description="Shows payment information")
async def pay(interaction: discord.Interaction):
    embed = discord.Embed(color=EMBED_COLOR)
    embed.description = (
        "**<:00000004whitepaw_cxa:1372680035710009454> Payment**\n\n"
        "<:DNS_Paypal_wuhh:1399149498089078854> **Paypal:** https://www.paypal.me/Sillywuh\n"
        "<:white_arrow112:1372679871494619136> __You must pay with fnf__\n\n"
        "<:DNS_Cashapp_wuhh:1399149573045485779> **Cashapp:** https://cash.app/$Sillywuh\n\n"
        "<:000_dotwhite:1371303745710723173> Make sure to send the correct amount\n"
        "<:000_dotwhite:1371303745710723173> Provide proof of payment once done <a:6D_princess:1371321502917722223>"
    )
    await interaction.response.send_message(embed=embed, ephemeral=False)

@app_commands.describe(user="User to show card for (only owner can use this)")
@bot.tree.command(name="card", description="Show your loyalty card")
async def card(interaction: discord.Interaction, user: discord.User = None):
    user = user or interaction.user

    if user != interaction.user:
        member = interaction.guild.get_member(interaction.user.id)
        if member is None or SPECIAL_ROLE_ID not in [role.id for role in member.roles]:
            await interaction.response.send_message("You don't have permission to check others' cards.", ephemeral=True)
            return

    punches = bot.get_punches(user.id)
    punches = max(0, min(punches, 8))  # Clamp punches between 0 and 8

    if punches == 0:
        await interaction.response.send_message(f"{user.name} has no punches yet.", ephemeral=True)
        return

    image_path = os.path.join(CARD_FOLDER, f"card_{punches}.webp")
    filename = f"card_{punches}.webp"

    if not os.path.exists(image_path):
        await interaction.response.send_message("Card image not found.", ephemeral=True)
        return

    file = discord.File(image_path, filename=filename)
    embed = discord.Embed(
        title=f"{user.name}'s Loyalty Card <:00000004whitepaw_cxa:1372680035710009454>",
        description=f"Punches: {punches}/8",
        color=EMBED_COLOR
    )
    embed.set_image(url=f"attachment://{filename}")

    await interaction.response.send_message(embed=embed, file=file, ephemeral=False)

@bot.tree.command(name="punch", description="Add a punch to a user")
@app_commands.describe(member="User to punch")
async def punch(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("You don’t have permission.", ephemeral=True)
        return

    punches = bot.add_punch(member.id)
    await interaction.response.send_message(f"<:ppawl:1372679923738607727> Gave a punch to {member.mention}. They now have {punches}/8 punches! <a:0kawaiiSparkles:1371321399955689523>")

@bot.tree.command(name="reset", description="Reset a user's loyalty card punches")
@app_commands.describe(member="User whose punches to reset")
async def reset(interaction: discord.Interaction, member: discord.Member):
    # Check if the user has the special role
    guild_member = interaction.guild.get_member(interaction.user.id)
    if guild_member is None or SPECIAL_ROLE_ID not in [role.id for role in guild_member.roles]:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    # Reset punches to zero
    bot.c.execute("INSERT OR REPLACE INTO punches (user_id, count) VALUES (?, ?)", (str(member.id), 0))
    bot.conn.commit()

    await interaction.response.send_message(f"Reset punches for {member.mention}.", ephemeral=True)

from discord import ui, Interaction, SelectOption
from discord.ext import commands

class QueueStatusView(ui.View):
    def __init__(self, original_embed, message):
        super().__init__(timeout=None)
        self.original_embed = original_embed
        self.message = message

        # Dropdown setup
        self.add_item(QueueStatusDropdown(self.original_embed, self.message))

class QueueStatusDropdown(ui.Select):
    def __init__(self, embed, message):
        self.embed = embed
        self.message = message
        options = [
            SelectOption(label="𓏲 ๋࣭ need uploading", value="Need uploading"),
            SelectOption(label="𓏲 ๋࣭ done", value="Done"),
        ]
        super().__init__(placeholder="Update ticket status", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        # Permission check
        member = interaction.guild.get_member(interaction.user.id)
        if not member or SPECIAL_ROLE_ID not in [role.id for role in member.roles]:
            await interaction.response.send_message("You can’t change the queue status.", ephemeral=True)
            return

        # Update embed
        new_status = f"**{self.values[0]}**"
        lines = self.embed.description.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("<:000bow:1371303813536940084> Ticket status :"):
                lines[i] = f"<:000bow:1371303813536940084> Ticket status : {new_status}"
                break
        self.embed.description = "\n".join(lines)

        await self.message.edit(embed=self.embed, view=self.view)
        await interaction.response.send_message(f"Status updated to {new_status}", ephemeral=True)

@bot.tree.command(name="q", description="Add an order to the queue")
@app_commands.describe(product_bought="What did they buy?", payment="How did they pay?")
async def queue(interaction: discord.Interaction, product_bought: str, payment: str):
    member = interaction.guild.get_member(interaction.user.id)
    if not member or SPECIAL_ROLE_ID not in [role.id for role in member.roles]:
        await interaction.response.send_message("You don’t have permission to use this command.", ephemeral=True)
        return

    queue_channel = bot.get_channel(QUEUE_CHANNEL_ID)
    if queue_channel is None:
        await interaction.response.send_message("Queue channel not found.", ephemeral=True)
        return

    embed = discord.Embed(
        title="queue status",
        description=(
            f"<:000bow:1371303813536940084> Customer : {interaction.user.mention}\n"
            f"<:000bow:1371303813536940084> Ticket : {interaction.channel.mention}\n"
            f"<:000bow:1371303813536940084> Product bought : **{product_bought}**\n"
            f"<:000bow:1371303813536940084> Payment : **{payment}**\n"
            f"<:000bow:1371303813536940084> Ticket status : **Pending**"
        ),
        color=EMBED_COLOR
    )
    msg = await queue_channel.send(embed=embed)
    view = QueueStatusView(embed, msg)
    await msg.edit(view=view)
    await interaction.response.send_message(f"Queue added in {queue_channel.mention}.", ephemeral=True)

async def handle(request):
    return web.Response(text="Bot is running")

port = int(os.getenv("PORT", 8080))
app = web.Application()
app.add_routes([web.get('/', handle)])

async def main():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server running on port {port}")

    await bot.start(os.getenv("DISCORD_TOKEN"))

asyncio.run(main())
