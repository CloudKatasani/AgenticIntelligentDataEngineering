"""Fleet observability and FinOps.

These tests pin the arithmetic that a client will read off a dashboard and make
budget decisions with. The interesting cases are the ones where a plausible
implementation would quietly lie: counting blocked runs as model activity,
counting an unapproved proposal as a completed run, or letting a dense chart
close its own gaps.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.connection import DatasetRef
from app.domain.model import ModelSelection, TokenUsage
from app.domain.run import GateResult, Run, RunRequest, RunStatus
from app.services.catalog_service import CatalogService
from app.services.observability_service import ObservabilityService


def _iso(days_ago: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _run(
    *,
    agent_id: str = "01",
    agent_name: str = "Source Profiling Agent",
    domain: str = "discovery",
    status: RunStatus = RunStatus.SUCCEEDED,
    actor: str = "dana@acme.com",
    model_id: str = "claude-haiku-4-5",
    cost: float = 0.0,
    modelled: float = 0.0,
    provider: str = "simulation",
    artifacts: int = 0,
    duration_ms: int | None = 100,
    days_ago: float = 0,
    gates: list[GateResult] | None = None,
    approved_by: str | None = None,
    cap: float | None = None,
    override: bool = False,
    datasets: int = 1,
) -> Run:
    from app.domain.run import Artifact

    return Run(
        id=f"run_{agent_id}_{actor}_{days_ago}_{status.value}_{cost}",
        agent_id=agent_id,
        agent_name=agent_name,
        agent_domain=domain,
        status=status,
        request=RunRequest(
            agent_id=agent_id,
            model=ModelSelection(model_id=model_id),
            actor=actor,
            cost_cap_usd=cap,
            override_dependency_gate=override,
            override_reason="upstream ran last quarter" if override else "",
            datasets=[
                DatasetRef(connection_id="c", database="D", schema_name="S", table=f"T{i}")
                for i in range(datasets)
            ],
        ),
        model_id=model_id,
        effort="high",
        requested_by=actor,
        provider=provider,
        created_at=_iso(days_ago),
        duration_ms=duration_ms,
        usage=TokenUsage(input_tokens=100, output_tokens=50, cost_usd=cost),
        estimated_cost_usd=modelled,
        gates=gates or [],
        approved_by=approved_by,
        approved_at=_iso(days_ago) if approved_by else None,
        artifacts=[
            Artifact(
                id=f"a{i}",
                run_id="r",
                agent_id=agent_id,
                key=f"k{i}",
                filename=f"f{i}.json",
                title="t",
                description="d",
                format="json",
                source="model",
            )
            for i in range(artifacts)
        ],
    )


@pytest.fixture
def service(catalog: CatalogService) -> ObservabilityService:
    return ObservabilityService(catalog)


# ---------------------------------------------------------------------- #
# Empty estate
# ---------------------------------------------------------------------- #


def test_no_runs_reports_zero_rather_than_failing(service: ObservabilityService) -> None:
    snap = service.snapshot([])
    assert snap["totals"]["runs"] == 0
    assert snap["totals"]["fleet_coverage"] == 0.0
    assert snap["portfolio"]["exercised"] == 0
    assert snap["adoption"]["total_users"] == 0


def test_every_agent_appears_even_before_it_is_used(service: ObservabilityService) -> None:
    """The per-agent table is the fleet, not the subset that happens to have run."""
    snap = service.snapshot([])
    assert len(snap["agents"]) == 35
    assert all(row["runs"] == 0 for row in snap["agents"])


# ---------------------------------------------------------------------- #
# Portfolio
# ---------------------------------------------------------------------- #


def test_coverage_counts_distinct_agents_not_runs(service: ObservabilityService) -> None:
    """Fifty runs of one agent is 1/35 coverage, not high adoption."""
    snap = service.snapshot([_run() for _ in range(50)])
    assert snap["totals"]["runs"] == 50
    assert snap["portfolio"]["exercised"] == 1
    assert snap["portfolio"]["coverage"] == round(1 / 35, 4)
    assert snap["portfolio"]["top_agent_share"] == 1.0


def test_never_run_lists_the_untouched_agents(service: ObservabilityService) -> None:
    snap = service.snapshot([_run(agent_id="01")])
    never = snap["portfolio"]["never_run"]
    assert len(never) == 34
    assert "01" not in {a["id"] for a in never}


def test_domain_coverage_is_per_domain(service: ObservabilityService) -> None:
    snap = service.snapshot([_run(agent_id="01", domain="discovery")])
    discovery = next(e for e in snap["portfolio"]["by_domain"] if e["key"] == "discovery")
    assert discovery["exercised"] == 1
    assert discovery["agents"] == 6
    assert discovery["runs"] == 1


# ---------------------------------------------------------------------- #
# Usage
# ---------------------------------------------------------------------- #


def test_awaiting_approval_is_not_counted_as_succeeded(service: ObservabilityService) -> None:
    """A proposal is not a completed piece of work — but it is not a failure either."""
    snap = service.snapshot(
        [
            _run(status=RunStatus.SUCCEEDED),
            _run(status=RunStatus.AWAITING_APPROVAL, days_ago=1),
        ]
    )
    row = next(r for r in snap["agents"] if r["agent_id"] == "01")
    assert row["succeeded"] == 1
    assert row["awaiting_approval"] == 1
    assert row["completion_rate"] == 1.0


def test_gate_block_rates_are_per_gate(service: ObservabilityService) -> None:
    gates_blocked = [
        GateResult(name="hard_dependencies", passed=False, detail="needs 08", blocking=True),
        GateResult(name="cost_cap", passed=True, detail="ok", blocking=True),
    ]
    gates_clean = [
        GateResult(name="hard_dependencies", passed=True, detail="ok", blocking=True),
        GateResult(name="cost_cap", passed=True, detail="ok", blocking=True),
    ]
    snap = service.snapshot(
        [
            _run(status=RunStatus.BLOCKED, gates=gates_blocked, provider=""),
            _run(gates=gates_clean, days_ago=1),
        ]
    )
    gates = {g["name"]: g for g in snap["usage"]["gates"]}
    assert gates["hard_dependencies"]["blocked"] == 1
    assert gates["hard_dependencies"]["evaluated"] == 2
    assert gates["hard_dependencies"]["block_rate"] == 0.5
    assert gates["cost_cap"]["block_rate"] == 0.0


def test_non_blocking_gate_failure_is_not_a_block(service: ObservabilityService) -> None:
    """The autonomy-tier gate reports the tier; it does not stop the run."""
    snap = service.snapshot(
        [
            _run(
                gates=[
                    GateResult(name="autonomy_tier", passed=False, detail="L1", blocking=False)
                ]
            )
        ]
    )
    assert next(g for g in snap["usage"]["gates"] if g["name"] == "autonomy_tier")["blocked"] == 0


def test_overrides_carry_their_reason(service: ObservabilityService) -> None:
    snap = service.snapshot([_run(override=True)])
    assert snap["usage"]["override_count"] == 1
    assert snap["usage"]["overrides"][0]["reason"] == "upstream ran last quarter"


def test_pending_queue_is_ordered_oldest_first(service: ObservabilityService) -> None:
    snap = service.snapshot(
        [
            _run(status=RunStatus.AWAITING_APPROVAL, agent_id="02", days_ago=0.1),
            _run(status=RunStatus.AWAITING_APPROVAL, agent_id="05", days_ago=3),
        ]
    )
    pending = snap["usage"]["pending_approvals"]
    assert snap["usage"]["pending_count"] == 2
    assert pending[0]["agent_id"] == "05"
    assert pending[0]["age_hours"] > pending[1]["age_hours"]


def test_duration_percentiles_are_observed_values(service: ObservabilityService) -> None:
    """Nearest-rank, so a p95 is always a duration some run actually took."""
    runs = [_run(duration_ms=ms, days_ago=i / 10) for i, ms in enumerate([10, 20, 30, 40, 100])]
    snap = service.snapshot(runs)
    assert snap["usage"]["p50_duration_ms"] in {10, 20, 30, 40, 100}
    assert snap["usage"]["p95_duration_ms"] == 100
    assert snap["usage"]["max_duration_ms"] == 100


# ---------------------------------------------------------------------- #
# FinOps
# ---------------------------------------------------------------------- #


def test_spend_splits_by_model_and_domain(service: ObservabilityService) -> None:
    snap = service.snapshot(
        [
            _run(model_id="claude-opus-5", cost=1.0, provider="anthropic"),
            _run(model_id="claude-haiku-4-5", cost=0.25, provider="anthropic", days_ago=1),
        ]
    )
    finops = snap["finops"]
    assert finops["spend_usd"] == 1.25
    assert finops["by_model"][0]["model_id"] == "claude-opus-5"
    assert finops["by_model"][0]["cost_usd"] == 1.0
    assert finops["by_domain"][0]["cost_usd"] == 1.25


def test_blocked_runs_are_not_counted_as_wasted_spend(service: ObservabilityService) -> None:
    """A guardrail refusing before execution is the system working, and it is free."""
    snap = service.snapshot(
        [
            _run(status=RunStatus.BLOCKED, cost=0.0, provider=""),
            _run(status=RunStatus.FAILED, cost=0.5, provider="anthropic", days_ago=1),
            _run(status=RunStatus.SUCCEEDED, cost=0.5, provider="anthropic", days_ago=2),
        ]
    )
    assert snap["finops"]["wasted_usd"] == 0.5
    assert snap["finops"]["wasted_share"] == 0.5


def test_modelled_cost_is_reported_separately_from_billed(
    service: ObservabilityService,
) -> None:
    """An offline run bills nothing but still answers "what would this cost"."""
    snap = service.snapshot([_run(cost=0.0, modelled=0.42, provider="simulation")])
    assert snap["finops"]["spend_usd"] == 0.0
    assert snap["finops"]["modelled_spend_usd"] == 0.42
    assert snap["totals"]["modelled_spend_usd"] == 0.42


def test_near_cap_runs_are_surfaced(service: ObservabilityService) -> None:
    snap = service.snapshot(
        [
            _run(cost=4.5, cap=5.0, provider="anthropic"),
            _run(cost=0.1, cap=5.0, provider="anthropic", days_ago=1),
        ]
    )
    near = snap["finops"]["near_cap"]
    assert len(near) == 1
    assert near[0]["utilisation"] == 0.9


def test_projection_is_labelled_as_an_extrapolation(service: ObservabilityService) -> None:
    snap = service.snapshot([_run(cost=3.0, provider="anthropic")], window_days=30)
    projection = snap["finops"]["projection"]
    assert projection["monthly_usd"] == 3.0
    assert "straight-line" in projection["basis"]


# ---------------------------------------------------------------------- #
# Provider mix
# ---------------------------------------------------------------------- #


def test_blocked_runs_count_as_neither_live_nor_simulated(
    service: ObservabilityService,
) -> None:
    """They never reached a provider, so counting them either way misstates the mix."""
    snap = service.snapshot(
        [
            _run(provider="", status=RunStatus.BLOCKED),
            _run(provider="simulation", days_ago=1),
            _run(provider="anthropic", days_ago=2),
        ]
    )
    totals = snap["totals"]
    assert totals["never_executed_runs"] == 1
    assert totals["simulated_runs"] == 1
    assert totals["live_runs"] == 1
    assert totals["simulated_share"] == 0.5


# ---------------------------------------------------------------------- #
# Adoption
# ---------------------------------------------------------------------- #


def test_adoption_counts_operators_and_their_breadth(service: ObservabilityService) -> None:
    snap = service.snapshot(
        [
            _run(actor="dana@acme.com", agent_id="01"),
            _run(actor="dana@acme.com", agent_id="02", days_ago=1),
            _run(actor="raj@acme.com", agent_id="01", days_ago=2),
        ]
    )
    adoption = snap["adoption"]
    assert adoption["total_users"] == 2
    users = {u["actor"]: u for u in adoption["users"]}
    assert users["dana@acme.com"]["agents_used"] == 2
    assert users["dana@acme.com"]["fleet_breadth"] == round(2 / 35, 4)
    assert users["raj@acme.com"]["agents_used"] == 1


def test_a_single_run_is_a_trial_not_adoption(service: ObservabilityService) -> None:
    snap = service.snapshot(
        [
            _run(actor="dana@acme.com"),
            _run(actor="dana@acme.com", days_ago=1),
            _run(actor="one-off@acme.com", days_ago=2),
        ]
    )
    assert snap["adoption"]["returning_users"] == 1
    assert snap["adoption"]["returning_rate"] == 0.5


def test_approvals_are_attributed_to_the_approver_not_the_requester(
    service: ObservabilityService,
) -> None:
    snap = service.snapshot([_run(actor="dana@acme.com", approved_by="priya@acme.com")])
    users = {u["actor"]: u for u in snap["adoption"]["users"]}
    assert users["dana@acme.com"]["runs"] == 1
    assert users["dana@acme.com"]["approvals_given"] == 0
    assert snap["usage"]["approvals_granted"] == 1


# ---------------------------------------------------------------------- #
# Windowing and series
# ---------------------------------------------------------------------- #


def test_window_excludes_older_runs_from_window_figures_only(
    service: ObservabilityService,
) -> None:
    """Lifetime totals keep everything; the window narrows the recent view."""
    snap = service.snapshot(
        [_run(days_ago=1, cost=1.0, provider="anthropic"), _run(days_ago=60, cost=9.0, provider="anthropic")],
        window_days=7,
    )
    assert snap["totals"]["runs"] == 2
    assert snap["totals"]["runs_in_window"] == 1
    assert snap["totals"]["spend_usd"] == 10.0
    assert snap["totals"]["spend_in_window_usd"] == 1.0


def test_daily_series_is_dense(service: ObservabilityService) -> None:
    """Every day in the window appears, so a bar chart cannot close its own gaps."""
    snap = service.snapshot([_run(days_ago=3)], window_days=7)
    series = snap["usage"]["daily"]
    assert len(series) == 7
    assert sum(point["runs"] for point in series) == 1
    assert sum(1 for point in series if point["value"] == 0) == 6
    assert [point["date"] for point in series] == sorted(point["date"] for point in series)
