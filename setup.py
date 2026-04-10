#!/usr/bin/env python3
"""
Setup script for the Prediction Market Sentiment Analyzer.
Installs dependencies and performs initial setup.
"""

import subprocess
import sys
from pathlib import Path


def install_requirements():
    """Install Python dependencies"""
    req_file = Path(__file__).parent / "requirements.txt"
    if not req_file.exists():
        print("ERROR: requirements.txt not found")
        return False

    print("Installing dependencies...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(req_file)]
        )
        print("✓ Dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Error installing dependencies: {e}")
        return False


def main():
    print("=" * 60)
    print("Prediction Market Sentiment Analyzer - Setup")
    print("=" * 60)
    print()

    print("This will install the required Python packages.")
    print("Packages: requests, py-clob-client, pandas, numpy, click, rich, etc.")
    print()

    response = input("Proceed with installation? (y/N): ").strip().lower()
    if response not in ["y", "yes"]:
        print("Setup cancelled")
        return

    if install_requirements():
        print()
        print("Setup complete!")
        print()
        print("To use the tool:")
        print("  python -m src.cli --help")
        print("  # or")
        print("  python src/cli.py arbitrage")
        print("  python src/cli.py sentiment")
        print()
    else:
        print("Setup failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
