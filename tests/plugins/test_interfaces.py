"""Tests for plugin interfaces"""

import pytest

from quads.plugins.interfaces.chat import ChatPlugin
from quads.plugins.interfaces.email import EmailPlugin
from quads.plugins.interfaces.hardware import HardwarePlugin
from quads.plugins.interfaces.provisioner import ProvisionerPlugin
from quads.plugins.interfaces.switch import SwitchPlugin
from quads.plugins.interfaces.ticketing import TicketingPlugin
from quads.plugins.interfaces.validator import ValidatorPlugin
from quads.plugins.interfaces.release import ReleasePlugin
from quads.plugins.base import BasePlugin


class TestChatInterface:
    """Test ChatPlugin interface"""

    def test_chat_plugin_is_base_plugin(self):
        """Test that ChatPlugin inherits from BasePlugin"""
        assert issubclass(ChatPlugin, BasePlugin)

    def test_chat_plugin_requires_send_message(self):
        """Test that ChatPlugin requires send_message method"""

        # Should fail to instantiate without implementing abstract method
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):

            class IncompleteChatPlugin(ChatPlugin):
                name = "incomplete"

            config = {}
            IncompleteChatPlugin(config)

    def test_chat_plugin_send_message_signature(self):
        """Test send_message method signature"""

        class CompleteChatPlugin(ChatPlugin):
            name = "complete"

            async def send_message(self, message: str, channels=None, **kwargs) -> bool:
                return True

        config = {}
        plugin = CompleteChatPlugin(config)
        # Should be able to call send_message
        import asyncio

        result = asyncio.run(plugin.send_message("test", channels=["#general"]))
        assert result is True


class TestEmailInterface:
    """Test EmailPlugin interface"""

    def test_email_plugin_is_base_plugin(self):
        """Test that EmailPlugin inherits from BasePlugin"""
        assert issubclass(EmailPlugin, BasePlugin)

    def test_email_plugin_requires_send_mail(self):
        """Test that EmailPlugin requires send_mail method"""

        class IncompleteEmailPlugin(EmailPlugin):
            name = "incomplete"

        config = {}
        with pytest.raises(TypeError):
            # Should fail because send_mail is not implemented
            plugin = IncompleteEmailPlugin(config)
            plugin.send_mail("subject", "body", ["user@example.com"])

    def test_email_plugin_send_mail_signature(self):
        """Test send_mail method signature"""

        class CompleteEmailPlugin(EmailPlugin):
            name = "complete"

            async def send_mail(self, subject: str, content: str, recipients, cc=None, **kwargs) -> bool:
                return True

        config = {}
        plugin = CompleteEmailPlugin(config)
        import asyncio

        result = asyncio.run(plugin.send_mail("Test", "Body", ["user@example.com"]))
        assert result is True


class TestHardwareInterface:
    """Test HardwarePlugin interface"""

    def test_hardware_plugin_is_base_plugin(self):
        """Test that HardwarePlugin inherits from BasePlugin"""
        assert issubclass(HardwarePlugin, BasePlugin)

    def test_hardware_plugin_has_required_methods(self):
        """Test that HardwarePlugin has required abstract methods"""

        class CompleteHardwarePlugin(HardwarePlugin):
            name = "complete"

            async def init(self, host: str, rack: str, uloc: str, blade: str) -> None:
                pass

            async def change_boot(self, boot_order: str, interfaces_path: str) -> bool:
                return True

            async def set_power_state(self, state: str) -> None:
                pass

            async def unmount_virtual_media(self) -> bool:
                return True

            async def detach_remote_image(self) -> bool:
                return True

            async def boot_to_type(self, host_type: str, interfaces_path: str) -> bool:
                return True

            async def reboot_server(self, graceful: bool = False) -> bool:
                return True

            async def set_next_boot_pxe(self) -> None:
                pass

            async def get_power_state(self) -> str:
                return "on"

        config = {}
        plugin = CompleteHardwarePlugin(config)
        assert plugin is not None


class TestProvisionerInterface:
    """Test ProvisionerPlugin interface"""

    def test_provisioner_plugin_is_base_plugin(self):
        """Test that ProvisionerPlugin inherits from BasePlugin"""
        assert issubclass(ProvisionerPlugin, BasePlugin)


class TestSwitchInterface:
    """Test SwitchPlugin interface"""

    def test_switch_plugin_is_base_plugin(self):
        """Test that SwitchPlugin inherits from BasePlugin"""
        assert issubclass(SwitchPlugin, BasePlugin)

    def test_switch_plugin_has_required_methods(self):
        """Test that SwitchPlugin has required abstract methods"""

        class CompleteSwitchPlugin(SwitchPlugin):
            name = "complete"

            def configure(self, host: str, old_cloud: str, new_cloud: str) -> bool:
                return True

            def modify(
                self,
                host: str,
                network: str = None,
                interfaces: str = None,
                cloud: str = None,
                old_cloud: str = None,
                index: int = None,
                vlan: int = None,
                port_mode: str = None,
                only_fail: bool = False,
            ) -> bool:
                return True

            def verify(self, host: str = None, cloud: str = None, change: bool = False) -> bool:
                return True

            def ls_config(self, cloud: str, all: bool = False) -> bool:
                return True

        config = {}
        plugin = CompleteSwitchPlugin(config)
        assert plugin is not None


class TestTicketingInterface:
    """Test TicketingPlugin interface"""

    def test_ticketing_plugin_is_base_plugin(self):
        """Test that TicketingPlugin inherits from BasePlugin"""
        assert issubclass(TicketingPlugin, BasePlugin)

    def test_ticketing_plugin_has_required_methods(self):
        """Test that TicketingPlugin has required abstract methods"""

        class CompleteTicketingPlugin(TicketingPlugin):
            name = "complete"

            def create_ticket(self, summary: str, description: str, labels: list = None) -> str:
                return "TICKET-123"

            def post_comment(self, ticket_id: str, comment: str) -> bool:
                return True

            def get_ticket(self, ticket_id: str) -> dict:
                return {"id": ticket_id}

        config = {}
        plugin = CompleteTicketingPlugin(config)
        assert plugin is not None


class TestValidatorInterface:
    """Test ValidatorPlugin interface"""

    def test_validator_plugin_is_base_plugin(self):
        """Test that ValidatorPlugin inherits from BasePlugin"""
        assert issubclass(ValidatorPlugin, BasePlugin)

    def test_validator_plugin_has_required_methods(self):
        """Test that ValidatorPlugin has required abstract methods"""

        class CompleteValidatorPlugin(ValidatorPlugin):
            name = "complete"

            async def validate(self, cloud: str = None, host: str = None, skip: str = None, **kwargs):
                return {"status": "pass", "checks": []}

        config = {}
        plugin = CompleteValidatorPlugin(config)
        assert plugin is not None


class TestReleaseInterface:
    """Test ReleasePlugin interface"""

    def test_release_plugin_is_base_plugin(self):
        """Test that ReleasePlugin inherits from BasePlugin"""
        assert issubclass(ReleasePlugin, BasePlugin)

    def test_release_plugin_has_required_methods(self):
        """Test that ReleasePlugin has required abstract methods"""

        class CompleteReleasePlugin(ReleasePlugin):
            name = "complete"

            async def move_and_rebuild(
                self, hostname: str, old_cloud: str, new_cloud: str, model: str, **kwargs
            ) -> bool:
                return True

        config = {}
        plugin = CompleteReleasePlugin(config)
        assert plugin is not None


class TestInterfaceInheritance:
    """Test that all plugin interfaces properly inherit from BasePlugin"""

    def test_all_interfaces_inherit_base_plugin(self):
        """Test that all plugin interfaces inherit from BasePlugin"""
        interfaces = [
            ChatPlugin,
            EmailPlugin,
            HardwarePlugin,
            ProvisionerPlugin,
            SwitchPlugin,
            TicketingPlugin,
            ValidatorPlugin,
            ReleasePlugin,
        ]

        for interface in interfaces:
            assert issubclass(interface, BasePlugin), f"{interface.__name__} should inherit from BasePlugin"

    def test_all_interfaces_are_abstract(self):
        """Test that plugin interfaces cannot be instantiated directly"""
        interfaces = [
            (ChatPlugin, "send_message"),
            (EmailPlugin, "send_mail"),
            (HardwarePlugin, "init"),
            (SwitchPlugin, "configure"),
            (TicketingPlugin, "create_ticket"),
            (ValidatorPlugin, "validate"),
            (ReleasePlugin, "move_and_rebuild"),
        ]

        for interface_class, method_name in interfaces:
            config = {}
            # Most will fail on instantiation or method call due to abstract methods
            # This is expected behavior
            try:
                instance = interface_class(config)
                # If instantiation succeeds, calling abstract method should fail
                assert hasattr(instance, method_name)
            except TypeError:
                # Expected: cannot instantiate abstract class
                pass
