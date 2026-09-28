"""Claude preset routing and effort settings use each provider's wire format."""

import pytest

from kohakuterrarium.llm.anthropic_presets import PRESETS
from kohakuterrarium.llm.variations import apply_variation_groups


class TestAnthropicPresets:
    def test_anthropic_direct_presets_use_anthropic_provider(self):
        assert PRESETS["claude-opus-4.7"]["provider"] == "anthropic"
        assert PRESETS["claude-opus-4.7"]["model"] == "claude-opus-4-7"
        assert PRESETS["claude-opus-4.8"]["provider"] == "anthropic"
        assert PRESETS["claude-opus-4.8"]["model"] == "claude-opus-4-8"
        assert PRESETS["claude-fable-5"]["provider"] == "anthropic"
        assert PRESETS["claude-fable-5"]["model"] == "claude-fable-5"
        assert PRESETS["claude-sonnet-5"]["provider"] == "anthropic"
        assert PRESETS["claude-sonnet-5"]["model"] == "claude-sonnet-5"

    @pytest.mark.parametrize(
        "name, model, field",
        [
            ("claude-opus-5.5", "claude-opus-5-5", "output_config"),
            ("claude-opus-5.5-or", "anthropic/claude-opus-5.5", "reasoning"),
        ],
    )
    def test_opus55_effort_preserves_always_on_thinking(self, name, model, field):
        preset = PRESETS[name]
        assert preset["model"] == model
        assert (preset["max_context"], preset["max_output"]) == (1_000_000, 128_000)
        assert preset["extra_body"][field]["effort"] == "medium"
        assert "off" not in preset["variation_groups"]["reasoning"]
        assert "none" not in preset["variation_groups"]["reasoning"]
        assert "temperature" not in preset
        for effort in preset["variation_groups"]["reasoning"]:
            selected = apply_variation_groups(
                preset, preset["variation_groups"], {"reasoning": effort}
            )
            assert selected["extra_body"][field]["effort"] == effort
            if field == "output_config":
                assert selected["extra_body"]["thinking"] == {
                    "type": "adaptive",
                    "display": "summarized",
                }
            else:
                assert selected["extra_body"]["reasoning"]["enabled"] is True
        assert preset["extra_body"][field]["effort"] == "medium"
