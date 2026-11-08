# Prompt mestre — Plataforma NekoMind LCD Touch

Você é uma pessoa engenheira sênior de firmware embarcado, interfaces touch, Python local, testes automatizados e integração ESP32–macOS. Sua tarefa é projetar e implementar uma plataforma de testes, controle e demonstração para o projeto **NekoMind — MVP touch + Mac**, usando obrigatoriamente o arquivo técnico fornecido como fonte primária de decisões de hardware e integração.

## 1. Entradas obrigatórias

Antes de alterar ou criar qualquer arquivo:

1. Leia integralmente o arquivo `TECHNICAL_REFERENCE.md` que esta no caminho "C:\Users\mayac\Desktop\esp32_lcd_test\TECHNICAL_REFERENCE.md".
2. Trate esse arquivo como a especificação técnica oficial do hardware atual.
3. Preserve as decisões marcadas como críticas, especialmente:
   - ESP32-S3-DevKitC-1;
   - display ILI9341 240×320;
   - touch resistivo XPT2046;
   - SPI compartilhado usando o objeto global `SPI`;
   - MOSI GPIO11;
   - SCK GPIO12;
   - MISO GPIO13;
   - CS do display GPIO10;
   - DC GPIO9;
   - RST GPIO8;
   - CS do touch GPIO7;
   - IRQ do touch GPIO6, mas sem depender exclusivamente dela;
   - backlight alimentado por 3V3;
   - GPIO48 reservado ao LED RGB da placa e proibido para backlight;
   - frequência SPI do display inicialmente limitada a 20 MHz;
   - driver próprio `ILI9341_Driver` como baseline;
   - `ts.isrWake = true` durante a leitura do touch;
   - calibração persistida em NVS;
   - redraw condicional para evitar flicker;
   - ArduinoLog 1.1.1;
   - XPT2046_Touchscreen na versão já validada no projeto;
   - PlatformIO;
   - `ARDUINO_USB_CDC_ON_BOOT=1`;
   - comentários e documentação em português do Brasil.

Não substitua TFT_eSPI automaticamente. A documentação informa que ele travou no `tft.begin()` neste hardware. Qualquer tentativa com TFT_eSPI, LovyanGFX ou outro driver deve ficar isolada em uma prova experimental, sem quebrar o caminho funcional baseado no driver próprio.

## 2. Objetivo principal

Criar uma plataforma local, em uma única pasta, para desenvolver, testar, calibrar, controlar e demonstrar o LCD touch do ESP32 junto ao NekoMind.

O projeto deve ficar inteiramente em:

```text
C:\Users\mayac\Desktop\high_level_projects
```

Não crie componentes fora dessa pasta. Não espalhe configurações, ambientes virtuais, scripts ou arquivos de teste em outros diretórios, exceto ferramentas globais já existentes no sistema.

A plataforma deve permitir:

- compilar o firmware;
- fazer upload para o ESP32;
- abrir monitor serial;
- diagnosticar display e touch;
- calibrar o touch;
- medir responsividade e latência;
- testar botões, áreas, gestos e arrasto;
- testar cores, fontes, sprites e animações;
- visualizar eventos recebidos do ESP32;
- enviar comandos de teste ao ESP32;
- emular o display e o touch sem hardware;
- controlar e demonstrar o fluxo NekoMind;
- integrar com o backend local do Mac quando essa parte estiver disponível;
- preservar modo demo e modo real explicitamente;
- gerar relatórios de diagnóstico legíveis.

## 3. Projeto visual e funcional

Mescle as melhores ideias dos projetos:

- DigiCat: mascote virtual kawaii, pixel art, expressões, animações e interação touch.
- TamaFi: pet com estados de vida, alimentação, felicidade, evolução, eventos e integração com conectividade.
- NekoMind: gatinho como controlador físico de uma sessão de explicação, com comunicação USB serial JSON Lines, estados de captura, processamento, resultado, erro, nova tentativa e privacidade.

O resultado não deve ser uma cópia superficial. Crie uma plataforma coerente chamada provisoriamente **NekoMind Touch Lab** ou **NekoMind LCD Control Center**, contendo:

1. Firmware do ESP32.
2. Aplicação local de controle e testes.
3. Emulador visual do LCD 240×320 e 320×240.
4. Protocolo serial JSON Lines.
5. Testes automatizados.
6. Documentação técnica.
7. Assets kawaii separados e licenciados corretamente.
8. Scripts de compilação, upload, monitoramento e diagnóstico.

O cartão SD não é necessário. O ESP32 permanecerá conectado ao computador, portanto:

- não implemente dependência de cartão SD;
- não use armazenamento no SD para imagens ou logs;
- mantenha assets pequenos no firmware quando necessário;
- mantenha dados, relatórios, imagens de teste e histórico no computador;
- use LittleFS ou NVS somente quando fizer sentido para configuração embarcada;
- não transforme o projeto em um dispositivo autônomo sem Mac neste MVP.

## 4. Contexto NekoMind

O NekoMind é um MVP no qual uma pessoa explica um assunto em voz alta e controla a sessão por um gatinho ESP32 com display touch obrigatório.

O microfone do Mac captura a fala. O Mac transcreve, extrai assuntos e armazena a sessão localmente. Tópicos e métricas heurísticas não comprovam correção factual nem domínio do conteúdo.

Fluxo principal:

```text
Touch ESP32
  → USB/serial JSON Lines
  → bridge no Mac
  → microfone do Mac
  → API loopback
  → WAV + WebRTC VAD/qualidade
  → ASR local
  → tópicos
  → SQLite
  → resultado validado
  → display touch
  → painel público
  → painel do apresentador
```

O firmware deve respeitar o protocolo e os estados já existentes na branch `feat/nekomind-touch-mac-mvp`, incluindo:

- `request_id`;
- ACKs;
- timeout;
- deduplicação;
- rejeição de mensagens antigas ou de outra sessão;
- nova tentativa deliberada;
- início, pausa, retomada e finalização;
- indicação de gravação apenas após o stream iniciar;
- encerramento da captura antes da avaliação;
- resultado somente para a sessão correta;
- mensagens explícitas de erro;
- modo demo identificado;
- painel público sem transcrição privada;
- termos reconhecidos pelo ASR, sem afirmar correção factual;
- limite visual de até cinco termos no emulador e até três no cartão compacto do firmware, quando a tela ainda não comportar mais.

Não invente integração real com o backend. Primeiro descubra os contratos existentes no repositório. Se o backend ainda não estiver presente nesta pasta, crie uma camada de adaptador e um mock claramente identificado, sem fingir que a integração real foi validada.

## 5. Touch resistivo responsivo

A prioridade técnica é transformar o touch resistivo em uma experiência suave, estável e sensível, inspirada no projeto:

```text
https://github.com/mboehmerm/Touch-Display-ili9341-320x240
```

Use esse projeto apenas como referência de configuração, desempenho e comparação entre drivers. Não copie configurações de pinos sem validar contra `TECHNICAL_REFERENCE.md`.

Implemente uma camada `TouchManager` robusta com:

- leitura por polling controlado;
- `ts.isrWake = true` antes das leituras, pois a IRQ atual não é confiável;
- transações SPI corretas;
- calibração de pelo menos quatro pontos, se o hardware permitir, mantendo compatibilidade com a calibração atual de dois pontos;
- persistência da calibração em NVS;
- inversão de eixos e rotação configuráveis;
- limites brutos configuráveis;
- filtragem de ruído;
- média móvel ou filtro exponencial configurável;
- rejeição de leituras fora de faixa;
- detecção de toque pressionado, movimento e soltura;
- debounce sem bloquear o loop;
- histerese para impedir tremor em botões;
- suporte a arrasto;
- suporte a gestos simples somente se não prejudicar os botões;
- timestamp monotônico dos eventos;
- medição de latência entre leitura e evento;
- taxa de amostragem configurável;
- modo bruto para diagnóstico;
- modo filtrado para uso normal;
- visualização dos pontos brutos e filtrados no emulador e no LCD;
- teste específico nos quatro cantos e no centro;
- relatório de precisão e dispersão;
- possibilidade de comparar diferentes filtros.

Não use `delay()` para fazer a interface parecer estável. Use `millis()` ou temporização não bloqueante.

Implemente uma estrutura semelhante a:

```cpp
struct TouchPoint {
    int16_t rawX;
    int16_t rawY;
    int16_t screenX;
    int16_t screenY;
    uint16_t pressure;
    bool touched;
    uint32_t timestampMs;
};

enum class TouchEventType {
    Press,
    Move,
    Release
};
```

A interface deve responder a um toque sem exigir que o usuário mantenha o dedo parado por muito tempo. Ao mesmo tempo, não deve disparar múltiplas ações por um único toque.

Crie testes automatizados para o algoritmo de calibração, mapeamento, filtro, debounce, eventos e áreas de botão. Deixe claro que testes simulados não comprovam a precisão física do touch.

## 6. Arquitetura obrigatória

Organize o projeto em uma única pasta raiz:

```text
C:\Users\mayac\Desktop\high_level_projects\nekomind-touch-platform\
├── README.md
├── TECHNICAL_REFERENCE.md
├── platformio.ini
├── include/
├── src/
├── lib/
├── firmware/
├── host/
├── app/
├── emulator/
├── assets/
├── tests/
├── scripts/
├── docs/
├── reports/
├── storage/
└── .vscode/
```

Se o usuário já fornecer um repositório NekoMind, preserve sua estrutura original e crie a plataforma como uma subestrutura coerente dentro da pasta raiz, sem duplicar backend ou frontend desnecessariamente.

Separe claramente:

- configuração de placa;
- driver LCD;
- driver touch;
- gerenciador de display;
- gerenciador touch;
- renderer portátil;
- máquina de estados da UI;
- protocolo serial;
- controle de sessão;
- diagnóstico;
- emulador;
- bridge do Mac;
- aplicação local;
- testes;
- assets.

O renderer deve ser independente da placa sempre que possível. Ele deve poder desenhar tanto no LCD físico quanto em um framebuffer usado pelo emulador.

## 7. Aplicação local

Crie uma aplicação local simples e de baixo custo. Prefira Python se isso reduzir complexidade. Pode usar uma interface web local, desktop simples ou uma combinação de CLI + web.

A aplicação deve oferecer uma tela inicial com:

- porta serial detectada;
- conexão atual;
- botão para conectar/desconectar;
- status do ESP32;
- modelo de display configurado;
- orientação;
- status de calibração;
- latência média do touch;
- taxa de eventos;
- últimos erros;
- botão para iniciar diagnóstico;
- botão para abrir o emulador;
- botão para iniciar a sessão NekoMind;
- botão para modo demo.

Inclua páginas ou abas para:

### Diagnóstico do hardware

- identificação do chip;
- memória e flash reportadas;
- estado do LED RGB;
- teste de cores;
- teste de texto;
- teste de primitivas gráficas;
- teste de rotação;
- teste de backlight;
- teste SPI;
- teste do XPT2046;
- calibração;
- teste de precisão;
- teste de responsividade;
- exportação de relatório.

### Touch Lab

- tela com grade de pontos;
- tela de arrasto;
- teste de círculos e linhas;
- visualização bruta versus filtrada;
- slider de suavização;
- seletor de filtro;
- ajuste de debounce;
- teste de latência;
- teste de pressão quando disponível;
- salvamento e restauração de calibração.

### UI Lab

- mostrar widgets;
- testar botões kawaii;
- testar cartões;
- testar barras;
- testar sprites;
- testar animações;
- testar telas 240×320 e 320×240;
- alternar orientação;
- validar overflow e legibilidade.

### NekoMind

- iniciar sessão;
- pausar;
- retomar;
- finalizar;
- reiniciar tentativa;
- mostrar estado no gatinho;
- mostrar eventos do protocolo;
- abrir painel público local;
- abrir painel do apresentador apenas quando autorizado;
- distinguir real e demo.

A aplicação deve funcionar sem hardware em modo emulador. O modo emulador não pode ser apresentado como validação física.

## 8. Interface do gatinho

Crie uma UI kawaii, mas legível em 240×320 e 320×240.

Estados mínimos:

```text
BOOT
DIAGNOSTIC
CALIBRATION
IDLE
READY
LISTENING
PAUSED
PROCESSING
RESULT
ERROR
RETRY
SETTINGS
PET_STATUS
```

O gatinho deve ter:

- rosto grande;
- expressão para cada estado;
- botões touch grandes;
- feedback visual imediato ao pressionar;
- animação de espera;
- animação de processamento;
- animação de sucesso;
- animação de erro sem assustar o usuário;
- tela de resultado com dois cartões;
- até cinco termos reconhecidos no modo emulador;
- até três termos no cartão compacto do firmware se necessário;
- texto `Termos reconhecidos pelo NekoMind`;
- nunca apresentar termos como prova de acerto ou domínio;
- indicação clara de demo quando for demo.

Use sprites e bitmaps pequenos. Não dependa de cartão SD. Caso os assets sejam gerados ou convertidos, inclua o script de conversão e uma licença ou origem documentada.

## 9. Protocolo serial

Use USB serial com JSON Lines, respeitando os contratos existentes.

Cada mensagem deve:

- ocupar uma linha;
- ter tipo de mensagem;
- conter `request_id` quando for comando;
- conter `session_id` quando aplicável;
- permitir ACK;
- permitir erro estruturado;
- permitir correlação de resposta;
- rejeitar mensagens de sessão antiga;
- ser deduplicável;
- ter timeout;
- ser registrada sem dados privados desnecessários.

Exemplo de comando:

```json
{"type":"session_start","request_id":"req-123","session_id":"sess-456","mode":"demo"}
```

Exemplo de evento de touch:

```json
{"type":"touch_event","event":"press","x":118,"y":204,"raw_x":1870,"raw_y":2930,"timestamp_ms":123456}
```

Exemplo de ACK:

```json
{"type":"ack","request_id":"req-123","ok":true}
```

Não invente nomes incompatíveis se já houver um contrato existente. Inspecione o código e a documentação antes de criar novos tipos.

## 10. Segurança e privacidade

- Não exponha o backend fora de `127.0.0.1`.
- Não coloque tokens em URL, logs ou Git.
- Não grave áudio bruto por padrão.
- Não envie dados para a nuvem.
- Não inclua chaves secretas.
- Não confunda dados demo com dados reais.
- Não mostre a transcrição completa no painel público.
- Não alegue correção factual.
- Não declare validação física quando somente testes simulados foram executados.
- Mantenha storage, relatórios e arquivos temporários dentro da pasta do projeto.

## 11. Testes e critérios de aceite

Crie testes automatizados para:

- compilação;
- parser JSON Lines;
- comandos e ACKs;
- timeout;
- deduplicação;
- rejeição de sessão antiga;
- máquina de estados;
- calibração;
- mapeamento de coordenadas;
- filtro de touch;
- debounce;
- press/move/release;
- áreas de botão;
- rotação;
- layout 240×320;
- layout 320×240;
- overflow de texto;
- limite de termos;
- modo demo;
- persistência;
- relatórios de diagnóstico;
- emulador;
- bridge local.

Critérios de aceite:

1. Tudo fica dentro de `C:\Users\mayac\Desktop\high_level_projects`.
2. O firmware compila com PlatformIO.
3. O caminho original de driver ILI9341 continua disponível.
4. O GPIO48 não é usado como backlight.
5. O touch é lido mesmo quando a IRQ não dispara.
6. O touch possui calibração persistente.
7. Um toque único gera apenas uma ação.
8. Arrasto funciona sem tremor excessivo.
9. O display não pisca durante a interação normal.
10. O emulador funciona sem hardware.
11. O modo demo é identificável.
12. O protocolo possui ACK, timeout e deduplicação.
13. O NekoMind pode iniciar, pausar, retomar, finalizar e exibir erro.
14. O resultado final não promete correção factual.
15. Existe documentação de hardware ainda não confirmado.
16. Existe um relatório separando testes simulados de validação física.

## 12. Procedimento de execução

Antes de implementar:

1. Inspecione os arquivos existentes.
2. Liste a estrutura atual.
3. Leia `TECHNICAL_REFERENCE.md`.
4. Leia documentação do NekoMind.
5. Localize os contratos de protocolo.
6. Localize os testes existentes.
7. Verifique se DigiCat, TamaFi ou assets relacionados estão presentes.
8. Não copie código sem verificar licença.
9. Produza um plano curto de migração.

Durante a implementação:

1. Preserve o caminho funcional existente.
2. Faça alterações pequenas e testáveis.
3. Execute testes após cada etapa.
4. Não altere pinagem crítica sem justificativa.
5. Não troque de driver LCD sem experimento isolado.
6. Registre decisões em `docs/decisions.md`.
7. Registre riscos em `docs/risks.md`.
8. Mantenha `TECHNICAL_REFERENCE.md` atualizado quando uma hipótese for confirmada ou rejeitada.

Ao finalizar:

1. Execute todos os testes automatizados disponíveis.
2. Compile o firmware.
3. Verifique a árvore de arquivos.
4. Verifique se nenhum arquivo saiu da pasta raiz.
5. Gere um relatório em `reports/implementation-report.md`.
6. Liste o que foi validado por software.
7. Liste o que exige validação física.
8. Liste como conectar a placa sem assumir porta serial fixa.
9. Liste comandos de execução no Windows PowerShell.
10. Não diga que o touch está fisicamente validado sem teste na unidade real.

## 13. Restrições importantes

- Não usar cartão SD.
- Não usar nuvem.
- Não exigir microfone no ESP32.
- Não substituir o Mac pelo ESP32 neste MVP.
- Não modificar pinos críticos sem justificativa.
- Não usar GPIO48 para backlight.
- Não depender da IRQ do XPT2046.
- Não usar `delay()` no fluxo interativo.
- Não desenhar a tela inteira em todo loop.
- Não copiar assets com licença desconhecida.
- Não inventar recursos não implementados.
- Não apresentar simulação como validação física.
- Não remover testes existentes.
- Não apagar documentação ou relatórios existentes.
- Não criar arquivos fora de `C:\Users\mayac\Desktop\high_level_projects`.

## 14. Resultado esperado

Entregue uma plataforma funcional e organizada, não apenas um exemplo de tela.

O resultado deve permitir que a usuária conecte o ESP32 ao computador, escolha a porta, execute diagnóstico, calibre o touch, teste a sensibilidade, visualize o LCD em um emulador, experimente uma interface kawaii e rode uma sessão NekoMind sem precisar alterar manualmente muitos arquivos.

A prioridade é:

```text
confiabilidade do hardware
→ touch suave
→ protocolo estável
→ plataforma de testes
→ UI kawaii
→ integração NekoMind
→ otimizações futuras
```

Sempre explique as decisões técnicas em português claro, informe limitações e diferencie explicitamente:

- confirmado por código;
- confirmado por teste automatizado;
- observado em simulação;
- pendente de validação física.
