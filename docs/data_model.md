# Persistência do MVP

`StudySession` relaciona 1:N com `Topic`, `Metric` e `AudioChunk`. Estados persistidos:
`recording`, `paused`, `processing`, `completed`, `error`, `recovery` e `cancelled`.
Transcrição, tópicos e métricas finais pertencem sempre ao id da sessão. A transação
de conclusão grava o conjunto final; falha não deve deixar nota ou tópicos de uma
análise incompleta.

- `start_request_id` tem unicidade (não nulos); `request_id` mantém compatibilidade.
  Payload divergente com o mesmo pedido retorna409. `finish_request_id` registra a
  solicitação que adquiriu o processamento; consultas/reenvios não criam nova análise.
- `capture_source` identifica `mac_microphone`; `device_session_id` é metadado opcional.
- `mode`, `asr_provider_config`, `topic_provider_config` congelam modo/provedores no início.
  `asr_provider_used`, `topic_provider_used` registram etapas realmente executadas.
  A origem ASR fica registrada mesmo se a extração falhar depois.
- `is_demo` é verdadeiro em demo ou quando qualquer adaptador executado é simulado.
  `analysis_origin` resume a classificação. Origem legada ausente é desconhecida;
  `is_demo=false` sozinho não comprova execução real.
- `audio_validation`/`speech_validation` preservam compatibilidade entre consumidores;
  guardam JSON resumido do gate de fala quando executado. `error_code`/`error_message`
  apresentam falhas sem logs internos nem conteúdo da explicação.
- `subject`, `subject_confirmed` e `metric_method_version` sustentam histórico por
  assunto. Somente sessões completadas, confirmadas e do mesmo método entram na tendência.
- `journey_json` registra etapas reais `capture`, `transcription`, `topics` e `result`
  com status, duração, provider e `is_demo`.
- `deletion_pending` é marcado antes de remoção confirmada para tornar falha parcial
  visível e evitar tratar a sessão como íntegra.

`Experience` é singleton operacional para touch/público/presenter: guarda `generation`,
sessão atual, estado, modo feira, heartbeat, diagnósticos, voz compacta e calibração
sanitizada. `OperatorCommand` guarda comandos locais por `request_id`, payload, resposta
resumida e status. O journal não deve conter áudio, transcrição completa ou token. Quando
uma sessão é excluída, recibos que apontam para ela são removidos ou têm resposta
limpa; no journal Mac, a resposta vira tombstone `session_deleted` para preservar
idempotência sem manter conteúdo do resultado.

## Áudio e concorrência

`AudioChunk` registra sessão, sequência, formato, taxa, tamanho e caminho. Existe índice
único `(session_id, sequence)`. O upload adquire transação SQLite `BEGIN IMMEDIATE`,
reconfere estado e conteúdo. Mesma sequência/bytes devolve registro existente;
conteúdo diferente ou lacuna falha. A análise adquire estado `processing` por UPDATE
condicional; outra finalização recebe o estado existente. Apenas chunks referenciados
pelo banco entram no merge; arquivos órfãos de interrupção não são áudio confirmado.
Arquivos são imutáveis por tentativa. Falhas normais limpam o arquivo da tentativa;
crash de processo pode deixar órfãos para inspeção/remoção manual, sem excluir dados antigos.
Quando `retain_raw_audio=false`, a conclusão bem-sucedida remove os arquivos brutos
referenciados após transcrição/persistência. A garantia cobre diretórios locais conhecidos
da sessão; cópias externas, backups fora do diretório e arquivos movidos manualmente
não são apagados pelo backend.
Falha nessa limpeza não desfaz a análise já concluída: a sessão permanece `completed`
com `error_code=audio_cleanup_failed` até uma recuperação `analyze` limpar o áudio
pendente.

O journal separado do bridge armazena payload/recibo por `request_id` e a sessão ativa.
É necessário preservar o journal em reconexões. Reinício nunca abre microfone sozinho.
Dados do journal, gravações e backups não são versionados.
Exclusão confirmada usa `deletion_pending` como tombstone antes de apagar arquivos e
linhas; falha parcial permite repetir a exclusão sem reprocessar a sessão.

## Migração de banco existente

`init_db()` inspeciona colunas, executa a migração aditiva versionada
`20260911_nm019_backend_lifecycle`, cria tabelas ausentes, garante índices e registra
interrupções. `create_all()` não é usado como migração de colunas. Antes de adicionar
colunas, a API SQLite de backup cria `nekomind.db.bak-<timestamp>` consistente com WAL.
Se backup falha, migração para. Nenhum registro antigo é apagado; origem não conhecida
não é fabricada. Duplicatas legadas que impeçam índice único bloqueiam inicialização,
exigindo inspeção, sem deduplicação destrutiva automática.

Executar com backend/bridge anteriores parados e um único worker. No startup, sessões
em recording/paused/processing recebem `recovery` e `backend_restarted`. Isso é
recuperação conservadora, não retomada automática. Bancos novos também recebem índices únicos.
Somente SQLite foi implementado/testado para esta estratégia; trocar URL para PostgreSQL
não oferece equivalência garantida.

## Rollback

Parar backend e bridge. Preservar uma cópia do banco/áudio/journal atuais antes de
qualquer restauração. Para voltar à versão antiga, selecionar explicitamente o backup
anterior à migração e restaurá-lo com os processos parados; não misturar arquivos WAL/SHM
do banco novo. A restauração perde sessões posteriores ao backup se não forem guardadas
separadamente. Preferir correção aditiva quando houver novos dados. Não há down migration
automática ou comando que apague dados em execução.

`DeletedSessionTombstone` conserva IDs de sessão e de pedido excluídos, sem conteúdo.
A alocação de sessão adquire `BEGIN IMMEDIATE` antes de calcular o próximo ID,
considerando sessões vivas e tombstones. IDs excluídos não voltam a identificar outro visitante.
