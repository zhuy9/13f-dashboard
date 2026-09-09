from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import ownership
import store
from test_ownership_store import CFG, FUNDS
from test_ownership_store import tables as ownership_tables
from test_store import FUNDS as HOLDING_FUNDS
from test_store import tables as holding_tables


def test_failed_snapshot_keeps_pointer_and_retry_matches_clean_run(monkeypatch):
    class Db:
        def __init__(self):
            self.docs = {"meta/latest": {"datasetId": "old"}}
            self.commits = 0

        def document(self, path):
            return path

        def batch(self):
            pending = {}

            def commit():
                self.commits += 1
                if self.commits == 2:
                    raise RuntimeError("interrupted")
                self.docs.update(pending)

            return SimpleNamespace(set=pending.__setitem__, commit=commit)

    monkeypatch.setattr(store, "_FIRESTORE_BATCH_SIZE", 2)
    db = Db()
    tables = holding_tables.__wrapped__()
    with pytest.raises(RuntimeError, match="interrupted"):
        store.write_firestore(db, tables, HOLDING_FUNDS, tables["periods"])
    assert db.docs["meta/latest"] == {"datasetId": "old"}

    store.write_firestore(db, tables, HOLDING_FUNDS, tables["periods"])
    retry_id = db.docs["meta/latest"]["datasetId"]
    clean = Db()
    clean.commits = 100
    store.write_firestore(clean, tables, HOLDING_FUNDS, tables["periods"])
    clean_id = clean.docs["meta/latest"]["datasetId"]
    retry = {p.removeprefix(f"datasets/{retry_id}/"): v for p, v in db.docs.items() if p.startswith(f"datasets/{retry_id}/")}
    expected = {
        p.removeprefix(f"datasets/{clean_id}/"): v for p, v in clean.docs.items() if p.startswith(f"datasets/{clean_id}/")
    }
    assert retry == expected
    assert "signals/2026-06-30" in retry


def test_ownership_checkpoint_waits_for_publication_and_retry_repairs_pages(monkeypatch):
    filings = ownership_tables.__wrapped__()["filings"]
    saved, attempts = [], []

    def publish(db, feed, issuers, investors):
        attempts.append((feed, issuers, investors))
        if len(attempts) == 1:
            raise RuntimeError("interrupted")
        return 1 + len(issuers) + len(investors)

    replacements = {
        "load_dotenv": lambda *a: None,
        "load_config": lambda: {"ownership": {**CFG, "refetch_overlap_days": 3}},
        "load_funds": lambda: FUNDS,
        "init_firestore": lambda: object(),
        "read_state": lambda bucket: saved[-1] if saved else None,
        "list_filings": lambda *a: filings[["accession"]].copy(),
        "fetch_rows": lambda listed, cfg: (filings[filings.accession.isin(listed.accession)].to_dict("records"), {}, 0),
        "_enrich": lambda df, *a, **kw: filings[filings.accession.isin(df.accession)].copy(),
        "read_holder_counts": lambda db: None,
        "write_state": lambda bucket, rows, raw: saved.append(rows.copy()),
        "write_firestore": publish,
        "step_summary": lambda *a: None,
    }
    monkeypatch.setenv("EDGAR_IDENTITY", "fixture")
    monkeypatch.setenv("GCS_BUCKET", "fixture")
    monkeypatch.setattr(ownership.sys, "argv", ["ownership.py"])
    monkeypatch.setattr("edgar.set_identity", lambda *a: None)
    monkeypatch.setattr("google.cloud.storage.Client", Mock())
    for name, replacement in replacements.items():
        monkeypatch.setattr(ownership, name, replacement)
    with pytest.raises(RuntimeError, match="interrupted"):
        ownership.main()
    assert not saved
    assert ownership.main() == 0
    assert attempts[0] == attempts[1]
    assert attempts[1][1] and attempts[1][2]
    assert len(saved[-1]) == len(filings)
