import os
import discord
from discord.ext import commands

from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

client = commands.Bot(command_prefix='!', intents=intents)

client.actGroupId = 0 #GLOBAL VARIABLE TO TRACK THE ID OF THE ACTIVATION GROUP CATEGORY
client.actGroupDict = {} #GLOBAL DICTIONARY TO TRACK THE IDS OF CURRENTLY ACTIVE GROUPS

@client.event
async def on_ready():
    for guild in client.guilds:
        if guild.name == GUILD:
            break

    #print(discord.__version__)

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

            team_role = discord.utils.get(guild.roles, name=f"Group {client.actGroupId} - Team {i}") #CHECK IF THE ROLE FOR THE TEAM ALREADY EXISTS
            if not team_role:
                team_role = await guild.create_role(name=f"Group {client.actGroupId} - Team {i}") #CREATE A ROLE FOR THE TEAM

            team_overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False), #DENY @EVERYONE
                role: discord.PermissionOverwrite(view_channel=False), #DENY @members
                botRole: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True), #ALLOW THE BOT
                admin: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, administrator=True), #ALLOW ADMINS
                team_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True) #ALLOW THE TEAM ROLE
            }

            team_channel = await guild.create_text_channel(name=f"team-{i}", category=category, overwrites=team_overwrites) #CREATE TEAM CHANNELS IN THE CATEGORY
            await team_channel.send(f"✅ Team {i} created.")

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
    while team_role := discord.utils.get(guild.roles, name=f"Group {groupId} - Team {teamId}"): #LOOP TO DELETE ALL TEAM ROLES FOR THE GROUP
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

# !assigntogroup @user groupId teamId(optional) // ASSIGNS THE USER TO THE GROUP ROLE AND TEAM ROLE IF TEAM ID IS PROVIDED
@client.command(name="assigntogroup")
async def assign_to_group(ctx, user: discord.Member, groupId: int, teamId: int = None): #PARAMETERS OF THE TEXT LINE, TEAMID IS OPTIONAL
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

    try:
        await user.add_roles(role)
        await ctx.send(f"✅ {user.mention} has been assigned to Group {groupId}.")
    except Exception as e:
        await ctx.send(f"Assignment Failed ❌")

    team_role = discord.utils.get(guild.roles, name=f"Group {groupId} - Team {teamId}")
    if not team_role:
        await ctx.send("❌ Team role not found.")
        return
    
    try:
        await user.add_roles(team_role)
        await ctx.send(f"✅ {user.mention} has been assigned to Team {teamId} in Group {groupId}.")
    except Exception as e:
        await ctx.send(f"Team Assignment Failed ❌")


client.run(TOKEN)