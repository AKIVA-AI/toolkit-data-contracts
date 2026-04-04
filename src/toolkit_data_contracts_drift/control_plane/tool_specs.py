"""
CLI command → ToolSpec mapping for toolkit-data-contracts.

Maps the 3 CLI subcommands (infer, profile, check) to ToolSpec contracts.

All commands are READ_ONLY + AUTO — data-contracts is a read/analysis-only toolkit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import ApprovalPolicy, AuthorityBoundary, PermissionScope, ToolSpec


@dataclass
class ToolkitCommandSpec:
    """Maps a CLI subcommand name to its ToolSpec and authority boundary."""

    command: str
    spec: ToolSpec
    boundary: AuthorityBoundary


def _make_spec(name: str, description: str, input_schema: dict[str, Any] | None = None) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=description,
        category="tool",
        version="1.0.0",
        owner="toolkit-data-contracts",
        permission_scope=PermissionScope.READ_ONLY,
        input_schema=input_schema,
        output_schema=None,
        sandbox_requirement=None,
        aliases=None,
    )


_READ_ONLY_AUTO = AuthorityBoundary(scope=PermissionScope.READ_ONLY, approval=ApprovalPolicy.AUTO)

TOOLKIT_TOOL_SPECS: dict[str, ToolkitCommandSpec] = {
    "infer": ToolkitCommandSpec(
        command="infer",
        spec=_make_spec(
            name="infer",
            description="Infer a data contract (schema) from JSONL records.",
            input_schema={
                "type": "object",
                "properties": {
                    "input_file": {"type": "string", "description": "Path to JSONL records"},
                    "output": {"type": "string", "description": "Output contract JSON path"},
                    "format": {"type": "string", "enum": ["json", "text"]},
                },
                "required": ["input_file"],
            },
        ),
        boundary=_READ_ONLY_AUTO,
    ),
    "profile": ToolkitCommandSpec(
        command="profile",
        spec=_make_spec(
            name="profile",
            description="Compute a baseline profile for drift detection from JSONL records.",
            input_schema={
                "type": "object",
                "properties": {
                    "input_file": {"type": "string"},
                    "contract": {"type": "string", "description": "Path to contract JSON"},
                    "output": {"type": "string", "description": "Output profile JSON path"},
                },
                "required": ["input_file", "contract"],
            },
        ),
        boundary=_READ_ONLY_AUTO,
    ),
    "check": ToolkitCommandSpec(
        command="check",
        spec=_make_spec(
            name="check",
            description=(
                "Validate JSONL records against a contract and optionally drift-check "
                "against a baseline profile."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "input_file": {"type": "string"},
                    "contract": {"type": "string"},
                    "baseline": {"type": "string", "description": "Optional baseline profile path"},
                    "drift_threshold": {"type": "number"},
                    "strict": {"type": "boolean"},
                    "format": {"type": "string", "enum": ["json", "text"]},
                },
                "required": ["input_file", "contract"],
            },
        ),
        boundary=_READ_ONLY_AUTO,
    ),
}


def get_tool_spec(command: str) -> ToolkitCommandSpec | None:
    """Return the ToolkitCommandSpec for a CLI subcommand, or None if unknown."""
    return TOOLKIT_TOOL_SPECS.get(command)


__all__ = ["TOOLKIT_TOOL_SPECS", "ToolkitCommandSpec", "get_tool_spec"]
