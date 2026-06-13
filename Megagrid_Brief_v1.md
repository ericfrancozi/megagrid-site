# MEGAGRID — Brief v1
*12/06/2026 · Fase 1 (Discovery) e Fase 2 (Planejamento) concluídas*

## 1. O produto
Portal gratuito sobre o **mercado livre de energia** no Brasil — preços, tendência, notícias e simuladores — alimentado por dados abertos oficiais (CCEE, ONS, ANEEL), com automação máxima e manutenção mínima. Modelo editorial: MegaWhat. Modelo de produto: fisconaweb (ferramentas + dados compilados + tráfego → receita de ads/patrocínio). Escopo confirmado com Eric: **100% energia** (mercado livre como núcleo + novos mercados: carregadores de veículos elétricos, baterias, GD). A menção à reforma tributária no prompt era herança do projeto anterior.

## 2. Estado do tema (o porquê do timing)
- **Passado:** mercado livre nasce em 1995 (Lei 9.074); por décadas restrito a grandes consumidores. Jan/2024: todo o Grupo A (alta/média tensão) pôde migrar — mercado saltou para ~40 mil consumidores e >35% do consumo nacional.
- **Atual (jun/2026):** Lei 15.269/2025 (conversão da MP 1.304) aprovada — maior reforma desde a criação do mercado. Cria o Supridor de Última Instância (SUI) e define a abertura total. Pauta quente: preço horário/CVaR, baterias, curtailment de eólicas/solares, data centers pedindo conexão, GD saturando redes.
- **Tendência:** abertura para baixa tensão comercial/industrial até **dez/2027** e residencial até **dez/2028** → o público potencial do tema sai de dezenas de milhares para dezenas de milhões. Janela ideal para construir audiência AGORA e estar posicionado quando a massa chegar.

## 3. Público e proposta de valor
Stakeholder já no mercado livre ou interessado (gestor, comercializadora, consumidor migrando, imprensa, curioso). Ele encontra: (1) atualização rápida, (2) base para decisão, (3) amparo para escolhas, (4) simulações fáceis, (5) passado → presente → tendência. Sentimento-alvo: "aqui eu entendo e me atualizo sem juridiquês/tecniquês" — nunca dito explicitamente.

## 4. Escopo da v1 (decidido no discovery de 12/06/2026)
1. **Painel de preços** — PLD horário e semanal por submercado, histórico e sparklines (CCEE dados abertos).
2. **Termômetro do MWh** — índice 0–100 de pressão de custo, recalculado diariamente. Insumos: EAR/ENA (reservatórios, ONS), momentum de PLD/CMO, carga verificada vs. ano anterior, bandeira tarifária (ANEEL). Metodologia pública e declarada na página.
3. **Radar de notícias** — agregado automático de fontes oficiais/setoriais (MME, ANEEL, ONS, CCEE, EPE) com título, fonte e link. Sem redação própria na v1 (custo zero, zero manutenção).
4. **4 calculadoras** (todas selecionadas por Eric): Migração cativo→livre · Precificação de contrato · Custo total do MWh · Conta de luz reversa. Cálculo 100% no navegador, metodologia e limitações declaradas (padrão fisconaweb).
5. **Entenda o mercado** — linha do tempo 1995 → 2024 → 2026 (Lei 15.269) → 2027 → 2028 + glossário básico.
6. **Newsletter** — só captura de e-mail na v1 (double opt-in). Envio automático = v2.
7. **Monetização** — slots de banner reservados ("Anuncie aqui") + mídia kit na v2.

## 5. Arquitetura técnica (em linguagem simples)
- **Site estático** (HTML/CSS/JS puro, 1 página com âncoras) — sem servidor, sem banco, sem mensalidade.
- **Robô de dados (GitHub Actions, gratuito):** todo dia de madrugada um script busca os dados nas APIs públicas (CKAN da CCEE e do ONS, ANEEL), recalcula o termômetro, coleta o RSS das fontes de notícia e grava arquivos JSON no repositório. O site só lê esses JSON.
- **Hospedagem:** Cloudflare Pages/Vercel grátis em subdomínio (decisão do discovery); quando comprar `megagrid.com.br` (~R$40/ano, Registro.br), apontamos sem retrabalho.
- **Manutenção esperada:** ~zero. Pontos de atenção: mudança de layout dos datasets oficiais (raro) e renovação de domínio.
- **Complexidade:** média. O risco técnico está só no robô de dados; o resto é padrão já validado no fisconaweb.

## 6. Identidade visual
Referência aprovada por Eric: lata Valspar Signature — **fundo azul-marinho quase preto + fitas iridescentes (ciano → azul → magenta → laranja) + tipografia branca forte**. Tradução: tema escuro sofisticado, gradientes de "fluxo de energia" como assinatura, números grandes em destaque. Nome: MEGAGRID.

## 7. Fontes de dados validadas (12/06/2026)
| Fonte | O quê | Acesso |
|---|---|---|
| dadosabertos.ccee.org.br | PLD_FINAL_HISTORICO (semanal), PLD horário/sombra, migração, contratos | CKAN API ✔ testado |
| dados.ons.org.br | EAR/ENA diário por subsistema, carga diária, CMO semanal/semi-horário, constrained-off, geração | CKAN API + AWS S3 ✔ testado |
| dadosabertos.aneel.gov.br | Tarifas distribuidoras, bandeiras tarifárias | CKAN API (validar no build) |
| RSS oficiais (MME, ANEEL, ONS, CCEE, EPE) | Radar de notícias | validar feeds no build |

## 8. Restrições permanentes
- **Nenhum conteúdo, case ou referência ligada à DACAR.**
- Tom direto, sem juridiquês; conteúdo informativo/educacional com aviso legal (não é recomendação de contratação ou investimento).
- Sempre citar e linkar a fonte oficial dos dados.

## 9. Roadmap v2 (não fazer agora)
Envio automático da newsletter · mídia kit PDF + página comercial · resumos de notícia gerados por IA · páginas por estado/distribuidora (SEO programático) · comparador de comercializadoras · termômetro com previsão meteorológica (INMET).

## 10. Estado atual do projeto
- ✔ Discovery concluído (escopo, calculadoras, publicação, newsletter decididos por Eric em 12/06/2026)
- ✔ Fontes de dados CCEE/ONS validadas via API
- ✔ Brief v1 gravado
- ✔ Mockup visual da homepage entregue (`site/index.html`) — **aguardando reação do Eric**
- ⏭ Próximo: Fase 3 — construir robô de dados + calculadoras reais + publicar
