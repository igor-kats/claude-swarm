# Contributing to Claude Swarm

Thank you for your interest in contributing to Claude Swarm! This document provides guidelines and instructions for contributing.

## Getting Started

### Prerequisites

- Python 3.10 or higher
- [Claude Code CLI](https://claude.com/claude-code) installed and authenticated
- Git

### Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/claude-swarm.git
   cd claude-swarm
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Verify installation**
   ```bash
   swarm --help
   pytest tests/
   ```

## Development Workflow

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_config.py -v

# Run with coverage
pytest tests/ --cov=src/claude_swarm --cov-report=html
```

### Code Quality

We use the following tools to maintain code quality:

```bash
# Format code with Black
black src/ tests/

# Lint with Ruff
ruff check src/ tests/

# Fix auto-fixable issues
ruff check src/ tests/ --fix
```

### Type Checking (Optional)

```bash
pip install mypy
mypy src/claude_swarm
```

## Making Changes

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring

### Commit Messages

Follow conventional commit format:

```
type(scope): description

[optional body]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
- `feat(agents): add new debugger agent`
- `fix(config): handle empty YAML files`
- `docs(readme): add installation instructions`

### Pull Request Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make your changes**
   - Write tests for new functionality
   - Update documentation if needed
   - Ensure all tests pass
   - Format and lint your code

3. **Push and create PR**
   ```bash
   git push origin feature/my-feature
   ```
   Then open a Pull Request on GitHub.

4. **PR Description**
   - Describe what changes you made
   - Explain why the changes are needed
   - Reference any related issues

## Project Structure

```
claude-swarm/
├── src/claude_swarm/
│   ├── __init__.py
│   ├── cli.py              # CLI commands
│   ├── config.py           # Configuration handling
│   ├── orchestrator.py     # Main orchestration logic
│   └── agents/
│       ├── __init__.py
│       ├── base.py         # Base agent class
│       ├── registry.py     # Agent registry
│       └── specialized.py  # Specialized agent implementations
├── tests/
│   ├── test_config.py
│   └── test_agents.py
├── examples/               # Example configurations
└── .github/workflows/      # CI/CD
```

## Adding a New Agent

1. **Define the agent in `agents/specialized.py`**:
   ```python
   class MyNewAgent(BaseAgent):
       agent_type = AgentType.MY_NEW_AGENT
       allowed_tools = ["Read", "Write", "Edit"]
       max_turns = 10

       system_prompt = """Your agent's system prompt..."""

       def _get_output_format(self) -> str:
           return """Output format instructions..."""
   ```

2. **Add to `AgentType` enum in `agents/base.py`**:
   ```python
   class AgentType(str, Enum):
       # ... existing types
       MY_NEW_AGENT = "my_new_agent"
   ```

3. **Register in `agents/registry.py`**:
   ```python
   _agents: dict[AgentType, Type[BaseAgent]] = {
       # ... existing agents
       AgentType.MY_NEW_AGENT: MyNewAgent,
   }
   ```

4. **Add tests in `tests/test_agents.py`**

## Code Style Guidelines

- Use type hints for function parameters and return values
- Write docstrings for public classes and functions
- Keep functions focused and single-purpose
- Prefer composition over inheritance
- Use meaningful variable and function names

## Reporting Issues

When reporting bugs, please include:

- Python version (`python --version`)
- Claude Swarm version (`swarm --version`)
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages/stack traces

## Feature Requests

Feature requests are welcome! Please:

- Search existing issues first
- Describe the use case
- Explain why it would be valuable
- Consider implementation approaches

## Questions?

- Open a [GitHub Discussion](https://github.com/igor-kats/claude-swarm/discussions)
- Check existing issues and discussions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
