"""
Control-plane adapter for toolkit-data-contracts (TK-05).

Covers config hierarchy and CLI command → ToolSpec mapping.
"""

from .config import ToolkitConfigContract, build_config_hierarchy
from .contracts import (
    _HAS_EXECUTION_CONTRACTS,
    ApprovalPolicy,
    AuthorityBoundary,
    PermissionScope,
)
from .contracts import (
    ToolSpec as CPToolSpec,
)
from .tool_specs import TOOLKIT_TOOL_SPECS, ToolkitCommandSpec, get_tool_spec

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
