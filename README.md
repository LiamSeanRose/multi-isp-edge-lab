# Multi-ISP Edge Lab

Containerlab simulation of a typical enterprise edge with three upstream ISPs. Built to explore BGP routing policy, observability, and automated failover testing across a multi-ISP environment — the kind of network design real enterprises and government organizations operate every day.

## Status

**Complete** — all five phases shipped.

## Roadmap

- [x] **Phase A** — Topology and base routing (Containerlab + eBGP with ECMP)
- [x] **Phase B** — Routing policy (local-pref, AS-path prepending, communities, prefix-list filtering)
- [x] **Phase C** — Observability (Prometheus + Grafana + per-ISP synthetic probes)
- [x] **Phase D** — Automated failover testing (pyATS test suite with SLA-bounded convergence assertions)
- [x] **Phase E** — Cost analytics (per-ISP traffic accounting and optimization recommendations)

## Architecture
Internal LAN (10.10.10.0/24)
                          │
                   ┌──────▼──────┐
                   │     CE1     │  AS 65010
                   └──┬───┬───┬──┘
                      │   │   │
          ┌───────────┘   │   └───────────┐
          │               │               │
     ┌────▼────┐     ┌────▼────┐     ┌────▼────┐
     │  ISP_A  │     │  ISP_B  │     │  ISP_C  │
     │ Premium │     │Standard │     │ Backup  │
     │ AS65001 │     │ AS65002 │     │ AS65003 │
     └────┬────┘     └────┬────┘     └────┬────┘
          │               │               │
          └───────────────┼───────────────┘
                          │
                   ┌──────▼──────┐
                   │  Internet   │  AS 65000
                   │ (8.8.8.0/24,│
                   │  1.1.1.0/24,│
                   │ 192.0.2.0/24)│
                   └─────────────┘
## What each phase delivers

**Phase A — Baseline reachability.** A working multi-ISP topology with plain eBGP everywhere, ECMP across all three uplinks. Hosts can reach the simulated public internet via any of the three ISPs. Deliberately policy-free as a foundation for Phase B.

**Phase B — Production-grade routing policy.** Local-preference steers outbound traffic to the premium ISP. AS-path prepending steers inbound traffic the same way. BGP communities tag routes by ISP tier for downstream automation. Prefix-list filtering structurally prevents route leakage in both directions. Failover behavior demonstrated by deliberately shutting BGP sessions and watching traffic shift through the tiers automatically.

**Phase C — Observability.** A Blackbox Exporter probe inside the lab fabric sends ICMP probes through each ISP independently (using /32 path-forcing static routes on ce1). Prometheus scrapes the probe and tags each measurement with its ISP label. Grafana visualizes per-ISP latency and probe success in real time.

**Phase D — Automated failover testing.** A pyATS test suite that simulates ISP failures, asserts correct failover within SLA windows, and measures convergence times. Six tests covering primary failure, cascade failure, recovery, and the negative case (BGP-only shutdown does NOT break the data plane — a key lesson encoded as a permanent regression test).

**Phase E — Cost analytics.** Python pipeline that polls per-ISP byte counters, applies a per-GB pricing model, projects monthly costs, and recommends specific traffic that should be moved to cheaper ISPs. Translates network engineering decisions into the language management speaks.

## Built on

- **Containerlab** + Arista cEOS-Lab 4.36
- **Hosted on** a Proxmox-managed Ubuntu VM — see [home-networking-lab](https://github.com/LiamSeanRose/home-networking-lab) for the underlying infrastructure
- **Observability stack:** Prometheus + Grafana + Blackbox Exporter (Docker Compose)
- **Automation:** pyATS + Genie (reused from home-networking-lab's Phase 3 venv)

## Repository structure
.
├── phase-a/   topology + initial eBGP configs
├── phase-b/   configs with full routing policy
├── phase-c/   monitoring stack + probe configs + dashboard screenshots
├── phase-d/   pyATS testbed + test suite + captured test results
├── phase-e/   flow collector + cost analyzer + sample report
└── README.md

Each phase folder includes its own README with deployment instructions, verification commands, and lessons learned from building it.

## Key learnings worth highlighting

- ECMP load-balances per-flow (5-tuple hash), not per-packet, to preserve TCP ordering
- AS-path prepending too aggressively (3x+) inverts path preference at the upstream ISP and trips BGP loop prevention, causing the affected ISP to advertise nothing
- BGP neighbor shutdown breaks the control plane but not the data plane when static routes exist; failover testing must exercise interface shutdown
- cEOS containers are AlmaLinux 9; `dnf install` fails from inside the container, so traffic shaping with tc/netem requires host-side namespace work
- Prometheus relabel rules are the standard pattern for using Blackbox Exporter; required reading for anyone running synthetic probes at scale