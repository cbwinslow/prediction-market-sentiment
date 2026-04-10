#!/usr/bin/env python3
"""
Deep dive scan - find ANY trading activity and mismatches
"""

import sys

sys.path.insert(0, "src")

from src.clients.kalshi_client import KalshiClient
from src.clients.polymarket_client import PolymarketClient
from difflib import SequenceMatcher
import re


def deep_kalshi_scan():
    """Deep scan of Kalshi markets"""
    print("=" * 80)
    print("DEEP KALSHI SCAN - LOOKING FOR ANY ACTIVITY")
    print("=" * 80)

    k_client = KalshiClient()
    markets = k_client.get_markets(limit=1000)

    print(f"\nTotal markets: {len(markets)}")

    # Check orderbooks for random markets to see if any have bids
    print("\nChecking orderbooks for activity (first 50 markets)...")
    markets_with_bids = []
    for m in markets[:50]:
        try:
            ob = k_client.get_orderbook(m.ticker)
            if "orderbook_fp" in ob:
                yes_bids = ob["orderbook_fp"].get("yes_dollars", [])
                no_bids = ob["orderbook_fp"].get("no_dollars", [])
                if yes_bids or no_bids:
                    markets_with_bids.append(
                        {
                            "ticker": m.ticker,
                            "title": m.title,
                            "yes_bids": len(yes_bids),
                            "no_bids": len(no_bids),
                            "yes_bid_price": yes_bids[0][0] if yes_bids else 0,
                            "volume": m.volume,
                        }
                    )
        except Exception as e:
            continue

    print(f"Markets with orderbook bids: {len(markets_with_bids)}")
    for mb in markets_with_bids[:10]:
        print(f"\n{mb['ticker']}: {mb['title'][:60]}")
        print(f"  Yes bids: {mb['yes_bids']} levels, best: ${mb['yes_bid_price']:.2f}")
        print(f"  Volume: {mb['volume']}")

    # Look for markets with any volume at all
    vol_markets = [m for m in markets if m.volume > 0]
    print(f"\nMarkets with volume_fp > 0: {len(vol_markets)}")

    if vol_markets:
        print("\nTop 10 by volume:")
        for m in sorted(vol_markets, key=lambda x: x.volume, reverse=True)[:10]:
            print(f"\n{m.ticker}: {m.title[:60]}")
            print(
                f"  Volume: {m.volume:.0f}, Yes bid: ${m.yes_bid_dollars:.2f}, Category: {m.category}"
            )

    # Check specific series we identified earlier
    print("\n" + "=" * 80)
    print("CHECKING SPECIFIC SERIES")
    print("=" * 80)

    series_to_check = ["KXHIGHNY", "KXA100MON", "KXSOL150", "KXINXAB"]
    for series in series_to_check:
        try:
            resp = k_client.session.get(
                f"{k_client.BASE_URL}/markets",
                params={"series_ticker": series, "limit": 5},
            )
            if resp.status_code == 200:
                data = resp.json()
                mks = data.get("markets", [])
                print(f"\n{series}: {len(mks)} markets")
                for m in mks[:3]:
                    print(f"  {m['ticker']}: {m['title'][:50]}")
                    print(
                        f"    yes_bid: ${m.get('yes_bid_dollars', 0):.2f}, vol: {m.get('volume_fp', 0)}"
                    )
        except Exception as e:
            print(f"{series}: error - {e}")


def deep_polymarket_scan():
    """Deep scan of Polymarket markets"""
    print("\n" + "=" * 80)
    print("DEEP POLYMARKET SCAN - LOOKING FOR ANY ACTIVITY")
    print("=" * 80)

    p_client = PolymarketClient()
    markets = p_client.get_markets(limit=1000)

    print(f"\nTotal markets: {len(markets)}")

    # Find accepting markets
    accepting = [m for m in markets if m.accepting_orders]
    print(f"Accepting orders: {len(accepting)}")

    # Find markets with non-0.5 prices AND accepting
    non_neutral = []
    for m in accepting:
        yes_token = next(
            (t for t in m.tokens if t.outcome.lower() in ["yes", "true"]), None
        )
        if yes_token and 0.05 < yes_token.price < 0.95:
            non_neutral.append(
                {"market": m, "price": yes_token.price, "token_id": yes_token.token_id}
            )

    print(f"Accepting markets with non-0.5 prices: {len(non_neutral)}")

    if non_neutral:
        print("\nSample non-0.5 markets:")
        for i, item in enumerate(non_neutral[:15], 1):
            m = item["market"]
            print(f"\n{i}. {m.question[:70]}")
            print(f"   Yes: {item['price']:.1%}, Token ID: {item['token_id'][:30]}...")
            print(f"   Tags: {', '.join(m.tags[:3])}")
            # Get orderbook if available
            try:
                ob = p_client.get_orderbook(item["token_id"])
                bids = ob.get("bids", [])
                asks = ob.get("asks", [])
                if bids or asks:
                    print(f"   Orderbook: {len(bids)} bids, {len(asks)} asks")
                    if bids:
                        print(f"     Best bid: {bids[0]}")
                else:
                    print(f"   Orderbook: empty")
            except Exception as e:
                print(f"   Orderbook: error ({e})")

    # Also check if there are ANY orderbooks at all
    print("\n" + "-" * 40)
    print("Testing orderbook availability on accepting markets...")
    orderbook_works = 0
    for m in accepting[:20]:
        yes_token = next(
            (t for t in m.tokens if t.outcome.lower() in ["yes", "true"]), None
        )
        if yes_token:
            try:
                ob = p_client.get_orderbook(yes_token.token_id)
                if ob.get("bids") or ob.get("asks"):
                    orderbook_works += 1
                    print(f"✓ Orderbook works for: {m.question[:50]}")
                    print(
                        f"  Bids: {len(ob.get('bids', []))}, Asks: {len(ob.get('asks', []))}"
                    )
                    if ob.get("bids"):
                        print(f"  Best: {ob['bids'][0]}")
                    break
            except:
                continue

    print(f"\nMarkets with working orderbooks: {orderbook_works}")


def cross_asset_with_current_prices():
    """Cross-asset scan with current prices and flexible matching"""
    print("\n" + "=" * 80)
    print("CROSS-ASSET SCAN - FLEXIBLE MATCHING")
    print("=" * 80)

    from src.analyzers.cross_asset import CrossAssetArbitrageDetector
    import yfinance as yf

    detector = CrossAssetArbitrageDetector()

    # Get current prices
    assets = {
        "BTC-USD": None,
        "ETH-USD": None,
        "SPY": None,
        "AAPL": None,
        "TSLA": None,
        "NVDA": None,
        "SOL-USD": None,
    }

    print("\nFetching current prices...")
    for asset in assets:
        data = detector._get_asset_data(asset)
        if data:
            assets[asset] = data

    # Get Polymarket markets with ANY price reference
    p_client = PolymarketClient()
    all_markets = p_client.get_markets(limit=1000)

    print("\nScanning Polymarket for markets mentioning:")
    asset_keywords = {
        "BTC-USD": ["btc", "bitcoin"],
        "ETH-USD": ["eth", "ethereum"],
        "SPY": ["spy", "s&p", "s and p"],
        "AAPL": ["apple"],
        "TSLA": ["tesla"],
        "NVDA": ["nvidia"],
        "SOL-USD": ["sol", "solana"],
    }

    matches_by_asset = {asset: [] for asset in assets}

    for m in all_markets:
        if not m.accepting_orders:
            continue
        yes_token = next(
            (t for t in m.tokens if t.outcome.lower() in ["yes", "true"]), None
        )
        if not yes_token or yes_token.price <= 0.05 or yes_token.price >= 0.95:
            continue

        question_lower = m.question.lower()
        for asset, keywords in asset_keywords.items():
            if any(kw in question_lower for kw in keywords):
                # Try to extract numeric range
                numbers = re.findall(
                    r"\$?(\d+(?:[.,]\d+)?)\s?(?:k|m|b|million|billion)?", question_lower
                )
                if numbers:
                    matches_by_asset[asset].append(
                        {
                            "question": m.question,
                            "price": yes_token.price,
                            "numbers": numbers,
                            "tags": m.tags,
                        }
                    )

    print("\nMatches by asset:")
    total = 0
    for asset, matches in matches_by_asset.items():
        if matches:
            print(
                f"\n{asset} (current: ${assets[asset]['current_price']:,.2f} if available): {len(matches)}"
            )
            for m in matches[:5]:
                print(f"  - {m['question'][:60]}...")
                print(f"    Price: {m['price']:.1%}, Numbers: {m['numbers']}")
            total += len(matches)

    print(f"\nTotal asset-referenced markets found: {total}")

    # Now try to find arbitrage based on simple comparison
    print("\n" + "=" * 80)
    print("ARBITRAGE ANALYSIS")
    print("=" * 80)

    opportunities = []
    for asset, matches in matches_by_asset.items():
        if asset not in assets or not matches:
            continue
        current_price = assets[asset]["current_price"]
        hist_vol = assets[asset]["historical_volatility"]

        for m in matches:
            # Extract all prices mentioned
            prices = []
            for num_str in m["numbers"]:
                try:
                    num = float(num_str.replace(",", ""))
                    # Check for k/m/b suffix
                    if "k" in num_str.lower():
                        num *= 1000
                    elif "m" in num_str.lower():
                        num *= 1000000
                    elif "b" in num_str.lower():
                        num *= 1000000000
                    prices.append(num)
                except:
                    continue

            if not prices:
                continue

            # Use highest price as strike (for above predictions)
            strike = max(prices)

            # Calculate BS probability
            T = 30 / 365.0
            bs_prob = detector._calculate_bs_probability(
                current_price, strike, T, hist_vol, direction="above"
            )

            discrepancy = abs(m["price"] - bs_prob)
            if discrepancy >= 0.2:  # 20% threshold
                opportunities.append(
                    {
                        "asset": asset,
                        "question": m["question"],
                        "current_price": current_price,
                        "strike": strike,
                        "pred_prob": m["price"],
                        "bs_prob": bs_prob,
                        "discrepancy": discrepancy,
                    }
                )

    if opportunities:
        print(f"\nFound {len(opportunities)} potential arbitrage opportunities:")
        for i, opp in enumerate(
            sorted(opportunities, key=lambda x: x["discrepancy"], reverse=True)[:10], 1
        ):
            print(f"\n{i}. {opp['question'][:70]}")
            print(f"   Asset: {opp['asset']} at ${opp['current_price']:,.2f}")
            print(f"   Strike: ${opp['strike']:,.0f}")
            print(f"   Prediction: {opp['pred_prob']:.1%}")
            print(f"   BS Calc: {opp['bs_prob']:.1%}")
            print(f"   Discrepancy: {opp['discrepancy']:.1%} <<< ARBITRAGE")
    else:
        print("\nNo cross-asset arbitrage opportunities found")


def main():
    print("DEEP OPPORTUNITY SCANNER")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    deep_kalshi_scan()
    deep_polymarket_scan()
    cross_asset_with_current_prices()

    print("\n" + "=" * 80)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 80)
    print("\nIf both platforms show zero active markets:")
    print("  → Markets may be in pre-listing phase")
    print("  → Liquidity providers may have withdrawn")
    print("  → It may be outside major trading periods (e.g., no sports)")
    print("  → API may be returning placeholder data")
    print("\nNext steps:")
    print("  1. Check the platforms' web UIs directly to verify trading activity")
    print("  2. Look for specific upcoming events with liquidity")
    print("  3. Consider that 2026-04-08 is a Monday - markets may be thin")


if __name__ == "__main__":
    from datetime import datetime

    main()
