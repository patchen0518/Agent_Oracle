"""Tool registration, schema emission, and dispatch."""

from __future__ import annotations

import functools
import inspect
import logging
import types
import typing
from dataclasses import dataclass, field
from typing import Annotated, Any, Callable, get_args, get_origin, get_type_hints

log = logging.getLogger(__name__)


def _type_to_json(annotation: Any) -> tuple[dict, bool]:
    """Return (json_schema_dict, is_optional)."""
    # Unwrap Annotated — handled by caller
    origin = get_origin(annotation)
    args = get_args(annotation)

    # X | None (Python 3.10+ union)
    if origin is types.UnionType:
        non_none = [a for a in args if a is not type(None)]
        optional = type(None) in args
        if len(non_none) == 1:
            schema, _ = _type_to_json(non_none[0])
            return schema, optional
        return {"type": "string"}, True

    # typing.Optional / typing.Union
    if origin is typing.Union:
        non_none = [a for a in args if a is not type(None)]
        optional = type(None) in args
        if len(non_none) == 1:
            schema, _ = _type_to_json(non_none[0])
            return schema, optional
        return {"type": "string"}, True

    if annotation is str:
        return {"type": "string"}, False
    if annotation is int:
        return {"type": "integer"}, False
    if annotation is float:
        return {"type": "number"}, False
    if annotation is bool:
        return {"type": "boolean"}, False

    if origin is list:
        item = args[0] if args else str
        item_schema, _ = _type_to_json(item)
        return {"type": "array", "items": item_schema}, False

    return {"type": "string"}, False  # fallback


def _build_schema(func: Callable) -> dict:
    """Build a JSON Schema object from a function's Annotated type hints."""
    try:
        hints = get_type_hints(func, include_extras=True)
    except Exception:
        hints = {}

    sig = inspect.signature(func)
    properties: dict[str, dict] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "ctx"):
            continue

        annotation = hints.get(param_name, str)
        description: str | None = None

        # Extract Annotated metadata
        if get_origin(annotation) is Annotated:
            inner_args = get_args(annotation)
            annotation = inner_args[0]
            description = next((a for a in inner_args[1:] if isinstance(a, str)), None)

        schema, is_optional = _type_to_json(annotation)
        if description:
            schema = {**schema, "description": description}
        properties[param_name] = schema

        if param.default is inspect.Parameter.empty and not is_optional:
            required.append(param_name)

    return {"type": "object", "properties": properties, "required": required}


@dataclass
class ToolDef:
    name: str
    description: str
    func: Callable
    parameters_schema: dict
    requires_permission: bool
    read_only: bool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}

    def register(self, td: ToolDef) -> None:
        self._tools[td.name] = td

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    def list_all(self) -> list[ToolDef]:
        return list(self._tools.values())

    def schemas(self) -> list[dict]:
        """Return the list of tool schemas for Ollama."""
        result = []
        for td in self._tools.values():
            result.append({
                "type": "function",
                "function": {
                    "name": td.name,
                    "description": td.description,
                    "parameters": td.parameters_schema,
                },
            })
        return result

    async def dispatch(self, name: str, args: dict) -> str:
        """Dispatch a tool call by name, returning a string result."""
        td = self._tools.get(name)
        if td is None:
            return f"[Tool error] Unknown tool: {name!r}"
        try:
            result = td.func(**args)
            if inspect.isawaitable(result):
                result = await result
            return str(result)
        except Exception as e:
            log.warning(f"Tool {name!r} raised: {e}")
            return f"[Tool error] {type(e).__name__}: {e}"


# Global registry — tools self-register on module import
REGISTRY = ToolRegistry()


def tool(
    description: str,
    *,
    requires_permission: bool = True,
    read_only: bool = False,
):
    """Decorator to register a tool in the global REGISTRY."""
    def decorator(func: Callable) -> Callable:
        schema = _build_schema(func)
        REGISTRY.register(ToolDef(
            name=func.__name__,
            description=description,
            func=func,
            parameters_schema=schema,
            requires_permission=requires_permission,
            read_only=read_only,
        ))

        @functools.wraps(func)
        async def wrapper(*a, **kw):
            result = func(*a, **kw)
            if inspect.isawaitable(result):
                return await result
            return result

        return wrapper

    return decorator
