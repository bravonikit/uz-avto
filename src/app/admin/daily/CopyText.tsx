"use client";
// Готовый текст поста и кнопка «Скопировать».

import { useState } from "react";

export function CopyText({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
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
        className="mt-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
      >
        {copied ? "Скопировано" : "Скопировать текст"}
      </button>
    </div>
  );
}
