"""Per-agent input contracts, document sources, and deterministic file reading.

The claim under test: the fleet does not share an input shape. Agent 01 reads
tables, agent 06 reads copybooks, agent 22 reads a metering export, agent 33
reads a sentence. These tests pin that each agent is asked for the thing its
own spec says it consumes, and that whatever arrives is counted rather than
described.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.document import DocumentContent, DocumentRef, DocumentSpace, SpaceKind
from app.domain.input_contract import InputBinding, InputKind, InputOrigin
from app.domain.run import RunStatus
from app.runtime.deterministic.artifacts import read_artifact, summarise_for_prompt
from app.runtime.input_contracts import INPUT_CONTRACTS, primary_kind, slots_for
from app.services.run_service import RunService
from tests.support import bindings_for, request_for

AGENT_IDS = [f"{i:02d}" for i in range(1, 36)]


# ---------------------------------------------------------------------- #
# The contract table
# ---------------------------------------------------------------------- #


def test_every_agent_has_a_contract() -> None:
    assert set(INPUT_CONTRACTS) == set(AGENT_IDS)


@pytest.mark.parametrize("agent_id", AGENT_IDS)
def test_every_slot_cites_the_spec_line_it_implements(agent_id: str) -> None:
    """A slot exists because the agent's own spec asked for it.

    Without the citation the table becomes a place to invent requirements, and
    an agent starts asking for things its contract never mentioned.
    """
    for slot in slots_for(agent_id):
        assert slot.spec_reference, f"agent {agent_id} slot {slot.key} cites nothing"
        assert slot.help, f"agent {agent_id} slot {slot.key} has no operator guidance"


def test_the_fleet_is_not_mostly_table_driven() -> None:
    """The finding that motivated all of this.

    Only six of thirty-five agents take database objects as their primary
    input. Presenting a table picker to the other twenty-nine asks them for
    something they cannot use.
    """
    kinds = [primary_kind(agent_id) for agent_id in AGENT_IDS]
    assert kinds.count("database_objects") == 6
    assert kinds.count("code_artifacts") == 4
    assert kinds.count("telemetry_export") == 7
    assert kinds.count("policy_document") == 8
    assert kinds.count("structured_request") == 8
    assert kinds.count("upstream_artifacts") == 2


def test_upstream_fed_agents_declare_no_slots() -> None:
    """09 and 11 receive everything from prior runs."""
    assert slots_for("09") == []
    assert slots_for("11") == []


def test_the_reconciliation_agent_asks_for_two_estates() -> None:
    """Agent 18 is the only agent that reads two sides at once."""
    keys = {slot.key for slot in slots_for("18") if slot.required}
    assert keys == {"source_objects", "target_objects"}


def test_file_slots_accept_every_file_origin() -> None:
    """Where a file lives is not the agent's business.

    Copybooks are copybooks whether they arrive from SharePoint, a Teams
    channel, a mounted share or a laptop.
    """
    slot = next(s for s in slots_for("06") if s.key == "legacy_artifacts")
    assert {o.value for o in slot.origins} == {
        "upload",
        "sharepoint",
        "teams",
        "shared_drive",
        "object_store",
    }


def test_an_unknown_agent_gets_a_permissive_default() -> None:
    """A spec folder added tomorrow is runnable today."""
    slots = slots_for("99")
    assert slots
    assert not any(slot.required for slot in slots)


def test_parameters_do_not_duplicate_slots() -> None:
    """An agent must not ask for the same answer in two boxes."""
    from app.runtime.artifact_plans import parameters_for
    from app.runtime.input_contracts import SUPERSEDED_PARAMETERS

    for agent_id in AGENT_IDS:
        parameter_keys = {p.key for p in parameters_for(agent_id)}
        slot_keys = {s.key for s in slots_for(agent_id)}
        assert not (parameter_keys & slot_keys), f"agent {agent_id} asks twice"
        assert not (parameter_keys & SUPERSEDED_PARAMETERS.get(agent_id, set()))


# ---------------------------------------------------------------------- #
# Deterministic reading
# ---------------------------------------------------------------------- #


def _doc(name: str, text: str) -> DocumentContent:
    return DocumentContent(
        ref=DocumentRef(id=f"s::{name}", space_id="s", name=name, path=name),
        data=text.encode(),
    )


def test_sql_reads_and_writes_are_separated() -> None:
    """That distinction is the lineage edge."""
    facts = read_artifact(
        _doc(
            "load.sql",
            "CREATE TABLE ANALYTICS.FCT AS SELECT * FROM RAW.ORDERS;\n"
            "INSERT INTO AUDIT.LOG SELECT 1;",
        )
    )
    reads = {r["object"] for r in facts.findings["reads"]}
    writes = {w["object"] for w in facts.findings["writes"]}
    assert reads == {"RAW.ORDERS"}
    assert writes == {"ANALYTICS.FCT", "AUDIT.LOG"}


def test_create_table_as_is_a_write_not_a_read() -> None:
    """The most common ETL statement there is; getting it backwards inverts
    every lineage edge it produces."""
    facts = read_artifact(_doc("x.sql", "CREATE OR REPLACE TABLE A.B AS SELECT * FROM C.D;"))
    assert {w["object"] for w in facts.findings["writes"]} == {"A.B"}
    assert {r["object"] for r in facts.findings["reads"]} == {"C.D"}


def test_sql_comments_do_not_become_lineage_edges() -> None:
    """Prose contains the word "from".

    Left unstripped, `-- appended from the mainframe extract` produces a table
    called `the`, presented with the same confidence as a real edge.
    """
    facts = read_artifact(
        _doc(
            "x.sql",
            "-- rows are appended from the mainframe extract\n"
            "/* staged from NOWHERE overnight */\n"
            "SELECT * FROM RAW.ORDERS;",
        )
    )
    objects = {r["object"] for r in facts.findings["reads"]}
    assert objects == {"RAW.ORDERS"}
    assert "the" not in objects
    assert "NOWHERE" not in objects


def test_copybook_fields_are_extracted_with_their_pictures() -> None:
    facts = read_artifact(
        _doc(
            "CUST.cpy",
            "       01  CUST-REC.\n"
            "           05  CUST-NO   PIC 9(08).\n"
            "           05  BAL-AMT   PIC S9(7)V99 COMP-3.\n",
        )
    )
    assert facts.language == "COBOL copybook"
    assert facts.findings["field_count"] == 3
    assert {f["name"] for f in facts.findings["fields"]} == {"CUST-REC", "CUST-NO", "BAL-AMT"}


def test_csv_columns_are_profiled_like_a_table() -> None:
    """A metering export gets the same treatment a database table gets."""
    facts = read_artifact(
        _doc("m.csv", "warehouse,credits\nWH_A,10.5\nWH_B,20.5\nWH_A,4\n")
    )
    columns = {c["column"]: c for c in facts.findings["columns"]}
    assert facts.findings["row_count"] == 3
    assert columns["credits"]["sum"] == 35.0
    assert columns["credits"]["min"] == 4.0
    assert columns["warehouse"]["distinct_count"] == 2


def test_a_mostly_text_column_is_not_summed() -> None:
    """Summing a column that is 40% text produces a number meaning nothing."""
    facts = read_artifact(_doc("m.csv", "code\n1\n2\nN/A\nunknown\n"))
    column = facts.findings["columns"][0]
    assert "sum" not in column
    assert "top_values" in column


def test_empty_cells_are_counted_as_missing() -> None:
    facts = read_artifact(_doc("m.csv", "a,b\n1,\n2,x\n3,\n"))
    columns = {c["column"]: c for c in facts.findings["columns"]}
    assert columns["b"]["null_count"] == 2


def test_malformed_xml_is_reported_rather_than_raised() -> None:
    """Real ETL exports are often not well-formed. One must not sink a run."""
    facts = read_artifact(_doc("job.xml", "<POWERMART><MAPPING></POWERMART>"))
    assert "parse_error" in facts.findings
    assert facts.excerpt


def test_prompt_evidence_frames_file_contents_as_untrusted() -> None:
    """Harvested content is data, never instructions."""
    text = summarise_for_prompt([read_artifact(_doc("x.sql", "SELECT * FROM A.B;"))])
    assert "untrusted" in text.lower()
    assert "do not recompute" in text.lower()


# ---------------------------------------------------------------------- #
# Document providers
# ---------------------------------------------------------------------- #


def test_a_directory_space_lists_and_fetches(tmp_path: Path) -> None:
    from app.adapters.documents.filesystem import DirectoryProvider

    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.sql").write_text("SELECT 1;")
    space = DocumentSpace(id="sp", name="Share", kind=SpaceKind.SHARED_DRIVE, root_path=str(tmp_path))
    provider = DirectoryProvider(space, tmp_path)

    ok, _ = provider.available()
    assert ok
    assert [e.name for e in provider.list()] == ["sub"]
    assert provider.fetch("sp::sub/a.sql").data == b"SELECT 1;"


def test_a_directory_space_refuses_to_escape_its_root(tmp_path: Path) -> None:
    """The path arrives from an HTTP request, so this will be tried."""
    from app.adapters.documents.filesystem import DirectoryProvider
    from app.core.errors import NotFound

    root = tmp_path / "space"
    root.mkdir()
    (tmp_path / "secret.txt").write_text("not yours")
    provider = DirectoryProvider(
        DocumentSpace(id="sp", name="S", kind=SpaceKind.SHARED_DRIVE, root_path=str(root)), root
    )

    with pytest.raises(NotFound):
        provider.fetch("sp::../secret.txt")
    with pytest.raises(NotFound):
        provider.list("../")


def test_an_upload_cannot_choose_its_own_path(tmp_path: Path) -> None:
    """A file named `../../app/main.py` lands as `main.py` like anything else."""
    from app.adapters.documents.filesystem import UploadProvider

    provider = UploadProvider(
        DocumentSpace(id="up", name="Uploads", kind=SpaceKind.UPLOAD), tmp_path / "uploads"
    )
    ref = provider.store("../../app/main.py", b"print()")
    assert ref.name == "main.py"
    assert (tmp_path / "uploads" / "main.py").exists()
    assert not (tmp_path.parent / "app" / "main.py").exists()


def test_uploading_the_same_name_twice_does_not_overwrite(tmp_path: Path) -> None:
    from app.adapters.documents.filesystem import UploadProvider

    provider = UploadProvider(
        DocumentSpace(id="up", name="Uploads", kind=SpaceKind.UPLOAD), tmp_path / "uploads"
    )
    first = provider.store("rules.sql", b"one")
    second = provider.store("rules.sql", b"two")
    assert first.name != second.name
    assert provider.fetch(first.id).data == b"one"


def test_sharepoint_reports_why_it_is_unreachable() -> None:
    """Configured-but-unreachable is a state the UI must be able to show,
    the same way an uninstalled database driver is."""
    from app.adapters.documents.microsoft_graph import SharePointProvider

    provider = SharePointProvider(
        DocumentSpace(id="sp", name="SP", kind=SpaceKind.SHAREPOINT, site_url="https://x/sites/y")
    )
    ok, detail = provider.available()
    assert not ok
    assert "tenant ID" in detail or "requests" in detail


# ---------------------------------------------------------------------- #
# End to end through the run engine
# ---------------------------------------------------------------------- #


def test_a_code_agent_runs_from_files_alone(run_service: RunService) -> None:
    """Agent 04 reads code, not rows: no table is selected anywhere here."""
    run = run_service.execute(request_for("04"))

    assert run.status is RunStatus.SUCCEEDED, run.error
    assert not run.request.datasets
    assert run.findings
    assert any("load_fct_orders.sql" in finding for finding in run.findings)


def test_file_evidence_reaches_the_output(run_service: RunService) -> None:
    """Objects named in the artifact were parsed out of the supplied file."""
    import json

    run = run_service.execute(request_for("04"))
    graph = next(a for a in run.artifacts if a.filename == "lineage-graph.json")
    payload = json.loads(run_service.artifacts.read(graph))

    statements = " ".join(o["statement"] for o in payload["observations"])
    assert "ANALYTICS.FCT_ORDERS" in statements
    assert "RAW.ORDERS" in statements
    assert payload["sources"], "the artifact should record which files it read"


def test_metering_totals_are_counted_not_generated(run_service: RunService) -> None:
    """Agent 22's numbers come from the CSV, exactly as the profiler's do."""
    run = run_service.execute(request_for("22"))
    assert run.status in {RunStatus.SUCCEEDED, RunStatus.AWAITING_APPROVAL}, run.error
    # 6,206.00 is the sum of the cost_usd column in the seeded metering export.
    assert any("6,206" in finding for finding in run.findings), run.findings


def test_an_unreadable_file_does_not_discard_the_readable_ones(
    run_service: RunService,
) -> None:
    """Losing one of twenty artifacts to a permissions problem must not throw
    away the other nineteen — but the run has to say which one was lost."""
    request = request_for("04")
    binding = request.inputs["artifacts"]
    request.inputs["artifacts"] = InputBinding(
        slot_key="artifacts",
        origin=InputOrigin.SHARED_DRIVE,
        file_ids=[*binding.file_ids, "space_samples::does/not/exist.sql"],
    )

    run = run_service.execute(request)
    assert run.status is RunStatus.SUCCEEDED
    assert run.findings
    assert any(e.level == "warn" and "unreadable" in e.message.lower() for e in run.events)


def test_an_inline_agent_needs_no_files_or_tables(run_service: RunService) -> None:
    """Agent 33 takes a sentence and nothing else."""
    run = run_service.execute(request_for("33"))
    assert run.status in {RunStatus.SUCCEEDED, RunStatus.AWAITING_APPROVAL}, run.error
    assert not run.request.datasets


def test_the_gate_names_the_missing_slot(run_service: RunService) -> None:
    request = request_for("19")
    del request.inputs["evidence"]
    run = run_service.execute(request)

    assert run.status is RunStatus.BLOCKED
    assert "Evidence bundle" in (run.error or "")
    # The slot that *was* supplied is acknowledged rather than ignored.
    gate = next(g for g in run.gates if g.name == "input_contract")
    assert "Incident summary" in gate.detail


def test_bindings_cover_every_required_slot_for_every_agent() -> None:
    """A guard on the test helper itself: if a contract gains a required slot
    and the helper cannot fill it, the fleet-wide smoke test would start
    passing for the wrong reason."""
    for agent_id in AGENT_IDS:
        bindings = bindings_for(agent_id)
        for slot in slots_for(agent_id):
            if slot.required:
                assert slot.key in bindings, f"agent {agent_id} slot {slot.key} unfilled"
                assert not bindings[slot.key].is_empty()
