"""
Config hierarchy contract for toolkit-data-contracts.

Three-tier hierarchy (mirrors Akiva platform pattern):
  Level 0 — Platform defaults (global Akiva CLI conventions)
  Level 1 — Toolkit config (pyproject.toml / config file)
  Level 2 — CLI overrides (argv flags)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolkitConfigContract:
    """
    Resolved configuration contract for toolkit-data-contracts.

    All fields represent resolved values after applying the three-tier
    hierarchy (platform defaults → toolkit config → CLI overrides).
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    toolkit_id: str = "TK-05"
    toolkit_name: str = "toolkit-data-contracts"
    version: str = "1.0.0"

    # ── Runtime behaviour ─────────────────────────────────────────────────────
    log_format: str = "json"
    structured_logging: bool = True
    output_format: str = "json"

    # ── Data-contracts specific ───────────────────────────────────────────────
    drift_threshold: float = 0.05  # fraction of records that may drift before alert
    max_records: int = 100_000  # hard cap on JSONL input size
    strict_mode: bool = False  # fail on any schema warning (not just errors)

    # ── Extension ─────────────────────────────────────────────────────────────
    extra: dict[str, Any] = field(default_factory=dict)


CONFIG_LEVELS = {
    "platform_default": 0,
    "toolkit_config": 1,
    "cli_override": 2,
}


def build_config_hierarchy(
    toolkit_config: dict[str, Any] | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> ToolkitConfigContract:
    """
    Merge config tiers into a resolved ToolkitConfigContract.

    Priority: CLI overrides > toolkit config > platform defaults.
    """
    resolved: dict[str, Any] = {
        "toolkit_id": "TK-05",
        "toolkit_name": "toolkit-data-contracts",
        "version": "1.0.0",
        "log_format": "json",
        "structured_logging": True,
        "output_format": "json",
        "drift_threshold": 0.05,
        "max_records": 100_000,
        "strict_mode": False,
        "extra": {},
    }

    if toolkit_config:
        for k, v in toolkit_config.items():
            if k in resolved:
                resolved[k] = v
            else:
                resolved["extra"][k] = v

    if cli_overrides:
        for k, v in cli_overrides.items():
            if k in resolved:
                resolved[k] = v
            else:
                resolved["extra"][k] = v

    return ToolkitConfigContract(**{k: v for k, v in resolved.items()})


__all__ = ["ToolkitConfigContract", "CONFIG_LEVELS", "build_config_hierarchy"]
