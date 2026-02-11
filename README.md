# 🐝 Claude Swarm (Archived)

> **This project is archived and no longer maintained.**

Claude Swarm was an experimental multi-agent orchestration system for Claude Code. It coordinated specialized AI agents (coder, reviewer, security auditor, tester, etc.) with isolated contexts, communicating through compressed summaries to work around context window limitations.

## Why Archived

Claude Code now has native support for the capabilities this project was built to provide:

- **Subagents** — Claude Code's built-in `Task` tool spawns specialized agents (Explore, Plan, Bash, general-purpose) with isolated contexts
- **Parallel execution** — Multiple subagents can run concurrently in a single message
- **Planning** — Native plan mode with architect-style exploration and user approval
- **Task tracking** — Built-in task creation, dependencies, and status tracking
- **Context management** — Automatic context compression and persistent memory across sessions

The core ideas in Swarm (pipeline workflows, security gates, project-type detection) were interesting but are better served by Claude Code's native capabilities or lightweight hooks/CLAUDE.md instructions rather than a separate subprocess-based orchestration layer.

## What Was Here

- A CLI (`swarm`) that coordinated 9 specialized agent types via the Claude Code CLI
- An automated pipeline: Coder → Security + Review (parallel) → Tester
- YAML-based configuration with project-type auto-detection
- Session persistence and resumable workflows

## License

MIT
