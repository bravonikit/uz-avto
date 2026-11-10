"use client";

import Link from "next/link";
import { useActionState, useState } from "react";
import {
  BODY_TYPES,
  BRANDS,
  BRAND_NAMES,
  CITIES,
  DRIVES,
  FUEL_TYPES,
  TRANSMISSIONS,
  YEARS,
} from "@/lib/catalog";
import { submitListing, type SellFormState } from "./actions";

const field =
  "w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 disabled:bg-slate-100";

const initialState: SellFormState = { status: "idle" };

export function SellForm() {
  // useActionState: отправляет форму на сервер и хранит ответ (ошибки или успех)
  const [state, formAction, pending] = useActionState(submitListing, initialState);
  const v = state.values ?? {};
  const [brand, setBrand] = useState(v.brand ?? "");
  const [photos, setPhotos] = useState<string[]>([]);

  if (state.status === "success") {
    return (
      <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-slate-200">
        <p className="text-4xl">✅</p>
        <h2 className="mt-3 text-xl font-bold">Объявление проверено и готово</h2>
        <p className="mt-2 text-slate-700">{state.summary}</p>
        <p className="mt-4 text-sm text-slate-500">
          Это тестовая версия: объявление пока никуда не сохраняется.
        </p>
        <Link href="/cars" className="mt-6 inline-block text-emerald-700 hover:underline">
          ← К объявлениям
        </Link>
      </div>
    );
  }

  const error = (name: string) =>
    state.errors?.[name] && <p className="mt-1 text-xs text-red-600">{state.errors[name]}</p>;

  return (
    <form action={formAction} className="space-y-8" noValidate>
      <Section title="Автомобиль">
        <Field label="Марка">
          <select
            name="brand"
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
            className={field}
          >
            <option value="">Выберите</option>
            {BRAND_NAMES.map((b) => (
              <option key={b}>{b}</option>
            ))}
          </select>
          {error("brand")}
        </Field>
        <Field label="Модель">
          <select
            key={brand}
            name="model"
            defaultValue={brand === v.brand ? v.model : ""}
            disabled={!brand}
            className={field}
          >
            <option value="">Выберите</option>
            {(BRANDS[brand] ?? []).map((m) => (
              <option key={m}>{m}</option>
            ))}
          </select>
          {error("model")}
        </Field>
        <Field label="Год выпуска">
          <select name="year" defaultValue={v.year ?? ""} className={field}>
            <option value="">Выберите</option>
            {YEARS.map((y) => (
              <option key={y}>{y}</option>
            ))}
          </select>
          {error("year")}
        </Field>
        <Field label="Пробег, км">
          <input name="mileage" inputMode="numeric" placeholder="45 000" defaultValue={v.mileage} className={field} />
          {error("mileage")}
        </Field>
        <Field label="Кузов">
          <Options name="bodyType" items={BODY_TYPES} value={v.bodyType} />
        </Field>
        <Field label="Топливо">
          <Options name="fuel" items={FUEL_TYPES} value={v.fuel} />
        </Field>
        <Field label="Коробка">
          <Options name="transmission" items={TRANSMISSIONS} value={v.transmission} />
        </Field>
        <Field label="Привод">
          <Options name="drive" items={DRIVES} value={v.drive} />
        </Field>
      </Section>

      <Section title="Фото">
        <div className="sm:col-span-2">
          <input
            type="file"
            accept="image/*"
            multiple
            onChange={(e) =>
              setPhotos(Array.from(e.target.files ?? [], (file) => URL.createObjectURL(file)))
            }
            className="block w-full text-sm file:mr-4 file:rounded-xl file:border-0 file:bg-emerald-50 file:px-4 file:py-2 file:font-semibold file:text-emerald-700"
          />
          <p className="mt-1 text-xs text-slate-400">
            Пока только предпросмотр — загрузку фото добавим вместе с хранилищем файлов.
          </p>
          {photos.length > 0 && (
            <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-5">
              {photos.map((src) => (
                // eslint-disable-next-line @next/next/no-img-element -- локальный предпросмотр
                <img key={src} src={src} alt="" className="aspect-square rounded-lg object-cover" />
              ))}
            </div>
          )}
        </div>
      </Section>

      <Section title="Цена и описание">
        <Field label="Цена, сум">
          <input name="price" inputMode="numeric" placeholder="150 000 000" defaultValue={v.price} className={field} />
          {error("price")}
        </Field>
        <Field label="Город">
          <select name="city" defaultValue={v.city ?? ""} className={field}>
            <option value="">Выберите</option>
            {CITIES.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
          {error("city")}
        </Field>
        <div className="sm:col-span-2">
          <Field label="Описание">
            <textarea
              name="description"
              rows={4}
              placeholder="Состояние, комплектация, история обслуживания…"
              defaultValue={v.description}
              className={field}
            />
          </Field>
        </div>
      </Section>

      <Section title="Контакты">
        <Field label="Имя">
          <input name="name" placeholder="Азиз" defaultValue={v.name} className={field} />
          {error("name")}
        </Field>
        <Field label="Телефон">
          <input
            name="phone"
            type="tel"
            placeholder="+998 90 123-45-67"
            defaultValue={v.phone ?? "+998 "}
            className={field}
          />
          {error("phone")}
        </Field>
      </Section>

      {state.status === "error" && (
        <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">Проверьте поля, отмеченные красным.</p>
      )}

      <button
        type="submit"
        disabled={pending}
        className="w-full rounded-xl bg-emerald-600 px-4 py-3 font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
      >
        {pending ? "Проверяем…" : "Разместить объявление"}
      </button>
    </form>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <fieldset className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
      <legend className="float-left mb-4 w-full text-lg font-bold">{title}</legend>
      <div className="clear-both grid gap-4 sm:grid-cols-2">{children}</div>
    </fieldset>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm text-slate-600">{label}</span>
      {children}
    </label>
  );
}

function Options({ name, items, value }: { name: string; items: readonly string[]; value?: string }) {
  return (
    <select name={name} defaultValue={value ?? items[0]} className={field}>
      {items.map((item) => (
        <option key={item}>{item}</option>
      ))}
    </select>
  );
}
