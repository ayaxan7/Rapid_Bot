import discord
from discord.ext import commands
import asyncio
import random
import logging

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Define intents for the bot
intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.reactions = True

# Initialize bot with the defined intents
DISCORD_TOKEN = "MTMwNjExNjM5NTkzOTAwNDQ1Nw.GJgX6t.0o_oYkpMgcri5-nt3NL-ms2nqsTUv-2hV9uUIM"  # Ensure to set this in your environment variables
bot = commands.Bot(command_prefix='!', intents=intents)

class AmongUsGame:
    def __init__(self):
        self.is_game_active = False
        self.players = {}  # {user_id: {"alive": bool, "role": str}}
        self.votes = {}
        self.meeting_active = False
        self.tasks = [
            "Fix Wiring", "Empty Garbage", "Download Data", 
            "Upload Data", "Scan ID Card", "Prime Shields",
            "Clear Asteroids", "Clean O2 Filter"
        ]

class AmongUsBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games = {}  # Dictionary to store games for different servers

    @commands.command(name="startgame")
    async def start_game(self, ctx, min_players: int = 4):
        logger.info(f"Command !startgame called in {ctx.guild.name} by {ctx.author.name}")
        
        if ctx.guild.id in self.games and self.games[ctx.guild.id].is_game_active:
            await ctx.send("A game is already in progress!")
            return
            
        self.games[ctx.guild.id] = AmongUsGame()
        game = self.games[ctx.guild.id]
        
        await ctx.send(f"🚀 Starting a new Among Us game! React with 👍 to join! Minimum players needed: {min_players}")
        join_message = await ctx.send("Waiting for players...")
        await join_message.add_reaction("👍")
        
        def check(reaction, user):
            return str(reaction.emoji) == "👍" and not user.bot
            
        try:
            while len(game.players) < min_players:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                if user.id not in game.players:
                    game.players[user.id] = {"alive": True, "role": None}
                    logger.info(f"{user.name} joined the game in {ctx.guild.name} ({len(game.players)}/{min_players})")
                    await ctx.send(f"{user.name} has joined the game! ({len(game.players)}/{min_players})")
        except asyncio.TimeoutError:
            logger.warning("Game cancelled due to insufficient players.")
            await ctx.send("Not enough players joined. Game cancelled!")
            del self.games[ctx.guild.id]
            return
            
        # Assign roles
        players = list(game.players.keys())
        impostor_count = max(1, len(players) // 5)  # 20% of players are impostors
        impostors = random.sample(players, impostor_count)
        logger.info(f"Roles assigned: Impostors are {impostors}")
        
        for player_id in game.players:
            game.players[player_id]["role"] = "impostor" if player_id in impostors else "crewmate"
            
        # DM roles to players
        for player_id, player_data in game.players.items():
            user = ctx.guild.get_member(player_id)
            role = player_data["role"]
            try:
                if role == "impostor":
                    other_impostors = [ctx.guild.get_member(imp_id).name for imp_id in impostors if imp_id != player_id]
                    await user.send(f"You are an Impostor! Other impostors: {', '.join(other_impostors)}")
                else:
                    await user.send("You are a Crewmate! Complete tasks and find the impostor!")
            except Exception as e:
                logger.error(f"Failed to send DM to {user.name}: {e}")
                
        game.is_game_active = True
        await ctx.send("🎮 Game has started! Check your DMs for your role!")

    @commands.command(name="emergency")
    async def emergency_meeting(self, ctx):
        logger.info(f"{ctx.author.name} called an emergency meeting in {ctx.guild.name}")
        
        if not await self._check_game_active(ctx):
            return
            
        game = self.games[ctx.guild.id]
        if game.meeting_active:
            await ctx.send("A meeting is already in progress!")
            return
            
        if not game.players[ctx.author.id]["alive"]:
            await ctx.send("Dead players cannot call meetings!")
            return
            
        game.meeting_active = True
        game.votes = {}
        
        await ctx.send("🚨 EMERGENCY MEETING! 🚨\nDiscuss and vote using !vote @player\nVoting ends in 60 seconds!")
        
        await asyncio.sleep(60)
        
        if not game.votes:
            logger.info("No votes received; meeting ended.")
            await ctx.send("No one voted! Meeting ended.")
            game.meeting_active = False
            return
            
        # Count votes
        vote_count = {}
        for voted_id in game.votes.values():
            vote_count[voted_id] = vote_count.get(voted_id, 0) + 1
            
        # Find player with most votes
        ejected_id = max(vote_count.items(), key=lambda x: x[1])[0]
        ejected_player = ctx.guild.get_member(ejected_id)
        game.players[ejected_id]["alive"] = False
        
        logger.info(f"{ejected_player.name} was ejected with votes: {vote_count}")
        await ctx.send(f"👻 {ejected_player.name} was ejected...")
        
        # Check win conditions
        await self._check_win_condition(ctx)
        game.meeting_active = False

    @commands.command(name="vote")
    async def vote(self, ctx, player: discord.Member):
        logger.info(f"{ctx.author.name} voted for {player.name} in {ctx.guild.name}")
        
        if not await self._check_game_active(ctx):
            return
            
        game = self.games[ctx.guild.id]
        if not game.meeting_active:
            await ctx.send("No meeting is currently active!")
            return
            
        if not game.players[ctx.author.id]["alive"]:
            await ctx.send("Dead players cannot vote!")
            return
            
        if player.id not in game.players:
            await ctx.send("That player is not in the game!")
            return
            
        game.votes[ctx.author.id] = player.id
        await ctx.send(f"{ctx.author.name} has voted!")
        
    async def _check_game_active(self, ctx):
        if ctx.guild.id not in self.games or not self.games[ctx.guild.id].is_game_active:
            await ctx.send("No game is currently active! Start one with !startgame")
            return False
        return True
        
    async def _check_win_condition(self, ctx):
        game = self.games[ctx.guild.id]
        alive_crew = sum(1 for p in game.players.values() if p["alive"] and p["role"] == "crewmate")
        alive_impostors = sum(1 for p in game.players.values() if p["alive"] and p["role"] == "impostor")
        
        if alive_impostors == 0:
            await ctx.send("👨‍🚀 Crewmates Win! All impostors have been ejected!")
            game.is_game_active = False
            logger.info("Game ended: Crewmates Win")
        elif alive_impostors >= alive_crew:
            await ctx.send("👻 Impostors Win! They have eliminated enough crewmates!")
            game.is_game_active = False
            logger.info("Game ended: Impostors Win")

def setup(bot):
    bot.add_cog(AmongUsBot(bot))

# Run the bot
bot.run(DISCORD_TOKEN)
