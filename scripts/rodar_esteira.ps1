# Esteira de candidaturas: roda 2x por semana pelo Agendador de Tarefas do Windows.
# Chama o Claude Code em modo headless com o procedimento do docs\rotina.md.

$base = "<raiz-do-repo>"
$log  = Join-Path $base "_logs"
New-Item -ItemType Directory -Force $log | Out-Null

# O Agendador inicia o processo em C:\WINDOWS\system32. Sem isto, o Claude headless
# nega TODA leitura em <raiz-do-repo> (fora do diretorio permitido) e a rotina
# morre no passo zero com exit 0, parecendo sucesso. Falhou assim em 13/08 e 17/08.
Set-Location $base

# C: vive sem espaco nesta maquina: browser e escrita precisam do TEMP em D:
$env:TEMP = "$base\_tmp"
$env:TMP  = "$base\_tmp"
New-Item -ItemType Directory -Force $env:TEMP | Out-Null

$stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
$saida = Join-Path $log "esteira_$stamp.log"

# O MCP do Apify e um daemon SSE em localhost:3006 e NAO sobe sozinho no boot. Se a maquina
# foi reiniciada desde o ultimo uso, a porta esta fechada e o passo 1 fica sem scraper.
$daemons = "$env:USERPROFILE\.claude\start-mcp-daemons.ps1"
if (-not (Test-NetConnection 127.0.0.1 -Port 3006 -WarningAction SilentlyContinue).TcpTestSucceeded) {
    if (Test-Path $daemons) {
        Start-Process powershell.exe -ArgumentList @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$daemons`""
        ) -WindowStyle Hidden
        # o daemon precisa de uns segundos para abrir a porta antes do claude subir
        for ($i = 0; $i -lt 20; $i++) {
            Start-Sleep -Seconds 3
            if ((Test-NetConnection 127.0.0.1 -Port 3006 -WarningAction SilentlyContinue).TcpTestSucceeded) { break }
        }
    }
}

$prompt = @'
Execute a rotina de candidaturas do dono do perfil.

Leia primeiro, nesta ordem:
  <raiz-do-repo>\docs\rotina.md     (o procedimento passo a passo)
  <raiz-do-repo>\data\perfil.json   (banco de respostas, filtros e o que NUNCA pode ser afirmado)
  <raiz-do-repo>\data\enviadas.json (nao repetir vaga ja enviada ou marcada como NAO ENVIAR)

Siga o docs\rotina.md a risca. Pontos inegociaveis:
- Auto-envio esta autorizado para vagas acima do corte de score.
- NUNCA preencha campo obrigatorio com afirmacao que nao esteja no perfil.json. Se nao houver
  resposta verdadeira, a vaga vai para <raiz-do-repo>\data\fila.md com a pergunta literal, e voce
  segue para a proxima. Nao invente experiencia.
- Rode o adaptador em dry-run e confira o estado impresso ANTES de enviar.
- Atualize enviadas.json a cada envio.

Feche com um relatorio curto: descobertas, aprovadas no filtro, enviadas com link, em fila e por que.
Lembre no fim que candidatura em Teamtailor so conta depois que ele clica no link de verificacao no
e-mail seu-email@exemplo.com.
'@

"=== esteira $stamp ===" | Out-File -FilePath $saida -Encoding utf8
try {
  # O MCP do Apify vive em <caminho do seu .mcp.json>, escopo de PROJETO.
  # Rodando com cwd nesta pasta, a sessao nunca carrega aquele arquivo e o passo 1 morre sem
  # scraper. mcp-esteira.json carrega SO o apify, explicitamente.
  # acceptEdits libera EDICAO, nao execucao nem rede. Sem allowedTools a esteira le o perfil
  # e nao consegue rodar adaptador, scraper nem abrir pagina de vaga. Escopo estreito de
  # proposito: python (os adaptadores Playwright) e as duas ferramentas de web. Nenhum outro
  # comando de shell, porque isto roda 2x por semana sem ninguem olhando.
  & claude -p $prompt --add-dir $base --mcp-config "$base\deploy\mcp-esteira.json" `
      --allowedTools "Bash(python:*)" "WebFetch" "WebSearch" `
      --permission-mode acceptEdits *>&1 |
      Out-File -FilePath $saida -Append -Encoding utf8
  "=== fim, exit=$LASTEXITCODE ===" | Out-File -FilePath $saida -Append -Encoding utf8

  # Canario: se o log nao mencionar envio nem fila, a rodada nao produziu nada.
  # Sem isto o Agendador reporta 0 (sucesso) mesmo quando a rotina morre no passo zero.
  # O sinal de saude e DESCOBERTAS, nao fila nem envio: "0 descobertas" significa que o
  # passo 1 (scraper) nao rodou. Fila alta com 0 descobertas e justamente o caso que a
  # versao anterior deste canario deixava passar, porque so olhava envio e fila.
  $txt = Get-Content $saida -Raw
  if ($txt -notmatch 'Descobertas:\s*\**\s*[1-9]') {
      "=== ALERTA: 0 descobertas. O passo 1 nao rodou (scraper, MCP ou permissao). ===" |
          Out-File -FilePath $saida -Append -Encoding utf8
  }
} catch {
  "=== ERRO: $($_.Exception.Message) ===" | Out-File -FilePath $saida -Append -Encoding utf8
}
