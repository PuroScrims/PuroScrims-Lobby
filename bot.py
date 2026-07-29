import discord
from discord.ext import commands
import re
import os
from flask import Flask
from threading import Thread

# ============================================
# BOT SETUP
# ============================================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='*', intents=intents)

# ============================================
# ROLE IDS
# ============================================

# Roles to ping when channel is muted
MUTED_ROLES = [
    1531855127227535390,
    1531855163638288474,
    1531855196945252454,
    1531855186992304210,
    1531855171104280736,
    1531852594354454618,
    1531853175596908724
]

# Staff roles that can add users
STAFF_ROLES = [
    1531853092776317088,
    1531853202851627198,
    1531853180634271856,
    1531853206534094959,
    1531853193380892874,
    1531853197960810556,
    1531853188779737199,
    1531853170601365514,
    1531853149319463162,
    1531853156886122586,
    1531853135843164302,
    1531853144592617603
]

# ============================================
# STORAGE
# ============================================
registered_users = {}

# ============================================
# BOT EVENTS
# ============================================

@bot.event
async def on_ready():
    print(f'✅ {bot.user} has connected to Discord!')
    print(f'📊 Bot is in {len(bot.guilds)} guilds')
    print(f'👥 Staff roles loaded: {len(STAFF_ROLES)}')
    print(f'🔔 Muted roles loaded: {len(MUTED_ROLES)}')
    await bot.change_presence(activity=discord.Game(name="*help | Staff Bot"))

@bot.event
async def on_message(message):
    # Ignore bot messages
    if message.author.bot:
        return
    
    # Check if message is in a registered channel and user is staff
    if message.channel.id in registered_users:
        # Check if user has staff role to bypass auto-reply
        has_staff_role = any(role.id in STAFF_ROLES for role in message.author.roles)
        if not has_staff_role:
            # Check if user is already registered
            if message.author.id not in registered_users:
                await message.reply(f"Would you like to add? {message.author.mention}")
    
    # Process commands
    await bot.process_commands(message)

# ============================================
# MUTE/UNMUTE COMMANDS
# ============================================

@bot.command(name='mf')
@commands.has_permissions(manage_channels=True)
async def mute_channel(ctx):
    """Mute the channel - Staff only"""
    channel = ctx.channel
    
    # Set slowmode to 1 hour (3600 seconds) as a form of muting
    await channel.edit(slowmode_delay=3600)
    
    # Create mention string for all muted roles
    role_mentions = ' '.join([f'<@&{role_id}>' for role_id in MUTED_ROLES])
    
    embed = discord.Embed(
        title="🔇 This Channel is Muted",
        description=f"**A Staff will open this channel when fills are needed**\n\n{role_mentions}",
        color=discord.Color.red()
    )
    embed.set_footer(text=f"Muted by {ctx.author.name}")
    embed.timestamp = discord.utils.utcnow()
    
    await ctx.send(embed=embed)

@bot.command(name='uf')
@commands.has_permissions(manage_channels=True)
async def unmute_channel(ctx):
    """Unmute the channel - Staff only"""
    channel = ctx.channel
    
    # Remove slowmode
    await channel.edit(slowmode_delay=0)
    
    embed = discord.Embed(
        title="🔊 This Channel is Unmuted",
        description="**Type to fill**",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"Unmuted by {ctx.author.name}")
    embed.timestamp = discord.utils.utcnow()
    
    await ctx.send(embed=embed)

# ============================================
# ADD USER COMMAND
# ============================================

@bot.command(name='add')
async def add_user(ctx, member: discord.Member = None):
    """Add a user to the lobby - Staff only"""
    
    # Check if user has staff role
    has_staff_role = any(role.id in STAFF_ROLES for role in ctx.author.roles)
    
    if not has_staff_role:
        await ctx.send("❌ You don't have permission to use this command!")
        return
    
    if member is None:
        await ctx.send("❌ Please mention a user to add!\nExample: `*add @username`")
        return
    
    if member == ctx.author:
        await ctx.send("❌ You can't add yourself!")
        return
    
    if member.bot:
        await ctx.send("❌ You can't register a bot!")
        return
    
    # Check if user is already registered
    if member.id in registered_users:
        await ctx.send(f"❌ {member.mention} is already registered!")
        return
    
    # Get channel name for role assignment
    channel_name = ctx.channel.name
    
    # Store the user
    registered_users[member.id] = {
        'registered_by': ctx.author.id,
        'channel': ctx.channel.id,
        'channel_name': channel_name,
        'timestamp': discord.utils.utcnow()
    }
    
    # ============================================
    # LOBBY ROLE ASSIGNMENT
    # ============================================
    
    lobby_role = None
    role_message = "ℹ️ No lobby role found for this channel"
    
    # Extract lobby number from channel name
    # Patterns: lobby-1, lobby 1, lobby1, Lobby-1, etc.
    patterns = [
        r'lobby[\s\-]?(\d+)',  # lobby-1, lobby 1, lobby1
        r'lobby_(\d+)',        # lobby_1
        r'Lobby[\s\-]?(\d+)',  # Lobby-1, Lobby 1
        r'Lobby_(\d+)'         # Lobby_1
    ]
    
    for pattern in patterns:
        match = re.search(pattern, channel_name, re.IGNORECASE)
        if match:
            lobby_number = match.group(1)
            # Look for a role with the lobby number
            for role in ctx.guild.roles:
                if role.name.lower() == f'lobby {lobby_number}'.lower():
                    lobby_role = role
                    break
                # Also check for exact match without space
                if role.name.lower() == f'lobby{lobby_number}'.lower():
                    lobby_role = role
                    break
            break
    
    # Assign lobby role if found
    if lobby_role:
        try:
            await member.add_roles(lobby_role)
            role_message = f"✅ Assigned role: {lobby_role.mention}"
        except discord.Forbidden:
            role_message = "❌ I don't have permission to assign that role!"
        except Exception as e:
            role_message = f"❌ Failed to assign role: {str(e)}"
    
    # ============================================
    # REGISTRATION EMBED
    # ============================================
    
    embed = discord.Embed(
        title="✅ User Registered Successfully",
        description=f"{member.mention} has been joined by {ctx.author.mention}",
        color=discord.Color.green()
    )
    embed.add_field(name="📌 Channel", value=ctx.channel.mention, inline=True)
    embed.add_field(name="🎭 Lobby Role", value=role_message, inline=True)
    embed.add_field(name="📝 Channel Name", value=channel_name, inline=False)
    embed.set_footer(text=f"Registered at")
    embed.timestamp = discord.utils.utcnow()
    
    await ctx.send(embed=embed)
    
    # Tag the user that has been registered
    await ctx.send(f"🎉 {member.mention} has been registered by {ctx.author.mention}!")

# ============================================
# REMOVE USER COMMAND
# ============================================

@bot.command(name='remove')
async def remove_user(ctx, member: discord.Member = None):
    """Remove a registered user - Staff only"""
    
    # Check if user has staff role
    has_staff_role = any(role.id in STAFF_ROLES for role in ctx.author.roles)
    
    if not has_staff_role:
        await ctx.send("❌ You don't have permission to use this command!")
        return
    
    if member is None:
        await ctx.send("❌ Please mention a user to remove!\nExample: `*remove @username`")
        return
    
    if member.id not in registered_users:
        await ctx.send(f"❌ {member.mention} is not registered!")
        return
    
    # Get user data before removing
    user_data = registered_users[member.id]
    registered_by = bot.get_user(user_data['registered_by'])
    
    # Remove from registered users
    del registered_users[member.id]
    
    embed = discord.Embed(
        title="🗑️ User Removed",
        description=f"{member.mention} has been removed by {ctx.author.mention}",
        color=discord.Color.orange()
    )
    embed.add_field(name="Registered by", value=registered_by.mention if registered_by else "Unknown", inline=True)
    embed.add_field(name="Channel", value=f"<#{user_data['channel']}>", inline=True)
    embed.set_footer(text=f"Removed at")
    embed.timestamp = discord.utils.utcnow()
    
    await ctx.send(embed=embed)

# ============================================
# LIST USERS COMMAND
# ============================================

@bot.command(name='list')
@commands.has_permissions(manage_channels=True)
async def list_users(ctx):
    """List all registered users - Staff only"""
    
    if not registered_users:
        await ctx.send("📋 No users are currently registered.")
        return
    
    embed = discord.Embed(
        title="📋 Registered Users",
        description=f"Total: {len(registered_users)} users",
        color=discord.Color.blue()
    )
    
    for user_id, data in list(registered_users.items())[:25]:  # Limit to 25 per embed
        user = bot.get_user(user_id)
        if user:
            staff = bot.get_user(data['registered_by'])
            embed.add_field(
                name=user.name,
                value=f"👤 ID: {user_id}\n📌 Registered by: {staff.mention if staff else 'Unknown'}\n📝 Channel: {data['channel_name']}",
                inline=False
            )
    
    await ctx.send(embed=embed)

# ============================================
# CLEAR ALL USERS COMMAND
# ============================================

@bot.command(name='clearall')
@commands.has_permissions(administrator=True)
async def clear_all_users(ctx):
    """Clear all registered users - Admin only"""
    
    if not registered_users:
        await ctx.send("📋 No users are currently registered.")
        return
    
    # Create confirmation embed
    embed = discord.Embed(
        title="⚠️ Clear All Users?",
        description=f"This will remove {len(registered_users)} registered users.",
        color=discord.Color.red()
    )
    embed.set_footer(text="Type *confirmclear to confirm")
    
    await ctx.send(embed=embed)

@bot.command(name='confirmclear')
@commands.has_permissions(administrator=True)
async def confirm_clear(ctx):
    """Confirm clearing all users - Admin only"""
    
    if not registered_users:
        await ctx.send("📋 No users are currently registered.")
        return
    
    count = len(registered_users)
    registered_users.clear()
    
    await ctx.send(f"🗑️ Cleared {count} registered users successfully!")

# ============================================
# HELP COMMAND
# ============================================

@bot.command(name='help')
async def custom_help(ctx):
    """Show all available commands"""
    
    embed = discord.Embed(
        title="🤖 Bot Commands",
        description="Here are all available commands:",
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="📌 Mute/Unmute",
        value="`*mf` - Mute current channel\n`*uf` - Unmute current channel",
        inline=False
    )
    
    embed.add_field(
        name="👥 User Management",
        value="`*add @user` - Register a user\n`*remove @user` - Remove a user\n`*list` - List all registered users",
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Admin",
        value="`*clearall` - Clear all users\n`*confirmclear` - Confirm clearing all users",
        inline=False
    )
    
    embed.add_field(
        name="🔒 Permissions",
        value="`*mf` and `*uf` require Manage Channels permission\n`*add` and `*remove` require Staff roles\n`*clearall` and `*confirmclear` require Administrator",
        inline=False
    )
    
    embed.set_footer(text="Bot is ready for use!")
    
    await ctx.send(embed=embed)

# ============================================
# ERROR HANDLING
# ============================================

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command!")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing required arguments! Use `*help` for usage.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument! Please check the command format.")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore unknown commands
    else:
        await ctx.send(f"❌ An error occurred: {str(error)}")
        print(f"Error: {error}")

# ============================================
# KEEP-ALIVE SERVER FOR RENDER
# ============================================

app = Flask('')

@app.route('/')
def home():
    return "🤖 Bot is alive and running!"

@app.route('/status')
def status():
    return {
        'status': 'online',
        'users_registered': len(registered_users),
        'guilds': len(bot.guilds)
    }

def run():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# ============================================
# RUN THE BOT
# ============================================

if __name__ == "__main__":
    keep_alive()
    
    # Get token from environment variable
    token = os.environ.get('DISCORD_TOKEN')
    if not token:
        print("❌ ERROR: DISCORD_TOKEN environment variable not set!")
        print("Please set it in Render dashboard or .env file")
        exit(1)
    
    print("🚀 Starting bot...")
    bot.run(token)
