#!/usr/bin/env python3
"""
MEGAGRID — Sentinela de frescor dos dados
Roda no GitHub Actions APÓS o commit do robô. Se alguma fonte estiver
parada além do limite, emite annotation ::error:: e sai com código 1 —
deixando o workflow VERMELHO (falha visível, em vez de erro silencioso).

Limites por arquivo (dias desde `updated`):
  noticias.json        2   (robô diário; Google News)
  mais-lidas.json      8   (semanal por cliques)
  termometro.json      2   (recalculado todo run)
  pld.json            10   (CCEE publica semanalmente)
  reservatorios.json   4   (ONS diário, com folga p/ atraso de publicação)
  carga.json           4   (ONS diário)
  bandeira.json       40   (ANEEL mensal)
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "site" / "data"

LIMITES_DIAS = {
    "noticias.json": 2,
    "mais-lidas.json": 8,
    "termometro.json": 2,
    "pld.json": 10,
    "reservatorios.json": 4,
    "carga.json": 4,
    "bandeira.json": 40,
}


def idade_dias(iso: str) -> float:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400


def main() -> int:
    falhas, avisos = [], []
    for nome, limite in LIMITES_DIAS.items():
        p = DATA_DIR / nome
        try:
            updated = json.loads(p.read_text("utf-8")).get("updated")
            idade = idade_dias(updated)
        except Exception as exc:
            falhas.append(f"{nome}: ilegível ({exc})")
            continue
        status = f"{nome}: {idade:.1f}d (limite {limite}d)"
        if idade > limite:
            falhas.append(status)
        elif idade > limite * 0.7:
            avisos.append(status)
        print(("STALE  " if idade > limite else "ok     ") + status)

    for a in avisos:
        print(f"::warning title=Fonte perto do limite::{a}")
    if falhas:
        for f in falhas:
            print(f"::error title=Fonte de dados PARADA::{f}")
        print(f"\n{len(falhas)} fonte(s) parada(s) — verifique o log do fetch acima.")
        return 1
    print("\nTodas as fontes dentro do limite de frescor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
