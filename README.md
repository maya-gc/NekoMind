# NekoMind — MVP touch + Mac

A pessoa explica um assunto em voz alta e controla a sessão por um gatinho ESP32
com **display touch obrigatório**. O microfone do **Mac** captura; o Mac transcreve,
extrai assuntos e armazena a sessão localmente. Tópicos e métricas heurísticas não
comprovam correção factual nem domínio do conteúdo.

Implementação de software e testes automatizados disponíveis nesta branch. Para a
unidade conectada, a referência da branch `pipeline` identifica ESP32-S3 com LCD
ILI9341 240×320 e touch XPT2046. O firmware agora inclui drivers SPI e USB/serial
para essa pinagem; [ligações, build e calibração](docs/esp32-s3-display-touch.md).
O build e o flash ESP-IDF passaram; após RST/EN, a pessoa na bancada confirmou que
o gatinho aparece sem piscar. O touch físico foi calibrado. O fluxo completo de
controles passou primeiro em demo: Diagnóstico → Começar → Pausar → Retomar →
Finalizar → resultado identificado como demo → Nova tentativa. Em 21/09/2026,
também passou uma sessão **real** na unidade conectada: diagnóstico pronto,
captura de voz humana iniciada e finalizada pelo LCD, ASR local, tópicos locais e
conclusão correlacionada no LCD e no painel público do Mac. O resultado foi
persistido com origem real em todas as etapas. A avaliação acústica com diferentes
vozes, distâncias, ruídos e pausas ainda precisa de ensaios adicionais.
O extrator `local_keywords` agora é uma opção explícita aceita para execução local
offline; ele não é LLM, não é mock, não chama nuvem e não prova domínio do assunto.

## Fluxo

Touch → USB/serial JSON Lines → bridge Mac → microfone Mac → API loopback →
WAV + WebRTC VAD/qualidade → ASR → tópicos → SQLite → resultado validado → touch,
painel público e painel do apresentador.

No modo feira, o display do gatinho resume a conclusão em dois cartões: prova curta
de captura/processamento e até cinco termos reconhecidos. A tela pública do Mac mostra
a jornada, duração, contagem de palavras e origem local para a plateia acompanhar o
funcionamento. A transcrição completa continua privada e nenhuma dessas evidências
é apresentada como nota ou prova de domínio. Os termos refletem o que o ASR local
reconheceu e podem divergir da fala quando o modelo ou a captação forem insuficientes.

A indicação de gravação depende de o stream ter iniciado. Pausa fecha o microfone;
retomar reabre; finalizar encerra captura antes de avaliar. Somente resultado concluído
da sessão correta produz conclusão. Há deduplicação, timeout, erro e nova tentativa.
Streamlit consulta histórico e oferece demo identificada; não grava pelo navegador.
As rotas web novas são `/touch` (emulador autorizado), `/public` (somente leitura,
sem token) e `/presenter` (reservado ao operador). Microfone embarcado, Wi-Fi e
autonomia sem Mac são possibilidades futuras.

## Resultado visual para apresentação

A informação foi distribuída entre o gatinho e o Mac para manter o display pequeno
legível e, ao mesmo tempo, deixar o funcionamento visível para a plateia:

- **Gatinho/display:** preserva o rosto, os estados e os controles grandes. Ao final,
  mostra dois cartões: uma confirmação curta de que houve fala e processamento e os
  termos reconhecidos. O emulador limita a lista a cinco termos; o renderer portátil
  do firmware agrupa até três no cartão compacto enquanto fonte e espaçamento ainda
  dependem da validação no módulo físico.
- **Painel público do Mac:** mostra captura, transcrição, extração e persistência,
  com duração, quantidade de palavras reconhecidas e origem local. Ele serve como
  evidência visual de que o fluxo percorreu as etapas, sem expor a transcrição.
- **Resultado honesto:** a tela diz `Termos reconhecidos pelo NekoMind`, pois o ASR
  pode divergir da fala. Conversas genéricas podem resultar em lista vazia; o sistema
  não completa uma quantidade fixa nem apresenta os termos como prova de acerto.
- **Modo demo:** continua disponível e sempre identificado. Dados simulados não são
  exibidos como resultado real.

Evidências inspecionadas no navegador: [display 320×240](ScreenshotsToCloseLoop/runs/presentation-evidence/touch-proof-320x240.jpg),
[termos no display](ScreenshotsToCloseLoop/runs/presentation-evidence/touch-terms-320x240.jpg)
e [painel público 1440×900](ScreenshotsToCloseLoop/runs/presentation-evidence/public-proof-1440x900.jpg).

## Status consolidado da branch

A branch `feat/nekomind-touch-mac-mvp` contém as melhorias NM-001 a NM-019 e os
ajustes encontrados durante os ensaios locais. A matriz detalhada por requisito está
no [relatório final](docs/final-report.md).

| Área | Entregue no software |
|---|---|
| Sessão e protocolo | Resultado correlacionado por sessão, comandos com `request_id`, ACKs, timeout, deduplicação, nova tentativa deliberada e rejeição de mensagens antigas ou de outra sessão. |
| Captura no Mac | Iniciar, pausar, retomar e finalizar alteram a captura real; diagnóstico de permissão/dispositivo, calibração, recuperação após interrupção e prevenção de suspensão com `caffeinate`. |
| Transcrição e fala | Cache lazy do faster-whisper por configuração, cleanup no encerramento, português preservado, WAV validado, WebRTC VAD, nível e clipping antes da análise. |
| Real e demonstração | Provedores explícitos, falha clara para configuração indisponível e origem efetivamente usada persistida e exibida; qualquer etapa simulada identifica a sessão como demo. |
| Assuntos | Extração lexical local ancorada na transcrição, sem lista fixa, fallback mock ou preenchimento artificial; remoção de termos genéricos, duplicatas e limite visual. |
| Dados e privacidade | Migração SQLite aditiva, jornada persistida, retenção configurável, remoção de áudio bruto, exclusão confirmada, tombstones e limpeza de recibos sem conteúdo privado. |
| Experiência da feira | Avatar e estados, touch/emulador, painel público somente leitura, painel do apresentador protegido por token local, histórico, assunto corrigível e resultado compacto em duas telas. |
| Firmware e protótipo | Controlador de sessão, parser JSON Lines, eventos de toque e layouts portáteis; drivers ILI9341/XPT2046 e USB Serial/JTAG específicos do ESP32-S3 conectado. |

Ajustes confirmados durante QA incluem: aguardar a janela real de calibração;
criar o diretório de captura no primeiro uso; não gravar bytes durante a pausa;
preservar e exibir `ended_at`; iniciar o diagnóstico real depois de validar o token;
posicionar mensagens de token dentro do diálogo; distinguir recuperação ainda não
consultada; usar confirmações acessíveis na página; corrigir overflow, botões e
paginação em 240×320 e 320×240; e reduzir resultados de até onze cartões para dois.

Validação atual: **187 testes de backend**, **28 testes web**, **6 testes do
Streamlit** e **23 casos C portáteis** aprovados. Os gates de evidência do navegador
e de assets passaram com 11 e 5 checks, respectivamente. Faster-whisper e microfone
do Mac foram exercitados com voz sintetizada local. O build ESP-IDF v5.3.1 e a
gravação USB da unidade ESP32-S3 foram executados nesta etapa; gatinho estável,
toques, botões e controle da captura pelo Mac foram confirmados na bancada em
modo demo. Uma sessão integralmente real com fala humana foi concluída no hardware
e conferida no SQLite e em `/public`; isso valida o percurso, mas ainda não mede
acurácia de transcrição, precisão dos termos nem robustez acústica.

## Instalação no macOS

Requer Python 3.11+ (testado com 3.12), Git e compilador C para os testes portáteis.
Na raiz do repositório:

```bash
PYTHON_BIN=python3.12 bash scripts/setup_backend.sh
backend/.venv/bin/python -m pip install -r backend/requirements-mac.txt
cp -n backend/.env.example backend/.env  # preservar configuração existente
bash scripts/run_backend.sh
```

O backend escuta `127.0.0.1:8000`, com **um worker e sem reload**. Não expor em rede.
No startup ele cria `backend/storage/operator-token` com permissão `0600`; use esse
valor apenas em memória no presenter/touch emulador, nunca em URL, log ou Git.
Para o bridge, em outro terminal:

```bash
cd backend
.venv/bin/python -m serial.tools.list_ports
.venv/bin/python -m sounddevice  # listar dispositivos; não grava
.venv/bin/python -m app.mac --port /dev/cu.PORTA_ESCOLHIDA
# Opcional: --device 'nome do microfone' --data-dir ./storage/mac
# Demo operacional sem serial/microfone físico: .venv/bin/python -m app.mac --simulate
```

A porta acima é um placeholder; depende do hardware. Não abrir duas instâncias com
a mesma porta/diretório. Após escolher o dispositivo, permitir microfone ao app de
terminal que executa Python em **Ajustes do Sistema → Privacidade e Segurança →
Microfone**. Se negado, a captura falha e o touch permite tentar novamente após corrigir.
No modo real, aceitar um token local válido enquanto a experiência está no início
dispara o diagnóstico do microfone automaticamente. O macOS mostra o pedido de
permissão somente quando a decisão ainda está pendente; se a permissão já foi concedida,
o diagnóstico segue direto para o estado pronto sem repetir a janela do sistema.
Nenhum áudio é capturado antes de um comando de início. O bridge usa `caffeinate`;
manter Mac ligado, tampa aberta e sem suspensão manual durante a sessão.

## Demo e real

O padrão é `NEKOMIND_MODE=demo`, ASR e extração `mock`. Sem modelo nem chave;
o teste demo com silêncio continua disponível e identificado em cada resultado.
O bridge real de captura pode operar em demo, mas a análise resultante é simulada.

Para ensaiar processamento real local com o extrator lexical explícito:

```bash
backend/.venv/bin/python -m pip install -r backend/requirements-real.txt
```

Configurar `backend/.env`: `NEKOMIND_MODE=real`, `NEKOMIND_ASR_PROVIDER=faster_whisper`,
`NEKOMIND_ASR_MODEL_SIZE=/caminho/absoluto/modelo-ctranslate2`, dispositivo `cpu`,
compute_type `int8` e `NEKOMIND_LLM_PROVIDER=local_keywords` se a análise lexical
offline for a opção desejada. Esses parâmetros são configuráveis, não um benchmark
ou recomendação de modelo validada. O modelo ASR precisa ser preparado localmente
pelo operador: `local_files_only=True` impede download automático. Não há chamada
de IA remota nem chave necessária.
Configuração desconhecida, modelo ausente, áudio sem fala ou extração inválida geram
falha explícita, sem fallback. Reiniciar processos após ajustar configuração.

O extrator lexical usa frases literalmente presentes na transcrição, sem lista fixa,
remove preenchimentos conversacionais e duplicatas contidas em termos maiores, com
máximo de cinco tópicos e sem preenchimento artificial. Não faz validação factual;
a qualidade semântica precisa ser avaliada na bancada. Substituir esse método por
outro modelo ou API é uma decisão futura; nenhuma API de nuvem foi acionada.

## Testes

```bash
backend/.venv/bin/python -m pip install -r backend/requirements-test.txt
cd backend
.venv/bin/python -m pytest -q
.venv/bin/python -m unittest discover -s tests -p test_asr_lifecycle.py -v
cd ..
bash iot/nekomind_firmware/scripts/test_firmware.sh
node --test frontend/tests/*.test.mjs
python3 -m pytest frontend/streamlit/tests -q
backend/.venv/bin/python -m ruff check backend/app backend/tests
```

Os testes usam microfone/modelos substitutos, SQLite temporário e uma PTY real do
sistema para transporte. VAD instalado é exercitado com silêncio/ruído sintéticos;
fala/níveis/pausas também usam substitutos conforme [método](docs/speech-validation.md).
Nenhum teste sintético comprova touch, voz ou Whisper físicos. Para Streamlit e seus
testes, ver [frontend](frontend/streamlit/README.md).

## Dados, recuperação e documentação

Áudio, SQLite, backups e journal ficam em `backend/storage/`, fora do Git. Por padrão
`NEKOMIND_RETAIN_RAW_AUDIO=false`: depois de transcrição e persistência bem-sucedidas,
o backend remove áudio bruto referenciado da sessão; exclusão confirmada remove sessão,
chunks, temporários, transcrição, tópicos e métricas do escopo local conhecido. Cópias
externas e backups feitos fora desse diretório continuam responsabilidade do operador.
O journal precisa ser preservado para reconhecer retransmissões. Reinício durante
captura gera recuperação, nunca reabre o microfone automaticamente.

- [Entrega e evidências](docs/delivery.md)
- [Status pronto para Notion — 11/09/2026](docs/notion-status-2026-09-11.md)
- [Relatório final](docs/final-report.md) · [QA e incidente de banco](docs/qa-report.md)
- [Arquitetura](docs/architecture.md) · [API](docs/api_contract.md)
- [USB/serial e estados](docs/iot_protocol.md) · [Dados e migração](docs/data_model.md)
- [ASR: cache e medição](docs/asr-model-lifecycle.md) · [VAD](docs/speech-validation.md)
- [Hardware Teknimas/ILI9341](docs/hardware-teknimas-ili9341.md) · [Modo feira](docs/feira-mode.md)
- [Painéis](docs/panels.md) · [Privacidade](docs/privacy-retention.md)
- [Ensaio para apresentação](docs/day-of-rehearsal.md) · [Teste real na mesa](docs/manual-validation.md) · [Checklist manual](docs/manual-checklist.md)
