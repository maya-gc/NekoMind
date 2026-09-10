# NekoMind — MVP touch + Mac

A pessoa explica um assunto em voz alta e controla a sessão por um gatinho ESP32
com **display touch obrigatório**. O microfone do **Mac** captura; o Mac transcreve,
extrai assuntos e armazena a sessão localmente. Tópicos e métricas heurísticas não
comprovam correção factual nem domínio do conteúdo.

Implementação de software e testes automatizados disponíveis nesta branch.
**Ainda não validado fisicamente**: placa, display, controlador de toque, pinos e
transporte USB físico precisam ser escolhidos e integrados. Os hooks de placa retornam
indisponibilidade explícita. ASR real, microfone real e calibração permanecem pendentes.
O extrator `local_keywords` é um candidato funcional **opt-in**, cuja adoção ainda
precisa de decisão; não representa escolha aprovada de modelo/provedor.

## Fluxo

Touch → USB/serial JSON Lines → bridge Mac → microfone Mac → API loopback →
WAV + WebRTC VAD → ASR → tópicos → SQLite → resultado validado → touch.

A indicação de gravação depende de o stream ter iniciado. Pausa fecha o microfone;
retomar reabre; finalizar encerra captura antes de avaliar. Somente resultado concluído
da sessão correta produz conclusão. Há deduplicação, timeout, erro e nova tentativa.
Streamlit consulta histórico e oferece demo identificada; não grava pelo navegador.
Microfone embarcado, Wi-Fi e autonomia sem Mac são possibilidades futuras.

## Instalação no macOS

Requer Python3.11+ (testado com3.12), Git e compilador C para os testes portáteis.
Na raiz do repositório:

```bash
PYTHON_BIN=python3.12 bash scripts/setup_backend.sh
backend/.venv/bin/python -m pip install -r backend/requirements-mac.txt
cp -n backend/.env.example backend/.env  # preservar configuração existente
bash scripts/run_backend.sh
```

O backend escuta `127.0.0.1:8000`, com **um worker e sem reload**. Não expor em rede.
Para o bridge, em outro terminal:

```bash
cd backend
.venv/bin/python -m serial.tools.list_ports
.venv/bin/python -m sounddevice  # listar dispositivos; não grava
.venv/bin/python -m app.mac --port /dev/cu.PORTA_ESCOLHIDA
# Opcional: --device 'nome do microfone' --data-dir ./storage/mac
```

A porta acima é um placeholder; depende do hardware. Não abrir duas instâncias com
a mesma porta/diretório. Após escolher o dispositivo, permitir microfone ao app de
terminal que executa Python em **Ajustes do Sistema → Privacidade e Segurança →
Microfone**. Se negado, a captura falha e o touch permite tentar novamente após corrigir.
Nenhum áudio é capturado antes de um comando de início. O bridge usa `caffeinate`;
manter Mac ligado, tampa aberta e sem suspensão manual durante a sessão.

## Demo e real

O padrão é `NEKOMIND_MODE=demo`, ASR e extração `mock`. Sem modelo nem chave;
o teste demo com silêncio continua disponível e identificado em cada resultado.
O bridge real de captura pode operar em demo, mas a análise resultante é simulada.

Para ensaiar processamento real local depois da decisão do extrator:

```bash
backend/.venv/bin/python -m pip install -r backend/requirements-real.txt
```

Configurar `backend/.env`: `NEKOMIND_MODE=real`, `NEKOMIND_ASR_PROVIDER=faster_whisper`,
`NEKOMIND_ASR_MODEL_SIZE=/caminho/absoluto/modelo-ctranslate2`, dispositivo `cpu`,
compute_type `int8` e, **se adotado**, `NEKOMIND_LLM_PROVIDER=local_keywords`.
Esses parâmetros são configuráveis, não um benchmark ou recomendação de modelo validada.
O modelo precisa ser preparado localmente pelo operador: `local_files_only=True`
impede download automático. Não há chamada de IA remota nem chave necessária.
Configuração desconhecida, modelo ausente, áudio sem fala ou extração inválida geram
falha explícita, sem fallback. Reiniciar processos após ajustar configuração.

O extrator lexical usa frases literalmente presentes na transcrição, sem lista fixa,
com máximo de8 tópicos e sem preenchimento artificial. Não faz validação factual;
a qualidade semântica e a decisão entre este método/modelo/API continuam abertas.

## Testes

```bash
backend/.venv/bin/python -m pip install -r backend/requirements-test.txt
cd backend
.venv/bin/python -m pytest -q
.venv/bin/python -m unittest discover -s tests -p test_asr_lifecycle.py -v
cd ..
bash iot/nekomind_firmware/scripts/test_firmware.sh
backend/.venv/bin/python -m ruff check backend/app backend/tests
```

Os testes usam microfone/modelos substitutos, SQLite temporário e uma PTY real do
sistema para transporte. VAD instalado é exercitado com silêncio/ruído sintéticos;
fala/níveis/pausas também usam substitutos conforme [método](docs/speech-validation.md).
Nenhum teste sintético comprova touch, voz ou Whisper físicos. Para Streamlit e seus
testes, ver [frontend](frontend/streamlit/README.md).

## Dados, recuperação e documentação

Áudio, SQLite, backups e journal ficam em `backend/storage/`, fora do Git. O journal
precisa ser preservado para reconhecer retransmissões. Reinício durante captura gera
erro, nunca reabre o microfone automaticamente. Reinício do backend marca sessões
incompletas como interrompidas. Falhas de captura não viram notas sobre conhecimento.
A migração é aditiva com backup SQLite consistente; ver rollback antes de usar banco
existente. Não há política automática de retenção: limpar dados locais só deliberadamente.

- [Mapa NM-001 a NM-007 e evidências](docs/delivery.md)
- [Arquitetura](docs/architecture.md) · [API](docs/api_contract.md)
- [USB/serial e estados](docs/iot_protocol.md) · [Dados e migração](docs/data_model.md)
- [ASR: cache e medição](docs/asr-model-lifecycle.md) · [VAD](docs/speech-validation.md)
- [Teste real na mesa](docs/manual-validation.md) · [Fontes](docs/implementation-sources.md)
