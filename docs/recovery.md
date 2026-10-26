# Recuperação após interrupção

Recuperação é explícita. Reinício, desconexão ou queda durante captura/processamento
não pode reabrir o microfone silenciosamente.

O bridge mantém journal local por `request_id` e sessão ativa. Ao iniciar depois de
`recording` ou `paused`, ele passa para `recovery/interrupted`. O backend marca sessões
abertas no startup como `recovery` com `backend_restarted`. O presenter e o touch
devem oferecer retomar ou descartar.

`recover resume` prepara a sessão para uma retomada comandada. `recover analyze`
reusa transcrição já persistida quando a falha ocorreu depois do ASR. `discard` remove
a sessão recuperável confirmada. Reenvio do mesmo `request_id` devolve estado/resultado
existente; payload divergente conflita.

Quando uma sessão já está `completed` com `audio_cleanup_failed`, `recover analyze`
é uma ação de limpeza: tenta remover áudio bruto pendente e limpar o erro sem repetir
transcrição, extração de tópicos ou métricas.

Resultado atrasado de outra sessão, ACK antigo ou `completed` sem sessão válida não
gera sucesso. A reconciliação exige `session_id`, estado, generation e origem compatíveis
entre bridge, backend e banco.

Se a jornada já entrou em transcrição, tópicos ou resultado, recuperar encaminha ao
worker de análise sem abrir microfone. Cancelamento invalidado por geração impede
que resultados tardios ressuscitem a sessão. Uma nova tentativa requer autoteste válido.
