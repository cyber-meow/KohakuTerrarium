"""Stored continuation through the real SDK with deterministic HTTP responses."""

import json

import httpx
import pytest

from kohakuterrarium.llm.codex_provider import CodexOAuthProvider


class TestResponsesHTTP:
    async def provider(self, handler, *, enabled=True):
        provider = CodexOAuthProvider(
            model="slurm/deepseek-v4.1-abl",
            api_key="test",
            base_url="https://responses.test/v1",
            reasoning_effort="none",
            http_continuation=enabled,
            max_retries=0,
            retry_policy={"max_retries": 0},
        )
        await provider.ensure_authenticated()
        original = provider._client
        provider._client = original.with_options(
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        )
        await original.close()
        return provider

    def response(self, response_id="resp_1", *, extra=(), completed=True):
        events = [*extra, {"type": "response.output_text.delta", "delta": "READY"}]
        if completed:
            events.append(
                {
                    "type": "response.completed",
                    "response": {
                        "id": response_id,
                        "status": "completed",
                        "store": True,
                        "output": [],
                    },
                }
            )
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content="".join(f"data: {json.dumps(event)}\n\n" for event in events),
        )

    async def test_delta_images_tools_history_edits_and_default_opt_out(self):
        calls = []

        def handler(request):
            calls.append(json.loads(request.content))
            return self.response(f"resp_{len(calls)}")

        provider = await self.provider(handler)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Remember this"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,AAAA"},
                    },
                ],
            }
        ]
        try:
            first = await provider.chat_complete(messages)
            messages += [
                {"role": "assistant", "content": first.content},
                {"role": "user", "content": "Which color?"},
            ]
            await provider.chat_complete(messages)
            assert calls[1]["previous_response_id"] == "resp_1"
            assert calls[1]["input"] == [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Which color?"}],
                }
            ]
            assert "image" not in json.dumps(calls[1])
            messages[1]["content"] = "edited assistant answer"
            messages += [
                {"role": "assistant", "content": "READY"},
                {"role": "user", "content": "next"},
            ]
            await provider.chat_complete(messages)
            assert "previous_response_id" not in calls[2]
            assert "edited assistant answer" in json.dumps(calls[2])
            assert "input_image" in json.dumps(calls[2])
        finally:
            await provider.close()
        provider = await self.provider(handler, enabled=False)
        try:
            await provider.chat_complete(messages)
            assert calls[-1]["store"] is False
            assert "previous_response_id" not in calls[-1]
        finally:
            await provider.close()

    async def test_expired_id_recovers_once_but_other_404_does_not(self):
        calls = []
        code = "previous_response_not_found"

        def handler(request):
            body = json.loads(request.content)
            calls.append(body)
            if body.get("previous_response_id"):
                return httpx.Response(
                    404, json={"error": {"code": code, "message": "missing"}}
                )
            return self.response(f"resp_{len(calls)}")

        provider = await self.provider(handler)
        messages = [{"role": "user", "content": "first"}]
        try:
            await provider.chat_complete(messages)
            messages += [
                {"role": "assistant", "content": "READY"},
                {"role": "user", "content": "next"},
            ]
            await provider.chat_complete(messages)
            assert len(calls) == 3
            assert "previous_response_id" in calls[1]
            assert "previous_response_id" not in calls[2]
            assert len(calls[2]["input"]) == 3
            code = "model_not_found"
            messages += [
                {"role": "assistant", "content": "READY"},
                {"role": "user", "content": "third"},
            ]
            with pytest.raises(Exception, match="missing"):
                await provider.chat_complete(messages)
            assert len(calls) == 4
        finally:
            await provider.close()

    async def test_tool_delta_retains_output_without_synthetic_pairing(self):
        calls = []
        tool = {
            "type": "function_call",
            "call_id": "call_a",
            "name": "lookup",
            "arguments": "{}",
        }

        def handler(request):
            calls.append(json.loads(request.content))
            return self.response(
                extra=[
                    {
                        "type": "response.output_item.done",
                        "output_index": 0,
                        "item": tool,
                    }
                ]
            )

        provider = await self.provider(handler)
        messages = [{"role": "user", "content": "look it up"}]
        try:
            await provider.chat_complete(messages)
            messages += [
                {
                    "role": "assistant",
                    "content": "READY",
                    "tool_calls": [
                        {
                            "id": "call_a",
                            "function": {"name": "lookup", "arguments": "{}"},
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": "call_a", "content": "42"},
            ]
            await provider.chat_complete(messages)
            assert calls[1]["input"] == [
                {"type": "function_call_output", "call_id": "call_a", "output": "42"}
            ]
            assert calls[1]["previous_response_id"] == "resp_1"
        finally:
            await provider.close()

    async def test_truncated_stream_never_commits_or_retries_output(self):
        calls = []

        def handler(request):
            calls.append(json.loads(request.content))
            return self.response(completed=False)

        provider = await self.provider(handler)
        try:
            with pytest.raises(RuntimeError, match="before response.completed"):
                await provider.chat_complete([{"role": "user", "content": "hi"}])
            assert len(calls) == 1
            assert provider._http_session._previous is None
        finally:
            await provider.close()
