"""Справочник моделей в выгрузке на сайт: каноничные марка, модель и поколение у каждого объявления.

Вызывает export_to_site.py после склейки источников, до оценки рынка.
Пишет:  data/models_disputed.json  очередь «Спорные модели» для админки (/admin/models), с подсказками и фото
        data/models_list.json      справочник марка -> модели для выпадающих списков админки
        ../public/review/<id>/N.jpg фото спорных постов Telegram, чтобы админка их показала
Читает: data/model_decisions.json   решения из админки:
          {"id": {"brand": "Chevrolet", "model": "Malibu 2"}}  поставить эту машину
          {"id": {"keep": true}}                                оставить как распознал разбор
          {"id": {"hide": true}}                                не объявление о машине, на сайт не выгружать
"""
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

from accounts import PARSER_DIR
from models_ref import all_models, brand_kind, canon_brand, normalize, suggest

DATA = PARSER_DIR / "data"
DISPUTED_FILE = DATA / "models_disputed.json"
DECISIONS_FILE = DATA / "model_decisions.json"
MODELS_LIST_FILE = DATA / "models_list.json"
REVIEW_DIR = PARSER_DIR.parent / "public" / "review"
TG_DIR = DATA / "_tg"
MAX_PHOTOS = 8


def _read(file: Path, empty):
    try:
        return json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty


def review_photos(item: dict) -> list[str]:
    """Все фото поста Telegram для админки. У Instagram пока только обложка."""
    photos = []
    if item["id"].startswith("tg-"):
        channel, post_id = item["id"][3:].rsplit("-", 1)
        files = sorted((TG_DIR / channel / "images").glob(f"{post_id}_*.jpg"),
                       key=lambda f: int(f.stem.rsplit("_", 1)[1]) if f.stem.rsplit("_", 1)[1].isdigit() else 0)
        target = REVIEW_DIR / item["id"]
        for number, file in enumerate(files[:MAX_PHOTOS], 1):
            out = target / f"{number}.jpg"
            try:
                if not out.is_symlink() and not out.exists():
                    target.mkdir(parents=True, exist_ok=True)
                    # Ссылка, а не копия: место на Маке не тратим, файл сам лежит на Google Диске
                    out.symlink_to(os.path.relpath(file, target))
                photos.append(f"/review/{item['id']}/{number}.jpg")
            except OSError:
                continue
    if not photos and item.get("image"):
        photos.append(item["image"])
    return photos


def display_model(n: dict) -> str:
    return f"{n['model']} {n['generation']}" if n.get("generation") else n["model"]


def apply_models(listings: list[dict]) -> tuple[list[dict], dict]:
    decisions = _read(DECISIONS_FILE, {})
    kept, disputed = [], []
    stats = {"ok": 0, "guess": 0, "manual": 0, "disputed": 0, "hidden": 0, "renamed": 0, "trucks": 0}
    for item in listings:
        raw_brand, raw_model = item["brand"], item["model"]
        item["raw_brand"], item["raw_model"] = raw_brand, raw_model
        decision = decisions.get(item["id"]) or {}
        if decision.get("hide"):
            stats["hidden"] += 1
            continue
        if decision.get("brand"):
            n = {"brand": decision["brand"], "model": decision.get("model"), "generation": None,
                 "kind": decision.get("kind") or brand_kind(decision["brand"]), "status": "manual"}
        else:
            n = normalize(raw_brand, raw_model, item.get("title"), item.get("year"), item.get("description"))
            if decision.get("keep"):
                n = {"brand": raw_brand, "model": raw_model, "generation": None, "kind": n["kind"], "status": "manual"}
        stats[n["status"]] += 1
        item["kind"] = n["kind"]
        item["model_status"] = n["status"]
        if n["kind"] != "car":
            stats["trucks"] += 1
        if n["status"] != "disputed" and n.get("brand") and n.get("model"):
            brand, model = n["brand"], display_model(n)
            if (brand, model) != (raw_brand, raw_model):
                stats["renamed"] += 1
                # Заголовок, собранный из старых марки и модели, собираем заново
                old_name = " ".join(p for p in (raw_brand, raw_model) if p)
                if not item.get("title") or item["title"].strip().lower() == old_name.lower():
                    item["title"] = f"{brand} {model}"
            item["brand"], item["model"] = brand, model
        elif n["status"] == "disputed":
            candidates = suggest(raw_brand, raw_model, item.get("title"), item.get("year"), item.get("description"))
            if n.get("suggest"):  # в тексте другая машина: её подсказку ставим первой
                first = n["suggest"].split(" ", 1)
                candidates = [c for c in candidates if [c["brand"], c["model"]] != first]
                hint = next((c for c in suggest(first[0], first[1] if len(first) > 1 else None, None,
                                                item.get("year"), None)), None)
                if hint:
                    candidates.insert(0, {**hint, "source": "из текста поста"})
            disputed.append({
                "id": item["id"], "url": item.get("source_url"), "account": item.get("source_account"),
                "reason": n.get("reason"), "brand": raw_brand, "model": raw_model, "title": item.get("title"),
                "year": item.get("year"), "mileage_km": item.get("mileage_km"), "price": item.get("price"),
                "date": item.get("date"), "text": item.get("description") or "",
                "candidates": [{**c, "model": display_model(c)} for c in candidates],
                "photos": review_photos(item),
            })
        kept.append(item)
    # Подсказок мало: добавляем самые частые модели этой марки в нашей базе
    popular: dict[str, Counter] = {}
    for item in kept:
        if item.get("model_status") in ("ok", "guess", "manual") and item["brand"] and item["model"]:
            popular.setdefault(item["brand"], Counter())[item["model"]] += 1
    for d in disputed:
        have = {(c["brand"], c["model"]) for c in d["candidates"]}
        brand = (d["candidates"][0]["brand"] if d["candidates"] else None) or canon_brand(d["brand"])
        for model, _ in (popular.get(brand) or Counter()).most_common(6):
            if len(d["candidates"]) >= 4:
                break
            if (brand, model) not in have:
                d["candidates"].append({"brand": brand, "model": model, "source": "частая у марки", "score": 0,
                                        "generation": None})
    disputed.sort(key=lambda d: d.get("date") or "", reverse=True)
    DISPUTED_FILE.write_text(json.dumps(disputed, ensure_ascii=False, indent=1), encoding="utf-8")
    MODELS_LIST_FILE.write_text(json.dumps(all_models(), ensure_ascii=False), encoding="utf-8")
    return kept, stats
