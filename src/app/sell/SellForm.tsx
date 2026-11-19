"use client";
// Форма подачи объявления. Проверяет и сохраняет её сервер (actions.ts),
// а здесь поля, предпросмотр фото и сжатие фото перед отправкой.

import { startTransition, useActionState, useState } from "react";
import { BODY_TYPES, CITIES, DRIVES, FUEL_TYPES, TRANSMISSIONS, YEARS } from "@/lib/catalog";
import { submitListing, type SellFormState } from "./actions";

const field =
  "w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 disabled:bg-slate-100";

const initialState: SellFormState = { status: "idle" };

// Длинная сторона фото после сжатия. Снимок с телефона весит 3-5 МБ, после сжатия около 300 КБ.
const PHOTO_MAX_SIDE = 1600;

type Photo = { url: string; blob: Blob }; // url нужен для предпросмотра, blob уходит на сервер

// Уменьшает фото и переводит в JPEG прямо в браузере: быстрее отправка и меньше места на диске
async function toJpeg(file: File): Promise<Blob> {
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  const scale = Math.min(1, PHOTO_MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const context = canvas.getContext("2d");
  if (!context) throw new Error("canvas");
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return new Promise((resolve, reject) =>
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("toBlob"))), "image/jpeg", 0.85),
  );
}

type Props = {
  brands: Record<string, string[]>; // марки и модели для подсказок, из объявлений на сайте
  maxPhotos: number;
};

export function SellForm({ brands, maxPhotos }: Props) {
  // useActionState: отправляет форму на сервер и хранит ответ (ошибки)
  const [state, formAction, pending] = useActionState(submitListing, initialState);
  const [brand, setBrand] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [photoNote, setPhotoNote] = useState("");
  const [preparing, setPreparing] = useState(false);

  // Модели подсказываем для введённой марки, регистр букв не важен
  const brandKey = Object.keys(brands).find((key) => key.toLowerCase() === brand.trim().toLowerCase());
  const models = brandKey ? brands[brandKey] : [];

  async function addPhotos(files: File[]) {
    setPreparing(true);
    setPhotoNote("");
    const free = Math.max(0, maxPhotos - photos.length);
    const added: Photo[] = [];
    let failed = 0;
    for (const file of files.slice(0, free)) {
      try {
        const blob = await toJpeg(file);
        added.push({ url: URL.createObjectURL(blob), blob });
      } catch {
        failed += 1; // браузер не смог открыть файл как картинку
      }
    }
    setPhotos((current) => [...current, ...added].slice(0, maxPhotos));
    if (files.length > free) setPhotoNote(`Можно добавить не больше ${maxPhotos} фото.`);
    else if (failed > 0) setPhotoNote(`Не удалось прочитать фото: ${failed}. Попробуйте JPEG или PNG.`);
    setPreparing(false);
  }

  function removePhoto(photo: Photo) {
    URL.revokeObjectURL(photo.url);
    setPhotos((current) => current.filter((item) => item !== photo));
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    // Марку из списка сохраняем в его написании: «chevrolet» станет «Chevrolet»
    if (brandKey) data.set("brand", brandKey);
    for (const [index, photo] of photos.entries()) data.append("photos", photo.blob, `${index + 1}.jpg`);
    startTransition(() => formAction(data));
  }

  const error = (name: string) =>
    state.errors?.[name] && <p className="mt-1 text-xs text-red-600">{state.errors[name]}</p>;

  return (
    <form onSubmit={handleSubmit} className="space-y-8" noValidate>
      <Section title="Автомобиль">
        <Field label="Марка">
          <input
            name="brand"
            list="sell-brands"
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
            placeholder="Chevrolet"
            autoComplete="off"
            className={field}
          />
          <datalist id="sell-brands">
            {Object.keys(brands).map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>
          {error("brand")}
        </Field>
        <Field label="Модель">
          <input name="model" list="sell-models" placeholder="Malibu 2" autoComplete="off" className={field} />
          <datalist id="sell-models">
            {models.map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>
          {error("model")}
        </Field>
        <Field label="Год выпуска">
          <select name="year" defaultValue="" className={field}>
            <option value="">Выберите</option>
            {YEARS.map((y) => (
              <option key={y}>{y}</option>
            ))}
          </select>
          {error("year")}
        </Field>
        <Field label="Пробег, км">
          <input name="mileage" inputMode="numeric" placeholder="45 000, у новой 0" className={field} />
          {error("mileage")}
        </Field>
        <Field label="Кузов">
          <Options name="bodyType" items={BODY_TYPES} />
        </Field>
        <Field label="Топливо">
          <Options name="fuel" items={FUEL_TYPES} />
        </Field>
        <Field label="Коробка">
          <Options name="transmission" items={TRANSMISSIONS} />
        </Field>
        <Field label="Привод">
          <Options name="drive" items={DRIVES} />
        </Field>
        <Field label="Цвет">
          <input name="color" placeholder="Белый" className={field} />
          {error("color")}
        </Field>
      </Section>

      <Section title="Фото">
        <div className="sm:col-span-2">
          <input
            type="file"
            accept="image/*"
            multiple
            disabled={preparing || photos.length >= maxPhotos}
            onChange={(e) => {
              const files = Array.from(e.target.files ?? []);
              e.target.value = ""; // чтобы тот же файл можно было выбрать ещё раз
              if (files.length > 0) void addPhotos(files);
            }}
            className="block w-full text-sm file:mr-4 file:rounded-xl file:border-0 file:bg-brand-50 file:px-4 file:py-2 file:font-semibold file:text-brand-700"
          />
          <p className="mt-1 text-xs text-slate-400">
            {preparing
              ? "Готовим фото…"
              : `До ${maxPhotos} фото. Первое станет обложкой: лучше вид спереди сбоку, машина целиком.`}
          </p>
          {photoNote && <p className="mt-1 text-xs text-red-600">{photoNote}</p>}
          {error("photos")}
          {photos.length > 0 && (
            <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-5">
              {photos.map((photo, index) => (
                <div key={photo.url} className="relative">
                  {/* eslint-disable-next-line @next/next/no-img-element -- локальный предпросмотр */}
                  <img src={photo.url} alt="" className="aspect-square w-full rounded-lg object-cover" />
                  {index === 0 && (
                    <span className="absolute bottom-1 left-1 rounded bg-slate-900/80 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                      Обложка
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => removePhoto(photo)}
                    aria-label="Убрать фото"
                    className="absolute top-1 right-1 flex h-6 w-6 items-center justify-center rounded-full bg-slate-900/80 text-sm leading-none text-white hover:bg-slate-900"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </Section>

      <Section title="Цена и описание">
        <Field label="Цена">
          <div className="flex gap-2">
            <input
              name="price"
              inputMode="numeric"
              placeholder={currency === "USD" ? "12 500" : "150 000 000"}
              className={`${field} min-w-0 flex-1`}
            />
            <select
              name="currency"
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              aria-label="Валюта"
              className={`${field.replace("w-full ", "")} w-24 shrink-0`}
            >
              <option value="USD">$</option>
              <option value="UZS">сум</option>
            </select>
          </div>
          {error("price")}
        </Field>
        <Field label="Город">
          <select name="city" defaultValue="Ташкент" className={field}>
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
              placeholder="Состояние, комплектация, сколько хозяев, что делали по машине"
              className={field}
            />
            {error("description")}
          </Field>
        </div>
      </Section>

      <Section title="Контакты">
        <Field label="Имя">
          <input name="name" placeholder="Азиз" autoComplete="name" className={field} />
          {error("name")}
        </Field>
        <Field label="Телефон">
          <input
            name="phone"
            type="tel"
            placeholder="+998 90 123 45 67"
            defaultValue="+998 "
            autoComplete="tel"
            className={field}
          />
          {error("phone")}
        </Field>
        <Field label="Telegram, если есть">
          <input name="telegram" placeholder="@aziz_auto" autoComplete="off" className={field} />
          {error("telegram")}
        </Field>
      </Section>

      {state.status === "error" && (
        <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">Проверьте поля, отмеченные красным.</p>
      )}

      <button
        type="submit"
        disabled={pending || preparing}
        className="w-full rounded-xl bg-brand-600 px-4 py-3 font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
      >
        {pending ? "Отправляем…" : "Разместить объявление"}
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

// Необязательная характеристика: по умолчанию «Не указано»
function Options({ name, items }: { name: string; items: readonly string[] }) {
  return (
    <select name={name} defaultValue="" className={field}>
      <option value="">Не указано</option>
      {items.map((item) => (
        <option key={item}>{item}</option>
      ))}
    </select>
  );
}
