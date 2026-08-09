"""Loads the agent fleet from ``ade-agent-specs``.

The catalog directory is the single source of truth. This service reads
``registry.yaml`` for the roster, then each agent's ``spec.yaml`` (the machine
contract) and ``SKILL.md`` (the runtime instructions), and returns typed
:class:`AgentSpec` objects. Nothing about the 35 agents is hardcoded here.
"""

from __future__ import annotations

import functools
import re
from pathlib import Path
from typing import Any

import yaml

from app.core.errors import NotFound
from app.core.logging import get_logger, log_event
from app.domain.agent import (
    AgentSpec,
    AutonomyTier,
    Dependency,
    DependencyKind,
    NonGoal,
)
from app.runtime import artifact_plans

logger = get_logger(__name__)

_ID_PREFIX = re.compile(r"^\s*(\d{1,2})")


def _agent_id_of(value: Any) -> str:
    """Extract the agent id from a spec reference.

    Dependencies and non-goal owners are written for human readers as
    ``"19 (Root Cause Analysis Agent)"``; only the leading number identifies
    the agent.
    """
    match = _ID_PREFIX.match(str(value))
    return match.group(1).zfill(2) if match else ""


class CatalogService:
    """Reads and caches the agent catalog."""

    def __init__(self, specs_root: Path) -> None:
        self.specs_root = specs_root
        self._agents: dict[str, AgentSpec] | None = None

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #

    def _registry_path(self) -> Path:
        return self.specs_root / "registry.yaml"

    def _load_registry(self) -> list[dict[str, Any]]:
        path = self._registry_path()
        if not path.exists():
            raise NotFound(
                f"Agent registry not found at {path}. Set ADE_SPECS_ROOT to the "
                "ade-agent-specs directory."
            )
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return list(data.get("agents", []))

    def _load(self) -> dict[str, AgentSpec]:
        registry = self._load_registry()
        names = {str(entry["id"]): entry["name"] for entry in registry}
        agents: dict[str, AgentSpec] = {}

        for entry in registry:
            agent_id = str(entry["id"])
            spec_path = self.specs_root / entry["spec"]
            skill_path = self.specs_root / entry["skill"]
            if not spec_path.exists():
                log_event(logger, "spec_missing", agent_id=agent_id, path=str(spec_path))
                continue
            raw = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
            skill = skill_path.read_text(encoding="utf-8") if skill_path.exists() else ""
            agents[agent_id] = self._build_spec(agent_id, raw, skill, names)

        log_event(logger, "catalog_loaded", agent_count=len(agents), root=str(self.specs_root))
        return agents

    def _build_spec(
        self,
        agent_id: str,
        raw: dict[str, Any],
        skill: str,
        names: dict[str, str],
    ) -> AgentSpec:
        meta = raw.get("metadata", {}) or {}
        autonomy = raw.get("autonomy", {}) or {}
        deps = raw.get("dependencies", {}) or {}

        def _dep_list(ids: Any, kind: DependencyKind) -> list[Dependency]:
            out: list[Dependency] = []
            for dep_id in ids or []:
                key = _agent_id_of(dep_id)
                if not key:
                    continue
                out.append(
                    Dependency(agent_id=key, agent_name=names.get(key, f"Agent {key}"), kind=kind)
                )
            return out

        non_goals: list[NonGoal] = []
        for item in raw.get("non_goals", []) or []:
            owner = _agent_id_of(item.get("owned_by") or "")
            non_goals.append(
                NonGoal(
                    exclusion=str(item.get("exclusion", "")),
                    owned_by=owner,
                    # A null owner is a deliberate catalog value: the excluded
                    # work is human-owned, not delegated to another agent.
                    owner_name=(
                        names.get(owner, f"Agent {owner}")
                        if owner
                        else "a human owner — no agent takes this on"
                    ),
                )
            )

        outputs = [str(o) for o in raw.get("outputs", []) or []]
        tier = AutonomyTier(str(autonomy.get("tier", "L1")))

        return AgentSpec(
            id=agent_id,
            slug=str(meta.get("slug", "")),
            name=str(meta.get("name", f"Agent {agent_id}")),
            domain=str(meta.get("domain", "unknown")),
            core_original_scope=bool(meta.get("core_original_scope", False)),
            tier=tier,
            tier_name=str(autonomy.get("tier_name", "")),
            tier_definition=str(autonomy.get("tier_definition", "")),
            purpose=str(raw.get("purpose", "")).strip(),
            scope=[str(s) for s in raw.get("scope", []) or []],
            non_goals=non_goals,
            inputs=[str(i) for i in raw.get("inputs", []) or []],
            outputs=outputs,
            tools=[str(t) for t in raw.get("tools", []) or []],
            hard_dependencies=_dep_list(deps.get("hard"), DependencyKind.HARD),
            soft_dependencies=_dep_list(deps.get("soft"), DependencyKind.SOFT),
            context_layer_requirements=[
                str(c) for c in deps.get("context_layer_requirements", []) or []
            ],
            triggers=[str(t) for t in raw.get("triggers", []) or []],
            acceptance_criteria=[str(a) for a in raw.get("acceptance_criteria", []) or []],
            evaluation=[str(e) for e in raw.get("evaluation", []) or []],
            kpis=[str(k) for k in raw.get("kpis", []) or []],
            escalation=str(raw.get("escalation", "")).strip(),
            skill_markdown=skill,
            artifacts=artifact_plans.plan_for(agent_id, outputs),
            parameters=artifact_plans.parameters_for(agent_id),
            requires_dataset=artifact_plans.requires_dataset(agent_id),
            regulated_tier_cap=(
                AutonomyTier.L1 if agent_id in artifact_plans.REGULATED_TIER_CAP else None
            ),
        )

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    @property
    def agents(self) -> dict[str, AgentSpec]:
        if self._agents is None:
            self._agents = self._load()
        return self._agents

    def reload(self) -> None:
        self._agents = None

    def list_agents(self) -> list[AgentSpec]:
        return sorted(self.agents.values(), key=lambda a: a.id)

    def get(self, agent_id: str) -> AgentSpec:
        key = str(agent_id).zfill(2)
        agent = self.agents.get(key)
        if agent is None:
            raise NotFound(f"No agent with id {agent_id}.")
        return agent

    def domains(self) -> list[str]:
        seen: list[str] = []
        for agent in self.list_agents():
            if agent.domain not in seen:
                seen.append(agent.domain)
        return seen

    def dependents_of(self, agent_id: str) -> list[AgentSpec]:
        """Agents that consume this agent's output."""
        key = str(agent_id).zfill(2)
        return [a for a in self.list_agents() if key in a.dependency_ids]

    def seams(self, agent_id: str) -> list[dict[str, str]]:
        """Reciprocal boundaries: where this agent hands off, and who hands to it.

        Design rule 1 says boundaries are reciprocal. This surfaces both
        directions so an operator can see the whole seam, not half of it.
        """
        agent = self.get(agent_id)
        out: list[dict[str, str]] = []
        for goal in agent.non_goals:
            # Human-owned exclusions are boundaries too, but they are not seams
            # with another agent, so they get their own direction.
            out.append(
                {
                    "direction": "hands_off" if goal.owned_by else "human_owned",
                    "counterpart_id": goal.owned_by,
                    "counterpart_name": goal.owner_name,
                    "detail": goal.exclusion,
                }
            )
        for other in self.list_agents():
            if other.id == agent.id:
                continue
            for goal in other.non_goals:
                if goal.owned_by and goal.owned_by == agent.id:
                    out.append(
                        {
                            "direction": "receives_from",
                            "counterpart_id": other.id,
                            "counterpart_name": other.name,
                            "detail": goal.exclusion,
                        }
                    )
        return out


@functools.lru_cache(maxsize=1)
def get_catalog_service() -> CatalogService:
    from app.core.config import get_settings

    return CatalogService(get_settings().specs_root)
