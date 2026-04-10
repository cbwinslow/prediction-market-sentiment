"""
Sentiment analysis aggregator for prediction markets.
Computes aggregate sentiment metrics across categories and platforms.
"""

import statistics
from typing import List, Dict, Optional
from datetime import datetime

from src.clients.kalshi_client import KalshiClient, KalshiMarket
from src.clients.polymarket_client import PolymarketClient, PolymarketMarket
from src.utils.models import MarketSentiment


class SentimentAnalyzer:
    """
    Analyzes sentiment across prediction markets.

    Aggregates implied probabilities into category-based sentiment scores,
    calculates volatility metrics, and tracks trends.
    """

    def __init__(self):
        self.kalshi_client = KalshiClient()
        self.polymarket_client = PolymarketClient()

    def _categorize_kalshi_market(self, market: KalshiMarket) -> str:
        """Categorize a Kalshi market into a broader sentiment category"""
        title_lower = market.title.lower()
        category_lower = market.category.lower() if market.category else ""

        if any(
            term in category_lower
            for term in ["politics", "elections", "government", "congress", "senate"]
        ):
            return "politics"
        elif any(
            term in title_lower
            for term in [
                "inflation",
                "gdp",
                "unemployment",
                "interest rate",
                "fed",
                "economy",
            ]
        ):
            return "economy"
        elif any(
            term in title_lower
            for term in ["crypto", "bitcoin", "ethereum", "blockchain"]
        ):
            return "crypto"
        elif any(
            term in title_lower
            for term in ["temperature", "weather", "climate", "hurricane", "storm"]
        ):
            return "weather"
        elif any(
            term in title_lower
            for term in ["sports", "football", "basketball", "soccer", "baseball"]
        ):
            return "sports"
        elif any(
            term in title_lower
            for term in ["tech", "ai", "artificial intelligence", "technology"]
        ):
            return "technology"
        else:
            return "other"

    def _categorize_polymarket_market(self, market: PolymarketMarket) -> str:
        """Categorize a Polymarket market into a broader sentiment category"""
        tags_lower = [t.lower() for t in market.tags]
        question_lower = market.question.lower()

        if any(t in ["politics", "elections", "government"] for t in tags_lower) or any(
            term in question_lower
            for term in ["president", "election", "congress", "senate", "vote"]
        ):
            return "politics"
        elif any(t in ["crypto", "bitcoin", "ethereum"] for t in tags_lower) or any(
            term in question_lower
            for term in ["bitcoin", "ethereum", "crypto", "blockchain"]
        ):
            return "crypto"
        elif any(
            t in ["sports", "football", "basketball", "soccer", "baseball"]
            for t in tags_lower
        ):
            return "sports"
        elif any(t in ["economy", "economic"] for t in tags_lower) or any(
            term in question_lower
            for term in ["inflation", "gdp", "unemployment", "fed", "economy"]
        ):
            return "economy"
        elif any(t in ["weather", "climate", "temperature"] for t in tags_lower):
            return "weather"
        elif any(t in ["technology", "tech", "ai"] for t in tags_lower) or any(
            term in question_lower
            for term in ["ai", "artificial intelligence", "technology"]
        ):
            return "technology"
        else:
            return "other"

    def analyze_sentiment_by_category(
        self,
        include_kalshi: bool = True,
        include_polymarket: bool = True,
        min_probability: float = 0.01,
    ) -> Dict[str, MarketSentiment]:
        """
        Calculate sentiment metrics aggregated by category.

        Args:
            include_kalshi: Include Kalshi markets in analysis
            include_polymarket: Include Polymarket markets in analysis
            min_probability: Minimum probability to include (filters noise)

        Returns:
            Dictionary mapping category -> MarketSentiment
        """
        category_data: Dict[str, List[float]] = {}
        category_volumes: Dict[str, float] = {}

        # Process Kalshi markets
        if include_kalshi:
            kalshi_markets = self.kalshi_client.get_markets(limit=1000)
            for market in kalshi_markets:
                if market.yes_bid_dollars < min_probability:
                    continue
                cat = self._categorize_kalshi_market(market)
                if cat not in category_data:
                    category_data[cat] = []
                    category_volumes[cat] = 0
                category_data[cat].append(market.implied_probability)
                category_volumes[cat] += market.volume

        # Process Polymarket markets
        if include_polymarket:
            polymarket_markets = self.polymarket_client.get_markets(limit=1000)
            for market in polymarket_markets:
                yes_token = next(
                    (t for t in market.tokens if t.outcome.lower() in ["yes", "true"]),
                    None,
                )
                if not yes_token or yes_token.price < min_probability:
                    continue
                cat = self._categorize_polymarket_market(market)
                if cat not in category_data:
                    category_data[cat] = []
                    category_volumes[cat] = 0
                category_data[cat].append(yes_token.price)
                # Rough volume estimate from token price
                category_volumes[cat] += yes_token.price * 10000

        # Calculate sentiment metrics for each category
        sentiments = {}
        now = datetime.now()

        for cat, probabilities in category_data.items():
            if not probabilities:
                continue

            avg_prob = statistics.mean(probabilities)
            total_vol = category_volumes[cat]

            # Calculate volume-weighted probability
            weighted_sum = 0
            total_weight = 0
            for i, prob in enumerate(probabilities):
                # Use simple weight proportional to volume (approximated)
                weight = 1.0  # Can be enhanced with actual volume if available
                weighted_sum += prob * weight
                total_weight += weight
            weighted_prob = (
                weighted_sum / total_weight if total_weight > 0 else avg_prob
            )

            # Count market directions
            bullish = sum(1 for p in probabilities if p > 0.5)
            bearish = sum(1 for p in probabilities if p < 0.5)
            neutral = len(probabilities) - bullish - bearish

            # Calculate volatility (standard deviation)
            volatility = (
                statistics.stdev(probabilities) if len(probabilities) > 1 else 0.0
            )

            sentiment = MarketSentiment(
                category=cat,
                total_markets=len(probabilities),
                avg_probability=avg_prob,
                weighted_probability=weighted_prob,
                total_volume=total_vol,
                bullish_count=bullish,
                bearish_count=bearish,
                neutral_count=neutral,
                volatility=volatility,
                timestamp=now,
            )
            sentiments[cat] = sentiment

        return sentiments

    def get_most_volatile_categories(self, top_n: int = 5) -> List[tuple]:
        """
        Get the most volatile categories (highest disagreement among markets).

        Returns:
            List of (category, volatility) tuples sorted by volatility descending
        """
        sentiments = self.analyze_sentiment_by_category()
        volatile = sorted(
            [(s.category, s.volatility) for s in sentiments.values()],
            key=lambda x: x[1],
            reverse=True,
        )
        return volatile[:top_n]

    def get_sentiment_trends(self) -> Dict[str, Dict[str, float]]:
        """
        Get sentiment comparisons between platforms.

        Returns:
            Dictionary with category -> {kalshi_avg, polymarket_avg, difference}
        """
        kalshi_sentiments = self.analyze_sentiment_by_category(
            include_kalshi=True, include_polymarket=False
        )
        polymarket_sentiments = self.analyze_sentiment_by_category(
            include_kalshi=False, include_polymarket=True
        )

        trends = {}
        all_cats = set(kalshi_sentiments.keys()) | set(polymarket_sentiments.keys())

        for cat in all_cats:
            kalshi_avg = (
                kalshi_sentiments[cat].avg_probability
                if cat in kalshi_sentiments
                else None
            )
            polymarket_avg = (
                polymarket_sentiments[cat].avg_probability
                if cat in polymarket_sentiments
                else None
            )

            if kalshi_avg and polymarket_avg:
                diff = kalshi_avg - polymarket_avg
            elif kalshi_avg:
                diff = kalshi_avg
            elif polymarket_avg:
                diff = -polymarket_avg
            else:
                diff = 0

            trends[cat] = {
                "kalshi_avg": kalshi_avg,
                "polymarket_avg": polymarket_avg,
                "difference": diff,
            }

        return trends
