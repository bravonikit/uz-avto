// POST /api/view: браузер сообщает, что открыта страница. В ответ общее число просмотров.

import { addView } from "@/lib/views";

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as { page?: unknown } | null;
  const page = typeof body?.page === "string" ? body.page : "";
  // Принимаем только адреса страниц сайта, не длиннее 200 символов
  if (!page.startsWith("/") || page.length > 200) {
    return Response.json({ error: "bad page" }, { status: 400 });
  }
  return Response.json({ total: await addView(page) });
}
