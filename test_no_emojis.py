#!/usr/bin/env python3
"""
Test script to verify the display format without emojis
"""

import asyncio
import aiohttp
from web3 import Web3

# Berachain RPC configuration
BERACHAIN_RPC_URL = "https://rpc.berachain.com/"
w3 = Web3(Web3.HTTPProvider(BERACHAIN_RPC_URL))

# Smart contract addresses
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

def floor_price(fsl: float, supply: float) -> float:
    if supply == 0:
        return 0
    return fsl / supply

def market_price(fsl: float, psl: float, supply: float) -> float:
    if supply == 0:
        return 0
    floor = floor_price(fsl, supply)
    if fsl == 0:
        return 0
    return floor + (psl / supply) * ((psl + fsl) / fsl) ** 6

def get_trend_indicator(price: float, last_price: float, change_24h: float) -> str:
    """Get trend indicator based on price movement"""
    if price > last_price:
        return "+"  # Up trend
    elif price < last_price:
        return "-"  # Down trend
    return "="  # Sideways

async def fetch_prg_price_from_contract():
    """Fetch PRG price directly from Goldilend smart contracts"""
    try:
        goldiswap_contract = w3.eth.contract(
            address=Web3.to_checksum_address(GOLDISWAP_ADDRESS),
            abi=GOLDISWAP_ABI
        )
        goldilocked_contract = w3.eth.contract(
            address=Web3.to_checksum_address(GOLDILOCKED_ADDRESS),
            abi=GOLDILOCKED_ABI
        )
        
        fsl = goldiswap_contract.functions.fsl().call()
        psl = goldiswap_contract.functions.psl().call()
        supply = goldiswap_contract.functions.totalSupply().call()
        prg_supply = goldilocked_contract.functions.totalSupply().call()
        treasury_balance = goldilocked_contract.functions.balanceOf(
            Web3.to_checksum_address(TREASURY_ADDRESS)
        ).call()
        
        fsl_float = w3.from_wei(fsl, 'ether')
        psl_float = w3.from_wei(psl, 'ether')
        supply_float = w3.from_wei(supply, 'ether')
        
        market = market_price(fsl_float, psl_float, supply_float)
        floor = floor_price(fsl_float, supply_float)
        prg_value = market - floor
        
        return {
            'price': prg_value,
            'market_price': market,
            'floor_price': floor
        }
        
    except Exception as e:
        print(f"Error fetching PRG price: {e}")
        return None

async def fetch_locks_price_from_coingecko():
    """Fetch LOCKS price from CoinGecko API"""
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": "goldilocks-dao",
                "vs_currencies": "usd",
                "include_24hr_change": "true"
            }
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'goldilocks-dao' in data and 'usd' in data['goldilocks-dao']:
                        price = float(data['goldilocks-dao']['usd'])
                        change_24h = float(data['goldilocks-dao'].get('usd_24h_change', 0))
                        return {
                            'price': price,
                            'change_24h': change_24h
                        }
                return None
    except Exception as e:
        print(f"Error fetching LOCKS price: {e}")
        return None

async def test_display_formats():
    """Test different display formats without emojis"""
    print("🎨 Testing Display Formats (No Emojis)")
    print("=" * 50)
    
    # Fetch data
    prg_data = await fetch_prg_price_from_contract()
    locks_data = await fetch_locks_price_from_coingecko()
    
    if not prg_data or not locks_data:
        print("❌ Failed to fetch token data")
        return False
    
    prg_price = prg_data['price']
    locks_price = locks_data['price']
    locks_change = locks_data['change_24h']
    
    # Test different formats
    formats = [
        # Format 1: Full precision
        f"PRG: ${prg_price:.6f} | LOCKS: ${locks_price:.4f}",
        
        # Format 2: Reduced precision
        f"PRG: ${prg_price:.4f} | LOCKS: ${locks_price:.4f}",
        
        # Format 3: With trend indicators
        f"PRG: ${prg_price:.4f}+ | LOCKS: ${locks_price:.4f}-",
        
        # Format 4: Shorter separators
        f"PRG: ${prg_price:.4f} / LOCKS: ${locks_price:.4f}",
        
        # Format 5: Minimal format
        f"PRG ${prg_price:.4f} / LOCKS ${locks_price:.4f}",
        
        # Format 6: Ultra minimal
        f"PRG${prg_price:.4f}/LOCKS${locks_price:.4f}",
    ]
    
    print("📊 Display Format Options:")
    print("-" * 30)
    
    for i, format_str in enumerate(formats, 1):
        length = len(format_str)
        status = "✅" if length <= 32 else "❌"
        print(f"{status} Format {i}: {format_str}")
        print(f"    Length: {length} chars {'(OK)' if length <= 32 else '(TOO LONG)'}")
        print()
    
    # Test the bot's actual logic
    print("🤖 Bot's Actual Display Logic:")
    print("-" * 30)
    
    # Simulate bot logic
    prg_trend = get_trend_indicator(prg_price, 0, 0)
    locks_trend = get_trend_indicator(locks_price, 0, locks_change)
    
    # PRG display (6 decimals)
    prg_display = f"PRG: ${prg_price:.6f} {prg_trend}"
    
    # LOCKS display (4 decimals)
    locks_display = f"LOCKS: ${locks_price:.4f} {locks_trend}"
    
    # Combined display
    combined = f"{prg_display} | {locks_display}"
    
    print(f"PRG Display: {prg_display} ({len(prg_display)} chars)")
    print(f"LOCKS Display: {locks_display} ({len(locks_display)} chars)")
    print(f"Combined: {combined} ({len(combined)} chars)")
    
    if len(combined) > 32:
        print(f"❌ Combined display exceeds Discord limit!")
        print(f"   Need to truncate by {len(combined) - 32} characters")
        
        # Show truncation options
        print("\n✂️  Truncation Options:")
        
        # Option 1: Reduce PRG precision
        prg_short = f"PRG: ${prg_price:.4f} {prg_trend}"
        combined_short = f"{prg_short} | {locks_display}"
        print(f"1. Reduce PRG precision: {combined_short} ({len(combined_short)} chars)")
        
        # Option 2: Reduce LOCKS precision
        locks_short = f"LOCKS: ${locks_price:.3f} {locks_trend}"
        combined_short2 = f"{prg_display} | {locks_short}"
        print(f"2. Reduce LOCKS precision: {combined_short2} ({len(combined_short2)} chars)")
        
        # Option 3: Shorter separators
        combined_short3 = f"{prg_display} / {locks_display}"
        print(f"3. Shorter separator: {combined_short3} ({len(combined_short3)} chars)")
        
        # Option 4: Remove spaces around trend
        prg_compact = f"PRG: ${prg_price:.4f}{prg_trend}"
        locks_compact = f"LOCKS: ${locks_price:.4f}{locks_trend}"
        combined_compact = f"{prg_compact} | {locks_compact}"
        print(f"4. Compact format: {combined_compact} ({len(combined_compact)} chars)")
        
    else:
        print(f"✅ Combined display fits within Discord limit!")
    
    return True

async def main():
    """Run the display format test"""
    print("🚀 Testing Display Formats Without Emojis")
    print("=" * 50)
    
    success = await test_display_formats()
    
    if success:
        print("\n🎉 Display format test completed!")
    else:
        print("\n❌ Display format test failed!")
    
    return success

if __name__ == "__main__":
    asyncio.run(main())
