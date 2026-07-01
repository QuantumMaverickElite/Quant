from __future__ import annotations

import os
import re
import sys
from pathlib import Path

SECRET_ENV_NAMES = [
    "ALPHA_VANTAGE_API_KEY",
    "FINNHUB_API_KEY",
    "NEWSAPI_KEY",
    "NEWS_API_KEY",
    "POLYGON_API_KEY",
    "MASSIVE_API_KEY",
    "OPENAI_COMPAT_API_KEY",
]


def parse_env_file(path: Path) -> dict[str, str]:
    out = {}

    if not path.exists():
        return out

    for raw in path.read_text(errors="ignore").splitlines():
        line = raw.strip()

        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[len("export "):].strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            out[key] = value

    return out


def collect_secrets() -> list[str]:
    values = []

    for name in SECRET_ENV_NAMES:
        value = os.environ.get(name, "").strip()
        if len(value) >= 6:
            values.append(value)

    config_dir = Path.home() / ".config" / "quant"
    for path in config_dir.glob("*.env"):
        env_values = parse_env_file(path)
        for name in SECRET_ENV_NAMES:
            value = env_values.get(name, "").strip()
            if len(value) >= 6:
                values.append(value)

    deduped = []
    seen = set()
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)

    return deduped


SECRETS = collect_secrets()


def redact(text: str) -> str:
    for secret in SECRETS:
        text = text.replace(secret, "<redacted>")

    text = re.sub(
        r"(?i)(api\s*key\s*(?:as|is|=|:)?\s*)[A-Za-z0-9_\-]{6,}",
        r"\1<redacted>",
        text,
    )

    text = re.sub(
        r"(?i)((?:apikey|api_key|token|secret|access_key|apiKey)=)[^&\s]+",
        r"\1<redacted>",
        text,
    )

    text = re.sub(
        r"(?i)((?:ALPHA_VANTAGE_API_KEY|FINNHUB_API_KEY|NEWSAPI_KEY|NEWS_API_KEY|POLYGON_API_KEY|MASSIVE_API_KEY|OPENAI_COMPAT_API_KEY)=)[^\s]+",
        r"\1<redacted>",
        text,
    )

    return text


for line in sys.stdin:
    sys.stdout.write(redact(line))
    sys.stdout.flush()
