"""Справочник марок и моделей uz-avto.

Каноничное имя машины = марка + модель (+ поколение, если поколения сильно
отличаются по цене: Malibu 1 и Malibu 2, Nexia 2 и Nexia 3, Tracker 1 и 2).
Комплектация (MAX, PRO, Champion, позиция) в ключ не входит, лежит в variant.

Как пользоваться:
    from models_ref import normalize
    normalize("BYD", "Chepion", title="Byd Chepion 605", year=2024)
    -> {"brand": "BYD", "model": "Song Plus", "generation": None,
        "variant": "Champion", "kind": "car", "status": "ok", ...}

status:
    ok        модель определена
    guess     модель определена по году или по косвенным словам, стоит глянуть
    disputed  не смогли определить или марка спорит с текстом (в отчёт)

Источники названий: наши объявления, avtoelon.uz и olx.uz (ноябрь 2026).
"""
from __future__ import annotations

import re

# Кириллица, похожая на латиницу: "Sаntafe", "IХ3", "С16" пишут вперемешку
LOOKALIKE = str.maketrans("аеорсхукмтвн", "aeopcxykmtbh")


def _norm(text: str | None) -> str:
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"[ _]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _variants(text: str) -> list[str]:
    """Текст как есть и с кириллицей, заменённой на латиницу."""
    t = _norm(text)
    alt = t.translate(LOOKALIKE)
    return [t] if alt == t else [t, alt]


# ---------------------------------------------------------------------------
# Марки: каноничное имя -> (регулярка написаний, тип)
# Тип: car, truck (грузовые и спецтехника), moto. На сайте авто показываем car.
# ---------------------------------------------------------------------------
BRANDS: dict[str, tuple[str, str]] = {
    "Chevrolet": (r"chevrolet|chevy|шевроле|шеврале", "car"),
    "Daewoo": (r"daewoo|деу|дэу", "car"),
    "Ravon": (r"ravon|равон", "car"),
    "BYD": (r"\bbyd\b|бид|бyd", "car"),
    "Denza": (r"denza|денза", "car"),
    "Yangwang": (r"yangwang|yang wang", "car"),
    "BMW": (r"\bbmw\b|бмв", "car"),
    "Mercedes-Benz": (r"mercedes|mersedes|mersedez|merc\b|мерседес|мерс\b|benz\b|maybach|майбах", "car"),
    "GAC": (r"\bgac\b|trumpchi|aion|айон|aйон", "car"),
    "Zeekr": (r"zeekr|zeeker|зикр|зекр", "car"),
    "Lixiang": (r"lixiang|li xiang|li auto|\bli\b|лисян|ликсианг", "car"),
    "Kia": (r"\bkia\b|киа", "car"),
    "Hyundai": (r"hyundai|hundai|хендай|хундай|хюндай", "car"),
    "Genesis": (r"genesis|генезис", "car"),
    "Dongfeng": (r"dongfeng|dong feng|dongfen|донгфенг|донфенг", "car"),
    "Forthing": (r"forthing", "car"),
    "Voyah": (r"voyah|вояж|воя", "car"),
    "Leapmotor": (r"leapmotors?|leap motor|липмотор", "car"),
    "Toyota": (r"toyota|тойота", "car"),
    "Lexus": (r"lexus|лексус", "car"),
    "Changan": (r"changan|chagan|chana\b|чанган", "car"),
    "Deepal": (r"deepal|дипал", "car"),
    "Audi": (r"\baudi\b|ауди", "car"),
    "Hongqi": (r"hongqi|хунчи|хонгчи", "car"),
    "Land Rover": (r"land rover|range rover|\brange\b|рендж|ренж", "car"),
    "Porsche": (r"porsche|порше", "car"),
    "Jetour": (r"jetour|джетур", "car"),
    "Volkswagen": (r"volkswagen|\bvw\b|фольксваген", "car"),
    "Tesla": (r"tesla|тесла", "car"),
    "Chery": (r"chery|cherry|чери", "car"),
    "Exeed": (r"exeed", "car"),
    "Bestune": (r"bestune", "car"),
    "FAW": (r"\bfaw\b", "car"),
    "Nissan": (r"nissan|ниссан", "car"),
    "Venucia": (r"venucia|venuchi", "car"),
    "XPeng": (r"xpeng|x-peng|сяопэн", "car"),
    "Geely": (r"geely|джили", "car"),
    "Livan": (r"livan", "car"),
    "Jiyue": (r"jiyue|baidu", "car"),
    "Aito": (r"\baito\b|аито", "car"),
    "Seres": (r"seres", "car"),
    "Avatr": (r"avatr|аватр", "car"),
    "Xiaomi": (r"xiaomi|сяоми|ксиоми", "car"),
    "Lynk & Co": (r"lynk", "car"),
    "Haval": (r"haval|хавал|хавейл", "car"),
    "Great Wall": (r"great wall", "car"),
    "Tank": (r"\btank\b", "car"),
    "Ora": (r"\bora\b", "car"),
    "Bentley": (r"bentley|бентли", "car"),
    "Rolls-Royce": (r"rolls|royce|royse|роллс", "car"),
    "Neta": (r"\bneta\b|нета", "car"),
    "Cadillac": (r"cadillac|кадиллак", "car"),
    "Lada": (r"\blada\b|\bvaz\b|ваз|лада|жигули", "car"),
    "Lamborghini": (r"lamborghini|ламборгини", "car"),
    "Ferrari": (r"ferrari|феррари", "car"),
    "Ford": (r"\bford\b|форд", "car"),
    "Honda": (r"honda|хонда", "car"),
    "Mazda": (r"mazda|мазда", "car"),
    "JAC": (r"\bjac\b", "car"),
    "MG": (r"\bmg\b", "car"),
    "GMC": (r"\bgmc\b", "car"),
    "BAIC": (r"\bbaic\b|beijing", "car"),
    "BAW": (r"\bbaw\b", "car"),
    "Mini": (r"\bmini\b", "car"),
    "Dodge": (r"dodge", "car"),
    "Ram": (r"\bram\b", "car"),
    "Skoda": (r"skoda|шкода", "car"),
    "IM": (r"\bim\b|im motors", "car"),
    "Maextro": (r"maextro", "car"),
    "Roewe": (r"roewe", "car"),
    "Renault": (r"renault|рено", "car"),
    "NIO": (r"\bnio\b", "car"),
    "ONVO": (r"onvo", "car"),
    "Infiniti": (r"infiniti|инфинити", "car"),
    "Rox": (r"\brox\b|polar stone", "car"),
    "Buick": (r"buick|бьюик", "car"),
    "Volvo": (r"volvo|вольво", "car"),
    "Polestar": (r"polestar|polistar", "car"),
    "Smart": (r"\bsmart\b", "car"),
    "Jeep": (r"\bjeep\b", "car"),
    "Kaiyi": (r"kaiyi", "car"),
    "iCar": (r"icar", "car"),
    "Soueast": (r"soueast", "car"),
    "Wuling": (r"wuling", "car"),
    "UAZ": (r"\buaz\b|уаз", "car"),
    "Enovate": (r"enovate", "car"),
    "Weltmeister": (r"weltmeister", "car"),
    "Fiat": (r"\bfiat\b", "car"),
    "Skywell": (r"skywell", "car"),
    "SsangYong": (r"ssang ?yong|kgm", "car"),
    "Stelato": (r"stelato", "car"),
    "Aston Martin": (r"aston", "car"),
    "Hycan": (r"hycan", "car"),
    "Mitsubishi": (r"mitsubishi|мицубиси", "car"),
    "Peugeot": (r"peugeot|пежо", "car"),
    "Lucid": (r"lucid", "car"),
    "Lingbox": (r"lingbox", "car"),
    "Isuzu": (r"isuzu", "truck"),
    "Shineray": (r"shineray", "truck"),
    "Shacman": (r"shacman|шакман", "truck"),
    "Sinotruk": (r"sinotruk|howo|хово", "truck"),
    "Sitrak": (r"sitrak", "truck"),
    "Chenglong": (r"chenglong|cenylon", "truck"),
    "QJMotor": (r"qjmotor", "moto"),
    "Benda": (r"benda", "moto"),
}

# Марки, которые парсер писал иначе: сводим к каноничной
BRAND_MERGE = {
    "Xpeng": "XPeng", "Howo": "Sinotruk", "Li": "Lixiang", "Li Auto": "Lixiang",
    "Mercedes": "Mercedes-Benz", "Dong Feng": "Dongfeng", "Cherry": "Chery", "ВАЗ": "Lada", "Vaz": "Lada",
}

# ---------------------------------------------------------------------------
# Модели: марка -> список (модель, регулярка, доп. правила). Порядок важен:
# сначала длинные и точные (Han L раньше Han, Malibu XL раньше Malibu).
# Доп. правила:
#   gen      регулярка поколения в тексте, группа 1 = номер
#   by_year  [(год от, год до, поколение)] если номер не написан
#   kind     truck / moto, если модель не легковая у легковой марки
# ---------------------------------------------------------------------------
M = dict  # короткая запись
MODELS: dict[str, list[tuple[str, str, dict]]] = {
    "Chevrolet": [
        ("Malibu XL", r"malibu\W*xl", M()),
        ("Malibu", r"malibu|malibi|малибу", M(gen=r"malibu\W*([12])\b(?!\s*(?:pozi|поз|pz))", gen_words=[(r"prem|primi", "2"), (r"ltz", "1")],
                                             by_year=[(2010, 2017, "1"), (2018, 2030, "2")])),
        ("Gentra", r"gentra|jentra|жентра|джентра", M()),
        ("Lacetti", r"lacetti|lachetti|ласетти|лачетти", M()),
        ("Cobalt", r"cobalt|kobalt|кобальт", M()),
        ("Spark", r"spark|спарк", M()),
        ("Nexia", r"nexia|neksiya|nexiya|нексия|nexia\W*r3", M(gen=r"ne(?:x|ks)iy?a\W*r?([123])\b", gen_words=[(r"ravon|\br3\b", "3")],
                                                         by_year=[(1995, 2008, "1"), (2008, 2016, "2"), (2016, 2030, "3")])),
        ("Tracker", r"tracker|treker|трекер", M(gen=r"tr[ae]c?ker\W*([12])\b(?!\s*(?:pozi|поз|pz))", gen_words=[(r"prem|primi|primer|redline", "2"), (r"ltz", "1")],
                                                by_year=[(2013, 2020, "1"), (2021, 2030, "2")])),
        ("Equinox", r"equinox|ekvinoks|эквинокс", M()),
        ("Captiva", r"captiva|kaptiva|каптива", M()),
        ("Onix", r"onix|оникс", M()),
        ("Traverse", r"traverse|travers|trevers|траверс", M()),
        ("Trailblazer", r"trail ?blazer|treblezer|трейлблейзер", M()),
        ("Blazer", r"blazer", M()),
        ("Monza", r"monza|монза", M()),
        ("Matiz", r"matiz|матиз", M()),
        ("Damas", r"damas|дамас", M()),
        ("Labo", r"labo\b|лабо", M()),
        ("Tahoe", r"tahoe|тахо", M()),
        ("Orlando", r"orlando|орландо", M()),
        ("Epica", r"epica|эпика", M()),
        ("Silverado", r"silverado", M()),
        ("Trax", r"\btrax\b", M()),
        ("Niva", r"niva|нива", M()),
        ("Menlo", r"menlo", M()),
    ],
    "Daewoo": [("Nexia", r"nexia|nexiya|neksiya", M(gen=r"nexia\W*([12])\b", by_year=[(1995, 2008, "1"), (2008, 2016, "2")])),
               ("Matiz", r"matiz", M()), ("Damas", r"damas", M()), ("Tico", r"tico", M())],
    "Ravon": [("R4", r"\br4\b", M()), ("Nexia", r"nexia|nexiya|neksiya|r3", M(gen=r"()", by_year=[(2015, 2030, "3")])), ("Gentra", r"gentra", M()),
              ("Spark", r"spark|r2", M()), ("Matiz", r"matiz", M())],
    "BYD": [
        ("Song Plus", r"song\W*plus|songplus|champ|chemp|chep|chimp|чемпион|чемпён", M()),
        ("Sealion 06", r"sea\W*lion\W*0?6", M()),
        ("Song Pro", r"song\W*pro", M()),
        ("Song L", r"song\W*l\b", M()),
        ("Song Ultra", r"song\W*ultra", M()),
        ("Song", r"\bsong\b", M()),
        ("Yuan Up", r"y\w{0,3}a?n?g?\W*(?:up|ap)\b|yuan\W*up|fuan\W*up|yuap", M()),
        ("Yuan Plus", r"yuan?g?\W*plus|yan\W*plus|atto\W*3", M()),
        ("Han L", r"(?:han|xan|хан)\W*l\b", M()),
        ("Han", r"\bhan\b|\bxan\b|\bхан\b|great han|\bham\b|\bhun\b", M()),
        ("Tang L", r"tang\W*l\b", M()),
        ("Tang", r"\btang\b|datang|great tang", M()),
        ("Qin L", r"(?:qin|chin|цинь)\W*l\b", M()),
        ("Chazor", r"chazor|chazo\b|chaser|destroyer", M()),
        ("Qin Plus", r"qin\W*plus", M()),
        ("Seagull", r"seag|seau|segul|siagel|sigil|sigul|dolphin mini|чайка", M()),
        ("Dolphin", r"dolphin|dolfin", M()),
        ("Sealion 06", r"seal?\w*\W*0?6\b|sealion\W*06", M()),
        ("Sealion 07", r"sealion\W*0?7\b|seal\w*\W*07", M()),
        ("Sealion 05", r"sealion\W*05|seal\W*05", M()),
        ("Seal 08", r"seal\W*08", M()),
        ("Sealion", r"sealion|sealon|sealleon|sealiom", M()),
        ("Seal", r"\bseal\b", M()),
        ("E2", r"\be\W?2\b", M()),
        ("E7", r"\be7\b|э\W*7", M()),
        ("E9", r"\be9\b", M()),
        ("Atto 8", r"atto\W*8", M()),
        ("Atto 3", r"\batto\b", M()),
        ("Xia", r"\bxia\b", M()),
        ("Leopard 3", r"leopard\W*3|titanium\W*3", M()),
        ("Leopard 5", r"leopard\W*5", M()),
        ("Leopard 7", r"leopard\W*7|titanium\W*7", M()),
        ("Leopard 8", r"leopard\W*8", M()),
        ("D1", r"\bd1\b", M()), ("T5", r"\bt5\b", M(kind="truck")),
        ("Song Plus", r"smart\W*605|\b605\b|\b520\b", M(guess=True)),
    ],
    "Denza": [("N9", r"n9", M()), ("Z9", r"z9", M()), ("N7", r"n7", M()), ("D9", r"d9", M()), ("N8L", r"n8", M())],
    "Yangwang": [("U8", r"u8", M())],
    "BMW": [
        ("XM", r"\bxm\b", M()),
        ("X7", r"x7", M()), ("X6", r"x6", M()), ("X5", r"x5", M()), ("X4", r"x4", M()), ("X3", r"\bx3", M()),
        ("X1", r"\bx1", M()), ("iX3", r"ix\W*3", M()), ("iX1", r"ix\W*1", M()), ("iX", r"\bix\b", M()),
        ("i7", r"\bi\W?7\b", M()),
        ("i5", r"\bi\W?5\b|i5 ", M()),
        ("i4", r"\bi\W?4\b", M()), ("i3", r"\bi\W?3\b|i35l", M()),
        ("M8", r"\bm8\b|m850", M()), ("M5", r"\bm5\b", M()), ("M4", r"\bm4\b", M()), ("M3", r"\bm3\b", M()),
        ("M2", r"\bm2\b", M()),
        ("8 Series", r"8\W*seri|8 series|840|850", M()),
        ("7 Series", r"7\W*seri|7 series|7seriya|725|728|730|735|740|745|750|760|\b7\b", M()),
        ("5 Series", r"5\W*seri|5 series|518|520|523|525|528|530|535|540|545|550|e39|e60|f10|g30|g60|\b5\b", M()),
        ("4 Series", r"4\W*seri|420|430|440|m440|grand ?coupe|\b4\b", M()),
        ("3 Series", r"3\W*seri|316|318|320|323|325|328|330|335|340|m340|e46|\b3\b", M()),
        ("2 Series", r"m240|220|230", M()),
        ("Z4", r"z4", M()),
        ("S1000RR", r"s1000", M(kind="moto")),
    ],
    "Mercedes-Benz": [
        ("EQE SUV", r"eqe\W*\d*\W*suv", M()),
        ("EQE", r"eqe", M()), ("EQS", r"eqs", M()), ("EQC", r"eqc", M()), ("EQB", r"eqb", M()), ("EQA", r"eqa", M()),
        ("Maybach", r"maybach|майбах|s\W*680|gls\W*600", M()),
        ("G-Class", r"\bg\W*(?:class|63|500|580|55|350|400)|g63|g500|g580|gelik|gelandewagen|гелик|\bg\b", M()),
        ("GLS", r"\bgls", M()), ("GLE", r"\bgle|\bml\b|\bml\W*\d|m-class", M()), ("GLC", r"\bglc", M()), ("GLK", r"\bglk", M()),
        ("GLA", r"\bgla\b|\bgla\W*\d", M()),
        ("CLE", r"\bcle\b|\bcle\W*\d", M()), ("CLS", r"\bcls", M()), ("CLA", r"\bcla\b|\bcla\W*\d", M()), ("CLK", r"\bclk", M()),
        ("AMG GT", r"amg\W*gt|\bgt\b", M()),
        ("SL", r"\bsl\b|5l", M()),
        ("S-Class", r"\bs\W*(?:class|\d{3})|w\W?(?:140|220|221|222|223)|s211|\bs\b", M()),
        ("E-Class", r"\be\W*(?:class|\d{2,3})|w\W?(?:124|210|211|212|213|214)|\be\b", M()),
        ("C-Class", r"\bc\W*(?:class|\d{3})|w\W?(?:202|203|204|205|206)", M()),
        ("CLK", r"w209", M()),
        ("V-Class", r"v-class|viano|vito|\bv\W*\d{3}", M()),
        ("Sprinter", r"sprinter", M()),
        ("Actros", r"actross?", M(kind="truck")),
    ],
    "GAC": [
        ("Aion i60", r"i\W*60|ai60", M()), ("Aion N60", r"n60", M()),
        ("Aion S Plus", r"s\W*plus|splus", M()), ("Aion S7", r"\bs7\b", M()),
        ("Aion Hyper GT", r"hyp\w*|hayper", M()), ("Aion V", r"aion\W*v\b|\bv\b", M()), ("Aion RT", r"\brt\b", M()),
        ("Aion Y Plus", r"y\W*plus", M()), ("Aion LX", r"\blx\b", M()), ("Aion S", r"aion\W*s\b|s580|\bs\b", M()),
        ("GS8", r"gs8", M()), ("S9", r"s9", M()), ("Empow", r"empow", M()), ("M8", r"\bm8\b", M()),
        ("Aion i60", r"\ba\W*60\b|\b60\b|530|650|210\s*km|hybrid|gibrid|гибрид|elek|electr|\bev\b|tok\b", M(guess=True)),
    ],
    "Zeekr": [("9X", r"9\W*[xх]|x9", M()), ("8X", r"8\W*[xх]", M()), ("7X", r"7\W*x|x7", M()), ("001", r"001", M()),
              ("007", r"007", M()), ("009", r"009", M()), ("X", r"zeekr\W*x\b|\bx\b", M())],
    "Lixiang": [("L9", r"l\W*9|i9", M()), ("L8", r"l\W*8", M()), ("L7", r"l\W*7", M()), ("L6", r"l+\W*6", M()),
                ("i8", r"\bi8\b", M()), ("i6", r"\bi6\b", M()), ("Mega", r"mega", M()), ("One", r"\bone\b", M())],
    "Kia": [
        ("K5", r"\bk\W?5\b|ka5|optima", M()), ("K8", r"\bk8\b", M()), ("K9", r"\bk9\b|quoris", M()),
        ("Sportage", r"sport(?:age|ej|ech)", M()), ("Sorento", r"sor+ento|соренто", M()),
        ("Sonet", r"sonet|sanet", M()), ("Seltos", r"seltos", M()), ("Carnival", r"[kcс]arn[ie]v", M()),
        ("Carens", r"carens", M()), ("Stinger", r"stinger|singer", M()), ("Cerato", r"cerato|forte|\bk3\b", M()),
        ("EV9", r"ev\W*9", M()), ("EV6", r"ev\W*6", M()), ("EV5", r"ev\W*5", M()), ("EV4", r"ev\W*4", M()),
        ("EV3", r"ev\W*3", M()), ("PV5", r"pv\W*5", M()),
        ("Bongo", r"bongo", M()), ("Soul", r"soul", M()), ("Rio", r"\brio\b", M()), ("Ray", r"\bray\b", M()),
    ],
    "Hyundai": [
        ("Santa Fe", r"s[aа]nta\W*fe|santafe|\bsanta\b", M()), ("Tucson", r"tucson|tuson|туксон", M()),
        ("Sonata", r"s[oa]n[ao]ta", M()), ("Elantra", r"elantr|avante", M()), ("Grandeur", r"grand\w*|grenier|grang", M()),
        ("Palisade", r"p[ao]lisade", M()), ("Staria", r"staria", M()), ("Starex", r"starex|h-1", M()),
        ("Ioniq 5", r"ioniq\W*5", M()), ("Ioniq 6", r"ioniq\W*6", M()), ("Ioniq", r"ioniq", M()),
        ("Accent", r"acc?s?ent|acsent", M()), ("Creta", r"[cg]reta", M()), ("Porter", r"porter", M()),
        ("i30", r"i30", M()), ("Kona", r"kona", M()), ("Casper", r"casper", M()),
    ],
    "Genesis": [("GV80", r"gv\W*80", M()), ("GV90", r"gv\W*90", M()), ("GV70", r"gv\W*70", M()), ("GV60", r"gv\W*60", M()),
                ("G90", r"g\W*90", M()), ("G80", r"g\W*80", M()), ("G70", r"g\W*70", M())],
    "Dongfeng": [
        ("eπ 008", r"(?:e\W*[pπп]|eπ)?\W*0?08\b|ep\W*008|008|oo8", M()),
        ("eπ 007", r"(?:e\W*[pπп])?\W*007", M()),
        ("Nammi 06", r"nammi", M()),
        ("Aeolus", r"aeolus|aelous|shine|haoji|huge|fengon\W*(?:s?600|580|e5|5)|fengo", M()),
        ("Mengshi", r"hummer|mengshi", M()),
        ("Sky EV01", r"sky", M()),
    ],
    "Forthing": [("T5 EVO", r"t5", M()), ("S7", r"\bs7\b", M()), ("Friday", r"friday", M())],
    "Voyah": [("Free", r"free", M()), ("Dream", r"dream", M()), ("Passion", r"pas+(?:s?ion|iyon)", M()),
              ("Courage", r"courage|kuraj", M()), ("Taishan", r"taishan", M())],
    "Leapmotor": [("C16", r"[cс]\W*16", M()), ("C11", r"[cс]\W*11", M()), ("C10", r"[cс]\W*10", M()),
                  ("C01", r"[cс]\W*01", M()), ("D19", r"d\W*19", M()), ("B10", r"b\W*10", M()), ("A10", r"a\W*10", M()),
                  ("T03", r"t\W*03", M()), ("Lafa 5", r"lafa", M())],
    "Toyota": [
        ("Land Cruiser Prado", r"prado|прадо|\b150\b|250", M()),
        ("Land Cruiser", r"land\W*cruiser|cruiser|\blc\b|lend|\b200\b|\b300\b|лэнд|ленд", M()),
        ("Camry", r"camr|kamri|камри", M()), ("Highlander", r"h\w*l[ae]nder|haylander", M()), ("RAV4", r"rav\W*4", M()),
        ("Corolla", r"corolla|levin", M()), ("Avalon", r"avalon", M()), ("GR86", r"gr\W*86", M()),
        ("Crown", r"crown", M()), ("Prius", r"prius", M()), ("Yaris", r"yaris", M()), ("4Runner", r"4runner", M()),
        ("Tundra", r"tundra", M()), ("Fortuner", r"fortuner", M()), ("Sequoia", r"sequoia", M()),
        ("Alphard", r"alphard", M()), ("bZ3", r"bz3", M()), ("bZ5", r"bz5", M()),
    ],
    "Lexus": [("LX", r"\blx", M()), ("RX", r"\brx", M()), ("GX", r"\bgx", M()), ("ES", r"\bes", M()), ("IS", r"\bis", M()),
              ("LS", r"\bls", M()), ("TX", r"\btx", M()), ("LM", r"\blm", M()), ("GS", r"\bgs", M()), ("NX", r"\bnx", M()),
              ("SC", r"\bsc", M())],
    "Changan": [
        ("Nevo A06", r"a\W*06", M()), ("Nevo A07", r"a\W*07", M()), ("Nevo A05", r"a\W*05", M()),
        ("Nevo Q05", r"q\W*05", M()), ("Nevo Q06", r"q\W*06", M()), ("Nevo Q07", r"q\W*07", M()),
        ("CS55 Plus", r"cs\W*55", M()), ("CS75 Plus", r"cs\W*75", M()), ("UNI-K", r"uni\W*k", M()),
        ("UNI-Z", r"uni\W*z", M()), ("UNI-V", r"uni\W*v", M()), ("UNI-T", r"uni\W*t", M()),
        ("Hunter", r"hunter", M()), ("Benben", r"ben\W*ben|\bben\b", M()), ("Star", r"star|butka|бутка", M(kind="truck")),
        ("Nevo E07", r"e\W*07", M()),
    ],
    "Deepal": [("S07", r"s\W*0?7", M()), ("S09", r"s\W*0?9", M()), ("S05", r"s\W*0?5", M()), ("SL03", r"sl\W*0?3", M()),
               ("L07", r"l\W*07", M()), ("L06", r"l\W*06", M()), ("G318", r"g\W*318", M())],
    "Audi": [
        ("RS7", r"rs\W*7", M()), ("RS6", r"rs\W*6", M()), ("RS5", r"rs\W*5", M()), ("RS3", r"rs\W*3", M()),
        ("Q6 e-tron", r"q6", M()), ("Q8", r"q8", M()), ("Q7", r"q7", M()), ("Q5", r"q5", M()), ("Q4 e-tron", r"q4", M()),
        ("Q2L", r"q2", M()),
        ("A8", r"\ba\W?8", M()), ("A7", r"\ba\W?7", M()), ("A6", r"\ba\W?6|\b55\b", M()), ("A5", r"\ba\W?5", M()),
        ("A4", r"\ba\W?4", M()), ("A3", r"\ba\W?3", M()), ("TT", r"\btt\b", M()), ("E5 Sportback", r"\be5\b", M()), ("E7X", r"e7x", M()),
    ],
    "Hongqi": [("E-QM5", r"e\W*q\W*m|eqm|eq5|\beq\b|510|610", M()), ("E-HS9", r"hs9", M()), ("HS5", r"hs5", M()), ("H5", r"\bh5\b", M()),
               ("H9", r"\bh9\b", M())],
    "Land Rover": [("Range Rover Sport", r"spo\W?rt|p360", M()),
                   ("Range Rover Velar", r"velar", M()), ("Range Rover Evoque", r"evoque", M()),
                   ("Range Rover", r"range|rover|autobiograph|vogue|\bsv\b|\brr\b|рендж", M()), ("Defender", r"defender", M()),
                   ("Freelander", r"freelander", M()), ("Discovery", r"discovery", M())],
    "Porsche": [("911", r"911|992|gt3|turbo s|\bturbo\b", M()), ("Taycan", r"taycan", M()), ("Cayenne", r"cayenne", M()),
                ("Macan", r"macan", M()), ("Panamera", r"panamera", M())],
    "Jetour": [("X70 Plus", r"x\W*70\W*plus", M()), ("X70", r"x\W*70", M()), ("X90 Plus", r"x\W*90", M()),
               ("X95", r"x\W*95", M()), ("X50", r"x\W*50", M()), ("T2", r"t\W*2|т2", M()), ("T1", r"t\W*1\b", M()),
               ("Dashing", r"dash", M())],
    "Volkswagen": [("ID.4", r"id\W*4", M()), ("ID.6", r"id\W*6", M()), ("ID.3", r"id\W*3", M()), ("ID.7", r"id\W*7", M()),
                   ("ID. Era 9X", r"era|9x|id\W*9", M()), ("ID. Unyx", r"unyx", M()), ("Golf", r"golf", M()),
                   ("Passat", r"passat", M()), ("Touareg", r"touareg", M()), ("Caddy", r"caddy", M()),
                   ("Tiguan", r"tiguan", M())],
    "Tesla": [("Model 3", r"model\W*3|\b3\b", M()), ("Model Y", r"model\W*y", M()), ("Model S", r"model\W*s", M()),
              ("Model X", r"model\W*x", M()), ("Cybertruck", r"cyber", M()), ("Roadster", r"roadster", M())],
    "Chery": [("Tiggo 8 Pro Max", r"tiggo\W*8\W*pro\W*max", M()), ("Tiggo 8 Pro", r"tiggo\W*8", M()),
              ("Tiggo 7 Pro", r"tiggo\W*7|\b7\W*pro", M()), ("Tiggo 2 Pro", r"tiggo\W*2", M()),
              ("Tiggo 4 Pro", r"tiggo\W*4", M()), ("Tiggo 9", r"tiggo\W*9", M()),
              ("Arrizo 8", r"arr?izo\W*8", M()), ("Arrizo 6 Pro", r"arr?izo", M())],
    "Exeed": [("TXL", r"txl", M()), ("LX", r"\blx\b", M()), ("RX", r"\brx\b", M()), ("VX", r"\bvx\b", M())],
    "Bestune": [("T33", r"t\W*33", M()), ("T55", r"t\W*55", M()), ("T77", r"t\W*77", M()), ("T99", r"t\W*99", M()),
                ("B70", r"b\W*70", M()), ("Yueyi 03", r"yueyi", M()), ("NAT", r"\bnat\b", M())],
    "FAW": [("Bestune T77", r"t77", M()), ("JH6", r"jh6|460|430", M(kind="truck"))],
    "Nissan": [("Maxima", r"max[s]?ima", M()), ("Patrol", r"patrol", M()), ("Sylphy", r"sylphy", M()),
               ("Altima", r"altima", M()), ("N7", r"\bn7\b", M()), ("NX8", r"nx8", M()), ("Qashqai", r"qashqa", M()),
               ("GT-R", r"gt\W*r", M()), ("Teana", r"teana", M())],
    "Venucia": [("Star", r"star", M()), ("VX6", r"vx6", M())],
    "XPeng": [("G9", r"g9", M()), ("G6", r"g6", M()), ("G3", r"g3", M()), ("P7", r"p7", M()), ("X9", r"x9", M()),
              ("GX", r"\bgx\b|\bxg\b", M()), ("Mona M03", r"m03|mona(?!\W*l)", M()), ("Mona L03", r"l03|mona\W*l", M()),
              ("P7+", r"p7\+", M())],
    "Geely": [("Galaxy M9", r"m9", M()), ("Galaxy L7", r"l7", M()), ("Galaxy Starship 7", r"starship", M()),
              ("Galaxy E8", r"ev8|e8", M()), ("Galaxy 700", r"700", M()), ("Monjaro", r"monjaro", M()),
              ("Geometry E", r"geometry", M()), ("Boyue", r"boyue", M()), ("Coolray", r"coolray", M()),
              ("Emgrand", r"emgrand", M()), ("EX5", r"ex5", M())],
    "Livan": [("RL-9", r"rl\W*9", M()), ("7", r"\b7\b", M())],
    "Jiyue": [("07", r"07|robocar", M()), ("01", r"01", M())],
    "Aito": [("M9", r"m\W?9", M()), ("M8", r"m\W?8", M()), ("M7", r"m\W?7", M()), ("M6", r"m\W?6", M()), ("M5", r"m\W?5|seres\W*5", M())],
    "Seres": [("SF5", r"sf5", M())],
    "Avatr": [("12", r"\b0?12\b", M()), ("11", r"\b11\b", M()), ("07", r"07", M()), ("06", r"06", M())],
    "Xiaomi": [("SU7", r"su\W*7", M()), ("YU7", r"yu\W*7", M()), ("YU9", r"yu\W*9", M())],
    "Lynk & Co": [("900", r"900", M()), ("Z10", r"z10", M()), ("08", r"\b08\b", M()), ("07", r"07", M()),
                  ("06", r"\b06\b", M()), ("10 EM-P", r"10\+|\b10\b", M()), ("09", r"09", M()), ("01", r"\b01\b", M())],
    "Haval": [("H6", r"h6", M()), ("Dargo", r"dargo", M()), ("Jolion", r"jolion", M()), ("M6", r"m6", M()),
              ("H9", r"h9", M()), ("Raptor", r"raptor", M())],
    "Bentley": [("Bentayga", r"bentayga|torcal", M()), ("Flying Spur", r"flying", M()), ("Continental GT", r"continental", M())],
    "Rolls-Royce": [("Cullinan", r"cullinan", M()), ("Phantom", r"phantom", M()), ("Spectre", r"spectre", M()),
                    ("Ghost", r"ghost", M()), ("Wraith", r"wraith", M())],
    "Neta": [("S", r"\bs\b|gt\W*s", M()), ("U Pro", r"\bu\b", M()), ("V", r"\bv\b", M()), ("L", r"\bl\b", M()),
             ("Aya", r"aya", M()), ("GT", r"\bgt\b", M())],
    "Cadillac": [("Escalade", r"esc[ao]lade", M()), ("XTS", r"xts", M()), ("Lyriq", r"lyriq", M())],
    "Lada": [("2106", r"2106", M()), ("2107", r"2107", M()), ("Vesta", r"vesta", M()), ("Niva", r"niva|нива|4x4", M()), ("Largus", r"largus", M()), ("XRAY", r"x\W*ray", M()),
             ("2112", r"2112", M()), ("Granta", r"granta", M()), ("Priora", r"priora", M())],
    "Lamborghini": [("Urus", r"urus", M()), ("Revuelto", r"revuelto", M()), ("Huracan", r"huracan", M())],
    "Ferrari": [("SF90", r"sf90", M()), ("Purosangue", r"purosangue", M()), ("296", r"296", M()), ("Amalfi", r"amalfi", M()),
                ("458", r"458", M()), ("12Cilindri", r"12c", M()), ("Roma", r"roma", M())],
    "Ford": [("Mustang", r"mustang", M()), ("Econoline", r"econoline", M()), ("Explorer", r"explorer", M())],
    "Honda": [("Crider", r"crider", M()), ("M-NV", r"m\W*nv", M()), ("Elysion", r"elysion", M()), ("Accord", r"accord", M())],
    "Mazda": [("CX-3", r"cx\W*3", M()), ("3", r"\b3\b", M()), ("6", r"\b6\b", M()), ("EZ-60", r"ez", M()), ("RX-8", r"rx\W*8", M())],
    "JAC": [("S5", r"s5", M()), ("T9", r"t9", M(kind="car")), ("Sunray", r"sunray", M(kind="truck")), ("JS6", r"js6", M())],
    "MG": [("ZS", r"zs", M()), ("Z7", r"\bz7\b", M()), ("7", r"\b0?7\b", M()), ("5", r"\b5\b", M()), ("Cyberster", r"cyber", M())],
    "GMC": [("Sierra", r"sierra", M()), ("Yukon", r"yukon", M()), ("Hummer EV", r"hummer", M()), ("Canyon", r"canyon", M())],
    "BAIC": [("BJ40", r"bj\W*40", M()), ("BJ60", r"bj\W*60", M()), ("212", r"212", M()), ("EU5", r"eu5", M())],
    "BAW": [("212", r"212", M()), ("M7", r"m7", M())],
    "Mini": [("Cooper", r"cooper", M()), ("Countryman", r"countryman", M())],
    "Dodge": [("Challenger", r"chall?enger", M()), ("Charger", r"charger", M()), ("RAM", r"\bram\b", M())],
    "Ram": [("1500", r"1500", M()), ("TRX", r"trx", M())],
    "Skoda": [("Kodiaq", r"kodiaq", M()), ("Octavia", r"octavia", M())],
    "IM": [("LS6", r"ls\W*6", M()), ("LS7", r"ls\W*7", M()), ("LS8", r"ls\W*8", M()), ("LS9", r"ls\W*9", M()),
           ("L6", r"\bl6\b", M()), ("L7", r"\bl7\b", M())],
    "Maextro": [("S800", r"s800", M()), ("V800", r"v800", M())],
    "Roewe": [("D6", r"d6", M()), ("M7", r"m7", M()), ("D7", r"\bd7\b|\b07\b", M()), ("i6", r"i6", M())],
    "Renault": [("Arkana", r"arkana", M()), ("Kaptur", r"kaptur|captur", M()), ("Duster", r"duster", M())],
    "NIO": [("ET5", r"et5", M()), ("ES6", r"es6", M()), ("ES8", r"es8", M()), ("EL8", r"el8", M()), ("ET7", r"et7", M())],
    "ONVO": [("L90", r"l90", M()), ("L60", r"l60", M())],
    "Infiniti": [("QX80", r"qx\W*80|qx", M()), ("QX60", r"qx\W*60", M())],
    "Rox": [("01", r"01", M()), ("Adamas", r"adamas", M())],
    "Buick": [("Velite 6", r"velite", M()), ("Electra E5", r"electra", M())],
    "Volvo": [("XC90", r"xc\W*90", M()), ("XC60", r"xc\W*60", M()), ("EX30", r"ex30", M())],
    "Polestar": [("2", r"\b2\b", M()), ("4", r"\b4\b", M())],
    "Smart": [("#1", r"#1|\b1\b", M()), ("#3", r"#3", M()), ("#5", r"#5|605", M())],
    "Jeep": [("Wrangler", r"wrangler", M()), ("Grand Cherokee", r"grand\W*cherokee", M())],
    "Kaiyi": [("X3 Pro", r"x3", M()), ("X7 Kunlun", r"x7|kunlun", M())],
    "iCar": [("V23", r"v23", M()), ("03", r"\b03\b", M())],
    "Soueast": [("S06", r"s06", M()), ("S07", r"s07", M()), ("S09", r"s09", M())],
    "Wuling": [("Hongguang", r"hongguang", M()), ("Cloud", r"cloud", M()), ("Bingo", r"bingo", M())],
    "UAZ": [("Patriot", r"patriot", M()), ("Hunter", r"hunter", M())],
    "Enovate": [("ME7", r"me7", M())], "Weltmeister": [("W6", r"w6", M()), ("EX5", r"ex5", M())],
    "Fiat": [("500", r"500", M())], "Skywell": [("ET5", r"et5|ev\W*520", M(guess=True))], "SsangYong": [("Torres", r"torres", M()), ("Rexton", r"rexton", M())],
    "Stelato": [("S9", r"s9", M())], "Aston Martin": [("Vantage", r"vantage", M()), ("DBX", r"dbx", M())],
    "Hycan": [("A06", r"a06", M())], "Mitsubishi": [("Pajero", r"pajero", M()), ("Outlander", r"outlander", M())],
    "Lucid": [("Air", r"\bair\b", M()), ("Gravity", r"gravity", M())],
    "Ora": [("Good Cat", r"cat", M())],
    "Shacman": [("X5000", r"x5000", M()), ("M3000S", r"m3000", M())],
    "Sinotruk": [("Howo Max", r"max", M()), ("Howo TX7", r"tx7|th7", M()), ("Howo", r"howo", M())],
    "Sitrak": [("G7", r"g7", M())], "Shineray": [("T30", r"t30", M())], "Chenglong": [("H5", r"h5|270|460", M(guess=True))],
    "QJMotor": [("SRK 600 RR", r"600", M())], "Benda": [("Darkflag 500", r"darkflag", M()), ("Chinchilla", r"chinchilla", M())],
}

# Комплектации и исполнения: в ключ модели не входят, сохраняем в variant
VARIANTS = [
    (r"champ|chemp|chep|chimp|чемпион", "Champion"), (r"\bmax\b", "MAX"), (r"\bpro\b", "PRO"), (r"ultra", "Ultra"),
    (r"flagship", "Flagship"), (r"honor|хонир", "Honor"), (r"\bsmart\b", "Smart"), (r"premier", "Premier"),
    (r"redline", "Redline"), (r"restay|restai|рестайл", "Рестайлинг"), (r"\bdm\W?i\b|hybrid|gibrid|gebrit|hibrid|гибрид", "DM-i"),
    (r"\bev\b|605|520|505", "EV"), (r"amg", "AMG"), (r"brabus", "Brabus"), (r"\bfull\b|фул", "Full"),
]
POSITION = re.compile(r"\b([1-6])\W*(?:-?\s*)(?:pozi\w*|позиц\w*|pz|п)\b|(?:pozi\w*|позиц\w*)\W*([1-6])\b")

# Слова, по которым видно, что это не одна машина и не объявление о продаже
NOT_ONE_CAR = re.compile(r"\b(?:запчаст\w*|zapchast\w*|razbor|разбор)\b")

_brand_re = {b: re.compile(p) for b, (p, _) in BRANDS.items()}
# Что вырезать из текста перед поиском модели, если не всю регулярку марки
STRIP = {"Land Rover": r"land\W*rover", "Mercedes-Benz": r"mercedes|mersedes|mersedez|мерседес|\bbenz\b",
         "Sinotruk": r"sinotruk", "GAC": r"\bgac\b|trumpchi", "Lixiang": r"lixiang|li xiang|li auto|лисян"}
_strip_re = {b: re.compile(p) for b, p in STRIP.items()}

# Марка из разбора, а по тексту видно, что это другая марка (суббренд или ошибка разбора)
REBRAND = {
    "Changan": [(r"deepal", "Deepal")],
    "Geely": [(r"livan", "Livan"), (r"baidu|robocar|jiyue", "Jiyue")],
    "Nissan": [(r"venuc", "Venucia")],
    "Chery": [(r"icar", "iCar")],
    "Dongfeng": [(r"forthing", "Forthing"), (r"chenglong", "Chenglong"), (r"howo", "Sinotruk")],
    "Volvo": [(r"polestar|polistar", "Polestar")],
    "NIO": [(r"imls|\bim\W*ls", "IM"), (r"onvo", "ONVO")],
    "Land Rover": [(r"cruiser|prado", "Toyota")],
    "Ravon": [(r"cob|kobl", "Chevrolet")],
}

# Модели без марки, по которым марку видно однозначно: для проверки, что в тексте не другая машина
DISTINCT = {
    "Chevrolet": r"\bgentra|\bcobalt|\bmalibu|\bnexia|\bneksiya|\btracker|\btreker|\bcaptiva|\bequinox|\bonix\b|\bdamas|\bmatiz|\blacetti|\bmonza|\btraverse|\btahoe",
    "BYD": r"song\W*plus|\bchampion|yuan\W*up|seagull|\bchazor",
    "Toyota": r"land\W*cruiser|\bprado|\bcamry",
    "Hyundai": r"\bsonata|\belantra|\btucson|santa\W*fe",
    "Kia": r"\bsportage|\bsorento|\bk5\b",
    "Mercedes-Benz": r"\bcls\W*\d{3}|\bgle\b|\bgls\b|\bg63\b",
    "Lixiang": r"lixiang|\bl[6-9]\b",
}
_distinct_re = {b: re.compile(p) for b, p in DISTINCT.items()}
_model_re = {b: [(n, re.compile(p), extra) for n, p, extra in ms] for b, ms in MODELS.items()}


def brand_kind(brand: str) -> str:
    return BRANDS.get(brand, ("", "car"))[1]


def canon_brand(brand: str | None) -> str | None:
    if not brand:
        return None
    brand = BRAND_MERGE.get(brand, brand)
    if brand in BRANDS:
        return brand
    for name, rx in _brand_re.items():
        if any(rx.search(v) for v in _variants(brand)):
            return name
    return brand


def find_model(brand: str, text: str) -> tuple[str, dict] | None:
    for name, rx, extra in _model_re.get(brand, []):
        if any(rx.search(v) for v in _variants(text)):
            return name, extra
    return None


def _strip_brand(brand: str, text: str) -> str:
    """Убирает из строки название марки, чтобы \\bx\\b и подобные не цеплялись за марку."""
    t = _norm(text)
    rx = _strip_re.get(brand) or _brand_re.get(brand)
    return rx.sub(" ", t) if rx else t


def brands_in_text(text: str) -> set[str]:
    found = set()
    for v in _variants(text):
        for name, rx in _brand_re.items():
            if rx.search(v):
                found.add(name)
    return found


def _rebrand(brand: str, text: str) -> str:
    for rx, new in REBRAND.get(brand, []):
        if any(re.search(rx, v) for v in _variants(text)):
            return new
    return brand


def _other_car_in(brand: str, model_rx: re.Pattern | None, text: str) -> str | None:
    """В тексте явно другая машина: модель другой марки, а нашей марки и модели нет."""
    if not text.strip():
        return None
    vs = _variants(text)
    if any(_brand_re[brand].search(v) for v in vs if brand in _brand_re):
        return None
    if model_rx and any(model_rx.search(v) for v in vs):
        return None
    for ob, rx in _distinct_re.items():
        if ob != brand and any(rx.search(v) for v in vs):
            return ob
    return None


def normalize(brand: str | None, model: str | None, title: str | None = None,
              year: int | None = None, description: str | None = None) -> dict:
    """Приводит пару марка/модель из разбора к справочнику."""
    raw_brand, raw_model = brand, model
    brand = canon_brand(brand)
    head = "\n".join((description or "").splitlines()[:3])
    if brand:
        brand = _rebrand(brand, " ".join([model or "", title or "", head]))
    out = {"brand": brand, "model": None, "generation": None, "variant": None, "position": None,
           "kind": brand_kind(brand) if brand else "car", "status": "disputed", "reason": None,
           "suggest": None, "raw": f"{raw_brand or ''}|{raw_model or ''}"}
    if not brand:
        out["reason"] = "нет марки"
        return out

    # 1) модель из разбора, 2) заголовок, 3) первые строки текста
    hit, source = None, None
    for src, text in (("model", model), ("title", title), ("description", head)):
        if (text or "").strip():
            hit = find_model(brand, _strip_brand(brand, text))
            if hit:
                source = src
                break
    # В заголовке может быть точнее: "Malibu" в разборе, "Malibu XL" в заголовке
    if hit and source == "model" and title:
        better = find_model(brand, _strip_brand(brand, title))
        if better and better[0] != hit[0] and better[0].startswith(hit[0]):
            hit = better

    blob = " ".join([model or "", title or "", head])
    for rx, name in VARIANTS:
        if any(re.search(rx, v) for v in _variants(blob)):
            out["variant"] = name if not out["variant"] else f'{out["variant"]}, {name}'
    pos = POSITION.search(_norm(blob))
    if pos:
        out["position"] = int(pos.group(1) or pos.group(2))

    if not hit:
        out["reason"] = "модель не узнана"
        return out

    name, extra = hit
    out["model"] = name
    if extra.get("kind"):
        out["kind"] = extra["kind"]
    out["status"] = "ok" if source in ("model", "title") and not extra.get("guess") else "guess"
    if out["status"] == "guess":
        out["reason"] = "модель по косвенным словам"

    # Поколение: номер в тексте, потом по комплектации, потом по году
    if extra.get("gen") is not None:
        gen = None
        short = " ".join([model or "", title or ""])
        for v in _variants(short):
            m = re.search(extra["gen"], v)
            if m and m.group(1):
                gen = m.group(1)
                break
        if not gen and year and extra.get("by_year"):
            for lo, hi, g in extra["by_year"]:
                if lo <= year <= hi:
                    gen, out["status"], out["reason"] = g, "guess", "поколение по году"
                    break
        if not gen:
            for rx, g in extra.get("gen_words", []):
                if any(re.search(rx, v) for v in _variants(blob)):
                    gen, out["status"], out["reason"] = g, "guess", "поколение по комплектации"
                    break
        out["generation"] = gen
        if not gen:
            out["status"], out["reason"] = "disputed", "нет поколения и года"

    # Разбор спорит с текстом поста: в первых строках другая машина
    model_rx = next((rx for n, rx, _ in _model_re.get(brand, []) if n == name), None)
    other = _other_car_in(brand, model_rx, head)
    if other:
        out["status"], out["reason"] = "disputed", f"в тексте другая машина: {other}"
        sug = find_model(other, _strip_brand(other, head))
        out["suggest"] = f"{other} {sug[0]}" if sug else other
    elif title and _other_car_in(brand, model_rx, title) and not _other_car_in(brand, model_rx, head):
        pass
    if out["status"] != "disputed" and NOT_ONE_CAR.search(_norm(" ".join([title or "", head]))):
        out["status"], out["reason"] = "disputed", "похоже на запчасти или разбор"
    return out


def model_key(n: dict) -> str | None:
    """Ключ для оценки рынка и страниц моделей: 'Chevrolet Malibu 2'."""
    if not (n.get("brand") and n.get("model")):
        return None
    parts = [n["brand"], n["model"]] + ([n["generation"]] if n.get("generation") else [])
    return " ".join(parts)
