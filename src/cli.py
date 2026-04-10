"""
Command-line interface for the prediction market sentiment analyzer.
Provides access to all analysis tools: arbitrage, sentiment, volatility.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from src.clients.kalshi_client import KalshiClient
from src.clients.polymarket_client import PolymarketClient
from src.analyzers.arbitrage import ArbitrageDetector
from src.analyzers.sentiment import SentimentAnalyzer
from src.analyzers.volatility import VolatilityAnalyzer
from src.analyzers.cross_asset import CrossAssetArbitrageDetector
from src.utils.exporter import DataExporter


console = Console()


@click.group()
@click.pass_context
def cli(ctx):
    """
    Prediction Market Sentiment Analyzer

    A tool for analyzing sentiment, detecting arbitrage opportunities,
    and calculating volatility metrics across Kalshi and Polymarket.

    All data is fetched from free public APIs - no authentication required.
    """
    ctx.ensure_object(dict)


@cli.command()
@click.option(
    "--min-spread", default=0.02, help="Minimum spread to consider (default: 0.02)"
)
@click.option(
    "--min-volume", default=100.0, help="Minimum combined volume (default: 100)"
)
@click.option(
    "--min-confidence", default=0.3, help="Minimum confidence score 0-1 (default: 0.3)"
)
@click.option(
    "--output",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def arbitrage(min_spread, min_volume, min_confidence, output):
    """Find arbitrage opportunities between Kalshi and Polymarket"""
    console.print("[bold cyan]Scanning for arbitrage opportunities...[/bold cyan]")

    detector = ArbitrageDetector()
    opportunities = detector.find_arbitrage_opportunities(
        min_spread=min_spread, min_volume=min_volume, min_confidence=min_confidence
    )

    if output == "json":
        result = [opp.to_dict() for opp in opportunities]
        print(json.dumps(result, indent=2))
    else:
        if not opportunities:
            console.print(
                "[yellow]No arbitrage opportunities found with current filters[/yellow]"
            )
            return

        table = Table(title=f"Found {len(opportunities)} Arbitrage Opportunities")
        table.add_column("Platforms", style="cyan")
        table.add_column("Kalshi Market", style="magenta")
        table.add_column("Polymarket Question", style="green")
        table.add_column("Price Spread", justify="right", style="yellow")
        table.add_column("Spread %", justify="right", style="yellow")
        table.add_column("Confidence", justify="right", style="blue")

        for opp in opportunities[:20]:  # Limit to top 20
            table.add_row(
                f"{opp.platform_a} ↔ {opp.platform_b}",
                opp.market_a[:30] + "..." if len(opp.market_a) > 30 else opp.market_a,
                opp.event_b[:40] + "..." if len(opp.event_b) > 40 else opp.event_b,
                f"{opp.spread:.3f}",
                f"{opp.spread_pct:.1f}%",
                f"{opp.confidence:.1%}",
            )

        console.print(table)

        # Summary stats
        avg_spread = sum(o.spread for o in opportunities) / len(opportunities)
        avg_conf = sum(o.confidence for o in opportunities) / len(opportunities)
        console.print(f"\n[bold]Summary:[/bold]")
        console.print(f"  Total opportunities: {len(opportunities)}")
        console.print(f"  Average spread: {avg_spread:.3f}")
        console.print(f"  Average confidence: {avg_conf:.1%}")


@cli.command()
@click.option(
    "--category",
    default=None,
    help="Filter by specific category (politics, crypto, sports, etc.)",
)
@click.option(
    "--output",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def sentiment(category, output):
    """Analyze sentiment across all prediction markets"""
    console.print("[bold cyan]Analyzing market sentiment...[/bold cyan]")

    analyzer = SentimentAnalyzer()
    sentiments = analyzer.analyze_sentiment_by_category()

    if category:
        sentiments = {
            k: v for k, v in sentiments.items() if k.lower() == category.lower()
        }

    if output == "json":
        result = {cat: s.to_dict() for cat, s in sentiments.items()}
        print(json.dumps(result, indent=2))
    else:
        table = Table(title="Market Sentiment by Category")
        table.add_column("Category", style="cyan")
        table.add_column("Markets", justify="right")
        table.add_column("Avg Prob", justify="right")
        table.add_column("Wtd Prob", justify="right")
        table.add_column("Bullish", justify="right", style="green")
        table.add_column("Bearish", justify="right", style="red")
        table.add_column("Neutral", justify="right")
        table.add_column("Volatility", justify="right")
        table.add_column("Score", justify="right")

        for cat, sent in sorted(
            sentiments.items(), key=lambda x: x[1].sentiment_score, reverse=True
        ):
            table.add_row(
                cat,
                str(sent.total_markets),
                f"{sent.avg_probability:.1%}",
                f"{sent.weighted_probability:.1%}",
                str(sent.bullish_count),
                str(sent.bearish_count),
                str(sent.neutral_count),
                f"{sent.volatility:.3f}",
                f"{sent.sentiment_score:+.2f}",
            )

        console.print(table)

        # Highlight most bullish and bearish
        if sentiments:
            most_bullish = max(sentiments.values(), key=lambda x: x.sentiment_score)
            most_bearish = min(sentiments.values(), key=lambda x: x.sentiment_score)
            console.print(
                f"\n[bold]Most Bullish:[/bold] {most_bullish.category} (score: {most_bullish.sentiment_score:+.2f})"
            )
            console.print(
                f"[bold]Most Bearish:[/bold] {most_bearish.category} (score: {most_bearish.sentiment_score:+.2f})"
            )


@cli.command()
@click.option("--top", default=10, help="Number of top categories to show")
def trends(top):
    """Show sentiment differences between Kalshi and Polymarket"""
    console.print(
        "[bold cyan]Calculating cross-platform sentiment trends...[/bold cyan]"
    )

    analyzer = SentimentAnalyzer()
    trends = analyzer.get_sentiment_trends()

    table = Table(title="Kalshi vs Polymarket Sentiment by Category")
    table.add_column("Category", style="cyan")
    table.add_column("Kalshi Avg", justify="right", style="green")
    table.add_column("Polymarket Avg", justify="right", style="red")
    table.add_column("Difference", justify="right")
    table.add_column("Direction", justify="center")

    for cat, data in sorted(
        trends.items(), key=lambda x: abs(x[1]["difference"]), reverse=True
    )[:top]:
        k_avg = data["kalshi_avg"] if data["kalshi_avg"] else 0
        p_avg = data["polymarket_avg"] if data["polymarket_avg"] else 0
        diff = data["difference"]
        direction = (
            "🔺 Kalshi" if diff > 0 else "🔻 Polymarket" if diff < 0 else "→ Equal"
        )
        color = "green" if diff > 0 else "red" if diff < 0 else "white"

        table.add_row(
            cat,
            f"{k_avg:.1%}" if k_avg else "N/A",
            f"{p_avg:.1%}" if p_avg else "N/A",
            f"[{color}]{diff:+.1%}[/{color}]",
            direction,
        )

    console.print(table)


@cli.command()
@click.option("--top", default=20, help="Number of markets to show")
@click.option(
    "--platform",
    type=click.Choice(["kalshi", "polymarket", "both"]),
    default="both",
    help="Filter by platform",
)
def liquidity(top, platform):
    """Show markets ranked by liquidity"""
    console.print("[bold cyan]Calculating liquidity rankings...[/bold cyan]")

    analyzer = VolatilityAnalyzer()
    rankings = analyzer.get_liquidity_rankings(top_n=top * 2)  # Get more to filter

    if platform != "both":
        rankings = [r for r in rankings if r["platform"] == platform]

    rankings = rankings[:top]

    table = Table(title=f"Top {len(rankings)} Markets by Liquidity")
    table.add_column("Rank", justify="right", style="cyan")
    table.add_column("Platform", style="magenta")
    table.add_column("Market", style="green")
    table.add_column("Liquidity Score", justify="right", style="yellow")
    table.add_column("Category", style="blue")

    for i, r in enumerate(rankings, 1):
        table.add_row(
            str(i),
            r["platform"],
            r["title"][:50] + "..." if len(r["title"]) > 50 else r["title"],
            f"{r['liquidity_score']:.1f}",
            r["category"][:30] if r["category"] else "",
        )

    console.print(table)


@cli.command()
@click.option(
    "--platform",
    type=click.Choice(["kalshi", "polymarket", "both"]),
    default="both",
    help="Platform to analyze",
)
def markets(platform):
    """List all available markets with current prices"""
    console.print("[bold cyan]Fetching market list...[/bold cyan]")

    if platform in ["kalshi", "both"]:
        try:
            k_client = KalshiClient()
            k_markets = k_client.get_markets(limit=50)

            table = Table(title=f"Kalshi Markets ({len(k_markets)} fetched)")
            table.add_column("Ticker", style="cyan")
            table.add_column("Title", style="green")
            table.add_column("Yes Bid", justify="right", style="yellow")
            table.add_column("Yes Ask", justify="right", style="yellow")
            table.add_column("Spread", justify="right")
            table.add_column("Volume", justify="right")
            table.add_column("Category", style="blue")

            for m in k_markets[:20]:
                table.add_row(
                    m.ticker,
                    m.title[:40] + "..." if len(m.title) > 40 else m.title,
                    f"${m.yes_bid_dollars:.2f}",
                    f"${m.yes_ask_dollars:.2f}",
                    f"${m.spread:.3f}",
                    f"{m.volume:,.0f}",
                    m.category or "",
                )

            console.print(table)
        except Exception as e:
            console.print(f"[red]Error fetching Kalshi markets: {e}[/red]")

    if platform in ["polymarket", "both"]:
        try:
            p_client = PolymarketClient()
            p_markets = p_client.get_markets(limit=50)

            table = Table(title=f"Polymarket Markets ({len(p_markets)} fetched)")
            table.add_column("Condition ID", style="cyan")
            table.add_column("Question", style="green")
            table.add_column("Yes Price", justify="right", style="yellow")
            table.add_column("Tokens", justify="right")
            table.add_column("Tags", style="blue")

            for m in p_markets[:20]:
                yes_price = next(
                    (t.price for t in m.tokens if t.outcome.lower() in ["yes", "true"]),
                    0,
                )
                table.add_row(
                    m.condition_id[:20] + "..."
                    if len(m.condition_id) > 20
                    else m.condition_id,
                    m.question[:40] + "..." if len(m.question) > 40 else m.question,
                    f"${yes_price:.2f}",
                    f"{len(m.tokens)}",
                    ", ".join(m.tags[:2]),
                )

            console.print(table)
        except Exception as e:
            console.print(f"[red]Error fetching Polymarket markets: {e}[/red]")


@cli.command()
def summary():
    """Print a summary of all market data and opportunities"""
    console.print("[bold cyan]Generating comprehensive summary...[/bold cyan]\n")

    # Fetch counts
    try:
        k_client = KalshiClient()
        k_markets = k_client.get_markets(limit=1000)
        console.print(f"[green]✓[/green] Kalshi: {len(k_markets)} active markets")
    except Exception as e:
        console.print(f"[red]✗[/red] Kalshi fetch failed: {e}")
        k_markets = []

    try:
        p_client = PolymarketClient()
        p_markets = p_client.get_markets(limit=1000)
        console.print(f"[green]✓[/green] Polymarket: {len(p_markets)} active markets")
    except Exception as e:
        console.print(f"[red]✗[/red] Polymarket fetch failed: {e}")
        p_markets = []

    # Sentiment analysis
    try:
        analyzer = SentimentAnalyzer()
        sentiments = analyzer.analyze_sentiment_by_category()

        console.print(f"\n[bold]Sentiment Overview:[/bold]")
        for cat, sent in sorted(
            sentiments.items(), key=lambda x: x[1].sentiment_score, reverse=True
        )[:5]:
            console.print(
                f"  {cat:15s}: {sent.sentiment_score:+.2f} (bullish: {sent.bullish_count}, bearish: {sent.bearish_count})"
            )
    except Exception as e:
        console.print(f"[red]Sentiment analysis failed: {e}[/red]")

    # Arbitrage scan
    try:
        detector = ArbitrageDetector()
        opportunities = detector.find_arbitrage_opportunities(
            min_spread=0.01, min_volume=50
        )
        console.print(
            f"\n[bold]Arbitrage Scan:[/bold] Found {len(opportunities)} opportunities (spread > 1%)"
        )
        if opportunities:
            console.print(
                f"  Best opportunity: {opportunities[0].spread:.1%} spread on {opportunities[0].event_b[:50]}"
            )
    except Exception as e:
        console.print(f"[red]Arbitrage detection failed: {e}[/red]")

    # Liquidity rankings
    try:
        vol_analyzer = VolatilityAnalyzer()
        rankings = vol_analyzer.get_liquidity_rankings(top_n=5)
        console.print(f"\n[bold]Most Liquid Markets:[/bold]")
        for i, r in enumerate(rankings, 1):
            console.print(
                f"  {i}. {r['platform']}: {r['title'][:40]}... (score: {r['liquidity_score']:.1f})"
            )
    except Exception as e:
        console.print(f"[red]Liquidity analysis failed: {e}[/red]")


@cli.command()
@click.option("--output-dir", default="output", help="Directory to save exports")
@click.option(
    "--format",
    type=click.Choice(["json", "csv", "both"]),
    default="json",
    help="Export format",
)
def export(output_dir, format):
    """Export all analysis results to files"""
    console.print("[bold cyan]Exporting analysis results...[/bold cyan]")

    exporter = DataExporter()
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Run all analyses
    try:
        # Sentiment data
        analyzer = SentimentAnalyzer()
        sentiments = analyzer.analyze_sentiment_by_category()
        sentiment_dict = {cat: s.to_dict() for cat, s in sentiments.items()}

        if format in ["json", "both"]:
            sentiment_file = output_path / f"sentiment_{timestamp}.json"
            with open(sentiment_file, "w") as f:
                json.dump(sentiment_dict, f, indent=2)
            console.print(f"[green]✓[/green] Sentiment data saved to {sentiment_file}")

        # Arbitrage opportunities
        detector = ArbitrageDetector()
        opportunities = detector.find_arbitrage_opportunities()
        opp_dicts = [opp.to_dict() for opp in opportunities]

        if format in ["json", "both"]:
            arb_file = output_path / f"arbitrage_{timestamp}.json"
            with open(arb_file, "w") as f:
                json.dump(opp_dicts, f, indent=2)
            console.print(f"[green]✓[/green] Arbitrage data saved to {arb_file}")

        if format == "csv":
            arb_csv = output_path / f"arbitrage_{timestamp}.csv"
            if DataExporter.to_csv(opp_dicts, str(arb_csv)):
                console.print(f"[green]✓[/green] Arbitrage CSV saved to {arb_csv}")

        # Liquidity rankings
        vol_analyzer = VolatilityAnalyzer()
        rankings = vol_analyzer.get_liquidity_rankings(top_n=100)

        if format in ["json", "both"]:
            liq_file = output_path / f"liquidity_{timestamp}.json"
            with open(liq_file, "w") as f:
                json.dump(rankings, f, indent=2)
            console.print(f"[green]✓[/green] Liquidity data saved to {liq_file}")

        if format == "csv":
            liq_csv = output_path / f"liquidity_{timestamp}.csv"
            if DataExporter.to_csv(rankings, str(liq_csv)):
                console.print(f"[green]✓[/green] Liquidity CSV saved to {liq_csv}")

        # Generate comprehensive report
        report_file = exporter.save_summary_report(
            sentiment_data=sentiments,
            arbitrage_opportunities=opportunities,
            volatility_rankings=rankings[:20],
            output_dir=output_dir,
        )
        console.print(f"[green]✓[/green] Summary report saved to {report_file}")

    except Exception as e:
        console.print(f"[red]Export failed: {e}[/red]")


@cli.command()
@click.option("--output-dir", default="output", help="Directory to save report")
def report(output_dir):
    """Generate a comprehensive analysis report"""
    console.print("[bold cyan]Generating comprehensive report...[/bold cyan]")

    try:
        analyzer = SentimentAnalyzer()
        sentiments = analyzer.analyze_sentiment_by_category()

        detector = ArbitrageDetector()
        opportunities = detector.find_arbitrage_opportunities()

        vol_analyzer = VolatilityAnalyzer()
        rankings = vol_analyzer.get_liquidity_rankings(top_n=50)

        exporter = DataExporter()
        report_file = exporter.save_summary_report(
            sentiment_data=sentiments,
            arbitrage_opportunities=opportunities,
            volatility_rankings=rankings[:20],
            output_dir=output_dir,
        )

        console.print(f"[green]✓[/green] Report generated: {report_file}")

        # Also print to console
        with open(report_file, "r") as f:
            console.print(Panel.fit(f.read(), title="Report Preview"))

    except Exception as e:
        console.print(f"[red]Report generation failed: {e}[/red]")


@cli.command()
@click.option(
    "--min-discrepancy",
    default=0.15,
    help="Minimum probability discrepancy (default: 0.15 = 15%)",
)
@click.option(
    "--platforms",
    type=click.Choice(["kalshi", "polymarket", "both"]),
    default="polymarket",
    help="Which prediction market platforms to scan",
)
@click.option(
    "--assets",
    default="BTC-USD,SPY,AAPL,TSLA,NVDA",
    help="Comma-separated list of asset tickers to analyze",
)
@click.option(
    "--output",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def cross_arbitrage(min_discrepancy, platforms, assets, output):
    """Find arbitrage between prediction markets and asset prices"""
    console.print("[bold cyan]Scanning for cross-asset arbitrage...[/bold cyan]")
    console.print(f"Assets: {assets}")
    console.print(f"Platforms: {platforms}")
    console.print(f"Minimum discrepancy: {min_discrepancy:.1%}")

    detector = CrossAssetArbitrageDetector()
    asset_list = [a.strip() for a in assets.split(",") if a.strip()]

    console.print("\n[yellow]Fetching asset data (yfinance)...[/yellow]")
    console.print("[dim]This may take a moment for multiple assets[/dim]\n")

    opportunities = detector.find_cross_asset_arbitrage(
        min_discrepancy=min_discrepancy,
        platforms=platforms if platforms != "both" else ["kalshi", "polymarket"],
    )

    # Also get sentiment by asset
    sentiment = detector.get_asset_vs_prediction_sentiment(assets=asset_list)

    if output == "json":
        result = {
            "opportunities": [opp.to_dict() for opp in opportunities],
            "asset_sentiment": sentiment,
        }
        print(json.dumps(result, indent=2, default=str))
    else:
        # Show asset sentiment summary
        if sentiment:
            table = Table(title="Asset Sentiment Summary")
            table.add_column("Asset", style="cyan")
            table.add_column("Price", justify="right")
            table.add_column("Vol", justify="right")
            table.add_column("Best Strike", style="yellow")
            table.add_column("Pred Prob", justify="right")
            table.add_column("Calc Prob", justify="right")
            table.add_column("Discrepancy", justify="right")

            for asset, data in sorted(sentiment.items()):
                opp = data.get("best_opportunity")
                if opp:
                    table.add_row(
                        asset,
                        f"${data['current_price']:,.2f}",
                        f"{data['volatility']:.1%}",
                        f"${opp['strike']:,.0f} {opp['direction']}",
                        f"{opp['prediction_probability']:.1%}",
                        f"{opp['calculated_probability']:.1%}",
                        f"[green]{opp['discrepancy']:.1%}[/green]",
                    )
                else:
                    table.add_row(
                        asset,
                        f"${data['current_price']:.2f}",
                        f"{data['volatility']:.1%}",
                        "N/A",
                        "N/A",
                        "N/A",
                        "N/A",
                    )
            console.print(table)

        # Show opportunities
        if opportunities:
            console.print(
                f"\n[bold]Found {len(opportunities)} cross-asset opportunities[/bold]"
            )
            table = Table(title="Top Opportunities")
            table.add_column("Platform", style="magenta")
            table.add_column("Market", style="cyan")
            table.add_column("Question", style="green")
            table.add_column("Asset/Strike", style="yellow")
            table.add_column("Pred Prob", justify="right")
            table.add_column("Calc Prob", justify="right")
            table.add_column("Disc", justify="right")
            table.add_column("Conf", justify="right")

            for opp in opportunities[:15]:
                asset_strike = f"{opp.asset} ${opp.strike:,.0f} {opp.direction}"
                table.add_row(
                    opp.platform,
                    opp.market_id[:15] + "..."
                    if len(opp.market_id) > 15
                    else opp.market_id,
                    opp.question[:50] + "..."
                    if len(opp.question) > 50
                    else opp.question,
                    asset_strike,
                    f"{opp.prediction_probability:.1%}",
                    f"{opp.calculated_probability:.1%}",
                    f"[green]{opp.discrepancy:.1%}[/green]",
                    f"{opp.confidence:.1%}",
                )
            console.print(table)
        else:
            console.print(
                "[yellow]No cross-asset arbitrage opportunities found[/yellow]"
            )
            console.print("[dim]Possible reasons:[/dim]")
            console.print(
                "  - Prediction markets may be efficiently priced relative to assets"
            )
            console.print("  - Asset volatility assumptions may need adjustment")
            console.print("  - Markets may not have clear price targets or expiries")


if __name__ == "__main__":
    cli()
