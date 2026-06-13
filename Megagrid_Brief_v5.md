# MEGAGRID — Brief v5
*13/06/2026 · substitui o v4 · mudanças: layout InfoMoney (notícias > ferramentas) + ticker em velocidade de pregão*

## 1. O produto
Portal gratuito sobre o **mercado livre de energia** no Brasil — preços, tendência, notícias e simuladores — alimentado por dados abertos oficiais (CCEE, ONS, ANEEL), com automação máxima e manutenção mínima. Modelo editorial: MegaWhat. Modelo de produto: fisconaweb (ferramentas + dados + tráfego → ads/patrocínio). Escopo: **100% energia** (mercado livre como núcleo + novos mercados: EVs/carregadores, baterias, GD, data centers).

## 2. Estado do tema
- **Passado:** mercado livre nasce em 1995 (Lei 9.074), restrito a grandes consumidores. Jan/2024: todo o Grupo A pode migrar — >35% do consumo nacional.
- **Atual (jun/2026):** Lei 15.269/2025 aprovada — cria o SUI e define a abertura total. Pauta quente: preço horário/CVaR, baterias, curtailment, data centers, GD saturando redes.
- **Tendência:** abertura BT comercial/industrial até **dez/2027**, residencial até **dez/2028** → público salta de milhares para milhões.

## 3. Público e proposta de valor
Stakeholder já no mercado livre ou interessado. Encontra: atualização rápida, base para decisão, amparo para escolhas, simulações fáceis, passado → presente → tendência. Sentimento-alvo (nunca dito): "aqui eu entendo e me atualizo sem tecniquês".

## 4. Escopo da v1
1. **Painel de preços** — PLD horário e semanal por submercado (CCEE).
2. **Termômetro do MWh** — índice 0–100 diário (EAR 35% · ENA 25% · momentum PLD/CMO 20% · carga 10% · bandeira 10%), metodologia pública.
3. **Radar de notícias com editorias** — agregado automático (MME, ANEEL, ONS, CCEE, EPE), imagem, fonte, link, classificação por editoria.
4. **"+ Lidas da semana"** — widget lateral numerado (1–5). Implementação v1: contagem de cliques via analytics gratuito (GoatCounter); fallback por recência enquanto volume for baixo.
5. **4 calculadoras**: Migração cativo→livre · Precificação de contrato · Custo total do MWh · Conta de luz reversa. 100% no navegador.
6. **Entenda o mercado** — linha do tempo 1995→2028 + glossário.
7. **Newsletter** — só captura (double opt-in) na v1.

## 5. Monetização — malha de espaços (mantida do v4)
| Posição | Formato | Observação |
|---|---|---|
| Pós-hero | Leaderboard 970×120 | primeiro espaço visto por todo visitante |
| Entre editorias | Banner 970×250 | meio de página, alto engajamento |
| Lateral (sticky) | Retângulo 300×250 | acompanha a leitura, abaixo do "+ Lidas" |
| Pré-rodapé | Bloco "Anuncie aqui" | pitch comercial → mídia kit (v2) |

v1: slots renderizados e prontos para AdSense ou patrocínio direto.

## 6. Hierarquia de conteúdo — REVISADA no v5 (layout InfoMoney)
**Decisão do Eric (13/06/2026):** notícias são mais relevantes que ferramentas. Layout reordenado para priorizar editorial, empurrando calculadoras para baixo.

### Ordem das seções no scroll (v0.5):
1. **Header** — branco, hambúrguer, ticker de pregão, logo, CTA
2. **Ticker** — fita contínua (PLD, bandeiras, reservatórios, carga, termômetro)
3. **Ad leaderboard 970×120** — logo após o ticker (máxima visibilidade)
4. **Manchetes** — grid 3 colunas:
   - Col. esquerda: manchete principal com título, lead, links relacionados
   - Col. centro: card visual com foto (overlay gradiente) + badge de editoria
   - Col. direita: Tempo Real (últimas 5 notícias com links) + "+ Lidas da semana" (1–5)
5. **Faixa de mercado** — grid 3 colunas:
   - PLD: gráfico de área com histórico do submercado Sudeste/CO
   - Cotações: tabela 7 linhas (SE/CO · S · NE · N · Bandeira · Reservatórios · Carga)
   - Termômetro do MWh: gauge semicircular com índice 0–100 + legenda
6. **Editoria 1 — Mercado Livre** — 4 cards de notícia em grid
7. **Ad banner 970×250**
8. **Editoria 2 — Regulação & Política Energética** — 4 cards de notícia em grid
9. **Editoria 3 — Transição & Novos Mercados** — 4 cards de notícia em grid
10. **Calculadoras** — 4 cards + simulador demo (empurradas para baixo, ferramentas secundárias)
11. **Timeline "Entenda o mercado"** — 1995→2028
12. **Newsletter** — captura de e-mail
13. **Ad "Anuncie aqui"** — bloco pré-rodapé
14. **Footer** — navy com ribbon gradiente

## 7. Ticker — REVISADO no v5
- **Velocidade:** `animation: roll 110s linear infinite` — cadência lenta estilo InfoMoney (era 38s no v0.4)
- Loop infinito: JS duplica o `innerHTML` do tape → animação CSS translada -50% sem costura
- Pausa no hover via `animation-play-state: paused`
- Respeita `prefers-reduced-motion`

## 8. Navegação / arquitetura de informação
- **Menu lateral** (hambúrguer): Início · Últimas do Radar · Preços & PLD · Termômetro · **Editorias** (Mercado Livre, Regulação, Política Energética, Empresas, Transição & Novos Mercados, Tarifas & Bandeiras) · **Calculadoras** (4) · Entenda o mercado · Glossário · Metodologia · Fontes · Anuncie · Privacidade.
- Editorias = filtros do Radar na v1 (chips + menu); páginas próprias na v2 (SEO).

## 9. Identidade visual (aprovada em 12/06/2026, sem alterações no v5)
- **Cabeçalho BRANCO** com hambúrguer, navegação e CTA azul.
- **Logo:** símbolo de pulso em gradiente + **MEGA** em gradiente iridescente (Valspar: ciano→azul→violeta→magenta→laranja) + **GRID** em navy #0A1426.
- **Escuro só em:** ticker e rodapé. **Gradiente restrito à marca** (logo + filete 3px do rodapé).
- **Acento único de UI:** azul #1456D6. Corpo claro e fotográfico (hero + thumbnails 16:9).

## 10. Arquitetura técnica
Site estático + robô diário (GitHub Actions) lendo CKAN CCEE/ONS/ANEEL + RSS oficiais + ranking de cliques → grava JSON → site lê. Hospedagem gratuita (Cloudflare Pages/Vercel) em subdomínio; domínio depois. Manutenção ~zero.

## 11. Fontes de dados validadas
CCEE dados abertos (PLD semanal/horário) ✔ · ONS dados abertos (EAR/ENA, carga, CMO) ✔ · ANEEL (tarifas, bandeiras — validar no build) · RSS oficiais (validar no build) · GoatCounter para "+ Lidas" (validar no build).

## 12. Restrições permanentes
- **Nenhum conteúdo, case ou referência ligada à DACAR.**
- Tom direto, sem juridiquês; aviso legal padrão; sempre citar e linkar a fonte oficial.

## 13. Roadmap v2 (não fazer agora)
Envio automático da newsletter · mídia kit PDF · páginas por editoria e por estado/distribuidora (SEO programático) · resumos por IA · comparador de comercializadoras · meteorologia INMET no termômetro.

## 14. Estado atual do projeto
- ✔ Discovery e plano aprovados (12/06/2026)
- ✔ Fontes CCEE/ONS validadas via API
- ✔ Mockups v0.1 → v0.2 → v0.3 → v0.4 iterados com feedback do Eric
- ✔ **v0.4 aprovado com elogio** ("ficou um tesão")
- ✔ **v0.5 entregue (13/06/2026)** — layout InfoMoney (notícias > ferramentas) + ticker 110s
- ⏭ Próximo: **Fase 3** — robô de dados reais (CCEE/ONS/ANEEL + RSS + ranking de cliques), 4 calculadoras completas, captura de e-mail, publicação em subdomínio gratuito
