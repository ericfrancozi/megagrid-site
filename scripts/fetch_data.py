#!/usr/bin/env python3
"""
MEGAGRID — Robô de dados v1
Executa via GitHub Actions (3x/dia: 09:00, 12:00 e 18:00 UTC = 06h, 09h e 15h BRT)
Fontes: CCEE CKAN · ONS CKAN/S3 · ANEEL · RSS feeds
Saída:  site/data/*.json
"""

import csv
import hashlib
import html
import io
import json
import logging
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

# ── Configuração ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("megagrid")

TZ_BR = ZoneInfo("America/Sao_Paulo")

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "site" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CCEE_API  = "https://dadosabertos.ccee.org.br/api/3/action"
ONS_API   = "https://dados.ons.org.br/api/3/action"
ONS_S3    = "https://ons-aws-prod-opendata.s3.amazonaws.com"
ANEEL_API = "https://dadosabertos.aneel.gov.br/api/3/action"

# UA de navegador: WAFs dos portais gov (CCEE/ANEEL) bloqueiam UAs de bot,
# o que fazia todas as chamadas falharem no GitHub Actions (2026-07).
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/csv;q=0.9, */*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

# Google News RSS — confiável, não bloqueia bots, agrega fontes oficiais e jornalísticas
_GN = "https://news.google.com/rss/search?hl=pt-BR&gl=BR&ceid=BR:pt-419&q="
RSS_FEEDS = {
    "Mercado Livre":  _GN + "mercado+livre+de+energia+el%C3%A9trica+CCEE",
    "Regulação":      _GN + "ANEEL+energia+el%C3%A9trica+regula%C3%A7%C3%A3o",
    "Política":       _GN + "MME+pol%C3%ADtica+energ%C3%A9tica+minist%C3%A9rio+energia",
    "Tarifas":        _GN + "bandeira+tarif%C3%A1ria+conta+luz+ANEEL",
    "Transição":      _GN + "energia+solar+e%C3%B3lica+renov%C3%A1vel+brasil+GD",
    # P1.4 — queries temáticas p/ ampliar o frescor diário
    "Leilões":        _GN + "leil%C3%A3o+de+energia+el%C3%A9trica",
    "Preços":         _GN + "PLD+CCEE+pre%C3%A7o+energia",
    "Migração":       _GN + "migra%C3%A7%C3%A3o+mercado+livre+energia",
    "Autoprodução":   _GN + "autoprodu%C3%A7%C3%A3o+energia",
    "Armazenamento":  _GN + "armazenamento+baterias+setor+el%C3%A9trico",
    "Subsídios":      _GN + "subs%C3%ADdios+CDE+conta+de+luz",
}
# Feeds institucionais — com o nome do órgão no campo `fonte`.
#
# P1.6 (2026-08-01): os três RSS diretos foram REMOVIDOS por estarem mortos
# na origem — verificado um a um, ver FEEDS_OFICIAIS_REMOVIDOS. Nunca
# entregaram um item sequer desde o P1.4, e a falha passou despercebida
# porque o Google News enche o acervo e mascara o buraco.
#
# Sobra o `espelho`: busca do Google News restrita ao domínio do órgão.
# Atenção ao que ele NÃO é: a URL continua sendo redirect do Google News,
# então isto dá atribuição correta ao órgão, não link oficial direto.
RSS_FEEDS_OFICIAIS = {
    "CCEE":  {"espelho": _GN + "site%3Accee.org.br"},
    "ANEEL": {"espelho": _GN + "site%3Agov.br%2Faneel"},
    "MME":   {"espelho": _GN + "site%3Agov.br%2Fmme"},
}

# Registro do que saiu e por quê — impresso no log a cada execução para a
# remoção não virar conhecimento perdido. Reavaliar de tempos em tempos:
# se um órgão republicar RSS, basta voltar a URL como "direto".
FEEDS_OFICIAIS_REMOVIDOS = {
    "CCEE":  ("https://www.ccee.org.br/rss/pautas-e-destaques.xml",
              "HTTP 403 — WAF do portal bloqueia qualquer cliente"),
    "ANEEL": ("https://www.aneel.gov.br/rss.xml",
              "HTTP 403 — domínio legado, órgão migrou para gov.br/aneel"),
    "MME":   ("https://www.gov.br/mme/pt-br/assuntos/noticias/RSS",
              "HTTP 404 — plataforma gov.br descontinuou RSS "
              "(a página de notícias responde 200 e não expõe feed)"),
}

# O espelho indexa o domínio inteiro, então traz também página estática
# (login, acervo, "consultas públicas"). Filtro rigoroso — na dúvida,
# descarta: é preferível o espelho render 0 itens a sujar a home.
ESPELHO_MAX_IDADE_DIAS = 7   # e item sem data de publicação é descartado
ESPELHO_MAX_POR_ORGAO  = 3
ESPELHO_TITULO_MIN     = 25  # "Acervo CCEE - CCEE" e afins

# ── Dedup por história (P1.6) ───────────────────────────────────────
# A mesma pauta contada por 10 veículos ocupava a dobra inteira da home.
# Dedup por URL/título não pega isso: os títulos são diferentes, a
# história é a mesma. Agrupamos por similaridade de tokens.
# Calibrado no acervo de 2026-08-01 (o cluster "bandeira amarela de agosto",
# 10 veículos no mesmo dia). O Jaccard DENTRO desse cluster varia de 0.30 a
# 1.00 — os veículos contam a mesma decisão com palavras bem diferentes
# ("bandeira tarifária amarela" vs. "tarifa extra na conta de luz"). Medido:
#     limiar   acervo   cluster da bandeira   grupos indevidos
#      0.60      54          6 itens                 0
#      0.50      50          2 itens                 0
#      0.40      49          1 item  ✓               0
# 0.40 é o ponto em que o cluster colapsa por inteiro sem fundir história
# alheia. Abaixo disso não melhora nada e só aumenta o risco.
JACCARD_MIN = 0.40           # ↑ separa mais (menos agrupamento) · ↓ agrupa mais
# A janela é o que impede a mesma pauta MENSAL de colapsar entre si:
# "bandeira amarela em julho" e "...em agosto" são quase idênticas em
# tokens e só não se fundem porque estão a 30 dias uma da outra.
DEDUP_JANELA_HORAS = 48      # só agrupa itens publicados nesta janela

STOPWORDS_PT = {
    "a", "à", "ao", "aos", "as", "às", "com", "como", "da", "das", "de",
    "dela", "dele", "deles", "do", "dos", "e", "em", "entre", "essa",
    "esse", "esta", "este", "eu", "foi", "há", "isso", "já", "la", "lhe",
    "mais", "mas", "me", "mesmo", "meu", "muito", "na", "nas", "nem",
    "no", "nos", "num", "numa", "o", "os", "ou", "para", "pela", "pelo",
    "per", "por", "porque", "qual", "quando", "que", "quem", "se", "sem",
    "ser", "será", "seu", "sobre", "sua", "são", "só", "também", "tem",
    "ter", "um", "uma", "vai", "veja", "vem", "ainda", "após", "até",
    "deve", "devem", "seguirá", "segue", "continua", "continuará", "fica",
    "ficar", "pode", "podem", "diz", "saiba", "confira", "entenda",
}

# Veículos especializados no setor — critério 2 de sobrevivência do grupo.
VEICULOS_ESPECIALIZADOS = (
    "megawhat", "agência infra", "agencia infra", "canal energia",
    "cenário energia", "cenario energia", "agência eixos", "agencia eixos",
    "canal solar", "epbr",
)
ESPELHO_BLOCKLIST = (
    "login", "acervo", "academy", "portal", "webmail", "intranet",
    "consultas publicas", "consulta publica", "audiencia publica",
    "fale conosco", "perguntas frequentes", "faq", "mapa do site",
    "acesso a informacao", "biblioteca", "glossario", "quem somos",
    "institucional",
    # seções de site que passaram no 1º dry run (2026-08-01)
    "organizacoes", "contas setoriais",
)

EDITORIA_RULES = {
    "mercado-livre": [
        "mercado livre", "acl", "comercialização", "migração",
        "consumidor livre", "varejista", "ccee", "contrato bilateral",
    ],
    "regulacao": [
        "aneel", "regulação", "resolução normativa", "nota técnica",
        "consulta pública", "lei ", "decreto", "portaria",
    ],
    "politica-energetica": [
        "mme", "política energética", "governo federal", "ministério",
        "epe", "plano decenal", "pne", "matriz energética",
    ],
    "empresas": [
        "empresa", "comercializadora", "geradora", "distribuidora",
        "transmissora", "investimento", "fusão", "aquisição",
    ],
    "transicao": [
        "solar", "fotovoltaica", "eólica", "renovável", "bateria",
        "armazenamento", "veículo elétrico", "carro elétrico", "ev ",
        "hidrogênio", "gd ", "geração distribuída", "data center",
        "curtailment", "offshore",
    ],
    "tarifas": [
        "tarifa", "bandeira", "conta de luz", "consumidor cativo",
        "revisão tarifária", "igpm", "reajuste",
    ],
}

# Banco de imagens por editoria (P1.9). Antes havia UMA foto fixa por
# editoria, então qualquer bloco de 4 cards da mesma editoria mostrava 4
# fotos idênticas. Todas as URLs abaixo foram verificadas (HTTP 200) e
# revisadas visualmente uma a uma — não são IDs colados no escuro.
#
# Saíram por não terem nada a ver com o setor:
#   tarifas  photo-1563013544… mão passando cartão de crédito no notebook
#   política photo-1524492412… Taj Mahal
_U = "https://images.unsplash.com/"
_Q = "?w=600&q=70"
BANCO_IMAGENS = {
    # painéis solares, eólicas, offshore — o tema tem farta oferta boa
    "transicao": [_U + p + _Q for p in (
        "photo-1508514177221-188b1cf16e9d",  # campo de painéis solares
        "photo-1466611653911-95081537e5b7",  # eólicas ao entardecer
        "photo-1497435334941-8c899ee9e8e9",  # usina solar (aérea)
        "photo-1548337138-e87d889cc369",     # eólicas offshore
        "photo-1497440001374-f26997328c1b",  # painéis sobre grama
        "photo-1611365892117-00ac5ef43c90",  # painéis e edificação
        "photo-1532601224476-15c79f2f7a51",  # eólicas em colinas
        "photo-1487875961445-47a00398c267",  # parque eólico
        "photo-1558449028-b53a39d100fc",     # fileira de painéis
        "photo-1595437193398-f24279553f4f",  # painel solar, céu limpo
    )],
    # mercado/indústria/infraestrutura — tira a torre ao pôr do sol do
    # posto de imagem única, que era o clichê saturado da editoria
    "mercado-livre": [_U + p + _Q for p in (
        "photo-1573164713988-8665fc963095",  # data center
        "photo-1591696205602-2f950c417cb9",  # gráfico de preços em tela
        "photo-1516937941344-00b4e0337589",  # planta industrial
        "photo-1516110833967-0b5716ca1387",  # automação industrial
        "photo-1504328345606-18bbc8c9d7d1",  # soldador, indústria pesada
        "photo-1494961104209-3c223057bd26",  # contêineres, logística
        "photo-1473341304170-971dccb5ac1e",  # linhas de transmissão
        "photo-1521737711867-e3b97375f902",  # reunião de negócio
        "photo-1454165804606-c3d57bc86b40",  # mesa de trabalho e planilha
    )],
    # documento, assinatura, norma
    "regulacao": [_U + p + _Q for p in (
        "photo-1450101499163-c8848c66ca85",  # assinatura de documento
        "photo-1503387762-592deb58ef4e",     # prancheta técnica
        "photo-1435527173128-983b87201f4d",  # caderno aberto
        "photo-1517048676732-d65bc937f952",  # reunião em mesa
        "photo-1552664730-d307ca884978",     # equipe em discussão
        "photo-1531482615713-2afd69097998",  # análise em laptop
    )],
    "politica-energetica": [_U + p + _Q for p in (
        "photo-1587691592099-24045742c181",  # apresentação/quadro
        "photo-1486406146926-c627a92ad1ab",  # prédios institucionais
        "photo-1600880292203-757bb62b4baf",  # acordo/reunião
        "photo-1516937941344-00b4e0337589",  # planta industrial
        "photo-1517048676732-d65bc937f952",  # mesa de reunião
    )],
    # medidor/quadro de luz/rede de distribuição — ver nota no relatório:
    # este é o banco mais curto, o acervo verificado não deu mais.
    "tarifas": [_U + p + _Q for p in (
        "photo-1621905251189-08b45d6a269e",  # técnico no quadro elétrico
        "photo-1473341304170-971dccb5ac1e",  # rede de distribuição
        "photo-1560518883-ce09059eeffa",     # residência (conta de luz)
        "photo-1591696205602-2f950c417cb9",  # custo/reajuste em gráfico
    )],
}

# Usado para editoria sem banco (ex.: "empresas") e como marcador do que
# pode ser sobrescrito: imagem vinda do próprio feed é preservada.
IMAGENS_FALLBACK = {
    "mercado-livre": "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=600&q=70",
    "regulacao":     "https://images.unsplash.com/photo-1450101499163-c8848c66ca85?w=600&q=70",
    "politica-energetica": "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=600&q=70",
    "empresas":      "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600&q=70",
    "transicao":     "https://images.unsplash.com/photo-1509391366360-2e959784a276?w=600&q=70",
    "tarifas":       "https://images.unsplash.com/photo-1563013544-824ae1b704d3?w=600&q=70",
}

BANDEIRA_META = {
    "verde":     {"adicional": 0.0,     "descricao": "Condições favoráveis de geração"},
    "amarela":   {"adicional": 0.01874, "descricao": "Condições de atenção"},
    "vermelha1": {"adicional": 0.03971, "descricao": "Condições de alerta — P1"},
    "vermelha2": {"adicional": 0.09492, "descricao": "Condições críticas — P2"},
    "escassez":  {"adicional": 0.14200, "descricao": "Escassez hídrica"},
}

# IDs dos recursos CCEE (um arquivo por ano)
CCEE_PLD_SEMANAL = {
    "2025": "b1a35c4b-a3ad-4572-9927-4dc5724578bd",
    "2026": "e34f98e8-68df-4a22-972f-02cb621ec978",
}

# Piso/teto do PLD homologados pela ANEEL (revisar anualmente).
# Usados no fallback via CMO: por definição, PLD semanal = CMO limitado
# ao piso/teto — então clamp(CMO) reproduz o PLD oficial.
PLD_PISO = 63.60
PLD_TETO = 726.00

# ── Helpers ─────────────────────────────────────────────────────────

def get(url, params=None, timeout=30, retries=3):
    """GET com retry/backoff. Loga status HTTP e início do body em falha
    para diagnóstico visível no log do GitHub Actions."""
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
            if r.status_code >= 400:
                last_err = f"HTTP {r.status_code}: {r.text[:160]!r}"
                log.warning("GET %s → %s (tentativa %d/%d)", url, last_err, attempt, retries)
            else:
                return r
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            log.warning("GET %s → %s (tentativa %d/%d)", url, last_err, attempt, retries)
        if attempt < retries:
            time.sleep(2 * attempt)
    log.error("GET esgotou tentativas: %s → %s", url, last_err)
    return None


def load_existing(name: str) -> dict:
    p = DATA_DIR / name
    if p.exists():
        try:
            return json.loads(p.read_text("utf-8"))
        except Exception:
            pass
    return {}


def save(name: str, data: dict):
    p = DATA_DIR / name
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    log.info("  → %s gravado", name)


def now_iso():
    """UTC — uso interno: campo `updated` e comparações de idade."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def agora_br():
    """Horário de Brasília. TODO carimbo que o leitor vê (id da manchete-dado,
    rótulo de mês, data na newsletter) sai daqui — às 22h de 01/08 em BRT o
    UTC já é 02/08, e a manchete nascia com a data do dia seguinte."""
    return datetime.now(TZ_BR)


def classify_editoria(text: str) -> str:
    """Slug canônico de editoria a partir do texto do item. Fonte ÚNICA da
    verdade (P1.6): quem decide o campo `editoria` decide também o prefixo
    do id. Antes eram duas variáveis diferentes — o id herdava o nome do
    feed ('Política') e a editoria vinha do conteúdo ('mercado-livre'),
    então os dois discordavam e o id ainda saía acentuado."""
    t = text.lower()
    scores = {
        ed: sum(1 for kw in kws if kw in t)
        for ed, kws in EDITORIA_RULES.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "mercado-livre"


def montar_id(editoria: str, url: str) -> str:
    """id = <slug da editoria sem acento>_<hash da url>. O prefixo espelha
    a editoria por construção, então não há como divergirem."""
    return f"{_sem_acento(editoria)}_{abs(hash(url)) % 100000}"


def normaliza_id(item: dict) -> dict:
    """Realinha o id de item já gravado cujo prefixo não bate com a
    editoria (acervo anterior ao P1.6). Preserva o sufixo numérico para o
    id continuar estável entre execuções."""
    ed = item.get("editoria") or "mercado-livre"
    slug = _sem_acento(ed)
    atual = str(item.get("id", ""))
    sufixo = atual.rsplit("_", 1)[-1] if "_" in atual else ""
    if not sufixo.isdigit():
        sufixo = str(abs(hash(item.get("url", ""))) % 100000)
    novo = f"{slug}_{sufixo}"
    if novo != atual:
        item["id"] = novo
    return item


# ── CCEE — PLD Semanal ──────────────────────────────────────────────

def _ccee_discover_pld_resource(year: str):
    """Descobre dinamicamente o resource_id do pld_media_semanal para o ano
    (auto-heal quando a CCEE publicar o recurso de um ano novo)."""
    r = get(f"{CCEE_API}/package_show", {"id": "pld_media_semanal"})
    if not r:
        return None
    try:
        for res in r.json()["result"]["resources"]:
            if year in (res.get("name") or ""):
                log.info("  resource descoberto p/ %s: %s", year, res["id"])
                return res["id"]
    except Exception as exc:
        log.warning("  package_show parse: %s", exc)
    return None


def _fetch_pld_via_cmo(existing: dict):
    """PLD calculado a partir do CMO semanal ONS (S3, sem geobloqueio).
    PLD = clamp(CMO, PLD_PISO, PLD_TETO) por submercado/semana."""
    year = datetime.utcnow().year
    url = _ons_csv_url("cmo-semanal", year) or \
        f"{ONS_S3}/dataset/cmo_se/CMO_SEMANAL_{year}.csv"
    r = get(url, timeout=60)
    if not r:
        return None
    try:
        rows = _parse_ons_csv(r.text)
        if not rows:
            raise ValueError("CSV vazio")
        sem_key = next((k for k in rows[0]
                        if "semana" in k.lower() and ("ini" in k.lower() or "inicio" in k.lower())), None) \
            or next((k for k in rows[0] if "data" in k.lower() or "din" in k.lower()), None)
        val_key = next((k for k in rows[0]
                        if "cmo" in k.lower() and "media" in k.lower()), None) \
            or next((k for k in rows[0] if "cmo" in k.lower() and "val" in k.lower()), None)
        if not sem_key or not val_key:
            raise ValueError(f"colunas não encontradas; header={list(rows[0])}")

        weeks: dict = {}
        for rw in rows:
            iso = (rw.get(sem_key) or "")[:10]
            sub = _ons_sub_key(rw)
            if not iso or not sub:
                continue
            try:
                cmo = float(str(rw[val_key]).replace(",", "."))
            except (ValueError, TypeError):
                continue
            pld_val = round(min(max(cmo, PLD_PISO), PLD_TETO), 2)
            wk = weeks.setdefault(iso, {"semana": iso})
            wk[{"SE/CO": "SE_CO", "S": "S", "NE": "NE", "N": "N"}[sub]] = pld_val

        historico = sorted(weeks.values(), key=lambda w: w["semana"])[-24:]
        if not historico:
            raise ValueError("nenhuma semana processada")

        latest = historico[-1]
        prev = historico[-2] if len(historico) >= 2 else {}

        def variacao(k):
            curr, ant = latest.get(k, 0), prev.get(k, latest.get(k, 0))
            return round((curr - ant) / ant * 100, 1) if ant else 0

        data = {
            "updated": now_iso(),
            "semana_ref": latest["semana"],
            "fonte": "ONS — CMO semanal (PLD = CMO com teto/piso ANEEL)",
            "submercados": {
                "SE/CO": {"preco": latest.get("SE_CO", 0), "variacao": variacao("SE_CO")},
                "S":     {"preco": latest.get("S", 0),     "variacao": variacao("S")},
                "NE":    {"preco": latest.get("NE", 0),    "variacao": variacao("NE")},
                "N":     {"preco": latest.get("N", 0),     "variacao": variacao("N")},
            },
            "historico": [
                {"semana": w["semana"], "SE_CO": w.get("SE_CO", 0), "S": w.get("S", 0),
                 "NE": w.get("NE", 0), "N": w.get("N", 0)} for w in historico
            ],
        }
        save("pld.json", data)
        log.info("  PLD via CMO %s: SE/CO R$ %.2f", latest["semana"],
                 data["submercados"]["SE/CO"]["preco"])
        return data
    except Exception as exc:
        log.warning("  CMO parse falhou (%s)", exc)
        return None


def fetch_pld() -> dict:
    log.info("CCEE PLD semanal…")
    existing = load_existing("pld.json")
    year = str(datetime.utcnow().year)
    res_id = CCEE_PLD_SEMANAL.get(year) or _ccee_discover_pld_resource(year) \
        or CCEE_PLD_SEMANAL["2026"]

    r = get(f"{CCEE_API}/datastore_search", {
        "resource_id": res_id,
        "limit": 300,
        "sort": "_id asc",
    })
    if not r:
        # último recurso: redescobrir o resource (id pode ter mudado)
        alt = _ccee_discover_pld_resource(year)
        if alt and alt != res_id:
            r = get(f"{CCEE_API}/datastore_search", {
                "resource_id": alt, "limit": 300, "sort": "_id asc",
            })
    if not r:
        # A CCEE geobloqueia IPs fora do BR (GitHub Actions = EUA, HTTP 403).
        # Fallback 2: ponte própria na Vercel rodando em São Paulo (gru1).
        log.info("  CCEE direta bloqueada — tentando ponte BR (megagrid.com.br/api/ccee-pld)")
        r = get("https://megagrid.com.br/api/ccee-pld", {"year": year}, timeout=60)
    if not r:
        # Fallback 3: CMO semanal da ONS (S3 liberado). Por definição
        # regulatória, PLD semanal = CMO limitado ao piso/teto ANEEL.
        log.info("  Ponte falhou — calculando PLD via CMO semanal ONS")
        data = _fetch_pld_via_cmo(existing)
        if data:
            return data
        log.warning("  PLD fetch falhou — mantendo existente")
        return existing

    records = r.json()["result"]["records"]
    sub_map = {"SUDESTE": "SE_CO", "SUL": "S", "NORDESTE": "NE", "NORTE": "N"}
    weeks: dict = {}

    for rec in records:
        raw_date = rec["SEMANA"]  # DD/MM/AAAA
        try:
            dt = datetime.strptime(raw_date, "%d/%m/%Y")
        except ValueError:
            continue
        iso = dt.strftime("%Y-%m-%d")
        sub = sub_map.get(rec["SUBMERCADO"])
        if not sub:
            continue
        if iso not in weeks:
            weeks[iso] = {"semana": iso}
        weeks[iso][sub] = round(float(rec["PLD_MEDIA_SEMANA"]), 2)

    historico = sorted(weeks.values(), key=lambda w: w["semana"])[-24:]
    if not historico:
        log.warning("  Nenhum registro PLD processado")
        return existing

    latest = historico[-1]
    prev   = historico[-2] if len(historico) >= 2 else {}

    def variacao(sub_key):
        curr = latest.get(sub_key, 0)
        ant  = prev.get(sub_key, curr)
        if ant and ant > 0:
            return round((curr - ant) / ant * 100, 1)
        return 0

    data = {
        "updated": now_iso(),
        "semana_ref": latest["semana"],
        "fonte": "CCEE — Dados Abertos (dadosabertos.ccee.org.br)",
        "submercados": {
            "SE/CO": {"preco": latest.get("SE_CO", 0), "variacao": variacao("SE_CO")},
            "S":     {"preco": latest.get("S",     0), "variacao": variacao("S")},
            "NE":    {"preco": latest.get("NE",    0), "variacao": variacao("NE")},
            "N":     {"preco": latest.get("N",     0), "variacao": variacao("N")},
        },
        "historico": [
            {
                "semana": w["semana"],
                "SE_CO": w.get("SE_CO", 0),
                "S":     w.get("S",     0),
                "NE":    w.get("NE",    0),
                "N":     w.get("N",     0),
            }
            for w in historico
        ],
    }
    save("pld.json", data)
    se = data["submercados"]["SE/CO"]
    log.info("  SE/CO: R$ %.2f (%.1f%%)", se["preco"], se["variacao"])
    return data


# ── ONS — Reservatórios (EAR) ───────────────────────────────────────

def _ons_csv_url(package: str, year: int):
    """Resolve a URL do CSV anual de um dataset ONS via package_show.
    ONS não tem datastore ativo — os dados vivem em CSVs no S3."""
    r = get(f"{ONS_API}/package_show", {"id": package}, timeout=30)
    if not r:
        return None
    try:
        csvs = [res["url"] for res in r.json()["result"]["resources"]
                if (res.get("format") or "").upper() == "CSV" and res.get("url")]
    except Exception as exc:
        log.warning("  ONS package_show parse: %s", exc)
        return None
    for y in (year, year - 1):  # fallback: ano anterior (virada de ano)
        for u in csvs:
            if str(y) in u:
                return u
    return None


def _parse_ons_csv(text: str):
    """DictReader defensivo p/ CSVs ONS (separador ';' padrão, fallback ',')."""
    header = text.split("\n", 1)[0]
    sep = ";" if header.count(";") >= header.count(",") else ","
    return list(csv.DictReader(io.StringIO(text), delimiter=sep))


_ONS_SUB_MAP = {"SE": "SE/CO", "S": "S", "NE": "NE", "N": "N"}


def _ons_sub_key(row: dict):
    """Mapeia subsistema ONS → chave do site (SE/CO, S, NE, N)."""
    sid = (row.get("id_subsistema") or "").strip().upper()
    if sid in _ONS_SUB_MAP:
        return _ONS_SUB_MAP[sid]
    nome = (row.get("nom_subsistema") or "").strip().upper()
    if "SUDESTE" in nome:
        return "SE/CO"
    if "NORDESTE" in nome:
        return "NE"
    if "NORTE" in nome:
        return "N"
    if "SUL" in nome:
        return "S"
    return None


def fetch_reservatorios() -> dict:
    log.info("ONS reservatórios (EAR)…")
    existing = load_existing("reservatorios.json")
    year = datetime.utcnow().year

    url = _ons_csv_url("ear-diario-por-subsistema", year) or \
        f"{ONS_S3}/dataset/ear_subsistema_di/EAR_DIARIO_SUBSISTEMA_{year}.csv"
    r = get(url, timeout=60)
    if not r:
        log.warning("  EAR fetch falhou — mantendo existente")
        return existing

    try:
        rows = _parse_ons_csv(r.text)
        if not rows:
            raise ValueError("CSV vazio")
        date_key = next((k for k in rows[0] if "data" in k.lower()), None)
        pct_key = next((k for k in rows[0]
                        if "percentual" in k.lower() and "ear" in k.lower()), None)
        if not date_key or not pct_key:
            raise ValueError(f"colunas não encontradas; header={list(rows[0])}")

        latest_date = max(rw[date_key] for rw in rows if rw.get(date_key))
        sub_ear = {}
        for rw in rows:
            if rw.get(date_key) != latest_date:
                continue
            sub = _ons_sub_key(rw)
            if not sub:
                continue
            try:
                sub_ear[sub] = round(float(str(rw[pct_key]).replace(",", ".")), 1)
            except (ValueError, TypeError):
                pass
        if not sub_ear:
            raise ValueError("nenhum subsistema reconhecido")

        avg = round(sum(sub_ear.values()) / len(sub_ear), 1)
        data = {
            "updated": now_iso(),
            "data_ref": latest_date,
            "fonte": "ONS — Dados Abertos (dados.ons.org.br)",
            "ear_percentual": avg,
            "subsistemas": sub_ear,
        }
        save("reservatorios.json", data)
        log.info("  EAR %s: %.1f%% %s", latest_date, avg, sub_ear)
        return data
    except Exception as exc:
        log.warning("  EAR parse falhou (%s) — mantendo existente", exc)
        return existing


# ── ONS — Carga do SIN ──────────────────────────────────────────────

def fetch_carga() -> dict:
    log.info("ONS carga verificada…")
    existing = load_existing("carga.json")
    year = datetime.utcnow().year

    url = _ons_csv_url("carga-energia", year) or \
        f"{ONS_S3}/dataset/carga_energia_di/CARGA_ENERGIA_{year}.csv"
    r = get(url, timeout=60)
    if not r:
        log.warning("  Carga fetch falhou — mantendo existente")
        return existing

    try:
        rows = _parse_ons_csv(r.text)
        if not rows:
            raise ValueError("CSV vazio")
        date_key = next((k for k in rows[0]
                         if "instante" in k.lower() or "data" in k.lower()), None)
        val_key = next((k for k in rows[0]
                        if "carga" in k.lower() and "mw" in k.lower()), None)
        if not date_key or not val_key:
            raise ValueError(f"colunas não encontradas; header={list(rows[0])}")

        # soma dos subsistemas por dia = carga do SIN
        por_dia: dict = {}
        for rw in rows:
            d = (rw.get(date_key) or "")[:10]
            try:
                v = float(str(rw[val_key]).replace(",", "."))
            except (ValueError, TypeError):
                continue
            if d:
                por_dia[d] = por_dia.get(d, 0.0) + v
        if not por_dia:
            raise ValueError("nenhum dia agregado")

        dias = sorted(por_dia)
        ultimo = dias[-1]
        val = por_dia[ultimo]
        var = 0.0
        if len(dias) >= 2 and por_dia[dias[-2]]:
            var = round((val - por_dia[dias[-2]]) / por_dia[dias[-2]] * 100, 1)

        data = {
            "updated": now_iso(),
            "data_ref": ultimo,
            "fonte": "ONS — Carga Verificada",
            "carga_mwmed": round(val),
            "variacao": var,
        }
        save("carga.json", data)
        log.info("  Carga %s: %.0f MWmed (%+.1f%%)", ultimo, val, var)
        return data
    except Exception as exc:
        log.warning("  Carga parse falhou (%s) — mantendo existente", exc)
        return existing


# ── ANEEL — Bandeira Tarifária ──────────────────────────────────────

# REGRA GERAL — ORDEM DE ARQUIVO EXTERNO NÃO É GARANTIA (P1.14)
#
# Nunca confiar na ordem em que uma fonte externa entrega suas linhas. A
# seleção do "registro mais recente" é SEMPRE explícita, por max() sobre o
# campo de DATA — jamais records[0], records[-1] ou sort=_id.
#
# Custou caro: até 17/08/2026 este extrator pedia `sort=_id desc` e lia
# records[0]. `_id` é o número da linha atribuído na ingestão do datastore e
# não tem relação alguma com a competência. A ANEEL republicou o recurso em
# 17/08/2026 e a série foi reingerida em outra ordem — agosto/2026 caiu no
# _id 74 e a última linha (_id 140) passou a ser junho/2020. O site publicou
# "bandeira verde, junho/2020, adicional zero" e a newsletter do dia saiu com
# esse dado. A fonte estava correta e completa o tempo todo; o robô é que
# escolhia a linha errada.
#
# Resource verificado em 2026-07: dataset "bandeiras-tarifarias",
# recurso "Bandeira Tarifária - Acionamento" (datastore ativo).
ANEEL_BANDEIRA_RES = "0591b8f6-fe54-437b-b72b-1aa2efd46e42"

_MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
             "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def _num_br(v) -> float:
    """Número em formato BR → float. '18,85' → 18.85 · '1.234,56' → 1234.56.
    O ponto só é separador de milhar quando existe vírgula decimal no valor;
    sem vírgula, '18.85' é decimal e stripar o ponto daria 1885."""
    s = str(v).strip()
    if not s:
        raise ValueError("valor vazio")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s)


def _competencia(rec: dict) -> str:
    """DatCompetencia normalizada em YYYY-MM-DD ('' se ausente/inválida)."""
    c = str(rec.get("DatCompetencia") or "")[:10]
    return c if len(c) == 10 and c[4] == "-" else ""


def _bandeira_mais_recente(records: list) -> dict:
    """Registro de MAIOR DatCompetencia. Ver REGRA acima: seleção por data,
    nunca por posição."""
    validos = [rc for rc in records if _competencia(rc)]
    return max(validos, key=_competencia) if validos else None


def fetch_bandeira() -> dict:
    log.info("ANEEL bandeira tarifária…")
    existing = load_existing("bandeira.json")

    hoje_br = agora_br()
    mes_corrente = f"{hoje_br.year:04d}-{hoje_br.month:02d}"

    def _buscar(params):
        resp = get(f"{ANEEL_API}/datastore_search",
                   dict(params, resource_id=ANEEL_BANDEIRA_RES))
        if not resp:
            return None
        try:
            return _bandeira_mais_recente(resp.json()["result"]["records"])
        except Exception as exc:
            log.warning("  Bandeira resposta ilegível: %s", exc)
            return None

    # Caminho normal: o datastore ordena por competência e devolve o topo.
    # Pedimos 12 linhas em vez de 1 para que o max() local ainda tenha o que
    # comparar — a ordenação do servidor é conveniência, não fonte da verdade.
    rec = _buscar({"limit": 12, "sort": "DatCompetencia desc"})

    # Se o topo veio atrás do mês corrente, não dá para concluir atraso da
    # fonte sem descartar a hipótese de o `sort` ter sido ignorado (campo
    # inexistente já voltou HTTP 200 com a ordem natural). Baixa a série
    # inteira — são ~140 linhas — e refaz o max() antes de declarar defasagem.
    # `rec` é None sempre que a ANEEL não respondeu (get() esgotou as
    # tentativas). _competencia() espera um dict e quebra com None, então a
    # competência do topo sai para uma variável ANTES do if — inclusive para o
    # log. Em 18/08/2026 a linha de diagnóstico foi justamente o que derrubou o
    # robô inteiro numa indisponibilidade passageira da ANEEL: o script morreu
    # com AttributeError, o commit dos dados bons não aconteceu e o sentinela
    # foi pulado. Diagnóstico não pode ser mais frágil que o dado que descreve.
    comp_topo = _competencia(rec) if rec else ""
    if comp_topo[:7] < mes_corrente:
        log.info("  Topo em %s < %s — varrendo a série inteira",
                 comp_topo[:7] or "—", mes_corrente)
        rec_full = _buscar({"limit": 5000})
        if rec_full and _competencia(rec_full) > comp_topo:
            rec = rec_full

    if rec:
        try:
            raw = str(rec.get("NomBandeiraAcionada", "")).lower()
            if "escassez" in raw:
                cor_key = "escassez"
            elif "vermelha" in raw:
                cor_key = "vermelha2" if "2" in raw else "vermelha1"
            elif "verde" in raw:
                cor_key = "verde"
            else:
                cor_key = "amarela"

            # VlrAdicionalBandeira vem em R$/MWh com vírgula decimal
            # (ex.: "18,85" = R$ 18,85/MWh = R$ 0,01885/kWh; verde vem ",00").
            adicional_mwh = None
            adicional = BANDEIRA_META[cor_key]["adicional"]
            try:
                adicional_mwh = round(_num_br(rec.get("VlrAdicionalBandeira")), 2)
                adicional = round(adicional_mwh / 1000, 5)
            except (ValueError, TypeError) as exc:
                log.warning("  Adicional ilegível (%r): %s — usando tabela de %s",
                            rec.get("VlrAdicionalBandeira"), exc, cor_key)

            comp = _competencia(rec)[:7]  # YYYY-MM
            ano_ref = mes_num = None
            try:
                y, m = comp.split("-")
                ano_ref, mes_num = int(y), int(m)
                mes_ref = f"{_MESES_PT[mes_num-1]}/{ano_ref}"
            except Exception:
                mes_ref = agora_br().strftime("%m/%Y")

            data = {
                "updated": now_iso(),
                "mes": mes_ref,
                # Competência em YYYY-MM: rótulo legível é para o leitor, o
                # sentinela precisa de um campo que dê para comparar.
                "competencia": comp,
                "fonte": "ANEEL — Dados Abertos",
                "cor": cor_key,
                "adicional_kwh": adicional,
                "adicional_mwh": adicional_mwh if adicional_mwh is not None
                                 else round(adicional * 1000, 2),
                "descricao": BANDEIRA_META[cor_key]["descricao"],
            }

            # Defasagem: o registro é REAL e fresco pelo sentinela, mas pode
            # estar apontando para o mês passado enquanto a manchete da home já
            # fala do mês corrente. O site assume a defasagem em vez de
            # escondê-la — deduzir a cor do mês novo a partir de notícia
            # misturaria camada editorial com dado e mataria a rastreabilidade.
            #
            # REGRA — AVISO AUTOMÁTICO NÃO ACUSA TERCEIRO (P1.14)
            # O texto relata apenas o que NÓS não conseguimos obter, nunca a
            # conduta de uma instituição. Até 17/08/2026 este aviso afirmava
            # que "a ANEEL ainda não publicou" — e, na ocasião em que apareceu
            # em produção, a ANEEL havia publicado: quem falhou foi o robô, que
            # lia a linha errada. Atribuir a falha ao órgão regulador com base
            # num bug nosso é pior que exibir a cor errada. Não sabemos por que
            # o dado não veio; sabemos que não o temos. É só isso que se diz.
            if ano_ref and (ano_ref, mes_num) < (hoje_br.year, hoje_br.month):
                atual = f"{_MESES_PT[hoje_br.month-1]}/{hoje_br.year}"
                data["defasado"] = True
                data["aviso"] = (f"Referência: {mes_ref}. Não foi possível "
                                 f"obter o registro de {atual}.")
                log.warning("  Bandeira DEFASADA: registro de %s, hoje é %s",
                            mes_ref, atual)

            save("bandeira.json", data)
            log.info("  Bandeira %s (comp. %s): %s — R$ %.2f/MWh",
                     mes_ref, comp or "—", cor_key, data["adicional_mwh"])
            return data
        except Exception as exc:
            log.warning("  Bandeira parse falhou: %s", exc)

    log.warning("  Bandeira sem registro utilizável — mantendo existente")
    return existing


# ── Termômetro do MWh (0–100) ───────────────────────────────────────

def calc_termometro(pld: dict, ear: dict, carga: dict, bandeira: dict) -> dict:
    log.info("Calculando Termômetro…")

    # Componente EAR (peso 35%) — EAR baixo = risco alto
    ear_pct = ear.get("ear_percentual", 50)
    ear_score = max(0, min(100, round((1 - ear_pct / 100) * 100)))

    # Componente PLD momentum (peso 20%) — PLD acima da média histórica = risco alto
    hist = pld.get("historico", [])
    if hist:
        # max() por semana, não hist[-1]: fetch_pld grava a série ordenada, mas
        # o termômetro também lê pld.json de disco (run anterior, edição manual)
        # e não deve depender da ordem de um arquivo que não montou. Ver a REGRA
        # em ANEEL_BANDEIRA_RES.
        latest_pld = max(hist, key=lambda w: str(w.get("semana", ""))).get("SE_CO", 200)
        avg_pld = sum(w.get("SE_CO", 200) for w in hist) / max(len(hist), 1)
        ratio = latest_pld / max(avg_pld, 1)
        pld_score = max(0, min(100, round((ratio - 0.5) / 1.5 * 100)))
    else:
        latest_pld = 200
        pld_score = 50

    # Componente ENA (peso 25%) — proxy via EAR até ter dado direto ONS
    ena_score = max(0, min(100, round((1 - ear_pct / 100) * 80 + 10)))

    # Componente Carga (peso 10%)
    carga_score = 50  # sem série histórica de referência na v1

    # Componente Bandeira (peso 10%)
    band_scores = {"verde": 0, "amarela": 33, "vermelha1": 67, "vermelha2": 90, "escassez": 100}
    cor = bandeira.get("cor", "amarela")
    band_score = band_scores.get(cor, 33)

    score = round(
        ear_score  * 0.35 +
        ena_score  * 0.25 +
        pld_score  * 0.20 +
        carga_score* 0.10 +
        band_score * 0.10
    )

    niveis = [
        (25, "ótimo",    "Condições hídricas e de preços favoráveis"),
        (45, "normal",   "Mercado em equilíbrio"),
        (65, "atenção",  "Sinais de pressão nos preços"),
        (80, "alerta",   "Risco elevado de alta no PLD"),
        (101,"crítico",  "Condições críticas — reservatórios baixos e PLD elevado"),
    ]
    nivel, nivel_desc = next((n, d) for thr, n, d in niveis if score <= thr)

    data = {
        "updated": now_iso(),
        "score": score,
        "nivel": nivel,
        "nivel_desc": nivel_desc,
        "componentes": {
            "ear":          {"peso": 35, "valor": ear_pct,     "score": ear_score},
            "ena":          {"peso": 25, "valor": "via EAR",   "score": ena_score},
            "pld_momentum": {"peso": 20, "valor": latest_pld,  "score": pld_score},
            "carga":        {"peso": 10, "valor": carga.get("carga_mwmed", 0), "score": carga_score},
            "bandeira":     {"peso": 10, "valor": cor,          "score": band_score},
        },
        "metodologia": "EAR 35% · ENA 25% · Momentum PLD/CMO 20% · Carga 10% · Bandeira 10%",
    }
    save("termometro.json", data)
    log.info("  Score: %d/100 (%s)", score, nivel)
    return data


# ── RSS — Notícias ──────────────────────────────────────────────────

_ENTIDADE_RE = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]{1,31});")


def _clean_text(txt: str) -> str:
    """Decodifica entidades HTML e normaliza espaços (mata &nbsp; na origem)."""
    if not txt:
        return ""
    # dupla passada: feeds do Google News às vezes vêm com &amp;nbsp;
    txt = html.unescape(txt)
    if _ENTIDADE_RE.search(txt):
        txt = html.unescape(txt)
    return re.sub(r"\s+", " ", txt).strip()


def _strip_fonte_suffix(lead: str, fonte_display: str) -> str:
    """Remove o nome da fonte que o Google News anexa ao fim do resumo.

    No título vem como " - Fonte" (regex acima); no lead vem colado por espaço,
    então usamos o nome real da fonte do próprio item.
    """
    lead = (lead or "").strip()
    if not lead:
        return ""
    if fonte_display:
        lead = re.sub(r"\s*[-–—]?\s*" + re.escape(fonte_display) + r"\s*$", "", lead, flags=re.I).strip()
    # fallback: sufixo " - Fonte" clássico, caso o nome real não bata
    return re.sub(r"\s+[-–—]\s+[\w\s.'&]{2,40}$", "", lead).strip()


# Diagnóstico por feed da execução — alimentado por _parse_feed e impresso
# por resumo_feeds(). Existe para feed morto nunca mais passar batido.
FEED_DIAG = []


def resumo_feeds():
    """Tabela por feed: URL, HTTP, itens brutos, aceitos e por que caíram."""
    log.info("")
    log.info("═══ RESUMO POR FEED ═══")
    log.info("%-16s %-11s %6s %8s  %s", "FONTE", "HTTP", "BRUTOS", "ACEITOS",
             "PRINCIPAIS DESCARTES")
    for d in FEED_DIAG:
        motivos = sorted(d["motivos"].items(), key=lambda x: -x[1])[:3]
        txt = " · ".join(f"{m} ({n})" for m, n in motivos) or "—"
        log.info("%-16s %-11s %6d %8d  %s", d["fonte"][:16], str(d["status"])[:11],
                 d["brutos"], d["aceitos"], txt[:70])
        log.info("%-16s   %s", "", d["url"][:96])
    brutos = sum(d["brutos"] for d in FEED_DIAG)
    aceitos = sum(d["aceitos"] for d in FEED_DIAG)
    mortos = [d["fonte"] for d in FEED_DIAG if d["brutos"] == 0]
    log.info("─── %d feeds · %d itens brutos · %d aceitos", len(FEED_DIAG),
             brutos, aceitos)
    if mortos:
        log.warning("─── feeds sem entrada nenhuma: %s", ", ".join(mortos))
    log.info("")


def _sem_acento(txt: str) -> str:
    """Minúsculas sem acento — base das comparações da blocklist."""
    return unicodedata.normalize("NFKD", (txt or "").lower()) \
        .encode("ascii", "ignore").decode("ascii")


def _manchete_nua(titulo: str) -> str:
    """Descarta a atribuição que o Google News acopla ao título
    ('Strategic Planning — Agência Nacional de Energia Elétrica' →
    'Strategic Planning'), sobrando só a manchete para medir."""
    return re.split(r"\s+[—–-]\s+", titulo, maxsplit=1)[0].strip()


def _limpa_titulo_oficial(titulo: str) -> str:
    """Tira a atribuição redundante do Google News no título institucional
    ('… — Agência Nacional de Energia Elétrica - www.gov.br' → '…'): o selo
    do card já mostra o órgão."""
    t = re.sub(r"\s+[—–-]\s+(www\.)?gov\.br\s*$", "", titulo).strip()
    t = re.sub(r"\s+[—–-]\s+(ag[êe]ncia nacional de energia el[ée]trica|"
               r"minist[ée]rio de minas e energia|ccee)\s*$", "", t,
               flags=re.I).strip()
    return t


_SLUG_INTEIRO = re.compile(r"^[a-z0-9._-]+$")


def _e_slug(titulo: str) -> bool:
    """True quando o texto é um identificador, não uma manchete.

    P1.13 (2026-08-17): o espelho da CCEE indexa páginas de dataset do CKAN
    (dadosabertos.ccee.org.br), cujo <title> é o próprio slug do recurso —
    'operacao_balanceada_publica'. O feed entrega isso no lugar de um título,
    e o item foi parar no card de destaque da home.

    Dois critérios, qualquer um basta:
      · nenhum espaço E tem underscore  → 'operacao_balanceada_publica'
      · casa inteiramente com ^[a-z0-9._-]+$ → 'pld-medio-semanal', 'ear.sudeste'

    Não convertemos underscore em espaço de propósito: slug maquiado continua
    não sendo manchete, e embelezar esconderia o defeito de origem.
    """
    t = (titulo or "").strip()
    if not t:
        return False
    if " " not in t and "_" in t:
        return True
    return bool(_SLUG_INTEIRO.fullmatch(t))


def _espelho_rejeita(titulo: str, url: str, pub) -> str:
    """Filtro do espelho institucional. Retorna o motivo da rejeição
    ('' = aprovado). Todos os critérios são obrigatórios e cumulativos.

    Nota: a URL vem como redirect opaco do Google News
    (news.google.com/rss/articles/CBMi…), então a blocklist morde de fato
    no título — a checagem na URL fica como rede para o feed direto."""
    if not pub:
        return "sem data de publicação"
    idade = (datetime.utcnow() - datetime(*pub[:6])).days
    if idade > ESPELHO_MAX_IDADE_DIAS:
        return f"publicado há {idade}d"
    nua = _manchete_nua(titulo)
    if len(nua) < ESPELHO_TITULO_MIN:
        return f"manchete curta ({len(nua)} chars: {nua!r})"
    alvo = _sem_acento(titulo) + " " + _sem_acento(url)
    for termo in ESPELHO_BLOCKLIST:
        if termo in alvo:
            return f"blocklist: {termo!r}"
    return ""


def _parse_feed(fonte, feed_url, seen_urls, max_per_feed=10,
                forcar_fonte=False, espelho=False):
    """Parseia um feed RSS e retorna lista de itens novos.

    forcar_fonte: mantém `fonte` como veio (nome do órgão), ignorando o
                  veículo que o Google News reporta.
    espelho:      aplica o filtro rigoroso de página institucional estática.
    """
    novos = []
    rejeitados = []
    diag = {"fonte": fonte, "url": feed_url, "status": "?", "brutos": 0,
            "aceitos": 0, "motivos": {}}
    FEED_DIAG.append(diag)

    def descarta(motivo):
        diag["motivos"][motivo] = diag["motivos"].get(motivo, 0) + 1

    try:
        feed = feedparser.parse(feed_url)
        entries = feed.entries or []
        # feedparser NÃO levanta exceção em 403/404: devolve 0 entradas e
        # marca bozo. Era essa a falha silenciosa dos feeds oficiais (P1.6).
        diag["status"] = feed.get("status", "sem status")
        diag["brutos"] = len(entries)
        if not entries:
            erro = feed.get("bozo_exception")
            diag["motivos"]["feed vazio na origem"] = 1
            log.warning("  %s: 0 entradas (HTTP %s%s)", fonte, diag["status"],
                        f" · {type(erro).__name__}" if erro else "")
        else:
            log.info("  %s: %d entradas (HTTP %s)", fonte, len(entries),
                     diag["status"])
        # O espelho varre o feed inteiro porque o filtro descarta muito;
        # os feeds normais mantêm a janela original das primeiras entradas.
        janela = entries if espelho else entries[:max_per_feed]
        for entry in janela:
            if len(novos) >= max_per_feed:
                break
            url = entry.get("link", "")
            if not url:
                descarta("sem link")
                continue
            if url in seen_urls:
                descarta("url já no acervo")
                continue
            fonte_display = fonte
            if "news.google.com" in feed_url and not forcar_fonte:
                src = _clean_text(entry.get("source", {}).get("title", ""))
                if src:
                    fonte_display = src
            titulo = _clean_text(entry.get("title", ""))
            titulo = re.sub(r"\s+-\s+[\w\s]+$", "", titulo).strip()
            if not titulo or len(titulo) < 10:
                descarta("título ausente ou curto demais")
                continue
            if _e_slug(titulo):
                log.info("    %s: slug recusado como título: %r", fonte, titulo)
                descarta("título é slug, não manchete")
                continue
            lead = entry.get("summary", "") or entry.get("description", "")
            lead = _clean_text(re.sub(r"<[^>]+>", " ", lead))
            lead = _strip_fonte_suffix(lead, fonte_display)[:300]
            imagem = None
            for mc in entry.get("media_content", []):
                if mc.get("url"):
                    imagem = mc["url"]
                    break
            if not imagem:
                for enc in entry.get("enclosures", []):
                    if enc.get("href"):
                        imagem = enc["href"]
                        break
            editoria = classify_editoria(titulo + " " + lead + " " + fonte)
            if not imagem:
                imagem = IMAGENS_FALLBACK.get(editoria, IMAGENS_FALLBACK["mercado-livre"])
            pub = entry.get("published_parsed") or entry.get("updated_parsed")
            if espelho:
                motivo = _espelho_rejeita(titulo, url, pub)
                if motivo:
                    rejeitados.append((titulo[:60], motivo))
                    descarta("filtro do espelho: " + motivo.split(":")[0])
                    continue
                titulo = _limpa_titulo_oficial(titulo)
            data_pub = datetime(*pub[:6]).strftime("%Y-%m-%dT%H:%M:%SZ") if pub else now_iso()
            novos.append({
                "id": montar_id(editoria, url),
                "titulo": titulo,
                "lead": lead,
                "fonte": fonte_display,
                "url": url,
                "imagem": imagem,
                "editoria": editoria,
                "data": data_pub,
            })
            seen_urls.add(url)
    except Exception as exc:
        diag["status"] = f"exceção: {type(exc).__name__}"
        diag["motivos"][f"exceção {type(exc).__name__}"] = 1
        log.warning("  Erro %s: %s: %s", fonte, type(exc).__name__, exc)
    diag["aceitos"] = len(novos)
    if espelho and rejeitados:
        log.info("    espelho %s: %d descartados (ex.: %s)", fonte,
                 len(rejeitados), "; ".join(f"{t} — {m}" for t, m in rejeitados[:3]))
    return novos


MANCHETE_DADO_URL = "https://megagrid.com.br/#precos"

_BANDEIRA_LABEL = {
    "verde": "verde", "amarela": "amarela",
    "vermelha1": "vermelha patamar 1", "vermelha2": "vermelha patamar 2",
    "escassez": "de escassez hídrica",
}


def _brl(valor: float) -> str:
    """Formata número no padrão pt-BR (1.234,56)."""
    return f"{valor:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _pct(valor: float) -> str:
    return f"{abs(valor):.1f}".replace(".", ",")


def atribuir_imagens(itens: list) -> list:
    """Distribui as fotos do banco na lista JÁ ordenada para exibição.

    Atribuição estável: índice = md5(id) % len(banco). É md5 e não a hash()
    do Python de propósito — aquela muda a cada processo por causa do
    PYTHONHASHSEED, e a foto de uma notícia trocaria a cada build.

    Desempate anti-repetição: se o item cair na mesma foto do item anterior
    DA MESMA EDITORIA, anda +1 no banco (com wrap) até diferir. Assim
    nenhum bloco mostra duas fotos iguais em sequência.

    Imagem que veio do próprio feed é preservada — só sobrescreve o que era
    fallback genérico."""
    substituiveis = set(IMAGENS_FALLBACK.values())
    ultima = {}
    for it in itens:
        ed = it.get("editoria")
        banco = BANCO_IMAGENS.get(ed)
        if not banco:
            continue
        atual = it.get("imagem") or ""
        if atual and atual not in substituiveis and atual not in banco:
            continue  # foto real da matéria: não mexe
        h = hashlib.md5(str(it.get("id", "")).encode("utf-8")).hexdigest()
        idx = int(h, 16) % len(banco)
        img = banco[idx]
        giros = 0
        while img == ultima.get(ed) and giros < len(banco) - 1:
            idx = (idx + 1) % len(banco)
            img = banco[idx]
            giros += 1
        it["imagem"] = img
        ultima[ed] = img
    return itens


def _tokens_titulo(titulo: str) -> frozenset:
    """Título → conjunto de tokens significativos: minúsculo, sem acento,
    sem pontuação, sem stopword, sem token de 1–2 letras."""
    t = _sem_acento(titulo)
    brutos = re.split(r"[^a-z0-9]+", t)
    stop = {_sem_acento(s) for s in STOPWORDS_PT}
    return frozenset(p for p in brutos if len(p) > 2 and p not in stop)


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _data_item(item: dict):
    try:
        return datetime.strptime(item.get("data", ""), "%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        return None


def _e_oficial(item: dict) -> bool:
    """Link do próprio veículo/órgão, não redirect do Google News."""
    return "news.google.com" not in (item.get("url") or "")


def _e_especializado(item: dict) -> bool:
    fonte = _sem_acento(item.get("fonte") or "")
    return any(_sem_acento(v) in fonte for v in VEICULOS_ESPECIALIZADOS)


def _escolhe_sobrevivente(grupo: list) -> dict:
    """1º fonte oficial · 2º veículo especializado · 3º mais recente."""
    def chave(it):
        d = _data_item(it)
        return (
            0 if _e_oficial(it) else 1,
            0 if _e_especializado(it) else 1,
            -(d.timestamp() if d else 0),
        )
    return sorted(grupo, key=chave)[0]


def agrupar_por_historia(itens: list) -> list:
    """Colapsa a mesma história contada por veículos diferentes.

    Dois itens são a mesma história quando Jaccard dos tokens do título
    >= JACCARD_MIN E as publicações estão a menos de DEDUP_JANELA_HORAS
    uma da outra. O agrupamento é transitivo (union-find): se A~B e B~C,
    os três caem no mesmo grupo mesmo que A e C não se pareçam sozinhos.

    Sobra 1 item por grupo; as fontes descartadas ficam em `tambem_em`,
    para virar UI depois ("+9 veículos") em vez de informação jogada fora."""
    n = len(itens)
    if n < 2:
        return itens
    toks = [_tokens_titulo(it.get("titulo", "")) for it in itens]
    datas = [_data_item(it) for it in itens]
    janela = timedelta(hours=DEDUP_JANELA_HORAS)

    pai = list(range(n))

    def raiz(i):
        while pai[i] != i:
            pai[i] = pai[pai[i]]
            i = pai[i]
        return i

    def une(i, j):
        ri, rj = raiz(i), raiz(j)
        if ri != rj:
            pai[max(ri, rj)] = min(ri, rj)

    for i in range(n):
        for j in range(i + 1, n):
            if datas[i] and datas[j] and abs(datas[i] - datas[j]) > janela:
                continue
            if _jaccard(toks[i], toks[j]) >= JACCARD_MIN:
                une(i, j)

    grupos = {}
    for i in range(n):
        grupos.setdefault(raiz(i), []).append(itens[i])

    saida, colapsados = [], 0
    for membros in grupos.values():
        if len(membros) == 1:
            saida.append(membros[0])
            continue
        vencedor = _escolhe_sobrevivente(membros)
        outras = []
        for it in membros:
            if it is vencedor:
                continue
            f = it.get("fonte")
            if f and f not in outras:
                outras.append(f)
        if outras:
            vencedor["tambem_em"] = outras
        colapsados += len(membros) - 1
        log.info("    história agrupada (%d→1): %s", len(membros),
                 vencedor.get("titulo", "")[:62])
        log.info("      também em: %s", ", ".join(outras[:8]) or "—")
        saida.append(vencedor)

    saida.sort(key=lambda x: x.get("data", ""), reverse=True)
    log.info("  dedup por história: %d → %d itens (%d colapsados)",
             n, len(saida), colapsados)
    return saida


def acervo_esta_velho(itens: list) -> bool:
    """True quando nada no acervo tem menos de 24h — o gatilho da
    manchete-dado. Item sem data legível é ignorado na conta."""
    agora = datetime.utcnow()
    for it in itens:
        try:
            dt = datetime.strptime(it.get("data", ""), "%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, TypeError):
            continue
        if (agora - dt) < timedelta(hours=24):
            return False
    return True


def gerar_manchete_dado(pld: dict, ear: dict, bandeira: dict) -> dict:
    """Manchete-dado: item sintético com os números do próprio Megagrid,
    usado como REDE DE SEGURANÇA (decisão de 01/08) — só entra quando o
    acervo inteiro passou de 24h. Em dia normal o hero é notícia real, e o
    PLD já aparece no ticker e na faixa "Mercado agora".

    Dedup por id `dado-YYYY-MM-DD`. Retorna {} se não houver dado."""
    hoje = agora_br().strftime("%Y-%m-%d")   # data do Brasil, não do UTC
    se = (pld or {}).get("submercados", {}).get("SE/CO", {}) or {}
    preco = se.get("preco") or 0
    variacao = se.get("variacao") or 0
    ear_pct = (ear or {}).get("ear_percentual")
    cor = (bandeira or {}).get("cor")
    band_label = _BANDEIRA_LABEL.get(cor, "")

    if preco and variacao:
        verbo = "sobe" if variacao > 0 else "cai"
        titulo = (f"PLD {verbo} {_pct(variacao)}% na semana e fecha a "
                  f"R$ {_brl(preco)} no Sudeste/CO")
    elif preco and ear_pct is not None:
        # variação zerada: a pauta vira o reservatório
        titulo = (f"Reservatórios do SIN em {_pct(ear_pct)}% e PLD estável a "
                  f"R$ {_brl(preco)} no Sudeste/CO")
    elif preco and band_label:
        titulo = (f"Bandeira {band_label} em vigor e PLD estável a "
                  f"R$ {_brl(preco)} no Sudeste/CO")
    elif ear_pct is not None and band_label:
        titulo = (f"Reservatórios do SIN em {_pct(ear_pct)}% com bandeira "
                  f"{band_label} em vigor")
    else:
        log.info("  manchete-dado: sem dado suficiente — pulando")
        return {}

    partes = []
    if preco:
        partes.append(f"PLD SE/CO a R$ {_brl(preco)}/MWh")
    if ear_pct is not None:
        partes.append(f"reservatórios em {_pct(ear_pct)}%")
    if band_label:
        partes.append(f"bandeira {band_label}")
    lead = (" · ".join(partes) + ". Leitura diária do Megagrid sobre os dados "
            "abertos de CCEE, ONS e ANEEL.")

    return {
        "id": f"dado-{hoje}",
        "titulo": titulo,
        "lead": lead,
        "fonte": "Megagrid Dados",
        "url": MANCHETE_DADO_URL,
        "imagem": IMAGENS_FALLBACK["mercado-livre"],
        "editoria": "mercado-livre",
        "data": now_iso(),
    }


def fetch_noticias(pld: dict = None, ear: dict = None, bandeira: dict = None) -> dict:
    log.info("RSS noticias...")
    existing = load_existing("noticias.json")
    existing_items = existing.get("itens", [])
    if not HAS_FEEDPARSER:
        log.warning("  feedparser nao instalado -- mantendo existente")
        return existing
    # Descarta seed data (URLs de dominio raiz sem path real) e a manchete-dado
    # já gravada — ela é regerada a cada run a partir dos números do dia.
    existing_real = [
        it for it in existing_items
        if it.get("url", "").count("/") > 3
        and not str(it.get("id", "")).startswith("dado-")
    ]
    # itens antigos são carregados como estão — limpa entidades já gravadas
    # e realinha o id ao slug da editoria (acervo anterior ao P1.6).
    for it in existing_real:
        it["titulo"] = _clean_text(it.get("titulo", ""))
        it["lead"] = _strip_fonte_suffix(_clean_text(it.get("lead", "")), it.get("fonte", ""))
        normaliza_id(it)
    # A guarda de slug vale também para o que já está gravado — sem isto o
    # item ruim sobrevive a todas as execuções seguintes (P1.13).
    limpos = []
    for it in existing_real:
        if _e_slug(it.get("titulo", "")):
            log.info("  acervo: slug recusado como título — %s: %r",
                     it.get("fonte", "?"), it.get("titulo", ""))
            continue
        limpos.append(it)
    existing_real = limpos
    seen_urls = {item["url"] for item in existing_real}
    novos = []
    # Google News RSS (queries temáticas)
    for fonte, feed_url in RSS_FEEDS.items():
        items = _parse_feed(fonte, feed_url, seen_urls)
        novos.extend(items)
    # Feeds institucionais — fonte = nome do órgão. Os RSS diretos saíram no
    # P1.6 (mortos na origem); resta o espelho, com filtro rigoroso.
    for orgao, removido in FEEDS_OFICIAIS_REMOVIDOS.items():
        log.info("  RSS direto de %s removido no P1.6 — %s", orgao, removido[1])
    for orgao, feeds in RSS_FEEDS_OFICIAIS.items():
        items = _parse_feed(orgao, feeds["espelho"], seen_urls,
                            max_per_feed=ESPELHO_MAX_POR_ORGAO,
                            forcar_fonte=True, espelho=True)
        novos.extend(items)
        log.info("  %s (espelho): %d itens aprovados", orgao, len(items))
        for it in items:
            log.info("      · %s | %s", it["data"][:10], it["titulo"][:64])
    todos = novos + existing_real
    todos.sort(key=lambda x: x.get("data", ""), reverse=True)
    # Dedup por história: a mesma pauta de N veículos vira 1 item (P1.6)
    todos = agrupar_por_historia(todos)
    # Manchete-dado: rede de segurança, não rotina — só quando o acervo
    # inteiro (já com os feeds de hoje) passou de 24h.
    if acervo_esta_velho(todos):
        dado = gerar_manchete_dado(pld or {}, ear or {}, bandeira or {})
        if dado:
            todos = [dado] + [it for it in todos if it.get("id") != dado["id"]]
            log.info("  manchete-dado ATIVADA (acervo > 24h): %s", dado["titulo"])
    else:
        log.info("  manchete-dado dispensada — há notícia com menos de 24h")
    todos = todos[:60]
    # Fotos só depois do corte e na ordem final de exibição — o desempate
    # anti-repetição depende de quem fica adjacente a quem.
    atribuir_imagens(todos)
    data = {
        "updated": now_iso(),
        "total": len(todos),
        "itens": todos,
    }
    save("noticias.json", data)
    log.info("  %d novas . %d reais existentes . %d total", len(novos), len(existing_real), len(todos))
    resumo_feeds()
    oficiais = [it for it in todos if _e_oficial(it)]
    log.info("  itens com URL fora do Google News: %d%s", len(oficiais),
             (" — " + ", ".join(sorted({it["fonte"] for it in oficiais}))[:70])
             if oficiais else "")
    return data

# ── + Lidas (GoatCounter ou fallback por recência) ──────────────────

GOATCOUNTER_API  = os.environ.get("GOATCOUNTER_API", "")
GOATCOUNTER_SITE = os.environ.get("GOATCOUNTER_SITE", "megagrid")

# REGRA — ANALYTICS É ACESSÓRIO, DADO É PRODUTO (18/08/2026)
# PLD, EAR, carga, bandeira e notícias são o produto; audiência é enfeite.
# Falha no GoatCounter — ou em qualquer analytics que venha depois — NUNCA
# derruba o robô de dados essenciais. Todo caminho de analytics vive dentro de
# try/except, degrada para o ranking por recência e registra o motivo em
# log.warning. Silêncio também é proibido: cair no fallback sem dizer por quê
# esconde uma integração quebrada por semanas.

def _mais_lidas(noticias: dict) -> dict:
    items = noticias.get("itens", [])
    # Só entra no ranking quem tem os dois campos que o site renderiza.
    validos = [n for n in items if n.get("titulo") and n.get("url")]

    if GOATCOUNTER_API and GOATCOUNTER_SITE:
        try:
            r = requests.get(
                f"https://{GOATCOUNTER_SITE}.goatcounter.com/api/v0/stats/hits",
                headers={"Authorization": f"Bearer {GOATCOUNTER_API}", **HEADERS},
                timeout=12,
            )
            if not r.ok:
                # 401/403 de token errado, 5xx do provedor, página de erro em
                # HTML: o motivo sai do status e do corpo cru, nunca de um
                # .json() que quebraria em resposta não-JSON.
                log.warning("  GoatCounter HTTP %s (%s) — caindo para recência",
                            r.status_code, r.text[:120])
            else:
                # Conta nova tem "hits" vazio ou paths que ainda não casam com
                # nenhuma URL do acervo — cenário normal nos primeiros dias,
                # tratado como fallback e não como erro.
                hits = sorted((r.json().get("hits") or []),
                              key=lambda h: h.get("count") or 0, reverse=True)
                lidas = []
                for hit in hits:
                    if len(lidas) >= 5:
                        break
                    path = hit.get("path") or ""
                    if not path:
                        continue
                    noticia = next((n for n in validos if path in n["url"]), None)
                    if noticia:
                        # rank vem do tamanho da lista, não do índice do hit:
                        # hit que não casa não pode abrir buraco na numeração.
                        lidas.append({"rank": len(lidas) + 1,
                                      "titulo": noticia["titulo"],
                                      "url": noticia["url"]})
                if lidas:
                    data = {"updated": now_iso(), "itens": lidas}
                    save("mais-lidas.json", data)
                    log.info("  Ranking por audiência (GoatCounter): %d itens",
                             len(lidas))
                    return data
                log.warning("  GoatCounter respondeu, mas nenhum de %d paths "
                            "casou com o acervo — caindo para recência", len(hits))
        except Exception as exc:
            log.warning("  GoatCounter falhou (%s: %s) — caindo para recência",
                        type(exc).__name__, exc)

    # Fallback: top 5 mais recentes
    lidas = [
        {"rank": i + 1, "titulo": n["titulo"], "url": n["url"]}
        for i, n in enumerate(validos[:5])
    ]
    data = {"updated": now_iso(), "fallback": True, "itens": lidas}
    save("mais-lidas.json", data)
    log.info("  Ranking por recência (sem GoatCounter)")
    return data


def fetch_mais_lidas(noticias: dict) -> dict:
    log.info("+ Lidas…")
    try:
        return _mais_lidas(noticias)
    except Exception as exc:
        # Rede de segurança final da REGRA acima: nem o fallback nem a gravação
        # em disco podem matar o run. Mantém o mais-lidas.json anterior.
        log.warning("  + Lidas falhou por completo (%s: %s) — mantendo o "
                    "arquivo anterior", type(exc).__name__, exc)
        return load_existing("mais-lidas.json")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    log.info("═══ MEGAGRID DataBot ═══")
    t0 = time.time()

    pld       = fetch_pld()
    ear       = fetch_reservatorios()
    carga     = fetch_carga()
    bandeira  = fetch_bandeira()
    termo     = calc_termometro(pld, ear, carga, bandeira)
    noticias  = fetch_noticias(pld, ear, bandeira)
    fetch_mais_lidas(noticias)

    elapsed = round(time.time() - t0, 1)
    log.info("═══ Concluído em %.1fs ═══", elapsed)
    log.info(
        "  PLD SE/CO: R$ %.2f | EAR: %.1f%% | Bandeira: %s | Termômetro: %d/100 | Notícias: %d",
        pld.get("submercados", {}).get("SE/CO", {}).get("preco", 0),
        ear.get("ear_percentual", 0),
        bandeira.get("cor", "—"),
        termo.get("score", 0),
        noticias.get("total", 0),
    )


if __name__ == "__main__":
    main()
