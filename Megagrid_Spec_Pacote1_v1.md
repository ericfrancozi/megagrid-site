# MEGAGRID — Spec de Build · Pacote 1 "Credibilidade" (v1)
**Data:** 20/07/2026 · **Origem:** Megagrid_Site_Plano_UXUI_v1.md (decisões 1–4 fechadas)
**Pronta para executar no Claude Code.** Uma entrega = um commit; QA visual ao final com o checklist do plano.

## Arquivos afetados (todos existentes)
| Arquivo | Papel |
|---|---|
| `site/index.html` | Home monolítica (HTML+CSS+JS num arquivo, ~74KB). Todos os ajustes de front. |
| `scripts/fetch_data.py` | Robô de dados. Correções de encoding, novas queries, manchete-dado, GoatCounter. |
| `.github/workflows/fetch-data.yml` | Cron do robô (hoje 1x/dia 09:00 UTC). Ganha 2 execuções extras. |
| `site/anuncie/index.html` | NOVO — stub mínimo do /anuncie (evita link morto do P1.5; P3.1 completa depois). |

## Pré-requisito (ação do Eric, 5 min, antes ou durante o sprint)
**GoatCounter secrets no GitHub** (destrava o ranking real do P1.3):
GoatCounter → Settings → API → criar token com permissão de leitura de estatísticas → GitHub repo `megagrid-site` → Settings → Secrets and variables → Actions → adicionar `GOATCOUNTER_API` (o token) e `GOATCOUNTER_SITE` (o código do site, ex.: `megagrid`). O robô já lê essas envs (workflow linha `GOATCOUNTER_API/SITE`); sem elas, cai no fallback por recência.

---

## P1.1 — Bugs de texto
**No robô (`fetch_data.py`, função `_parse_feed`):**
- Aplicar `html.unescape()` em `titulo` e `lead` (import `html`); depois normalizar espaços (`re.sub(r"\s+", " ", ...)`) — mata `&nbsp;` na origem. Remover sufixo "  Fonte" que o Google News anexa ao lead (mesmo regex já usado no título).
**No front (`index.html`):**
- Criar mapa de rótulos de editoria e usá-lo em TODO lugar que hoje exibe o id cru:
  `{"mercado-livre":"Mercado Livre","regulacao":"Regulação","politica-energetica":"Política Energética","empresas":"Empresas","transicao":"Transição","tarifas":"Tarifas"}`
- Ticker: consertar o corte do primeiro label (o keyframe `roll` começa com conteúdo sob a borda esquerda). Adicionar padding-left inicial no tape ou iniciar a animação em `translateX(0)` com o primeiro item visível; garantir também `min-width` nos itens para não truncar "SUDESTE/C.OESTE".
- Ticker: quando 2+ submercados tiverem o MESMO preço na mesma atualização, agrupar visualmente: exibir `SE/CO · S · NE R$ 176,11` (um item só) em vez de três itens idênticos. Implementar no JS que monta o tape a partir de `pld.json`.
**Aceite:** nenhuma entidade HTML crua; todas as editorias acentuadas; ticker sem labels cortados em 360/768/1456px; submercados convergidos agrupados.

## P1.2 — Regra de exclusão entre módulos
**No front (JS do `index.html`, função que distribui `noticias.json`):**
- Construir um `Set` de URLs já usadas na ordem de prioridade: (1) manchete principal, (2) card visual de destaque, (3) lista de secundárias da esquerda, (4) grids de editoria.
- "+ Lidas" (de `mais-lidas.json`) filtra contra esse Set. Se após o filtro sobrarem < 3 itens, **o módulo não renderiza** (regra nº 1 do plano: nunca vazio, nunca repetido).
**Aceite:** zero título repetido acima da dobra com acervo ≥ 8; módulo colapsa com acervo menor.

## P1.3 — Remover "Tempo real"; "+ Lidas" por audiência real
**No front:** excluir a seção/markup do widget "TEMPO REAL" e seu CSS/JS associado. "+ Lidas" sobe para o topo da coluna direita.
**No robô:** nada a mudar no código (`fetch_mais_lidas` já usa GoatCounter quando as envs existem) — depende do pré-requisito de secrets acima.
**Aceite:** home sem "Tempo real"; log do robô mostrando ranking por cliques (não "por recência"); zero repetição com a manchete (via P1.2).

## P1.4 — Frescor: mais fontes + ritmo + manchete-dado
**No robô (`fetch_data.py`):**
1. Ampliar `RSS_FEEDS` (Google News) com ~6 novas queries temáticas: leilão de energia elétrica; PLD CCEE preço energia; migração mercado livre energia; autoprodução energia; armazenamento baterias setor elétrico; subsídios CDE conta de luz. (Manter as 5 atuais.)
2. Promover os feeds institucionais (CCEE/ANEEL/MME, hoje só fallback) a fontes SEMPRE coletadas, com `fonte` = nome do órgão.
3. **Manchete-dado:** nova função `gerar_manchete_dado(pld, ear, bandeira)` que cria 1 item diário sintético quando o item mais novo do acervo tiver > 24h **ou** sempre às 06h (decisão de implementação: sempre gerar; dedup por id `dado-YYYY-MM-DD`). Título no padrão: `"PLD {sobe|cai} {x}% na semana e fecha a R$ {preço} no {submercado}"` (usar SE/CO; se variação 0, usar reservatórios ou bandeira como pauta). `fonte:"Megagrid Dados"`, `editoria:"mercado-livre"`, `url:"https://megagrid.com.br/#precos"`, sem imagem de banco (usa card do P2.1 futuramente; por ora `IMAGENS_FALLBACK`).
**No workflow (`fetch-data.yml`):** cron adicional — `"0 12 * * *"` e `"0 18 * * *"` (≈ 09h e 15h BRT) além do atual `"0 9 * * *"`. Atenção: manter o passo da sentinela como está.
**Aceite:** ≥ 3 itens novos/dia útil por 10 dias (medível no git log do `noticias.json`); manchete da home sempre ≤ 24h.

## P1.5 — Placeholders de anúncio
**No front (`index.html`):**
- Remover o bloco "Publicidade · Leaderboard 970×120" do topo (conteúdo sobe).
- Substituir o bloco tracejado "ESPAÇO RESERVADO · ANUNCIE AQUI" do pré-rodapé por um cartão discreto de linha única: `Anuncie no Megagrid — sua marca diante de quem decide energia →` linkando para `/anuncie`. Sem borda tracejada, sem "publicidade", estilo card sólido `--alt`.
- Link "Anuncie aqui" do rodapé passa a apontar para `/anuncie`.
**Novo `site/anuncie/index.html` (stub):** mesma base visual da página /obrigado (header + card central). Conteúdo: título "Anuncie no Megagrid", 3 bullets de formatos (banner na newsletter semanal · relatório patrocinado · dado exclusivo co-branded), princípio editorial (1 linha: "patrocínio não interfere no dado"), contato `contato@megagrid.com.br`. SEM números de audiência (decisão 4). Meta `noindex` até o P3.1 completar.
**Aceite:** zero caixas vazias/tracejadas em qualquer viewport; 1 único ponto comercial; /anuncie responde 200 com o stub.

---

## Fora de escopo do Pacote 1 (não fazer agora)
Cards visuais por matéria (P2.1) · hierarquia do hero (P2.2) · carrossel da timeline (P2.3) · grid da calculadora (P2.4) · mídia kit completo com números (P3.1) · selos fonte+hora nos widgets (P3.2 — nota: quando fizer, usar o campo `fonte` dos JSONs, que já indica o fallback CMO quando ativo).

## Descoberta pendente (rodar na abertura do sprint, 30 min)
Auditar o que o plano não viu: páginas internas (Últimas/Preços/Editorias/Calculadoras/Entenda — verificar se existem como âncoras ou rotas), versão mobile da home, Lighthouse baseline (registrar score antes das mudanças para comparar no aceite).

## QA final do pacote (gate de produção)
Checklist do plano (seção 7) completo em mobile/tablet/desktop + sentinela do robô verde no dia seguinte ao deploy + `noticias.json` com ≥ 3 itens novos no primeiro dia útil pós-deploy.
