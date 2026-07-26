#!/usr/bin/env python3
"""
Automatic Foreman RBAC bootstrap.

Ensures the roles, filters, usergroup, and cloud user accounts that QUADS requires
in Foreman exist when quads-server starts.  Documented manual setup steps from
docs/switch-host-setup.md are automated here.

All operations are idempotent: existing objects are detected and left unchanged.
"""

import asyncio
import fcntl
import logging
import threading
import time

from quads.config import Config
from quads.server.models import Cloud, db
from quads.tools.external.foreman import Foreman

logger = logging.getLogger(__name__)

CLOUDUSER_HOSTS_ROLE = "clouduser_hosts"
CLOUDUSER_VIEWS_ROLE = "clouduser_views"
CLOUDUSERS_GROUP = "cloudusers"

CLOUDUSER_HOSTS_PERMISSIONS = [
    "view_hosts",
    "edit_hosts",
    "build_hosts",
    "power_hosts",
    "console_hosts",
]

# One filter per resource type, mirroring the documented hammer commands.
CLOUDUSER_VIEWS_PERMISSION_GROUPS = [
    ["view_operatingsystems"],
    ["view_architectures"],
    ["view_media"],
    ["view_ptables"],
    ["edit_params", "view_params"],
    ["view_users"],
]


async def ensure_quads_rbac(cloud_names):
    """
    Ensure QUADS-required Foreman roles, filters, usergroup, and cloud users exist.
    Safe to call concurrently from multiple gunicorn workers — all creates are guarded
    by a get-first check, so duplicate attempts are harmless.
    """
    foreman_conf = Config.plugins.get("foreman", {})
    api_url = foreman_conf.get("api_url")
    username = foreman_conf.get("username")
    password = foreman_conf.get("password")

    if not all([api_url, username, password]):
        logger.warning("Foreman RBAC setup: missing api_url/username/password in foreman plugin config")
        return

    foreman = Foreman(api_url, username, password)

    if not await foreman.verify_credentials():
        logger.warning("Foreman RBAC setup: credentials invalid or Foreman unreachable; skipping")
        return

    # --- Roles ---
    hosts_role_id = await foreman.get_or_create_role(CLOUDUSER_HOSTS_ROLE)
    if not hosts_role_id:
        logger.error("Foreman RBAC setup: could not create/find role '%s'" % CLOUDUSER_HOSTS_ROLE)
        return

    views_role_id = await foreman.get_or_create_role(CLOUDUSER_VIEWS_ROLE)
    if not views_role_id:
        logger.error("Foreman RBAC setup: could not create/find role '%s'" % CLOUDUSER_VIEWS_ROLE)
        return

    # --- Filters: clean up duplicates, then ensure each required filter exists ---
    await foreman.cleanup_duplicate_filters(hosts_role_id)
    await foreman.cleanup_duplicate_filters(views_role_id)

    await foreman.ensure_filter(
        hosts_role_id,
        CLOUDUSER_HOSTS_PERMISSIONS,
        search="user.login = current_user",
    )

    for perm_group in CLOUDUSER_VIEWS_PERMISSION_GROUPS:
        await foreman.ensure_filter(views_role_id, perm_group)

    # --- Usergroup ---
    group_id = await foreman.get_or_create_usergroup(CLOUDUSERS_GROUP, [hosts_role_id, views_role_id])
    if not group_id:
        logger.error("Foreman RBAC setup: could not create/find usergroup '%s'" % CLOUDUSERS_GROUP)
        return

    await foreman.cleanup_duplicate_memberships(group_id)

    # --- Cloud users ---
    mail = foreman_conf.get("rbac_user_mail") or Config.plugins.get("email", {}).get(
        "from_address", "quads@example.com"
    )
    default_password = Config.get("ipmi_cloud_password", "password")
    auth_source_id = int(foreman_conf.get("rbac_auth_source_id", 1))
    rbac_exclude_raw = foreman_conf.get("rbac_exclude") or ""
    excluded = set(rbac_exclude_raw.split("|")) if rbac_exclude_raw else set()

    for cloud_name in cloud_names:
        if cloud_name in excluded:
            continue
        user_id = await foreman.get_or_create_cloud_user(cloud_name, default_password, mail, auth_source_id)
        if not user_id:
            logger.warning("Foreman RBAC setup: could not create/find user '%s'" % cloud_name)
            continue
        if not await foreman.add_user_to_usergroup(group_id, user_id):
            logger.warning(
                "Foreman RBAC setup: could not add user '%s' to group '%s'" % (cloud_name, CLOUDUSERS_GROUP)
            )

    logger.info("Foreman RBAC setup complete")


_RBAC_LOCK_PATH = "/tmp/quads_foreman_rbac.lock"


def _rbac_thread(app):
    if not Config.plugins.get("foreman", {}).get("enabled", False):
        return
    if app.config.get("TESTING", False):
        return
    time.sleep(3)
    try:
        with open(_RBAC_LOCK_PATH, "w") as lock_file:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                logger.debug("Foreman RBAC setup already running in another worker; skipping")
                return

            try:
                with app.app_context():
                    cloud_names = [c.name for c in db.session.query(Cloud).all()]

                asyncio.run(ensure_quads_rbac(cloud_names))
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
    except Exception as ex:
        logger.warning("Foreman RBAC setup failed: %s" % ex)


def start_foreman_rbac_thread(app):
    """Start a daemon thread that bootstraps Foreman RBAC after server startup."""
    t = threading.Thread(target=_rbac_thread, args=(app,), daemon=True)
    t.start()
