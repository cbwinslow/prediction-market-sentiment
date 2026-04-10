#!/usr/bin/env python3
"""
DEMONSTRATION: How the arbitrage scanner would work with real data
This uses simulated/example data to show the methodology.
"""

import random
from datetime import datetime
from rich.console import Console
from rich.table import Table

console = Console()


def simulate_active_markets():
    """Simulate what active markets would look like based on web UI observations"""

    # Based on Polymarket web UI (April 8, 2026), these are real active markets
    mock_markets = [
        {
            "platform": "polymarket",
            "id": "0x123...",
            "question": "Will Bitcoin be above $70,000 on April 30, 2026?",
            "asset": "BTC-USD",
            "strike": 70000,
            "direction": "above",
            "current_price": 71686,
            "historical_vol": 0.498,
            "prediction_prob": 0.62,  # Market implied
            "bs_prob": 0.58,  # Calculated
            "volume_usd": 270000,
            "tags": ["crypto", "bitcoin"],
        },
        {
            "platform": "polymarket",
            "id": "0x456...",
            "question": "Will WTI Crude Oil hit $90+ in April 2026?",
            "asset": "CL=F",  # Oil futures
            "strike": 90,
            "direction": "above",
            "current_price": 82.50,
            "historical_vol": 0.35,
            "prediction_prob": 0.45,
            "bs_prob": 0.52,
            "volume_usd": 16000000,
            "tags": ["finance", "oil"],
        },
        {
            "platform": "polymarket",
            "id": "0x789...",
            "question": "Will Strait of Hormuz traffic normalize by April 30?",
            "asset": "IRAN",  # Proxy
            "strike": None,
            "direction": None,
            "current_price": None,
            "historical_vol": None,
            "prediction_prob": 0.50,  # Binary event, no BS calc
            "bs_prob": None,
            "volume_usd": 4000000,
            "tags": ["politics", "middle-east"],
        },
        {
            "platform": "kalshi",
            "id": "KXHIGHNY-26APR30-85",
            "question": "Will NYC high temp exceed 85°F on April 30?",
            "asset": "weather",
            "strike": 85,
            "direction": "above",
            "current_price": None,  # Not a tradeable asset
            "historical_vol": None,
            "prediction_prob": 0.38,
            "bs_prob": None,
            "volume_usd": 5000,
            "tags": ["weather"],
        },
    ]

    return mock_markets


def demonstrate_arbitrage():
    """Show what arbitrage opportunities would look like"""

    console.print("\n" + "=" * 80)
    console.print("ARBITRAGE SCANNER - DEMONSTRATION WITH SIMULATED DATA")
    console.print("=" * 80)
    console.print(
        "\n[Note: Using simulated data because public APIs return stale data]"
    )
    console.print("[Real data requires API keys or web scraping - see README]\n")

    markets = simulate_active_markets()

    # Show active markets
    table = Table(title="Active Markets (Simulated)")
    table.add_column("Platform")
    table.add_column("Question")
    table.add_column("Pred Prob", justify="right")
    table.add_column("Volume", justify="right")
    table.add_column("Tags")

    for m in markets:
        vol_display = (
            f"${m['volume_usd'] / 1e6:.1f}M"
            if m["volume_usd"] > 1e6
            else f"${m['volume_usd'] / 1e3:.0f}K"
        )
        table.add_row(
            m["platform"],
            m["question"][:50] + "...",
            f"{m['prediction_prob']:.1%}",
            vol_display,
            ", ".join(m["tags"][:2]),
        )

    console.print(table)

    # Demonstrate cross-asset arbitrage
    console.print("\n" + "=" * 80)
    console.print("CROSS-ASSET ARBITRAGE EXAMPLE")
    console.print("=" * 80)

    example = {
        "question": "Will Bitcoin exceed $100k by Dec 2025?",
        "current_btc": 71686,
        "strike": 100000,
        "prediction_prob": 0.45,
        "bs_prob": 0.62,
        "time_to_expiry": 0.75,
        "volatility": 0.50,
    }

    console.print(f"\nEvent: {example['question']}")
    console.print(f"Current BTC price: ${example['current_btc']:,.0f}")
    console.print(f"Strike: ${example['strike']:,}")
    console.print(f"Time to expiry: {example['time_to_expiry']:.1f} years")
    console.print(f"Volatility: {example['volatility']:.1%}")
    console.print("\nCalculation:")
    console.print(f"  Black-Scholes probability: {example['bs_prob']:.1%}")
    console.print(f"  Prediction market probability: {example['prediction_prob']:.1%}")
    discrepancy = abs(example["bs_prob"] - example["prediction_prob"])
    console.print(f"  Discrepancy: [bold green]{discrepancy:.1%}[/bold green]")

    if discrepancy >= 0.15:
        console.print(f"\n[bold green]✓ ARBITRAGE OPPORTUNITY IDENTIFIED[/bold green]")
        console.print("Strategy:")
        console.print(
            f"  - If BS prob > pred prob: Market undervalued → BUY prediction"
        )
        console.print(
            f"  - If BS prob < pred prob: Market overvalued → SELL/SHORT prediction"
        )
    else:
        console.print("\nMarket efficiently priced")

    # Demonstrate intra-platform arb
    console.print("\n" + "=" * 80)
    console.print("INTRAPLATFORM ARBITRAGE EXAMPLE")
    console.print("=" * 80)

    scenario = [
        ("Will Fed raise rates in April?", 0.72, 16000000),
        ("Will Fed increase rates Apr 2026?", 0.68, 12000000),
    ]

    console.print("\nTwo markets on same event with different prices:")
    for q, prob, vol in scenario:
        console.print(f"  {q}")
        console.print(f"    Probability: {prob:.1%}, Volume: ${vol / 1e6:.1f}M")

    avg_prob = sum(p for _, p, _ in scenario) / len(scenario)
    spread = max(p for _, p, _ in scenario) - min(p for _, p, _ in scenario)
    console.print(f"\nAverage probability: {avg_prob:.1%}")
    console.print(f"Spread between markets: {spread:.1%}")

    if spread >= 0.03:
        console.print(
            f"\n[bold green]✓ ARBITRAGE: Long cheaper market, short dearer market[/bold green]"
        )
        console.print("Profit locked in when positions closed, regardless of outcome")

    console.print("\n" + "=" * 80)
    console.print("HOW TO GET REAL DATA")
    console.print("=" * 80)
    console.print("""
To make this work with real data:

1. POLYMARKET:
   - Create account at polymarket.com
   - Generate API key in settings
   - Add API creds to .env (or modify client to use public stats endpoint)
   - Web scraping may be needed for live order books

2. KALSHI:
   - Create account at kalshi.com
   - Generate API key
   - Use authenticated endpoints for live market data

3. ALTERNATIVE DATA SOURCES:
   - Use The Graph protocol to query on-chain Polymarket data
   - WebSocket subscriptions for real-time updates
   - Paid APIs: Bloomberg Terminal, Reuter's Eikon, etc.

4. SETUP:
   cp .env.example .env
   # Fill in API keys
   pip install -r requirements.txt
   python -m src.cli cross-arbitrage --assets BTC-USD,SPY,AAPL

5. MONITOR:
   - Run scanner periodically (cron job)
   - Set thresholds: min_discrepancy=0.15, min_volume=10000
   - Save opportunities to CSV/JSON for analysis
""")


if __name__ == "__main__":
    demonstrate_arbitrage()
