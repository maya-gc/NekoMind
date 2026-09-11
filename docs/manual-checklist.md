# Checklist manual de validação

Este checklist é para execução humana/local depois da integração final. Não substitui
`docs/qa-report.md`.

- Confirmar branch, `.env` sem segredos, backend em `127.0.0.1` e token `0600`.
- Abrir `/public`, `/presenter` e `/touch`; colar token somente no presenter/touch.
- Verificar viewports 240x320 e 320x240: rosto visível, texto sem corte, botões >=44px.
- Rodar diagnóstico em demo e real local; modelo ausente deve falhar claro.
- Iniciar pelo touch; só mostrar gravando após confirmação do Mac.
- Testar voz normal, baixa e clipping com consentimento se usar microfone real.
- Pausar, retomar e finalizar; conferir jornada sem barra fictícia.
- Forçar interrupção do bridge; confirmar recuperação sem abrir microfone.
- Descartar recuperação e resetar feira; conferir limpeza do público e presenter.
- Excluir sessão confirmada; conferir ausência no histórico e remoção de arquivos locais.
- Registrar limitações: sem validação física, sem modelo instalado, sem áudio real ou sem display.
