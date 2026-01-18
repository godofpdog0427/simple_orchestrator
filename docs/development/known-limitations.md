# Known Limitations and Future Improvements

This document tracks known limitations in the current implementation and outlines potential future improvements as the project scales.

---

## Bash Read-Only Mode Security

### Current Implementation

ASK and PLAN modes allow bash for information gathering with:

1. **Primary defense**: System prompt instructs LLM to use read-only operations
2. **Safety net**: Blacklist blocks obvious dangerous commands (reboot, rm -rf /, sudo, etc.)

**Implementation details** (Phase 6A++):
- File: `src/orchestrator/tools/builtin/bash.py`
- Method: `_is_dangerous_command(command: str) -> tuple[bool, str]`
- Dangerous commands: `reboot`, `shutdown`, `halt`, `poweroff`, `killall`, `pkill`, `dd`, `mkfs`, `fdisk`, `parted`, `:()`
- Dangerous patterns: `sudo`, `rm -rf /`, `> /dev/`, `curl.*|.*bash`, `wget.*|.*sh`
- Output redirection blocking: `>`, `>>`

### Known Gaps

The current blacklist-based approach cannot prevent all possible modifications:

**Bypasses that are theoretically possible but unlikely:**

1. **Complex command injection**
   - Example: `python -c "import os; os.system('reboot')"`
   - Why unlikely: Requires LLM to deliberately craft malicious code, violates system prompt

2. **Indirect file modification**
   - Example: `python script.py` (where script.py modifies files)
   - Why unlikely: Requires pre-existing malicious scripts in workspace

3. **Package installation**
   - Example: `pip install malicious-package`
   - Why unlikely: Violates read-only instruction, package must already be malicious

4. **Scripting language abuse**
   - Example: `node -e "require('fs').unlinkSync('/important/file')"`
   - Why unlikely: Same as command injection - requires deliberate violation

5. **Environment variable manipulation**
   - Example: `export PATH=/malicious:$PATH`
   - Why unlikely: Limited impact in subprocess, doesn't persist

### Why This Is Acceptable for Current Scope

1. **Claude 4.x has extremely strong instruction following**
   - System prompts explicitly state "read-only operations only"
   - LLM is highly unlikely to deliberately violate instructions
   - Testing shows consistent adherence to read-only guidance

2. **Personal project scope (not multi-tenant production)**
   - Single user environment
   - User can monitor and approve bash commands (requires_approval flag)
   - No untrusted user input

3. **Workspace isolation provides additional protection**
   - Tasks execute within `.orchestrator/workspace` directory
   - Limited blast radius for accidental modifications
   - Important files outside workspace are protected

4. **Blacklist prevents 90% of accidental disasters**
   - Catches obvious dangerous commands (reboot, shutdown)
   - Prevents destructive patterns (rm -rf /, sudo)
   - Blocks output redirection that could overwrite files

5. **Trade-off analysis**
   - **Benefit**: Bash greatly enhances ASK/PLAN mode capabilities (ls, grep, find, etc.)
   - **Risk**: Theoretical bypasses exist but require deliberate LLM misbehavior
   - **Mitigation**: System prompt + blacklist + workspace isolation
   - **Conclusion**: Risk acceptable given strong LLM instruction following

### Future Improvements (When Project Scales)

Consider these approaches if deploying to production or multi-user environments:

#### 1. Sandboxed Bash Execution

Run bash in Docker container with read-only filesystem:

```python
# Example implementation
async def _execute_sandboxed(self, command: str) -> ToolResult:
    docker_cmd = [
        "docker", "run", "--rm",
        "--read-only",  # Read-only root filesystem
        "--tmpfs", "/tmp",  # Allow temp writes to tmpfs
        "--network", "none",  # No network access
        "--user", "nobody",  # Non-root user
        "alpine:latest",
        "sh", "-c", command
    ]
    # ... execute docker_cmd with asyncio.create_subprocess_exec
```

**Pros**:
- OS-level enforcement of read-only
- Cannot bypass with scripting languages
- Complete isolation

**Cons**:
- Requires Docker installation
- Performance overhead
- More complex error handling

#### 2. Whitelist-Based Approach

Only allow specific safe commands:

```python
ALLOWED_COMMANDS = [
    "ls", "cat", "grep", "find", "head", "tail",
    "wc", "pwd", "tree", "file", "du", "df"
]

def _is_command_allowed(self, command: str) -> bool:
    base_command = command.split()[0]
    return base_command in ALLOWED_COMMANDS
```

**Pros**:
- Most restrictive approach
- No bypass possible
- Clear security boundary

**Cons**:
- Less flexible (cannot use pipes, combinations)
- Requires parsing command AST for piping detection
- May break legitimate use cases

#### 3. Process-Level Isolation

Use subprocess with restricted PATH and resource limits:

```python
import resource

async def _execute_restricted(self, command: str) -> ToolResult:
    # Preexec function to set resource limits
    def limit_resources():
        # Limit CPU time (1 second)
        resource.setrlimit(resource.RLIMIT_CPU, (1, 1))
        # Limit memory (100MB)
        resource.setrlimit(resource.RLIMIT_AS, (100*1024*1024, 100*1024*1024))

    # Restricted PATH (only safe binaries)
    safe_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/tmp",
    }

    process = await asyncio.create_subprocess_shell(
        command,
        preexec_fn=limit_resources,  # Set limits before exec
        env=safe_env,
        # ... other args
    )
```

**Pros**:
- Medium security level
- No external dependencies (Docker)
- Resource limits prevent runaway processes

**Cons**:
- Still vulnerable to command injection
- Platform-specific (resource module on Unix only)
- Complex to maintain

#### 4. Read-Only Filesystem Mount

Mount workspace as read-only when in ASK/PLAN modes:

```bash
# Example: remount workspace as read-only
mount -o remount,ro /path/to/workspace
```

**Pros**:
- OS-level enforcement
- Most robust solution
- No parsing needed

**Cons**:
- Requires root privileges or FUSE
- Platform-specific implementation
- May interfere with legitimate temp file needs

---

## Decision Log

### 2026-01-18: Implemented Hybrid Approach (Trust + Blacklist)

**Decision**: Use system prompt guidance + lightweight blacklist for bash read-only mode in ASK/PLAN modes

**Rationale**:
1. Appropriate for personal project scope
2. Claude 4.x has very strong instruction following capabilities
3. Workspace isolation provides additional protection
4. Blacklist catches 90% of accidental dangerous commands
5. Trade-off: Flexibility vs. absolute security → chose flexibility

**Risk Acceptance**:
- Theoretical bypasses exist (command injection, scripting languages)
- These bypasses require deliberate LLM misbehavior
- Probability is extremely low given Claude 4.x instruction following
- Impact is limited by workspace isolation

**Mitigation**:
- Document limitation for future consideration
- Plan future improvements (Docker sandboxing) when project scales
- Monitor for any unexpected bash usage patterns

**Review Trigger**:
- When deploying to multi-user environment
- When accepting untrusted user input
- When moving to production environment
- If bash misuse patterns are observed

---

## Contributing to This Document

When adding new known limitations:

1. **Describe current implementation** - What exists today
2. **Document the gap** - What doesn't work or is insecure
3. **Explain why it's acceptable now** - Scope, trade-offs, mitigations
4. **Propose future improvements** - What could be done later
5. **Add decision log entry** - Why this choice was made, when to revisit

---

## Related Documentation

- [Architecture](architecture.md) - Overall system design
- [Implementation Status](implementation-status.md) - Current phase status
- [Security Considerations](security.md) - General security guidelines (future)
- [Phase 6A++ Plan](/Users/liuyi/.claude/plans/hazy-cooking-meerkat.md) - Read-only bash implementation details
