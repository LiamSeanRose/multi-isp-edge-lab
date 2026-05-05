# Phase C — Observability

Synthetic probe pipeline showing per-ISP latency and reachability in real
time. Built on Prometheus + Grafana + Blackbox Exporter, with per-ISP path
forcing on the customer edge so a single probe host can measure all three
upstreams independently.

## Architecture

A `probe` container running prom/blackbox-exporter sits on the internal LAN
alongside host1. ICMP probes are sent every 15s to three target IPs:

  | Target      | Forced via | Measures     |
  |-------------|------------|--------------|
  | 8.8.8.8     | isp_a      | Premium Fiber|
  | 1.1.1.1     | isp_b      | Standard Cable|
  | 192.0.2.1   | isp_c      | LTE Backup   |

Path forcing is implemented as /32 static routes on ce1 that override the
BGP-installed /24 routes. Same destinations, different next-hops, producing
three independent measurement streams.

Prometheus scrapes the probe container at 172.30.30.115:9115 and tags each
probe with an `isp` label via relabel rules. Grafana queries Prometheus to
visualize the metrics.

## Stack

- prometheus + grafana run via Docker Compose on the lab VM
- blackbox-exporter runs as a node inside the Containerlab fabric
- /32 path-forcing routes on ce1 (in ce1.cfg)
- ISP impairments via tc/netem (deferred — see Lessons Learned)

## Bring it up

    cd ~/multi-isp-monitoring && docker compose up -d
    cd ~/multi-isp-lab && sudo containerlab deploy -t multi-isp.clab.yml

Grafana at http://192.168.1.80:3000 (admin/admin)

## Verify

    docker exec clab-multi-isp-probe traceroute -n 8.8.8.8   # via isp_a
    docker exec clab-multi-isp-probe traceroute -n 1.1.1.1   # via isp_b
    docker exec clab-multi-isp-probe traceroute -n 192.0.2.1 # via isp_c

Prometheus targets: http://192.168.1.80:9090/targets — five UP targets,
including three blackbox probes labeled by isp.

## Failover demo

Shutting an ISP's BGP session causes Blackbox probes through that ISP to
fail. The probe_success metric drops to 0 for the affected isp label,
visible in Grafana within ~30 seconds:

    docker exec clab-multi-isp-ce1 Cli -c "enable
    configure
    router bgp 65010
    neighbor 100.64.2.1 shutdown
    end"

Bring it back with `no neighbor 100.64.2.1 shutdown`.

## Lessons learned

1. Container egress traffic from non-clab Docker containers leaves via the
   lab VM's normal gateway, not the lab fabric. Probes had to be added as
   a node inside the Containerlab topology to actually traverse the lab.

2. cEOS containers are AlmaLinux 9 internally, but `dnf install` from
   inside the container fails (no working repo path). `tc` for netem-based
   ISP impairments would need to be applied from the host side on veth
   pairs — Containerlab places host-side veths in Docker network
   namespaces, so locating them requires `nsenter` against
   `/var/run/docker/netns/`. Deferred to a future improvement.

3. Prometheus relabel rules that conditionally set labels (e.g., setting
   `isp=isp_a` when target=8.8.8.8) need each rule to be its own
   relabel_config block — they execute sequentially against each target.
   Easy to write incorrectly.

4. Grafana's default Builder mode wraps queries in extra braces. Switch to
   Code mode for raw PromQL.
