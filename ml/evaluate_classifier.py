"""Evaluate ai_classify on the labeled request set and log the results to MLflow.

Uses the same call as pipeline/silver.sql (version 2.1, config labels and instructions).
Writes evidence/classifier_eval.txt. Env: INTAKE_CATALOG is not needed; DATABRICKS_SQL_WAREHOUSE_ID is.
"""

import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path

from databricks.sdk import WorkspaceClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))
import run  # noqa: E402


def lit(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def classify_all(w, rows, cfg):
    labels = json.dumps({c["label"]: c["description"] for c in cfg["categories"]})
    values = ",\n".join(f"({lit(r['request_id'])}, {lit(r['title'] + '. ' + r['description'])})" for r in rows)
    stmt = f"""SELECT id, ai_classify(content, {lit(labels)},
                 map('version', '2.1', 'instructions', {lit(cfg['classify_instructions'])},
                     'enableConfidenceScores', 'true')):response[0] AS top
               FROM VALUES {values} AS t(id, content)"""
    out = {}
    for r in run.sql(w, stmt):
        top = json.loads(r["top"]) if r["top"] else {}
        out[r["id"]] = (top.get("value"), top.get("confidence_score"))
    return out


def metrics(truth, pred, labels):
    per = {}
    for lab in labels:
        tp = sum(t == lab and p == lab for t, p in zip(truth, pred))
        fp = sum(t != lab and p == lab for t, p in zip(truth, pred))
        fn = sum(t == lab and p != lab for t, p in zip(truth, pred))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        per[lab] = (prec, rec, 2 * prec * rec / (prec + rec) if prec + rec else 0.0, tp + fn)
    acc = sum(t == p for t, p in zip(truth, pred)) / len(truth)
    return acc, sum(v[2] for v in per.values()) / len(per), per


def main():
    cfg = json.loads((ROOT / "config/app_config.json").read_text())
    with open(ROOT / "eval/labeled_categories.csv") as fh:
        rows = list(csv.DictReader(fh))
    w = WorkspaceClient()
    preds = classify_all(w, rows, cfg)
    labels = [c["label"] for c in cfg["categories"]]
    truth = [r["true_category"] for r in rows]
    pred = [preds.get(r["request_id"], (None, None))[0] for r in rows]
    acc, macro_f1, per = metrics(truth, pred, labels)
    confs = [c for _, c in preds.values() if c is not None]
    misses = [(r["title"], r["true_category"], p) for r, p in zip(rows, pred) if p != r["true_category"]]
    lines = [f"rows={len(rows)} model=ai_classify version=2.1 (instructions + label descriptions from config)",
             f"accuracy={acc:.3f}", f"macro_f1={macro_f1:.3f}",
             f"mean_confidence={sum(confs) / len(confs):.3f}" if confs else "mean_confidence=n/a",
             "## per label: precision recall f1 support"]
    lines += [f"{lab}: {p:.2f} {r:.2f} {f:.2f} {n}" for lab, (p, r, f, n) in per.items()]
    lines += ["## confusion (true -> predicted, misses only)"]
    lines += [f"{t} -> {p}: {n}" for (t, p), n in Counter((t, p) for _, t, p in misses).most_common()]
    lines += ["## misclassified examples"] + [f"{t!r}: true={a} predicted={p}" for t, a, p in misses[:15]]
    run.write_evidence("classifier_eval.txt", lines)
    log_mlflow(w, {"accuracy": acc, "macro_f1": macro_f1}, {"model": "ai_classify", "version": "2.1",
                                                            "rows": len(rows)}, "classifier_eval.txt")


def log_mlflow(w, metrics_, params, evidence_name):
    try:
        import mlflow
        mlflow.set_tracking_uri("databricks")
        name = os.environ.get("MLFLOW_EXPERIMENT_NAME", f"/Users/{w.current_user.me().user_name}/oneintake-evaluation")
        mlflow.set_experiment(name)
        with mlflow.start_run(run_name=evidence_name.removesuffix(".txt")):
            mlflow.log_params(params)
            mlflow.log_metrics(metrics_)
            mlflow.log_artifact(str(run.EVIDENCE / evidence_name))
        print(f"logged to MLflow experiment {name}")
    except Exception as e:  # evidence file is the source of truth; MLflow is best effort
        print(f"MLflow logging skipped: {e}")


if __name__ == "__main__":
    main()
