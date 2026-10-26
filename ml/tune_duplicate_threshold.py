"""Tune the likely-duplicate threshold on eval/duplicate_pairs.csv and write it back to config.

Scores pairs exactly like the live check: BGE query embedding (config prefix) of the new request's
title and description against the document embedding of the existing item, cosine similarity.
Grid 0.60-0.95 step 0.05; picks the best F1 with precision >= 0.90 and updates
config/app_config.json and the databricks.yml duplicate_threshold default. Writes evidence/duplicate_eval.txt.
"""

import csv
import json
import math
import re
import sys
from pathlib import Path

from databricks.sdk import WorkspaceClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))
sys.path.insert(0, str(ROOT / "ml"))
import run  # noqa: E402
from evaluate_classifier import lit, log_mlflow  # noqa: E402

MIN_PRECISION = 0.90
GRID = [round(0.60 + 0.05 * i, 2) for i in range(8)]


def text_of(title, desc):
    return " ".join(f"{title.strip()}. {desc.strip()}".split()).strip(". ")


def score_pairs(w, pairs, emb):
    values = ",\n".join(f"({p['pair_id']}, {lit(emb['query_prefix'] + text_of(p['title_b'], p['description_b']))}, "
                        f"{lit(text_of(p['title_a'], p['description_a']))})" for p in pairs)
    stmt = f"""SELECT id, to_json(ai_query('{emb['endpoint']}', q)) AS q, to_json(ai_query('{emb['endpoint']}', d)) AS d
               FROM VALUES {values} AS t(id, q, d)"""
    scores = {}
    for r in run.sql(w, stmt):
        q, d = json.loads(r["q"]), json.loads(r["d"])
        dot = sum(a * b for a, b in zip(q, d))
        scores[int(r["id"])] = dot / (math.sqrt(sum(a * a for a in q)) * math.sqrt(sum(b * b for b in d)))
    return scores


def sweep(pairs, scores):
    rows = []
    for t in GRID:
        tp = sum(1 for p in pairs if scores[int(p["pair_id"])] >= t and p["is_duplicate"] == "1")
        fp = sum(1 for p in pairs if scores[int(p["pair_id"])] >= t and p["is_duplicate"] == "0")
        fn = sum(1 for p in pairs if scores[int(p["pair_id"])] < t and p["is_duplicate"] == "1")
        prec = tp / (tp + fp) if tp + fp else 1.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        rows.append((t, prec, rec, 2 * prec * rec / (prec + rec) if prec + rec else 0.0, tp, fp, fn))
    return rows


def write_threshold(t):
    cfg_path = ROOT / "config/app_config.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["thresholds"]["likely_duplicate"] = t
    text = cfg_path.read_text()
    cfg_path.write_text(re.sub(r'"likely_duplicate": [0-9.]+', f'"likely_duplicate": {t}', text))
    yml = ROOT / "databricks.yml"
    yml.write_text(re.sub(r'(duplicate_threshold:\n(?:    .*\n)*?    default: )"[0-9.]+"', rf'\1"{t}"', yml.read_text()))


def main():
    cfg = json.loads((ROOT / "config/app_config.json").read_text())
    with open(ROOT / "eval/duplicate_pairs.csv") as fh:
        pairs = list(csv.DictReader(fh))
    w = WorkspaceClient()
    scores = score_pairs(w, pairs, cfg["embedding"])
    rows = sweep(pairs, scores)
    eligible = [r for r in rows if r[1] >= MIN_PRECISION and r[4] > 0]
    best = max(eligible, key=lambda r: (r[3], r[1])) if eligible else None
    pos = sorted(round(scores[int(p["pair_id"])], 3) for p in pairs if p["is_duplicate"] == "1")
    neg = sorted(round(scores[int(p["pair_id"])], 3) for p in pairs if p["is_duplicate"] == "0")
    lines = [f"pairs={len(pairs)} positives={len(pos)} negatives={len(neg)} endpoint={cfg['embedding']['endpoint']}",
             "score=cosine(query embedding of new title+description with BGE prefix, document embedding of existing)",
             f"positive scores: {pos}", f"negative scores: {neg}",
             "## threshold precision recall f1 tp fp fn"]
    lines += [f"{t:.2f} {p:.3f} {r:.3f} {f:.3f} {tp} {fp} {fn}" for t, p, r, f, tp, fp, fn in rows]
    previous = cfg["thresholds"]["likely_duplicate"]
    if best:
        lines.append(f"chosen likely_duplicate={best[0]:.2f} (best F1 {best[3]:.3f} with precision {best[1]:.3f} "
                     f">= {MIN_PRECISION}); previous={previous}")
        write_threshold(best[0])
    else:
        lines.append(f"no threshold reached precision >= {MIN_PRECISION}; kept likely_duplicate={previous}")
    demo = [p for p in pairs if p["title_b"].startswith("Chatbot so agents can check load ETA")]
    if demo:
        lines.append(f"demo pair full-text score={scores[int(demo[0]['pair_id'])]:.3f}")
    run.write_evidence("duplicate_eval.txt", lines)
    if best:
        log_mlflow(w, {"precision": best[1], "recall": best[2], "f1": best[3], "threshold": best[0]},
                   {"endpoint": cfg["embedding"]["endpoint"], "min_precision": MIN_PRECISION}, "duplicate_eval.txt")


if __name__ == "__main__":
    main()
