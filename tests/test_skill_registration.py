"""Tests that all 11 skills are properly registered."""
import pytest
from ops_agent.core import SkillRegistry
import ops_agent.skills  # triggers registration


class TestSkillRegistration:
    EXPECTED_SKILLS = [
        "cost-anomaly", "zombie-hunter", "security-posture",
        "capacity-planner", "event-analysis", "resiliency-gaps",
        "tag-enforcer", "lifecycle-tracker", "health-monitor",
        "quota-guardian", "arch-diagram", "costopt-intelligence",
    ]

    def test_all_12_skills_registered(self):
        assert len(SkillRegistry.all()) >= 12

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_registered(self, skill_name):
        skill = SkillRegistry.get(skill_name)
        assert skill is not None, f"Skill '{skill_name}' not registered"

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_has_name(self, skill_name):
        skill = SkillRegistry.get(skill_name)
        assert skill.name == skill_name

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_has_description(self, skill_name):
        skill = SkillRegistry.get(skill_name)
        assert len(skill.description) > 10

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_has_version(self, skill_name):
        skill = SkillRegistry.get(skill_name)
        assert skill.version
