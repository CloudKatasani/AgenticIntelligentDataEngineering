"""Fleet observability and FinOps, computed from the run journal.

Every figure on the observability tab is derived here from runs that actually
happened. Two figures are not measurements — the 30-day projection and the
modelled list-price cost — and both are named as such wherever they appear,
because a spend dashboard that quietly estimates is worse than no dashboard at
all. Everything else is counted, not inferred.

Four questions, which map to the four sections of the payload:

* **Portfolio** — which of the 35 agents does this organisation actually use?
  Coverage, not volume: an estate running one agent 400 times has a portfolio
  problem that a run count hides.
* **Usage** — what is the fleet doing, and where does it stop? Status mix,
  duration percentiles, and which guardrail refuses work most often.
* **FinOps** — where does the money go, and what did it buy? Spend by agent,
  model and domain, plus the spend that bought nothing because the run failed.
* **Adoption** — who uses this, how widely, and are they coming back?

The run journal is the only input. Where the journal cannot answer a question
honestly, the payload says so rather than guessing — see ``identity_basis``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from app.domain.run import Run, RunStatus
from app.services.catalog_service import CatalogService
from app.services.model_registry import list_models

# Statuses that consumed model tokens but produced nothing durable. Blocked runs
# are excluded on purpose: a guardrail refusing before execution is the system
# working, and it costs nothing.
_WASTED_STATUSES = {RunStatus.FAILED, RunStatus.REJECTED}

# A run is "near the cap" once it has spent this share of its ceiling. Runs that
# cross it are the ones whose cap is about to start truncating real work.
_NEAR_CAP_RATIO = 0.8


def _parse(iso: str) -> datetime | None:
    if not iso:
        return None
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _percentile(values: list[int], pct: float) -> int | None:
    """Nearest-rank percentile.

    Nearest-rank rather than interpolated: these are observed durations, and an
    interpolated p95 is a number no run ever took.
    """
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, min(len(ordered), int(round(pct / 100 * len(ordered) + 0.5))))
    return ordered[rank - 1]


def _ratio(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0


@dataclass
class _Bucket:
    """Accumulator shared by the per-agent, per-model and per-user rollups."""

    runs: int = 0
    succeeded: int = 0
    awaiting: int = 0
    blocked: int = 0
    failed: int = 0
    partial: int = 0
    rejected: int = 0
    artifacts: int = 0
    objects: int = 0
    cost_usd: float = 0.0
    modelled_cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    durations: list[int] = field(default_factory=list)
    actors: set[str] = field(default_factory=set)
    models: set[str] = field(default_factory=set)
    agents: set[str] = field(default_factory=set)
    simulated: int = 0
    live: int = 0
    never_executed: int = 0
    """Blocked before a provider was ever called — neither live nor simulated."""

    first_at: str = ""
    last_at: str = ""

    def add(self, run: Run) -> None:
        self.runs += 1
        status = run.status
        if status is RunStatus.SUCCEEDED:
            self.succeeded += 1
        elif status is RunStatus.AWAITING_APPROVAL:
            self.awaiting += 1
        elif status is RunStatus.BLOCKED:
            self.blocked += 1
        elif status is RunStatus.FAILED:
            self.failed += 1
        elif status is RunStatus.PARTIAL:
            self.partial += 1
        elif status is RunStatus.REJECTED:
            self.rejected += 1

        self.artifacts += len(run.artifacts)
        self.objects += len(run.request.datasets)
        self.cost_usd += run.usage.cost_usd
        self.modelled_cost_usd += run.estimated_cost_usd
        self.input_tokens += run.usage.input_tokens
        self.output_tokens += run.usage.output_tokens
        self.cache_read_tokens += run.usage.cache_read_tokens
        if run.duration_ms is not None:
            self.durations.append(run.duration_ms)
        self.actors.add(run.requested_by)
        self.models.add(run.model_id)
        self.agents.add(run.agent_id)
        if run.provider == "simulation":
            self.simulated += 1
        elif run.provider:
            self.live += 1
        else:
            self.never_executed += 1
        if run.created_at:
            if not self.first_at or run.created_at < self.first_at:
                self.first_at = run.created_at
            if run.created_at > self.last_at:
                self.last_at = run.created_at

    @property
    def completed(self) -> int:
        """Runs that got as far as producing something a human can act on."""
        return self.succeeded + self.awaiting + self.partial

    def as_dict(self) -> dict[str, Any]:
        return {
            "runs": self.runs,
            "succeeded": self.succeeded,
            "awaiting_approval": self.awaiting,
            "blocked": self.blocked,
            "failed": self.failed,
            "partial": self.partial,
            "rejected": self.rejected,
            "completion_rate": _ratio(self.completed, self.runs),
            "block_rate": _ratio(self.blocked, self.runs),
            "artifacts": self.artifacts,
            "objects": self.objects,
            "cost_usd": round(self.cost_usd, 6),
            "modelled_cost_usd": round(self.modelled_cost_usd, 6),
            "cost_per_run_usd": round(self.cost_usd / self.runs, 6) if self.runs else 0.0,
            "cost_per_artifact_usd": (
                round(self.cost_usd / self.artifacts, 6) if self.artifacts else 0.0
            ),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "p50_duration_ms": _percentile(self.durations, 50),
            "p95_duration_ms": _percentile(self.durations, 95),
            "distinct_users": len(self.actors),
            "distinct_models": len(self.models),
            "simulated_runs": self.simulated,
            "live_runs": self.live,
            "never_executed_runs": self.never_executed,
            "first_run_at": self.first_at,
            "last_run_at": self.last_at,
        }


class ObservabilityService:
    def __init__(self, catalog: CatalogService) -> None:
        self.catalog = catalog

    # ------------------------------------------------------------------ #
    # Entry point
    # ------------------------------------------------------------------ #

    def snapshot(self, runs: Iterable[Run], *, window_days: int = 30) -> dict[str, Any]:
        all_runs = list(runs)
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        windowed = [r for r in all_runs if (_parse(r.created_at) or cutoff) >= cutoff]

        return {
            "window_days": window_days,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "totals": self._totals(all_runs, windowed),
            "portfolio": self._portfolio(all_runs),
            "agents": self._per_agent(all_runs),
            "usage": self._usage(all_runs, windowed, window_days),
            "finops": self._finops(all_runs, windowed, window_days),
            "adoption": self._adoption(all_runs, windowed, window_days),
            "identity_basis": (
                "Operator labels are self-declared: the product has no authentication, "
                "so adoption figures count stated identities, not verified ones."
            ),
        }

    # ------------------------------------------------------------------ #
    # Totals
    # ------------------------------------------------------------------ #

    def _totals(self, all_runs: list[Run], windowed: list[Run]) -> dict[str, Any]:
        overall = _Bucket()
        for run in all_runs:
            overall.add(run)
        recent = _Bucket()
        for run in windowed:
            recent.add(run)

        agents = self.catalog.list_agents()
        exercised = {r.agent_id for r in all_runs}
        return {
            "runs": overall.runs,
            "runs_in_window": recent.runs,
            "artifacts": overall.artifacts,
            "objects_processed": overall.objects,
            "spend_usd": round(overall.cost_usd, 6),
            "spend_in_window_usd": round(recent.cost_usd, 6),
            "modelled_spend_usd": round(overall.modelled_cost_usd, 6),
            "total_tokens": overall.input_tokens + overall.output_tokens,
            "fleet_size": len(agents),
            "agents_exercised": len(exercised),
            "fleet_coverage": _ratio(len(exercised), len(agents)),
            "distinct_users": len(overall.actors),
            "awaiting_approval": overall.awaiting,
            "live_runs": overall.live,
            "simulated_runs": overall.simulated,
            "never_executed_runs": overall.never_executed,
            # Share of runs that reached a provider and were answered offline.
            # Blocked runs are excluded from the denominator: they never asked a
            # model anything, so counting them would understate the mix.
            "simulated_share": _ratio(overall.simulated, overall.simulated + overall.live),
        }

    # ------------------------------------------------------------------ #
    # Portfolio — coverage of the fleet, not volume through it
    # ------------------------------------------------------------------ #

    def _portfolio(self, runs: list[Run]) -> dict[str, Any]:
        agents = self.catalog.list_agents()
        by_agent: dict[str, _Bucket] = defaultdict(_Bucket)
        for run in runs:
            by_agent[run.agent_id].add(run)

        domains: dict[str, dict[str, Any]] = {}
        tiers: dict[str, dict[str, Any]] = {}
        for agent in agents:
            bucket = by_agent.get(agent.id)
            for key, table in ((agent.domain, domains), (agent.tier.value, tiers)):
                entry = table.setdefault(
                    key, {"key": key, "agents": 0, "exercised": 0, "runs": 0, "cost_usd": 0.0}
                )
                entry["agents"] += 1
                if bucket:
                    entry["exercised"] += 1
                    entry["runs"] += bucket.runs
                    entry["cost_usd"] = round(entry["cost_usd"] + bucket.cost_usd, 6)

        for table in (domains, tiers):
            for entry in table.values():
                entry["coverage"] = _ratio(entry["exercised"], entry["agents"])

        never_run = [
            {
                "id": a.id,
                "name": a.name,
                "domain": a.domain,
                "tier": a.tier.value,
                "core": a.core_original_scope,
            }
            for a in agents
            if a.id not in by_agent
        ]

        core = [a for a in agents if a.core_original_scope]
        core_exercised = [a for a in core if a.id in by_agent]

        # Concentration: how much of all activity sits on the single busiest
        # agent. High concentration with high coverage is a healthy fleet with a
        # workhorse; high concentration with low coverage is a pilot that never
        # broadened.
        total_runs = sum(b.runs for b in by_agent.values())
        busiest = max(by_agent.items(), key=lambda kv: kv[1].runs, default=None)

        return {
            "fleet_size": len(agents),
            "exercised": len(by_agent),
            "coverage": _ratio(len(by_agent), len(agents)),
            "never_run": never_run,
            "core_agents": len(core),
            "core_exercised": len(core_exercised),
            "core_coverage": _ratio(len(core_exercised), len(core)),
            "by_domain": sorted(domains.values(), key=lambda e: e["key"]),
            "by_tier": sorted(tiers.values(), key=lambda e: e["key"]),
            "top_agent_share": _ratio(busiest[1].runs, total_runs) if busiest else 0.0,
            "top_agent_id": busiest[0] if busiest else "",
        }

    # ------------------------------------------------------------------ #
    # Per-agent usage — the table this tab exists for
    # ------------------------------------------------------------------ #

    def _per_agent(self, runs: list[Run]) -> list[dict[str, Any]]:
        by_agent: dict[str, _Bucket] = defaultdict(_Bucket)
        blocked_by_gate: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        overrides: dict[str, int] = defaultdict(int)

        for run in runs:
            by_agent[run.agent_id].add(run)
            for gate in run.gates:
                if gate.blocking and not gate.passed:
                    blocked_by_gate[run.agent_id][gate.name] += 1
            if run.request.override_dependency_gate:
                overrides[run.agent_id] += 1

        rows: list[dict[str, Any]] = []
        for agent in self.catalog.list_agents():
            bucket = by_agent.get(agent.id, _Bucket())
            gates = blocked_by_gate.get(agent.id, {})
            rows.append(
                {
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "domain": agent.domain,
                    "tier": agent.tier.value,
                    "core": agent.core_original_scope,
                    "requires_approval": agent.requires_approval,
                    "overrides": overrides.get(agent.id, 0),
                    "blocked_by_gate": dict(sorted(gates.items(), key=lambda kv: -kv[1])),
                    **bucket.as_dict(),
                }
            )
        rows.sort(key=lambda r: (-r["runs"], r["agent_id"]))
        return rows

    # ------------------------------------------------------------------ #
    # Usage — what the fleet does, and where it stops
    # ------------------------------------------------------------------ #

    def _usage(self, all_runs: list[Run], windowed: list[Run], days: int) -> dict[str, Any]:
        status_mix: dict[str, int] = defaultdict(int)
        durations: list[int] = []
        gate_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"evaluated": 0, "blocked": 0})
        overrides: list[dict[str, str]] = []
        handoffs = 0

        for run in all_runs:
            status_mix[run.status.value] += 1
            if run.duration_ms is not None:
                durations.append(run.duration_ms)
            for gate in run.gates:
                stat = gate_stats[gate.name]
                stat["evaluated"] += 1
                if gate.blocking and not gate.passed:
                    stat["blocked"] += 1
            handoffs += len(run.handoffs)
            if run.request.override_dependency_gate:
                overrides.append(
                    {
                        "run_id": run.id,
                        "agent_id": run.agent_id,
                        "agent_name": run.agent_name,
                        "actor": run.requested_by,
                        "reason": run.request.override_reason or "(no reason recorded)",
                        "at": run.created_at,
                    }
                )

        gates = [
            {
                "name": name,
                "evaluated": stat["evaluated"],
                "blocked": stat["blocked"],
                "block_rate": _ratio(stat["blocked"], stat["evaluated"]),
            }
            for name, stat in sorted(gate_stats.items(), key=lambda kv: -kv[1]["blocked"])
        ]

        pending = [
            {
                "run_id": r.id,
                "agent_id": r.agent_id,
                "agent_name": r.agent_name,
                "actor": r.requested_by,
                "created_at": r.created_at,
                "age_hours": self._age_hours(r.created_at),
                "artifacts": len(r.artifacts),
            }
            for r in all_runs
            if r.status is RunStatus.AWAITING_APPROVAL
        ]
        pending.sort(key=lambda p: p["age_hours"] or 0, reverse=True)

        approvals = [r for r in all_runs if r.approved_at]
        approval_lag = [
            lag
            for lag in (self._lag_hours(r.created_at, r.approved_at) for r in approvals)
            if lag is not None
        ]

        return {
            "status_mix": dict(sorted(status_mix.items(), key=lambda kv: -kv[1])),
            "p50_duration_ms": _percentile(durations, 50),
            "p95_duration_ms": _percentile(durations, 95),
            "max_duration_ms": max(durations) if durations else None,
            "gates": gates,
            "overrides": sorted(overrides, key=lambda o: o["at"], reverse=True)[:20],
            "override_count": len(overrides),
            "handoffs_recorded": handoffs,
            "pending_approvals": pending[:20],
            "pending_count": len(pending),
            "approvals_granted": len(approvals),
            "median_approval_lag_hours": (
                round(sorted(approval_lag)[len(approval_lag) // 2], 2) if approval_lag else None
            ),
            "daily": self._daily(windowed, days, value="runs"),
        }

    # ------------------------------------------------------------------ #
    # FinOps
    # ------------------------------------------------------------------ #

    def _finops(self, all_runs: list[Run], windowed: list[Run], days: int) -> dict[str, Any]:
        by_model: dict[str, _Bucket] = defaultdict(_Bucket)
        by_domain: dict[str, _Bucket] = defaultdict(_Bucket)
        by_agent: dict[str, _Bucket] = defaultdict(_Bucket)
        wasted = 0.0
        near_cap: list[dict[str, Any]] = []
        capped = 0

        for run in all_runs:
            by_model[run.model_id].add(run)
            by_domain[run.agent_domain].add(run)
            by_agent[run.agent_id].add(run)
            if run.status in _WASTED_STATUSES:
                wasted += run.usage.cost_usd
            if run.status is RunStatus.PARTIAL:
                capped += 1
            cap = run.request.cost_cap_usd
            if cap and run.usage.cost_usd >= cap * _NEAR_CAP_RATIO:
                near_cap.append(
                    {
                        "run_id": run.id,
                        "agent_id": run.agent_id,
                        "agent_name": run.agent_name,
                        "cost_usd": round(run.usage.cost_usd, 6),
                        "cap_usd": cap,
                        "utilisation": _ratio(int(run.usage.cost_usd * 1e6), int(cap * 1e6)),
                    }
                )

        catalog = {m.id: m for m in list_models()}
        models = []
        for model_id, bucket in sorted(by_model.items(), key=lambda kv: -kv[1].cost_usd):
            descriptor = catalog.get(model_id)
            models.append(
                {
                    "model_id": model_id,
                    "display_name": descriptor.display_name if descriptor else model_id,
                    "model_tier": descriptor.tier.value if descriptor else "unknown",
                    "input_usd_per_mtok": descriptor.input_usd_per_mtok if descriptor else None,
                    "output_usd_per_mtok": descriptor.output_usd_per_mtok if descriptor else None,
                    **bucket.as_dict(),
                }
            )

        total = sum(b.cost_usd for b in by_model.values())
        modelled = sum(b.modelled_cost_usd for b in by_model.values())
        window_total = sum(r.usage.cost_usd for r in windowed)
        agents = {a.id: a for a in self.catalog.list_agents()}

        return {
            "spend_usd": round(total, 6),
            "spend_in_window_usd": round(window_total, 6),
            # What these runs would have cost at list price on the models
            # they selected. Always shown as modelled, never as billed.
            "modelled_spend_usd": round(modelled, 6),
            "wasted_usd": round(wasted, 6),
            "wasted_share": _ratio(int(wasted * 1e6), int(total * 1e6)) if total else 0.0,
            "by_model": models,
            "by_domain": [
                {"key": domain, **bucket.as_dict()}
                for domain, bucket in sorted(by_domain.items(), key=lambda kv: -kv[1].cost_usd)
            ],
            "top_agents": [
                {
                    "agent_id": agent_id,
                    "agent_name": agents[agent_id].name if agent_id in agents else agent_id,
                    "domain": agents[agent_id].domain if agent_id in agents else "",
                    **bucket.as_dict(),
                }
                for agent_id, bucket in sorted(by_agent.items(), key=lambda kv: -kv[1].cost_usd)[:10]
            ],
            "capped_runs": capped,
            "near_cap": sorted(near_cap, key=lambda n: -n["utilisation"])[:10],
            "daily": self._daily(windowed, days, value="cost"),
            "daily_modelled": self._daily(windowed, days, value="modelled_cost"),
            "projection": self._projection(windowed, days),
        }

    def _projection(self, windowed: list[Run], days: int) -> dict[str, Any]:
        """A 30-day run-rate, labelled as the straight-line extrapolation it is."""
        spend = sum(r.usage.cost_usd for r in windowed)
        if not windowed or days <= 0:
            return {"daily_usd": 0.0, "monthly_usd": 0.0, "basis": "no runs in the window"}
        daily = spend / days
        return {
            "daily_usd": round(daily, 6),
            "monthly_usd": round(daily * 30, 6),
            "basis": f"straight-line from {len(windowed)} run(s) over {days} days",
        }

    # ------------------------------------------------------------------ #
    # Adoption
    # ------------------------------------------------------------------ #

    def _adoption(self, all_runs: list[Run], windowed: list[Run], days: int) -> dict[str, Any]:
        by_user: dict[str, _Bucket] = defaultdict(_Bucket)
        approvals: dict[str, int] = defaultdict(int)
        for run in all_runs:
            by_user[run.requested_by].add(run)
            if run.approved_by:
                approvals[run.approved_by] += 1

        fleet_size = len(self.catalog.list_agents())
        recent_actors = {r.requested_by for r in windowed}
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        users = []
        for actor, bucket in sorted(by_user.items(), key=lambda kv: -kv[1].runs):
            first = _parse(bucket.first_at)
            users.append(
                {
                    "actor": actor,
                    "agents_used": len(bucket.agents),
                    "fleet_breadth": _ratio(len(bucket.agents), fleet_size),
                    "approvals_given": approvals.get(actor, 0),
                    "active_in_window": actor in recent_actors,
                    "new_in_window": bool(first and first >= cutoff),
                    **bucket.as_dict(),
                }
            )

        # A single run is a trial; coming back for a second is adoption.
        returning = [u for u in users if u["runs"] > 1]

        return {
            "total_users": len(users),
            "active_in_window": len(recent_actors),
            "new_in_window": sum(1 for u in users if u["new_in_window"]),
            "returning_users": len(returning),
            "returning_rate": _ratio(len(returning), len(users)),
            "median_fleet_breadth": (
                round(sorted(u["fleet_breadth"] for u in users)[len(users) // 2], 4)
                if users
                else 0.0
            ),
            "users": users,
            "daily_active": self._daily(windowed, days, value="actors"),
        }

    # ------------------------------------------------------------------ #
    # Shared helpers
    # ------------------------------------------------------------------ #

    def _daily(self, runs: list[Run], days: int, *, value: str) -> list[dict[str, Any]]:
        """A dense daily series — every day in the window, including empty ones.

        Dense on purpose: a sparse series drawn as a bar chart silently closes
        the gaps and makes intermittent use look continuous.
        """
        today = datetime.now(timezone.utc).date()
        span = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
        runs_by_day: dict[str, list[Run]] = defaultdict(list)
        for run in runs:
            moment = _parse(run.created_at)
            if moment:
                runs_by_day[moment.date().isoformat()].append(run)

        series = []
        for day in span:
            key = day.isoformat()
            bucket = runs_by_day.get(key, [])
            if value == "cost":
                amount: float = round(sum(r.usage.cost_usd for r in bucket), 6)
            elif value == "modelled_cost":
                amount = round(sum(r.estimated_cost_usd for r in bucket), 6)
            elif value == "actors":
                amount = len({r.requested_by for r in bucket})
            else:
                amount = len(bucket)
            series.append({"date": key, "value": amount, "runs": len(bucket)})
        return series

    @staticmethod
    def _age_hours(created_at: str) -> float | None:
        moment = _parse(created_at)
        if not moment:
            return None
        return round((datetime.now(timezone.utc) - moment).total_seconds() / 3600, 2)

    @staticmethod
    def _lag_hours(start: str, end: str | None) -> float | None:
        first, second = _parse(start), _parse(end or "")
        if not first or not second:
            return None
        return round((second - first).total_seconds() / 3600, 4)
