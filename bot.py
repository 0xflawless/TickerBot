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
from web3 import Web3
import requests

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
DEBUG = os.getenv('DEBUG', '0').lower() in ('1', 'true', 'yes')

# Berachain RPC configuration
BERACHAIN_RPC_URL = os.getenv('BERACHAIN_RPC_URL', 'https://rpc.berachain.com/')
w3 = Web3(Web3.HTTPProvider(BERACHAIN_RPC_URL))

# Smart contract addresses (from Goldilend)
GOLDISWAP_ADDRESS = "0xb7E448E5677D212B8C8Da7D6312E8Afc49800466"
GOLDILOCKED_ADDRESS = "0xbf2E152f460090aCE91A456e3deE5ACf703f27aD"
TREASURY_ADDRESS = "0x895614c89beC7D11454312f740854d08CbF57A78"

# ABI for smart contract interactions
GOLDISWAP_ABI = [
    {
        "inputs": [],
        "name": "fsl",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "psl", 
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

GOLDILOCKED_ABI = [
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

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
        self.display_role = None  # Add this for the display role
        self.last_price = 0

class GuildConfig:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.is_tracking = False
        self.tokens = {}  # Dictionary of token_id: TokenConfig
        self.update_interval = 300  # Default 5 minutes in seconds
        self.config_channel_id = None  # Channel for admin commands
        self.display_channel_id = None  # Channel for price display

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

# PRG Price Calculation Functions (from Goldilend smart contracts)
def floor_price(fsl: float, supply: float) -> float:
    """Calculate floor price from FSL and supply"""
    if supply == 0:
        return 0
    return fsl / supply

def market_price(fsl: float, psl: float, supply: float) -> float:
    """Calculate market price using bonding curve formula"""
    if supply == 0:
        return 0
    floor = floor_price(fsl, supply)
    if fsl == 0:
        return 0
    return floor + (psl / supply) * ((psl + fsl) / fsl) ** 6

async def fetch_prg_price_from_contract():
    """Fetch PRG price directly from Goldilend smart contracts"""
    try:
        # Create contract instances
        goldiswap_contract = w3.eth.contract(
            address=Web3.to_checksum_address(GOLDISWAP_ADDRESS),
            abi=GOLDISWAP_ABI
        )
        goldilocked_contract = w3.eth.contract(
            address=Web3.to_checksum_address(GOLDILOCKED_ADDRESS),
            abi=GOLDILOCKED_ABI
        )
        
        # Fetch contract data
        fsl = goldiswap_contract.functions.fsl().call()
        psl = goldiswap_contract.functions.psl().call()
        supply = goldiswap_contract.functions.totalSupply().call()
        prg_supply = goldilocked_contract.functions.totalSupply().call()
        treasury_balance = goldilocked_contract.functions.balanceOf(
            Web3.to_checksum_address(TREASURY_ADDRESS)
        ).call()
        
        # Convert from wei to ether
        fsl_float = w3.from_wei(fsl, 'ether')
        psl_float = w3.from_wei(psl, 'ether')
        supply_float = w3.from_wei(supply, 'ether')
        
        # Calculate PRG price using bonding curve
        market = market_price(fsl_float, psl_float, supply_float)
        floor = floor_price(fsl_float, supply_float)
        prg_value = market - floor
        
        # Calculate circulating supply (total - treasury)
        circulating_supply = w3.from_wei(prg_supply - treasury_balance, 'ether')
        
        logger.info(f"PRG Contract Data - FSL: {fsl_float}, PSL: {psl_float}, Supply: {supply_float}")
        logger.info(f"PRG Price: {prg_value}, Market: {market}, Floor: {floor}")
        
        return {
            'price': prg_value,
            'market_price': market,
            'floor_price': floor,
            'circulating_supply': circulating_supply,
            'fsl': fsl_float,
            'psl': psl_float,
            'supply': supply_float
        }
        
    except Exception as e:
        logger.error(f"Error fetching PRG price from contract: {e}")
        return None

def get_trend_indicator(price: float, last_price: float, change_24h: float) -> str:
    """Get trend indicator based on price movement"""
    if price > last_price:
        return "+"  # Up trend
    elif price < last_price:
        return "-"  # Down trend
    return "="  # Sideways

async def create_or_get_role(guild: discord.Guild, name: str, reason: str) -> discord.Role:
    """Create or get a role with the given name"""
    role = discord.utils.get(guild.roles, name=name)
    if not role:
        try:
            role = await guild.create_role(name=name, reason=reason)
            # Move role to a higher position so it can be displayed
            positions = {role: guild.me.top_role.position - 1}
            await guild.edit_role_positions(positions)
        except Exception as e:
            logger.error(f"Error creating role {name}: {e}")
            return None
    return role

@tasks.loop(seconds=60)
async def update_price_info():
    """Update bot nicknames and status for all tracked tokens"""
    try:
        current_time = int(time.time())
        logger.info("Running price update check...")
        
        # Track all 24h changes for global status
        all_24h_changes = []
        
        for guild_id, config in tracked_guilds.items():
            try:
                if not config.is_tracking:
                    logger.debug(f"Guild {guild_id} is not tracking")
                    continue
                
                guild = bot.get_guild(guild_id)
                if not guild:
                    logger.warning(f"Could not find guild {guild_id}")
                    continue
                
                logger.debug(f"Processing guild: {guild.name} ({guild_id})")
                
                # Reset all_24h_changes for each guild
                all_24h_changes = []  # Move this here to reset for each guild
                
                # Collect all price information first
                status_parts = []
                for token_id, token_config in config.tokens.items():
                    try:
                        # Handle PRG token differently - fetch from smart contract
                        if token_id == "prg" or token_config.token_symbol == "PRG":
                            prg_data = await fetch_prg_price_from_contract()
                            if prg_data is None:
                                continue
                            
                            current_price = prg_data['price']
                            # For PRG, we don't have 24h change from contract, so use 0
                            change_24h = 0
                            
                            logger.debug(f"Got PRG price from contract: ${current_price:.6f}")
                        else:
                            # Regular CoinGecko tokens
                            current_price, change_24h = await fetch_token_price_with_24h(token_id)
                            if current_price is None:
                                continue
                            
                            logger.debug(f"Got price for {token_config.token_symbol}: ${current_price:.4f}, 24h: {change_24h:+.1f}%")
                        
                        # Get trend indicator
                        trend = get_trend_indicator(current_price, token_config.last_price, change_24h)
                        
                        # Format price display (without 24h change)
                        if token_config.token_symbol == "PRG":
                            # Use 4 decimal places for PRG to fit within Discord limit
                            price_str = f"{token_config.token_symbol}: ${current_price:.4f}{trend}"
                        else:
                            price_str = f"{token_config.token_symbol}: ${current_price:.4f}{trend}"
                        status_parts.append(price_str)
                        
                        # Track 24h change for this guild's status
                        if change_24h is not None:
                            all_24h_changes.append((token_config.token_symbol, change_24h))
                        
                        token_config.last_price = current_price

                    except Exception as e:
                        logger.error(f"Error processing token {token_id}: {e}")
                        continue

                # Update bot nickname with prices
                if status_parts:
                    try:
                        nick = " | ".join(status_parts)
                        if len(nick) > 32:
                            max_tokens = len(status_parts)
                            while max_tokens > 0:
                                nick = " | ".join(status_parts[:max_tokens])
                                if len(nick) <= 29:
                                    break
                                max_tokens -= 1
                            nick = nick[:29] + "..." if len(nick) > 32 else nick
                        
                        logger.debug(f"Setting nickname in {guild.name} to: {nick}")
                        await guild.me.edit(nick=nick)
                        
                        # Update status for this guild's token only
                        if all_24h_changes:
                            symbol, change = all_24h_changes[0]  # Get first (and only) token
                            status = f"24h: {symbol} {change:+.1f}%"
                            logger.debug(f"Setting status in {guild.name} to: {status}")
                            await bot.change_presence(
                                activity=discord.Activity(
                                    type=discord.ActivityType.watching,
                                    name=status
                                )
                            )
                    except Exception as e:
                        logger.error(f"Error updating display in {guild.name}: {e}")

            except Exception as e:
                logger.error(f"Error updating guild {guild_id}: {e}")
                continue

    except Exception as e:
        logger.error(f"Critical error in update task: {e}")

@bot.event
async def on_ready():
    """Bot startup logic"""
    logger.info(f'{bot.user} has connected to Discord!')
    try:
        load_tracked_guilds()
        
        # Force sync all commands
        logger.info("Syncing commands...")
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands")
        
        # Stop the task if it's running
        if update_price_info.is_running():
            update_price_info.stop()
        
        # Start the task
        update_price_info.start()
        logger.info("Price update task started")
        
        # Log currently tracked guilds and tokens
        for guild_id, config in tracked_guilds.items():
            guild = bot.get_guild(guild_id)
            guild_name = guild.name if guild else "Unknown Guild"
            logger.info(f"Tracking in {guild_name} ({guild_id}):")
            for token_id, token_config in config.tokens.items():
                logger.info(f"- {token_config.token_symbol} ({token_id})")
    except Exception as e:
        logger.error(f"Error in on_ready: {e}")

@bot.tree.command(name="add_token", description="Add a token to track in this server")
@app_commands.describe(token_id="CoinGecko token ID (e.g., 'bitcoin' or 'ethereum')")
@app_commands.default_permissions(administrator=True)
async def add_token(interaction: discord.Interaction, token_id: str):
    """Add a token to track"""
    await interaction.response.defer()
    
    guild_id = interaction.guild_id
    if guild_id not in tracked_guilds:
        tracked_guilds[guild_id] = GuildConfig(guild_id)
    
    config = tracked_guilds[guild_id]
    
    # Check if any token is already being tracked
    if config.tokens:
        await interaction.followup.send(
            "⚠️ **Only one token can be tracked per bot instance!**\n\n"
            "To track multiple tokens, you need to:\n"
            "1. Create additional bot applications in Discord Developer Portal\n"
            "2. Get tokens for each bot\n"
            "3. Run separate instances of the bot with different tokens\n\n"
            "See the README.md for instructions on setting up multiple bots."
        )
        return

    # Handle PRG token specially
    if token_id.lower() == "prg":
        token_symbol = "PRG"
        config.tokens[token_id] = TokenConfig(token_id, token_symbol)
        config.is_tracking = True
        save_tracked_guilds()
        
        # Test PRG price fetch from contract
        prg_data = await fetch_prg_price_from_contract()
        if prg_data:
            price = prg_data['price']
            interval_str = get_human_readable_time(config.update_interval)
            await interaction.followup.send(
                f"✅ Successfully added PRG tracking from Goldilend smart contract!\n"
                f"Current PRG price: ${price:.6f}\n"
                f"Market price: ${prg_data['market_price']:.6f}\n"
                f"Floor price: ${prg_data['floor_price']:.6f}\n"
                f"The bot will update prices every {interval_str}."
            )
        else:
            await interaction.followup.send(
                f"⚠️ PRG token added, but there was an error fetching the initial price from contract.\n"
                "The bot will retry in the next update cycle."
            )
        return
    
    # Regular CoinGecko token verification
    token_symbol, valid = await verify_token_id(token_id)
    if not valid:
        await interaction.followup.send(
            "❌ Invalid token ID. Please check the token ID on CoinGecko.\n"
            "Example: For Bitcoin use 'bitcoin', for Ethereum use 'ethereum'\n"
            "For PRG from Goldilend contract, use 'prg'"
        )
        return
    
    if token_id in config.tokens:
        await interaction.followup.send(f"⚠️ {token_symbol} is already being tracked!")
        return
        
    config.tokens[token_id] = TokenConfig(token_id, token_symbol)
    config.is_tracking = True
    save_tracked_guilds()
    
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
            # Delete the role if it exists
            if token_config.display_role:
                try:
                    await token_config.display_role.delete()
                except Exception as e:
                    logger.error(f"Error deleting role: {e}")
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
        # Handle PRG token differently
        if token_id == "prg" or token_config.token_symbol == "PRG":
            prg_data = await fetch_prg_price_from_contract()
            if prg_data:
                price = prg_data['price']
                status = f"${price:.6f} (from contract)"
                embed.add_field(
                    name=token_config.token_symbol,
                    value=f"Price: {status}\nMarket: ${prg_data['market_price']:.6f}\nFloor: ${prg_data['floor_price']:.6f}\nSource: Goldilend Contract",
                    inline=False
                )
            else:
                embed.add_field(
                    name=token_config.token_symbol,
                    value="Price: Unable to fetch from contract\nSource: Goldilend Contract",
                    inline=False
                )
        else:
            # Regular CoinGecko tokens
            price = await fetch_token_price(token_id)
            status = f"${price:.4f}" if price else "Unable to fetch price"
            embed.add_field(
                name=token_config.token_symbol,
                value=f"Price: {status}\nToken ID: {token_id}\nSource: CoinGecko",
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
                "config_channel_id": config.config_channel_id,
                "display_channel_id": config.display_channel_id,
                "tokens": {
                    token_id: {
                        "symbol": token_config.token_symbol,
                        "last_price": token_config.last_price
                    }
                    for token_id, token_config in config.tokens.items()
                }
            }
        
        temp_file = f"{SAVE_FILE}.tmp"
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=4)
        os.replace(temp_file, SAVE_FILE)
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
                config.config_channel_id = guild_data.get("config_channel_id")
                config.display_channel_id = guild_data.get("display_channel_id")
                
                for token_id, token_data in guild_data["tokens"].items():
                    token_config = TokenConfig(token_id, token_data["symbol"])
                    token_config.last_price = token_data.get("last_price", 0)
                    config.tokens[token_id] = token_config
                
                tracked_guilds[guild_id] = config
    except Exception as e:
        logger.error(f"Error loading tracked guilds: {e}")
        if os.path.exists(SAVE_FILE):
            backup_name = f"{SAVE_FILE}.backup.{int(time.time())}"
            try:
                os.rename(SAVE_FILE, backup_name)
                logger.info(f"Backed up corrupted save file to {backup_name}")
            except Exception as e:
                logger.error(f"Failed to backup corrupted save file: {e}")

@bot.tree.command(name="status", description="Check bot status and API health")
async def check_status(interaction: discord.Interaction):
    """Check bot status and API health"""
    await interaction.response.defer()
    
    embed = discord.Embed(title="Bot Status", color=discord.Color.blue())
    
    # Check CoinGecko API health
    try:
        test_price = await fetch_token_price("bitcoin")
        coingecko_status = "✅ Operational" if test_price else "⚠️ Having issues"
    except Exception:
        coingecko_status = "❌ Not responding"
    
    # Check Berachain/PRG contract health
    try:
        prg_data = await fetch_prg_price_from_contract()
        contract_status = "✅ Operational" if prg_data else "⚠️ Having issues"
        if prg_data:
            contract_status += f"\nPRG Price: ${prg_data['price']:.6f}"
    except Exception:
        contract_status = "❌ Not responding"
    
    embed.add_field(
        name="CoinGecko API",
        value=coingecko_status,
        inline=True
    )
    
    embed.add_field(
        name="Berachain/PRG Contract",
        value=contract_status,
        inline=True
    )
    
    # Add guild-specific information
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
        
        # Show tokens tracked in this server
        tokens_in_server = len(config.tokens)
        token_list = ", ".join(token_config.token_symbol for token_config in config.tokens.values())
    else:
        interval_str = "5 minutes (default)"
        tokens_in_server = 0
        token_list = "None"
    
    embed.add_field(
        name="Server Settings",
        value=f"Update Interval: {interval_str}\n"
              f"Tokens in this server: {token_list}",
        inline=False
    )
    
    # Add global statistics (count unique tokens)
    total_guilds = len(tracked_guilds)
    unique_tokens = {
        token_config.token_symbol 
        for guild in tracked_guilds.values() 
        for token_config in guild.tokens.values()
    }
    
    embed.add_field(
        name="Global Statistics",
        value=f"Total Servers: {total_guilds}\n"
              f"Unique Tokens Tracked: {len(unique_tokens)}",
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

@bot.tree.command(
    name="force_update",
    description="Force an immediate price update"
)
@app_commands.default_permissions(administrator=True)
async def force_update(interaction: discord.Interaction):
    """Force an immediate price update"""
    await interaction.response.defer()
    
    guild_id = interaction.guild_id
    if guild_id not in tracked_guilds:
        await interaction.followup.send("No tokens are being tracked in this server.")
        return
    
    config = tracked_guilds[guild_id]
    if not config.tokens:
        await interaction.followup.send("No tokens are being tracked in this server.")
        return
    
    try:
        # Reset the last update time to force an update
        config.last_update_time = 0
        # Run the update
        await update_price_info()
        await interaction.followup.send("✅ Forced price update completed!")
    except Exception as e:
        logger.error(f"Error in force_update: {e}")
        await interaction.followup.send("❌ Error forcing update. Check logs for details.")

@bot.tree.command(
    name="sync",
    description="Sync all slash commands (Admin only)"
)
@app_commands.default_permissions(administrator=True)
async def sync_slash_commands(interaction: discord.Interaction):
    """Sync all slash commands"""
    await interaction.response.defer()
    
    try:
        synced = await bot.tree.sync()
        await interaction.followup.send(
            f"✅ Successfully synced {len(synced)} commands!\n"
            "All commands should now be available."
        )
        logger.info(f"Manually synced {len(synced)} commands")
    except Exception as e:
        logger.error(f"Error syncing commands: {e}")
        await interaction.followup.send("❌ Failed to sync commands!")

@bot.tree.command(
    name="setup",
    description="Setup bot configuration and display channels"
)
@app_commands.describe(
    config_channel="Channel for bot configuration commands",
    display_channel="Channel where price updates will be shown"
)
@app_commands.default_permissions(administrator=True)
async def setup(
    interaction: discord.Interaction,
    config_channel: discord.TextChannel,
    display_channel: discord.TextChannel
):
    """Setup bot configuration"""
    await interaction.response.defer()
    
    guild_id = interaction.guild_id
    if guild_id not in tracked_guilds:
        tracked_guilds[guild_id] = GuildConfig(guild_id)
    
    config = tracked_guilds[guild_id]
    
    # Save channel IDs
    config.config_channel_id = config_channel.id
    config.display_channel_id = display_channel.id
    save_tracked_guilds()
    
    # Create setup message
    embed = discord.Embed(
        title="🔧 Bot Setup",
        description="Configure the bot by using these commands:",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="1️⃣ Add Tokens",
        value="`/add_token [token_id]` - Add tokens to track\n"
              "Example: `/add_token bitcoin`",
        inline=False
    )
    
    embed.add_field(
        name="2️⃣ Set Update Interval",
        value="`/set_interval [seconds]` - Set how often prices update\n"
              "Example: `/set_interval 300` for 5 minutes",
        inline=False
    )
    
    embed.add_field(
        name="📊 Display Channel",
        value=f"Price updates will be shown in {display_channel.mention}",
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Config Channel",
        value=f"Use commands in {config_channel.mention}",
        inline=False
    )
    
    embed.add_field(
        name="Other Commands",
        value="`/list_tokens` - Show tracked tokens\n"
              "`/remove_token [symbol]` - Stop tracking a token\n"
              "`/status` - Check bot status\n"
              "`/force_update` - Force immediate update",
        inline=False
    )
    
    # Send setup guide to config channel
    try:
        await config_channel.send(embed=embed)
        await interaction.followup.send(
            f"✅ Setup complete! Check {config_channel.mention} for configuration instructions."
        )
    except Exception as e:
        logger.error(f"Error sending setup message: {e}")
        await interaction.followup.send(
            "❌ Error: Make sure the bot has permission to send messages in the configured channels."
        )

def run_bot():
    """Run the bot"""
    bot.run(TOKEN)

if __name__ == "__main__":
    run_bot() 