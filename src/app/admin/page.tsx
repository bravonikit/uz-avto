// Админка, вкладка «Заявки»: объявления, которые продавцы подали через кабинет.
// Отсюда они публикуются в ленту /cars или отклоняются. Адрес: /admin

import Link from "next/link";
import { Suspense } from "react";
import { isAdmin } from "@/lib/admin";
import { formatMileage, formatPrice } from "@/lib/format";
import { getSimilarListings } from "@/lib/listings";
import { formatPhone, toListing } from "@/lib/published";
import { getAllSellerListings, sellerPhotoUrl, STATUS_LABELS, type SellerListing } from "@/lib/seller-listings";
import { moderateListing } from "./actions";

const dateTime = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Asia/Tashkent",
});

export default function AdminPage() {
  return (
    <Suspense fallback={<p className="text-slate-400">Загружаем заявки…</p>}>
      <Submissions />
    </Suspense>
  );
}

async function Submissions() {
  if (!(await isAdmin())) return null;
  const listings = await getAllSellerListings();
  const groups = [
    { title: "Ждут проверки", items: listings.filter((item) => item.status === "moderation") },
    { title: "Опубликованы", items: listings.filter((item) => item.status === "active" || item.status === "sold") },
    { title: "Отклонены", items: listings.filter((item) => item.status === "rejected") },
  ];

  if (listings.length === 0) {
    return (
      <p className="rounded-2xl bg-white p-8 text-center text-slate-500 shadow-sm ring-1 ring-slate-200">
        Продавцы пока ничего не подавали. Новые объявления из формы «Подать объявление» появятся здесь.
      </p>
    );
  }

  return (
    <div className="space-y-10">
      {groups.map(
        (group) =>
          group.items.length > 0 && (
            <section key={group.title}>
              <h2 className="mb-3 text-xl font-bold">
                {group.title} <span className="font-normal text-slate-400">{group.items.length}</span>
              </h2>
              <ul className="space-y-4">
                {group.items.map((item) => (
                  <Submission key={item.id} item={item} />
                ))}
              </ul>
            </section>
          ),
      )}
    </div>
  );
}

// Медиана цен похожих машин на сайте в долларах: подсказка, не ошибся ли продавец с ценой
function similarPrice(item: SellerListing) {
  const prices = getSimilarListings(toListing(item), 30)
    .filter((car) => car.price !== undefined && car.currency === "USD")
    .map((car) => car.price!)
    .sort((a, b) => a - b);
  if (prices.length < 3) return undefined;
  return { price: prices[Math.floor(prices.length / 2)], count: prices.length };
}

const button = "rounded-xl px-4 py-2 text-sm font-semibold";

function Submission({ item }: { item: SellerListing }) {
  const specs = [
    formatMileage(item.mileage),
    item.transmission,
    item.fuel,
    item.bodyType,
    item.drive && `привод ${item.drive.toLowerCase()}`,
    item.color,
    item.city,
  ].filter(Boolean);
  const similar = similarPrice(item);

  return (
    <li className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <div className="flex gap-2 overflow-x-auto pb-2">
        {item.photos.map((file) => (
          <a key={file} href={sellerPhotoUrl(item.id, file)} target="_blank" rel="noopener noreferrer" className="shrink-0">
            {/* eslint-disable-next-line @next/next/no-img-element -- фото продавца лежит вне папки public */}
            <img src={sellerPhotoUrl(item.id, file)} alt="" loading="lazy" className="h-28 w-36 rounded-xl bg-slate-100 object-cover" />
          </a>
        ))}
      </div>

      <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="text-lg font-bold">
          {item.brand} {item.model}, {item.year}
        </h3>
        <span className="text-lg font-bold">{formatPrice(item.price, item.currency)}</span>
        <span className="text-xs text-slate-500">{STATUS_LABELS[item.status]}</span>
      </div>
      {similar && (
        <p className="text-sm text-slate-500">
          Похожие на сайте: около {formatPrice(similar.price, "USD")} (по {similar.count} объявлениям)
        </p>
      )}
      <p className="mt-1 text-sm text-slate-600">{specs.join(" · ")}</p>
      {item.description && (
        <p className="mt-2 max-h-40 overflow-auto text-sm leading-relaxed whitespace-pre-line text-slate-700">
          {item.description}
        </p>
      )}
      <p className="mt-2 text-sm">
        {item.name},{" "}
        <a href={`tel:+${item.phone}`} className="text-brand-700 hover:underline">
          {formatPhone(item.phone)}
        </a>
        {item.telegram && (
          <>
            ,{" "}
            <a href={`https://t.me/${item.telegram}`} target="_blank" rel="noopener noreferrer" className="text-brand-700 hover:underline">
              @{item.telegram}
            </a>
          </>
        )}
      </p>
      <p className="mt-1 text-xs text-slate-400">
        Подано {dateTime.format(new Date(item.createdAt))} · № {item.id} · фото: {item.photos.length}
        {item.rejectReason && ` · причина отказа: ${item.rejectReason}`}
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {item.status === "moderation" && (
          <>
            <form action={moderateListing}>
              <input type="hidden" name="id" value={item.id} />
              <input type="hidden" name="decision" value="publish" />
              <button type="submit" className={`${button} bg-brand-600 text-white hover:bg-brand-700`}>
                Опубликовать
              </button>
            </form>
            <form action={moderateListing} className="flex min-w-0 flex-1 gap-2">
              <input type="hidden" name="id" value={item.id} />
              <input type="hidden" name="decision" value="reject" />
              <input
                name="reason"
                placeholder="Причина отказа, её увидит продавец"
                maxLength={300}
                className="min-w-0 flex-1 rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500"
              />
              <button type="submit" className={`${button} text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50`}>
                Отклонить
              </button>
            </form>
          </>
        )}
        {(item.status === "active" || item.status === "sold") && (
          <>
            <Link href={`/cars/${item.id}`} className={`${button} text-brand-700 ring-1 ring-slate-300 hover:bg-slate-50`}>
              Открыть на сайте
            </Link>
            <form action={moderateListing}>
              <input type="hidden" name="id" value={item.id} />
              <input type="hidden" name="decision" value="review" />
              <button type="submit" className={`${button} text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50`}>
                Снять с публикации
              </button>
            </form>
          </>
        )}
        {item.status === "rejected" && (
          <form action={moderateListing}>
            <input type="hidden" name="id" value={item.id} />
            <input type="hidden" name="decision" value="review" />
            <button type="submit" className={`${button} text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50`}>
              Вернуть на проверку
            </button>
          </form>
        )}
      </div>
    </li>
  );
}
