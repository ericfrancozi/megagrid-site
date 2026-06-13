# MEGAGRID — Brief v2
*12/06/2026 · substitui o v1 · mudança: direção visual revisada por feedback do Eric + estratégia de imagens*

## 1. O produto
Portal gratuito sobre o **mercado livre de energia** no Brasil — preços, tendência, notícias e simuladores — alimentado por dados abertos oficiais (CCEE, ONS, ANEEL), com automação máxima e manutenção mínima. Modelo editorial: MegaWhat. Modelo de produto: fisconaweb (ferramentas + dados compilados + tráfego → receita de ads/patrocínio). Escopo: **100% energia** (mercado livre como núcleo + novos mercados: carregadores de veículos elétricos, baterias, GD).

## 2. Estado do tema (o porquê do timing)
- **Passado:** mercado livre nasce em 1995 (Lei 9.074), restrito a grandes consumidores. Jan/2024: todo o Grupo A pode migrar — >35% do consumo nacional.
- **Atual (jun/2026):** Lei 15.269/2025 aprovada — cria o SUI e define a abertura total. Pauta quente: preço horário/CVaR, baterias, curtailment, data centers, GD saturando redes.
- **Tendência:** abertura BT comercial/industrial até **dez/2027** e residencial até **dez/2028** → público potencial salta de milhares para milhões. Construir audiência agora.

## 3. Público e proposta de valor
Stakeholder já no mercado livre ou interessado. Encontra: atualização rápida, base para decisão, amparo para escolhas, simulações fáceis, passado → presente → tendência. Sentimento-alvo (nunca dito): "aqui eu entendo e me atualizo sem tecniquês".

## 4. Escopo da v1 (decidido em 12/06/2026)
1. **Painel de preços** — PLD horário e semanal por submercado (CCEE).
2. **Termômetro do MWh** — índice 0–100 diário (EAR 35% · ENA 25% · momentum PLD/CMO 20% · carga 10% · bandeira 10%), metodologia pública.
3. **Radar de notícias** — agregado automático (MME, ANEEL, ONS, CCEE, EPE) com imagem, título, fonte e link.
4. **4 calculadoras**: Migração cativo→livre · Precificação de contrato · Custo total do MWh · Conta de luz reversa. 100% no navegador.
5. **Entenda o mercado** — linha do tempo 1995→2028 + glossário.
6. **Newsletter** — só captura (double opt-in) na v1.
7. **Monetização** — slots "Anuncie aqui" + mídia kit na v2.

## 5. Arquitetura técnica
Site estático (HTML/CSS/JS) + robô diário no GitHub Actions lendo CKAN da CCEE/ONS/ANEEL e RSS oficiais → grava JSON → site lê. Hospedagem gratuita (Cloudflare Pages/Vercel) em subdomínio; domínio próprio depois. Manutenção ~zero. Complexidade: média.

## 6. Identidade visual — REVISADA no v2
**Decisão do Eric (12/06/2026):** fundo escuro reprovado para o corpo do site; leitura geral deve se assemelhar ao MegaWhat (portal claro, jornalístico, fotográfico).
- **Base clara:** fundo branco/cinza-claro (#FFF / #F4F6F9), texto #15212F, cards brancos com borda sutil.
- **Escuro só na moldura:** cabeçalho, faixa de cotações (ticker) e rodapé em azul-marinho #0A1426.
- **Gradiente iridescente (lata Valspar) restrito à marca:** palavra MEGA do logo + filete de 3px sob o cabeçalho e sobre o rodapé. **Não usar em botões, títulos ou cards.**
- **Acento único de interface:** azul #1456D6 (botões, links, kickers). Verde/vermelho apenas para variação de preço; escala verde→vermelho no gauge do termômetro (semântica de dados, não branding).
- **Imagens obrigatórias** (feedback do Eric): portal deve ser fotográfico como o MegaWhat. Hero com foto + cards de notícia com thumbnail 16:9.

### 6.1 Estratégia de imagens (manutenção zero)
- v1: notícia usa a imagem do próprio feed RSS quando existir; senão, fallback automático para banco temático por categoria (fotos Unsplash hotlink, licença livre, crédito no rodapé — padrão já usado no fisconaweb).
- Categorias do banco: transmissão/grid, solar, eólica, hidrelétrica, data center, carro elétrico/carregador, medidor/conta.

## 7. Fontes de dados validadas (12/06/2026)
CCEE dados abertos (PLD semanal/horário, migração) ✔ · ONS dados abertos (EAR/ENA, carga, CMO, constrained-off) ✔ · ANEEL dados abertos (tarifas, bandeiras — validar no build) · RSS oficiais MME/ANEEL/ONS/CCEE/EPE (validar feeds no build).

## 8. Restrições permanentes
- **Nenhum conteúdo, case ou referência ligada à DACAR.**
- Tom direto, sem juridiquês; aviso legal padrão; sempre citar e linkar a fonte oficial.

## 9. Roadmap v2 (não fazer agora)
Envio automático da newsletter · mídia kit PDF · resumos por IA · páginas por estado/distribuidora (SEO programático) · comparador de comercializadoras · meteorologia INMET no termômetro.

## 10. Estado atual do projeto
- ✔ Discovery e plano aprovados (12/06/2026)
- ✔ Fontes CCEE/ONS validadas via API
- ✔ Mockup v0.1 (escuro) entregue → feedback: clarear corpo, manter moldura escura, gradiente só na marca, adicionar fotos
- ✔ Mockup v0.2 (claro, estilo MegaWhat, com imagens) entregue — **aguardando reação do Eric**
- ⏭ Próximo: Fase 3 — robô de dados reais (CCEE/ONS/ANEEL + RSS), 4 calculadoras completas, captura de e-mail, publicação em subdomínio gratuito
