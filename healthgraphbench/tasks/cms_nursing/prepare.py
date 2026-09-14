"""Deterministic CMS nursing-home task preparation.

The builder reads official CMS snapshots and keeps only derived episode and
ownership features in memory. It does not ship CMS rows in the repository.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping


TARGET_YEARS = tuple(range(2019, 2026))
SERIOUS_SEVERITY_CODES = frozenset("GHIJKL")
EXCLUDED_CURRENT_ROLES = frozenset(
    {
        "W-2 MANAGING EMPLOYEE",
        "5% OR GREATER MORTGAGE INTEREST",
        "5% OR GREATER SECURITY INTEREST",
        "CONTRACTED MANAGING EMPLOYEE",
    }
)
CHOW_ROLES = frozenset(
    {
        "OPERATIONAL/MANAGERIAL CONTROL",
        "5% OR GREATER INDIRECT OWNERSHIP INTEREST",
        "CORPORATE OFFICER",
        "5% OR GREATER DIRECT OWNERSHIP INTEREST",
        "CORPORATE DIRECTOR",
        "LIMITED PARTNERSHIP INTEREST",
        "GENERAL PARTNERSHIP INTEREST",
    }
)

OwnerRecord = tuple[str, date, str, str]
Episode = tuple[str, date]


@dataclass(frozen=True, slots=True)
class CmsSources:
    health_citations: Path
    ownership: Path
    provider_info: Path
    survey_dates: Path
    penalties: Path
    chow: Path
    chow_owners: Path


@dataclass(frozen=True, slots=True)
class CmsPrepared:
    rows: tuple[dict[str, Any], ...]
    sources: CmsSources
    standard_episodes: frozenset[Episode]
    serious_episodes: frozenset[Episode]
    provider_static: Mapping[str, Mapping[str, Any]]
    combined_records: Mapping[str, tuple[OwnerRecord, ...]]
    combined_first: Mapping[str, Mapping[str, date]]
    chow_dates: Mapping[str, tuple[date, ...]]
    state_values: tuple[str, ...]
    current_records: Mapping[str, tuple[OwnerRecord, ...]] = field(default_factory=dict)


def normalize_owner_name(owner_type: str, name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", f"{owner_type}|{name}".upper().strip())


def _parse_date(value: str) -> date | None:
    text = value.strip()
    if not text:
        return None
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if match:
        try:
            return date(int(match.group(3)), int(match.group(1)), int(match.group(2)))
        except ValueError:
            return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    try:
        return datetime.strptime(text, "%m/%d/%Y").date()
    except ValueError:
        return None


def _read_csv(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def _read_json_records(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "results", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    raise ValueError(f"Expected a JSON record list in {path}")


def _first_by_entity(
    records_by_ccn: Mapping[str, Iterable[OwnerRecord]],
) -> dict[str, dict[str, date]]:
    result: dict[str, dict[str, date]] = defaultdict(dict)
    for ccn, records in records_by_ccn.items():
        for owner, association, _role, _owner_type in records:
            current = result[owner].get(ccn)
            if current is None or association < current:
                result[owner][ccn] = association
    return result


def _episode_histories(
    standard_episodes: Iterable[Episode], serious_episodes: set[Episode]
) -> dict[str, tuple[tuple[date, ...], tuple[int, ...]]]:
    dates_by_ccn: dict[str, list[date]] = defaultdict(list)
    for ccn, episode_date in standard_episodes:
        dates_by_ccn[ccn].append(episode_date)
    histories: dict[str, tuple[tuple[date, ...], tuple[int, ...]]] = {}
    for ccn, dates in dates_by_ccn.items():
        ordered = tuple(sorted(set(dates)))
        prefix = [0]
        for episode_date in ordered:
            prefix.append(prefix[-1] + int((ccn, episode_date) in serious_episodes))
        histories[ccn] = ordered, tuple(prefix)
    return histories


def history_stats(
    episode_histories: Mapping[str, tuple[tuple[date, ...], tuple[int, ...]]],
    ccn: str,
    target_date: date,
) -> dict[str, Any]:
    dates, prefix = episode_histories[ccn]
    import bisect

    index = bisect.bisect_left(dates, target_date)
    start365 = bisect.bisect_left(dates, target_date - timedelta(days=365))
    start730 = bisect.bisect_left(dates, target_date - timedelta(days=730))
    return {
        "prior_inspections": index,
        "prior_serious": prefix[index],
        "recent365_inspections": index - start365,
        "recent365_serious": prefix[index] - prefix[start365],
        "recent730_inspections": index - start730,
        "recent730_serious": prefix[index] - prefix[start730],
        "days_since_last": (target_date - dates[index - 1]).days if index else None,
        "index": index,
    }


def _peer_stats_from_maps(
    ccn: str,
    target_date: date,
    records_by_ccn: Mapping[str, Iterable[OwnerRecord]],
    first_by_entity: Mapping[str, Mapping[str, date]],
    episode_histories: Mapping[str, tuple[tuple[date, ...], tuple[int, ...]]],
    histories: dict[tuple[str, date], dict[str, Any]],
) -> dict[str, int]:
    active = {
        owner
        for owner, association, _role, _owner_type in records_by_ccn.get(ccn, ())
        if association <= target_date
    }
    peers: set[str] = set()
    for owner in active:
        for peer, association in first_by_entity.get(owner, {}).items():
            if peer != ccn and association <= target_date:
                peers.add(peer)
    output = {
        "owner_count": len(active),
        "peer_count": len(peers),
        "peer_prior_facilities": 0,
        "peer_prior_inspections": 0,
        "peer_prior_serious": 0,
        "peer_recent365_inspections": 0,
        "peer_recent365_serious": 0,
        "peer_recent730_serious": 0,
        "peer_any_serious365": 0,
        "peer_any_serious730": 0,
    }
    for peer in peers:
        if peer not in episode_histories:
            continue
        key = (peer, target_date)
        stats = histories.get(key)
        if stats is None:
            stats = history_stats(episode_histories, peer, target_date)
            histories[key] = stats
        if not stats["prior_inspections"]:
            continue
        output["peer_prior_facilities"] += 1
        output["peer_prior_inspections"] += stats["prior_inspections"]
        output["peer_prior_serious"] += stats["prior_serious"]
        output["peer_recent365_inspections"] += stats["recent365_inspections"]
        output["peer_recent365_serious"] += stats["recent365_serious"]
        output["peer_recent730_serious"] += stats["recent730_serious"]
        output["peer_any_serious365"] += int(stats["recent365_serious"] > 0)
        output["peer_any_serious730"] += int(stats["recent730_serious"] > 0)
    return output


def _build_current_owner_maps(
    rows: Iterable[dict[str, str]],
) -> tuple[dict[str, list[OwnerRecord]], dict[str, list[OwnerRecord]]]:
    all_records: dict[str, list[OwnerRecord]] = defaultdict(list)
    relevant_records: dict[str, list[OwnerRecord]] = defaultdict(list)
    for row in rows:
        ccn = row["CMS Certification Number (CCN)"].strip()
        association = _parse_date(row.get("Association Date", ""))
        if not ccn or association is None:
            continue
        owner_type = row.get("Owner Type", "").strip()
        owner_name = row.get("Owner Name", "").strip()
        if not owner_type or not owner_name:
            continue
        role = row.get("Role played by Owner or Manager in Facility", "").strip()
        record = (normalize_owner_name(owner_type, owner_name), association, role, owner_type)
        all_records[ccn].append(record)
        if role not in EXCLUDED_CURRENT_ROLES:
            relevant_records[ccn].append(record)
    return all_records, relevant_records


def _build_chow_maps(
    chow_rows: Iterable[dict[str, str]],
    owner_rows: Iterable[dict[str, str]],
) -> tuple[dict[str, list[date]], dict[str, list[OwnerRecord]]]:
    enrollment_to_ccn: dict[str, str] = {}
    chow_dates: dict[str, list[date]] = defaultdict(list)
    for row in chow_rows:
        effective = _parse_date(row.get("EFFECTIVE DATE", ""))
        if effective is None:
            continue
        for side in ("BUYER", "SELLER"):
            enrollment = row.get(f"ENROLLMENT ID - {side}", "").strip()
            ccn = row.get(f"CCN - {side}", "").strip()
            if enrollment and ccn:
                enrollment_to_ccn[enrollment] = ccn
                chow_dates[ccn].append(effective)

    stable_records: dict[str, list[OwnerRecord]] = defaultdict(list)
    for row in owner_rows:
        ccn = enrollment_to_ccn.get(row.get("ENROLLMENT ID", "").strip())
        association = _parse_date(row.get("ASSOCIATION DATE - OWNER", ""))
        role = row.get("ROLE TEXT - OWNER", "").strip()
        associate = row.get("ASSOCIATE ID - OWNER", "").strip()
        owner_type = row.get("TYPE - OWNER", "").strip()
        if ccn and association is not None and associate and role in CHOW_ROLES:
            stable_records[ccn].append((f"PAC:{associate}", association, role, owner_type))
    return chow_dates, stable_records


def prepare_sources(sources: CmsSources) -> CmsPrepared:
    standard_episodes: set[Episode] = set()
    for row in _read_csv(sources.survey_dates):
        if row.get("Type of Survey", "").strip() != "Health Standard":
            continue
        episode_date = _parse_date(row.get("Survey Date", ""))
        ccn = row.get("CMS Certification Number (CCN)", "").strip()
        if ccn and episode_date is not None:
            standard_episodes.add((ccn, episode_date))

    serious_episodes: set[Episode] = set()
    for row in _read_csv(sources.health_citations):
        if row.get("Survey Type", "").strip() != "Health":
            continue
        episode_date = _parse_date(row.get("Survey Date", ""))
        ccn = row.get("CMS Certification Number (CCN)", "").strip()
        if (
            ccn
            and episode_date is not None
            and row.get("Standard Deficiency", "").strip() == "Y"
            and row.get("Scope Severity Code", "").strip() in SERIOUS_SEVERITY_CODES
        ):
            serious_episodes.add((ccn, episode_date))

    provider_static: dict[str, dict[str, Any]] = {}
    for row in _read_csv(sources.provider_info):
        ccn = row.get("CMS Certification Number (CCN)", "").strip()
        if not ccn or ccn in provider_static:
            continue
        approval_date = _parse_date(
            row.get("Date First Approved to Provide Medicare and Medicaid Services", "")
        )
        if approval_date is None:
            continue
        provider_static[ccn] = {
            "state": row.get("State", "").strip(),
            "approval_date": approval_date,
            "provider_type": row.get("Provider Type", "").strip(),
        }

    current_all, current_relevant = _build_current_owner_maps(_read_csv(sources.ownership))
    chow_dates, stable_records = _build_chow_maps(
        _read_json_records(sources.chow), _read_json_records(sources.chow_owners)
    )
    stable_records = {
        ccn: records for ccn, records in stable_records.items() if ccn in provider_static
    }
    # fill the map with current ownership only for CCNs absent from CHOW.
    combined_records: dict[str, list[OwnerRecord]] = defaultdict(list)
    for ccn, records in stable_records.items():
        combined_records[ccn] = list(records)
    for ccn, records in current_relevant.items():
        combined_records.setdefault(ccn, list(records))
    combined_first = _first_by_entity(combined_records)
    episode_histories = _episode_histories(standard_episodes, serious_episodes)

    base_rows: list[dict[str, Any]] = []
    for ccn, episode_date in sorted(standard_episodes, key=lambda item: (item[1], item[0])):
        if episode_date.year not in TARGET_YEARS or ccn not in episode_histories:
            continue
        stats = history_stats(episode_histories, ccn, episode_date)
        if not stats["prior_inspections"] or ccn not in provider_static:
            continue
        provider = provider_static[ccn]
        age_years = max(0.0, (episode_date - provider["approval_date"]).days / 365.25)
        chow = chow_dates.get(ccn, [])
        base_rows.append(
            {
                "ccn": ccn,
                "date": episode_date,
                "year": episode_date.year,
                "label": int((ccn, episode_date) in serious_episodes),
                "state": provider["state"],
                "provider_type": provider["provider_type"],
                "age_years": age_years,
                "prior_inspections": stats["prior_inspections"],
                "prior_serious": stats["prior_serious"],
                "prior_serious_rate": stats["prior_serious"] / stats["prior_inspections"],
                "recent365_inspections": stats["recent365_inspections"],
                "recent365_serious": stats["recent365_serious"],
                "recent730_inspections": stats["recent730_inspections"],
                "recent730_serious": stats["recent730_serious"],
                "days_since_last": stats["days_since_last"],
                "chow_prior": sum(chow_date < episode_date for chow_date in chow),
                "chow_recent365": sum(
                    episode_date - timedelta(days=365) <= chow_date < episode_date
                    for chow_date in chow
                ),
            }
        )

    rows: list[dict[str, Any]] = []
    histories_cache: dict[tuple[str, date], dict[str, Any]] = {}
    for base in base_rows:
        row = dict(base)
        row.update(
            _peer_stats_from_maps(
                base["ccn"],
                base["date"],
                combined_records,
                combined_first,
                episode_histories,
                histories_cache,
            )
        )
        rows.append(row)

    state_values = tuple(sorted({str(row["state"]) for row in rows}))
    return CmsPrepared(
        tuple(rows),
        sources,
        frozenset(standard_episodes),
        frozenset(serious_episodes),
        provider_static,
        {ccn: tuple(records) for ccn, records in combined_records.items()},
        combined_first,
        {ccn: tuple(dates) for ccn, dates in chow_dates.items()},
        state_values,
        {ccn: tuple(records) for ccn, records in current_all.items()},
    )
