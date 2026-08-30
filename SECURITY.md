# Segurança

Este repositório automatiza uma busca de emprego, então ele lida com identidade, currículo
e credencial de portal. As regras abaixo são cumpridas por código, não por disciplina.

## O que nunca é versionado

| O quê | Onde fica | Como é garantido |
|---|---|---|
| Identidade, pretensão, empregador | `data/perfil.json` | `.gitignore` cobre `**/perfil.json` |
| Currículo, anexo, respostas dissertativas | `curriculos/`, `anexos/`, `respostas/` | `.gitignore` |
| Credencial | variável de ambiente ou `.env` | `.gitignore` cobre `.env*` e `env.sh` |
| Segredo de OAuth do Google | onde `GMAIL_CLIENT_SECRET` apontar | `.gitignore` cobre `*oauth*client*.json` |
| Sessão de navegador (cookie do LinkedIn, Upwork) | `_perfil-nav/`, `_perfil-edge/` | `.gitignore` cobre `**/_perfil-*/` |
| Tabela de mascaramento de tela | `tools/redacao/mapa.local.js` | `.gitignore` |

**Campo vazio aborta o adaptador.** Ele nunca inventa resposta para destravar formulário.

## Duas barreiras, não uma

`.githooks/pre-commit` bloqueia credencial de provedor (AWS, GitHub, Google, Slack, Stripe,
Brevo), chave privada, JWT, string de conexão com senha, CPF, telefone e cartão. Ele é a
primeira barreira e **não basta**: só vê o que está staged, e `--no-verify`, um clone sem
`git config core.hooksPath .githooks`, ou um commit pela interface do GitHub passam por
cima dele.

Por isso o job `segredos` do CI roda a mesma verificação contra a **árvore inteira**, no
servidor, onde não dá para pular.

## Escopo do acesso ao Gmail

`gmail.readonly`. Não envia, não responde, não arquiva, não apaga. O token do OAuth fica na
máquina de quem roda e não passa por servidor nenhum.

⚠️ App em publishing status **Testing** tem refresh token que expira em 7 dias. Para rodar
em cron, publique o app.

## Limites conhecidos

- O gate da instância publicada (`deploy/nginx.conf`) tem a chave **cravada no arquivo** e
  ela viaja na query string, o que a coloca no log do nginx e no histórico do navegador.
  Serve para esconder de indexador, não para conter alguém determinado.
- `PUT /api/perfil` e `DELETE /api/arquivos/...` não têm autenticação própria: dependem
  desse gate. `core/store.py` previne path traversal e limita extensão e tamanho, então o
  dano fica contido às pastas de anexo.

## Reportar

Abra uma issue **sem incluir** o dado sensível que a motivou.
