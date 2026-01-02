"""Vendored dependencies loader for Vacation Calendar Updater.

This module ensures vendored packages in app/_vendor are available
before any other packages in sys.path, making the application
self-contained and portable.
"""

from __future__ import annotations

import sys
from pathlib import Path


def setup_vendor_packages() -> None:
    """Prepend vendored packages to sys.path if they exist."""
    vendor_path = Path(__file__).parent / "_vendor"

    if not vendor_path.exists():
        return

    vendor_packages = str(vendor_path)

    # Only add if not already in path (at the beginning)
    if vendor_packages not in sys.path:
        sys.path.insert(0, vendor_packages)


# Initialize vendor packages on import
setup_vendor_packages()

# Re-export commonly used vendored packages for convenience
__all__ = ["setup_vendor_packages"]
