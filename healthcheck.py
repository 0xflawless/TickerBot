import os
import sys
import aiohttp
import asyncio
from dotenv import load_dotenv

async def check_bot_health():
    """Basic health check for the bot"""
    try:
        # Check if token exists
        load_dotenv()
        if not os.getenv('DISCORD_TOKEN'):
            print("Discord token not found")
            return False
        
        # Test CoinGecko API
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/ping"
            async with session.get(url) as response:
                if response.status != 200:
                    print("CoinGecko API not responding")
                    return False
        
        return True
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(check_bot_health())
    sys.exit(0 if result else 1) 