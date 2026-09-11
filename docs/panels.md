# Superfícies web

`/touch` é o emulador local do display. Ele lê o snapshot de experiência e só envia
comandos quando o operador informa o token local em memória. O token não é salvo em
`localStorage` e não deve aparecer em URL. O emulador existe para QA, demonstração e
operação local enquanto o touch físico não estiver validado.

O frontend está em `frontend/web`: `src/api.mjs` encapsula chamadas HTTP, `src/app.mjs`
coordena rotas e token em memória, `src/state.mjs` sanitiza snapshots/modelos de tela,
`src/render.mjs` renderiza touch, público e presenter, e `styles.css` define os layouts.
Comandos são enviados por `/api/v1/experience/commands` e acompanhados por
`/api/v1/experience/commands/{request_id}` até ACK do Mac ou timeout local.

`/public` é a tela de TV/monitor. Ela consulta `/api/v1/experience/public` sem token e
é somente leitura. Mostra estado do gatinho, modo real/demo, jornada, tópicos e
resultado público. Não mostra transcrição completa, áudio, token, controles de reset,
cancelamento, diagnóstico administrativo ou dados do visitante anterior após reset.

`/presenter` é reservado à equipe. Ele solicita o token local, mantém o valor em memória
da página e consulta `/api/v1/experience/presenter`. Pode repetir diagnóstico, calibrar,
cancelar, recuperar, descartar e resetar com confirmação. Não deve mostrar áudio bruto,
transcrição completa ou segredos por padrão.

Streamlit permanece como histórico local. O cliente lê o token em `storage/operator-token`
para chamar rotas privadas em loopback e continua sem captura de navegador.

A confirmação destrutiva usa diálogo na página, com Confirmar/Voltar, Escape e foco
restrito ao diálogo. A fila mantém pedido pendente até recibo do Mac. Nova tentativa
usa `retry` e novo request_id; reset limpa navegação e rascunhos do visitante.
