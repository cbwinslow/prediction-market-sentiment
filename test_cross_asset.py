#!/usr/bin/env python3
"""Test cross-asset arbitrage detection"""

import sys

sys.path.insert(0, "src")

from src.analyzers.cross_asset import CrossAssetArbitrageDetector

detector = CrossAssetArbitrageDetector()

print("=" * 70)
print("CROSS-ASSET ARBITRAGE DETECTOR")
print("=" * 70)

# First, let's look for markets with asset references
print("\nScanning for markets with price targets...")

# Check Polymarket for crypto/stock mentions
from src.clients.polymarket_client import PolymarketClient

p_client = PolymarketClient()

print("\nFetching Polymarket markets...")
pm_markets = p_client.get_markets(limit=500)
print(f"Total: {len(pm_markets)}")

# Find markets that mention prices or assets
price_markets = []
for m in pm_markets:
    question = m.question.lower()
    if any(
        term in question
        for term in [
            "btc",
            "bitcoin",
            "eth",
            "ethereum",
            "spy",
            "stock",
            "price",
            "above $",
            "below $",
        ]
    ):
        price_markets.append(m)

print(f"Markets with price references: {len(price_markets)}")

if price_markets:
    print("\nSample price-related markets:")
    for i, m in enumerate(price_markets[:5], 1):
        yes_token = next(
            (t for t in m.tokens if t.outcome.lower() in ["yes", "true"]), None
        )
        price = yes_token.price if yes_token else 0
        print(f"\n{i}. {m.question[:80]}...")
        print(f"   Yes probability: {price:.1%}")
        print(f"   Tags: {', '.join(m.tags[:3])}")

# Now try to extract asset info from these questions
print("\n" + "=" * 70)
print("ASSET EXTRACTION TEST")
print("=" * 70)

test_questions = [
    "Will BTC be above $100,000 by December 31, 2025?",
    "Will Ethereum exceed $5,000 before June 2025?",
    "Will SPY close above 500 this month?",
    "Will Apple stock reach $250 by end of Q2?",
    "Will Tesla stock drop below $150?",
    "Will Bitcoin price be over $150k in 2025?",
    "Will the Fed raise rates above 5%?",
    "Will gold price exceed $3000?",
]

for q in test_questions:
    info = detector._extract_asset_info(q)
    print(f"\nQuestion: {q}")
    if info:
        print(
            f"  → Asset: {info['asset']}, Strike: ${info['strike']:,.0f}, Direction: {info['direction']}"
        )
    else:
        print("  → No asset detected")

# Test fetching asset data
print("\n" + "=" * 70)
print("ASSET DATA FETCH TEST")
print("=" * 70)

for asset in ["BTC-USD", "SPY", "AAPL"]:
    data = detector._get_asset_data(asset)
    if data:
        print(f"\n{asset}:")
        print(f"  Price: ${data['current_price']:,.2f}")
        print(f"  Hist Vol: {data['historical_volatility']:.1%}")
        if data["implied_volatility"]:
            print(f"  IV: {data['implied_volatility']:.1%}")
    else:
        print(f"\n{asset}: Failed to fetch")

# Test Black-Scholes probability
print("\n" + "=" * 70)
print("BLACK-SCHOLES PROBABILITY TEST")
print("=" * 70)

# Example: BTC at $95k, strike $100k, 30% annual vol, 6 months
test_cases = [
    (95000, 100000, 0.30, 0.5, "above", "ITM call scenario"),
    (100000, 95000, 0.30, 0.5, "above", "OTM call scenario"),
    (150, 200, 0.40, 0.25, "below", "Put scenario"),
]

for spot, strike, vol, T, direction, desc in test_cases:
    prob = detector._calculate_bs_probability(spot, strike, T, vol, direction=direction)
    moneyness = (
        "ITM"
        if (direction == "above" and spot > strike)
        or (direction == "below" and spot < strike)
        else "OTM"
    )
    print(f"\n{desc}:")
    print(
        f"  Spot=${spot:,}, Strike=${strike:,}, T={T:.1f}y, Vol={vol:.1%}, {moneyness}"
    )
    print(f"  Risk-neutral prob of {direction}: {prob:.1%}")

# Try to find actual cross-asset opportunities
print("\n" + "=" * 70)
print("SCANNING FOR CROSS-ASSET ARBITRAGE")
print("=" * 70)

print("\nRunning detector (this may take a moment due to yfinance calls)...")
opportunities = detector.find_cross_asset_arbitrage(
    min_discrepancy=0.10,  # 10% difference
    min_volume=100,
    platforms=["polymarket"],  # Start with polymarket (more active)
)

print(f"\nFound {len(opportunities)} opportunities")

if opportunities:
    print("\nTop opportunities:")
    for i, opp in enumerate(opportunities[:5], 1):
        print(f"\n{i}. {opp.event_a[:70]}...")
        print(f"   Prediction market: {opp.price_a:.1%}")
        print(f"   BS-calculated: {opp.price_b:.1%}")
        print(f"   Discrepancy: {opp.spread:.1%}")
        print(f"   Confidence: {opp.confidence:.1%}")
else:
    print("\nNo significant discrepancies found.")
    print("Reasons:")
    print(" - Markets may not have exact price targets")
    print(" - Volatility assumptions may be off")
    print(" - Need to account for risk premium in options")

# Try sentiment aggregation
print("\n" + "=" * 70)
print("ASSET SENTIMENT OVERVIEW")
print("=" * 70)

sentiment = detector.get_asset_vs_prediction_sentiment(
    assets=["BTC-USD", "SPY", "AAPL", "TSLA"]
)
for asset, data in sentiment.items():
    print(f"\n{asset}:")
    print(f"  Current price: ${data['current_price']:,.2f}")
    print(f"  Hist vol: {data['volatility']:.1%}")
    opp = data.get("best_opportunity")
    if opp:
        print(f"  Best discrepancy: {opp['discrepancy']:.1%}")
        print(f"    Prediction prob: {opp['prediction_prob']:.1%}")
        print(f"    BS prob: {opp['bs_prob']:.1%}")
        print(f"    Strike: ${opp['strike']:,.0f} {opp['direction']}")
        print(
            f"    Platforms: {', '.join(opp['platforms'])} (total {opp['num_markets']} markets)"
        )

print("\n" + "=" * 70)
print("Test complete")
print("=" * 70)
