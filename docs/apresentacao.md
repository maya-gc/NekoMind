# Apresentação e vídeo — roteiro (macOS)

A apresentação e os vídeos são feitos no **Mac**. O Windows é usado para
desenvolver e gerar mídias (relatórios e capturas da pipeline).

## Na véspera

1. `git pull` na `main` e `bash scripts/test_auto.sh` — tudo verde.
   Confira também o selo do CI no README (Windows e macOS).
2. `bash scripts/test_auto.sh --repeticoes 10 --sem-placa` — taxa de sucesso
   para citar na banca (o relatório HTML mostra aprovadas/total por etapa).
3. `bash scripts/preparar_mac.sh` (com internet, uma vez): Python 3.12, voz
   Kokoro, Ollama + tutor `qwen2.5:7b`, transcrição e checklist. Depois disso
   tudo funciona **offline**.
4. Ensaio completo: `bash scripts/apresentar.sh` e o roteiro abaixo, duas vezes.
5. Grave o **vídeo reserva** (seção “Vídeo”) para o caso de o hardware falhar.

## Supervisor (dia inteiro no ar)

`scripts/apresentar.sh` / `scripts\apresentar.ps1` agora sobem tudo pelo
supervisor (`python -m app.devtools.supervisor`): Ollama, backend e bridge
são reiniciados sozinhos se caírem ou pararem de responder; os logs ficam em
`backend/storage/logs/` (girados a cada 5 MB) e o banco recebe backup no início
e no fim em `backend/storage/backups/` (últimos 10). Ctrl+C encerra tudo.
O checklist avisa se o computador estiver na bateria.

## Antes de subir ao palco (5 minutos)

```bash
bash scripts/apresentar.sh            # checklist + backend + bridge + telas
```

O checklist confere: Python e dependências, porta 8000, placa ESP (heartbeat e
desenho do LCD), microfone, modelo de transcrição, detector de fala, voz Kokoro,
Ollama (opcional) e disco. Se algo crítico falhar ele **para** e diz como resolver.

- Microfone ou modelo com problema → **plano B**: `bash scripts/apresentar.sh --plano-b`.
  A placa e as telas funcionam igual, os resultados aparecem marcados como
  **DEMO** (nunca apresentar como real).
- Placa sem resposta → aperte **RST** na placa, feche qualquer monitor serial e
  rode de novo. Se persistir, mostre o **vídeo reserva**.
- Sem som na sala → `--voz silent` (falas da gatinha só na tela).

Telas: `/presenter` no notebook (operador) e `/public` no projetor (plateia).

## Roteiro de 3 minutos

1. **Problema** (20 s): explicar em voz alta ajuda a aprender; a gatinha guia.
2. **Material** (20 s): no `/presenter`, cole um texto curto com 2 ideias e
   toque **Salvar e usar na próxima sessão**.
3. **Missão** (30 s): no LCD, **Diagnóstico** → **Pronto** → escolha a missão →
   **Começar** e explique só metade do conteúdo → **Finalizar**.
4. **Pergunta e dica** (40 s): a gatinha pergunta; toque **Pedir dica**.
5. **Segunda resposta** (40 s): **Responder**, complete a explicação, **Finalizar**.
6. **Comparação** (20 s): mostre a frase “Agora: … Antes, esse trecho não apareceu.”
   no LCD e a jornada no `/public`.
7. **Bastidores** (10 s): tudo local; mostre o relatório HTML da pipeline e o CI verde.

Frase de limite (dizer sempre): *a comparação mostra quais trechos do material
apareceram na fala; não é nota nem prova de domínio.*

## Vídeo (Mac)

- Grave a tela com **Cmd+Shift+5** (gravar tela inteira, microfone ligado) e o
  LCD com o celular em suporte, de cima. Junte lado a lado depois.
- Use o roteiro acima; mantenha **até 2 minutos**.
- Para cortes limpos de interface sem hardware, gere capturas automáticas:
  `bash scripts/test_auto.sh --sem-placa` → `pipeline/telas/*.png` (telas
  `/public` e `/touch` em cada etapa, prontas para slides ou GIF).
- Para um GIF rápido a partir das capturas (requer ffmpeg):
  `ffmpeg -framerate 1 -pattern_type glob -i 'telas/r1-guiado-*-public.png' -vf scale=960:-1 fluxo.gif`

## Perguntas prováveis da banca

| Pergunta | Resposta curta |
|---|---|
| A IA está na placa? | Não. A placa faz a interação (touch + tela); o computador processa localmente. Hipótese B (tudo no ESP) foi estudada e descartada para o MVP. |
| Funciona sem internet? | Sim, depois de baixar os modelos uma vez. |
| Como sabem que funciona? | CI em Windows e macOS, pipeline com 7 cenários e N repetições, bancada real; relatório HTML como evidência. |
| A comparação avalia conhecimento? | Não. É lexical e limitada ao material; está documentado. |
| E o microfone/alto-falante no dispositivo? | Hoje são os do computador; confirmar com a rubrica A3. |
