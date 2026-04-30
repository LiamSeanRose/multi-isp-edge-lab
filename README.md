\# Multi-ISP Edge Lab



Containerlab simulation of a typical enterprise edge with three upstream ISPs. Built to explore BGP routing policy, observability, and automated failover testing across a multi-ISP environment — the kind of network design real enterprises and government organizations operate every day.



\## Goals



\- Model a realistic multi-ISP enterprise edge: 1 customer edge router (CE), 3 ISPs with distinct characteristics (premium / standard / backup), simulated public internet

\- Implement production-grade BGP routing policy: communities, local pref, AS-path prepending, prefix lists, route maps

\- Build observability across all three ISPs: synthetic probes, flow analysis, unified dashboards

\- Automate failover testing: pyATS suite that periodically simulates ISP failures and verifies traffic reroutes correctly within SLA

\- Demonstrate cost analysis: measure which traffic actually needs which ISP, output recommendations



\## Roadmap



\- \[ ] \*\*Phase A\*\* — Topology and base routing (Containerlab + eBGP)

\- \[ ] \*\*Phase B\*\* — Routing policy (communities, local pref, prepending)

\- \[ ] \*\*Phase C\*\* — Observability (Prometheus + Grafana + synthetic probes)

\- \[ ] \*\*Phase D\*\* — Automated failover testing (pyATS)

\- \[ ] \*\*Phase E\*\* — Cost analytics (NetFlow analysis)



\## Architecture

Internal LAN (10.10.10.0/24)

&#x20;             │

&#x20;       ┌─────▼─────┐

&#x20;       │    CE1    │  AS 65010

&#x20;       └──┬──┬──┬──┘

&#x20;          │  │  │

&#x20;   ┌──────┘  │  └──────┐

&#x20;   │         │         │

┌────▼───┐ ┌───▼───┐ ┌───▼───┐

│ ISP\_A  │ │ ISP\_B │ │ ISP\_C │

│ Premium│ │Standard│ │ Backup│

│ AS65001│ │ AS65002│ │AS65003│

└────┬───┘ └───┬───┘ └───┬───┘

│         │         │

└─────────┼─────────┘

│

┌─────▼─────┐

│  Internet │  AS 65000

│ (8.8.8.0, │

│  1.1.1.0, │

│  192.0.2.0)│

└───────────┘

\## Built on



\- Containerlab + Arista cEOS-Lab 4.36

\- Hosted on a Proxmox-managed Ubuntu VM (see \[home-networking-lab](https://github.com/LiamSeanRose/home-networking-lab) for the underlying infrastructure)



\## Status



Phase A in progress.

