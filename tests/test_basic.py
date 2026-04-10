"""
Tests for the Prediction Market Sentiment Analyzer.
Run with: python -m pytest tests/ -v
"""

import pytest
from src.clients.kalshi_client import KalshiClient, KalshiMarket
from src.clients.polymarket_client import PolymarketClient, PolymarketMarket
from src.analyzers.arbitrage import ArbitrageDetector
from src.analyzers.sentiment import SentimentAnalyzer
from src.analyzers.volatility import VolatilityAnalyzer


class TestKalshiClient:
    """Tests for Kalshi API client"""

    def test_get_markets(self):
        """Test fetching markets from Kalshi"""
        client = KalshiClient()
        markets = client.get_markets(limit=10)
        assert isinstance(markets, list)
        if markets:
            assert all(isinstance(m, KalshiMarket) for m in markets)
            assert all(m.ticker for m in markets)

    def test_market_data_structure(self):
        """Test market data has required fields"""
        client = KalshiClient()
        markets = client.get_markets(limit=5)
        if markets:
            m = markets[0]
            assert hasattr(m, "ticker")
            assert hasattr(m, "title")
            assert hasattr(m, "yes_bid_dollars")
            assert hasattr(m, "no_bid_dollars")
            assert hasattr(m, "implied_probability")


class TestPolymarketClient:
    """Tests for Polymarket API client"""

    def test_get_markets(self):
        """Test fetching markets from Polymarket"""
        client = PolymarketClient()
        markets = client.get_markets(limit=10)
        assert isinstance(markets, list)
        if markets:
            assert all(isinstance(m, PolymarketMarket) for m in markets)
            assert all(m.condition_id for m in markets)

    def test_market_tokens(self):
        """Test Polymarket markets have tokens"""
        client = PolymarketClient()
        markets = client.get_markets(limit=5)
        if markets:
            m = markets[0]
            assert isinstance(m.tokens, list)
            assert len(m.tokens) >= 2  # At least 2 outcomes


class TestArbitrageDetector:
    """Tests for arbitrage detection"""

    def test_detector_initialization(self):
        """Test detector can be initialized"""
        detector = ArbitrageDetector()
        assert detector is not None

    def test_find_opportunities(self):
        """Test finding arbitrage opportunities"""
        detector = ArbitrageDetector()
        opportunities = detector.find_arbitrage_opportunities(
            min_spread=0.01, min_volume=10, min_confidence=0.1
        )
        assert isinstance(opportunities, list)
        if opportunities:
            assert all("spread" in opp.to_dict() for opp in opportunities)
            assert all(opp.confidence >= 0.1 for opp in opportunities)

    def test_market_matching(self):
        """Test market matching algorithm"""
        detector = ArbitrageDetector()
        kalshi_markets = detector.kalshi_client.get_markets(limit=10)
        polymarket_markets = detector.polymarket_client.get_markets(limit=20)
        matches = detector.match_markets(kalshi_markets, polymarket_markets)
        assert isinstance(matches, list)
        if matches:
            assert all(m.similarity_score > 0 for m in matches)


class TestSentimentAnalyzer:
    """Tests for sentiment analysis"""

    def test_analyzer_initialization(self):
        """Test analyzer can be initialized"""
        analyzer = SentimentAnalyzer()
        assert analyzer is not None

    def test_analyze_sentiment(self):
        """Test sentiment analysis by category"""
        analyzer = SentimentAnalyzer()
        sentiments = analyzer.analyze_sentiment_by_category(limit=50)
        assert isinstance(sentiments, dict)
        if sentiments:
            # Check that sentiment objects have required attributes
            for cat, sent in sentiments.items():
                assert hasattr(sent, "avg_probability")
                assert hasattr(sent, "sentiment_score")
                assert 0 <= sent.avg_probability <= 1

    def test_sentiment_trends(self):
        """Test cross-platform sentiment trends"""
        analyzer = SentimentAnalyzer()
        trends = analyzer.get_sentiment_trends()
        assert isinstance(trends, dict)
        for cat, data in trends.items():
            assert "kalshi_avg" in data
            assert "polymarket_avg" in data
            assert "difference" in data


class TestVolatilityAnalyzer:
    """Tests for volatility analysis"""

    def test_analyzer_initialization(self):
        """Test analyzer can be initialized"""
        analyzer = VolatilityAnalyzer()
        assert analyzer is not None

    def test_liquidity_rankings(self):
        """Test getting liquidity rankings"""
        analyzer = VolatilityAnalyzer()
        rankings = analyzer.get_liquidity_rankings(top_n=5)
        assert isinstance(rankings, list)
        if rankings:
            assert all("liquidity_score" in r for r in rankings)
            assert all(0 <= r["liquidity_score"] <= 100 for r in rankings)

    def test_liquidity_score_calculation(self):
        """Test liquidity score calculation"""
        analyzer = VolatilityAnalyzer()
        # Test with sample orderbook
        orderbook = {
            "bids": [{"price": "0.55", "size": "1000"}],
            "asks": [{"price": "0.56", "size": "800"}],
        }
        score = analyzer.calculate_liquidity_score(orderbook)
        assert isinstance(score, float)
        assert 0 <= score <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
