# MEGAGRID — Brief v3
*12/06/2026 · substitui o v2 · mudanças: cabeçalho branco, logo definido, menu lateral com editorias, ticker estilo pregão*

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
3. **Radar de notícias com editorias** — agregado automático (MME, ANEEL, ONS, CCEE, EPE) com imagem, título, fonte, link e classificação automática por editoria.
4. **4 calculadoras**: Migração cativo→livre · Precificação de contrato · Custo total do MWh · Conta de luz reversa. 100% no navegador.
5. **Entenda o mercado** — linha do tempo 1995→2028 + glossário.
6. **Newsletter** — só captura (double opt-in) na v1.
7. **Monetização** — slots "Anuncie aqui" + mídia kit na v2.

## 5. Navegação / arquitetura de informação — NOVO no v3
- **Menu lateral** (hambúrguer, modelo MegaWhat): Início · Últimas do Radar · Preços & PLD · Termômetro · **Editorias** (Mercado Livre, Regulação, Política Energética, Empresas, Transição & Novos Mercados, Tarifas & Bandeiras) · **Calculadoras** (4) · Entenda o mercado · Glossário · Metodologia · Fontes · Anuncie · Privacidade.
- **Editorias** funcionam como filtros do Radar na v1 (chips + links do menu); podem virar páginas próprias na v2 (SEO).
- **Ticker = fita de pregão** (pedido do Eric 12/06/2026): faixa escura com rolagem contínua estilo bolsa de valores — PLD dos 4 submercados, bandeira, reservatórios, carga e termômetro; pausa no hover; respeita `prefers-reduced-motion`.

## 6. Identidade visual — REVISADA no v3
- **Cabeçalho BRANCO** (decisão 12/06/2026, modelo MegaWhat), com hambúrguer, navegação e CTA azul.
- **Logo:** símbolo de pulso de energia em gradiente + **MEGA** em gradiente iridescente (lata Valspar: ciano→azul→violeta→magenta→laranja) + **GRID** em azul-marinho #0A1426. Análogo invertido ao MegaWhat (onde MEGA é navy).
- **Escuro só em:** ticker (fita de pregão) e rodapé (#0A1426 / #101F3C).
- **Gradiente restrito à marca:** logo + filete de 3px sobre o rodapé. Nunca em botões, títulos ou cards.
- **Acento único de UI:** azul #1456D6. Verde/vermelho só para variação de preço; escala do gauge é semântica de dados.
- **Corpo claro e fotográfico:** fundo branco/#F4F6F9, hero com foto, thumbnails 16:9 nas notícias (imagem do feed RSS quando existir; senão banco temático Unsplash por categoria — crédito no rodapé).

## 7. Arquitetura técnica
Site estático (HTML/CSS/JS) + robô diário no GitHub Actions lendo CKAN da CCEE/ONS/ANEEL e RSS oficiais → grava JSON → site lê. Classificação de editoria por regras de palavra-chave/fonte (sem custo de IA na v1). Hospedagem gratuita (Cloudflare Pages/Vercel) em subdomínio; domínio próprio depois. Manutenção ~zero. Complexidade: média.

## 8. Fontes de dados validadas (12/06/2026)
CCEE dados abertos (PLD semanal/horário, migração) ✔ · ONS dados abertos (EAR/ENA, carga, CMO, constrained-off) ✔ · ANEEL dados abertos (tarifas, bandeiras — validar no build) · RSS oficiais MME/ANEEL/ONS/CCEE/EPE (validar feeds no build).

## 9. Restrições permanentes
- **Nenhum conteúdo, case ou referência ligada à DACAR.**
- Tom direto, sem juridiquês; aviso legal padrão; sempre citar e linkar a fonte oficial.

## 10. Roadmap v2 (não fazer agora)
Envio automático da newsletter · mídia kit PDF · páginas próprias por editoria e por estado/distribuidora (SEO programático) · resumos por IA · comparador de comercializadoras · meteorologia INMET no termômetro.

## 11. Estado atual do projeto
- ✔ Discovery e plano aprovados (12/06/2026)
- ✔ Fontes CCEE/ONS validadas via API
- ✔ Mockup v0.1 (escuro) → feedback: clarear, fotos
- ✔ Mockup v0.2 (claro + imagens) → feedback: cabeçalho branco, logo MEGA colorido + GRID navy, menu lateral, ticker rolante
- ✔ Mockup v0.3 entregue com tudo acima — **aguardando reação do Eric**
- ⏭ Próximo: Fase 3 — robô de dados reais (CCEE/ONS/ANEEL + RSS), 4 calculadoras completas, captura de e-mail, publicação em subdomínio gratuito
