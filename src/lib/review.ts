// Журнал ручного разбора: то, что парсер не решил сам и оставил человеку.
// Очереди пишет parser/export_to_site.py при каждом прогоне, решения из админки он читает при следующем:
//   parser/data/cross_seller_candidates.json  пары «похоже на одну машину у разных продавцов»
//   parser/data/pair_decisions.json           решения по парам: {"id1|id2": "same" или "different"}
//   parser/data/price_suspects.json           объявления со странной ценой (на сайте цена скрыта)
//   parser/data/price_overrides.json          решения по ценам: {"id": 12500} или {"id": null}, если цены нет
// Решение меняет сайт после следующего прогона парсера (run_daily.sh).

import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const DATA = path.join(process.cwd(), "parser", "data");
const PAIRS_FILE = path.join(DATA, "cross_seller_candidates.json");
const PAIR_DECISIONS_FILE = path.join(DATA, "pair_decisions.json");
const SUSPECTS_FILE = path.join(DATA, "price_suspects.json");
const PRICE_OVERRIDES_FILE = path.join(DATA, "price_overrides.json");

type PairSide = { id: string; account: string; price: number | null; url: string };
export type PairCandidate = { car: string; first: PairSide; second: PairSide };
export type PairDecision = "same" | "different";
export type PriceSuspect = {
  id: string;
  account: string;
  title: string | null;
  year: number | null;
  price: number | null;
  reason: string;
  url: string;
};

async function readJson<T>(file: string, empty: T): Promise<T> {
  try {
    return JSON.parse(await readFile(file, "utf8")) as T;
  } catch {
    return empty; // файла нет: парсер ещё не запускали или решений пока не было
  }
}

async function writeJson(file: string, value: unknown) {
  await mkdir(DATA, { recursive: true });
  await writeFile(file, JSON.stringify(value, null, 1));
}

// Изменения делаем по очереди, чтобы два клика подряд не затёрли друг друга
let queue: Promise<unknown> = Promise.resolve();

function inQueue<T>(task: () => Promise<T>): Promise<T> {
  const result = queue.then(task);
  queue = result.catch(() => undefined);
  return result;
}

// Ключ пары не зависит от порядка: так же его строит parser/export_to_site.py
export function pairKey(firstId: string, secondId: string) {
  return [firstId, secondId].sort().join("|");
}

// Пары без решения. Первыми идут с одинаковой ценой (почти наверняка одна машина), дальше по росту разницы цен.
export async function getPairQueue(): Promise<{ pairs: PairCandidate[]; decided: number }> {
  const [all, decisions] = await Promise.all([
    readJson<PairCandidate[]>(PAIRS_FILE, []),
    readJson<Record<string, PairDecision>>(PAIR_DECISIONS_FILE, {}),
  ]);
  const gap = (pair: PairCandidate) =>
    pair.first.price && pair.second.price
      ? Math.abs(pair.first.price - pair.second.price) / Math.max(pair.first.price, pair.second.price)
      : 1;
  const pairs = all
    .filter((pair) => !(pairKey(pair.first.id, pair.second.id) in decisions))
    .sort((a, b) => gap(a) - gap(b));
  return { pairs, decided: all.length - pairs.length };
}

// Записывает решение по паре. Принимаем только пары из очереди парсера.
export function decidePair(firstId: string, secondId: string, decision: PairDecision): Promise<boolean> {
  return inQueue(async () => {
    const key = pairKey(firstId, secondId);
    const all = await readJson<PairCandidate[]>(PAIRS_FILE, []);
    if (!all.some((pair) => pairKey(pair.first.id, pair.second.id) === key)) return false;
    const decisions = await readJson<Record<string, PairDecision>>(PAIR_DECISIONS_FILE, {});
    decisions[key] = decision;
    await writeJson(PAIR_DECISIONS_FILE, decisions);
    return true;
  });
}

// Странные цены без решения
export async function getPriceQueue(): Promise<{ suspects: PriceSuspect[]; decided: number }> {
  const [all, overrides] = await Promise.all([
    readJson<PriceSuspect[]>(SUSPECTS_FILE, []),
    readJson<Record<string, number | null>>(PRICE_OVERRIDES_FILE, {}),
  ]);
  const suspects = all.filter((item) => !(item.id in overrides));
  return { suspects, decided: all.length - suspects.length };
}

// Записывает проверенную цену в долларах. null значит «цены в посте нет».
export function decidePrice(id: string, price: number | null): Promise<boolean> {
  return inQueue(async () => {
    const all = await readJson<PriceSuspect[]>(SUSPECTS_FILE, []);
    if (!all.some((item) => item.id === id)) return false;
    const overrides = await readJson<Record<string, number | null>>(PRICE_OVERRIDES_FILE, {});
    overrides[id] = price;
    await writeJson(PRICE_OVERRIDES_FILE, overrides);
    return true;
  });
}
