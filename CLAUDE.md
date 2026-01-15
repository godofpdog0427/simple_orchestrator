# CLAUDE.md

This file provides comprehensive guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Last Updated**: 2026-01-16
**Current Phase**: Phase 2.5 (TodoList Tool - In Progress)

---

## ⚠️ CRITICAL: Git Branch Strategy

**READ THIS FIRST - MANDATORY RULES**

This project uses a strict branch strategy to prevent catastrophic data loss:

### Branch Structure

- **`main`** - Production-ready code. **PROTECTED BRANCH**
- **`dev`** - Development integration branch. **Default working branch**
- **`feature/*`** - Feature branches (created from `dev`)
- **`fix/*`** - Bug fix branches (created from `dev`)

### Branching Rules for Claude Code

**YOU MUST FOLLOW THESE RULES:**

1. **NEVER merge to `main`** - Only the human user can merge to `main`
2. **ALWAYS create feature branches from `dev`** - Never from `main`
3. **ALWAYS merge your changes to `dev`** - Never to `main`
4. **NEVER force push** - Especially not to `main` or `dev`
5. **ALWAYS work on feature branches** - Format: `feature/description` or `fix/description`

### Workflow for Claude Code

```bash
# 1. Start from dev branch
git checkout dev
git pull origin dev  # Get latest changes

# 2. Create feature branch
git checkout -b feature/your-feature-name

# 3. Make changes and commit
git add .
git commit -m "feat: your changes"

# 4. Push feature branch
git push -u origin feature/your-feature-name

# 5. Merge to dev (NEVER to main)
git checkout dev
git merge feature/your-feature-name
git push origin dev

# 6. Delete feature branch (optional)
git branch -d feature/your-feature-name
```

### What You CAN Do

✅ Create feature branches from `dev`
✅ Commit to feature branches
✅ Merge feature branches to `dev`
✅ Push to `dev` branch
✅ Create pull requests (for review)

### What You CANNOT Do

❌ **Merge to `main`** (NEVER)
❌ **Force push to any branch**
❌ **Delete `main` or `dev` branches**
❌ **Create branches from `main`** (use `dev` instead)
❌ **Push directly to `main`**

### Emergency Recovery

If you accidentally work on the wrong branch:

```bash
# Save your work
git stash

# Switch to correct branch
git checkout dev
git checkout -b feature/your-feature

# Restore your work
git stash pop
```

### Why This Matters

This project was previously lost due to an accidental `/clear` command. The branch strategy ensures:
- `main` always has stable, working code
- All development happens in isolated feature branches
- Only the human user controls what goes to production (`main`)
- Claude Code cannot accidentally destroy the codebase

---

## Project Overview

**Simple Orchestrator** is a lightweight CLI Agent Orchestrator designed for personal use with AI coding assistants. It provides a hook-based, extensible framework for managing complex multi-step tasks with LLM agents.

### Core Capabilities

- **Hook-based Lifecycle Management**: Intercept and customize behavior at key execution points
- **Hierarchical Task Management**: Break down complex tasks into subtasks with dependency tracking
- **Extensible Tool System**: Register custom tools via classes, decorators, or YAML configs
- **Subagent Spawning**: Delegate subtasks to specialized agents with resource constraints
- **Skill-based Instructions**: Prompt-based skills (SKILL.md files) guide LLM behavior
- **Human-in-the-Loop (HITL)**: Approve critical operations before execution

## Quick Start

### Setup

```bash
# Install dependencies
pip install -e ".[dev]"

# Create .env file
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Running

```bash
# Start orchestrator in interactive mode
orchestrator chat

# Run with specific config
orchestrator start --config config/custom.yaml

# Add a task
orchestrator task add "Analyze code and suggest improvements"
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=orchestrator --cov-report=html

# Run integration tests only
pytest tests/integration/
```

---

## Theoretical Foundation

### Architecture Philosophy

This orchestrator is built on proven AI agent design patterns:

#### 1. BDI (Belief-Desire-Intention) Model

- **Beliefs**: Task state, tool registry, conversation history, skill library
- **Desires**: User-defined tasks and goals
- **Intentions**: Active task execution, tool selection, subagent delegation

#### 2. ReAct (Reasoning and Acting) Pattern

The LLM alternates between:
- **Reasoning**: Analyzing the current state, planning next steps
- **Acting**: Using tools, spawning subagents, updating task state

#### 3. Design Principles

- **Async-First**: All I/O operations use `async/await` for non-blocking execution
- **Hook-Driven**: Every key action triggers lifecycle hooks for extensibility
- **Declarative Tools**: Tools describe capabilities; LLM decides usage
- **Prompt-Based Skills**: Skills are instructions (SKILL.md), not code workflows
- **Subagent Isolation**: Child agents have limited context and resource budgets
- **Human Oversight**: Critical operations require explicit approval (HITL)

---

## Architecture Deep Dive

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                           │
│  (click commands, interactive prompt, config loading)       │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Orchestrator Core                         │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Hook Engine │  │ Task Manager │  │ LLM Client   │      │
│  │ (lifecycle) │  │ (queue/deps) │  │ (Anthropic)  │      │
│  └─────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │Tool Registry│  │Skill Registry│  │Subagent Mgr  │      │
│  │(bash, file) │  │(SKILL.md)    │  │(spawning)    │      │
│  └─────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 1. LLM Integration (Anthropic)

**CRITICAL**: This orchestrator uses Anthropic's **native tool calling API**. Do NOT use text-based tool parsing.

#### Correct Tool Calling Flow

1. **Tool Registration**: Tools converted to Anthropic schema
   ```python
   {
       "name": "bash",
       "description": "Execute bash commands",
       "input_schema": {
           "type": "object",
           "properties": {
               "command": {"type": "string", "description": "..."}
           },
           "required": ["command"]
       }
   }
   ```

2. **API Call**: Tools passed via `tools` parameter
   ```python
   response = await client.messages.create(
       model="claude-3-5-sonnet-20241022",
       messages=conversation_history,
       tools=tool_schemas  # List of tool definitions
   )
   ```

3. **Response Handling**: Parse `stop_reason`
   - `stop_reason == "end_turn"`: Extract text content
   - `stop_reason == "tool_use"`: Process `tool_use` blocks

4. **Tool Execution**: Execute tools and return results
   ```python
   tool_results = []
   for block in response.content:
       if block.type == "tool_use":
           result = await execute_tool(block.name, block.input)
           tool_results.append({
               "type": "tool_result",
               "tool_use_id": block.id,  # CRITICAL: Match ID
               "content": str(result)
           })

   # Add as user message
   conversation_history.append({
       "role": "user",
       "content": tool_results
   })
   ```

#### Key Files

- `src/orchestrator/llm/client.py` - LLM abstraction layer
- `src/orchestrator/llm/providers/anthropic.py` - Anthropic provider (future)
- `src/orchestrator/core/orchestrator.py:_reasoning_loop()` - Main ReAct loop

#### Provider Abstraction (Future)

Currently only Anthropic is supported. Future providers:
- OpenAI (GPT-4)
- Google (Gemini)
- Local models (Ollama)

Each provider will implement `LLMProvider` ABC with standardized `chat()` interface.

### 2. Hook System

**Status**: Base classes implemented (Phase 1), engine not active yet (Phase 2).

#### Hook Lifecycle Events

| Event | When Triggered | Context Provided |
|-------|---------------|------------------|
| `orchestrator.start` | Orchestrator initialization | config |
| `orchestrator.stop` | Orchestrator shutdown | final_state |
| `task.created` | Task added to queue | task |
| `task.started` | Task execution begins | task, agent_context |
| `task.completed` | Task succeeds | task, result |
| `task.failed` | Task fails | task, error |
| `tool.before_execute` | Before tool runs | tool_name, input |
| `tool.after_execute` | After tool runs | tool_name, result |
| `tool.requires_approval` | Tool needs HITL | tool_name, input |
| `subagent.spawned` | Subagent created | parent_task, child_task |
| `subagent.completed` | Subagent finishes | parent_task, result |
| `llm.before_call` | Before LLM API call | messages, tools |
| `llm.after_call` | After LLM response | response, token_count |

#### Hook Priority

Hooks execute in priority order (lower number = higher priority):

```yaml
hooks:
  - name: logging_hook
    priority: 10
    events: ["*"]  # All events

  - name: hitl_approval
    priority: 50
    events: ["tool.requires_approval"]

  - name: metrics_collector
    priority: 100
    events: ["task.completed", "task.failed"]
```

#### Hook Results

Hooks can:
- **Continue**: `HookResult(action="continue")`
- **Block**: `HookResult(action="block", reason="...")`
- **Modify**: `HookResult(action="continue", modified_context={...})`

#### Built-in Hooks (Phase 2)

1. **LoggingHook**: Logs all events to file
2. **HITLHook**: Prompts user for approval on critical operations
3. **MetricsHook**: Collects execution statistics
4. **CachingHook**: Caches tool results for deduplication

#### Custom Hook Example

```python
from orchestrator.hooks.base import Hook, HookContext, HookResult

class CustomValidationHook(Hook):
    name = "custom_validation"
    priority = 20
    events = ["task.started"]

    async def execute(self, context: HookContext) -> HookResult:
        task = context.data["task"]
        if not task.description:
            return HookResult(
                action="block",
                reason="Task must have description"
            )
        return HookResult(action="continue")
```

### 3. Task System

#### Task Model

```python
@dataclass
class Task:
    id: str
    title: str
    description: str
    status: TaskStatus  # PENDING, IN_PROGRESS, COMPLETED, FAILED
    priority: TaskPriority  # LOW, NORMAL, HIGH, CRITICAL

    # Hierarchy (Phase 3)
    parent_id: Optional[str] = None
    subtasks: list[str] = field(default_factory=list)

    # Dependencies (Phase 3)
    depends_on: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)

    # Execution
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

#### Task Lifecycle

```
PENDING → IN_PROGRESS → COMPLETED
                     ↘ FAILED

If retry enabled: FAILED → PENDING (up to max_retries)
```

#### Phase 1: Simple Queue

- Tasks execute sequentially
- No hierarchy or dependencies
- `get_next_executable_task()` returns first PENDING task

#### Phase 3: Hierarchical Tasks

- Parent tasks spawn subtasks
- Subtasks execute before parent completes
- `get_next_executable_task()` respects:
  - Dependencies: All tasks in `depends_on` must be COMPLETED
  - Hierarchy: Subtasks execute before parent

#### Task Manager API

```python
class TaskManager:
    async def create_task(self, title: str, description: str, **kwargs) -> Task
    async def get_task(self, task_id: str) -> Optional[Task]
    async def update_task(self, task_id: str, **updates) -> Task
    async def list_tasks(self, status: Optional[TaskStatus] = None) -> list[Task]
    async def get_next_executable_task(self) -> Optional[Task]

    # Hierarchy (Phase 3)
    async def create_subtask(self, parent_id: str, **kwargs) -> Task
    async def add_dependency(self, task_id: str, depends_on_id: str)
```

### 4. Tool System

#### Tool Registration Methods

##### 1. Class-Based (Complex Tools)

```python
from orchestrator.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult

class DatabaseQueryTool(Tool):
    definition = ToolDefinition(
        name="database_query",
        description="Execute SQL query on database",
        parameters=[
            ToolParameter(
                name="query",
                type="string",
                description="SQL query to execute",
                required=True
            ),
            ToolParameter(
                name="db_name",
                type="string",
                description="Database name",
                required=False,
                default="default"
            )
        ],
        requires_approval=True  # HITL for destructive queries
    )

    def __init__(self, connection_pool):
        self.pool = connection_pool

    async def execute(self, query: str, db_name: str = "default") -> ToolResult:
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetch(query)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

##### 2. Decorator-Based (Simple Functions)

```python
from orchestrator.tools.base import tool

@tool(name="word_count", requires_approval=False)
async def word_count(text: str) -> int:
    """Count words in the given text."""
    return len(text.split())

@tool(name="sentiment_analysis")
async def analyze_sentiment(text: str) -> dict:
    """Analyze sentiment of text."""
    # Tool implementation
    return {"sentiment": "positive", "score": 0.85}
```

##### 3. YAML-Based (User Extensions)

```yaml
# user_extensions/tools/custom.yaml
tools:
  - name: fetch_weather
    description: Fetch current weather for a location
    type: http_request
    parameters:
      - name: location
        type: string
        required: true
    config:
      method: GET
      url: "https://api.weather.com/v1/current?location={location}"
      headers:
        API-Key: "${WEATHER_API_KEY}"
    requires_approval: false
```

#### Built-in Tools

1. **BashTool**: Execute shell commands
   - Safety: Blocked command patterns (rm -rf /, fork bombs)
   - Timeout: Configurable (default 30s)
   - Working directory tracking

2. **FileReadTool**: Read file contents
   - Size limit: Configurable (default 10MB)
   - Encoding: UTF-8 with fallback

3. **FileWriteTool**: Write/create files
   - Auto-create parent directories
   - Atomic writes (temp file + rename)

4. **FileDeleteTool**: Delete files/directories
   - Requires approval for directories
   - Safety checks (no system paths)

#### Tool Registry

```python
class ToolRegistry:
    def register(self, tool: Tool)
    def get(self, name: str) -> Optional[Tool]
    def list_tools(self) -> list[ToolDefinition]
    def to_anthropic_schema(self) -> list[dict]  # Convert to API format
```

#### Anthropic Schema Conversion

```python
def _convert_to_anthropic_schema(self, tool_def: ToolDefinition) -> dict:
    properties = {}
    required = []

    for param in tool_def.parameters:
        properties[param.name] = {
            "type": param.type,
            "description": param.description
        }
        if param.required:
            required.append(param.name)

    return {
        "name": tool_def.name,
        "description": tool_def.description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required
        }
    }
```

### 5. Skill System

#### Design Philosophy

**Skills are prompts, not code.** A SKILL.md file contains:
- **Instructions**: How to approach a task
- **Best practices**: Domain-specific guidelines
- **Examples**: Template usage patterns
- **Safety checks**: Common pitfalls to avoid

The LLM reads the skill and uses available tools to achieve the goal.

#### SKILL.md Format

```markdown
---
name: code_review
description: "Review code for bugs, style, and security issues"
tools_required: [file_read]
version: "1.0.0"
tags: [code, quality, security]
---

# Code Review

## Overview
Systematic code review focusing on correctness, security, style, and maintainability.

## When to Use
- Pull request review
- Security audit
- Code quality assessment

## Review Checklist

### 1. Correctness
- [ ] Logic errors or edge cases
- [ ] Null/undefined handling
- [ ] Type mismatches

### 2. Security
- [ ] SQL injection vulnerabilities
- [ ] XSS vulnerabilities
- [ ] Authentication checks

## Process
1. Read all changed files
2. Check each item in checklist
3. Document findings with severity levels
4. Suggest specific fixes

## Example Output
**File**: `auth.py:42`
**Severity**: High
**Issue**: Missing authentication check
**Fix**: Add `@require_auth` decorator
```

#### Built-in Skills

1. **code_edit**: Safe code modification patterns
2. **code_review**: Code quality assessment
3. **research**: Web research methodology
4. **git_operations**: Git workflow best practices
5. **file_management**: File organization patterns

#### Skill Auto-Discovery (Phase 4)

```python
class SkillRegistry:
    def __init__(self):
        self._skills = {}
        self._load_builtin_skills()
        self._load_user_skills()

    def _load_user_skills(self):
        """Auto-discover skills from user_extensions/skills/*/SKILL.md"""
        for skill_dir in Path("user_extensions/skills").glob("*/"):
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                skill = self._parse_skill(skill_file)
                self.register(skill)
```

#### Using Skills in Tasks

```python
# User creates task with skill hint
orchestrator task add "Review auth.py for security issues" --skill code_review

# Orchestrator injects skill instructions into system prompt
system_prompt = f"""
You are an AI assistant with access to tools.

Active Skill: Code Review
{skill_content}

Task: Review auth.py for security issues
"""
```

### 6. Subagent System (Phase 4)

#### Purpose

Delegate complex subtasks to isolated child agents with:
- Limited context (only parent task info)
- Resource constraints (token budget, time limit)
- Restricted tool access

#### Spawning Subagents

```python
class SubagentManager:
    async def spawn(
        self,
        parent_task: Task,
        subtask: Task,
        context: dict,
        constraints: dict
    ) -> SubagentHandle:
        """
        Spawn isolated subagent for subtask execution.

        Constraints:
            max_tokens: 50000 (default)
            timeout_seconds: 300 (default)
            allowed_tools: ["bash", "file_read"] (default: all)
            skill: Optional skill to load
        """
        subagent = Orchestrator(
            llm_client=self.llm_client,
            config={
                "max_tokens": constraints.get("max_tokens", 50000),
                "allowed_tools": constraints.get("allowed_tools")
            }
        )

        # Execute subtask in isolation
        result = await asyncio.wait_for(
            subagent.execute_task(subtask, context),
            timeout=constraints.get("timeout_seconds", 300)
        )

        return SubagentHandle(task_id=subtask.id, result=result)
```

#### Communication Rules

- **Parent → Child**: Only through task context (no direct calls)
- **Child → Parent**: Only through task result
- **Child ↔ Child**: No communication (isolated)

#### Resource Limits

```yaml
subagents:
  max_concurrent: 3  # Maximum parallel subagents
  default_constraints:
    max_tokens: 50000
    timeout_seconds: 300
    allowed_tools: ["bash", "file_read", "file_write"]
```

### 7. Human-in-the-Loop (HITL) (Phase 2)

#### Approval Workflow

1. Tool requires approval (`requires_approval=True`)
2. Hook `tool.requires_approval` triggered
3. HITL hook prompts user:
   ```
   Tool 'bash' requires approval:
   Command: rm -rf old_logs/

   Approve? [y/N]:
   ```
4. User response:
   - `y`: Execution continues
   - `n`: Execution blocked, alternative sought

#### Approval Levels

```yaml
hitl:
  approval_required:
    - tool_name: bash
      conditions:
        - pattern: "rm -rf.*"
        - pattern: "sudo.*"

    - tool_name: file_delete
      conditions:
        - target_is_directory: true

    - tool_name: database_query
      conditions:
        - query_type: ["DELETE", "DROP", "TRUNCATE"]
```

#### Auto-Approval (Advanced)

```python
class SmartHITLHook(Hook):
    async def execute(self, context: HookContext) -> HookResult:
        tool_name = context.data["tool_name"]
        tool_input = context.data["input"]

        # Check whitelist
        if self._is_whitelisted(tool_name, tool_input):
            return HookResult(action="continue")

        # Prompt user
        approved = await self._prompt_user(tool_name, tool_input)

        if approved:
            # Add to whitelist for future
            self._add_to_whitelist(tool_name, tool_input)
            return HookResult(action="continue")
        else:
            return HookResult(action="block", reason="User denied approval")
```

### 8. Configuration System

#### Configuration Files

```
config/
├── default.yaml       # Default configuration
├── hooks.yaml         # Hook definitions
├── schema.json        # JSON schema for validation
└── local.yaml         # Local overrides (gitignored)
```

#### Complete Configuration Schema

```yaml
# config/default.yaml

# LLM Provider Settings
llm:
  provider: anthropic  # anthropic, openai, google, local

  anthropic:
    model: claude-3-5-sonnet-20241022
    api_key_env: ANTHROPIC_API_KEY  # Read from env var
    max_tokens: 8192
    temperature: 0.7

  openai:  # Future
    model: gpt-4-turbo
    api_key_env: OPENAI_API_KEY

# Tool Configuration
tools:
  # Built-in tools
  bash:
    enabled: true
    timeout: 30
    blocked_commands:
      - "rm -rf /"
      - ":(){ :|:& };:"  # Fork bomb
      - "> /dev/sda"

  file_read:
    enabled: true
    max_file_size: 10485760  # 10 MB

  file_write:
    enabled: true
    create_dirs: true

  file_delete:
    enabled: true
    requires_approval: true

# Task Management
tasks:
  max_retries: 3
  retry_delay: 5  # seconds
  persistence_file: .orchestrator/tasks.json

# Subagent Settings (Phase 4)
subagents:
  enabled: false
  max_concurrent: 3
  default_constraints:
    max_tokens: 50000
    timeout_seconds: 300
    allowed_tools: ["bash", "file_read", "file_write"]

# Hook Settings (Phase 2)
hooks:
  enabled: false
  config_file: config/hooks.yaml

# HITL Settings (Phase 2)
hitl:
  enabled: false
  auto_approve_safe_tools: true
  approval_timeout: 300  # seconds

# Skill Settings
skills:
  builtin_path: src/orchestrator/skills/builtin
  user_path: user_extensions/skills
  auto_discover: true

# Memory Settings (Phase 5)
memory:
  enabled: false
  cross_session: false
  embeddings_provider: local  # local, openai
  vector_store: chroma

# Caching Settings (Phase 5)
cache:
  enabled: false
  tool_results: true
  llm_responses: false
  ttl: 3600  # seconds

# Logging
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR
  file: .orchestrator/orchestrator.log
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Persistence
persistence:
  state_file: .orchestrator/state.json
  auto_save: true
  save_interval: 60  # seconds
```

#### Hook Configuration

```yaml
# config/hooks.yaml

hooks:
  - name: logging_hook
    type: builtin  # builtin, custom, external
    priority: 10
    enabled: true
    events: ["*"]
    config:
      log_file: .orchestrator/hooks.log

  - name: hitl_approval
    type: builtin
    priority: 50
    enabled: true
    events: ["tool.requires_approval"]
    config:
      timeout: 300
      auto_approve_patterns:
        - tool: bash
          command_regex: "^ls.*"
        - tool: bash
          command_regex: "^cat (?!.*\\.env).*"  # cat anything except .env

  - name: metrics_collector
    type: builtin
    priority: 100
    enabled: true
    events:
      - task.completed
      - task.failed
      - tool.after_execute
    config:
      output_file: .orchestrator/metrics.json

  - name: custom_validator
    type: custom
    priority: 20
    enabled: true
    events: ["task.started"]
    module: user_extensions.hooks.validator
    class: CustomValidationHook
```

### 9. Error Handling & Retry

#### Three-Level Retry Configuration

```yaml
# Global defaults (lowest priority)
retry:
  max_retries: 3
  retry_delay: 5
  backoff_multiplier: 2.0  # Exponential backoff

# Tool-level overrides (medium priority)
tools:
  bash:
    max_retries: 2  # Less retries for bash

  file_read:
    max_retries: 5  # More retries for file ops

# Task-level overrides (highest priority)
# Set programmatically:
task = await task_manager.create_task(
    title="Critical sync",
    description="...",
    max_retries=10
)
```

#### Retry Logic

```python
async def execute_with_retry(
    self,
    task: Task,
    context: dict
) -> Any:
    max_retries = task.max_retries or self.config["retry"]["max_retries"]
    delay = self.config["retry"]["retry_delay"]
    multiplier = self.config["retry"]["backoff_multiplier"]

    for attempt in range(max_retries + 1):
        try:
            result = await self._reasoning_loop(task, context)
            return result
        except RetryableError as e:
            if attempt == max_retries:
                raise

            wait_time = delay * (multiplier ** attempt)
            logger.warning(f"Retry {attempt + 1}/{max_retries} after {wait_time}s: {e}")
            await asyncio.sleep(wait_time)
        except FatalError:
            raise  # Don't retry fatal errors
```

#### Error Types

```python
class OrchestratorError(Exception):
    """Base error"""

class RetryableError(OrchestratorError):
    """Errors that can be retried (API timeouts, rate limits)"""

class FatalError(OrchestratorError):
    """Errors that should not be retried (invalid input, auth failures)"""

class ToolExecutionError(RetryableError):
    """Tool failed but may succeed on retry"""

class TaskValidationError(FatalError):
    """Task is invalid and cannot be executed"""
```

---

## Implementation Status

### Phase 1: Core Foundation ✅ COMPLETED

**Goal**: Minimal working orchestrator with basic task execution.

**Checklist**:
- ✅ CLI interface (`orchestrator` command)
- ✅ Basic orchestrator loop (ReAct pattern)
- ✅ LLM client with Anthropic provider
- ✅ Tool registry + built-in tools (bash, file_read, file_write, file_delete)
- ✅ Simple task model (no hierarchy yet)
- ✅ 5 built-in skills (code_edit, code_review, research, git_operations, file_management)
- ✅ Configuration loading (YAML)
- ✅ Environment variable support (python-dotenv)

**Not Implemented**:
- Hook system (base classes only)
- Task dependencies
- Subagents
- HITL approvals
- Memory/caching

### Phase 2: Hook System & HITL ✅ COMPLETED

**Goal**: Add extensibility through hooks and human oversight.

**Checklist**:
- ✅ Hook engine implementation
  - ✅ Event triggering at lifecycle points
  - ✅ Priority-based execution
  - ✅ Context propagation
  - ✅ Result handling (continue/block/modify)
- ✅ Built-in hooks
  - ✅ LoggingHook (all events)
  - ✅ HITLHook (approval prompts)
  - ✅ MetricsHook (statistics collection)
- ✅ HITL workflow
  - ✅ Interactive approval prompts
  - ✅ Approval rules configuration
  - ✅ Auto-approval for safe operations
  - ✅ Timeout handling
- ✅ Hook configuration loading
  - ✅ Parse `config/hooks.yaml`
  - ⚠️ Register custom hooks from user_extensions (framework ready, not implemented)
  - ✅ Enable/disable hooks dynamically

**Implemented Files**:
- `src/orchestrator/hooks/engine.py` - Hook engine with event orchestration
- `src/orchestrator/hooks/builtin/logging.py` - LoggingHook, StartupLoggingHook, LLMCallLoggingHook
- `src/orchestrator/hooks/builtin/hitl.py` - HITLHook with interactive approval prompts
- `src/orchestrator/hooks/builtin/metrics.py` - MetricsHook for statistics collection
- `src/orchestrator/core/orchestrator.py` - Integrated hook triggers at all lifecycle events
- `config/hooks.yaml` - Complete hook configuration

**Completion**: ~95% (user_extensions auto-discovery deferred to Phase 4)

### Phase 2.5: TodoList Tool (Hotfix) 🚧 IN PROGRESS

**Reason for Insertion**: Critical capability gap discovered - Agent cannot track progress across long reasoning loops (max 20 iterations).

**Problem**: In complex multi-step tasks, the Agent may lose track of what has been completed after 10+ iterations, leading to incomplete or repeated work.

**Solution**: Implement TodoList tool (inspired by Claude Code's TodoWrite) to enable structured task progress tracking.

**Checklist**:
- ✅ Extend Task model with `todo_list` field and `TodoItem` model
- ✅ Implement TodoListTool with operations: write, add, update, list, clear
- ✅ Register tool in ToolRegistry
- ✅ Update system prompt with usage instructions
- ✅ Enable in configuration (config/default.yaml)
- ⏳ Testing with complex multi-step tasks

**Implemented Files**:
- `src/orchestrator/tasks/models.py` - Added TodoItem model and Task.todo_list field
- `src/orchestrator/tools/builtin/todo.py` - TodoListTool implementation
- `src/orchestrator/tools/registry.py` - Registered TodoListTool
- `src/orchestrator/core/orchestrator.py` - Updated system prompt, task injection
- `config/default.yaml` - Enabled todo_list tool

**Usage Example**:
```python
# Agent can now use todo_list tool
{
  "operation": "write",
  "todos": [
    {"content": "Read database schema", "status": "pending", "active_form": "Reading database schema"},
    {"content": "Design new table", "status": "pending", "active_form": "Designing new table"},
    {"content": "Write migration", "status": "pending", "active_form": "Writing migration"}
  ]
}

# Update progress
{"operation": "update", "index": 0, "status": "completed"}
{"operation": "update", "index": 1, "status": "in_progress"}
```

**Impact**: Enables Agent to handle complex tasks without losing context. Critical for production use.

**Priority**: HIGH - Blocks effective execution of complex tasks

**Completion**: ~90% (implementation done, testing pending)

### Phase 3: Task Hierarchy & Dependencies ⏳ NOT STARTED

**Goal**: Support complex multi-step workflows with task decomposition.

**Checklist**:
- [ ] Task hierarchy
  - [ ] Parent-child relationships
  - [ ] Subtask creation API
  - [ ] Automatic subtask execution
- [ ] Task dependencies
  - [ ] `depends_on` and `blocks` relationships
  - [ ] Dependency resolution algorithm
  - [ ] Cycle detection
- [ ] Smart task scheduling
  - [ ] Execute tasks in dependency order
  - [ ] Parallel execution of independent tasks
  - [ ] Progress tracking across hierarchy
- [ ] Task decomposition skill
  - [ ] LLM analyzes complex tasks
  - [ ] Automatically creates subtasks
  - [ ] Sets appropriate dependencies

**Estimated Effort**: 3-4 days

### Phase 4: Subagents & Skill Registry ⏳ NOT STARTED

**Goal**: Enable delegation and skill-based task assignment.

**Checklist**:
- [ ] Subagent manager
  - [ ] Spawn isolated child agents
  - [ ] Resource constraints (tokens, time, tools)
  - [ ] Context isolation
  - [ ] Result collection
- [ ] Subagent lifecycle
  - [ ] Concurrent subagent limits
  - [ ] Graceful shutdown
  - [ ] Error propagation to parent
- [ ] Skill registry
  - [ ] Auto-discover SKILL.md files
  - [ ] Parse frontmatter metadata
  - [ ] Index by tags and tools_required
  - [ ] Skill search API
- [ ] Skill injection
  - [ ] Match task to appropriate skill
  - [ ] Inject skill instructions into prompt
  - [ ] Track skill usage metrics

**Estimated Effort**: 4-5 days

### Phase 5: Memory & Optimization ⏳ NOT STARTED

**Goal**: Improve efficiency through caching and cross-session memory.

**Checklist**:
- [ ] Tool result caching
  - [ ] Cache identical tool calls
  - [ ] TTL-based invalidation
  - [ ] Cache hit metrics
- [ ] LLM response caching
  - [ ] Cache repeated queries
  - [ ] Semantic similarity matching
  - [ ] Privacy-aware caching (no sensitive data)
- [ ] Cross-session memory
  - [ ] Embeddings generation (tool results, task outcomes)
  - [ ] Vector database (ChromaDB)
  - [ ] Similarity search for relevant history
  - [ ] Memory injection into context
- [ ] Performance optimization
  - [ ] Parallel tool execution
  - [ ] Batch LLM calls where possible
  - [ ] Streaming responses
  - [ ] Token usage tracking and budgets

**Estimated Effort**: 5-7 days

---

## Key Design Decisions

### 1. Async Everywhere

**Decision**: All I/O operations use `async/await`.

**Rationale**:
- Non-blocking LLM API calls
- Concurrent tool execution (Phase 5)
- Efficient subagent management
- Better resource utilization

**Impact**:
- All custom tools must be `async def`
- Hook execution is async
- Task execution is async

### 2. Anthropic Native Tool Calling

**Decision**: Use Anthropic's tool calling API, not text parsing.

**Rationale**:
- More reliable than regex parsing
- Structured tool input/output
- Proper error handling
- Native support in API

**Implementation**: See `src/orchestrator/core/orchestrator.py:_reasoning_loop()`

### 3. Sequential Execution (Phase 1)

**Decision**: Execute tasks one at a time in Phase 1.

**Rationale**:
- Simpler implementation
- Easier debugging
- Sufficient for initial use cases

**Future**: Parallel execution in Phase 5 with proper resource management.

### 4. Skills as Prompts

**Decision**: Skills are markdown instructions, not executable code.

**Rationale**:
- More flexible (LLM decides tool usage)
- Easier to create (no coding required)
- Version-controllable text files
- LLM can adapt instructions to context

**Alternative Rejected**: Executable skill workflows (too rigid, less adaptable).

### 5. Subagent Isolation

**Decision**: Subagents have limited context and resources.

**Rationale**:
- Prevents context overflow
- Forces task decomposition
- Budget control (tokens, time)
- Clearer separation of concerns

**Communication**: Parent → Child via task context, Child → Parent via result only.

### 6. Hook-Based Extensibility

**Decision**: Hooks at every key lifecycle point.

**Rationale**:
- Extensible without modifying core
- User customizations in user_extensions
- Easy to enable/disable features
- Composable behaviors (multiple hooks per event)

**Examples**: Logging, HITL, metrics, custom validation.

### 7. Three-Level Retry Configuration

**Decision**: Global < Tool < Task retry settings.

**Rationale**:
- Sensible defaults for all tools
- Tool-specific overrides (bash vs file_read)
- Critical task overrides
- Flexible without complexity

**Backoff**: Exponential backoff to avoid rate limits.

### 8. Declarative Tool Definitions

**Decision**: Tools declare capabilities; LLM decides usage.

**Rationale**:
- LLM has full context for tool selection
- Tools don't need complex orchestration logic
- Easy to add new tools
- Natural language tool descriptions

**Schema**: Tools converted to Anthropic's `input_schema` format.

---

## Important Patterns

### Adding a New Tool

#### Simple Function Tool

```python
# user_extensions/tools/my_tools.py

from orchestrator.tools.base import tool

@tool(name="count_lines", requires_approval=False)
async def count_lines(file_path: str) -> int:
    """Count lines in a file."""
    with open(file_path) as f:
        return len(f.readlines())
```

#### Class-Based Tool with State

```python
# user_extensions/tools/my_tools.py

from orchestrator.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult

class GitStatusTool(Tool):
    definition = ToolDefinition(
        name="git_status",
        description="Get git repository status",
        parameters=[
            ToolParameter(
                name="repo_path",
                type="string",
                description="Path to git repository",
                required=False,
                default="."
            )
        ],
        requires_approval=False
    )

    async def execute(self, repo_path: str = ".") -> ToolResult:
        import subprocess
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            return ToolResult(success=True, data=result.stdout)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

# Register in user_extensions/__init__.py
from .tools.my_tools import GitStatusTool
def register_user_extensions(orchestrator):
    orchestrator.tool_registry.register(GitStatusTool())
```

### Creating a New Skill

```bash
# Create skill directory
mkdir -p user_extensions/skills/deployment

# Create SKILL.md
cat > user_extensions/skills/deployment/SKILL.md << 'EOF'
---
name: deployment
description: "Deploy applications to production safely"
tools_required: [bash, file_read]
version: "1.0.0"
tags: [devops, deployment, production]
---

# Deployment

## Overview
Safe deployment procedures for production environments.

## Pre-Deployment Checklist
- [ ] All tests passing
- [ ] Code reviewed and approved
- [ ] Database migrations prepared
- [ ] Rollback plan documented
- [ ] Monitoring alerts configured

## Deployment Steps
1. Check current production status
2. Create backup
3. Run database migrations
4. Deploy new version
5. Verify deployment
6. Monitor for errors

## Rollback Procedure
If deployment fails:
1. Stop new version
2. Restore from backup
3. Roll back database migrations
4. Restart old version
5. Document failure for post-mortem
EOF
```

### Adding a Custom Hook

```python
# user_extensions/hooks/custom_hooks.py

from orchestrator.hooks.base import Hook, HookContext, HookResult

class SlackNotificationHook(Hook):
    name = "slack_notification"
    priority = 90
    events = ["task.completed", "task.failed"]

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def execute(self, context: HookContext) -> HookResult:
        import httpx

        task = context.data["task"]
        event = context.event

        message = {
            "text": f"Task {task.title} {event.split('.')[1]}",
            "attachments": [{
                "color": "good" if event == "task.completed" else "danger",
                "fields": [
                    {"title": "Task ID", "value": task.id, "short": True},
                    {"title": "Status", "value": task.status.value, "short": True}
                ]
            }]
        }

        async with httpx.AsyncClient() as client:
            await client.post(self.webhook_url, json=message)

        return HookResult(action="continue")

# Register in config/hooks.yaml
hooks:
  - name: slack_notification
    type: custom
    priority: 90
    enabled: true
    events: ["task.completed", "task.failed"]
    module: user_extensions.hooks.custom_hooks
    class: SlackNotificationHook
    config:
      webhook_url: "${SLACK_WEBHOOK_URL}"
```

### Using HITL for Critical Operations

```python
# Mark tool as requiring approval
class DestructiveTool(Tool):
    definition = ToolDefinition(
        name="delete_database",
        description="Permanently delete a database",
        parameters=[...],
        requires_approval=True  # <-- Triggers HITL
    )

    async def execute(self, db_name: str) -> ToolResult:
        # This will only execute after user approval
        ...
```

### Task Decomposition (Phase 3)

```python
# User creates high-level task
await task_manager.create_task(
    title="Migrate database to PostgreSQL",
    description="Migrate from MySQL to PostgreSQL"
)

# LLM decomposes into subtasks:
subtasks = [
    "Export MySQL schema",
    "Convert schema to PostgreSQL syntax",
    "Export MySQL data",
    "Transform data for PostgreSQL",
    "Import schema to PostgreSQL",
    "Import data to PostgreSQL",
    "Verify data integrity",
    "Update application configuration"
]

for i, subtask_title in enumerate(subtasks):
    await task_manager.create_subtask(
        parent_id=parent_task.id,
        title=subtask_title,
        depends_on=[subtasks[i-1].id] if i > 0 else []
    )
```

### Spawning a Subagent (Phase 4)

```python
# Parent task delegates to subagent
parent_task = await task_manager.get_task(task_id)

subtask = await task_manager.create_task(
    title="Research best PostgreSQL migration tools",
    description="Find and compare tools for MySQL to PostgreSQL migration"
)

subagent_handle = await subagent_manager.spawn(
    parent_task=parent_task,
    subtask=subtask,
    context={"domain": "database migration"},
    constraints={
        "max_tokens": 30000,
        "timeout_seconds": 180,
        "allowed_tools": ["web_fetch", "file_read"],
        "skill": "research"
    }
)

result = await subagent_handle.wait()
```

---

## Configuration

### Main Configuration

Located at `config/default.yaml`. See complete schema in Architecture Deep Dive section.

Key settings:
- `llm.anthropic.model` - Claude model version
- `tools.bash.blocked_commands` - Safety patterns
- `tasks.max_retries` - Global retry limit
- `logging.level` - Verbosity

### Local Overrides

Create `config/local.yaml` (gitignored) for personal settings:

```yaml
llm:
  anthropic:
    max_tokens: 4096  # Override default
    temperature: 0.5

logging:
  level: DEBUG  # More verbose locally
```

### Environment Variables

Required:
- `ANTHROPIC_API_KEY` - Your Anthropic API key

Optional:
- `ORCHESTRATOR_CONFIG` - Path to custom config file
- `ORCHESTRATOR_LOG_LEVEL` - Override log level
- `ORCHESTRATOR_STATE_DIR` - State directory (default: `.orchestrator/`)

---

## Troubleshooting

### API Key Not Found

**Symptom**: `Error: ANTHROPIC_API_KEY environment variable not set`

**Solution**:
1. Check `.env` file exists: `ls -la .env`
2. Verify key is set: `grep ANTHROPIC_API_KEY .env`
3. Ensure no quotes: `ANTHROPIC_API_KEY=sk-ant-xxx` (not `"sk-ant-xxx"`)
4. Restart shell or re-run `source .venv/bin/activate`

### Tool Not Found

**Symptom**: `Tool 'my_tool' not found in registry`

**Solution**:
1. Check tool is registered: `orchestrator tool list`
2. Verify tool is enabled in config:
   ```yaml
   tools:
     my_tool:
       enabled: true
   ```
3. Check registration in `ToolRegistry._register_builtin_tools()` or user_extensions

### LLM Not Using Tools

**Symptom**: LLM responds with text instead of calling tools

**Possible Causes**:
1. Tools not passed to API - check `_reasoning_loop()` passes `tools` parameter
2. Tool descriptions unclear - improve `description` and `parameters.description`
3. Task doesn't require tools - LLM correctly determined text response is sufficient

**Debug**:
```python
# Add logging in _reasoning_loop()
logger.debug(f"Calling LLM with {len(tools)} tools: {[t['name'] for t in tools]}")
```

### Import Errors

**Symptom**: `ModuleNotFoundError: No module named 'orchestrator'`

**Solution**:
1. Ensure in virtual environment: `which python` should show `.venv/bin/python`
2. Install in editable mode: `pip install -e ".[dev]"`
3. Check `pyproject.toml` exists and has correct `[project]` section

### Task Stuck in IN_PROGRESS

**Symptom**: Task never completes or fails

**Possible Causes**:
1. LLM infinite loop - check conversation history for repeated patterns
2. Tool timeout - increase `tools.bash.timeout` in config
3. Hook blocking - check hook logs for `action="block"`

**Debug**:
```bash
# Check state file
cat .orchestrator/state.json | jq '.tasks[] | select(.status == "IN_PROGRESS")'

# Check logs
tail -f .orchestrator/orchestrator.log
```

### High Token Usage

**Symptom**: Hitting token limits frequently

**Solutions**:
1. Reduce `max_tokens` in config
2. Use more focused task descriptions
3. Enable result caching (Phase 5)
4. Use subagents with token budgets (Phase 4)

---

## Testing Guidelines

### Unit Tests

```bash
# Test specific module
pytest tests/unit/test_tools.py

# Test with verbose output
pytest tests/unit/test_tools.py -v

# Test specific function
pytest tests/unit/test_tools.py::test_bash_tool_execute
```

### Integration Tests

```bash
# Requires API key
export ANTHROPIC_API_KEY=sk-ant-xxx
pytest tests/integration/

# Skip slow tests
pytest tests/integration/ -m "not slow"
```

### Writing Tests

```python
# tests/unit/test_custom_tool.py

import pytest
from orchestrator.tools.base import ToolResult
from user_extensions.tools.my_tools import MyTool

@pytest.mark.asyncio
async def test_my_tool_success():
    tool = MyTool()
    result = await tool.execute(input="test")

    assert result.success is True
    assert result.data == "expected output"

@pytest.mark.asyncio
async def test_my_tool_failure():
    tool = MyTool()
    result = await tool.execute(input="invalid")

    assert result.success is False
    assert "error" in result.error.lower()
```

---

## Deferred Features (Not in Phase 1)

These features have base implementations but are not active:

- ❌ Hook system execution (base classes exist)
- ❌ Task hierarchy and dependencies (fields exist in model)
- ❌ Subagent spawning (no manager yet)
- ❌ HITL approval workflow (no prompts yet)
- ❌ Skill auto-discovery (manual loading only)
- ❌ Cross-session memory (no vector store)
- ❌ Tool result caching (no cache layer)
- ❌ Parallel task execution (sequential only)
- ❌ Multiple LLM providers (Anthropic only)

See phase roadmap for implementation timeline.

---

## Contributing

### Adding Features

1. Check phase roadmap for planned features
2. Create feature branch: `git checkout -b feature/my-feature`
3. Implement with tests
4. Update CLAUDE.md if architecture changes
5. Submit pull request

### Code Style

- Use `black` for formatting: `black src/`
- Use `ruff` for linting: `ruff check src/`
- Type hints required: `mypy src/`
- Docstrings for public APIs (Google style)

### Commit Messages

Follow conventional commits:
```
feat: add database query tool
fix: resolve tool registry race condition
docs: update skill creation guide
test: add integration tests for hooks
refactor: simplify task dependency resolution
```

---

## License

MIT License - see LICENSE file for details.

---

## Additional Resources

- **Anthropic API Docs**: https://docs.anthropic.com/
- **ReAct Paper**: https://arxiv.org/abs/2210.03629
- **BDI Architecture**: https://en.wikipedia.org/wiki/Belief-desire-intention_model
- **Project Issues**: https://github.com/godofpdog/simple_orchestrator/issues
