# FAQ

## Installation

### Python/pip not installed (common on Android/mobile projects)

If you get `command not found: pip` or `command not found: python`, you need to install Python first:

**macOS:**
```bash
# Install Python via Homebrew
brew install python

# Or download from python.org
# https://www.python.org/downloads/
```

**After installation, use `pip3` instead of `pip`:**
```bash
pip3 install git+https://github.com/igor-kats/claude-swarm.git
```

## General

### Can I use swarm in any project type?

Yes! Swarm auto-detects project types (Python, Node.js, React Native, Rust, Go, etc.) but works with any codebase. For unsupported project types, it falls back to generic defaults.

### How is this different from just using Claude Code?

Claude Code is a single agent with one context window. When working on large features, it eventually loses track of earlier work. Swarm coordinates multiple specialized agents, each with fresh context, communicating only through compressed summaries.

### Do I need an Anthropic API key?

No. Swarm uses the Claude Code CLI under the hood, which handles authentication through your Claude subscription.

## Troubleshooting

### "Claude CLI not found"

Install Claude Code: https://claude.ai/code

### "Agent timed out"

Agents have a 5-minute timeout. For complex tasks, break them down:

```bash
swarm plan "Big feature"  # Let architect break it down
```

### "Security blocked deployment"

```bash
swarm summaries  # Check what security found
```

Then fix the issues and re-run.

### "'AgentConfig' object has no attribute 'get'"

Upgrade to v0.2.1 or later:
```bash
pip3 install --upgrade git+https://github.com/igor-kats/claude-swarm.git@v0.2.1
```
