// Кабинет продавца: его объявления и кнопка «Подать объявление». Адрес: /cabinet
// Продавца узнаём по куке браузера (src/lib/seller-session.ts), входа по телефону пока нет.

import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { formatDate, formatMileage, formatPrice } from "@/lib/format";
import {
  getSellerListings,
  sellerPhotoUrl,
  STATUS_LABELS,
  type SellerListing,
  type SellerListingStatus,
} from "@/lib/seller-listings";
import { getSellerId } from "@/lib/seller-session";
import { DeleteButton } from "./DeleteButton";

export const metadata: Metadata = { title: "Кабинет продавца" };

// Цвет метки статуса в списке
const STATUS_COLORS: Record<SellerListingStatus, string> = {
  moderation: "bg-amber-50 text-amber-800",
  active: "bg-emerald-50 text-emerald-800",
  rejected: "bg-red-50 text-red-700",
  sold: "bg-slate-100 text-slate-600",
};

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export default function CabinetPage({ searchParams }: Props) {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Кабинет продавца</h1>
        <Link
          href="/sell"
          className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
        >
          + Подать объявление
        </Link>
      </div>
      {/* Кто открыл кабинет, узнаём из куки, поэтому список показывается «на лету» */}
      <Suspense fallback={<p className="text-slate-400">Загружаем ваши объявления…</p>}>
        <MyListings searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function MyListings({ searchParams }: Props) {
  const [params, sellerId] = await Promise.all([searchParams, getSellerId()]);
  const listings = sellerId ? await getSellerListings(sellerId) : [];
  const justAdded = typeof params.new === "string" && listings.some((listing) => listing.id === params.new);

  if (listings.length === 0) {
    return (
      <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-slate-200">
        <h2 className="text-lg font-bold">У вас пока нет объявлений</h2>
        <p className="mt-2 text-sm text-slate-500">
          Подайте первое: марка, год, пробег, цена и несколько фото. Это бесплатно.
        </p>
        <Link
          href="/sell"
          className="mt-5 inline-block rounded-xl bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-700"
        >
          Подать объявление
        </Link>
      </div>
    );
  }

  return (
    <>
      {justAdded && (
        <p className="mb-4 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800">
          Объявление принято и отправлено на проверку. После проверки оно появится на сайте.
        </p>
      )}
      <p className="mb-3 text-sm text-slate-500">Мои объявления: {listings.length}</p>
      <ul className="space-y-3">
        {listings.map((listing) => (
          <ListingRow key={listing.id} listing={listing} />
        ))}
      </ul>
      <p className="mt-6 text-xs text-slate-400">
        Кабинет пока привязан к этому браузеру: с другого телефона или компьютера объявления не видны.
      </p>
    </>
  );
}

function ListingRow({ listing }: { listing: SellerListing }) {
  const title = `${listing.brand} ${listing.model}, ${listing.year}`;
  const details = [formatMileage(listing.mileage), listing.transmission, listing.fuel, listing.city].filter(Boolean);

  return (
    <li className="flex gap-4 rounded-2xl bg-white p-3 shadow-sm ring-1 ring-slate-200">
      {/* eslint-disable-next-line @next/next/no-img-element -- фото продавца лежит вне папки public */}
      <img
        src={sellerPhotoUrl(listing.id, listing.photos[0])}
        alt=""
        className="h-24 w-32 shrink-0 rounded-xl bg-slate-100 object-cover sm:h-28 sm:w-40"
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
          <h2 className="font-semibold">{title}</h2>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[listing.status]}`}>
            {STATUS_LABELS[listing.status]}
          </span>
        </div>
        <p className="mt-0.5 font-bold">{formatPrice(listing.price, listing.currency)}</p>
        <p className="mt-0.5 truncate text-sm text-slate-500">{details.join(" · ")}</p>
        {listing.status === "rejected" && (
          <p className="mt-1 text-sm text-red-700">
            {listing.rejectReason ? `Причина: ${listing.rejectReason}` : "Объявление не прошло проверку."}
          </p>
        )}
        {(listing.status === "active" || listing.status === "sold") && (
          <Link href={`/cars/${listing.id}`} className="mt-1 text-sm text-brand-700 hover:underline">
            Открыть на сайте
          </Link>
        )}
        <div className="mt-auto flex items-center justify-between pt-2 text-xs text-slate-400">
          <span>
            Подано {formatDate(listing.createdAt)} · фото: {listing.photos.length}
          </span>
          <DeleteButton id={listing.id} title={title} />
        </div>
      </div>
    </li>
  );
}
