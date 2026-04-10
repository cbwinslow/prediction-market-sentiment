"""
Cross-asset arbitrage detector.
Compares prediction market odds to actual market prices/options.
"""

import re
import yfinance as yf
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import numpy as np
from scipy.stats import norm

from src.clients.kalshi_client import KalshiClient, KalshiMarket
from src.clients.polymarket_client import PolymarketClient, PolymarketMarket
from src.utils.models import CrossAssetOpportunity


@dataclass
class AssetMatch:
    """Matched prediction market and asset data"""

    platform: str
    market_id: str
    question: str
    asset_ticker: str
    current_asset_price: float
    prediction_probability: float
    expiry_date: Optional[date]
    strike_price: Optional[float]
    direction: str  # "above" or "below"
    market_type: str  # "price_target", "rate", "election", etc


class CrossAssetArbitrageDetector:
    """
    Detects arbitrage between prediction markets and actual asset prices.

    Extracts price targets from prediction market questions, fetches current
    asset prices, calculates the probability of the event occurring based on
    market conditions, and compares to the prediction market's implied probability.
    """

    # Regex patterns for extracting asset references and price targets
    PATTERNS = {
        # "Will BTC be above $100k..." OR "Will BTC reach $100k..."
        "btc": re.compile(
            r"(?:will|does|is).*?(bitcoin|btc).*?(reach|hit|exceed|above|over|greater|less|below|drop|fall|under).*?\$?(\d+(?:[.,]\d+)?)\s?(?:(k|thousand|m|million|b|billion)\b)?",
            re.I,
        ),
        # "Will SPY exceed 500..." OR "Will SPY go above 500..."
        "spy": re.compile(
            r"(?:will|does|is).*?(spy|s&p 500|s&p500).*?(reach|hit|exceed|above|over|below|under|drop|fall).*?\$?(\d+(?:[.,]\d+)?)",
            re.I,
        ),
        # "Will Apple stock be above $200..." OR "Will Apple hit $200..."
        "stock": re.compile(
            r"(?:will|does|is).*?(apple|microsoft|google|amazon|tesla|nvidia|amd|intel|meta|facebook).*?stock.*?(reach|hit|exceed|above|over|below|drop|fall).*?\$?(\d+(?:[.,]\d+)?)",
            re.I,
        ),
        # More generic: "Will X be/stay above/below/go above $Y"
        "generic": re.compile(
            r"(?:will|does|is|can).*?([A-Z]{1,5})\b.*?(be|stay|go|reach|hit|exceed|surpass|top|drop|fall|test)?\s*(?:above|over|below|under|past|>|<)?\s*\$?(\d+(?:[.,]\d+)?)",
            re.I,
        ),
    }

    def __init__(self):
        self.kalshi_client = KalshiClient()
        self.polymarket_client = PolymarketClient()

    def _direction_to_side(self, direction_word: str) -> str:
        """Map direction words to 'above' or 'below'"""
        above_words = [
            "above",
            "over",
            "greater",
            ">",
            "exceed",
            "reach",
            "hit",
            "surpass",
            "top",
            "exceeds",
            "reaches",
        ]
        below_words = [
            "below",
            "under",
            "less",
            "<",
            "drop",
            "fall",
            "below",
            "falls",
            "drops",
        ]
        direction_lower = direction_word.lower()
        if direction_lower in above_words:
            return "above"
        elif direction_lower in below_words:
            return "below"
        else:
            # Default based on context - if unsure, can't determine
            return None

    def _extract_asset_info(self, question: str) -> Optional[Dict]:
        """
        Extract asset ticker, price target, direction from a market question.

        Returns:
            Dict with keys: asset, strike, direction, expiry_approx, confidence
        """
        question_lower = question.lower()

        # Try BTC pattern
        m = self.PATTERNS["btc"].search(question_lower)
        if m:
            asset = "BTC-USD"
            direction_word = m.group(2).lower()
            direction = self._direction_to_side(direction_word)
            if not direction:
                return None
            strike_raw = m.group(3).replace(",", "")
            multiplier = m.group(4).lower() if m.group(4) else ""
            if multiplier in ["k", "thousand"]:
                strike = float(strike_raw) * 1000
            elif multiplier in ["m", "million"]:
                strike = float(strike_raw) * 1000000
            elif multiplier in ["b", "billion"]:
                strike = float(strike_raw) * 1000000000
            else:
                strike = float(strike_raw)
            return {
                "asset": asset,
                "strike": strike,
                "direction": direction,
                "confidence": 0.9,
            }

        # Try SPY pattern
        m = self.PATTERNS["spy"].search(question_lower)
        if m:
            asset = "SPY"
            direction_word = m.group(2).lower()
            direction = self._direction_to_side(direction_word)
            if not direction:
                return None
            strike = float(m.group(3).replace(",", ""))
            return {
                "asset": asset,
                "strike": strike,
                "direction": direction,
                "confidence": 0.85,
            }

        # Try stock pattern
        m = self.PATTERNS["stock"].search(question_lower)
        if m:
            company = m.group(1).lower()
            ticker_map = {
                "apple": "AAPL",
                "microsoft": "MSFT",
                "google": "GOOGL",
                "amazon": "AMZN",
                "tesla": "TSLA",
                "nvidia": "NVDA",
                "amd": "AMD",
                "intel": "INTC",
                "meta": "META",
                "facebook": "META",
            }
            ticker = ticker_map.get(company, company.upper())
            direction_word = m.group(2).lower()
            direction = self._direction_to_side(direction_word)
            if not direction:
                return None
            strike = float(m.group(3).replace(",", ""))
            return {
                "asset": ticker,
                "strike": strike,
                "direction": direction,
                "confidence": 0.8,
            }

        # Try generic ticker pattern (e.g., "Will TSLA go above 300")
        m = self.PATTERNS["generic"].search(question_lower)
        if m:
            ticker = m.group(1).upper()
            direction_word = m.group(2).lower() if m.group(2) else ""
            strike = float(m.group(3).replace(",", ""))
            # Validate ticker format (1-5 uppercase letters)
            if re.match(r"^[A-Z]{1,5}$", ticker):
                direction = self._direction_to_side(direction_word)
                if not direction:
                    # If no explicit direction, can't infer
                    return None
                return {
                    "asset": ticker,
                    "strike": strike,
                    "direction": direction,
                    "confidence": 0.7,
                }

        return None

    def _estimate_expiry(self, market) -> Optional[date]:
        """Estimate expiry date from market data"""
        # Try to get from close_time or expiration
        if hasattr(market, "close_time"):
            try:
                # Parse ISO format
                dt = datetime.fromisoformat(market.close_time.replace("Z", "+00:00"))
                return dt.date()
            except:
                pass

        if hasattr(market, "expiration_time"):
            try:
                dt = datetime.fromisoformat(
                    market.expiration_time.replace("Z", "+00:00")
                )
                return dt.date()
            except:
                pass

        # Guess from title "Will X by Dec 31, 2025?"
        # Could extract month/year but complex - return None
        return None

    def _get_asset_data(self, asset_ticker: str) -> Optional[Dict]:
        """
        Fetch current asset data via yfinance.

        Returns:
            Dict with price, volatility, returns, etc.
        """
        try:
            ticker = yf.Ticker(asset_ticker)

            # Get current price
            info = ticker.info
            current_price = info.get("regularMarketPrice") or info.get("currentPrice")
            if not current_price:
                # Fallback to history
                hist = ticker.history(period="1d")
                if not hist.empty:
                    current_price = float(hist["Close"].iloc[-1])

            if not current_price:
                return None

            # Get historical data for volatility calculation
            hist = ticker.history(period="3mo")
            if hist.empty:
                return None

            # Calculate historical volatility (annualized)
            returns = hist["Close"].pct_change().dropna()
            daily_vol = returns.std()
            annual_vol = daily_vol * np.sqrt(252)

            # Get options expirations if available (for IV)
            try:
                options = ticker.options
                if len(options) > 0:
                    nearest_expiry = options[0]
                    chain = ticker.option_chain(nearest_expiry)
                    # ATM implied volatility
                    spot = current_price
                    atm_calls = chain.calls[
                        chain.calls["strike"].between(spot * 0.9, spot * 1.1)
                    ]
                    if not atm_calls.empty:
                        atm_iv = atm_calls["impliedVolatility"].mean()
                    else:
                        atm_iv = None
                else:
                    nearest_expiry = None
                    atm_iv = None
            except:
                nearest_expiry = None
                atm_iv = None

            return {
                "ticker": asset_ticker,
                "current_price": float(current_price),
                "historical_volatility": float(annual_vol),
                "implied_volatility": float(atm_iv) if atm_iv else None,
                "nearest_expiry": nearest_expiry,
                "returns": returns,
            }
        except Exception as e:
            print(f"Error fetching {asset_ticker}: {e}")
            return None

    def _calculate_bs_probability(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        risk_free_rate: float = 0.05,
        direction: str = "above",
    ) -> float:
        """
        Use Black-Scholes to calculate probability of finishing in-the-money.
        Approximation: For binary options (digital options), probability ≈ N(d2).

        d2 = [ln(S/K) + (r - σ²/2)T] / (σ√T)
        """
        if time_to_expiry <= 0:
            # Expired or immediate - use current moneyness
            if direction == "above":
                return 1.0 if spot > strike else 0.0
            else:
                return 1.0 if spot < strike else 0.0

        S = spot
        K = strike
        T = time_to_expiry
        sigma = volatility
        r = risk_free_rate

        try:
            d2 = (np.log(S / K) + (r - 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            if direction == "above":
                prob = norm.cdf(d2)
            else:
                prob = 1 - norm.cdf(d2)
            return float(prob)
        except:
            return 0.5  # Default if calculation fails

    def find_cross_asset_arbitrage(
        self,
        min_discrepancy: float = 0.15,  # 15% probability difference
        min_volume: float = 1000.0,
        platforms: List[str] = ["kalshi", "polymarket"],
    ) -> List[CrossAssetOpportunity]:
        """
        Find arbitrage opportunities between prediction markets and asset prices.

        Args:
            min_discrepancy: Minimum probability difference to flag
            min_volume: Minimum market volume
            platforms: Which platforms to scan

        Returns:
            List of arbitrage opportunities
        """
        opportunities = []

        # Fetch prediction markets
        kalshi_markets = (
            self.kalshi_client.get_markets(limit=1000) if "kalshi" in platforms else []
        )
        polymarket_markets = (
            self.polymarket_client.get_markets(limit=1000)
            if "polymarket" in platforms
            else []
        )

        # Process Kalshi markets
        for km in kalshi_markets:
            if km.yes_bid_dollars <= 0 or km.volume < min_volume:
                continue

            asset_info = self._extract_asset_info(km.title)
            if not asset_info:
                continue

            asset_ticker = asset_info["asset"]
            strike = asset_info["strike"]
            direction = asset_info["direction"]

            # Get asset data
            asset_data = self._get_asset_data(asset_ticker)
            if not asset_data:
                continue

            spot = asset_data["current_price"]
            vol = (
                asset_data["implied_volatility"] or asset_data["historical_volatility"]
            )

            # Estimate time to expiry
            expiry = self._estimate_expiry(km)
            if expiry:
                T = (expiry - date.today()).days / 365.0
                if T < 0:
                    T = 0
            else:
                # Default 30 days if unknown
                T = 30 / 365.0

            # Calculate risk-neutral probability from asset price
            market_prob = asset_info["confidence"]  # Our confidence in the match
            bs_prob = self._calculate_bs_probability(
                spot, strike, T, vol, direction=direction
            )
            pred_prob = km.implied_probability

            discrepancy = abs(pred_prob - bs_prob)
            if discrepancy >= min_discrepancy:
                opp = CrossAssetOpportunity(
                    platform="kalshi",
                    market_id=km.ticker,
                    question=km.title[:200],
                    asset=asset_ticker,
                    asset_price=asset_data["current_price"],
                    strike=strike,
                    direction=direction,
                    prediction_probability=pred_prob,
                    calculated_probability=bs_prob,
                    discrepancy=discrepancy,
                    time_to_expiry=T,
                    confidence=market_prob,
                )
                opportunities.append(opp)

        # Process Polymarket markets
        for pm in polymarket_markets:
            if not pm.accepting_orders:
                continue

            yes_token = next(
                (t for t in pm.tokens if t.outcome.lower() in ["yes", "true"]), None
            )
            if not yes_token or yes_token.price <= 0:
                continue

            asset_info = self._extract_asset_info(pm.question)
            if not asset_info:
                continue

            asset_ticker = asset_info["asset"]
            strike = asset_info["strike"]
            direction = asset_info["direction"]

            asset_data = self._get_asset_data(asset_ticker)
            if not asset_data:
                continue

            spot = asset_data["current_price"]
            vol = (
                asset_data["implied_volatility"] or asset_data["historical_volatility"]
            )

            expiry = self._estimate_expiry(pm)
            if expiry:
                T = (expiry - date.today()).days / 365.0
                if T < 0:
                    T = 0
            else:
                T = 30 / 365.0

            market_prob = asset_info["confidence"]
            bs_prob = self._calculate_bs_probability(
                spot, strike, T, vol, direction=direction
            )
            pred_prob = yes_token.price

            discrepancy = abs(pred_prob - bs_prob)
            if discrepancy >= min_discrepancy:
                opp = CrossAssetOpportunity(
                    platform="polymarket",
                    market_id=pm.condition_id,
                    question=pm.question[:200],
                    asset=asset_ticker,
                    asset_price=asset_data["current_price"],
                    strike=strike,
                    direction=direction,
                    prediction_probability=pred_prob,
                    calculated_probability=bs_prob,
                    discrepancy=discrepancy,
                    time_to_expiry=T,
                    confidence=market_prob,
                )
                opportunities.append(opp)

        # Sort by discrepancy descending
        opportunities.sort(key=lambda x: x.spread, reverse=True)
        return opportunities

    def get_asset_vs_prediction_sentiment(
        self, assets: List[str] = ["BTC-USD", "SPY", "AAPL", "TSLA", "NVDA"]
    ) -> Dict[str, Dict]:
        """
        For specified assets, show prediction market probabilities vs
        Black-Scholes/options-implied probabilities.

        Returns:
            Dict[asset -> {prediction_prob, bs_prob, discrepancy, best_market}]
        """
        sentiment = {}

        for asset in assets:
            asset_data = self._get_asset_data(asset)
            if not asset_data:
                continue

            # Find matching prediction markets for this asset
            matches = []

            # Check Kalshi
            for km in self.kalshi_client.get_markets(limit=1000):
                if km.yes_bid_dollars <= 0:
                    continue
                info = self._extract_asset_info(km.title)
                if info and info["asset"] == asset:
                    matches.append(
                        {
                            "platform": "kalshi",
                            "market": km,
                            "asset_info": info,
                            "pred_prob": km.implied_probability,
                        }
                    )

            # Check Polymarket
            for pm in self.polymarket_client.get_markets(limit=1000):
                yes_token = next(
                    (t for t in pm.tokens if t.outcome.lower() in ["yes", "true"]), None
                )
                if not yes_token or yes_token.price <= 0:
                    continue
                info = self._extract_asset_info(pm.question)
                if info and info["asset"] == asset:
                    matches.append(
                        {
                            "platform": "polymarket",
                            "market": pm,
                            "asset_info": info,
                            "pred_prob": yes_token.price,
                        }
                    )

            if not matches:
                continue

            # Aggregate by strike/direction
            grouped = {}
            for m in matches:
                strike = m["asset_info"]["strike"]
                direction = m["asset_info"]["direction"]
                key = (strike, direction)
                if key not in grouped:
                    grouped[key] = []
                grouped[key].append(m)

            # Calculate best opportunity for this asset
            best_discrepancy = 0
            best_match = None

            for (strike, direction), group in grouped.items():
                # Average prediction probability
                avg_pred = sum(g["pred_prob"] for g in group) / len(group)

                # Calculate BS probability
                spot = asset_data["current_price"]
                vol = (
                    asset_data["implied_volatility"]
                    or asset_data["historical_volatility"]
                )
                T = 30 / 365.0  # Assume 30 days if no expiry
                bs_prob = self._calculate_bs_probability(
                    spot, strike, T, vol, direction=direction
                )

                discrepancy = abs(avg_pred - bs_prob)
                if discrepancy > best_discrepancy:
                    best_discrepancy = discrepancy
                    best_match = {
                        "strike": strike,
                        "direction": direction,
                        "prediction_probability": avg_pred,
                        "calculated_probability": bs_prob,
                        "discrepancy": discrepancy,
                        "platforms": list(set(g["platform"] for g in group)),
                        "num_markets": len(group),
                    }

            if best_match:
                sentiment[asset] = {
                    "current_price": asset_data["current_price"],
                    "volatility": asset_data["historical_volatility"],
                    "best_opportunity": best_match,
                }

        return sentiment
