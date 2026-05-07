"""
analyze_costs.py — Read flows.csv and produce a cost report.

Aggregates bytes per ISP, applies a per-GB pricing model, computes
projected monthly costs, and prints a management-friendly report.

Run:
    python analyze_costs.py [path-to-flows.csv]
"""

import csv
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# Pricing model — $ per GB. Realistic-ish enterprise ISP contract shapes.
PRICING = {
    "isp_a": {"name": "Premium Fiber",  "cost_per_gb": 0.05},
    "isp_b": {"name": "Standard Cable", "cost_per_gb": 0.01},
    "isp_c": {"name": "LTE Backup",     "cost_per_gb": 0.50},
}

GB = 1024 ** 3


def load_flows(path):
    """Load flow records from CSV, return list of dicts."""
    records = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append({
                "timestamp": datetime.fromisoformat(row["timestamp"]),
                "isp": row["isp"],
                "in_bytes": int(row["in_bytes_delta"]),
                "out_bytes": int(row["out_bytes_delta"]),
            })
    return records


def aggregate_by_isp(records):
    """Sum total bytes per ISP across all sample windows."""
    totals = defaultdict(lambda: {"in": 0, "out": 0})
    for r in records:
        totals[r["isp"]]["in"] += r["in_bytes"]
        totals[r["isp"]]["out"] += r["out_bytes"]
    return totals


def compute_costs(totals, sample_duration_seconds):
    """Compute observed and projected-monthly costs per ISP."""
    SECONDS_PER_MONTH = 30 * 24 * 3600
    scale = SECONDS_PER_MONTH / sample_duration_seconds if sample_duration_seconds > 0 else 1

    report = []
    for isp, byte_totals in totals.items():
        if isp not in PRICING:
            continue
        total_bytes = byte_totals["in"] + byte_totals["out"]
        observed_gb = total_bytes / GB
        observed_cost = observed_gb * PRICING[isp]["cost_per_gb"]

        projected_gb = observed_gb * scale
        projected_cost = observed_cost * scale

        report.append({
            "isp": isp,
            "name": PRICING[isp]["name"],
            "rate": PRICING[isp]["cost_per_gb"],
            "observed_bytes": total_bytes,
            "observed_gb": observed_gb,
            "observed_cost": observed_cost,
            "projected_monthly_gb": projected_gb,
            "projected_monthly_cost": projected_cost,
        })
    return report


def print_report(report, records):
    """Pretty-print the cost report."""
    if not records:
        print("No flow data found.")
        return

    duration = (records[-1]["timestamp"] - records[0]["timestamp"]).total_seconds()
    total_observed = sum(r["observed_cost"] for r in report)
    total_projected = sum(r["projected_monthly_cost"] for r in report)

    print("=" * 70)
    print("  MULTI-ISP TRAFFIC COST REPORT")
    print("=" * 70)
    print(f"  Sample window: {records[0]['timestamp']} → {records[-1]['timestamp']}")
    print(f"  Duration: {duration:.0f} seconds ({len(records)} sample rows)")
    print()
    print(f"  {'ISP':<22} {'Rate':>10} {'Observed':>14} {'Projected/Month':>18}")
    print(f"  {'-'*22} {'-'*10} {'-'*14} {'-'*18}")

    for r in sorted(report, key=lambda x: -x["projected_monthly_cost"]):
        print(f"  {r['name']:<22} ${r['rate']:>5.2f}/GB  "
              f"{r['observed_gb']:>8.4f} GB   "
              f"{r['projected_monthly_gb']:>8.2f} GB / ${r['projected_monthly_cost']:>6.2f}")

    print(f"  {'-'*22} {'-'*10} {'-'*14} {'-'*18}")
    print(f"  {'TOTAL':<22} {'':>10} ${total_observed:>10.6f}   ${total_projected:>15.2f}")
    print("=" * 70)
    print()


def find_optimization_opportunities(report, records):
    """Identify traffic that could move to a cheaper ISP."""
    if not report:
        return

    # Sort ISPs by cost ascending — cheapest first
    cheapest = min(report, key=lambda r: r["rate"])

    print("OPTIMIZATION ANALYSIS")
    print("-" * 70)
    print(f"  Cheapest tier: {cheapest['name']} at ${cheapest['rate']:.2f}/GB")
    print()

    for r in report:
        if r["isp"] == cheapest["isp"]:
            continue
        if r["observed_bytes"] == 0:
            continue
        # If 50% of this ISP's traffic could move to the cheapest, what would we save?
        movable_fraction = 0.5
        movable_gb = r["projected_monthly_gb"] * movable_fraction
        current_cost_of_movable = movable_gb * r["rate"]
        new_cost_of_movable = movable_gb * cheapest["rate"]
        savings = current_cost_of_movable - new_cost_of_movable

        if savings < 0.01:
            continue

        print(f"  {r['name']} → {cheapest['name']}:")
        print(f"    If 50% of traffic ({movable_gb:.2f} GB/mo) moved to {cheapest['name']},")
        print(f"    monthly savings: ${savings:.2f}")
        print()

    print("  Recommendations:")
    print(f"    - Tag bulk/non-latency-sensitive traffic (backups, log shipping,")
    print(f"      software updates) with a DSCP marking and policy-route via")
    print(f"      {cheapest['name']}. Use BGP communities + policy-based routing")
    print(f"      to enforce.")
    print(f"    - Reserve {report[0]['name'] if report[0]['rate'] > cheapest['rate'] else cheapest['name']} for")
    print(f"      latency-sensitive flows: VoIP, video conferencing, real-time APIs.")
    print()


def main():
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("flows.csv")
    if not csv_path.exists():
        print(f"Error: {csv_path} not found. Run collect_flows.py first.")
        sys.exit(1)

    records = load_flows(csv_path)
    if not records:
        print("flows.csv is empty.")
        sys.exit(1)

    duration = (records[-1]["timestamp"] - records[0]["timestamp"]).total_seconds()
    totals = aggregate_by_isp(records)
    report = compute_costs(totals, duration)

    print_report(report, records)
    find_optimization_opportunities(report, records)


if __name__ == "__main__":
    main()
