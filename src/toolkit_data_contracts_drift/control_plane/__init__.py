"""
Control-plane adapter for toolkit-data-contracts (TK-05).

Covers config hierarchy and CLI command → ToolSpec mapping.
"""

from .config import ToolkitConfigContract, build_config_hierarchy
from .tool_specs import TOOLKIT_TOOL_SPECS, get_tool_spec, ToolkitCommandSpec
from .contracts import (
    PermissionScope,
    ApprovalPolicy,
    AuthorityBoundary,
    ToolSpec as CPToolSpec,
    _HAS_EXECUTION_CONTRACTS,
)

__all__ = [
    "ToolkitConfigContract",
    "build_config_hierarchy",
    "TOOLKIT_TOOL_SPECS",
    "get_tool_spec",
    "ToolkitCommandSpec",
    "PermissionScope",
    "ApprovalPolicy",
    "AuthorityBoundary",
    "CPToolSpec",
    "_HAS_EXECUTION_CONTRACTS",
]
