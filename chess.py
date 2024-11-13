import discord
from discord.ext import commands
import chess
import requests
import random
import os
import firebase_admin
from firebase_admin import credentials, auth, firestore
import discord
from discord.ext import commands
import asyncio
import aiohttp

# Discord bot setup with message content intent
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Dictionary to store active games for each user
games = {}

# Lichess API endpoint for cloud Stockfish analysis
LICHESS_ANALYSIS_URL = "https://lichess.org/api/cloud-eval"
LICHESS_API_TOKEN = "lip_KHYG6MpXrfPLCYCPCm6l"
FIREBASE_CERT_PATH = "google-services.json"
def create_board_image():
    """Create a simple text representation of the chess board"""
    return """
    Current board position:
    8 ♜ ♞ ♝ ♛ ♚ ♝ ♞ ♜
    7 ♟ ♟ ♟ ♟ ♟ ♟ ♟ ♟
    6 · · · · · · · ·
    5 · · · · · · · ·
    4 · · · · · · · ·
    3 · · · · · · · ·
    2 ♙ ♙ ♙ ♙ ♙ ♙ ♙ ♙
    1 ♖ ♘ ♗ ♕ ♔ ♗ ♘ ♖
      a b c d e f g h
    """

def get_best_move(fen):
    headers = {"Authorization": f"Bearer {LICHESS_API_TOKEN}"}
    response = requests.get(
        LICHESS_ANALYSIS_URL,
        params={'fen': fen},
        headers=headers
    )
    if response.status_code == 200:
        data = response.json()
        if 'pvs' in data and len(data['pvs']) > 0:
            best_move_sequence = data['pvs'][0]['moves']
            best_move = best_move_sequence.split()[0]
            return best_move
    return None

@bot.event
async def on_ready():
    print(f'Bot is ready! Logged in as {bot.user.name}')

@bot.command(name="start")
async def start_chess_game(ctx):
    await ctx.send("Welcome to Chess! Please choose your color using !color white or !color black")

@bot.command(name="color")
async def choose_color(ctx, color: str):
    if color.lower() not in ["white", "black"]:
        await ctx.send("Please choose either 'white' or 'black'.")
        return

    # Clear any existing game for this user
    if ctx.author.id in games:
        del games[ctx.author.id]

    games[ctx.author.id] = {
        "board": chess.Board(),
        "color": color.lower(),
        "draw_attempts": 0
    }
    
    board = games[ctx.author.id]["board"]
    await ctx.send(f"Current position:\n\n{board}\n")
    
    if color.lower() == "black":
        best_move_uci = get_best_move(board.fen())
        if best_move_uci:
            bot_move = chess.Move.from_uci(best_move_uci)
            if bot_move in board.legal_moves:
                san_move = board.san(bot_move)
                board.push(bot_move)
                await ctx.send(f"You've chosen black! Bot's opening move: {san_move}\n\n{board}\n\nYour move!")
            else:
                await ctx.send("Error starting game. Please try again.")
                del games[ctx.author.id]
    else:
        await ctx.send(f"You've chosen white! Make your move using !move <your move> in UCI format (e.g., e2e4)")

@bot.command(name="move")
async def make_move(ctx, move: str):
    game_data = games.get(ctx.author.id)
    if not game_data:
        await ctx.send("You don't have an active game. Start one with !start!")
        return

    board = game_data["board"]
    user_color = game_data["color"]

    # Verify turn
    is_whites_turn = board.turn
    player_is_white = user_color == "white"
    
    if is_whites_turn != player_is_white:
        await ctx.send("It's not your turn!")
        return

    # Process player's move
    try:
        player_move = chess.Move.from_uci(move)
        if player_move in board.legal_moves:
            san_move = board.san(player_move)
            board.push(player_move)
            await ctx.send(f"Your move: {san_move}\n\n{board}\n")
            
            # Check game end after player move
            if board.is_game_over():
                if board.is_checkmate():
                    await ctx.send("Checkmate! You won! 🎉")
                elif board.is_stalemate():
                    await ctx.send("Stalemate! It's a draw. 🤝")
                elif board.is_insufficient_material():
                    await ctx.send("Draw due to insufficient material! 🤝")
                del games[ctx.author.id]
                return
        else:
            await ctx.send("Invalid move! Please make sure your move is legal.")
            return
    except ValueError:
        await ctx.send("Invalid move format! Use standard UCI notation, e.g., e2e4.")
        return

    # Get bot's move
    best_move_uci = get_best_move(board.fen())
    if best_move_uci:
        try:
            bot_move = chess.Move.from_uci(best_move_uci)
            if bot_move in board.legal_moves:
                san_move = board.san(bot_move)
                board.push(bot_move)
                await ctx.send(f"Bot's move: {san_move}\n\n{board}\n\nYour move!")
                
                # Check game end after bot move
                if board.is_game_over():
                    if board.is_checkmate():
                        await ctx.send("Checkmate! The bot won! Better luck next time! ♟")
                    elif board.is_stalemate():
                        await ctx.send("Stalemate! It's a draw. 🤝")
                    elif board.is_insufficient_material():
                        await ctx.send("Draw due to insufficient material! 🤝")
                    del games[ctx.author.id]
            else:
                await ctx.send("Bot made an illegal move. Please try your move again.")
                board.pop()
        except ValueError:
            await ctx.send("Error processing bot's move. Please try again.")
            board.pop()
    else:
        await ctx.send("Failed to retrieve a move from Lichess. Please try again.")
        board.pop()

@bot.command(name="board")
async def show_board(ctx):
    game_data = games.get(ctx.author.id)
    if game_data:
        board = game_data["board"]
        await ctx.send(f"Current position:\n\n{board}\n\nFEN: {board.fen()}")
    else:
        await ctx.send("You don't have an active game. Start one with !start!")

@bot.command(name="resign")
async def resign_game(ctx):
    game_data = games.get(ctx.author.id)
    if not game_data:
        await ctx.send("You don't have an active game to resign!")
        return
    
    user_color = game_data["color"]
    await ctx.send(f"Game Over! {ctx.author.name} ({user_color}) resigns. The bot wins! ⚔")
    del games[ctx.author.id]

@bot.command(name="draw")
async def offer_draw(ctx):
    game_data = games.get(ctx.author.id)
    if not game_data:
        await ctx.send("You don't have an active game to offer a draw!")
        return

    if game_data["draw_attempts"] >= 3:
        await ctx.send("You have already used all 3 draw offers in this game!")
        return

    game_data["draw_attempts"] += 1
    remaining_attempts = 3 - game_data["draw_attempts"]

    if random.random() < 0.01:
        await ctx.send("The bot accepts your draw offer. Game drawn by agreement! 🤝")
        del games[ctx.author.id]
    else:
        await ctx.send(f"The bot declines your draw offer. The game continues! You have {remaining_attempts} draw offer{'s' if remaining_attempts != 1 else ''} remaining.")

@bot.command(name="chess")
async def chess_help(ctx):
    help_text = """
*Chess Bot Commands:*
!start - Start a new chess game
!color <white/black> - Choose your color
!move <move> - Make a move (e.g., !move e2e4)
!board - Show current board position
!resign - Resign the current game
!draw - Offer a draw (max 3 attempts per game)
!chess - Show this help message

*Move Format:*
Use UCI notation (e.g., e2e4, g1f3) for moves
- The first two characters are the starting square
- The last two characters are the target square
- For pawn promotion, add the piece letter (e.g., e7e8q for queen)
"""
    await ctx.send(help_text)
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
bot.run("MTMwNjExNjM5NTkzOTAwNDQ1Nw.GJgX6t.0o_oYkpMgcri5-nt3NL-ms2nqsTUv-2hV9uUIM")