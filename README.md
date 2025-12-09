# 🐝 Claude Swarm

**Universal multi-agent orchestration for Claude Code**

Claude Swarm lets you develop large features without losing context by using specialized AI agents with isolated contexts, coordinated by a lightweight orchestrator.

## The Problem

When developing big features with Claude Code, you eventually hit context limits. The AI loses track of earlier decisions, forgets file contents, and starts making mistakes.

## The Solution

```
┌─────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                         │
│  (Lightweight context - only summaries & decisions)     │
└───────────────────────────┬─────────────────────────────┘
                            │
    ┌───────────┬───────────┼───────────┬───────────┐
    ▼           ▼           ▼           ▼           ▼
┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐
│ CODER  │  │REVIEWER│  │SECURITY│  │ TESTER │  │  DOCS  │
│        │  │        │  │        │  │        │  │        │
│ Fresh  │  │ Fresh  │  │ Fresh  │  │ Fresh  │  │ Fresh  │
│Context │  │Context │  │Context │  │Context │  │Context │
└────────┘  └────────┘  └────────┘  └────────┘  └────────┘
```

Each agent:
- Gets a **fresh context** for each task
- Has a **specialized system prompt** for its role
- Returns only a **compressed summary** to the orchestrator

## Installation

```bash
# Install latest version from GitHub
pip install git+https://github.com/igor-kats/claude-swarm.git

# Or install a specific version
pip install git+https://github.com/igor-kats/claude-swarm.git@v0.2.0
```

For development:
```bash
git clone https://github.com/igor-kats/claude-swarm.git
cd claude-swarm
pip install -e ".[dev]"
```

**Requirements:**
- Python 3.10+
- Claude Code CLI installed (`claude` command available)

## Quick Start

### 1. Initialize in your project

```bash
cd your-project
swarm init
```

This creates:
- `.swarm.yaml` - Configuration file
- `.swarm/` - Workspace directory (add to .gitignore)

### 2. Run a task

```bash
# Simple task with automatic pipeline (code → review → security → test)
swarm run "Add user authentication with JWT"

# Use a specific agent
swarm run "Fix the login timeout bug" --agent debugger

# Skip the automatic pipeline
swarm run "Add a helper function" --no-pipeline
```

### 3. Plan a big feature

```bash
# Get an architecture plan
swarm plan "Implement payment processing with Stripe"

# Plan and execute immediately
swarm plan "Add real-time notifications" --execute
```

## Available Agents

| Agent | Purpose | Tools |
|-------|---------|-------|
| `coder` | Write production code | Read, Write, Edit, Bash |
| `reviewer` | Code review for quality | Read only |
| `security` | Security vulnerability audit | Read, Grep, Bash |
| `tester` | Write comprehensive tests | Read, Write, Edit, Bash |
| `docs` | Create/update documentation | Read, Write, Edit |
| `architect` | Plan implementations | Read only |
| `debugger` | Diagnose and fix bugs | Read, Write, Edit, Bash |
| `mobile_ui` | React Native UI | Read, Write, Edit |
| `aws` | Cloud infrastructure | Read, Write, Edit, Bash |

```bash
swarm agents  # List all available agents
```

## Configuration

Edit `.swarm.yaml` to customize:

```yaml
# Auto-detected, but you can override
project_type: react-native

# Orchestrator settings
orchestrator:
  max_context_tokens: 8000
  auto_pipeline: true       # Auto-run review/security/test
  parallel_reviews: true    # Run security & review in parallel
  require_security_pass: true
  require_tests: true

# Enable/disable agents
agents:
  coder:
    enabled: true
    max_turns: 15
  security:
    enabled: true
  docs:
    enabled: false  # Disable documentation agent

# Project structure
source_dirs:
  - src
  - app
  - components
test_dirs:
  - __tests__
  - tests
```

## Project Type Auto-Detection

Swarm automatically detects your project type and configures appropriate defaults:

| Detected Files | Project Type | Default Source Dirs |
|---------------|--------------|---------------------|
| `app.json` (expo/react-native) | react-native | src, app, components, screens |
| `pyproject.toml`, `requirements.txt` | python | src, lib |
| `package.json` | nodejs | src, lib, routes |
| `tsconfig.json` | typescript | src, lib |
| `Cargo.toml` | rust | src |
| `go.mod` | go | cmd, pkg, internal |

## CLI Commands

```bash
swarm init              # Initialize in current project
swarm run <task>        # Run a task with agents
swarm plan <feature>    # Plan a feature implementation
swarm execute <id>      # Execute a planned session
swarm status            # Show current sessions
swarm agents            # List available agents
swarm summaries         # Show recent agent summaries
swarm config            # Show current configuration
```

## How It Works

### Context Management

The key innovation is **summary-only communication**:

1. **Orchestrator** maintains minimal context:
   - Feature description
   - Architecture decisions
   - Last 20 agent summaries (compressed)

2. **Agents** get fresh context each time:
   - Task description
   - Relevant file paths
   - Recent summaries (for continuity)

3. **Agents return** only structured summaries:
   ```json
   {
     "summary": "Added JWT auth middleware",
     "files_changed": ["src/auth/jwt.py"],
     "issues": [],
     "blocked": false
   }
   ```

### Pipeline Execution

For code changes, the default pipeline is:

```
CODER → [SECURITY + REVIEWER] → TESTER
              (parallel)
```

- Security can **block** deployment if critical issues found
- Review provides feedback for improvement
- Tests ensure correctness

## Custom Agents

Define project-specific agents in `.swarm.yaml`:

```yaml
custom_agents:
  finops:
    system_prompt: |
      You are an AWS FinOps specialist.
      Focus on cost optimization, tagging, and efficiency.
    allowed_tools:
      - Read
      - Bash
      - Grep
    max_turns: 10
```

## Programmatic Usage

```python
from claude_swarm import Orchestrator, AgentType

# Initialize
orchestrator = Orchestrator()

# Run single agent
result = orchestrator.invoke_agent(
    AgentType.CODER,
    "Implement user registration",
    context_files=["src/auth/"]
)

# Run full pipeline
results = orchestrator.run_pipeline(
    "Add password reset feature",
    context_files=["src/auth/", "src/email/"]
)

# Plan and execute feature
tasks = orchestrator.plan_feature("OAuth integration")
results = orchestrator.execute_plan()
```

## Best Practices

### 1. Be Specific in Tasks

```bash
# Good
swarm run "Add input validation to UserForm component with email format check"

# Less good
swarm run "Fix the form"
```

### 2. Provide Context Files

```bash
swarm run "Add pagination to users API" --context src/api/users.py --context src/models/user.py
```

### 3. Use Architect for Big Features

```bash
# Let architect break down the work
swarm plan "Implement complete checkout flow with cart, payment, and order confirmation"
```

### 4. Review Session Summaries

```bash
swarm summaries  # See what agents have done
swarm status     # Check session progress
```

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

**See [FAQ.md](FAQ.md) for more questions and troubleshooting.**

## License

MIT

## Contributing

PRs welcome! Please read CONTRIBUTING.md first.
