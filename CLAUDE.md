# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claude Swarm is a multi-agent orchestration system that coordinates specialized AI agents via the Claude Code CLI. It solves context window limitations by distributing work across agents that each get fresh contexts and communicate through compressed summaries.

## Working Style
- Work autonomously. Do not ask for confirmation on routine decisions.
- Use subagents to parallelize independent work.
- When facing ambiguity, make the best judgment call and document it.
- Only ask the user when something is truly blocking.

## Hard Rules — NEVER do without explicit user approval:
- Do NOT deploy anything (no terraform apply, no CDK deploy, no SAM deploy, no serverless deploy)
- Do NOT run tests against production or staging data/accounts
- Do NOT modify or delete any real AWS resources
- Do NOT push to main/master branch
- All infrastructure changes — dry-run/plan only (terraform plan, cdk diff, etc.)
- All tests must use mocks, fixtures, or local data only
- 
## Commands

```bash
# Install for development
pip install -e ".[dev]"

# Run tests
pytest tests/ -v
pytest tests/test_config.py -v          # single test file

# Lint and format
black src/ tests/                        # format (line-length: 100)
ruff check src/ tests/                   # lint
ruff check src/ tests/ --fix             # auto-fix lint issues

# Build
python -m build

# CLI entry point
swarm <command>                          # e.g. swarm run, swarm plan, swarm agents
```

CI runs Black formatting check and Ruff linting, then pytest on Python 3.10/3.11/3.12.

## Architecture

### Core flow

```
Orchestrator (keeps only summaries, minimal context)
    ↓ dispatches tasks to
Specialized Agents (each gets fresh context with task + file paths + recent summaries)
    ↓ return
AgentResult (compressed summary back to orchestrator)
```

### Key modules (`src/claude_swarm/`)

- **`cli.py`** — Click-based CLI. Entry point registered as `swarm` in pyproject.toml. Uses Rich for terminal output.
- **`orchestrator.py`** — Session management, task execution, pipeline orchestration. `run_pipeline()` runs the default pipeline: Coder → Security+Review (parallel) → Tester. State persisted as JSON in `.swarm/state/`.
- **`config.py`** — Pydantic-based configuration. Auto-detects project type from signature files (pyproject.toml → Python, package.json → Node.js, etc.). Loads overrides from `.swarm.yaml`.
- **`agents/base.py`** — `BaseAgent` abstract class and `AgentResult` dataclass. Template method pattern: subclasses override `_get_output_format()`. Supports background (subprocess capture) and interactive (new terminal) execution modes.
- **`agents/specialized.py`** — All concrete agent implementations (CoderAgent, ReviewerAgent, SecurityAgent, TesterAgent, DocsAgent, ArchitectAgent, DebuggerAgent, MobileUIAgent, AWSAgent). Each defines role-specific system prompts and output formats.
- **`agents/registry.py`** — `AgentRegistry` factory. Maps `AgentType` enum to agent classes. Supports custom agent registration.

### Configuration

Project config lives in `.swarm.yaml`. The `SwarmConfig` Pydantic model validates it. Per-agent settings (enabled, max_turns, temperature, system_prompt_override, allowed_tools) are in `AgentConfig`.

### Workspace

`.swarm/` directory stores runtime state, summaries, and task files. It's auto-created and should be gitignored.

## Code Style

- Python 3.10+, type hints throughout
- Black with line-length 100, target Python 3.10
- Ruff rules: E, F, I, N, W (E501 ignored — handled by Black)
- Dataclasses for simple data structures, Pydantic models for validated configuration
- Agents invoke the `claude` CLI as a subprocess with timeouts (600s default)
