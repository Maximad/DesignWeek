"""Editable, whitelisted public copy for DesignWeek.

Defaults are extracted from the checked-in public HTML and the existing JS data
so the editor never drifts from the published default text.
No user-supplied HTML is accepted or rendered.
"""
from __future__ import annotations

import ast
import re
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EditableTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = []
        self.fields = []

    def handle_starttag(self, tag, attrs):
        for item in self.active:
            item["depth"] += 1
        attrs = dict(attrs)
        key = attrs.get("data-cms-key")
        if key:
            if not re.fullmatch(r"[a-z0-9_.-]{3,80}", key):
                raise ValueError("Invalid editable site-content key")
            self.active.append({
                "key": key,
                "group": attrs.get("data-cms-group", "الموقع"),
                "label": attrs.get("data-cms-label", key),
                "default": [],
                "depth": 1,
            })

    def handle_data(self, data):
        for item in self.active:
            item["default"].append(data)

    def handle_endtag(self, tag):
        for item in self.active:
            item["depth"] -= 1
        completed = [item for item in self.active if item["depth"] == 0]
        self.active = [item for item in self.active if item["depth"] != 0]
        for item in completed:
            item["default"] = "".join(item["default"]).strip()
            self.fields.append(item)


def _js_literal(source: str, name: str, closing_marker: str):
    match = re.search(
        r"\bconst " + re.escape(name) + r" = (.*?);\s*" + re.escape(closing_marker),
        source, re.DOTALL,
    )
    if not match:
        raise ValueError(f"Missing JS data for {name}")
    data = re.sub(r"(?<=[{,])\s*([a-zA-Z_][\w]*):", r' "\1":', match.group(1))
    return ast.literal_eval(data)


@lru_cache(maxsize=1)
def all_fields():
    parser = EditableTextParser()
    parser.feed((ROOT / "index.html").read_text(encoding="utf-8"))
    fields = [
        {k: v for k, v in item.items() if k != "depth"}
        for item in parser.fields
    ]
    js = (ROOT / "assets" / "main.js").read_text(encoding="utf-8")
    days = _js_literal(js, "days", "const tabs")
    types = _js_literal(js, "types", "const config")

    def add(key: str, group: str, label: str, default: str):
        fields.append({"key": key, "group": group, "label": label, "default": default})

    for index, day in enumerate(days):
        group = f"البرنامج — اليوم {index + 1}"
        for prop, label in [
            ("tag", "نوع النشاط"),
            ("title", "عنوان اليوم"),
            ("summary", "الوصف"),
        ]:
            add(f"program.{index}.{prop}", group, label, day[prop])
        for pos, item in enumerate(day["items"]):
            add(f"program.{index}.item.{pos}", group, f"فعالية أو نشاط {pos + 1}", item)

    for slug, data in types.items():
        group = f"تفاصيل المشاركة — {data['title']}"
        add(f"participate.{slug}.details.description", group, "وصف شكل المشاركة", data["desc"])
        for pos, item in enumerate(data["requirements"]):
            add(f"participate.{slug}.requirement.{pos}", group, f"المتطلبات {pos + 1}", item)

    keys = [field["key"] for field in fields]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate content-editor keys")
    return fields


def field_groups():
    groups = {}
    for field in all_fields():
        groups.setdefault(field["group"], []).append(field)
    return groups
