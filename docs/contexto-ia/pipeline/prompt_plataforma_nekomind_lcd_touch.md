# Prompt mestre — auditar e evoluir o NekoMind

## Papel e resultado esperado

Atue como equipe sênior de arquitetura, Python/FastAPI, JavaScript, firmware ESP32-S3,
qualidade e segurança. Trabalhe **no repositório NekoMind existente**; não crie um
segundo projeto e não reimplemente componentes que já estejam presentes.

Entregue uma evolução pequena, verificável e pronta para revisão, acompanhada de um
relatório que separe claramente:

- confirmado por inspeção de código;
- confirmado por teste automatizado;
- observado apenas em simulação;
- pendente de hardware, voz real ou validação humana.

## 1. Descoberta e sincronização segura

1. Localize a raiz pelo diretório `.git`; não dependa de um caminho absoluto de usuário.
2. Leia `README.md`, `backend/README.md`, `docs/README.md`,
   `docs/contexto-ia/pipeline/TECHNICAL_REFERENCE.md`, os contratos citados por eles e
   qualquer `AGENTS.md` aplicável.
3. Antes de sincronizar, execute `git status --short --branch`, identifique a branch e
   verifique o remoto. Nunca descarte trabalho local.
4. Execute `git fetch --prune origin`. Atualize `main` somente por
   `git pull --ff-only origin main` quando o working tree estiver limpo e não houver
   divergência local. Em qualquer outro caso, preserve os arquivos e registre o bloqueio.
5. Registre o SHA inicial, o SHA final e os commits incorporados.
6. Mapeie código, testes, CI, documentação, scripts, experimentos e artefatos. Trate
   relatórios antigos como evidência histórica, não como estado atual.

## 2. Fontes de verdade e ordem de precedência

Em caso de conflito, use esta ordem:

1. comportamento coberto por testes atuais e contratos públicos;
2. `docs/api_contract.md`, `docs/iot_protocol.md`, `docs/data_model.md`,
   `docs/privacy-retention.md` e documentação atual de execução;
3. código da `main`;
4. documentação histórica e este prompt.

Não invente endpoints, mensagens seriais, estados, dependências ou integrações. Se uma
informação não puder ser confirmada, marque-a como hipótese.

## 3. Invariantes do produto

- O backend e os painéis locais devem permanecer restritos a loopback por padrão.
- Não exponha tokens, transcrições privadas, áudio bruto, credenciais ou dados pessoais
  em URLs, logs, screenshots ou Git.
- Modo demo deve ser visível e nunca apresentado como execução real.
- ASR, termos, tópicos e métricas são sinais heurísticos; não comprovam domínio nem
  correção factual.
- Preserve correlação por `session_id`/`request_id`, ACK, timeout, deduplicação,
  idempotência e rejeição de eventos antigos onde esses contratos se aplicam.
- Preserve acessibilidade, escape de HTML e layouts 240×320, 320×240 e desktop.
- Não use rede ou serviços de nuvem sem requisito explícito. Falhas de serviços locais
  opcionais devem resultar em degradação clara, não em sucesso fictício.

## 4. Invariantes de hardware

Antes de modificar firmware, valide as decisões em
`docs/contexto-ia/pipeline/TECHNICAL_REFERENCE.md` e na implementação atual.

- Alvo: ESP32-S3, ILI9341 240×320 e XPT2046.
- Pinagem de referência: MOSI 11, SCK 12, MISO 13, CS display 10, DC 9, RST 8,
  CS touch 7 e IRQ touch 6.
- Backlight em 3V3; GPIO48 é reservado ao LED RGB e não pode ser usado como backlight.
- Preserve o driver funcional atual e o SPI compartilhado; drivers alternativos devem
  ficar isolados como experimento.
- Leitura touch não pode depender somente de IRQ; preserve calibração persistente,
  filtragem e temporização não bloqueante.
- Não use cartão SD nem apresente emulação ou compilação como validação física.

## 5. Auditoria obrigatória

Analise, no mínimo:

1. **Backend:** validação de entrada, transições de sessão, concorrência, timeouts,
   tratamento de erro, persistência, privacidade, integrações opcionais e compatibilidade.
2. **Frontend:** contrato de API, sanitização, acessibilidade, estados vazios/erro/demo,
   navegação por teclado, responsividade e consistência entre painel e display.
3. **Firmware/protocolo:** parsing limitado, limites de buffer, estados, watchdog,
   comunicação USB, touch, redraw e comportamento sem hardware.
4. **Testes/CI:** comandos realmente executáveis, testes determinísticos, lacunas em
   regressões críticas e diferença entre CI, host, emulador e placa real.
5. **Documentação/operação:** instalação reproduzível, comandos atuais, referências
   quebradas, números de testes desatualizados e instruções perigosas ou obsoletas.

Priorize achados como P0 (segurança/perda de dados), P1 (fluxo principal quebrado),
P2 (confiabilidade/UX relevante) ou P3 (manutenção/documentação). Para cada achado,
inclua evidência, impacto, reprodução e correção proposta.

## 6. Implementação

1. Escolha apenas melhorias sustentadas por evidência e dentro do escopo atual.
2. Preserve compatibilidade e faça mudanças pequenas e coesas.
3. Adicione ou ajuste testes de regressão antes ou junto da correção.
4. Não enfraqueça testes para obter resultado verde e não esconda exceções relevantes.
5. Não altere pinagem, protocolo, esquema persistente ou contrato público sem migração,
   documentação e teste de compatibilidade.
6. Não faça upload para placa, publicação, push, merge ou rotação de credenciais sem
   solicitação explícita.

## 7. Validação

Use os ambientes já configurados e os mesmos comandos da CI sempre que possível:

```powershell
cd backend
python -m pytest -q -rfEs -p no:cacheprovider
python -m ruff check app tests
cd ..
node --test frontend/tests/*.test.mjs
cd backend
python -m app.devtools.c_compiler
```

Quando disponíveis e seguros, execute também o pipeline virtual e o preflight sem placa.
Não instale dependências ou acione microfone/placa real silenciosamente. Se uma etapa não
puder rodar, informe o comando, o motivo e o que permanece sem validação.

## 8. Critérios de aceite

- `main` local sincronizada por fast-forward ou impedimento documentado sem perda de dados.
- Nenhuma regressão nos testes existentes.
- Todo bug corrigido possui teste de regressão proporcional.
- Nenhum segredo ou dado privado novo foi versionado.
- Modo real, demo, mock e simulação continuam distinguíveis.
- Documentação corrente descreve a `main`, não uma antiga branch de entrega.
- O relatório final lista arquivos alterados, comandos/resultados, riscos residuais e
  próximos passos, distinguindo software de validação física.

## 9. Formato da entrega

Apresente nesta ordem:

1. sincronização e baseline;
2. achados priorizados;
3. alterações implementadas e motivo;
4. testes executados com contagens e resultado;
5. pendências de hardware/voz/validação humana;
6. próximos passos curtos e ordenados por impacto.
