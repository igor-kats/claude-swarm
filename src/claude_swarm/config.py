"""
Configuration management for Claude Swarm.
Handles project detection, config loading, and defaults.
"""

from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class ProjectType(str, Enum):
    """Detected project types with specific agent configurations."""

    PYTHON = "python"
    REACT_NATIVE = "react-native"
    NODEJS = "nodejs"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    GENERIC = "generic"


class AgentConfig(BaseModel):
    """Configuration for a single agent."""

    enabled: bool = True
    system_prompt_override: Optional[str] = None
    allowed_tools: list[str] = Field(default_factory=list)
    max_turns: int = 30
    temperature: float = 0.7
    custom_instructions: Optional[str] = None


class OrchestratorConfig(BaseModel):
    """Configuration for the main orchestrator."""

    max_context_tokens: int = 8000
    summary_max_tokens: int = 500
    auto_pipeline: bool = True  # Automatically run review/security/test after code
    parallel_reviews: bool = True  # Run security & code review in parallel
    require_security_pass: bool = True  # Block on security issues
    require_tests: bool = True  # Require tests for new code


class SwarmConfig(BaseModel):
    """Main configuration for the swarm."""

    project_type: ProjectType = ProjectType.GENERIC
    project_root: Path = Field(default_factory=Path.cwd)
    workspace_dir: str = ".swarm"

    # Agent configurations
    orchestrator: OrchestratorConfig = Field(default_factory=OrchestratorConfig)
    agents: dict[str, AgentConfig] = Field(default_factory=dict)

    # Project-specific settings
    source_dirs: list[str] = Field(default_factory=lambda: ["src", "lib", "app"])
    test_dirs: list[str] = Field(default_factory=lambda: ["tests", "test", "__tests__"])
    ignore_patterns: list[str] = Field(
        default_factory=lambda: [
            "node_modules",
            ".git",
            "__pycache__",
            ".swarm",
            "venv",
            ".venv",
            "build",
            "dist",
            ".next",
            "*.pyc",
            "*.log",
        ]
    )

    # Custom agent definitions (for project-specific agents)
    custom_agents: dict[str, dict] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True


# Project type detection signatures
PROJECT_SIGNATURES = {
    ProjectType.REACT_NATIVE: [
        ("app.json", lambda c: "expo" in c.lower() or "react-native" in c.lower()),
        ("package.json", lambda c: "react-native" in c.lower()),
    ],
    ProjectType.PYTHON: [
        ("pyproject.toml", None),
        ("setup.py", None),
        ("requirements.txt", None),
        ("Pipfile", None),
    ],
    ProjectType.NODEJS: [
        ("package.json", lambda c: "react-native" not in c.lower()),
    ],
    ProjectType.TYPESCRIPT: [
        ("tsconfig.json", None),
    ],
    ProjectType.RUST: [
        ("Cargo.toml", None),
    ],
    ProjectType.GO: [
        ("go.mod", None),
    ],
    ProjectType.JAVA: [
        ("pom.xml", None),
        ("build.gradle", None),
    ],
}

# Default source directories per project type
PROJECT_SOURCE_DIRS = {
    ProjectType.REACT_NATIVE: ["src", "app", "components", "screens", "hooks", "utils", "services"],
    ProjectType.PYTHON: ["src", "lib", "app"],
    ProjectType.NODEJS: ["src", "lib", "app", "routes", "controllers", "services"],
    ProjectType.TYPESCRIPT: ["src", "lib", "app"],
    ProjectType.RUST: ["src"],
    ProjectType.GO: ["cmd", "pkg", "internal"],
    ProjectType.JAVA: ["src/main/java", "src"],
    ProjectType.GENERIC: ["src", "lib", "app"],
}

# Default test directories per project type
PROJECT_TEST_DIRS = {
    ProjectType.REACT_NATIVE: ["__tests__", "tests", "e2e"],
    ProjectType.PYTHON: ["tests", "test"],
    ProjectType.NODEJS: ["__tests__", "tests", "test"],
    ProjectType.TYPESCRIPT: ["__tests__", "tests", "test"],
    ProjectType.RUST: ["tests"],
    ProjectType.GO: ["*_test.go"],  # Go uses file naming convention
    ProjectType.JAVA: ["src/test/java", "test"],
    ProjectType.GENERIC: ["tests", "test", "__tests__"],
}


def detect_project_type(project_root: Path) -> ProjectType:
    """
    Auto-detect project type based on configuration files.

    Checks for signature files and their contents to determine
    the most likely project type.
    """
    for project_type, signatures in PROJECT_SIGNATURES.items():
        for filename, content_check in signatures:
            filepath = project_root / filename
            if filepath.exists():
                if content_check is None:
                    return project_type
                try:
                    content = filepath.read_text()
                    if content_check(content):
                        return project_type
                except Exception:
                    continue

    return ProjectType.GENERIC


def load_config(project_root: Optional[Path] = None) -> SwarmConfig:
    """
    Load configuration from .swarm.yaml or create defaults.

    Priority:
    1. .swarm.yaml in project root
    2. Auto-detected settings based on project type
    3. Generic defaults
    """
    if project_root is None:
        project_root = Path.cwd()

    config_path = project_root / ".swarm.yaml"

    # Start with defaults
    project_type = detect_project_type(project_root)

    config = SwarmConfig(
        project_type=project_type,
        project_root=project_root,
        source_dirs=PROJECT_SOURCE_DIRS.get(project_type, PROJECT_SOURCE_DIRS[ProjectType.GENERIC]),
        test_dirs=PROJECT_TEST_DIRS.get(project_type, PROJECT_TEST_DIRS[ProjectType.GENERIC]),
    )

    # Override with config file if exists
    if config_path.exists():
        try:
            with open(config_path) as f:
                yaml_config = yaml.safe_load(f)

            if yaml_config:
                # Merge with defaults
                config = SwarmConfig(
                    project_type=ProjectType(yaml_config.get("project_type", project_type)),
                    project_root=project_root,
                    workspace_dir=yaml_config.get("workspace_dir", ".swarm"),
                    orchestrator=OrchestratorConfig(**yaml_config.get("orchestrator", {})),
                    agents={k: AgentConfig(**v) for k, v in yaml_config.get("agents", {}).items()},
                    source_dirs=yaml_config.get("source_dirs", config.source_dirs),
                    test_dirs=yaml_config.get("test_dirs", config.test_dirs),
                    ignore_patterns=yaml_config.get("ignore_patterns", config.ignore_patterns),
                    custom_agents=yaml_config.get("custom_agents", {}),
                )
        except Exception as e:
            # Log warning but continue with defaults
            print(f"Warning: Could not load .swarm.yaml: {e}")

    return config


def init_config(project_root: Optional[Path] = None, force: bool = False) -> Path:
    """
    Initialize a new .swarm.yaml configuration file.

    Auto-detects project type and creates appropriate defaults.
    """
    if project_root is None:
        project_root = Path.cwd()

    config_path = project_root / ".swarm.yaml"

    if config_path.exists() and not force:
        raise FileExistsError(f"Configuration already exists at {config_path}")

    project_type = detect_project_type(project_root)

    config_content = f"""# Claude Swarm Configuration
# Auto-detected project type: {project_type.value}

project_type: {project_type.value}
workspace_dir: .swarm

# Orchestrator settings
orchestrator:
  max_context_tokens: 8000
  summary_max_tokens: 500
  auto_pipeline: true      # Auto-run review/security/test after code changes
  parallel_reviews: true   # Run security & code review in parallel
  require_security_pass: true
  require_tests: true

# Agent configurations (override defaults)
agents:
  coder:
    enabled: true
    max_turns: 30
  reviewer:
    enabled: true
    max_turns: 20
  security:
    enabled: true
    max_turns: 20
  tester:
    enabled: true
    max_turns: 30
  docs:
    enabled: false  # Enable if you want auto-documentation

# Project structure
source_dirs: {PROJECT_SOURCE_DIRS.get(project_type, PROJECT_SOURCE_DIRS[ProjectType.GENERIC])}
test_dirs: {PROJECT_TEST_DIRS.get(project_type, PROJECT_TEST_DIRS[ProjectType.GENERIC])}

# Patterns to ignore
ignore_patterns:
  - node_modules
  - .git
  - __pycache__
  - .swarm
  - venv
  - .venv
  - build
  - dist
  - "*.pyc"
  - "*.log"

# Custom agents (define your own specialized agents)
# custom_agents:
#   aws_specialist:
#     system_prompt: "You are an AWS infrastructure specialist..."
#     allowed_tools: ["Read", "Bash"]
#   mobile_ui:
#     system_prompt: "You are a React Native UI specialist..."
#     allowed_tools: ["Read", "Write", "Edit"]
"""

    config_path.write_text(config_content)

    # Create workspace directory
    workspace = project_root / ".swarm"
    workspace.mkdir(exist_ok=True)
    (workspace / "summaries").mkdir(exist_ok=True)
    (workspace / "tasks").mkdir(exist_ok=True)
    (workspace / "state").mkdir(exist_ok=True)

    # Add to .gitignore if exists
    gitignore = project_root / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text()
        if ".swarm/" not in content:
            with open(gitignore, "a") as f:
                f.write("\n# Claude Swarm\n.swarm/\n")

    return config_path
