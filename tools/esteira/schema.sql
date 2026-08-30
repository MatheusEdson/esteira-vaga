-- Esteira de vagas: armazenar primeiro, classificar depois.
--
-- POR QUE SEPARAR. Antes o script buscava e classificava na mesma passada, entao melhorar
-- uma regra exigia baixar tudo de novo, e o que passou batido ficava perdido pra sempre.
-- Com o e-mail no banco, classificar vira funcao pura: melhora a regra, roda de novo em
-- cima do que ja esta aqui, custo zero de API e nada se perde.
--
-- Convencao de nome segue o resto do projeto pessoal (ares_, cfo_, planner_).

create table if not exists vagas_emails (
  id              text primary key,        -- id da mensagem no Gmail, natural e estavel
  thread_id       text not null,
  data            timestamptz,
  remetente       text,                    -- "Nome <email>" como veio
  remetente_email text,                    -- so' o endereco, minusculo, pra agrupar
  assunto         text,
  corpo           text,                    -- NULL quando o remetente esta na lista de ruido
  eu_mandei       boolean not null default false,

  -- Derivado. Pode ser recalculado a qualquer momento a partir de assunto+corpo.
  estado          text,                    -- OFERTA, EXPIRANDO, convite, entrevista, ...
  acoes           text[] not null default '{}',
  ruido           text,                    -- motivo do corte, quando cortado
  versao_regra    int,                     -- versao do classificador que gerou o acima
  classificado_em timestamptz,

  -- Fluxo humano.
  visto           boolean not null default false,
  visto_em        timestamptz,
  nota            text,                    -- anotacao dele sobre a mensagem

  criado_em       timestamptz not null default now()
);

-- Reclassificar so' o que ficou pra tras da versao atual.
create index if not exists vagas_emails_versao_idx on vagas_emails (versao_regra);
-- A tela de leitura em batch: o que importa e' o nao-visto com estado.
create index if not exists vagas_emails_fila_idx
  on vagas_emails (visto, data desc) where ruido is null;
create index if not exists vagas_emails_estado_idx on vagas_emails (estado)
  where ruido is null;
create index if not exists vagas_emails_thread_idx on vagas_emails (thread_id);
create index if not exists vagas_emails_remetente_idx on vagas_emails (remetente_email);

-- Ponteiro de sincronizacao incremental. Uma linha so'.
-- O Gmail da' o delta desde um historyId em vez de reler a caixa: e' o que faz o cron
-- custar quase nada. `historyId` do Gmail expira depois de ~1 semana sem uso, entao
-- guardar tambem a data permite cair pra varredura por janela quando ele morre.
create table if not exists vagas_sync (
  id            int primary key default 1,
  history_id    text,
  ultimo_sync   timestamptz,
  ultimo_erro   text,
  mensagens     int not null default 0,
  constraint vagas_sync_uma_linha check (id = 1)
);

insert into vagas_sync (id) values (1) on conflict (id) do nothing;
