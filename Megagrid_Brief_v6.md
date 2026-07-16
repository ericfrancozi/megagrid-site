# MEGAGRID — Brief v6
*18/06/2026 · substitui o v5 · mudanças: site no ar em megagrid.com.br + robô de dados real + sistema de e-mail completo (double opt-in, boas-vindas e newsletter semanal automática)*

## 1. O produto
Portal gratuito sobre o **mercado livre de energia** no Brasil — preços, tendência, notícias e simuladores — alimentado por dados abertos oficiais (CCEE, ONS, ANEEL), com automação máxima e manutenção mínima. Modelo editorial: MegaWhat. Modelo de produto: fisconaweb (ferramentas + dados + tráfego → ads/patrocínio). Escopo: **100% energia** (mercado livre como núcleo + novos mercados: EVs/carregadores, baterias, GD, data centers).

## 2. Estado do tema
- **Passado:** mercado livre nasce em 1995 (Lei 9.074), restrito a grandes consumidores. Jan/2024: todo o Grupo A pode migrar — >35% do consumo nacional.
- **Atual (jun/2026):** Lei 15.269/2025 aprovada — cria o SUI e define a abertura total. Pauta quente: preço horário/CVaR, baterias, curtailment, data centers, GD saturando redes.
- **Tendência:** abertura BT comercial/industrial até **dez/2027**, residencial até **dez/2028** → público salta de milhares para milhões.

## 3. Público e proposta de valor
Stakeholder já no mercado livre ou interessado. Encontra: atualização rápida, base para decisão, amparo para escolhas, simulações fáceis, passado → presente → tendência. Sentimento-alvo (nunca dito): "aqui eu entendo e me atualizo sem tecniquês".

## 4. Escopo entregue (v1 publicada)
1. **Painel de preços** — PLD semanal por submercado (CCEE) + histórico.
2. **Termômetro do MWh** — índice 0–100 diário (EAR 35% · ENA 25% · momentum PLD 20% · carga 10% · bandeira 10%), metodologia pública.
3. **Radar de notícias com editorias** — agregado automático, imagem, fonte, link, classificação por editoria.
4. **"+ Lidas da semana"** — widget lateral numerado (1–5), cliques via GoatCounter + fallback por recência.
5. **4 calculadoras** — Migração cativo→livre · Precificação de contrato · Custo total do MWh · Conta de luz reversa. 100% no navegador.
6. **Entenda o mercado** — linha do tempo 1995→2028 + glossário.
7. **Newsletter — agora COMPLETA** (era só captura no v5):
   - **Double opt-in:** inscrição → e-mail "Confirme sua inscrição" → clique → página `/obrigado` + entra na lista.
   - **Boas-vindas:** automação dispara e-mail "Bem-vindo ao Megagrid" após confirmação.
   - **Resumo semanal automático:** toda segunda 8h (BRT), robô monta e envia o "Resumo da semana" com preços + termômetro + manchetes.

## 5. Monetização — malha de espaços
| Posição | Formato | Observação |
|---|---|---|
| Pós-hero | Leaderboard 970×120 | primeiro espaço visto por todo visitante |
| Entre editorias | Banner 970×250 | meio de página, alto engajamento |
| Lateral (sticky) | Retângulo 300×250 | acompanha a leitura, abaixo do "+ Lidas" |
| Pré-rodapé | Bloco "Anuncie aqui" | pitch comercial → mídia kit |

Slots renderizados e prontos para AdSense ou patrocínio direto. Mídia-kit PDF já incluído em `site/midia-kit-megagrid.pdf`.

## 6. Hierarquia de conteúdo (layout InfoMoney — mantido)
Header branco → ticker de pregão (110s) → ad leaderboard → manchetes (3 colunas: principal · card visual · Tempo Real + "+ Lidas") → faixa de mercado (PLD · cotações · termômetro) → editorias (Mercado Livre, Regulação & Política, Transição & Novos Mercados) → calculadoras → timeline → **newsletter** → ad "Anuncie aqui" → footer.

## 7. Identidade visual (mantida)
Cabeçalho BRANCO. Logo: pulso em gradiente + **MEGA** iridescente (Valspar) + **GRID** navy #0A1426. Escuro só em ticker e rodapé. Acento de UI: azul #1456D6. Os e-mails seguem a mesma identidade (wordmark MEGAGRID, botão azul, filete gradiente).

## 8. Arquitetura técnica — ATUALIZADA
- **Site:** estático em `site/`, deploy automático na **Vercel** (push no GitHub → deploy). Domínio próprio **megagrid.com.br** (registro.br), DNS apontando para Vercel, DNSSEC desativado.
- **Robô de dados (diário):** GitHub Actions `fetch-data.yml` (06h BRT) → `fetch_data.py` lê CCEE/ONS/ANEEL + **Google News RSS** (5 buscas temáticas, com fallback institucional) → grava JSONs em `site/data/` → commit/push → site lê.
- **Robô da newsletter (semanal):** GitHub Actions `newsletter.yml` (seg 08h BRT) → `send_newsletter.py` lê os JSONs → monta HTML branded → envia via **Brevo Email Campaigns API** para a lista de inscritos. Trava de segurança: não envia se faltar dado essencial.
- **Inscrição:** formulário → `api/subscribe.js` (Vercel Function) → endpoint **double opt-in** do Brevo, com fallback seguro.
- **Analytics:** GoatCounter + Vercel Insights. **SEO:** meta OG/Twitter, favicon, robots.txt, sitemap.xml.

## 9. Infra de e-mail (Brevo) — referência
- Conta Brevo "Fisconaweb" (compartilhada com fisconaweb.com.br). Domínio **megagrid.com.br autenticado** (DKIM + DMARC + SPF). Remetente **Megagrid <contato@megagrid.com.br>** (verificado). E-mail de contato encaminhado via forwardemail.net → Gmail.
- **Lista:** Megagrid Newsletter = ID 4 (limpa, só inscritos reais).
- **Templates:** #5 "Confirmação de inscrição" (DOI, ativo) · #6 "Boas-vindas" · automação de boas-vindas (gatilho: contato adicionado à lista #4 → 5 min → e-mail).
- **Env vars (Vercel):** BREVO_API_KEY, BREVO_LIST_ID, BREVO_DOI_TEMPLATE_ID=5. **Secret (GitHub):** BREVO_API_KEY.
- **Entregabilidade:** domínio novo → Gmail faz greylisting nas primeiras entregas; reputação aquece com o tempo. Primeiro envio real validado em 18/06/2026.

## 10. Fontes de dados
CCEE dados abertos (PLD) ✔ · ONS dados abertos (EAR/ENA, carga) ✔ · ANEEL (tarifas, bandeiras) ✔ · Google News RSS + RSS institucionais ✔ · GoatCounter ("+ Lidas") ✔.

## 11. Restrições permanentes
- **Nenhum conteúdo, case ou referência ligada à DACAR.**
- Tom direto, sem juridiquês; aviso legal padrão; sempre citar e linkar a fonte oficial.

## 12. Roadmap (próximos passos)
- Refinar o e-mail de boas-vindas (remover placeholders genéricos do builder).
- Páginas por editoria e por estado/distribuidora (SEO programático).
- Resumos por IA · comparador de comercializadoras · meteorologia INMET no termômetro.
- Aquecimento de domínio / monitorar entregabilidade da newsletter.
- (Concluído do roadmap v5: **envio automático da newsletter** ✔.)

## 13. Estado atual do projeto (18/06/2026)
- ✔ Discovery, plano e identidade aprovados
- ✔ Site **publicado e no ar em megagrid.com.br** (Vercel + domínio próprio)
- ✔ Robô de dados real rodando diariamente (CCEE/ONS/ANEEL + Google News)
- ✔ 4 calculadoras funcionais · termômetro · radar de notícias · "+ Lidas"
- ✔ SEO + analytics (OG/Twitter, sitemap, robots, GoatCounter, Vercel Insights)
- ✔ **Sistema de e-mail completo:** double opt-in + boas-vindas + **newsletter semanal automática** (testada e entregue)
- ✔ Lista de inscritos limpa (contatos de teste removidos)
- ⏭ Próximo: refinar e-mail de boas-vindas · aquecer domínio · SEO programático (v2)
