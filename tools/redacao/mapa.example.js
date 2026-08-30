// Tabela de mascaramento. COPIE para mapa.local.js e preencha com os SEUS valores.
//
// Por que este arquivo existe separado: a tabela lista, em texto puro, exatamente aquilo
// que voce quer esconder. Nome de cliente, id de conta de anuncio, telefone, nome de
// pessoa. Versionar a tabela publica o segredo que a ferramenta deveria proteger, e foi
// isso que aconteceu aqui antes desta separacao.
//
// mapa.local.js esta no .gitignore. Ele nunca sobe.
//
// Uso: no Console (F12), cole PRIMEIRO o conteudo de mapa.local.js, depois redigir.js.

window.MAPA_REDACAO = [
  // ---- Conta A (Google) ----
  ["NomeDoCliente", "CLIENT A"], ["nomedocliente.com", "clienta.com"],
  ["000-000-0000", "000-000-0000"],          // id da conta, com e sem hifen
  ["0000000000", "0000000000"],

  // ---- Conta B (Meta) ----
  ["Outro Cliente", "CLIENT B"], ["outrocliente", "clientb"],
  ["000000000", "000000000"],                 // pixel
  ["0000000000000000", "0000000000000000"],   // conta de anuncio
  ["00000-0000", "00000-0000"],               // telefone que aparece no CTWA

  // ---- nomes de pessoa que aparecem em log de alteracao ----
  ["Nome", "—"], ["Sobrenome", "—"]
];
