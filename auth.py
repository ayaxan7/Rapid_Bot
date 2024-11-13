import os
import firebase_admin
from firebase_admin import credentials, auth, firestore
import discord
from discord.ext import commands
import asyncio
import aiohttp  # For async HTTP requests

# Load sensitive data from environment variables
DISCORD_TOKEN = "MTMwNjExNjM5NTkzOTAwNDQ1Nw.GJgX6t.0o_oYkpMgcri5-nt3NL-ms2nqsTUv-2hV9uUIM"  # Ensure to set this in your environment variables
FIREBASE_CERT_PATH = "google-services.json"

# Initialize Firebase Admin SDK
print("Initializing Firebase Admin SDK...")
try:
    cred = credentials.Certificate(FIREBASE_CERT_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase Admin initialized successfully.")
except Exception as e:
    print(f"Failed to initialize Firebase Admin: {e}")

# Initialize Discord bot with specific intents
print("Setting up Discord bot...")
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Channel and role configuration with specific IDs and admin IDs
ROLE_CHANNEL_CONFIG = {
    'HR': {
        'channels': [1306150186363518976],
        'color': discord.Color.blue(),
        'admin_id': 745718514450563185
    },
    'Technical': {
        'channels': [1306158852990959649],
        'color': discord.Color.green(),
        'admin_id': 745718514450563185
    },
    'Logistics': {
        'channels': [1306165213006921738],
        'color': discord.Color.orange(),
        'admin_id': 745718514450563185
    }
}

async def setup_role_permissions(guild):
    """Create roles if they don't exist and return a dictionary of roles"""
    roles = {}
    for role_name, config in ROLE_CHANNEL_CONFIG.items():
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            try:
                role = await guild.create_role(
                    name=role_name,
                    color=config['color'],
                    reason="Role created for department access"
                )
                print(f"Created role {role_name} in {guild.name}")
            except Exception as e:
                print(f"Error creating role {role_name}: {e}")
        roles[role_name] = role
    return roles

async def notify_admin(guild, user, role_name):
    """Notify the admin about a new user request"""
    try:
        admin_id = ROLE_CHANNEL_CONFIG[role_name]['admin_id']
        admin = await guild.fetch_member(admin_id)
        
        if admin:
            channel_names = [guild.get_channel(channel_id).name 
                             for channel_id in ROLE_CHANNEL_CONFIG[role_name]['channels']
                             if guild.get_channel(channel_id)]
            
            dm_channel = await admin.create_dm()
            await dm_channel.send(
                f"New access request:\n"
                f"User: {user.name} ({user.id})\n"
                f"Role: {role_name}\n"
                f"Requested Channels: {', '.join(channel_names)}\n\n"
                f"To grant access, please manually add them to the appropriate channels."
            )
            return True
        return False
    except Exception as e:
        print(f"Error notifying admin: {e}")
        return False

async def create_user(original_ctx, dm_channel, email, password, role, author):
    """Create a new Firebase user and notify the admin"""
    try:
        user_record = auth.create_user(email=email, password=password)
        users_ref = db.collection('users')
        users_ref.document(user_record.uid).set({
            'email': email,
            'role': role,
            'discord_id': str(author.id)
        })

        guild = original_ctx.guild
        if guild:
            await setup_role_permissions(guild)
            if await notify_admin(guild, author, role):
                await dm_channel.send(
                    f"{author.mention} User {email} created successfully with role: {role}. "
                    "An admin has been notified to process your channel access request."
                )
            else:
                await dm_channel.send(
                    f"{author.mention} User created but there was an issue notifying the admin. "
                    "Please contact an administrator directly."
                )

        print(f"User {email} created with role: {role} and UID: {user_record.uid}")
        return user_record
    except Exception as e:
        await dm_channel.send(f"{author.mention} Error: Could not create user. {str(e)}")
        print(f"Firebase error: {e}")
        return None

# New command to fetch a random dad joke
@bot.command(name='dadjoke')
async def dad_joke(ctx):
    """Command to fetch a random dad joke"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://icanhazdadjoke.com/slack') as response:
                if response.status == 200:
                    joke_data = await response.json()
                    joke = joke_data['attachments'][0]['text']
                    await ctx.send(f"Here's a dad joke for you:\n{joke}")
                else:
                    await ctx.send("Sorry, I couldn't fetch a joke at the moment.")
    except Exception as e:
        await ctx.send(f"An error occurred while fetching the joke: {e}")

@bot.command(name='adduser')
async def add_user(ctx):
    """Command to add a new user through DM interaction"""
    if not isinstance(ctx.channel, discord.DMChannel):
        original_ctx = ctx
        await ctx.send(f"{ctx.author.mention} I'll send you a DM to collect the user details.")
        try:
            dm_channel = await ctx.author.create_dm()
        except discord.Forbidden:
            await ctx.send(f"{ctx.author.mention} I couldn't send you a DM. Please enable DMs from server members.")
            return
    else:
        await ctx.send(f"{ctx.author.mention} This command must be used in a server channel, not in DMs.")
        return

    try:
        await dm_channel.send(f"{ctx.author.mention} Please provide the email address for the new user:")
        email_msg = await bot.wait_for('message', check=lambda m: m.author == ctx.author and isinstance(m.channel, discord.DMChannel), timeout=120.0)
        email = email_msg.content

        await dm_channel.send(f"{ctx.author.mention} Please provide the password (minimum 6 characters):")
        password_msg = await bot.wait_for('message', check=lambda m: m.author == ctx.author and isinstance(m.channel, discord.DMChannel), timeout=60.0)
        password = password_msg.content

        role_msg = await dm_channel.send(f"{ctx.author.mention} Please provide the professional role (1: HR, 2: Technical, 3: Logistics):")
        role_content = await bot.wait_for('message', check=lambda m: m.author == ctx.author and isinstance(m.channel, discord.DMChannel), timeout=60.0)
        role = {'1': 'HR', '2': 'Technical', '3': 'Logistics'}.get(role_content.content, None)

        # New feature: Asking for interests
        await dm_channel.send(f"{ctx.author.mention} Please share your interests (e.g., programming, gaming, tech, etc.):")
        interests_msg = await bot.wait_for('message', check=lambda m: m.author == ctx.author and isinstance(m.channel, discord.DMChannel), timeout=120.0)
        interests = interests_msg.content

        user_record = await create_user(original_ctx, dm_channel, email, password, role, ctx.author)
        if user_record:
            # Save interests in Firebase (optional)
            users_ref = db.collection('users')
            users_ref.document(user_record.uid).update({
                'interests': interests  # Store interests in the user document
            })
            await dm_channel.send(f"{ctx.author.mention} User creation process completed successfully!")

    except asyncio.TimeoutError:
        await dm_channel.send(f"{ctx.author.mention} The request timed out. Please try again using the !adduser command.")
    except Exception as e:
        await dm_channel.send(f"{ctx.author.mention} An unexpected error occurred: {str(e)}\nPlease try again using the !adduser command.")
        print(f"Error in add_user: {e}")


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord and is active in {len(bot.guilds)} servers')
    for guild in bot.guilds:
        await setup_role_permissions(guild)
        print(f"Set up roles in {guild.name}")

print("Starting Discord bot...")
bot.run(DISCORD_TOKEN)