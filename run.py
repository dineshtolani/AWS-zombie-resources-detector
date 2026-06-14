#!/usr/bin/env python3
"""
Project Acheron — AWS + Kubernetes Cloud Resource Intelligence Platform

Usage:
    python run.py                    # Full pipeline (single week)
    python run.py --weeks 4          # Simulate 4 weekly scans
    python run.py --weeks 4 --aws 100 --k8s 60   # Custom resource counts
    python run.py --reset            # Reset all state
    python run.py --version          # Show version
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Project Acheron — AWS + Kubernetes Resource Intelligence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                  Run single weekly scan
  python run.py --weeks 4        Simulate 4 weeks (shows recurrence)
  python run.py --reset          Clear all stored state
  python run.py --weeks 6 --aws 200 --k8s 100   Custom scale
        """,
    )
    parser.add_argument("--weeks", type=int, default=1, help="Number of weekly cycles to simulate (default: 1)")
    parser.add_argument("--aws", type=int, default=120, help="Number of AWS resources to generate (default: 120)")
    parser.add_argument("--k8s", type=int, default=80, help="Number of K8s resources to generate (default: 80)")
    parser.add_argument("--incidents", type=int, default=80, help="Number of log entries per week (default: 80)")
    parser.add_argument("--reset", action="store_true", help="Reset all stored state before running")
    parser.add_argument("--version", action="store_true", help="Show version and exit")

    args = parser.parse_args()

    if args.version:
        print("Project Acheron v1.0.0")
        sys.exit(0)

    from src.core.state_store import StateStore
    from src.core.orchestrator import AcheronOrchestrator

    if args.reset:
        store = StateStore()
        store.reset()
        print("State reset complete.")
        if args.weeks == 0:
            sys.exit(0)

    orch = AcheronOrchestrator()
    orch.simulate_weeks(
        num_weeks=args.weeks,
        cw_count=args.aws,
        prom_count=args.k8s,
        incident_count=args.incidents,
    )


if __name__ == "__main__":
    main()
