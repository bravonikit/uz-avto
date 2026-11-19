// Админка, вкладка «Аналитика дня»: что появилось за день и два готовых поста для Telegram канала.
// Каждый пост это картинка 1080 на 1350 и короткая подпись к ней:
// «Ниже рынка» (самая большая выгода против похожих машин) и «Самые красивые» (самые дорогие машины дня).
// Третий пост: «Подборка дня», 5 случайных машин на тему дня (30 тем по кругу, src/lib/daily-themes.ts).
// Другая тема: /admin/daily?theme=5
// Адрес: /admin/daily, конкретный день: /admin/daily?day=2026-11-16
// Обновляется сама: страница считается при открытии из файла объявлений, который раз в день
// перезаписывает парсер (parser/export_to_site.py). Показывается последний полный день.

import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";
import { isAdmin } from "@/lib/admin";
import { formatDate, formatMileage, formatPrice } from "@/lib/format";
import { DAILY_THEMES, getThemePick, themeIndexForDay, type ThemePick } from "@/lib/daily-themes";
import { getDailyDigest, getListingDays, listingTitle, marketDiscount, type DailyDigest, type Listing } from "@/lib/listings";
import { publishedPosts, telegramChannel, type PublishedPost } from "@/lib/telegram";
import { CopyText } from "./CopyText";
import { PostImage, type PostImageItem } from "./PostImage";

// Адрес сайта для ссылок в постах. Пока домена нет, в тексте стоит заметная заглушка.
const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "https://АДРЕС-САЙТА").replace(/\/$/, "");
const DAYS_IN_SWITCHER = 7;

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export default function DailyPage({ searchParams }: Props) {
  return (
    <Suspense fallback={<p className="text-slate-400">Считаем день…</p>}>
      <Daily searchParams={searchParams} />
    </Suspense>
  );
}

function percent(share: number) {
  return `${Math.round(share * 100)}%`;
}

// Одна машина в тексте поста: название, пробег, цена и ссылка на карточку
function postLines(listing: Listing, number: number, withMarket: boolean) {
  const details = [listingTitle(listing), listing.mileage !== undefined && formatMileage(listing.mileage)].filter(Boolean);
  const discount = marketDiscount(listing);
  const market =
    withMarket && listing.market && discount !== undefined
      ? ` (похожие около ${formatPrice(listing.market.price, "USD")}, ниже на ${percent(discount)})`
      : "";
  return [
    `${number}. ${details.join(" · ")}`,
    `${formatPrice(listing.price, listing.currency)}${market}`,
    `${SITE_URL}/cars/${listing.id}`,
  ].join("\n");
}

// "66 900$": на картинке знак доллара стоит после числа, как пишут продавцы
function dollars(amount: number) {
  return `${new Intl.NumberFormat("ru-RU").format(Math.round(amount))}$`;
}

// Машина для картинки поста
function imageItem(listing: Listing, withMarket: boolean): PostImageItem {
  const sub = [listing.year, listing.mileage !== undefined && (listing.mileage === 0 ? "без пробега" : formatMileage(listing.mileage))];
  return {
    title: listing.title ?? `${listing.brand} ${listing.model}`,
    sub: sub.filter(Boolean).join(" · "),
    price: dollars(listing.price!),
    market: withMarket && listing.market ? dollars(listing.market.price) : undefined,
    cheaper: withMarket && listing.market ? dollars(listing.market.price - listing.price!) : undefined,
    image: listing.image,
    cutTop: listing.photoQuality === "bad",
  };
}

// Подпись под картинкой: список машин со ссылками на карточки
function caption(title: string, digest: DailyDigest, listings: Listing[], withMarket: boolean) {
  return [
    `${title}, ${formatDate(digest.day)}`,
    "",
    listings.map((listing, index) => postLines(listing, index + 1, withMarket)).join("\n\n"),
    "",
    `Все машины дня: ${SITE_URL}/cars?day=${digest.day}&hideSold=1`,
  ].join("\n");
}

// "за 3 дня", "за 1 день", "в день публикации"
function sellTerm(days: number) {
  const whole = Math.round(days);
  if (whole <= 0) return "в день публикации";
  const last = whole % 10;
  const word = last === 1 && whole % 100 !== 11 ? "день" : last >= 2 && last <= 4 && (whole % 100 < 12 || whole % 100 > 14) ? "дня" : "дней";
  return `за ${whole} ${word}`;
}

// Итоги темы одной строкой: для подписи на картинке и для заметки в админке
function themeSummary(pick: ThemePick) {
  const { stats } = pick;
  return [
    `выставлено ${stats.listed}`,
    `продано ${stats.sold}`,
    stats.medianPrice !== undefined && `средняя цена ${dollars(stats.medianPrice)}`,
    stats.medianDaysToSell !== undefined && `обычно уходит ${sellTerm(stats.medianDaysToSell)}`,
  ]
    .filter(Boolean)
    .join(", ");
}

// Подпись к подборке: итоги месяца, быстро проданные, потом машины с картинки
function themeCaption(pick: ThemePick, digest: DailyDigest) {
  const fast = pick.stats.fastSold.map(
    (listing) => `• ${listingTitle(listing)}, ${dollars(listing.price!)}: продана ${sellTerm(listing.daysToSell!)}`,
  );
  return [
    `🚗 ${pick.theme.title}`,
    `Итоги ${pick.window}: ${themeSummary(pick)}.`,
    ...(fast.length > 0 ? ["", "Быстрее всех ушли:", ...fast] : []),
    "",
    "Сейчас в продаже:",
    pick.listings.map((listing, index) => postLines(listing, index + 1, false)).join("\n\n"),
    "",
    `Все машины дня: ${SITE_URL}/cars?day=${digest.day}&hideSold=1`,
  ].join("\n");
}

async function Daily({ searchParams }: Props) {
  if (!(await isAdmin())) return null;
  const params = await searchParams;
  await connection(); // день считается при каждом открытии, а не один раз при сборке

  const days = getListingDays();
  if (days.length === 0) return <p className="text-slate-500">Объявлений пока нет.</p>;
  const day = typeof params.day === "string" && days.includes(params.day) ? params.day : days[0];
  const digest = getDailyDigest(day);
  const todaysTheme = themeIndexForDay(day);
  const asked = typeof params.theme === "string" ? Number(params.theme) : NaN;
  const themeIndex = Number.isInteger(asked) && asked >= 0 && asked < DAILY_THEMES.length ? asked : todaysTheme;
  const pick = getThemePick(themeIndex, day);
  const channel = telegramChannel();
  const sent = await publishedPosts();
  const stats: [string, string][] = [
    ["Объявлений за день", String(digest.total)],
    ["В наличии", String(digest.inStock)],
    ["С ценой", String(digest.withPrice)],
    ["Ниже рынка", String(digest.belowMarket)],
    ["Средняя цена (медиана)", digest.medianPrice !== undefined ? formatPrice(digest.medianPrice, "USD") : "нет"],
  ];

  return (
    <>
      <div className="mb-6 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200" data-day={day}>
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2 className="text-xl font-bold">Аналитика за {formatDate(day)}</h2>
          <span className="text-sm text-slate-500">
            {day === days[0] ? "последний полный день в данных" : "архивный день"}
          </span>
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-sm">
          {days.slice(0, DAYS_IN_SWITCHER).map((item) => (
            <Link
              key={item}
              href={`/admin/daily?day=${item}`}
              className={`rounded-full px-3 py-1 ${
                item === day ? "bg-slate-900 text-white" : "text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
              }`}
            >
              {formatDate(item)}
            </Link>
          ))}
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
          {stats.map(([label, value]) => (
            <div key={label} className="rounded-xl bg-slate-50 p-3">
              <dt className="text-xs text-slate-500">{label}</dt>
              <dd className="mt-1 text-lg font-bold">{value}</dd>
            </div>
          ))}
        </dl>
        {digest.topBrands.length > 0 && (
          <p className="mt-3 text-sm text-slate-600">
            Чаще всего выставляли: {digest.topBrands.map((item) => `${item.brand} (${item.count})`).join(", ")}.
          </p>
        )}
        {!process.env.NEXT_PUBLIC_SITE_URL && (
          <p className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-800">
            Адрес сайта не задан, в текстах постов стоит заглушка. Когда появится домен, добавьте строку
            NEXT_PUBLIC_SITE_URL=https://... в файл .env.local и перезапустите сайт.
          </p>
        )}
      </div>

      <div className="space-y-10">
        <Post
          layout="list"
          image={{ kicker: "ТОП 5 ЗА СУТКИ", title: "Ниже рынка 💸", footer: "Рынок: медиана похожих машин у других продавцов Ташкента" }}
          fileName={`nizhe-rynka-${day}.png`}
          day={day}
          title="Пост 1. Ниже рынка"
          note="В наличии, с ценой и фото, самая большая выгода в долларах против похожих машин. Оценка рынка по 8 и более похожим."
          listings={digest.deals}
          text={caption("💸 Ниже рынка", digest, digest.deals, true)}
          empty="За этот день нет машин ниже рынка с надёжной оценкой."
          channel={channel}
          sent={sent}
        />
        <Post
          layout="tiles"
          image={{ kicker: "ТОП 5 ЗА СУТКИ", title: "Самые красивые 💎", footer: "Машины в наличии в Ташкенте" }}
          fileName={`samye-krasivye-${day}.png`}
          day={day}
          title="Пост 2. Самые красивые"
          note="Самые дорогие машины дня в наличии, с ценой и фото. Машины из первого поста сюда не попадают."
          listings={digest.best}
          text={caption("💎 Самые красивые", digest, digest.best, false)}
          empty="За этот день нет машин с ценой и фото."
          channel={channel}
          sent={sent}
        />
        <Post
          layout="tiles"
          image={{ kicker: "ПОДБОРКА ДНЯ", title: pick.theme.title, footer: `Ташкент ${pick.window}: ${themeSummary(pick)}` }}
          fileName={`podborka-${day}-${themeIndex + 1}.png`}
          day={day}
          title={`Пост 3. Подборка дня: ${pick.theme.title}`}
          note={`Тема ${themeIndex + 1} из ${DAILY_THEMES.length}${themeIndex === todaysTheme ? ", по расписанию на этот день" : ", выбрана вручную"}. Случайные ${pick.listings.length} из ${pick.found} машин в продаже ${pick.window}. Итоги: ${themeSummary(pick)}.`}
          listings={pick.listings}
          text={themeCaption(pick, digest)}
          empty={`По теме «${pick.theme.title}» машин в продаже за 90 дней не нашлось.`}
          channel={channel}
          sent={sent}
        >
          {pick.stats.fastSold.length > 0 && (
            <div className="mb-4 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
              <p className="font-semibold">Быстрее всех ушли {pick.window}</p>
              <ul className="mt-1 space-y-0.5">
                {pick.stats.fastSold.map((listing) => (
                  <li key={listing.id}>
                    <Link href={`/cars/${listing.id}`} className="hover:underline">
                      {listingTitle(listing)}
                    </Link>
                    , {formatPrice(listing.price, listing.currency)}: продана {sellTerm(listing.daysToSell!)}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="mb-4 flex flex-wrap gap-2 text-xs">
            {DAILY_THEMES.map((theme, index) => (
              <Link
                key={theme.title}
                href={`/admin/daily?day=${day}&theme=${index}`}
                className={`rounded-full px-2.5 py-1 ${
                  index === themeIndex
                    ? "bg-slate-900 text-white"
                    : index === todaysTheme
                      ? "text-brand-700 ring-1 ring-brand-600"
                      : "text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"
                }`}
              >
                {index + 1}. {theme.title}
              </Link>
            ))}
          </div>
        </Post>
      </div>
    </>
  );
}

type PostProps = {
  layout: "list" | "tiles";
  image: { kicker: string; title: string; footer: string };
  fileName: string;
  day: string;
  title: string;
  note: string;
  listings: Listing[];
  text: string;
  empty: string;
  children?: React.ReactNode; // доп. блок под заголовком: переключатель тем
  channel?: string; // канал бота; нет: публикация в канал выключена
  sent: Record<string, PublishedPost>; // что уже уходило в канал
};

function Post({ layout, image, fileName, day, title, note, listings, text, empty, children, channel, sent }: PostProps) {
  return (
    <section data-post={fileName.replace(/\.png$/, "")} data-sent={sent[fileName.replace(/\.png$/, "")] ? "1" : undefined}>
      <h3 className="text-lg font-bold">{title}</h3>
      <p className="mt-1 mb-4 text-sm text-slate-500">{note}</p>
      {children}
      {listings.length === 0 ? (
        <p className="text-sm text-slate-500">{empty}</p>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <PostImage
            layout={layout}
            kicker={image.kicker}
            title={image.title}
            footer={image.footer}
            date={formatDate(day)}
            items={listings.map((listing) => imageItem(listing, layout === "list"))}
            fileName={fileName}
            caption={text}
            channel={channel}
            published={sent[fileName.replace(/\.png$/, "")]}
          />
          <div className="min-w-0">
            <p className="mb-2 text-xs font-semibold tracking-wide text-slate-400 uppercase">Машины на картинке</p>
            <ol className="mb-5 space-y-1 text-sm">
              {listings.map((listing, index) => (
                <li key={listing.id}>
                  {index + 1}.{" "}
                  <Link href={`/cars/${listing.id}`} className="text-brand-700 hover:underline">
                    {listingTitle(listing)}
                  </Link>{" "}
                  <span className="text-slate-500">{formatPrice(listing.price, listing.currency)}</span>
                </li>
              ))}
            </ol>
            <p className="mb-2 text-xs font-semibold tracking-wide text-slate-400 uppercase">Подпись к картинке</p>
            <CopyText text={text} />
          </div>
        </div>
      )}
    </section>
  );
}
