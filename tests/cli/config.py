CLOUD = "cloud99"
DEFAULT_CLOUD = "cloud01"
DEFINE_CLOUD = "cloud02"
REMOVE_CLOUD = "cloud03"
MOD_CLOUD = "cloud04"
FREE_CLOUD = "cloud05"
HOST1 = "host1.example.com"
HOST2 = "host2.example.com"
DEFINE_HOST = "define.example.com"
MODEL1 = "r640"
MODEL2 = "r930"
HOST_TYPE = "scalelab"
IFNAME1 = "em1"
IFNAME2 = "em2"
IFMAC1 = "A0:B1:C2:D3:E4:F5"
IFMAC2 = "A0:B1:C2:D3:E4:F6"
IFIP1 = "10.0.0.1"
IFIP2 = "10.0.0.2"
IFPORT1 = "et-4/0/0"
IFPORT2 = "et-4/0/1"
IFBIOSID1 = "Nic1.Interfaces.1"
IFBIOSID2 = "Nic1.Interfaces.2"
IFSPEED = 1000
IFVENDOR1 = "Intel"
IFVENDOR2 = "Melanox"
OS_TYPE = "RHEL 7"

RESPONSE_LS = f"""INFO     tests.cli.test_base:cli.py:418 {HOST1}"""

RESPONSE_DEF_HOST = "Successful request"
RESPONSE_RM = "INFO     test_log:cli.py:181 Successfully removed\n"


class NetcatStub:
    def __init__(self, ip, port=22, loop=None):
        pass

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def connect(self):
        pass

    async def close(self):
        pass

    async def write(self, data):
        pass

    async def health_check(self):
        self.__sizeof__()
        return True


class SSHHelperStub(object):
    def __init__(self, _host, _user=None, _password=None):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def connect(self):
        pass

    def disconnect(self):
        pass

    def run_cmd(self, cmd=None):
        return True, []

    def copy_ssh_key(self, _ssh_key):
        pass


def switch_config_stub(host=None, old_cloud=None, new_cloud=None):
    return True
