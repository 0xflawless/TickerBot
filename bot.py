import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import logging
from dotenv import load_dotenv
import time
import asyncio
import json
import sys
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
DEBUG = os.getenv('DEBUG', '0').lower() in ('1', 'true', 'yes')

# Setup logging with debug level based on environment variable
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('Crypto_Tracker_Bot')

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Price tracking variables
tracked_guilds = {}  # Store guild configurations
last_price = 0

# Add rate limiting for CoinGecko API
COINGECKO_RATE_LIMIT = 50  # requests per minute
rate_limit_counter = 0
last_reset_time = 0

# Add after other global variables
SAVE_FILE = "tracked_tokens.json"

# Add these constants near the top
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Add constant at the top
MAX_UPDATE_INTERVAL = 24 * 3600  # 24 hours in seconds

# After loading environment variables
if not TOKEN:
    logger.error("No Discord token found. Make sure DISCORD_TOKEN is set in your .env file")
    sys.exit(1)

async def check_rate_limit():
    """Check and handle CoinGecko API rate limit"""
    global rate_limit_counter, last_reset_time
    current_time = int(time.time())
    
    # Reset counter every minute
    if current_time - last_reset_time >= 60:
        rate_limit_counter = 0
        last_reset_time = current_time
    
    if rate_limit_counter >= COINGECKO_RATE_LIMIT:
        await asyncio.sleep(60 - (current_time - last_reset_time))
        rate_limit_counter = 0
        last_reset_time = int(time.time())
    
    rate_limit_counter += 1

class TokenConfig:
    def __init__(self, token_id: str, token_symbol: str):
        self.token_id = token_id
        self.token_symbol = token_symbol
        self.last_price = 0
        self.price_24h_ago = 0
        self.last_24h_update = 0

class GuildConfig:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.is_tracking = False
        self.tokens = {}  # Dictionary of token_id: TokenConfig
        self.update_interval = 300  # Default 5 minutes in seconds

async def fetch_token_price(token_id: str, retry_count=0):
    """Fetch token price from CoinGecko API with retries"""
    try:
        await check_rate_limit()
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": token_id,
                "vs_currencies": "usd"
            }
            async with session.get(url, params=params) as response:
                if response.status == 429:  # Rate limit exceeded
                    if retry_count < MAX_RETRIES:
                        logger.warning(f"Rate limit reached, retrying in {RETRY_DELAY} seconds...")
                        await asyncio.sleep(RETRY_DELAY)
                        return await fetch_token_price(token_id, retry_count + 1)
                    else:
                        logger.error("Max retries reached for rate limit")
                        return None
                
                if response.status == 200:
                    data = await response.json()
                    if token_id in data and 'usd' in data[token_id]:
                        return float(data[token_id]['usd'])
                    else:
                        logger.error(f"Invalid response format for {token_id}")
                        return None
                elif response.status >= 500 and retry_count < MAX_RETRIES:
                    logger.warning(f"Server error {response.status}, retrying...")
                    await asyncio.sleep(RETRY_DELAY)
                    return await fetch_token_price(token_id, retry_count + 1)
                else:
                    logger.error(f"API returned status code: {response.status}")
                    return None
    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
        if retry_count < MAX_RETRIES:
            logger.warning(f"Network error, retrying... Error: {e}")
            await asyncio.sleep(RETRY_DELAY)
            return await fetch_token_price(token_id, retry_count + 1)
        logger.error(f"Max retries reached for network error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching price for {token_id}: {e}")
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

async def fetch_token_price_with_24h(token_id: str, retry_count=0):
    """Fetch current price and 24h change from CoinGecko"""
    try:
        await check_rate_limit()
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": token_id,
                "vs_currencies": "usd",
                "include_24hr_change": "true"
            }
            async with session.get(url, params=params) as response:
                if response.status == 429:  # Rate limit exceeded
                    if retry_count < MAX_RETRIES:
                        logger.warning(f"Rate limit reached, retrying in {RETRY_DELAY} seconds...")
                        await asyncio.sleep(RETRY_DELAY)
                        return await fetch_token_price_with_24h(token_id, retry_count + 1)
                    else:
                        logger.error("Max retries reached for rate limit")
                        return None, None
                
                if response.status == 200:
                    data = await response.json()
                    if token_id in data and 'usd' in data[token_id]:
                        price = float(data[token_id]['usd'])
                        change_24h = float(data[token_id].get('usd_24h_change', 0))
                        return price, change_24h
                    else:
                        logger.error(f"Invalid response format for {token_id}")
                        return None, None
                else:
                    logger.error(f"API returned status code: {response.status}")
                    return None, None
    except Exception as e:
        logger.error(f"Error fetching price for {token_id}: {e}")
        return None, None

def get_trend_indicator(price: float, last_price: float, change_24h: float) -> str:
    """Get trend indicator based on price movement"""
    if price > last_price:
        return "↗️"  # Up trend
    elif price < last_price:
        return "↘️"  # Down trend
    return "➡️"  # Sideways

@tasks.loop(seconds=60)
async def update_price_info():
    """Update bot nicknames for all tracked tokens"""
    try:
        current_time = int(time.time())
        guilds_to_remove = []
        
        for guild_id, config in tracked_guilds.items():
            try:
                if not config.is_tracking:
                    continue
                
                if not hasattr(config, 'last_update_time'):
                    config.last_update_time = 0
                
                if current_time - config.last_update_time < config.update_interval:
                    continue
                
                guild = bot.get_guild(guild_id)
                if not guild:
                    logger.warning(f"Could not find guild {guild_id}")
                    guilds_to_remove.append(guild_id)
                    continue
                
                config.last_update_time = current_time
                
                # Collect all price information first
                status_parts = []
                for token_id, token_config in config.tokens.items():
                    try:
                        current_price, change_24h = await fetch_token_price_with_24h(token_id)
                        if current_price is None:
                            continue

                        # Get trend indicator
                        trend = get_trend_indicator(current_price, token_config.last_price, change_24h)
                        
                        # Format price display
                        price_str = f"{token_config.token_symbol}: ${current_price:.4f}"
                        if change_24h is not None:
                            price_str += f" ({change_24h:+.1f}%) {trend}"
                        else:
                            price_str += f" {trend}"
                        
                        status_parts.append(price_str)
                        token_config.last_price = current_price

                    except Exception as e:
                        logger.error(f"Error processing token {token_id}: {e}")
                        continue

                # Update bot nickname with all prices
                if status_parts:
                    try:
                        nick = " | ".join(status_parts)
                        if len(nick) > 32:
                            # Try to make a more intelligent truncation
                            max_tokens = len(status_parts)
                            while max_tokens > 0:
                                nick = " | ".join(status_parts[:max_tokens])
                                if len(nick) <= 29:  # Leave room for "..."
                                    break
                                max_tokens -= 1
                            nick = nick[:29] + "..." if len(nick) > 32 else nick
                        
                        await guild.me.edit(nick=nick)
                    except Exception as e:
                        logger.error(f"Error updating nickname: {e}")

            except Exception as e:
                logger.error(f"Error updating guild {guild_id}: {e}")
                continue

        # Clean up removed guilds
        for guild_id in guilds_to_remove:
            del tracked_guilds[guild_id]
            save_tracked_guilds()

    except Exception as e:
        logger.error(f"Critical error in update task: {e}")
    finally:
        # Ensure the task keeps running even if there's an error
        if not update_price_info.is_running():
            update_price_info.start()

@bot.event
async def on_ready():
    """Bot startup logic"""
    logger.info(f'{bot.user} has connected to Discord!')
    try:
        load_tracked_guilds()
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
        update_price_info.start()
    except Exception as e:
        logger.error(f"Error in on_ready: {e}")

@bot.tree.command(name="add_token", description="Add a token to track in this server")
@app_commands.describe(token_id="CoinGecko token ID (e.g., 'bitcoin' or 'ethereum')")
@app_commands.default_permissions(administrator=True)
async def add_token(interaction: discord.Interaction, token_id: str):
    """Add a token to track"""
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
    
    if token_id in config.tokens:
        await interaction.followup.send(f"⚠️ {token_symbol} is already being tracked!")
        return
        
    config.tokens[token_id] = TokenConfig(token_id, token_symbol)
    config.is_tracking = True
    save_tracked_guilds()  # Save after adding token
    
    # Test price fetch
    price = await fetch_token_price(token_id)
    if price:
        interval_str = get_human_readable_time(config.update_interval)
        await interaction.followup.send(
            f"✅ Successfully added {token_symbol} tracking!\n"
            f"Current price: ${price:.4f}\n"
            f"The bot will update prices every {interval_str}."
        )
    else:
        await interaction.followup.send(
            f"⚠️ Token added, but there was an error fetching the initial price.\n"
            "The bot will retry in the next update cycle."
        )

@bot.tree.command(name="remove_token")
async def remove_token(interaction: discord.Interaction, token_symbol: str):
    """Remove a token from tracking"""
    guild_id = interaction.guild_id
    if guild_id not in tracked_guilds:
        await interaction.response.send_message("No tokens are being tracked in this server.")
        return
    
    config = tracked_guilds[guild_id]
    token_symbol = token_symbol.upper()
    
    # Find token by symbol
    token_id_to_remove = None
    for token_id, token_config in config.tokens.items():
        if token_config.token_symbol == token_symbol:
            token_id_to_remove = token_id
            break
    
    if token_id_to_remove:
        del config.tokens[token_id_to_remove]
        save_tracked_guilds()
        await interaction.response.send_message(f"✅ Removed {token_symbol} from tracking.")
        
        if not config.tokens:
            config.is_tracking = False
    else:
        await interaction.response.send_message(f"❌ {token_symbol} is not being tracked.")

@bot.tree.command(name="list_tokens", description="List all tracked tokens")
async def list_tokens(interaction: discord.Interaction):
    """List all tracked tokens and their prices"""
    guild_id = interaction.guild_id
    
    if guild_id not in tracked_guilds or not tracked_guilds[guild_id].tokens:
        await interaction.response.send_message("No tokens are being tracked in this server.")
        return
    
    config = tracked_guilds[guild_id]
    
    embed = discord.Embed(title="Tracked Tokens", color=discord.Color.blue())
    
    for token_id, token_config in config.tokens.items():
        price = await fetch_token_price(token_id)
        status = f"${price:.4f}" if price else "Unable to fetch price"
        embed.add_field(
            name=token_config.token_symbol,
            value=f"Price: {status}\nToken ID: {token_id}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

def save_tracked_guilds():
    """Save tracked guilds and tokens to file"""
    try:
        data = {}
        for guild_id, config in tracked_guilds.items():
            data[str(guild_id)] = {
                "is_tracking": config.is_tracking,
                "update_interval": config.update_interval,
                "tokens": {
                    token_id: {
                        "symbol": token_config.token_symbol,
                        "last_price": token_config.last_price,
                        "price_24h_ago": token_config.price_24h_ago,
                        "last_24h_update": token_config.last_24h_update
                    }
                    for token_id, token_config in config.tokens.items()
                }
            }
        
        with open(SAVE_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving tracked guilds: {e}")

def load_tracked_guilds():
    """Load tracked guilds and tokens from file"""
    try:
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, 'r') as f:
                data = json.load(f)
            
            for guild_id_str, guild_data in data.items():
                guild_id = int(guild_id_str)
                config = GuildConfig(guild_id)
                config.is_tracking = guild_data["is_tracking"]
                config.update_interval = guild_data.get("update_interval", 300)
                
                for token_id, token_data in guild_data["tokens"].items():
                    token_config = TokenConfig(token_id, token_data["symbol"])
                    token_config.last_price = token_data["last_price"]
                    token_config.price_24h_ago = token_data["price_24h_ago"]
                    token_config.last_24h_update = token_data["last_24h_update"]
                    config.tokens[token_id] = token_config
                
                tracked_guilds[guild_id] = config
    except Exception as e:
        logger.error(f"Error loading tracked guilds: {e}")

@bot.tree.command(name="status", description="Check bot status and API health")
async def check_status(interaction: discord.Interaction):
    """Check bot status and API health"""
    await interaction.response.defer()
    
    embed = discord.Embed(title="Bot Status", color=discord.Color.blue())
    
    # Check API health
    try:
        test_price = await fetch_token_price("bitcoin")
        api_status = "✅ Operational" if test_price else "⚠️ Having issues"
    except Exception:
        api_status = "❌ Not responding"
    
    embed.add_field(
        name="CoinGecko API",
        value=api_status,
        inline=False
    )
    
    # Add guild statistics and update interval
    guild_id = interaction.guild_id
    if guild_id in tracked_guilds:
        config = tracked_guilds[guild_id]
        interval_seconds = config.update_interval
        if interval_seconds >= 3600:
            interval_str = f"{interval_seconds / 3600:.1f} hours"
        elif interval_seconds >= 60:
            interval_str = f"{interval_seconds / 60:.1f} minutes"
        else:
            interval_str = f"{interval_seconds} seconds"
    else:
        interval_str = "5 minutes (default)"
    
    embed.add_field(
        name="Server Settings",
        value=f"Update Interval: {interval_str}",
        inline=False
    )
    
    # Add global statistics
    total_guilds = len(tracked_guilds)
    total_tokens = sum(len(config.tokens) for config in tracked_guilds.values())
    
    embed.add_field(
        name="Statistics",
        value=f"Servers: {total_guilds}\nTotal tokens tracked: {total_tokens}",
        inline=False
    )
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(
    name="set_interval",
    description="Set the price update interval (60 seconds to 24 hours)"
)
@app_commands.describe(
    seconds="Update interval in seconds (60 to 86400)"
)
@app_commands.default_permissions(administrator=True)
async def set_interval(interaction: discord.Interaction, seconds: int):
    """Set the price update interval for this server"""
    if not 60 <= seconds <= MAX_UPDATE_INTERVAL:
        await interaction.response.send_message(
            f"❌ Update interval must be between 60 seconds and 24 hours ({MAX_UPDATE_INTERVAL} seconds)."
        )
        return
    
    guild_id = interaction.guild_id
    if guild_id not in tracked_guilds:
        tracked_guilds[guild_id] = GuildConfig(guild_id)
    
    config = tracked_guilds[guild_id]
    old_interval = config.update_interval
    config.update_interval = seconds
    save_tracked_guilds()
    
    time_str = get_human_readable_time(seconds)
    old_time_str = get_human_readable_time(old_interval)
    
    await interaction.response.send_message(
        f"✅ Update interval changed from {old_time_str} to {time_str}"
    )

def get_human_readable_time(seconds: int) -> str:
    """Convert seconds to human readable time string"""
    if seconds >= 3600:
        return f"{seconds / 3600:.1f} hours"
    elif seconds >= 60:
        return f"{seconds / 60:.1f} minutes"
    return f"{seconds} seconds"

@bot.tree.command(
    name="get_interval",
    description="Show current price update interval"
)
async def get_interval(interaction: discord.Interaction):
    """Show current price update interval"""
    guild_id = interaction.guild_id
    if guild_id not in tracked_guilds:
        await interaction.response.send_message(
            "No tokens are being tracked in this server yet."
        )
        return
    
    config = tracked_guilds[guild_id]
    time_str = get_human_readable_time(config.update_interval)
    
    await interaction.response.send_message(
        f"Current update interval: {time_str}"
    )

@bot.event
async def on_guild_remove(guild):
    """Cleanup when bot is removed from a guild"""
    try:
        if guild.id in tracked_guilds:
            del tracked_guilds[guild.id]
            save_tracked_guilds()
            logger.info(f"Cleaned up tracking for removed guild {guild.id}")
    except Exception as e:
        logger.error(f"Error cleaning up removed guild {guild.id}: {e}")

def run_bot():
    """Run the bot"""
    bot.run(TOKEN)

if __name__ == "__main__":
    run_bot() 