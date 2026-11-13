"use client";
// Считает просмотры: при открытии каждой страницы отправляет её адрес на /api/view.
// Сам ничего не рисует. Общее число просмотров передаёт блоку SiteStats на главной.

import { usePathname } from "next/navigation";
import { useEffect } from "react";

export const VIEWS_EVENT = "site-views";

// В режиме разработки React запускает эффект дважды: второй раз подряд не считаем
let lastSent = { page: "", at: 0 };

export function ViewTracker() {
  const pathname = usePathname();

  useEffect(() => {
    const now = Date.now();
    if (lastSent.page === pathname && now - lastSent.at < 2000) return;
    lastSent = { page: pathname, at: now };

    fetch("/api/view", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ page: pathname }),
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((data: { total?: number } | null) => {
        if (typeof data?.total === "number") {
          window.dispatchEvent(new CustomEvent(VIEWS_EVENT, { detail: data.total }));
        }
      })
      .catch(() => undefined); // счётчик не должен ломать страницу
  }, [pathname]);

  return null;
}
