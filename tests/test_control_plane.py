"""
Tests for toolkit-data-contracts control_plane adapter.

Coverage:
  - contracts: PermissionScope, ApprovalPolicy, AuthorityBoundary, framework flag
  - config: build_config_hierarchy (defaults, toolkit config, CLI overrides)
  - tool_specs: TOOLKIT_TOOL_SPECS covers all 3 commands, get_tool_spec lookup
"""

from __future__ import annotations

from toolkit_data_contracts_drift.control_plane.config import (
    CONFIG_LEVELS,
    ToolkitConfigContract,
    build_config_hierarchy,
)
from toolkit_data_contracts_drift.control_plane.contracts import (
    _HAS_EXECUTION_CONTRACTS,
    ApprovalPolicy,
    AuthorityBoundary,
    PermissionScope,
)
from toolkit_data_contracts_drift.control_plane.tool_specs import (
    TOOLKIT_TOOL_SPECS,
    get_tool_spec,
)

# ── contracts ─────────────────────────────────────────────────────────────────


class TestPermissionScope:
    def test_values(self) -> None:
        assert PermissionScope.READ_ONLY.value == "read_only"
        assert PermissionScope.FULL_ACCESS.value == "full_access"


class TestAuthorityBoundary:
    def test_auto_neither_denied_nor_needs_approval(self) -> None:
        b = AuthorityBoundary(scope=PermissionScope.READ_ONLY, approval=ApprovalPolicy.AUTO)
        assert not b.is_denied()
        assert not b.needs_approval()

    def test_deny_is_detected(self) -> None:
        b = AuthorityBoundary(scope=PermissionScope.READ_ONLY, approval=ApprovalPolicy.DENY)
        assert b.is_denied()

    def test_scope_allows(self) -> None:
        b = AuthorityBoundary(scope=PermissionScope.FULL_ACCESS, approval=ApprovalPolicy.AUTO)
        assert b.scope_allows(PermissionScope.READ_ONLY)
        assert b.scope_allows(PermissionScope.FULL_ACCESS)


class TestFrameworkFlag:
    def test_flag_is_bool(self) -> None:
        assert isinstance(_HAS_EXECUTION_CONTRACTS, bool)


# ── config ────────────────────────────────────────────────────────────────────


class TestConfigLevels:
    def test_ordering(self) -> None:
        assert CONFIG_LEVELS["platform_default"] < CONFIG_LEVELS["toolkit_config"]
        assert CONFIG_LEVELS["toolkit_config"] < CONFIG_LEVELS["cli_override"]


class TestBuildConfigHierarchy:
    def test_defaults(self) -> None:
        cfg = build_config_hierarchy()
        assert cfg.toolkit_id == "TK-05"
        assert cfg.toolkit_name == "toolkit-data-contracts"
        assert cfg.drift_threshold == 0.05
        assert cfg.max_records == 100_000
        assert cfg.strict_mode is False

    def test_toolkit_config_overrides_defaults(self) -> None:
        cfg = build_config_hierarchy(toolkit_config={"drift_threshold": 0.10, "strict_mode": True})
        assert cfg.drift_threshold == 0.10
        assert cfg.strict_mode is True

    def test_cli_overrides_toolkit_config(self) -> None:
        cfg = build_config_hierarchy(
            toolkit_config={"drift_threshold": 0.10},
            cli_overrides={"drift_threshold": 0.01},
        )
        assert cfg.drift_threshold == 0.01

    def test_unknown_keys_go_to_extra(self) -> None:
        cfg = build_config_hierarchy(toolkit_config={"my_flag": 42})
        assert cfg.extra.get("my_flag") == 42

    def test_returns_correct_type(self) -> None:
        assert isinstance(build_config_hierarchy(), ToolkitConfigContract)


# ── tool_specs ────────────────────────────────────────────────────────────────


class TestToolkitToolSpecs:
    EXPECTED_COMMANDS = {"infer", "profile", "check"}

    def test_all_commands_present(self) -> None:
        assert set(TOOLKIT_TOOL_SPECS.keys()) == self.EXPECTED_COMMANDS

    def test_all_commands_are_read_only(self) -> None:
        for name, cmd in TOOLKIT_TOOL_SPECS.items():
            assert cmd.spec.permission_scope == PermissionScope.READ_ONLY, name

    def test_all_commands_auto_approval(self) -> None:
        for name, cmd in TOOLKIT_TOOL_SPECS.items():
            assert cmd.boundary.approval == ApprovalPolicy.AUTO, name

    def test_no_sandbox_required(self) -> None:
        for name, cmd in TOOLKIT_TOOL_SPECS.items():
            assert cmd.spec.sandbox_requirement is None, name

    def test_command_key_matches_command_field(self) -> None:
        for key, cmd in TOOLKIT_TOOL_SPECS.items():
            assert cmd.command == key

    def test_owner_is_toolkit(self) -> None:
        for cmd in TOOLKIT_TOOL_SPECS.values():
            assert cmd.spec.owner == "toolkit-data-contracts"

    def test_infer_requires_input_file(self) -> None:
        schema = TOOLKIT_TOOL_SPECS["infer"].spec.input_schema
        assert schema is not None
        assert "input_file" in schema.get("required", [])

    def test_profile_requires_input_file_and_contract(self) -> None:
        schema = TOOLKIT_TOOL_SPECS["profile"].spec.input_schema
        assert schema is not None
        required = schema.get("required", [])
        assert "input_file" in required
        assert "contract" in required

    def test_check_requires_input_file_and_contract(self) -> None:
        schema = TOOLKIT_TOOL_SPECS["check"].spec.input_schema
        assert schema is not None
        required = schema.get("required", [])
        assert "input_file" in required
        assert "contract" in required

    def test_check_has_drift_threshold_property(self) -> None:
        schema = TOOLKIT_TOOL_SPECS["check"].spec.input_schema
        assert schema is not None
        assert "drift_threshold" in schema.get("properties", {})


class TestGetToolSpec:
    def test_returns_spec_for_known_command(self) -> None:
        assert get_tool_spec("check") is not None

    def test_returns_none_for_unknown(self) -> None:
        assert get_tool_spec("unknown") is None

    def test_returns_none_for_empty_string(self) -> None:
        assert get_tool_spec("") is None
