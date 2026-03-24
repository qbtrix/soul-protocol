#!/usr/bin/env bash
# setup.sh — Install soul-protocol and configure MCP server for the current agent.
# Run by the agent after skill installation.

set -euo pipefail

echo "Installing soul-protocol with MCP support..."
pip install "soul-protocol[mcp]" --quiet 2>/dev/null || \
  uv pip install "soul-protocol[mcp]" --quiet 2>/dev/null || \
  echo "Could not install soul-protocol. Please install manually: pip install soul-protocol[mcp]"

# Auto-detect agent and configure MCP
if command -v soul &>/dev/null; then
  # Try to detect agent type from environment
  if [ -n "${CLAUDE_CODE:-}" ] || [ -d ".claude" ]; then
    echo "Detected Claude Code — configuring MCP server..."
    soul inject --target claude-code 2>/dev/null || true
  elif [ -d ".cursor" ]; then
    echo "Detected Cursor — configuring MCP server..."
    soul inject --target cursor 2>/dev/null || true
  elif [ -d ".vscode" ]; then
    echo "Detected VS Code — configuring MCP server..."
    soul inject --target vscode 2>/dev/null || true
  fi

  # Initialize a default soul if none exists
  if [ ! -d ".soul" ] && [ ! -f "*.soul" ]; then
    echo "No soul found — creating default soul..."
    mkdir -p .soul
    soul birth "Assistant" --output .soul/assistant.soul 2>/dev/null || true
  fi

  echo "Soul Protocol ready. Use soul_state to check the soul."
else
  echo "soul CLI not found in PATH. You may need to restart your shell."
fi
