"use client";
// Мелкая строка на главной: сколько объявлений в продаже и сколько просмотров у сайта.

import { useEffect, useState } from "react";
import { VIEWS_EVENT } from "./ViewTracker";

const numberFormat = new Intl.NumberFormat("ru-RU");

export function SiteStats({ listings }: { listings: number }) {
  const [views, setViews] = useState<number | null>(null);

  useEffect(() => {
    const onViews = (event: Event) => setViews((event as CustomEvent<number>).detail);
    window.addEventListener(VIEWS_EVENT, onViews);
    return () => window.removeEventListener(VIEWS_EVENT, onViews);
  }, []);

  return (
    <p className="mt-8 text-center text-xs text-slate-400">
      Объявлений в продаже: {numberFormat.format(listings)}
      {views !== null && ` · Просмотров страниц: ${numberFormat.format(views)}`}
    </p>
  );
}
