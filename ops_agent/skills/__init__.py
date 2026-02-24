from ops_agent.skills.cost_anomaly import CostAnomalySkill
from ops_agent.skills.zombie_hunter import ZombieHunterSkill
from ops_agent.skills.security_posture import SecurityPostureSkill
from ops_agent.skills.capacity_planner import CapacityPlannerSkill
from ops_agent.skills.event_analysis import EventAnalysisSkill
from ops_agent.skills.resiliency_gaps import ResiliencyGapsSkill
from ops_agent.skills.tag_enforcer import TagEnforcerSkill
from ops_agent.skills.lifecycle_tracker import LifecycleTrackerSkill
from ops_agent.skills.health_monitor import HealthMonitorSkill
from ops_agent.skills.quota_guardian import QuotaGuardianSkill
from ops_agent.skills.arch_diagram import ArchDiagramSkill
from ops_agent.skills.costopt_intelligence import CostOptIntelligenceSkill
from ops_agent.core import SkillRegistry

for skill_cls in [CostAnomalySkill, ZombieHunterSkill, SecurityPostureSkill,
                  CapacityPlannerSkill, EventAnalysisSkill, ResiliencyGapsSkill,
                  TagEnforcerSkill, LifecycleTrackerSkill, HealthMonitorSkill,
                  QuotaGuardianSkill, ArchDiagramSkill, CostOptIntelligenceSkill]:
    SkillRegistry.register(skill_cls())
