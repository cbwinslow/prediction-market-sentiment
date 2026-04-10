#!/usr/bin/env python3
"""Debug Kalshi orderbook structure"""

from src.clients.kalshi_client import KalshiClient
import json

k_client = KalshiClient()
markets = k_client.get_markets(status="open", limit=20)

print("Checking orderbooks for open markets...")
count = 0
for m in markets:
    if count >= 3:
        break
    print(f"\nTicker: {m.ticker}")
    print(f"Title: {m.title[:60]}")
    print(f"yes_bid_dollars: {m.yes_bid_dollars}, no_bid_dollars: {m.no_bid_dollars}")
    print(f"volume: {m.volume}")
    try:
        ob = k_client.get_orderbook(m.ticker)
        print("Orderbook structure:")
        print(json.dumps(ob, indent=2)[:1000])
        count += 1
    except Exception as e:
        print(f"Error: {e}")
