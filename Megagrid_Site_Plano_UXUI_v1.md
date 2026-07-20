# MEGAGRID — Diagnóstico UX/UI e Plano de Melhoria do Site (v1)
**Data:** 20/07/2026
**Base:** auditoria visual ao vivo da home (megagrid.com.br), topo ao rodapé, desktop 1456px
**Uso deste documento:** documento-fundador do workstream "site". Cada passo tem objetivo e critério de aceite — a spec para o Claude Code nasce daqui, pacote a pacote.

> **Anotações do backend (Claude, 20/07/2026)** — fatos verificados que ajustam o diagnóstico:
> - **§3.1 (causa do conteúdo parado):** o robô roda **1x/dia (06h BRT)** via GitHub Actions e coleta Google News RSS (5 buscas temáticas). A causa não é robô quebrado — é **frequência 1x/dia + pool de queries limitado**. Corrigível no P1.4 com mais queries + 2–3 crons/dia.
> - **§3.5 (encoding):** o `&nbsp;` vem do `description` do Google News sem `html.unescape` no `fetch_data.py` — conserto de 1 linha no robô, não no front. "TRANSICAO" é o id da editoria usado como label de exibição — corrigir mapeamento id→rótulo.
> - **P1.3/P3.3 (GoatCounter):** analytics **JÁ EXISTE** (GoatCounter + Vercel Insights, desde jun/2026). PORÉM o log do robô mostra "Ranking por recência (sem GoatCounter)" — os secrets `GOATCOUNTER_API`/`GOATCOUNTER_SITE` não estão configurados no GitHub, então o "+ Lidas" está no fallback por recência. **Consertar essa ponte é pré-requisito do aceite do P1.3** (ranking por pageview real).
> - **§3.5 (ticker com valores idênticos):** convergência real de submercados é comum no PLD (SE/CO=S=NE frequentemente). Tratamento visual proposto no doc está correto.
> - **Infra que o plano pode usar:** cadeia PLD com 3 fallbacks + sentinela de frescor (jul/2026) já garante dado diário confiável para a "manchete-dado" do P1.4.

---
## 1. Resumo executivo
O site hoje vale nota 3 em percepção, mas a fundação vale 6: ticker de dados, calculadora com metodologia, timeline regulatória e CTA de newsletter são ativos que a maioria dos portais do setor não tem. O que derruba a nota são **4 causas-raiz, todas consertáveis em 2 sprints**: (1) conteúdo parado, (2) três módulos mostrando as mesmas 5 matérias, (3) bugs de texto/layout que passam impressão de site quebrado, (4) placeholders de anúncio vazios como primeira coisa que o visitante vê.
**Meta:** nota 7-8 em duas semanas de trabalho. O Pacote 1 (credibilidade) é pré-requisito para iniciar o outreach de patrocinadores; os Pacotes 2 e 3 podem correr em paralelo aos primeiros contatos.
**Princípio norteador:** o MEGAGRID não é um portal de notícias com dados — é um **terminal de dados que também publica notícias**. Toda decisão de design deveria reforçar isso.
---
## 2. Objetivo e princípios de design
**Objetivo do site:** ser a referência de dados acionáveis do mercado livre de energia para gestores, comercializadoras e consumidores em migração — e, comercialmente, sustentar patrocínio em USD via newsletter e espaços qualificados.
Quatro regras permanentes (valem para qualquer tela, hoje e na v2):
1. **Nunca mostrar espaço vazio.** Todo bloco renderizado tem conteúdo real ou não é renderizado. Placeholder de anúncio sem anunciante vira autopromoção da newsletter.
2. **Nenhum dado sem fonte e hora.** Todo número exibe origem (CCEE/ONS/ANEEL) e carimbo de atualização. É o diferencial competitivo — deve ser visível, não escondido no rodapé.
3. **Imagem só se for única e informativa.** Foto genérica repetida comunica descuido. Gráfico gerado do próprio dado comunica a marca.
4. **"Tempo real" só se for tempo real.** Nome de módulo é promessa; promessa quebrada na home destrói a credibilidade do resto.
---
## 3. Diagnóstico detalhado (o que foi visto, com evidência)
### 3.1 Conteúdo parado — o problema nº 1
- Item mais recente da home: "há 3 dias" (17/07). Demais: "há 4 dias", "há 6 dias", "13/07".
- Num site cuja promessa é "traduzido em dados" e que tem widget chamado "tempo real", a manchete de 3 dias atrás é o maior destruidor de credibilidade — para leitor e para patrocinador que visita antes de responder um e-mail de prospecção.
- Causa provável: robô com poucas fontes e/ou baixa frequência de coleta/publicação. *(Confirmado no backend: 1x/dia + 5 queries — ver anotação no topo.)*
### 3.2 Redundância tripla acima da dobra
- As **mesmas 5 matérias** aparecem em três módulos simultâneos: lista de manchetes (coluna esquerda), "TEMPO REAL" (coluna direita) e "+ LIDAS DA SEMANA" (coluna direita, logo abaixo).
- Causa: acervo pequeno + ausência de regra de exclusão entre módulos (um item exibido num módulo não deveria repetir no vizinho).
- Efeito colateral: o widget "tempo real" exibe itens com "há 6 dias" — contradição direta com o nome.
### 3.3 Imagens estáticas e repetidas
- Existe **uma única foto** na home (torres de transmissão, escura, genérica), usada no card de destaque. Todos os demais itens são texto puro.
- É fallback único, não escolha editorial. Confirma a percepção: "estáticas e sempre as mesmas".
### 3.4 Espaços em branco — parte intencional mal executada, parte bug
**Intencionais (espaços de mídia), mas contraproducentes como estão:**
- Topo: caixa cinza "Publicidade — Leaderboard 970×120 — primeiro espaço visto por todo visitante" é literalmente a primeira coisa que qualquer visitante vê. Para o leitor, parece site inacabado; para o patrocinador, parece inventário encalhado (ninguém comprou).
- Rodapé: segunda caixa tracejada "ESPAÇO RESERVADO · ANUNCIE AQUI".
**Bugs de layout (não intencionais):**
- Coluna central termina antes das laterais → vão branco sob o card de destaque.
- Timeline "Entenda o mercado": card "2028" órfão sozinho na segunda linha, com 4 posições vazias ao lado.
- Calculadora: tabela de resultados ocupa metade da largura; a outra metade fica vazia.
### 3.5 Bugs de texto e encoding
- Subtítulo da manchete exibe HTML cru: "amarela&nbsp;&nbsp;Notícia Exata".
- Etiqueta de categoria "TRANSICAO" sem cedilha/til (deveria ser TRANSIÇÃO).
- Ticker: primeiro label truncado ("CO" cortado à esquerda — provavelmente SUDESTE/C.OESTE).
- Ticker: SE/CO, SUL e NORDESTE com valor idêntico (R$ 182,63 ▲3,7%) é convergência real de submercados, mas sem indicação disso parece valor repetido por erro. Merece tratamento visual (ex.: agrupar ou indicar "submercados convergidos").
### 3.6 Hierarquia da home
- Manchete em texto (esquerda) e card com foto (centro) competem pela atenção — não há um "lead" claro.
- O fluxo da página não conta uma história: notícia → calculadora → timeline → newsletter estão empilhados sem transição ou hierarquia de importância.
### 3.7 O que já está bom (preservar, não mexer)
- **Ticker de dados no topo** (PLD por submercado, bandeira, reservatórios, carga SIN): nenhum portal de mídia do setor abre com isso. É o embrião do diferencial.
- **Calculadora cativo × livre** com tabela de economia em 3 anos e nota de metodologia ("não constituem oferta...") — ativo de aquisição e credibilidade.
- **Timeline regulatória** com "VOCÊ ESTÁ AQUI" em 2026 (Lei 15.269/2025, abertura 2027/2028) — didática, boa para o público em migração.
- **CTA de newsletter** claro ("O essencial do mercado, sem ruído", "sem spam, descadastro em 1 clique").
- **Rodapé** com fontes oficiais (CCEE, ONS, ANEEL — Dados Abertos), Termômetro do MWh, Metodologia, e o filete de gradiente da marca.
- Tipografia limpa, identidade discreta, selo BETA honesto.
---
## 4. Plano passo a passo
Formato de cada passo: **o que fazer → objetivo → critério de aceite**. Complexidade estimada entre parênteses (simples/média/ambiciosa).
### PACOTE 1 — Credibilidade (Sprint 1, ~1 semana) — pré-requisito para prospecção
**P1.1 — Corrigir bugs de texto** (simples)
- O quê: decodificar entidades HTML nos títulos/subtítulos vindos do robô (&nbsp; etc.); corrigir acentuação das etiquetas de categoria (TRANSIÇÃO); consertar labels truncados do ticker.
- Objetivo: eliminar qualquer sinal visível de "site quebrado" — é o conserto mais barato com maior efeito imediato.
- Aceite: nenhuma entidade HTML crua em nenhuma página; todas as categorias acentuadas; ticker legível em qualquer largura de tela.
**P1.2 — Regra de exclusão entre módulos da home** (simples)
- O quê: um item exibido na manchete/destaque não aparece nos widgets laterais; cada módulo puxa de um pool distinto (destaque = editorial/mais relevante; lidas = ranking por pageview real).
- Objetivo: acabar com a sensação de "só existem 5 matérias no site inteiro".
- Aceite: zero repetição de título acima da dobra com acervo ≥ 8 itens; com acervo menor, módulos laterais colapsam (regra nº 1: não renderizar vazio nem repetido).
**P1.3 — Remover o widget "Tempo real"; fica somente "+ Lidas da semana"** (simples) — *DECIDIDO pelo Eric em 20/07*
- O quê: excluir o widget "Tempo real" da home. "+ Lidas" passa a ser o único módulo lateral de notícias, com ranking por pageview real (não por ordem de publicação) e sem repetir itens já exibidos na manchete/destaque (regra do P1.2).
- Objetivo: eliminar a redundância e a promessa quebrada ("tempo real" com itens de 6 dias). O papel de "dado ao vivo" segue coberto pelo ticker do topo; um widget lateral de dados ricos fica registrado no backlog v2.
- Aceite: home sem o widget "Tempo real"; "+ Lidas" ordenado por audiência real; zero repetição com a manchete.
- *Dependência técnica (backend): configurar secrets GOATCOUNTER_API/GOATCOUNTER_SITE no GitHub para o ranking real funcionar.*
**P1.4 — Frescor editorial: robô com mais fontes e ritmo mínimo** (média)
- O quê: ampliar as fontes coletadas (candidatas naturais: agências e portais do setor + fontes oficiais CCEE/ONS/ANEEL para "notícias de dado"); meta de 3-5 itens novos por dia útil; se não houver notícia nova no dia, a manchete da home passa a ser o **dado do dia** (ex.: "PLD sobe 3,7% e fecha a R$ 182,63") gerado pelo robô.
- Objetivo: home nunca abre com conteúdo de 3 dias; o site respira diariamente mesmo sem redação humana.
- Aceite: 10 dias úteis seguidos com ≥ 3 itens novos/dia; manchete sempre com ≤ 24h.
**P1.5 — Placeholders de anúncio: recolher e concentrar** (simples)
- O quê: remover a caixa "Leaderboard 970×120" do topo; no lugar dela, nada (conteúdo sobe) ou autopromoção da newsletter. Manter **um único** espaço comercial discreto (meio ou rodapé) linkando para a página /anuncie (P3.1).
- Objetivo: primeira impressão passa a ser conteúdo e dado, não inventário vazio; a venda de mídia migra para um lugar profissional (mídia kit), onde ela converte de verdade.
- Aceite: zero caixas vazias/tracejadas visíveis; 1 ponto de contato comercial no máximo, com destino /anuncie.
### PACOTE 2 — Identidade visual "terminal de dados" (Sprint 2, ~1 semana)
**P2.1 — Imagens geradas do próprio dado** (média)
- O quê: substituir a foto genérica por cards visuais gerados automaticamente por matéria: mini-gráfico ou número-chave + título + cor da editoria, no estilo Axios/Chartr. Servem também como OG image (o card que aparece quando o link é compartilhado no LinkedIn/WhatsApp).
- Objetivo: resolver "imagens estáticas e sempre as mesmas" na raiz — cada matéria ganha imagem única, e a imagem em si faz marketing da marca "dados" a cada compartilhamento.
- Aceite: nenhuma foto de banco de imagem na home; toda matéria com card visual próprio; OG image válida ao compartilhar link.
**P2.2 — Hierarquia do hero** (média)
- O quê: 1 manchete dominante (título grande + card visual do P2.1), 2-3 secundárias menores; widgets de dados à direita.
- Objetivo: leitor entende em 3 segundos o que é mais importante agora.
- Aceite: teste do aperto de olhos — com a tela desfocada, há um único ponto focal claro.
**P2.3 — Timeline em carrossel horizontal** (simples)
- O quê: os cards 1995→2028 em uma única linha com scroll horizontal e "VOCÊ ESTÁ AQUI" destacado.
- Objetivo: eliminar o card órfão de 2028 e os 4 vãos; timeline vira elemento navegável.
- Aceite: sem quebra de linha em nenhuma largura de tela; sem área morta.
**P2.4 — Equilíbrio de grid** (simples)
- O quê: colunas da home com alturas equilibradas; resultado da calculadora ocupando a largura útil (ex.: gráfico de barras da economia ao lado da tabela).
- Objetivo: eliminar os vãos brancos não intencionais remanescentes.
- Aceite: nenhuma coluna termina > 150px antes da vizinha acima da dobra.
**P2.5 — (Avaliar depois) Tema escuro "terminal"** (ambiciosa — backlog v2)
- O quê: modo escuro com números grandes, estética Bloomberg-like.
- Objetivo: elevar percepção de produto financeiro para o público trader/gestor. Não é crítico agora; entra na v2 se os Pacotes 1-3 performarem.
### PACOTE 3 — Prova para patrocinador (paralelo ao Sprint 2)
**P3.1 — Página /anuncie com mídia kit** (média)
- O quê: página única com: audiência (visitantes/mês, assinantes da newsletter, perfil do leitor), formatos (banner newsletter, relatório patrocinado, dado exclusivo/co-branded), princípios editoriais (patrocínio não interfere no dado) e contato.
- Objetivo: substituir caixas vazias por uma vitrine profissional; é o destino de todo o funil de prospecção já mapeado (doc prospeccao-megagrid-v1 no Drive).
- Aceite: página no ar, linkada no rodapé e no espaço comercial único; números reais (sem inflar).
**P3.2 — Fonte e metodologia visíveis nos widgets** (simples)
- O quê: cada número da home com micro-selo "Fonte: CCEE · atualizado HH:MM" e link para a página de metodologia (que já existe no rodapé).
- Objetivo: transformar rigor em elemento de marca visível — é o que patrocinador compra ao associar a marca ao MEGAGRID.
- Aceite: 100% dos dados exibidos com fonte + hora clicáveis.
- *Nota backend: quando o PLD vier do fallback, o selo deve refletir a fonte real ("ONS — CMO semanal (PLD = CMO com teto/piso ANEEL)") — o campo `fonte` do pld.json já traz isso.*
**P3.3 — Analytics confiável** (simples) — *JÁ EXISTE (GoatCounter + Vercel Insights). Gap: secrets do GoatCounter no robô (ver P1.3) e consolidação de métricas da newsletter (Brevo) num painel.*
- O quê: garantir analytics + métricas da newsletter (assinantes, open rate) num painel simples.
- Objetivo: sem números de audiência não existe mídia kit nem precificação de cota — é insumo direto da prospecção.
- Aceite: 30 dias de dados limpos antes do primeiro pitch com números.
---
## 5. Sequenciamento e relação com a prospecção
- **Semana 1:** Pacote 1 inteiro. É a condição para outreach — não abordar patrocinador com caixa vazia no topo e manchete de 3 dias.
- **Semana 2:** Pacote 2 + P3.1/P3.2. Primeiros contatos de prospecção (Thunders, Way2) podem começar ao fim desta semana.
- **Contínuo:** P3.3 acumulando prova de audiência; funil de prospecção (mapeamento, sem outreach) roda em paralelo desde já — nada se perde.
- **Trade-off nomeado:** "melhorar o site antes de prospectar" é correto para o *contato*, mas errado se virar pausa geral. O redesign tem escopo fechado (este documento); não deixar virar projeto aberto que adia receita indefinidamente.
---
## 6. Decisões que são suas (responder antes da spec de cada pacote)
1. ~~**"Tempo real":** vira widget de dados ou é removido?~~ **DECIDIDO (20/07): removido — fica somente "+ Lidas".** (P1.3 já reflete isso.)
2. ~~**Fontes do robô**~~ **DECIDIDO (20/07): Google News ampliado (mais queries temáticas) + fontes oficiais CCEE/ONS/ANEEL/MME como "notícia de dado" + manchete-dado gerada pelo robô. Modelo mantido: título + crédito + link (padrão seguro). RSS diretos de veículos: não por ora.**
3. ~~**Analytics:** já existe?~~ **RESPONDIDO (backend): existe — GoatCounter + Vercel Insights. Pendências: secrets do GoatCounter no GitHub (P1.3) e painel consolidado com métricas Brevo.**
4. ~~**Números do mídia kit**~~ **DECIDIDO (20/07): /anuncie entra no ar já, com formatos + princípios editoriais + contato, SEM números de audiência; métricas reais entram após 30 dias de dados limpos.**
---
## 7. Como executar (fluxo de trabalho)
1. ~~Colar este documento no projeto megagrid.~~ ✔ (salvo em 20/07)
2. Responder as decisões da seção 6 (restam a 2 e a 4).
3. Pedir a **spec do Pacote 1** (uma spec por pacote, não uma gigante): objetivo, telas afetadas, dados, critérios de aceite — pronta para o Claude Code executar.
4. Build no Claude Code → deploy de preview na Vercel → **QA visual com o checklist abaixo** → produção.
5. Repetir para Pacotes 2 e 3.
**Checklist de QA visual (rodar após cada deploy):**
- [ ] Zero caixas vazias ou tracejadas em qualquer viewport (mobile, tablet, desktop)
- [ ] Zero entidades HTML cruas ou acentos faltando
- [ ] Manchete com ≤ 24h; carimbo "atualizado às" presente e correto
- [ ] Nenhum título repetido acima da dobra
- [ ] Ticker legível, sem labels cortados
- [ ] Toda imagem única por matéria; OG image correta ao compartilhar
- [ ] Todo dado com fonte + hora
- [ ] Lighthouse: performance e acessibilidade ≥ 90 (mobile)
---
## 8. Métricas de sucesso (medir em 30 dias após Sprint 2)
| Métrica | Hoje (estimado) | Meta 30 dias |
|---|---|---|
| Itens novos publicados/dia útil | < 1 | ≥ 3 |
| Idade da manchete da home | até 3 dias | ≤ 24h |
| Caixas vazias/bugs visíveis na home | 5+ | 0 |
| Nota subjetiva UX/UI (sua) | 3 | ≥ 7 |
| Assinantes newsletter/semana | medir | crescer com base medida |
| Página /anuncie | não existe | no ar, com números reais |
---
## Backlog v2 (depois — não agora)
- Widget lateral de dados ao vivo (mini-gráfico do PLD do dia, bandeira, reservatórios, carga SIN com carimbo de hora) — substitui com vantagem o antigo "Tempo real"; sustenta a oferta de "dado exclusivo" a patrocinadores
- Tema escuro "terminal" (P2.5)
- Páginas de dado por submercado (PLD histórico navegável, comparadores)
- Alertas por e-mail/WhatsApp (PLD acima de X, mudança de bandeira) — potencial produto pago
- Comparador de comercializadoras / diretório do mercado livre (ativo de SEO e de prospecção)
- API pública com tier gratuito (aquisição de audiência técnica) e tier pago
- Relatório mensal em PDF patrocinado (produto direto do funil de patrocínio)
---
*Documento gerado a partir de auditoria visual real da home em 20/07/2026. Não verificado nesta auditoria: páginas internas (Últimas, Preços, Editorias, Calculadoras, Entenda), versão mobile e performance (Lighthouse) — incluir na descoberta do Pacote 1. Anotações de backend adicionadas em 20/07 pelo Claude (workstream dados/infra).*
