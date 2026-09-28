"""Claude model presets for Anthropic Messages and OpenRouter."""

from typing import Any

from kohakuterrarium.llm.preset_groups import (
    _ANTHROPIC_EFFORT_46_GROUP,
    _ANTHROPIC_EFFORT_47_GROUP,
    _OR_REASONING_GROUP,
    _OR_REASONING_GROUP_WITH_XHIGH,
)

PRESETS: dict[str, dict[str, Any]] = {
    # ═══════════════════════════════════════════════════════
    #  Anthropic Claude Direct API (primary — non-OpenAI format,
    #  requires the dedicated ``anthropic`` backend_type client).
    #
    #  Adaptive thinking is the only thinking mode on 4.7+:
    #    Fable 5, Opus 5.5: thinking always on; effort low…xhigh/max
    #    Opus 4.7/4.8, Sonnet 5: adaptive; effort low…xhigh/max
    #    Opus 4.6 / Sonnet 4.6:  adaptive; effort low…high/max
    #  ``thinking.display`` defaults to "omitted" on Fable 5 /
    #  Opus 4.7/4.8 / Sonnet 5 — we opt in to "summarized" so the
    #  UI can show the reasoning trace.
    # ═══════════════════════════════════════════════════════
    "claude-fable-5": {
        "provider": "anthropic",
        "model": "claude-fable-5",
        "max_context": 1000000,
        # Thinking is always on for Fable 5 (explicit ``adaptive`` is
        # accepted; ``disabled`` is rejected with a 400). The raw chain of
        # thought is never returned — "summarized" is the visible option.
        # NOTE: requires 30-day data retention on the org (no ZDR).
        "extra_body": {
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": "high"},
        },
        "variation_groups": {"reasoning": _ANTHROPIC_EFFORT_47_GROUP},
    },
    "claude-opus-5.5": {
        "provider": "anthropic",
        "model": "claude-opus-5-5",
        "max_context": 1000000,
        "max_output": 128000,
        # Opus 5.5 always uses adaptive thinking; medium is its default effort.
        "extra_body": {
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": "medium"},
        },
        "variation_groups": {"reasoning": _ANTHROPIC_EFFORT_47_GROUP},
    },
    "claude-opus-4.8": {
        "provider": "anthropic",
        "model": "claude-opus-4-8",
        "max_context": 1000000,
        # 4.8 guidance: start at ``high`` and sweep — reflexive xhigh is
        # no longer the best default (higher ceiling than 4.7).
        "extra_body": {
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": "high"},
        },
        "variation_groups": {"reasoning": _ANTHROPIC_EFFORT_47_GROUP},
    },
    "claude-opus-4.7": {
        "provider": "anthropic",
        "model": "claude-opus-4-7",
        "max_context": 1000000,
        # Opus 4.7 defaults ``thinking.display`` to ``"omitted"`` — we
        # explicitly opt in to summarized thinking for the UI trace.
        "extra_body": {
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": "xhigh"},
        },
        "variation_groups": {"reasoning": _ANTHROPIC_EFFORT_47_GROUP},
    },
    "claude-opus-4.6": {
        "provider": "anthropic",
        "model": "claude-opus-4-6",
        "max_context": 1000000,
        "extra_body": {
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "high"},
        },
        "variation_groups": {"reasoning": _ANTHROPIC_EFFORT_46_GROUP},
    },
    "claude-sonnet-5": {
        "provider": "anthropic",
        "model": "claude-sonnet-5",
        "max_context": 1000000,
        # Sonnet 5 runs adaptive thinking even when the field is omitted;
        # we keep it explicit + summarized for a visible trace. Full effort
        # scale incl. xhigh (first Sonnet with it).
        "extra_body": {
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": "high"},
        },
        "variation_groups": {"reasoning": _ANTHROPIC_EFFORT_47_GROUP},
    },
    "claude-sonnet-4.6": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "max_context": 1000000,
        "extra_body": {
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "high"},
        },
        "variation_groups": {"reasoning": _ANTHROPIC_EFFORT_46_GROUP},
    },
    "claude-haiku-4.5": {
        "provider": "anthropic",
        "model": "claude-haiku-4-5",
        "max_context": 200000,
        # Haiku 4.5 uses the older extended-thinking (budget_tokens), not the
        # adaptive effort scale — not exposed as a variation group here.
    },
    # ═══════════════════════════════════════════════════════
    #  Anthropic Claude via OpenRouter (-or suffix).
    #  OR normalizes reasoning knobs via its unified param.
    #  xhigh is honored by Fable 5 / Opus 4.7+ / Sonnet 5.
    # ═══════════════════════════════════════════════════════
    "claude-fable-5-or": {
        "provider": "openrouter",
        "model": "anthropic/claude-fable-5",
        "max_context": 1000000,
        "max_output": 128000,
        "extra_body": {
            "reasoning": {"enabled": True, "effort": "high"},
            "cache_control": {"type": "ephemeral"},
        },
        "variation_groups": {"reasoning": _OR_REASONING_GROUP_WITH_XHIGH},
    },
    "claude-opus-5.5-or": {
        "provider": "openrouter",
        "model": "anthropic/claude-opus-5.5",
        "max_context": 1000000,
        "max_output": 128000,
        "extra_body": {
            "reasoning": {"enabled": True, "effort": "medium"},
            "cache_control": {"type": "ephemeral"},
        },
        "variation_groups": {"reasoning": _OR_REASONING_GROUP_WITH_XHIGH},
    },
    "claude-opus-4.8-or": {
        "provider": "openrouter",
        "model": "anthropic/claude-opus-4.8",
        "max_context": 1000000,
        "extra_body": {
            "reasoning": {"enabled": True, "effort": "high"},
            "cache_control": {"type": "ephemeral"},
        },
        "variation_groups": {"reasoning": _OR_REASONING_GROUP_WITH_XHIGH},
    },
    "claude-opus-4.7-or": {
        "provider": "openrouter",
        "model": "anthropic/claude-opus-4.7",
        "max_context": 1000000,
        "extra_body": {
            "reasoning": {"enabled": True, "effort": "high"},
            "cache_control": {"type": "ephemeral"},
        },
        "variation_groups": {"reasoning": _OR_REASONING_GROUP_WITH_XHIGH},
    },
    "claude-opus-4.6-or": {
        "provider": "openrouter",
        "model": "anthropic/claude-opus-4.6",
        "max_context": 1000000,
        "extra_body": {
            "reasoning": {"enabled": True, "effort": "high"},
            "cache_control": {"type": "ephemeral"},
        },
        "variation_groups": {"reasoning": _OR_REASONING_GROUP},
    },
    "claude-sonnet-5-or": {
        "provider": "openrouter",
        "model": "anthropic/claude-sonnet-5",
        "max_context": 1000000,
        "extra_body": {
            "reasoning": {"enabled": True, "effort": "high"},
            "cache_control": {"type": "ephemeral"},
        },
        "variation_groups": {"reasoning": _OR_REASONING_GROUP_WITH_XHIGH},
    },
    "claude-sonnet-4.6-or": {
        "provider": "openrouter",
        "model": "anthropic/claude-sonnet-4.6",
        "max_context": 1000000,
        "extra_body": {
            "reasoning": {"enabled": True, "effort": "high"},
            "cache_control": {"type": "ephemeral"},
        },
        "variation_groups": {"reasoning": _OR_REASONING_GROUP},
    },
    "claude-haiku-4.5-or": {
        "provider": "openrouter",
        "model": "anthropic/claude-haiku-4.5",
        "max_context": 200000,
        "max_output": 64000,
        "extra_body": {
            "cache_control": {"type": "ephemeral"},
        },
        "variation_groups": {
            "reasoning": {
                "off": {"extra_body.reasoning.enabled": False},
                "low": {
                    "extra_body.reasoning.enabled": True,
                    "extra_body.reasoning.effort": "low",
                },
                "medium": {
                    "extra_body.reasoning.enabled": True,
                    "extra_body.reasoning.effort": "medium",
                },
                "high": {
                    "extra_body.reasoning.enabled": True,
                    "extra_body.reasoning.effort": "high",
                },
            }
        },
    },
}
