# Arquitetura — MVP touch + Mac

ESP32 com **display touch obrigatório** controla a sessão e apresenta avatar,
estados, resumo e nova tentativa. O microfone do **Mac** captura a explicação;
o Mac transcreve, extrai tópicos e persiste o resultado em SQLite. USB/serial
transporta comandos e respostas JSON Lines, sem áudio do ESP no caminho principal.
Streamlit consulta o histórico; não é gravador de navegador.

## Fluxo e fronteiras

Touch → controlador portátil C → transporte serial → bridge local no Mac →
microfone/arquivo PCM → API FastAPI em loopback → WAV validado → detector de fala →
ASR local → extrator de tópicos → transação SQLite → resultado validado → touch.

A captura começa exclusivamente por comando iniciado no touch. O estado gravando
exige confirmação do stream no Mac. Pausa para o stream; retomar o reabre. Finalizar
para e fecha o arquivo antes de processamento. Silêncio não finaliza a sessão.
Tópicos e métricas heurísticas não comprovam acerto factual nem domínio de conteúdo.

## Componentes e ownership

- `backend/app/`: API, serviços, adaptadores, schemas, persistência e migração.
- `backend/app/mac/`: bridge serial, captura local, diário de solicitações e recuperação.
- `iot/nekomind_firmware/main/`: lógica portátil de sessão e limites de integração
  de placa. Escolha de placa/display/controladores/pinos permanece aberta.
- `frontend/streamlit/`: histórico, tópicos, proveniência e estados; sem captura.

Uma instância do bridge controla uma captura. Executar backend com um worker, sem
reload durante sessões. Idempotência no banco protege criação e finalização;
a confirmação visual sozinha não evita repetição. O diário do bridge resolve reenvio
de comandos e reinícios incertos sem abrir captura automaticamente.

## Modos e privacidade

Demo permanece útil, offline e explicitamente identificado, inclusive quando recebe
silêncio. Real não pode trocar por mock em falhas. Cada etapa registra a origem
executada; origem incompleta/desconhecida não equivale a resultado integralmente real.
ASR usa cache lazy por configuração no mesmo processo. Não há chamada de IA remota
ou credencial de API necessária ao processamento local.

Loopback é o limite operacional do MVP, sem promessa de isolamento entre usuários
locais. Não expor a API em rede. Arquivos de áudio, bancos e journals ficam locais e
fora do Git; payloads de erro não devem incluir gravações ou transcrições. Processos
recebem dados somente durante a sessão solicitada. Mac deve permanecer ligado e
sem suspensão. Permissão de microfone e driver físico têm validação separada.

## Futuro e pendências

Microfone embarcado, Wi-Fi, autonomia sem Mac e serviços de IA em nuvem ficam fora
desta implementação. O antigo esboço I2S é histórico e não prova captura real.
Escolha de modelo/provedor e refinamento semântico do extrator têm decisão separada.
Ver [protocolo](iot_protocol.md), [dados](data_model.md),
[validação manual](manual-validation.md) e mapa de entrega.
