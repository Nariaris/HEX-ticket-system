import discord
from discord.ext import commands
from discord.ui import Button, View
import io
import json
import os

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
ticket_category_id = None
DATA_FILE = "ticket_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

@bot.event
async def on_ready():
    global ticket_category_id
    print(f"Bot zalogowany jako {bot.user}.")
    data = load_data()
    ticket_category_id = data.get("ticket_category_id")
    if ticket_category_id:
        guild = discord.utils.get(bot.guilds)
        category = discord.utils.get(guild.categories, id=ticket_category_id)
        if category:
            print(f"Załadowano kategorię ticketów: {category.name}")
        else:
            print("Nie znaleziono kategorii, możliwe, że została usunięta.")
    bot.add_view(TicketCreateView())
    try:
        synced = await bot.tree.sync()
        print(f"Successfully synced {len(synced)} commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

class TicketCreateView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Stwórz Ticket", style=discord.ButtonStyle.green, custom_id="create_ticket_button_1")
    async def create_ticket_button(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        global ticket_category_id
        if not ticket_category_id:
            await interaction.response.send_message("System ticketów nie jest poprawnie skonfigurowany.", ephemeral=True)
            return
        category = discord.utils.get(guild.categories, id=ticket_category_id)
        if not category:
            await interaction.response.send_message("Nie znaleziono kategorii ticketów.", ephemeral=True)
            return
        ticket_channel_name = f"ticket-{interaction.user.name.lower()}"
        existing_channel = discord.utils.get(guild.channels, name=ticket_channel_name)
        if existing_channel:
            await interaction.response.send_message("Już masz otwarty ticket!", ephemeral=True)
            return
        ticket_channel = await category.create_text_channel(
            ticket_channel_name,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
        )
        ticket_embed = discord.Embed(
            title=" -> Lorem ipsum <- ",
            description="Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vivamus lacus enim, feugiat vel ligula sit amet, efficitur scelerisque neque. Suspendisse ullamcorper nibh vel diam vulputate scelerisque.",
            color=discord.Color.green()
        )
        ticket_embed.set_footer(text="HEX Tickets")
        ping_button = Button(label="Oznacz administrację!", style=discord.ButtonStyle.red, custom_id=f"ping_admin_{ticket_channel.id}")

        async def ping_callback(interaction: discord.Interaction):
            await ticket_channel.send(f"<@ID_ROLI_ADMINISTRACYJNEJ>, użytkownik {interaction.user.mention} potrzebuje pomocy!")
            ping_button.disabled = True
            await interaction.message.edit(view=ping_view)
            await interaction.response.send_message("Administracja została oznaczona!", ephemeral=True)

        ping_button.callback = ping_callback
        ping_view = View()
        ping_view.add_item(ping_button)
        await ticket_channel.send(embed=ticket_embed, view=ping_view)
        await interaction.response.send_message(f"Stworzyłem Twój ticket: {ticket_channel.mention}", ephemeral=True)

@bot.tree.command(name="setup", description="Tworzy kategorię i kanał do tworzenia ticketów (tylko dla administratorów).")
async def setup(interaction: discord.Interaction):
    guild = interaction.guild
    global ticket_category_id
    if ticket_category_id:
        await interaction.response.send_message("System ticketów jest już skonfigurowany.", ephemeral=True)
        return
    category = await guild.create_category("🎫 Tikety")
    ticket_category_id = category.id
    data = load_data()
    data["ticket_category_id"] = ticket_category_id
    save_data(data)
    ticket_channel = await category.create_text_channel("stwórz-ticket")
    embed = discord.Embed(
        title="LOREM IPSUM",
        description="Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
        color=discord.Color.blue()
    )
    embed.set_footer(text="HEX Tickets")
    view = TicketCreateView()
    await ticket_channel.send(embed=embed, view=view)
    await interaction.response.send_message("System ticketów został skonfigurowany.", ephemeral=True)

@bot.tree.command(name="zamknij", description="Zamyka kanał ticketa po potwierdzeniu (tylko dla administratorów).")
async def zamknij(interaction: discord.Interaction):
    if interaction.channel.category_id != ticket_category_id:
        await interaction.response.send_message("Ten kanał nie jest ticketem!", ephemeral=True)
        return
    embed = discord.Embed(
        title="Zamykanie Ticketa",
        description="Czy na pewno chcesz zamknąć ten ticket? Potwierdź poniżej.",
        color=discord.Color.red()
    )
    confirm_view = View()
    confirm_button = Button(label="Tak", style=discord.ButtonStyle.green, custom_id=f"confirm_close_{interaction.channel.id}")
    cancel_button = Button(label="Nie", style=discord.ButtonStyle.red, custom_id=f"cancel_close_{interaction.channel.id}")

    async def confirm_callback(interaction: discord.Interaction):
        messages = []
        async for message in interaction.channel.history(limit=None, oldest_first=True):
            messages.append(f"{message.author}: {message.content}")
        transcript = "\n".join(messages)
        transcript_file = discord.File(io.BytesIO(transcript.encode()), filename="transcript.txt")
        try:
            await interaction.user.send("Poniżej znajduje się transkrypt Twojego ticketa:", file=transcript_file)
        except discord.Forbidden:
            await interaction.response.send_message("Nie mogłem wysłać Ci transkryptu na priv. Upewnij się, że masz włączone wiadomości prywatne.", ephemeral=True)
        await interaction.channel.delete()

    async def cancel_callback(interaction: discord.Interaction):
        await interaction.message.delete()
        await interaction.response.send_message("Zamykanie ticketa zostało anulowane.", ephemeral=True)

    confirm_button.callback = confirm_callback
    cancel_button.callback = cancel_callback
    confirm_view.add_item(confirm_button)
    confirm_view.add_item(cancel_button)
    await interaction.response.send_message(embed=embed, view=confirm_view)

bot.run("TOKEN")
