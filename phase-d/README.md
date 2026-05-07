# Phase D — Automated failover testing

A pyATS test suite that simulates ISP failures, asserts correct failover
behavior, and measures convergence time. Catches regressions in routing
policy that would otherwise only surface during real outages.

## What it tests

Six tests covering the failover lifecycle:

1. **Baseline path** — verifies ce1 prefers isp_a (Phase B's local-pref 200)
2. **Baseline reachability** — host1 can reach the simulated public internet
3. **Primary failover** — shut isp_a's interface, assert traffic shifts to
   isp_b within SLA, assert reachability preserved
4. **Cascade failover** — shut isp_a + isp_b, assert traffic lands on
   isp_c (LTE backup), assert reachability preserved
5. **Recovery** — restore primary interface, assert traffic returns to
   isp_a automatically
6. **Negative test** — BGP-only shutdown does NOT break data plane,
   because /32 path-forcing static routes on ce1 override BGP state.
   This documents Phase C's lesson that failover testing must exercise
   the data plane (interface shutdown), not just the control plane.

## Measured convergence times

From the included `test-results.txt`:

- Failover (isp_a → isp_b): ~0.2s
- Cascade failover (→ isp_c): ~0.2s
- Recovery (back to isp_a): ~2.3s

These are direct-connect failures where the interface goes down
immediately, so BGP convergence is bounded by FIB update speed rather
than BGP timers. Recovery is slower because BGP must re-establish the
session from scratch.

## Run

```bash
cd ~/network-lab-phase3 && source venv/bin/activate
cd ~/multi-isp-lab/tests
pytest test_failover.py -v -s
```

## Project structure

- `testbed.yaml` — pyATS testbed describing all 5 routers
- `test_failover.py` — the test suite
- `test-results.txt` — captured passing run

## Lessons learned

1. **Test isolation requires aggressive cleanup.** The `restore_state`
   fixture with `autouse=True` runs after every test (including failed
   ones) to bring all interfaces and BGP neighbors back up. Without
   this, a test that crashes mid-way leaves the network in a broken
   state for the next test.

2. **cEOS SSH host keys regenerate on every redeploy.** Stale entries
   in `~/.ssh/known_hosts` cause silent connection failures. Clear them
   with `ssh-keygen -R <ip>` and re-populate with `ssh-keyscan` after
   each redeploy.

3. **The `admin` user has no default password on cEOS.** Must be set
   explicitly with `username admin secret admin` in cEOS config, then
   `write memory` to persist across the running config. Without this,
   pyATS gets `CredentialsExhaustedError`.

4. **session-scoped fixtures in pyATS are critical for performance.**
   Reconnecting to all 5 routers per test would add ~30s per test;
   `scope="session"` connects once and reuses the connection.

## Built on

- Phase A topology (Containerlab + 5 cEOS routers)
- Phase B routing policy (local-pref / AS-path prepending / communities /
  prefix-lists — what we're actually testing for correctness)
- Phase C path forcing (the /32 static routes the negative test asserts on)
- pyATS + Genie from `~/network-lab-phase3/venv/` (reused from the
  home-networking-lab project)
