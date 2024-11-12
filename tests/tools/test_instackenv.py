#!/usr/bin/env python3
import os

from quads.config import Config
from quads.tools.make_instackenv_json import main
from tests.tools.test_base import TestBase


class TestInstackenv(TestBase):
    def test_make_instackenv_json(self):
        Config.__setattr__("openstack_management", True)
        Config.__setattr__("openshift_management", True)
        Config.__setattr__("foreman_unavailable", True)
        Config.__setattr__("json_web_path", os.path.join(os.path.dirname(__file__), "../artifacts/"))
        main()
        with open(
            os.path.join(os.path.dirname(__file__), "../artifacts/cloud99_instackenv.json")
        ) as cloud99_instackenv:
            instackenv_list = list(cloud99_instackenv.readlines())
            instackenv_list = [line.strip() for line in instackenv_list]
        with open(
            os.path.join(os.path.dirname(__file__), "../artifacts/cloud99_ocpinventory.json")
        ) as cloud99_ocpinventory:
            ocpinventory_list = list(cloud99_ocpinventory.readlines())
            ocpinventory_list = [line.strip() for line in ocpinventory_list]
        with open(os.path.join(os.path.dirname(__file__), "fixtures/cloud99_env.json")) as cloud99_instackenv:
            fixtures_list = list(cloud99_instackenv.readlines())
            fixtures_list = [line.strip() for line in fixtures_list]
        assert instackenv_list == fixtures_list
        assert ocpinventory_list == fixtures_list
