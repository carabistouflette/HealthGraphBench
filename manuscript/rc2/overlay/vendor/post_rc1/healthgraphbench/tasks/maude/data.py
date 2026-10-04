"""Streaming official MAUDE snapshots into quarterly product/problem graphs."""

from __future__ import annotations

import csv
import hashlib
import heapq
import io
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

QUARTERS: tuple[str, ...] = tuple(
    f"{year}Q{quarter}" for year in range(2019, 2026) for quarter in range(1, 5)
)
QUARTER_INDEX: dict[str, int] = {quarter: index for index, quarter in enumerate(QUARTERS)}
Edge = tuple[str, str]


@dataclass(slots=True)
class ParserStats:
    physical_lines: int = 0
    numeric_key_lines: int = 0
    valid_rows: int = 0
    wrong_field_count: int = 0
    non_numeric_key_lines: int = 0
    blank_product_rows: int = 0
    blank_lines: int = 0
    outside_window: int = 0
    key_inversions: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "physical_lines": self.physical_lines,
            "numeric_key_lines": self.numeric_key_lines,
            "valid_rows": self.valid_rows,
            "wrong_field_count": self.wrong_field_count,
            "non_numeric_key_lines": self.non_numeric_key_lines,
            "blank_product_rows": self.blank_product_rows,
            "blank_lines": self.blank_lines,
            "outside_window": self.outside_window,
            "key_inversions": self.key_inversions,
        }


@dataclass(slots=True)
class ProblemStats:
    physical_lines: int = 0
    malformed_lines: int = 0
    valid_two_field_numeric_lines: int = 0
    nonblank_problem_associations: int = 0
    blank_problem_code_lines: int = 0
    unique_problem_mdr_keys: int = 0
    keys_with_multiple_distinct_problem_codes: int = 0
    max_distinct_problem_codes_per_key: int = 0
    key_inversions: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "physical_lines": self.physical_lines,
            "malformed_lines": self.malformed_lines,
            "valid_two_field_numeric_lines": self.valid_two_field_numeric_lines,
            "nonblank_problem_associations": self.nonblank_problem_associations,
            "blank_problem_code_lines": self.blank_problem_code_lines,
            "unique_problem_mdr_keys": self.unique_problem_mdr_keys,
            "keys_with_multiple_distinct_problem_codes": self.keys_with_multiple_distinct_problem_codes,
            "max_distinct_problem_codes_per_key": self.max_distinct_problem_codes_per_key,
            "key_inversions": self.key_inversions,
        }


@dataclass(frozen=True, slots=True)
class QuarterSnapshot:
    quarter: str
    report_keys: int
    product_reports: Mapping[str, int]
    product_manufacturers: Mapping[str, frozenset[str]]
    edges: frozenset[Edge]
    edge_report_counts: Mapping[Edge, int]


@dataclass(frozen=True, slots=True)
class DataAudit:
    device_stats: Mapping[str, ParserStats]
    problem_stats: ProblemStats
    unique_device_mdr_keys: int
    matched_device_problem_mdr_keys: int
    problem_only_mdr_keys: int
    valid_device_rows: int
    keys_multiple_valid_device_rows: int
    duplicate_valid_rows_beyond_unique_product_per_key: int
    keys_multiple_product_codes: int
    max_valid_rows_per_key: int
    max_unique_products_per_key: int
    problem_keys_with_multiple_codes: int
    max_distinct_problem_codes_per_key: int
    unique_product_problem_edges: int
    unique_product_codes: int
    unique_problem_codes: int


@dataclass(frozen=True, slots=True)
class DataBundle:
    snapshots: tuple[QuarterSnapshot, ...]
    audit: DataAudit
    source_paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class DeviceRow:
    key: int
    quarter: str
    product: str
    manufacturer: str


def quarter_from_date(value: str) -> str | None:
    try:
        year_text, month_text, _ = value.strip().split("/", 2)
        year = int(year_text)
        month = int(month_text)
        quarter = (month - 1) // 3 + 1
    except (ValueError, TypeError):
        return None
    result = f"{year}Q{quarter}"
    return result if result in QUARTER_INDEX else None


def _device_stream(path: Path, stats: ParserStats) -> Iterator[DeviceRow]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != 1:
            raise ValueError(f"Expected one member in {path}, found {len(names)}")
        with archive.open(names[0]) as handle:
            header = handle.readline().decode("latin1").rstrip("\r\n").split("|")
            if len(header) != 34:
                raise ValueError(f"Unexpected device header width in {path}: {len(header)}")
            previous_key: int | None = None
            for raw in handle:
                stats.physical_lines += 1
                raw = raw.rstrip(b"\r\n")
                if not raw:
                    stats.blank_lines += 1
                    continue
                fields = raw.decode("latin1").split("|")
                if not fields[0].isdigit():
                    stats.non_numeric_key_lines += 1
                    continue
                stats.numeric_key_lines += 1
                if len(fields) != 34:
                    stats.wrong_field_count += 1
                    continue
                key = int(fields[0])
                if previous_key is not None and key < previous_key:
                    stats.key_inversions += 1
                previous_key = key
                quarter = quarter_from_date(fields[8])
                if quarter is None:
                    stats.outside_window += 1
                    continue
                product = fields[28].strip()
                if not product or product in {"*", "NA", "NI", "UNK"}:
                    stats.blank_product_rows += 1
                    continue
                stats.valid_rows += 1
                yield DeviceRow(key, quarter, product, fields[11].strip())


def _merged_device_groups(
    paths: Sequence[tuple[str, Path]],
    stats_by_year: dict[str, ParserStats],
) -> Iterator[tuple[int, list[DeviceRow]]]:
    streams: list[Iterator[DeviceRow]] = []
    heap: list[tuple[int, int, DeviceRow]] = []
    for year, path in paths:
        stats = ParserStats()
        stats_by_year[year] = stats
        stream = iter(_device_stream(path, stats))
        streams.append(stream)
        try:
            row = next(stream)
        except StopIteration:
            continue
        heapq.heappush(heap, (row.key, len(streams) - 1, row))

    while heap:
        key = heap[0][0]
        group: list[DeviceRow] = []
        while heap and heap[0][0] == key:
            _, index, row = heapq.heappop(heap)
            group.append(row)
            try:
                next_row = next(streams[index])
            except StopIteration:
                continue
            heapq.heappush(heap, (next_row.key, index, next_row))
        yield key, group


def _problem_groups(
    path: Path,
    stats: ProblemStats,
) -> Iterator[tuple[int, frozenset[str]]]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != 1:
            raise ValueError(f"Expected one member in {path}, found {len(names)}")
        with archive.open(names[0]) as handle:
            current_key: int | None = None
            codes: set[str] = set()
            previous_key: int | None = None
            for raw in handle:
                stats.physical_lines += 1
                raw = raw.rstrip(b"\r\n")
                if not raw:
                    continue
                parts = raw.decode("latin1").split("|")
                if len(parts) != 2 or not parts[0].isdigit():
                    stats.malformed_lines += 1
                    continue
                stats.valid_two_field_numeric_lines += 1
                key = int(parts[0])
                if previous_key is not None and key < previous_key:
                    stats.key_inversions += 1
                previous_key = key
                if current_key is None:
                    current_key = key
                if key != current_key:
                    frozen_codes = frozenset(codes)
                    stats.unique_problem_mdr_keys += 1
                    stats.max_distinct_problem_codes_per_key = max(
                        stats.max_distinct_problem_codes_per_key, len(frozen_codes)
                    )
                    if len(frozen_codes) > 1:
                        stats.keys_with_multiple_distinct_problem_codes += 1
                    yield current_key, frozen_codes
                    current_key = key
                    codes = set()
                code = parts[1].strip()
                if not code or code in {"*", "NA", "NI", "UNK"}:
                    stats.blank_problem_code_lines += 1
                else:
                    stats.nonblank_problem_associations += 1
                    codes.add(code)
            if current_key is not None:
                frozen_codes = frozenset(codes)
                stats.unique_problem_mdr_keys += 1
                stats.max_distinct_problem_codes_per_key = max(
                    stats.max_distinct_problem_codes_per_key, len(frozen_codes)
                )
                if len(frozen_codes) > 1:
                    stats.keys_with_multiple_distinct_problem_codes += 1
                yield current_key, frozen_codes


def _advance_problem(
    iterator: Iterator[tuple[int, frozenset[str]]],
) -> tuple[int | None, frozenset[str] | None]:
    try:
        return next(iterator)
    except StopIteration:
        return None, None


def load_snapshots(device_dir: Path, problem_zip: Path) -> DataBundle:
    paths = tuple((str(year), device_dir / f"device{year}.zip") for year in range(2019, 2026))
    for _, path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    if not problem_zip.is_file():
        raise FileNotFoundError(problem_zip)

    device_stats: dict[str, ParserStats] = {}
    problem_stats = ProblemStats()
    device_groups = iter(_merged_device_groups(paths, device_stats))
    problem_groups = iter(_problem_groups(problem_zip, problem_stats))
    device_key, device_group = _advance_device(device_groups)
    problem_key, problem_codes = _advance_problem(problem_groups)

    quarter_reports: Counter[str] = Counter()
    product_reports: dict[str, Counter[str]] = defaultdict(Counter)
    product_manufacturers: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    quarter_edges: dict[str, set[Edge]] = defaultdict(set)
    edge_report_counts: dict[str, Counter[Edge]] = defaultdict(Counter)
    matched_keys = 0
    problem_only_keys = 0
    unique_device_keys = 0
    valid_device_rows = 0
    keys_multiple_rows = 0
    duplicate_rows = 0
    keys_multiple_products = 0
    max_rows = 0
    max_products = 0

    while device_key is not None or problem_key is not None:
        if problem_key is None or (device_key is not None and device_key < problem_key):
            matched_codes: frozenset[str] | None = None
        elif device_key is None or problem_key < device_key:
            problem_only_keys += 1
            problem_key, problem_codes = _advance_problem(problem_groups)
            continue
        else:
            matched_codes = problem_codes
            matched_keys += 1
            problem_key, problem_codes = _advance_problem(problem_groups)

        if device_group is None:
            raise RuntimeError("Device stream ended with a missing group")
        unique_device_keys += 1
        valid_device_rows += len(device_group)
        products = {row.product for row in device_group}
        keys_multiple_rows += len(device_group) > 1
        duplicate_rows += len(device_group) - len(products)
        keys_multiple_products += len(products) > 1
        max_rows = max(max_rows, len(device_group))
        max_products = max(max_products, len(products))

        by_quarter: dict[str, set[str]] = defaultdict(set)
        by_manufacturer: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for row in device_group:
            by_quarter[row.quarter].add(row.product)
            if row.manufacturer:
                by_manufacturer[row.quarter][row.product].add(row.manufacturer)
        for quarter, quarter_products in by_quarter.items():
            quarter_reports[quarter] += 1
            for product in quarter_products:
                product_reports[quarter][product] += 1
                product_manufacturers[quarter][product].update(
                    by_manufacturer[quarter].get(product, set())
                )
                if matched_codes:
                    for problem in matched_codes:
                        edge = (product, problem)
                        quarter_edges[quarter].add(edge)
                        edge_report_counts[quarter][edge] += 1

        device_key, device_group = _advance_device(device_groups)

    snapshots: list[QuarterSnapshot] = []
    for quarter in QUARTERS:
        snapshots.append(
            QuarterSnapshot(
                quarter=quarter,
                report_keys=quarter_reports[quarter],
                product_reports=dict(product_reports[quarter]),
                product_manufacturers={
                    product: frozenset(manufacturers)
                    for product, manufacturers in product_manufacturers[quarter].items()
                },
                edges=frozenset(quarter_edges[quarter]),
                edge_report_counts=dict(edge_report_counts[quarter]),
            )
        )

    all_edges = set().union(*(snapshot.edges for snapshot in snapshots))
    all_products = {product for product, _ in all_edges}
    all_problems = {problem for _, problem in all_edges}
    audit = DataAudit(
        device_stats=device_stats,
        problem_stats=problem_stats,
        unique_device_mdr_keys=unique_device_keys,
        matched_device_problem_mdr_keys=matched_keys,
        problem_only_mdr_keys=problem_only_keys,
        valid_device_rows=valid_device_rows,
        keys_multiple_valid_device_rows=keys_multiple_rows,
        duplicate_valid_rows_beyond_unique_product_per_key=duplicate_rows,
        keys_multiple_product_codes=keys_multiple_products,
        max_valid_rows_per_key=max_rows,
        max_unique_products_per_key=max_products,
        problem_keys_with_multiple_codes=problem_stats.keys_with_multiple_distinct_problem_codes,
        max_distinct_problem_codes_per_key=problem_stats.max_distinct_problem_codes_per_key,
        unique_product_problem_edges=len(all_edges),
        unique_product_codes=len(all_products),
        unique_problem_codes=len(all_problems),
    )
    source_paths = (*tuple(path for _, path in paths), problem_zip)
    return DataBundle(tuple(snapshots), audit, source_paths)


def _advance_device(
    iterator: Iterator[tuple[int, list[DeviceRow]]],
) -> tuple[int | None, list[DeviceRow] | None]:
    try:
        return next(iterator)
    except StopIteration:
        return None, None


def load_problem_parent_map(
    archive_path: Path,
    observed_codes: set[str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Derive nearest IMDRF parent keys from the official FDA code mapping.

    The FDA CSV exposes FDA, NCIt, and IMDRF mappings but no explicit parent column.
    Parent keys therefore use the nearest shorter IMDRF prefix present in the same
    official mapping; a missing parent remains unmapped rather than inferred from
    numeric FDA code order.
    """
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != 1:
            raise ValueError(f"Expected one member in {archive_path}, found {len(names)}")
        with archive.open(names[0]) as handle:
            text = io.TextIOWrapper(handle, encoding="utf-8-sig", newline="")
            rows = list(csv.DictReader(text))
    code_to_imdrf = {
        row["FDA_CODE"].strip(): row["IMDRF_CODE"].strip()
        for row in rows
        if row.get("FDA_CODE") and row.get("IMDRF_CODE", "").strip()
    }
    imdrf_to_code: dict[str, str] = {}
    for code, imdrf in code_to_imdrf.items():
        imdrf_to_code.setdefault(imdrf, code)
    parent_map: dict[str, str] = {}
    for code in sorted(observed_codes):
        imdrf = code_to_imdrf.get(code, "")
        prefixes = [
            candidate
            for candidate in imdrf_to_code
            if len(candidate) < len(imdrf) and imdrf.startswith(candidate)
        ]
        if prefixes:
            parent_map[code] = f"IMDRF:{max(prefixes, key=len)}"
    return parent_map, code_to_imdrf


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
