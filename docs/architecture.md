# Arquitetura — MVP touch + Mac

ESP32 com **display touch obrigatório** controla a sessão e apresenta avatar,
estados, resumo e nova tentativa. O microfone do **Mac** captura a explicação;
o Mac transcreve, extrai tópicos e persiste o resultado em SQLite. USB/serial
transporta comandos, confirmações, estados, métricas compactas e resultados JSON
Lines, sem áudio do ESP no caminho principal. Streamlit consulta o histórico; não
é gravador de navegador. As superfícies web novas são `/touch`, `/public` e
`/presenter`.

## Fluxo e fronteiras

Touch → controlador portátil C → transporte serial → bridge local no Mac →
microfone/arquivo PCM → API FastAPI em loopback → WAV validado → detector de fala
e qualidade → ASR local → extrator de tópicos → transação SQLite → resultado validado
→ touch/público/presenter.

A captura começa exclusivamente por comando iniciado no touch. O estado gravando
exige confirmação do stream no Mac. Pausa para o stream; retomar o reabre. Finalizar
para e fecha o arquivo antes de processamento. Silêncio não finaliza a sessão.
Tópicos e métricas heurísticas não comprovam acerto factual nem domínio de conteúdo.

## Componentes e ownership

- `backend/app/`: API, serviços, adaptadores, schemas, persistência e migração.
- `backend/app/mac/`: bridge serial, captura local, diário de solicitações e recuperação.
- `iot/nekomind_firmware/main/`: lógica portátil de sessão e limites de integração
  de placa. Escolha de placa/display/controladores/pinos permanece aberta.
- `frontend/web/`: touch emulador com controles/resultado essencial, painel público do
  Mac com evidências da jornada e presenter local reservado.
- `frontend/streamlit/`: histórico, tópicos, proveniência e estados; sem captura.

Uma instância do bridge controla uma captura. Executar backend com um worker, sem
reload durante sessões. Idempotência no banco protege criação e finalização;
a confirmação visual sozinha não evita repetição. O diário do bridge resolve reenvio
de comandos e reinícios incertos sem abrir captura automaticamente.

## Modos e privacidade

Demo permanece útil, offline e explicitamente identificado, inclusive quando recebe
silêncio. Real não pode trocar por mock em falhas. Cada etapa registra a origem
executada; origem incompleta/desconhecida não equivale a resultado integralmente real.
No modo feira, a projeção pública deriva fala detectada, duração, contagem de palavras e
etapas concluídas desses dados persistidos. A projeção não expõe a transcrição completa.
ASR usa cache lazy por configuração no mesmo processo. `local_keywords` é uma opção
explícita local/offline para tópicos: não é LLM, não é mock e não chama nuvem. Não
há chamada de IA remota ou credencial de API necessária ao processamento local.

Loopback é o limite operacional do MVP, sem promessa de isolamento entre usuários
locais. Não expor a API em rede. O backend gera `storage/operator-token` com modo
`0600`; rotas `/api/v1/sessions`, `/api/v1/audio`, `/api/v1/experience/presenter`,
`/commands`, `/bridge` e `/providers` exigem Bearer local. `/api/v1/experience/public`
é leitura pública local e não comanda a experiência. O reset por inatividade é agendado
no POST autenticado do bridge, durante heartbeat. O token fica apenas em memória no
presenter/touch emulador; Streamlit lê o arquivo local para histórico. Arquivos de
áudio, bancos, journals e token ficam locais e fora do Git; payloads de erro não devem
incluir gravações ou transcrições.

Por padrão `retain_raw_audio=false`; depois de transcrição e persistência bem-sucedidas,
o backend remove áudio bruto local da sessão. A propriedade `mac_directory` usa
`mac_data_dir` quando configurado ou `storage_dir.parent / "mac"` como padrão.

## Futuro e pendências

Microfone embarcado, Wi-Fi, autonomia sem Mac e serviços de IA em nuvem ficam fora
desta implementação. O antigo esboço I2S é histórico e não prova captura real.
Escolha de modelo ASR local e validação física do display Teknimas/ILI9341 têm gates
separados.
Ver [protocolo](iot_protocol.md), [dados](data_model.md),
[validação manual](manual-validation.md) e mapa de entrega.
