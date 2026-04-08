import os
import discord
from discord.ext import commands

import pandas as pd

from dotenv import load_dotenv

def find_volunteer(column, value):
    try:
        df = pd.read_csv(VOLUNTEER_CSV, dtype=str)

        df[column] = df[column].astype(str).str.strip()
        clean_value = str(value).strip()

        matches = df.index[df[column] == clean_value].tolist()
        return matches[0] if matches else None

    except Exception as e:
        print(f"Error reading CSV: {e}")
        return None


def update_volunteer(index, columns, values):
    try:
        df = pd.read_csv(VOLUNTEER_CSV, dtype=str)
        if index < len(df):
            for col, val in zip(columns, values):
                df.at[index, col] = str(val).strip()
            df.to_csv(VOLUNTEER_CSV, index=False)
            return True
        else:
            print(f"Index {index} is out of bounds.")
            return False
    except Exception as e:
        print(f"Error updating CSV: {e}")
        return False
    
def add_to_group(column, value, group_id, team_id=None):
    volunteer_idx = find_volunteer(column, value)
    if volunteer_idx:
        update_volunteer(volunteer_idx, ['GroupID', 'TeamID'], [group_id, team_id])
        return
    
def remove_from_group(column, value):
    volunteer_idx = find_volunteer(column, value)
    if volunteer_idx:
        update_volunteer(volunteer_idx, ['GroupID', 'TeamID'], ['', ''])
        return
    
def get_discord_from_id(id):
    volunteer_idx = find_volunteer('ID', id)
    if volunteer_idx:
        df = pd.read_csv(VOLUNTEER_CSV)
        return df.at[volunteer_idx, 'DiscordID']
    return None

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN_ACTIVATION')
GUILD = os.getenv('DISCORD_GUILD')
VOLUNTEER_CSV = os.getenv('VOLUNTEER_CSV')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

client = commands.Bot(command_prefix='!', intents=intents)

client.actGroupId = 1 #GLOBAL VARIABLE TO TRACK THE ID OF THE ACTIVATION GROUP CATEGORY
client.actGroupDict = {} #GLOBAL DICTIONARY TO TRACK THE IDS OF CURRENTLY ACTIVE GROUPS

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
                client.actGroupDict[groupId] = category.id #ADD THE GROUP ID AND CATEGORY ID TO THE DICTIONARY OF ACTIVE GROUPS
                if groupId >= client.actGroupId:
                    client.actGroupId = groupId + 1 #SET THE NEXT GROUP ID TO BE ONE GREATER THAN THE HIGHEST CURRENTLY ACTIVE GROUP ID
            except Exception as e:
                print(f"Error processing category '{category.name}': {e}")

    print(
        f'{client.user} has connected to the following guild:\n'
        f'{guild.name}(id: {guild.id})'
    )

# !activate location emergency teams // CREATES A CATEGORY FOR AN ACTIVATION GROUP
@client.command(name="activate")
async def activate(ctx, location: str, emergency: str, teams: int): #PARAMETERS OF THE TEXT LINE
    if not ctx.author.guild_permissions.manage_channels: #CHECK IF THE USER HAS PERMISSION TO MANAGE CHANNELS
        await ctx.send("❌ You do not have permission to use this command.")
        return

    guild = ctx.guild
    user = ctx.message.author
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
        await ctx.send("❌ This command can only be used in a server.")
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
        await ctx.send(f"Group {client.actGroupId} activated with location '{location}' and emergency '{emergency}' ✅") #CONFIRMATION MESSAGE

    except Exception as e:
        await ctx.send(f"Category Creation Failed ❌")#IF IT FAIL
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

            team_channel = await guild.create_text_channel(name=f"team-{i:02d}", category=category, overwrites=team_overwrites) #CREATE TEAM CHANNELS IN THE CATEGORY
            await team_channel.send(f"✅ Team {i:02d} created.")

    except Exception as e:
        await ctx.send(f"Text Channel Creation Failed ❌")#IF IT FAILS
        return
    
    client.actGroupDict[client.actGroupId] = category.id #ADD THE CATEGORY ID AND GROUP ID TO THE DICTIONARY OF ACTIVE GROUPS
    client.actGroupId += 1 #INCREMENT THE GROUP ID FOR THE NEXT ACTIVATION

# !deactivate groupId(number) // DELETES THE CATEGORY AND ALL CHANNELS WITHIN THE CATEGORY FOR THE GROUP ID, ALSO DELETES THE ROLES ASSOCIATED WITH THE GROUP
@client.command(name="deactivate")
async def deactivate(ctx, groupId: int): #PARAMETER OF THE TEXT LINE
    if not ctx.author.guild_permissions.manage_channels: #CHECK IF THE USER HAS PERMISSION TO MANAGE CHANNELS
        await ctx.send("❌ You do not have permission to use this command.")
        return
    
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
    categoryId = client.actGroupDict.get(groupId) #GET THE CATEGORY ID OF THE GROUP TO BE DEACTIVATED
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

# !assigntogroup volunteerId groupId teamId(optional) // ASSIGNS THE USER TO THE GROUP ROLE AND TEAM ROLE IF TEAM ID IS PROVIDED
@client.command(name="assignbyid")
async def assign_by_id(ctx, volunteerId: int, groupId: int, teamId: int = None): #PARAMETERS OF THE TEXT LINE, TEAMID IS OPTIONAL
    if not ctx.author.guild_permissions.manage_roles:
        await ctx.send("❌ You do not have permission to use this command.")
        return
    
    discord_id = get_discord_from_id(volunteerId).strip() #GET THE DISCORD USERNAME FROM THE VOLUNTEER ID
    #print(repr(discord_id))

    if not discord_id:
        await ctx.send("❌ Volunteer ID not found.")
        return
    
    if not groupId in client.actGroupDict:
        await ctx.send("❌ Invalid Group ID.")
        return

    
    guild = ctx.guild
    user = guild.get_member(int(discord_id)) #GET THE DISCORD USER OBJECT USING THE USERNAME
    #print(user)
    role = discord.utils.get(guild.roles, name=f"Group {groupId} Member")
    if not role:
        await ctx.send("❌ Group role not found.")
        return
    
    team_role = discord.utils.get(guild.roles, name=f"Team {groupId}{teamId:02d}")
    if not team_role:
        await ctx.send("❌ Team role not found.")
        return
    
    add_to_group('ID', volunteerId, groupId, f"{groupId}{teamId:02d}") #UPDATE THE CSV TO REFLECT THE GROUP AND TEAM ASSIGNMENT

    if user:
        try:
            await user.add_roles(role)
            await ctx.send(f"✅ {user.mention} has been assigned to Group {groupId}.")
        except Exception as e:
            await ctx.send(f"Assignment Failed ❌")
        
        try:
            await user.add_roles(team_role)
            await ctx.send(f"✅ {user.mention} has been assigned to Team {teamId:02d} in Group {groupId}.")
        except Exception as e:
            await ctx.send(f"Team Assignment Failed ❌")

@client.command(name="assignbydiscord")
async def assign_by_discord(ctx, user: discord.Member, groupId: int, teamId: int = None): #PARAMETERS OF THE TEXT LINE, TEAMID IS OPTIONAL
    if not ctx.author.guild_permissions.manage_roles:
        await ctx.send("❌ You do not have permission to use this command.")
        return

    if not groupId in client.actGroupDict:
        await ctx.send("❌ Invalid Group ID.")
        return

    guild = ctx.guild
    role = discord.utils.get(guild.roles, name=f"Group {groupId} Member")
    if not role:
        await ctx.send("❌ Group role not found.")
        return
    
    team_role = discord.utils.get(guild.roles, name=f"Team {groupId}{teamId:02d}")
    if not team_role:
        await ctx.send("❌ Team role not found.")
        return

    add_to_group('DiscordID', user.id, groupId, f"{groupId}{teamId:02d}") #UPDATE THE CSV TO REFLECT THE GROUP AND TEAM ASSIGNMENT

    try:
        await user.add_roles(role)
        await ctx.send(f"✅ {user.mention} has been assigned to Group {groupId}.")
    except Exception as e:
        await ctx.send(f"Assignment Failed ❌")

    try:
        await user.add_roles(team_role)
        await ctx.send(f"✅ {user.mention} has been assigned to Team {teamId:02d} in Group {groupId}.")
    except Exception as e:
        await ctx.send(f"Team Assignment Failed ❌")

@client.command(name="unassignbyid")
async def unassign_by_id(ctx, volunteerId: int, groupId: int, teamId: int = None):
    if not ctx.author.guild_permissions.manage_roles:
        await ctx.send("❌ You do not have permission to use this command.")
        return

    discord_id = get_discord_from_id(volunteerId).strip()
    #print(repr(discord_id))

    if not discord_id:
        await ctx.send("❌ Volunteer ID not found.")
        return

    if not groupId in client.actGroupDict:
        await ctx.send("❌ Invalid Group ID.")
        return

    guild = ctx.guild
    user = guild.get_member(int(discord_id))
    #print(user)
    role = discord.utils.get(guild.roles, name=f"Group {groupId} Member")
    if not role:
        await ctx.send("❌ Group role not found.")
        return

    team_role = discord.utils.get(guild.roles, name=f"Team {groupId}{teamId:02d}")
    if not team_role:
        await ctx.send("❌ Team role not found.")
        return

    remove_from_group('ID', volunteerId, groupId, f"{groupId}{teamId:02d}")

    if user:
        try:
            await user.remove_roles(role)
            await ctx.send(f"✅ {user.mention} has been removed from Group {groupId}.")
        except Exception as e:
            await ctx.send(f"Unassignment Failed ❌")

        try:
            await user.remove_roles(team_role)
            await ctx.send(f"✅ {user.mention} has been removed from Team {teamId:02d} in Group {groupId}.")
        except Exception as e:
            await ctx.send(f"Team Unassignment Failed ❌")

@client.command(name="unassignbydiscord")
async def unassign_by_discord(ctx, user: discord.Member, groupId: int, teamId: int = None):
    if not ctx.author.guild_permissions.manage_roles:
        await ctx.send("❌ You do not have permission to use this command.")
        return

    if not groupId in client.actGroupDict:
        await ctx.send("❌ Invalid Group ID.")
        return

    guild = ctx.guild
    role = discord.utils.get(guild.roles, name=f"Group {groupId} Member")
    if not role:
        await ctx.send("❌ Group role not found.")
        return
    
    team_role = discord.utils.get(guild.roles, name=f"Team {groupId}{teamId:02d}")
    if not team_role:
         await ctx.send("❌ Team role not found.")
         return

    remove_from_group('DiscordID', user.id, groupId, f"{groupId}{teamId:02d}")

    try:
        await user.remove_roles(role)
        await ctx.send(f"✅ {user.mention} has been removed from Group {groupId}.")
    except Exception as e:
        await ctx.send(f"Unassignment Failed ❌")

    try:
        await user.remove_roles(team_role)
        await ctx.send(f"✅ {user.mention} has been removed from Team {teamId:02d} in Group {groupId}.")
    except Exception as e:
        await ctx.send(f"Team Unassignment Failed ❌")

client.run(TOKEN)