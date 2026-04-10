#!/usr/bin/env python
"""
Test authenticated Polymarket client.
Requires: POLYMARKET_PRIVATE_KEY env var

Without credentials, shows what you'd need to set up.
"""

import os

# First check if we have credentials
private_key = os.getenv("POLYMARKET_PRIVATE_KEY")

if not private_key:
    print("=" * 70)
    print("POLYMARKET AUTHENTICATED CLIENT - SETUP REQUIRED")
    print("=" * 70)
    print()
    print("To enable authenticated access (order books, trading):")
    print()
    print("1. Get your private key:")
    print("   - Open MetaMask")
    print("   - Click account menu → Account Details → Show private key")
    print("   - Copy the key (without 0x prefix)")
    print()
    print("2. Set environment variable:")
    print('   export POLYMARKET_PRIVATE_KEY="your_key_without_0x"')
    print()
    print("3. (Optional) If using email/Magic wallet:")
    print('   export POLYMARKET_FUNDER_ADDRESS="your_proxy_wallet"')
    print()
    print("=" * 70)
    print("WHAT AUTHENTICATED ACCESS ENABLES")
    print("=" * 70)
    print()
    print("  ✓ Order book depth (bids/asks with sizes)")
    print("  ✓ Your positions and orders")
    print("  ✓ Place trades programmatically")
    print("  ✓ Real-time price data from CLOB")
    print()
    print("The free Gamma API (already implemented) gives you:")
    print("  ✓ Market list with prices")
    print("  ✓ Volume data")
    print("  ✓ Best bid/ask prices")
    print()

    # Still test the basic client (read-only)
    print("Testing read-only access (no key required)...")
    print()

    from py_clob_client.client import ClobClient

    client = ClobClient("https://clob.polymarket.com")
    ok = client.get_ok()
    print(f"✓ CLOB connection: {ok}")

    # Test Gamma API (already in our client)
    from src.clients.polymarket_client import PolymarketClient

    poly = PolymarketClient()
    markets = poly.get_markets(limit=10, active_only=True)

    print(f"✓ Gamma API: {len(markets)} markets")

    if markets:
        m = markets[0]
        print(f"  Sample: {m.question[:50]}")
        print(f"  Price: {m.tokens[0].price:.2%}")
        print(f"  Volume: ${m.volume:,.0f}")

    print()
    print("Without auth, we can still get live prices and volume!")
    print("Auth is needed only for order book depth and trading.")

else:
    print("Private key detected - testing authenticated client...")
    print()

    from src.clients.polymarket_auth import create_auth_client

    client = create_auth_client()
    if client:
        print("✓ Authenticated client created")

        # Get order book for a market
        import requests

        # Get a live market
        gamma = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"limit": 1, "active": "true"},
        ).json()[0]

        token_id = gamma["clobTokenIds"][0]
        print(f"\nGetting order book for: {gamma['question'][:40]}...")

        try:
            book = client.get_order_book(token_id)
            print(f"✓ Order book retrieved")
            print(f"  Bids: {len(book.get('bids', []))}")
            print(f"  Asks: {len(book.get('asks', []))}")

            if book.get("bids"):
                print(f"  Best bid: {book['bids'][0]}")
            if book.get("asks"):
                print(f"  Best ask: {book['asks'][0]}")

        except Exception as e:
            print(f"  Error: {e}")

        # Get positions
        try:
            positions = client.get_positions()
            print(f"\nYour positions: {len(positions)}")
        except Exception as e:
            print(f"Positions error: {e}")
    else:
        print("Failed to create client")
