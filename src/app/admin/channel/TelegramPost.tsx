"use client";
// Пост из Telegram в том виде, в каком его видят в ленте канала.
// Используем официальный виджет Telegram: он подставляет пост и сам подгоняет высоту.

import { useEffect, useRef } from "react";

// post: "канал/номер поста", например "carsaleuzb/83960"
export function TelegramPost({ post }: { post: string }) {
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = box.current;
    if (!element) return;
    const script = document.createElement("script");
    script.async = true;
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.setAttribute("data-telegram-post", post);
    script.setAttribute("data-width", "100%");
    element.replaceChildren(script);
    return () => element.replaceChildren();
  }, [post]);

  return <div ref={box} className="min-h-32" />;
}
