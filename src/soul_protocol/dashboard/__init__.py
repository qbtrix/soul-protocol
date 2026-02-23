# dashboard/__init__.py — Soul Protocol visual dashboard
# Created: v0.3.0 — Provides a local web UI for visualizing soul identity,
#   memory, and state. Zero extra dependencies (stdlib http.server).

from .app import start_dashboard

__all__ = ["start_dashboard"]
