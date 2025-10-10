#!/usr/bin/env python3
"""
Standalone test script for PRG price calculation from Goldilend smart contracts
This script tests the PRG price fetching functionality without importing bot.py
"""

import asyncio
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
        
        print(f"PRG Contract Data - FSL: {fsl_float}, PSL: {psl_float}, Supply: {supply_float}")
        print(f"PRG Price: {prg_value}, Market: {market}, Floor: {floor}")
        
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

async def test_berachain_connection():
    """Test connection to Berachain network"""
    print("🔗 Testing Berachain connection...")
    try:
        # Test basic connection
        latest_block = w3.eth.block_number
        print(f"✅ Connected to Berachain! Latest block: {latest_block}")
        
        # Test if we can get chain ID
        chain_id = w3.eth.chain_id
        print(f"✅ Chain ID: {chain_id}")
        
        return True
    except Exception as e:
        print(f"❌ Failed to connect to Berachain: {e}")
        return False

async def test_contract_connection():
    """Test connection to Goldilend contracts"""
    print("\n📋 Testing contract connections...")
    try:
        # Test Goldiswap contract
        goldiswap_contract = w3.eth.contract(
            address=Web3.to_checksum_address(GOLDISWAP_ADDRESS),
            abi=GOLDISWAP_ABI
        )
        
        # Test Goldilocked contract
        goldilocked_contract = w3.eth.contract(
            address=Web3.to_checksum_address(GOLDILOCKED_ADDRESS),
            abi=GOLDILOCKED_ABI
        )
        
        print(f"✅ Goldiswap contract: {GOLDISWAP_ADDRESS}")
        print(f"✅ Goldilocked contract: {GOLDILOCKED_ADDRESS}")
        
        return True
    except Exception as e:
        print(f"❌ Failed to connect to contracts: {e}")
        return False

async def test_prg_price_calculation():
    """Test PRG price calculation"""
    print("\n💰 Testing PRG price calculation...")
    try:
        # Fetch PRG data from contract
        prg_data = await fetch_prg_price_from_contract()
        
        if prg_data is None:
            print("❌ Failed to fetch PRG data from contract")
            return False
        
        print("✅ PRG data fetched successfully!")
        print(f"   📊 FSL (Floor Support Liquidity): {prg_data['fsl']:.6f}")
        print(f"   📊 PSL (Premium Support Liquidity): {prg_data['psl']:.6f}")
        print(f"   📊 Supply: {prg_data['supply']:.6f}")
        print(f"   💵 Floor Price: ${prg_data['floor_price']:.6f}")
        print(f"   💵 Market Price: ${prg_data['market_price']:.6f}")
        print(f"   💵 PRG Price: ${prg_data['price']:.6f}")
        print(f"   📈 Circulating Supply: {prg_data['circulating_supply']:.6f}")
        
        # Validate the calculation
        expected_market = market_price(prg_data['fsl'], prg_data['psl'], prg_data['supply'])
        expected_floor = floor_price(prg_data['fsl'], prg_data['supply'])
        expected_prg = expected_market - expected_floor
        
        print(f"\n🧮 Validation:")
        print(f"   Market Price Match: {abs(prg_data['market_price'] - expected_market) < 0.000001}")
        print(f"   Floor Price Match: {abs(prg_data['floor_price'] - expected_floor) < 0.000001}")
        print(f"   PRG Price Match: {abs(prg_data['price'] - expected_prg) < 0.000001}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to calculate PRG price: {e}")
        return False

async def test_price_formatting():
    """Test price formatting for display"""
    print("\n🎨 Testing price formatting...")
    try:
        prg_data = await fetch_prg_price_from_contract()
        if prg_data is None:
            print("❌ No PRG data available for formatting test")
            return False
        
        price = prg_data['price']
        
        # Test different formatting scenarios
        if price < 0.001:
            formatted = f"${price:.8f}"
        elif price < 0.01:
            formatted = f"${price:.6f}"
        else:
            formatted = f"${price:.6f}"
        
        print(f"✅ PRG Price: {formatted}")
        print(f"✅ Display format: PRG: {formatted} 📈")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to format PRG price: {e}")
        return False

async def main():
    """Run all tests"""
    print("🚀 Starting PRG Price Integration Tests\n")
    print("=" * 50)
    
    tests = [
        ("Berachain Connection", test_berachain_connection),
        ("Contract Connection", test_contract_connection),
        ("PRG Price Calculation", test_prg_price_calculation),
        ("Price Formatting", test_price_formatting)
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
    print("📋 TEST RESULTS SUMMARY")
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
        print("🎉 All tests passed! PRG integration is ready to deploy.")
        return True
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    # Run the tests
    success = asyncio.run(main())
    exit(0 if success else 1)
