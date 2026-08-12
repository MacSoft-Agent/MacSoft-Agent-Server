"""Schema-driven validation for every official AutoCount command.

The module intentionally contains no command-specific rules. It supports both
JSON Schema-shaped metadata and the descriptive payload/native metadata exposed
by the current AutoCount Cloud catalog.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any


_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_REQUIRED = re.compile(r"\brequired\b", re.IGNORECASE)
_CONDITIONAL_REQUIRED = re.compile(
    r"\brequired\s+or\s+optional\b|\boptional\b.{0,24}\brequired\b|"
    r"\brequired\b.{0,48}\bonly\s+for\b",
    re.IGNORECASE,
)
_ALIAS_FOR = re.compile(
    r"\b(?:optional\s+)?alias\s+for\s+([A-Za-z][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
_ALSO_ALIAS = re.compile(
    r"\b([A-Za-z][A-Za-z0-9_]*)\s+is\s+also\s+accepted\s+as\s+(?:a\s+)?(?:compatibility\s+)?alias\b",
    re.IGNORECASE,
)


@dataclass
class ValidationResult:
    valid: bool = True
    missing_fields: list[dict[str, Any]] = field(default_factory=list)
    unknown_fields: list[dict[str, Any]] = field(default_factory=list)
    type_errors: list[dict[str, Any]] = field(default_factory=list)
    location_errors: list[dict[str, Any]] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def add(self, category: str, **issue: Any) -> None:
        getattr(self, category).append(issue)
        self.valid = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "missing_fields": self.missing_fields,
            "unknown_fields": self.unknown_fields,
            "type_errors": self.type_errors,
            "location_errors": self.location_errors,
            "suggestions": self.suggestions,
        }


def _schema_body(schema_response: dict[str, Any]) -> dict[str, Any]:
    current = schema_response
    for _ in range(3):
        data = current.get("data")
        if not isinstance(data, dict):
            break
        if any(key in current for key in ("payloadSchema", "nativePayload", "properties")):
            break
        current = data
    return current


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return value.__class__.__name__


def _matches_type(value: Any, expected: str) -> bool:
    return {
        "null": value is None,
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "string": isinstance(value, str),
        "array": isinstance(value, list),
        "object": isinstance(value, dict),
    }.get(expected, True)


def _validate_json_schema(
    value: Any,
    schema: dict[str, Any],
    *,
    path: str,
    result: ValidationResult,
) -> None:
    nullable = bool(schema.get("nullable"))
    raw_type = schema.get("type")
    allowed_types = raw_type if isinstance(raw_type, list) else [raw_type]
    allowed_types = [str(item) for item in allowed_types if item]
    if nullable and "null" not in allowed_types:
        allowed_types.append("null")

    if value is None and (nullable or "null" in allowed_types):
        return
    if allowed_types and not any(_matches_type(value, expected) for expected in allowed_types):
        result.add(
            "type_errors",
            path=path,
            expected=" or ".join(allowed_types),
            actual=_type_name(value),
        )
        return

    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        result.add(
            "type_errors",
            path=path,
            expected="one of the official enum values",
            actual=str(value),
        )

    if isinstance(value, str) and schema.get("format") == "date":
        try:
            if not _DATE.fullmatch(value):
                raise ValueError
            date.fromisoformat(value)
        except ValueError:
            result.add(
                "type_errors",
                path=path,
                expected="YYYY-MM-DD date",
                actual=value,
            )

    if isinstance(value, dict):
        properties = schema.get("properties")
        if isinstance(properties, dict):
            required = schema.get("required", [])
            if isinstance(required, list):
                for key in required:
                    if key not in value:
                        child_schema = properties.get(key)
                        issue: dict[str, Any] = {
                            "path": f"{path}.{key}",
                            "field": str(key),
                            "message": "Required by the official schema.",
                        }
                        if isinstance(child_schema, dict):
                            title = child_schema.get("title")
                            description = child_schema.get("description")
                            if isinstance(title, str) and title.strip():
                                issue["title"] = title.strip()
                            if isinstance(description, str) and description.strip():
                                issue["description"] = description.strip()
                        result.add(
                            "missing_fields",
                            **issue,
                        )
            for key, item in value.items():
                child_schema = properties.get(key)
                if not isinstance(child_schema, dict):
                    result.add(
                        "unknown_fields",
                        path=f"{path}.{key}",
                        message="Field is not defined by the official schema.",
                    )
                    continue
                _validate_json_schema(
                    item,
                    child_schema,
                    path=f"{path}.{key}",
                    result=result,
                )

    if isinstance(value, list):
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if isinstance(minimum, int) and len(value) < minimum:
            result.add(
                "type_errors",
                path=path,
                expected=f"at least {minimum} items",
                actual=str(len(value)),
            )
        if isinstance(maximum, int) and len(value) > maximum:
            result.add(
                "type_errors",
                path=path,
                expected=f"at most {maximum} items",
                actual=str(len(value)),
            )
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value):
                _validate_json_schema(
                    item,
                    items,
                    path=f"{path}[{index}]",
                    result=result,
                )


def _native_sections(schema: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    native = schema.get("nativePayload")
    if not isinstance(native, dict):
        return {}
    sections = native.get("sections")
    if not isinstance(sections, list):
        return {}

    result: dict[str, dict[str, dict[str, Any]]] = {}
    for section in sections:
        if not isinstance(section, dict):
            continue
        name = str(section.get("name") or section.get("id") or section.get("section") or "").strip().lower()
        fields = section.get("fields")
        if not name or not isinstance(fields, list):
            continue
        mapped: dict[str, dict[str, Any]] = {}
        for item in fields:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            names = [str(item["name"])]
            aliases = item.get("aliases", [])
            if isinstance(aliases, str):
                names.append(aliases)
            elif isinstance(aliases, list):
                names.extend(str(alias) for alias in aliases)
            for field_name in names:
                mapped[field_name.lower()] = item
        result[name] = mapped
    return result


def _expected_from_description(description: str, example: Any) -> str | None:
    lowered = description.lower()
    if "array" in lowered:
        return "array"
    if "boolean" in lowered or "true/false" in lowered:
        return "boolean"
    if re.search(r"\b(integer|whole number)\b", lowered):
        return "integer"
    # Business identifiers are text even when their description uses phrases
    # such as "account number" or "document number". Check identifier meaning
    # before treating the bare word "number" as a JSON numeric type.
    if re.search(
        r"\b(account|document|invoice|reference|registration|serial|cheque|check)\s+number\b",
        lowered,
    ):
        return "string"
    if re.search(r"\b(number|numeric|decimal)\b", lowered):
        return "number"
    if "object" in lowered:
        return "object"
    if "string" in lowered or "yyyy-mm-dd" in lowered or "code" in lowered:
        return "string"
    if example is not None:
        return _type_name(example)
    return None


def _validate_descriptive_schema(
    payload: dict[str, Any],
    schema: dict[str, Any],
    payload_schema: dict[str, Any],
    result: ValidationResult,
) -> None:
    examples = schema.get("examplePayload")
    if not isinstance(examples, dict):
        examples = {}
    sections = _native_sections(schema)
    master = sections.get("master", {})
    details = sections.get("details", {}) or sections.get("detail", {})

    alias_to_target: dict[str, str] = {}
    for key, raw_description in payload_schema.items():
        description = str(raw_description)
        alias_match = _ALIAS_FOR.search(description)
        if alias_match:
            alias_to_target[key] = alias_match.group(1)
        for match in _ALSO_ALIAS.finditer(description):
            alias_to_target[match.group(1)] = key

    present = set(payload)
    for key, raw_description in payload_schema.items():
        description = str(raw_description)
        if not _REQUIRED.search(description) or _CONDITIONAL_REQUIRED.search(description):
            continue
        accepted = {key}
        accepted.update(alias for alias, target in alias_to_target.items() if target == key)
        target = alias_to_target.get(key)
        if target:
            accepted.add(target)
        if not present.intersection(accepted):
            result.add(
                "missing_fields",
                path=f"$.{key}",
                field=key,
                description=description,
                message="Required by the official command metadata.",
            )

    allowed_root = set(payload_schema)
    detail_names = set(details)
    master_names = set(master)
    line_containers: set[str] = set()

    for key, value in payload.items():
        if key not in allowed_root:
            lowered = key.lower()
            if lowered in detail_names and lowered not in master_names:
                result.add(
                    "location_errors",
                    path=f"$.{key}",
                    message="This official Detail field cannot be placed in Master/root data.",
                )
            else:
                result.add(
                    "unknown_fields",
                    path=f"$.{key}",
                    message="Field is not defined by the official payload schema.",
                )
            continue

        description = str(payload_schema[key])
        native_metadata = master.get(key.lower())
        expected = (
            str(native_metadata.get("type") or "").lower()
            if isinstance(native_metadata, dict)
            else ""
        )
        if not expected:
            expected = _expected_from_description(description, examples.get(key))
        if expected and not _matches_type(value, expected):
            result.add(
                "type_errors",
                path=f"$.{key}",
                expected=expected,
                actual=_type_name(value),
            )
            continue
        if "yyyy-mm-dd" in description.lower() and isinstance(value, str):
            try:
                if not _DATE.fullmatch(value):
                    raise ValueError
                date.fromisoformat(value)
            except ValueError:
                result.add(
                    "type_errors",
                    path=f"$.{key}",
                    expected="YYYY-MM-DD date",
                    actual=value,
                )
        if isinstance(value, list) and re.search(r"\b(item|line|detail|row)s?\b", description, re.IGNORECASE):
            line_containers.add(key)

    for key in line_containers:
        rows = payload.get(key)
        if not isinstance(rows, list):
            continue
        for index, row in enumerate(rows):
            row_path = f"$.{key}[{index}]"
            if not isinstance(row, dict):
                result.add(
                    "type_errors",
                    path=row_path,
                    expected="object",
                    actual=_type_name(row),
                )
                continue
            for field_name, value in row.items():
                metadata = details.get(field_name.lower())
                if metadata is None:
                    if field_name.lower() in master_names:
                        result.add(
                            "location_errors",
                            path=f"{row_path}.{field_name}",
                            message="This official Master field cannot be placed in a Detail row.",
                        )
                    else:
                        result.add(
                            "unknown_fields",
                            path=f"{row_path}.{field_name}",
                            message="Detail field is not defined by the official native metadata.",
                        )
                    continue
                expected = str(metadata.get("type") or "").lower()
                if expected and not _matches_type(value, expected):
                    result.add(
                        "type_errors",
                        path=f"{row_path}.{field_name}",
                        expected=expected,
                        actual=_type_name(value),
                    )


def validate_command_payload(
    schema_response: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    result = ValidationResult()
    if not isinstance(payload, dict):
        result.add(
            "type_errors",
            path="$",
            expected="object",
            actual=_type_name(payload),
        )
        return result.as_dict()

    schema = _schema_body(schema_response)
    payload_schema = schema.get("payloadSchema")
    if not isinstance(payload_schema, dict):
        if isinstance(schema.get("properties"), dict):
            payload_schema = schema
        else:
            result.add(
                "type_errors",
                path="$schema",
                expected="official payload schema",
                actual="missing",
            )
            return result.as_dict()

    if "properties" in payload_schema or payload_schema.get("type") == "object":
        _validate_json_schema(payload, payload_schema, path="$", result=result)
    else:
        _validate_descriptive_schema(payload, schema, payload_schema, result)
    return result.as_dict()
