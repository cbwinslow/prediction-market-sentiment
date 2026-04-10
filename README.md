# Prediction Market Sentiment Analyzer

A free tool that analyzes sentiment, detects arbitrage opportunities, and calculates volatility metrics across prediction markets on **Kalshi** and **Polymarket**.

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

## Installation

```bash
# Clone or download the project
cd prediction-market-sentiment

# Install dependencies
pip install -r requirements.txt

# Or run the setup script
python setup.py
```

## Quick Start

```bash
# Show all commands
python -m src.cli --help

# Find arbitrage opportunities
python -m src.cli arbitrage --min-spread 0.02 --min-confidence 0.3

# Analyze sentiment by category
python -m src.cli sentiment

# Compare Kalshi vs Polymarket sentiment
python -m src.cli trends --top 10

# View liquidity rankings
python -m src.cli liquidity --top 20

# List all markets
python -m src.cli markets --platform both

# Get a comprehensive summary
python -m src.cli summary
```

## How It Works

### Data Sources
All data is fetched from **free public APIs**:

- **Kalshi**: `https://api.elections.kalshi.com/trade-api/v2`
  - No authentication required for public market data
  - Official Python SDK: `kalshi_python_sync`
  
- **Polymarket**: `https://clob.polymarket.com`
  - No authentication required for public endpoints
  - SDK: `py-clob-client`

### Arbitrage Detection

The tool uses natural language processing techniques to match similar markets:

1. **Text similarity**: Sequence matcher compares market questions
2. **Keyword matching**: Jaccard similarity on extracted key terms
3. **Price comparison**: Calculates spread between matched markets
4. **Confidence scoring**: Combines similarity score and volume metrics

Example arbitrage opportunity:
```
Platforms: kalshi ↔ polymarket
Kalshi: KXAPPROVAL "Will Biden's approval be > 45%?" - Yes: $0.48
Polymarket: "Will Biden's approval rating be above 45%?" - Yes: $0.52
Spread: 4 cents (8.3%)
Confidence: 85%
```

### Sentiment Analysis

Markets are categorized into broader themes:
- **Politics**: Elections, approval ratings, government actions
- **Crypto**: Bitcoin, Ethereum, blockchain events
- **Sports**: Games, tournaments, player outcomes
- **Economy**: Inflation, GDP, Fed decisions
- **Weather**: Temperature, storms, climate events
- **Technology**: AI, tech companies, innovations

For each category, the tool calculates:
- Average implied probability
- Volume-weighted probability
- Bullish/bearish count
- Volatility (standard deviation)
- Composite sentiment score

## Output Examples

### Arbitrage Table
```
┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━┓
┃ Platforms              ┃ Kalshi Market                                                          ┃ Polymarket Question                                      ┃ Spread   ┃ Spread %┃ Confidence┃
┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━┩
│ kalshi ↔ polymarket    │ KXAPPROVAL "Will Biden approval be > 44% Dec?"                        │ "Will Biden's approval rating be above 44% at end of… │ $0.042   ┃ 8.4%   │ 78%       │
│ kalshi ↔ polymarket    │ KXAPPROVAL "Will Biden approval be > 43% Dec?"                        │ "Will Biden's approval rating be above 43% at end of… │ $0.038   ┃ 7.6%   │ 72%       │
│ kalshi ↔ polymarket    │ KXETH "Will Ethereum be > $4000 Dec 31?"                              │ "Will ETH be above $4000 on Dec 31, 2025?"             │ $0.085   ┃ 6.8%   │ 85%       │
└───────────────────────┴─────────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────┴──────────┴────────┴──────────┘
```

### Sentiment Table
```
┏━━━━━━━━━━ ┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Category  ┃ Markets  ┃ Avg Prob ┃ Wtd Prob ┃ Bullish  ┃ Bearish  ┃ Neutral  ┃ Volatility┃ Score      ┃
┡━━━━━━━━━━ ╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ politics  ┃ 127      ┃ 58.2%    ┃ 57.8%    ┃ 78       ┃ 42       ┃ 7        ┃ 0.142     ┃ +0.23      │
│ crypto    ┃ 89       ┃ 62.4%    ┃ 63.1%    ┃ 61       ┃ 25       ┃ 3        ┃ 0.189     ┃ +0.42      │
│ sports    ┃ 203      ┃ 51.2%    ┃ 51.0%    ┃ 98       ┃ 101      ┃ 4        ┃ 0.098     ┃ -0.01      │
│ economy   ┃ 56       ┃ 47.8%    ┃ 48.2%    ┃ 19       ┃ 34       ┃ 3        ┃ 0.121     ┃ -0.21      │
└───────────┴──────────┴──────────┴──────────┴──────────┴──────────┴──────────┴───────────┴────────────┘
```

## Technical Details

### Project Structure
```
prediction-market-sentiment/
├── src/
│   ├── cli.py              # Main CLI interface
│   ├── clients/
│   │   ├── kalshi_client.py    # Kalshi API wrapper
│   │   └── polymarket_client.py # Polymarket API wrapper
│   ├── analyzers/
│   │   ├── arbitrage.py        # Arbitrage detection
│   │   ├── sentiment.py        # Sentiment analysis
│   │   └── volatility.py       # Volatility metrics
│   └── utils/
│       └── models.py           # Data models
├── requirements.txt
├── setup.py
├── README.md
└── tests/
```

### Python SDKs (Optional)
You can also use the official SDKs directly if you need advanced features:

```bash
pip install kalshi_python_sync py-clob-client
```

## Limitations

- **Matching algorithm**: Text similarity matching is approximate; some matched pairs may not be identical events
- **No real trading**: This is an analysis tool only - no actual trading execution
- **Rate limits**: Public APIs may have rate limits; use responsibly
- **Historical data**: Limited to what's available via public endpoints
- **Volume estimates**: Polymarket volume is estimated from token prices (actual volume data requires auth)
- **Data availability**: Kalshi's API may return many markets with zero liquidity at times. Active markets with real prices are often concentrated in specific series (e.g., weather, esports). For best results, query during active trading periods or focus on series with known volume.

## Future Enhancements

- [ ] Real-time WebSocket streaming for live updates
- [ ] Historical price trend analysis
- [ ] Correlation matrix between markets
- [ ] Portfolio rebalancing suggestions
- [ ] Export to CSV/Excel
- [ ] Web dashboard (Streamlit/Dash)
- [ ] Machine learning prediction models
- [ ] Alert/notification system for new arbitrage opportunities
- [ ] Order book depth visualization
- [ ] Multi-language support

## Disclaimer

**This tool is for educational and research purposes only.**

Prediction markets involve real money and significant risk. The arbitrage opportunities identified may not be risk-free due to:
- Event outcome differences (markets aren't perfectly matched)
- Transaction costs and fees
- Timing risks (prices change quickly)
- Settlement risks

Always do your own research and understand the risks before making any financial decisions.

## License

MIT License - feel free to use and modify.

## Credits

Built using free public APIs from:
- [Kalshi](https://kalshi.com) - CFTC-regulated prediction market
- [Polymarket](https://polymarket.com) - Decentralized prediction market
