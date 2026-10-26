"""Phase 1 self-check: synthetic data shape, planted pairs, and no company names."""

import csv
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_gen"))
import generate  # noqa: E402
from names import BUSINESS_UNITS, SYSTEMS  # noqa: E402
from seeds import AMBIGUOUS, PLANTED_PAIRS  # noqa: E402


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    root = tmp_path_factory.mktemp("gen")
    generate.main(root)
    return root


def read_csv(p):
    with open(p) as fh:
        return list(csv.DictReader(fh))


def test_row_counts(out):
    assert len(read_csv(out / "data/raw/opportunity_log.csv")) == 300
    assert len(json.loads((out / "data/raw/project_tracker.json").read_text())) == 60
    assert len(read_csv(out / "eval/labeled_categories.csv")) == 50
    assert len(read_csv(out / "eval/duplicate_pairs.csv")) == 40


def test_columns_follow_form_config(out):
    fields = [f["field_name"] for f in json.loads((ROOT / "config/form_fields.json").read_text())]
    header = list(read_csv(out / "data/raw/opportunity_log.csv")[0].keys())
    assert header[1:1 + len(fields)] == fields


def test_planted_pairs(out):
    assert 15 <= len(PLANTED_PAIRS) <= 20
    reqs = {r["title"] for r in read_csv(out / "data/raw/opportunity_log.csv")}
    projs = {p["name"]: p for p in json.loads((out / "data/raw/project_tracker.json").read_text())}
    assert projs["Agent ETA assistant"]["status"] == "in_progress"
    assert generate.LIVE_DEMO_TITLE not in reqs
    for _c, kind, existing, _d, new, _nd in PLANTED_PAIRS:
        assert new in reqs or new == generate.LIVE_DEMO_TITLE
        assert existing in (projs if kind == "project" else reqs)
    pairs = read_csv(out / "eval/duplicate_pairs.csv")
    assert sum(int(p["is_duplicate"]) for p in pairs) == len(PLANTED_PAIRS)


def test_ambiguous_requests(out):
    assert len(AMBIGUOUS) == 10
    reqs = {r["title"] for r in read_csv(out / "data/raw/opportunity_log.csv")}
    assert all(t in reqs for t, *_ in AMBIGUOUS)


def test_titles_unique(out):
    titles = [r["title"] for r in read_csv(out / "data/raw/opportunity_log.csv")]
    assert len(titles) == len(set(titles))


def test_generic_names_only(out):
    form = json.loads((ROOT / "config/form_fields.json").read_text())
    opts = {f["field_name"]: f["options"] for f in form}
    assert opts["business_unit"] == BUSINESS_UNITS
    assert opts["data_sources"] == SYSTEMS
    rows = read_csv(out / "data/raw/opportunity_log.csv")
    assert {r["business_unit"] for r in rows} <= set(BUSINESS_UNITS)
    for r in rows:
        assert set(r["data_sources"].split(";")) <= set(SYSTEMS)
        assert r["requester_email"].endswith("@example.com")


def test_no_faker_company_names(out):
    text = "\n".join(p.read_text() for p in out.rglob("*") if p.is_file())
    assert not re.search(r"\b(Inc|LLC|Ltd|PLC|Corp|GmbH|and Sons)\b", text)
    faker = pytest.importorskip("faker")
    fk = faker.Faker()
    fk.seed_instance(0)
    names = {fk.company() for _ in range(3000)}
    hits = [n for n in names if n in text]
    assert not hits, hits[:5]


def test_deterministic(tmp_path):
    generate.main(tmp_path / "a")
    generate.main(tmp_path / "b")
    for rel in ["data/raw/opportunity_log.csv", "data/raw/project_tracker.json"]:
        assert (tmp_path / "a" / rel).read_text() == (tmp_path / "b" / rel).read_text()


def test_bundle_config_matches_app_config():
    cfg = json.loads((ROOT / "config" / "app_config.json").read_text())
    bundle = (ROOT / "databricks.yml").read_text()
    assert f'default: "{cfg["classify_instructions"]}"' in bundle
    assert f'default: "{cfg["thresholds"]["likely_duplicate"]}"' in bundle
