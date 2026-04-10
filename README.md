# Prediction Market Sentiment Analyzer

A free tool that analyzes sentiment, detects arbitrage opportunities, and calculates volatility metrics across prediction markets on **Kalshi** and **Polymarket**.

## ⚡ Current Status (April 2026)

### ✅ Working
- **Polymarket Gamma API** - Live data without authentication
  - 200+ active markets with real-time prices
  - Volume data ($10M+ on popular markets like GTA VI)
  - Best bid/ask prices
- Arbitrage detection algorithm (tested with historical data)
- Sentiment analysis by category
- Cross-asset arbitrage module (prediction markets vs stock/crypto prices)
- CLI with 7 commands

### ⚠️ Limited By Data
- **Kalshi API** - Public endpoint returns markets but no active bid/ask data
  - Need API key + account activity for live pricing

### 🔄 Next Step (Requires Your Action)
- **Polymarket Wallet Auth** - For order book depth (bids/asks with sizes)
  - Need MetaMask private key
  - Enables real cross-platform arbitrage detection

---

## Features

### 1. Arbitrage Opportunity Finder
- Scans both platforms for price discrepancies on similar events
- Calculates spread, confidence scores, and volume-weighted opportunities
- Filters by minimum spread, volume, and confidence thresholds
- Returns sorted list of best arbitrage opportunities

### 2. Sentiment Analysis
- Aggregates implied probabilities by category (politics, crypto, sports, economy, etc.)
- Calculates volume-weighted average probabilities
- Identifies bullish vs bearish markets
- Measures sentiment volatility within categories
- Generates sentiment scores from -1 (bearish) to +1 (bullish)

### 3. Cross-Platform Sentiment Trends
- Compares sentiment between Kalshi and Polymarket by category
- Identifies which platform is more bullish/bearish on specific topics
- Highlights major divergences

### 4. Liquidity Rankings
- Ranks markets by liquidity score (order book depth + volume)
- Helps identify most tradable markets
- Available for both platforms

### 5. Comprehensive Market Explorer
- Lists all active markets with current prices
- Shows order book depth
- Displays spreads and volumes

### 6. Cross-Asset Arbitrage
- Compares prediction market probabilities to options-implied probabilities
- Uses Black-Scholes model for risk-neutral probabilities
- Supports stocks (via yfinance) and crypto

---

## Installation

```bash
# Clone the project
cd prediction-market-sentiment

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install optional: py-clob-client for authenticated access
pip install py-clob-client
```

## Quick Start

```bash
# Show all commands
python -m src.cli --help

# Find arbitrage opportunities (needs live data)
python -m src.cli arbitrage --min-spread 0.02 --min-confidence 0.3

# Analyze sentiment by category
python -m src.cli sentiment

# Compare Kalshi vs Polymarket sentiment
python -m src.cli trends --top 10

# View liquidity rankings
python -m src.cli liquidity --top 20

# List all markets (Polymarket has live data!)
python -m src.cli markets --platform polymarket

# Cross-asset arbitrage (prediction vs stock/crypto prices)
python -m src.cli cross-arbitrage --assets BTC-USD,SPY

# Get a comprehensive summary
python -m src.cli summary
```

## Testing Scripts

```bash
# Test live data from Polymarket
python test_live_arbitrage.py

# Test historical arbitrage (proof of concept)
python test_historical_arbitrage.py

# Test authenticated client (requires wallet)
python test_auth_client.py
```

---

## How It Works

### Data Sources

| Platform | API | Auth Required? | Data Available |
|----------|-----|----------------|-----------------|
| Polymarket | Gamma API (free) | No | ✅ Prices, volume, best bid/ask |
| Polymarket | CLOB API | Yes (wallet) | ✅ Order book depth, trading |
| Kalshi | Trade API | Yes (API key) | ⚠️ Markets only (no active bids) |

**Polymarket Gamma API** - No authentication required:
- 200+ active markets with real-time prices
- Volume data (e.g., GTA VI: $13M+)
- Best bid/ask from order book

### Arbitrage Detection

The tool uses natural language processing to match similar markets:

1. **Text similarity**: SequenceMatcher compares market questions
2. **Keyword matching**: Jaccard similarity on extracted key terms
3. **Price comparison**: Calculates spread between matched markets
4. **Confidence scoring**: Combines similarity score and volume metrics

### Cross-Asset Arbitrage

Compares prediction market implied probabilities to:
- **Options-implied probabilities** (Black-Scholes model)
- **Stock/crypto prices** (via yfinance)

Example:
- Prediction market: "Bitcoin above $100k by Dec 2025" = 45%
- Black-Scholes (BTC at $72k, 50% vol, 0.8 years to expiry) = 62%
- Discrepancy: 17% → Potential arbitrage opportunity

---

## Setting Up Authentication

### Polymarket Wallet (Recommended)

For order book depth and trading:

```bash
# 1. Get your private key from MetaMask:
#    Account menu → Account Details → Show Private Key
#    Copy the key (WITHOUT the 0x prefix)

# 2. Set environment variable
export POLYMARKET_PRIVATE_KEY="your_key_without_0x"

# 3. (Optional) For email/Magic wallet
export POLYMARKET_FUNDER_ADDRESS="your_proxy_wallet"
export POLYMARKET_SIGNATURE_TYPE="1"
```

Then run `python test_auth_client.py` to verify.

### Kalshi API Key

1. Create account at [kalshi.com](https://kalshi.com)
2. Generate API key in account settings
3. Use authenticated endpoints for live bid/ask data

---

## Sample Output

### Live Markets (Polymarket Gamma API)
```
Q: Russia-Ukraine Ceasefire before GTA VI?
  Yes: 52.50%, Volume: $1,460,280

Q: Will Jesus Christ return before GTA VI?
  Yes: 48.50%, Volume: $10,936,726

Q: GTA VI released before June 2026?
  Yes: 1.85%, Volume: $13,301,208
```

### Arbitrage Test (Historical Proof of Concept)
```
Question                                                  Spread       Volume
--------------------------------------------------------------------------------
NBA: Wizards vs. Pistons (02/01/2023)                     21.1% $   254,806
Will the FDV of OpenSea's token be above $15b 1 week after l   14.7% $    88,334
NBA: Wizards vs. Nets (02/04/2023)                        13.4% $   223,815
```

---

## Project Structure

```
prediction-market-sentiment/
├── src/
│   ├── cli.py                     # Main CLI interface
│   ├── clients/
│   │   ├── kalshi_client.py       # Kalshi API wrapper
│   │   ├── polymarket_client.py  # Polymarket Gamma API (free)
│   │   └── polymarket_auth.py     # Polymarket CLOB API (wallet auth)
│   ├── analyzers/
│   │   ├── arbitrage.py          # Platform arbitrage detection
│   │   ├── sentiment.py          # Category sentiment analysis
│   │   ├── volatility.py         # Liquidity/volatility metrics
│   │   └── cross_asset.py        # Cross-asset arbitrage
│   └── utils/
│       ├── models.py              # Data models
│       └── exporter.py           # Export utilities
├── tests/
│   └── test_basic.py
├── test_live_arbitrage.py         # Test live data
├── test_historical_arbitrage.py  # Proof of concept
├── test_auth_client.py           # Auth setup
├── requirements.txt
├── setup.py
└── README.md
```

---

## Limitations

- **Kalshi data**: Public API returns markets but no active bid/ask. Need API key for live data.
- **Matching algorithm**: Text similarity is approximate; some matches may not be identical events
- **No real trading**: This is an analysis tool only
- **Rate limits**: Respect API limits (4000 req/10s for Gamma API)
- **Cross-platform arb**: Requires authenticated access for order book depth

---

## Disclaimer

**This tool is for educational and research purposes only.**

Prediction markets involve real money and significant risk. The arbitrage opportunities identified may not be risk-free due to:
- Event outcome differences (markets aren't perfectly matched)
- Transaction costs and fees
- Timing risks (prices change quickly)
- Settlement risks

Always do your own research and understand the risks before making any financial decisions.

---

## License

MIT License - feel free to use and modify.

---

## Credits

Built using free public APIs from:
- [Kalshi](https://kalshi.com) - CFTC-regulated prediction market
- [Polymarket](https://polymarket.com) - Decentralized prediction market

Official SDKs: `py-clob-client`, `kalshi_python_sync`