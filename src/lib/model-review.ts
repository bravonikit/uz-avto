// Очередь «Спорные модели»: объявления, где справочник (parser/models_ref.py) не смог уверенно
// определить марку и модель или разбор спорит с текстом поста.
//   parser/data/models_disputed.json  очередь с подсказками и фото, пишет parser/apply_models.py при выгрузке
//   parser/data/model_decisions.json  решения из админки: {"id": {"brand", "model"}} | {"keep": true} | {"hide": true}
//   parser/data/models_list.json      справочник марка -> модели для подсказок в форме
// Решение попадает на сайт после следующей выгрузки (run_daily.sh или python export_to_site.py).

import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const DATA = path.join(process.cwd(), "parser", "data");
const DISPUTED_FILE = path.join(DATA, "models_disputed.json");
const DECISIONS_FILE = path.join(DATA, "model_decisions.json");
const LIST_FILE = path.join(DATA, "models_list.json");

export type ModelCandidate = { brand: string; model: string; source: string; score: number };
export type ModelDispute = {
  id: string;
  url: string | null;
  account: string | null;
  reason: string | null;
  brand: string | null;
  model: string | null;
  title: string | null;
  year: number | null;
  mileage_km: number | null;
  price: number | null;
  date: string | null;
  text: string;
  candidates: ModelCandidate[];
  photos: string[];
};
export type ModelDecision = { brand: string; model: string } | { keep: true } | { hide: true };

async function readJson<T>(file: string, empty: T): Promise<T> {
  try {
    return JSON.parse(await readFile(file, "utf8")) as T;
  } catch {
    return empty; // файла нет: выгрузку ещё не запускали или решений пока не было
  }
}

// Изменения по очереди, чтобы два клика подряд не затёрли друг друга
let queue: Promise<unknown> = Promise.resolve();
function inQueue<T>(task: () => Promise<T>): Promise<T> {
  const result = queue.then(task);
  queue = result.catch(() => undefined);
  return result;
}

export async function getModelQueue(): Promise<{ items: ModelDispute[]; decided: number }> {
  const [all, decisions] = await Promise.all([
    readJson<ModelDispute[]>(DISPUTED_FILE, []),
    readJson<Record<string, ModelDecision>>(DECISIONS_FILE, {}),
  ]);
  const items = all.filter((item) => !(item.id in decisions));
  return { items, decided: all.length - items.length };
}

export async function getModelList(): Promise<Record<string, string[]>> {
  return readJson<Record<string, string[]>>(LIST_FILE, {});
}

// Записывает решение. Принимаем только объявления из очереди.
export function decideModel(id: string, decision: ModelDecision): Promise<boolean> {
  return inQueue(async () => {
    const all = await readJson<ModelDispute[]>(DISPUTED_FILE, []);
    if (!all.some((item) => item.id === id)) return false;
    const decisions = await readJson<Record<string, ModelDecision>>(DECISIONS_FILE, {});
    decisions[id] = decision;
    await mkdir(DATA, { recursive: true });
    await writeFile(DECISIONS_FILE, JSON.stringify(decisions, null, 1));
    return true;
  });
}
