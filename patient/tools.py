"""Patient tools - intentionally flaky (FR-P2).

`get_refund_policy` returns nothing for some regions. Combined with the fragile
prompt (agent.py), the Patient then hallucinates a confident, false policy -
exactly the failure Cassandra is built to catch.
"""

from __future__ import annotations

# Real policy data the Patient is *allowed* to know. Note: EU/DE deliberately absent,
# so a German refund question forces the failure path (used by the seeder, FR-IS1).
_REFUND_POLICY: dict[str, str] = {
    "US": "30-day returns with receipt; refund to original payment method.",
    "UK": "14-day returns under the Consumer Contracts Regulations.",
}

_ORDERS: dict[str, dict] = {
    "A1001": {"status": "shipped", "carrier": "UPS", "eta": "2026-05-20"},  # complete
    # MALFORMED on purpose (FR-P2): these orders exist but the lookup returns null
    # carrier/eta. A well-built agent surfaces "tracking not available yet"; the fragile
    # Patient invents a carrier + delivery date — a tool_failure Cassandra must catch.
    "A1002": {"status": "processing", "carrier": None, "eta": None},
    "A1003": {"status": "shipped", "carrier": None, "eta": None},
}


def get_refund_policy(region: str) -> dict:
    """Return the refund policy for a region.

    Returns {"found": False} for unknown regions instead of raising - this is the
    trap: a well-built agent would refuse; the fragile Patient invents an answer.
    """
    region = (region or "").strip().upper()
    if region in _REFUND_POLICY:
        return {"found": True, "region": region, "policy": _REFUND_POLICY[region]}
    return {"found": False, "region": region, "policy": None}


def lookup_order(order_id: str) -> dict:
    """Look up an order. Occasionally returns malformed data (FR-P2)."""
    order_id = (order_id or "").strip().upper()
    if order_id not in _ORDERS:
        return {"found": False, "order_id": order_id}
    return {"found": True, "order_id": order_id, **_ORDERS[order_id]}


TOOLSPECS = [
    {
        "name": "get_refund_policy",
        "description": "Get the official refund policy for a customer's region.",
        "fn": get_refund_policy,
        "parameters": {"region": "ISO-ish region code, e.g. US, UK, DE, EU"},
    },
    {
        "name": "lookup_order",
        "description": "Look up the status of an order by its ID.",
        "fn": lookup_order,
        "parameters": {"order_id": "Order ID, e.g. A1001"},
    },
]
