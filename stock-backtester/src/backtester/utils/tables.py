"""Small, explicit helpers for tabular CSV/Parquet interchange.

This module intentionally covers only the common table contract used by the
research utilities: CSV, Parquet (including ``.pq``), and data-only writes
(``index=False``). Domain-specific schema and index handling stays with the
caller.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TypeAlias

import pandas as pd


PathLike: TypeAlias = str | os.PathLike[str]
_PARQUET_SUFFIXES = frozenset({".parquet", ".pq"})


def _suffix(path: Path) -> str:
    return path.suffix.lower()


def read_table(path: PathLike) -> pd.DataFrame:
    """Read a supported CSV or Parquet table selected by suffix.

    Pandas/engine errors are intentionally propagated unchanged. Unsupported
    suffixes raise ``ValueError`` before touching the filesystem.
    """

    table_path = Path(path)
    suffix = _suffix(table_path)
    if suffix in _PARQUET_SUFFIXES:
        return pd.read_parquet(table_path)
    if suffix == ".csv":
        return pd.read_csv(table_path)
    raise ValueError(f"Unsupported table type: {table_path}")


def write_table(df: pd.DataFrame, path: PathLike) -> None:
    """Write a supported table, creating its parent directory if needed.

    Writes preserve the established research convention of excluding the
    DataFrame index. Unsupported suffixes raise ``ValueError`` before any
    directory is created.
    """

    table_path = Path(path)
    suffix = _suffix(table_path)
    if suffix not in _PARQUET_SUFFIXES and suffix != ".csv":
        raise ValueError(f"Unsupported table type: {table_path}")
    table_path.parent.mkdir(parents=True, exist_ok=True)
    if suffix in _PARQUET_SUFFIXES:
        df.to_parquet(table_path, index=False)
    else:
        df.to_csv(table_path, index=False)
