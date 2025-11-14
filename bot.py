import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from dotenv import load_dotenv
import time
import asyncio
import json
import sys
from datetime import datetime, timedelta
from web3 import Web3

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

# LOCKS Price Calculation Functions (from Goldilend smart contracts)
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


class GuildConfig:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.is_tracking = False
        self.update_interval = 300  # Default 5 minutes in seconds
        self.config_channel_id = None  # Channel for admin commands
        self.display_channel_id = None  # Channel for price display
        self.last_price = 0


async def fetch_locks_price_from_contract():
    """Fetch LOCKS price directly from Goldilend smart contracts"""
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
        locks_supply = goldilocked_contract.functions.totalSupply().call()
        treasury_balance = goldilocked_contract.functions.balanceOf(
            Web3.to_checksum_address(TREASURY_ADDRESS)
        ).call()
        
        # Convert from wei to ether
        fsl_float = w3.from_wei(fsl, 'ether')
        psl_float = w3.from_wei(psl, 'ether')
        supply_float = w3.from_wei(supply, 'ether')
        
        # Calculate LOCKS price using bonding curve
        market = market_price(fsl_float, psl_float, supply_float)
        floor = floor_price(fsl_float, supply_float)
        locks_value = market  # Use market price directly for LOCKS
        
        # Calculate circulating supply (total - treasury)
        circulating_supply = w3.from_wei(locks_supply - treasury_balance, 'ether')
        
        logger.info(f"LOCKS Contract Data - FSL: {fsl_float}, PSL: {psl_float}, Supply: {supply_float}")
        logger.info(f"LOCKS Price: {locks_value}, Market: {market}, Floor: {floor}")
        
        return {
            'price': locks_value,
            'market_price': market,
            'floor_price': floor,
            'circulating_supply': circulating_supply,
            'fsl': fsl_float,
            'psl': psl_float,
            'supply': supply_float
        }
        
    except Exception as e:
        logger.error(f"Error fetching LOCKS price from contract: {e}")
        return None

def get_trend_indicator(price: float, last_price: float) -> str:
    """Get trend indicator based on price movement"""
    if price > last_price:
        return "📈"  # Up trend
    elif price < last_price:
        return "📉"  # Down trend
    return "➡️"  # Sideways

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
    """Update bot nicknames and status for LOCKS price tracking"""
    try:
        current_time = int(time.time())
        logger.info("Running LOCKS price update check...")
        
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
                
                # Fetch LOCKS price from smart contract
                locks_data = await fetch_locks_price_from_contract()
                if locks_data is None:
                    logger.warning(f"Failed to fetch LOCKS price for guild {guild_id}")
                    continue
                
                current_price = locks_data['price']
                
                # Format price display for LOCKS (no trend indicator)
                price_str = f"LOCKS: ${current_price:.5f}"
                
                # Update bot nickname with LOCKS price
                try:
                    logger.debug(f"Setting nickname in {guild.name} to: {price_str}")
                    await guild.me.edit(nick=price_str)
                    
                    # Update status (LOCKS doesn't have 24h change from contract)
                    status = "LOCKS from Goldilocks"
                    logger.debug(f"Setting status in {guild.name} to: {status}")
                    await bot.change_presence(
                        activity=discord.Activity(
                            type=discord.ActivityType.watching,
                            name=status
                        )
                    )
                except Exception as e:
                    logger.error(f"Error updating display in {guild.name}: {e}")
                
                # Update last price
                config.last_price = current_price

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
        
        # Log currently tracked guilds
        for guild_id, config in tracked_guilds.items():
            guild = bot.get_guild(guild_id)
            guild_name = guild.name if guild else "Unknown Guild"
            logger.info(f"Tracking LOCKS in {guild_name} ({guild_id})")
    except Exception as e:
        logger.error(f"Error in on_ready: {e}")

@bot.tree.command(name="start_locks", description="Start tracking LOCKS price from Goldilend smart contracts")
@app_commands.default_permissions(administrator=True)
async def start_locks(interaction: discord.Interaction):
    """Start tracking LOCKS price"""
    await interaction.response.defer()
    
    guild_id = interaction.guild_id
    if guild_id not in tracked_guilds:
        tracked_guilds[guild_id] = GuildConfig(guild_id)
    
    config = tracked_guilds[guild_id]
    
    # Check if LOCKS is already being tracked
    if config.is_tracking:
        await interaction.followup.send(
            "⚠️ **LOCKS is already being tracked in this server!**\n\n"
            "This bot only tracks LOCKS price from Goldilend smart contracts."
        )
        return

    # Start LOCKS tracking
    config.is_tracking = True
    save_tracked_guilds()
    
    # Test LOCKS price fetch from contract
    locks_data = await fetch_locks_price_from_contract()
    if locks_data:
        price = locks_data['price']
        interval_str = get_human_readable_time(config.update_interval)
        await interaction.followup.send(
            f"✅ Successfully started LOCKS tracking from Goldilend smart contract!\n"
            f"Current LOCKS price: ${price:.6f}\n"
            f"Market price: ${locks_data['market_price']:.6f}\n"
            f"Floor price: ${locks_data['floor_price']:.6f}\n"
            f"The bot will update prices every {interval_str}."
        )
    else:
        await interaction.followup.send(
            f"⚠️ LOCKS tracking started, but there was an error fetching the initial price from contract.\n"
            "The bot will retry in the next update cycle."
        )

@bot.tree.command(name="stop_locks", description="Stop tracking LOCKS price")
@app_commands.default_permissions(administrator=True)
async def stop_locks(interaction: discord.Interaction):
    """Stop tracking LOCKS price"""
    guild_id = interaction.guild_id
    if guild_id not in tracked_guilds:
        await interaction.response.send_message("LOCKS is not being tracked in this server.")
        return
    
    config = tracked_guilds[guild_id]
    
    if not config.is_tracking:
        await interaction.response.send_message("❌ LOCKS is not being tracked in this server.")
        return
    
    config.is_tracking = False
    save_tracked_guilds()
    await interaction.response.send_message("✅ Stopped LOCKS price tracking.")

@bot.tree.command(name="locks_status", description="Show LOCKS price and tracking status")
async def locks_status(interaction: discord.Interaction):
    """Show LOCKS price and tracking status"""
    guild_id = interaction.guild_id
    
    if guild_id not in tracked_guilds:
        await interaction.response.send_message("LOCKS is not being tracked in this server. Use `/start_locks` to begin tracking.")
        return
    
    config = tracked_guilds[guild_id]
    
    if not config.is_tracking:
        await interaction.response.send_message("LOCKS is not being tracked in this server. Use `/start_locks` to begin tracking.")
        return
    
    embed = discord.Embed(title="LOCKS Price Status", color=discord.Color.blue())
    
    # Fetch current LOCKS data
    locks_data = await fetch_locks_price_from_contract()
    if locks_data:
        price = locks_data['price']
        embed.add_field(
            name="LOCKS Price",
            value=f"**Current Price:** ${price:.6f}\n"
                  f"**Market Price:** ${locks_data['market_price']:.6f}\n"
                  f"**Floor Price:** ${locks_data['floor_price']:.6f}\n"
                  f"**Circulating Supply:** {locks_data['circulating_supply']:.2f}\n"
                  f"**Source:** Goldilend Smart Contract",
            inline=False
        )
        
        # Add contract data
        embed.add_field(
            name="Contract Data",
            value=f"**FSL:** {locks_data['fsl']:.6f}\n"
                  f"**PSL:** {locks_data['psl']:.6f}\n"
                  f"**Supply:** {locks_data['supply']:.6f}",
            inline=True
        )
        
        # Add tracking info
        interval_str = get_human_readable_time(config.update_interval)
        embed.add_field(
            name="Tracking Info",
            value=f"**Status:** ✅ Active\n"
                  f"**Update Interval:** {interval_str}\n"
                  f"**Last Price:** ${config.last_price:.6f}",
            inline=True
        )
    else:
        embed.add_field(
            name="LOCKS Price",
            value="❌ Unable to fetch price from contract\n**Source:** Goldilend Smart Contract",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

def save_tracked_guilds():
    """Save tracked guilds to file"""
    try:
        data = {}
        for guild_id, config in tracked_guilds.items():
            data[str(guild_id)] = {
                "is_tracking": config.is_tracking,
                "update_interval": config.update_interval,
                "config_channel_id": config.config_channel_id,
                "display_channel_id": config.display_channel_id,
                "last_price": config.last_price
            }
        
        temp_file = f"{SAVE_FILE}.tmp"
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=4)
        os.replace(temp_file, SAVE_FILE)
    except Exception as e:
        logger.error(f"Error saving tracked guilds: {e}")

def load_tracked_guilds():
    """Load tracked guilds from file"""
    try:
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, 'r') as f:
                data = json.load(f)
            
            for guild_id_str, guild_data in data.items():
                guild_id = int(guild_id_str)
                config = GuildConfig(guild_id)
                config.is_tracking = guild_data.get("is_tracking", False)
                config.update_interval = guild_data.get("update_interval", 300)
                config.config_channel_id = guild_data.get("config_channel_id")
                config.display_channel_id = guild_data.get("display_channel_id")
                config.last_price = guild_data.get("last_price", 0)
                
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

@bot.tree.command(name="status", description="Check bot status and LOCKS contract health")
async def check_status(interaction: discord.Interaction):
    """Check bot status and LOCKS contract health"""
    await interaction.response.defer()
    
    embed = discord.Embed(title="LOCKS Bot Status", color=discord.Color.blue())
    
    # Check Berachain/LOCKS contract health
    try:
        locks_data = await fetch_locks_price_from_contract()
        contract_status = "✅ Operational" if locks_data else "⚠️ Having issues"
        if locks_data:
            contract_status += f"\nLOCKS Price: ${locks_data['price']:.6f}"
    except Exception:
        contract_status = "❌ Not responding"
    
    embed.add_field(
        name="Berachain/LOCKS Contract",
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
        
        # Show LOCKS tracking status
        locks_status = "✅ Active" if config.is_tracking else "❌ Inactive"
    else:
        interval_str = "5 minutes (default)"
        locks_status = "❌ Not configured"
    
    embed.add_field(
        name="Server Settings",
        value=f"Update Interval: {interval_str}\n"
              f"LOCKS Tracking: {locks_status}",
        inline=False
    )
    
    # Add global statistics
    total_guilds = len(tracked_guilds)
    active_guilds = sum(1 for config in tracked_guilds.values() if config.is_tracking)
    
    embed.add_field(
        name="Global Statistics",
        value=f"Total Servers: {total_guilds}\n"
              f"Active LOCKS Tracking: {active_guilds}",
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
        await interaction.followup.send("LOCKS is not being tracked in this server.")
        return
    
    config = tracked_guilds[guild_id]
    if not config.is_tracking:
        await interaction.followup.send("LOCKS is not being tracked in this server.")
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
        name="1️⃣ Start LOCKS Tracking",
        value="`/start_locks` - Start tracking LOCKS price from Goldilend smart contracts",
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
        value="`/locks_status` - Show LOCKS price and tracking status\n"
              "`/stop_locks` - Stop tracking LOCKS price\n"
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