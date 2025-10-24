"""
Migration plugins for QUADS

This package contains implementations of the MigrationPlugin interface
for moving and rebuilding hosts.
"""

from .standard import StandardMigrationPlugin

__all__ = ["StandardMigrationPlugin"]
