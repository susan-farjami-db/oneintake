"""Freight-shaped distributions for the synthetic intake data.

Applied after generate.py builds its rows, with its own seed, so titles, ids, planted pairs,
and the eval sets do not change. What it shapes:

- Seasonality: requests spike in produce season (Apr-Jun) and the Q4 peak (Sep-Nov), when
  truck capacity is tight and operating teams feel the most pain. Those months are also when
  the Task Force has the least time, so manual decisions take longer.
- Business-unit skew: the units closest to loads and capacity (agent operations, capacity and
  carrier relations, brokerage) file the most requests. Finance and capacity requests carry
  the largest value. Safety and claims requests skew urgent.
- Cross-unit duplicates: each planted duplicate comes from a different business unit than the
  work it repeats, which is how double funding happens.
"""

import random
from datetime import timedelta

SHAPE_SEED = 20261115
MONTH_WEIGHT = {1: 0.5, 2: 0.5, 3: 0.7, 4: 1.4, 5: 1.8, 6: 1.6,
                7: 0.7, 8: 0.7, 9: 1.3, 10: 2.0, 11: 1.8, 12: 0.5}
PEAK_MONTHS = {4, 5, 6, 9, 10, 11}
# business unit: (request share weight, value multiplier, urgency weights low/medium/high)
BU_PROFILE = {
    "Agent Operations": (18, 1.1, (2, 5, 3)),
    "Capacity and Carrier Relations": (15, 1.4, (2, 4, 4)),
    "Brokerage": (13, 1.3, (2, 5, 3)),
    "Safety and Compliance": (10, 1.0, (1, 4, 5)),
    "Finance": (10, 1.6, (3, 5, 2)),
    "Technology": (10, 1.0, (3, 5, 2)),
    "Customer Solutions": (9, 0.9, (3, 5, 2)),
    "Claims and Insurance": (8, 0.9, (2, 4, 4)),
    "Human Resources": (4, 0.6, (5, 4, 1)),
    "Marketing": (3, 0.5, (5, 4, 1)),
}
DECIDED = {"approved", "rejected", "merged"}


def _bu(rng, exclude=None):
    names = [b for b in BU_PROFILE if b != exclude]
    return rng.choices(names, weights=[BU_PROFILE[b][0] for b in names])[0]


def _value(rng, base, bu):
    return int(round(base * BU_PROFILE[bu][1] * rng.uniform(0.85, 1.15) / 1000) * 1000)


def _cycle_days(rng, month):
    """Manual Task Force decision time today: weeks, and slower in peak season."""
    days = rng.gammavariate(4.0, 7.0)
    return max(3, int(days * (1.5 if month in PEAK_MONTHS else 1.0)))


def _offset_weights(today):
    return [MONTH_WEIGHT[(today - timedelta(days=d)).month] for d in range(1, 361)]


def shape(requests, projects, planted, today):
    """Reshape dates, units, values, and urgency in place. planted = generate.py tuples."""
    rng = random.Random(SHAPE_SEED)
    urng = random.Random(SHAPE_SEED + 1)  # own stream, so urgency is independent of unit draws
    weights = _offset_weights(today)
    offsets = list(range(1, 361))
    new_ids = {b for _a, _et, _ed, b, _nt, _nd in planted}
    existing_of = {b: a for a, _et, _ed, b, _nt, _nd in planted}
    units = {r["request_id"]: r for r in requests} | {p["project_id"]: p for p in projects}

    for p in projects:
        bu = _bu(rng)
        p["business_unit"], p["est_value_usd"] = bu, _value(rng, p["est_value_usd"], bu)

    for r in requests:
        rid = r["request_id"]
        if rid in new_ids:  # planted new request: a different unit than the work it repeats
            bu = _bu(rng, exclude=units[existing_of[rid]]["business_unit"])
        else:
            bu = _bu(rng)
        r["business_unit"] = bu
        r["est_value_usd"] = _value(rng, float(r["est_value_usd"]), bu)
        r["urgency"] = urng.choices(["low", "medium", "high"], weights=BU_PROFILE[bu][2])[0]
        if rid in new_ids:  # keep planted new requests recent and undecided
            continue
        status = r["status"]
        while True:
            sub = today - timedelta(days=rng.choices(offsets, weights=weights)[0])
            cycle = _cycle_days(rng, sub.month)
            if status not in DECIDED or sub + timedelta(days=cycle) <= today:
                break
        if status in DECIDED:
            upd = sub + timedelta(days=cycle)
        elif status == "in_review":
            upd = min(today, sub + timedelta(days=rng.randint(1, max(1, cycle // 2))))
        else:
            upd = sub
        r["submitted_at"], r["updated_at"] = sub.isoformat(), upd.isoformat()


def summary(requests):
    """Lines for evidence/data_gen.txt that show the shaped distributions."""
    from collections import Counter
    from datetime import datetime
    months = Counter(datetime.fromisoformat(r["submitted_at"]).month for r in requests)
    bus = Counter(r["business_unit"] for r in requests)
    value = Counter()
    for r in requests:
        value[r["business_unit"]] += float(r["est_value_usd"])
    high = Counter(r["business_unit"] for r in requests if r["urgency"] == "high")
    peak = [r for r in requests if datetime.fromisoformat(r["submitted_at"]).month in PEAK_MONTHS]
    out = ["## requests by submission month (peak = Apr-Jun, Sep-Nov)"]
    out += [f"month_{m:02d}={months.get(m, 0)}" for m in range(1, 13)]
    out.append(f"peak_season_share={len(peak) / len(requests):.2f}")
    out.append("## business unit: requests, total est value USD, high urgency share")
    for bu, n in bus.most_common():
        out.append(f"{bu}: requests={n} value={int(value[bu])} high_urgency={high[bu] / n:.2f}")
    return out
