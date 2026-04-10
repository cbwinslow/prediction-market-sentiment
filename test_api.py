#!/usr/bin/env python3
"""Test script to debug API responses"""

from src.clients.kalshi_client import KalshiClient
from src.clients.polymarket_client import PolymarketClient

print("=" * 60)
print("TESTING API CONNECTIONS")
print("=" * 60)

# Test Kalshi
print("\n1. Testing Kalshi API...")
k_client = KalshiClient()
try:
    # Try different status values
    for status in ["open", "closed", "settled", "unopened"]:
        try:
            markets = k_client.get_markets(status=status, limit=50)
            print(f"   Fetched {len(markets)} markets with status='{status}'")
            if markets:
                break
        except Exception as e:
            print(f"   Status '{status}' failed: {e}")

    active = [m for m in markets if m.yes_bid_dollars > 0]
    print(f"   Markets with yes_bid > 0: {len(active)}")

    if active:
        print("\n   Sample active Kalshi market:")
        m = active[0]
        print(f"   Ticker: {m.ticker}")
        print(f"   Title: {m.title[:60]}")
        print(f"   Yes Bid: ${m.yes_bid_dollars:.2f}")
        print(f"   Category: {m.category}")
        print(f"   Volume: {m.volume}")
    else:
        print("\n   No markets with yes_bid > 0. Checking orderbook for pricing...")
        if markets:
            m = markets[0]
            print(f"   Checking orderbook for ticker: {m.ticker}")
            try:
                ob = k_client.get_orderbook(m.ticker)
                print(f"   Orderbook keys: {list(ob.keys())}")
                if "orderbook_fp" in ob:
                    yes_bids = ob["orderbook_fp"].get("yes_dollars", [])
                    if yes_bids:
                        print(f"   Top yes bid from orderbook: ${yes_bids[0][0]}")
            except Exception as e:
                print(f"   Error fetching orderbook: {e}")
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback

    traceback.print_exc()

# Test Polymarket
print("\n2. Testing Polymarket API...")
p_client = PolymarketClient()
try:
    markets = p_client.get_markets(limit=50)
    print(f"   Fetched {len(markets)} markets")

    accepting = [m for m in markets if m.accepting_orders and len(m.tokens) >= 2]
    print(f"   Markets accepting orders with >=2 tokens: {len(accepting)}")

    if accepting:
        print("\n   Sample Polymarket market:")
        m = accepting[0]
        yes_token = next(
            (t for t in m.tokens if t.outcome.lower() in ["yes", "true"]), None
        )
        print(f"   Condition ID: {m.condition_id[:40]}...")
        print(f"   Question: {m.question[:60]}...")
        if yes_token:
            print(f"   Yes token price: {yes_token.price:.2%}")
        print(f"   Active: {m.active}, Accepting: {m.accepting_orders}")
        print(f"   Tags: {', '.join(m.tags[:3])}")
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 60)
print("Test complete")
print("=" * 60)
