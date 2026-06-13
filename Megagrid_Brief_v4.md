# MEGAGRID — Brief v4
*12/06/2026 · substitui o v3 · mudanças: malha de espaços publicitários + bloco "+ Lidas" (visual v0.4 aprovado pelo Eric: "ficou um tesão")*

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
4. **"+ Lidas da semana"** — widget lateral numerado (1–5). Implementação v1: contagem de cliques via analytics gratuito com API (ex.: GoatCounter); robô diário consome o ranking. Enquanto não houver volume, fallback automático por recência/destaque.
5. **4 calculadoras**: Migração cativo→livre · Precificação de contrato · Custo total do MWh · Conta de luz reversa. 100% no navegador.
6. **Entenda o mercado** — linha do tempo 1995→2028 + glossário.
7. **Newsletter** — só captura (double opt-in) na v1.

## 5. Monetização — malha de espaços (NOVO no v4)
| Posição | Formato | Observação |
|---|---|---|
| Pós-hero | Leaderboard 970×120 | primeiro espaço visto por todo visitante |
| Entre Preços e Radar | Banner 970×250 | meio de página, alto engajamento |
| Lateral do Radar (sticky) | Retângulo 300×250 | acompanha a leitura, abaixo do "+ Lidas" |
| Pré-rodapé | Bloco "Anuncie aqui" | pitch comercial → mídia kit (v2) |

v1: slots renderizados e prontos para AdSense ou patrocínio direto (troca de imagem+link via 1 arquivo JSON). Mídia kit PDF na v2.

## 6. Navegação / arquitetura de informação
- **Menu lateral** (hambúrguer): Início · Últimas do Radar · Preços & PLD · Termômetro · **Editorias** (Mercado Livre, Regulação, Política Energética, Empresas, Transição & Novos Mercados, Tarifas & Bandeiras) · **Calculadoras** (4) · Entenda o mercado · Glossário · Metodologia · Fontes · Anuncie · Privacidade.
- Editorias = filtros do Radar na v1 (chips + menu); páginas próprias na v2 (SEO).
- **Ticker = fita de pregão** com rolagem contínua (PLD 4 submercados, bandeira, reservatórios, carga, termômetro); pausa no hover; respeita `prefers-reduced-motion`.
- **Radar em 2 colunas** (desktop): notícias à esquerda; coluna lateral sticky com "+ Lidas" + retângulo publicitário (padrão MegaWhat/fisconaweb).

## 7. Identidade visual (aprovada em 12/06/2026)
- **Cabeçalho BRANCO** com hambúrguer, navegação e CTA azul.
- **Logo:** símbolo de pulso de energia em gradiente + **MEGA** em gradiente iridescente (Valspar: ciano→azul→violeta→magenta→laranja) + **GRID** em navy #0A1426.
- **Escuro só em:** ticker e rodapé. **Gradiente restrito à marca** (logo + filete 3px do rodapé).
- **Acento único de UI:** azul #1456D6. Corpo claro e fotográfico (hero + thumbnails 16:9; foto do feed RSS ou banco temático Unsplash).

## 8. Arquitetura técnica
Site estático + robô diário (GitHub Actions) lendo CKAN CCEE/ONS/ANEEL + RSS oficiais + ranking de cliques → grava JSON → site lê. Classificação de editoria por regras. Hospedagem gratuita (Cloudflare Pages/Vercel) em subdomínio; domínio depois. Manutenção ~zero. Complexidade: média.

## 9. Fontes de dados validadas (12/06/2026)
CCEE dados abertos (PLD semanal/horário, migração) ✔ · ONS dados abertos (EAR/ENA, carga, CMO) ✔ · ANEEL (tarifas, bandeiras — validar no build) · RSS oficiais (validar no build) · GoatCounter ou similar para "+ Lidas" (validar no build).

## 10. Restrições permanentes
- **Nenhum conteúdo, case ou referência ligada à DACAR.**
- Tom direto, sem juridiquês; aviso legal padrão; sempre citar e linkar a fonte oficial.

## 11. Roadmap v2 (não fazer agora)
Envio automático da newsletter · mídia kit PDF · páginas por editoria e por estado/distribuidora (SEO programático) · resumos por IA · comparador de comercializadoras · meteorologia INMET no termômetro.

## 12. Estado atual do projeto
- ✔ Discovery e plano aprovados (12/06/2026)
- ✔ Fontes CCEE/ONS validadas via API
- ✔ Mockups v0.1 → v0.2 → v0.3 iterados com feedback do Eric
- ✔ **v0.3 aprovado com elogio**; v0.4 entregue somando malha de ads (4 posições) + "+ Lidas" em coluna lateral sticky
- ⏭ Próximo: **Fase 3** — robô de dados reais (CCEE/ONS/ANEEL + RSS + ranking de cliques), 4 calculadoras completas, captura de e-mail, publicação em subdomínio gratuito
