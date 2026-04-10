"""
Volatility and liquidity metrics calculator for prediction markets.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime, timedelta

from src.clients.kalshi_client import KalshiClient, KalshiMarket
from src.clients.polymarket_client import PolymarketClient, PolymarketMarket


class VolatilityAnalyzer:
    """
    Calculates volatility and liquidity metrics for prediction markets.

    Metrics include:
    - Spread volatility: How much the bid-ask spread varies
    - Price volatility: Standard deviation of price changes
    - Liquidity score: Based on order book depth
    - Volume profile: Trading volume patterns
    """

    def __init__(self):
        self.kalshi_client = KalshiClient()
        self.polymarket_client = PolymarketClient()

    def calculate_liquidity_score(
        self, orderbook: Dict, market: Optional[object] = None
    ) -> float:
        """
        Calculate a liquidity score (0-100) based on order book depth.

        Args:
            orderbook: Order book data from API
            market: Market object for context

        Returns:
            Liquidity score where higher is more liquid
        """
        # Extract order book data
        if "orderbook_fp" in orderbook:  # Kalshi format
            yes_bids = orderbook["orderbook_fp"].get("yes_dollars", [])
            no_bids = orderbook["orderbook_fp"].get("no_dollars", [])
            total_volume = sum(level[1] for level in yes_bids + no_bids)
        elif "bids" in orderbook:  # Polymarket format
            bids = orderbook.get("bids", [])
            asks = orderbook.get("asks", [])
            total_volume = sum(float(b["size"]) for b in bids) + sum(
                float(a["size"]) for a in asks
            )
        else:
            total_volume = 0

        # Also consider market volume if available
        if market:
            if hasattr(market, "volume"):
                total_volume += market.volume
            elif hasattr(market, "tokens"):
                # Rough estimate for Polymarket
                total_volume += 10000  # Placeholder

        # Normalize to 0-100 scale (log scale to handle large ranges)
        if total_volume > 0:
            score = min(100, np.log10(total_volume + 1) * 20)
        else:
            score = 0

        return round(score, 2)

    def analyze_market_volatility(
        self,
        market_id: str,
        platform: str,
        historical_prices: List[float],
        window: int = 20,
    ) -> Dict[str, float]:
        """
        Calculate volatility metrics for a market.

        Args:
            market_id: Market identifier
            platform: 'kalshi' or 'polymarket'
            historical_prices: List of historical prices
            window: Rolling window for volatility calculation

        Returns:
            Dictionary with volatility metrics
        """
        if len(historical_prices) < 2:
            return {"volatility": 0, "max_drawdown": 0, "sharpe_ratio": 0}

        # Calculate returns
        returns = np.diff(historical_prices) / historical_prices[:-1]

        # Annualized volatility (assuming data is frequent enough)
        volatility = np.std(returns) * np.sqrt(
            252 * 24
        )  # Scale to annual from hourly-ish

        # Maximum drawdown
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = np.min(drawdown)

        # Sharpe ratio (assuming 0% risk-free rate for simplicity)
        if np.std(returns) > 0:
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252 * 24)
        else:
            sharpe_ratio = 0

        return {
            "volatility": round(float(volatility), 4),
            "max_drawdown": round(float(max_drawdown), 4),
            "sharpe_ratio": round(float(sharpe_ratio), 4),
            "data_points": len(historical_prices),
        }

    def get_liquidity_rankings(self, top_n: int = 20) -> List[Dict]:
        """
        Get markets ranked by liquidity.

        Returns:
            List of markets with liquidity scores, sorted descending
        """
        rankings = []

        # Get Kalshi markets
        try:
            kalshi_markets = self.kalshi_client.get_markets(limit=100)
            for km in kalshi_markets[:top_n]:
                try:
                    orderbook = self.kalshi_client.get_orderbook(km.ticker)
                    score = self.calculate_liquidity_score(orderbook, km)
                    rankings.append(
                        {
                            "platform": "kalshi",
                            "market_id": km.ticker,
                            "title": km.title,
                            "liquidity_score": score,
                            "volume": km.volume,
                            "category": km.category,
                        }
                    )
                except Exception as e:
                    continue
        except Exception as e:
            print(f"Error fetching Kalshi liquidity: {e}")

        # Get Polymarket markets
        try:
            polymarket_markets = self.polymarket_client.get_markets(limit=100)
            for pm in polymarket_markets[:top_n]:
                try:
                    yes_token = next(
                        (t for t in pm.tokens if t.outcome.lower() in ["yes", "true"]),
                        None,
                    )
                    if not yes_token:
                        continue
                    orderbook = self.polymarket_client.get_orderbook(yes_token.token_id)
                    score = self.calculate_liquidity_score(orderbook, pm)
                    rankings.append(
                        {
                            "platform": "polymarket",
                            "market_id": pm.condition_id,
                            "title": pm.question,
                            "liquidity_score": score,
                            "volume": yes_token.price * 10000,  # Rough estimate
                            "category": ", ".join(pm.tags[:3]),
                        }
                    )
                except Exception as e:
                    continue
        except Exception as e:
            print(f"Error fetching Polymarket liquidity: {e}")

        # Sort by liquidity score descending
        rankings.sort(key=lambda x: x["liquidity_score"], reverse=True)
        return rankings[:top_n]

    def calculate_spread_volatility(
        self, market_id: str, platform: str, num_snapshots: int = 100
    ) -> Dict[str, float]:
        """
        Calculate how volatile the spread is over time (snapshots needed).

        This is a placeholder - would need historical order book data.
        For now, returns current spread statistics.
        """
        spreads = []

        try:
            if platform == "kalshi":
                market = self.kalshi_client.get_market(market_id)
                orderbook = self.kalshi_client.get_orderbook(market_id)
                # Extract current spread
                if "orderbook_fp" in orderbook:
                    yes_bids = orderbook["orderbook_fp"].get("yes_dollars", [])
                    if yes_bids:
                        best_bid = yes_bids[0][0]
                        best_ask = yes_bids[0][0]  # In binary markets, ask = 1 - bid
                        spread = abs(best_ask - best_bid)
                        spreads.append(spread)
            elif platform == "polymarket":
                market = self.polymarket_client.get_market(market_id)
                yes_token = next(
                    (
                        t
                        for t in market["tokens"]
                        if t["outcome"].lower() in ["yes", "true"]
                    ),
                    None,
                )
                if yes_token:
                    orderbook = self.polymarket_client.get_orderbook(
                        yes_token["token_id"]
                    )
                    bids = orderbook.get("bids", [])
                    asks = orderbook.get("asks", [])
                    if bids and asks:
                        best_bid = float(bids[0]["price"])
                        best_ask = float(asks[0]["price"])
                        spread = best_ask - best_bid
                        spreads.append(spread)
        except Exception as e:
            print(f"Error calculating spread: {e}")

        if spreads:
            return {
                "current_spread": round(spreads[0], 4),
                "spread_mean": round(np.mean(spreads), 4),
                "spread_std": round(np.std(spreads), 4),
                "spread_volatility": round(
                    np.std(spreads) / np.mean(spreads) if np.mean(spreads) > 0 else 0, 4
                ),
            }
        else:
            return {
                "current_spread": 0,
                "spread_mean": 0,
                "spread_std": 0,
                "spread_volatility": 0,
            }
