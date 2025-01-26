import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('PDT_Bot')

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Price tracking variables
tracked_guilds = {}  # Store guild configurations
last_price = 0

class GuildConfig:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.price_role = None
        self.is_tracking = False
        self.last_price = 0
        self.token_id = None  # CoinGecko token ID
        self.token_symbol = None  # Token symbol for display

async def fetch_token_price(token_id: str):
    """Fetch token price from CoinGecko API"""
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": token_id,
                "vs_currencies": "usd"
            }
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if token_id in data:
                        return float(data[token_id]['usd'])
                    else:
                        logger.error(f"Token ID {token_id} not found in response")
                        return None
                else:
                    logger.error(f"API returned status code: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Error fetching price: {e}")
        return None

async def verify_token_id(token_id: str):
    """Verify if token ID exists on CoinGecko"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.coingecko.com/api/v3/coins/{token_id}"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['symbol'].upper(), True
                return None, False
    except Exception as e:
        logger.error(f"Error verifying token ID: {e}")
        return None, False

@tasks.loop(minutes=5)
async def update_price_info():
    """Update bot's nickname and role color for all tracked guilds"""
    try:
        for guild_id, config in tracked_guilds.items():
            if not config.is_tracking or not config.token_id:
                continue

            guild = bot.get_guild(guild_id)
            if not guild:
                continue

            current_price = await fetch_token_price(config.token_id)
            if not current_price:
                continue

            try:
                # Update bot nickname
                await guild.me.edit(nick=f"{config.token_symbol}: ${current_price:.4f}")
            except Exception as e:
                logger.error(f"Error updating nickname in guild {guild_id}: {e}")

            # Handle price role
            if not config.price_role:
                role_name = f"{config.token_symbol} Price"
                config.price_role = discord.utils.get(guild.roles, name=role_name)
                if not config.price_role:
                    try:
                        config.price_role = await guild.create_role(
                            name=role_name,
                            reason=f"Role for {config.token_symbol} price tracking"
                        )
                    except Exception as e:
                        logger.error(f"Error creating role in guild {guild_id}: {e}")
                        continue

            # Update role color
            if config.last_price > 0:
                new_color = discord.Color.green() if current_price > config.last_price else discord.Color.red()
                try:
                    await config.price_role.edit(color=new_color)
                except Exception as e:
                    logger.error(f"Error updating role color in guild {guild_id}: {e}")

            config.last_price = current_price

    except Exception as e:
        logger.error(f"Unexpected error in update_price_info: {e}")

@bot.event
async def on_ready():
    """Bot startup logic"""
    logger.info(f'{bot.user} has connected to Discord!')
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Error syncing commands: {e}")
    update_price_info.start()

@bot.tree.command(name="setup", description="Configure token tracking for this server")
@app_commands.describe(token_id="CoinGecko token ID (e.g., 'bitcoin' or 'ethereum')")
@app_commands.default_permissions(administrator=True)
async def setup(interaction: discord.Interaction, token_id: str):
    """Setup token tracking for the server"""
    await interaction.response.defer()
    
    # Verify token exists on CoinGecko
    token_symbol, valid = await verify_token_id(token_id)
    if not valid:
        await interaction.followup.send(
            "❌ Invalid token ID. Please check the token ID on CoinGecko.\n"
            "Example: For Bitcoin use 'bitcoin', for Ethereum use 'ethereum'"
        )
        return

    guild_id = interaction.guild_id
    if guild_id not in tracked_guilds:
        tracked_guilds[guild_id] = GuildConfig(guild_id)
    
    config = tracked_guilds[guild_id]
    config.token_id = token_id
    config.token_symbol = token_symbol
    config.is_tracking = True
    
    # Test price fetch
    price = await fetch_token_price(token_id)
    if price:
        await interaction.followup.send(
            f"✅ Successfully configured tracking for {token_symbol}!\n"
            f"Current price: ${price:.4f}\n"
            "The bot will update the price every 5 minutes."
        )
    else:
        await interaction.followup.send(
            f"⚠️ Token configured, but there was an error fetching the initial price.\n"
            "The bot will retry in the next update cycle."
        )

@bot.tree.command(name="price", description="Get current token price")
async def price(interaction: discord.Interaction):
    """Get current token price"""
    guild_id = interaction.guild_id
    
    if guild_id not in tracked_guilds or not tracked_guilds[guild_id].token_id:
        await interaction.response.send_message(
            "No token configured for this server. An admin needs to run /setup first."
        )
        return
    
    config = tracked_guilds[guild_id]
    current_price = await fetch_token_price(config.token_id)
    
    if current_price:
        await interaction.response.send_message(
            f"Current {config.token_symbol} Price: ${current_price:.4f}"
        )
    else:
        await interaction.response.send_message("Unable to fetch price at the moment.")

@bot.tree.command(name="start_tracking", description="Start tracking PDT price in this server")
@app_commands.default_permissions(administrator=True)
async def start_tracking(interaction: discord.Interaction):
    """Start tracking PDT price in the current server"""
    guild_id = interaction.guild_id
    
    if guild_id not in tracked_guilds:
        tracked_guilds[guild_id] = GuildConfig(guild_id)
    
    tracked_guilds[guild_id].is_tracking = True
    await interaction.response.send_message("PDT price tracking has been enabled for this server!")

@bot.tree.command(name="stop_tracking", description="Stop tracking PDT price in this server")
@app_commands.default_permissions(administrator=True)
async def stop_tracking(interaction: discord.Interaction):
    """Stop tracking PDT price in the current server"""
    guild_id = interaction.guild_id
    
    if guild_id in tracked_guilds:
        tracked_guilds[guild_id].is_tracking = False
        await interaction.response.send_message("PDT price tracking has been disabled for this server!")
    else:
        await interaction.response.send_message("Price tracking was not enabled for this server.")

@bot.tree.command(name="status", description="Check price tracking status for this server")
@app_commands.default_permissions(administrator=True)
async def status(interaction: discord.Interaction):
    """Check price tracking status"""
    guild_id = interaction.guild_id
    
    if guild_id in tracked_guilds and tracked_guilds[guild_id].is_tracking:
        await interaction.response.send_message("Price tracking is currently active in this server.")
    else:
        await interaction.response.send_message("Price tracking is not active in this server.")

def run_bot():
    """Run the bot"""
    bot.run(TOKEN)

if __name__ == "__main__":
    run_bot() 