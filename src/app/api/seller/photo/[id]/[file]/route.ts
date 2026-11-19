// GET /api/seller/photo/<id объявления>/<файл>: отдаёт фото, которое продавец загрузил в форме.
// Фото лежат в .data/uploads, а не в public, поэтому раздаём их сами.

import { readFile } from "node:fs/promises";
import { sellerPhotoFile } from "@/lib/seller-listings";

type Context = { params: Promise<{ id: string; file: string }> };

export async function GET(_request: Request, { params }: Context) {
  const { id, file } = await params;
  const filePath = sellerPhotoFile(id, file);
  if (!filePath) return new Response("Not found", { status: 404 });
  try {
    const bytes = await readFile(filePath);
    return new Response(new Uint8Array(bytes), {
      headers: {
        "Content-Type": "image/jpeg",
        // Фото объявления не меняется: браузер может держать его у себя сутки
        "Cache-Control": "public, max-age=86400",
      },
    });
  } catch {
    return new Response("Not found", { status: 404 });
  }
}
