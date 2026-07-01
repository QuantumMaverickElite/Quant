#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd


MODELS = {
    "github_gpt41": {
        "env": Path.home() / ".config/quant/llm_github_models.env",
        "model": "openai/gpt-4.1",
        "sleep": 10,
        "cooldown": 900,
    },
    "github_deepseek_v3": {
        "env": Path.home() / ".config/quant/llm_github_models.env",
        "model": "deepseek/deepseek-v3-0324",
        "sleep": 10,
        "cooldown": 900,
    },
    "github_llama33_70b": {
        "env": Path.home() / ".config/quant/llm_github_models.env",
        "model": "meta/llama-3.3-70b-instruct",
        "sleep": 10,
        "cooldown": 900,
    },
    "github_gpt4o": {
        "env": Path.home() / ".config/quant/llm_github_models.env",
        "model": "openai/gpt-4o",
        "sleep": 10,
        "cooldown": 900,
    },
    "gemini_flash_lite": {
        "env": Path.home() / ".config/quant/llm_gemini.env",
        "model": "gemini-2.5-flash-lite",
        "sleep": 20,
        "cooldown": 1800,
    },
}


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    if path.suffix == ".jsonl":
        return pd.read_json(path, lines=True)
    raise ValueError(f"Unsupported file type: {path}")


def write_outputs(df: pd.DataFrame, out_base: Path) -> None:
    out_base.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_base.with_suffix(".parquet"), index=False)
    df.to_csv(out_base.with_suffix(".csv"), index=False)
    df.to_json(out_base.with_suffix(".jsonl"), orient="records", lines=True)


def load_env_file(path: Path) -> dict[str, str]:
    env = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = shlex.split(v.strip())[0]
    return env


def existing_output(out_base: Path) -> pd.DataFrame:
    for p in [
        out_base.with_suffix(".parquet"),
        out_base.with_suffix(".csv"),
        out_base.with_suffix(".jsonl"),
    ]:
        if p.exists():
            return read_table(p)
    return pd.DataFrame()


def classify_chunk(events_chunk: pd.DataFrame, model_name: str, chunk_id: int, args) -> tuple[bool, pd.DataFrame]:
    cfg = MODELS[model_name]

    work_dir = Path("outputs/intelligence/llm_batch_tmp")
    work_dir.mkdir(parents=True, exist_ok=True)

    chunk_events = work_dir / f"chunk_{chunk_id:04d}_{model_name}_events.parquet"
    chunk_out = work_dir / f"chunk_{chunk_id:04d}_{model_name}_classifications.jsonl"

    events_chunk.to_parquet(chunk_events, index=False)

    env = os.environ.copy()
    env.update(load_env_file(cfg["env"]))
    env["OPENAI_COMPAT_MODEL"] = str(cfg["model"])
    env["PYTHONPATH"] = "src"

    cmd = [
        sys.executable,
        "scripts/classify_event_facts_llm.py",
        "--events", str(chunk_events),
        "--mode", "api",
        "--max-rows", str(len(events_chunk)),
        "--force",
        "--out", str(chunk_out),
        "--sleep-seconds", str(cfg["sleep"]),
        "--text-limit", str(args.text_limit),
    ]

    if args.no_response_format:
        cmd.append("--no-response-format")

    print()
    print(f"== chunk {chunk_id} using {model_name}: {cfg['model']} ==")
    print(" ".join(shlex.quote(x) for x in cmd))

    try:
        proc = subprocess.run(
            cmd,
            env=env,
            text=True,
            timeout=args.chunk_timeout,
        )
        ok = proc.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"chunk timed out after {args.chunk_timeout:.1f}s")
        ok = False

    frames = []

    final_p = chunk_out.with_suffix(".parquet")
    partial_p = final_p.with_name(final_p.stem + "_partial.parquet")

    if final_p.exists():
        frames.append(pd.read_parquet(final_p))
    if partial_p.exists():
        frames.append(pd.read_parquet(partial_p))

    got = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return ok, got


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--chunk-size", type=int, default=2)
    parser.add_argument("--max-chunks", type=int, default=1)
    parser.add_argument("--cooldown-between-chunks", type=float, default=300)
    parser.add_argument("--text-limit", type=int, default=3500)
    parser.add_argument("--models", default="github_gpt41,github_deepseek_v3,github_llama33_70b,github_gpt4o")
    parser.add_argument("--no-response-format", action="store_true")
    parser.add_argument("--chunk-timeout", type=float, default=600)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    events = read_table(Path(args.events))
    events["event_id"] = events["event_id"].astype(str)

    out_base = Path(args.out)
    existing = existing_output(out_base)

    if len(existing):
        existing["event_id"] = existing["event_id"].astype(str)
        done = set(existing["event_id"])
    else:
        done = set()

    remaining = events[~events["event_id"].isin(done)].copy()
    model_names = [m.strip() for m in args.models.split(",") if m.strip()]

    print("== LLM batch runner ==")
    print("input rows:", len(events))
    print("already classified:", len(done))
    print("remaining:", len(remaining))
    print("chunk size:", args.chunk_size)
    print("max chunks:", args.max_chunks)
    print("models:", ", ".join(model_names))

    if args.dry_run:
        cols = [c for c in ["event_id", "ticker", "event_time", "provider", "sample_bucket", "title"] if c in remaining.columns]
        print()
        print(remaining[cols].head(args.chunk_size * args.max_chunks).to_string(index=False))
        return

    frames = []
    if len(existing):
        frames.append(existing)

    cooldown_until = {m: 0.0 for m in model_names}
    chunks_done = 0
    chunk_id = 1

    while chunks_done < args.max_chunks:
        current = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        done = set(current["event_id"].astype(str)) if len(current) else set()
        remaining = events[~events["event_id"].isin(done)].copy()

        if remaining.empty:
            print("all rows classified")
            break

        available = [m for m in model_names if cooldown_until.get(m, 0.0) <= time.time()]
        if not available:
            wait = max(1, min(cooldown_until.values()) - time.time())
            print(f"all models cooling down; sleeping {wait:.1f}s")
            time.sleep(wait)
            continue

        model_name = available[0]
        chunk = remaining.head(args.chunk_size).copy()

        ok, got = classify_chunk(chunk, model_name, chunk_id, args)

        if len(got):
            got["event_id"] = got["event_id"].astype(str)
            frames.append(got)

            merged = pd.concat(frames, ignore_index=True)
            merged = merged.drop_duplicates("event_id", keep="last")
            write_outputs(merged, out_base)

            print(f"saved cumulative rows: {len(merged)}")

        if ok:
            chunks_done += 1
            chunk_id += 1
            if chunks_done < args.max_chunks:
                print(f"cooldown between chunks: {args.cooldown_between_chunks:.1f}s")
                time.sleep(args.cooldown_between_chunks)
        else:
            cooldown = MODELS[model_name]["cooldown"]
            cooldown_until[model_name] = time.time() + cooldown
            print(f"{model_name} failed; cooling down for {cooldown}s")
            chunk_id += 1
            time.sleep(30)

    final = existing_output(out_base)
    print()
    print("== final ==")
    print("rows written:", len(final))
    if len(final) and "classifier_model" in final.columns:
        print(final["classifier_model"].value_counts().to_string())


if __name__ == "__main__":
    main()
