#!/usr/bin/env python3
"""
Real Opportunity Finder - Uses trading activity as the signal for "active"
"""

import sys

sys.path.insert(0, "src")

from src.clients.kalshi_client import KalshiClient
from src.clients.polymarket_client import PolymarketClient
from datetime import datetime, timedelta
import re


def find_active_markets_by_trades():
    """
    Find markets that have recent trades - the truest signal of an active market
    """
    print("=" * 80)
    print("FINDING ACTIVE MARKETS BY RECENT TRADES")
    print("=" * 80)

    p_client = PolymarketClient()

    # Get all markets
    print("\nFetching all Polymarket markets...")
    all_markets = p_client.get_markets(limit=1000)
    print(f"Total: {len(all_markets)}")

    # For each market, check if there are recent trades
    # We'll sample markets that look promising first
    promising = []

    # Look for markets with non-0.5 prices AND volume-ish tags
    for m in all_markets:
        yes_token = next(
            (t for t in m.tokens if t.outcome.lower() in ["yes", "true"]), None
        )
        if not yes_token:
            continue
        price = yes_token.price
        if price <= 0.05 or price >= 0.95:
            continue  # Too extreme, likely resolved
        if abs(price - 0.5) < 0.05:
            continue  # Stuck at 50%, no conviction

        # Check tags for active topics
        tags_lower = [t.lower() for t in m.tags]
        active_tags = [
            "politics",
            "crypto",
            "elections",
            "sports",
            "golf",
            "soccer",
            "basketball",
            "finance",
            "oil",
            "bitcoin",
            "ethereum",
        ]
        has_active_tag = any(tag in active_tags for tag in tags_lower)

        # Look for dollar amounts in question (price targets)
        has_dollar = "$" in m.question

        if has_active_tag or has_dollar:
            promising.append(
                {"market": m, "price": price, "tags": m.tags, "question": m.question}
            )

    print(f"Promising markets (non-0.5, relevant tags): {len(promising)}")

    # Now check for recent trades on these promising markets
    active_markets = []
    for item in promising[:100]:  # Check top 100 promising
        m = item["market"]
        try:
            trades = p_client.get_trades(
                token_id=item["market"].tokens[0].token_id, limit=10
            )
            if trades and len(trades) > 0:
                # Check if any trade is recent (last 24 hours)
                now = datetime.now()
                recent = False
                for trade in trades:
                    ts = trade.get("timestamp")
                    if ts:
                        try:
                            trade_time = datetime.fromisoformat(
                                ts.replace("Z", "+00:00")
                            )
                            if (now - trade_time).total_seconds() < 86400:  # 24 hours
                                recent = True
                                break
                        except:
                            continue

                if recent:
                    active_markets.append(
                        {
                            "question": m.question,
                            "price": item["price"],
                            "tags": m.tags[:3],
                            "trades": len(trades),
                            "volume_est": item["price"] * 10000,
                        }
                    )
        except Exception as e:
            continue

    print(f"Markets with recent trades (last 24h): {len(active_markets)}")

    if active_markets:
        print("\nACTIVE MARKETS WITH TRADING:")
        for i, am in enumerate(active_markets[:20], 1):
            print(f"\n{i}. {am['question'][:70]}")
            print(
                f"   Price: {am['price']:.1%}, Recent trades: {am['trades']}, Tags: {', '.join(am['tags'])}"
            )

    return active_markets


def find_platform_arbitrage_with_active(active_markets):
    """
    Look for arbitrage between Kalshi and Polymarket on ACTIVE markets
    """
    print("\n" + "=" * 80)
    print("PLATFORM ARBITRAGE ON ACTIVE MARKETS")
    print("=" * 80)

    k_client = KalshiClient()

    # Get Kalshi markets with ACTUAL orderbook activity
    print("\nScanning Kalshi for markets with orderbook bids...")
    k_markets = k_client.get_markets(limit=1000)

    active_k = []
    for m in k_markets[:200]:  # Check first 200
        try:
            ob = k_client.get_orderbook(m.ticker)
            yes_bids = ob.get("orderbook_fp", {}).get("yes_dollars", [])
            if yes_bids:
                active_k.append(
                    {
                        "ticker": m.ticker,
                        "title": m.title,
                        "yes_bid": yes_bids[0][0] if yes_bids else 0,
                        "category": m.category,
                        "volume": m.volume,
                    }
                )
        except:
            continue

    print(f"Kalshi markets with orderbook bids: {len(active_k)}")

    if not active_k or not active_markets:
        print("Insufficient active markets for comparison")
        return []

    # Simple text matching
    opportunities = []
    for k in active_k:
        k_title = k["title"].lower()
        for p in active_markets:
            p_q = p["question"].lower()
            # Simple keyword overlap
            k_words = set(re.findall(r"\w+", k_title))
            p_words = set(re.findall(r"\w+", p_q))
            if len(k_words & p_words) >= 3:  # At least 3 common words
                spread = abs(k["yes_bid"] - p["price"])
                if spread >= 0.02:  # 2% spread
                    opportunities.append(
                        {
                            "kalshi": k,
                            "polymarket": p,
                            "spread": spread,
                            "common_words": len(k_words & p_words),
                        }
                    )

    if opportunities:
        print(f"\nFound {len(opportunities)} platform arbitrage opportunities:")
        for i, opp in enumerate(
            sorted(opportunities, key=lambda x: x["spread"], reverse=True)[:10], 1
        ):
            print(f"\n{i}. Spread: {opp['spread']:.1%}")
            print(
                f"   Kalshi: {opp['kalshi']['title'][:60]}... (yes_bid: ${opp['kalshi']['yes_bid']:.2f})"
            )
            print(
                f"   Polymarket: {opp['polymarket']['question'][:60]}... (price: {opp['polymarket']['price']:.1%})"
            )
    else:
        print("\nNo platform arbitrage found")

    return opportunities


def find_specific_active_markets():
    """Query specific known active markets from web UI"""
    print("\n" + "=" * 80)
    print("CHECKING SPECIFIC ACTIVE MARKETS FROM WEB UI")
    print("=" * 80)

    p_client = PolymarketClient()

    # These are known active from web: need to find their condition IDs
    # Let's search for markets with "Bitcoin" and "WTI" and "Hormuz"

    print("\nSearching for specific active markets...")
    all_markets = p_client.get_markets(limit=1000)

    targets = {
        "bitcoin": ["bitcoin", "btc"],
        "oil": ["wti", "crude", "oil"],
        "hormuz": ["hormuz", "strait"],
        "hungary": ["hungary", "orban", "magyar"],
        "masters": ["masters", "golf", "scheffler"],
    }

    found = {}
    for category, keywords in targets.items():
        found[category] = []
        for m in all_markets:
            if not m.accepting_orders:
                continue
            q_lower = m.question.lower()
            if any(kw in q_lower for kw in keywords):
                yes_token = next(
                    (t for t in m.tokens if t.outcome.lower() in ["yes", "true"]), None
                )
                if yes_token and 0.01 < yes_token.price < 0.99:
                    found[category].append(
                        {
                            "question": m.question,
                            "price": yes_token.price,
                            "tags": m.tags,
                            "condition_id": m.condition_id,
                        }
                    )

    for cat, items in found.items():
        print(f"\n{cat.upper()} markets found: {len(items)}")
        for item in items[:5]:
            print(f"  - {item['question'][:70]}")
            print(
                f"    Price: {item['price']:.1%}, Tags: {', '.join(item['tags'][:2])}"
            )

    return found


def check_orderbooks_directly():
    """Test orderbook endpoints to see which markets actually have orderbooks"""
    print("\n" + "=" * 80)
    print("TESTING ORDERBOOK DIRECTLY")
    print("=" * 80)

    import requests

    # Get markets that are accepting orders
    resp = requests.get(
        "https://clob.polymarket.com/markets?accepting_orders=true&limit=50"
    )
    if resp.status_code == 200:
        data = resp.json()
        markets = data.get("data", [])
        print(f"Accepting markets: {len(markets)}")

        # Test orderbook on first few
        for m in markets[:5]:
            print(f"\n{m['question'][:60]}")
            print(f"  enable_order_book: {m.get('enable_order_book')}")
            print(f"  active: {m.get('active')}")
            tokens = m.get("tokens", [])
            if tokens:
                token_id = tokens[0]["token_id"]
                ob_resp = requests.get(
                    "https://clob.polymarket.com/orderbook",
                    params={"token_id": token_id},
                )
                print(f"  Orderbook HTTP: {ob_resp.status_code}")
                if ob_resp.status_code == 200:
                    ob = ob_resp.json()
                    bids = ob.get("bids", [])
                    asks = ob.get("asks", [])
                    print(f"  Bids: {len(bids)}, Asks: {len(asks)}")
                    if bids:
                        print(f"    Best bid: {bids[0]['price']} ({bids[0]['size']})")
                else:
                    print(f"  Body: {ob_resp.text[:100]}")


def main():
    print("REAL OPPORTUNITY FINDER")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. Find active markets by trades
    active = find_active_markets_by_trades()

    # 2. Check specific known actives
    specific = find_specific_active_markets()

    # 3. Test orderbooks
    check_orderbooks_directly()

    # 4. Platform arbitrage
    if active:
        find_platform_arbitrage_with_active(active)

    print("\n" + "=" * 80)
    print("CONCLUSIONS")
    print("=" * 80)
    print("\nKey findings:")
    print("  - Active markets exist (see above)")
    print("  - Orderbook access varies")
    print("  - Platform arbitrage requires both platforms to have the same event")
    print("  - Cross-asset requires price-target markets (rare)")


if __name__ == "__main__":
    main()
