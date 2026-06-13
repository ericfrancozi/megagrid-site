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

HEADERS = {
    "User-Agent": (
        "Megagrid-DataBot/1.0 "
        "(github.com/megagrid-br; contato@megagrid.com.br)"
    ),
    "Accept": "application/json",
}

RSS_FEEDS = {
    "CCEE": "https://www.ccee.org.br/rss/pautas-e-destaques.xml",
    "ANEEL": "https://www.aneel.gov.br/rss.xml",
    "ONS": "https://www.ons.org.br/rss.aspx",
    "MME": "https://www.gov.br/mme/pt-br/assuntos/noticias/RSS",
    "EPE": "https://www.epe.gov.br/pt/rss",
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

# ── Helpers ─────────────────────────────────────────────────────────

def get(url, params=None, timeout=25):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as exc:
        log.warning("GET falhou: %s → %s", url, exc)
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

def fetch_pld() -> dict:
    log.info("CCEE PLD semanal…")
    existing = load_existing("pld.json")
    year = str(datetime.utcnow().year)
    res_id = CCEE_PLD_SEMANAL.get(year, CCEE_PLD_SEMANAL["2026"])

    r = get(f"{CCEE_API}/datastore_search", {
        "resource_id": res_id,
        "limit": 300,
        "sort": "_id asc",
    })
    if not r:
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

def fetch_reservatorios() -> dict:
    log.info("ONS reservatórios (EAR)…")
    existing = load_existing("reservatorios.json")
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Tenta CKAN ONS
    for res_id in [
        "7d475b7a-2a0b-4a6a-a22e-2834a61c5b73",
        "ear_diario_subsistema",
        "ear-subsistema-diario",
    ]:
        r = get(f"{ONS_API}/datastore_search", {
            "resource_id": res_id,
            "limit": 10,
            "sort": "dat_referencia desc",
        })
        if r and r.json().get("success"):
            records = r.json()["result"].get("records", [])
            if records:
                sub_ear: dict = {}
                for rec in records:
                    sub = rec.get("nom_subsistema", rec.get("SUBSISTEMA", ""))
                    pct_key = next(
                        (k for k in rec if "percentual" in k.lower() and "ear" in k.lower()), None
                    )
                    if pct_key and sub:
                        try:
                            sub_ear[sub] = round(float(rec[pct_key]), 1)
                        except (ValueError, TypeError):
                            pass
                if sub_ear:
                    avg = round(sum(sub_ear.values()) / len(sub_ear), 1)
                    data = {
                        "updated": now_iso(),
                        "data_ref": records[0].get("dat_referencia", today),
                        "fonte": "ONS — Dados Abertos (dados.ons.org.br)",
                        "ear_percentual": avg,
                        "subsistemas": sub_ear,
                    }
                    save("reservatorios.json", data)
                    log.info("  EAR: %.1f%%", avg)
                    return data

    # Tenta CSV no S3 da ONS
    year = datetime.utcnow().year
    for fname in [f"ear_subsistema_{year}.csv", f"EAR_DiarioSubsistema_{year}.csv"]:
        r = get(f"{ONS_S3}/dataset/ear_subsistema/{fname}")
        if r:
            try:
                reader = csv.DictReader(io.StringIO(r.text))
                rows = list(reader)
                if rows:
                    date_key = next((k for k in rows[0] if "data" in k.lower() or "dat" in k.lower()), None)
                    if date_key:
                        rows.sort(key=lambda x: x.get(date_key, ""), reverse=True)
                        latest_date = rows[0][date_key]
                        latest_rows = [rw for rw in rows if rw[date_key] == latest_date]
                        sub_ear = {}
                        for rw in latest_rows:
                            sub = rw.get("nom_subsistema", rw.get("Subsistema", ""))
                            pct_key = next(
                                (k for k in rw if "percentual" in k.lower() and "ear" in k.lower()), None
                            )
                            if pct_key and sub:
                                try:
                                    sub_ear[sub] = round(float(rw[pct_key].replace(",", ".")), 1)
                                except (ValueError, AttributeError):
                                    pass
                        if sub_ear:
                            avg = round(sum(sub_ear.values()) / len(sub_ear), 1)
                            data = {
                                "updated": now_iso(),
                                "data_ref": latest_date,
                                "fonte": "ONS — S3 opendata",
                                "ear_percentual": avg,
                                "subsistemas": sub_ear,
                            }
                            save("reservatorios.json", data)
                            return data
            except Exception as exc:
                log.warning("  CSV ONS: %s", exc)

    log.warning("  EAR fetch falhou — mantendo existente")
    return existing


# ── ONS — Carga do SIN ──────────────────────────────────────────────

def fetch_carga() -> dict:
    log.info("ONS carga verificada…")
    existing = load_existing("carga.json")

    for res_id in ["carga_energia_verificada", "carga-verificada-diario"]:
        r = get(f"{ONS_API}/datastore_search", {
            "resource_id": res_id,
            "limit": 5,
            "sort": "dat_referencia desc",
        })
        if r and r.json().get("success"):
            records = r.json()["result"].get("records", [])
            if records:
                rec = records[0]
                val_key = next(
                    (k for k in rec if "carga" in k.lower() and "mw" in k.lower()), None
                )
                if val_key:
                    try:
                        val = float(rec[val_key])
                        var = 0
                        if len(records) >= 2:
                            prev_val = float(records[1].get(val_key, val))
                            if prev_val:
                                var = round((val - prev_val) / prev_val * 100, 1)
                        data = {
                            "updated": now_iso(),
                            "data_ref": rec.get("dat_referencia", ""),
                            "fonte": "ONS — Dados Abertos",
                            "carga_mwmed": round(val),
                            "variacao": var,
                        }
                        save("carga.json", data)
                        log.info("  Carga: %.0f MWmed", val)
                        return data
                    except (ValueError, TypeError):
                        pass

    log.warning("  Carga fetch falhou — mantendo existente")
    return existing


# ── ANEEL — Bandeira Tarifária ──────────────────────────────────────

def fetch_bandeira() -> dict:
    log.info("ANEEL bandeira tarifária…")
    existing = load_existing("bandeira.json")

    for res_id in ["bandeiras-tarifarias", "bandeira_tarifaria"]:
        r = get(f"{ANEEL_API}/datastore_search", {
            "resource_id": res_id,
            "limit": 3,
            "sort": "dat_vigencia desc",
        })
        if r and r.json().get("success"):
            records = r.json()["result"].get("records", [])
            if records:
                rec = records[0]
                cor_raw = str(rec.get("dsc_bandeira", rec.get("cor", "amarela"))).lower()
                cor_key = next(
                    (k for k in BANDEIRA_META if k in cor_raw.replace(" ", "")),
                    "amarela"
                )
                mes_ref = rec.get("dat_vigencia", datetime.utcnow().strftime("%Y-%m"))
                data = {
                    "updated": now_iso(),
                    "mes": mes_ref,
                    "fonte": "ANEEL — Dados Abertos",
                    "cor": cor_key,
                    "adicional_kwh": BANDEIRA_META[cor_key]["adicional"],
                    "descricao": BANDEIRA_META[cor_key]["descricao"],
                }
                save("bandeira.json", data)
                log.info("  Bandeira: %s", cor_key)
                return data

    # Fallback: scrape da página pública ANEEL
    r = get("https://www.aneel.gov.br/bandeiras-tarifarias")
    if r:
        text = r.text.lower()
        for cor in ["escassez", "vermelha2", "vermelha 2", "vermelha1", "vermelha 1", "amarela", "verde"]:
            if cor.replace(" ", "") in text.replace(" ", ""):
                cor_key = cor.replace(" ", "")
                if cor_key not in BANDEIRA_META:
                    cor_key = "amarela"
                data = {
                    "updated": now_iso(),
                    "mes": datetime.utcnow().strftime("%B/%Y"),
                    "fonte": "ANEEL — bandeiras-tarifarias",
                    "cor": cor_key,
                    "adicional_kwh": BANDEIRA_META[cor_key]["adicional"],
                    "descricao": BANDEIRA_META[cor_key]["descricao"],
                }
                save("bandeira.json", data)
                log.info("  Bandeira (scrape): %s", cor_key)
                return data

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

def fetch_noticias() -> dict:
    log.info("RSS notícias…")
    existing = load_existing("noticias.json")
    existing_items = existing.get("itens", [])
    seen_urls = {item["url"] for item in existing_items}

    if not HAS_FEEDPARSER:
        log.warning("  feedparser não instalado — mantendo existente")
        return existing

    novos = []
    for fonte, feed_url in RSS_FEEDS.items():
        log.info("  %s: %s", fonte, feed_url)
        try:
            feed = feedparser.parse(feed_url)
            for entry in (feed.entries or [])[:12]:
                url = entry.get("link", "")
                if not url or url in seen_urls:
                    continue
                titulo = entry.get("title", "").strip()
                if not titulo:
                    continue

                # Lead / summary — remove tags HTML
                lead = entry.get("summary", "") or entry.get("description", "")
                lead = re.sub(r"<[^>]+>", "", lead).strip()[:300]

                # Imagem
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
                if pub:
                    data_pub = datetime(*pub[:6]).strftime("%Y-%m-%dT%H:%M:%SZ")
                else:
                    data_pub = now_iso()

                novos.append({
                    "id": f"{fonte.lower()}_{abs(hash(url)) % 100000}",
                    "titulo": titulo,
                    "lead": lead,
                    "fonte": fonte,
                    "url": url,
                    "imagem": imagem,
                    "editoria": editoria,
                    "data": data_pub,
                })
                seen_urls.add(url)
        except Exception as exc:
            log.warning("  Erro %s: %s", fonte, exc)

    todos = novos + existing_items
    todos.sort(key=lambda x: x.get("data", ""), reverse=True)
    todos = todos[:60]

    data = {
        "updated": now_iso(),
        "total": len(todos),
        "itens": todos,
    }
    save("noticias.json", data)
    log.info("  %d novas · %d total", len(novos), len(todos))
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
