"""Worked examples for all 35 agents, grouped by domain.

One estate, one story: Meridian Retail Group is moving a mainframe customer
master and a legacy warehouse onto Snowflake and publishing a certified
customer-360 product. Every example uses objects that exist in the seeded demo
warehouse and files that exist in the seeded sample workspace, so a client who
asks "can I see that for real?" gets the same run rather than a different one.
"""

from __future__ import annotations

from app.domain.canvas import WorkedExample


def all_examples() -> dict[str, WorkedExample]:
    from app.runtime.canvas import (
        build,
        consumption,
        crosscutting,
        discovery,
        governance,
        operations,
        quality,
    )

    examples: dict[str, WorkedExample] = {}
    for module in (discovery, build, quality, operations, governance, consumption, crosscutting):
        examples.update({e.agent_id: e for e in module.EXAMPLES})
    return examples
