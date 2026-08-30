# Rotina de candidaturas · 2x por semana (segunda e quinta, manhã)

Procedimento que o Claude executa quando o cron dispara. `perfil.json` é a única fonte de verdade
sobre o que pode ser afirmado. `enviadas.json` impede candidatura repetida.

## Decisões do dono do perfil que definem o comportamento
- **Auto-envio**, sem revisão prévia de shortlist. O filtro do `perfil.json` é a única salvaguarda.
- **Easy Apply do LinkedIn incluído**, usando o perfil de browser persistente em `data/_perfil-edge` (ou o caminho em `PERFIL_EDGE`).
  Ele logou na mão uma vez. Nunca pedir nem armazenar senha. Se a sessão caiu, parar e avisar.
- **Guardrail de integridade**: campo obrigatório sem resposta verdadeira no `perfil.json` significa
  **fila, não envio**. Nunca inventar experiência para destravar um formulário.

## Passo 1 · Descoberta
Rodar via MCP Apify, actor `valig/linkedin-jobs-scraper`, uma chamada por linha:

| title | location | limit |
|---|---|---|
| SEO Specialist | Brazil | 25 |
| Technical SEO | Brazil | 15 |
| Paid Media Specialist | Brazil | 20 |
| Performance Marketing | Brazil | 20 |
| Google Ads Specialist | Brazil | 15 |
| Growth Marketing | Brazil | 20 |
| Generative Engine Optimization | Worldwide | 15 |

### Trilha DEV (desde 15/08, rodar junto com a de growth)
Usar `filtros_dev` e `pontuacao_fit_dev` do `perfil.json`. Alvos: Full Stack pleno, Growth Engineer
híbrido e Platform/DevOps/SRE. **Não** perseguir Arquitetura/Tech Lead.

| title | location | limit |
|---|---|---|
| Growth Engineer | Brazil | 15 |
| Growth Engineer | Latin America | 15 |
| Full Stack Developer | Brazil | 20 |
| Platform Engineer | Latin America | 15 |
| DevOps | Brazil | 15 |
| Data Engineer | Brazil | 15 |

CV por alvo: vaga de produto/full stack usa `dev_fullstack`; vaga que mistura aquisição, tracking,
experimentação ou automação de marketing usa `growth_engineer`, que é o diferencial dele.

### Empresas
Depois buscar por empresa nas que contratam LATAM para cliente dos EUA, que é onde está o USD:
`Hire With Near`, `Athyna`, `Somewhere`, `Jobgether`, `Darkroom`, `Mindgruve`, `Bionic Talent`,
`BairesDev`, `Support Shepherd`, `Ubiminds`.

Puxar com `fields=id,url,title,companyName,location,workType,contractType,experienceLevel,applyType,applyUrl,postedTimeAgo,applicationsCount,salary,description`.

## Passo 2 · Filtro e pontuação
Aplicar `filtros` e `pontuacao_fit` do `perfil.json`, nessa ordem:
1. Descartar id já presente em `enviadas.json`.
2. Título precisa bater `titulo_precisa_conter_um_de` e não bater `titulo_reprova_se_contiver`.
3. Descrição não pode bater `descricao_reprova_se_contiver`.
4. Localização, senioridade, idade do post e número de candidatos dentro do permitido.
5. Se a descrição exigir mais de `anos_maximos_exigidos` anos, descartar.
6. Se exigir como **obrigatório** algo do bloco `NUNCA_AFIRMAR`, descartar.
7. Somar `pontuacao_fit`, subtrair penalidades.

## Fonte secundária · Biblioteca de Anúncios da Meta (testada 17/08)

Ideia do dono do perfil: empresa que contrata anuncia vaga no Meta. Testado com
`mcp__mcp-meta-2b__ads_library_search`. Resultado medido:

- **Brasil, sem filtro de tipo: FUNCIONA.** `search_terms="vaga gestor de tráfego contratando"`,
  `countries=["BR"]`, `ad_active_status="ACTIVE"` → 71 estimados, maioria vaga real, criada no dia.
- **`ad_type="EMPLOYMENT_ADS"`: INÚTIL.** BR devolve 0 e US devolve lixo. Declarar categoria especial
  de emprego é exigência focada nos EUA e quase ninguém declara. Não usar esse filtro.
- **EUA em inglês: NÃO FUNCIONA.** "hiring media buyer" → 142 estimados e ZERO vaga; é tudo agência
  vendendo serviço e guru vendendo curso (Jason Wojo, Caples.ai, Coast Summit). Empresa americana
  recruta por LinkedIn e ATS, não por anúncio no Facebook.

**Qualidade do que sai no BR:** agência de PME oferecendo vaga PRESENCIAL no interior (Porto Alegre,
Goiânia, São José do Rio Preto, Balneário Camboriú). É o segmento que ele quer DEIXAR. Prioridade baixa.

**Ruído a cortar sempre:** infoproduto e comunidade paga se disfarçam de vaga. Sinais: "QG das
Agências", nome de página que é nome de pessoa + "Tráfego Pago", título tipo "Inscreva-se já",
"Saiba Mais". Vaga real costuma ter no `ad_creative_link_title`: "Vaga:", "Vagas abertas",
"Envie seu currículo", "Candidate-se".

**Uso melhor da mesma ferramenta (a testar):** buscar por `page_ids` das agências de staffing LATAM
(Hire With Near, Floowi, Activate Talent, Scale Army, Remote Talent LATAM). Se elas anunciam vaga,
é remota em dólar com pouca concorrência.

### Termos testados (17/08) e o que cada um devolveu

| Query | País | Estimado | O que veio |
|---|---|---|---|
| `vaga gestor de tráfego contratando` | BR | **71** | ✅ vagas reais de agência, criadas no dia. **É A ÚNICA QUE SERVE** |
| `we're hiring join our team apply now` | US | **50.909** | ❌ mercado local por hora: cafeteria, Chick-fil-A, YMCA, salva-vidas, enfermagem, encanador, mecânico |
| `hiring media buyer` | US | 142 | ❌ zero vaga; agência vendendo serviço e guru (Jason Wojo, Caples.ai) |
| `paid media specialist hiring remote` + EMPLOYMENT_ADS | US | 5 | ❌ lixo, páginas nigerianas |
| `gestor de tráfego growth performance vaga` + EMPLOYMENT_ADS | BR | **0** | ❌ o filtro EMPLOYMENT_ADS não é populado |
| `vaga home office remota marketing` | BR | **0** | ❌ |
| `trabajo remoto vacante marketing digital` | MX,CO,AR | 5 | ❌ páginas agregadoras e funil de captação |

**Conclusão estrutural:** anúncio de vaga no Meta = mercado de trabalho LOCAL e PRESENCIAL. Trabalho
remoto de conhecimento não é anunciado ali porque o público não está no Facebook e o custo por
candidato qualificado é pior que LinkedIn/ATS. Portanto essa fonte NÃO substitui o scraper do
LinkedIn; ela complementa só no recorte "agência brasileira contratando gestor de tráfego".

**Sinal de golpe a filtrar:** anúncio de trabalho remoto no Meta com linguagem genérica de benefício
("remote work offers greater location flexibility", "flexible work hours") sem nome de cargo nem
empresa reconhecível. Visto em 17/08 na página "Hotel Web-3". Padrão de fraude de recrutamento.

**Filtro de golpe mais objetivo, descoberto 17/08:** `currency` do anúncio é **NGN** (naira) mirando
palavra-chave de emprego em inglês, com `page_name` que é nome de pessoa física. Cluster visto:
"Lisa Black", "selina McKinley", "Barbara Maria Emily", "AI-Kyndra", "The Celestial CEO",
"AmeriPride Services". Descartar sempre.

### VEREDITO FINAL (9 queries, 4 mercados, 17/08)
As agências de staffing LATAM (Floowi, Hire With Near, Activate Talent) têm **0 anúncios** no Meta:
elas só usam LinkedIn. A query `now hiring marketing manager join our team` (US, 1.010 estimados)
devolve vaga de marketing real (HenkinSchultz, Careers At Crown) mas **presencial nos EUA**, para a
qual ele não é elegível.

**Conclusão: a Biblioteca do Meta NÃO é fonte de vaga remota de trabalho de conhecimento.** Manter
apenas a query BR de gestor de tráfego, como fonte secundária de baixa prioridade. Não gastar mais
tempo explorando essa fonte; o LinkedIn produziu 100% das 14 candidaturas.

### ⚠️ CORRIGIDO EM 18/08: o veredito acima estava ERRADO

O o dono do perfil foi impactado por **dois anúncios de vaga de media buyer no Instagram** e me trouxe as
landing pages. Refiz a busca e a fonte funciona: **eu tinha buscado com os termos errados.**

Meu erro foi triplo: busquei em **português** (`gestor de tráfego`), busquei o **mercado americano**
(`countries: US`), e busquei **cargo genérico de marketing**. Mas esses anúncios são em **inglês**,
pagos por **agência de fora**, e mirados em **LatAm**. A UTM da Contractor Liberty diz literalmente
`LatAm - LP Applications`.

**A receita que funciona:**

| Parâmetro | Valor |
|---|---|
| `search_terms` | `media buyer` (amplo, 103 ativos) ou `media buyers needed hiring` (estreito, 17 e quase tudo vaga real) |
| `countries` | `["BR","MX","CO","AR"]` — o país de ENTREGA, não o do anunciante |
| `ad_active_status` | `ACTIVE` |
| `limit` | 50 |

Outros termos que valem rodar: `hiring media buyer`, `paid ads specialist`, `performance marketer`,
`GHL specialist`, `we're hiring`.

**Prova de que fecha ponta a ponta:** a busca devolveu `windows.scaleprediction.com/seniormediabuyerapplications`,
que é exatamente a URL que ele recebeu no feed do Instagram.

**GOTCHA para extrair o link de destino:** o campo da API só traz `ad_creative_link_title`, não a URL.
Para pegar o destino é preciso abrir `facebook.com/ads/library/?id=<id>` e decodificar os anchors: o
Meta embrulha link externo em `l.facebook.com/l.php?u=<urlencoded>`. Filtrar por "facebook.com no
host" **descarta justamente o destino** (erro que eu cometi na primeira passada). Script pronto:
um script auxiliar local (nao versionado).

**Ruído a filtrar:** ~50% da query ampla é app de microdrama (Beereel, Unicorn Illusion, "Eve helped
Noah build Black Tech...") e guru de curso (Brook Hiddink). O sinal está em criativo com linguagem de
contratação: `needed`, `wanted`, `we're hiring`, `apply`, `join`.

**Colheita da primeira rodada boa (18/08):** Contractor Liberty, ScalingPredictably, Stratus Digital
(UK, £3-5k base), Rizen Estate, Value Add Marketing (Media Buyer + GHL Specialist), Grow Pro Agency
via torre.ai. Detalhe em `COLAR-mediabuyer-ads-meta.md`.

**Promover a fonte primária secundária de verdade**, não "baixa prioridade". Rodar as duas queries a
cada rodada.

## Passo 2.5 · CHECAR MODELO DE TRABALHO (obrigatório, antes de qualquer outra coisa)

O actor do LinkedIn **não devolve modelo de trabalho**. Em 15/08 eu escrevi adaptador e preenchi
formulário inteiro de uma vaga que era **presencial em São Paulo**, e descobri só no screenshot.
Erro caro e evitável.

Antes de escrever qualquer resposta ou adaptador, checar o modelo de trabalho na URL da vaga e ler
o cabeçalho. Regra de corte:

- **Remoto** ou **Remoto (LATAM/Brasil)** → segue.
- **Presencial ou híbrido em a cidade do perfil** → segue.
- **Presencial ou híbrido em qualquer outra cidade** → DESCARTA e registra o motivo. Ele não muda de
  cidade (`presencial_outra_cidade_ok: false` no perfil.json).
- **"Remoto hoje, híbrido depois"** → NÃO decidir sozinho, perguntar a ele.

Cuidado com a armadilha: no LinkedIn a vaga aparece como "São Paulo, São Paulo, Brazil" tanto para
presencial quanto para remoto com sede em SP. A localização no card não é o modelo.

## Passo 3 · Rota de envio
Para cada vaga com score acima de `corte_auto_envio.score_minimo`:

1. **Resolver a URL real de candidatura.** O actor devolve `applyUrl` vazio, então abrir a página da
   vaga no LinkedIn com o perfil persistente e pegar o destino do botão de apply.
2. **Detectar o ATS** pelo domínio: `teamtailor.com` ou careers.* com Teamtailor, `workable.com`,
   `greenhouse.io`, `lever.co`, `ashbyhq.com`, `recruitee.com`, `gupy.io`.
3. **Escolher o CV** por trilha: vaga de SEO/web usa `web_seo`; vaga de mídia paga ou mista usa
   `paid_seo`; vaga em português no Brasil usa `growth_pt`.
4. **Rodar o adaptador em dry-run primeiro**, ler o estado impresso e o screenshot. Só então enviar.
5. Se aparecer campo obrigatório sem resposta no `perfil.json`: **não enviar**, registrar em `fila.md`
   com a pergunta literal e seguir para a próxima.
6. Registrar em `enviadas.json`: id, url, empresa, título, data, CV usado, score, status.

Adaptador pronto e testado: `aplicar_teamtailor.py` (funciona em qualquer careers site Teamtailor).
Para ATS ainda sem adaptador: usar `core/recon.py` para mapear o formulário, escrever
o adaptador, testar em dry-run e só depois enviar.

## Passo 4 · Relatório
Fechar com: quantas descobertas, quantas passaram o filtro, quantas enviadas com link, quantas na fila
e por qual pergunta travou. Se alguma vaga exigir decisão dele (salário fora da faixa, presencial,
pergunta pessoal), listar explicitamente.

## Verificação de e-mail
Vários ATS (Teamtailor entre eles) só completam a candidatura depois que o dono do perfil clica num link
enviado por e-mail. **Sempre lembrar no relatório**: candidatura sem verificação não existe para o
recrutador.
