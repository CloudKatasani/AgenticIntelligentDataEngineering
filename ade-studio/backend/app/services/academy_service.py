"""The Academy: teaching material generated from the specs themselves.

Nothing here is hand-written per agent. Each lesson is assembled from that
agent's own spec and SKILL.md, so the training material cannot drift from the
contract the runtime actually enforces — the failure mode of every hand-written
internal wiki.
"""

from __future__ import annotations

from typing import Any

from app.domain.agent import AgentSpec
from app.services.catalog_service import CatalogService

TIER_GUIDE: list[dict[str, str]] = [
    {
        "tier": "L0",
        "name": "Advisory",
        "meaning": "Proposes only. A human does the work; the agent argues for an approach.",
        "in_the_product": "Runs finish in Awaiting acceptance. Artifacts are labelled Proposal.",
    },
    {
        "tier": "L1",
        "name": "Draft-and-review",
        "meaning": "Produces a complete artifact, but nothing takes effect until a human accepts it.",
        "in_the_product": "Runs finish in Awaiting acceptance. Accepting promotes artifacts to Record.",
    },
    {
        "tier": "L2",
        "name": "Supervised action",
        "meaning": "May execute autonomously outside production; production actions need approval.",
        "in_the_product": "Runs complete on their own. The environment on the connection decides.",
    },
    {
        "tier": "L3",
        "name": "Bounded autonomous action",
        "meaning": "May act within a versioned, pre-approved catalog of actions with rollback.",
        "in_the_product": "Only agent 20 reaches here, and ADE Studio still plans rather than executes.",
    },
    {
        "tier": "L4",
        "name": "Autonomous, non-mutating",
        "meaning": "Runs continuously and independently, but changes no data.",
        "in_the_product": "Agent 17 monitors and reports; it cannot write to a source.",
    },
]

DESIGN_RULES: list[dict[str, str]] = [
    {
        "rule": "Non-overlapping scope by construction",
        "detail": (
            "Every agent's spec names the agent that owns each excluded piece of work, and the "
            "boundary is reciprocal. An agent that does an adjacent agent's job has violated its "
            "scope even when the output is correct."
        ),
        "enforced_by": "Handoffs are a required field of every run's output contract.",
    },
    {
        "rule": "Dependencies are typed",
        "detail": (
            "Hard dependencies block execution; soft dependencies only degrade quality. The "
            "hard-dependency graph is validated acyclic."
        ),
        "enforced_by": "The hard_dependencies gate refuses a run whose upstream agents have not completed.",
    },
    {
        "rule": "Autonomy tiers are structural",
        "detail": (
            "Tier is a property of the agent, not of how confident it feels. Agents 02, 26 and 27 "
            "are capped at L1 in regulated environments regardless of measured accuracy."
        ),
        "enforced_by": "The autonomy_tier gate caps the tier when the connection is marked regulated.",
    },
    {
        "rule": "Determinism where possible",
        "detail": (
            "Statistics, diffs and comparisons come from deterministic tools. The model interprets "
            "them; it never computes them."
        ),
        "enforced_by": "Profiles are computed by the profiler and passed to the model as facts.",
    },
    {
        "rule": "Cross-cutting agents have no domain scope",
        "detail": "Supervisor routes, Evaluator measures, Reviewer critiques. None produces domain artifacts.",
        "enforced_by": "Agents 33–35 are estate-scoped and require no object selection.",
    },
]


class AcademyService:
    def __init__(self, catalog: CatalogService) -> None:
        self.catalog = catalog

    # ------------------------------------------------------------------ #

    def overview(self) -> dict[str, Any]:
        agents = self.catalog.list_agents()
        by_domain: dict[str, list[dict[str, str]]] = {}
        for agent in agents:
            by_domain.setdefault(agent.domain, []).append(
                {
                    "id": agent.id,
                    "name": agent.name,
                    "tier": agent.tier.value,
                    "purpose": agent.purpose,
                    "core": str(agent.core_original_scope),
                }
            )
        return {
            "agent_count": len(agents),
            "domains": [
                {
                    "domain": domain,
                    "agents": members,
                    "blurb": _DOMAIN_BLURBS.get(domain, ""),
                }
                for domain, members in by_domain.items()
            ],
            "tiers": TIER_GUIDE,
            "design_rules": DESIGN_RULES,
            "learning_paths": self.learning_paths(),
        }

    def learning_paths(self) -> list[dict[str, Any]]:
        """Ordered routes through the fleet, built from the real dependency graph."""
        return [
            {
                "id": "onboard-a-source",
                "title": "Onboard a new source, end to end",
                "why": (
                    "The path a new dataset actually travels: understand it, classify it, "
                    "describe it, then model and build on it."
                ),
                "steps": self._steps(["01", "02", "05", "03", "08", "07", "09", "10", "11"]),
            },
            {
                "id": "trustworthy-data",
                "title": "Make a dataset trustworthy",
                "why": "How quality commitments are proposed, codified, monitored and enforced.",
                "steps": self._steps(["01", "16", "13", "17", "21", "19", "20"]),
            },
            {
                "id": "govern-and-publish",
                "title": "Govern it and publish it",
                "why": "From classification through entitlement and evidence to a published product.",
                "steps": self._steps(["02", "26", "27", "28", "13", "29", "12", "31"]),
            },
            {
                "id": "run-it-well",
                "title": "Run it well",
                "why": "Cost, latency, orchestration and capacity once the pipelines exist.",
                "steps": self._steps(["22", "23", "24", "25"]),
            },
            {
                "id": "modernize-legacy",
                "title": "Modernize a legacy system",
                "why": "Recovering semantics from a system nobody remembers, then proving parity.",
                "steps": self._steps(["06", "14", "09", "18", "11"]),
            },
            {
                "id": "supervise-the-fleet",
                "title": "Supervise the fleet",
                "why": "The cross-cutting agents that route, measure and critique the others.",
                "steps": self._steps(["33", "34", "35"]),
            },
        ]

    def _steps(self, agent_ids: list[str]) -> list[dict[str, str]]:
        steps: list[dict[str, str]] = []
        for agent_id in agent_ids:
            try:
                agent = self.catalog.get(agent_id)
            except Exception:  # noqa: BLE001 — a path must survive a missing spec
                continue
            steps.append(
                {
                    "id": agent.id,
                    "name": agent.name,
                    "tier": agent.tier.value,
                    "domain": agent.domain,
                    "one_liner": agent.purpose.split(".")[0].strip() + ".",
                }
            )
        return steps

    # ------------------------------------------------------------------ #

    def lesson(self, agent_id: str) -> dict[str, Any]:
        """Everything a new operator needs to use one agent correctly."""
        agent = self.catalog.get(agent_id)
        dependents = self.catalog.dependents_of(agent.id)
        seams = self.catalog.seams(agent.id)
        tier = next((t for t in TIER_GUIDE if t["tier"] == agent.tier.value), {})

        return {
            "agent": {
                "id": agent.id,
                "name": agent.name,
                "domain": agent.domain,
                "tier": agent.tier.value,
                "tier_name": agent.tier_name,
                "tier_definition": agent.tier_definition,
                "core_original_scope": agent.core_original_scope,
                "purpose": agent.purpose,
            },
            "in_one_sentence": agent.purpose.split(".")[0].strip() + ".",
            "why_it_exists": _why(agent),
            "owns": agent.scope,
            "does_not_own": [
                {
                    "exclusion": g.exclusion,
                    "owner_id": g.owned_by,
                    "owner_name": g.owner_name,
                }
                for g in agent.non_goals
            ],
            "seams": seams,
            "reads": agent.inputs,
            "produces": agent.outputs,
            "artifacts": [a.model_dump() for a in agent.artifacts],
            "tools": agent.tools,
            "depends_on": {
                "hard": [d.model_dump() for d in agent.hard_dependencies],
                "soft": [d.model_dump() for d in agent.soft_dependencies],
                "context_layer": agent.context_layer_requirements,
            },
            "feeds": [{"id": d.id, "name": d.name, "domain": d.domain} for d in dependents],
            "triggers": agent.triggers,
            "workflow": _workflow(agent),
            "acceptance_criteria": agent.acceptance_criteria,
            "evaluation": agent.evaluation,
            "kpis": agent.kpis,
            "escalation": agent.escalation,
            "tier_guide": tier,
            "guardrails": _guardrails(agent),
            "checkpoint": _checkpoint(agent),
            "skill_markdown": agent.skill_markdown,
        }


_DOMAIN_BLURBS: dict[str, str] = {
    "discovery": (
        "Find out what is actually there. These agents produce the ground truth every other "
        "agent reasons over — profiles, classifications, lineage and shared vocabulary."
    ),
    "build": (
        "Turn understanding into working data assets: models, schemas, mappings, code, tests, "
        "semantics and the contracts that bind them."
    ),
    "quality": (
        "Keep it correct over time. Rules and baselines catch problems, diagnosis explains them, "
        "and remediation — carefully — fixes them."
    ),
    "operations": (
        "Keep it affordable, fast and on schedule: cost, latency, orchestration and capacity."
    ),
    "governance": (
        "Make it defensible: who may see it, how long it is kept, what evidence exists, and what "
        "is fit to publish."
    ),
    "consumption": (
        "Serve the people who use the data — rationalising reports, answering questions and "
        "capturing new requests."
    ),
    "cross-cutting": (
        "No domain scope of their own. They route work, measure the fleet, and critique its "
        "output."
    ),
}


def _why(agent: AgentSpec) -> str:
    """Explain the agent's existence through the boundary it defends.

    Quoted spec text is reproduced verbatim — lower-casing it would mangle the
    acronyms the catalog is full of (CI, PII, SLO, NL→SQL).
    """
    delegated = [g for g in agent.non_goals if not g.human_owned]
    if not delegated:
        return (
            f"{agent.name} exists because this is a distinct job with its own evidence, "
            "thresholds and failure modes, and it is measured on its own terms."
        )
    first = delegated[0]
    owns = agent.scope[0] if agent.scope else "a single, well-defined piece of the work"
    return (
        f"{agent.name} is deliberately narrow. It owns “{owns}”, and explicitly does not own "
        f"“{first.exclusion}” — that belongs to {first.owner_name}. Splitting the work this way "
        "is what keeps each agent's evaluation meaningful and its output auditable."
    )


def _workflow(agent: AgentSpec) -> list[str]:
    """Pull the numbered Workflow section straight out of SKILL.md."""
    lines = agent.skill_markdown.splitlines()
    steps: list[str] = []
    inside = False
    for line in lines:
        if line.strip().lower().startswith("## workflow"):
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if inside and line.strip():
            steps.append(line.strip())
    return steps


def _guardrails(agent: AgentSpec) -> list[str]:
    lines = agent.skill_markdown.splitlines()
    rules: list[str] = []
    inside = False
    for line in lines:
        if "universal guardrails" in line.strip().lower():
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if inside and line.strip().startswith("-"):
            rules.append(line.strip().lstrip("- ").strip())
    return rules


def _checkpoint(agent: AgentSpec) -> list[dict[str, Any]]:
    """Three questions that check the operator understood the boundary.

    Generated from the spec, so the answers stay correct as the catalog changes.
    """
    questions: list[dict[str, Any]] = []

    # Only agent-owned exclusions make a sensible "which agent owns this?"
    # question; human-owned ones have no agent answer.
    delegated = [g for g in agent.non_goals if not g.human_owned]
    if delegated:
        goal = delegated[0]
        distractors = [g.owner_name for g in delegated[1:3]]
        options = list(dict.fromkeys([goal.owner_name, agent.name, *distractors]))[:4]
        questions.append(
            {
                "question": f"Which agent owns “{goal.exclusion}”?",
                "options": sorted(options),
                "answer": goal.owner_name,
                "explanation": (
                    f"{agent.name} names this in its non-goals and hands off to "
                    f"{goal.owner_name} rather than doing it."
                ),
            }
        )

    questions.append(
        {
            "question": f"{agent.name} runs at tier {agent.tier.value}. What does that permit?",
            "options": [f"{t['tier']} — {t['name']}" for t in TIER_GUIDE],
            "answer": next(
                (f"{t['tier']} — {t['name']}" for t in TIER_GUIDE if t["tier"] == agent.tier.value),
                "",
            ),
            "explanation": agent.tier_definition,
        }
    )

    if agent.hard_dependencies:
        dep = agent.hard_dependencies[0]
        questions.append(
            {
                "question": f"What happens if {dep.agent_name} has not run for this scope?",
                "options": [
                    "The run is blocked until it does, or an override is recorded",
                    "The agent regenerates the missing output itself",
                    "The run proceeds with lower confidence",
                    "The dependency is only a suggestion",
                ],
                "answer": "The run is blocked until it does, or an override is recorded",
                "explanation": (
                    "Hard dependencies block execution. Missing hard inputs are reported as "
                    "blockers, never worked around by regenerating another agent's outputs."
                ),
            }
        )
    else:
        questions.append(
            {
                "question": f"{agent.name} has no hard dependencies. What does that mean?",
                "options": [
                    "It can start from platform and context-layer inputs alone",
                    "It never needs any input",
                    "It outranks other agents",
                    "Its output needs no review",
                ],
                "answer": "It can start from platform and context-layer inputs alone",
                "explanation": (
                    "No hard dependency means nothing blocks it, not that it works without inputs "
                    "— its context-layer prerequisites still apply."
                ),
            }
        )
    return questions
