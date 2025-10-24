import asyncio
import logging
from typing import List, Optional, Dict
from quads.plugins.dispatchers.base import MultiPluginDispatcher
from quads.plugins.interfaces.email import EmailPlugin
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)


class EmailDispatcher(MultiPluginDispatcher[EmailPlugin]):

    def __init__(self, plugin_manager: PluginManager, plugin_names: Optional[List[str]] = None):
        super().__init__(plugin_manager, EmailPlugin, "Email", plugin_names=plugin_names)

    async def send_mail(
        self,
        subject: str,
        body: str,
        recipients: List[str],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict]] = None,
        html: bool = True,
        **kwargs,
    ) -> Dict[str, bool]:

        plugins = self.get_active_plugins()

        if not plugins:
            logger.warning("No email plugins available to send mail")
            return {}

        tasks = []
        plugin_names = []

        for plugin in plugins:
            if not plugin.enabled:
                continue

            tasks.append(
                self._send_with_plugin(
                    plugin, subject, body, recipients, cc, bcc, reply_to, attachments, html, **kwargs
                )
            )
            plugin_names.append(plugin.name)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        result_map = {}
        for plugin_name, result in zip(plugin_names, results):
            if isinstance(result, Exception):
                logger.error(f"Email plugin {plugin_name} raised exception: {result}")
                result_map[plugin_name] = False
            else:
                result_map[plugin_name] = result

        success_count = sum(1 for v in result_map.values() if v)
        logger.info(f"Email sent via {success_count}/{len(result_map)} plugins")

        return result_map

    async def _send_with_plugin(
        self,
        plugin: EmailPlugin,
        subject: str,
        body: str,
        recipients: List[str],
        cc: Optional[List[str]],
        bcc: Optional[List[str]],
        reply_to: Optional[str],
        attachments: Optional[List[Dict]],
        html: bool,
        **kwargs,
    ) -> bool:
        try:
            logger.debug(f"Sending email via {plugin.name}")
            success = await plugin.send_mail(
                subject=subject,
                body=body,
                recipients=recipients,
                cc=cc,
                bcc=bcc,
                reply_to=reply_to,
                attachments=attachments,
                html=html,
                **kwargs,
            )

            if success:
                logger.info(f"✓ Email sent successfully via {plugin.name}")
            else:
                logger.warning(f"✗ Email failed via {plugin.name}")

            return success

        except Exception as e:
            logger.error(f"Exception in email plugin {plugin.name}: {e}", exc_info=True)
            return False

    async def send_template_mail(
        self,
        template_name: str,
        recipients: List[str],
        template_vars: Dict,
        **kwargs,
    ) -> Dict[str, bool]:

        plugins = self.get_active_plugins()

        if not plugins:
            logger.warning("No email plugins available to send template mail")
            return {}

        tasks = []
        plugin_names = []

        for plugin in plugins:
            if not plugin.enabled:
                continue

            tasks.append(self._send_template_with_plugin(plugin, template_name, recipients, template_vars, **kwargs))
            plugin_names.append(plugin.name)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        result_map = {}
        for plugin_name, result in zip(plugin_names, results):
            if isinstance(result, Exception):
                logger.error(f"Email plugin {plugin_name} raised exception: {result}")
                result_map[plugin_name] = False
            else:
                result_map[plugin_name] = result

        success_count = sum(1 for v in result_map.values() if v)
        logger.info(f"Template email sent via {success_count}/{len(result_map)} plugins")

        return result_map

    async def _send_template_with_plugin(
        self,
        plugin: EmailPlugin,
        template_name: str,
        recipients: List[str],
        template_vars: Dict,
        **kwargs,
    ) -> bool:
        try:
            logger.debug(f"Sending template email via {plugin.name}")
            success = await plugin.send_template_mail(
                template_name=template_name,
                recipients=recipients,
                template_vars=template_vars,
                **kwargs,
            )

            if success:
                logger.info(f"✓ Template email sent successfully via {plugin.name}")
            else:
                logger.warning(f"✗ Template email failed via {plugin.name}")

            return success

        except Exception as e:
            logger.error(f"Exception in email plugin {plugin.name}: {e}", exc_info=True)
            return False

    def send_mail_sync(
        self,
        subject: str,
        body: str,
        recipients: List[str],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict]] = None,
        html: bool = True,
        **kwargs,
    ) -> Dict[str, bool]:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.send_mail(subject, body, recipients, cc, bcc, reply_to, attachments, html, **kwargs)
            )
        finally:
            loop.close()

    def send_template_mail_sync(
        self,
        template_name: str,
        recipients: List[str],
        template_vars: Dict,
        **kwargs,
    ) -> Dict[str, bool]:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_template_mail(template_name, recipients, template_vars, **kwargs))
        finally:
            loop.close()

    def get_enabled_plugins(self) -> List[str]:
        return [p.name for p in self._plugins if p.enabled]

    async def health_check_all(self) -> Dict[str, bool]:
        results = {}
        for plugin in self._plugins:
            try:
                results[plugin.name] = plugin.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {plugin.name}: {e}")
                results[plugin.name] = False
        return results


_dispatcher_instance: Optional[EmailDispatcher] = None


def get_email_dispatcher(plugin_manager: Optional[PluginManager] = None) -> EmailDispatcher:

    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            raise RuntimeError("PluginManager required to initialize EmailDispatcher")
        _dispatcher_instance = EmailDispatcher(plugin_manager)

    return _dispatcher_instance


def send_mail(
    subject: str,
    body: str,
    recipients: List[str],
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    reply_to: Optional[str] = None,
    attachments: Optional[List[Dict]] = None,
    html: bool = True,
    **kwargs,
) -> Dict[str, bool]:

    dispatcher = get_email_dispatcher()
    return dispatcher.send_mail_sync(subject, body, recipients, cc, bcc, reply_to, attachments, html, **kwargs)


def send_template_mail(
    template_name: str,
    recipients: List[str],
    template_vars: Dict,
    **kwargs,
) -> Dict[str, bool]:

    dispatcher = get_email_dispatcher()
    return dispatcher.send_template_mail_sync(template_name, recipients, template_vars, **kwargs)
