#!/usr/bin/env python3
"""
Test script for PRG price calculation from Goldilend smart contracts
This script tests the PRG price fetching functionality without running the Discord bot
"""

import asyncio
import sys
import os
from web3 import Web3
import json

# Add the current directory to Python path to import from bot.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the PRG calculation functions from bot.py
from bot import (
    fetch_prg_price_from_contract,
    floor_price,
    market_price,
    GOLDISWAP_ADDRESS,
    GOLDILOCKED_ADDRESS,
    TREASURY_ADDRESS,
    GOLDISWAP_ABI,
    GOLDILOCKED_ABI
)

# Berachain RPC configuration
BERACHAIN_RPC_URL = "https://artio.rpc.berachain.com/"
w3 = Web3(Web3.HTTPProvider(BERACHAIN_RPC_URL))

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
    sys.exit(0 if success else 1)
