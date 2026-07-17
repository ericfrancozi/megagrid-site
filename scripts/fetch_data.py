#!/usr/bin/env python3
"""
MEGAGRID — Robô de dados v1
Executa via GitHub Actions (cron diário 09:00 UTC = 06:00 BRT)
Fontes: CCEE CKAN · ONS CKAN/S3 · ANEEL · RSS feeds
Saída:  site/data/*.json
"""

import csv
import io
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

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
}
# Feeds institucionais diretos como fallback secundário
RSS_FEEDS_FALLBACK = {
    "CCEE": "https://www.ccee.org.br/rss/pautas-e-destaques.xml",
    "ANEEL": "https://www.aneel.gov.br/rss.xml",
    "MME": "https://www.gov.br/mme/pt-br/assuntos/noticias/RSS",
}

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
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_editoria(text: str) -> str:
    t = text.lower()
    scores = {
        ed: sum(1 for kw in kws if kw in t)
        for ed, kws in EDITORIA_RULES.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "mercado-livre"


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

# Resource verificado em 2026-07: dataset "bandeiras-tarifarias",
# recurso "Bandeira Tarifária - Acionamento" (datastore ativo).
ANEEL_BANDEIRA_RES = "0591b8f6-fe54-437b-b72b-1aa2efd46e42"

_MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
             "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def fetch_bandeira() -> dict:
    log.info("ANEEL bandeira tarifária…")
    existing = load_existing("bandeira.json")

    r = get(f"{ANEEL_API}/datastore_search", {
        "resource_id": ANEEL_BANDEIRA_RES,
        "limit": 3,
        "sort": "_id desc",
    })
    if r:
        try:
            records = r.json()["result"]["records"]
            rec = records[0]
            raw = str(rec.get("NomBandeiraAcionada", "")).lower()
            if "escassez" in raw:
                cor_key = "escassez"
            elif "vermelha" in raw:
                cor_key = "vermelha2" if "2" in raw else "vermelha1"
            elif "verde" in raw:
                cor_key = "verde"
            else:
                cor_key = "amarela"

            # VlrAdicionalBandeira vem em R$/MWh com vírgula (ex.: "18,85")
            adicional = BANDEIRA_META[cor_key]["adicional"]
            try:
                adicional = round(
                    float(str(rec.get("VlrAdicionalBandeira", "")).replace(".", "").replace(",", ".")) / 1000,
                    5,
                )
            except (ValueError, TypeError):
                pass

            comp = str(rec.get("DatCompetencia", ""))[:7]  # YYYY-MM
            try:
                y, m = comp.split("-")
                mes_ref = f"{_MESES_PT[int(m)-1]}/{y}"
            except Exception:
                mes_ref = datetime.utcnow().strftime("%m/%Y")

            data = {
                "updated": now_iso(),
                "mes": mes_ref,
                "fonte": "ANEEL — Dados Abertos",
                "cor": cor_key,
                "adicional_kwh": adicional,
                "descricao": BANDEIRA_META[cor_key]["descricao"],
            }
            save("bandeira.json", data)
            log.info("  Bandeira %s: %s (R$ %.5f/kWh)", mes_ref, cor_key, adicional)
            return data
        except Exception as exc:
            log.warning("  Bandeira parse falhou: %s", exc)

    log.warning("  Bandeira fetch falhou — mantendo existente")
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
        latest_pld = hist[-1].get("SE_CO", 200)
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

def _parse_feed(fonte, feed_url, seen_urls, max_per_feed=10):
    """Parseia um feed RSS e retorna lista de itens novos."""
    novos = []
    try:
        feed = feedparser.parse(feed_url)
        entries = feed.entries or []
        log.info("  %s: %d entradas", fonte, len(entries))
        for entry in entries[:max_per_feed]:
            url = entry.get("link", "")
            if not url or url in seen_urls:
                continue
            titulo = entry.get("title", "").strip()
            titulo = re.sub(r"\s+-\s+[\w\s]+$", "", titulo).strip()
            if not titulo or len(titulo) < 10:
                continue
            lead = entry.get("summary", "") or entry.get("description", "")
            lead = re.sub(r"<[^>]+>", "", lead).strip()[:300]
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
            data_pub = datetime(*pub[:6]).strftime("%Y-%m-%dT%H:%M:%SZ") if pub else now_iso()
            fonte_display = fonte
            if "news.google.com" in feed_url:
                src = entry.get("source", {}).get("title", "")
                if src:
                    fonte_display = src
            novos.append({
                "id": f"{fonte.lower().replace(' ','_')}_{abs(hash(url)) % 100000}",
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
        log.warning("  Erro %s: %s", fonte, exc)
    return novos


def fetch_noticias() -> dict:
    log.info("RSS noticias...")
    existing = load_existing("noticias.json")
    existing_items = existing.get("itens", [])
    if not HAS_FEEDPARSER:
        log.warning("  feedparser nao instalado -- mantendo existente")
        return existing
    # Descarta seed data (URLs de dominio raiz sem path real)
    existing_real = [
        it for it in existing_items
        if it.get("url", "").count("/") > 3
    ]
    seen_urls = {item["url"] for item in existing_real}
    novos = []
    # 1a tentativa: Google News RSS
    for fonte, feed_url in RSS_FEEDS.items():
        items = _parse_feed(fonte, feed_url, seen_urls)
        novos.extend(items)
    # 2a tentativa: feeds diretos (se Google News falhou)
    if not novos:
        log.info("  Google News sem itens -- tentando feeds diretos...")
        for fonte, feed_url in RSS_FEEDS_FALLBACK.items():
            items = _parse_feed(fonte, feed_url, seen_urls)
            novos.extend(items)
    todos = novos + existing_real
    todos.sort(key=lambda x: x.get("data", ""), reverse=True)
    todos = todos[:60]
    data = {
        "updated": now_iso(),
        "total": len(todos),
        "itens": todos,
    }
    save("noticias.json", data)
    log.info("  %d novas . %d reais existentes . %d total", len(novos), len(existing_real), len(todos))
    return data

# ── + Lidas (GoatCounter ou fallback por recência) ──────────────────

GOATCOUNTER_API  = os.environ.get("GOATCOUNTER_API", "")
GOATCOUNTER_SITE = os.environ.get("GOATCOUNTER_SITE", "megagrid")

def fetch_mais_lidas(noticias: dict) -> dict:
    log.info("+ Lidas…")
    items = noticias.get("itens", [])

    if GOATCOUNTER_API and GOATCOUNTER_SITE:
        try:
            r = requests.get(
                f"https://{GOATCOUNTER_SITE}.goatcounter.com/api/v0/stats/hits",
                headers={"Authorization": f"Bearer {GOATCOUNTER_API}", **HEADERS},
                timeout=12,
            )
            if r.ok:
                hits = sorted(r.json().get("hits", []), key=lambda h: h.get("count", 0), reverse=True)
                lidas = []
                for i, hit in enumerate(hits[:5], 1):
                    path = hit["path"]
                    noticia = next((n for n in items if path in n.get("url", "")), None)
                    if noticia:
                        lidas.append({"rank": i, "titulo": noticia["titulo"], "url": noticia["url"]})
                if lidas:
                    data = {"updated": now_iso(), "itens": lidas}
                    save("mais-lidas.json", data)
                    return data
        except Exception as exc:
            log.warning("  GoatCounter falhou: %s", exc)

    # Fallback: top 5 mais recentes
    lidas = [
        {"rank": i + 1, "titulo": n["titulo"], "url": n["url"]}
        for i, n in enumerate(items[:5])
    ]
    data = {"updated": now_iso(), "fallback": True, "itens": lidas}
    save("mais-lidas.json", data)
    log.info("  Ranking por recência (sem GoatCounter)")
    return data


# ── Main ─────────────────────────────────────────────────────────────

def main():
    log.info("═══ MEGAGRID DataBot ═══")
    t0 = time.time()

    pld       = fetch_pld()
    ear       = fetch_reservatorios()
    carga     = fetch_carga()
    bandeira  = fetch_bandeira()
    termo     = calc_termometro(pld, ear, carga, bandeira)
    noticias  = fetch_noticias()
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
