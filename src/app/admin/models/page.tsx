// Админка, вкладка «Спорные модели»: марку и модель не удалось определить уверенно. Адрес: /admin/models
// У каждого объявления фото поста, текст и до четырёх подсказок: из названия, заголовка, текста поста
// или частые модели этой марки. Можно выбрать подсказку, вписать свою машину, оставить как есть или скрыть.
// Решения хранятся в parser/data/model_decisions.json, на сайте видны после следующей выгрузки.

import { Suspense } from "react";
import { isAdmin } from "@/lib/admin";
import { formatDate, formatMileage, formatPrice } from "@/lib/format";
import { getModelList, getModelQueue, type ModelDispute } from "@/lib/model-review";
import { decideModelAction } from "../actions";

const SHOW = 10; // карточек за раз: после решения подтягиваются следующие

export default function ModelsPage() {
  return (
    <Suspense fallback={<p className="text-slate-400">Загружаем очередь…</p>}>
      <Models />
    </Suspense>
  );
}

async function Models() {
  if (!(await isAdmin())) return null;
  const [{ items, decided }, list] = await Promise.all([getModelQueue(), getModelList()]);
  const brands = Object.keys(list).sort((a, b) => a.localeCompare(b));
  const models = [...new Set(Object.values(list).flat())].sort((a, b) => a.localeCompare(b));
  return (
    <>
      <p className="mb-5 text-xs text-slate-400">
        Осталось {items.length}, уже решено {decided}. Решения сохраняются сразу, а на сайте видны после следующей
        выгрузки.
      </p>
      <datalist id="brand-list">
        {brands.map((brand) => (
          <option key={brand} value={brand} />
        ))}
      </datalist>
      <datalist id="model-list">
        {models.map((model) => (
          <option key={model} value={model} />
        ))}
      </datalist>
      {items.length === 0 ? (
        <p className="rounded-2xl bg-white p-8 text-center text-slate-500 shadow-sm ring-1 ring-slate-200">
          Спорных моделей нет.
        </p>
      ) : (
        <ul className="max-w-4xl space-y-4">
          {items.slice(0, SHOW).map((item) => (
            <Dispute key={item.id} item={item} />
          ))}
        </ul>
      )}
    </>
  );
}

const button = "rounded-xl px-4 py-2 text-sm font-semibold";
const light = `${button} text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50`;
const input = "w-40 rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500";

function Dispute({ item }: { item: ModelDispute }) {
  const was = [item.brand, item.model].filter(Boolean).join(" ") || "ничего";
  const facts = [
    item.year && `${item.year} г.`,
    item.mileage_km !== null && item.mileage_km !== undefined && formatMileage(item.mileage_km),
    item.price ? formatPrice(item.price, "USD") : "без цены",
    item.date && formatDate(item.date),
  ].filter(Boolean);
  return (
    <li className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-bold">{item.title || "без заголовка"}</h3>
        <p className="text-xs text-slate-500">
          {item.account && `@${item.account} · `}
          {facts.join(" · ")}
        </p>
      </div>

      {item.photos.length > 0 ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {item.photos.map((src) => (
            <a key={src} href={src} target="_blank" rel="noopener noreferrer">
              {/* eslint-disable-next-line @next/next/no-img-element -- фото поста для проверки */}
              <img src={src} alt="" loading="lazy" className="aspect-[4/3] w-full rounded-xl bg-slate-100 object-cover" />
            </a>
          ))}
        </div>
      ) : (
        <div className="flex h-24 items-center justify-center rounded-xl bg-slate-100 text-xs text-slate-400">
          нет фото, смотрите пост
        </div>
      )}

      <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
        Разбор: <b>{was}</b>. {item.reason}
      </p>
      {item.text && (
        <p className="mt-2 max-h-40 overflow-auto text-sm leading-relaxed whitespace-pre-line text-slate-700">{item.text}</p>
      )}
      {item.url && (
        <a href={item.url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-block text-sm text-brand-700 hover:underline">
          Пост ↗
        </a>
      )}

      {item.candidates.length > 0 && (
        <form action={decideModelAction} className="mt-4 flex flex-wrap gap-2">
          <input type="hidden" name="id" value={item.id} />
          <input type="hidden" name="decision" value="pick" />
          {item.candidates.map((candidate, index) => (
            <button
              key={`${candidate.brand}|${candidate.model}`}
              type="submit"
              name="car"
              value={`${candidate.brand}|${candidate.model}`}
              className={index === 0 ? `${button} bg-slate-900 text-white hover:bg-slate-700` : light}
            >
              {candidate.brand} {candidate.model}
              <span className={`ml-1.5 text-xs font-normal ${index === 0 ? "text-white/60" : "text-slate-400"}`}>
                {candidate.source}
              </span>
            </button>
          ))}
        </form>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <form action={decideModelAction} className="flex flex-wrap gap-2">
          <input type="hidden" name="id" value={item.id} />
          <input type="hidden" name="decision" value="manual" />
          <input name="brand" list="brand-list" placeholder="Марка" defaultValue={item.candidates[0]?.brand ?? item.brand ?? ""} className={input} />
          <input name="model" list="model-list" placeholder="Модель" className={input} />
          <button type="submit" className={light}>
            Поставить
          </button>
        </form>
        <form action={decideModelAction}>
          <input type="hidden" name="id" value={item.id} />
          <input type="hidden" name="decision" value="keep" />
          <button type="submit" className={light}>
            Оставить как есть
          </button>
        </form>
        <form action={decideModelAction}>
          <input type="hidden" name="id" value={item.id} />
          <input type="hidden" name="decision" value="hide" />
          <button type="submit" className={`${button} text-red-700 ring-1 ring-red-200 hover:bg-red-50`}>
            Не объявление, скрыть
          </button>
        </form>
      </div>
    </li>
  );
}
