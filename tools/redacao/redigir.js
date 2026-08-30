// Cola no Console (F12) ANTES de comecar a gravar, em CADA aba que vai aparecer.
// Troca o nome do cliente por rotulo neutro nos nos de texto e continua trocando
// conforme a SPA re-renderiza (Google Ads e Meta redesenham a tela toda hora).
(function () {
  // A tabela NAO vive aqui. Ela lista em texto puro o que deve ser escondido: nome de
  // cliente, id de conta, telefone, nome de pessoa. Versionar isso publica o segredo que
  // a ferramenta protege. Cole mapa.local.js no Console antes deste arquivo.
  var MAPA = window.MAPA_REDACAO;
  if (!MAPA || !MAPA.length) {
    console.error("[redacao] Cole mapa.local.js PRIMEIRO. Sem tabela, nada e' mascarado " +
                  "e a gravacao sai com os dados reais na tela.");
    return;
  }

  function limpar(raiz) {
    var w = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT, null, false);
    var nos = [], n;
    while ((n = w.nextNode())) nos.push(n);
    for (var i = 0; i < nos.length; i++) {
      var t = nos[i].nodeValue, o = t;
      for (var j = 0; j < MAPA.length; j++) {
        if (t.indexOf(MAPA[j][0]) !== -1) t = t.split(MAPA[j][0]).join(MAPA[j][1]);
      }
      if (t !== o) nos[i].nodeValue = t;
    }
    // atributo tambem vaza: tooltip e aria-label aparecem no hover durante a gravacao
    var els = raiz.querySelectorAll ? raiz.querySelectorAll("[title],[aria-label]") : [];
    for (var k = 0; k < els.length; k++) {
      ["title", "aria-label"].forEach(function (a) {
        var v = els[k].getAttribute(a);
        if (!v) return;
        var o2 = v;
        for (var j = 0; j < MAPA.length; j++) {
          if (v.indexOf(MAPA[j][0]) !== -1) v = v.split(MAPA[j][0]).join(MAPA[j][1]);
        }
        if (v !== o2) els[k].setAttribute(a, v);
      });
    }
  }

  function titulo() {
    var t = document.title;
    for (var j = 0; j < MAPA.length; j++) {
      if (t.indexOf(MAPA[j][0]) !== -1) t = t.split(MAPA[j][0]).join(MAPA[j][1]);
    }
    if (t !== document.title) document.title = t;
  }

  limpar(document.body); titulo();
  new MutationObserver(function (ms) {
    for (var i = 0; i < ms.length; i++) {
      for (var j = 0; j < ms[i].addedNodes.length; j++) {
        var n2 = ms[i].addedNodes[j];
        if (n2.nodeType === 1) limpar(n2);
      }
      if (ms[i].type === "characterData") limpar(document.body);
    }
    titulo();
  }).observe(document.body, { childList: true, subtree: true, characterData: true });

  console.log("%credacao ativa — confere na tela antes de gravar", "color:#0a0;font-weight:bold");
})();
