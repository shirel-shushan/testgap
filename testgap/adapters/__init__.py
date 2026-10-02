"""Coverage adapters for JavaScript test runners."""

from .base import CoverageAdapter
from .vitest import VitestAdapter

__all__ = ["CoverageAdapter", "VitestAdapter"]
