"use client";
// Готовый текст поста и кнопка «Скопировать».

import { useState } from "react";

export function CopyText({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  // Буфер обмена браузер даёт только на localhost и https. По адресу 10.x.x.x копируем старым способом
  const copy = async () => {
    try {
      if (navigator.clipboard) await navigator.clipboard.writeText(text);
      else {
        const area = document.createElement("textarea");
        area.value = text;
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false); // браузер не дал доступ к буферу: текст можно выделить и скопировать руками
    }
  };
  return (
    <div>
      <textarea
        readOnly
        value={text}
        rows={Math.min(22, text.split("\n").length + 1)}
        onFocus={(event) => event.currentTarget.select()}
        className="w-full rounded-xl border border-slate-300 bg-slate-50 p-3 font-mono text-xs leading-relaxed text-slate-800"
      />
      <button
        type="button"
        onClick={copy}
        className={`mt-2 rounded-xl px-4 py-2 text-sm font-semibold text-white transition active:scale-95 ${copied ? "bg-emerald-600" : "bg-slate-900 hover:bg-slate-700"}`}
      >
        {copied ? "Скопировано ✓" : "Скопировать текст"}
      </button>
    </div>
  );
}
