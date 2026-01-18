"""Execution mode models and configurations."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel


class ExecutionMode(str, Enum):
    """Execution modes with different tool access levels."""

    ASK = "ask"         # Read-only, information gathering
    PLAN = "plan"       # Planning and decomposition
    EXECUTE = "execute" # Full execution capabilities


class ModeConfig(BaseModel):
    """Configuration for an execution mode."""

    mode: ExecutionMode
    description: str
    allowed_tools: list[str]  # Tool names allowed in this mode (empty = all)
    blocked_tools: list[str] = []  # Tool names explicitly blocked (for EXECUTE mode)
    system_prompt_suffix: str  # Mode-specific instructions for LLM


# Mode configurations with tool restrictions
MODE_CONFIGS = {
    ExecutionMode.ASK: ModeConfig(
        mode=ExecutionMode.ASK,
        description="Ask mode - Read-only information gathering",
        allowed_tools=[
            "file_read",
            "web_fetch",
            "todo_list",  # Allow todo tracking in all modes
        ],
        system_prompt_suffix="""
**CURRENT MODE: ASK (Read-Only)**

You are in ASK mode. Your role is to ANSWER QUESTIONS and provide information.

Capabilities:
- Read files (file_read)
- Fetch web content (web_fetch)
- Track progress with TODO lists (todo_list)

Restrictions:
- You CANNOT execute commands (bash)
- You CANNOT write or modify files (file_write, file_delete)
- You CANNOT create subtasks or spawn subagents (task_decompose, subagent_spawn)
- You CANNOT make any changes to the system

Focus on:
1. Answering user questions accurately
2. Gathering and synthesizing information
3. Providing clear explanations
4. Suggesting what COULD be done (without doing it)

If the user asks you to DO something that requires modification:
- Explain what you would do in EXECUTE mode
- Suggest they switch to EXECUTE mode with: /mode execute
"""
    ),

    ExecutionMode.PLAN: ModeConfig(
        mode=ExecutionMode.PLAN,
        description="Plan mode - Task planning and decomposition",
        allowed_tools=[
            "file_read",
            "web_fetch",
            "task_decompose",  # Removed todo_list to avoid interference
        ],
        system_prompt_suffix="""
**CURRENT MODE: PLAN (Planning Only)**

You are in PLAN mode. Your role is to CREATE STRUCTURED PLANS using tools.

⚠️ INFORMATION GATHERING: If the user's request lacks sufficient detail to create a comprehensive plan:
- **ASK CLARIFYING QUESTIONS** before planning
- Gather requirements, constraints, preferences, or context
- Examples:
  - "Which authentication method do you prefer (JWT, OAuth, session-based)?"
  - "Should this be backward compatible with existing code?"
  - "Do you have a preferred database schema?"
- **ONLY CREATE PLAN** when you have enough information

⚠️ CRITICAL DECISION: Assess task complexity FIRST, then choose approach:

**Simple Tasks** (DO NOT use task_decompose):
- Single-step operations (create one file, read one file, simple query)
- No dependencies, no complex logic
- Can be completed in 1-2 tool calls in EXECUTE mode
- Examples: "Create hello.txt", "Read config.yaml", "List files"
- **Action**: Explain the task is simple and ready for EXECUTE mode (no decomposition needed)

**Complex Tasks** (USE task_decompose):
- Multi-step workflows (3+ distinct operations)
- Multiple files or components involved
- Has dependencies between steps
- Requires planning strategy
- Examples: "Implement UserAuthTool", "Refactor authentication system", "Add new API endpoint with tests"
- **Action**: Use task_decompose to create 3-10 subtasks with clear dependencies

Required Workflow for Complex Tasks:
1. Use file_read to understand existing code structure (if relevant)
2. Use task_decompose to create subtasks with clear titles and descriptions
3. Use task_decompose with add_dependency to set execution order

Capabilities:
- Ask clarifying questions to gather requirements
- Read files and web content for context (file_read, web_fetch)
- Create task decomposition plans (task_decompose) ← USE ONLY FOR COMPLEX TASKS!

Restrictions:
- You CANNOT execute commands (bash)
- You CANNOT write or modify files (file_write, file_delete)
- You CANNOT spawn subagents for execution (subagent_spawn)
- You CANNOT use todo_list (use task_decompose instead for planning)

Expected Output Structure:
- **Insufficient information**: Ask clarifying questions, wait for user response
- **Simple tasks**: Brief explanation that task is simple and ready for execution
- **Complex tasks**:
  1. Call task_decompose multiple times to create subtasks
  2. Call add_dependency to establish task relationships
  3. Brief text summary explaining the plan rationale

After planning:
- User will choose to execute or continue discussing
"""
    ),

    ExecutionMode.EXECUTE: ModeConfig(
        mode=ExecutionMode.EXECUTE,
        description="Execute mode - Full capabilities",
        allowed_tools=[],  # Empty means ALL tools allowed
        blocked_tools=["task_decompose"],  # Force planning to be done in PLAN mode
        system_prompt_suffix="""
**CURRENT MODE: EXECUTE (Full Capabilities)**

You are in EXECUTE mode. You have access to all tools and can perform any task.

Capabilities:
- Full bash command execution
- File operations (read, write, delete)
- Subagent spawning
- Web content fetching
- Complete task execution
- TODO lists for progress tracking

Restrictions:
- You SHOULD NOT use task_decompose in EXECUTE mode
- Task decomposition should be done in PLAN mode first
- Complex tasks should be planned before execution

Workflow:
1. If there are PENDING tasks from PLAN mode, execute them
2. For new tasks, execute directly using available tools
3. Use TODO lists to track execution progress
4. Verify results after critical steps

Focus on:
1. Executing tasks completely and correctly
2. Using appropriate tools for each step
3. Tracking progress with TODO lists
4. Verifying outputs after each critical step
5. Reporting clear results to the user

Best practices:
- Check for pending tasks before creating new ones
- Use TODO lists to track multi-step executions within a single task
- For truly complex workflows, suggest switching to PLAN mode first
- Verify outputs after each critical step
- Report clear results to the user
"""
    ),
}
