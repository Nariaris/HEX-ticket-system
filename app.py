import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import io
import json
import os

# Bot intents for handling messages, guilds, and message content
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

# Initializing the bot with a command prefix and intents
bot = commands.Bot(command_prefix="\\", intents=intents)

# Variable to store the ticket category ID
ticket_category_id = None

# File to store persistent data (e.g., ticket category ID)
DATA_FILE = "ticket_data.json"

# Function to load data from the JSON file
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

# Function to save data to the JSON file
def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

@bot.event
async def on_ready():
    global ticket_category_id
    print(f"Bot is ready!")
    
    # Load data and get the ticket category ID
    data = load_data()
    ticket_category_id = data.get("ticket_category_id")
    
    # Check if the ticket category exists
    if ticket_category_id:
        guild = discord.utils.get(bot.guilds)
        category = discord.utils.get(guild.categories, id=ticket_category_id)
        if category:
            print(f"Loaded ticket category: {category.name}")
        else:
            print("Ticket category not found; it may have been deleted.")
    
    # Register the ticket creation view
    bot.add_view(TicketCreateView())
    
    # Synchronize slash commands
    try:
        synced = await bot.tree.sync()
        print(f"Successfully synced {len(synced)} commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# Modal class for ticket creation with a reason input field
class TicketCreateModal(Modal, title="Create a Ticket"):
    reason = TextInput(label="Reason for ticket creation", style=discord.TextStyle.long)

    def __init__(self, user):
        super().__init__()
        self.user = user  # Store the user who initiated the ticket

    # Handle form submission
    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        global ticket_category_id
        
        # Ensure the ticketing system is properly configured
        if not ticket_category_id:
            await interaction.response.send_message("The ticketing system is not configured properly.", ephemeral=True)
            return
        
        # Get the ticket category
        category = discord.utils.get(guild.categories, id=ticket_category_id)
        if not category:
            await interaction.response.send_message("Ticket category not found.", ephemeral=True)
            return
        
        # Check if the user already has an open ticket
        ticket_channel_name = f"ticket-{self.user.name.lower()}"
        existing_channel = discord.utils.get(guild.channels, name=ticket_channel_name)
        if existing_channel:
            await interaction.response.send_message("You already have an open ticket!", ephemeral=True)
            return
        
        # Create a new ticket channel
        ticket_channel = await category.create_text_channel(
            ticket_channel_name,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                self.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
        )
        
        # Create an embed with ticket information
        ticket_embed = discord.Embed(
            title="Lorem Ipsum Title",
            description="Lorem Ipsum Description",
            color=discord.Color.green()
        )
        ticket_embed.add_field(name="Reason", value=self.reason.value, inline=False)
        ticket_embed.set_footer(text="Lorem Ipsum Footer")

        # Button to notify administrators
        ping_button = Button(label="Notify Admins", style=discord.ButtonStyle.red, custom_id=f"ping_admin_{ticket_channel.id}")

        # Callback for when the button is pressed
        async def ping_callback(interaction: discord.Interaction):
            await ticket_channel.send(f"Admins, user {interaction.user.mention} needs assistance!")
            ping_button.disabled = True
            await interaction.message.edit(view=ping_view)
            await interaction.response.send_message("Admins have been notified!", ephemeral=True)

        ping_button.callback = ping_callback
        ping_view = View()
        ping_view.add_item(ping_button)

        # Send the embed and button to the ticket channel
        await ticket_channel.send(embed=ticket_embed, view=ping_view)
        await interaction.response.send_message(f"Your ticket has been created: {ticket_channel.mention}", ephemeral=True)

# View class for the button to create tickets
class TicketCreateView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Create Ticket", style=discord.ButtonStyle.green, custom_id="create_ticket_button_1")
    async def create_ticket_button(self, interaction: discord.Interaction, button: Button):
        modal = TicketCreateModal(user=interaction.user)
        await interaction.response.send_modal(modal)

# Slash command to set up the ticketing system
@bot.tree.command(name="setup", description="Sets up the ticketing system (admin only).")
async def setup(interaction: discord.Interaction):
    guild = interaction.guild
    global ticket_category_id
    
    # Check if the system is already configured
    if ticket_category_id:
        await interaction.response.send_message("The ticketing system is already configured.", ephemeral=True)
        return
    
    # Create the ticket category and setup channel
    category = await guild.create_category("🎫 Tickets")
    ticket_category_id = category.id
    data = load_data()
    data["ticket_category_id"] = ticket_category_id
    save_data(data)
    ticket_channel = await category.create_text_channel("create-ticket")
    
    # Embed with instructions for creating tickets
    embed = discord.Embed(
        title="Lorem Ipsum Title",
        description="Lorem Ipsum Description for creating a ticket.",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Lorem Ipsum Footer")
    view = TicketCreateView()
    await ticket_channel.send(embed=embed, view=view)
    await interaction.response.send_message("The ticketing system has been set up.", ephemeral=True)

# Slash command to close a ticket
@bot.tree.command(name="close", description="Closes the ticket channel after confirmation (admin only).")
async def close(interaction: discord.Interaction):
    if interaction.channel.category_id != ticket_category_id:
        await interaction.response.send_message("This channel is not a ticket!", ephemeral=True)
        return
    
    # Embed asking for confirmation to close the ticket
    embed = discord.Embed(
        title="Closing Ticket",
        description="Are you sure you want to close this ticket? Confirm below.",
        color=discord.Color.red()
    )
    confirm_view = View()
    confirm_button = Button(label="Yes", style=discord.ButtonStyle.green, custom_id=f"confirm_close_{interaction.channel.id}")
    cancel_button = Button(label="No", style=discord.ButtonStyle.red, custom_id=f"cancel_close_{interaction.channel.id}")

    # Function to close the ticket
    async def confirm_callback(interaction: discord.Interaction):
        messages = []
        async for message in interaction.channel.history(limit=None, oldest_first=True):
            messages.append(f"{message.author}: {message.content}")
        transcript = "\n".join(messages)
        transcript_file = discord.File(io.BytesIO(transcript.encode()), filename="transcript.txt")
        try:
            await interaction.user.send("Here is the transcript of your ticket:", file=transcript_file)
        except discord.Forbidden:
            await interaction.response.send_message("I couldn't send you the transcript. Make sure your DMs are open.", ephemeral=True)
        await interaction.channel.delete()

    # Function to cancel ticket closure
    async def cancel_callback(interaction: discord.Interaction):
        await interaction.message.delete()
        await interaction.response.send_message("Ticket closure has been canceled.", ephemeral=True)

    confirm_button.callback = confirm_callback
    cancel_button.callback = cancel_callback
    confirm_view.add_item(confirm_button)
    confirm_view.add_item(cancel_button)
    await interaction.response.send_message(embed=embed, view=confirm_view)

# Run the bot
bot.run("YOUR_BOT_TOKEN")
