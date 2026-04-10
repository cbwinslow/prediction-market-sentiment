#!/usr/bin/env python3
"""
Practical Arbitrage Finder - Works with AMM-based prediction markets
Design: Find mispricings between similar events on Polymarket itself,
and between Polymarket and Kalshi where orderbooks exist.
"""

import sys

sys.path.insert(0, "src")

from src.clients.kalshi_client import KalshiClient
from src.clients.polymarket_client import PolymarketClient
from difflib import SequenceMatcher
import re
from datetime import datetime, timedelta


def get_recent_trades_found():
    """
    Strategy: Get markets that have had recent trades.
    We'll fetch trades for a sample of markets to identify active ones.
    """
    print("=" * 80)
    print("STRATEGY 1: Find markets with recent trade activity")
    print("=" * 80)

    p_client = PolymarketClient()
    all_markets = p_client.get_markets(limit=500)  # Sample 500

    # Filter: accepting_orders, active, and tokens with non-0.5 prices
    candidates = []
    for m in all_markets:
        if not (m.accepting_orders and m.active):
            continue
        yes_token = next(
            (t for t in m.tokens if t.outcome.lower() in ["yes", "true"]), None
        )
        if not yes_token:
            continue
        # Price must be between 5% and 95% and not exactly 0.5
        price = yes_token.price
        if 0.05 < price < 0.95 and abs(price - 0.5) > 0.02:
            candidates.append(m)

    print(f"Candidate markets (active, accepting, non-0.5): {len(candidates)}")

    # Now check which have recent trades
    active_with_trades = []
    now = datetime.now()

    print("\nChecking recent trades (last 7 days)...")
    for m in candidates[:100]:  # Check top 100
        try:
            trades = p_client.get_trades(token_id=m.tokens[0].token_id, limit=50)
            if trades:
                # Check if any trade in last 7 days
                recent = False
                for t in trades:
                    ts = t.get("timestamp")
                    if ts:
                        try:
                            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                            if (now - dt).days < 7:
                                recent = True
                                break
                        except:
                            continue
                if recent:
                    yes_token = next(
                        t for t in m.tokens if t.outcome.lower() in ["yes", "true"]
                    )
                    active_with_trades.append(
                        {
                            "question": m.question,
                            "price": yes_token.price,
                            "tags": m.tags,
                            "trades": len(trades),
                            "condition_id": m.condition_id,
                        }
                    )
        except Exception as e:
            continue

    print(f"Markets with trades in last 7 days: {len(active_with_trades)}")

    if active_with_trades:
        print("\nACTIVE MARKETS (recent trades):")
        for i, m in enumerate(active_with_trades[:15], 1):
            print(f"\n{i}. {m['question'][:70]}")
            print(f"   Price: {m['price']:.1%}, Trades seen: {m['trades']}")
            print(f"   Tags: {', '.join(m['tags'][:3])}")

    return active_with_trades


def find_similar_market_arbitrage(active_markets):
    """
    Find arbitrage between Polymarket markets that are similar but have different prices.
    This is intra-platform arbitrage.
    """
    print("\n" + "=" * 80)
    print("INTRAPLATFORM ARBITRAGE: Similar Markets on Polymarket")
    print("=" * 80)

    opportunities = []

    # Compare all pairs
    for i in range(len(active_markets)):
        for j in range(i + 1, len(active_markets)):
            m1 = active_markets[i]
            m2 = active_markets[j]

            # Simple text similarity
            q1 = m1["question"].lower()
            q2 = m2["question"].lower()

            # Extract core topic
            words1 = set(re.findall(r"\w{4,}", q1))  # 4+ letter words
            words2 = set(re.findall(r"\w{4,}", q2))

            if len(words1 & words2) >= 3:  # At least 3 common words
                # Check if they're essentially the same event
                price1 = m1["price"]
                price2 = m2["price"]
                spread = abs(price1 - price2)

                if spread >= 0.05:  # 5% difference
                    opportunities.append(
                        {
                            "market1": m1,
                            "market2": m2,
                            "spread": spread,
                            "common_words": len(words1 & words2),
                        }
                    )

    if opportunities:
        print(f"\nFound {len(opportunities)} similar-market arbitrage opportunities:")
        for i, opp in enumerate(
            sorted(opportunities, key=lambda x: x["spread"], reverse=True)[:10], 1
        ):
            print(f"\n{i}. Spread: {opp['spread']:.1%}")
            print(
                f"   Q1: {opp['market1']['question'][:60]}... ({opp['market1']['price']:.1%})"
            )
            print(
                f"   Q2: {opp['market2']['question'][:60]}... ({opp['market2']['price']:.1%})"
            )
            print(f"   Common words: {opp['common_words']}")
    else:
        print("\nNo similar-market arbitrage found")

    return opportunities


def check_kalshi_for_similar(active_polymarket):
    """
    Try to find similar markets on Kalshi
    """
    print("\n" + "=" * 80)
    print("CROSS-PLATFORM: Polymarket vs Kalshi")
    print("=" * 80)

    k_client = KalshiClient()
    k_markets = k_client.get_markets(limit=1000)

    print(f"\nKalshi markets: {len(k_markets)}")

    # Find Kalshi markets with some volume
    k_active = [m for m in k_markets if m.volume > 0]
    print(f"Kalshi markets with volume > 0: {len(k_active)}")

    if not k_active:
        print("No active Kalshi markets to compare")
        return []

    matches = []
    for p_market in active_polymarket[:50]:
        p_q = p_market["question"].lower()
        p_price = p_market["price"]

        for k_market in k_active[:200]:
            k_title = k_market.title.lower()

            # Check similarity
            p_words = set(re.findall(r"\w{4,}", p_q))
            k_words = set(re.findall(r"\w{4,}", k_title))

            if len(p_words & k_words) >= 3:
                k_bid = k_market.yes_bid_dollars
                if 0.05 < k_bid < 0.95:
                    spread = abs(p_price - k_bid)
                    if spread >= 0.1:  # 10% threshold
                        matches.append(
                            {
                                "polymarket": p_market,
                                "kalshi": k_market,
                                "spread": spread,
                                "common": len(p_words & k_words),
                            }
                        )

    if matches:
        print(f"\nFound {len(matches)} cross-platform matches:")
        for i, m in enumerate(
            sorted(matches, key=lambda x: x["spread"], reverse=True)[:10], 1
        ):
            print(f"\n{i}. Spread: {m['spread']:.1%}")
            print(
                f"   Polymarket: {m['polymarket']['question'][:60]}... ({m['polymarket']['price']:.1%})"
            )
            print(
                f"   Kalshi: {m['kalshi'].title[:60]}... (${m['kalshi'].yes_bid_dollars:.2f})"
            )
            print(f"   Common words: {m['common']}")
    else:
        print("\nNo cross-platform matches found")

    return matches


def analyze_polymarket_price_efficiency():
    """
    Check if Polymarket prices are efficient by looking at very close YES/NO spreads
    """
    print("\n" + "=" * 80)
    print("EFFICIENCY ANALYSIS: YES/NO Spreads")
    print("=" * 80)

    p_client = PolymarketClient()
    markets = p_client.get_markets(limit=500)

    accepting = [m for m in markets if m.accepting_orders and m.active]
    print(f"Accepting active markets: {len(accepting)}")

    # For binary markets (2 tokens), YES + NO should ≈ 1.0
    binary = [m for m in accepting if len(m.tokens) == 2]
    print(f"Binary markets (2 tokens): {len(binary)}")

    inefficient = []
    for m in binary:
        if len(m.tokens) != 2:
            continue
        token_prices = [t.price for t in m.tokens]
        total = sum(token_prices)
        # In efficient AMM, YES+NO = 1.0 (minus fees)
        if abs(total - 1.0) > 0.05:  # More than 5% deviation
            inefficient.append(
                {
                    "question": m.question,
                    "yes": token_prices[0]
                    if token_prices[0] > token_prices[1]
                    else token_prices[1],
                    "no": token_prices[1]
                    if token_prices[0] > token_prices[1]
                    else token_prices[0],
                    "sum": total,
                }
            )

    print(f"Inefficient markets (YES+NO deviates >5%): {len(inefficient)}")
    if inefficient:
        print("\nInefficient markets (potential arb within same market):")
        for i, m in enumerate(inefficient[:10], 1):
            print(f"\n{i}. {m['question'][:60]}")
            print(f"   Yes: {m['yes']:.1%}, No: {m['no']:.1%}, Sum: {m['sum']:.2%}")
            print(
                f"   Spot-check: sum should be ~100%, deviation = {(m['sum'] - 1):.1%}"
            )


def main():
    print("PRACTICAL OPPORTUNITY FINDER")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Strategy 1: Find active markets by trades
    active = get_recent_trades_found()

    if len(active) < 2:
        print("\nNot enough active markets for arbitrage analysis")
        print("Recommendation: Markets appear illiquid or API data is stale")
        return

    # Strategy 2: Intra-platform arbitrage on Polymarket
    intra_arb = find_similar_market_arbitrage(active)

    # Strategy 3: Cross-platform with Kalshi
    cross_arb = check_kalshi_for_similar(active)

    # Strategy 4: Check market efficiency
    analyze_polymarket_price_efficiency()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Active markets found: {len(active)}")
    print(f"Intra-platform opportunities: {len(intra_arb)}")
    print(f"Cross-platform opportunities: {len(cross_arb)}")

    if len(active) < 5:
        print("\n⚠️  WARNING: Very few active markets detected.")
        print("This could indicate:")
        print("  - Off-peak trading hours")
        print("  - API returning stale data")
        print("  - Most markets are AMM with invariant 0.5")
        print("\nRecommendations:")
        print("  1. Check https://polymarket.com directly for current activity")
        print("  2. Focus on high-volume categories (politics, crypto, sports)")
        print("  3. Use 'similar markets' arb only when events truly overlap")


if __name__ == "__main__":
    main()
