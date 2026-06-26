"""Gradio launch/runtime helpers for Docker, RunPod, and proxy environments."""

import logging
import os

logger = logging.getLogger(__name__)

_NO_PROXY_HOSTS = ("localhost", "127.0.0.1", "::1")


def configure_gradio_runtime_env():
    """Ensure Gradio can reach itself on localhost (common RunPod/proxy issue)."""
    for var in ("NO_PROXY", "no_proxy"):
        current = os.environ.get(var, "")
        parts = [part.strip() for part in current.split(",") if part.strip()]
        for host in _NO_PROXY_HOSTS:
            if host not in parts:
                parts.append(host)
        os.environ[var] = ",".join(parts)


def build_gradio_launch_kwargs(args, app_logger):
    configure_gradio_runtime_env()
    launch_kwargs = dict(
        max_threads=1,
        share=args.public_url,
        server_name=os.environ.get("GRADIO_SERVER_NAME", "127.0.0.1"),
        server_port=int(os.environ.get("GRADIO_SERVER_PORT", "7860")),
        show_error=True,
        quiet=False,
        debug=app_logger.isEnabledFor(logging.DEBUG),
    )
    root_path = os.environ.get("GRADIO_ROOT_PATH", "").strip()
    if root_path:
        launch_kwargs["root_path"] = root_path
    return launch_kwargs
