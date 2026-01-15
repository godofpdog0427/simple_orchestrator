"""Task data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Task priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Task(BaseModel):
    """Task model with hierarchy and dependency support."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM

    # Hierarchy
    parent_id: Optional[str] = None
    subtasks: list[str] = Field(default_factory=list)

    # Dependencies
    depends_on: list[str] = Field(default_factory=list)
    blocks: list[str] = Field(default_factory=list)

    # Execution context
    assigned_to: Optional[str] = None
    skill_required: Optional[str] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Results
    result: Optional[Any] = None
    error: Optional[str] = None

    class Config:
        """Pydantic config."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class ValidationResult(BaseModel):
    """Result of parameter validation."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
