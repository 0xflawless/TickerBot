#!/usr/bin/env python3
"""
Test the final display format to ensure it fits within Discord's 32-character limit
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

async def test_final_display_format():
    """Test the final display format used by the bot"""
    print("🎯 Testing Final Display Format")
    print("=" * 40)
    
    # Fetch data
    prg_data = await fetch_prg_price_from_contract()
    locks_data = await fetch_locks_price_from_coingecko()
    
    if not prg_data or not locks_data:
        print("❌ Failed to fetch token data")
        return False
    
    prg_price = prg_data['price']
    locks_price = locks_data['price']
    locks_change = locks_data['change_24h']
    
    # Simulate bot's actual display logic
    print("🤖 Bot's Display Logic:")
    print("-" * 25)
    
    # PRG display (4 decimals, no space before trend)
    prg_trend = get_trend_indicator(prg_price, 0, 0)
    prg_display = f"PRG: ${prg_price:.4f}{prg_trend}"
    print(f"PRG: {prg_display} ({len(prg_display)} chars)")
    
    # LOCKS display (4 decimals, no space before trend)
    locks_trend = get_trend_indicator(locks_price, 0, locks_change)
    locks_display = f"LOCKS: ${locks_price:.4f}{locks_trend}"
    print(f"LOCKS: {locks_display} ({len(locks_display)} chars)")
    
    # Combined display
    combined = f"{prg_display} | {locks_display}"
    print(f"Combined: {combined} ({len(combined)} chars)")
    
    # Check Discord limit
    if len(combined) <= 32:
        print(f"✅ FITS within Discord's 32-character limit!")
        print(f"   Remaining space: {32 - len(combined)} characters")
    else:
        print(f"❌ EXCEEDS Discord's 32-character limit!")
        print(f"   Over by: {len(combined) - 32} characters")
        return False
    
    # Test status display
    status_display = f"Watching 24h: LOCKS {locks_change:+.1f}%"
    print(f"Status: {status_display} ({len(status_display)} chars)")
    
    # Test with different price scenarios
    print("\n📊 Testing Different Price Scenarios:")
    print("-" * 35)
    
    test_scenarios = [
        ("Low PRG price", 0.0001, locks_price),
        ("High PRG price", 0.9999, locks_price),
        ("Low LOCKS price", prg_price, 0.0001),
        ("High LOCKS price", prg_price, 99.9999),
        ("Both low", 0.0001, 0.0001),
        ("Both high", 0.9999, 99.9999),
    ]
    
    for scenario_name, test_prg, test_locks in test_scenarios:
        test_prg_display = f"PRG: ${test_prg:.4f}+"
        test_locks_display = f"LOCKS: ${test_locks:.4f}+"
        test_combined = f"{test_prg_display} | {test_locks_display}"
        
        fits = len(test_combined) <= 32
        status = "✅" if fits else "❌"
        print(f"{status} {scenario_name}: {test_combined} ({len(test_combined)} chars)")
    
    return True

async def main():
    """Run the final format test"""
    print("🚀 Testing Final Display Format (No Emojis)")
    print("=" * 50)
    
    success = await test_final_display_format()
    
    if success:
        print("\n🎉 Final format test passed!")
        print("✅ Bot is ready for deployment with proper character limits!")
    else:
        print("\n❌ Final format test failed!")
        print("⚠️  Need to adjust format further")
    
    return success

if __name__ == "__main__":
    asyncio.run(main())
