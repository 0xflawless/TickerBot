import os
import sys
import aiohttp
import asyncio
from dotenv import load_dotenv

async def check_bot_health():
    """Basic health check for the PRG bot"""
    try:
        # Check if token exists
        load_dotenv()
        if not os.getenv('DISCORD_TOKEN'):
            print("Discord token not found")
            return False
        
        # Test Berachain connection
        from web3 import Web3
        BERACHAIN_RPC_URL = "https://rpc.berachain.com/"
        w3 = Web3(Web3.HTTPProvider(BERACHAIN_RPC_URL))
        
        # Test basic connection
        latest_block = w3.eth.block_number
        if latest_block is None:
            print("Berachain connection failed")
            return False
        
        print(f"Berachain connection OK - Latest block: {latest_block}")
        return True
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(check_bot_health())
    sys.exit(0 if result else 1) 