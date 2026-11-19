"""Собирает справочник моделей по нашей базе и сверяет с агрегаторами.

    .venv/bin/python build_models_catalog.py

Читает src/data/instagram-listings.json (всё, что выгружено на сайт), прогоняет
каждое объявление через models_ref.normalize и пишет:
    data/models_catalog.json   марка -> модели: сколько объявлений, как писали, есть ли на avtoelon
    data/models_disputed.json  объявления, где модель не определена или спорит с текстом
    data/models_map.json       id объявления -> каноничная марка, модель, поколение
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from models_ref import brand_kind, model_key, normalize

ROOT = Path(__file__).resolve().parent
LISTINGS = ROOT.parent / "src" / "data" / "instagram-listings.json"
AGG = ROOT / "data" / "aggregators.json"
OUT = ROOT / "data"


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9а-я]", "", (text or "").lower())


def main() -> None:
    listings = json.loads(LISTINGS.read_text())
    agg = json.loads(AGG.read_text())
    avto = {b: {_key(m) for m in ms} for b, ms in agg["avtoelon"].items()}

    catalog: dict = defaultdict(lambda: {"kind": "car", "count": 0, "models": defaultdict(
        lambda: {"count": 0, "generations": Counter(), "written_as": Counter(), "variants": Counter()})})
    disputed, mapping = [], {}
    status = Counter()

    for item in listings:
        n = normalize(item.get("brand"), item.get("model"), item.get("title"), item.get("year"), item.get("description"))
        status[n["status"]] += 1
        mapping[item["id"]] = {k: n[k] for k in ("brand", "model", "generation", "variant", "position", "kind", "status")}
        mapping[item["id"]]["key"] = model_key(n)
        if n["status"] == "disputed":
            disputed.append({
                "id": item["id"], "url": item.get("source_url"), "reason": n["reason"],
                "was": n["raw"], "brand": n["brand"], "model": n["model"], "suggest": n["suggest"], "year": item.get("year"),
                "title": item.get("title"), "text": (item.get("description") or "")[:200],
            })
            continue
        b = catalog[n["brand"]]
        b["kind"] = brand_kind(n["brand"])
        b["count"] += 1
        m = b["models"][n["model"]]
        m["count"] += 1
        m["kind"] = n["kind"]
        if n["generation"]:
            m["generations"][n["generation"]] += 1
        m["written_as"][item.get("model") or ""] += 1
        if n["variant"]:
            for v in n["variant"].split(", "):
                m["variants"][v] += 1

    out = {}
    for brand, b in sorted(catalog.items(), key=lambda kv: -kv[1]["count"]):
        models = {}
        for name, m in sorted(b["models"].items(), key=lambda kv: -kv[1]["count"]):
            on_avtoelon = None
            if brand in avto:
                k = _key(name)
                on_avtoelon = any(k == a or k in a or a in k for a in avto[brand] if a)
            models[name] = {
                "count": m["count"],
                "kind": m.get("kind", "car"),
                "generations": dict(m["generations"]),
                "variants": dict(m["variants"].most_common(6)),
                "written_as": dict(m["written_as"].most_common(15)),
                "on_avtoelon": on_avtoelon,
            }
        out[brand] = {"kind": b["kind"], "count": b["count"], "on_avtoelon": brand in agg["avtoelon"],
                      "olx_count": agg["olx"].get(brand), "models": models}

    # Что есть на avtoelon, а у нас пока нет: пригодится для формы подачи объявления
    missing = {}
    for brand, ms in agg["avtoelon"].items():
        ours = {_key(m) for m in out.get(brand, {}).get("models", {})}
        rest = [m for m in ms if not any(_key(m) == o or o in _key(m) or _key(m) in o for o in ours if o)]
        if rest:
            missing[brand] = rest

    (OUT / "models_catalog.json").write_text(json.dumps(
        {"brands": out, "only_on_avtoelon": missing}, ensure_ascii=False, indent=1))
    (OUT / "models_disputed.json").write_text(json.dumps(disputed, ensure_ascii=False, indent=1))
    (OUT / "models_map.json").write_text(json.dumps(mapping, ensure_ascii=False))

    keys = Counter(v["key"] for v in mapping.values() if v["key"])
    print(f"объявлений {len(listings)}: {dict(status)}")
    print(f"марок {len(out)}, моделей {sum(len(b['models']) for b in out.values())}, ключей рынка {len(keys)}")
    print("причины спорных:", Counter(d["reason"].split(":")[0] for d in disputed).most_common())


if __name__ == "__main__":
    main()
