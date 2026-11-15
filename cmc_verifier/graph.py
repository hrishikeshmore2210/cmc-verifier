"""Assemble the verification graph (ARCHITECTURE.md §1, §3.1).

Flow:
    START -> ingest -> extract_claims -> ground
          -> [ every check in CHECKS, in parallel ]
          -> critic -> human_review -> END

The fan-out/fan-in is the whole point: `ground` points at every check, and every
check points at `critic`, so `critic` runs once, after all checks complete.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .models import VerificationState
from .nodes.checks import CHECKS
from .nodes.critic import critic
from .nodes.extract_claims import extract_claims
from .nodes.ground import ground
from .nodes.ingest import ingest
from .nodes.review import human_review
from .nodes.safety import isolate


def build_graph(interactive: bool = False):
    """interactive=True compiles with a checkpointer and pauses BEFORE human_review so a
    person can record decisions (see review.py) and then resume with invoke(None, config)."""
    g = StateGraph(VerificationState)

    # spine
    g.add_node("ingest", ingest)
    g.add_node("extract_claims", extract_claims)
    g.add_node("ground", ground)

    # parallel checks
    for name, fn in CHECKS.items():
        g.add_node(name, isolate(name, fn))

    # critic + human-in-the-loop
    g.add_node("critic", critic)
    g.add_node("human_review", human_review)

    # wiring
    g.add_edge(START, "ingest")
    g.add_edge("ingest", "extract_claims")
    g.add_edge("extract_claims", "ground")

    for name in CHECKS:               # fan-out
        g.add_edge("ground", name)
        g.add_edge(name, "critic")    # fan-in (critic joins all branches)

    g.add_edge("critic", "human_review")
    g.add_edge("human_review", END)

    if interactive:
        from langgraph.checkpoint.memory import InMemorySaver
        return g.compile(checkpointer=InMemorySaver(), interrupt_before=["human_review"])
    return g.compile()
