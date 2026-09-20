"""Opt-in stored Responses continuation with verified history prefixes."""

import asyncio
import hashlib
import json
from typing import Any, AsyncIterator, Callable

from kohakuterrarium.utils.logging import get_logger
from kohakuterrarium.llm.codex_format import to_responses_input

logger = get_logger(__name__)


def merged_reasoning(effort, extra):
    """Combine a provider effort with explicit Responses reasoning overrides."""
    result = {"effort": effort} if effort and effort != "none" else {}
    if isinstance(extra.get("reasoning"), dict):
        result.update(extra["reasoning"])
    return result


def wire_extra_body(extra):
    """Exclude framework transport controls and separately merged reasoning."""
    return {
        key: value
        for key, value in extra.items()
        if key
        not in {
            "reasoning",
            "websocket_mode",
            "http_continuation",
            "disable_prompt_caching",
        }
    }


def assistant_input(model, text, fields, calls):
    """Convert a completed provider turn to its expected conversation echo."""
    message = {
        "role": "assistant",
        "content": "".join(text),
        **fields,
        "tool_calls": [
            {
                "id": call.id,
                "function": {"name": call.name, "arguments": call.arguments},
            }
            for call in calls
        ],
    }
    return to_responses_input([message], model=model)


def _fingerprints(items: list[dict[str, Any]]) -> tuple[bytes, ...]:
    return tuple(
        hashlib.sha256(
            json.dumps(item, sort_keys=True, ensure_ascii=False).encode()
        ).digest()
        for item in items
    )


def _missing_previous(exc: Exception) -> bool:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error", body)
        if isinstance(error, dict):
            return error.get("code") in {
                "previous_response_not_found",
                "previous_response_id_not_found",
            }
    return False


class ResponsesHTTPSession:
    """Retain one completed response ID and fingerprints of its exact input echo."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._previous: str | None = None
        self._known: tuple[bytes, ...] = ()

    def invalidate(self) -> None:
        self._previous = None
        self._known = ()

    async def stream_turn(
        self,
        create: Callable[..., Any],
        params: dict[str, Any],
        items: list[dict[str, Any]],
        pairing_fix: Callable[..., Any],
        assistant_echo: Callable[[], list[dict[str, Any]]],
    ) -> AsyncIterator[Any]:
        """Send a delta for an unchanged prefix; recover explicit pre-output misses once."""
        async with self._lock:
            fingerprints = _fingerprints(items)
            known = self._known
            previous = self._previous
            delta = bool(
                previous
                and len(items) > len(known)
                and fingerprints[: len(known)] == known
            )
            self.invalidate()
            request = {**params, "store": True, "stream": True}
            request["input"] = items[len(known) :] if delta else pairing_fix(items)
            if delta:
                request["previous_response_id"] = previous
            try:
                stream = await create(**request)
            except Exception as exc:
                if not delta or not _missing_previous(exc):
                    raise
                logger.warning(
                    "Stored Responses context expired; resending full history"
                )
                request.pop("previous_response_id")
                request["input"] = pairing_fix(items)
                stream = await create(**request)
            completed = None
            try:
                async for event in stream:
                    kind = getattr(event, "type", "")
                    if kind in {"error", "response.failed", "response.incomplete"}:
                        raise RuntimeError(f"Responses stream ended with {kind}")
                    if kind == "response.completed":
                        completed = getattr(event, "response", None)
                    yield event
            finally:
                await stream.close()
            if completed is None:
                raise RuntimeError("Responses stream ended before response.completed")
            if (
                getattr(completed, "status", None) == "completed"
                and getattr(completed, "store", True) is not False
                and getattr(completed, "id", None)
            ):
                self._previous = completed.id
                self._known = fingerprints + _fingerprints(assistant_echo())
