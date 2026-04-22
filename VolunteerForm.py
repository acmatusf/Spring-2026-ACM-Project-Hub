import os
import discord
import meshcore
import asyncio
from discord.ext import commands

from email_validator import validate_email
from phonenumbers import parse, is_valid_number, NumberParseException

import pandas as pd

from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN_FORM')
GUILD = os.getenv('DISCORD_GUILD')
VOLUNTEER_CSV = os.getenv('VOLUNTEER_CSV')
SUBMITTED_TXT = os.getenv('SUBMITTED_TXT')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

client = commands.Bot(command_prefix="!", intents=intents)

client.volunteerID = 0
client.messageBuffer = []
client.mesBufferLock = asyncio.Lock()

@client.event
async def on_ready():
    for guild in client.guilds:
        if guild.name == GUILD:
            break
    df = pd.read_csv(VOLUNTEER_CSV)
    #print(len(df))
    if len(df) > 1:
        client.volunteerID = df.iloc[-1, 0]  # Assuming the first column is volunteerID

    print(f'Volunteer ID starts at: {client.volunteerID}')

    print(
        f'{client.user} has connected to the following guild:\n'
        f'{guild.name}(id: {guild.id})'
    )

    asyncio.create_task(meshcore_loop())

class VolunteerForm(discord.ui.Modal, title="Volunteer Form"):
    name = discord.ui.TextInput(label="Full Name")
    email = discord.ui.TextInput(label="Email", required=False)
    phone = discord.ui.TextInput(label="Phone Number", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        with open(SUBMITTED_TXT, 'r') as f:
            submitted = set(line.strip() for line in f)
            if str(interaction.user.id) in submitted:
                await interaction.response.send_message("You have already submitted the form. Thank you!", ephemeral=True)
                return
        
        if self.email.value:
            try:
                validate_email(self.email.value)

            except Exception as e:
                await interaction.response.send_message(f"Please enter a valid email address. {e}", ephemeral=True)
                return
        
        if self.phone.value:
            try:
                phone_number = parse(self.phone.value, "US")
                if not is_valid_number(phone_number):
                    raise NumberParseException(0, "Invalid phone number")

            except NumberParseException as e:
                await interaction.response.send_message(f"Please enter a valid phone number. {e}", ephemeral=True)
                return
            
        await interaction.response.send_message("Thank you for submitting the form!", ephemeral=True)
        client.volunteerID += 1
        # You can store or process responses here
        with open(VOLUNTEER_CSV, 'a') as f:
            f.write(f"{client.volunteerID},{self.name.value},{interaction.user.id},{phone_number},{self.email.value},0,0\n")
        with open(SUBMITTED_TXT, 'a') as f:
            f.write(f"{interaction.user.id}\n")
        
        

@client.command(help="Creates a button that opens the volunteer form", name="form")
async def form(ctx):
    await ctx.send("Click the button to fill out the form", view=FormButton())

class FormButton(discord.ui.View):
    @discord.ui.button(label="Open Form", style=discord.ButtonStyle.primary)
    async def open_form(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VolunteerForm())

@client.event
async def on_message(message):
    #ignore mesages from self
    if message.author == client.user:
        return
    #process commands first to avoid conflicts with message buffer
    if message.content.startswith("!"):
        await client.process_commands(message)
        return

    await client.mesBufferLock.acquire()
    try:
        client.messageBuffer.append((message.author, message.created_at ,message.content))
    finally:
        client.mesBufferLock.release()


    await client.process_commands(message)

async def meshcore_loop():
    #device = await meshcore.MeshCore.create_ble()
    device = await meshcore.MeshCore.create_serial("COM7")
    print("Connected to MeshCore device")

    while True:
        result = await device.commands.get_contacts()
        if result.type == meshcore.EventType.ERROR:
            print(f"Error getting contacts: {result.error}")
            continue
        
        contacts = result.payload
        if contacts:
            contact = next(iter(contacts.items()))[1]
            #await device.commands.send_msg(contact, f"Connection Found")
            await client.mesBufferLock.acquire()
            try:
                #send all messages in buffer
                for message in client.messageBuffer:
                    result = await device.commands.send_msg(contact, f"{message[0]} at {message[1]}: {message[2]}")
                    if result.type == meshcore.EventType.ERROR:
                        print(f"Error sending message: {result.payload}")
                #empty buffer after sending
                client.messageBuffer = []
            finally:
                client.mesBufferLock.release()
            #empty buffer and send to meshcore

        await asyncio.sleep(10)

client.run(TOKEN)