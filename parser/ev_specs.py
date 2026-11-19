"""Запас хода и состояние батареи электромобилей и гибридов из текста поста (бесплатно, без ИИ).

Продавцы пишут запас хода по разному:
  явно:            «запас хода 520 км», «zapas xod 605», «🔋605km», «токда 400 км юради» (сейчас проходит 400 км)
  в названии:      «BYD Champion 605», «Gac Aion i60 650 ev», «Byd 2024 605тали»
Не путаем с телефонами (97-123-45-67), ценами (19.900$), мощностью («340 ot kuchi») и пробегом («45.000 km yurgan»).
У гибридов (DM-i, EREV) число в названии это запас хода на электричестве: «Champion Hybrid 150km».

  range_km      запас хода, км (паспортный, как пишет продавец)
  range_now_km  сколько машина проходит сейчас на полной зарядке, если продавец написал отдельно
  range_total_km  у гибридов: общий запас хода на бензине и электричестве («Champion DM-i 1250»)
  battery_pct   состояние батареи, % («ёмкость 98%», «yomkist 97%», «93%🔋»)
  powertrain    ev, hybrid или None, если по тексту не понять
Голос продавца добирает price_fill.py (Gemini): если в тексте ничего нет, берём оттуда.
"""
from __future__ import annotations

import re

ELECTRIC_BRANDS = {"Zeekr", "Lixiang", "Leapmotor", "Aito", "Avatr", "Voyah", "Deepal", "Denza", "XPeng", "NIO", "Tesla",
                   "Xiaomi", "Neta", "Hongqi", "BYD", "GAC", "Dongfeng", "Changan", "IM", "ONVO", "Jiyue", "Yangwang",
                   "Polestar", "Seres", "Maextro", "Smart", "Rox", "iCar", "Enovate", "Weltmeister", "Skywell", "Lingbox"}
ELECTRIC_WORDS = re.compile(r"\bev\b|elektr|electr|электр|zaryad|заряд|батар|batar|🔋|\bkwh\b|квт|tok\b|ток\b|lidar", re.I)
HYBRID_WORDS = re.compile(r"hybrid|gibrid|gebrit|hibrid|гибрид|\bdm\W?i\b|\bphev\b|\berev\b|\bem\W?i\b", re.I)

NUM = r"(?<![\d\-()+.,/])(\d{3,4})(?![\d\-().,/])"  # отдельное число: не кусок телефона, цены или даты
EXPLICIT = [
    re.compile(r"(?:запас\w*\s*ход\w*|zapas\w*\s*(?:xod|hod|xot)\w*|zapas\b|🔋|запас\b|range)\s*[:\-–—]?\s*" + NUM, re.I),
    re.compile(NUM + r"\s*(?:km|км|кm)\s*(?:li\s*)?(?:zapas|запас)", re.I),
]
NOW = re.compile(r"(?:токда|tokda|hozir|ҳозир|хозир|сейчас|реально|real)\D{0,15}" + NUM + r"\s*(?:km|км)", re.I)
IN_NAME = re.compile(NUM + r"\s*(?:km|км|кm|tali|тали|lik|лик|li|ли)?(?=\s|$|[^\w])", re.I)
NOT_RANGE_AFTER = re.compile(r"^\s*(?:ot\b|от\b|л\.?\s*с|hp|ls\b|л\b|\$|у\.?е|sum|сум|ming|минг|mln|млн|yurgan|юрган|bosgan|босган|probeg|пробег|ming)", re.I)
NOT_RANGE_LINE = re.compile(r"probeg|пробег|yurgan|юрган|bosgan|босган|narx|нарх|цена|price|tel|тел|📞|☎|блок|index", re.I)
BATTERY = re.compile(r"(?:ёмкост\w*|емкост\w*|yomk\w*|ёмк\w*|batar\w*|batter\w*|акб|soh|akkum\w*|аккум\w*)\D{0,12}(\d{2,3})\s*%"
                     r"|(?<![\d.,])(\d{2,3})\s*%\s*🔋|🔋\s*(\d{2,3})\s*%", re.I)
HYBRID_ELECTRIC_MAX = 400  # у гибрида число больше этого: общий запас хода на бензине и электричестве
RANGE_MIN, RANGE_MAX = 50, 1600


def _first_lines(title: str | None, text: str | None) -> list[str]:
    lines = [title or ""] + [line for line in (text or "").splitlines() if line.strip()][:2]
    return [line for line in lines if line.strip()]


def _ok(value: int) -> bool:
    return RANGE_MIN <= value <= RANGE_MAX


def ev_specs(brand: str | None, model: str | None, title: str | None, text: str | None) -> dict:
    blob = " ".join([model or "", title or "", text or ""])
    electric = bool(ELECTRIC_WORDS.search(blob)) or bool(HYBRID_WORDS.search(blob))
    if brand not in ELECTRIC_BRANDS and not electric:
        return {}
    out: dict = {"powertrain": "hybrid" if HYBRID_WORDS.search(blob) else ("ev" if electric else None)}
    full = (title or "") + "\n" + (text or "")

    for rx in EXPLICIT:
        for m in rx.finditer(full):
            value = int(m.group(1))
            if _ok(value) and not NOT_RANGE_AFTER.match(full[m.end():m.end() + 12]):
                out.setdefault("range_km", value)
                break
    now = NOW.search(full)
    if now and _ok(int(now.group(1))):
        out["range_now_km"] = int(now.group(1))

    if "range_km" not in out:
        for line in _first_lines(title, text):
            if NOT_RANGE_LINE.search(line):
                continue
            for m in IN_NAME.finditer(line):
                value = int(m.group(1))
                if not _ok(value) or 1990 <= value <= 2030:  # год выпуска
                    continue
                after = line[m.end():m.end() + 12]
                if NOT_RANGE_AFTER.match(after):
                    continue
                # Голое число без «км» берём, только если оно похоже на запас хода, а не на модель (Zeekr 001, Lynk 900)
                if not m.group(0).strip().isdigit() or value >= 300:
                    if (model or "").replace(" ", "").lower().endswith(str(value)):
                        continue  # это номер модели: Lynk & Co 900, Shacman X5000
                    out["range_km"] = value
                    break
            if "range_km" in out:
                break

    battery = BATTERY.search(full)
    if battery:
        pct = int(next(g for g in battery.groups() if g))
        if 50 <= pct <= 100:
            out["battery_pct"] = pct
    # Гибрид: большое число это общий запас хода, а не на электричестве
    if out.get("powertrain") == "hybrid" and out.get("range_km", 0) > HYBRID_ELECTRIC_MAX:
        out["range_total_km"] = out.pop("range_km")
    # Запас хода от 300 км и ни слова про гибрид: электромобиль (BYD Champion 605, Han 605)
    if not out.get("powertrain") and out.get("range_km", 0) >= 300:
        out["powertrain"] = "ev"
    return {k: v for k, v in out.items() if v is not None}
