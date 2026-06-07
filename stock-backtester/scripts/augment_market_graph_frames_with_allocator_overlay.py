# scripts/augment_market_graph_frames_with_allocator_overlay.py

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add allocator visual overlay arrays to cached market graph frames."
    )

    parser.add_argument(
        "--frames-dir",
        required=True,
        help="Existing market graph frames directory containing manifest.json.",
    )
    parser.add_argument(
        "--allocator-overlay",
        default="outputs/market_fabric/allocator_visual_overlay.parquet",
        help="Clean allocator visual overlay parquet.",
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        help="Output augmented frames directory.",
    )
    parser.add_argument("--force", action="store_true")

    return parser.parse_args()


def normalize_ticker(x: object) -> str:
    return str(x).strip().upper().replace(".", "-")


def load_manifest(frames_dir: Path) -> dict:
    path = frames_dir / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text())


def resolve_frame_path(frames_dir: Path, record: dict) -> Path:
    p = Path(record["path"])

    if p.is_absolute() and p.exists():
        return p

    if p.exists():
        return p

    candidate = frames_dir / p
    if candidate.exists():
        return candidate

    raise FileNotFoundError(p)


def load_overlay(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path).copy()

    required = {
        "date",
        "ticker",
        "final_signal_score",
        "allocator_rank",
        "node_size_score",
        "node_alpha_score",
        "is_top_1_allocator_pick",
        "is_top_3_allocator_pick",
        "is_top_5_allocator_pick",
        "fabric_edge_mode",
        "fabric_node_role",
        "compression_state",
        "market_compression_score",
    }

    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Allocator overlay missing columns: {sorted(missing)}")

    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["ticker"] = df["ticker"].map(normalize_ticker)

    return df


def frame_date(data: dict) -> pd.Timestamp:
    raw = data.get("date")

    if raw is None:
        raise ValueError("Frame missing date array/key.")

    if isinstance(raw, np.ndarray):
        if raw.shape == ():
            raw = raw.item()
        elif len(raw):
            raw = raw.tolist()
        else:
            raise ValueError("Frame date array is empty.")

    return pd.Timestamp(str(raw)).normalize()


def as_str_array(values: list[str]) -> np.ndarray:
    return np.array(values, dtype=object)


def augment_one_frame(
    source_path: Path,
    output_path: Path,
    overlay: pd.DataFrame,
) -> dict:
    npz = np.load(source_path, allow_pickle=True)
    data = {k: npz[k] for k in npz.files}

    date = frame_date(data)
    tickers = [normalize_ticker(x) for x in data["tickers"].tolist()]
    n = len(tickers)

    today = overlay[overlay["date"].eq(date)].copy()

    by_ticker = {
        normalize_ticker(row.ticker): row
        for row in today.itertuples(index=False)
    }

    final_signal_score = np.zeros(n, dtype=np.float32)
    allocator_rank = np.full(n, np.nan, dtype=np.float32)
    node_size_score = np.zeros(n, dtype=np.float32)
    node_alpha_score = np.zeros(n, dtype=np.float32)

    is_top_1 = np.zeros(n, dtype=bool)
    is_top_3 = np.zeros(n, dtype=bool)
    is_top_5 = np.zeros(n, dtype=bool)

    fabric_edge_mode: list[str] = []
    fabric_node_role: list[str] = []
    compression_state: list[str] = []

    market_compression_score = np.full(n, np.nan, dtype=np.float32)

    matched = 0

    for i, ticker in enumerate(tickers):
        row = by_ticker.get(ticker)

        if row is None:
            fabric_edge_mode.append("normal_edges")
            fabric_node_role.append("neutral")
            compression_state.append("UNKNOWN")
            continue

        matched += 1

        final_signal_score[i] = float(row.final_signal_score)
        allocator_rank[i] = float(row.allocator_rank)
        node_size_score[i] = float(row.node_size_score)
        node_alpha_score[i] = float(row.node_alpha_score)

        is_top_1[i] = bool(row.is_top_1_allocator_pick)
        is_top_3[i] = bool(row.is_top_3_allocator_pick)
        is_top_5[i] = bool(row.is_top_5_allocator_pick)

        fabric_edge_mode.append(str(row.fabric_edge_mode))
        fabric_node_role.append(str(row.fabric_node_role))
        compression_state.append(str(row.compression_state))

        market_compression_score[i] = float(row.market_compression_score)

    data["allocator_final_signal_score"] = final_signal_score
    data["allocator_rank"] = allocator_rank
    data["allocator_node_size_score"] = node_size_score
    data["allocator_node_alpha_score"] = node_alpha_score
    data["allocator_is_top_1"] = is_top_1
    data["allocator_is_top_3"] = is_top_3
    data["allocator_is_top_5"] = is_top_5
    data["allocator_fabric_edge_mode"] = as_str_array(fabric_edge_mode)
    data["allocator_fabric_node_role"] = as_str_array(fabric_node_role)
    data["allocator_compression_state"] = as_str_array(compression_state)
    data["allocator_market_compression_score"] = market_compression_score
    data["allocator_overlay_matched"] = np.array(matched, dtype=np.int32)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_path, **data)

    return {
        "frame": output_path.name,
        "date": str(date.date()),
        "nodes": n,
        "matched": matched,
        "match_rate": matched / max(1, n),
    }


def main() -> None:
    args = parse_args()

    frames_dir = Path(args.frames_dir)
    out_dir = Path(args.out_dir)

    if out_dir.exists():
        if not args.force:
            raise FileExistsError(
                f"{out_dir} already exists. Use --force to overwrite."
            )
        shutil.rmtree(out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(frames_dir)
    overlay = load_overlay(Path(args.allocator_overlay))

    new_records = []
    reports = []

    for i, record in enumerate(manifest["frames"]):
        src = resolve_frame_path(frames_dir, record)
        out_name = src.name
        dst = out_dir / out_name

        report = augment_one_frame(src, dst, overlay)
        reports.append(report)

        new_record = dict(record)
        new_record["path"] = str(dst)
        new_records.append(new_record)

        if (i + 1) % 25 == 0 or i == 0:
            print(
                f"[{i + 1:04d}/{len(manifest['frames']):04d}] "
                f"{report['date']} matched={report['matched']}/{report['nodes']}"
            )

    new_manifest = dict(manifest)
    new_manifest["frames"] = new_records
    new_manifest.setdefault("parameters", {})
    new_manifest["parameters"]["allocator_overlay"] = str(Path(args.allocator_overlay))
    new_manifest["parameters"]["allocator_overlay_augmented"] = True

    (out_dir / "manifest.json").write_text(json.dumps(new_manifest, indent=2))

    report_df = pd.DataFrame(reports)
    report_path = out_dir / "allocator_overlay_augmentation_report.csv"
    report_df.to_csv(report_path, index=False)

    print()
    print(f"Saved augmented frames -> {out_dir}")
    print(f"Saved manifest -> {out_dir / 'manifest.json'}")
    print(f"Saved report -> {report_path}")
    print()
    print(report_df.tail(20).to_string(index=False))


if __name__ == "__main__":
    main()
