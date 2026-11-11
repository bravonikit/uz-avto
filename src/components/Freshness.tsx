"use client";
// Свежесть объявления: "сегодня", "вчера", "3 дня назад", а для старых — дата.
// Считается в браузере, потому что "сегодня" зависит от момента, когда страницу открыли:
// сервер отдаёт обычную дату, браузер сразу заменяет её на свежесть.

import { useSyncExternalStore } from "react";
import { formatDate, formatFreshness } from "@/lib/format";

const subscribe = () => () => {}; // подписываться не на что: значение не меняется, пока страница открыта

export function Freshness({ date }: { date: string }) {
  return useSyncExternalStore(
    subscribe,
    () => formatFreshness(date), // в браузере
    () => formatDate(date), // на сервере
  );
}
