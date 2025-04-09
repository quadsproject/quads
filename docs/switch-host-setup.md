QUADS Bare-Metal Switch and Host Setup
======================================

General guidelines of how to setup your network switches, servers and DNS for QUADS.

![quads](../image/quads.png)

   * [QUADS Bare-Metal Switch and Host Setup](#quads-bare-metal-switch-and-host-setup)
      * [Network Architecture](#network-architecture)
      * [Physical Switch Setup](#physical-switch-setup)
      * [Distribution Switch Configuration](#distribution-switch-configuration)
      * [TOR Switch Configuration](#tor-switch-configuration)
      * [Greenfield TOR Switch Configuration](#greenfield-tor-switch-configuration)
      * [QUADS Host Network Setup](#quads-host-network-setup)
      * [Adding New QUADS Host](#adding-new-quads-host)
        * [Integration into Foreman or a Provisioning System](#integration-into-foreman-or-a-provisioning-system)
          * [Foreman Tuning](#foreman-tuning)
          * [Create Foreman Roles and Filters](#create-foreman-roles-and-filters)
          * [Adding New QUADS Host IPMI](#adding-new-quads-host-ipmi)
          * [Add Optional SSH Keys](#add-optional-ssh-keys)
          * [Create QUADS IPMI Credentials](#create-quads-ipmi-credentials)
      * [Define Optional Public VLANS](#define-optional-public-vlans)
        * [Define Publicly Routable VLANS on TOR Switches](#define-publicly-routable-vlans-on-tor-switches)
        * [Define Publicly Routable VLANS on Distribution Switches](#define-publicly-routable-vlans-on-distribution-switches)
        * [Generate a Skeleton VLANS YAML config](#generate-a-skeleton-vlans-yaml-config)
        * [Run Tool to Import VLANS into the Database](#run-tool-to-import-vlans-into-the-database)

## Network Architecture
   - We use top-of-rack switches that connect up to two distribution switches (Juniper QFX5200 currently)
   - Each TOR switch is uplinked to a pair of distribution (QFX5200 also) configured via MC-LAG

## Physical Switch Setup
   * Connect the serial console for remote management
   * Connect 100gigE optics for uplinks and fiber cable (or appropriate for your environment) - we use 4 x optics per rack.
   * Add ssh keys to your switches for management
```
set system login user quads uid 2002
set system login user quads class super-user
set system login user quads authentication ssh-rsa "ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAgEAtX0bAdKVSDeQa4PCN4bLLAqjR0DExUB1lhG1q4jPf9tWwWJ1cRqG3wn7CEqlItiankKdqd+8eZHTGgmBft76
XhjiXtwR4VkANjAqJUFXTkgSXj9nz0rkrHGVYYWvPBvg5KiZm5/ba+ndvyQWc5vDhv8dIKo17uZ5DC6DOcCQs4y6QhYxxVAiqIZaFeFkgRw4Ebkx+MhZ1VrVByOC2PZtj2drwGAa7ItX2i4idIaKTRBI9pehL4ay4NGbzdUeEP304X
k5vwnxBvDBE2oOuZFguQFyNAOkvy+61Tnp6waE05Ss/ZU3J861+fiCJJ1o3waas80qOAIwVTaIwGQ/FTJngZutRcLkdTC21+qaRbW9ZbTIG+bUp1NKAhj84HSsNc8CTcwNEcv8nwi0Cy4ZXY88+DcO5n6CmFFOm7sXTr0umrhBsKTh
Le+f24Xm77cBE5qNleFns7hkPZxRqEznC0xdd1xKswexbAB9mb2vP3uy1qzk3yQsifatzX3qANWrNgjQlALFXEf95woncUY+VA95Y028YM0/ojpi57jq7wHImh9iqzli20G9RE= quads@example.com"
```
   * You may also want a `~/.ssh/config` entry for each of your switches to make things easier.

```
Host 10.12.67.247
     User                       quads
     IdentityFile               /root/.ssh/id_rsa_quads
     UserKnownHostsFile         /dev/null
     StrictHostKeyChecking      false
     PubkeyAcceptedKeyTypes=+ssh-dss
```

   * Note: `python3-paramiko` wants your private key to contain the algo type in it, e.g. `BEGIN RSA PRIVATE KEY and END RSA PRIVATE KEY`
      * The following command will fix this for you:  `ssh-keygen -p -m PEM -f ~/.ssh/id_rsa` (don't set passphrase).
      * More details at [Stack Exchange](https://stackoverflow.com/questions/45829838/paramiko-connect-with-private-key-not-a-valid-openssh-private-public-key-fil#45844549)
      * We will be moving to `libssh` in an upcoming release.

## Distribution Switch Configuration
   * Configure your switch ports for QUADS-managed hosts as follows, we are using ```et-0/0/12``` on both distribution switches for an example rack.
      * Note: ```interface-range``` identifier is unique, so for example uplinks for B07 would be PC44 and ae44

```
set interfaces interface-range PC43 member et-0/0/12
set interfaces interface-range PC43 apply-macro do-not-expand
set interfaces interface-range PC43 description sw13-access-scalelab
set interfaces interface-range PC43 ether-options 802.3ad ae43
set interfaces ae43 apply-groups MCAE
set interfaces ae43 apply-groups ACCESS_TRUNK
set interfaces ae43 description sw13-access-scalelab
set interfaces ae43 mtu 9216
set interfaces ae43 aggregated-ether-options lacp active
set interfaces ae43 aggregated-ether-options lacp admin-key 43
set interfaces ae43 aggregated-ether-options mc-ae mc-ae-id 43
```

## TOR Switch Configuration
   * You can easily capture the configuration of an existing QUADS switch with these commands
   * Alter any interface or IP address configuration so that it's unique to your new switch

```
set cli screen-length 0
show configuration | display set
```

## Greenfield TOR Switch Configuration
This configuration is for a brand new switch and you have no others from where you can copy and modify the configuration.
   * Set chassis and channel speed appropriately

```
set chassis redundancy graceful-switchover
set chassis aggregated-devices ethernet device-count 448
set chassis fpc 0 pic 0 port-range 0 29 channel-speed 10g
```

   * Define your uplink interfaces to the distribution switches, do this for both sets.

```
set interfaces interface-range PC1 member et-0/0/31
set interfaces interface-range PC1 member et-0/0/30
set interfaces interface-range PC1 apply-macro do-not-expand
set interfaces interface-range PC1 description sw01-dist-scalelab
set interfaces interface-range PC1 ether-options 802.3ad ae1
```
   * QinQ Group Settings and Port Prefixes
      * We use 100/40GbE breakout cables to split 1 x 40/100G port into many
      * ```xe-0/0/0:0``` is the channel 0 (there are 4 channels, 0,1,2,3) from a breakout cable.
      * ```et``` is generally 40 or 100GbE, ```xe``` is 10GbE
         * e.g. 2 x 40GbE breakout cables turns into 8 x 10GbE ports

   * Create a set of QinQ VLAN group for each QUADS Assignment/Cloud that you intend to use.
   * We use vl1140, vl1150, vl1160, vl1170 and so on.
```
set groups QinQ_vl1140 interfaces <*> flexible-vlan-tagging
set groups QinQ_vl1140 interfaces <*> native-vlan-id 1140
set groups QinQ_vl1140 interfaces <*> mtu 9216
set groups QinQ_vl1140 interfaces <*> encapsulation extended-vlan-bridge
set groups QinQ_vl1140 interfaces <*> unit 0 vlan-id-list 1-4000
set groups QinQ_vl1140 interfaces <*> unit 0 input-vlan-map push
set groups QinQ_vl1140 interfaces <*> unit 0 output-vlan-map pop
```
   * QUADS will apply/unapply QinQ Group Settings for you when things are moved.
   * **Do not paste this below, it's an example**
   * _Done manually it would look like this for example_
```
set interfaces xe-0/0/0:0 apply-groups QinQ_vl1140
set interfaces xe-0/0/0:1 apply-groups QinQ_vl1140
set interfaces xe-0/0/0:2 apply-groups QinQ_vl1140
set interfaces xe-0/0/0:3 apply-groups QinQ_vl1140
set interfaces xe-0/0/1:0 apply-groups QinQ_vl1140
set interfaces xe-0/0/1:1 apply-groups QinQ_vl1140
set interfaces xe-0/0/1:2 apply-groups QinQ_vl1140
set interfaces xe-0/0/1:3 apply-groups QinQ_vl1140
```

## QUADS Host Network Setup
*  QUADS host interface information is now kept in the QUADS database, you can define this afterward at the time of defining your QUADS-managed host.  Refer to the host interface section of the [QUADS Usage Documentation](https://github.com/redhat-performance/quads/tree/master#quads-usage-documentation) after following the rest of this document.

## Adding New QUADS Host
* Rack the new systems to be added to QUADS
  * The provisioning interface is typically wired into a 1GbE NIC and connected to a switch **not** managed by QUADS.
  * Create DNS records using the following name format (in Foreman a new host entry will work)
  * If you already have your own naming convention then CNAMES will work.
```
(rack name)-(u-location)-(blade)-(system type)-(domain)
```
```
b08-h13-000-r620.rdu.openstack.engineering.example.com
```

* Optional PDU power management configuration
  * ~~Once the host is added, and if you have pdu_management enabled, you will also want to ensure you have your host PDU connections mapped out.  For more information on how to setup the PDU-connections.txt file please refer to [docs/pdu-setup.md](https://github.com/redhat-performance/quads/docs/pdu-setup.md)~~

  * **NOTE** As of `1.1.0` PDU management is currently unavailable but will be added back in soon.

### Sending Notification Emails from a Container
   * If you want to send email from QUADS containers (and not the localhost MTA) you will need changes to the localhost MTA of the host running your podman container to facilitate relaying mail through it, as cgroup and container isolation do not permit this without additional settings.
      * In `/etc/postfix/main.cf` where `172.17.0.1` is your `docker0` interface on the podman container host.
      * In our R&D environments we use an upstream SMTP relay server, your environment may vary.
```
inet_interfaces = all
mydestination =
local_recipient_maps =
mynetworks = 172.17.0.0/16, localhost, 127.0.0.0/8
relay_domains = domain.example.com, example.com
relayhost = [ipaddress.of.your.relay.smtp.server]
smtpd_recipient_restrictions = permit_mynetworks
smtpd_authorized_xforward_hosts = [::1]/128
smtpd_client_restrictions =
```

   * If you're running QUADS in a VM or bare-metal host and you have an upstream SMTP server simply configure postfix appropriately.
      * In `/etc/postfix/main.cf`

```
relayhost = [ip.address.of.your.relay.smtp.server]
inet_interfaces = all
```

### Integration into Foreman or a Provisioning System
   * We will not be covering setting up [Foreman](https://theforeman.org) however that is documented [extensively here](https://theforeman.org/manuals/nightly/#3.InstallingForeman).
   * We do provide some [example templates](https://github.com/redhat-performance/quads/tree/master/templates) for post-provisioning creation of system interface config files like ```/etc/sysconfig/network-scripts/ifcfg-*``` for use with QUADs.

#### Foreman Tuning
   * Because we use `asyncio` and make direct calls to the Foreman API you may want to adjust your `MaxKeepAliveRequests` in your Apache configuration for `mod_passenger` to accomodate more simultaneous connections.
   * In `/etc/httpd/conf.d/05-foreman.conf` and `/etc/httpd/conf.d/05-foreman-ssl.conf`

```
MaxKeepAliveRequests 200
```

#### Create Foreman Roles and Filters
   * This is Foreman-specific so if you want another provisioning backend you can ignore it.
   * We use RBAC roles and filters to allow per-cloud Foreman views into subsets of machines, QUADS will manage this for you once created.
      * Foreman views are based on system ownership of cloud users (generic users per environment)
      * You need to create two roles, with filters below - `clouduser_views` and `clouduser_hosts`
      * Each server role has filters attached that grant it certain permissions
   * Create the `clouduser_hosts` role
```
hammer role create --name clouduser_hosts
```
   * Create a filter with a singular search scope of `user.login = current_user`
```
hammer filter create --role clouduser_hosts --search "user.login = current_user" --permissions view_hosts,edit_hosts,build_hosts,power_hosts,console_hosts --role-id $(hammer role info --name clouduser_hosts | egrep ^Id: | awk '{ print $NF }')
```
   * Next you'll need to make a Foreman user per unique cloud environment if they don't exist already
```
hammer user create --login cloud01 --password password --mail quads@example.com --auth-source-id 1
hammer user create --login cloud02 --password password --mail quads@example.com --auth-source-id 1
hammer user create --login cloud03 --password password --mail quads@example.com --auth-source-id 1
```

   * Lastly you will need to provide a special group these users belong to for generic, persistent filters cloud users will always need.

```
hammer role create --name clouduser_views
hammer filter create --role clouduser_views --permissions view_operatingsystems
```
   * Now you'll need to update the filters associated with the `cloudusers_views` role with other resource types.
```
hammer filter update --role clouduser_views --permissions view_architectures --id $(hammer filter list | grep clouduser_views | awk '{print $1}')
hammer filter update --role clouduser_views --permissions view_media --id $(hammer filter list | grep clouduser_views | awk '{print $1}')
hammer filter update --role clouduser_views --permissions view_ptables --id $(hammer filter list | grep clouduser_views | awk '{print $1}')
hammer filter update --role clouduser_views --permissions edit_params,view_params --id $(hammer filter list | grep clouduser_views | awk '{print $1}')
hammer filter update --role clouduser_views --permissions view_users --id $(hammer filter list | grep clouduser_views | awk '{print   $1}')
```
   * Your filters should look something like this when you're done, this can also be done in the Foreman UI as well if you have problems with CLI.

   * `clouduser_views` role filter

![clouduser_rbac2](../image/cloud_rbac2.png?raw=true)

   * `clouduser_hosts` role filter

![clouduser_rbac](../image/cloud_rbac.png?raw=true)

   * Next create your `cloudusers` generic group and tie it all together
```
hammer user-group create --name cloudusers --roles clouduser_views clouduser_hosts
```
   * Lastly, add all your existing cloud users as members of this group (we use 32 cloud users in this example)
```
for clouduser in $(seq 1 9); do hammer user-group add-user --name cloudusers --user cloud0$clouduser; done
for clouduser in $(seq 10 32); do hammer user-group add-user --name cloudusers --user cloud$clouduser; done
```

   * You should see the `cloudusers` group now have the following roles added above:

![clouduser_rbac3](../image/cloud_rbac3.png?raw=true)

   * In order for non-admin environment users (e.g. cloud02, cloud03) to see only their hosts the hosts simply need to have their ownership changed to that respective cloud user. [foreman_heal.py](https://github.com/redhat-performance/quads/blob/master/quads/tools/foreman_heal.py) will take care of this for you, we typically run this every 3 hours outside of [cron](https://github.com/redhat-performance/quads/blob/master/cron/quads#L45).  This will both setup system ownership as well as fix inconsistencies if they exist when run.

   * If you'd prefer to manage this yourself with `hammer cli` then we're just running the equivalent of `hammer host update --name host01.example.com --owner newcloudusername`

### Adding New QUADS Host IPMI

#### Add Optional SSH Keys

   * Ensure QUADS host has access to the out-of-band interfaces
      * For Dell systems we copy the QUADS ssh key in via racadm
```
/opt/dell/srvadmin/bin/idracadm -r <drac IP> -u root -p calvin sshpkauth -f /root/.ssh/id_rsa_r620.pub -i 2 -k 1
```
   * Refer to your vendor out-of-band documentation for other system types if you want to add ssh keys.

#### Create QUADS IPMI Credentials
   * IPMI credentials are defined in [the QUADS configuration file](https://github.com/redhat-performance/quads/blob/master/conf/quads.yml#L138) so adjust accordingly to your environment and preference.
   * Note: SuperMicro systems (and perhaps other vendors) do not have the `root` user by default, if not you'll need to create it.
   * Check if the `root` user exists first, Dell systems come with a `root` user by default so this step can be omitted.

```
ipmitool -I lanplus -H mgmt-<hostname> -U ADMIN -P ADMIN  user list | grep root
```

   * Note: SuperMicro systems (and perhaps other vendors) do not have the `root` user by default, if not you'll need to create it.

```
ipmitool -I lanplus -H mgmt-<hostname> -U ADMIN -P ADMIN  user set name 3 root
ipmitool -I lanplus -H mgmt-<hostname> -U ADMIN -P ADMIN  user set password 3 YourRootPass
ipmitool -I lanplus -H mgmt-<hostname> -U ADMIN -P ADMIN user priv 3 0x4
ipmitool -I lanplus -H mgmt-<hostname> -U ADMIN -P ADMIN channel setaccess 1 3 ipmi=on
```

   * Create a ```quads``` IPMI user on all out-of-band interfaces with the proper privileges

```
ipmitool -I lanplus -H mgmt-<hostname> -U root -P <pw> user set name 4 quads
ipmitool -I lanplus -H mgmt-<hostname> -U root -P <pw> user set password 4 quadspassword
ipmitool -I lanplus -H mgmt-<hostname> -U root -P <pw> user priv 4 0x4
ipmitool -I lanplus -H mgmt-<hostname> -U root -P <pw> user enable 4
ipmitool -I lanplus -H mgmt-<hostname> -U root -P <pw> channel setaccess 1 4 ipmi=on
```

At this point you can **proceed with initializing QUADS** [from the main documentation](https://github.com/redhat-performance/quads#quads-usage-documentation).

## Define Optional Public VLANS

Public VLANS are an optional feature that allow you to tag the 4th (or last) internal interface across a set of machines when you define an new cloud environment.  You must already have these sets of VLANS defined on each top-of-rack switch in your environment respectively.

The below examples are how we do this on Juniper QFX5X00 switches, adjust as necessary.

This should be done after you have a working QUADS installation.

### Define Publicly Routable VLANS on TOR Switches

   - On all the TOR switch(es), for each VLAN you want to share across racks, for example VLAN 601:

```
set interfaces ae1 unit 601 vlan-id 601
set protocols igmp-snooping vlan vlan601
set protocols vstp vlan 601
set vlans vlan601 apply-groups VMOVE
set vlans vlan601 description pubnet01
set vlans vlan601 vlan-id 601
set vlans vlan601 interface ae1.601
```

### Define Publicly Routable VLANS on Distribution Switches

   - You'll also want corresponding configurations on your DIST switches.
   - The aeXX interfaces are port channsls from TOR to DIST

```
set interfaces ae31 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae32 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae33 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae34 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae35 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae36 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae37 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae38 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae39 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae40 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae41 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae42 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae43 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae44 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae45 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae46 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae47 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae48 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae49 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae50 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae51 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae52 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae53 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae54 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae55 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae56 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae57 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae58 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae59 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae60 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae61 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae62 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae63 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae64 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae65 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae66 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae67 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae68 unit 0 family ethernet-switching vlan members 601-620
set interfaces ae69 unit 0 family ethernet-switching vlan members 601-620
set interfaces irb unit 601 description pubnet01
set interfaces irb unit 601 family inet address 10.1.49.254/23 primary
set interfaces irb unit 601 family inet address 10.1.49.254/23 preferred
set interfaces irb unit 601 family inet6 address 2620:52:0:130::1fe/64
set forwarding-options dhcp-relay group DHCPServerScaleLAB interface irb.601
set protocols router-advertisement interface irb.601 prefix 2620:52:0:130::/64
set protocols pim interface irb.601 mode sparse
set protocols pim interface irb.601 version 2
set protocols igmp-snooping vlan vlan601
set vlans vlan601 apply-groups VMOVE
set vlans vlan601 description pubnet01
set vlans vlan601 vlan-id 601
set vlans vlan601 l3-interface irb.601
```

### Generate a Skeleton VLANS YAML config

We ship an example VLANS yaml configuration template you can use generate your public VLAN definitions and import them into the QUADS database.

   - First, edit the template to your liking to match your network setup.

```
vi /opt/quads/conf/vlans.yml
```

   - These settings should match the physical routable VLAN interfaces that you have defined on your switches, along with their VLAN ID.

### Run Tool to Import VLANS into the Database

Lastly, run the import tool to parse the VLAN YAML config and define these VLANs into your QUADS database.

```
cd /opt/quads/
python3 /usr/lib/python3.12/site-packages/quads/tools/vlan_yaml_to_db.py --yaml /opt/quads/conf/vlans.yml
```
