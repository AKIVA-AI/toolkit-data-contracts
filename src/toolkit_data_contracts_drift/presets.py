"""Built-in contracts for LLM-shaped data.

Each preset is a JSON Schema contract plus record-level checks that JSON
Schema cannot express (tool-call arguments against the tool's own schema,
tool results that answer no call, identical preference pairs, duplicate chunk
ids, inconsistent embedding sizes).

Presets:

- ``openai-chat``: OpenAI chat-completions / fine-tuning rows
  (``{"messages": [...], "tools": [...]}``).
- ``anthropic-messages``: Anthropic Messages API rows
  (``{"system": ..., "messages": [...], "tools": [...]}``).
- ``tool-calls``: one tool call per row (OpenAI ``{"name", "arguments"}`` or
  ``{"type": "function", "function": {...}}``, or an Anthropic ``tool_use``
  block), checked against ``--tools``.
- ``sft``: supervised fine-tuning rows (``messages`` with an assistant turn,
  ``prompt``/``completion``, or ``text``), as used by TRL and most trainers.
- ``dpo``: preference rows (``prompt``/``chosen``/``rejected``, or the OpenAI
  ``input``/``preferred_output``/``non_preferred_output`` format).
- ``rag-chunks``: retrieval chunk records (``id``, ``text``, optional
  ``doc_id``, offsets, ``metadata``, ``embedding``).
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from .contract import CONTRACT_VERSION, JSON_SCHEMA_DIALECT
from .io import strict_json_loads
from .schema import Issue, SchemaError, Validator, check_schema

# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #

_OPENAI_PART = {
    "type": "object",
    "required": ["type"],
    "properties": {
        "type": {"enum": ["text", "image_url", "input_audio", "file", "refusal"]},
        "text": {"type": "string"},
        "image_url": {
            "type": "object",
            "required": ["url"],
            "properties": {"url": {"type": "string", "minLength": 1}},
        },
    },
    "allOf": [
        {
            "if": {"required": ["type"], "properties": {"type": {"const": "text"}}},
            "then": {"required": ["text"]},
        },
        {
            "if": {"required": ["type"], "properties": {"type": {"const": "image_url"}}},
            "then": {"required": ["image_url"]},
        },
    ],
}

_OPENAI_CHAT = {
    "$schema": JSON_SCHEMA_DIALECT,
    "title": "OpenAI chat messages",
    "type": "object",
    "required": ["messages"],
    "properties": {
        "messages": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/message"}},
        "tools": {"type": "array", "items": {"$ref": "#/$defs/tool"}},
        "parallel_tool_calls": {"type": "boolean"},
    },
    "$defs": {
        "content": {
            "anyOf": [
                {"type": "string"},
                {"type": "array", "items": {"$ref": "#/$defs/part"}},
            ]
        },
        "part": _OPENAI_PART,
        "tool_call": {
            "type": "object",
            "required": ["id", "type", "function"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "type": {"const": "function"},
                "function": {
                    "type": "object",
                    "required": ["name", "arguments"],
                    "properties": {
                        "name": {"type": "string", "minLength": 1},
                        "arguments": {"type": "string"},
                    },
                },
            },
        },
        "tool": {
            "type": "object",
            "required": ["type", "function"],
            "properties": {
                "type": {"const": "function"},
                "function": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string", "minLength": 1},
                        "description": {"type": "string"},
                        "parameters": {"type": "object"},
                        "strict": {"type": ["boolean", "null"]},
                    },
                },
            },
        },
        "message": {
            "type": "object",
            "required": ["role"],
            "properties": {
                "role": {"enum": ["system", "developer", "user", "assistant", "tool"]},
                "content": {"anyOf": [{"$ref": "#/$defs/content"}, {"type": "null"}]},
                "name": {"type": "string"},
                "tool_calls": {"type": "array", "items": {"$ref": "#/$defs/tool_call"}},
                "tool_call_id": {"type": "string", "minLength": 1},
                "weight": {"enum": [0, 1]},
            },
            "allOf": [
                {
                    "if": {
                        "required": ["role"],
                        "properties": {"role": {"enum": ["system", "developer", "user"]}},
                    },
                    "then": {
                        "required": ["content"],
                        "properties": {"content": {"$ref": "#/$defs/content"}},
                    },
                },
                {
                    "if": {"required": ["role"], "properties": {"role": {"const": "tool"}}},
                    "then": {
                        "required": ["tool_call_id", "content"],
                        "properties": {"content": {"$ref": "#/$defs/content"}},
                    },
                },
                {
                    "if": {"required": ["role"], "properties": {"role": {"const": "assistant"}}},
                    "then": {
                        "anyOf": [
                            {
                                "required": ["content"],
                                "properties": {"content": {"$ref": "#/$defs/content"}},
                            },
                            {
                                "required": ["tool_calls"],
                                "properties": {"tool_calls": {"minItems": 1}},
                            },
                        ]
                    },
                },
            ],
        },
    },
}


def _block_rule(block_type: str, required: list[str], props: dict[str, Any]) -> dict[str, Any]:
    return {
        "if": {"required": ["type"], "properties": {"type": {"const": block_type}}},
        "then": {"required": required, "properties": props},
    }


_SOURCE = {
    "type": "object",
    "required": ["type"],
    "properties": {"type": {"enum": ["base64", "url", "file", "text", "content"]}},
}

_ANTHROPIC_MESSAGES = {
    "$schema": JSON_SCHEMA_DIALECT,
    "title": "Anthropic Messages API",
    "type": "object",
    "required": ["messages"],
    "properties": {
        "system": {
            "anyOf": [
                {"type": "string"},
                {"type": "array", "items": {"$ref": "#/$defs/block"}},
            ]
        },
        "messages": {
            "type": "array",
            "minItems": 1,
            "prefixItems": [{"$ref": "#/$defs/message", "properties": {"role": {"const": "user"}}}],
            "items": {"$ref": "#/$defs/message"},
        },
        "tools": {"type": "array", "items": {"$ref": "#/$defs/tool"}},
    },
    "$defs": {
        "message": {
            "type": "object",
            "required": ["role", "content"],
            "properties": {
                "role": {"enum": ["user", "assistant", "system"]},
                "content": {
                    "anyOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"$ref": "#/$defs/block"}},
                    ]
                },
            },
        },
        "block": {
            "type": "object",
            "required": ["type"],
            "properties": {"type": {"type": "string", "minLength": 1}},
            "allOf": [
                _block_rule("text", ["text"], {"text": {"type": "string"}}),
                _block_rule("image", ["source"], {"source": _SOURCE}),
                _block_rule("document", ["source"], {"source": _SOURCE}),
                _block_rule(
                    "tool_use",
                    ["id", "name", "input"],
                    {
                        "id": {"type": "string", "minLength": 1},
                        "name": {"type": "string", "minLength": 1},
                        "input": {"type": "object"},
                    },
                ),
                _block_rule(
                    "tool_result",
                    ["tool_use_id"],
                    {
                        "tool_use_id": {"type": "string", "minLength": 1},
                        "content": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "array", "items": {"$ref": "#/$defs/block"}},
                            ]
                        },
                        "is_error": {"type": "boolean"},
                    },
                ),
                _block_rule(
                    "thinking",
                    ["thinking"],
                    {"thinking": {"type": "string"}, "signature": {"type": "string"}},
                ),
                _block_rule("redacted_thinking", ["data"], {"data": {"type": "string"}}),
            ],
        },
        "tool": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "description": {"type": "string"},
                "input_schema": {"type": "object"},
                "type": {"type": "string"},
            },
            "anyOf": [{"required": ["input_schema"]}, {"required": ["type"]}],
        },
    },
}

_TOOL_CALLS = {
    "$schema": JSON_SCHEMA_DIALECT,
    "title": "Tool calls",
    "anyOf": [
        {
            "type": "object",
            "required": ["name", "arguments"],
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "arguments": {"type": ["string", "object"]},
            },
        },
        {
            "type": "object",
            "required": ["type", "function"],
            "properties": {
                "type": {"const": "function"},
                "function": {
                    "type": "object",
                    "required": ["name", "arguments"],
                    "properties": {
                        "name": {"type": "string", "minLength": 1},
                        "arguments": {"type": ["string", "object"]},
                    },
                },
            },
        },
        {
            "type": "object",
            "required": ["type", "name", "input"],
            "properties": {
                "type": {"const": "tool_use"},
                "name": {"type": "string", "minLength": 1},
                "input": {"type": "object"},
            },
        },
    ],
}

_TRAIN_MESSAGE = {
    "type": "object",
    "required": ["role", "content"],
    "properties": {
        "role": {"enum": ["system", "developer", "user", "assistant", "tool"]},
        "content": {"type": ["string", "array", "null"]},
    },
}
_MESSAGES = {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/message"}}

_SFT = {
    "$schema": JSON_SCHEMA_DIALECT,
    "title": "Supervised fine-tuning rows",
    "anyOf": [
        {
            "type": "object",
            "required": ["messages"],
            "properties": {
                "messages": {
                    **_MESSAGES,
                    "contains": {"properties": {"role": {"const": "assistant"}}},
                }
            },
        },
        {
            "type": "object",
            "required": ["prompt", "completion"],
            "properties": {
                "prompt": {"anyOf": [{"type": "string"}, _MESSAGES]},
                "completion": {"anyOf": [{"type": "string", "minLength": 1}, _MESSAGES]},
            },
        },
        {
            "type": "object",
            "required": ["text"],
            "properties": {"text": {"type": "string", "minLength": 1}},
        },
    ],
    "$defs": {"message": _TRAIN_MESSAGE},
}

_RESPONSE = {"anyOf": [{"type": "string", "minLength": 1}, _MESSAGES]}

_DPO = {
    "$schema": JSON_SCHEMA_DIALECT,
    "title": "Preference (DPO) rows",
    "anyOf": [
        {
            "type": "object",
            "required": ["chosen", "rejected"],
            "properties": {
                "prompt": {"anyOf": [{"type": "string"}, _MESSAGES]},
                "chosen": _RESPONSE,
                "rejected": _RESPONSE,
            },
        },
        {
            "type": "object",
            "required": ["input", "preferred_output", "non_preferred_output"],
            "properties": {
                "input": {
                    "type": "object",
                    "required": ["messages"],
                    "properties": {"messages": _MESSAGES},
                },
                "preferred_output": _MESSAGES,
                "non_preferred_output": _MESSAGES,
            },
        },
    ],
    "$defs": {"message": _TRAIN_MESSAGE},
}

_RAG_CHUNKS = {
    "$schema": JSON_SCHEMA_DIALECT,
    "title": "RAG chunk records",
    "type": "object",
    "required": ["id", "text"],
    "properties": {
        "id": {"type": ["string", "integer"], "minLength": 1},
        "text": {"type": "string", "minLength": 1},
        "doc_id": {"type": ["string", "integer"]},
        "source": {"type": "string"},
        "title": {"type": "string"},
        "chunk_index": {"type": "integer", "minimum": 0},
        "start_char": {"type": "integer", "minimum": 0},
        "end_char": {"type": "integer", "minimum": 0},
        "metadata": {"type": "object"},
        "embedding": {"type": "array", "minItems": 1, "items": {"type": "number"}},
    },
}


# --------------------------------------------------------------------------- #
# Tool definitions
# --------------------------------------------------------------------------- #


class ToolsError(ValueError):
    """The tool definitions cannot be used."""


def parse_tools(obj: Any) -> dict[str, Any]:
    """Map tool name -> argument JSON Schema (``None`` when the tool has none).

    Accepts a list (or ``{"tools": [...]}``) of OpenAI tools
    (``{"type": "function", "function": {"name", "parameters"}}``), legacy
    OpenAI functions (``{"name", "parameters"}``) or Anthropic tools
    (``{"name", "input_schema"}``; Anthropic-defined tools with a ``type`` and
    no schema are accepted without argument checks).

    Raises:
        ToolsError: on a malformed definition or an unsupported schema.
    """
    if isinstance(obj, dict) and "tools" in obj:
        obj = obj["tools"]
    if not isinstance(obj, list):
        raise ToolsError("tools must be a list (or an object with a 'tools' list)")
    tools: dict[str, Any] = {}
    for i, t in enumerate(obj):
        if not isinstance(t, dict):
            raise ToolsError(f"tools[{i}] is not an object")
        spec = _dict(t.get("function")) or t
        name = spec.get("name")
        if not isinstance(name, str) or not name:
            raise ToolsError(f"tools[{i}] has no name")
        schema = spec.get("parameters", spec.get("input_schema"))
        if schema is not None:
            try:
                check_schema(schema)
            except SchemaError as e:
                raise ToolsError(f"tool {name!r}: {e}") from e
        tools[name] = schema
    return tools


# --------------------------------------------------------------------------- #
# Record-level checks
# --------------------------------------------------------------------------- #


def _dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


@dataclass
class _Call:
    name: Any
    args: Any  # JSON string (OpenAI) or object (Anthropic)
    call_id: Any = None


@dataclass
class RecordChecks:
    """Checks JSON Schema cannot express, run on every record of a preset."""

    preset: str
    tools: dict[str, Any] | None = None
    tool_calls_checked: int = 0
    tool_calls_unchecked: int = 0
    _validators: dict[str, Validator] = field(default_factory=dict)
    _chunk_ids: set[str] = field(default_factory=set)
    _embedding_dims: int | None = None

    def __call__(self, record: Any) -> list[Issue]:
        if not isinstance(record, dict):
            return []
        if self.preset in ("openai-chat", "anthropic-messages"):
            return self._chat(record)
        if self.preset == "tool-calls":
            return self._flat_tool_call(record)
        if self.preset == "dpo":
            return self._preference(record)
        if self.preset == "rag-chunks":
            return self._chunk(record)
        return []

    # -- tool calls --------------------------------------------------------- #

    def _record_tools(self, record: dict[str, Any]) -> dict[str, Any] | None:
        if "tools" in record:
            try:
                return parse_tools(record["tools"])
            except ToolsError:
                return None  # the JSON Schema check already reports the shape
        return self.tools

    def _check_call(self, call: _Call, tools: dict[str, Any] | None) -> list[Issue]:
        if tools is None:
            self.tool_calls_unchecked += 1
            return []
        self.tool_calls_checked += 1
        name = call.name if isinstance(call.name, str) else ""
        where = f"tool[{name}]"
        if name not in tools:
            return [("unknown_tool", where, "unknown_tool")]
        args = call.args
        if isinstance(args, str):
            try:
                args = strict_json_loads(args) if args.strip() else {}
            except ValueError:
                return [("tool_args_invalid_json", where, "tool_args_invalid_json")]
        if not isinstance(args, dict):
            return [("tool_args_not_object", where, "tool_args_not_object")]
        schema = tools[name]
        if schema is None:
            return []
        key = json.dumps(schema, sort_keys=True)
        v = self._validators.get(key)
        if v is None:
            v = self._validators[key] = Validator(schema, strict_integer=True)
        return [
            (f"tool_args_{kind}", where if path == "$" else f"{where}.{path}", message)
            for kind, path, message in v.errors(args)
        ]

    def _chat(self, record: dict[str, Any]) -> list[Issue]:
        tools = self._record_tools(record)
        issues: list[Issue] = []
        seen_ids: set[str] = set()
        anthropic = self.preset == "anthropic-messages"
        for msg in _list(record.get("messages")):
            msg = _dict(msg)
            calls: list[_Call] = []
            results: list[Any] = []
            if anthropic:
                for block in _list(msg.get("content")):
                    block = _dict(block)
                    if block.get("type") == "tool_use":
                        calls.append(_Call(block.get("name"), block.get("input"), block.get("id")))
                    elif block.get("type") == "tool_result":
                        results.append(block.get("tool_use_id"))
            else:
                for tc in _list(msg.get("tool_calls")):
                    fn = _dict(_dict(tc).get("function"))
                    calls.append(_Call(fn.get("name"), fn.get("arguments"), _dict(tc).get("id")))
                if msg.get("role") == "tool":
                    results.append(msg.get("tool_call_id"))
            for rid in results:
                if isinstance(rid, str) and rid not in seen_ids:
                    field_name = (
                        "messages[].content[].tool_use_id"
                        if anthropic
                        else ("messages[].tool_call_id")
                    )
                    issues.append(("orphan_tool_result", field_name, "orphan_tool_result"))
            for call in calls:
                if isinstance(call.call_id, str):
                    seen_ids.add(call.call_id)
                issues.extend(self._check_call(call, tools))
        return issues

    def _flat_tool_call(self, record: dict[str, Any]) -> list[Issue]:
        if record.get("type") == "tool_use":
            call = _Call(record.get("name"), record.get("input"))
        elif isinstance(record.get("function"), dict):
            fn = record["function"]
            call = _Call(fn.get("name"), fn.get("arguments"))
        else:
            call = _Call(record.get("name"), record.get("arguments"))
        return self._check_call(call, self.tools)

    # -- preference pairs --------------------------------------------------- #

    def _preference(self, record: dict[str, Any]) -> list[Issue]:
        if "chosen" in record and "rejected" in record:
            a, b, where = record["chosen"], record["rejected"], "chosen"
        elif "preferred_output" in record and "non_preferred_output" in record:
            a, b = record["preferred_output"], record["non_preferred_output"]
            where = "preferred_output"
        else:
            return []
        issues: list[Issue] = []
        if type(a) is not type(b):
            issues.append(("preference_type_mismatch", where, "chosen_and_rejected_differ_in_type"))
        elif a == b:
            issues.append(("preference_identical", where, "chosen_equals_rejected"))
        return issues

    # -- RAG chunks --------------------------------------------------------- #

    def _chunk(self, record: dict[str, Any]) -> list[Issue]:
        issues: list[Issue] = []
        cid = record.get("id")
        if isinstance(cid, (str, int)) and not isinstance(cid, bool):
            key = f"{type(cid).__name__}:{cid}"
            if key in self._chunk_ids:
                issues.append(("duplicate_id", "id", "duplicate_id"))
            self._chunk_ids.add(key)
        emb = record.get("embedding")
        if isinstance(emb, list) and emb:
            if self._embedding_dims is None:
                self._embedding_dims = len(emb)
            elif len(emb) != self._embedding_dims:
                issues.append(
                    (
                        "embedding_dimension_mismatch",
                        "embedding",
                        f"expected {self._embedding_dims} dimensions",
                    )
                )
        start, end = record.get("start_char"), record.get("end_char")
        if isinstance(start, int) and isinstance(end, int) and start > end:
            issues.append(("offset_order", "start_char", "start_char > end_char"))
        return issues

    def summary(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.preset in ("openai-chat", "anthropic-messages", "tool-calls"):
            out["tool_calls_checked"] = self.tool_calls_checked
            out["tool_calls_unchecked"] = self.tool_calls_unchecked
        return out


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Preset:
    name: str
    description: str
    schema: dict[str, Any]
    needs_tools: bool = False

    def contract(self) -> dict[str, Any]:
        return {
            "version": CONTRACT_VERSION,
            "name": self.name,
            "description": self.description,
            "schema": copy.deepcopy(self.schema),
        }

    def checks(self, tools: dict[str, Any] | None = None) -> RecordChecks:
        return RecordChecks(preset=self.name, tools=tools)


PRESETS: dict[str, Preset] = {
    p.name: p
    for p in (
        Preset(
            "openai-chat",
            "OpenAI chat rows; tool-call arguments checked against the row's tools or --tools",
            _OPENAI_CHAT,
        ),
        Preset(
            "anthropic-messages",
            "Anthropic Messages rows; tool_use inputs checked against the row's tools or --tools",
            _ANTHROPIC_MESSAGES,
        ),
        Preset(
            "tool-calls",
            "One tool call per row, arguments checked against --tools",
            _TOOL_CALLS,
            needs_tools=True,
        ),
        Preset(
            "sft", "SFT rows: messages with an assistant turn, prompt/completion, or text", _SFT
        ),
        Preset("dpo", "Preference rows: prompt/chosen/rejected or OpenAI preference format", _DPO),
        Preset("rag-chunks", "RAG chunks: id, text, offsets, metadata, embedding", _RAG_CHUNKS),
    )
}


def get_preset(name: str) -> Preset:
    try:
        return PRESETS[name]
    except KeyError as e:
        raise ValueError(f"unknown preset {name!r}; choose from {sorted(PRESETS)}") from e


CheckFn = Callable[[Any], list[Issue]]


def run_checks(checks: Iterable[CheckFn], record: Any) -> list[Issue]:
    out: list[Issue] = []
    for c in checks:
        out.extend(c(record))
    return out
