"use client";
// Кнопка «Удалить» в кабинете. Перед удалением переспрашивает, чтобы не удалить случайно.

import { deleteListing } from "./actions";

export function DeleteButton({ id, title }: { id: string; title: string }) {
  return (
    <form
      action={deleteListing}
      onSubmit={(event) => {
        if (!window.confirm(`Удалить объявление «${title}»?`)) event.preventDefault();
      }}
    >
      <input type="hidden" name="id" value={id} />
      <button type="submit" className="text-sm text-slate-500 hover:text-red-600">
        Удалить
      </button>
    </form>
  );
}
