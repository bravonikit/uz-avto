"""Поправка цен аналогов на пробег и год для оценки рынка (market.py).

Для каждой модели оцениваем, во сколько раз меняется цена:
  за каждые 10 000 км пробега  (обычно минус 2–5%)
  за каждый год выпуска        (обычно плюс 5–12%)
Регрессия логарифма цены на год и пробег внутри модели. Где объявлений мало, коэффициенты
подтягиваются к общим по рынку (чем меньше данных, тем сильнее). Выбросы (ошибки разбора цены)
отбрасываем и считаем заново. Потом цену каждого аналога пересчитываем на год и пробег
оцениваемой машины: аналог с пробегом 150 тыс. км становится дороже, если наша машина прошла 50 тыс.
"""
from __future__ import annotations

import math

KM_STEP = 10_000
SHRINK = 25  # «сила» общего коэффициента: столько объявлений модели нужно, чтобы свой коэффициент весил половину
MIN_POINTS = 8
KM_LIMITS = (-0.08, 0.0)   # за 10 000 км: цена не может расти с пробегом и падать быстрее 8%
YEAR_LIMITS = (0.0, 0.25)  # за год: машина постарше не дороже и дешевеет не больше чем на 25% в год
OUTLIER = 0.45  # отклонение логарифма цены больше этого: скорее ошибка цены, в оценке коэффициентов не участвует


def _ols2(rows: list[tuple[float, float, float]]) -> tuple[float, float] | None:
    """МНК y = by*x1 + bk*x2 по центрированным данным. None, если система вырождена."""
    s11 = sum(a * a for a, _, _ in rows)
    s22 = sum(b * b for _, b, _ in rows)
    s12 = sum(a * b for a, b, _ in rows)
    s1y = sum(a * y for a, _, y in rows)
    s2y = sum(b * y for _, b, y in rows)
    det = s11 * s22 - s12 * s12
    if det <= 1e-9:
        return None
    return (s1y * s22 - s2y * s12) / det, (s2y * s11 - s1y * s12) / det


def _centered(points: list[tuple[int, float, float]]) -> list[tuple[float, float, float]]:
    n = len(points)
    my = sum(p[0] for p in points) / n
    mk = sum(p[1] for p in points) / n
    ml = sum(p[2] for p in points) / n
    return [(p[0] - my, p[1] - mk, p[2] - ml) for p in points]


def _clip(value: float, limits: tuple[float, float]) -> float:
    return min(max(value, limits[0]), limits[1])


def _fit(points: list[tuple[int, float, float]]) -> tuple[float, float] | None:
    rows = _centered(points)
    first = _ols2(rows)
    if not first:
        return None
    by, bk = first
    kept = [r for r in rows if abs(r[2] - by * r[0] - bk * r[1]) <= OUTLIER]
    if len(kept) >= MIN_POINTS and len(kept) < len(rows):
        again = _ols2(_centered([p for p, r in zip(points, rows) if abs(r[2] - by * r[0] - bk * r[1]) <= OUTLIER]))
        if again:
            by, bk = again
    return by, bk


def fit_slopes(groups: dict[tuple, list[dict]]) -> tuple[dict[tuple, tuple[float, float]], tuple[float, float]]:
    """Коэффициенты (за год, за 10 000 км) по моделям и общие. groups: модель -> объявления с ценой, годом и пробегом."""
    per_model: dict[tuple, list[tuple[int, float, float]]] = {}
    for key, items in groups.items():
        pts = [(i["year"], i["mileage_km"] / KM_STEP, math.log(i["price"])) for i in items
               if i["price"] and i["year"] and i["mileage_km"] is not None]
        if len(pts) >= 3:
            per_model[key] = pts
    # Общие коэффициенты: все модели вместе, каждая со своим средним
    pooled = [row for pts in per_model.values() for row in _centered(pts)]
    general = _ols2(pooled) or (0.08, -0.03)
    general = (_clip(general[0], YEAR_LIMITS), _clip(general[1], KM_LIMITS))
    slopes = {}
    for key, pts in per_model.items():
        own = _fit(pts) if len(pts) >= MIN_POINTS else None
        if not own:
            slopes[key] = general
            continue
        w = len(pts) / (len(pts) + SHRINK)
        slopes[key] = (_clip(w * own[0] + (1 - w) * general[0], YEAR_LIMITS),
                       _clip(w * own[1] + (1 - w) * general[1], KM_LIMITS))
    return slopes, general


def adjusted(price: float, analog: dict, target: dict, slope: tuple[float, float]) -> float:
    """Цена аналога, пересчитанная на год и пробег оцениваемой машины."""
    by, bk = slope
    shift = by * (target["year"] - analog["year"])
    if target["mileage_km"] is not None and analog["mileage_km"] is not None:
        shift += bk * (target["mileage_km"] - analog["mileage_km"]) / KM_STEP
    return price * math.exp(shift)
