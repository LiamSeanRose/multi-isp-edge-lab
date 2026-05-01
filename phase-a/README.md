# Phase A — Topology and base routing

A multi-ISP enterprise edge built on Containerlab + Arista cEOS. One customer
edge router (ce1) with eBGP sessions to three transit ISPs of different
characteristics (Premium Fiber, Standard Cable, LTE Backup), each connected
to a simulated public internet that originates 8.8.8.0/24, 1.1.1.0/24, and
192.0.2.0/24.

Phase A is intentionally policy-free: plain eBGP everywhere with ECMP across
all three uplinks. The point is to establish baseline reachability so Phase B
can introduce production-grade routing policy and the change can be observed.

## Topology

- ce1 (AS 65010) — customer edge, internal LAN gateway on VLAN 10 (10.10.10.0/24)
- isp_a (AS 65001) — Premium Fiber transit
- isp_b (AS 65002) — Standard Cable transit
- isp_c (AS 65003) — LTE Backup transit
- internet (AS 65000) — pretend public internet
- host1, host2 — Alpine Linux containers on the internal LAN

Inter-router links use 100.64.0.0/10 carrier-grade NAT space, /31 per link,
matching real ISP edge addressing conventions.

## Deploy

    cd ~/multi-isp-lab
    sudo containerlab deploy -t multi-isp.clab.yml

## Verify

    docker exec clab-multi-isp-host1 ping -c 3 8.8.8.8
    docker exec clab-multi-isp-host1 traceroute -n 8.8.8.8
    docker exec clab-multi-isp-ce1 Cli -c "show ip bgp summary"
    docker exec clab-multi-isp-ce1 Cli -c "show ip route bgp"

A successful traceroute will show three different ISP next-hops on hop 2,
demonstrating ECMP load-balancing across all three uplinks.

## Files

- multi-isp.clab.yml — Containerlab topology
- configs/ce1.cfg — customer edge router
- configs/isp_a.cfg, isp_b.cfg, isp_c.cfg — transit ISPs
- configs/internet.cfg — simulated public internet

## Built on

Hosted on the Ubuntu lab VM from the
[home-networking-lab](https://github.com/LiamSeanRose/home-networking-lab) project
(Proxmox VE + Terraform IaC).
