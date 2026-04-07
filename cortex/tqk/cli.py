#!/usr/bin/env python3
"""
Cortex TQK CLI - Tool Qualification Kit Generator

Generates complete Tool Qualification Kit documentation:
- TOR (Tool Operational Requirements)
- TVP (Tool Verification Plan)
- TVR (Tool Verification Report)
- SOUP Manifest

Usage:
    python -m cortex.tqk.cli --generate all
    python -m cortex.tqk.cli --generate tor --output tqk/
    python -m cortex.tqk.cli --generate soup --output tqk/soup.md
    python -m cortex.tqk.cli --run-tests
"""

import argparse
import sys
from pathlib import Path


def generate_tor(output_path: Path) -> None:
    """Generate Tool Operational Requirements"""
    from cortex.tqk.tor import ToolOperationalRequirements
    
    tor = ToolOperationalRequirements()
    content = tor.to_markdown()
    
    output_file = output_path / "TOR.md"
    output_file.write_text(content)
    print(f"Generated: {output_file}")


def generate_tvp(output_path: Path) -> None:
    """Generate Tool Verification Plan"""
    from cortex.tqk.tvp import ToolVerificationPlan
    
    tvp = ToolVerificationPlan()
    content = tvp.to_markdown()
    
    output_file = output_path / "TVP.md"
    output_file.write_text(content)
    print(f"Generated: {output_file}")


def generate_soup(output_path: Path) -> None:
    """Generate SOUP Manifest"""
    from cortex.tqk.soup import SOUPManagement
    
    soup = SOUPManagement()
    content = soup.to_markdown()
    
    output_file = output_path / "SOUP.md"
    output_file.write_text(content)
    print(f"Generated: {output_file}")


def generate_iso14971_annex(output_path: Path) -> None:
    """Generate ISO 14971 Risk Management Annex"""
    from cortex.tqk.soup import SOUPManagement
    
    soup = SOUPManagement()
    content = soup.generate_iso14971_annex()
    
    output_file = output_path / "ISO14971_Annex_C.md"
    output_file.write_text(content)
    print(f"Generated: {output_file}")


def run_tests(output_path: Path) -> None:
    """Run automated TVP tests"""
    from cortex.tqk.tvr import ToolVerificationReport, AutomatedTVRunner
    
    report = ToolVerificationReport()
    runner = AutomatedTVRunner(report)
    
    print("Running automated tests...")
    runner.run_all()
    
    # Generate report
    content = report.to_markdown()
    
    output_file = output_path / "TVR.md"
    output_file.write_text(content)
    print(f"Generated: {output_file}")
    
    # Print summary
    summary = report.get_summary()
    print(f"\nTest Summary:")
    print(f"  Total: {summary['total_tests']}")
    print(f"  Passed: {summary['passed']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Pass Rate: {summary['pass_rate']:.1f}%")


def generate_all(output_path: Path) -> None:
    """Generate complete TQK"""
    print("Generating complete Tool Qualification Kit...")
    print()
    
    generate_tor(output_path)
    generate_tvp(output_path)
    generate_soup(output_path)
    generate_iso14971_annex(output_path)
    
    print()
    print("TQK generation complete!")
    print(f"Files written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Cortex Tool Qualification Kit Generator"
    )
    
    parser.add_argument(
        "--generate",
        choices=["all", "tor", "tvp", "soup", "iso14971"],
        default="all",
        help="What to generate"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("TQK"),
        help="Output directory"
    )
    
    parser.add_argument(
        "--run-tests",
        action="store_true",
        help="Run automated verification tests"
    )
    
    args = parser.parse_args()
    
    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)
    
    if args.run_tests:
        run_tests(args.output)
        return
    
    if args.generate == "all":
        generate_all(args.output)
    elif args.generate == "tor":
        generate_tor(args.output)
    elif args.generate == "tvp":
        generate_tvp(args.output)
    elif args.generate == "soup":
        generate_soup(args.output)
    elif args.generate == "iso14971":
        generate_iso14971_annex(args.output)


if __name__ == "__main__":
    main()