from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any


_FRONTMATTER_RE = re.compile(r"^\ufeff?---\s*\r?\n(.*?)\r?\n---\s*\r?\n?(.*)$", re.DOTALL)


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    triggers: tuple[str, ...]
    path: Path


class SkillStore:
    def __init__(self, *, skills: list[Skill], max_active: int, allow_name_match: bool) -> None:
        self.skills = skills
        self.max_active = max(1, max_active)
        self.allow_name_match = allow_name_match

    def match(self, user_input: str) -> list[Skill]:
        text = (user_input or "").strip()
        if not text:
            return []

        text_l = text.lower()
        out: list[Skill] = []
        for skill in self.skills:
            if self._is_match(skill, text_l):
                out.append(skill)
            if len(out) >= self.max_active:
                break
        return out

    def _is_match(self, skill: Skill, text_l: str) -> bool:
        skill_name_l = skill.name.lower()
        if f"${skill_name_l}" in text_l:
            return True
        if self.allow_name_match and skill_name_l in text_l:
            return True

        for trigger in skill.triggers:
            trigger_l = trigger.strip().lower()
            if trigger_l and trigger_l in text_l:
                return True
        return False

    @staticmethod
    def render_instructions(active_skills: list[Skill]) -> str:
        if not active_skills:
            return ""

        blocks: list[str] = []
        for skill in active_skills:
            blocks.append(
                "\n".join(
                    [
                        f"[Skill: {skill.name}]",
                        f"Description: {skill.description}",
                        "Instructions:",
                        skill.body.strip(),
                    ]
                ).strip()
            )
        return "\n\n".join(blocks).strip()


def load_skill_store(skills_cfg: dict[str, Any], *, config_dir: Path) -> SkillStore | None:
    enabled = bool(skills_cfg.get("enabled", False))
    if not enabled:
        return None

    rel_dir = str(skills_cfg.get("dir") or "skills").strip()
    skills_dir = (config_dir / rel_dir).resolve()

    if not skills_dir.exists() or not skills_dir.is_dir():
        return SkillStore(skills=[], max_active=1, allow_name_match=True)

    max_active = _to_int(skills_cfg.get("max_active"), 2)
    allow_name_match = bool(skills_cfg.get("allow_name_match", True))

    skills: list[Skill] = []
    for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
        parsed = _parse_skill_file(skill_file)
        if parsed is not None:
            skills.append(parsed)

    return SkillStore(
        skills=skills,
        max_active=max_active,
        allow_name_match=allow_name_match,
    )


def compose_prompt_with_skills(base_prompt: str, active_skills: list[Skill]) -> str:
    addendum = SkillStore.render_instructions(active_skills)
    if not addendum:
        return base_prompt

    base = (base_prompt or "").strip()
    if not base:
        return addendum

    return f"{base}\n\n=== Active Skills ===\n{addendum}"


def _parse_skill_file(path: Path) -> Skill | None:
    raw = path.read_text(encoding="utf-8-sig")
    matched = _FRONTMATTER_RE.match(raw)
    if not matched:
        return None

    frontmatter_raw = matched.group(1).strip()
    body = matched.group(2).strip()

    fm = _parse_frontmatter(frontmatter_raw)
    if fm is None:
        return None

    name = str(fm.get("name") or path.parent.name).strip()
    description = str(fm.get("description") or "").strip()
    triggers_raw = fm.get("triggers") or []
    triggers = _normalize_triggers(triggers_raw)

    if not name or not body:
        return None

    return Skill(
        name=name,
        description=description,
        body=body,
        triggers=triggers,
        path=path,
    )


def _normalize_triggers(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                out.append(text)
        return tuple(out)
    return ()


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _parse_frontmatter(text: str) -> dict[str, Any] | None:
    # Keep parser dependency-free by supporting the subset used by SKILL.md:
    # key: value
    # key:
    #   - item
    data: dict[str, Any] = {}
    current_list_key: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- "):
            if current_list_key is None:
                continue
            value = stripped[2:].strip().strip("\"'")
            if value:
                existing = data.get(current_list_key)
                if isinstance(existing, list):
                    existing.append(value)
            continue

        if ":" not in line:
            current_list_key = None
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            current_list_key = None
            continue

        if not value:
            data[key] = []
            current_list_key = key
            continue

        current_list_key = None
        cleaned = value.strip().strip("\"'")
        data[key] = cleaned

    return data
