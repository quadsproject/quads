"""
Release plugins for QUADS

This package contains implementations of the ReleasePlugin interface
for moving and rebuilding hosts.
"""

from .standard import StandardReleasePlugin

__all__ = ["StandardReleasePlugin"]
