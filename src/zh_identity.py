"""Identidade por IMPRESSÃO entre a carta em chinês SIMPLIFICADO e a carta EN.

Por que existe: o crivo do modo chinês (`src/chinese_scan.py`) só reconhecia par forte
quando o número EN aparecia no título ou quando o set chinês constava na tabela curada
`ZH_SET_TO_EN` (set inteiro → set EN). As compilações simplificadas (CS/CSV/CSM/CBB),
promos e Gem Pack misturam sets japoneses e renumeram tudo, então quase todo anúncio que
passava a razão ≥ 4× caía em "validar" por identidade — não por preço. Este módulo troca a
correspondência por SET pela correspondência por CARTA.

Fonte pública: 52poke wiki (神奇宝贝百科, MediaWiki, CC BY-NC-SA 3.0), lida pela API
`api.php`. Duas páginas por impressão:

* página do PRODUTO simplificado ("星彩晶璃（TCG）"): lista cada carta com
  ``{{卡牌列表/entryjp|245/208|{{C|皮卡丘ex|SV8}}|雷||SAR|全}}`` — número chinês, nome, set
  JAPONÊS de origem (a compilação chinesa reimprime cartas japonesas), raridade;
* página da CARTA ("皮卡丘ex（SV8）"): ``{{ExpansionList/main/zh|…|cnicon=CSV9C|cnno=245/208|
  cnrar=SAR|zhicon=SV8F|zhno=132/106|…|illus=GIDORA}}`` (impressão simplificada + a
  tradicional correspondente, que espelha a japonesa) e ``{{ExpansionList/main|…|
  enexpansion=浪湧電光|enno=238/191|enrar=SIR|jaicon=SV8|jano=132/106|illus=GIDORA}}``
  (impressão EN + a japonesa correspondente).

Junção, da mais forte para a mais fraca (campo ``how`` de cada linha):

1. ``tc-jp`` — a impressão tradicional (set JP sem o sufixo F + número) é a mesma impressão
   japonesa da linha EN. Exata.
2. ``set+illus+rar`` — o set JP de origem corresponde ao set EN da linha (mapa JP→EN obtido do
   próprio corpus, semeado por ``ZH_SET_TO_EN``) **e** mesmo ilustrador **e** família de
   raridade compatível (SAR↔SIR, AR↔IR, SR↔UR, UR↔HR, SSR↔SHUR, RR↔DR…). É o "fingerprint"
   possível sem imagem: quem desenhou + que tipo de impressão + de onde veio.
3. ``illus+rar`` — sem set JP conhecido: ilustrador + família de raridade únicos na página.
   Mais fraco; fica marcado.
4. ``None`` — a impressão chinesa não tem par EN identificável (arte exclusiva, promo, ou
   dado ausente). Nunca chuta: com mais de um candidato a linha sai ``ambiguous``.

Texto (nome/ilustrador) e conferência por IMAGEM são fatores separados; a imagem fica
para uma etapa seguinte, com os casos ``ambiguous``/``None`` como alvo definido.

Nada aqui recomenda compra. O catálogo é metadado público de impressão; não carrega preço.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from functools import lru_cache

WIKI_API = "https://wiki.52poke.com/api.php"
WIKI_LICENSE = "CC BY-NC-SA 3.0 (神奇宝贝百科 / 52poke wiki)"
# Navegação dos produtos simplificados por era (Template:PTCG版本导航/<nome>).
NAV_TEMPLATES = ("太阳&月亮系列简中", "剑&盾系列简中", "朱&紫系列简中", "超级进化系列简中")
CATALOG_PATH = os.path.join(os.path.dirname(__file__), "catalog", "zh_identity.json")
SET_CATALOG_PATH = os.path.join(os.path.dirname(__file__), "catalog", "set_catalog.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ebay-arbitrage-scanner zh_identity; +offline tests)"}


# --- wikitext: templates ------------------------------------------------------------
def _split_top_level(body: str, sep: str = "|") -> list[str]:
    """Divide em `sep` só no nível 0 de `{{ }}` e `[[ ]]`."""
    parts, depth, cur, i = [], 0, [], 0
    while i < len(body):
        two = body[i:i + 2]
        if two in ("{{", "[["):
            depth += 1
            cur.append(two)
            i += 2
            continue
        if two in ("}}", "]]"):
            depth = max(0, depth - 1)
            cur.append(two)
            i += 2
            continue
        ch = body[i]
        if ch == sep and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    parts.append("".join(cur))
    return parts


def iter_templates(wikitext: str, name_prefix: str = "") -> list[tuple[str, list[str], dict[str, str]]]:
    """Templates de NÍVEL 0 do texto: (nome, posicionais, nomeados). Aninhados ficam
    dentro dos valores (ex.: `{{RarityCBB|C}}` no campo cnrar)."""
    out = []
    i, n = 0, len(wikitext)
    while i < n:
        start = wikitext.find("{{", i)
        if start < 0:
            break
        depth, j = 0, start
        while j < n:
            two = wikitext[j:j + 2]
            if two == "{{":
                depth += 1
                j += 2
            elif two == "}}":
                depth -= 1
                j += 2
                if depth == 0:
                    break
            else:
                j += 1
        body = wikitext[start + 2:j - 2]
        i = j
        args = _split_top_level(body)
        name = args[0].strip()
        if name_prefix and not name.startswith(name_prefix):
            continue
        positional, named = [], {}
        for a in args[1:]:
            k, eq, v = a.partition("=")
            if eq and re.fullmatch(r"\s*[A-Za-z0-9_\-]+\s*", k):
                named[k.strip()] = v.strip()
            else:
                positional.append(a.strip())
        out.append((name, positional, named))
    return out


_INNER_TEMPLATE_RE = re.compile(r"\{\{([^{}|]*)(?:\|([^{}]*))?\}\}")


def _inner_template_text(m: re.Match) -> str:
    """`{{RarityCBB|C}}` → `C` (último posicional); `{{ex|ex-t=1}}` → `ex` (só nomeados →
    fica o nome do template, que é o sufixo escrito na carta)."""
    name = (m.group(1) or "").strip()
    positional = [a for a in (m.group(2) or "").split("|") if a and "=" not in a]
    return positional[-1].strip() if positional else name


def plain(value: str | None) -> str:
    """Valor "limpo": `{{RarityCBB|C}}` → `C`, `{{ex}}` → `ex`, `[[a|b]]` → `b`, `'''x'''` → `x`."""
    v = value or ""
    for _ in range(3):
        v2 = _INNER_TEMPLATE_RE.sub(_inner_template_text, v)
        if v2 == v:
            break
        v = v2
    v = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", v)
    v = re.sub(r"'{2,}", "", v)
    v = re.sub(r"<[^>]+>", "", v)
    return v.strip()


# --- números --------------------------------------------------------------------------
def parse_cn_number(text: str | None) -> tuple[str | None, str | None]:
    """Número chinês como impresso → (número, total). "245/208" → ("245", "208");
    Gem Pack "07 01/09" → ("07 01", "09"); promo "003/SV-P" → ("3", "SV-P"); só "SV-P" →
    (None, "SV-P"). Numerador puro perde zeros à esquerda; o de Gem Pack fica "PP NN"."""
    t = plain(text)
    m = re.fullmatch(r"(\d{1,2})\s+(\d{1,3})\s*/\s*(\d{1,3})", t)
    if m:
        return f"{int(m.group(1)):02d} {int(m.group(2)):02d}", m.group(3)
    m = re.fullmatch(r"(\d{1,4})\s*/\s*([A-Za-z0-9.\-]+)", t)
    if m:
        return str(int(m.group(1))), m.group(2)
    m = re.fullmatch(r"([A-Za-z0-9.\-]+)", t)
    if m and not t.isdigit():
        return None, t
    return (str(int(t)), None) if t.isdigit() else (None, None)


def norm_en_number(text: str | None) -> str | None:
    """"238/191" → "238"; "TG23/TG30" → "TG23"; "SV49/SV94" → "SV49"; "SVP053" → "SVP053";
    "004/102" → "4"."""
    t = plain(text)
    if not t:
        return None
    num = t.split("/")[0].strip()
    if num.isdigit():
        return str(int(num))
    return num or None


def norm_code(code: str | None) -> str:
    """Código de set comparável: "CSV9.5C" ≡ "csv95c" (PriceCharting tira o ponto)."""
    return re.sub(r"[^a-z0-9\-]", "", (code or "").lower())


def jp_code_from_tc(tc_icon: str | None) -> str | None:
    """Tradicional espelha o japonês com sufixo F: "SV8F" → "sv8"; "SV4aF" → "sv4a"."""
    c = plain(tc_icon)
    if not c:
        return None
    if len(c) > 1 and c.endswith(("F", "f")):
        c = c[:-1]
    return norm_code(c)


# --- raridades (famílias comparáveis entre JP/simplificado e EN) --------------------------
# Lado japonês/chinês (a impressão chinesa herda a raridade japonesa).
JP_RARITY_FAMILY = {
    "C": "c", "U": "u", "R": "r", "RR": "rr", "RRR": "rrr", "TR": "tr", "AR": "ar", "CHR": "chr",
    "SR": "sr", "SSR": "ssr", "SAR": "sar", "UR": "ur", "HR": "hr", "CSR": "csr", "K": "k",
    "ACE": "ace", "PR": "pr", "S": "s", "A": "a", "MA": "ma",
}
# Lado EN (códigos como a 52poke escreve nas linhas EN).
EN_RARITY_FAMILY = {
    "C": "c", "U": "u", "R": "r", "RH": "r", "H": "r", "DR": "rr", "TR": "rrr", "IR": "ar",
    "CHR": "chr", "UR": "sr", "SIR": "sar", "HR": "ur", "RR": "hr", "SHR": "s", "SHUR": "ssr",
    "CSR": "csr", "K": "k", "ACE": "ace", "PR": "pr", "A": "a", "MA": "ma", "SR": "sr",
}


def rarity_family(code: str | None, side: str) -> str | None:
    c = plain(code).replace("—", "").strip()
    if not c:
        return None
    table = JP_RARITY_FAMILY if side == "jp" else EN_RARITY_FAMILY
    return table.get(c.upper(), None)


def rarity_compatible(cn_rar: str | None, en_rar: str | None) -> bool | None:
    """True/False quando as duas famílias são conhecidas; None quando alguma é desconhecida
    (não bloqueia, fica registrado)."""
    a, b = rarity_family(cn_rar, "jp"), rarity_family(en_rar, "en")
    if a is None or b is None:
        return None
    return a == b


def norm_illus(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", plain(text).lower())


# --- página do produto simplificado ---------------------------------------------------
@dataclass
class SetEntry:
    cn_no: str | None          # "245" · "07 01" (Gem Pack) · None (sem número)
    cn_total: str | None       # "208" · "09" · "SV-P"
    name: str                  # nome chinês como escrito na lista
    link_kind: str             # "C" (Pokémon, com set JP) · "TCG" (treinador/energia) · ""
    jp_hint_set: str | None    # "SV8" · "SV1a" · "30th" (set JP de origem, da lista)
    jp_hint_no: str | None     # "004" quando a lista já dá o número JP
    rarity: str | None         # "SAR" · "C" · None
    raw: str = ""


@dataclass
class SetPage:
    title: str
    alt_code: str | None
    entries: list[SetEntry] = field(default_factory=list)

    @property
    def name(self) -> str:
        return re.sub(r"（TCG）$", "", self.title)


_ALT_RE = re.compile(r"\|\s*alt\s*=\s*([^\n|]+)")


def parse_set_page(title: str, wikitext: str) -> SetPage:
    alt = _ALT_RE.search(wikitext or "")
    page = SetPage(title=title, alt_code=alt.group(1).strip() if alt else None)
    for name, pos, _named in iter_templates(wikitext or "", "卡牌列表/entry"):
        if len(pos) < 2:
            continue
        cn_no, cn_total = parse_cn_number(pos[0])
        link = pos[1]
        kind, cname, hint_set, hint_no = "", plain(link), None, None
        inner = iter_templates(link)
        if inner:
            tname, targs, _ = inner[0]
            if tname.strip() == "C" and targs:
                kind, cname = "C", plain(targs[0])
                if len(targs) > 1 and targs[1].strip():
                    toks = targs[1].split()
                    hint_set = toks[0]
                    if len(toks) > 1 and re.fullmatch(r"[A-Za-z]*\d+[A-Za-z]*", toks[1]):
                        hint_no = toks[1]
            elif tname.strip() == "TCG" and targs:
                kind, cname = "TCG", plain(targs[0])
        rarity = plain(pos[4]) if len(pos) > 4 else None
        page.entries.append(SetEntry(cn_no, cn_total, cname, kind, hint_set, hint_no, rarity or None, raw=pos[0]))
    return page


def card_page_title(entry: SetEntry) -> str | None:
    """Título provável da página da carta: Pokémon → "皮卡丘ex（SV8）"; treinador/energia →
    "琉琪亚的展现（TCG）". A API resolve redirecionamento e variante de escrita."""
    if not entry.name:
        return None
    if entry.link_kind == "C" and entry.jp_hint_set:
        return f"{entry.name}（{entry.jp_hint_set}）"
    return f"{entry.name}（TCG）"


# --- página da carta ------------------------------------------------------------------
@dataclass
class CardPage:
    title: str
    zh_name: str = ""
    ja_name: str = ""
    en_name: str = ""
    sc_rows: list[dict] = field(default_factory=list)   # ExpansionList/main/zh
    en_rows: list[dict] = field(default_factory=list)   # ExpansionList/main


def parse_card_page(title: str, wikitext: str) -> CardPage:
    page = CardPage(title=title)
    for name, pos, named in iter_templates(wikitext or ""):
        n = name.strip()
        if n == "N" and not page.zh_name:
            page.zh_name = plain(pos[0]) if pos else ""
            page.ja_name = plain(pos[2]) if len(pos) > 2 else ""
            page.en_name = plain(pos[3]) if len(pos) > 3 else ""
        elif n == "ExpansionList/main/zh":
            row = {k: plain(v) for k, v in named.items()}
            if row.get("cnicon") or row.get("cnno") or row.get("zhicon"):
                page.sc_rows.append(row)
        elif n == "ExpansionList/main":
            row = {k: plain(v) for k, v in named.items()}
            if row.get("enexpansion") or row.get("enno"):
                page.en_rows.append(row)
    return page


def _row_illus(row: dict) -> set[str]:
    return {norm_illus(row.get(k)) for k in ("illus", "illus2", "illustrator") if norm_illus(row.get(k))}


def _cn_no_key(text: str | None) -> str | None:
    return parse_cn_number(text)[0]


# --- set EN: nome da Bulbapedia → nome da watchlist -----------------------------------------
_PREFIX_RE = re.compile(r"^(?:SV\d*|SWSH\d*|SM|XY|EX|HS|DP|BW|PL)\s*(?::|-)\s*", re.I)
EN_SET_ALIASES = {
    "151": "SV: Scarlet & Violet 151",
    "pokemongo": "Pokemon GO",
    "swordandshield": "SWSH01: Sword & Shield Base Set",
    "sunandmoon": "SM Base Set",
    "xy": "XY Base Set",
    "scarletandviolet": "SV01: Scarlet & Violet Base Set",
    "heartgoldandsoulsilver": "HeartGold SoulSilver",
    "diamondandpearl": "Diamond and Pearl",
    "blackandwhite": "Black and White",
}


def _norm_set(text: str) -> str:
    t = text.replace("é", "e").replace("&", " and ")
    t = re.sub(r"\((?:TCG|ATCG)\)", "", t)
    return re.sub(r"[^a-z0-9]", "", t.lower())


@lru_cache(maxsize=1)
def _watchlist_set_index() -> dict[str, str]:
    idx: dict[str, str] = {}
    try:
        with open(SET_CATALOG_PATH, encoding="utf-8") as fh:
            names = [k for k in json.load(fh) if k != "_meta"]
    except OSError:
        names = []
    for name in names:
        idx.setdefault(_norm_set(name), name)
        stripped = _PREFIX_RE.sub("", name)
        idx.setdefault(_norm_set(stripped), name)
    return idx


def to_watchlist_set(bulbapedia_name: str | None, en_no: str | None = None) -> tuple[str | None, bool]:
    """("SV08: Surging Sparks", True) para "Surging Sparks (TCG)"; subconjuntos pelo número
    ("TG23" → Trainer Gallery, "GG44" → Galarian Gallery, "SV49" → Shiny Vault). Sem
    correspondência na watchlist devolve (nome Bulbapedia limpo, False) — nunca inventa."""
    if not bulbapedia_name:
        return None, False
    base = re.sub(r"\s*\((?:TCG|ATCG)\)\s*$", "", bulbapedia_name).strip()
    key = _norm_set(base)
    idx = _watchlist_set_index()
    name = EN_SET_ALIASES.get(key) or idx.get(key)
    no = (en_no or "").upper()
    if name:
        if no.startswith("TG") and (name + " Trainer Gallery") in idx.values():
            name = name + " Trainer Gallery"
        elif no.startswith("GG") and "Crown Zenith" in name:
            name = "SWSH: Crown Zenith: Galarian Gallery"
        elif re.fullmatch(r"SV\d+", no) and (name + ": Shiny Vault") in idx.values():
            name = name + ": Shiny Vault"
        return name, True
    return base, False


# --- junção -----------------------------------------------------------------------------
@dataclass
class Linked:
    """Uma impressão simplificada e (quando identificável) a impressão EN correspondente."""
    cn_code: str
    cn_no: str | None
    cn_total: str | None
    cn_rar: str | None
    zh_name: str
    en_name: str
    illus: str
    tc: str | None            # "SV8F 132"
    jp: str | None            # "sv8 132" (código normalizado + número)
    en_set: str | None        # nome da watchlist quando resolvido; senão nome Bulbapedia
    en_set_resolved: bool
    en_no: str | None
    en_rar: str | None
    how: str | None           # tc-jp · set+illus+rar · illus+rar · None
    page: str
    ambiguous: list[str] = field(default_factory=list)
    note: str = ""

    def to_json(self) -> dict:
        d = {
            "cn_code": self.cn_code, "cn_no": self.cn_no, "cn_total": self.cn_total, "cn_rar": self.cn_rar,
            "zh_name": self.zh_name, "en_name": self.en_name, "illus": self.illus, "tc": self.tc, "jp": self.jp,
            "en_set": self.en_set, "en_no": self.en_no, "en_rar": self.en_rar, "how": self.how, "page": self.page,
        }
        if not self.en_set_resolved and self.en_set:
            d["en_set_unresolved"] = True
        if self.ambiguous:
            d["ambiguous"] = self.ambiguous
        if self.note:
            d["note"] = self.note
        return d


def _en_candidates(en_rows: list[dict], resolve) -> list[dict]:
    out = []
    for r in en_rows:
        exp = r.get("enexpansion") or ""
        if not exp:
            continue
        no = norm_en_number(r.get("enno"))
        name, ok = resolve(exp, no)
        out.append({**r, "_en_set": name, "_en_ok": ok, "_en_no": no, "_illus": _row_illus(r),
                    "_ja": (norm_code(r.get("jaicon")), _cn_no_key(r.get("jano")))})
    return out


def link_entry(entry: SetEntry, cn_code: str, page: CardPage | None, resolve, jp_to_en: dict[str, set[str]],
               set_name: str = "") -> Linked:
    """Liga UMA entrada da lista do produto à impressão EN, pelas regras do módulo."""
    zh_name = page.zh_name if page and page.zh_name else entry.name
    en_name = page.en_name if page else ""
    title = page.title if page else ""
    base = dict(cn_code=cn_code, cn_no=entry.cn_no, cn_total=entry.cn_total, cn_rar=entry.rarity, zh_name=zh_name,
                en_name=en_name, illus="", tc=None, jp=None, en_set=None, en_set_resolved=False, en_no=None,
                en_rar=None, how=None, page=title)
    if page is None:
        return Linked(**base, note="pagina-da-carta-nao-encontrada")

    # linha simplificada desta impressão na página da carta
    sc = None
    for r in page.sc_rows:
        if _cn_no_key(r.get("cnno")) != entry.cn_no or not entry.cn_no:
            continue
        same_code = norm_code(r.get("cnicon")) == norm_code(cn_code)
        same_name = set_name and (r.get("cnexpansion") or "").startswith(set_name.split(" ")[0])
        if same_code or same_name:
            sc = r
            if same_code:
                break
    illus: set[str] = _row_illus(sc) if sc else set()
    cn_rar = entry.rarity or (sc.get("cnrar") if sc else None)
    base["cn_rar"] = cn_rar
    base["illus"] = (sc.get("illus") or "") if sc else ""
    tc_code = jp_code_from_tc(sc.get("zhicon")) if sc else None
    tc_no = _cn_no_key(sc.get("zhno")) if sc else None
    if sc and sc.get("zhicon"):
        base["tc"] = f"{sc.get('zhicon')} {tc_no or ''}".strip()
    jp_code = tc_code or (norm_code(entry.jp_hint_set) if entry.jp_hint_set else None)
    jp_no = tc_no or (str(int(entry.jp_hint_no)) if entry.jp_hint_no and entry.jp_hint_no.isdigit() else None)
    if jp_code:
        base["jp"] = f"{jp_code} {jp_no or ''}".strip()
    cands = _en_candidates(page.en_rows, resolve)
    if not cands:
        return Linked(**base, note="sem-impressao-en-na-pagina" if not sc else "")

    def _pick(rows: list[dict], how: str) -> Linked | None:
        distinct = {(r["_en_set"], r["_en_no"]) for r in rows}
        if len(distinct) == 1:
            r = rows[0]
            return Linked(**{**base, "en_set": r["_en_set"], "en_set_resolved": r["_en_ok"], "en_no": r["_en_no"],
                             "en_rar": r.get("enrar") or None, "how": how})
        return None

    # 1) mesma impressão japonesa (tradicional espelha o JP; linha EN traz jaicon/jano)
    if jp_code and jp_no:
        exact = [r for r in cands if r["_ja"] == (jp_code, jp_no)]
        if exact:
            got = _pick(exact, "tc-jp")
            if got:
                return got
            return Linked(**base, ambiguous=sorted({f"{r['_en_set']} {r['_en_no']}" for r in exact}), note="varias-en-para-a-mesma-jp")
    # 2) set JP → set(s) EN + ilustrador + família de raridade
    if jp_code and illus:
        en_sets = jp_to_en.get(jp_code) or set()
        pool = [r for r in cands if r["_en_set"] in en_sets and (r["_illus"] & illus)]
        rar_ok = [r for r in pool if rarity_compatible(cn_rar, r.get("enrar")) is not False]
        if rar_ok:
            got = _pick(rar_ok, "set+illus+rar")
            if got:
                return got
            return Linked(**base, ambiguous=sorted({f"{r['_en_set']} {r['_en_no']}" for r in rar_ok}), note="varias-en-no-mesmo-set")
    # 3) ilustrador + família de raridade únicos na página
    if illus:
        pool = [r for r in cands if (r["_illus"] & illus) and rarity_compatible(cn_rar, r.get("enrar")) is True]
        if pool:
            got = _pick(pool, "illus+rar")
            if got:
                return got
            return Linked(**base, ambiguous=sorted({f"{r['_en_set']} {r['_en_no']}" for r in pool}), note="varias-en-por-ilustrador")
    return Linked(**base, note="sem-par-en-identificavel")


def learn_jp_to_en(pages: list[CardPage], resolve, seed: dict[str, set[str]] | None = None) -> dict[str, set[str]]:
    """Mapa JP→EN aprendido do corpus: toda linha EN que traz `jaicon` diz a que set EN
    aquele set japonês foi. Semente: `ZH_SET_TO_EN` do scan (chaves já normalizadas)."""
    out: dict[str, set[str]] = {k: set(v) for k, v in (seed or {}).items()}
    for p in pages:
        for r in p.en_rows:
            ja = norm_code(r.get("jaicon"))
            exp = r.get("enexpansion") or ""
            if not ja or not exp:
                continue
            name, ok = resolve(exp, norm_en_number(r.get("enno")))
            if name:
                out.setdefault(ja, set()).add(name)
    return out


# --- cliente MediaWiki (injetável) ------------------------------------------------------
class WikiClient:
    """Lotes de até 50 títulos por chamada, redirecionamento e conversão de variante
    (简/繁) resolvidos pela API, 1 requisição/s, cache opcional em disco (JSON bruto)."""

    def __init__(self, fetch=None, sleep_s: float = 1.0, cache_dir: str | None = None, log=print, batch: int = 25):
        self._fetch = fetch or self._urlopen
        self.sleep_s = sleep_s
        self.cache_dir = cache_dir
        self.log = log
        self.batch = max(1, min(50, batch))   # a API aceita 50 títulos; lotes menores evitam 502 do backend
        self.calls = 0
        self._last = 0.0

    @staticmethod
    def _urlopen(url: str) -> str:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8", errors="replace")

    def _get(self, params: dict) -> dict:
        url = WIKI_API + "?" + urllib.parse.urlencode({**params, "format": "json"})
        path = None
        if self.cache_dir:
            os.makedirs(self.cache_dir, exist_ok=True)
            path = os.path.join(self.cache_dir, re.sub(r"[^a-z0-9]+", "_", url.lower())[-150:] + ".json")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as fh:
                    return json.load(fh)
        last_err: Exception | None = None
        for attempt in range(6):
            wait = self.sleep_s - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            if attempt:
                time.sleep(5.0 * attempt)   # 5xx/timeout transitório: espera 5, 10, 15, 20, 25 s
            try:
                body = self._fetch(url)
                self._last = time.time()
                self.calls += 1
                data = json.loads(body)
                break
            except (OSError, ValueError) as exc:   # HTTPError 5xx, URLError, timeout, JSON truncado
                self._last = time.time()
                last_err = exc
                status = getattr(exc, "code", None)
                if status and status < 500 and status != 429:
                    raise
        else:
            raise RuntimeError(f"52poke indisponível após 6 tentativas ({last_err})") from last_err
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(body)
        return data

    def template_wikitext(self, name: str) -> str:
        d = self._get({"action": "parse", "page": f"Template:{name}", "prop": "wikitext"})
        return ((d.get("parse") or {}).get("wikitext") or {}).get("*", "")

    def pages(self, titles: list[str], langlinks: bool = False) -> dict[str, dict]:
        """{título pedido: {"title": título real, "revid", "wikitext", "missing", "en": langlink}}."""
        out: dict[str, dict] = {}
        titles = [t for t in dict.fromkeys(titles) if t]
        for i in range(0, len(titles), self.batch):
            chunk = titles[i:i + self.batch]
            params = {"action": "query", "redirects": 1, "converttitles": 1, "prop": "revisions" + ("|langlinks" if langlinks else ""),
                      "rvprop": "content|ids", "rvslots": "main", "titles": "|".join(chunk)}
            if langlinks:
                params["lllang"] = "en"
            d = self._get(params)
            q = d.get("query") or {}
            alias: dict[str, str] = {}
            for kind in ("normalized", "converted", "redirects"):
                for m in q.get(kind) or []:
                    alias[m["from"]] = m["to"]

            def _final(t: str) -> str:
                seen = set()
                while t in alias and t not in seen:
                    seen.add(t)
                    t = alias[t]
                return t

            by_title = {p.get("title"): p for p in (q.get("pages") or {}).values()}
            for t in chunk:
                p = by_title.get(_final(t))
                if not p or "missing" in p:
                    out[t] = {"title": _final(t), "missing": True, "wikitext": "", "revid": None, "en": None}
                    continue
                rev = (p.get("revisions") or [{}])[0]
                en = next((x.get("*") for x in p.get("langlinks") or [] if x.get("lang") == "en"), None)
                out[t] = {"title": p.get("title"), "missing": False, "revid": rev.get("revid"),
                          "wikitext": ((rev.get("slots") or {}).get("main") or {}).get("*", ""), "en": en}
        return out


def nav_product_names(nav_wikitext: str) -> list[str]:
    """Nomes dos produtos simplificados listados numa navegação (`{{TCG|nome}}`), sem a
    linha da série."""
    names = []
    for m in re.finditer(r"\{\{TCG\|([^|}]+)", nav_wikitext or ""):
        n = m.group(1).strip()
        if n.endswith("系列") or n in names:
            continue
        names.append(n)
    return names


# --- catálogo em disco e consulta -------------------------------------------------------
class Catalog:
    def __init__(self, rows: list[dict], meta: dict | None = None):
        self.rows = rows
        self.meta = meta or {}
        self._by_cn: dict[tuple[str, str], list[dict]] = {}
        self._by_en: dict[tuple[str, str], list[dict]] = {}
        for r in rows:
            if r.get("cn_no"):
                self._by_cn.setdefault((norm_code(r.get("cn_code")), r["cn_no"]), []).append(r)
            if r.get("en_set") and r.get("en_no") and not r.get("en_set_unresolved"):
                self._by_en.setdefault((r["en_set"], str(r["en_no"])), []).append(r)

    @classmethod
    def from_file(cls, path: str = CATALOG_PATH) -> "Catalog":
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return cls(d.get("rows") or [], d.get("_meta") or {})

    def by_cn(self, code: str | None, no: str | None) -> list[dict]:
        if not code or not no:
            return []
        return list(self._by_cn.get((norm_code(code), no), []))

    def by_en(self, set_name: str | None, number: str | None) -> list[dict]:
        if not set_name or not number:
            return []
        n = str(int(number)) if str(number).isdigit() else str(number)
        return list(self._by_en.get((set_name, n), []))

    def __len__(self) -> int:
        return len(self.rows)


_LOADED: dict[str, Catalog | None] = {}


def load(path: str = CATALOG_PATH) -> Catalog | None:
    """Catálogo versionado, ou None quando o arquivo não existe (o scan segue só com a
    regra por set)."""
    if path not in _LOADED:
        try:
            _LOADED[path] = Catalog.from_file(path)
        except (OSError, ValueError):
            _LOADED[path] = None
    return _LOADED[path]


# PriceCharting → código 52poke. Consoles: pokemon-chinese-csv9c, -gem-pack-2, -promo,
# -151-collect, -30th-celebration.
_PC_CONSOLE_RE = re.compile(r"/game/pokemon-chinese-([a-z0-9.\-]+)/([a-z0-9.%\-']+)", re.I)


def cn_key_from_pc_url(url: str | None) -> tuple[str, str] | None:
    """(código, número) da página chinesa do PriceCharting; None quando não dá para saber
    sem chutar (promo sem código no slug, 30th, número ausente)."""
    m = _PC_CONSOLE_RE.search(url or "")
    if not m:
        return None
    console, slug = m.group(1).lower(), urllib.parse.unquote(m.group(2)).lower()
    tail = slug.rsplit("-", 1)[-1]
    if console.startswith("gem-pack"):
        vol = console.rsplit("-", 1)[-1]
        vol = vol if vol.isdigit() else "1"
        if not tail.isdigit() or len(tail) < 3:
            return None
        # "eevee-407" = 4/07 · "umbreon-1115" = 11/15 (numerador colado ao denominador)
        pack, no = (tail[:-2], tail[-2:]) if len(tail) <= 4 else (tail[:2], tail[2:])
        return f"cbb{vol}c", f"{int(pack):02d} {int(no):02d}"
    if console == "151-collect":
        return ("151c", str(int(tail))) if tail.isdigit() else None
    if console == "promo":
        # "mew-ex-3sv-p" = 003/SV-P · "pikachu-153sv-p" · "squirtle-330th-p" = 003/30th-P
        mm = re.search(r"-(\d{1,4})(sv|sm|s|m|30th)-p$", slug)
        return (f"{mm.group(2)}-p", str(int(mm.group(1)))) if mm else None
    if console == "30th-celebration":
        return ("30thc", str(int(tail))) if tail.isdigit() else None
    if not tail.isdigit():
        return None
    return norm_code(console), str(int(tail))


_TITLE_CODE_RE = re.compile(r"\b((?:csvl|csv|csm|cbb|cs)\d{1,2}(?:\.\d)?[a-z]{0,2})\b", re.I)
_TITLE_VOL_RE = re.compile(r"gem\s*pack\s*vol(?:ume)?\.?\s*(\d)", re.I)   # "Gem Pack 4/07" NÃO é volume 4


def _title_code(token: str) -> str:
    """"CSV9C"/"csv9" → "csv9c"; "CS4aC"/"cs4a" → "cs4ac"; "CSM1cC" → "csm1cc". Um "c"
    final sozinho é lido como o sufixo de simplificado (é o uso corrente nos títulos)."""
    c = norm_code(token)
    return c if c.endswith("c") else c + "c"


def cn_key_from_title(title: str | None, number: str | None, denominator: str | None = None) -> tuple[str, str] | None:
    """(código, número) a partir do título do anúncio: código de set simplificado
    ("CSV9C 245/208", "cs4ac #150") ou "151C"/"…/151"; Gem Pack só com volume dito."""
    t = title or ""
    if not number:
        return None
    m = _TITLE_VOL_RE.search(t)
    if m and denominator and denominator.isdigit():
        return f"cbb{m.group(1)}c", f"{int(number):02d} {int(denominator):02d}"
    m = _TITLE_CODE_RE.search(t)
    if m:
        return _title_code(m.group(1)), str(int(number))
    if re.search(r"\b151c\b", t, re.I) or (denominator == "151"):
        return "151c", str(int(number))
    return None


def identity_for(card_set: str | None, card_number: str | None, key: tuple[str, str] | None,
                 catalog: Catalog | None = None) -> dict | None:
    """Veredito do catálogo para um anúncio: {"status", "cn", "en", "how", "en_name"}.

    status: "mesma-carta" (a impressão chinesa é a carta EN da watchlist) ·
    "outra-carta" (catalogada, mas é OUTRA carta EN) · "sem-par-en" (catalogada, sem par EN
    identificável) · "ambigua" · "nao-catalogada" (chave fora do catálogo) · None (sem
    chave ou sem catálogo)."""
    if not key:
        return None
    cat = catalog or load()
    if cat is None:
        return None
    code, no = key
    rows = cat.by_cn(code, no)
    cn = f"{code.upper()} {no}"
    if not rows:
        return {"status": "nao-catalogada", "cn": cn, "en": None, "how": None, "en_name": None}
    want_no = str(int(card_number)) if card_number and str(card_number).isdigit() else (card_number or "")
    ens = {(r.get("en_set"), r.get("en_no")) for r in rows if r.get("en_set") and r.get("en_no")}
    if any(s == card_set and n == want_no for s, n in ens):
        r = next(r for r in rows if r.get("en_set") == card_set and r.get("en_no") == want_no)
        return {"status": "mesma-carta", "cn": cn, "en": f"{card_set} {want_no}", "how": r.get("how"), "en_name": r.get("en_name")}
    if any(r.get("ambiguous") for r in rows):
        return {"status": "ambigua", "cn": cn, "en": " | ".join(sorted({a for r in rows for a in r.get("ambiguous") or []})),
                "how": None, "en_name": rows[0].get("en_name")}
    if ens:
        s, n = sorted(ens)[0]
        return {"status": "outra-carta", "cn": cn, "en": f"{s} {n}", "how": rows[0].get("how"), "en_name": rows[0].get("en_name")}
    return {"status": "sem-par-en", "cn": cn, "en": None, "how": None, "en_name": rows[0].get("en_name")}
