from typing import List, Optional
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBasic, HTTPBearer
from fastapi_mcp import MCPRouter, MCPApp
from pydantic import BaseModel, Field

# Initialize FastAPI MCP app
app = MCPApp()
router = MCPRouter()

# Security schemes
security_basic = HTTPBasic()
security_bearer = HTTPBearer()


# Base Models
class Error(BaseModel):
    code: int = Field(..., example=400)
    message: str = Field(..., example="Something went horribly wrong.")


class Cloud(BaseModel):
    name: str = Field(..., example="cloud12")
    last_redefined: Optional[str] = Field(None, example="1984-02-02")


class CloudSummary(BaseModel):
    name: str = Field(..., example="cloud12")
    count: Optional[int] = Field(None, example=10)
    description: Optional[str] = Field(None, example="Short description here")
    owner: Optional[str] = Field(None, example="jsbach")
    ticket: Optional[str] = Field(None, example="2122")
    ccuser: Optional[List[str]] = Field(None, example=["edroste", "kgodel"])
    provisioned: Optional[bool] = Field(None, example=True)
    validated: Optional[bool] = Field(None, example=True)


class Disk(BaseModel):
    disk_id: Optional[int] = Field(None, example=1)
    disk_type: Optional[str] = Field(None, example="nvme")
    size_gb: Optional[int] = Field(None, example=2000)
    count: Optional[int] = Field(None, example=10)
    host_id: Optional[int] = Field(None, example=10)


class Memory(BaseModel):
    id: Optional[int] = Field(None, example=12)
    size_gb: int
    handle: str
    host_id: int


class Processor(BaseModel):
    id: Optional[int] = Field(None, example=12)
    handle: Optional[str] = Field(None, example="CoreI7")
    vendor: Optional[str] = Field(None, example="Intel")
    product: Optional[str] = Field(None, example="i7")
    cores: Optional[int] = Field(None, example=20)
    threads: Optional[int] = Field(None, example=20)
    host_id: Optional[int] = Field(None, example=10)


class Interface(BaseModel):
    id: Optional[int] = Field(None, example=12)
    name: Optional[str] = Field(None, example="em1")
    bios_id: Optional[str] = Field(None, example="nic1")
    mac_address: Optional[str] = Field(None, example="aa:00:bb:11:cc:22")
    switch_ip: Optional[str] = Field(None, example="10.1.1.18")
    switch_port: Optional[str] = Field(None, example="xt-0-0/1")
    speed: Optional[int] = Field(None, example=1000)
    vendor: Optional[str] = Field(None, example="Intel")
    pxe_boot: Optional[bool] = Field(None, example=True)
    maintenance: Optional[bool] = Field(None, example=False)
    host_id: Optional[int] = Field(None, example=10)


class Host(BaseModel):
    id: Optional[int] = Field(None, example=12)
    name: str = Field(..., example="host.example.com")
    model: Optional[str] = Field(None, example="r640")
    host_type: Optional[str] = Field(None, example="vendor")
    build: Optional[bool] = Field(None, example=True)
    validated: Optional[bool] = Field(None, example=True)
    switch_config_applied: Optional[bool] = Field(None, example=True)
    broken: Optional[bool] = Field(None, example=True)
    retired: Optional[bool] = Field(None, example=True)
    can_self_schedule: Optional[bool] = Field(None, example=False)
    last_build: Optional[str] = Field(None, example="2022-02-02")
    cloud_id: Optional[int] = Field(None, example=12)
    default_cloud_id: Optional[int] = Field(None, example=1)
    interfaces: Optional[List[Interface]] = None
    disks: Optional[List[Disk]] = None
    memory: Optional[List[Memory]] = None
    processors: Optional[List[Processor]] = None


class Schedule(BaseModel):
    start: Optional[str] = Field(None, example="2022-02-02T22:00")
    end: Optional[str] = Field(None, example="2022-04-02T22:00")
    build_start: Optional[str] = Field(None, example="2022-02-02T22:00")
    build_end: Optional[str] = Field(None, example="2022-04-02T22:00")
    assignment_id: Optional[int] = Field(None, example=12)
    host_id: Optional[int] = Field(None, example=1)


class Assignment(BaseModel):
    active: Optional[bool] = Field(None, example=True)
    provisioned: Optional[bool] = Field(None, example=True)
    validated: Optional[bool] = Field(None, example=True)
    is_self_schedule: Optional[bool] = Field(None, example=False)
    description: Optional[str] = Field(None, example="Short description here")
    owner: Optional[str] = Field(None, example="jsbach")
    ticket: Optional[str] = Field(None, example="2122")
    qinq: Optional[int] = Field(None, example=1)
    wipe: Optional[bool] = Field(None, example=True)
    ccuser: Optional[List[str]] = Field(None, example=["edroste", "kgodel"])
    cloud_id: Optional[int] = Field(None, example=12)
    vlan_id: Optional[int] = Field(None, example=12)


class Move(BaseModel):
    host: str = Field(..., example="host.example.com")
    new: str = Field(..., example="cloud09")
    current: str = Field(..., example="cloud01")


class Version(BaseModel):
    result: str = Field(..., example="Quads version 2.0 Max")


class Vlan(BaseModel):
    gateway: Optional[str] = Field(None, example="10.1.18.8")
    ip_free: Optional[int] = Field(None, example=256)
    ip_range: Optional[str] = None
    netmask: Optional[str] = Field(None, example="255.255.255.255")
    vlan_id: Optional[int] = Field(None, example=601)


# Additional Models
class AuthResponse(BaseModel):
    auth_token: str = Field(..., example="7h1515aV3rYkr1p71k70k3n")


class RegisterRequest(BaseModel):
    email: str = Field(..., example="quads@redhat.com")
    password: str = Field(..., example="7h1515aV3rYkr1p71k70k3n")


class RegisterResponse(BaseModel):
    status: int = Field(..., example=200)
    message: str = Field(..., example="Successful login")
    auth_token: str = Field(..., example="7h1515aV3rYkr1p71k70k3n")


class Notification(BaseModel):
    fail: Optional[bool] = Field(None, example=False)
    success: Optional[bool] = Field(None, example=False)
    initial: Optional[bool] = Field(None, example=False)
    pre_initial: Optional[bool] = Field(None, example=False)
    pre: Optional[bool] = Field(None, example=False)
    one_day: Optional[bool] = Field(None, example=False)
    three_days: Optional[bool] = Field(None, example=False)
    five_days: Optional[bool] = Field(None, example=False)
    seven_days: Optional[bool] = Field(None, example=False)
    assignment: Optional[int] = Field(None, example=12)


# Routes
@router.get("/version/", response_model=Version, tags=["Other"])
async def get_version():
    """Returns Quads version"""
    return {"result": "Quads version 2.0 Max"}


@router.get("/clouds/", response_model=List[Cloud], tags=["Clouds"])
async def get_clouds():
    """Returns a list with all the defined clouds"""
    # Implementation needed
    pass


@router.post("/clouds/", status_code=201, tags=["Clouds"])
async def create_cloud(cloud: Cloud, token: HTTPBearer = Security(security_bearer)):
    """Add a new cloud"""
    # Implementation needed
    pass


@router.get("/clouds/free/", response_model=List[Cloud], tags=["Clouds"])
async def get_free_clouds():
    """Returns all free clouds that are available for new assignments"""
    # Implementation needed
    pass


@router.get("/clouds/summary/", response_model=CloudSummary, tags=["Clouds"])
async def get_clouds_summary():
    """Returns all clouds summary"""
    # Implementation needed
    pass


@router.get("/hosts/", response_model=List[Host], tags=["Hosts"])
async def get_hosts(
    name: Optional[str] = None,
    model: Optional[str] = None,
    host_type: Optional[str] = None,
    build: Optional[bool] = None,
    validated: Optional[bool] = None,
    switch_config_applied: Optional[bool] = None,
    broken: Optional[bool] = None,
    retired: Optional[bool] = None,
    last_build: Optional[str] = None,
    created_on: Optional[str] = None,
):
    """Returns a list with all the defined hosts"""
    # Implementation needed
    pass


@router.post("/hosts/", status_code=201, tags=["Hosts"])
async def create_host(host: Host, token: HTTPBearer = Security(security_bearer)):
    """Add a new host"""
    # Implementation needed
    pass


# Authentication Routes
@router.post("/login/", response_model=AuthResponse, tags=["Auth"])
async def login(credentials: HTTPBasic = Depends(security_basic)):
    """Login endpoint with Basic Auth that returns token for Bearer Auth"""
    # Implementation needed
    pass


@router.post("/logout/", tags=["Auth"])
async def logout(token: HTTPBearer = Security(security_bearer)):
    """Logout endpoint for blacklisting authentication token"""
    # Implementation needed
    pass


@router.post("/register/", response_model=RegisterResponse, tags=["Auth"])
async def register(request: RegisterRequest):
    """Register new users"""
    # Implementation needed
    pass


# Assignment Routes
@router.get("/assignments/active/", response_model=List[Assignment], tags=["Assignments"])
async def get_active_assignments():
    """Returns a list with all active assignments"""
    # Implementation needed
    pass


@router.get("/assignments/active/{cloud_name}/", response_model=List[Assignment], tags=["Assignments"])
async def get_active_assignments_by_cloud(cloud_name: str):
    """Returns a list with all active assignments for a specific cloud"""
    # Implementation needed
    pass


@router.post("/assignments/", status_code=201, tags=["Assignments"])
async def create_assignment(assignment: Assignment, token: HTTPBearer = Security(security_bearer)):
    """Add a new assignment"""
    # Implementation needed
    pass


@router.post("/assignments/self/", status_code=201, tags=["Assignments"])
async def create_self_assignment(assignment: Assignment, token: HTTPBearer = Security(security_bearer)):
    """Create a new self assignment"""
    # Implementation needed
    pass


@router.post("/assignments/terminate/{assignment_id}/", tags=["Assignments"])
async def terminate_assignment(assignment_id: str, token: HTTPBearer = Security(security_bearer)):
    """Terminate an assignment by id"""
    # Implementation needed
    pass


# Schedule Routes
@router.get("/schedules/", response_model=List[Schedule], tags=["Schedules"])
async def get_schedules():
    """Returns a list with all the defined schedules"""
    # Implementation needed
    pass


@router.post("/schedules/", status_code=201, tags=["Schedules"])
async def create_schedule(schedule: Schedule, token: HTTPBearer = Security(security_bearer)):
    """Add a new schedule"""
    # Implementation needed
    pass


@router.get("/schedules/{schedule_id}/", response_model=Schedule, tags=["Schedules"])
async def get_schedule(schedule_id: str):
    """Returns a schedule by id"""
    # Implementation needed
    pass


@router.patch("/schedules/{schedule_id}/", response_model=Schedule, tags=["Schedules"])
async def update_schedule(schedule_id: str, schedule: Schedule, token: HTTPBearer = Security(security_bearer)):
    """Update an existing schedule"""
    # Implementation needed
    pass


@router.delete("/schedules/{schedule_id}/", tags=["Schedules"])
async def delete_schedule(schedule_id: str, token: HTTPBearer = Security(security_bearer)):
    """Delete schedule by id"""
    # Implementation needed
    pass


# Notification Routes
@router.get("/notifications/", response_model=List[Notification], tags=["Notifications"])
async def get_notifications():
    """Returns a list with all the defined notifications"""
    # Implementation needed
    pass


@router.get("/notifications/{notification_id}/", response_model=Notification, tags=["Notifications"])
async def get_notification(notification_id: str):
    """Returns a notification by id"""
    # Implementation needed
    pass


@router.patch("/notifications/{notification_id}/", status_code=201, tags=["Notifications"])
async def update_notification(
    notification_id: str, notification: Notification, token: HTTPBearer = Security(security_bearer)
):
    """Update an existing notification"""
    # Implementation needed
    pass


# Available Routes
@router.get("/available/", response_model=List[Host], tags=["Available"])
async def get_available_hosts(start: Optional[str] = None, end: Optional[str] = None, cloud: Optional[str] = None):
    """Returns a list of available hosts"""
    # Implementation needed
    pass


@router.get("/available/{hostname}/", response_model=List[Host], tags=["Available"])
async def check_host_availability(hostname: str, start: Optional[str] = None, end: Optional[str] = None):
    """Returns a boolean for whether the host is available or not"""
    # Implementation needed
    pass


# Moves Routes
@router.get("/moves/", response_model=List[Move], tags=["Moves"])
async def get_moves(date: Optional[str] = None):
    """Returns a list of hosts that are transitioning with the source and target clouds"""
    # Implementation needed
    pass


# VLAN Routes
@router.get("/vlans/", response_model=List[Vlan], tags=["Vlans"])
async def get_vlans():
    """Returns a list with all the defined vlans"""
    # Implementation needed
    pass


@router.post("/vlans/", status_code=201, tags=["Vlans"])
async def create_vlan(vlan: Vlan, token: HTTPBearer = Security(security_bearer)):
    """Add a new vlan"""
    # Implementation needed
    pass


@router.get("/vlans/free/", response_model=List[Vlan], tags=["Vlans"])
async def get_free_vlans():
    """Returns a list with all the free vlans"""
    # Implementation needed
    pass


@router.get("/vlans/{vlan_id}/", response_model=Vlan, tags=["Vlans"])
async def get_vlan(vlan_id: int):
    """Returns a detail of a specific vlan by id"""
    # Implementation needed
    pass


@router.patch("/vlans/{vlan_id}/", response_model=Vlan, tags=["Vlans"])
async def update_vlan(vlan_id: int, vlan: Vlan, token: HTTPBearer = Security(security_bearer)):
    """Update an existing vlan"""
    # Implementation needed
    pass


@router.delete("/vlans/{vlan_id}/", tags=["Vlans"])
async def delete_vlan(vlan_id: int, token: HTTPBearer = Security(security_bearer)):
    """Delete vlan by vlan id"""
    # Implementation needed
    pass


# Cloud Routes
@router.delete("/clouds/{cloudName}/", tags=["Clouds"])
async def delete_cloud(cloudName: str, token: HTTPBearer = Security(security_bearer)):
    """Delete cloud by cloud name"""
    # Implementation needed
    pass


@router.patch("/clouds/{cloudName}/", response_model=Cloud, tags=["Clouds"])
async def update_cloud(cloudName: str, cloud: Cloud, token: HTTPBearer = Security(security_bearer)):
    """Update an existing cloud"""
    # Implementation needed
    pass


# Host Routes
@router.get("/hosts/{hostName}/", response_model=Host, tags=["Hosts"])
async def get_host(hostName: str):
    """Returns a host by name"""
    # Implementation needed
    pass


@router.patch("/hosts/{hostName}/", response_model=Host, tags=["Hosts"])
async def update_host(hostName: str, host: Host, token: HTTPBearer = Security(security_bearer)):
    """Update an existing host"""
    # Implementation needed
    pass


@router.delete("/hosts/{hostName}/", tags=["Hosts"])
async def delete_host(hostName: str, token: HTTPBearer = Security(security_bearer)):
    """Delete host by host name"""
    # Implementation needed
    pass


# Host Components Routes
@router.get("/hosts/{hostName}/memory/", response_model=List[Memory], tags=["Memory"])
async def get_host_memory(hostName: str):
    """Returns a host memory by host name"""
    # Implementation needed
    pass


@router.get("/hosts/{hostName}/processors/", response_model=List[Processor], tags=["Processors"])
async def get_host_processors(hostName: str):
    """Returns a host processors by host name"""
    # Implementation needed
    pass


@router.get("/hosts/{hostName}/disks/", response_model=List[Disk], tags=["Disks"])
async def get_host_disks(hostName: str):
    """Returns a host disks by host name"""
    # Implementation needed
    pass


@router.get("/hosts/{hostName}/interfaces/", response_model=List[Interface], tags=["Interfaces"])
async def get_host_interfaces(hostName: str):
    """Returns a host interfaces by host name"""
    # Implementation needed
    pass


# Interface Routes
@router.get("/interfaces/", response_model=List[Interface], tags=["Interfaces"])
async def get_interfaces():
    """Returns a list of all interfaces"""
    # Implementation needed
    pass


@router.get("/interfaces/{interface_id}/", response_model=Interface, tags=["Interfaces"])
async def get_interface(interface_id: str):
    """Returns a specific interface for a specific interface id"""
    # Implementation needed
    pass


@router.post("/interfaces/{hostName}/", response_model=Interface, tags=["Interfaces"])
async def create_interface(hostName: str, interface: Interface, token: HTTPBearer = Security(security_bearer)):
    """Create a host interface definition"""
    # Implementation needed
    pass


@router.patch("/interfaces/{hostName}/", response_model=Interface, tags=["Interfaces"])
async def update_interface(hostName: str, interface: Interface, token: HTTPBearer = Security(security_bearer)):
    """Update an existing host interface definitions"""
    # Implementation needed
    pass


@router.delete("/interfaces/{hostName}/{ifName}/", tags=["Interfaces"])
async def delete_interface(hostName: str, ifName: str, token: HTTPBearer = Security(security_bearer)):
    """Delete interface on host by interface id"""
    # Implementation needed
    pass


# Memory Routes
@router.get("/memory/", response_model=List[Memory], tags=["Memory"])
async def get_memory():
    """Returns a list of all memory"""
    # Implementation needed
    pass


@router.get("/memory/{memory_id}/", response_model=Memory, tags=["Memory"])
async def get_memory_by_id(memory_id: str):
    """Returns a specific memory for a specific memory id"""
    # Implementation needed
    pass


@router.delete("/memory/{memory_id}/", tags=["Memory"])
async def delete_memory(memory_id: str, token: HTTPBearer = Security(security_bearer)):
    """Delete memory on host by memory id"""
    # Implementation needed
    pass


@router.post("/memory/{hostName}/", response_model=Memory, tags=["Memory"])
async def create_memory(hostName: str, memory: Memory, token: HTTPBearer = Security(security_bearer)):
    """Create a host memory definition"""
    # Implementation needed
    pass


# Processor Routes
@router.get("/processors/", response_model=Processor, tags=["Processors"])
async def get_processors():
    """Returns a list of all processors"""
    # Implementation needed
    pass


@router.get("/processors/{processor_id}/", response_model=Processor, tags=["Processors"])
async def get_processor(processor_id: str):
    """Returns a specific processor for a specific processor id"""
    # Implementation needed
    pass


@router.delete("/processors/{processor_id}/", tags=["Processors"])
async def delete_processor(processor_id: str, token: HTTPBearer = Security(security_bearer)):
    """Delete processor on host by processor id"""
    # Implementation needed
    pass


@router.post("/processors/{hostName}/", response_model=Processor, tags=["Processors"])
async def create_processor(hostName: str, processor: Processor, token: HTTPBearer = Security(security_bearer)):
    """Create a host processors definition"""
    # Implementation needed
    pass


# Disk Routes
@router.get("/disks/", response_model=List[Disk], tags=["Disks"])
async def get_disks():
    """Returns all disks"""
    # Implementation needed
    pass


@router.get("/disks/{disk_id}/", response_model=Disk, tags=["Disks"])
async def get_disk(disk_id: str):
    """Returns a specific disk by disc id"""
    # Implementation needed
    pass


@router.delete("/disks/{disk_id}/", tags=["Disks"])
async def delete_disk(disk_id: str, token: HTTPBearer = Security(security_bearer)):
    """Delete disk on host by disk id"""
    # Implementation needed
    pass


@router.post("/disks/{hostName}/", response_model=Disk, tags=["Disks"])
async def create_disk(hostName: str, disk: Disk, token: HTTPBearer = Security(security_bearer)):
    """Create a host disk definition"""
    # Implementation needed
    pass


@router.patch("/disks/{hostName}/", response_model=Disk, tags=["Disks"])
async def update_disk(hostName: str, disk: Disk, token: HTTPBearer = Security(security_bearer)):
    """Update an existing host disks definitions"""
    # Implementation needed
    pass


# Add the router to the app
app.include_router(router, prefix="/api/v3")

# Add OpenAPI tags metadata
app.openapi_tags = [
    {"name": "Auth", "description": "Everything about authentication"},
    {"name": "Clouds", "description": "Operations about clouds"},
    {"name": "Assignments", "description": "Operations about assignments"},
    {"name": "Hosts", "description": "Operations about hosts"},
    {"name": "Interfaces", "description": "Operations about interfaces"},
    {"name": "Disks", "description": "Operations about disks"},
    {"name": "Memory", "description": "Operations about memory"},
    {"name": "Processors", "description": "Operations about processors"},
    {"name": "Vlans", "description": "Operations about vlans"},
    {"name": "Schedules", "description": "Operations about schedules"},
    {"name": "Available", "description": "Operations about hosts availability"},
    {"name": "Moves", "description": "Operations about hosts transitions"},
    {"name": "Other", "description": "Other operations"},
]

# Configure app metadata
app.title = "QUADS"
app.description = """
QUADS automates the future scheduling, end-to-end provisioning and delivery of bare-metal servers and networks.

This is its REST API implementation.

Some useful links:
- [Quads repository](https://github.com/redhat-performance/quads)
- [Quads blog](https://quads.dev)
"""
app.version = "3.0.0"


# Error handling
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return {"code": exc.status_code, "message": str(exc.detail)}


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return {"code": 500, "message": str(exc)}
