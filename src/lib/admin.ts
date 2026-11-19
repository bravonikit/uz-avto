// Кто может открыть админку (/admin).
// Пароль задаётся в файле .env.local в корне проекта строкой ADMIN_PASSWORD=... (файл в git не попадает).
// Пока пароля нет, админка открыта только при локальной разработке (npm run dev),
// а на настоящем сервере закрыта совсем.

import { createHmac, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";

const COOKIE = "admin_session";
const MONTH_SECONDS = 60 * 60 * 24 * 30;

function password() {
  return process.env.ADMIN_PASSWORD || undefined;
}

// В куке лежит не сам пароль, а его отпечаток: по куке пароль не восстановить
function sessionToken(value: string) {
  return createHmac("sha256", value).update("uz-avto-admin").digest("hex");
}

function sameText(first: string, second: string) {
  const a = Buffer.from(first);
  const b = Buffer.from(second);
  return a.length === b.length && timingSafeEqual(a, b);
}

// open: пароля нет, идёт локальная разработка; password: нужен вход; closed: сервер без пароля
export function adminMode(): "open" | "password" | "closed" {
  if (password()) return "password";
  return process.env.NODE_ENV === "development" ? "open" : "closed";
}

export async function isAdmin(): Promise<boolean> {
  const mode = adminMode();
  if (mode !== "password") {
    await cookies(); // страница админки всегда собирается «на лету», а не заранее
    return mode === "open";
  }
  const token = (await cookies()).get(COOKIE)?.value;
  return Boolean(token) && sameText(token!, sessionToken(password()!));
}

// Проверяет пароль и запоминает вход на месяц. Вызывать только из серверных действий.
export async function signInAdmin(entered: string): Promise<boolean> {
  const expected = password();
  if (!expected || !sameText(sessionToken(entered), sessionToken(expected))) return false;
  (await cookies()).set(COOKIE, sessionToken(expected), {
    httpOnly: true,
    sameSite: "strict",
    secure: process.env.NODE_ENV === "production",
    maxAge: MONTH_SECONDS,
    path: "/",
  });
  return true;
}

export async function signOutAdmin() {
  (await cookies()).delete(COOKIE);
}
