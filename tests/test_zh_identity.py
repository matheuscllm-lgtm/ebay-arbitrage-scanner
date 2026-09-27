"""Catálogo de identidade por impressão: chinês simplificado → carta EN (offline).

Fixtures = wikitext real da 52poke wiki (páginas de produto e de carta, 2026-09-27),
recortado. Nenhum preço."""
import json
import os

import pytest

from src import chinese_scan as cs
from src import zh_identity as zi

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _read(name: str) -> str:
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def _resolve(exp_zh: str, en_no: str | None):
    bulba = {"浪湧電光": "Surging Sparks (TCG)", "星晶冠冕": "Stellar Crown (TCG)", "151": "151 (TCG)",
             "帕底亚天机": "Paldean Fates (TCG)", "棱镜进化": "Prismatic Evolutions (TCG)",
             "群雄昇騰": "Ascended Heroes (TCG)", "朱紫 黑色之星": "SVP Black Star Promos (TCG)"}.get(exp_zh)
    return zi.to_watchlist_set(bulba, en_no) if bulba else (exp_zh, False)


JP_TO_EN = {"sv8": {"SV08: Surging Sparks"}, "sv7": {"SV07: Stellar Crown"}, "sv2a": {"SV: Scarlet & Violet 151"},
            "sv4a": {"SV: Paldean Fates"}, "sv8a": {"SV: Prismatic Evolutions"}}


# --- wikitext -------------------------------------------------------------------------
def test_plain_and_template_split():
    assert zi.plain("{{RarityCBB|C}}") == "C"
    assert zi.plain("皮卡丘{{ex|ex-t=1}}") == "皮卡丘ex"
    assert zi.plain("[[全图卡（TCG）|全]] '''x'''") == "全 x"
    assert zi._split_top_level("a|{{b|c}}|[[d|e]]|f") == ["a", "{{b|c}}", "[[d|e]]", "f"]


def test_parse_set_page_entries_numbers_hints_and_rarities():
    sp = zi.parse_set_page("星彩晶璃（TCG）", _read("zh_set_csv9_excerpt.txt"))
    assert sp.alt_code == "CSV9C" and sp.name == "星彩晶璃" and len(sp.entries) == 12
    by_no = {e.cn_no: e for e in sp.entries}
    pika = by_no["245"]
    assert (pika.name, pika.link_kind, pika.jp_hint_set, pika.rarity, pika.cn_total) == ("皮卡丘ex", "C", "SV8", "SAR", "208")
    lisia = by_no["257"]
    assert (lisia.name, lisia.link_kind, lisia.jp_hint_set, lisia.rarity) == ("琉琪亚的展现", "TCG", None, "SAR")
    assert by_no["1"].name == "蛋蛋" and by_no["1"].rarity == "C" and by_no["26"].jp_hint_set == "SV7"
    assert zi.card_page_title(pika) == "皮卡丘ex（SV8）" and zi.card_page_title(lisia) == "琉琪亚的展现（TCG）"


def test_parse_gem_pack_entries_keep_pack_and_number():
    sp = zi.parse_set_page("宝石包 第一弹（TCG）", _read("zh_set_gem1_excerpt.txt"))
    assert sp.alt_code == "CBB1C" and len(sp.entries) == 9
    e = sp.entries[5]
    assert (e.cn_no, e.cn_total, e.rarity, e.jp_hint_set, e.jp_hint_no) == ("01 06", "09", "R", "SV1a", "004")
    assert sp.entries[0].rarity == "C"       # {{RarityCBB|C}} → C


def test_parse_cn_number_forms():
    assert zi.parse_cn_number("245/208") == ("245", "208")
    assert zi.parse_cn_number("001/208") == ("1", "208")
    assert zi.parse_cn_number("07 01/09") == ("07 01", "09")
    assert zi.parse_cn_number("003/SV-P") == ("3", "SV-P")
    assert zi.parse_cn_number("SV-P") == (None, "SV-P")
    assert zi.norm_en_number("238/191") == "238" and zi.norm_en_number("TG23/TG30") == "TG23"
    assert zi.norm_en_number("SVP053") == "SVP053" and zi.norm_en_number("004/102") == "4"


def test_parse_card_page_rows_and_names():
    cp = zi.parse_card_page("皮卡丘ex（SV8）", _read("zh_card_pikachu_ex_sv8.txt"))
    assert (cp.zh_name, cp.ja_name, cp.en_name) == ("皮卡丘ex", "ピカチュウex", "Pikachu ex")
    sc = [r for r in cp.sc_rows if r.get("cnno") == "245/208"][0]
    assert (sc["cnicon"], sc["cnrar"], sc["zhicon"], sc["zhno"], sc["illus"]) == ("CSV9C", "SAR", "SV8F", "132/106", "GIDORA")
    en = [r for r in cp.en_rows if r.get("enno") == "238/191"][0]
    assert (en["enexpansion"], en["enrar"], en["jaicon"], en["jano"]) == ("浪湧電光", "SIR", "SV8", "132/106")
    cap = zi.parse_card_page("船长皮卡丘（CBB1）", _read("zh_card_captain_pikachu_cbb1.txt"))
    assert cap.sc_rows[0]["cnrar"] == "C" and cap.sc_rows[0]["cnno"] == "07 01/09"   # template aninhado limpo


# --- junção ---------------------------------------------------------------------------
def _entry(sp: zi.SetPage, no: str) -> zi.SetEntry:
    return next(e for e in sp.entries if e.cn_no == no)


def test_link_tc_jp_exact_pikachu_sar():
    sp = zi.parse_set_page("星彩晶璃（TCG）", _read("zh_set_csv9_excerpt.txt"))
    cp = zi.parse_card_page("皮卡丘ex（SV8）", _read("zh_card_pikachu_ex_sv8.txt"))
    got = zi.link_entry(_entry(sp, "245"), "CSV9C", cp, _resolve, JP_TO_EN, set_name=sp.name)
    assert (got.en_set, got.en_no, got.en_rar, got.how) == ("SV08: Surging Sparks", "238", "SIR", "tc-jp")
    assert got.tc == "SV8F 132" and got.jp == "sv8 132" and got.illus == "GIDORA" and got.en_name == "Pikachu ex"
    ur = zi.link_entry(_entry(sp, "260"), "CSV9C", cp, _resolve, JP_TO_EN, set_name=sp.name)
    assert (ur.en_no, ur.en_rar, ur.how) == ("247", "HR", "tc-jp")
    j = got.to_json()
    assert j["cn_code"] == "CSV9C" and j["cn_no"] == "245" and "ambiguous" not in j and "en_set_unresolved" not in j


def test_link_turtonator_common_and_ar_by_tc_jp():
    sp = zi.parse_set_page("星彩晶璃（TCG）", _read("zh_set_csv9_excerpt.txt"))
    cp = zi.parse_card_page("爆焰龜獸（SV7）", _read("zh_card_turtonator_sv7.txt"))
    # 026 C: tradicional SV7F 015 = japonesa SV7 015 da linha EN (Stellar Crown 25 C)
    c = zi.link_entry(_entry(sp, "26"), "CSV9C", cp, _resolve, JP_TO_EN, set_name=sp.name)
    assert (c.en_set, c.en_no, c.en_rar, c.how, c.tc) == ("SV07: Stellar Crown", "25", "C", "tc-jp", "SV7F 15")
    # 209 AR: SV7F 105 ↔ SV7 105 → Stellar Crown 146 IR (AR↔IR, Yukihiro Tada)
    ar = zi.link_entry(_entry(sp, "209"), "CSV9C", cp, _resolve, JP_TO_EN, set_name=sp.name)
    assert (ar.en_set, ar.en_no, ar.en_rar, ar.how) == ("SV07: Stellar Crown", "146", "IR", "tc-jp")


def test_link_lisia_sar_has_no_en_pair_and_never_guesses():
    sp = zi.parse_set_page("星彩晶璃（TCG）", _read("zh_set_csv9_excerpt.txt"))
    cp = zi.parse_card_page("琉琪亞的展示（TCG）", _read("zh_card_lisia_appeal.txt"))
    sar = zi.link_entry(_entry(sp, "257"), "CSV9C", cp, _resolve, JP_TO_EN, set_name=sp.name)
    # SAR chinesa (En Morikura, sem tradicional) × SIR inglesa (Nobusawa/Mochipuyo): outro
    # ilustrador → sem par; a UR/SR (En Morikura) tem família diferente → não vira par
    assert sar.en_set is None and sar.how is None and sar.note == "sem-par-en-identificavel" and not sar.ambiguous
    u = zi.link_entry(_entry(sp, "204"), "CSV9C", cp, _resolve, JP_TO_EN, set_name=sp.name)
    assert (u.en_set, u.en_no, u.en_rar, u.how) == ("SV08: Surging Sparks", "179", "U", "tc-jp")


def test_link_mew_ex_151_collect_rows_and_fallback_without_jp_columns():
    import copy
    cp = zi.parse_card_page("梦幻ex（SV2a）", _read("zh_card_mew_ex_sv2a.txt"))
    e = zi.SetEntry("191", "151", "梦幻ex", "C", "SV2a", None, "SAR")
    got = zi.link_entry(e, "151C", cp, _resolve, JP_TO_EN, set_name="收集啦151 惊")
    # SAR 191 vem da tradicional SV4aF 347 = japonesa SV4a 347 → Paldean Fates 232 SIR
    assert (got.en_set, got.en_no, got.en_rar, got.how, got.tc) == ("SV: Paldean Fates", "232", "SIR", "tc-jp", "SV4aF 347")
    # página SEM colunas japonesas nas linhas EN (acontece): set JP→EN + ilustrador + família
    cp2 = copy.deepcopy(cp)
    for r in cp2.en_rows:
        r.pop("jaicon", None)
        r.pop("jano", None)
    got2 = zi.link_entry(e, "151C", cp2, _resolve, JP_TO_EN, set_name="收集啦151 惊")
    assert (got2.en_set, got2.en_no, got2.en_rar, got2.how) == ("SV: Paldean Fates", "232", "SIR", "set+illus+rar")
    rr = zi.link_entry(zi.SetEntry("151", "151", "梦幻ex", "C", "SV2a", None, "RR"), "151C", cp2, _resolve, JP_TO_EN, set_name="收集啦151")
    assert (rr.en_set, rr.en_no, rr.en_rar, rr.how) == ("SV: Scarlet & Violet 151", "151", "DR", "set+illus+rar")
    # sem set JP conhecido no mapa: só ilustrador + família (marcado como mais fraco)
    got3 = zi.link_entry(e, "151C", cp2, _resolve, {}, set_name="收集啦151 惊")
    assert (got3.en_no, got3.how) == ("232", "illus+rar")
    # linha chinesa sem ilustrador na wiki: set JP→EN + família únicos (SAR ↔ SIR 232, não SHUR 216)
    cp3 = copy.deepcopy(cp2)
    for r in cp3.sc_rows:
        r.pop("illus", None)
    got4 = zi.link_entry(e, "151C", cp3, _resolve, JP_TO_EN, set_name="收集啦151 惊")
    assert (got4.en_set, got4.en_no, got4.how) == ("SV: Paldean Fates", "232", "set+rar")
    promo = zi.link_entry(zi.SetEntry("3", "SV-P", "梦幻ex", "C", "SV2a", None, None), "SV-P", cp, _resolve, JP_TO_EN, set_name="SV-P简体中文版特典卡")
    assert promo.how is None and promo.en_set is None   # promo simplificada (satoma): sem par EN


def test_missing_page_and_learned_jp_map():
    e = zi.SetEntry("177", "208", "支援按铃", "TCG", None, None, "U")
    got = zi.link_entry(e, "CSV9C", None, _resolve, JP_TO_EN, set_name="星彩晶璃")
    assert got.how is None and got.note == "pagina-da-carta-nao-encontrada" and got.to_json()["note"]
    cp = zi.parse_card_page("皮卡丘ex（SV8）", _read("zh_card_pikachu_ex_sv8.txt"))
    learned = zi.learn_jp_to_en([cp], _resolve, seed={"sv7": {"SV07: Stellar Crown"}})
    assert learned["sv8"] == {"SV08: Surging Sparks"} and "SV: Prismatic Evolutions" in learned["sv8a"]
    assert learned["sv7"] == {"SV07: Stellar Crown"}


def test_rarity_families_and_watchlist_set_names():
    assert zi.rarity_compatible("SAR", "SIR") is True and zi.rarity_compatible("UR", "HR") is True
    assert zi.rarity_compatible("SR", "UR") is True and zi.rarity_compatible("AR", "IR") is True
    assert zi.rarity_compatible("SSR", "SHUR") is True and zi.rarity_compatible("RR", "DR") is True
    assert zi.rarity_compatible("SAR", "UR") is False and zi.rarity_compatible("XYZ", "C") is None
    # eras SM/SWSH: GX/V holo ↔ RR, RU (full art) ↔ SR, RS (arco-íris) ↔ HR
    assert zi.rarity_compatible("RR", "GX") is True and zi.rarity_compatible("SR", "RU") is True
    assert zi.rarity_compatible("HR", "RS") is True and zi.rarity_compatible("RRR", "VMAX") is True
    # Shiny Vault: o número EN (SV49) decide; qualquer família brilhante japonesa serve
    assert zi.rarity_compatible("SSR", "RU", "SV49") is True and zi.rarity_compatible("S", "SH", "SV3") is True
    assert zi.rarity_compatible("SR", "RU", "SV49") is False and zi.rarity_compatible("SR", "RU", "49") is True
    assert zi.to_watchlist_set("Surging Sparks (TCG)") == ("SV08: Surging Sparks", True)
    assert zi.to_watchlist_set("151 (TCG)") == ("SV: Scarlet & Violet 151", True)
    assert zi.to_watchlist_set("Pokémon GO (TCG)") == ("Pokemon GO", True)
    assert zi.to_watchlist_set("Brilliant Stars (TCG)", "TG23") == ("SWSH09: Brilliant Stars Trainer Gallery", True)
    assert zi.to_watchlist_set("Crown Zenith (TCG)", "GG44") == ("SWSH: Crown Zenith: Galarian Gallery", True)
    assert zi.to_watchlist_set("Hidden Fates (TCG)", "SV49") == ("Hidden Fates: Shiny Vault", True)
    assert zi.to_watchlist_set("Team Up (TCG)") == ("SM - Team Up", True)
    assert zi.to_watchlist_set("SVP Black Star Promos (TCG)") == ("SVP Black Star Promos", False)


# --- chaves do anúncio e veredito -------------------------------------------------------
def test_cn_key_from_pricecharting_url_and_title():
    assert zi.cn_key_from_pc_url("https://www.pricecharting.com/game/pokemon-chinese-csv9c/pikachu-ex-245") == ("csv9c", "245")
    assert zi.cn_key_from_pc_url("https://www.pricecharting.com/game/pokemon-chinese-csv95c/x-12") == ("csv95c", "12")
    assert zi.cn_key_from_pc_url("https://www.pricecharting.com/game/pokemon-chinese-gem-pack-2/eevee-407") == ("cbb2c", "04 07")
    assert zi.cn_key_from_pc_url("https://www.pricecharting.com/game/pokemon-chinese-gem-pack-2/umbreon-1115") == ("cbb2c", "11 15")
    assert zi.cn_key_from_pc_url("https://www.pricecharting.com/game/pokemon-chinese-151-collect/mew-ex-191") == ("151c", "191")
    assert zi.cn_key_from_pc_url("https://www.pricecharting.com/game/pokemon-chinese-promo/mew-ex-3sv-p") == ("sv-p", "3")
    assert zi.cn_key_from_pc_url("https://www.pricecharting.com/game/pokemon-chinese-promo/30th-anniversary-starter") is None
    assert zi.cn_key_from_pc_url("https://www.pricecharting.com/game/pokemon-surging-sparks/pikachu-ex-238") is None
    assert zi.cn_key_from_title("Pokemon S-Chinese CSV9C 245/208 Pikachu ex SAR PSA 10", "245", "208") == ("csv9c", "245")
    assert zi.cn_key_from_title("PSA 10 Pikachu ex Simplified Chinese cs4ac #150", "150") == ("cs4ac", "150")
    assert zi.cn_key_from_title("Mew ex 191/151 Chinese PSA 10", "191", "151") == ("151c", "191")
    assert zi.cn_key_from_title("Eevee Gem Pack Vol.2 4/07 Chinese PSA 10", "4", "07") == ("cbb2c", "04 07")
    assert zi.cn_key_from_title("Eevee Gem Pack 4/07 Chinese PSA 10", "4", "07") is None      # sem volume: não chuta
    assert zi.cn_key_from_title("Pikachu ex Chinese PSA 10", None) is None


def _catalog() -> zi.Catalog:
    rows = [
        {"cn_code": "CSV9C", "cn_no": "245", "cn_rar": "SAR", "en_name": "Pikachu ex", "en_set": "SV08: Surging Sparks", "en_no": "238", "en_rar": "SIR", "how": "tc-jp"},
        {"cn_code": "CSV9C", "cn_no": "257", "cn_rar": "SAR", "en_name": "Lisia's Appeal", "en_set": None, "en_no": None, "how": None},
        {"cn_code": "CSV9C", "cn_no": "153", "cn_rar": "C", "en_name": "Eevee", "en_set": None, "en_no": None, "how": None,
         "ambiguous": ["SV08: Surging Sparks 143", "SV: Prismatic Evolutions 74"]},
        {"cn_code": "151C", "cn_no": "191", "cn_rar": "SAR", "en_name": "Mew ex", "en_set": "SV: Paldean Fates", "en_no": "232", "en_rar": "SIR", "how": "set+illus+rar"},
    ]
    return zi.Catalog(rows, {"generated_on": "2026-09-27"})


def test_identity_for_statuses():
    cat = _catalog()
    same = zi.identity_for("SV08: Surging Sparks", "238", ("csv9c", "245"), cat)
    assert same["status"] == "mesma-carta" and same["en"] == "SV08: Surging Sparks 238" and same["how"] == "tc-jp"
    other = zi.identity_for("SV: Scarlet & Violet 151", "232", ("151c", "191"), cat)
    assert other["status"] == "outra-carta" and other["en"] == "SV: Paldean Fates 232" and other["en_name"] == "Mew ex"
    assert zi.identity_for("SV08: Surging Sparks", "234", ("csv9c", "257"), cat)["status"] == "sem-par-en"
    assert zi.identity_for("SV08: Surging Sparks", "143", ("csv9c", "153"), cat)["status"] == "ambigua"
    assert zi.identity_for("SV08: Surging Sparks", "238", ("csv9c", "999"), cat)["status"] == "nao-catalogada"
    assert zi.identity_for("SV08: Surging Sparks", "238", None, cat) is None
    assert cat.by_en("SV08: Surging Sparks", "238")[0]["cn_no"] == "245" and cat.by_en("X", None) == []


def test_catalog_roundtrip_file(tmp_path):
    p = tmp_path / "zh_identity.json"
    p.write_text(json.dumps({"_meta": {"generated_on": "2026-09-27"}, "rows": _catalog().rows}), encoding="utf-8")
    cat = zi.Catalog.from_file(str(p))
    assert len(cat) == 4 and cat.by_cn("csv9c", "245")[0]["en_no"] == "238" and cat.meta["generated_on"] == "2026-09-27"
    assert zi.load(str(tmp_path / "nao-existe.json")) is None


# --- integração no crivo do modo chinês ----------------------------------------------------
def _row(**kw):
    base = {"exclusive": False, "match": "nome", "rarity_check": True, "language": "ZH-HANS", "ratio": 5.0,
            "card": "Pikachu ex", "set": "SV08: Surging Sparks", "number": "238", "rarity": "Special Illustration Rare",
            "en_ref": {"price": 500.0, "source": "vendas", "n": 4},
            "listing": {"price": 100.0, "title": "Pokemon S-Chinese CSV9C 245/208 Pikachu ex SAR PSA 10"},
            "zh": {"status": "ok", "n_sales_90d": 3, "url": "https://www.pricecharting.com/game/pokemon-chinese-csv9c/pikachu-ex-245"}}
    base.update(kw)
    return base


def test_classify_uses_catalog_identity(monkeypatch):
    monkeypatch.setattr(cs.zh_identity, "load", lambda path=None: _catalog())
    p = cs.DEFAULT_PARAMS
    r = _row()
    r["zh_catalog"] = cs.catalog_identity(r)
    assert r["zh_catalog"]["status"] == "mesma-carta"
    # sem catálogo a linha cairia em "set-zh-sem-correspondencia" (csv9c fora de ZH_SET_TO_EN)
    assert cs.classify({**r, "zh_catalog": None}, p) == ("validar", ["set-zh-sem-correspondencia"])
    assert cs.classify(r, p) == ("candidata", [])
    # a mesma impressão chinesa anunciada contra OUTRA carta EN da watchlist
    o = _row(card="Mew ex", set="SV: Scarlet & Violet 151", number="232",
             listing={"price": 100.0, "title": "Mew ex 191/151 SAR Chinese PSA 10"},
             zh={"status": "ok", "n_sales_90d": 3, "url": "https://www.pricecharting.com/game/pokemon-chinese-151-collect/mew-ex-191"})
    o["zh_catalog"] = cs.catalog_identity(o)
    assert o["zh_catalog"]["status"] == "outra-carta" and cs.classify(o, p) == ("validar", ["catalogo-outra-carta"])
    s = _row(number="234", card="Lisia's Appeal", listing={"price": 100.0, "title": "Lisia's Appeal CSV9C 257/208 SAR S-Chinese PSA 10"},
             zh={"status": "ok", "n_sales_90d": 3, "url": ""})
    s["zh_catalog"] = cs.catalog_identity(s)
    assert s["zh_catalog"]["status"] == "sem-par-en" and cs.classify(s, p) == ("validar", ["catalogo-sem-par-en"])
    # chave só pela página chinesa (título sem código nem fração)
    u = _row(listing={"price": 100.0, "title": "Pikachu ex SAR Simplified Chinese PSA 10"})
    u["zh_catalog"] = cs.catalog_identity(u)
    assert u["zh_catalog"]["status"] == "mesma-carta" and u["zh_catalog"]["cn"] == "CSV9C 245"
    # fora do catálogo: regra antiga segue valendo
    n = _row(listing={"price": 100.0, "title": "Pikachu ex CSV9C 999/208 S-Chinese PSA 10"}, zh={"status": "ok", "n_sales_90d": 3, "url": ""})
    n["zh_catalog"] = cs.catalog_identity(n)
    assert n["zh_catalog"]["status"] == "nao-catalogada" and cs.classify(n, p) == ("validar", ["set-zh-sem-correspondencia"])


def test_rescore_recomputes_catalog_identity(monkeypatch):
    monkeypatch.setattr(cs.zh_identity, "load", lambda path=None: _catalog())
    monkeypatch.setattr(cs, "character_points", lambda name: 25)
    row = {**_row(), "pokemon": "Pikachu", "zh": {"status": "ok", "n_sales_90d": 3, "median_90d": 150.0, "pop_psa10": 30, "pop_total": 40,
                                                   "sales_per_month_observed": 1.0, "url": "https://www.pricecharting.com/game/pokemon-chinese-csv9c/pikachu-ex-245"}}
    out = cs.rescore({"meta": {"params": {}}, "rows": [row]})
    r = out["rows"][0]
    assert r["zh_catalog"]["status"] == "mesma-carta" and r["bucket"] == "candidata" and r["reasons"] == []


def test_funnel_counts_catalog_reasons_first():
    import chinese_thesis as ct
    assert ct.FUNNEL_STEPS[0][1] == ("catalogo-outra-carta", "catalogo-sem-par-en")
    assert "catalogo-ambiguo" in ct.FUNNEL_STEPS[1][1]
