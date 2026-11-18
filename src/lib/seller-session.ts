// Кто сейчас в кабинете продавца.
// Входа по телефону или Telegram пока нет, поэтому продавца узнаём по куке в его браузере:
// при первой подаче объявления выдаём случайный номер и запоминаем на год.
// С другого телефона или после очистки браузера кабинет будет пустым.
// Когда появится вход, поменяется только этот файл.

import { randomUUID } from "node:crypto";
import { cookies } from "next/headers";

const COOKIE = "seller_id";
const YEAR_SECONDS = 60 * 60 * 24 * 365;

// Номер продавца из куки. Нет куки: человек ещё ничего не подавал.
export async function getSellerId(): Promise<string | undefined> {
  const value = (await cookies()).get(COOKIE)?.value;
  return value && /^[0-9a-f-]{36}$/.test(value) ? value : undefined;
}

// То же, но если номера ещё нет, выдаёт новый. Вызывать можно только из серверных действий.
export async function ensureSellerId(): Promise<string> {
  const existing = await getSellerId();
  if (existing) return existing;
  const id = randomUUID();
  (await cookies()).set(COOKIE, id, {
    httpOnly: true, // скрипты на странице куку не видят
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    maxAge: YEAR_SECONDS,
    path: "/",
  });
  return id;
}
