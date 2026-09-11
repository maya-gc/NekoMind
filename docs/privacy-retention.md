# Privacidade, retenção e exclusão

O padrão do MVP é local e offline. O backend, o bridge, o banco SQLite, os chunks,
o áudio bruto, o journal e o token ficam sob `backend/storage/` ou no diretório Mac
configurado. Nada deve ser enviado à nuvem sem autorização específica.

`NEKOMIND_RETAIN_RAW_AUDIO=false` é o padrão. Após transcrição e persistência
bem-sucedidas, o backend remove os arquivos brutos referenciados da sessão. Quando
`true`, os arquivos permanecem para inspeção local.

Se a análise terminar com sucesso mas a limpeza de áudio falhar, a sessão permanece
`completed` e recebe `error_code=audio_cleanup_failed`. Isso preserva resultado,
tópicos e métricas já gravados. `POST /api/v1/sessions/{id}/recover` com
`{"action":"analyze"}` nesse caso apenas tenta limpar o áudio pendente e remover o
erro; não repete ASR, tópicos ou métricas.

Exclusão confirmada remove, no escopo local conhecido da sessão:

- linha `StudySession`;
- chunks e temporários sob `storage/audio/session_<id>`;
- dados do diretório Mac `mac/session_<id>` quando configurado;
- transcrição, tópicos, métricas e histórico do assunto daquela sessão.

Se a exclusão falhar depois de marcar `deletion_pending`, o tombstone permanece para
permitir repetir a limpeza com segurança. Enquanto tombstoned, a sessão não deve entrar
em processamento nem ser tratada como íntegra.

O journal Mac preserva identidade de comandos para idempotência, mas respostas ligadas
à sessão excluída são substituídas por tombstone `session_deleted`, sem resumo, tópicos
ou dados do visitante. Recibos operacionais do backend também são removidos ou
esvaziados quando apontam para a sessão apagada.

A garantia não alcança cópias externas, snapshots de backup, SSD/TRIM, Time Machine,
screenshots, exports, logs fora do diretório do projeto ou arquivos movidos pelo
operador. Sessões ativas ou recuperáveis exigem fluxo próprio para evitar apagar dados
necessários à retomada.

Não registrar áudio real, transcrição pessoal, token, `.env`, banco local ou caminhos
sensíveis em Git, QA público, fixtures ou mensagens de erro.
