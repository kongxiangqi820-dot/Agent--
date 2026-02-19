from __future__ import annotations

import json
from pathlib import Path


def load_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")

    suffix = p.suffix.lower()
    # utf-8-sig handles files saved by Windows tools that include a BOM.
    data = p.read_text(encoding="utf-8-sig")

    if suffix == ".json":
        return json.loads(data)

    if suffix in (".toml", ".tml"):
        try:
            import tomllib  # py>=3.11
        except Exception as e:
            raise RuntimeError("Reading TOML requires Python 3.11+ (tomllib).") from e
        return tomllib.loads(data)

    if suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except Exception as e:
            raise RuntimeError("Reading YAML requires PyYAML: pip install pyyaml") from e
        return yaml.safe_load(data) or {}

    try:
        return json.loads(data)
    except Exception:
        pass

    raise RuntimeError(f"Unsupported config format: {suffix}")
