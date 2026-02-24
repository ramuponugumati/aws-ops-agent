"""Core framework — skill registry, event router, state management."""
import json
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ActionStatus(Enum):
    PENDING = "pending_approval"
    APPROVED = "approved"
    EXECUTED = "executed"
    SKIPPED = "skipped"


@dataclass
class Finding:
    skill: str
    title: str
    severity: Severity
    description: str
    resource_id: str = ""
    account_id: str = ""
    region: str = ""
    monthly_impact: float = 0.0
    recommended_action: str = ""
    action_status: ActionStatus = ActionStatus.PENDING
    auto_remediate: bool = False
    metadata: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self):
        d = asdict(self)
        d["severity"] = self.severity.value
        d["action_status"] = self.action_status.value
        return d


@dataclass
class SkillResult:
    skill_name: str
    findings: list[Finding] = field(default_factory=list)
    duration_seconds: float = 0.0
    accounts_scanned: int = 0
    regions_scanned: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total_impact(self):
        return sum(f.monthly_impact for f in self.findings)

    @property
    def critical_count(self):
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)


class BaseSkill:
    """Base class for all ops agent skills."""
    name: str = "base"
    description: str = ""
    version: str = "0.1.0"

    def scan(self, regions, profile=None, account_id=None, **kwargs) -> SkillResult:
        raise NotImplementedError

    def remediate(self, finding: Finding, profile=None) -> bool:
        """Optional: auto-remediate a finding. Returns True if successful."""
        return False


class SkillRegistry:
    """Registry of all available skills."""
    _skills: dict[str, BaseSkill] = {}

    @classmethod
    def register(cls, skill: BaseSkill):
        cls._skills[skill.name] = skill

    @classmethod
    def get(cls, name: str) -> Optional[BaseSkill]:
        return cls._skills.get(name)

    @classmethod
    def all(cls) -> dict[str, BaseSkill]:
        return cls._skills

    @classmethod
    def names(cls) -> list[str]:
        return list(cls._skills.keys())
