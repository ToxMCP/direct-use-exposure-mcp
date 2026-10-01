"""Centralized logging configuration for Direct-Use Exposure MCP."""

from __future__ import annotations

import logging
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    """Log diagnostics to stderr, preserving stdout for MCP JSON-RPC messages."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger = logging.getLogger("exposure_scenario_mcp")
    root_logger.setLevel(level)
    root_logger.handlers = []
    root_logger.addHandler(handler)
    root_logger.propagate = False
