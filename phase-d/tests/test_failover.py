"""
test_failover.py — Automated failover tests for the multi-ISP edge.

Verifies that the BGP routing policy from Phase B produces correct failover
behavior under simulated ISP failures, and measures convergence time.

Run with:
    pytest test_failover.py -v
"""

import re
import time
import pytest
from genie.testbed import load


# --- Fixtures ---

@pytest.fixture(scope="session")
def fabric():
    """Connect to all devices once per test session."""
    tb = load("testbed.yaml")
    for name, device in tb.devices.items():
        device.connect(log_stdout=False, learn_hostname=True)
    yield tb
    for device in tb.devices.values():
        try:
            device.disconnect()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def restore_state(fabric):
    """After every test, ensure all ce1 interfaces and BGP neighbors are up.
    Runs even if a test fails — guarantees test isolation.
    """
    yield  # test runs here
    ce1 = fabric.devices["ce1"]
    ce1.execute("enable")
    ce1.configure([
        "interface Ethernet1",
        "no shutdown",
        "interface Ethernet2",
        "no shutdown",
        "interface Ethernet3",
        "no shutdown",
        "router bgp 65010",
        "no neighbor 100.64.1.1 shutdown",
        "no neighbor 100.64.2.1 shutdown",
        "no neighbor 100.64.3.1 shutdown",
    ])
    time.sleep(5)  # let BGP reconverge before next test


# --- Helpers ---

def get_active_path(fabric, target="8.8.8.0/24"):
    """Return the next-hop IP currently used by ce1 to reach `target`.
    
    Parses `show ip route <prefix>` and extracts the via-IP.
    Returns None if no route exists.
    """
    ce1 = fabric.devices["ce1"]
    output = ce1.execute(f"show ip route {target}")
    match = re.search(r"via (\d+\.\d+\.\d+\.\d+)", output)
    return match.group(1) if match else None


def ping_from_host(fabric, target_ip, count=3):
    """Run a ping from host1 (a Docker container, not a pyATS device) and
    return True if at least one packet was received.
    """
    import subprocess
    result = subprocess.run(
        ["docker", "exec", "clab-multi-isp-host1",
         "ping", "-c", str(count), "-W", "2", target_ip],
        capture_output=True, text=True, timeout=15,
    )
    # Look for at least one successful reply
    return "bytes from" in result.stdout


def wait_for_path_change(fabric, expected_next_hop, timeout=30, target="8.8.8.0/24"):
    """Poll ce1's routing table until the active path becomes `expected_next_hop`.
    
    Returns the elapsed time in seconds, or raises TimeoutError if the path
    doesn't change within `timeout` seconds.
    """
    start = time.time()
    while time.time() - start < timeout:
        current = get_active_path(fabric, target)
        if current == expected_next_hop:
            return time.time() - start
        time.sleep(0.5)
    raise TimeoutError(
        f"Path to {target} did not become via {expected_next_hop} within {timeout}s "
        f"(current: {current})"
    )


# --- Tests ---

def test_baseline_path_is_isp_a(fabric):
    """Baseline: With all ISPs healthy, ce1 prefers isp_a (local-pref 200)."""
    next_hop = get_active_path(fabric)
    assert next_hop == "100.64.1.1", (
        f"Expected baseline path via isp_a (100.64.1.1), got {next_hop}"
    )


def test_baseline_reachability(fabric):
    """Baseline: host1 can reach the simulated public internet."""
    assert ping_from_host(fabric, "8.8.8.8"), "host1 cannot reach 8.8.8.8"


def test_failover_isp_a_to_isp_b(fabric):
    """Shut isp_a's interface — traffic should fail over to isp_b within SLA."""
    ce1 = fabric.devices["ce1"]
    SLA_SECONDS = 30

    # Sanity: confirm we start on isp_a
    assert get_active_path(fabric) == "100.64.1.1"

    # Break the path
    ce1.configure(["interface Ethernet1", "shutdown"])

    # Wait for ce1 to switch to isp_b
    elapsed = wait_for_path_change(fabric, "100.64.2.1", timeout=SLA_SECONDS)
    print(f"\n  → Failover to isp_b took {elapsed:.2f}s")

    # Verify reachability is preserved
    assert ping_from_host(fabric, "8.8.8.8"), (
        "host1 lost reachability after isp_a interface shutdown"
    )


def test_cascade_failover_to_isp_c(fabric):
    """Shut isp_a AND isp_b — traffic should land on isp_c (LTE backup)."""
    ce1 = fabric.devices["ce1"]
    SLA_SECONDS = 45

    ce1.configure([
        "interface Ethernet1", "shutdown",
        "interface Ethernet2", "shutdown",
    ])

    elapsed = wait_for_path_change(fabric, "100.64.3.1", timeout=SLA_SECONDS)
    print(f"\n  → Cascade failover to isp_c took {elapsed:.2f}s")

    assert ping_from_host(fabric, "8.8.8.8"), (
        "host1 lost reachability after isp_a + isp_b interface shutdown"
    )


def test_recovery_returns_to_isp_a(fabric):
    """After interface restoration, traffic should return to the preferred path."""
    ce1 = fabric.devices["ce1"]

    # Break primary
    ce1.configure(["interface Ethernet1", "shutdown"])
    wait_for_path_change(fabric, "100.64.2.1", timeout=30)

    # Restore primary
    ce1.configure(["interface Ethernet1", "no shutdown"])

    # Path should return to isp_a once BGP reconverges
    elapsed = wait_for_path_change(fabric, "100.64.1.1", timeout=30)
    print(f"\n  → Recovery to isp_a took {elapsed:.2f}s")


def test_bgp_only_shutdown_does_not_break_data_plane(fabric):
    """Negative test: BGP shutdown alone should NOT break reachability,
    because the /32 path-forcing static routes on ce1 override BGP state.
    
    This documents the lesson from Phase C — failover testing must
    exercise the data plane (interface shutdown), not just the control
    plane (BGP shutdown).
    """
    ce1 = fabric.devices["ce1"]

    ce1.configure([
        "router bgp 65010",
        "neighbor 100.64.1.1 shutdown",
    ])
    time.sleep(3)  # let BGP register the shutdown

    # The 8.8.8.8 ping (forced via isp_a by /32 static route) should STILL succeed
    # because the interface is up and the static route doesn't depend on BGP
    assert ping_from_host(fabric, "8.8.8.8"), (
        "Expected reachability to survive BGP-only shutdown (because of /32 "
        "static routes), but ping failed. Has the static-route configuration changed?"
    )
