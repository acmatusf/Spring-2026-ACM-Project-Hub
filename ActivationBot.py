import asyncio
import os
import discord
from discord.ext import commands

from email_validator import validate_email
from phonenumbers import parse, is_valid_number, NumberParseException

import pandas as pd

from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN_ACTIVATION')
GUILD = os.getenv('DISCORD_GUILD')
GUILD_ID = int(os.getenv('DISCORD_GUILD_ID'))
VOLUNTEER_CSV = os.getenv('VOLUNTEER_CSV')

#returns indices of volunteers in the CSV that match the value in the specified column, returns None if no matches are found
def find_volunteers(column, value):
    try:
        df = pd.read_csv(VOLUNTEER_CSV, dtype=str)

        df[column] = df[column].astype(str).str.strip()
        clean_value = str(value).strip()

        matches = df.index[df[column] == clean_value].tolist()
        print(matches)
        return matches

    except Exception as e:
        print(f"Error reading CSV: {e}")
        return None


def update_volunteer(index, columns, values):
    try:
        df = pd.read_csv(VOLUNTEER_CSV, dtype=str)
        if index < len(df):
            for col, val in zip(columns, values):
                df.at[index, col] = str(val).strip()
                print(f"Updated index {index}: set {col} to {val}")
            df.to_csv(VOLUNTEER_CSV, index=False)
            return True
        else:
            print(f"Index {index} is out of bounds.")
            return False
    except Exception as e:
        print(f"Error updating CSV: {e}")
        return False
    
def get_volunteer_info(index):
    try:
        df = pd.read_csv(VOLUNTEER_CSV, dtype=str)
        if index < len(df):
            volunteer_info = df.iloc[index].to_dict()
            return volunteer_info
        else:
            print(f"Index {index} is out of bounds.")
            return None
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return None
    
def update_group(column, value, group_id, team_id=0):
    volunteer_idx = find_volunteers(column, value)[0]
    if volunteer_idx is not None:
        update_volunteer(volunteer_idx, ['GroupID', 'TeamID'], [group_id, team_id])
        return
    
async def remove_roles_from_user(user):
    guild = client.get_guild(GUILD_ID)

    if guild is None:
        guild = await client.fetch_guild(GUILD_ID)
    
    roles_to_remove = []

    for group_id in client.actGroupDict.keys():
        role = discord.utils.get(
            guild.roles,
            name=f"Group {group_id} Member"
        )
        if role:
            roles_to_remove.append(role)

        team_count = client.actGroupDict[group_id][1]

        for team_id in range(1, team_count + 1):
            team_role = discord.utils.get(
                guild.roles,
                name=f"Team {group_id}{team_id:02d}"
            )
            if team_role:
                roles_to_remove.append(team_role)
        if roles_to_remove:
            await user.remove_roles(*roles_to_remove)
    
def get_discord_from_id(id):
    volunteer_idx = find_volunteers('ID', id)[0]
    if volunteer_idx is not None:
        df = pd.read_csv(VOLUNTEER_CSV)
        return df.at[volunteer_idx, 'DiscordID']
    return None

class ProtectedView(discord.ui.View):
    def __init__(self, assignment):
        super().__init__(timeout=300)
        self.assignment = assignment

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return False


        if client.adminRole in interaction.user.roles:
            return True

        # safe block (NO response spam issues)
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ You do not have permission to use this.", ephemeral=True)
            await interaction.message.delete()

        return False

class AssignmentStucture:
    def __init__(self):
        self.unassign = False
        self.guild = None
        self.identifierType = None
        self.identifierValue = None
        self.groupID = None
        self.teamID = None
        self.future = asyncio.get_event_loop().create_future()
    #Setters
    def setGuild(self, guild):
        self.guild = guild
    def setIdentifierType(self, identifierType):
        self.identifierType = identifierType
    def setIdentifierValue(self, identifierValue):
        self.identifierValue = identifierValue
    def setGroupID(self, groupID):
        self.groupID = groupID
    def setTeamID(self, teamID):
        self.teamID = teamID

class IdentifierView(ProtectedView):
    def __init__(self, assignment):
        super().__init__(assignment)
        self.add_item(IdentifierSelect(assignment))

class IdentifierSelect(discord.ui.Select):
    def __init__(self, assignment):
        options = [
            discord.SelectOption(label="Volunteer ID", value="ID"),
            discord.SelectOption(label="Discord User", value="DiscordID"),
            discord.SelectOption(label="Email", value="Email"),
            discord.SelectOption(label="Phone Number", value="Phone")
        ]
        super().__init__(placeholder="Select an identifier type:", options=options, min_values=1, max_values=1)
        self.assignment = assignment
    
    async def callback(self, interaction: discord.Interaction):
        self.assignment.setIdentifierType(self.values[0])

        if self.values[0] == "DiscordID":
            view = UserSelectView(self.assignment)
            await interaction.response.edit_message(content="Select Discord User:", view=view)
        else:
            await interaction.response.send_modal(IdentifierModal(self.assignment))

class IdentifierModal(discord.ui.Modal):
    def __init__(self, assignment):
        super().__init__(title=f"Enter the {assignment.identifierType} of the volunteer")
        self.assignment = assignment
        self.identifier = discord.ui.TextInput(label=f"{assignment.identifierType}", placeholder=f"Enter the volunteer's {assignment.identifierType} here...", required=True)
        self.add_item(self.identifier)

    async def on_submit(self, interaction: discord.Interaction):
        if client.adminRole not in interaction.user.roles:
            await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
            return

        if self.assignment.identifierType == "Email":
            try:
                validate_email(self.identifier.value)
            except Exception as e:
                await interaction.response.edit_message(content=f"Please enter a valid email address. {e}", view=None)
                return
            self.assignment.setIdentifierValue(self.identifier.value.strip())
        elif self.assignment.identifierType == "Phone":
            try:
                phone_number = parse(self.identifier.value, "US")
                if not is_valid_number(phone_number):
                    raise NumberParseException(0, "Invalid phone number")
            except NumberParseException as e:
                await interaction.response.edit_message(content=f"Please enter a valid phone number. {e}", view=None)
                return
            self.assignment.setIdentifierValue(phone_number)
        elif self.assignment.identifierType == "ID":
            if not self.identifier.value.isdigit():
                await interaction.response.edit_message(content="Please enter a valid volunteer ID (numeric).", view=None)
                return
            self.assignment.setIdentifierValue(int(self.identifier.value.strip()))
        else:
            self.assignment.setIdentifierValue(self.identifier.value.strip())

        if self.assignment.unassign == True:
            if not self.assignment.future.done():
                self.assignment.future.set_result(True)
                await interaction.response.edit_message(content=f"Operation completed successfully.", view=None)
                return

        view = GroupSelectView(self.assignment)
        await interaction.response.edit_message(content="Select a group:", view=view)

class UserSelectView(ProtectedView):
    def __init__(self, assignment):
        super().__init__(assignment)
        self.add_item(UserSelect(assignment))

class UserSelect(discord.ui.UserSelect):
    def __init__(self, assignment):
        super().__init__(placeholder="Select a user:", min_values=1, max_values=1)
        self.assignment = assignment

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.edit_message(content="❌ This command can only be used in a server.", view=None)
            return

        user = self.values[0]
        self.assignment.setIdentifierValue(user.id)

        if self.assignment.unassign == True:
            if not self.assignment.future.done():
                self.assignment.future.set_result(True)
                await interaction.response.edit_message(content=f"Operation completed successfully.", view=None)
                return

        view = GroupSelectView(self.assignment)
        await interaction.response.edit_message(content="Select a group to assign to:", view=view)

class GroupSelectView(ProtectedView):
    def __init__(self, assignment):
        super().__init__(assignment)
        self.add_item(GroupSelect(assignment))

class GroupSelect(discord.ui.Select):
    def __init__(self, assignment):
        options = [discord.SelectOption(label=f"Group {groupId}", value=str(groupId)) for groupId in client.actGroupDict.keys()]
        super().__init__(placeholder="Select a group to assign to:", options=options, min_values=1, max_values=1)
        self.assignment = assignment

    async def callback(self, interaction: discord.Interaction):
        self.assignment.setGroupID(int(self.values[0]))

        view = TeamSelectView(self.assignment)
        await interaction.response.edit_message(content="Select a team to assign to:", view=view)
        
class TeamSelectView(ProtectedView):
    def __init__(self, assignment):
        super().__init__(assignment)
        self.add_item(TeamSelect(assignment))

class TeamSelect(discord.ui.Select):
    def __init__(self, assignment):

        groupId = assignment.groupID

        category_id = client.actGroupDict.get(groupId)[0]
        if category_id is None:
            raise ValueError(f"Group ID {groupId} not found in active groups.")
        
        category = assignment.guild.get_channel(category_id)
        if category is None:
            raise ValueError(f"Category for Group ID {groupId} not found.")
        
        teams = client.actGroupDict.get(groupId)[1]
        options = [discord.SelectOption(label=f"Team {groupId}{i:02d}", value=i) for i in range(1, teams + 1)]
        super().__init__(placeholder="Select a team:", options=options)
        self.assignment = assignment

    async def callback(self, interaction: discord.Interaction):
        self.assignment.setTeamID(int(self.values[0]))
        if not self.assignment.future.done():
            self.assignment.future.set_result(True)
        await interaction.response.edit_message(content=f"Operation completed successfully.", view=None)

class Activate(discord.ui.Modal, title="Activate Group"):
    def __init__(self):
        super().__init__(title="Activate Group")
        self.location = discord.ui.TextInput(label="Location")
        self.emergency = discord.ui.TextInput(label="Emergency Type")
        self.teams = discord.ui.TextInput(label="Number of Teams")

        self.add_item(self.location)
        self.add_item(self.emergency)
        self.add_item(self.teams)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.teams.value.isdigit() or int(self.teams.value) <= 0:
            await interaction.response.send_message("Please enter a valid number of teams (positive integer).", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        await activation(interaction, self.location.value.strip(), self.emergency.value.strip(), int(self.teams.value.strip()))
        


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

client = commands.Bot(command_prefix='!', intents=intents)

client.actGroupId = 1 #GLOBAL VARIABLE TO TRACK THE ID OF THE ACTIVATION GROUP CATEGORY
client.actGroupDict = {} #GLOBAL DICTIONARY TO TRACK THE IDS AND NUMBER OF TEAMS (ID, TeamCount) OF CURRENTLY ACTIVE GROUPS
client.adminRole = None

@client.event
async def on_ready():
    for guild in client.guilds:
        if guild.name == GUILD:
            break

    #print(discord.__version__)
    #print("Current Directory:", os.getcwd())
    #print("Files in Directory:", os.listdir())
    #print("Members cached:", len(guild.members))
    #for member in guild.members:
    #    print(f"Username: {member.name} | Display: {member.display_name} | ID: {member.id}")
    #FIND ALREADY ACTIVATED GROUPS WHEN FIRST RUN
    for category in guild.categories:
        if category.name.startswith("Group "):
            try:
                groupId = int(category.name.split()[1]) #EXTRACT THE GROUP ID FROM THE CATEGORY NAME
                for channel in category.channels:
                    if channel.name.startswith(f"team-{groupId}"):
                        teamCount = int(channel.name.split(f"-{groupId}")[1]) #EXTRACT THE TEAM COUNT FROM THE CHANNEL NAME, ASSUMING TEAMS ARE NAMED IN THE FORMAT "team-XX"

                client.actGroupDict[groupId] = (category.id, teamCount) #ADD THE GROUP ID AND CATEGORY ID TO THE DICTIONARY OF ACTIVE GROUPS
                if groupId >= client.actGroupId:
                    client.actGroupId = groupId + 1 #SET THE NEXT GROUP ID TO BE ONE GREATER THAN THE HIGHEST CURRENTLY ACTIVE GROUP ID
            except Exception as e:
                print(f"Error processing category '{category.name}': {e}")

    if not discord.utils.get(guild.roles, name="ActivationAdmin"):
        client.adminRole = await guild.create_role(name=f"ActivationAdmin")
    else:
        client.adminRole = discord.utils.get(guild.roles, name="ActivationAdmin")    

    print(
        f'{client.user} has connected to the following guild:\n'
        f'{guild.name}(id: {guild.id})\n'
    )

    for key, value in client.actGroupDict.items():
        print(f"Active Group {key}: Category ID {value[0]}, Team Count {value[1]}")

# !activate location emergency teams // CREATES A CATEGORY FOR AN ACTIVATION GROUP
@client.command(help="!activate <location> <emergency> <# ofteams>", name="activate")
async def activate(ctx):
    if client.adminRole not in ctx.author.roles:
        await ctx.send("❌ You do not have permission to use this command.")
        return

    #if not ctx.author.guild_permissions.manage_channels: #CHECK IF THE USER HAS PERMISSION TO MANAGE CHANNELS
    #    await ctx.send("❌ You do not have permission to use this command.")
    #    return

    await ctx.send("", view=FormButton())

class FormButton(discord.ui.View):
    @discord.ui.button(label="Activate Group", style=discord.ButtonStyle.primary)
    async def open_form(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(Activate())


async def activation(interaction: discord.Interaction, location: str, emergency: str, teams: int): #PARAMETERS OF THE TEXT LINE
    guild = interaction.guild
    user = interaction.user

    if client.adminRole not in user.roles:
        await interaction.followup.send("❌ You do not have permission to use this command.", ephemeral=True)
        return

    botRole = discord.utils.get(guild.roles, name="ActivationApp") #GET THE BOT ROLE TO GIVE IT PERMISSIONS IN THE CATEGORY

    #create two roles for the group, one for members and one for admins, and assign them to the user who activated the group
    role = discord.utils.get(guild.roles, name=f"Group {client.actGroupId} Member") #CHECK IF THE ROLE FOR THE GROUP ALREADY EXISTS
    admin = discord.utils.get(guild.roles, name=f"Group {client.actGroupId} Admin") #CHECK IF THE ADMIN ROLE FOR THE GROUP ALREADY EXISTS

    if not role:
        role = await guild.create_role(name=f"Group {client.actGroupId} Member") #CREATE ROLE IF DOESN'T EXIST

    if not admin:
        admin = await guild.create_role(name=f"Group {client.actGroupId} Admin") #CREATE ADMIN ROLE IF DOESN'T EXIST

    #give both roles to author, this allows them to see and manage activation group
    await user.add_roles(role)
    await user.add_roles(admin)

    if guild is None:
        await interaction.followup.send("❌ This command can only be used in a server.", ephemeral=True)
        return
        
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False), #DENY @EVERYONE
        botRole: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True), #ALLOW THE BOT
        role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True), #ALLOW MEMBERS
        admin: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, administrator=True) #ALLOW ADMINS
    }
    
    
    try:
        #create private category that only those within the role can see and access
        category = await guild.create_category(name=f"Group {client.actGroupId} - {location} - {emergency}", overwrites=overwrites) #CREATE THE CATEGORY WITH THE NAME AND PERMISSIONS
        #await interaction.response.send_message(f"Group {client.actGroupId} activated with location '{location}' and emergency '{emergency}' ✅") #CONFIRMATION MESSAGE

    except Exception as e:
        await interaction.followup.send(f"Category Creation Failed ❌", ephemeral=True)#IF IT FAIL
        return

    try:
        #create text channel within category
        general_channel = await guild.create_text_channel(name="general-chat", category=category) #CREATE A TEXT CHANNEL IN THE CATEGORY
        await general_channel.send(f"✅ Group Activated")

        #create channel for bot commands
        command_channel = await guild.create_text_channel(name="commands", category=category) #CREATE A COMMAND CHANNEL IN THE CATEGORY
        await command_channel.send(f"✅ Command Channel Created")


        for i in range(1, teams + 1):

            team_role = discord.utils.get(guild.roles, name=f"Team {client.actGroupId}{i:02d}") #CHECK IF THE ROLE FOR THE TEAM ALREADY EXISTS
            if not team_role:
                team_role = await guild.create_role(name=f"Team {client.actGroupId}{i:02d}") #CREATE A ROLE FOR THE TEAM

            team_overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False), #DENY @EVERYONE
                role: discord.PermissionOverwrite(view_channel=False), #DENY @members
                botRole: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True), #ALLOW THE BOT
                admin: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, administrator=True), #ALLOW ADMINS
                team_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True) #ALLOW THE TEAM ROLE
            }

            team_channel = await guild.create_text_channel(name=f"team-{client.actGroupId}{i:02d}", category=category, overwrites=team_overwrites) #CREATE TEAM CHANNELS IN THE CATEGORY
            await team_channel.send(f"✅ Team {i:02d} created.")

    except Exception as e:
        await interaction.followup.send(f"Text Channel Creation Failed ❌", ephemeral=True)#IF IT FAILS
        return
    
    if(len(client.actGroupDict) >= 99):
        await interaction.followup.send("❌ Maximum number of active groups reached. Please deactivate an existing group before activating a new one.", ephemeral=True)
        return
    
    while client.actGroupId in client.actGroupDict:
        client.actGroupId = client.actGroupId % 100 + 1 #INCREMENT THE GROUP ID UNTIL IT FINDS AN AVAILABLE ID, THIS PREVENTS ISSUES WITH RESTARTS AND DELETIONS CREATING DUPLICATE IDS, GO BACK TO 1 AFTER 99 TO REUSE IDS OF DELETED GROUPS
        if client.actGroupId == 0:
            client.actGroupId = 1 #skip 0 since it's used to indicate no group in the CSV
    
    client.actGroupDict[client.actGroupId] = (category.id, teams) #ADD THE CATEGORY ID AND GROUP ID TO THE DICTIONARY OF ACTIVE GROUPS
    client.actGroupId += 1 #INCREMENT THE GROUP ID FOR THE NEXT ACTIVATION

# !deactivate groupId(number) // DELETES THE CATEGORY AND ALL CHANNELS WITHIN THE CATEGORY FOR THE GROUP ID, ALSO DELETES THE ROLES ASSOCIATED WITH THE GROUP
@client.command(help="!deactivate <groupId>", name="deactivate")
async def deactivate(ctx, groupId: int): #PARAMETER OF THE TEXT LINE

    if client.adminRole not in ctx.author.roles:
        await ctx.send("❌ You do not have permission to use this command.")
        return

    #if not ctx.author.guild_permissions.manage_channels: #CHECK IF THE USER HAS PERMISSION TO MANAGE CHANNELS
    #    await ctx.send("❌ You do not have permission to use this command.")
    #    return
    
    if not groupId in client.actGroupDict: #CHECK IF THE GROUP ID IS VALID
        await ctx.send("❌ Invalid Group ID.")
        return
    
    guild = ctx.guild

    role = discord.utils.get(guild.roles, name=f"Group {groupId} Member") #GET THE MEMBER ROLE FOR THE GROUP
    admin = discord.utils.get(guild.roles, name=f"Group {groupId} Admin") #GET THE ADMIN ROLE FOR THE GROUP

    try:
        if role is not None:
            await role.delete() #DELETE THE MEMBER ROLE
        if admin is not None:
            await admin.delete() #DELETE THE ADMIN ROLE
    except Exception as e:
        await ctx.send(f"Role Deletion Failed ❌")#IF IT FAILS

    teamId = 1
    while team_role := discord.utils.get(guild.roles, name=f"Team {groupId}{teamId:02d}"): #LOOP TO DELETE ALL TEAM ROLES FOR THE GROUP
        try:
            await team_role.delete() #DELETE THE TEAM ROLE
        except Exception as e:
            await ctx.send(f"Team Role Deletion Failed ❌")#IF IT FAILS
        teamId += 1


    #find category from groupId
    categoryId = client.actGroupDict.get(groupId)[0] #GET THE CATEGORY ID OF THE GROUP TO BE DEACTIVATED
    category = guild.get_channel(categoryId) #GET THE CATEGORY OBJECT USING THE ID
    if category is None:
        await ctx.send("❌ Group not found.")
    else:
        try:
            #delete all channels within the category
            for channel in category.channels:
                await channel.delete() #DELETE EACH CHANNEL IN THE CATEGORY
        except Exception as e:
            await ctx.send(f"Channel Deletion Failed ❌")#IF IT FAILS
            return



    try:
        await category.delete() #DELETE THE CATEGORY, THIS ALSO DELETES ALL CHANNELS WITHIN THE CATEGORY
        del client.actGroupDict[groupId] #REMOVE THE GROUP FROM THE DICTIONARY OF ACTIVE GROUPS
        await ctx.send(f"✅ Group {groupId} deactivated and category deleted.")
    except Exception as e:
        await ctx.send(f"Category Deletion Failed ❌")#IF IT FAILS


@client.command(help="!assign (opens menus to choose who to assign where)", name="assign")
async def assign(ctx):
    if client.adminRole not in ctx.author.roles:
        await ctx.send("❌ You do not have permission to use this command.")
        return

    #if not ctx.author.guild_permissions.manage_roles:
    #    await ctx.send("❌ You do not have permission to use this command.")
    #    return
    
    assignment = AssignmentStucture()
    assignment.setGuild(ctx.guild)
    view = IdentifierView(assignment)

    #initialize chain to select all values for assignment
    msg = await ctx.send("Select an identifier type to find the volunteer:", view=view)
    await assignment.future
    await msg.delete()

    update_group(assignment.identifierType, assignment.identifierValue, assignment.groupID, f"{assignment.groupID}{assignment.teamID:02d}")

    if(assignment.identifierType == "DiscordID"):
        guild = ctx.guild
        user = guild.get_member(int(assignment.identifierValue))
        await remove_roles_from_user(user)
        role = discord.utils.get(guild.roles, name=f"Group {int(assignment.groupID)} Member")
        if not role:
            await ctx.send("❌ Group role not found.")
            return
        
        team_role = discord.utils.get(guild.roles, name=f"Team {int(assignment.groupID)}{int(assignment.teamID):02d}")
        if not team_role:
            await ctx.send("❌ Team role not found.")
            return

        try:
            await user.add_roles(role)
            await ctx.send(f"✅ {user.mention} has been assigned to Group {int(assignment.groupID)}.")
        except Exception as e:
            await ctx.send(f"Assignment Failed ❌")

        try:
            await user.add_roles(team_role)
            await ctx.send(f"✅ {user.mention} has been assigned to Team {int(assignment.teamID):02d} in Group {int(assignment.groupID)}.")
        except Exception as e:
            await ctx.send(f"Team Assignment Failed ❌")

@client.command(help="!unassign (opens menus to choose who to unassign)", name="unassign")
async def unassign(ctx):
    if client.adminRole not in ctx.author.roles:
        await ctx.send("❌ You do not have permission to use this command.")
        return

    #if not ctx.author.guild_permissions.manage_roles:
    #    await ctx.send("❌ You do not have permission to use this command.")
    #    return
    
    assignment = AssignmentStucture()
    assignment.setGuild(ctx.guild)
    assignment.unassign = True
    view = discord.ui.View()

    #initialize chain to select all values for assignment
    identifier_select = IdentifierSelect(assignment)
    view.add_item(identifier_select)
    msg = await ctx.send("Select an identifier type to find the volunteer:", view=view)
    await assignment.future
    await msg.delete()

    update_group(assignment.identifierType, assignment.identifierValue, 0, 0)

    if(assignment.identifierType == "DiscordID"):
        user = ctx.guild.get_member(int(assignment.identifierValue))
        await remove_roles_from_user(user)

client.run(TOKEN)