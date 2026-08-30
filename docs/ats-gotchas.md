# Armadilhas por ATS

Conhecimento acumulado aplicando em vaga real. Cada item custou tempo de depuracao, e
varios custaram uma tentativa perdida em formulario com anti-bot que aceita um envio so'.

Compilado das candidaturas reais registradas em `data/enviadas.json` (gitignored).
Cada entrada e um formulario que quebrou de um jeito especifico.

## A regra que vale para todos

**Texto de sucesso na tela nao prova envio. A prova e' um POST de submissao com 2xx.**

Ja vi formulario mostrar mensagem de sucesso sem ter enviado nada, e endpoint de telemetria
devolver 201 com o formulario VAZIO. Quando houver anti-bot na frente, preencha por script
e deixe o clique final para o humano na PRIMEIRA tentativa: rodada de teste queima cota e o
clique seguinte volta 429.

## Ashby  _(3 casos)_

**Agent Careers**

Cover letter era UPLOAD DE ARQUIVO, não textarea. Gerei cover-letter-agent.pdf para isso.

**ElevenLabs**

O primeiro submit não pegou: precisa scroll_into_view antes do clique. Confirmar pelo sumiço do botão, não por texto.

**Ruby Labs**

CONCLUSAO ESTRUTURAL: Ashby nao aceita envio automatizado, 5 de 5 tentativas. Parar de gastar tempo tentando; rotear Ashby direto para envio manual com as respostas prontas.


## Teamtailor  _(3 casos)_

**Floowi (staffing LATAM para agências dos EUA)**

Salário é input[type=range]. 'full_email' é HONEYPOT, tem que ficar vazio. O consent só valida com check() do Playwright no input[type=checkbox]; JS checked=true e o hidden do Rails com o mesmo name não funcionam ('Must be accepted').

**Bionic Talent**

O adaptador ABORTOU na primeira passada por 2 perguntas sem resposta verdadeira (WordPress dissertativa e Figma). O guardrail funcionou como projetado.

**Bionic Talent**

FALHA MINHA: esta candidatura saiu nomeando '(empregador)' com link, mais '(empregador)' com link, porque o campo experiencia_agencia_texto do perfil.json ficou desatualizado quando os CVs foram renomeados para 'Stealth Startup'. O CV anexado e a resposta dissertativa se contradizem para o mesmo recrutador. Corrigido no perfil DEPOIS deste envio (decisao dele em 18/08: padronizar em Stealth Startup, nunca nomear). Nao ha como retirar o que ja foi enviado nesta.


## LinkedIn Easy Apply  _(2 casos)_

**Jobgether (em nome de empresa parceira, nao nomeada no anuncio)**

Primeiro Easy Apply enviado da esteira. Confirmacao NAO aparece em /my-items/saved-jobs?cardType=APPLIED com o seletor que tentei (devolveu 0 itens); a prova confiavel e' reabrir a pagina da vaga e procurar 'Candidatura enviada' (script auxiliar local).

**Emerging Travel Group**

ACHADO REAPROVEITAVEL: a pergunta customizada 'Where are you currently located?' RECUSOU '(sua cidade), MG, Brasil' com 'Please enter a valid answer' e ACEITOU '(sua cidade), Brazil'. O campo rejeita acento. Corrigido no aplicar_easyapply.py, que agora manda o valor em ASCII com o pais em ingles.


## careers-page.com (Manatal)  _(1 caso)_

**TalentHQ (staffing p/ empresas dos EUA; recrutadora a recrutadora, o e-mail de contato da vaga)**

- 1) FILTRO DE ATENCAO: a vaga instrui responder literalmente uma palavra-chave na pergunta 'Why should we consider YOU for this position?'. O campo e input de UMA linha, o que confirma que esperam so a palavra. Escrever paragrafo la = falhar no teste.
- 2) O formulario so existe depois de clicar o botao Apply (button.btn-lg); antes disso a pagina tem 0 campos visiveis e os labels vem como template Angular '[[ field.label ]]'.
- 3) IDs de campo comecam com digito (1530182), entao seletor CSS '#1530182' e INVALIDO; usar input[name='...'].
- 4) NAO afirmar LinkedIn Ads (NUNCA_AFIRMAR): o requisito e OR entre Google/Meta/LinkedIn/Programmatic e Google+Meta ja satisfaz.


## Deel (jobs.deel.com)  _(1 caso)_

**AtomChat (conversational commerce / WhatsApp, LatAm)**

- SETE, todos no adaptador aplicar_deel_atomchat.py:
- 1) LIMITE DE 500 CARACTERES nas dissertativas, e o campo NAO declara maxLength: aceita o texto todo em silencio, marca aria-invalid=true sem mensagem no campo, e o botao Apply fica disabled para sempre. Achado por bissecao (498 valido, 598 invalido); o contador '480/500' existe na tela mas passa batido.
- 2) O parser de CV da Deel SOBRESCREVE firstName/lastName: subir o PDF ANTES de preencher os textos, senao lastName virava 'Nome DoMeio Sobrenome'.
- 3) O campo de preaviso e inputmode=numeric com min=10 max=100, ou seja DIAS: '2 weeks' virava '2' e reprovava por ficar abaixo do minimo; o certo e '14'.
- 4) O dial code e combobox com autocomplete (role=combobox), nao aceita fill puro: clicar, digitar 'Brazil', ArrowDown, Enter.
- 5) O checkbox de consentimento NAO TEM ROTULO nenhum; casar por indice (e o ultimo dos 11), nao por texto.
- 6) Existem DOIS botoes 'Apply' e o .last e INVISIVEL: iterar e pegar o primeiro visivel E habilitado.
- 7) O MUI valida no blur e as vezes deixa campo preenchido como aria-invalid: precisa de um passe de reprocessamento (re-fill + Tab) nos que ficarem invalidos.


## GoHighLevel / LeadConnector  _(1 caso)_

**Contractor Liberty**

- 1) O campo Country e um vue-multiselect: o input real tem width:0 e position:absolute, invisivel e nao clicavel. Setar .value nao registra no estado do Vue e o form devolve 'Country is required' com o campo mostrando Brazil. Fix: clicar em div.multiselect:has(#country), digitar, ArrowDown, Enter.
- 2) Os radios NAO tem atributo name; o id vem como '<opcao>_<grupo>_<indice>_<formId>', entao a chave do grupo e o 2o segmento do id.
- 3) O botao SUBMIT e um <div class='ghl-btn ghl-submit-btn'>, nao um <button>.
- 4) IMPORTANTE: o POST para backend.leadconnectorhq.com/forms/form-survey-event sai com 201 mesmo em formulario VAZIO, entao NAO e prova de envio. A prova e um POST de submissao real; aqui nao houve nenhum, so challenges.cloudflare.com repetindo 8x com 200. Adaptador: aplicar_contractorliberty.py


## Greenhouse  _(1 caso)_

**Wellhub (ex-Gympass)**

3 tentativas falharam antes. (1) O campo de detalhe da declaração de conflito é TEXTAREA e meu preenchedor só varria input[type=text]. (2) O id de um combobox tem colchetes (question_...[]), que quebra o seletor CSS '#id'; usar [id="..."]. (3) A lista de erros do Greenhouse mistura rótulo de campo obrigatório com erro real, então só o screenshot revela o que falta.


## inhire  _(1 caso)_

**Radix**

- 1) Cidade e País são react-dropdown-select: o input[name] é opacity:0 e .fill() NÃO registra no estado do React. Tem que clicar no wrapper div.react-dropdown-select, digitar, e clicar em button[role=option].
- 2) O data-option-value do país é o ISO ('BR'), mas nas perguntas de diversidade é UUID: casar pelo rótulo visível.
- 3) O form valida as DUAS etapas juntas: 'Avançar' fica disabled enquanto a pergunta de grupos da etapa 2 estiver vazia, o que engana o diagnóstico.
- 4) Score 66, o mais alto do lote.


## widget de chat conversacional (ClickFunnels)  _(1 caso)_

**ScalePrediction (Sell More Loans)**

Os campos cf_contact_number/month/year/cvc na pagina sao boilerplate de template do ClickFunnels, NAO cobranca. Verificado: a pagina tem 5 estudos de caso com clientes nomeados, foto de equipe e nenhuma taxa.


## Workable em dominio proprio  _(1 caso)_

**Hire Overseas (staffing para clientes dos EUA)**

- 1) Envio automatizado barrado: Workable tem backdrop [data-ui=backdrop] que engole o clique no submit E anti-bot da Cloudflare.
- 2) Portfolio precisava ser LINK publico, nao anexo: publicado em https://seudominio.com/portfolio/ (noindex) no vps2b.
- 3) O resumo por IA do Loom escreveu 'Anthony Argos' e '50 client accounts' no video de 17/08; regenera a cada gravacao, conferir sempre antes de mandar o link.

