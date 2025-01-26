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

# Add rate limiting for CoinGecko API
COINGECKO_RATE_LIMIT = 50  # requests per minute
rate_limit_counter = 0
last_reset_time = 0

# Add after other global variables
SAVE_FILE = "tracked_tokens.json"

# Add these constants near the top
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

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
        self.price_role = None
        self.last_price = 0

class GuildConfig:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.is_tracking = False
        self.tokens = {}  # Dictionary of token_id: TokenConfig

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

@tasks.loop(minutes=5)
async def update_price_info():
    """Update bot's nickname and role colors for all tracked tokens"""
    try:
        for guild_id, config in tracked_guilds.items():
            if not config.is_tracking:
                continue

            guild = bot.get_guild(guild_id)
            if not guild:
                logger.warning(f"Could not find guild {guild_id}")
                continue

            status_parts = []
            tokens_to_remove = []  # Track tokens that need to be removed
            
            for token_id, token_config in config.tokens.items():
                try:
                    current_price = await fetch_token_price(token_id)
                    if current_price is None:
                        logger.warning(f"Failed to fetch price for {token_config.token_symbol}")
                        continue

                    status_parts.append(f"{token_config.token_symbol}: ${current_price:.4f}")

                    # Handle price role
                    try:
                        if not token_config.price_role:
                            role_name = f"{token_config.token_symbol} Price"
                            token_config.price_role = discord.utils.get(guild.roles, name=role_name)
                            if not token_config.price_role:
                                token_config.price_role = await guild.create_role(
                                    name=role_name,
                                    reason=f"Role for {token_config.token_symbol} price tracking"
                                )

                        # Update role color
                        if token_config.last_price > 0:
                            new_color = discord.Color.green() if current_price > token_config.last_price else discord.Color.red()
                            await token_config.price_role.edit(color=new_color)

                        token_config.last_price = current_price
                    except discord.Forbidden:
                        logger.error(f"Missing permissions for role management in guild {guild_id}")
                    except discord.NotFound:
                        logger.error(f"Role for {token_config.token_symbol} was deleted")
                        token_config.price_role = None
                    except Exception as e:
                        logger.error(f"Error handling role for {token_config.token_symbol}: {e}")

                except Exception as e:
                    logger.error(f"Error processing {token_config.token_symbol}: {e}")
                    tokens_to_remove.append(token_id)

            # Remove failed tokens
            for token_id in tokens_to_remove:
                del config.tokens[token_id]

            # Update bot nickname
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
                except discord.Forbidden:
                    logger.error(f"Cannot change nickname in guild {guild_id}")
                except Exception as e:
                    logger.error(f"Error updating nickname in guild {guild_id}: {e}")

    except Exception as e:
        logger.error(f"Unexpected error in update_price_info: {e}")

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
        await interaction.followup.send(
            f"✅ Successfully added {token_symbol} tracking!\n"
            f"Current price: ${price:.4f}\n"
            "The bot will update prices every 5 minutes."
        )
    else:
        await interaction.followup.send(
            f"⚠️ Token added, but there was an error fetching the initial price.\n"
            "The bot will retry in the next update cycle."
        )

@bot.tree.command(name="remove_token", description="Remove a token from tracking")
@app_commands.describe(token_symbol="Token symbol (e.g., 'BTC' or 'ETH')")
@app_commands.default_permissions(administrator=True)
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
        # Remove the role if it exists
        token_config = config.tokens[token_id_to_remove]
        if token_config.price_role:
            try:
                await token_config.price_role.delete()
            except Exception as e:
                logger.error(f"Error deleting role: {e}")
        
        del config.tokens[token_id_to_remove]
        save_tracked_guilds()  # Save after removing token
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

async def cleanup_guild_roles(guild: discord.Guild):
    """Clean up orphaned price roles"""
    try:
        price_roles = [r for r in guild.roles if r.name.endswith(" Price")]
        for role in price_roles:
            token_symbol = role.name.replace(" Price", "")
            is_active = False
            if guild.id in tracked_guilds:
                for token_config in tracked_guilds[guild.id].tokens.values():
                    if token_config.token_symbol == token_symbol:
                        is_active = True
                        break
            
            if not is_active:
                try:
                    await role.delete()
                    logger.info(f"Cleaned up orphaned role {role.name}")
                except Exception as e:
                    logger.error(f"Error cleaning up role {role.name}: {e}")
    except Exception as e:
        logger.error(f"Error in cleanup_guild_roles: {e}")

@bot.tree.command(name="cleanup", description="Clean up orphaned price roles")
@app_commands.default_permissions(administrator=True)
async def cleanup(interaction: discord.Interaction):
    """Clean up orphaned price roles"""
    await interaction.response.defer()
    await cleanup_guild_roles(interaction.guild)
    await interaction.followup.send("✅ Cleaned up orphaned price roles!")

def save_tracked_guilds():
    """Save tracked guilds and tokens to file"""
    try:
        data = {}
        for guild_id, config in tracked_guilds.items():
            data[str(guild_id)] = {
                "is_tracking": config.is_tracking,
                "tokens": {
                    token_id: {
                        "symbol": token_config.token_symbol,
                        "last_price": token_config.last_price
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
                
                for token_id, token_data in guild_data["tokens"].items():
                    token_config = TokenConfig(token_id, token_data["symbol"])
                    token_config.last_price = token_data["last_price"]
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
    
    # Add guild statistics
    total_guilds = len(tracked_guilds)
    total_tokens = sum(len(config.tokens) for config in tracked_guilds.values())
    
    embed.add_field(
        name="Statistics",
        value=f"Servers: {total_guilds}\nTotal tokens tracked: {total_tokens}",
        inline=False
    )
    
    await interaction.followup.send(embed=embed)

def run_bot():
    """Run the bot"""
    bot.run(TOKEN)

if __name__ == "__main__":
    run_bot() 