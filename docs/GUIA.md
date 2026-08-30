# Guia de uso

Este repositório tem três ferramentas que funcionam juntas, mas podem ser usadas separadas.
Nenhuma delas depende das outras para rodar.

| Pasta | O que faz |
|---|---|
| `tools/esteira/` | Lê sua caixa de e-mail, separa o que é resposta de candidatura do que é ruído, guarda num banco e te avisa quando aparece oferta ou prazo vencendo |
| `tools/upwork/` | Abre vagas da Upwork num navegador que **você** controla, lê a descrição, pontua contra o seu perfil e preenche proposta |
| `tools/redacao/` | Esconde nome de cliente e ID de conta na tela antes de você tirar print para portfólio |

> **Antes de começar:** nada aqui envia e-mail, aceita proposta ou assina contrato por você.
> As ferramentas leem, organizam e preenchem. **Apertar enviar continua sendo humano.**
> Isso não é limitação técnica, é escolha: o custo de um envio errado é maior que o ganho
> de automatizar o clique.

---

## Parte 1 — A esteira de e-mail

### O problema que ela resolve

Quem está procurando vaga recebe muito e-mail, e quase nada importa. Numa caixa real,
medida: **2.100 mensagens em 45 dias, das quais 91 eram de verdade.** O resto era alerta
de vaga, newsletter e notificação social.

Pior: alerta de vaga **parece** resposta. Se você filtrar por remetente (`from:linkedin.com`),
recebe 257 alertas e nenhuma resposta de recrutador.

Numa medição real, três coisas estavam enterradas nesse ruído e só apareceram quando a
esteira entrou no ar: uma **carta proposta assinada**, um **convite de entrevista em vídeo
com prazo vencendo**, e um **"final reminder"** de uma vaga. Todos visíveis na caixa,
nenhum visto.

### A decisão de arquitetura que importa

Filtrar por **conteúdo**, não por remetente.

**Lista de permitidos falha invisível.** Se o ATS que te respondeu não está na sua lista,
ele simplesmente não existe, e você nunca descobre. Aconteceu de verdade: a lista dizia
`greenhouse.io`, mas o Greenhouse envia de `greenhouse-mail.io`. Um caractere, e um dos
maiores ATS do mundo ficou invisível.

**Lista de bloqueados falha visível.** O ruído que falta na lista aparece na tela, você vê
e corta. Perder uma entrevista custa muito mais do que ler um assunto de newsletter.

E **armazenar antes de classificar**. Se busca e classificação são a mesma passada, melhorar
uma regra exige baixar tudo de novo, e o que passou batido fica perdido para sempre. Com o
e-mail no banco, classificar vira função pura: melhora a regra, roda de novo em cima do que
já está lá, custo zero de API.

### Como configurar

**1. Acesso ao Gmail.** Conta pessoal (`@gmail.com`) **não** aceita service account. Domain
delegation existe só em Workspace. O único caminho é OAuth de aplicativo desktop:

- Google Cloud Console → crie um projeto
- APIs e serviços → Biblioteca → ative a **Gmail API**
- Clients → Create OAuth client → tipo **Aplicativo para desktop** → baixe o JSON
- Audience → **Test users** → adicione o seu próprio e-mail
  (sem isso o consentimento morre em `access_denied`)

⚠️ **App em publishing status "Testing" tem refresh token que expira em 7 dias.** Se você
for rodar isso num cron, publique o app (**In production**), senão ele morre em uma semana
parecendo bug. Publicar exige uma home page que descreva o app e tenha o **mesmo nome** que
está no consentimento — o revisor olha a raiz do domínio, então a forma que funciona é um
subdomínio dedicado.

**2. Banco.** Qualquer Postgres serve. Aplique `tools/esteira/schema.sql`.

**3. Variáveis** (crie um `.env` a partir do `.env.example`):

```
GMAIL_CLIENT_SECRET=caminho/para/gmail-oauth-client.json
DATABASE_URL=postgresql://usuario:senha@host:porta/banco
MEUS_EMAILS=voce@gmail.com,voce@empresa.com
AVISO_PARA=voce@gmail.com
BREVO_API_KEY_ESTEIRA=...      # opcional, só para o alerta por e-mail
BREVO_SENDER_ESTEIRA=...
```

### Como usar

```bash
python tools/esteira/gmail_vagas.py autorizar   # uma vez, abre o navegador
python tools/esteira/esteira.py sync            # busca e grava
python tools/esteira/esteira.py classificar     # roda as regras em cima do banco
python tools/esteira/esteira.py ler             # a fila do que precisa de você
python tools/esteira/esteira.py visto <id>      # tira da fila
python tools/esteira/gmail_vagas.py tudo 7          # varre a caixa inteira e mostra o padrão
```

Em cron, o comando é `esteira.py cron`, que faz sync e classificar em sequência.

### Ajustando as regras

Tudo vive em `tools/esteira/gmail_vagas.py`, em listas no topo do arquivo:

- `FRASES` — o que **procurar**, em português e inglês
- `RUIDO_DE` — remetentes que nunca interessam
- `RUIDO_ASSUNTO` — assuntos de alerta, comparados **sem acento**
- `REGRAS` — o estado da candidatura; **a ordem é a prioridade**, o primeiro que casa ganha
- `ACAO` — o que exige você

Depois de mexer, incremente `VERSAO_REGRA` em `esteira.py` e rode `classificar`. Ele
reprocessa só o que ficou para trás.

**Duas armadilhas já pagas:**

Rejeição em português não casa com regex em inglês. Uma rejeição real passou batido porque
dizia "optamos por seguir com outros perfis", e a regra só conhecia "unfortunately".

Acento quebra comparação. A lista dizia `esta contratando` e o assunto real era
`está contratando`. Doze alertas vazaram por causa de um acento. Por isso a comparação passa
por `sem_acento()`.

---

## Parte 2 — Upwork

### O princípio

**Quem abre o navegador decide se você passa.**

Navegador lançado por automação é detectado e cai em desafio infinito — você resolve o
captcha e ele gera outro, para sempre. Navegador aberto **por uma pessoa**, ao qual a
automação **se conecta depois**, passa normalmente.

Por isso o fluxo é:

1. Você abre o Brave/Chrome com porta de depuração
2. Você passa o Cloudflare, se aparecer
3. A ferramenta **se conecta** ao que já está aberto, nunca lança nada

```bash
# você roda isto, sem nenhuma flag de automação
brave.exe --remote-debugging-port=9333 --user-data-dir=C:\caminho\perfil
```

Em ordem de peso, o que faz um navegador ser detectado: **identidade do binário > idade do
perfil > cadência > IP > comportamento**. Perfil recém-criado num binário conhecido cai;
perfil antigo com histórico real passa.

### Comandos

```bash
python tools/upwork/upw2.py estado                    # onde estou, estou logado, tem muro
python tools/upwork/upw2.py ir <url>                  # navega e espera o desafio passar
python tools/upwork/upw2.py ler                       # salva o texto da página
python tools/upwork/upw2.py campos                    # lista os campos do formulário
python tools/upwork/upw2.py set "<rótulo>" "<texto>"  # preenche um campo
python tools/upwork/upw2.py propor <url> <arquivo>    # preenche a carta e PARA
python tools/upwork/upw2.py js "<javascript>"         # executa JS na página
```

### Três armadilhas do formulário da Upwork

Descobertas quebrando a cara, e cada uma custa um envio que falha em silêncio.

**O "Schedule a rate increase" é obrigatório**, mesmo escrito *optional*. Em vaga por hora,
sem escolher frequência o envio falha dizendo só "Please fix the errors below", sem apontar
onde. `Never` resolve.

**O lance de posição tem botão "Set bid" separado.** Digitar o número no campo não aplica
nada. Sem clicar, o site usa o valor anterior e reclama.

**Setter nativo de JavaScript não aciona o framework deles em todo campo.** Em `textarea`
funciona; em alguns `input` o campo fica visivelmente preenchido e o formulário continua
dizendo que está vazio. Nesses, só `fill` de verdade (via `set`) registra.

E uma de método: **clique não é prova de envio.** Confirme sempre na lista de propostas
enviadas ou na mudança de URL. Duas vezes o clique "funcionou" e nada foi enviado.

### Pontuação de vagas

`tools/upwork/pontuar.py` filtra antes de você gastar Connects. Ajuste no topo do arquivo:

- `PISO_HORA` e `PISO_FIXO` — abaixo disso nem lê
- `VETO_TEXTO` — o que elimina na hora (anos de experiência que você não tem, exigência de
  residir em outro país, tecnologia que você não domina)
- `VETO_SKILL` — habilidades que você não vende

**O melhor previsor de vaga boa não é o orçamento anunciado, é o `$/h médio que o cliente
já pagou`.** Um cliente pedindo especialista em CAPI com descrição impecável pagava
**US$5,74/hora** de média em 625 vagas publicadas. A descrição seduz; o histórico não mente.

---

## Parte 3 — Redação de tela para portfólio

`tools/redacao/redigir.js` troca nome de cliente, ID de conta e telefone por rótulo neutro
**na tela**, antes do print.

Cole no Console (F12) antes de gravar ou printar. Ele continua trocando conforme a página
se redesenha, e cobre também `title` e `aria-label`, que aparecem no hover e são o vazamento
mais comum.

A tabela NAO fica no `redigir.js`. Copie `tools/redacao/mapa.example.js` para
`mapa.local.js` (gitignored), preencha com os seus termos, e no Console cole
`mapa.local.js` PRIMEIRO e `redigir.js` depois.

A separacao existe porque a tabela lista, em texto puro, exatamente o que deve ser
escondido: nome de cliente, id de conta, telefone. Versionar a tabela publica o
segredo que a ferramenta protege.

**A regra que economiza retrabalho: capture cru, redija na publicação.** Dá para tirar
informação depois; não dá para recuperar o que não foi capturado.

---

## O que este repositório não faz

- Não envia proposta, não aceita oferta, não responde recrutador
- Não guarda credencial: tudo vem de variável de ambiente
- Não versiona currículo, resposta, print ou dado pessoal — veja o `.gitignore`

## Se for usar de verdade

Comece pela **Parte 1**, com `gmail_vagas.py tudo 7`. Ele varre sua caixa dos últimos 7 dias e
mostra o padrão real: quanto é ruído, quanto é alerta, quanto é pipeline de verdade.

Você vai descobrir que o número de e-mails que realmente importam é menor do que imagina, e
que provavelmente já perdeu alguma coisa. Foi assim que este projeto começou.
