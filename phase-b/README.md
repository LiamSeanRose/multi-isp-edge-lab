# Phase B — Routing policy

Production-grade BGP routing policy applied to the Phase A topology. The
network now expresses business intent (premium / standard / backup ISP tiers)
through declarative BGP attributes, with automatic failover and structural
guardrails against route leakage.

## Policy applied

### Outbound preference (local-pref)
Routes received from each ISP are tagged with local-preference at ingress:
- isp_a (Premium Fiber) → local-pref 200
- isp_b (Standard Cable) → local-pref 100
- isp_c (LTE Backup) → local-pref 50

Result: ce1 sends all traffic via isp_a unless it goes down, in which case
BGP automatically shifts to isp_b, then isp_c.

### Inbound preference (AS-path prepending)
ce1 prepends its own AS to advertisements going out to less-preferred ISPs:
- isp_a: no prepending (most attractive)
- isp_b: 1x prepend
- isp_c: 2x prepend

Result: the public internet sees isp_a as the shortest AS-path and prefers
returning traffic via isp_a. Symmetric routing achieved.

### Communities (route metadata)
Routes are tagged at ingress with a community identifying their source tier:
- 65010:100 — premium (from isp_a)
- 65010:200 — standard (from isp_b)
- 65010:300 — backup (from isp_c)

Communities are local convention but make BGP tables self-documenting and
enable downstream automation (filters, monitoring, accounting).

### Prefix-list filtering
- Outbound: ce1 will only advertise 10.10.10.0/24. Any other prefix that
  ends up in BGP is structurally blocked from being propagated upstream.
- Inbound: ce1 only accepts the three known public prefixes (8.8.8.0/24,
  1.1.1.0/24, 192.0.2.0/24) from each ISP. Hijack-style injections (e.g.
  default routes) are dropped on receipt.

## Failover demonstrated

Shutting BGP sessions in sequence (`neighbor X shutdown`) shifts traffic
through the tiers automatically:

    isp_a up                      → traffic via isp_a
    isp_a shut                    → traffic via isp_b
    isp_a shut, isp_b shut        → traffic via isp_c (LTE)
    no shutdown (restore)         → traffic returns to isp_a

Convergence is sub-second from BGP, plus a few seconds for FIB install.

## Verify

Outbound preference (only isp_a's next-hop should appear):

    docker exec clab-multi-isp-host1 traceroute -n 8.8.8.8

Inbound preference (internet should see three different AS-path lengths):

    docker exec clab-multi-isp-internet Cli -c "show ip bgp 10.10.10.0/24"

Communities (each route should show one of 65010:100/200/300):

    docker exec clab-multi-isp-ce1 Cli -c "show ip bgp 8.8.8.0/24"

Filter enforcement (PfxAdv to each ISP should be exactly 1):

    docker exec clab-multi-isp-ce1 Cli -c "show ip bgp summary"

## Lessons learned

1. AS-path prepending too aggressively (3x or more in this topology) inverts
   the path preference at the upstream ISP, causing BGP loop-prevention to
   suppress the advertisement entirely. Lesson: prefer 1-2x prepends; for
   stronger inbound steering use BGP communities advertised to the upstream.

2. cEOS will silently accept `neighbor X route-map NAME in/out` even when
   route-map NAME does not exist. Lesson: define route maps before applying
   them, and verify with `show route-map` after every change.

3. Adding a `match` clause to a route-map introduces an implicit deny for
   non-matching routes. This is the desired behavior for inbound filtering
   but a footgun if you add a match clause expecting the unmatched routes
   to pass through unchanged.
