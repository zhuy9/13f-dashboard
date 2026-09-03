"""GCS raw/parquet archive and Firestore document writer."""

import io
import logging

import pandas as pd
from firebase_admin import firestore

logger = logging.getLogger(__name__)

# Tables archived to parquet, one file per period. Dict-shaped per-period tables
# (manager_similarity, clusters) and tables without a period column (fastest_growing,
# latest-period-only by definition) aren't split-and-archived here -- archival only,
# not consumed by the live site. `# ponytail: JSON export for those if BigQuery needs them.`
_PARQUET_TABLES = [
    "holdings",
    "manager_quarter_summary",
    "manager_sector_exposure",
    "stock_quarter_summary",
    "stock_trend",
    "consensus_buys",
    "consensus_exits",
    "high_conviction",
    "biggest_new",
    "biggest_adds",
    "biggest_trims",
    "top_signals",
    "sector_rotation",
    "options_exposure",
]

_FIRESTORE_BATCH_SIZE = 400


def write_gcs(bucket, raw_by_filing: dict, tables: dict) -> None:
    """Raw 13F XML + one Parquet per table per period. Best-effort: log and continue per object."""
    for (cik, period), raw_xml in raw_by_filing.items():
        if not raw_xml:
            continue
        try:
            bucket.blob(f"raw/{cik}/{period}/infotable.xml").upload_from_string(raw_xml, content_type="application/xml")
        except Exception:
            logger.exception("GCS upload failed: raw/%s/%s", cik, period)

    for name in _PARQUET_TABLES:
        df = tables.get(name)
        if df is None or df.empty or "period" not in df.columns:
            continue
        for period, period_df in df.groupby("period"):
            try:
                buf = io.BytesIO()
                period_df.to_parquet(buf, index=False)
                bucket.blob(f"parquet/{name}/{period}.parquet").upload_from_string(
                    buf.getvalue(), content_type="application/octet-stream"
                )
            except Exception:
                logger.exception("GCS upload failed: parquet/%s/%s", name, period)


def _camel(key: str) -> str:
    head, *rest = key.split("_")
    return head + "".join(part.title() for part in rest)


def _clean(obj):
    """snake_case -> camelCase keys, recursively; NaN/NaT -> None."""
    if isinstance(obj, dict):
        return {_camel(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, float) and pd.isna(obj):
        return None
    return obj


def _records(df: pd.DataFrame) -> list[dict]:
    return _clean(df.to_dict("records"))


def _commit_in_batches(db, writes: list[tuple[str, dict]]) -> None:
    for i in range(0, len(writes), _FIRESTORE_BATCH_SIZE):
        batch = db.batch()
        for path, data in writes[i : i + _FIRESTORE_BATCH_SIZE]:
            batch.set(db.document(path), data)
        batch.commit()


def _build_meta(tables: dict, funds: list[dict], periods: list[str]) -> dict:
    latest_period = periods[-1]
    managers = [{"cik": f["cik"], "short": f["short"], "name": f["name"], "cluster": f["cluster"]} for f in funds]
    clusters_at_latest = list(tables["clusters"].get(latest_period, {}).values())
    return {
        "latestPeriod": latest_period,
        "periods": periods,
        "managers": managers,
        "clusters": _clean(clusters_at_latest),
        "symbols": _records(tables["symbols"][["symbol", "name", "sector"]]),
        "updatedAt": firestore.SERVER_TIMESTAMP,
    }


def _build_manager_docs(tables: dict, funds: list[dict]) -> dict[str, dict]:
    manager_periods = tables["totals"].groupby("cik")["period"].apply(lambda s: sorted(s)).to_dict()
    return {
        f["cik"]: {
            "cik": f["cik"],
            "name": f["name"],
            "short": f["short"],
            "cluster": f["cluster"],
            "periods": manager_periods.get(f["cik"], []),
        }
        for f in funds
    }


def _build_manager_quarter_docs(tables: dict, funds: list[dict]) -> dict[str, dict]:
    short_by_cik = {f["cik"]: f["short"] for f in funds}
    totals_idx = tables["totals"].set_index(["cik", "period"])
    mqs = tables["manager_quarter_summary"]
    mse = tables["manager_sector_exposure"]
    similarity = tables["manager_similarity"]

    docs = {}
    for (cik, period), grp in mqs.groupby(["cik", "period"]):
        counts = grp["status"].value_counts()
        similar = similarity.get(period, {}).get("most_similar", {}).get(cik, [])
        docs[f"{cik}_{period}"] = {
            "filedAt": totals_idx.loc[(cik, period), "filed_at"],
            "totalValue": int(totals_idx.loc[(cik, period), "total_value"]),
            "count": int((grp["value"] > 0).sum()),
            "counts": {
                "new": int(counts.get("NEW", 0)),
                "added": int(counts.get("ADDED", 0)),
                "trimmed": int(counts.get("TRIMMED", 0)),
                "unchanged": int(counts.get("UNCHANGED", 0)),
                "soldOut": int(counts.get("SOLD_OUT", 0)),
            },
            "positions": _records(grp.drop(columns=["cik", "period"])),
            "sectors": _records(mse[(mse["cik"] == cik) & (mse["period"] == period)].drop(columns=["cik", "period"])),
            "mostSimilar": [
                {"cik": s["cik"], "short": short_by_cik.get(s["cik"], s["cik"]), "score": s["score"]} for s in similar
            ],
        }
    return docs


def _build_stock_docs(tables: dict, funds: list[dict]) -> dict[str, dict]:
    short_by_cik = {f["cik"]: f["short"] for f in funds}
    symbols = tables["symbols"].set_index("symbol")
    trend = tables["stock_trend"]
    sqs = tables["stock_quarter_summary"]
    options = tables["options_exposure"]
    latest_period = sqs["period"].max()

    docs = {}
    for symbol, meta in symbols.iterrows():
        latest_row = sqs[(sqs["symbol"] == symbol) & (sqs["period"] == latest_period)]
        latest = None
        if len(latest_row):
            r = latest_row.iloc[0].drop(labels=["symbol", "name"])
            opt = options[(options["symbol"] == symbol) & (options["period"] == latest_period)]
            calls = [{"cik": c, "short": short_by_cik.get(c, c)} for c in opt["call_holders"].iloc[0]] if len(opt) else []
            puts = [{"cik": c, "short": short_by_cik.get(c, c)} for c in opt["put_holders"].iloc[0]] if len(opt) else []
            latest = _clean(r.to_dict())
            latest["options"] = {"calls": calls, "puts": puts}

        docs[symbol] = {
            "symbol": symbol,
            "name": meta["name"],
            "sector": meta["sector"],
            "trend": _records(trend[trend["symbol"] == symbol].drop(columns=["symbol"])),
            "latest": latest,
        }
    return docs


def _build_signals_docs(tables: dict, periods: list[str]) -> dict[str, dict]:
    # (Firestore field name, source table name) -- table names stay snake_case (Python side);
    # doc field names are camelCase (JS side), converted explicitly since these are top-level
    # document keys, not row fields that flow through _records()/_clean()'s recursive _camel().
    e_tables = [
        ("consensusBuys", "consensus_buys"),
        ("consensusExits", "consensus_exits"),
        ("highConviction", "high_conviction"),
        ("biggestNew", "biggest_new"),
        ("biggestAdds", "biggest_adds"),
        ("biggestTrims", "biggest_trims"),
        ("topSignals", "top_signals"),
    ]
    docs = {}
    for period in periods:
        doc = {
            field: _records(tables[table][tables[table]["period"] == period].drop(columns=["period"]))
            for field, table in e_tables
        }
        doc["fastestGrowing"] = _records(tables["fastest_growing"]) if period == periods[-1] else []

        rotation = tables["sector_rotation"]
        doc["sectorRotation"] = _records(rotation[rotation["period"] == period].drop(columns=["period"]))

        sim = tables["manager_similarity"].get(period, {"ciks": [], "matrix": [], "most_similar": {}})
        # Firestore forbids arrays nested directly inside arrays, so each row is a {values: [...]} map.
        doc["managerSimilarity"] = {"ciks": sim["ciks"], "matrix": [{"values": row} for row in sim["matrix"]]}

        opts = tables["options_exposure"]
        doc["optionsExposure"] = _records(opts[opts["period"] == period].drop(columns=["period"]))
        docs[period] = doc
    return docs


def write_firestore(db, tables: dict, funds: list[dict], periods: list[str]) -> None:
    """Build and write meta/latest, managers/*, manager_quarters/*, stocks/*, signals/* in batches of 400."""
    writes: list[tuple[str, dict]] = [("meta/latest", _build_meta(tables, funds, periods))]

    for cik, doc in _build_manager_docs(tables, funds).items():
        writes.append((f"managers/{cik}", doc))
    for doc_id, doc in _build_manager_quarter_docs(tables, funds).items():
        writes.append((f"manager_quarters/{doc_id}", doc))
    for symbol, doc in _build_stock_docs(tables, funds).items():
        writes.append((f"stocks/{symbol}", doc))
    for period, doc in _build_signals_docs(tables, periods).items():
        writes.append((f"signals/{period}", doc))

    _commit_in_batches(db, writes)
