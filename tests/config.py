"""Template responses and requests for API testing."""

from datetime import datetime, timedelta

from tests.cli.config import OS_TYPE

# --------------------
# AUTH
# --------------------
EXPIRED_TEST_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2NzU3Njc4NDUsImlhdCI6MTY3NTc2MTg0NSwic3ViIjoi"
    "Z3JhZnVsc0ByZWRoYXQuY29tIn0.lDTmUpY4b3sICYUcAriui6yTv-iki10fBm07x6fuayc"
)

# --------------------
# HOSTS
# --------------------
HOST_1_REQUEST = {
    "name": "host1.example.com",
    "default_cloud": "cloud01",
    "model": "fc640",
    "rack": "h01",
    "uloc": "u01",
    "host_type": "scalelab",
}
HOST_2_REQUEST = {
    "name": "host2.example.com",
    "default_cloud": "cloud01",
    "model": "r640",
    "rack": "h01",
    "uloc": "u02",
    "host_type": "alias",
    "boot_mode": "Bios",
}
HOST_3_REQUEST = {
    "name": "host3.example.com",
    "default_cloud": "cloud01",
    "model": "1029p",
    "rack": "h01",
    "uloc": "u03",
    "host_type": "scalelab",
}
HOST_4_REQUEST = {
    "name": "host4.example.com",
    "default_cloud": "cloud01",
    "model": "r640",
    "rack": "h01",
    "uloc": "u04",
    "cloud": "cloud03",
    "host_type": "scalelab",
}
HOST_5_REQUEST = {
    "name": "host5.example.com",
    "default_cloud": "cloud05",
    "model": "6048r",
    "rack": "h01",
    "uloc": "u05",
    "cloud": "cloud05",
    "host_type": "scalelab",
}
SELF_HOST_1_REQUEST = {
    "name": "host11.example.com",
    "default_cloud": "cloud01",
    "model": "fc640",
    "rack": "h01",
    "uloc": "u11",
    "host_type": "scalelab",
    "can_self_schedule": False,
}
SELF_HOST_2_REQUEST = {
    "name": "host12.example.com",
    "default_cloud": "cloud01",
    "model": "r640",
    "rack": "h01",
    "uloc": "u12",
    "host_type": "alias",
    "can_self_schedule": False,
}
SELF_HOST_3_REQUEST = {
    "name": "host13.example.com",
    "default_cloud": "cloud01",
    "model": "1029p",
    "rack": "h01",
    "uloc": "u13",
    "host_type": "scalelab",
    "can_self_schedule": False,
}
SELF_HOST_4_REQUEST = {
    "name": "host14.example.com",
    "default_cloud": "cloud01",
    "model": "r640",
    "rack": "h01",
    "uloc": "u14",
    "host_type": "scalelab",
    "can_self_schedule": False,
}
SELF_HOST_5_REQUEST = {
    "name": "host15.example.com",
    "default_cloud": "cloud01",
    "model": "6048r",
    "rack": "h01",
    "uloc": "u15",
    "host_type": "scalelab",
    "can_self_schedule": False,
}

# --------------------
# DISKS
# --------------------
DISK_1_REQUEST = (
    {"disk_type": "nvme", "size_gb": 2000, "count": 2},
    "host1.example.com",
)
DISK_1_RESPONSE = {
    "disk_type": "nvme",
    "size_gb": 2000,
    "count": 2,
    "host_id": 1,
    "id": 1,
}
DISK_2_REQUEST = (
    {"disk_type": "sata", "size_gb": 4000, "count": 1},
    "host1.example.com",
)
DISK_2_RESPONSE = {
    "disk_type": "sata",
    "size_gb": 4000,
    "count": 1,
    "host_id": 1,
    "id": 2,
}
DISK_3_REQUEST = (
    {"disk_type": "nvme", "size_gb": 1000, "count": 3},
    "host2.example.com",
)
DISK_4_REQUEST = (
    {"disk_type": "scsi", "size_gb": 1000, "count": 2},
    "host3.example.com",
)
DISK_1_UPDATE_REQUEST = [
    {
        "disk_id": 1,
        "disk_type": "scsi",
        "size_gb": 1000,
        "count": 4,
    },
    "host1.example.com",
]
DISK_1_UPDATE_RESPONSE = {
    "disk_type": "scsi",
    "size_gb": 1000,
    "count": 4,
    "host_id": 1,
    "id": 1,
}

# --------------------
# INTERFACES
# --------------------
INTERFACE_1_REQUEST = (
    {
        "name": "em1",
        "bios_id": "NIC.Integrated.1",
        "mac_address": "00:d3:00:e4:00:c2",
        "switch_ip": "192.168.1.2",
        "switch_port": "et-0/0/0:1",
        "speed": 1000,
        "vendor": "Mellanox",
    },
    "host1.example.com",
)
INTERFACE_1_RESPONSE = {
    "name": "em1",
    "bios_id": "NIC.Integrated.1",
    "mac_address": "00:d3:00:e4:00:c2",
    "switch_ip": "192.168.1.2",
    "switch_port": "et-0/0/0:1",
    "speed": 1000,
    "vendor": "Mellanox",
    "host_id": 1,
    "id": 1,
    "maintenance": False,
    "pxe_boot": False,
}
INTERFACE_1_UPDATE_REQUEST = {
    "id": 1,
    "switch_ip": "192.168.2.2",
    "switch_port": "et-0/0/0:2",
}
INTERFACE_1_UPDATE_RESPONSE = {
    key: INTERFACE_1_UPDATE_REQUEST.get(key, INTERFACE_1_RESPONSE[key]) for key in INTERFACE_1_RESPONSE
}
INTERFACE_2_REQUEST = (
    {
        "name": "em1",
        "bios_id": "NIC.Integrated.1",
        "mac_address": "00:d3:00:e4:00:c3",
        "switch_ip": "192.168.1.2",
        "switch_port": "et-0/0/0:2",
        "speed": 1000,
        "vendor": "Mellanox",
    },
    "host2.example.com",
)
INTERFACE_3_REQUEST = (
    {
        "name": "em1",
        "bios_id": "NIC.Integrated.1",
        "mac_address": "00:d3:00:e4:00:c2",
        "switch_ip": "192.168.1.2",
        "switch_port": "et-0/0/0:3",
        "speed": 10000,
        "vendor": "Mellanox",
    },
    "host3.example.com",
)
INTERFACE_4_REQUEST = (
    {
        "name": "em1",
        "bios_id": "NIC.Integrated.1",
        "mac_address": "00:d3:00:e4:00:c5",
        "switch_ip": "192.168.2.2",
        "switch_port": "et-0/0/0:1",
        "speed": 1000,
        "vendor": "Mellanox",
    },
    "host4.example.com",
)

# --------------------
# MEMORY
# --------------------
MEMORY_1_REQUEST = ({"handle": "DIMM1", "size_gb": 2}, "host1.example.com")
MEMORY_1_RESPONSE = {"handle": "DIMM1", "size_gb": 2, "host_id": 1, "id": 1}
MEMORY_2_REQUEST = ({"handle": "DIMM2", "size_gb": 2}, "host1.example.com")
MEMORY_2_RESPONSE = {"handle": "DIMM2", "size_gb": 2, "host_id": 1, "id": 3}
MEMORY_3_REQUEST = ({"handle": "DIMM1", "size_gb": 4}, "host2.example.com")
MEMORY_3_RESPONSE = {"handle": "DIMM1", "size_gb": 4, "host_id": 2, "id": 2}
MEMORY_4_REQUEST = ({"handle": "DIMM1", "size_gb": 2}, "host2.example.com")
MEMORY_5_REQUEST = ({"handle": "DIMM1", "size_gb": 16}, "host3.example.com")
MEMORY_6_REQUEST = ({"handle": "DIMM2", "size_gb": 8}, "host4.example.com")

# --------------------
# PROCESSORS
# --------------------
PROCESSOR_1_REQUEST = (
    {
        "handle": "Intel Xeon Gold 6230 - 1",
        "vendor": "Intel",
        "product": "Xeon Gold 6230",
        "cores": 20,
        "threads": 40,
        "processor_type": "CPU",
    },
    "host1.example.com",
)
PROCESSOR_1_RESPONSE = {
    "handle": "Intel Xeon Gold 6230 - 1",
    "vendor": "Intel",
    "product": "Xeon Gold 6230",
    "cores": 20,
    "threads": 40,
    "processor_type": "CPU",
    "host_id": 1,
    "id": 1,
}
PROCESSOR_2_REQUEST = (
    {
        "handle": "Intel Xeon Gold 6230 - 2",
        "vendor": "Intel",
        "product": "Xeon Gold 6230",
        "cores": 20,
        "threads": 40,
        "processor_type": "CPU",
    },
    "host1.example.com",
)
PROCESSOR_2_RESPONSE = {
    "handle": "Intel Xeon Gold 6230 - 2",
    "vendor": "Intel",
    "product": "Xeon Gold 6230",
    "cores": 20,
    "threads": 40,
    "processor_type": "CPU",
    "host_id": 1,
    "id": 2,
}
PROCESSOR_3_REQUEST = (
    {
        "handle": "Intel Xeon Gold 6330 - 1",
        "vendor": "Intel",
        "product": "Xeon Gold 6330",
        "cores": 28,
        "threads": 56,
        "processor_type": "CPU",
    },
    "host2.example.com",
)
PROCESSOR_4_REQUEST = (
    {
        "handle": "AMD EPYC 7742 - 1",
        "vendor": "AMD",
        "product": "EPYC 7742",
        "cores": 64,
        "threads": 128,
        "processor_type": "CPU",
    },
    "host3.example.com",
)
PROCESSOR_5_REQUEST = (
    {
        "handle": "Intel Xeon Gold 6230 - 1",
        "vendor": "Intel",
        "product": "Xeon Gold 6230",
        "cores": 20,
        "threads": 40,
        "processor_type": "CPU",
    },
    "host4.example.com",
)

# --------------------
# VLANs
# --------------------
VLAN_1_REQUEST = {
    "gateway": "192.168.12.19",
    "ip_free": 510,
    "ip_range": "10.1.48.0/23",
    "netmask": "255.255.0.0",
    "vlan_id": 601,
}
VLAN_1_RESPONSE = {
    "gateway": "192.168.12.19",
    "ip_free": 510,
    "ip_range": "10.1.48.0/23",
    "netmask": "255.255.0.0",
    "vlan_id": 601,
    "id": 1,
}
VLAN_2_REQUEST = {
    "gateway": "192.168.12.20",
    "ip_free": 1022,
    "ip_range": "10.1.50.0/22",
    "netmask": "255.255.252.0",
    "vlan_id": 602,
}
VLAN_2_RESPONSE = {
    "gateway": "192.168.12.20",
    "ip_free": 1022,
    "ip_range": "10.1.50.0/22",
    "netmask": "255.255.252.0",
    "vlan_id": 602,
    "id": 2,
}
VLAN_3_REQUEST = {
    "gateway": "192.168.12.21",
    "ip_free": 1022,
    "ip_range": "10.1.54.0/22",
    "netmask": "255.255.252.0",
    "vlan_id": 603,
}
VLAN_1_UPDATE_REQUEST = {
    "gateway": "192.168.22.19",
    "ip_free": 510,
    "ip_range": "10.20.48.0/23",
    "netmask": "255.254.0.0",
}
VLAN_1_UPDATE_RESPONSE = {
    "gateway": "192.168.22.19",
    "ip_free": 510,
    "ip_range": "10.20.48.0/23",
    "netmask": "255.254.0.0",
    "vlan_id": 601,
    "id": 1,
}

# --------------------
# ASSIGNMENTS
# --------------------
ASSIGNMENT_1_REQUEST = {
    "cloud": "cloud02",
    "vlan": "601",
    "description": "Test allocation.",
    "owner": "grafuls",
    "ticket": "1",
    "ccuser": "gonza",
}
ASSIGNMENT_1_RESPONSE = {
    "active": True,
    "boot_order": "foreman",
    "ccuser": ["gonza"],
    "cloud": {"id": 2, "last_redefined": "___", "name": "cloud02"},
    "cloud_id": 2,
    "created_at": "___",
    "description": "Test allocation.",
    "id": 1,
    "is_self_schedule": False,
    "notification": {
        "assignment_id": 1,
        "fail": False,
        "five_days": False,
        "id": 1,
        "initial": False,
        "one_day": False,
        "pre": False,
        "pre_initial": False,
        "seven_days": False,
        "success": False,
        "three_days": False,
    },
    "ostype": OS_TYPE,
    "owner": "grafuls",
    "provisioned": False,
    "qinq": None,
    "ticket": "1",
    "validated": False,
    "vlan": {
        "gateway": "192.168.12.19",
        "id": 1,
        "ip_free": 510,
        "ip_range": "10.1.48.0/23",
        "netmask": "255.255.0.0",
        "vlan_id": 601,
    },
    "vlan_id": 1,
    "wipe": False,
}
ASSIGNMENT_1_UPDATE_REQUEST = {
    "cloud": "cloud04",
    "vlan": "603",
    "description": "Updated description.",
    "owner": "gonza",
    "ticket": "123",
    "qinq": "1",
    "wipe": "True",
    "ccuser": "gonza, grafuls",
}
ASSIGNMENT_1_UPDATE_RESPONSE = {
    "active": True,
    "boot_order": "foreman",
    "ccuser": ["gonza", "grafuls"],
    "cloud": {"id": 4, "last_redefined": "___", "name": "cloud04"},
    "cloud_id": 4,
    "created_at": "___",
    "description": "Updated description.",
    "id": 1,
    "is_self_schedule": False,
    "notification": {
        "assignment_id": 1,
        "fail": False,
        "five_days": False,
        "id": 1,
        "initial": False,
        "one_day": False,
        "pre": False,
        "pre_initial": False,
        "seven_days": False,
        "success": False,
        "three_days": False,
    },
    "ostype": OS_TYPE,
    "owner": "gonza",
    "provisioned": False,
    "qinq": 1,
    "ticket": "123",
    "validated": False,
    "vlan": {
        "gateway": "192.168.12.21",
        "id": 3,
        "ip_free": 1022,
        "ip_range": "10.1.54.0/22",
        "netmask": "255.255.252.0",
        "vlan_id": 603,
    },
    "vlan_id": 3,
    "wipe": True,
}
ASSIGNMENT_2_REQUEST = {
    "cloud": "cloud03",
    "vlan": "602",
    "description": "Test allocation.",
    "owner": "grafuls",
    "ticket": "2",
    "ccuser": "gonza",
}
ASSIGNMENT_2_RESPONSE = {
    "active": True,
    "boot_order": "foreman",
    "ccuser": ["gonza"],
    "cloud": {"id": 3, "last_redefined": "___", "name": "cloud03"},
    "cloud_id": 3,
    "created_at": "___",
    "description": "Test allocation.",
    "id": 2,
    "is_self_schedule": False,
    "notification": {
        "assignment_id": 2,
        "fail": False,
        "five_days": False,
        "id": 2,
        "initial": False,
        "one_day": False,
        "pre": False,
        "pre_initial": False,
        "seven_days": False,
        "success": False,
        "three_days": False,
    },
    "ostype": OS_TYPE,
    "owner": "grafuls",
    "provisioned": False,
    "qinq": None,
    "ticket": "2",
    "validated": False,
    "vlan": {
        "gateway": "192.168.12.20",
        "id": 2,
        "ip_free": 1022,
        "ip_range": "10.1.50.0/22",
        "netmask": "255.255.252.0",
        "vlan_id": 602,
    },
    "vlan_id": 2,
    "wipe": False,
}
SELF_ASSIGNMENT_1_REQUEST = {
    "cloud": "cloud04",
    "vlan": "603",
    "description": "Test allocation.",
    "owner": "grafuls",
    "ticket": "3",
    "ccuser": "gonza",
    "is_self_schedule": True,
}
SELF_ASSIGNMENT_1_RESPONSE = {
    "active": True,
    "boot_order": "foreman",
    "ccuser": ["gonza"],
    "cloud": {"id": 4, "last_redefined": "___", "name": "cloud04"},
    "cloud_id": 4,
    "created_at": "___",
    "description": "Test allocation.",
    "id": 3,
    "is_self_schedule": True,
    "notification": {
        "assignment_id": 3,
        "fail": False,
        "five_days": False,
        "id": 3,
        "initial": False,
        "one_day": False,
        "pre": False,
        "pre_initial": False,
        "seven_days": False,
        "success": False,
        "three_days": False,
    },
    "owner": "grafuls",
    "provisioned": False,
    "qinq": None,
    "ticket": "3",
    "validated": False,
    "vlan": {
        "gateway": "192.168.12.21",
        "id": 3,
        "ip_free": 1022,
        "ip_range": "10.1.54.0/22",
        "netmask": "255.255.252.0",
        "vlan_id": 603,
    },
    "vlan_id": 3,
    "wipe": False,
}

# --------------------
# SCHEDULES
# --------------------
start_date = datetime.now() - timedelta(days=1)
start_str = start_date.strftime("%Y-%m-%d")
end_date = start_date + timedelta(days=3650)
end_str = end_date.strftime("%Y-%m-%d")
end_date_future = start_date + timedelta(days=36500)
end_str_future = end_date_future.strftime("%Y-%m-%d")
build_end = start_date + timedelta(days=1)
build_end_str = build_end.strftime("%Y-%m-%d")

SELF_SCHEDULE_1_REQUEST = {
    "cloud": "cloud04",
    "hostname": "host2.example.com",
}
SELF_SCHEDULE_1_RESPONSE = {
    "assignment": {
        "active": True,
        "boot_order": "foreman",
        "ccuser": ["gonza"],
        "cloud": {
            "id": 4,
            "name": "cloud04",
        },
        "cloud_id": 4,
        "description": "Test allocation.",
        "id": 3,
        "is_self_schedule": True,
        "notification": {
            "assignment_id": 3,
            "fail": False,
            "five_days": False,
            "id": 3,
            "initial": False,
            "one_day": False,
            "pre": False,
            "pre_initial": False,
            "seven_days": False,
            "success": False,
            "three_days": False,
        },
        "ostype": OS_TYPE,
        "owner": "grafuls",
        "provisioned": False,
        "qinq": None,
        "ticket": "3",
        "validated": False,
        "vlan": {
            "gateway": "192.168.12.21",
            "id": 3,
            "ip_free": 1022,
            "ip_range": "10.1.54.0/22",
            "netmask": "255.255.252.0",
            "vlan_id": 603,
        },
        "vlan_id": 3,
        "wipe": False,
    },
    "assignment_id": 3,
    "build_end": None,
    "build_start": None,
    "end": "Tue, 06 Jun 2023 22:00:00 GMT",
    "host": {
        "blade": None,
        "bootmode": None,
        "broken": False,
        "build": False,
        "can_self_schedule": True,
        "cloud": {
            "id": 1,
            "name": "cloud01",
        },
        "cloud_id": 1,
        "default_cloud": {
            "id": 1,
            "name": "cloud01",
        },
        "default_cloud_id": 1,
        "host_type": "alias",
        "id": 2,
        "last_build": None,
        "model": "R640",
        "name": "host2.example.com",
        "rack": "h01",
        "retired": False,
        "switch_config_applied": False,
        "uloc": "u02",
        "validated": False,
    },
    "host_id": 2,
    "id": 3,
    "start": "Thu, 01 Jun 2023 22:00:00 GMT",
}
SELF_SCHEDULE_2_REQUEST = {
    "cloud": "cloud04",
    "hostname": "host3.example.com",
}
SELF_SCHEDULE_2_RESPONSE = {
    "assignment": {
        "active": True,
        "boot_order": "foreman",
        "ccuser": ["gonza"],
        "cloud": {
            "id": 4,
            "name": "cloud04",
        },
        "cloud_id": 4,
        "description": "Test allocation.",
        "id": 3,
        "is_self_schedule": True,
        "notification": {
            "assignment_id": 3,
            "fail": False,
            "five_days": False,
            "id": 3,
            "initial": False,
            "one_day": False,
            "pre": False,
            "pre_initial": False,
            "seven_days": False,
            "success": False,
            "three_days": False,
        },
        "ostype": OS_TYPE,
        "owner": "grafuls",
        "provisioned": False,
        "qinq": None,
        "ticket": "3",
        "validated": False,
        "vlan": {
            "gateway": "192.168.12.21",
            "id": 3,
            "ip_free": 1022,
            "ip_range": "10.1.54.0/22",
            "netmask": "255.255.252.0",
            "vlan_id": 603,
        },
        "vlan_id": 3,
        "wipe": False,
    },
    "assignment_id": 3,
    "build_end": None,
    "build_start": None,
    "end": "Tue, 06 Jun 2023 22:00:00 GMT",
    "host": {
        "blade": None,
        "bootmode": None,
        "broken": False,
        "build": False,
        "can_self_schedule": True,
        "cloud": {
            "id": 1,
            "name": "cloud01",
        },
        "cloud_id": 1,
        "default_cloud": {
            "id": 1,
            "name": "cloud01",
        },
        "default_cloud_id": 1,
        "host_type": "scalelab",
        "id": 3,
        "last_build": None,
        "model": "1029P",
        "name": "host3.example.com",
        "rack": "h01",
        "retired": False,
        "switch_config_applied": False,
        "uloc": "u03",
        "validated": False,
    },
    "host_id": 3,
    "id": 4,
    "start": "Thu, 01 Jun 2023 22:00:00 GMT",
}
SELF_SCHEDULE_3_REQUEST = {
    "cloud": "cloud04",
    "hostname": "host4.example.com",
}
SELF_SCHEDULE_3_RESPONSE = {
    "assignment": {
        "active": True,
        "boot_order": "foreman",
        "ccuser": ["gonza"],
        "cloud": {
            "id": 4,
            "name": "cloud04",
        },
        "cloud_id": 4,
        "description": "Test allocation.",
        "id": 3,
        "is_self_schedule": True,
        "notification": {
            "assignment_id": 3,
            "fail": False,
            "five_days": False,
            "id": 3,
            "initial": False,
            "one_day": False,
            "pre": False,
            "pre_initial": False,
            "seven_days": False,
            "success": False,
            "three_days": False,
        },
        "owner": "grafuls",
        "provisioned": False,
        "qinq": None,
        "ticket": "3",
        "validated": False,
        "vlan": {
            "gateway": "192.168.12.21",
            "id": 3,
            "ip_free": 1022,
            "ip_range": "10.1.54.0/22",
            "netmask": "255.255.252.0",
            "vlan_id": 603,
        },
        "vlan_id": 3,
        "wipe": False,
    },
    "assignment_id": 3,
    "build_end": None,
    "build_start": None,
    "end": "Tue, 06 Jun 2023 22:00:00 GMT",
    "host": {
        "broken": False,
        "build": False,
        "bootmode": None,
        "can_self_schedule": True,
        "cloud": {
            "id": 1,
            "name": "cloud01",
        },
        "cloud_id": 1,
        "default_cloud": {
            "id": 1,
            "name": "cloud01",
        },
        "default_cloud_id": 1,
        "host_type": "alias",
        "id": 4,
        "last_build": None,
        "model": "R640",
        "name": "host4.example.com",
        "retired": False,
        "switch_config_applied": False,
        "validated": False,
    },
    "host_id": 4,
    "id": 3,
    "start": "Thu, 01 Jun 2023 22:00:00 GMT",
}
SELF_SCHEDULE_NON_REQUEST = {
    "cloud": "cloud04",
    "hostname": "host11.example.com",
}
SCHEDULE_1_REQUEST = {
    "cloud": "cloud02",
    "hostname": "host2.example.com",
    "start": f"{start_str} 22:00",
    "end": f"{end_str} 22:00",
}
SCHEDULE_1_RESPONSE = {
    "assignment": {
        "active": True,
        "boot_order": "foreman",
        "ccuser": ["gonza"],
        "cloud": {
            "id": 2,
            "last_redefined": "Tue, 07 Mar 2023 11:36:53 GMT",
            "name": "cloud02",
        },
        "cloud_id": 2,
        "created_at": "Tue, 07 Mar 2023 11:36:53 GMT",
        "description": "Test allocation.",
        "id": 1,
        "is_self_schedule": False,
        "notification": {
            "assignment_id": 1,
            "fail": False,
            "five_days": False,
            "id": 1,
            "initial": False,
            "one_day": False,
            "pre": False,
            "pre_initial": False,
            "seven_days": False,
            "success": False,
            "three_days": False,
        },
        "ostype": "RHEL 7",
        "owner": "grafuls",
        "provisioned": False,
        "qinq": None,
        "ticket": "1",
        "validated": False,
        "vlan": {
            "gateway": "192.168.12.19",
            "id": 1,
            "ip_free": 510,
            "ip_range": "10.1.48.0/23",
            "netmask": "255.255.0.0",
            "vlan_id": 601,
        },
        "vlan_id": 1,
        "wipe": False,
    },
    "assignment_id": 1,
    "build_end": None,
    "build_start": None,
    "created_at": "Tue, 07 Mar 2023 11:36:53 GMT",
    "end": "Tue, 18 Mar 2042 22:00:00 GMT",
    "host": {
        "blade": None,
        "bootmode": None,
        "broken": False,
        "build": False,
        "can_self_schedule": True,
        "cloud": {
            "id": 1,
            "last_redefined": "Tue, 07 Mar 2023 11:36:53 GMT",
            "name": "cloud01",
        },
        "cloud_id": 1,
        "created_at": "Tue, 07 Mar 2023 11:36:53 GMT",
        "default_cloud": {
            "id": 1,
            "last_redefined": "Tue, 07 Mar 2023 11:36:53 GMT",
            "name": "cloud01",
        },
        "default_cloud_id": 1,
        "host_type": "alias",
        "id": 2,
        "last_build": None,
        "model": "R640",
        "name": "host2.example.com",
        "rack": "h01",
        "retired": False,
        "switch_config_applied": False,
        "uloc": "u02",
        "validated": False,
    },
    "host_id": 2,
    "id": 1,
    "start": "Sat, 04 Feb 2023 22:00:00 GMT",
}
SCHEDULE_2_REQUEST = {
    "cloud": "cloud03",
    "hostname": "host3.example.com",
    "start": f"{start_str} 22:00",
    "end": f"{end_str_future} 22:00",
}
SCHEDULE_2_RESPONSE = {
    "assignment": {
        "active": True,
        "boot_order": "foreman",
        "ccuser": ["gonza"],
        "cloud": {
            "id": 3,
            "last_redefined": "Tue, 07 Mar 2023 11:36:53 GMT",
            "name": "cloud03",
        },
        "cloud_id": 3,
        "created_at": "Tue, 07 Mar 2023 11:36:53 GMT",
        "description": "Test allocation.",
        "id": 2,
        "is_self_schedule": False,
        "notification": {
            "assignment_id": 2,
            "fail": False,
            "five_days": False,
            "id": 2,
            "initial": False,
            "one_day": False,
            "pre": False,
            "pre_initial": False,
            "seven_days": False,
            "success": False,
            "three_days": False,
        },
        "ostype": "RHEL 7",
        "owner": "grafuls",
        "provisioned": False,
        "qinq": None,
        "ticket": "2",
        "validated": False,
        "vlan": {
            "gateway": "192.168.12.20",
            "id": 2,
            "ip_free": 1022,
            "ip_range": "10.1.50.0/22",
            "netmask": "255.255.252.0",
            "vlan_id": 602,
        },
        "vlan_id": 2,
        "wipe": False,
    },
    "assignment_id": 2,
    "build_end": None,
    "build_start": None,
    "created_at": "Tue, 07 Mar 2023 11:36:53 GMT",
    "end": "Fri, 18 Mar 2044 22:00:00 GMT",
    "host": {
        "blade": None,
        "bootmode": None,
        "broken": False,
        "build": False,
        "can_self_schedule": True,
        "cloud": {
            "id": 1,
            "last_redefined": "Tue, 07 Mar 2023 11:36:53 GMT",
            "name": "cloud01",
        },
        "cloud_id": 1,
        "created_at": "Tue, 07 Mar 2023 11:36:53 GMT",
        "default_cloud": {
            "id": 1,
            "last_redefined": "Tue, 07 Mar 2023 11:36:53 GMT",
            "name": "cloud01",
        },
        "default_cloud_id": 1,
        "host_type": "scalelab",
        "id": 3,
        "last_build": None,
        "model": "1029P",
        "name": "host3.example.com",
        "rack": "h01",
        "retired": False,
        "switch_config_applied": False,
        "uloc": "u03",
        "validated": False,
    },
    "host_id": 3,
    "id": 2,
    "start": "Sat, 04 Feb 2023 22:00:00 GMT",
}
SCHEDULE_1_UPDATE_REQUEST = {
    "start": f"{start_str}T22:00",
    "end": f"{end_str}T22:00",
    "build_start": f"{start_str}T22:00",
    "build_end": f"{build_end_str}T22:00",
}
INITIAL_MESSAGE = "\nGreetings Citizen,\n\nYou've been allocated a new environment!\n\ncloud_info1\n\n(Details)  \nhttps://quads.scalelab.example.com/assignments/#cloud1\n\nYou can view your machine list, duration and other  \ndetails above.\n\nYou can also view/manage your hosts via Foreman:\n\nhttp://foreman.example.com/hosts/\n\nUsername: cloud1  \nPassword: rdu2@ticket1\n\nFor additional information regarding system usage  \nplease see the following documentation:\n\nhttps://quads.scalelab.example.com/FAQ/  \nhttps://quads.scalelab.example.com/Usage/\n\nPerf/Scale DevOps Team"
INITIAL_SUBJECT = "New QUADS Assignment Allocated - cloud1 ticket1"

FUTURE_INITIAL_MESSAGE = "\nGreetings Citizen,\n\nYou've been allocated a new future environment!\n\nThe environment is not yet ready for use but you are being notified ahead of time  \nthat it is being prepared.\n\ncloud_info1\n\nWhen your environment is ready and your hardware/network has  \npassed automated validation it will be released to you.\n\nYou'll receive another email with environment-specific  \ninformation and additional system details when it's ready.  \n\nBefore this happens a future schedule will be entered and  \ncommunicated to you via your service ticket/request.  \n\nAfterwards, when the time comes a series of automated tests and  \nvalidation phases will occur to make sure your systems/network  \nare in their final, desired state before being ready to use.\n\nFor additional information regarding the Scale Lab usage  \nplease see the following documentation:\n\nhttps://quads.scalelab.example.com/FAQ/  \nhttps://quads.scalelab.example.com/Usage/\n\nPerf/Scale DevOps Team"
FUTURE_INITIAL_SUBJECT = "New QUADS Assignment Defined for the Future: cloud1 - ticket1"

FUTURE_MESSAGE = "\nThis is a message to alert you that in 1 days  \nyour allocated environment:\n\ncloud_info1\n\n(Details)\n\nhttps://quads.scalelab.example.com/assignments/#cloud1\n\nwill change.  As host schedules are activated some  \nhosts will automatically be reprovisioned and moved to  \nyour environment.  This could also mean that one or more  \nhosts will evacuate your environment ahead of others.\n\nQUADS has detected a change in schedule to the following  \nhosts:\n\n\nhost1\n\nhost2\n\n\nFor additional information regarding the Scale Lab usage  \nplease see the following documentation:\n\nhttps://quads.scalelab.example.com/FAQ/  \nhttps://quads.scalelab.example.com/Usage/\n\nThank you for your attention.\n\nPerf/Scale DevOps Team"
FUTURE_SUBJECT = "QUADS upcoming assignment notification - cloud1 - ticket1"

MESSAGE = "\nThis is a message to alert you that in 1 days  \nyour allocated environment:\n\ncloud_info1\n\n(Detail)\n\nhttps://quads.scalelab.example.com/assignments/#cloud1\n\nwill have some or all of the hosts expire.  The following  \nhosts will automatically be reprovisioned and returned to  \nthe pool of available hosts.\n\n\nhost1  \n\nhost2  \n\n\n\n\n\n\n\n\nIf you have already submitted an extension you can disregard  \nthis message, our system will continue to send out expiration  \nnotices until the actual extension is executed.\n\n\n\nDocs:\n\nhttps://quads.scalelab.example.com/FAQ/  \nhttps://quads.scalelab.example.com/Usage/\n\nThank you for your attention.\n\nPerf/Scale DevOps Team\n"
SUBJECT = "QUADS upcoming expiration for cloud1 - ticket1"

CC_USERS = [
    "someuser@example.com",
    "someuser@example.com",
    "someuser@example.com",
    "someuser@example.com",
]
OWNER = "owner1"
POST_TEXT = "QUADS: cloud_info1 is now active, choo choo! - https://quads.scalelab.example.com/assignments/#cloud1 -  owner1 someuser@example.com, someuser@example.com, someuser@example.com, someuser@example.com"
