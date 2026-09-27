# Identidade por impressão — chinês simplificado ↔ carta EN

Complemento do [modo chinês](CHINESE_PSA10.md). Data: 2026-09-27. Status: **implementado e
testado offline; catálogo gerado com dados reais da fonte; ainda não validado em scan ao
vivo** (o scan seguinte é a validação).

## Problema

O crivo do modo chinês só reconhecia "par forte" (mesma carta EN) quando o número EN
aparecia no título do anúncio ou quando o set chinês estava em `ZH_SET_TO_EN`, uma tabela
curada que mapeia um **set chinês inteiro** para o set EN que reimprime a mesma lista de
cartas (ex.: `sv4aF` ↔ Paldean Fates). Isso funciona para o tradicional (que espelha o
japonês set a set) e falha para o simplificado: as compilações CS/CSV/CSM/CBB, os Gem Pack,
as promos e as caixas 151 **misturam cartas de vários sets japoneses e renumeram tudo**.
Resultado no scan de 2026-09-26: de todo anúncio simplificado que passava a razão EN÷ZH ≥ 4×,
a maior parte caía em `validar` por `set-zh-sem-correspondencia` — identidade, não preço.
O funil do `chinese_thesis.py` mede exatamente isso.

Bases prontas não resolvem: TCGdex devolve para `zh-cn` o mesmo registro de `zh-tw` (e não tem
cartas nos sets `…C`); o `PTCG-database` herda isso (o próprio README avisa que `data_sc/` é
texto de Taiwan sob códigos japoneses). Ficou a ideia de **fingerprint** (ligar impressões
por atributos que a tradução não muda), aplicada a uma fonte que tem o simplificado de fato.

## Fonte

**52poke wiki** (神奇宝贝百科, `wiki.52poke.com`, MediaWiki, conteúdo CC BY-NC-SA 3.0),
lida pela API `api.php` (lotes de até 50 títulos; a API resolve redirecionamento e variante
简/繁 — o título da página pode estar em tradicional). Duas páginas por impressão:

1. **Página do produto simplificado** (`星彩晶璃（TCG）`, `宝石包 第一弹（TCG）`,
   `SV-P简体中文版特典卡（TCG）`…), listada nas navegações por era
   `Template:PTCG版本导航/{太阳&月亮,剑&盾,朱&紫,超级进化}系列简中`. Cada carta é uma linha
   `{{卡牌列表/entryjp|245/208|{{C|皮卡丘ex|SV8}}|雷||SAR|全}}`: número chinês, nome, **set
   japonês de origem** (Pokémon) ou `{{TCG|nome}}` (treinador/energia), raridade. Gem Pack usa
   `07 01/09` (pacote + número); promos usam `003/SV-P`.
2. **Página da carta** (`皮卡丘ex（SV8）`, `琉琪亚的展现（TCG）`): linhas
   `ExpansionList/main/zh` (impressão **simplificada** `cnicon/cnno/cnrar` + a **tradicional**
   correspondente `zhicon/zhno`, que espelha a japonesa, + `illus`) e `ExpansionList/main`
   (impressão **EN** `enexpansion/enno/enrar` + a **japonesa** correspondente `jaicon/jano` +
   `illus`). O nome EN vem do cabeçalho `{{N|皮卡丘ex||ピカチュウex|Pikachu ex}}`.

O nome do set EN vem em chinês (`浪湧電光`); a página desse set tem o langlink para a
Bulbapedia (`Surging Sparks (TCG)`), e `to_watchlist_set()` converte para o nome da watchlist
(`SV08: Surging Sparks`), com os subconjuntos pelo número (`TG23` → Trainer Gallery, `GG44` →
Galarian Gallery, `SV49` → Shiny Vault) e aliases para os nomes que a watchlist escreve
diferente (`151`, `Pokémon GO`, `Sword & Shield`…). Set sem nome na watchlist fica com o nome
Bulbapedia e a marca `en_set_unresolved` — nunca inventa.

## Junção (campo `how` de cada linha)

Da mais forte para a mais fraca; **nunca chuta**: com mais de um candidato a linha sai
`ambiguous` (lista os candidatos) e não vira par.

| `how` | regra | leitura |
|---|---|---|
| `tc-jp` | a impressão tradicional da linha simplificada (`SV8F 132` → JP `sv8 132`) é a mesma impressão japonesa da linha EN (`jaicon/jano`) | exata: mesma impressão, mesma arte |
| `set+illus+rar` | set JP de origem ↔ set EN (mapa JP→EN **aprendido do corpus** — toda linha EN com `jaicon` ensina — semeado por `ZH_SET_TO_EN`) **e** mesmo ilustrador **e** família de raridade compatível (SAR↔SIR, AR↔IR, SR↔UR, UR↔HR, SSR↔SHUR, RR↔DR…) | fingerprint sem imagem: quem desenhou + tipo de impressão + de onde veio |
| `set+rar` | a linha chinesa da wiki não traz ilustrador: set JP→EN + família de raridade únicos na página | mais fraco; fica marcado |
| `illus+rar` | sem set JP no mapa: ilustrador + família de raridade únicos na página | mais fraco; fica marcado |
| `None` | sem par EN identificável (`note`: `sem-par-en-identificavel`, `pagina-da-carta-nao-encontrada`, `sem-impressao-en-na-pagina`) | arte/impressão exclusiva do chinês, promo, ou dado ausente |

Exemplos reais (fixtures de teste, `tests/fixtures/zh_*.txt`):

- `CSV9C 245/208 SAR 皮卡丘ex` → tradicional `SV8F 132` = JP `SV8 132` → **Surging Sparks 238 SIR**
  (GIDORA), `tc-jp`.
- `CSV9C 257/208 SAR 琉琪亚的展现` (Lisia's Appeal, En Morikura) → a SIR inglesa 234 é de
  Nobusawa/Mochipuyo: **sem par EN** — arte exclusiva do simplificado. Antes, "nome + set" a
  deixava passar como se fosse a mesma carta.
- `CSV9C 258/208 UR 闪焰王牌ex` (Cinderace ex dourada) → Stellar Crown EN não tem HR dessa
  carta: **sem par EN** (impressão só do simplificado dentro de um set regular).
- `151C 191 SAR 梦幻ex` → `SV4aF 347` → **Paldean Fates 232 SIR** (USGMEN): a caixa 151 chinesa
  reimprime uma SAR de OUTRO set EN — `ZH_SET_TO_EN` (151C ↔ SV 151) dizia "mesmo set".
- `CSV9C 153 C 伊布` → Surging Sparks 143 **ou** Prismatic Evolutions 74 (mesmo ilustrador):
  `ambiguous` — alvo da conferência por imagem.

## Arquivo e uso

- `python zh_catalog.py` gera `src/catalog/zh_identity.json` (versionado; `_meta` com data,
  contagens por `how`, mapa JP→EN aprendido, sets EN citados e não resolvidos). `--report`
  escreve o funil da junção, páginas ausentes e ambíguas (local, `results/`). Cache bruto da
  API em `data/cache/52poke/` (local). ~1 req/s, lotes de 25.
- No scan (`src/chinese_scan.py`): `catalog_identity(row)` monta a chave **código simplificado
  + número chinês** pelo título (`CSV9C 245/208`, `151C`, `Gem Pack Vol.2 4/07`) ou, sem ela,
  pela página chinesa do PriceCharting já localizada (`/pokemon-chinese-csv9c/pikachu-ex-245`,
  `gem-pack-2/eevee-407` = 4/07, `promo/mew-ex-3sv-p`), e grava `row["zh_catalog"]`:
  - `mesma-carta` → identidade provada por impressão: `classify` dispensa número/set/raridade
    do título;
  - `outra-carta` → motivo `catalogo-outra-carta` (a impressão chinesa anunciada é outra carta EN);
  - `sem-par-en` → motivo `catalogo-sem-par-en`;
  - `ambigua` → motivo `catalogo-ambiguo` e a regra por set continua valendo;
  - `nao-catalogada`/None → regra por set (`ZH_SET_TO_EN`) como antes.
- `rescore()` recalcula `zh_catalog` com o catálogo vigente, então um JSON antigo re-pontua
  com a regra atual. O funil do `chinese_thesis.py` mostra os dois motivos novos como primeira
  etapa.
- Testes: `tests/test_zh_identity.py` (parser, junção pelas três rotas, negativos, nomes de set,
  chaves de anúncio, veredito, integração no `classify`/`rescore`). A suíte isola o catálogo
  real (`tests/conftest.py`): nenhum teste depende do que ele diz hoje.

## Limites honestos

- A fonte é uma wiki comunitária: linha faltando ou trocada vira `None`/`ambiguous`, nunca um
  par falso silencioso — mas também não há garantia de completude. Páginas de treinadores
  novos podem não existir ainda (`pagina-da-carta-nao-encontrada`).
- `how=illus+rar` é o elo fraco declarado; `ambiguous` são os casos que o texto não separa.
  A conferência por **imagem** (arte da impressão chinesa × EN) é a próxima camada e tem
  esses dois conjuntos como alvo definido. Não foi implementada aqui: precisa de amostra
  rotulada para calibrar o limiar antes de decidir identidade sozinha.
- Identidade não é preço nem tese: provar que a carta é a mesma só tira o motivo
  `set-zh-sem-correspondencia`; evidência de revenda chinesa, idioma e margem seguem iguais.
- `ZH_SET_TO_EN` continua como regra de retaguarda (tradicional espelha o japonês set a set) e
  como semente do mapa JP→EN.

## Resultado da geração

Geração de 2026-09-27 (`_meta` do arquivo; `python zh_catalog.py --report results/zh_identity_report.md` reproduz):

- 91 produtos simplificados (navegações SM/SWSH/SV/ME), 5679 páginas de carta lidas, 164 ausentes na wiki; ~240 chamadas à API na primeira leitura (regeração a partir do cache local não chama a wiki).
- 10707 impressões catalogadas; 470 entradas sem código ou número (decks/promos sem lista numerada) ficaram fora — não há como consultá-las.
- Ligação: `tc-jp` 4811 · `set+illus+rar` 496 · `set+rar` 652 · `illus+rar` 683 · ambíguas 187 · sem par EN 3878.
- Raridades altas (AR/SR/SAR/UR/HR/SSR/CHR/CSR): 1670 impressões — `tc-jp` 1007, `set+illus+rar` 34, `set+rar` 81, `illus+rar` 143, ambíguas 31, sem par 374.
- 611 das 1669 cartas EN da watchlist têm ao menos uma impressão simplificada identificada (o resto é carta de era/set sem edição simplificada, ou impressão que a wiki ainda não liga).
- Sem par EN nas raridades altas é, em grande parte, impressão que só existe em simplificado (UR douradas de compilação, SAR de arte própria, Gem Pack, energias) — exatamente o que o crivo precisa saber para não tratar como a carta EN.
- Validação em scan ao vivo ainda não feita: o próximo scan do modo chinês mede quanto do funil `set-zh-sem-correspondencia` vira `mesma-carta`/`catalogo-*`.
