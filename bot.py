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
bot.remove_command('help')

# ============================================
# ROLE IDS
# ============================================

MUTED_ROLES = [
    1531855127227535390,
    1531855163638288474,
    1531855196945252454,
    1531855186992304210,
    1531855171104280736,
    1531852594354454618,
    1531853175596908724
]

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
    await bot.change_presence(activity=discord.Game(name="*help"))

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Only reply in lobby channels
    channel_name = message.channel.name.lower()
    if "lobby" in channel_name:
        # Check if the message author is NOT staff
        has_staff_role = any(role.id in STAFF_ROLES for role in message.author.roles)
        if not has_staff_role and message.author.id not in registered_users:
            # Create a "Yes" button – staff will click this to register the player
            view = discord.ui.View()
            button = discord.ui.Button(label='Yes', style=discord.ButtonStyle.green, custom_id='add_user')
            view.add_item(button)
            await message.reply(f"Would you like to add? {message.author.mention}", view=view)

    await bot.process_commands(message)

# ============================================
# BUTTON HANDLER – Staff clicks to register the player
# ============================================

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        if interaction.data['custom_id'] == 'add_user':
            # Only staff can click this button
            clicker_has_staff = any(role.id in STAFF_ROLES for role in interaction.user.roles)
            if not clicker_has_staff:
                await interaction.response.send_message("❌ Only staff can register players.", ephemeral=True)
                return

            # Get the original message that the bot replied to
            if not interaction.message.reference:
                await interaction.response.send_message("❌ Could not find the original message.", ephemeral=True)
                return

            # Fetch the original message from the reference
            original_msg_id = interaction.message.reference.message_id
            try:
                original_msg = await interaction.channel.fetch_message(original_msg_id)
            except:
                await interaction.response.send_message("❌ Could not fetch the original message.", ephemeral=True)
                return

            player = original_msg.author  # This is the player who typed

            # Check if the player is already registered
            if player.id in registered_users:
                await interaction.response.send_message(f"❌ {player.mention} is already registered.", ephemeral=True)
                return

            # Check if player is staff (shouldn't happen, but just in case)
            if any(role.id in STAFF_ROLES for role in player.roles):
                await interaction.response.send_message("❌ Cannot register a staff member.", ephemeral=True)
                return

            # Register the player
            channel_name = interaction.channel.name
            registered_users[player.id] = {
                'registered_by': interaction.user.id,  # staff who clicked
                'channel': interaction.channel.id,
                'channel_name': channel_name,
                'timestamp': discord.utils.utcnow()
            }

            # Assign lobby role if found
            lobby_role = None
            patterns = [r'lobby[\s\-]?(\d+)', r'lobby_(\d+)', r'Lobby[\s\-]?(\d+)', r'Lobby_(\d+)']
            for pattern in patterns:
                match = re.search(pattern, channel_name, re.IGNORECASE)
                if match:
                    lobby_number = match.group(1)
                    for role in interaction.guild.roles:
                        if role.name.lower() == f'lobby {lobby_number}'.lower() or role.name.lower() == f'lobby{lobby_number}'.lower():
                            lobby_role = role
                            break
                    break

            if lobby_role:
                try:
                    await player.add_roles(lobby_role)
                except:
                    pass

            # Send confirmation embed – shows player registered by staff
            embed = discord.Embed(
                description=f"{player.mention} has been registered by {interaction.user.mention}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

# ============================================
# MUTE COMMAND
# ============================================

@bot.command(name='mf')
@commands.has_permissions(manage_channels=True)
async def mute_channel(ctx):
    try:
        everyone = ctx.guild.default_role
        await ctx.channel.set_permissions(everyone, send_messages=False)
        await ctx.send("## ❗ This Channel is Muted ❗\n### A Staff will open this channel when fills are needed")
    except Exception as e:
        await ctx.send(f"Error: {e}")

# ============================================
# UNMUTE COMMAND
# ============================================

@bot.command(name='uf')
@commands.has_permissions(manage_channels=True)
async def unmute_channel(ctx):
    try:
        everyone = ctx.guild.default_role
        await ctx.channel.set_permissions(everyone, send_messages=True)
        role_mentions = ' '.join([f'<@&{role_id}>' for role_id in MUTED_ROLES])
        await ctx.send(f"## 🟢 This Channel is Unmuted\n### Type to fill\n\n{role_mentions}")
    except Exception as e:
        await ctx.send(f"Error: {e}")

# ============================================
# ADD USER COMMAND (STAFF ONLY)
# ============================================

@bot.command(name='add')
async def add_user(ctx, member: discord.Member = None):
    # Check if user has staff role
    has_staff_role = any(role.id in STAFF_ROLES for role in ctx.author.roles)
    if not has_staff_role:
        await ctx.send("❌ You don't have permission to use this command!")
        return

    if not member:
        await ctx.send("❌ Mention a user: *add @user")
        return

    if member.bot:
        await ctx.send("❌ Can't register a bot")
        return

    if member.id in registered_users:
        await ctx.send(f"❌ {member.mention} is already registered")
        return

    # Register the user
    channel_name = ctx.channel.name
    registered_users[member.id] = {
        'registered_by': ctx.author.id,
        'channel': ctx.channel.id,
        'channel_name': channel_name,
        'timestamp': discord.utils.utcnow()
    }

    # Check for lobby role
    lobby_role = None
    patterns = [r'lobby[\s\-]?(\d+)', r'lobby_(\d+)', r'Lobby[\s\-]?(\d+)', r'Lobby_(\d+)']
    for pattern in patterns:
        match = re.search(pattern, channel_name, re.IGNORECASE)
        if match:
            lobby_number = match.group(1)
            for role in ctx.guild.roles:
                if role.name.lower() == f'lobby {lobby_number}'.lower() or role.name.lower() == f'lobby{lobby_number}'.lower():
                    lobby_role = role
                    break
            break

    if lobby_role:
        try:
            await member.add_roles(lobby_role)
        except:
            pass

    embed = discord.Embed(
        description=f"{member.mention} has been registered by {ctx.author.mention}",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

# ============================================
# REMOVE USER COMMAND (STAFF ONLY)
# ============================================

@bot.command(name='remove')
async def remove_user(ctx, member: discord.Member = None):
    has_staff_role = any(role.id in STAFF_ROLES for role in ctx.author.roles)
    if not has_staff_role:
        await ctx.send("❌ You don't have permission to use this command!")
        return

    if not member:
        await ctx.send("❌ Mention a user: *remove @user")
        return

    if member.id not in registered_users:
        await ctx.send(f"❌ {member.mention} is not registered")
        return

    user_data = registered_users[member.id]
    registered_by = bot.get_user(user_data['registered_by'])

    del registered_users[member.id]

    embed = discord.Embed(
        description=f"{member.mention} has been removed by {ctx.author.mention}",
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)

# ============================================
# LIST USERS COMMAND
# ============================================

@bot.command(name='list')
@commands.has_permissions(manage_channels=True)
async def list_users(ctx):
    if not registered_users:
        await ctx.send("No users registered")
        return

    embed = discord.Embed(
        title=f"Registered Users ({len(registered_users)})",
        color=discord.Color.blue()
    )

    for user_id, data in list(registered_users.items())[:20]:
        user = bot.get_user(user_id)
        if user:
            staff = bot.get_user(data['registered_by'])
            embed.add_field(
                name=user.name,
                value=f"Added by: {staff.name if staff else 'Unknown'}\nChannel: {data['channel_name']}",
                inline=False
            )

    await ctx.send(embed=embed)

# ============================================
# HELP COMMAND
# ============================================

@bot.command(name='help')
async def custom_help(ctx):
    embed = discord.Embed(
        title="Bot Commands",
        description="All available commands:",
        color=discord.Color.purple()
    )
    embed.add_field(
        name="Mute/Unmute",
        value="`*mf` - Mute channel\n`*uf` - Unmute channel",
        inline=False
    )
    embed.add_field(
        name="User Management",
        value="`*add @user` - Register user\n`*remove @user` - Remove user\n`*list` - List users",
        inline=False
    )
    await ctx.send(embed=embed)

# ============================================
# ERROR HANDLING
# ============================================

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ No permission")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing arguments. Use *help")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"❌ Error: {error}")

# ============================================
# KEEP-ALIVE SERVER
# ============================================

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# ============================================
# RUN BOT
# ============================================

if __name__ == "__main__":
    keep_alive()
    token = os.environ.get('DISCORD_TOKEN')
    if not token:
        print("❌ DISCORD_TOKEN not set!")
        exit(1)
    bot.run(token)
