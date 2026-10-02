"""Built-in LLM data presets.

Row fixtures follow the documented formats:
- OpenAI chat fine-tuning / function calling:
  https://platform.openai.com/docs/guides/supervised-fine-tuning (chat rows with
  ``tools`` and assistant ``tool_calls`` whose ``arguments`` is a JSON string).
- OpenAI preference fine-tuning (``input`` / ``preferred_output`` /
  ``non_preferred_output``): https://platform.openai.com/docs/guides/direct-preference-optimization
- Anthropic Messages API tool use (``tool_use`` / ``tool_result`` blocks, tools
  with ``input_schema``): https://docs.anthropic.com/en/docs/build-with-claude/tool-use
- TRL dataset formats (``messages``, ``prompt``/``completion``, ``text``,
  ``prompt``/``chosen``/``rejected``): https://huggingface.co/docs/trl/dataset_formats

Every schema verdict is cross-checked against the reference ``jsonschema``
validator.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from toolkit_data_contracts_drift.cli import EXIT_CHECK_FAILED, EXIT_CLI_ERROR, EXIT_SUCCESS, main
from toolkit_data_contracts_drift.contract import validate_records
from toolkit_data_contracts_drift.presets import PRESETS, ToolsError, get_preset, parse_tools

WEATHER_OPENAI = {
    "type": "function",
    "function": {
        "name": "get_current_weather",
        "description": "Get the current weather",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string"},
                "format": {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["location", "format"],
        },
    },
}
WEATHER_ANTHROPIC = {
    "name": "get_weather",
    "description": "Get the current weather in a given location",
    "input_schema": {
        "type": "object",
        "properties": {"location": {"type": "string"}, "unit": {"enum": ["c", "f"]}},
        "required": ["location"],
    },
}


def _openai_row(arguments: str, *, with_tools: bool = True, result_id: str = "call_1") -> dict:
    row: dict = {
        "messages": [
            {"role": "user", "content": "What is the weather in San Francisco?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "get_current_weather", "arguments": arguments},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": result_id, "content": "21 C, sunny"},
            {"role": "assistant", "content": "It is 21 C and sunny."},
        ]
    }
    if with_tools:
        row["tools"] = [WEATHER_OPENAI]
    return row


def _anthropic_row(tool_input: dict, result_id: str = "toolu_01") -> dict:
    return {
        "system": "You are a weather assistant.",
        "messages": [
            {"role": "user", "content": "What's the weather like in San Francisco?"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me check."},
                    {
                        "type": "tool_use",
                        "id": "toolu_01",
                        "name": "get_weather",
                        "input": tool_input,
                    },
                ],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": result_id, "content": "15 C"}],
            },
        ],
    }


GOOD_ARGS = json.dumps({"location": "San Francisco, CA", "format": "celsius"})

VALID = {
    "openai-chat": [
        _openai_row(GOOD_ARGS),
        {
            "messages": [
                {"role": "system", "content": "Be brief."},
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello!", "weight": 1},
            ]
        },
        {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What is in this image?"},
                        {"type": "image_url", "image_url": {"url": "https://example.com/cat.png"}},
                    ],
                },
                {"role": "assistant", "content": "A cat."},
            ]
        },
    ],
    "anthropic-messages": [
        _anthropic_row({"location": "San Francisco, CA"}),
        {
            "messages": [
                {"role": "user", "content": "Hi"},
                {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": "", "signature": "sig"},
                        {"type": "text", "text": "Hello"},
                    ],
                },
            ]
        },
    ],
    "tool-calls": [
        {"name": "get_current_weather", "arguments": GOOD_ARGS},
        {"type": "function", "function": {"name": "get_current_weather", "arguments": GOOD_ARGS}},
        {
            "type": "tool_use",
            "name": "get_current_weather",
            "input": {"location": "Paris", "format": "celsius"},
        },
    ],
    "sft": [
        {"messages": [{"role": "user", "content": "2+2?"}, {"role": "assistant", "content": "4"}]},
        {"prompt": "The sky is", "completion": " blue."},
        {"text": "The sky is blue."},
        {
            "prompt": [{"role": "user", "content": "2+2?"}],
            "completion": [{"role": "assistant", "content": "4"}],
        },
    ],
    "dpo": [
        {"prompt": "The sky is", "chosen": " blue.", "rejected": " green."},
        {
            "chosen": [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello!"},
            ],
            "rejected": [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Go away"},
            ],
        },
        {
            "input": {"messages": [{"role": "user", "content": "Hello"}]},
            "preferred_output": [{"role": "assistant", "content": "Hi, how can I help?"}],
            "non_preferred_output": [{"role": "assistant", "content": "What?"}],
        },
    ],
    "rag-chunks": [
        {
            "id": "doc1#0",
            "doc_id": "doc1",
            "text": "Paris is the capital of France.",
            "chunk_index": 0,
            "start_char": 0,
            "end_char": 31,
            "metadata": {"lang": "en"},
            "embedding": [0.1, -0.2, 0.3],
        },
        {"id": 7, "text": "Short chunk."},
    ],
}

INVALID = {
    "openai-chat": [
        {"messages": []},
        {"messages": [{"role": "robot", "content": "x"}]},
        {"messages": [{"role": "user"}]},
        {"messages": [{"role": "tool", "content": "x"}]},
        {"messages": [{"role": "assistant", "content": None}]},
        {"messages": [{"role": "user", "content": [{"type": "image_url"}]}]},
    ],
    "anthropic-messages": [
        {"messages": [{"role": "assistant", "content": "I start"}]},
        {"messages": [{"role": "user", "content": [{"type": "text"}]}]},
        {"messages": [{"role": "user", "content": [{"type": "tool_use", "id": "t", "name": "x"}]}]},
        {"messages": [{"role": "user"}]},
    ],
    "tool-calls": [
        {"name": "", "arguments": "{}"},
        {"type": "tool_use", "name": "x"},
        {"arguments": "{}"},
    ],
    "sft": [
        {"messages": [{"role": "user", "content": "no answer"}]},
        {"prompt": "x", "completion": ""},
        {"text": ""},
        {"question": "x"},
    ],
    "dpo": [{"prompt": "x", "chosen": "a"}, {"chosen": "", "rejected": "b"}],
    "rag-chunks": [
        {"id": "a"},
        {"id": "a", "text": ""},
        {"id": "", "text": "x"},
        {"id": "a", "text": "x", "embedding": []},
        {"id": "a", "text": "x", "chunk_index": -1},
    ],
}


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_preset_schema_is_valid_json_schema(name: str) -> None:
    Draft202012Validator.check_schema(PRESETS[name].schema)


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_schema_verdicts_match_reference_validator(name: str) -> None:
    ref = Draft202012Validator(PRESETS[name].schema)
    contract = get_preset(name).contract()
    for row in VALID[name]:
        assert ref.is_valid(row), row
        assert validate_records(contract=contract, records=[row], strict_integer=True) == [], row
    for row in INVALID[name]:
        assert not ref.is_valid(row), row
        assert validate_records(contract=contract, records=[row], strict_integer=True), row


def _checks(name: str, rows: list[dict], tools=None) -> list[tuple[str, str, str]]:
    check = get_preset(name).checks(tools)
    out = []
    for row in rows:
        out.extend(check(row))
    return out


class TestToolCalls:
    def test_valid_openai_call(self):
        assert _checks("openai-chat", [_openai_row(GOOD_ARGS)]) == []

    def test_argument_type_and_enum_errors(self):
        args = json.dumps({"location": 94103, "format": "kelvin"})
        assert sorted(_checks("openai-chat", [_openai_row(args)])) == [
            ("tool_args_enum_mismatch", "tool[get_current_weather].format", "enum"),
            (
                "tool_args_type_mismatch",
                "tool[get_current_weather].location",
                "type_mismatch:integer",
            ),
        ]

    def test_missing_required_argument(self):
        args = json.dumps({"location": "Paris"})
        assert _checks("openai-chat", [_openai_row(args)]) == [
            ("tool_args_missing_required", "tool[get_current_weather].format", "missing_required")
        ]

    def test_arguments_must_be_json_object(self):
        assert _checks("openai-chat", [_openai_row('{"location": "Paris",')]) == [
            ("tool_args_invalid_json", "tool[get_current_weather]", "tool_args_invalid_json")
        ]
        assert _checks("openai-chat", [_openai_row("[1, 2]")]) == [
            ("tool_args_not_object", "tool[get_current_weather]", "tool_args_not_object")
        ]

    def test_unknown_tool(self):
        row = _openai_row(GOOD_ARGS)
        row["messages"][1]["tool_calls"][0]["function"]["name"] = "get_stock_price"
        assert _checks("openai-chat", [row]) == [
            ("unknown_tool", "tool[get_stock_price]", "unknown_tool")
        ]

    def test_orphan_tool_result(self):
        assert _checks("openai-chat", [_openai_row(GOOD_ARGS, result_id="call_9")]) == [
            ("orphan_tool_result", "messages[].tool_call_id", "orphan_tool_result")
        ]

    def test_without_tool_definitions_calls_are_counted_unchecked(self):
        check = get_preset("openai-chat").checks(None)
        assert check(_openai_row(json.dumps({"location": 1}), with_tools=False)) == []
        assert check.summary() == {"tool_calls_checked": 0, "tool_calls_unchecked": 1}

    def test_anthropic_tool_use_against_anthropic_tools(self):
        tools = parse_tools([WEATHER_ANTHROPIC])
        assert _checks("anthropic-messages", [_anthropic_row({"location": "SF"})], tools) == []
        assert sorted(_checks("anthropic-messages", [_anthropic_row({"unit": "k"})], tools)) == [
            ("tool_args_enum_mismatch", "tool[get_weather].unit", "enum"),
            ("tool_args_missing_required", "tool[get_weather].location", "missing_required"),
        ]
        orphan = _anthropic_row({"location": "SF"}, result_id="toolu_99")
        assert _checks("anthropic-messages", [orphan], tools) == [
            ("orphan_tool_result", "messages[].content[].tool_use_id", "orphan_tool_result")
        ]

    def test_integer_arguments_follow_json_schema(self):
        tools = parse_tools(
            [
                {
                    "name": "n",
                    "input_schema": {"type": "object", "properties": {"k": {"type": "integer"}}},
                }
            ]
        )
        assert _checks("tool-calls", [{"name": "n", "arguments": {"k": 2.0}}], tools) == []
        assert _checks("tool-calls", [{"name": "n", "arguments": {"k": 2.5}}], tools) == [
            ("tool_args_type_mismatch", "tool[n].k", "type_mismatch:number")
        ]

    def test_parse_tools_formats_and_errors(self):
        tools = parse_tools(
            {
                "tools": [
                    WEATHER_OPENAI,
                    WEATHER_ANTHROPIC,
                    {"type": "bash_20250124", "name": "bash"},
                    {"name": "legacy", "parameters": {"type": "object"}},
                ]
            }
        )
        assert set(tools) == {"get_current_weather", "get_weather", "bash", "legacy"}
        assert tools["bash"] is None
        with pytest.raises(ToolsError, match="unsupported"):
            parse_tools([{"name": "x", "input_schema": {"unevaluatedProperties": False}}])
        with pytest.raises(ToolsError):
            parse_tools([{"description": "no name"}])


class TestRowChecks:
    def test_dpo_identical_and_mismatched_pairs(self):
        assert _checks("dpo", [{"prompt": "p", "chosen": "a", "rejected": "a"}]) == [
            ("preference_identical", "chosen", "chosen_equals_rejected")
        ]
        mixed = {"chosen": "a", "rejected": [{"role": "assistant", "content": "b"}]}
        assert _checks("dpo", [mixed]) == [
            ("preference_type_mismatch", "chosen", "chosen_and_rejected_differ_in_type")
        ]
        same = [{"role": "assistant", "content": "x"}]
        openai = {"input": {"messages": []}, "preferred_output": same, "non_preferred_output": same}
        assert _checks("dpo", [openai]) == [
            ("preference_identical", "preferred_output", "chosen_equals_rejected")
        ]

    def test_rag_duplicate_ids_dimensions_and_offsets(self):
        rows = [
            {"id": "a", "text": "x", "embedding": [0.1, 0.2]},
            {"id": "a", "text": "y", "embedding": [0.1, 0.2, 0.3]},
            {"id": 1, "text": "z", "start_char": 9, "end_char": 3},
            {"id": "1", "text": "z"},
        ]
        assert _checks("rag-chunks", rows) == [
            ("duplicate_id", "id", "duplicate_id"),
            ("embedding_dimension_mismatch", "embedding", "expected 2 dimensions"),
            ("offset_order", "start_char", "start_char > end_char"),
        ]


def _jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


class TestCli:
    def test_check_with_preset_reports_preset_and_tool_counts(self, tmp_path: Path):
        data = _jsonl(tmp_path / "chat.jsonl", [_openai_row(GOOD_ARGS)] * 3)
        out = tmp_path / "r.json"
        code = main(["check", "--input", str(data), "--preset", "openai-chat", "--out", str(out)])
        assert code == EXIT_SUCCESS
        pred = json.loads(out.read_text(encoding="utf-8"))["predicate"]
        assert pred["details"]["preset"] == "openai-chat"
        assert pred["summary"]["tool_calls_checked"] == 3
        assert pred["inputs"][0]["name"] == "preset:openai-chat"

    def test_bad_tool_arguments_fail_the_check(self, tmp_path: Path):
        data = _jsonl(tmp_path / "chat.jsonl", [_openai_row(json.dumps({"location": 1}))])
        out = tmp_path / "r.json"
        code = main(["check", "--input", str(data), "--preset", "openai-chat", "--out", str(out)])
        assert code == EXIT_CHECK_FAILED
        pred = json.loads(out.read_text(encoding="utf-8"))["predicate"]
        kinds = {i["kind"] for i in pred["details"]["validation_issues"]}
        assert kinds == {"tool_args_type_mismatch", "tool_args_missing_required"}
        assert pred["summary"]["invalid_records"] == 1

    def test_tool_calls_preset_needs_tools(self, tmp_path: Path):
        data = _jsonl(
            tmp_path / "calls.jsonl", [{"name": "get_current_weather", "arguments": GOOD_ARGS}]
        )
        assert main(["check", "--input", str(data), "--preset", "tool-calls"]) == EXIT_CLI_ERROR
        tools = tmp_path / "tools.json"
        tools.write_text(json.dumps([WEATHER_OPENAI]), encoding="utf-8")
        args = ["check", "--input", str(data), "--preset", "tool-calls", "--tools", str(tools)]
        assert main(args) == EXIT_SUCCESS

    def test_tools_need_a_tool_preset_and_contract_excludes_preset(self, tmp_path: Path):
        data = _jsonl(tmp_path / "d.jsonl", [{"text": "x"}])
        tools = tmp_path / "tools.json"
        tools.write_text("[]", encoding="utf-8")
        assert main(["check", "--input", str(data), "--preset", "sft", "--tools", str(tools)]) == 2
        contract = tmp_path / "c.json"
        assert main(["presets", "show", "sft", "--out", str(contract)]) == EXIT_SUCCESS
        both = ["check", "--input", str(data), "--preset", "sft", "--contract", str(contract)]
        assert main(both) == EXIT_CLI_ERROR
        assert main(["check", "--input", str(data), "--contract", str(contract)]) == EXIT_SUCCESS
        assert main(["check", "--input", str(data)]) == EXIT_CLI_ERROR

    def test_presets_list(self, capsys: pytest.CaptureFixture[str]):
        assert main(["presets", "list"]) == EXIT_SUCCESS
        listed = [line.split()[0] for line in capsys.readouterr().out.splitlines()]
        assert listed == list(PRESETS)

    def test_profile_and_drift_with_preset(self, tmp_path: Path):
        base_rows = [
            {"messages": [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]}
        ] * 20
        cur_rows = [
            {
                "messages": [
                    {"role": "system", "content": "s"},
                    {"role": "assistant", "content": "a"},
                ]
            }
        ] * 20
        base = _jsonl(tmp_path / "base.jsonl", base_rows)
        cur = _jsonl(tmp_path / "cur.jsonl", cur_rows)
        prof, out = tmp_path / "p.json", tmp_path / "r.json"
        assert main(["profile", "--input", str(base), "--preset", "sft", "--out", str(prof)]) == 0
        code = main(
            [
                "check",
                "--input",
                str(cur),
                "--preset",
                "sft",
                "--baseline",
                str(prof),
                "--out",
                str(out),
            ]
        )
        assert code == EXIT_CHECK_FAILED
        drift = json.loads(out.read_text(encoding="utf-8"))["predicate"]["details"]["drift_issues"]
        assert ("drift_categorical", "messages[].role") in {(d["kind"], d["field"]) for d in drift}
