# ADE Agent Specifications

Generated spec + skill files for the **Agentic Data Engineering (ADE)** fleet: 35 agents, each with a
machine-readable `spec.yaml` and an operator-readable `SKILL.md`.

★ = one of the six core agents from the original project scope.

## Design rules enforced across the catalog

1. **Non-overlapping scope by construction.** Every agent's spec carries `non_goals` entries that name
   the agent owning the excluded ground. Boundaries are reciprocal: where two agents share a seam
   (16↔17 rules-vs-baselines, 22↔23 cost-vs-latency, 19↔20 diagnose-vs-act, 06↔14 extract-vs-translate,
   11↔16 CI-tests-vs-production-rules, 02↔26 classify-vs-enforce, 05↔03 bind-vs-describe,
   13↔21 CI-verdict-vs-runtime-drift, 24↔20 plan-vs-execute), each side's spec names the seam explicitly.
2. **Dependencies are typed.** `hard` deps block execution; `soft` deps enhance quality. The hard-dep
   graph is validated acyclic at generation time. The one intentionally bidirectional *workflow* seam
   (16 proposes quality commitments, 13 codifies them) is modeled as 13→hard-dep→16 with the reverse
   direction as data-flow only, so the graph stays a DAG.
3. **Autonomy tiers are structural.** L0 advisory → L4 autonomous-non-mutating. Agents 02, 26, 27 are
   capped at L1 in regulated environments regardless of measured accuracy. Agent 20 is the only agent
   permitted to mutate production data, and only inside a versioned action catalog.
4. **Determinism where possible.** Statistics, diffs, comparisons, and CI verdicts come from
   deterministic tools; LLM reasoning interprets, drafts, and adjudicates — it never computes numbers.
5. **Cross-cutting agents (33–35) have no domain scope.** Supervisor routes, Evaluator measures,
   Reviewer critiques. None of them produces domain artifacts.

## Catalog

| ID | Agent | Domain | Tier | Hard deps | Soft deps |
|---|---|---|---|---|---|
| 01 | [Source Profiling Agent](ade-agent-specs/agents/01-source-profiling/SKILL.md) | discovery | L2 | — | — |
| 02 ★ | [Data Classification Agent](ade-agent-specs/agents/02-data-classification/SKILL.md) | discovery | L1 | 01 | 05 |
| 03 | [Catalog & Documentation Agent](ade-agent-specs/agents/03-catalog-documentation/SKILL.md) | discovery | L2 | 01 | 04, 05 |
| 04 | [Lineage Reconstruction Agent](ade-agent-specs/agents/04-lineage-reconstruction/SKILL.md) | discovery | L2 | — | — |
| 05 | [Glossary & Semantic Alignment Agent](ade-agent-specs/agents/05-glossary-semantic-alignment/SKILL.md) | discovery | L1 | 01 | 03 |
| 06 | [Source System Interrogation Agent](ade-agent-specs/agents/06-source-system-interrogation/SKILL.md) | discovery | L1 | — | — |
| 07 ★ | [SchemaBuilder Agent](ade-agent-specs/agents/07-schema-builder/SKILL.md) | build | L1 | 08, 02 | — |
| 08 ★ | [Data Modeling Agent](ade-agent-specs/agents/08-data-modeling/SKILL.md) | build | L0 | 01, 05 | 06 |
| 09 ★ | [Data Mapping Agent](ade-agent-specs/agents/09-data-mapping/SKILL.md) | build | L1 | 08, 01 | 06, 04 |
| 10 ★ | [Coding Agent](ade-agent-specs/agents/10-coding/SKILL.md) | build | L1 | 09, 07 | 15 |
| 11 | [Test Generation Agent](ade-agent-specs/agents/11-test-generation/SKILL.md) | build | L1 | 09, 01 | 08 |
| 12 | [Semantic Layer Agent](ade-agent-specs/agents/12-semantic-layer/SKILL.md) | build | L1 | 08, 05 | 07 |
| 13 | [Data Contract Agent](ade-agent-specs/agents/13-data-contract/SKILL.md) | build | L1 | 07, 16 | — |
| 14 | [Legacy Modernization Agent](ade-agent-specs/agents/14-legacy-modernization/SKILL.md) | build | L1 | 06 | 09 |
| 15 | [Ingestion Pattern Agent](ade-agent-specs/agents/15-ingestion-pattern/SKILL.md) | build | L1 | 01 | — |
| 16 ★ | [Data Quality Rules Agent](ade-agent-specs/agents/16-data-quality-rules/SKILL.md) | quality | L1 | 01, 02 | 05 |
| 17 | [Anomaly & Freshness Agent](ade-agent-specs/agents/17-anomaly-freshness/SKILL.md) | quality | L4 | — | 13 |
| 18 | [Reconciliation & Parity Agent](ade-agent-specs/agents/18-reconciliation-parity/SKILL.md) | quality | L2 | 09 | 14 |
| 19 | [Root Cause Analysis Agent](ade-agent-specs/agents/19-root-cause-analysis/SKILL.md) | quality | L2 | 04 | — |
| 20 | [Remediation / Self-Healing Agent](ade-agent-specs/agents/20-remediation-self-healing/SKILL.md) | quality | L3 | 19, 24 | 16 |
| 21 | [Schema Drift & Impact Agent](ade-agent-specs/agents/21-schema-drift-impact/SKILL.md) | quality | L2 | 04, 13 | — |
| 22 | [FinOps Agent](ade-agent-specs/agents/22-finops/SKILL.md) | operations | L2 | — | — |
| 23 | [Performance Tuning Agent](ade-agent-specs/agents/23-performance-tuning/SKILL.md) | operations | L2 | — | 22, 04 |
| 24 | [Orchestration & Backfill Agent](ade-agent-specs/agents/24-orchestration-backfill/SKILL.md) | operations | L2 | 04 | 15 |
| 25 | [Capacity & Retention Agent](ade-agent-specs/agents/25-capacity-retention/SKILL.md) | operations | L1 | — | 27, 13, 22 |
| 26 | [Access & Entitlement Agent](ade-agent-specs/agents/26-access-entitlement/SKILL.md) | governance | L1 | 02 | 07 |
| 27 | [Privacy & Retention Agent](ade-agent-specs/agents/27-privacy-retention/SKILL.md) | governance | L1 | 02, 04 | — |
| 28 | [Regulatory Evidence Agent](ade-agent-specs/agents/28-regulatory-evidence/SKILL.md) | governance | L1 | 04 | 16, 26, 13, 18, 20, 27 |
| 29 | [Data Product Publishing Agent](ade-agent-specs/agents/29-data-product-publishing/SKILL.md) | governance | L1 | 13, 16, 03 | 12 |
| 30 | [BI Rationalization Agent](ade-agent-specs/agents/30-bi-rationalization/SKILL.md) | consumption | L1 | 04 | 12 |
| 31 | [Analyst Assist (NL→SQL) Agent](ade-agent-specs/agents/31-analyst-assist-nl-sql/SKILL.md) | consumption | L2 | 12 | 29 |
| 32 | [Request Intake Agent](ade-agent-specs/agents/32-request-intake/SKILL.md) | consumption | L1 | 03 | 29, 12, 31 |
| 33 | [Supervisor / Orchestrator Agent](ade-agent-specs/agents/33-supervisor-orchestrator/SKILL.md) | cross-cutting | L2 | — | — |
| 34 | [Evaluator Agent](ade-agent-specs/agents/34-evaluator/SKILL.md) | cross-cutting | L2 | — | — |
| 35 | [Reviewer Agent](ade-agent-specs/agents/35-reviewer/SKILL.md) | cross-cutting | L1 | — | — |

## Files

```
ade-agent-specs/
├── README.md                  ← catalog index (same content as this file)
├── registry.yaml              ← machine-readable fleet registry
├── dependency-graph.mmd       ← Mermaid DAG (hard deps solid, soft deps dotted)
└── agents/
    └── NN-slug/
        ├── spec.yaml          ← machine-readable contract (scope, non-goals, deps, evals)
        └── SKILL.md           ← operator/agent-readable instructions
```

## How the pieces are meant to be used

- **spec.yaml** is the contract: the Supervisor (33) validates handoffs against `inputs`/`outputs`,
  the Evaluator (34) reads `evaluation` thresholds, CI reads `dependencies` to order work.
- **SKILL.md** is what gets loaded into the agent's context at runtime (Claude skill / Cortex Agent
  instruction / system-prompt module). The Boundaries and Universal-guardrails sections are
  non-negotiable text and should survive any prompt compression.
- Regenerate rather than hand-edit: the catalog source is the single source of truth, and the
  generator validates reference integrity and acyclicity on every run.
