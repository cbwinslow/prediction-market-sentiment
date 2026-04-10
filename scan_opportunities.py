#!/usr/bin/env python3
"""
Opportunity Scanner - Designed to find real arbitrage and sentiment opportunities
"""

import sys

sys.path.insert(0, "src")

from src.clients.kalshi_client import KalshiClient
from src.clients.polymarket_client import PolymarketClient
from src.analyzers.arbitrage import ArbitrageDetector
from src.analyzers.cross_asset import CrossAssetArbitrageDetector
from datetime import datetime
import re


def scan_market_activity():
    """Scan both platforms for actually active markets"""
    print("=" * 80)
    print("MARKET ACTIVITY SCAN")
    print("=" * 80)

    k_client = KalshiClient()
    p_client = PolymarketClient()

    # Kalshi scan
    print("\n[KALSHI]")
    print("-" * 40)
    k_markets = k_client.get_markets(limit=1000)
    print(f"Total markets fetched: {len(k_markets)}")

    # Find markets with actual trading (volume > 0 or bids > 0)
    active_k = []
    for m in k_markets:
        # Check if this market has real pricing
        try:
            yes_bid = float(m.yes_bid_dollars)
            volume = float(m.volume)
            if yes_bid > 0 and yes_bid < 1 and volume > 0:
                active_k.append(m)
        except:
            continue

    print(f"Active markets (yes_bid > 0, volume > 0): {len(active_k)}")

    if active_k:
        # Group by category
        categories = {}
        for m in active_k:
            cat = m.category if m.category else "uncategorized"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(m)

        print("\nActive markets by category:")
        for cat, markets in sorted(
            categories.items(), key=lambda x: len(x[1]), reverse=True
        )[:10]:
            print(f"  {cat}: {len(markets)}")
            # Show most liquid in this category
            if markets:
                most_liquid = max(markets, key=lambda x: x.volume)
                print(
                    f"    Top: {most_liquid.ticker} - {most_liquid.title[:50]}... (vol: {most_liquid.volume:.0f}, bid: ${most_liquid.yes_bid_dollars:.2f})"
                )

    # Show top 5 most liquid Kalshi markets
    if active_k:
        top5 = sorted(active_k, key=lambda x: x.volume, reverse=True)[:5]
        print("\nTop 5 most liquid Kalshi markets:")
        for i, m in enumerate(top5, 1):
            print(f"{i}. {m.ticker}")
            print(f"   {m.title[:70]}")
            print(
                f"   Yes: ${m.yes_bid_dollars:.2f}, Vol: {m.volume:.0f}, Category: {m.category}"
            )

    # Polymarket scan
    print("\n" + "=" * 80)
    print("[POLYMARKET]")
    print("-" * 40)
    p_markets = p_client.get_markets(limit=1000)
    print(f"Total markets fetched: {len(p_markets)}")

    # Find active accepting markets with real pricing
    active_p = []
    for m in p_markets:
        if not m.accepting_orders:
            continue
        yes_token = next(
            (t for t in m.tokens if t.outcome.lower() in ["yes", "true"]), None
        )
        if not yes_token:
            continue
        # Only include if price is not exactly 0.5 (which often means no activity)
        price = yes_token.price
        if 0 < price < 1 and abs(price - 0.5) > 0.01:
            active_p.append(m)

    print(f"Active accepting markets (non-0.5 prices): {len(active_p)}")

    if active_p:
        # Group by tags
        tag_counts = {}
        for m in active_p:
            for tag in m.tags[:3]:  # Use first 3 tags
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        print("\nActive markets by tag (top 10):")
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        for tag, count in sorted_tags:
            print(f"  {tag}: {count}")

        # Show top 5 most active (by proxy: token price * 10000 as volume estimate)
        if active_p:

            def volume_estimate(m):
                yes_token = next(
                    t for t in m.tokens if t.outcome.lower() in ["yes", "true"]
                )
                return yes_token.price * 10000

            top5 = sorted(active_p, key=volume_estimate, reverse=True)[:5]
            print("\nTop 5 active Polymarket markets (by volume estimate):")
            for i, m in enumerate(top5, 1):
                yes_token = next(
                    t for t in m.tokens if t.outcome.lower() in ["yes", "true"]
                )
                print(f"{i}. {m.condition_id[:20]}...")
                print(f"   {m.question[:70]}")
                print(f"   Yes: {yes_token.price:.1%}, Tags: {', '.join(m.tags[:3])}")

    return active_k, active_p


def scan_platform_arbitrage(active_k, active_p):
    """Look for arbitrage between Kalshi and Polymarket on similar events"""
    print("\n" + "=" * 80)
    print("PLATFORM ARBITRAGE SCAN")
    print("=" * 80)

    detector = ArbitrageDetector(similarity_threshold=0.6)

    # Use only active markets
    k_filtered = [m for m in active_k if m.yes_bid_dollars > 0]
    p_filtered = []
    for m in active_p:
        yes_token = next(
            (t for t in m.tokens if t.outcome.lower() in ["yes", "true"]), None
        )
        if yes_token and yes_token.price > 0:
            p_filtered.append(m)

    print(
        f"\nScanning {len(k_filtered)} active Kalshi vs {len(p_filtered)} active Polymarket markets..."
    )

    matches = detector.match_markets(k_filtered, p_filtered)
    print(f"Found {len(matches)} similar market pairs")

    if matches:
        # Calculate spreads
        opportunities = []
        for match in matches:
            km = match.kalshi_market
            pm = match.polymarket_market
            pm_yes_token = next(
                t for t in pm.tokens if t.outcome.lower() in ["yes", "true"]
            )

            spread = abs(km.implied_probability - pm_yes_token.price)
            if spread >= 0.02:  # 2% minimum
                opportunities.append(
                    {
                        "kalshi_ticker": km.ticker,
                        "kalshi_title": km.title,
                        "kalshi_prob": km.implied_probability,
                        "polymarket_q": pm.question,
                        "polymarket_prob": pm_yes_token.price,
                        "spread": spread,
                        "similarity": match.similarity_score,
                        "kalshi_vol": km.volume,
                    }
                )

        if opportunities:
            print(
                f"\nFound {len(opportunities)} arbitrage opportunities (spread > 2%):"
            )
            for i, opp in enumerate(
                sorted(opportunities, key=lambda x: x["spread"], reverse=True)[:10], 1
            ):
                print(
                    f"\n{i}. Spread: {opp['spread']:.1%} (similarity: {opp['similarity']:.1%})"
                )
                print(f"   Kalshi: {opp['kalshi_title'][:60]}...")
                print(
                    f"     Probability: {opp['kalshi_prob']:.1%} (vol: {opp['kalshi_vol']:.0f})"
                )
                print(f"   Polymarket: {opp['polymarket_q'][:60]}...")
                print(f"     Probability: {opp['polymarket_prob']:.1%}")
        else:
            print("\nNo opportunities with spread > 2% found")
    else:
        print("No similar market pairs found")


def scan_cross_asset_opportunities():
    """Look for cross-asset opportunities with current data"""
    print("\n" + "=" * 80)
    print("CROSS-ASSET ARBITRAGE SCAN")
    print("=" * 80)

    detector = CrossAssetArbitrageDetector()

    # Test specific known queries
    test_queries = [
        # BTC related
        ("Will BTC exceed $100,000 before 2026?", "BTC-USD", 100000, "above"),
        ("Will Bitcoin be above $75k by end of 2025?", "BTC-USD", 75000, "above"),
        ("Will Ethereum top $5,000 this year?", "ETH-USD", 5000, "above"),
        ("Will ETH drop below $2,000?", "ETH-USD", 2000, "below"),
        # SPY
        ("Will SPY close above 5500 this month?", "SPY", 5500, "above"),
        ("Will SPY fall below 4000?", "SPY", 4000, "below"),
        # Stocks
        ("Will AAPL hit $250?", "AAPL", 250, "above"),
        ("Will Tesla drop below $200?", "TSLA", 200, "below"),
        ("Will NVDA exceed $1,000?", "NVDA", 1000, "above"),
    ]

    print("\nAsset price snapshot:")
    asset_data = {}
    for asset in ["BTC-USD", "ETH-USD", "SPY", "AAPL", "TSLA", "NVDA"]:
        data = detector._get_asset_data(asset)
        if data:
            asset_data[asset] = data
            print(f"\n{asset}:")
            print(f"  Price: ${data['current_price']:,.2f}")
            print(f"  Hist Vol: {data['historical_volatility']:.1%}")
            if data["implied_volatility"]:
                print(f"  IV: {data['implied_volatility']:.1%}")
        else:
            print(f"\n{asset}: Failed to fetch")

    print("\n" + "-" * 40)
    print("Testing known prediction market queries:")

    for query, asset, strike, direction in test_queries:
        if asset not in asset_data:
            continue
        data = asset_data[asset]
        T = 30 / 365.0  # Assume 30 days
        vol = data["implied_volatility"] or data["historical_volatility"]
        bs_prob = detector._calculate_bs_probability(
            data["current_price"], strike, T, vol, direction=direction
        )
        print(f"\n{query}")
        print(f"  Asset: {asset} at ${data['current_price']:,.2f}")
        print(f"  Strike: ${strike:,.0f} {direction}")
        print(f"  Black-Scholes probability (30d): {bs_prob:.1%}")

        # Check if this exact market exists on Polymarket or Kalshi
        # Would need to fetch markets and check - simplified for now
        if data["current_price"] > strike and direction == "above":
            moneyness = "ITM"
        elif data["current_price"] < strike and direction == "below":
            moneyness = "ITM"
        else:
            moneyness = "OTM"
        print(f"  Status: {moneyness}")

    # Now actually scan prediction markets for matching queries
    print("\n" + "-" * 40)
    print("Scanning for matching prediction markets...")

    p_markets = p_client.get_markets(limit=500)
    matches = []
    for m in p_markets:
        if not m.accepting_orders:
            continue
        yes_token = next(
            (t for t in m.tokens if t.outcome.lower() in ["yes", "true"]), None
        )
        if not yes_token or yes_token.price <= 0 or abs(yes_token.price - 0.5) < 0.05:
            continue  # Skip neutral/no activity

        info = detector._extract_asset_info(m.question)
        if info and info["asset"] in asset_data:
            data = asset_data[info["asset"]]
            T = 30 / 365.0
            vol = data["historical_volatility"]
            bs_prob = detector._calculate_bs_probability(
                data["current_price"],
                info["strike"],
                T,
                vol,
                direction=info["direction"],
            )
            discrepancy = abs(yes_token.price - bs_prob)
            if discrepancy >= 0.15:
                matches.append(
                    {
                        "question": m.question,
                        "asset": info["asset"],
                        "strike": info["strike"],
                        "direction": info["direction"],
                        "pred_prob": yes_token.price,
                        "bs_prob": bs_prob,
                        "discrepancy": discrepancy,
                        "asset_price": data["current_price"],
                    }
                )

    if matches:
        print(f"\nFound {len(matches)} cross-asset opportunities (discrepancy > 15%):")
        for i, match in enumerate(
            sorted(matches, key=lambda x: x["discrepancy"], reverse=True)[:10], 1
        ):
            print(f"\n{i}. {match['question'][:70]}...")
            print(f"   Asset: {match['asset']} at ${match['asset_price']:,.2f}")
            print(f"   Strike: ${match['strike']:,.0f} {match['direction']}")
            print(f"   Prediction: {match['pred_prob']:.1%}")
            print(f"   BS Calc: {match['bs_prob']:.1%}")
            print(f"   Discrepancy: {match['discrepancy']:.1%}")
    else:
        print("\nNo significant cross-asset opportunities found.")


def scan_for_specific_patterns():
    """Scan for specific high-probability patterns"""
    print("\n" + "=" * 80)
    print("PATTERN-BASED SCANNING")
    print("=" * 80)

    p_client = PolymarketClient()
    markets = p_client.get_markets(limit=1000)

    patterns = {
        r"Will.*above\s+\$(\d+(?:k|K|m|M|b|B)?)": "price_above",
        r"Will.*below\s+\$(\d+(?:k|K|m|M|b|B)?)": "price_below",
        r"Will.*exceed\s+\$(\d+(?:k|K|m|M|b|B)?)": "price_above",
        r"Will.*hit\s+\$(\d+(?:k|K|m|M|b|B)?)": "price_above",
        r"Will.*drop\s+below\s+\$(\d+(?:k|K|m|M|b|B)?)": "price_below",
        r"Will.*crash\s+below\s+\$(\d+(?:k|K|m|M|b|B)?)": "price_below",
    }

    print("\nSearching for price-target patterns in Polymarket questions...")

    found = []
    for m in markets:
        if not m.accepting_orders:
            continue
        yes_token = next(
            (t for t in m.tokens if t.outcome.lower() in ["yes", "true"]), None
        )
        if not yes_token or yes_token.price <= 0.05 or yes_token.price >= 0.95:
            continue  # Skip extreme low/high

        question = m.question
        for pattern, ptype in patterns.items():
            match = re.search(pattern, question, re.I)
            if match:
                price_str = match.group(1).lower()
                # Parse multiplier
                if "k" in price_str:
                    strike = float(price_str.replace("k", "")) * 1000
                elif "m" in price_str:
                    strike = float(price_str.replace("m", "")) * 1000000
                elif "b" in price_str:
                    strike = float(price_str.replace("b", "")) * 1000000000
                else:
                    strike = float(price_str.replace(",", ""))

                found.append(
                    {
                        "question": question,
                        "type": ptype,
                        "strike": strike,
                        "probability": yes_token.price,
                        "tags": m.tags[:3],
                        "condition_id": m.condition_id,
                    }
                )
                break  # Only first match

    print(f"Found {len(found)} markets with explicit price targets")

    if found:
        # Group by asset (try to infer)
        print("\nSample findings:")
        for i, f in enumerate(found[:15], 1):
            print(f"\n{i}. {f['question'][:70]}")
            print(f"   Type: {f['type']}, Strike: ${f['strike']:,.0f}")
            print(f"   Probability: {f['probability']:.1%}")
            print(f"   Tags: {', '.join(f['tags'])}")

    return found


def main():
    print("=" * 80)
    print("OPPORTUNITY SCANNER - DESIGNED TO FIND REAL TRADING OPPORTUNITIES")
    print("=" * 80)
    print(f"\nScan started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Scan 1: Market activity
    active_k, active_p = scan_market_activity()

    # Scan 2: Platform arbitrage
    if active_k and active_p:
        scan_platform_arbitrage(active_k, active_p)
    else:
        print("\n[Skipping platform arbitrage - not enough active markets]")

    # Scan 3: Cross-asset
    try:
        scan_cross_asset_opportunities()
    except Exception as e:
        print(f"\nCross-asset scan error: {e}")

    # Scan 4: Pattern-based
    try:
        found_patterns = scan_for_specific_patterns()
    except Exception as e:
        print(f"\nPattern scan error: {e}")

    print("\n" + "=" * 80)
    print("SCAN COMPLETE")
    print("=" * 80)
    print("\nSummary:")
    print(f"  Kalshi active markets: {len(active_k)}")
    print(f"  Polymarket active markets: {len(active_p)}")
    print("\nRecommendations:")
    print("  1. If active markets exist, focus on platform arbitrage")
    print("  2. Monitor pattern-based scans for new price-target markets")
    print("  3. Check cross-asset when asset prices move significantly")
    print("  4. Liquidity matters - filter by volume > threshold")


if __name__ == "__main__":
    main()
