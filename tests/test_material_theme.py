"""Theme-token regression tests; work even without PySide6."""
from core.theme import (PRESETS, ThemeColors, contrast_ink,
                        relative_luminance, style_for, tokens_for)


def contrast_ratio(first, second):
    a, b = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def test_preset_primary_button_contrast():
    for theme in PRESETS.values():
        tokens = tokens_for(theme)
        assert contrast_ratio(tokens.accent, tokens.accent_ink) >= 4.5
        assert contrast_ratio(tokens.secondary, tokens.secondary_ink) >= 4.5
        assert contrast_ratio(tokens.background, tokens.text) >= 4.5


def test_custom_light_background_remains_legible():
    theme = ThemeColors("#fbe600", "#ec21ad", "#f1e6f7")
    tokens = tokens_for(theme)
    assert tokens.text == "#23152a"
    assert contrast_ink(theme.yellow) == "#1b1024"
    assert contrast_ratio(tokens.background, tokens.text) >= 4.5
    css = style_for(theme)
    assert "QComboBox#methodSelector" in css
    assert "QTabBar::tab:selected" in css
    assert "QPushButton#sendButton:disabled" in css


def test_dark_tokens_use_contrasting_text():
    theme = PRESETS["Electric"]
    tokens = tokens_for(theme)
    assert tokens.text == "#fffaff"
    assert contrast_ratio(tokens.field, tokens.text) >= 4.5
