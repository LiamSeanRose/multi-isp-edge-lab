"""
collect_flows.py — Poll per-ISP interface counters from the customer edge.

Connects to ce1 every POLL_INTERVAL seconds, grabs `show interfaces counters`,
parses byte counts per ISP-facing interface, computes deltas between samples,
and writes results to flows.csv as time-series records.

Run:
    python collect_flows.py [DURATION_SECONDS]

Default duration: 300 seconds (5 minutes). Output: flows.csv in CWD.
"""

import csv
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from genie.testbed import load


POLL_INTERVAL = 10  # seconds between samples
DEFAULT_DURATION = 300

# Map ce1's interfaces to ISP names for human-friendly output
INTERFACE_TO_ISP = {
    "Et1": "isp_a",
    "Et2": "isp_b",
    "Et3": "isp_c",
}


def parse_counters(output):
    """Parse `show interfaces counters` Arista output into {ifname: (in_bytes, out_bytes)}.

    cEOS output has TWO tables — InOctets table first, then OutOctets table.
    We parse them independently and merge.
    """
    counters = {}
    # Match: "Et1   <number>  <number>  <number>  <number>"
    # The first number after the interface name is the byte count (InOctets or OutOctets)
    pattern = re.compile(r"^(Et\d+)\s+(\d+)\s+\d+\s+\d+\s+\d+", re.MULTILINE)

    # Split on the second header line that starts with "Port" + "OutOctets"
    parts = re.split(r"^Port\s+OutOctets", output, maxsplit=1, flags=re.MULTILINE)

    # First section: InOctets
    in_section = parts[0]
    for match in pattern.finditer(in_section):
        ifname = match.group(1)
        counters[ifname] = (int(match.group(2)), 0)

    # Second section: OutOctets (if present)
    if len(parts) > 1:
        out_section = parts[1]
        for match in pattern.finditer(out_section):
            ifname = match.group(1)
            in_bytes = counters.get(ifname, (0, 0))[0]
            counters[ifname] = (in_bytes, int(match.group(2)))

    return counters

def main():
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DURATION

    tb = load("../tests/testbed.yaml")
    ce1 = tb.devices["ce1"]
    ce1.connect(log_stdout=False, learn_hostname=True)

    output_path = Path("flows.csv")
    write_header = not output_path.exists()

    print(f"Collecting flow data every {POLL_INTERVAL}s for {duration}s...")
    print(f"Writing to: {output_path.absolute()}")

    previous = None
    start = time.time()

    with output_path.open("a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["timestamp", "isp", "in_bytes_delta", "out_bytes_delta"])

        while time.time() - start < duration:
            output = ce1.execute("show interfaces counters")
            current = parse_counters(output)
            timestamp = datetime.now(timezone.utc).isoformat()

            if previous is not None:
                for ifname, isp in INTERFACE_TO_ISP.items():
                    if ifname in current and ifname in previous:
                        in_delta = current[ifname][0] - previous[ifname][0]
                        out_delta = current[ifname][1] - previous[ifname][1]
                        writer.writerow([timestamp, isp, in_delta, out_delta])
                f.flush()
                print(f"[{timestamp}] sampled — "
                      + ", ".join(
                          f"{INTERFACE_TO_ISP[i]}={current[i][1] - previous[i][1]}B"
                          for i in INTERFACE_TO_ISP if i in current and i in previous))

            previous = current
            time.sleep(POLL_INTERVAL)

    ce1.disconnect()
    print(f"\nDone. Wrote samples to {output_path.absolute()}")


if __name__ == "__main__":
    main()
