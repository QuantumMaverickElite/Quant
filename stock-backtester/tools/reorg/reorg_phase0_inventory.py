#!/usr/bin/env python3
"""Build deterministic Phase 0 authority, script, contract, and overlay maps.

This tool is deliberately dependency-free and conservative.  It reads Git
metadata plus bounded source/documentation trees; it does not import project
code, contact providers, inspect environments, or enumerate bulk outputs/data.
It is an extension of the existing ``reorg_*`` audit tools, not a production
pipeline.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Iterable


SKIP_PARTS = {
    ".git",
    ".venv",
    ".vnev",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "outputs",
    "data",
    "target",
    "node_modules",
}
OVERLAY_RE = re.compile(r"^market_intelligence_.*_overlay$")
TEXT_SUFFIXES = {".py", ".sh", ".md", ".rst", ".txt", ".json", ".toml", ".yaml", ".yml"}
OVERLAY_SUFFIXES = TEXT_SUFFIXES | {".lock", ".cfg"}
OUTPUT_RE = re.compile(r"(?:outputs|data/intelligence|rust_engine/target|/tmp/quant_[A-Za-z0-9_.-]+)(?:/[A-Za-z0-9_{}.$%+=:@,~*?/-]+)?")
SCRIPT_REF_RE = re.compile(r"(?:scripts|visuals)/[A-Za-z0-9_./-]+\.(?:py|sh)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="stock-backtester root")
    parser.add_argument(
        "--manifest-dir",
        default="docs/reorg",
        help="Tracked manifest directory, relative to --root",
    )
    return parser.parse_args()


def git_bytes(root: Path, *args: str) -> bytes:
    try:
        return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return b""


def tracked_paths(root: Path) -> list[str]:
    raw = git_bytes(root, "ls-files", "-z")
    if raw:
        return sorted(p.decode("utf-8", "replace") for p in raw.split(b"\0") if p)
    return sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and not any(part in SKIP_PARTS for part in p.relative_to(root).parts)
    )


def safe_walk(root: Path, *, include_overlays: bool = False) -> Iterable[Path]:
    """Walk source-sized trees only; excluded bulk trees are never descended."""
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        kept: list[str] = []
        for name in dirs:
            if name in SKIP_PARTS:
                continue
            if not include_overlays and OVERLAY_RE.match(name):
                continue
            kept.append(name)
        dirs[:] = sorted(kept)
        for name in sorted(files):
            path = current_path / name
            if path.is_file():
                yield path


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_write(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def source_texts(root: Path, paths: list[str]) -> dict[str, str]:
    return {
        rel: read_text(root / rel)
        for rel in paths
        if Path(rel).suffix.lower() in TEXT_SUFFIXES
    }


def imports_for(text: str) -> list[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return sorted(found)


def output_refs(text: str) -> list[str]:
    refs: set[str] = set()
    for match in OUTPUT_RE.finditer(text):
        token = match.group(0).rstrip("'\"`),.;}]")
        if token:
            refs.add(token)
    return sorted(refs)


def script_refs(text: str) -> list[str]:
    return sorted(set(SCRIPT_REF_RE.findall(text)))


def subsystem_for(path: str, imports: list[str]) -> str:
    value = f"{path} {' '.join(imports)}".lower()
    checks = [
        ("intelligence", ("intelligence", "event_", "llm", "news", "worker")),
        ("market_fabric", ("market_fabric", "market_graph", "visual")),
        ("correlation_deformation", ("correlation", "peer_", "deformation", "spread")),
        ("mean_reversion", ("mean_reversion", "signals")),
        ("allocator_matrix", ("allocator", "threshold", "matrix")),
        ("rust_stress", ("rust", "stress")),
        ("market_state", ("market_state", "entropy", "volatility", "garch", "context")),
        ("dividend_capture", ("dividend",)),
        ("options_volatility", ("options",)),
        ("reorganization", ("reorg", "sacred")),
    ]
    for name, needles in checks:
        if any(needle in value for needle in needles):
            return name
    return "general"


def classify_script(path: str, text: str, refs: list[str], sacred: bool) -> tuple[str, str, str]:
    lower = path.lower()
    stem = Path(path).stem.lower()
    if "/archive/" in lower or "/legacy/" in lower:
        return "ARCHIVED / HISTORICAL", "HIGH", "archive/legacy path; preserved explicitly"
    if "/workers/" in lower or stem.startswith("run_worker"):
        return "WORKER / REMOTE TOOLING", "HIGH", "worker path or remote shell reference"
    if sacred:
        return "COMMAND / ENTRY POINT", "HIGH", "listed in configs/sacred_scripts.json"
    if stem.startswith(("test_", "smoke_")):
        return "TEST / SMOKE", "HIGH", "test/smoke naming plus executable script"
    if stem.startswith("reorg_") or stem.startswith(("audit_", "compact_", "prune_", "archive_")):
        return "MAINTENANCE TOOL", "HIGH", "audit/maintenance behavior"
    if any(word in stem for word in ("visual", "plot", "render", "market_fabric", "graph_fabric")):
        return "VISUALIZATION", "MEDIUM", "visualization imports/paths or documented frame workflow"
    if any(word in stem for word in ("train", "calibrat", "classif", "label_", "launch_long", "monitor_long", "walk_forward")):
        return "TRAINING", "MEDIUM", "training/classification/calibration behavior"
    if any(word in stem for word in ("fetch", "download", "collect", "source", "parse_cbworker", "normalize_worker")):
        return "DATA INGESTION", "MEDIUM", "source/download/normalization behavior"
    if any(word in stem for word in ("build_", "merge_", "join_", "extract_", "resolve_", "apply_", "create_", "export_")):
        return "DATA TRANSFORMATION", "MEDIUM", "derived-table or export behavior"
    if any(word in stem for word in ("compare", "benchmark", "evaluate", "inspect", "diagnose", "summarize", "score", "validate", "monte_carlo", "stress")):
        return "EVALUATION / BENCHMARK", "MEDIUM", "comparison, diagnostics, or stress behavior"
    if stem.startswith(("run_", "backtest_")):
        role = "PIPELINE ORCHESTRATOR" if refs else "COMMAND / ENTRY POINT"
        return role, "MEDIUM", "run/backtest entry point with static references"
    return "UNCERTAIN", "LOW", "no sufficiently strong static role evidence"


def sacred_commands(root: Path) -> set[str]:
    path = root / "configs" / "sacred_scripts.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    result: set[str] = set()
    for command in payload.get("commands", []):
        match = re.search(r"(?:python(?:3)?\s+)?(scripts/[A-Za-z0-9_./-]+\.(?:py|sh))", command.get("command", ""))
        if match:
            result.add(match.group(1))
    return result


def build_script_rows(root: Path, paths: list[str]) -> list[dict[str, object]]:
    scripts = [p for p in paths if p.startswith("scripts/") and Path(p).suffix.lower() in {".py", ".sh"}]
    texts = source_texts(root, paths)
    sacred = sacred_commands(root)
    reverse_refs: dict[str, set[str]] = defaultdict(set)
    docs = {p: t for p, t in texts.items() if p.startswith("docs/")}
    for source, text in texts.items():
        for ref in script_refs(text):
            reverse_refs[ref].add(source)
    rows: list[dict[str, object]] = []
    for path in sorted(scripts):
        text = texts.get(path, read_text(root / path))
        imports = imports_for(text)
        refs = script_refs(text)
        refs_to_paths = output_refs(text)
        outputs = [ref for ref in refs_to_paths if ref.startswith("outputs/") or "target" in ref or ref.startswith("/tmp/")]
        inputs = [ref for ref in refs_to_paths if ref not in outputs]
        role, confidence, evidence = classify_script(path, text, refs, path in sacred)
        subsystem = subsystem_for(path, imports)
        docs_ref = sorted(doc for doc, doc_text in docs.items() if Path(path).name in doc_text)
        callers = sorted(reverse_refs.get(path, set()) - {path})
        risk = "HIGH" if path in sacred or "/workers/" in path or outputs and ("rust" in path or "intelligence" in path) else "MEDIUM"
        if role.startswith("ARCHIVED"):
            status = "HISTORICAL"
            destination = "research/history or archive manifest"
        elif role == "WORKER / REMOTE TOOLING":
            status = "ACTIVE / EXTERNAL CONTRACT"
            destination = "pipelines/intelligence or worker tooling"
        elif role == "UNCERTAIN":
            status = "UNCERTAIN"
            destination = "USER DECISION REQUIRED"
        elif role in {"COMMAND / ENTRY POINT", "PIPELINE ORCHESTRATOR"}:
            status = "ACTIVE RESEARCH"
            destination = "scripts compatibility wrapper + src/quant_research/pipelines"
        else:
            status = "ACTIVE RESEARCH"
            destination = "src/quant_research or research/experiments"
        rows.append({
            "path": path,
            "classification": role,
            "subsystem": subsystem,
            "status": status,
            "imports": ";".join(imports),
            "input_paths": ";".join(inputs),
            "output_paths": ";".join(outputs),
            "invoked_by": ";".join(callers),
            "docs_references": ";".join(docs_ref),
            "sacred": "yes" if path in sacred else "no",
            "migration_risk": risk,
            "likely_destination": destination,
            "confidence": confidence,
            "evidence": evidence,
        })
    return rows


SUBSYSTEMS = [
    ("packaged backtester", "src/backtester/cli.py;src/backtester/engines/position_engine.py;src/backtester/engines/event_engine.py", "src/backtester/cli.py", "ACTIVE CORE", "HIGH", "prices;strategy parameters", "outputs/backtests;outputs/reports", "scripts/test_*;docs/systems", "scripts/legacy;older CLI history", "medium", "Stable original CLI, not the sole entry point for newer research.", ""),
    ("mean-reversion signals", "src/backtester/signals/mean_reversion.py", "scripts/run_mean_reversion_signals.py", "ACTIVE CORE", "HIGH", "peer_spreads.parquet", "outputs/signals/*.parquet", "context/deformation/intelligence scripts", "older standalone signal scripts", "high", "Canonical builder is clear; adjustment layers remain separate.", ""),
    ("volatility/GARCH", "src/backtester/analytics/volatility.py;src/backtester/analytics/fast_volatility.py", "src/backtester/analytics/volatility.py", "ACTIVE CORE", "HIGH", "price series", "volatility metric tables", "decision and MarketState modules", "legacy garch import names", "medium", "Several scripts retain compatibility imports for old module names.", ""),
    ("entropy", "src/backtester/analytics/entropy.py", "src/backtester/analytics/entropy.py", "ACTIVE CORE", "HIGH", "returns", "entropy metrics and decisions", "decision/market_context", "older MarketState scripts", "medium", "Reusable feature layer.", ""),
    ("market context", "src/backtester/context/market_context.py;src/backtester/decision/market_state.py", "scripts/run_market_context_features.py", "REUSABLE INFRASTRUCTURE", "HIGH", "prices, volatility, entropy", "outputs/context/*.parquet", "mean-reversion and allocator scripts", "older MarketState runners", "high", "Context and MarketState overlap conceptually but should not be merged yet.", ""),
    ("correlation/deformation", "src/backtester/correlation/", "scripts/run_correlation_features.py; scripts/run_regime_correlation_features.py", "ACTIVE RESEARCH", "HIGH", "price/returns matrices", "outputs/correlation/*.parquet;outputs/context/*deformation*", "peer spreads, signals, market fabric", "correlation tracker predecessors", "high", "Current reusable correlation package plus script orchestration.", ""),
    ("large-universe pipeline", "scripts/build_universe.py;scripts/export_rust_matrix_inputs.py;scripts/export_returns_matrix.py;scripts/large_universe_peer_search.py;scripts/generate_peer_basket_spreads.py", "scripts/export_rust_matrix_inputs.py", "ACTIVE RESEARCH", "HIGH", "universe files, binary matrices", "matrix metadata, peers, spreads, Rust inputs", "Rust stress; market fabric", "small-universe mean-reversion path", "high", "Standalone matrix-oriented workflow with literal temp paths and schemas.", ""),
    ("matrix allocator", "src/backtester/engines/matrix_allocator_engine.py", "scripts/threshold_rebalance_matrix_engine.py", "REUSABLE INFRASTRUCTURE", "HIGH", "feature/price matrices", "threshold summaries and curves", "benchmark and Monte Carlo scripts", "threshold_rebalance_fast_v2/v3", "high", "Reusable bridge, not final allocator.", ""),
    ("Python Monte Carlo", "scripts/monte_carlo_from_feature_matrix.py;scripts/monte_carlo_market_state.py;scripts/monte_carlo_strategy_grid.py;scripts/monte_carlo_allocator_intelligence.py", "family-specific runners", "ACTIVE RESEARCH", "MEDIUM", "features, prices, signals", "outputs/monte_carlo/*", "scorecards and reports", "older one-off Monte Carlo scripts", "medium", "Legitimate distinct families; do not consolidate yet.", ""),
    ("Rust stress engine", "rust_engine/src/", "rust_engine stress_mc; scripts/export_rust_*", "REUSABLE INFRASTRUCTURE", "HIGH", "binary prices, orders CSV, metadata", "outputs/rust_stress/*", "stress summaries and plots", "earlier Rust engine commits", "high", "Python/Rust schema boundary.", ""),
    ("market fabric", "visuals/build_market_graph_frames.py;visuals/visualize_market_graph_fabric.py", "scripts/run_combined_allocator_market_fabric_latest.sh", "ACTIVE RESEARCH", "HIGH", "returns, signals, context, overlays", "outputs/market_graph_fabric_frames;reports/plots", "visualizer and overlay augmenters", "scripts/archive/visual_experiments", "high", "Current visualization descendant; stress contains forward information.", ""),
    ("operational heuristic intelligence", "src/backtester/intelligence/intelligence_engine.py;src/backtester/intelligence/batch.py", "scripts/run_market_intelligence_live.py", "OPERATIONAL FALLBACK", "HIGH", "provider documents, price risk", "outputs/intelligence/*.json/csv", "signal integration and live workflows", "market_intelligence v1-v5 families", "high", "Still protected; legacy status must be user-confirmed.", "USER DECISION REQUIRED: still operational?"),
    ("event-learning intelligence research", "src/backtester/intelligence/event_fact_table.py;event_outcome_labels.py;event_impact_dataset.py;event_day_impact_dataset.py", "scripts/run_worker_sources_to_events.sh; scripts/train_event_day_baseline.py", "ACTIVE RESEARCH", "HIGH", "normalized worker/news rows, prices", "outputs/intelligence/event_*", "LLM join and training", "heuristic intelligence", "high", "Current branch direction; not allocator-promoted.", ""),
    ("NLP/LLM feature generation", "src/backtester/intelligence/llm_event_classifier.py;llm_feature_join.py", "scripts/classify_event_facts_llm.py", "ACTIVE RESEARCH", "HIGH", "event fact tables", "LLM classification/join tables", "event-day dataset", "local semantic/NLP classifiers", "high", "LLM extracts features; it does not allocate.", ""),
    ("training", "src/backtester/intelligence/walk_forward_calibrator.py;scripts/run_intelligence_training_batch.py;scripts/launch_long_intelligence_training.py", "scripts/launch_long_intelligence_training.py; scripts/train_event_day_baseline.py", "ACTIVE RESEARCH", "MEDIUM", "labeled features and event datasets", "training_runs, reports, predictions", "promotion gates and summaries", "v4-v5 training families", "high", "Old path is developed; new event baseline is a smoke test.", ""),
    ("dividend capture", "dividend-capture/src/;src/backtester/strategies/event_strategies.py", "dividend-capture/src/*/backtest.py;src/backtester/cli.py", "ACTIVE RESEARCH", "HIGH", "dividend and price data", "dividend outputs and trade frames", "standalone findings and event engine", "original/PG-like experiment families", "medium", "Two valid ownership contexts remain.", "USER DECISION REQUIRED: unify or preserve separately?"),
    ("survivable volatility", "src/features/survivable_volatility.py", "scripts/apply_survivable_volatility.py", "ACTIVE RESEARCH", "MEDIUM", "price and market-cap features", "survivable-volatility signals", "signal creation/backtests", "earlier volatility experiments", "medium", "Current code sits outside the installable package.", ""),
    ("workers", "scripts/workers/;worker_ingest/", "scripts/workers/run_*worker.sh", "OPERATIONAL FALLBACK", "HIGH", "remote worker/source payloads", "worker_ingest cache and normalized sources", "event-learning ingestion", "earlier Chromebook worker bundles", "high", "Remote host, SSH, redaction, and local exclude assumptions.", "USER DECISION REQUIRED: permanent dependency?"),
    ("visualization", "visuals/;src/backtester/visuals/", "visuals/visualize_market_graph_fabric.py", "ACTIVE RESEARCH", "HIGH", "signals, frames, summaries", "plots, frames, media", "market fabric and reports", "scripts/archive/visual_experiments", "medium", "Separate interactive visualization from trading logic.", ""),
]


def build_subsystem_rows() -> list[dict[str, str]]:
    fields = ["subsystem", "canonical_paths", "primary_entries", "status", "authority_confidence", "major_inputs", "major_outputs", "callers_consumers", "historical_descendants", "migration_risk", "notes", "user_decision"]
    return [dict(zip(fields, row)) for row in SUBSYSTEMS]


KNOWN_CONTRACTS = [
    ("outputs/signals/", "signal tables", "intermediate pipeline contract; selected files are research evidence", "high"),
    ("outputs/context/", "context and deformation tables", "intermediate pipeline contract", "high"),
    ("outputs/correlation/", "correlation, peers, spreads", "intermediate pipeline contract", "high"),
    ("outputs/intelligence/", "reports, event datasets, training runs", "mixed: contract, evidence, and cache", "high"),
    ("outputs/threshold_rebalance/", "allocator trials and summaries", "research evidence; compact selected baselines", "medium"),
    ("outputs/rust_inputs/", "Rust binary inputs and metadata", "cross-language contract", "high"),
    ("outputs/rust_stress/", "Rust stress runs", "research evidence plus regenerable runs", "high"),
    ("outputs/market_fabric/", "allocator/trade overlays", "visualization contract", "high"),
    ("outputs/market_graph_fabric_frames/", "frame caches and summaries", "generated visualization artifact; selected runs preserve evidence", "high"),
    ("outputs/intelligence/training_runs/", "walk-forward predictions and manifests", "research evidence; retention requires explicit promotion", "high"),
    ("outputs/monte_carlo/", "simulation summaries and paths", "mixed; summaries evidence, paths regenerable", "medium"),
    ("outputs/feature_matrix/", "feature/price matrices", "intermediate contract and selected baseline", "high"),
    ("outputs/backtests/", "portfolio/trade/equity outputs", "research evidence", "medium"),
    ("outputs/reorg_audit/", "audit reports", "regenerable audit output", "low"),
]


def build_contract_rows(root: Path, paths: list[str]) -> list[dict[str, object]]:
    texts = source_texts(root, paths)
    rows: list[dict[str, object]] = []
    for prefix, kind, handling, risk in KNOWN_CONTRACTS:
        producers: set[str] = set()
        consumers: set[str] = set()
        refs: set[str] = set()
        for path, text in texts.items():
            found = [ref for ref in output_refs(text) if ref.startswith(prefix)]
            if not found:
                continue
            refs.update(found)
            lower = text.lower()
            if any(word in lower for word in ("to_csv", "to_parquet", "write_text", "tofile", "out_path", "out-dir", "output_dir")):
                producers.add(path)
            else:
                consumers.add(path)
        if producers and consumers:
            consumers -= producers
        rows.append({
            "path_pattern": prefix,
            "contract_family": kind,
            "producers": ";".join(sorted(producers)),
            "consumers": ";".join(sorted(consumers)),
            "formats_seen": ";".join(sorted({Path(ref).suffix.lower() for ref in refs if Path(ref).suffix})),
            "hard_coded_reference": "yes" if refs else "documented/default path",
            "generated": "yes",
            "reproducibility_role": handling,
            "regeneration_safety": "unknown until manifest/input hashes exist" if risk == "high" else "likely regenerable",
            "migration_risk": risk,
            "notes": "Do not move until producers, consumers, and schemas have compatibility tests.",
        })
    return rows


def overlay_roots(project: Path, repo: Path) -> list[Path]:
    roots = [p for p in project.iterdir() if p.is_dir() and OVERLAY_RE.match(p.name)]
    roots += [p for p in repo.iterdir() if p.is_dir() and OVERLAY_RE.match(p.name)]
    return sorted(set(roots), key=lambda p: p.as_posix())


def build_overlay_rows(project: Path, repo: Path, tracked: set[str]) -> list[dict[str, object]]:
    overlays = overlay_roots(project, repo)
    rows: list[dict[str, object]] = []
    canonical_paths: set[str] = set()
    for overlay in overlays:
        # Internal overlays are relative to stock-backtester; root overlays are
        # relative to the repository root.  Keeping that distinction prevents
        # root-level ignored overlays from crashing the inventory walk.
        base = project if overlay.parent == project else repo
        for path in safe_walk(overlay, include_overlays=True):
            if path.suffix.lower() not in OVERLAY_SUFFIXES:
                continue
            rel_inside = path.relative_to(overlay).as_posix()
            canonical_rel = rel_inside
            canonical = base / canonical_rel
            canonical_display = canonical_rel
            if base == repo and project != repo:
                canonical_display = canonical.relative_to(repo).as_posix()
            canonical_paths.add(canonical_display)
            canonical_exists = canonical.is_file()
            overlay_hash = sha256(path)
            canonical_hash = sha256(canonical) if canonical_exists else ""
            if not canonical_exists:
                relation = "CANONICAL MISSING"
                priority = "HIGH"
            elif overlay_hash == canonical_hash:
                relation = "IDENTICAL"
                priority = "LOW"
            else:
                relation = "DIFFERENT"
                priority = "HIGH" if path.suffix.lower() in {".py", ".sh", ".toml"} else "MEDIUM"
            rows.append({
                "overlay_path": path.relative_to(base).as_posix(),
                "version": overlay.name,
                "file_path": rel_inside,
                "canonical_destination": canonical_display,
                "canonical_exists": "yes" if canonical_exists else "no",
                "overlay_sha256": overlay_hash,
                "canonical_sha256": canonical_hash,
                "relationship": relation,
                "canonical_tracked": "yes" if base == project and canonical_rel in tracked else "no",
                "canonical_git_history_appears": "yes" if base == project and canonical_rel in tracked else "unknown",
                "preservation_priority": priority,
                "notes": "Overlay source is ignored by Git; preserve before any archival decision.",
            })
    return sorted(rows, key=lambda row: (str(row["overlay_path"]), str(row["file_path"])))


def physical_inventory(project: Path, repo: Path) -> list[dict[str, object]]:
    candidates = [
        ("stock-backtester/.venv", "PYTHON ENVIRONMENT"),
        ("stock-backtester/.vnev", "PYTHON ENVIRONMENT"),
        ("stock-backtester/outputs", "GENERATED OUTPUT"),
        ("stock-backtester/data", "DATA / CACHE"),
        ("stock-backtester/rust_engine/target", "RUST BUILD PRODUCT"),
        ("stock-backtester/archive", "ARCHIVE / REPRODUCIBILITY"),
        ("worker_ingest", "DATA / CACHE"),
    ]
    rows = []
    for display, category in candidates:
        path = repo / display
        rows.append({
            "path": display,
            "category": category,
            "exists": "yes" if path.exists() else "no",
            "scanned_file_by_file": "no",
            "notes": "Presence recorded without descending into bulk contents.",
        })
    for path in overlay_roots(project, repo):
        rows.append({
            "path": path.relative_to(repo).as_posix(),
            "category": "OVERLAY",
            "exists": "yes",
            "scanned_file_by_file": "bounded source/doc scan",
            "notes": "Patch source and documentation only.",
        })
    return rows


def write_markdown(manifest_dir: Path, name: str, title: str, rows: list[dict[str, object]], columns: list[str], intro: str) -> None:
    lines = [f"# {title}", "", intro, "", f"Machine-readable source: `{name}.csv`", "", "| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    for row in rows:
        values = [str(row.get(column, "")).replace("|", "\\|").replace("\n", " ") for column in columns]
        lines.append("| " + " | ".join(values) + " |")
    output_names = {
        "scripts": "SCRIPT_INVENTORY.md",
        "output_contracts": "OUTPUT_CONTRACTS.md",
        "overlay_lineage": "OVERLAY_LINEAGE.md",
    }
    (manifest_dir / output_names.get(name, f"{name.upper()}.md")).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    project = Path(args.root).resolve()
    repo = project.parent if project.name == "stock-backtester" else project
    if not (project / "scripts").exists() and (repo / "stock-backtester").is_dir():
        project = repo / "stock-backtester"
    manifest_dir = project / args.manifest_dir
    manifest_dir.mkdir(parents=True, exist_ok=True)
    paths = tracked_paths(project)
    tracked = set(paths)
    subsystem_rows = build_subsystem_rows()
    script_rows = build_script_rows(project, paths)
    contract_rows = build_contract_rows(project, paths)
    overlay_rows = build_overlay_rows(project, repo, tracked)
    inventory_rows = physical_inventory(project, repo)

    csv_write(manifest_dir / "subsystems.csv", list(subsystem_rows[0]), subsystem_rows)
    csv_write(manifest_dir / "scripts.csv", list(script_rows[0]), script_rows)
    csv_write(manifest_dir / "output_contracts.csv", list(contract_rows[0]), contract_rows)
    csv_write(manifest_dir / "overlay_lineage.csv", list(overlay_rows[0]), overlay_rows)
    csv_write(manifest_dir / "physical_inventory.csv", list(inventory_rows[0]), inventory_rows)

    inventory = {
        "project_root": "stock-backtester",
        "tracked_file_count": len(paths),
        "tracked_python_count": sum(Path(p).suffix.lower() == ".py" for p in paths),
        "tracked_script_count": len(script_rows),
        "tracked_doc_count": sum(p.startswith("docs/") and Path(p).suffix.lower() in {".md", ".rst", ".txt"} for p in paths),
        "tracked_config_count": sum(p.startswith("configs/") for p in paths),
        "overlay_directory_count": len(overlay_roots(project, repo)),
        "overlay_file_count": len(overlay_rows),
        "excluded_bulk_trees": [row["path"] for row in inventory_rows if row["scanned_file_by_file"] == "no"],
        "classification_policy": "bounded source/doc scan; bulk trees represented by directory metadata only",
    }
    (manifest_dir / "repository_inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    write_markdown(manifest_dir, "scripts", "Script Inventory", script_rows, ["path", "classification", "subsystem", "status", "sacred", "migration_risk", "confidence", "likely_destination"], "Classification is evidence-assisted static analysis of imports, references, documentation, path contracts, and directory role. UNCERTAIN means the repository did not provide enough evidence for a safe semantic decision.")
    write_markdown(manifest_dir, "output_contracts", "Output Contracts", contract_rows, ["path_pattern", "contract_family", "producers", "consumers", "formats_seen", "reproducibility_role", "regeneration_safety", "migration_risk"], "These are filesystem interfaces, not proposed destinations. GENERATED does not mean disposable.")
    write_markdown(manifest_dir, "overlay_lineage", "Overlay Lineage", overlay_rows, ["overlay_path", "version", "file_path", "canonical_destination", "relationship", "canonical_tracked", "preservation_priority"], "Overlay files are ignored by Git. No archival or promotion is performed by this tool.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
