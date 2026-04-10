"""
Arbitrage detection across Kalshi and Polymarket prediction markets.
Identifies price discrepancies between platforms for similar events.
"""

import re
from typing import List, Dict, Tuple, Set
from difflib import SequenceMatcher
from dataclasses import dataclass

from src.clients.kalshi_client import KalshiClient, KalshiMarket
from src.clients.polymarket_client import PolymarketClient, PolymarketMarket
from src.utils.models import ArbitrageOpportunity


@dataclass
class EventMatch:
    """Helper for matching similar events across platforms"""

    kalshi_market: KalshiMarket
    polymarket_market: PolymarketMarket
    similarity_score: float
    normalized_kalshi_prob: float
    normalized_polymarket_prob: float


class ArbitrageDetector:
    """
    Detects arbitrage opportunities between Kalshi and Polymarket.

    Arbitrage occurs when the same or very similar events have different
    implied probabilities on different platforms, allowing for risk-free
    profit by buying on the cheaper platform and selling on the expensive one.
    """

    def __init__(self, similarity_threshold: float = 0.7):
        """
        Initialize the arbitrage detector.

        Args:
            similarity_threshold: Minimum text similarity (0-1) to consider markets related
        """
        self.similarity_threshold = similarity_threshold
        self.kalshi_client = KalshiClient()
        self.polymarket_client = PolymarketClient()

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison by removing extra spaces, lowercase, etc."""
        # Remove special characters, normalize whitespace, lowercase
        normalized = re.sub(r"[^\w\s]", "", text.lower())
        normalized = " ".join(normalized.split())
        return normalized

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate string similarity between two texts"""
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)
        return SequenceMatcher(None, norm1, norm2).ratio()

    def _extract_key_terms(self, text: str) -> Set[str]:
        """Extract key terms from market question/title"""
        # Remove common stop words and keep meaningful terms
        stop_words = {
            "will",
            "what",
            "who",
            "when",
            "where",
            "the",
            "a",
            "an",
            "is",
            "are",
            "be",
            "to",
            "of",
            "and",
            "or",
            "in",
            "on",
            "at",
            "for",
            "by",
            "with",
        }
        words = self._normalize_text(text).split()
        return {word for word in words if len(word) > 2 and word not in stop_words}

    def _jaccard_similarity(self, set1: Set[str], set2: Set[str]) -> float:
        """Calculate Jaccard similarity between two sets of terms"""
        if not set1 or not set2:
            return 0.0
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return intersection / union

    def match_markets(
        self,
        kalshi_markets: List[KalshiMarket],
        polymarket_markets: List[PolymarketMarket],
    ) -> List[EventMatch]:
        """
        Match similar markets between Kalshi and Polymarket.

        Args:
            kalshi_markets: List of Kalshi markets
            polymarket_markets: List of Polymarket markets

        Returns:
            List of EventMatch objects with matched markets
        """
        matches = []

        for km in kalshi_markets:
            for pm in polymarket_markets:
                # Skip inactive/closed markets
                if not km.yes_bid_dollars or not pm.tokens:
                    continue

                # Get the YES token from Polymarket (assuming binary markets)
                pm_yes_token = next(
                    (t for t in pm.tokens if t.outcome.lower() in ["yes", "true"]), None
                )
                if not pm_yes_token:
                    continue

                # Calculate similarity scores
                text_similarity = self._calculate_similarity(km.title, pm.question)
                kalshi_terms = self._extract_key_terms(km.title)
                polymarket_terms = self._extract_key_terms(pm.question)
                jaccard_sim = self._jaccard_similarity(kalshi_terms, polymarket_terms)

                # Combined similarity score
                combined_score = text_similarity * 0.6 + jaccard_sim * 0.4

                if combined_score >= self.similarity_threshold:
                    match = EventMatch(
                        kalshi_market=km,
                        polymarket_market=pm,
                        similarity_score=combined_score,
                        normalized_kalshi_prob=km.implied_probability,
                        normalized_polymarket_prob=pm_yes_token.price,
                    )
                    matches.append(match)

        # Sort by similarity (best matches first)
        matches.sort(key=lambda x: x.similarity_score, reverse=True)
        return matches

    def find_arbitrage_opportunities(
        self,
        min_spread: float = 0.02,
        min_volume: float = 100.0,
        min_confidence: float = 0.3,
    ) -> List[ArbitrageOpportunity]:
        """
        Find arbitrage opportunities between matched markets.

        Args:
            min_spread: Minimum price difference to consider (in probability units)
            min_volume: Minimum combined volume to consider
            min_confidence: Minimum confidence score (0-1)

        Returns:
            List of arbitrage opportunities sorted by spread descending
        """
        # Fetch markets from both platforms
        kalshi_markets = self.kalshi_client.get_markets(limit=500)
        polymarket_markets = self.polymarket_client.get_markets(limit=500)

        # Filter for active markets with prices
        kalshi_markets = [
            m for m in kalshi_markets if m.yes_bid_dollars > 0 and m.yes_ask_dollars > 0
        ]
        polymarket_markets = [
            m for m in polymarket_markets if m.accepting_orders and len(m.tokens) >= 2
        ]

        # Match markets
        matches = self.match_markets(kalshi_markets, polymarket_markets)

        opportunities = []
        for match in matches:
            km = match.kalshi_market
            pm = match.polymarket_market
            pm_yes_token = next(
                t for t in pm.tokens if t.outcome.lower() in ["yes", "true"]
            )

            # Calculate spread
            prob_a = match.normalized_kalshi_prob
            prob_b = match.normalized_polymarket_prob
            spread = abs(prob_a - prob_b)

            if spread < min_spread:
                continue

            # Calculate combined volume
            combined_volume = km.volume + (
                pm_yes_token.price * 10000
            )  # Rough estimate from token price

            if combined_volume < min_volume:
                continue

            # Calculate confidence based on similarity, volume, and market liquidity
            volume_factor = min(1.0, combined_volume / 1000000)  # Cap at 1.0
            similarity_factor = match.similarity_score
            confidence = similarity_factor * 0.5 + volume_factor * 0.5

            if confidence < min_confidence:
                continue

            # Calculate implied probability difference as percentage
            avg_prob = (prob_a + prob_b) / 2
            prob_diff_pct = (spread / avg_prob) * 100 if avg_prob > 0 else 0

            opp = ArbitrageOpportunity(
                platform_a="kalshi",
                platform_b="polymarket",
                market_a=km.ticker,
                market_b=pm.condition_id,
                event_a=km.event_ticker,
                event_b=pm.question[:50],
                price_a=prob_a,
                price_b=prob_b,
                spread=spread,
                spread_pct=prob_diff_pct,
                volume_a=km.volume,
                volume_b=combined_volume,
                implied_probability_difference=spread,
                confidence=confidence,
            )
            opportunities.append(opp)

        # Sort by spread (highest first)
        opportunities.sort(key=lambda x: x.spread, reverse=True)
        return opportunities

    def get_cross_platform_sentiment(self) -> Dict[str, float]:
        """
        Calculate aggregate sentiment differences between platforms.

        Returns:
            Dictionary with category -> sentiment delta (positive means Kalshi more bullish)
        """
        kalshi_markets = self.kalshi_client.get_markets(limit=1000)
        polymarket_markets = self.polymarket_client.get_markets(limit=1000)

        # Group by category (simplified matching)
        kalshi_by_category = {}
        for m in kalshi_markets:
            cat = m.category.lower() if m.category else "other"
            if cat not in kalshi_by_category:
                kalshi_by_category[cat] = []
            kalshi_by_category[cat].append(m.implied_probability)

        polymarket_by_category = {}
        for m in polymarket_markets:
            # Map Polymarket categories/tags to comparable groups
            tags = [t.lower() for t in m.tags]
            if any(t in ["politics", "elections", "government"] for t in tags):
                cat = "politics"
            elif any(t in ["crypto", "bitcoin", "ethereum"] for t in tags):
                cat = "crypto"
            elif any(t in ["sports", "football", "basketball", "soccer"] for t in tags):
                cat = "sports"
            elif any(t in ["economy", "economic", "inflation", "gdp"] for t in tags):
                cat = "economy"
            elif any(t in ["weather", "climate", "temperature"] for t in tags):
                cat = "weather"
            else:
                cat = "other"

            if cat not in polymarket_by_category:
                polymarket_by_category[cat] = []
            # Use yes token price
            yes_token = next(
                (t for t in m.tokens if t.outcome.lower() in ["yes", "true"]), None
            )
            if yes_token:
                polymarket_by_category[cat].append(yes_token.price)

        # Calculate average sentiment by category
        sentiment_deltas = {}
        all_categories = set(kalshi_by_category.keys()) | set(
            polymarket_by_category.keys()
        )

        for cat in all_categories:
            k_probs = kalshi_by_category.get(cat, [])
            p_probs = polymarket_by_category.get(cat, [])

            if k_probs and p_probs:
                k_avg = sum(k_probs) / len(k_probs)
                p_avg = sum(p_probs) / len(p_probs)
                sentiment_deltas[cat] = k_avg - p_avg  # Positive = Kalshi more bullish
            elif k_probs:
                sentiment_deltas[cat] = sum(k_probs) / len(k_probs)
            elif p_probs:
                sentiment_deltas[cat] = -(sum(p_probs) / len(p_probs))

        return sentiment_deltas
