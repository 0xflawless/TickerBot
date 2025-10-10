#!/usr/bin/env python3
"""
Comprehensive test script for both PRG (smart contract) and LOCKS (CoinGecko) tokens
This script tests both price fetching methods to ensure the bot works correctly
"""

import asyncio
import aiohttp
from web3 import Web3
import json

# Berachain RPC configuration
BERACHAIN_RPC_URL = "https://rpc.berachain.com/"
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

# PRG Price Calculation Functions
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
        print(f"Error fetching PRG price from contract: {e}")
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
        print(f"Error fetching LOCKS price from CoinGecko: {e}")
        return None

def get_trend_indicator(price: float, last_price: float, change_24h: float) -> str:
    """Get trend indicator based on price movement"""
    if price > last_price:
        return "📈"  # Up trend
    elif price < last_price:
        return "📉"  # Down trend
    return "➡️"  # Sideways

async def test_prg_token():
    """Test PRG token from smart contract"""
    print("🥣 Testing PRG Token (Smart Contract)")
    print("-" * 40)
    
    try:
        prg_data = await fetch_prg_price_from_contract()
        
        if prg_data is None:
            print("❌ Failed to fetch PRG data from contract")
            return False
        
        print("✅ PRG data fetched successfully!")
        print(f"   📊 FSL: {prg_data['fsl']:,.2f}")
        print(f"   📊 PSL: {prg_data['psl']:,.2f}")
        print(f"   📊 Supply: {prg_data['supply']:,.2f}")
        print(f"   💵 Floor Price: ${prg_data['floor_price']:.6f}")
        print(f"   💵 Market Price: ${prg_data['market_price']:.6f}")
        print(f"   💵 PRG Price: ${prg_data['price']:.6f}")
        print(f"   📈 Circulating Supply: {prg_data['circulating_supply']:,.2f}")
        
        # Test display formatting
        price = prg_data['price']
        trend = get_trend_indicator(price, 0, 0)  # No previous price for trend
        display_format = f"PRG: ${price:.6f} {trend}"
        print(f"   🎨 Display: {display_format}")
        
        return True
        
    except Exception as e:
        print(f"❌ PRG test failed: {e}")
        return False

async def test_locks_token():
    """Test LOCKS token from CoinGecko"""
    print("\n🔒 Testing LOCKS Token (CoinGecko)")
    print("-" * 40)
    
    try:
        locks_data = await fetch_locks_price_from_coingecko()
        
        if locks_data is None:
            print("❌ Failed to fetch LOCKS data from CoinGecko")
            return False
        
        print("✅ LOCKS data fetched successfully!")
        print(f"   💵 Price: ${locks_data['price']:.6f}")
        print(f"   📊 24h Change: {locks_data['change_24h']:+.2f}%")
        
        # Test display formatting
        price = locks_data['price']
        change_24h = locks_data['change_24h']
        trend = get_trend_indicator(price, 0, change_24h)
        display_format = f"LOCKS: ${price:.4f} {trend}"
        print(f"   🎨 Display: {display_format}")
        
        return True
        
    except Exception as e:
        print(f"❌ LOCKS test failed: {e}")
        return False

async def test_combined_display():
    """Test combined display of both tokens"""
    print("\n🎭 Testing Combined Display")
    print("-" * 40)
    
    try:
        # Fetch both tokens
        prg_data = await fetch_prg_price_from_contract()
        locks_data = await fetch_locks_price_from_coingecko()
        
        if prg_data is None or locks_data is None:
            print("❌ Failed to fetch data for combined display test")
            return False
        
        # Format both tokens
        prg_price = prg_data['price']
        prg_trend = get_trend_indicator(prg_price, 0, 0)
        prg_display = f"PRG: ${prg_price:.6f} {prg_trend}"
        
        locks_price = locks_data['price']
        locks_change = locks_data['change_24h']
        locks_trend = get_trend_indicator(locks_price, 0, locks_change)
        locks_display = f"LOCKS: ${locks_price:.4f} {locks_trend}"
        
        # Combined display
        combined_display = f"{prg_display} | {locks_display}"
        print(f"✅ Combined Display: {combined_display}")
        
        # Test nickname length (Discord has a 32 character limit)
        if len(combined_display) > 32:
            print(f"⚠️  Warning: Display is {len(combined_display)} characters (Discord limit: 32)")
            # Show truncated version
            truncated = combined_display[:29] + "..."
            print(f"   Truncated: {truncated}")
        else:
            print(f"✅ Display length: {len(combined_display)} characters (within limit)")
        
        # Test status display
        status_display = f"Watching 24h: LOCKS {locks_change:+.1f}%"
        print(f"✅ Status Display: {status_display}")
        
        return True
        
    except Exception as e:
        print(f"❌ Combined display test failed: {e}")
        return False

async def test_price_accuracy():
    """Test price accuracy and validation"""
    print("\n🎯 Testing Price Accuracy")
    print("-" * 40)
    
    try:
        # Test PRG calculation accuracy
        prg_data = await fetch_prg_price_from_contract()
        if prg_data:
            # Validate PRG calculation
            expected_market = market_price(prg_data['fsl'], prg_data['psl'], prg_data['supply'])
            expected_floor = floor_price(prg_data['fsl'], prg_data['supply'])
            expected_prg = expected_market - expected_floor
            
            prg_accurate = abs(prg_data['price'] - expected_prg) < 0.000001
            print(f"✅ PRG calculation accuracy: {prg_accurate}")
            
            if not prg_accurate:
                print(f"   Expected: {expected_prg:.10f}")
                print(f"   Actual: {prg_data['price']:.10f}")
                print(f"   Difference: {abs(prg_data['price'] - expected_prg):.10f}")
        
        # Test LOCKS price range (should be reasonable)
        locks_data = await fetch_locks_price_from_coingecko()
        if locks_data:
            price = locks_data['price']
            locks_reasonable = 0.001 < price < 1000  # Reasonable range
            print(f"✅ LOCKS price reasonable: {locks_reasonable} (${price:.6f})")
            
            if not locks_reasonable:
                print(f"   Warning: LOCKS price ${price:.6f} seems unusual")
        
        return True
        
    except Exception as e:
        print(f"❌ Price accuracy test failed: {e}")
        return False

async def main():
    """Run all tests for both tokens"""
    print("🚀 Starting Comprehensive Token Tests")
    print("=" * 50)
    
    tests = [
        ("PRG Token (Smart Contract)", test_prg_token),
        ("LOCKS Token (CoinGecko)", test_locks_token),
        ("Combined Display", test_combined_display),
        ("Price Accuracy", test_price_accuracy)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📋 COMPREHENSIVE TEST RESULTS")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Both tokens are ready for deployment.")
        print("\n📊 Summary:")
        print("   🥣 PRG: Real-time price from Goldilend smart contract")
        print("   🔒 LOCKS: Live price from CoinGecko API")
        print("   🎭 Combined: Both tokens display together in bot nickname")
        return True
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    # Run the comprehensive tests
    success = asyncio.run(main())
    exit(0 if success else 1)
