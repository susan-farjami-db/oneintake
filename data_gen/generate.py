"""Seeded synthetic intake data. Usage: python data_gen/generate.py [out_root]"""

import csv
import json
import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from names import (BENEFITS, BUSINESS_UNITS, EMAIL_DOMAIN, FIRST_NAMES, LAST_NAMES,  # noqa: E402
                   PAINS, PATTERNS, SUBJECTS, SYSTEMS)
from seeds import AMBIGUOUS, PLANTED_PAIRS  # noqa: E402

SEED = 20261026
ROOT = Path(__file__).resolve().parent.parent
N_REQUESTS, N_PROJECTS = 300, 60
TODAY = datetime(2026, 10, 20)



def person(rng):
    f, l = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    return f"{f} {l}", f"{f}.{l}@{EMAIL_DOMAIN}".lower()


def value_usd(rng):
    return int(round(rng.lognormvariate(11.8, 0.8) / 1000) * 1000)


def field_value(field, row, rng):
    """Value for a configured form field; unknown fields fall back to their type."""
    name, ftype, opts = field["field_name"], field["type"], field.get("options") or []
    if name in row:
        return row[name]
    if name == "requester_email":
        return person(rng)[1]
    if name == "sponsor":
        return person(rng)[0]
    if name == "est_value_usd":
        return value_usd(rng)
    if name == "expected_benefit":
        return rng.choice(BENEFITS)
    if name == "urgency":
        return rng.choices(opts, weights=[3, 5, 2])[0]
    if ftype == "select":
        return rng.choice(opts)
    if ftype == "multiselect":
        return ";".join(rng.sample(opts, k=min(2, len(opts))))
    if ftype == "number":
        return rng.randint(1, 100)
    if ftype == "email":
        return person(rng)[1]
    return f"{field['label']} details"


def dates(rng, recent=False):
    sub = TODAY - timedelta(days=rng.randint(1, 20) if recent else rng.randint(1, 360))
    upd = min(TODAY, sub + timedelta(days=rng.randint(0, 45)))
    return sub, upd


def main(out_root=ROOT):
    out_root = Path(out_root)
    rng = random.Random(SEED)
    fields = json.loads((ROOT / "config/form_fields.json").read_text())
    combos = [(c, s) for c in PATTERNS for s in SUBJECTS]
    rng.shuffle(combos)

    def concept(cat, subj):
        s, d, systems = subj
        t, desc = rng.choice(PATTERNS[cat])
        title = t.format(s=s)
        desc = f"{desc.format(s=s, d=d)} {rng.choice(PAINS)}"
        return title[0].upper() + title[1:], desc[0].upper() + desc[1:], cat, systems

    requests, projects, labels = [], [], []

    def add_request(title, desc, cat, systems, status, recent=False, bu=None):
        sub, upd = dates(rng, recent)
        if status == "submitted":
            upd = sub
        row = {"request_id": str(uuid.UUID(int=rng.getrandbits(128), version=4)), "title": title,
               "description": desc, "business_unit": bu or rng.choice(BUSINESS_UNITS),
               "problem_statement": desc.split(". ")[0] + ".", "data_sources": ";".join(systems)}
        for f in fields:
            row[f["field_name"]] = field_value(f, row, rng)
        row.update(status=status, submitted_at=sub.isoformat(), updated_at=upd.isoformat())
        requests.append(row)
        labels.append((row, cat))
        return row

    def add_project(name, desc, cat, systems, status):
        owner, email = person(rng)
        start = TODAY - timedelta(days=rng.randint(30, 500))
        p = {"project_id": f"PRJ-{len(projects) + 1:04d}", "name": name, "description": desc,
             "business_unit": rng.choice(BUSINESS_UNITS), "owner": owner, "owner_email": email,
             "status": status, "category": cat, "est_value_usd": value_usd(rng),
             "start_date": start.date().isoformat(), "systems": systems}
        projects.append(p)
        return p

    planted, ambiguous_ids = [], []
    for cat, kind, et, ed, nt, nd in PLANTED_PAIRS:
        sys_ = rng.sample(SYSTEMS, 2)
        if kind == "project":
            st = "in_progress" if et == "Agent ETA assistant" else rng.choice(["in_progress", "planned", "completed"])
            a = add_project(et, ed, cat, sys_, st)["project_id"]
        else:
            a = add_request(et, ed, cat, sys_, rng.choice(["in_review", "approved"]))["request_id"]
        b = add_request(nt, nd, cat, sys_, "submitted", recent=True)["request_id"]
        planted.append((a, et, ed, b, nt, nd))
    for t, d, cat, _sec in AMBIGUOUS:
        ambiguous_ids.append(add_request(t, d, cat, rng.sample(SYSTEMS, 2),
                                         rng.choice(["submitted", "in_review"]))["request_id"])
    statuses = ["submitted"] * 3 + ["in_review"] * 3 + ["approved"] * 3 + ["rejected", "merged"]
    pstatuses = ["in_progress", "planned", "completed", "on_hold"]
    while len(projects) < N_PROJECTS:
        cat, subj = combos.pop()
        add_project(*concept(cat, subj), rng.choice(pstatuses))
    combo_rows = []
    while len(requests) < N_REQUESTS:
        cat, subj = combos.pop()
        row = add_request(*concept(cat, subj), rng.choice(statuses))
        combo_rows.append((row, cat, subj[0]))

    raw = out_root / "data/raw"
    raw.mkdir(parents=True, exist_ok=True)
    cols = ["request_id"] + [f["field_name"] for f in fields] + ["status", "submitted_at", "updated_at"]
    with open(raw / "opportunity_log.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(requests)
    (raw / "project_tracker.json").write_text(json.dumps(projects, indent=1))

    ev = out_root / "eval"
    ev.mkdir(exist_ok=True)
    label_rows = [(r, c) for r, c in labels if r["request_id"] in ambiguous_ids][:5]
    label_rows += [(r, c) for r, c, _ in combo_rows[:45]]
    with open(ev / "labeled_categories.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["request_id", "title", "description", "true_category"])
        w.writerows([r["request_id"], r["title"], r["description"], c] for r, c in label_rows)

    pairs = [(a, at, ad, b, bt, bd, 1) for a, at, ad, b, bt, bd in planted]
    by_subj, by_cat = {}, {}
    for r, c, s in combo_rows:
        by_subj.setdefault(s, []).append(r)
        by_cat.setdefault(c, []).append(r)
    hard = [v[:2] for v in by_subj.values() if len(v) >= 2][:8]
    hard += [v[:2] for v in by_cat.values()][:7]
    while len(hard) < 22:
        hard.append(rng.sample([r for r, _, _ in combo_rows], 2))
    pairs += [(x["request_id"], x["title"], x["description"], y["request_id"], y["title"],
               y["description"], 0) for x, y in hard]
    with open(ev / "duplicate_pairs.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["pair_id", "id_a", "title_a", "description_a", "id_b", "title_b", "description_b", "is_duplicate"])
        w.writerows([i + 1, *p] for i, p in enumerate(pairs))

    summary = (f"seed={SEED}\nrequests={len(requests)}\nprojects={len(projects)}\n"
               f"planted_pairs={len(planted)}\nambiguous={len(ambiguous_ids)}\n"
               f"labeled_categories={len(label_rows)}\nduplicate_pairs={len(pairs)}\n")
    (out_root / "evidence").mkdir(exist_ok=True)
    (out_root / "evidence/data_gen.txt").write_text(summary)
    print(summary)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT)
