"""
Data export utilities for saving analysis results.
"""

import json
import csv
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path


class DataExporter:
    """Export analysis results to various formats"""

    @staticmethod
    def to_json(data: Any, filepath: str, indent: int = 2) -> bool:
        """Export data to JSON file"""
        try:
            with open(filepath, "w") as f:
                if hasattr(data, "to_dict"):
                    json.dump(data.to_dict(), f, indent=indent)
                elif isinstance(data, list):
                    json.dump(
                        [
                            item.to_dict() if hasattr(item, "to_dict") else item
                            for item in data
                        ],
                        f,
                        indent=indent,
                    )
                else:
                    json.dump(data, f, indent=indent)
            return True
        except Exception as e:
            print(f"Error exporting to JSON: {e}")
            return False

    @staticmethod
    def to_csv(data: List[Dict], filepath: str) -> bool:
        """Export list of dictionaries to CSV"""
        if not data:
            print("No data to export")
            return False

        try:
            # Get fieldnames from first item
            fieldnames = list(data[0].keys())

            with open(filepath, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            return True
        except Exception as e:
            print(f"Error exporting to CSV: {e}")
            return False

    @staticmethod
    def generate_filename(prefix: str, extension: str) -> str:
        """Generate timestamped filename"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}.{extension}"

    @staticmethod
    def save_summary_report(
        sentiment_data: Dict,
        arbitrage_opportunities: List,
        volatility_rankings: List,
        output_dir: str = "output",
    ) -> str:
        """Generate a comprehensive summary report"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report = f"""
====================================================
PREDICTION MARKET SENTIMENT ANALYSIS REPORT
Generated: {timestamp}
====================================================

SUMMARY
-------
Total Categories Analyzed: {len(sentiment_data)}
Total Arbitrage Opportunities: {len(arbitrage_opportunities)}
Total Markets in Liquidity Rankings: {len(volatility_rankings)}

SENTIMENT BY CATEGORY
---------------------
"""
        for cat, sent in sorted(
            sentiment_data.items(), key=lambda x: x[1].sentiment_score, reverse=True
        ):
            report += f"\n{cat:15s}: Score {sent.sentiment_score:+.2f}, Avg {sent.avg_probability:.1%}, Vol {sent.volatility:.3f}"

        if arbitrage_opportunities:
            report += f"\n\nTOP ARBITRAGE OPPORTUNITIES\n--------------------------\n"
            for i, opp in enumerate(arbitrage_opportunities[:5], 1):
                report += f"\n{i}. {opp.platform_a} ↔ {opp.platform_b}\n"
                report += f"   Event: {opp.event_b[:60]}...\n"
                report += f"   Spread: {opp.spread:.3f} ({opp.spread_pct:.1f}%)\n"
                report += f"   Confidence: {opp.confidence:.1%}\n"

        if volatility_rankings:
            report += f"\n\nMOST LIQUID MARKETS\n-------------------\n"
            for i, r in enumerate(volatility_rankings[:10], 1):
                report += f"\n{i}. {r['platform']}: {r['title'][:50]}... (Score: {r['liquidity_score']:.1f})"

        report += "\n\n====================================================\n"

        # Save to file
        report_file = (
            output_path / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        with open(report_file, "w") as f:
            f.write(report)

        # Also save raw data as JSON
        data_file = (
            output_path / f"data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        export_data = {
            "timestamp": timestamp,
            "sentiment": {cat: s.to_dict() for cat, s in sentiment_data.items()},
            "arbitrage": [opp.to_dict() for opp in arbitrage_opportunities],
            "liquidity_rankings": volatility_rankings,
        }
        with open(data_file, "w") as f:
            json.dump(export_data, f, indent=2)

        return str(report_file)
