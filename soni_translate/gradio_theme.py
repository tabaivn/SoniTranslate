"""Gradio theme helpers — safe across gradio 4.x (no hard-coded missing themes)."""

import logging
import os

logger = logging.getLogger(__name__)

# gradio 4.44.1 exports: Default, Glass, Monochrome, Soft (see gradio/themes/__init__.py).
_BUILTIN_THEME_CLASS_NAMES = ("Soft", "Default", "Monochrome", "Glass")
_DEFAULT_THEME_KEY = "soft"


def get_gradio_builtin_theme_names():
    import gradio as gr

    return [
        cls_name.lower()
        for cls_name in _BUILTIN_THEME_CLASS_NAMES
        if hasattr(gr.themes, cls_name)
    ]


def resolve_gradio_theme(theme):
    import gradio as gr

    available = {}
    for cls_name in _BUILTIN_THEME_CLASS_NAMES:
        theme_cls = getattr(gr.themes, cls_name, None)
        if callable(theme_cls):
            available[cls_name.lower()] = theme_cls

    if not available:
        raise RuntimeError(
            "No built-in Gradio themes found. Check your gradio installation."
        )

    fallback_key = (
        _DEFAULT_THEME_KEY
        if _DEFAULT_THEME_KEY in available
        else next(iter(available))
    )

    if not isinstance(theme, str) or not theme.strip():
        return available[fallback_key]()

    key = theme.strip().lower()
    if key in available:
        return available[key]()

    if "/" in theme and os.environ.get("SONITR_ALLOW_HF_THEME", "0") == "1":
        return theme

    logger.info(
        "Gradio theme '%s' is unavailable or needs Hugging Face download; "
        "using '%s'. Built-in options: %s. "
        "Set SONITR_ALLOW_HF_THEME=1 to use Hugging Face theme ids.",
        theme,
        fallback_key,
        ", ".join(sorted(available)),
    )
    return available[fallback_key]()
