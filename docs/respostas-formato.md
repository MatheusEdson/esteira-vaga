# Formato de `respostas/`

As respostas dissertativas ficam fora do código, em `respostas/`, que é **gitignored**.

## Por quê

Elas carregam número. Verba mensal de mídia do empregador, retorno de conta de cliente,
volume de leads processados. Numa candidatura privada isso é o que te faz ser levado a
sério. Num repositório público é dado de terceiro que você não tem o direito de publicar,
e contradiz o que o README promete sobre nada pessoal ficar no código.

Antes desta separação eram 9 blocos e cerca de 6.400 caracteres embutidos nos adaptadores.

## Formato

Um arquivo por adaptador, com o nome do adaptador sem o prefixo `aplicar_`:

```
adapters/aplicar_deel_atomchat.py  ->  respostas/deel_atomchat.md
core/preencher_workable.py         ->  respostas/workable.md
```

Dentro, uma seção `##` por resposta, com o nome exato da constante que o adaptador pede:

```markdown
## OUTBOUND_DESAFIO

O texto da resposta, do jeito que vai para o formulário.
Pode ter várias linhas e parágrafos.

## ANOS_GTM

Outra resposta.
```

## O que acontece se faltar

O adaptador **aborta antes de abrir o navegador**, dizendo qual arquivo ou qual seção
falta. Nunca envia formulário com campo vazio.
