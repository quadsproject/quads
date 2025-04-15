QUADS Metadata Model and Search Library
======================================

In QUADS `1.1.4` and above we've implemented a metadata model in the QUADS database that captures information about host hardware, model, and other useful information.  We'll be expanding this as time progresses.

![quads](../image/quads.png)

  * [How to Import Host Metadata](#how-to-import-host-metadata)
     * [Gathering Metadata via lshw Tools Locally](#gathering-metadata-via-lshw-tools-locally)
     * [Gathering Metadata via lshw Tools Remotely](#gathering-metadata-via-lshw-tools-remotely)
     * [Modify YAML Host Data](#modify-yaml-host-data)
     * [Add any Supporting Model Type](#add-any-supporting-model-type)
     * [Importing Host Metadata](#importing-host-metadata)
  * [How to Export Host Metadata](#how-to-export-host-metadata)
  * [Querying Host Information](#querying-host-information)
     * [Example Filter Searches](#example-filter-searches)
        * [Example Hardware Filter Searches](#example-hardware-filter-searches)
        * [Example GPU Filter Searches](#example-gpu-filter-searches)
        * [Example Network Filter Searches](#example-network-filter-searches)
           * [Combined Network Search Example](#combined-network-search-example)
   * [Querying Host Status](#querying-host-status)
     * [Example Filter Searches](#example-status-filter-searches)
## How to Import Host Metadata
  * Host metadata can be gathered by both editing and importing YAML files or directly via `lshw` locally on each host or remotely en-masse.

### Gathering Metadata via lshw Tools Locally
  * We can use the popular [lshw](https://linux.die.net/man/1/lshw) tool to gather hardware details into JSON
  * We ship a tool called `lshw2meta.py` to transform this into a format for updating host metadata into QUADS.

First, install `lshw` on your target QUADS-managed host(s)

```
dnf install lshw
```

Next run `lshw` to capture all the hardware details of each remote host in JSON.

```
lshw -json > $(hostname).json
```

Next, copy the JSON file(s) over to your QUADS host here: `quads:/opt/quads/lshw/`

Now, back on your QUADS host use the `lshw2meta.py` tool to convert this data and import it directly into the QUADS database for each host.

```
python3 /usr/lib/python3.12/site-packages/quads/tools/lshw2meta.py
```

### Gathering Metadata via lshw Tools Remotely
  * We also provide an `lshw.py` tool which can be used to gather `lshw` JSON data remotely over SSH
  * This assumes you have root SSH keys on each remote system.
  * This assumes all of your hosts are in `cloud01` and powered on and accessible
  * This assumes you have `lshw` installed as well on every remote host

First, gather all of the JSON metadata from your remote QUADS-managed host(s):
```
python3 /usr/lib/python3.12/site-packages/quads/tools/lshw.py
```

Now import them all via `lshw2meta.py`
```
python3 /usr/lib/python3.12/site-packages/quads/tools/lshw2meta.py
```

### Modify YAML Host Data
  * Host metadata uses a standard YAML key/value pair format, here's a [reference example](../conf/hosts_metadata.yml)
  * Host metadata is not required unless you want to use it, **it is entirely optional**

### Add any Supporting Model Type
  * We list some example model types of baremetal systems we use, you will also want to edit the `models:` value so it has any additional system models you might use in the [QUADS Conf](../conf/hosts_metadata.yml#L238)
  * To generate a YAML metadata file for importing QUADS-managed hosts you can use this command:

```
for h in $(quads --ls-hosts) ; do echo "- name: $h" ; echo "  model: $(echo $h | awk -F. '{ print $1 }' | awk -F- '{ print $NF }' | tr a-z A-Z)" ; done > /tmp/hosts_metadata.yml
```

### Importing Host Metadata

  * To import host metadata from a file:

```
quads --define-host-details --metadata /tmp/hosts_metadata.yml
```

  * Doing this again or modifying your `hosts_metadata.yml` file and re-importing will overwrite all values or remove ones that might have been removed from the QUADS database.

## How to Export Host Metadata
  * To export the same formatted YAML key/value pair metadata data source from your hosts use the `--export-host-details` command.
  * The file provided should be a new file, or overwrite an existing one and the path should be somewhere on the filesystem.

```
quads --export-host-details /tmp/my_host_data.yml
```

## Querying Host Information
  * The sub-command `--filter` can be used with `--ls-available` and `--ls-hosts` commands.

| Component              | Field Type | Description                  | Operators       |
|------------------------|------------|------------------------------|-----------------|
| model                  |  string    | defined system model         | ==,!=           |
| rack                   |  string    | rack name                    | ==,!=           |
| uloc                   |  string    | U location                   | ==,!=           |
| blade                  |  string    | blade id                     | ==,!=           |
| disks.size_gb          |  integer   | disk size in GB              | ==,!=,<,<=,>,>= |
| disks.disks_type       |  string    | nvme,sata,ssd                | ==,!=           |
| disks.count            |  integer   | number of disks              | ==,!=,<,<=,>,>= |
| interfaces.count       |  integer   | number of interfaces         | ==,!=,<,<=,>,>= |
| interfaces.name        |  string    | name of interface            | ==,!=           |
| interfaces.mac_address |  string    | mac address                  | ==,!=           |
| interfaces.switch_port |  string    | switch port                  | ==,!=           |
| interfaces.switch_ip   |  string    | switch ip address per port   | ==,!=           |
| interfaces.speed       |  integer   | link speed                   | ==,!=,<,<=,>,>= |
| interfaces.vendor      |  string    | interface vendor             | ==,!=           |
| interfaces.maintenance |  boolean   | interface maintenance status | ==,!=           |
| interfaces.bios_id     |  string    | interface BIOS boot devname  | ==,!=           |
| build                  |  boolean   | build status                 | ==,!=           |
| validated              |  boolean   | validated status             | ==,!=           |
| broken                 |  boolean   | broken status                | ==,!=           |
| retired                |  boolean   | retired status               | ==,!=           |
| switch_config_applied  |  boolean   | host switch config status    | ==,!=           |
| memory.handle          |  string    | DIMM details                 | ==,!=           |
| memory.size_gb         |  integer   | amount of system memory      | ==,!=,<,<=,>,>= |
| processors.handle      |  string    | CPU details                  | ==,!=           |
| processors.vendor      |  string    | CPU/GPU vendor information   | ==,!=           |
| processors.product     |  string    | CPU/GPU model information    | ==,!=           |
| processors.cores       |  integer   | CPU cores in the system      | ==,!=,<,<=,>,>= |
| processors.threads     |  integer   | CPU threads in the system    | ==,!=,<,<=,>,>= |

### Example Filter Searches
  * Accepted operators are `==, !=, <, <=, >, >=`
  * For the REST API the operators must be appended to the key like so `disks.size_gb__gte=2000`

| Operator | Appended |
|----------|----------|
| ==       |          |
| !=       | __ne     |
| <        | __lt     |
| <=       | __lte    |
| >        | __gt     |
| >=       | __gte    |
| like     | __like   |
| ilike    | __ilike  |
| in       | __in     |

#### Example Hardware Filter Searches

  * Search for systems with disk type NVMe, with a size of 2TB or more and available between `2020-07-20 17:00` and `2020-07-22 13:00`

```
quads --ls-available --schedule-start "2020-07-20 17:00" --schedule-end "2020-07-22 13:00" --filter "disks.disk_type==nvme,disks.size_gb>=2000"
```
  * Via the API

```
curl https://quads.example.com/api/v3/available?start=2020-07-20T17:00&end=2020-07-22T13:00&disks.disk_type=nvme&disks.size_gb__gte=2000
```

  * Search for systems with SATA disks available from `2020-07-20 17:00` until `2020-07-22 13:00`

```
quads --ls-available --schedule-start "2020-07-20 17:00" --schedule-end "2020-07-22 13:00" --filter "disks.disk_type==sata"
```
  * Via the API

```
curl https://quads.example.com/api/v3/available?start=2020-07-20T17:00&end=2020-07-22T13:00&disks.disk_type=sata
```

  * Search for systems of model type `1029U-TRTP` available from `2020-07-20 17:00` until `2020-07-22 13:00`

```
quads --ls-available --schedule-start "2020-07-20 17:00" --schedule-end "2020-07-22 13:00" --filter "model==1029U-TRTP"
```
  * Via the API

```
curl https://quads.example.com/api/v3/available?start=2020-07-20T17:00&end=2020-07-22T13:00&model=1029U-TRTP
```

  * Search for systems with **two NVMe** disks **and** disk size of **more than** 2TB, available from `2020-07-20 17:00` until `2020-07-22 13:00`

```
quads --ls-available --schedule-start "2020-07-20 17:00" --schedule-end "2020-07-22 13:00" --filter "disks.disk_type==nvme,disks.count>2, disks.size_gb<2000"
```
  * Via the API

```
curl https://quads.example.com/api/v3/available?start=2020-07-20T17:00&end=2020-07-22T13:00&disks.disk_type=nvme&disks.count__gt=2&disks.size_gb__lt=2000
```

  * Search all systems by model and number of interfaces.

```
quads --ls-hosts --filter "model==FC640,interfaces__size==5"
```
  * Via the API

```
curl https://quads.example.com/api/v3/hosts?model=FC640&interfaces__size=5
```

#### Example GPU Filter Searches
  * List all systems with an Nvidia GPU

```
quads --ls-hosts --filter "processors.vendor==NVIDIA Corporation"
```

  * Via the API

```
curl https://quads.example.com/api/v3/hosts?processors.vendor=NVIDIA%20Corporation | jq
```

  * List all systems with an Nvidia Tesla T4 GPU

```
quads --ls-hosts --filter "processors.product==TU104GL [Tesla T4]"
```

  * Via the API

```
curl 'https://quads.example.com/api/v3/hosts?processors.product=TU104GL%20\[Tesla%20T4\] | jq'
```

#### Example Network Filter Searches

  * Find a host by MAC Address.
  * This is useful for finding what host has what MAC Address.

```
quads --ls-hosts --filter "interfaces.mac_address==ac:1f:6b:2d:19:48"
```
  * Via the API

```
curl https://quads.example.com/api/v3/hosts?interfaces.mac_address=ac:1f:6b:2d:19:48
```

  * Find hosts by switch IP address.
  * Shows all hosts connected to a particular switch

```
quads --ls-host --filter "interfaces.switch_ip==10.1.34.216"
```
  * Via the API

```
curl https://quads.example.com/api/v3/hosts?interfaces.switch_ip=10.1.34.216
```

  * Find hosts by physical switchport
  * Shows all hosts that have a specific physical switchport name

```
quads --ls-host --filter "interfaces.switch_port==et-0/0/7:1"
```
  * Via the API

```
curl https://quads.example.com/api/v3/hosts?interfaces.switch_port=et-0/0/7:1
```

##### Combined Network Search Example

  * Like other filter strings you can combine elements together.
  * Example: Search for a host by physical switchport **and** switch IP address.

```
quads --ls-hosts --filter "interfaces.switch_ip==10.1.34.216,interfaces.switch_port==et-0/0/7:1"
```
  * Via the API

```
curl https://quads.example.com/api/v3/hosts?interfaces.switch_ip=10.1.34.216&interfaces.switch_port=et-0/0/7:1
```

## Querying Host Status
* We will be adding features to query host status in addition to hardware metadata/details.
* Functionality here may include retirement/decomission status and other useful attributes.

### Example Status Filter Searches

  * List all systems by retirement (decomission) status.

```
quads --ls-hosts --filter "retired==True"
```
  * Via the API

```
curl https://quads.example.com/api/v3/hosts?retired=True
```

  * List retired hosts and filter by model

```
quads --ls-hosts --filter "retired==True,model==1029P"
```
  * Via the API

```
curl https://quads.example.com/api/v3/hosts?retired=True&model=1029P
```
