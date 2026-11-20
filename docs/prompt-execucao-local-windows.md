# Prompt operacional — iniciar o NekoMind no Windows

Trabalhe no repositório NekoMind existente e deixe a aplicação pronta para uso com a
placa ESP32-S3 conectada. Não considere o trabalho concluído apenas porque processos
foram iniciados: valide saúde, comunicação e interfaces visíveis.

## Procedimento

1. Confirme que a `main` local está sincronizada, sem descartar mudanças locais.
2. Leia `README.md`, `docs/execution.md`, `docs/day-of-rehearsal.md` e os scripts de
   inicialização. Use o fluxo oficial do projeto, sem duplicar serviços manualmente.
3. Verifique se as portas HTTP necessárias estão livres e detecte a porta serial por
   VID/PID/nome; nunca assuma `COM3` sem conferir.
4. Execute o preflight em modo real para backend, dependências, microfone, ASR, voz,
   Ollama e placa. Se um item opcional falhar, use a degradação documentada e informe-a.
5. Não grave firmware automaticamente. Compile/flash somente se o diagnóstico indicar
   firmware ausente/incompatível ou se houver solicitação explícita; antes, confirme a
   porta exata e preserve a configuração existente.
6. Inicie o supervisor oficial com backend, bridge físico, tutor local e voz. Mantenha
   os processos vivos em segundo plano e registre PID/logs para encerramento posterior.
7. Valide por HTTP, no mínimo: `/api/v1/health`, `/public`, `/touch` e `/presenter`.
   Confirme que o serviço escuta apenas em `127.0.0.1`.
8. Abra as interfaces no navegador e confira visualmente que carregaram, que o modo
   real/demo está corretamente identificado e que não há erro bloqueante.
9. Confirme nos logs que a bridge abriu a porta serial correta e que não há loop de
   reinício. Não inicie uma sessão nem acione o microfone sem necessidade para o teste
   de prontidão.

## Critérios de aceite

- ESP32 detectado e bridge conectada na porta correta.
- Backend saudável em loopback.
- Painel do apresentador, painel público e emulador touch carregados.
- Tutor/voz disponíveis ou degradação explícita e não bloqueante.
- Processos permanecem ativos após a validação, com logs e forma clara de encerrá-los.
- Nenhum segredo, token ou transcrição é exposto em URL, log ou resposta final.
- A entrega informa URLs, estado da placa, modo real/demo, limitações e comando de parada.
