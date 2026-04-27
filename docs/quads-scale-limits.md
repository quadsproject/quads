# Deployment Scale Limits

   * [Deployment Scale Limits](#deployment-scale-limits)
      * [Theoretical Limits](#theoretical-limits-per-l2-tagged-vlan-network)
      * [Current Limits](#current-limits)
      * [Breakdown](#breakdown)
      * [References](#references)

_How many hosts and environments can a single QUADS instance use?_

QUADS is designed to handle large amounts of hosts spread across independent, isolated multi-tenant environments.

QUADS is physically limited by the VLAN limit in the [IEEE 802.1Q](https://standards.ieee.org/ieee/802.1Q/6844/) spec which specifies **4090** usable VLANS per VLAN-tagged Layer 2 network.

## Theoritical Limits per L2 Tagged VLAN Network

* In theory each QUADS instance can scale to the number of individual isolated **environments** equal to `4090 / highest number of internal interfaces in a host minus one (for your spare cloud)`
* Each QUADS instance can scale to a number of **hosts** equal to `98,160 / highest number of internal interfaces in a host`

## Current Limits
   > [!NOTE]
   > Our current implementation iterates VLAN assignments by 10 so that means the formula  is `4090 / 10 minus 10` for maximum available VLAN-tagged environments or _clouds_ which reduces the maximum amount of multi-tenant environments by 60% or more of this total.

   > [!TIP]
   > In [RFE #589](https://github.com/quadsproject/quads/issues/589) we'll be removing this increment-by-10 approach from the codebase so that scale of usable VLAN-tagged environments will likely double to their theoritical limit for common deployments with 4 or less internal interfaces per host.

For example, right now QUADS can support 399 individual environments with a combined host count of [24,540 servers.](https://gist.github.com/sadsfae/f932b6deecd2dcf4725d357803c6c806) or `98,160 vmembers / 4` per VLAN-tagged layer 2 network if the highest number of internal interfaces across your host fleet is 4.

   > [!TIP]
   > It is assumed we are referring to limits in a single QUADS instance, limits could be vastly expanded once [multi-Forman](https://github.com/quadsproject/quads/issues/384) support is added which could potentially support multiple VLAN-tagged layer 2 networks.

Consult the below chart on host and network scale limits:

## Breakdown

* Current and future limits per VLAN-tagged layer 2 Network

| Component | Current Limit | Future RFE #589 Limit | Notes |
|-----------|---------------|-----------------------|-------|
| Cloud Environments | 399 | 1268 | assuming 4x interfaces max/host|
| Physical Hosts | 24,540 | 24,540 | assuming 4x interfaces max/host|

## References

[1](https://www.juniper.net/documentation/us/en/software/junos/multicast-l2/topics/topic-map/q-in-q.html)
[2](https://www.juniper.net/documentation/us/en/software/junos/multicast-l2/topics/topic-map/bridging-and-vlans.html)
[3](https://www.juniper.net/documentation/en_US/junos/topics/topic-map/bridging-and-vlans.html#id-configuring-vlans-on-switches-with-enhanced-layer-2-support)
[4](https://www.juniper.net/documentation/us/en/software/junos/multicast-l2/topics/ref/statement/vlan-id-edit-vlans-qfx-series.html)
[5](https://networkengineering.stackexchange.com/questions/18839/vlan-creation-on-juniper-qfx5100)
