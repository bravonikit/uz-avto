"use client";
// "use client" значит: этот компонент работает в браузере.
// Нужно, потому что список моделей меняется сразу при выборе марки.

import Form from "next/form";
import { useState } from "react";
import { CITIES, YEARS } from "@/lib/catalog";
import type { ListingFilters } from "@/lib/listings";

const field =
  "w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 disabled:bg-slate-100 disabled:text-slate-400";

type Props = {
  brands: Record<string, string[]>; // марка → модели
  initial?: ListingFilters;
};

export function SearchForm({ brands, initial = {} }: Props) {
  const [brand, setBrand] = useState(initial.brand ?? "");
  const [model, setModel] = useState(initial.model ?? "");
  const models = brand ? (brands[brand] ?? []) : [];

  return (
    // <Form> отправляет поля в адрес страницы: /cars?brand=Kia&city=Ташкент
    <Form action="/cars" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <select
        name="brand"
        value={brand}
        onChange={(e) => {
          setBrand(e.target.value);
          setModel(""); // при смене марки сбрасываем модель
        }}
        className={field}
        aria-label="Марка"
      >
        <option value="">Все марки</option>
        {Object.keys(brands).map((name) => (
          <option key={name}>{name}</option>
        ))}
      </select>

      <select
        name="model"
        value={model}
        onChange={(e) => setModel(e.target.value)}
        disabled={!brand}
        className={field}
        aria-label="Модель"
      >
        <option value="">{brand ? "Все модели" : "Сначала марка"}</option>
        {models.map((name) => (
          <option key={name}>{name}</option>
        ))}
      </select>

      <div className="flex gap-2">
        <input
          name="priceFrom"
          inputMode="numeric"
          placeholder="Цена от, сум"
          defaultValue={initial.priceFrom}
          className={field}
          aria-label="Цена от, сум"
        />
        <input
          name="priceTo"
          inputMode="numeric"
          placeholder="до"
          defaultValue={initial.priceTo}
          className={field}
          aria-label="Цена до, сум"
        />
      </div>

      <div className="flex gap-2">
        <select name="yearFrom" defaultValue={initial.yearFrom ?? ""} className={field} aria-label="Год от">
          <option value="">Год от</option>
          {YEARS.map((y) => (
            <option key={y}>{y}</option>
          ))}
        </select>
        <select name="yearTo" defaultValue={initial.yearTo ?? ""} className={field} aria-label="Год до">
          <option value="">до</option>
          {YEARS.map((y) => (
            <option key={y}>{y}</option>
          ))}
        </select>
      </div>

      <select name="city" defaultValue={initial.city ?? ""} className={field} aria-label="Город">
        <option value="">Весь Узбекистан</option>
        {CITIES.map((c) => (
          <option key={c}>{c}</option>
        ))}
      </select>

      <select name="sort" defaultValue={initial.sort ?? "new"} className={field} aria-label="Сортировка">
        <option value="new">Сначала новые</option>
        <option value="cheap">Сначала дешёвые</option>
        <option value="expensive">Сначала дорогие</option>
      </select>

      <button
        type="submit"
        className="rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-700 sm:col-span-2"
      >
        Показать объявления
      </button>
    </Form>
  );
}
